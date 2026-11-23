"""Glue between the API, extraction, pipeline and the database.

Keeps routes thin. All deterministic logic lives in ``pipeline``.
"""

from __future__ import annotations

import json
import logging
import time
from datetime import date
from pathlib import Path
from typing import Optional

from sqlmodel import Session, select

from app.db.models import (ActionRow, Buyer, CheckResult, Document, Followup, Invoice, Package,
                           PaymentEvent, Supplier)
from app.db.session import DATA_DIR
from app.extraction.base import InputFile, classify, extract_file
from app.extraction.pdf_text import UnreadableFileError, read_document
from app.matching.checks import NoInvoiceError, state
from app.matching.graph import doc_confidence
from app.matching.normalize import normalize_gstin, normalize_ref, party_similarity
from app.pipeline import analyze, known_value
from app.rules.config import get_config
from app.schemas import DocType, ExtractedPackage

# T3.10: one line per processed package. Ids, counts and timings only, never document text
# (CLAUDE.md rule 4).
log = logging.getLogger("vyapaariq.processing")

UPLOAD_DIR = DATA_DIR / "uploads"
ALLOWED_EXT = (".pdf", ".png", ".jpg", ".jpeg")
MAX_FILE_BYTES = 15 * 1024 * 1024


class PackageError(ValueError):
    """Client-facing error with a clear message."""


def safe_name(name: str) -> str:
    base = Path(name or "file").name
    return "".join(c if c.isalnum() or c in "._- " else "_" for c in base)[:120] or "file"


# ---------------------------------------------------------------- upload
def create_package(s: Session, files: list[tuple[str, bytes]], buyer_name: Optional[str] = None,
                   doc_types: Optional[list[Optional[str]]] = None) -> Package:
    if not files:
        raise PackageError("No files uploaded.")
    for name, data in files:
        if not name.lower().endswith(ALLOWED_EXT):
            raise PackageError(f"Unsupported file type: {name}. Use PDF, PNG or JPG.")
        if not data:
            raise PackageError(f"{name} is empty.")
        if len(data) > MAX_FILE_BYTES:
            raise PackageError(f"{name} is larger than 15 MB.")

    supplier = s.exec(select(Supplier)).first()
    pkg = Package(supplier_id=supplier.id if supplier else None, buyer_name_hint=buyer_name)
    s.add(pkg)
    s.commit()
    s.refresh(pkg)

    pdir = UPLOAD_DIR / str(pkg.id)
    pdir.mkdir(parents=True, exist_ok=True)
    for i, (name, data) in enumerate(files):
        fname = safe_name(name)
        path = pdir / f"{i:02d}_{fname}"
        path.write_bytes(data)
        hint = (doc_types or [None] * len(files))[i] if doc_types and i < len(doc_types) else None
        try:
            content = read_document(data, fname)
            dt, _, method = classify(fname, content)
            err = None
        except UnreadableFileError as exc:
            dt, method, err = DocType.other, "none", str(exc)
        if hint and hint in DocType._value2member_map_:
            dt, method = DocType(hint), "user"
        f = InputFile(fname, data)
        s.add(Document(package_id=pkg.id, doc_type=dt.value, doc_type_method=method, filename=fname,
                       path=str(path), sha256=f.sha256, error=err))
    s.commit()
    s.refresh(pkg)
    return pkg


# ---------------------------------------------------------------- buyers
def resolve_buyer(s: Session, name: Optional[str], gstin: Optional[str]) -> Optional[Buyer]:
    if not name and not gstin:
        return None
    g = normalize_gstin(gstin)
    buyers = s.exec(select(Buyer)).all()
    if g:
        for b in buyers:
            if normalize_gstin(b.gstin) == g:
                return b
    if name:
        for b in buyers:
            names = [b.name] + json.loads(b.aliases_json or "[]")
            if any(party_similarity(name, n) >= 0.9 for n in names):
                return b
    b = Buyer(name=name or g, gstin=g or None)
    s.add(b)
    s.commit()
    s.refresh(b)
    return b


