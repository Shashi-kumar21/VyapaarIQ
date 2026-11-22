"""Regex/heuristic extractor for digital PDFs (EXTRACTOR=text).

Confidence policy:
  label found and parsed        0.85
  label absent on a readable doc value=None, 0.75  ("confidently absent")
  scanned / no text layer       value=None, 0.0   (uncertain -> checks become uncertain)
"""

from __future__ import annotations

import re
from typing import Any, Optional

from app.extraction.pdf_text import PdfContent
from app.matching.normalize import parse_amount, parse_date
from app.schemas import DOC_MODELS, BaseDoc, DocType, LineItem

FOUND, ABSENT = 0.85, 0.75
GSTIN = r"\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]"
SEP = r"\s*[:\-]\s*"


def _search(pages: list[str], pattern: str) -> tuple[Optional[str], Optional[int]]:
    for i, page in enumerate(pages, 1):
        m = re.search(pattern, page, re.IGNORECASE | re.MULTILINE)
        if m:
            return m.group(1).strip(), i
    return None, None


def _line_after(pages: list[str], label: str) -> tuple[Optional[str], Optional[int]]:
    for i, page in enumerate(pages, 1):
        lines = page.splitlines()
        for k, ln in enumerate(lines):
            if re.match(rf"^\s*{label}\s*:?\s*$", ln, re.IGNORECASE) and k + 1 < len(lines):
                return lines[k + 1].strip(), i
    return None, None


def _first_line(pages: list[str]) -> tuple[Optional[str], Optional[int]]:
    for ln in pages[0].splitlines() if pages else []:
        if ln.strip():
            return ln.strip(), 1
    return None, None


def _rows(pages: list[str], ncols: int) -> list[list[str]]:
    rows = []
    for page in pages:
        for ln in page.splitlines():
            cols = re.split(r"\s{2,}", ln.strip())
            if len(cols) == ncols and re.fullmatch(r"\d{1,3}", cols[0]):
                rows.append(cols)
    return rows


