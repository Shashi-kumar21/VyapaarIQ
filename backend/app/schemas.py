"""Frozen data contracts (BUILD_SPEC §6, §7, §12).

Owned by A0. Other modules import from here; change only through A0 and bump
``SCHEMA_VERSION`` when a change is not backward compatible.
"""

from __future__ import annotations

from datetime import date
from enum import Enum
from typing import Annotated, Any, Generic, Literal, Optional, TypeVar, Union

from pydantic import BaseModel, Field

SCHEMA_VERSION = "1.1"  # 1.1: DueDateResult.uncertain/msmed_applies, InterestEstimate.computable

T = TypeVar("T")


# --------------------------------------------------------------------------
# Extracted field wrapper: every value carries confidence + source page (§4)
# --------------------------------------------------------------------------
class F(BaseModel, Generic[T]):
    """One extracted field; never a guess.

    ``value=None`` with confidence >= threshold means "confidently absent";
    with low confidence it means "could not read" (checks become uncertain).
    """

    value: Optional[T] = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    source_page: Optional[int] = None

    @property
    def known(self) -> bool:
        return self.value is not None


def empty() -> Any:
    return Field(default_factory=F)


class LineItem(BaseModel):
    """Superset line item; each doc type fills the columns it has."""

    desc: Optional[str] = None
    hsn: Optional[str] = None
    qty: Optional[float] = None
    unit: Optional[str] = None
    rate: Optional[float] = None
    amount: Optional[float] = None
    qty_received: Optional[float] = None
    qty_accepted: Optional[float] = None


class DocType(str, Enum):
    invoice = "invoice"
    po = "po"
    challan = "challan"
    eway = "eway"
    grn = "grn"
    contract = "contract"
    other = "other"


# --------------------------------------------------------------------------
# Documents (§6)
# --------------------------------------------------------------------------
class BaseDoc(BaseModel):
    doc_type: DocType
    filename: Optional[str] = None
    page_count: int = 1
    extractor: Optional[str] = None  # claude | text | fixture
    fallback: bool = False  # True when a fallback extractor produced this doc ("demo fallback")
    doc_no: F[str] = empty()
    doc_date: F[date] = empty()
    supplier_name: F[str] = empty()
    supplier_gstin: F[str] = empty()
    supplier_udyam: F[str] = empty()
    buyer_name: F[str] = empty()
    buyer_gstin: F[str] = empty()
    po_reference: F[str] = empty()


class InvoiceDoc(BaseDoc):
    doc_type: Literal[DocType.invoice] = DocType.invoice
    invoice_no: F[str] = empty()
    invoice_date: F[date] = empty()
    line_items: F[list[LineItem]] = empty()
    taxable_value: F[float] = empty()
    cgst: F[float] = empty()
    sgst: F[float] = empty()
    igst: F[float] = empty()
    total: F[float] = empty()
    payment_terms_text: F[str] = empty()
    payment_terms_days: F[int] = empty()
    due_date_text: F[str] = empty()
    irn: F[str] = empty()
    bank_details_present: F[bool] = empty()


class PODoc(BaseDoc):
    doc_type: Literal[DocType.po] = DocType.po
    po_no: F[str] = empty()
    po_date: F[date] = empty()
    line_items: F[list[LineItem]] = empty()
    po_total: F[float] = empty()
    delivery_date: F[date] = empty()
    payment_terms_text: F[str] = empty()
    payment_terms_days: F[int] = empty()


class ChallanDoc(BaseDoc):
    doc_type: Literal[DocType.challan] = DocType.challan
    challan_no: F[str] = empty()
    challan_date: F[date] = empty()
    invoice_reference: F[str] = empty()
    line_items: F[list[LineItem]] = empty()
    vehicle_no: F[str] = empty()
    received_by_name: F[str] = empty()
    received_stamp_present: F[bool] = empty()
    received_signature_present: F[bool] = empty()
    received_date: F[date] = empty()


class EwayDoc(BaseDoc):
    doc_type: Literal[DocType.eway] = DocType.eway
    eway_no: F[str] = empty()
    generated_date: F[date] = empty()
    invoice_reference: F[str] = empty()
    value: F[float] = empty()
    vehicle_no: F[str] = empty()
    valid_until: F[date] = empty()


class GRNDoc(BaseDoc):
    doc_type: Literal[DocType.grn] = DocType.grn
    grn_no: F[str] = empty()
    grn_date: F[date] = empty()
    invoice_reference: F[str] = empty()
    line_items: F[list[LineItem]] = empty()
    accepted_by: F[str] = empty()
    remarks: F[str] = empty()


class ContractDoc(BaseDoc):
    doc_type: Literal[DocType.contract] = DocType.contract
    payment_terms_text: F[str] = empty()
    payment_terms_days: F[int] = empty()
    deemed_acceptance_clause_present: F[bool] = empty()
    interest_clause_text: F[str] = empty()


