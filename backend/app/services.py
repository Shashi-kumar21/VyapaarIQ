"""Glue between the API, extraction, pipeline and the database.

Keeps routes thin. All deterministic logic lives in ``pipeline``.
"""

from __future__ import annotations

import json
import time
from datetime import date
from pathlib import Path
from typing import Optional

from sqlmodel import Session, select

from app.db.models import ActionRow, Buyer, CheckResult, Document, Invoice, Package, Supplier
from app.db.session import DATA_DIR
from app.extraction.base import InputFile, classify, extract_file
from app.extraction.pdf_text import UnreadableFileError, read_document
from app.matching.checks import NoInvoiceError
from app.matching.graph import doc_confidence
from app.matching.normalize import normalize_gstin, normalize_ref, party_similarity
from app.pipeline import analyze
from app.schemas import DocType, ExtractedPackage

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
        raise PackageError(str(exc)) from exc

    inv_doc = pkg_docs.first(DocType.invoice)
    buyer = resolve_buyer(s, inv_doc.buyer_name.value or pkg.buyer_name_hint, inv_doc.buyer_gstin.value)
    pkg.buyer_id = buyer.id if buyer else None

    inv = s.exec(select(Invoice).where(Invoice.package_id == package_id)).first() or Invoice(package_id=package_id)
    gst = sum(v for v in (inv_doc.cgst.value, inv_doc.sgst.value, inv_doc.igst.value) if v) or None
    inv.buyer_id = pkg.buyer_id
    inv.invoice_no = a.invoice_no
    inv.invoice_no_norm = normalize_ref(a.invoice_no) if a.invoice_no else None
    inv.invoice_date = inv_doc.invoice_date.value
    inv.amount_total, inv.amount_taxable, inv.gst_amount = a.amount_total, inv_doc.taxable_value.value, gst
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
    return inv
