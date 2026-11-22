"""FastAPI app: ``uvicorn app.main:app --reload`` from ``backend/``."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.db.session import init_db


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
)
app.include_router(router)
