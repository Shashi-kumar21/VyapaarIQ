"""Hosted-demo helpers (docs/deploy.md, D-41). Every piece is off unless its env var is set, so
local development and the tests behave exactly as before.

- ``DEMO_PASSWORD`` (+ optional ``DEMO_USER``, default ``demo``): HTTP Basic auth on every request
  except ``/api/health`` (the platform's health check). The app has no login of its own, so a
  hosted link without this would let anyone upload files.
- ``STATIC_DIR``: serve the built frontend (``frontend/dist``) from the same origin as the API, with
  an SPA fallback to ``index.html`` for client-side routes.
- ``DEMO_BOOTSTRAP=1``: on an empty database, seed the synthetic history and pre-process the
  packages in ``DEMO_PRELOAD`` (default ``PKG01,PKG20``, as in docs/demo_script.md). The free host
  has no persistent disk, so every restart starts from this clean demo state.
"""

from __future__ import annotations

import base64
import binascii
import logging
import os
import secrets
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from starlette.types import ASGIApp, Receive, Scope, Send
from sqlmodel import select

log = logging.getLogger("vyapaariq.deploy")

OPEN_PATHS = {"/api/health"}
REPO = Path(__file__).resolve().parents[2]


# ---------------------------------------------------------------- basic auth
class BasicAuthMiddleware:
    """Pure ASGI middleware: 401 + ``WWW-Authenticate`` unless the request carries the shared
    credentials. Constant-time comparison; the password is never logged."""

    def __init__(self, app: ASGIApp, user: str, password: str) -> None:
        self.app = app
        self.user = user.encode()
        self.password = password.encode()

    def _ok(self, header: bytes | None) -> bool:
        if not header or not header.lower().startswith(b"basic "):
            return False
        try:
            user, _, pwd = base64.b64decode(header[6:].strip(), validate=True).partition(b":")
        except (binascii.Error, ValueError):
            return False
        # evaluate both comparisons, so timing does not reveal which part was wrong
        return secrets.compare_digest(user, self.user) & secrets.compare_digest(pwd, self.password)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope.get("path") in OPEN_PATHS or scope.get("method") == "OPTIONS":
            await self.app(scope, receive, send)
            return
        headers = dict(scope.get("headers") or [])
        if self._ok(headers.get(b"authorization")):
            await self.app(scope, receive, send)
            return
        await send({"type": "http.response.start", "status": 401, "headers": [
            (b"www-authenticate", b'Basic realm="VyapaarIQ demo", charset="UTF-8"'),
            (b"content-type", b"text/plain; charset=utf-8")]})
        await send({"type": "http.response.body", "body": b"Login required for the VyapaarIQ demo."})


def add_basic_auth(app: FastAPI) -> bool:
    password = os.environ.get("DEMO_PASSWORD") or ""
    if not password:
        return False
    app.add_middleware(BasicAuthMiddleware, user=os.environ.get("DEMO_USER") or "demo", password=password)
    return True


# ---------------------------------------------------------------- frontend
def mount_frontend(app: FastAPI, static_dir: str | None) -> bool:
    """Serve ``static_dir`` (a Vite build) at ``/``. Call after the API router is included."""
    if not static_dir:
        return False
    root = Path(static_dir).resolve()
    index = root / "index.html"
    if not index.is_file():
        log.warning("STATIC_DIR %s has no index.html; frontend not served", root)
        return False

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        if path == "api" or path.startswith("api/"):
            raise HTTPException(404, "Not found.")  # unknown API paths stay JSON 404s
        target = (root / path).resolve()
        if path and target.is_file() and target.is_relative_to(root):
            return FileResponse(target)
        return FileResponse(index)  # client-side route (e.g. /invoices/61)

    return True


# ---------------------------------------------------------------- demo bootstrap
def bootstrap_demo() -> dict:
    """Seed + preload the demo packages, only on an empty database (idempotent)."""
    from app.api.routes import _today
    from app.db.models import Package
    from app.db.session import session_scope
    from app.seed import seed
    from app.services import create_package, process_package

    samples = Path(os.environ.get("SAMPLES_DIR") or REPO / "samples" / "out")
    wanted = [p.strip() for p in (os.environ.get("DEMO_PRELOAD") or "PKG01,PKG20").split(",") if p.strip()]
    out = {"seeded": 0, "preloaded": []}
    with session_scope() as s:
        out["seeded"] = seed(s)["created"]
        if s.exec(select(Package)).first() is not None:
            return out  # already has packages: never duplicate (C14 would flag them)
        for name in wanted:
            files = sorted((samples / name).glob("*.pdf"))
            if not files:
                log.warning("demo preload: no PDFs for %s in %s", name, samples)
                continue
            pkg = create_package(s, [(f.name, f.read_bytes()) for f in files])
            process_package(s, pkg.id, today=_today())  # same demo clock as the API
            out["preloaded"].append(name)
    log.info("demo bootstrap: seeded %d, preloaded %s", out["seeded"], ",".join(out["preloaded"]) or "none")
    return out
