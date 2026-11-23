"""API routes. Errors are returned as ``{"detail": "<clear message>"}``."""

from __future__ import annotations

import json
import os
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import Response
from sqlmodel import Session, select

from app.db.models import ActionRow, Buyer, CheckResult, Document, Followup, Invoice, Package
from app.db.session import get_session
from app.schemas import SCHEMA_VERSION, DocType
from app.rules.config import get_config
from app.scoring.buyer_profile import compute_profile
from app.services import (PackageError, buyer_history, cash_forecast, create_package, dispute_pack,
                          generate_followups, process_package)

router = APIRouter(prefix="/api")


def _today() -> date:
    """Demo clock: ``VYAPAARIQ_TODAY=YYYY-MM-DD`` pins 'today' for reproducible demos."""
    v = os.environ.get("VYAPAARIQ_TODAY")
    return date.fromisoformat(v) if v else date.today()


@router.get("/health")
def health():
    # uncertain_below: the UI's "needs human check" threshold comes from config, not the frontend.
    return {"status": "ok", "schema_version": SCHEMA_VERSION,
            "extractor": os.environ.get("EXTRACTOR", "text"), "today": _today().isoformat(),
            "uncertain_below": float(get_config()["extraction"]["uncertain_below"]),
            "min_history": int(get_config()["buyer_profile"]["min_history"])}


# ---------------------------------------------------------------- packages
@router.post("/packages", status_code=201)
async def upload_package(files: list[UploadFile] = File(default=[]),
                         buyer_name: Optional[str] = Form(default=None),
                         doc_types: Optional[str] = Form(default=None,
                                                         description="JSON list, same order as files"),
                         s: Session = Depends(get_session)):
    payload = [(f.filename or "file", await f.read()) for f in files]
    types = None
    if doc_types:
        try:
            types = json.loads(doc_types)
        except json.JSONDecodeError:
            types = None
        valid = {t.value for t in DocType}
        if (not isinstance(types, list) or len(types) > len(payload)
                or any(t is not None and t not in valid for t in types)):
            raise HTTPException(400, "doc_types must be a JSON list with at most one entry per file; "
                                     f"each entry is null or one of {sorted(valid)}.")
    try:
        pkg = create_package(s, payload, buyer_name=buyer_name, doc_types=types)
    except PackageError as exc:
        raise HTTPException(400, str(exc))
    return package_view(s, pkg)


@router.post("/packages/{package_id}/process")
def process(package_id: int, s: Session = Depends(get_session)):
    if s.get(Package, package_id) is None:
        raise HTTPException(404, "Package not found.")
    try:
        inv = process_package(s, package_id, today=_today())
    except PackageError as exc:
        raise HTTPException(422, str(exc))
    return {"package_id": package_id, "invoice_id": inv.id, "status": "done",
            "processing_ms": inv.processing_ms}


@router.get("/packages/{package_id}")
def get_package(package_id: int, s: Session = Depends(get_session)):
    pkg = s.get(Package, package_id)
    if pkg is None:
        raise HTTPException(404, "Package not found.")
    return package_view(s, pkg)


def package_view(s: Session, pkg: Package) -> dict:
    docs = s.exec(select(Document).where(Document.package_id == pkg.id)).all()
    inv = s.exec(select(Invoice).where(Invoice.package_id == pkg.id)).first()
    return {
        "id": pkg.id, "status": pkg.status, "error": pkg.error, "created_at": pkg.created_at,
        "invoice_id": inv.id if inv else None,
        "documents": [{
            "id": d.id, "filename": d.filename, "doc_type": d.doc_type, "doc_type_method": d.doc_type_method,
            "extractor": d.extractor, "fallback": d.fallback, "extraction_conf": d.extraction_conf,
            "page_count": d.page_count, "error": d.error,
            "fields": json.loads(d.extracted_json) if d.extracted_json else None,
        } for d in docs],
    }


