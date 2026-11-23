"""Seed history, follow-up drafts, cash-at-risk forecast, dispute pack (T3.5, T4.1-T4.4)."""

from datetime import date, timedelta

import pytest
from sqlmodel import Session, SQLModel, create_engine, select

from app.db.models import Buyer, Invoice, PaymentEvent
from app.dispute.pack import build_pack, pdf_safe, to_markdown, to_pdf
from app.fmt import inr
from app.followups.drafts import DRAFT_LABEL, FollowupContext, build_followups, buyer_requests
from app.forecast.cash_at_risk import OpenInvoice, forecast
from app.scoring.buyer_profile import compute_profile
from app.seed import seed
from app.services import buyer_history

from .test_api import _upload_and_process, client  # noqa: F401  (fixture)

TODAY = date(2026, 11, 23)


# ---------------------------------------------------------------- formatting
def test_inr_grouping():
    assert inr(240000) == "₹2,40,000"
    assert inr(12345678.4) == "₹1,23,45,678"
    assert inr(999) == "₹999"
    assert inr(-1500) == "-₹1,500"
    assert inr(None) == "-"
    assert pdf_safe("₹5 C01 Invoice ↔ PO ≥") == "Rs. 5 C01 Invoice <-> PO >="


# ---------------------------------------------------------------- seed
@pytest.fixture()
def mem():
    from app.db import models  # noqa: F401

    eng = create_engine("sqlite://")
    SQLModel.metadata.create_all(eng)
    with Session(eng) as s:
        yield s


def test_seed_creates_flagged_history_with_label_mix(mem):
    out = seed(mem)
    assert out["created"] == 60 and not out["skipped"]
    invs = mem.exec(select(Invoice)).all()
    assert len(invs) == 60 and all(i.synthetic and i.status == "paid" for i in invs)
    assert len(mem.exec(select(PaymentEvent)).all()) == 60
    buyers = mem.exec(select(Buyer)).all()
    assert len(buyers) == 6 and all(b.synthetic for b in buyers)
    labels = {b.name.split()[0]: compute_profile(buyer_history(mem, b.id)).label for b in buyers}
    assert labels["Kaveri"] == "Reliable" and labels["Narmada"] == "Mixed" and labels["Deccan"] == "Slow"
    assert set(labels.values()) == {"Reliable", "Mixed", "Slow"}


def test_seed_is_idempotent_and_resettable(mem):
    seed(mem)
    again = seed(mem)
    assert again["skipped"] and len(mem.exec(select(Invoice)).all()) == 60
    redo = seed(mem, reset=True)
    assert redo["removed"] == 60 and redo["created"] == 60
    assert len(mem.exec(select(Invoice)).all()) == 60


# ---------------------------------------------------------------- follow-ups
def _ctx(**kw):
    base = dict(invoice_no="SPC/26-27/0107", amount=240000.0, due_date=date(2026, 10, 13),
                due_reasoning="GRN date + 30 days", buyer_name="Kaveri Auto Assemblies Pvt Ltd",
                supplier_name="Shakti Precision Components Pvt Ltd",
                missing=buyer_requests(["C10", "C02"]),
                attachments=["Tax invoice SPC/26-27/0107"])
    base.update(kw)
    return FollowupContext(**base)


def test_followup_cadence_and_required_content():
    drafts = build_followups(_ctx())
    assert [x.step for x in drafts] == [-7, -1, 3, 10, 25]
    assert [x.send_on for x in drafts] == [date(2026, 10, 13) + timedelta(days=k) for k in (-7, -1, 3, 10, 25)]
    for x in drafts:
        assert x.status == "draft" and DRAFT_LABEL in x.text
        assert "SPC/26-27/0107" in x.text and "₹2,40,000" in x.text and "13 Oct 2026" in x.text
        assert "Attached: Tax invoice SPC/26-27/0107" in x.text
    assert "the GRN or a written acceptance" in drafts[0].text  # D-7 asks the buyer for it
    assert buyer_requests(["C02", "C14"]) == []  # supplier-side fixes are not asked of the buyer
    assert "45 days" in drafts[3].text and "verify" in drafts[3].text  # D+10 cites the rule politely
    assert "ODR portal" in drafts[4].text and "not legal advice" in drafts[4].text


