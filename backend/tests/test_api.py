"""API end to end with a temp SQLite DB and the sample PDFs (EXTRACTOR=text)."""

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from app.scoring.buyer_profile import compute_profile

from .conftest import OUT


@pytest.fixture()
def client(tmp_path, monkeypatch, ground_truth):
    monkeypatch.setenv("VYAPAARIQ_DB", str(tmp_path / "t.db"))
    monkeypatch.setenv("EXTRACTOR", "text")
    monkeypatch.setenv("VYAPAARIQ_TODAY", "2026-11-23")
    from app import services
    from app.db import session

    monkeypatch.setattr(services, "UPLOAD_DIR", tmp_path / "uploads")
    session.reset_engine()
    from app.main import app

    with TestClient(app) as c:
        yield c
    session.reset_engine()


def _files(pkg: str):
    return [("files", (p.name, p.read_bytes(), "application/pdf")) for p in sorted((OUT / pkg).glob("*.pdf"))]


def _upload_and_process(client, pkg):
    r = client.post("/api/packages", files=_files(pkg))
    assert r.status_code == 201, r.text
    pid = r.json()["id"]
    r = client.post(f"/api/packages/{pid}/process")
    assert r.status_code == 200, r.text
    return r.json()["invoice_id"]


def test_health(client):
    r = client.get("/api/health").json()
    from app.schemas import SCHEMA_VERSION

    assert r["status"] == "ok" and r["schema_version"] == SCHEMA_VERSION
    assert r["uncertain_below"] == 0.6  # from rules/config.yaml
    assert r["min_history"] == 5


def test_upload_validation(client):
    assert client.post("/api/packages", files=[]).status_code in (400, 422)
    r = client.post("/api/packages", files=[("files", ("notes.txt", b"hello", "text/plain"))])
    assert r.status_code == 400 and "Unsupported" in r.json()["detail"]
    r = client.post("/api/packages", files=[("files", ("empty.pdf", b"", "application/pdf"))])
    assert r.status_code == 400 and "empty" in r.json()["detail"]


def test_clean_package_end_to_end(client):
    inv_id = _upload_and_process(client, "PKG01")
    inv = client.get(f"/api/invoices/{inv_id}").json()
    assert inv["invoice_no"] == "SPC/26-27/0101"
    assert inv["readiness_score"] >= 85 and inv["risk_tier"] == "Low"
    assert inv["analysis"]["due"]["acceptance_basis"] == "grn"
    assert {d["doc_type"] for d in inv["documents"]} >= {"invoice", "po", "challan", "grn"}
    graph = client.get(f"/api/invoices/{inv_id}/graph").json()
    assert {n["id"] for n in graph["nodes"]} >= {"inv", "po", "challan", "grn"}
    assert all("from" in e for e in graph["edges"])
    assert client.get("/api/invoices").json()[0]["id"] == inv_id


def test_grn_missing_package_flags_blocker_and_action(client):
    inv_id = _upload_and_process(client, "PKG07")
    a = client.get(f"/api/invoices/{inv_id}").json()["analysis"]
    c10 = next(c for c in a["checks"] if c["check_id"] == "C10")
    assert c10["status"] == "missing" and c10["severity"] == "blocker"
    assert a["score"]["tier"] in ("Medium", "High")
    assert a["actions"][0]["check_id"] == "C10" and a["actions"][0]["due_by"]
    grn = next(n for n in a["graph"]["nodes"] if n["id"] == "grn")
    assert grn["status"] == "missing"


def test_duplicate_invoice_detected_against_db(client):
    _upload_and_process(client, "PKG17")           # original SPC/26-27/0117 for buyer GEL
    inv_id = _upload_and_process(client, "PKG23")  # reuses the same number
    a = client.get(f"/api/invoices/{inv_id}").json()["analysis"]
    c14 = next(c for c in a["checks"] if c["check_id"] == "C14")
    assert c14["status"] == "fail"


def test_reprocessing_same_package_is_not_a_duplicate(client):
    r = client.post("/api/packages", files=_files("PKG01"))
    pid = r.json()["id"]
    client.post(f"/api/packages/{pid}/process")
    r = client.post(f"/api/packages/{pid}/process").json()
    a = client.get(f"/api/invoices/{r['invoice_id']}").json()["analysis"]
    assert next(c for c in a["checks"] if c["check_id"] == "C14")["status"] == "pass"


def test_corrupt_file_keeps_partial_results(client):
    files = _files("PKG01") + [("files", ("broken.pdf", b"%PDF-1.4 not really", "application/pdf"))]
    pid = client.post("/api/packages", files=files).json()["id"]
    assert client.post(f"/api/packages/{pid}/process").status_code == 200
    docs = client.get(f"/api/packages/{pid}").json()["documents"]
    broken = next(d for d in docs if d["filename"] == "broken.pdf")
    assert broken["error"] and "readable" in broken["error"]


def test_package_without_invoice_fails_clearly(client):
    files = [f for f in _files("PKG01") if "invoice" not in f[1][0]]
    pid = client.post("/api/packages", files=files).json()["id"]
    r = client.post(f"/api/packages/{pid}/process")
    assert r.status_code == 422 and "No invoice" in r.json()["detail"]
    assert client.get(f"/api/packages/{pid}").json()["status"] == "failed"


def test_not_found_errors(client):
    assert client.get("/api/invoices/999").status_code == 404
    assert client.post("/api/packages/999/process").status_code == 404
    assert client.get("/api/buyers/999/profile").status_code == 404


def test_buyer_profile_endpoint_insufficient_history(client):
    _upload_and_process(client, "PKG01")
    buyers = client.get("/api/buyers").json()
    assert buyers and buyers[0]["profile"]["label"] == "Insufficient history"


# ---------------------------------------------------------------- profile unit tests
D = date(2026, 1, 1)


def _hist(lates):
    return [(D + timedelta(days=10 * i), D + timedelta(days=10 * i + late)) for i, late in enumerate(lates)]


def test_profile_min_history():
    assert compute_profile(_hist([0, 0, 0, 0])).label == "Insufficient history"


def test_profile_labels_and_trend():
    assert compute_profile(_hist([0, -2, 3, 0, 1])).label == "Reliable"
    slow = compute_profile(_hist([25, 40, 35, 60, 22, 45]))
    assert slow.label == "Slow" and slow.pct_paid_over_30_late == 66.7  # 40, 35, 60, 45 of 6
    mixed = compute_profile(_hist([0, 2, 10, 12, 35, 8]))
    assert mixed.label == "Mixed"
    worse = compute_profile(_hist([0, 0, 0, 20, 30, 40]))
    assert worse.trend == "worsening"