class OtherDoc(BaseDoc):
    doc_type: Literal[DocType.other] = DocType.other


AnyDoc = Annotated[
    Union[InvoiceDoc, PODoc, ChallanDoc, EwayDoc, GRNDoc, ContractDoc, OtherDoc],
    Field(discriminator="doc_type"),
]

DOC_MODELS: dict[DocType, type[BaseDoc]] = {
    DocType.invoice: InvoiceDoc,
    DocType.po: PODoc,
    DocType.challan: ChallanDoc,
    DocType.eway: EwayDoc,
    DocType.grn: GRNDoc,
    DocType.contract: ContractDoc,
    DocType.other: OtherDoc,
}


class ExtractedPackage(BaseModel):
    """All documents of one package after extraction; input to matching."""

    documents: list[AnyDoc] = Field(default_factory=list)

    def of(self, doc_type: DocType) -> list[BaseDoc]:
        return [d for d in self.documents if d.doc_type == doc_type]

    def first(self, doc_type: DocType) -> Optional[Any]:
        docs = self.of(doc_type)
        return docs[0] if docs else None


# --------------------------------------------------------------------------
# Checks, scoring, actions (§7)
# --------------------------------------------------------------------------
class CheckStatus(str, Enum):
    passed = "pass"
    fail = "fail"
    missing = "missing"
    uncertain = "uncertain"


class Severity(str, Enum):
    blocker = "blocker"
    warning = "warning"
    info = "info"


class Check(BaseModel):
    check_id: str  # C01..C14
    name: str
    status: CheckStatus
    severity: Severity
    detail: str  # deterministic one-line explanation
    explanation: Optional[str] = None  # optional LLM rephrasing; never affects status
    evidence_refs: list[str] = Field(default_factory=list)  # graph node ids
    facts: dict[str, Any] = Field(default_factory=dict)


class Penalty(BaseModel):
    check_id: str
    status: CheckStatus
    severity: Severity
    points: int


class RiskTier(str, Enum):
    low = "Low"
    medium = "Medium"
    high = "High"


class ScoreBreakdown(BaseModel):
    score: int
    tier: RiskTier
    penalties: list[Penalty]
    note: str = "Illustrative readiness score, not a prediction of buyer payment."


class Action(BaseModel):
    priority: int  # 1 = do first
    check_id: str
    title: str
    rationale: str
    due_by: Optional[date] = None
    owner_role: str = "supplier_accounts"
    status: str = "open"


class DueDateResult(BaseModel):
    acceptance_date: Optional[date]
    acceptance_basis: Literal["grn", "challan_received", "deemed", "unknown"]
    terms_days_applied: Optional[int]
    terms_basis: Literal["written_terms", "written_terms_capped", "no_written_terms",
                         "written_terms_unreadable", "unknown"]
    due_date: Optional[date]
    reasoning: str
    estimated: bool = True
    uncertain: bool = False  # True when an input (e.g. terms days) could not be read
    msmed_applies: bool = True  # False for a medium (or larger) supplier


class InterestEstimate(BaseModel):
    principal: float
    due_date: Optional[date]
    as_of: date
    days_late: int
    annual_rate_pct: float  # 3 x bank rate
    interest: Optional[float]  # None when not computable / not applicable
    computable: bool = True
    formula: str
    note: str = "Estimated statutory interest (MSMED s.16). Not legal advice; verify the bank rate."


# --------------------------------------------------------------------------
# Evidence graph (§12)
# --------------------------------------------------------------------------
NodeStatus = Literal["ok", "missing", "mismatch", "uncertain"]
EdgeStatus = Literal["matched", "mismatch", "missing", "uncertain"]


class GraphNode(BaseModel):
    id: str
    type: str
    label: str
    status: NodeStatus
    doc_no: Optional[str] = None


class GraphEdge(BaseModel):
    from_: str = Field(alias="from")
    to: str
    status: EdgeStatus
    confidence: float = 1.0
    note: str = ""
    check_ids: list[str] = Field(default_factory=list)

    model_config = {"populate_by_name": True}


class Graph(BaseModel):
    nodes: list[GraphNode] = Field(default_factory=list)
    edges: list[GraphEdge] = Field(default_factory=list)


# --------------------------------------------------------------------------
# Full analysis of one invoice package (pipeline output)
# --------------------------------------------------------------------------
class Analysis(BaseModel):
    invoice_no: Optional[str]
    buyer_name: Optional[str]
    amount_total: Optional[float]
    checks: list[Check]
    score: ScoreBreakdown
    due: DueDateResult
    interest: Optional[InterestEstimate] = None
    actions: list[Action]
    graph: Graph
    extractor_used: Optional[str] = None
    fallback_used: bool = False