def test_followup_tones_differ_and_medium_supplier_skips_msmed():
    friendly = build_followups(_ctx(), tone="friendly")
    firm = build_followups(_ctx(), tone="firm")
    assert all(a.text != b.text for a, b in zip(friendly, firm))
    medium = build_followups(_ctx(msmed_applies=False))
    assert "45 days" not in medium[3].text and "ODR" not in medium[4].text


def test_followup_whatsapp_and_validation():
    wa = build_followups(_ctx(), channel="whatsapp")
    assert all(x.channel == "whatsapp" and "Dear" not in x.text and "SPC/26-27/0107" in x.text for x in wa)
    with pytest.raises(ValueError):
        build_followups(_ctx(), tone="angry")
    with pytest.raises(ValueError):
        build_followups(_ctx(), channel="sms")


# ---------------------------------------------------------------- forecast
def _oi(i, amount, due, tier="Low", median=None):
    return OpenInvoice(id=i, invoice_no=f"I{i}", buyer_id=1, buyer_name="B", amount=amount,
                       due_date=due, risk_tier=tier, buyer_median_late=median)


def test_forecast_buckets_and_risk_rules():
    rows = [
        _oi(1, 100, TODAY + timedelta(days=10)),               # in the 30-day window
        _oi(2, 200, TODAY + timedelta(days=10), median=30.0),  # pushed to day 40 -> at risk in 30
        _oi(3, 300, TODAY + timedelta(days=5), tier="High"),   # High tier -> at risk
        _oi(4, 400, None),                                     # unknown due date -> at risk
        _oi(5, 500, TODAY - timedelta(days=20)),               # past expected date, unpaid -> at risk
    ]
    f30 = forecast(rows, TODAY, 30)
    assert f30["totals"] == {"open": 1500, "expected_in_window": 100, "at_risk": 1400, "count": 5}
    b = {x["key"]: x["amount"] for x in f30["buckets"]}
    assert b == {"overdue": 500, "next_30": 400, "days_31_60": 200, "beyond_60": 0, "unknown": 400}
    by_id = {r["id"]: r for r in f30["invoices"]}
    assert by_id[2]["expected_date"] == TODAY + timedelta(days=40) and by_id[2]["at_risk"]
    f60 = forecast(rows, TODAY, 60)
    assert f60["totals"]["at_risk"] == 1200  # invoice 2 is now inside the window
    assert by_id[5]["reasons"] == ["unpaid 20 day(s) after expected date"]
    assert "median days late" in f30["formula"] and "Illustrative" in f30["note"]
    with pytest.raises(ValueError):
        forecast(rows, TODAY, 45)


# ---------------------------------------------------------------- dispute pack (unit)
def _analysis():
    return {
        "buyer_name": "Kaveri Auto Assemblies Pvt Ltd",
        "checks": [{"check_id": "C10", "name": "GRN / acceptance", "status": "missing", "severity": "blocker",
                    "detail": "No GRN in package."},
                   {"check_id": "C01", "name": "Invoice ↔ PO reference", "status": "pass",
                    "severity": "blocker", "detail": "ok"}],
        "score": {"score": 70, "tier": "Medium"},
        "due": {"due_date": "2026-10-13", "acceptance_date": "2026-09-13",
                "acceptance_basis": "challan_received", "reasoning": "Challan received date + 30 days.",
                "msmed_applies": True},
        "actions": [{"check_id": "C10", "title": "Request GRN / acceptance acknowledgement"}],
    }