class TextExtractor:
    name = "text"

    def extract(self, f, content: PdfContent, doc_type: DocType) -> Optional[BaseDoc]:
        model = DOC_MODELS[doc_type]
        if content.is_scanned:
            return model()  # all fields confidence 0 -> uncertain
        p = content.pages
        out: dict[str, Any] = {}

        def put(name: str, raw: Optional[str], page: Optional[int], parse=None):
            if raw is None:
                out[name] = {"value": None, "confidence": ABSENT}
                return
            val = parse(raw) if parse else raw
            out[name] = {"value": val, "confidence": FOUND if val is not None else 0.3,
                         "source_page": page}

        supplier_doc = doc_type in (DocType.invoice, DocType.challan, DocType.eway)
        if supplier_doc:
            put("supplier_name", *_first_line(p))
            put("supplier_gstin", *_search(p, rf"^GSTIN{SEP}({GSTIN})"))
            if doc_type == DocType.eway:
                put("buyer_name", *_search(p, rf"Recipient{SEP}(.+)$"))
                put("buyer_gstin", *_search(p, rf"Recipient GSTIN{SEP}({GSTIN})"))
            else:
                put("buyer_name", *_line_after(p, "Bill To" if doc_type == DocType.invoice else "Consignee"))
                put("buyer_gstin", *_search(p, rf"(?:Buyer|Consignee) GSTIN{SEP}({GSTIN})"))
        else:
            put("buyer_name", *_first_line(p))
            put("buyer_gstin", *_search(p, rf"^GSTIN{SEP}({GSTIN})"))
            if doc_type == DocType.po:
                put("supplier_name", *_line_after(p, "Vendor"))
            else:
                put("supplier_name", *_search(p, rf"^Supplier{SEP}(.+)$"))
            put("supplier_gstin", *_search(p, rf"(?:Vendor|Supplier) GSTIN{SEP}({GSTIN})"))
        put("supplier_udyam", *_search(p, r"(UDYAM-[A-Z]{2}-\d{2}-\d{7})"))
        put("po_reference", *_search(
            p, rf"(?:Buyer PO No|PO Ref(?:erence)?|Order Reference|PO No|Buyer'?s Order No)\.?{SEP}(\S+)"))

        getattr(self, f"_{doc_type.value}", lambda *_: None)(p, put, out)
        no_key = {"invoice": "invoice_no", "po": "po_no", "challan": "challan_no",
                  "eway": "eway_no", "grn": "grn_no"}.get(doc_type.value)
        date_key = {"invoice": "invoice_date", "po": "po_date", "challan": "challan_date",
                    "eway": "generated_date", "grn": "grn_date"}.get(doc_type.value)
        if no_key and no_key in out:
            out["doc_no"] = out[no_key]
        if date_key and date_key in out:
            out["doc_date"] = out[date_key]
        return model(**out)

    # ---- per doc type ------------------------------------------------------
    @staticmethod
    def _terms(p, put):
        text, page = _search(p, rf"Payment Terms{SEP}(.+)$")
        put("payment_terms_text", text, page)
        days = None
        if text:
            m = re.search(r"(\d{1,3})\s*days", text, re.IGNORECASE)
            days = m.group(1) if m else None
        put("payment_terms_days", days, page, int)

    @staticmethod
    def _priced_items(p) -> Optional[list[LineItem]]:
        rows = _rows(p, 7)
        if not rows:
            return None
        return [LineItem(desc=r[1], hsn=r[2], qty=parse_amount(r[3]), unit=r[4],
                         rate=parse_amount(r[5]), amount=parse_amount(r[6])) for r in rows]

    def _invoice(self, p, put, out):
        put("invoice_no", *_search(p, rf"(?:Invoice No\.?|Invoice Number|Inv\.? No\.?){SEP}(\S+)"))
        put("invoice_date", *_search(p, rf"Invoice Date{SEP}(.+)$"), parse_date)
        put("taxable_value", *_search(p, rf"Taxable Value{SEP}([\d,]+\.?\d*)"), parse_amount)
        for tax in ("cgst", "sgst", "igst"):
            raw, page = _search(p, rf"{tax}[^:\n]*:\s*([\d,]+\.?\d*)")
            if raw is None:  # absent tax line = zero tax, confidently
                out[tax] = {"value": 0.0, "confidence": ABSENT}
            else:
                put(tax, raw, page, parse_amount)
        put("total", *_search(p, rf"(?:Grand Total|Invoice Total|Total Amount){SEP}([\d,]+\.?\d*)"),
            parse_amount)
        self._terms(p, put)
        put("irn", *_search(p, rf"IRN{SEP}(\S+)"))
        bank = re.search(r"IFSC|A/c No", "\n".join(p), re.IGNORECASE)
        out["bank_details_present"] = {"value": bool(bank), "confidence": FOUND}
        items = self._priced_items(p)
        out["line_items"] = {"value": items, "confidence": FOUND if items else ABSENT}

    def _po(self, p, put, out):
        put("po_no", *_search(p, rf"PO No\.?{SEP}(\S+)"))
        put("po_date", *_search(p, rf"PO Date{SEP}(.+)$"), parse_date)
        put("delivery_date", *_search(p, rf"Delivery (?:By|Date){SEP}(.+)$"), parse_date)
        put("po_total", *_search(p, rf"PO Total[^:\n]*:\s*([\d,]+\.?\d*)"), parse_amount)
        self._terms(p, put)
        items = self._priced_items(p)
        out["line_items"] = {"value": items, "confidence": FOUND if items else ABSENT}

    def _challan(self, p, put, out):
        put("challan_no", *_search(p, rf"Challan No\.?{SEP}(\S+)"))
        put("challan_date", *_search(p, rf"Challan Date{SEP}(.+)$"), parse_date)
        put("invoice_reference", *_search(p, rf"Against Invoice No\.?{SEP}(\S+)"))
        put("vehicle_no", *_search(p, rf"Vehicle No\.?{SEP}(\S+)"))
        who, page = _search(p, rf"Received By{SEP}(.+)$")
        put("received_by_name", None if not who or "__" in who else who, page)
        put("received_date", *_search(p, rf"Received Date{SEP}(.+)$"), parse_date)
        text = "\n".join(p)
        out["received_stamp_present"] = {"value": bool(re.search(r"^\s*RECEIVED\b", text, re.M)),
                                         "confidence": ABSENT}
        out["received_signature_present"] = {"value": bool(re.search(r"\(signed\)", text, re.I)),
                                             "confidence": ABSENT}
        rows = _rows(p, 3)
        items = [LineItem(desc=r[1], qty=parse_amount(r[2])) for r in rows] or None
        out["line_items"] = {"value": items, "confidence": FOUND if items else ABSENT}

    def _eway(self, p, put, out):
        put("eway_no", *_search(p, rf"E-?Way Bill No\.?{SEP}(\d+)"))
        put("generated_date", *_search(p, rf"Generated (?:Date|On){SEP}(.+)$"), parse_date)
        put("valid_until", *_search(p, rf"Valid (?:Upto|Until){SEP}(.+)$"), parse_date)
        put("invoice_reference", *_search(p, rf"Document No[^:\n]*:\s*(\S+)"))
        put("value", *_search(p, rf"Value of Goods{SEP}([\d,]+\.?\d*)"), parse_amount)
        put("vehicle_no", *_search(p, rf"Vehicle No\.?{SEP}(\S+)"))

    def _grn(self, p, put, out):
        put("grn_no", *_search(p, rf"GRN No\.?{SEP}(\S+)"))
        put("grn_date", *_search(p, rf"GRN Date{SEP}(.+)$"), parse_date)
        put("invoice_reference", *_search(p, rf"Supplier Invoice No\.?{SEP}(\S+)"))
        put("accepted_by", *_search(p, rf"Accepted By{SEP}(.+)$"))
        put("remarks", *_search(p, rf"Remarks{SEP}(.+)$"))
        rows = _rows(p, 4)
        items = [LineItem(desc=r[1], qty_received=parse_amount(r[2]), qty_accepted=parse_amount(r[3]))
                 for r in rows] or None
        out["line_items"] = {"value": items, "confidence": FOUND if items else ABSENT}
