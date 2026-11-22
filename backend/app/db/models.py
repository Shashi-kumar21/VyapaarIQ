"""SQLModel tables (BUILD_SPEC §5). JSON blobs are stored as text."""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Optional

from sqlmodel import Field, SQLModel


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Supplier(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    gstin: Optional[str] = None
    udyam_no: Optional[str] = None
    enterprise_class: str = "small"


class Buyer(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    gstin: Optional[str] = Field(default=None, index=True)
    aliases_json: str = "[]"
    synthetic: bool = False  # seeded demo buyer


class Package(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    supplier_id: Optional[int] = Field(default=None, foreign_key="supplier.id")
    buyer_id: Optional[int] = Field(default=None, foreign_key="buyer.id")
    created_at: datetime = Field(default_factory=_now)
    status: str = "uploaded"  # uploaded | processing | done | failed
    error: Optional[str] = None
    buyer_name_hint: Optional[str] = None


class Document(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    package_id: int = Field(foreign_key="package.id", index=True)
    doc_type: str = "other"
    doc_type_method: Optional[str] = None
    filename: str
    path: str
    sha256: str
    extracted_json: Optional[str] = None
    extraction_conf: Optional[float] = None
    page_count: Optional[int] = None
    extractor: Optional[str] = None
    fallback: bool = False
    error: Optional[str] = None


class Invoice(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    package_id: Optional[int] = Field(default=None, foreign_key="package.id", index=True)
    buyer_id: Optional[int] = Field(default=None, foreign_key="buyer.id", index=True)
    invoice_no: Optional[str] = Field(default=None, index=True)
    invoice_no_norm: Optional[str] = Field(default=None, index=True)
    invoice_date: Optional[date] = None
    amount_total: Optional[float] = None
    amount_taxable: Optional[float] = None
    gst_amount: Optional[float] = None
    payment_terms_days: Optional[int] = None
    due_date: Optional[date] = None
    status: str = "open"  # open | paid | disputed
    readiness_score: Optional[int] = None
    risk_tier: Optional[str] = None
    analysis_json: Optional[str] = None
    processing_ms: Optional[int] = None
    synthetic: bool = False  # seeded history row
    created_at: datetime = Field(default_factory=_now)


class CheckResult(SQLModel, table=True):
    __tablename__ = "check_result"
    id: Optional[int] = Field(default=None, primary_key=True)
    invoice_id: int = Field(foreign_key="invoice.id", index=True)
    check_id: str
    status: str
    severity: str
    detail_json: str = "{}"


class ActionRow(SQLModel, table=True):
    __tablename__ = "action"
    id: Optional[int] = Field(default=None, primary_key=True)
    invoice_id: int = Field(foreign_key="invoice.id", index=True)
    priority: int
    check_id: str
    title: str
    rationale: str
    due_by: Optional[date] = None
    owner_role: str = "supplier_accounts"
    status: str = "open"


class Followup(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    invoice_id: int = Field(foreign_key="invoice.id", index=True)
    step: int  # days relative to due date
    send_on: Optional[date] = None
    channel: str = "email"
    tone: str = "friendly"
    draft_text: str = ""
    status: str = "draft"  # always draft: never sent


class PaymentEvent(SQLModel, table=True):
    __tablename__ = "payment_event"
    id: Optional[int] = Field(default=None, primary_key=True)
    invoice_id: int = Field(foreign_key="invoice.id", index=True)
    paid_on: date
    amount: float
