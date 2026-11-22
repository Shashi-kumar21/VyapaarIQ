"""Engine, ``init_db()`` and session helpers. DB path from ``VYAPAARIQ_DB``."""

from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Optional

from sqlalchemy.engine import Engine
from sqlmodel import Session, SQLModel, create_engine

BACKEND_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = BACKEND_DIR / "data"

_engine: Optional[Engine] = None


def db_url() -> str:
    path = os.environ.get("VYAPAARIQ_DB") or str(DATA_DIR / "vyapaariq.db")
    if path == ":memory:":
        return "sqlite://"
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{path}"


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        url = db_url()
        kw = {"connect_args": {"check_same_thread": False}}
        if url == "sqlite://":
            from sqlalchemy.pool import StaticPool
            kw["poolclass"] = StaticPool
        _engine = create_engine(url, **kw)
    return _engine


def reset_engine() -> None:
    """Tests: drop the cached engine so a new ``VYAPAARIQ_DB`` takes effect."""
    global _engine
    if _engine is not None:
        _engine.dispose()
    _engine = None


def init_db() -> None:
    from app.db import models  # noqa: F401  (register tables)

    SQLModel.metadata.create_all(get_engine())


def get_session() -> Iterator[Session]:
    """FastAPI dependency."""
    with Session(get_engine()) as s:
        yield s


@contextmanager
def session_scope() -> Iterator[Session]:
    with Session(get_engine()) as s:
        yield s
