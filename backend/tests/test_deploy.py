"""Hosted-demo helpers (app/deploy.py, docs/deploy.md): shared-password gate, same-origin UI and the
demo bootstrap. Each is off unless its env var is set; the default app must not change."""

import base64

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.deploy import BasicAuthMiddleware, add_basic_auth, bootstrap_demo, mount_frontend


def _auth(user: str, pwd: str) -> dict:
    return {"Authorization": "Basic " + base64.b64encode(f"{user}:{pwd}".encode()).decode()}


def _mini_app() -> FastAPI:
    app = FastAPI()

    @app.get("/api/health")
    def health():
        return {"status": "ok"}

    @app.get("/api/invoices")
    def invoices():
        return []

    return app


# ---------------------------------------------------------------- password gate
def test_no_password_means_no_gate(monkeypatch):
    monkeypatch.delenv("DEMO_PASSWORD", raising=False)
    app = _mini_app()
    assert add_basic_auth(app) is False
    assert TestClient(app).get("/api/invoices").status_code == 200


def test_password_gate(monkeypatch):
    monkeypatch.setenv("DEMO_PASSWORD", "s3cret-demo")
    monkeypatch.delenv("DEMO_USER", raising=False)
    app = _mini_app()
    assert add_basic_auth(app) is True
    c = TestClient(app)
    r = c.get("/api/invoices")
    assert r.status_code == 401 and r.headers["www-authenticate"].startswith('Basic realm="VyapaarIQ demo"')
    assert "s3cret" not in r.text
    assert c.get("/api/invoices", headers=_auth("demo", "wrong")).status_code == 401
    assert c.get("/api/invoices", headers=_auth("admin", "s3cret-demo")).status_code == 401
    assert c.get("/api/invoices", headers={"Authorization": "Basic !!!not-base64"}).status_code == 401
    assert c.get("/api/invoices", headers={"Authorization": "Bearer s3cret-demo"}).status_code == 401
    assert c.get("/api/invoices", headers=_auth("demo", "s3cret-demo")).status_code == 200
    assert c.get("/api/health").status_code == 200  # the platform's health check stays open


def test_custom_user(monkeypatch):
    monkeypatch.setenv("DEMO_PASSWORD", "p")
    monkeypatch.setenv("DEMO_USER", "judge")
    app = _mini_app()
    add_basic_auth(app)
    c = TestClient(app)
    assert c.get("/api/invoices", headers=_auth("demo", "p")).status_code == 401
    assert c.get("/api/invoices", headers=_auth("judge", "p")).status_code == 200


def test_hsts_on_every_response_and_non_http_scopes(monkeypatch):
    monkeypatch.setenv("DEMO_PASSWORD", "p")
    app = _mini_app()
    add_basic_auth(app)
    c = TestClient(app)
    for r in (c.get("/api/health"), c.get("/api/invoices"), c.get("/api/invoices", headers=_auth("demo", "p"))):
        assert r.headers["strict-transport-security"] == "max-age=31536000"
    with TestClient(app):  # lifespan still runs through the gate
        pass
    from starlette.websockets import WebSocketDisconnect

    with pytest.raises(WebSocketDisconnect) as e:  # no websocket gets past the gate
        with c.websocket_connect("/ws"):
            pass
    assert e.value.code == 1008


def test_middleware_compares_both_parts():
    m = BasicAuthMiddleware(app=None, user="u", password="p")
    ok = lambda u, p: m._ok(("Basic " + base64.b64encode(f"{u}:{p}".encode()).decode()).encode())  # noqa: E731
    assert ok("u", "p") and not ok("u", "") and not ok("", "p") and not ok("u", "p:extra")
    assert not m._ok(None) and not m._ok(b"Basic ")


# ---------------------------------------------------------------- same-origin UI
@pytest.fixture()
def dist(tmp_path):
    d = tmp_path / "dist"
    (d / "assets").mkdir(parents=True)
    (d / "index.html").write_text("<!doctype html><div id=root></div>", encoding="utf-8")
    (d / "assets" / "app.js").write_text("console.log(1)", encoding="utf-8")
    (tmp_path / "secret.txt").write_text("outside", encoding="utf-8")
    return d


def test_frontend_served_with_spa_fallback(dist):
    app = _mini_app()
    assert mount_frontend(app, str(dist)) is True
    c = TestClient(app)
    assert c.get("/").text.startswith("<!doctype html>")
    assert c.get("/invoices/61").text.startswith("<!doctype html>")  # client-side route
    assert c.get("/assets/app.js").text == "console.log(1)"
    assert c.get("/api/invoices").json() == []  # API routes still win
    r = c.get("/api/nope")
    assert r.status_code == 404 and r.headers["content-type"].startswith("application/json")
    assert "outside" not in c.get("/../secret.txt").text  # never serves files outside dist
    assert "outside" not in c.get("/%2e%2e/secret.txt").text


def test_frontend_off_without_build(tmp_path):
    app = _mini_app()
    assert mount_frontend(app, None) is False
    assert mount_frontend(app, str(tmp_path / "missing")) is False
    assert TestClient(app).get("/").status_code == 404


# ---------------------------------------------------------------- demo bootstrap
def test_bootstrap_seeds_and_preloads_once(tmp_path, monkeypatch, ground_truth):
    monkeypatch.setenv("VYAPAARIQ_DB", str(tmp_path / "demo.db"))
    monkeypatch.setenv("EXTRACTOR", "fixture")
    monkeypatch.setenv("VYAPAARIQ_TODAY", "2026-11-23")
    monkeypatch.delenv("DEMO_PRELOAD", raising=False)
    from app import services
    from app.db import session

    monkeypatch.setattr(services, "UPLOAD_DIR", tmp_path / "uploads")
    session.reset_engine()
    try:
        session.init_db()
        first = bootstrap_demo()
        assert first["seeded"] == 60 and first["preloaded"] == ["PKG01", "PKG20"]
        again = bootstrap_demo()  # a second start on the same DB adds nothing (no C14 duplicates)
        assert again == {"seeded": 0, "preloaded": []}
        from sqlmodel import select

        from app.db.models import Invoice

        with session.session_scope() as s:
            live = [i for i in s.exec(select(Invoice)).all() if not i.synthetic]
        assert sorted(i.readiness_score for i in live) == [90, 100]  # PKG20 (C12 warning), PKG01 (clean)
    finally:
        session.reset_engine()