def duplicate_lookup_for(s: Session, exclude_package_id: Optional[int]):
    def lookup(invoice_no: str, gstin: Optional[str], name: Optional[str]) -> bool:
        norm = normalize_ref(invoice_no)
        rows = s.exec(select(Invoice).where(Invoice.invoice_no_norm == norm)).all()
        for inv in rows:
            if inv.package_id is not None and inv.package_id == exclude_package_id:
                continue
            buyer = s.get(Buyer, inv.buyer_id) if inv.buyer_id else None
            if buyer is None:
                return True
            if gstin and normalize_gstin(buyer.gstin) == normalize_gstin(gstin):
                return True
            if name and party_similarity(buyer.name, name) >= 0.9:
                return True
        return False
    return lookup


# ---------------------------------------------------------------- process
def process_package(s: Session, package_id: int, *, mode: Optional[str] = None,
                    today: Optional[date] = None) -> Invoice:
    pkg = s.get(Package, package_id)
    if pkg is None:
        raise PackageError("Package not found.")
    started = time.perf_counter()
    pkg.status, pkg.error = "processing", None
    s.add(pkg)
    s.commit()

    docs = s.exec(select(Document).where(Document.package_id == package_id)).all()
    extracted = []
    for d in docs:
        try:
            data = Path(d.path).read_bytes()
            doc = extract_file(InputFile(d.filename, data, DocType(d.doc_type)), mode=mode)
        except UnreadableFileError as exc:
            d.error = str(exc)
            s.add(d)
            continue
        except Exception:  # noqa: BLE001 - keep partial results, report clearly
            d.error = "Extraction failed for this file."
            s.add(d)
            continue
        d.extracted_json = doc.model_dump_json()
        d.extraction_conf = doc_confidence(doc)
        d.page_count, d.extractor, d.fallback, d.error = doc.page_count, doc.extractor, doc.fallback, None
        s.add(d)
        extracted.append(doc)
    s.commit()

    pkg_docs = ExtractedPackage(documents=extracted)
    try:
        a = analyze(pkg_docs, duplicate_lookup=duplicate_lookup_for(s, package_id), today=today)
    except NoInvoiceError as exc:
        pkg.status, pkg.error = "failed", str(exc)
        s.add(pkg)
        s.commit()
        log.warning("package %s failed after %d ms: no invoice found", package_id, int((time.perf_counter() - started) * 1000))
        raise PackageError(str(exc)) from exc
    except Exception as exc:  # noqa: BLE001 - never leave a package stuck in "processing"
        pkg.status, pkg.error = "failed", "Analysis failed for this package."
        s.add(pkg)
        s.commit()
        log.warning("package %s failed after %d ms: %s", package_id, int((time.perf_counter() - started) * 1000), type(exc).__name__)
        raise PackageError(pkg.error) from exc

    # Rule 3: only values read at or above the confidence threshold are stored or used to
    # identify the buyer. Uncertain values stay visible in the document fields for a human check.
    thr = float(get_config()["extraction"]["uncertain_below"])
    inv_doc = pkg_docs.first(DocType.invoice)
    buyer = resolve_buyer(s, known_value(inv_doc.buyer_name, thr) or pkg.buyer_name_hint,
                          known_value(inv_doc.buyer_gstin, thr))
    pkg.buyer_id = buyer.id if buyer else None

    inv = s.exec(select(Invoice).where(Invoice.package_id == package_id)).first() or Invoice(package_id=package_id)
    gst_fields = (inv_doc.cgst, inv_doc.sgst, inv_doc.igst)
    gst = None
    if all(state(f, thr) != "uncertain" for f in gst_fields):
        gst = sum(f.value for f in gst_fields if f.value) or None
    inv.buyer_id = pkg.buyer_id
    inv.invoice_no = a.invoice_no
    inv.invoice_no_norm = normalize_ref(a.invoice_no) if a.invoice_no else None
    inv.invoice_date = known_value(inv_doc.invoice_date, thr)
    inv.amount_total, inv.amount_taxable, inv.gst_amount = (a.amount_total,
                                                            known_value(inv_doc.taxable_value, thr), gst)
    inv.payment_terms_days = a.due.terms_days_applied
    inv.due_date = a.due.due_date
    inv.readiness_score, inv.risk_tier = a.score.score, a.score.tier.value
    inv.analysis_json = a.model_dump_json(by_alias=True)
    inv.processing_ms = int((time.perf_counter() - started) * 1000)
    s.add(inv)
    s.commit()
    s.refresh(inv)

    for old in s.exec(select(CheckResult).where(CheckResult.invoice_id == inv.id)).all():
        s.delete(old)
    for old in s.exec(select(ActionRow).where(ActionRow.invoice_id == inv.id)).all():
        s.delete(old)
    for c in a.checks:
        s.add(CheckResult(invoice_id=inv.id, check_id=c.check_id, status=c.status.value,
                          severity=c.severity.value,
                          detail_json=json.dumps({"detail": c.detail, "facts": c.facts}, default=str)))
    for act in a.actions:
        s.add(ActionRow(invoice_id=inv.id, priority=act.priority, check_id=act.check_id, title=act.title,
                        rationale=act.rationale, due_by=act.due_by, owner_role=act.owner_role))
    pkg.status = "done"
    s.add(pkg)
    s.commit()
    s.refresh(inv)
    log.info("package %s -> invoice %s: %d document(s), extractor %s%s, %d ms", package_id, inv.id,
             len(docs), a.extractor_used, " (fallback)" if a.fallback_used else "", inv.processing_ms)
    return inv


