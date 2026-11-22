"""Extraction prompts per doc type (T2.2, BUILD_SPEC §6 rules)."""

from __future__ import annotations

from app.schemas import DOC_MODELS, DocType

SYSTEM = """You extract structured fields from Indian business documents \
(GST tax invoices, purchase orders, delivery challans, e-way bills, goods \
receipt notes, contracts) for an MSME supplier's receivables tool.

Return only one JSON object, no prose and no code fences.

Rules:
- For every requested field return {"value": ..., "confidence": 0..1, "source_page": n or null}.
- If a field is not on the document, return value null with a high confidence \
(you are sure it is absent). If you cannot read it, return value null with a low confidence.
- Never guess or compute a value that is not printed. Do not invent document numbers.
- Dates as ISO YYYY-MM-DD. Amounts as plain numbers in INR (no symbols, no commas).
- payment_terms_text must quote the exact source wording.
- Boolean fields (e.g. received_stamp_present) are true only if visibly present.
- line_items: list of objects with the keys given; use null for missing columns.
"""

LINE_KEYS = {
    DocType.invoice: ["desc", "hsn", "qty", "unit", "rate", "amount"],
    DocType.po: ["desc", "hsn", "qty", "unit", "rate", "amount"],
    DocType.challan: ["desc", "qty"],
    DocType.grn: ["desc", "qty_received", "qty_accepted"],
}
SKIP = {"doc_type", "filename", "page_count", "extractor", "fallback"}


def field_names(doc_type: DocType) -> list[str]:
    return [k for k in DOC_MODELS[doc_type].model_fields if k not in SKIP]


def user_prompt(doc_type: DocType) -> str:
    fields = ", ".join(field_names(doc_type))
    lines = LINE_KEYS.get(doc_type)
    extra = f"\nEach line_items entry has keys: {', '.join(lines)}." if lines else ""
    return (f"Document type: {doc_type.value}.\nExtract these fields: {fields}.{extra}\n"
            "Respond with the JSON object only.")
