"""FastAPI app: ``uvicorn app.main:app --reload`` from ``backend/``."""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.db.session import init_db


# App log lines (e.g. per-package processing time, T3.10) at INFO in the uvicorn terminal.
# Uvicorn configures only its own loggers, so give ours a handler once.
_LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")


def log_level(raw: str | None) -> tuple[int, str | None]:
    """Level from VYAPAARIQ_LOG_LEVEL, case-insensitive. An unknown name falls back to INFO and
    returns a warning instead of raising: a typo must never stop the API from starting."""
    name = (raw or "INFO").strip().upper()
    if name in _LEVELS:
        return getattr(logging, name), None
    return logging.INFO, f"Unknown VYAPAARIQ_LOG_LEVEL {raw!r}; using INFO (one of {', '.join(_LEVELS)})."


_app_log = logging.getLogger("vyapaariq")
if not _app_log.handlers:
    _h = logging.StreamHandler()
    _h.setFormatter(logging.Formatter("%(levelname)s:     %(name)s: %(message)s"))
    _app_log.addHandler(_h)
    _level, _warning = log_level(os.environ.get("VYAPAARIQ_LOG_LEVEL"))
    _app_log.setLevel(_level)
    if _warning:
        _app_log.warning(_warning)


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(title="VyapaarIQ API", version="0.1.0", lifespan=lifespan,
              description="Invoice evidence graph and payment-readiness checks (demo, synthetic data).")
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
    # The UI reads these on dispute-pack downloads (file name, PDF -> Markdown fallback flag).
    expose_headers=["Content-Disposition", "X-Pack-Format"],
)
app.include_router(router)