# ---------------------------------------------------------------- invoices
def _invoice_summary(s: Session, inv: Invoice) -> dict:
    buyer = s.get(Buyer, inv.buyer_id) if inv.buyer_id else None
    return {
        "id": inv.id, "package_id": inv.package_id, "invoice_no": inv.invoice_no,
        "invoice_date": inv.invoice_date, "buyer_id": inv.buyer_id, "buyer_name": buyer.name if buyer else None,
        "amount_total": inv.amount_total, "due_date": inv.due_date, "status": inv.status,
        "readiness_score": inv.readiness_score, "risk_tier": inv.risk_tier, "synthetic": inv.synthetic,
    }


@router.get("/invoices")
def list_invoices(tier: Optional[str] = None, buyer_id: Optional[int] = None,
                  status: Optional[str] = Query(default=None), include_history: bool = False,
                  s: Session = Depends(get_session)):
    q = select(Invoice)
    if not include_history:
        q = q.where(Invoice.synthetic == False)  # noqa: E712
    if tier:
        q = q.where(Invoice.risk_tier == tier)
    if buyer_id:
        q = q.where(Invoice.buyer_id == buyer_id)
    if status:
        q = q.where(Invoice.status == status)
    rows = s.exec(q.order_by(Invoice.id.desc())).all()
    return [_invoice_summary(s, r) for r in rows]


@router.get("/actions")
def top_actions(limit: int = Query(default=5, ge=1, le=50), s: Session = Depends(get_session)):
    """Open actions across open, non-synthetic invoices, ranked like build_actions:
    severity (blocker, warning, info; an uncertain check ranks half a step lower), then due_by."""
    from app.scoring.actions import SEVERITY_RANK

    open_ids = {i.id: i for i in s.exec(select(Invoice).where(Invoice.status == "open",
                                                              Invoice.synthetic == False)).all()}  # noqa: E712
    rows = []
    for a in s.exec(select(ActionRow).where(ActionRow.status == "open")).all():
        inv = open_ids.get(a.invoice_id)
        if inv is None:
            continue
        chk = s.exec(select(CheckResult).where(CheckResult.invoice_id == a.invoice_id,
                                               CheckResult.check_id == a.check_id)).first()
        sev = chk.severity if chk else "info"
        rank = SEVERITY_RANK.get(sev, 3) + (0.5 if chk and chk.status == "uncertain" else 0)
        rows.append(((rank, a.due_by or date.max, a.invoice_id, a.priority), {
            "invoice_id": a.invoice_id, "invoice_no": inv.invoice_no,
            "buyer_name": _invoice_summary(s, inv)["buyer_name"], "risk_tier": inv.risk_tier,
            "check_id": a.check_id, "severity": sev, "check_status": chk.status if chk else None,
            "title": a.title, "rationale": a.rationale, "due_by": a.due_by, "owner_role": a.owner_role,
            "priority_in_invoice": a.priority}))
    rows.sort(key=lambda kv: kv[0])
    return [r for _, r in rows[:limit]]


def _get_invoice(s: Session, invoice_id: int) -> Invoice:
    inv = s.get(Invoice, invoice_id)
    if inv is None:
        raise HTTPException(404, "Invoice not found.")
    return inv


@router.get("/invoices/{invoice_id}")
def get_invoice(invoice_id: int, s: Session = Depends(get_session)):
    inv = _get_invoice(s, invoice_id)
    out = _invoice_summary(s, inv)
    out["analysis"] = json.loads(inv.analysis_json) if inv.analysis_json else None
    out["processing_ms"] = inv.processing_ms
    if inv.package_id:
        out["documents"] = package_view(s, s.get(Package, inv.package_id))["documents"]
    return out


@router.get("/invoices/{invoice_id}/graph")
def get_graph(invoice_id: int, s: Session = Depends(get_session)):
    inv = _get_invoice(s, invoice_id)
    if not inv.analysis_json:
        raise HTTPException(409, "Invoice has not been processed yet.")
    return json.loads(inv.analysis_json)["graph"]


