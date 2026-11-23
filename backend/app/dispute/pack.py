"""Dispute evidence pack (BUILD_SPEC §11): one structure, two renderers.

``build_pack`` gathers facts deterministically from the stored analysis and
extracted documents. ``to_markdown`` always works; ``to_pdf`` uses reportlab
and the caller falls back to Markdown if it fails. Only key fields are
included, never full document text.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from io import BytesIO
from typing import Any, Optional

from app.fmt import d, inr
from app.rules.interest import estimate_interest

FOOTER = "Generated assistance, not legal advice. Figures are estimates; verify before use."
DOC_LABELS = {"invoice": "Tax invoice", "po": "Purchase order", "challan": "Delivery challan / LR",
              "eway": "E-way bill", "grn": "GRN / acceptance", "contract": "Contract / terms",
              "other": "Other document"}
# Per doc type: (field, label) shown in the document index.
KEY_FIELDS = {
    "invoice": [("invoice_no", "No."), ("invoice_date", "Date"), ("total", "Total"), ("po_reference", "PO ref")],
    "po": [("po_no", "No."), ("po_date", "Date"), ("po_total", "Total"), ("payment_terms_text", "Terms")],
    "challan": [("challan_no", "No."), ("challan_date", "Date"), ("received_date", "Received"),
                ("received_by_name", "Received by")],
    "eway": [("eway_no", "No."), ("generated_date", "Date"), ("value", "Value")],
    "grn": [("grn_no", "No."), ("grn_date", "Date"), ("accepted_by", "Accepted by")],
    "contract": [("payment_terms_text", "Terms")],
}
AMOUNT_FIELDS = {"total", "po_total", "value"}


@dataclass
class Section:
    title: str
    paragraphs: list[str] = field(default_factory=list)
    table: Optional[list[list[str]]] = None  # first row = header


@dataclass
class Pack:
    title: str
    subtitle: str
    sections: list[Section]
    footer: str = FOOTER


def _val(fields: Optional[dict], name: str) -> Any:
    f = (fields or {}).get(name)
    return f.get("value") if isinstance(f, dict) else None


def _date(v: Any) -> Optional[date]:
    if isinstance(v, date):
        return v
    try:
        return date.fromisoformat(str(v)) if v else None
    except ValueError:
        return None


def build_pack(*, invoice: dict, analysis: dict, documents: list[dict], supplier: Optional[dict],
               today: date, rupee: str = "₹") -> Pack:
    """``invoice`` = API invoice summary, ``analysis`` = stored Analysis JSON,
    ``documents`` = package_view documents (with ``fields``)."""
    def money(x):
        return inr(x, rupee)

    due = analysis.get("due") or {}
    checks = analysis.get("checks") or []
    due_date = _date(due.get("due_date"))
    amount = invoice.get("amount_total")
    sup = supplier or {}
    by_type: dict[str, dict] = {}
    for doc in documents:
        by_type.setdefault(doc["doc_type"], doc.get("fields") or {})

    # Cover summary
    blockers = [c for c in checks if c["status"] != "pass" and c["severity"] == "blocker"]
    score = analysis.get("score") or {}
    cover = Section("Summary", [
        f"Supplier: {sup.get('name') or '-'} (GSTIN {sup.get('gstin') or '-'}, "
        f"Udyam {sup.get('udyam_no') or 'not on record'}).",
        f"Buyer: {invoice.get('buyer_name') or analysis.get('buyer_name') or '-'}.",
        f"Invoice {invoice.get('invoice_no') or '-'} dated {d(_date(invoice.get('invoice_date')))} for "
        f"{money(amount)}; estimated due date {d(due_date)}.",
        f"Readiness score {score.get('score', '-')} / 100 (tier {score.get('tier', '-')}); "
        f"{len(blockers)} blocker issue(s) open. Illustrative score, not a prediction of payment.",
    ])

    inv_f = by_type.get("invoice", {})
    facts = Section("Invoice facts", table=[["Field", "Value"]] + [
        ["Invoice no.", str(invoice.get("invoice_no") or "-")],
        ["Invoice date", d(_date(invoice.get("invoice_date")))],
        ["Taxable value", money(_val(inv_f, "taxable_value"))],
        ["CGST / SGST / IGST", " / ".join(money(_val(inv_f, k)) for k in ("cgst", "sgst", "igst"))],
        ["Total", money(amount)],
        ["PO reference", str(_val(inv_f, "po_reference") or "-")],
        ["Payment terms (as written)", str(_val(inv_f, "payment_terms_text")
                                           or _val(by_type.get("po"), "payment_terms_text") or "-")],
    ])

    index_rows = [["#", "Document", "File", "Key fields", "Conf."]]
    for i, doc in enumerate(documents, 1):
        fields = doc.get("fields") or {}
        keys = []
        for name, label in KEY_FIELDS.get(doc["doc_type"], []):
            v = _val(fields, name)
            if v is not None:
                keys.append(f"{label}: {money(v) if name in AMOUNT_FIELDS else v}")
        conf = doc.get("extraction_conf")
        index_rows.append([str(i), DOC_LABELS.get(doc["doc_type"], doc["doc_type"]), doc["filename"],
                           "; ".join(keys) or (doc.get("error") or "-"),
                           f"{conf:.2f}" if isinstance(conf, (int, float)) else "-"])
    index = Section("Document index", table=index_rows)

    po_f, ch_f, grn_f = by_type.get("po"), by_type.get("challan"), by_type.get("grn")
    events = [
        ("Purchase order", _date(_val(po_f, "po_date"))),
        ("Invoice issued", _date(invoice.get("invoice_date"))),
        ("Goods dispatched (challan)", _date(_val(ch_f, "challan_date"))),
        ("Goods received (challan)", _date(_val(ch_f, "received_date"))),
        ("GRN / acceptance", _date(_val(grn_f, "grn_date"))),
        (f"Acceptance used for due date ({due.get('acceptance_basis', 'unknown')})",
         _date(due.get("acceptance_date"))),
        ("Due date (estimated)", due_date),
        ("Today", today),
    ]
    timeline = Section("Timeline", table=[["Date", "Event"]] + [
        [x.isoformat(), label] for label, x in sorted((e for e in events if e[1]), key=lambda e: e[1])])
    missing_events = [label for label, x in events if x is None]
    if missing_events:
        timeline.paragraphs.append("Not found in the documents: " + ", ".join(missing_events) + ".")

    checks_sec = Section("Verification checks", table=[["Check", "Status", "Severity", "Detail"]] + [
        [f"{c['check_id']} {c['name']}", c["status"], c["severity"], c["detail"]] for c in checks])

    due_sec = Section("Due date and reasoning", [
        f"Estimated due date: {d(due_date)}.",
        due.get("reasoning") or "No reasoning recorded.",
        "Marked uncertain: an input could not be read reliably." if due.get("uncertain") else "",
    ])

    est = estimate_interest(float(amount or 0.0), due_date, today)
    if est.computable and est.days_late > 0:
        interest_text = [f"Principal {money(est.principal)}, {est.days_late} day(s) late as of {d(today)}, "
                         f"annual rate {est.annual_rate_pct:g}%: estimated interest {money(est.interest)}.",
                         f"Formula: {est.formula}.", est.note]
    elif est.computable:
        interest_text = [f"Not yet overdue as of {d(today)}; no interest accrued.", est.note]
    else:
        interest_text = [est.formula, est.note]
    interest_sec = Section("Estimated statutory interest", interest_text)

    gaps = [c for c in checks if c["status"] in ("fail", "missing") and c["severity"] in ("blocker", "warning")]
    unsure = [c for c in checks if c["status"] == "uncertain"]
    missing_sec = Section("Missing or weak evidence",
                          [f"{c['check_id']} {c['name']}: {c['detail']}" for c in gaps]
                          + [f"{c['check_id']} {c['name']}: needs human check ({c['detail']})" for c in unsure]
                          or ["No evidence gaps detected by the automated checks."])

    steps = [a["title"] for a in (analysis.get("actions") or [])[:3]]
    msmed = due.get("msmed_applies", True)
    next_sec = Section("Suggested next step", [
        ("Close these gaps first: " + "; ".join(steps) + ".") if steps else "Evidence set looks complete.",
        ("If payment remains overdue, a Micro/Small supplier may file a delayed-payment reference on the "
         "MSME ODR portal with this pack attached (verify the current process before filing)."
         if msmed else "MSMED delayed-payment remedies apply only to micro/small suppliers; seek advice."),
    ])

    sections = [cover, facts, index, timeline, checks_sec, due_sec, interest_sec, missing_sec, next_sec]
    for s in sections:
        s.paragraphs = [p for p in s.paragraphs if p]
    return Pack(title=f"Evidence pack: invoice {invoice.get('invoice_no') or invoice.get('id')}",
                subtitle=f"Prepared {d(today)} - estimated, not legal advice, verify before use",
                sections=sections)


# ---------------------------------------------------------------- renderers
def _md_cell(x: str) -> str:
    return str(x).replace("|", "\\|").replace("\n", " ")


def to_markdown(pack: Pack) -> str:
    out = [f"# {pack.title}", "", f"_{pack.subtitle}_", ""]
    for s in pack.sections:
        out += [f"## {s.title}", ""]
        out += [p + "\n" for p in s.paragraphs]
        if s.table:
            out.append("| " + " | ".join(_md_cell(c) for c in s.table[0]) + " |")
            out.append("|" + "---|" * len(s.table[0]))
            out += ["| " + " | ".join(_md_cell(c) for c in row) + " |" for row in s.table[1:]]
            out.append("")
    out += ["---", f"_{pack.footer}_", ""]
    return "\n".join(out)


PDF_SAFE = {"₹": "Rs. ", "↔": "<->", "≥": ">=", "≤": "<=", "–": "-", "—": "-",
            "’": "'", "“": '"', "”": '"', "×": "x"}


def pdf_safe(text: str) -> str:
    """Core PDF fonts (Helvetica) cannot draw the rupee sign or arrows; swap them for ASCII."""
    for k, v in PDF_SAFE.items():
        text = text.replace(k, v)
    return text


def to_pdf(pack: Pack) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    from xml.sax.saxutils import escape as _escape

    def escape(x: str) -> str:
        return _escape(pdf_safe(x))

    ss = getSampleStyleSheet()
    small = ss["BodyText"].clone("small", fontSize=8, leading=10)
    buf = BytesIO()

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica-Oblique", 7)
        canvas.drawString(15 * mm, 10 * mm, pdf_safe(f"{pack.footer}  |  page {doc.page}"))
        canvas.restoreState()

    story = [Paragraph(escape(pack.title), ss["Title"]), Paragraph(escape(pack.subtitle), ss["Italic"]),
             Spacer(1, 6)]
    width = A4[0] - 30 * mm
    for s in pack.sections:
        story.append(Paragraph(escape(s.title), ss["Heading2"]))
        story += [Paragraph(escape(p), ss["BodyText"]) for p in s.paragraphs]
        if s.table:
            data = [[Paragraph(escape(str(c)), small) for c in row] for row in s.table]
            t = Table(data, repeatRows=1, colWidths=[width / len(s.table[0])] * len(s.table[0]))
            t.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8ecf2")),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#9aa5b1")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]))
            story += [Spacer(1, 4), t]
        story.append(Spacer(1, 6))
    SimpleDocTemplate(buf, pagesize=A4, leftMargin=15 * mm, rightMargin=15 * mm, topMargin=15 * mm,
                      bottomMargin=18 * mm, title=pack.title).build(story, onFirstPage=footer,
                                                                    onLaterPages=footer)
    return buf.getvalue()