# ---------------------------------------------------------------- history / forecast
def buyer_history(s: Session, buyer_id: int) -> list[tuple[date, date]]:
    """[(due_date, last paid_on)] for this buyer's paid invoices (seeded + real)."""
    out = []
    for inv in s.exec(select(Invoice).where(Invoice.buyer_id == buyer_id)).all():
        pays = s.exec(select(PaymentEvent).where(PaymentEvent.invoice_id == inv.id)).all()
        if inv.due_date and pays:
            out.append((inv.due_date, max(p.paid_on for p in pays)))
    return out


def cash_forecast(s: Session, today: date, days: int) -> dict:
    from app.forecast.cash_at_risk import OpenInvoice, forecast
    from app.scoring.buyer_profile import compute_profile

    medians: dict[int, Optional[float]] = {}
    names: dict[int, str] = {}
    rows = []
    q = select(Invoice).where(Invoice.status == "open", Invoice.synthetic == False)  # noqa: E712
    for inv in s.exec(q).all():
        bid = inv.buyer_id
        if bid is not None and bid not in medians:
            medians[bid] = compute_profile(buyer_history(s, bid)).median_days_late
            b = s.get(Buyer, bid)
            names[bid] = b.name if b else None
        dup = s.exec(select(CheckResult).where(CheckResult.invoice_id == inv.id, CheckResult.check_id == "C14",
                                               CheckResult.status == "fail")).first() is not None
        rows.append(OpenInvoice(id=inv.id, invoice_no=inv.invoice_no, buyer_id=bid,
                                buyer_name=names.get(bid), amount=inv.amount_total, due_date=inv.due_date,
                                risk_tier=inv.risk_tier, buyer_median_late=medians.get(bid),
                                duplicate_suspect=dup))
    return forecast(rows, today, days)