# ---------------------------------------------------------------- follow-ups
def _followup_view(f: Followup) -> dict:
    return {"id": f.id, "invoice_id": f.invoice_id, "step": f.step,
            "step_label": f"D{f.step:+d}", "send_on": f.send_on,
            "past": bool(f.send_on and f.send_on < _today()), "channel": f.channel, "tone": f.tone,
            "draft_text": f.draft_text, "status": f.status}


@router.post("/invoices/{invoice_id}/followups/generate")
def followups_generate(invoice_id: int, tone: str = Query(default="friendly", pattern="^(friendly|firm)$"),
                       channel: str = Query(default="email", pattern="^(email|whatsapp)$"),
                       s: Session = Depends(get_session)):
    _get_invoice(s, invoice_id)
    try:
        rows = generate_followups(s, invoice_id, tone=tone, channel=channel, today=_today())
    except PackageError as exc:
        raise HTTPException(409, str(exc))
    return {"invoice_id": invoice_id, "note": "Drafts only. Nothing is sent.",
            "followups": [_followup_view(f) for f in rows]}


@router.get("/invoices/{invoice_id}/followups")
def followups_list(invoice_id: int, tone: Optional[str] = None, channel: Optional[str] = None,
                   s: Session = Depends(get_session)):
    _get_invoice(s, invoice_id)
    q = select(Followup).where(Followup.invoice_id == invoice_id)
    if tone:
        q = q.where(Followup.tone == tone)
    if channel:
        q = q.where(Followup.channel == channel)
    rows = s.exec(q.order_by(Followup.tone, Followup.channel, Followup.step)).all()
    return [_followup_view(f) for f in rows]


# ---------------------------------------------------------------- dispute pack
@router.get("/invoices/{invoice_id}/dispute-pack")
def get_dispute_pack(invoice_id: int, format: str = Query(default="pdf", pattern="^(pdf|md)$"),
                     s: Session = Depends(get_session)):
    from app.dispute.pack import to_markdown, to_pdf

    view = get_invoice(invoice_id, s)
    try:
        pack = dispute_pack(s, invoice_id, _today(), view)
    except PackageError as exc:
        raise HTTPException(409, str(exc))
    stem = "evidence-pack-" + "".join(c if c.isalnum() else "-" for c in (view["invoice_no"] or str(invoice_id)))
    if format == "pdf":
        try:
            return Response(to_pdf(pack), media_type="application/pdf",
                            headers={"Content-Disposition": f'attachment; filename="{stem}.pdf"',
                                     "X-Pack-Format": "pdf"})
        except Exception:  # noqa: BLE001 - spec §11: fall back to Markdown if PDF fails
            pass
    return Response(to_markdown(pack), media_type="text/markdown; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{stem}.md"',
                             "X-Pack-Format": "md" if format == "md" else "md-fallback"})


# ---------------------------------------------------------------- forecast
@router.get("/forecast")
def get_forecast(days: int = Query(default=30), s: Session = Depends(get_session)):
    if days not in (30, 60):
        raise HTTPException(400, "days must be 30 or 60.")
    return cash_forecast(s, _today(), days)


# ---------------------------------------------------------------- buyers
@router.get("/buyers")
def list_buyers(s: Session = Depends(get_session)):
    rows = []
    for b in s.exec(select(Buyer).order_by(Buyer.name)).all():
        rows.append({"id": b.id, "name": b.name, "gstin": b.gstin, "synthetic": b.synthetic,
                     "profile": compute_profile(buyer_history(s, b.id)).model_dump()})
    return rows


@router.get("/buyers/{buyer_id}/profile")
def buyer_profile(buyer_id: int, s: Session = Depends(get_session)):
    b = s.get(Buyer, buyer_id)
    if b is None:
        raise HTTPException(404, "Buyer not found.")
    return {"id": b.id, "name": b.name, "gstin": b.gstin, "synthetic": b.synthetic,
            **compute_profile(buyer_history(s, b.id)).model_dump()}