def test_dispute_pack_sections_markdown_and_pdf():
    inv = {"id": 1, "invoice_no": "SPC/26-27/0107", "invoice_date": "2026-09-05", "amount_total": 240000.0,
           "buyer_name": "Kaveri Auto Assemblies Pvt Ltd"}
    docs = [{"doc_type": "invoice", "filename": "inv.pdf", "extraction_conf": 0.95,
             "fields": {"invoice_no": {"value": "SPC/26-27/0107"}, "total": {"value": 240000.0}}}]
    pack = build_pack(invoice=inv, analysis=_analysis(), documents=docs,
                      supplier={"name": "Shakti Precision Components Pvt Ltd", "gstin": "27AAECS4821K1Z6"},
                      today=TODAY)
    assert [s.title for s in pack.sections] == [
        "Summary", "Invoice facts", "Document index", "Timeline", "Verification checks",
        "Due date and reasoning", "Estimated statutory interest", "Missing or weak evidence",
        "Suggested next step"]
    md = to_markdown(pack)
    assert "not legal advice" in md and "ODR portal" in md and "Total: ₹2,40,000" in md
    assert "C10 GRN / acceptance: No GRN in package." in md
    assert "41 day(s) late" in md  # 13 Oct -> 23 Nov
    pdf = to_pdf(pack)
    assert pdf.startswith(b"%PDF") and len(pdf) > 2000


# ---------------------------------------------------------------- API
def test_api_followups_generate_and_list(client):  # noqa: F811
    inv_id = _upload_and_process(client, "PKG07")
    r = client.post(f"/api/invoices/{inv_id}/followups/generate?tone=firm")
    assert r.status_code == 200, r.text
    rows = r.json()["followups"]
    assert [x["step_label"] for x in rows] == ["D-7", "D-1", "D+3", "D+10", "D+25"]
    assert all(x["status"] == "draft" and x["tone"] == "firm" for x in rows)
    client.post(f"/api/invoices/{inv_id}/followups/generate?tone=firm")  # regenerating replaces
    client.post(f"/api/invoices/{inv_id}/followups/generate?tone=friendly")
    assert len(client.get(f"/api/invoices/{inv_id}/followups").json()) == 10
    assert len(client.get(f"/api/invoices/{inv_id}/followups?tone=firm").json()) == 5
    assert client.post(f"/api/invoices/{inv_id}/followups/generate?tone=rude").status_code == 422
    assert client.post("/api/invoices/999/followups/generate").status_code == 404


def test_api_dispute_pack_pdf_and_md(client):  # noqa: F811
    inv_id = _upload_and_process(client, "PKG07")
    r = client.get(f"/api/invoices/{inv_id}/dispute-pack")
    assert r.status_code == 200 and r.headers["content-type"] == "application/pdf"
    assert r.content.startswith(b"%PDF") and r.headers["x-pack-format"] == "pdf"
    md = client.get(f"/api/invoices/{inv_id}/dispute-pack?format=md")
    assert md.status_code == 200 and md.headers["content-type"].startswith("text/markdown")
    assert "SPC/26-27/0107" in md.text and "C10" in md.text and "not legal advice" in md.text
    assert client.get("/api/invoices/999/dispute-pack").status_code == 404


def test_api_forecast_uses_seeded_buyer_history(client):  # noqa: F811
    from app.db.session import session_scope

    with session_scope() as s:
        seed(s)
    inv_id = _upload_and_process(client, "PKG13")  # KAA, seeded as Reliable
    f = client.get("/api/forecast?days=30").json()
    assert f["totals"]["count"] == 1  # seeded paid history is not open
    row = f["invoices"][0]
    assert row["id"] == inv_id and row["buyer_median_days_late"] is not None
    assert client.get("/api/forecast?days=45").status_code == 400
    kaa = next(b for b in client.get("/api/buyers").json() if b["name"].startswith("Kaveri"))
    assert kaa["synthetic"] and kaa["profile"]["label"] == "Reliable"