def supplier_info(s: Session, inv: Invoice) -> dict:
    """Supplier row if seeded, else the supplier named on the invoice itself."""
    sup = s.exec(select(Supplier)).first()
    if sup is not None:
        return sup.model_dump()
    fields = {}
    if inv.package_id:
        for doc in s.exec(select(Document).where(Document.package_id == inv.package_id,
                                                 Document.doc_type == "invoice")).all():
            fields = json.loads(doc.extracted_json) if doc.extracted_json else {}
            break
    val = lambda k: (fields.get(k) or {}).get("value")  # noqa: E731
    return {"name": val("supplier_name"), "gstin": val("supplier_gstin"), "udyam_no": val("supplier_udyam")}


# ---------------------------------------------------------------- follow-ups
def _attachments(s: Session, inv: Invoice) -> list[str]:
    from app.dispute.pack import DOC_LABELS

    if not inv.package_id:
        return []
    out = []
    for doc in s.exec(select(Document).where(Document.package_id == inv.package_id)).all():
        if doc.error or doc.doc_type == "other":
            continue
        no = None
        if doc.extracted_json:
            no = (json.loads(doc.extracted_json).get("doc_no") or {}).get("value")
        out.append(DOC_LABELS.get(doc.doc_type, doc.doc_type) + (f" {no}" if no else ""))
    return out


def generate_followups(s: Session, invoice_id: int, *, tone: str, channel: str,
                       today: Optional[date] = None) -> list[Followup]:
    """Replace this invoice's drafts for ``channel`` + ``tone`` with a fresh set. Never sends."""
    from app.followups.drafts import FollowupContext, build_followups, buyer_requests

    inv = s.get(Invoice, invoice_id)
    if inv is None:
        raise LookupError("Invoice not found.")
    if not inv.analysis_json:
        raise PackageError("Invoice has not been processed yet.")
    if inv.due_date is None:
        raise PackageError("No due date could be determined for this invoice; "
                           "resolve acceptance and payment terms first.")
    a = json.loads(inv.analysis_json)
    buyer = s.get(Buyer, inv.buyer_id) if inv.buyer_id else None
    supplier = supplier_info(s, inv)
    checks = {c["check_id"]: c for c in a.get("checks", [])}
    missing = buyer_requests([cid for cid, c in checks.items()
                              if c["status"] in ("fail", "missing") and c["severity"] != "info"])
    due = a.get("due", {})
    ctx = FollowupContext(
        invoice_no=inv.invoice_no or f"#{inv.id}", amount=inv.amount_total, due_date=inv.due_date,
        due_reasoning=due.get("reasoning", ""),
        buyer_name=(buyer.name if buyer else a.get("buyer_name")) or "Buyer",
        supplier_name=supplier.get("name") or "the supplier",
        msmed_applies=due.get("msmed_applies", True),
        udyam_on_record=checks.get("C13", {}).get("status") == "pass",
        due_basis=due.get("acceptance_basis", "unknown"), due_uncertain=bool(due.get("uncertain")),
        missing=missing, attachments=_attachments(s, inv))
    drafts = build_followups(ctx, tone=tone, channel=channel, today=today)
    q = select(Followup).where(Followup.invoice_id == inv.id, Followup.tone == tone, Followup.channel == channel)
    for old in s.exec(q).all():
        s.delete(old)
    rows = [Followup(invoice_id=inv.id, step=dr.step, send_on=dr.send_on, channel=dr.channel, tone=dr.tone,
                     draft_text=dr.text, status="draft") for dr in drafts]
    s.add_all(rows)
    s.commit()
    for r in rows:
        s.refresh(r)
    return rows


# ---------------------------------------------------------------- dispute pack
def dispute_pack(s: Session, invoice_id: int, today: date, invoice_view: dict):
    from app.dispute.pack import build_pack

    inv = s.get(Invoice, invoice_id)
    if inv is None:
        raise LookupError("Invoice not found.")
    if not inv.analysis_json:
        raise PackageError("Invoice has not been processed yet.")
    return build_pack(invoice=invoice_view, analysis=json.loads(inv.analysis_json),
                      documents=invoice_view.get("documents") or [],
                      supplier=supplier_info(s, inv), today=today)
