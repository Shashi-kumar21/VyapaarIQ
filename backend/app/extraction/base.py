"""Extractor interface, doc-type classifier and the fallback chain (§4, T4.8).

Modes (``EXTRACTOR`` env var): ``claude`` -> ``text`` -> ``fixture``.
Each extractor returns a document or ``None`` when it cannot handle the file
(no API key, no ground-truth match). With fallback on, the next extractor is
tried and the document is flagged ``fallback=True`` ("demo fallback" badge).
"""

from __future__ import annotations

import hashlib
import os
import re
from dataclasses import dataclass, field
from typing import Optional, Protocol

from app.extraction.pdf_text import PdfContent, read_document
from app.schemas import DOC_MODELS, BaseDoc, DocType, ExtractedPackage


@dataclass
class InputFile:
    filename: str
    data: bytes
    doc_type_hint: Optional[DocType] = None
    sha256: str = field(init=False)

    def __post_init__(self) -> None:
        self.sha256 = hashlib.sha256(self.data).hexdigest()


class Extractor(Protocol):
    name: str

    def extract(self, f: InputFile, content: PdfContent, doc_type: DocType) -> Optional[BaseDoc]:
        ...


# ---------------------------------------------------------------- classifier
_NAME_HINTS = [
    (DocType.eway, r"e[-_ ]?way|ewb"),
    (DocType.grn, r"grn|goods[-_ ]?receipt|acceptance"),
    (DocType.challan, r"challan|\bdc\b|_dc_|delivery|\blr\b|lorry"),
    (DocType.po, r"\bpo\b|_po[_.]|purchase[-_ ]?order"),
    (DocType.contract, r"contract|agreement|terms"),
    (DocType.invoice, r"invoice|\binv\b|_inv[_.]|bill"),
]
_TEXT_HINTS = [
    (DocType.eway, r"E-?\s*WAY\s+BILL"),
    (DocType.grn, r"GOODS\s+RECEIPT\s+NOTE|\bGRN\s+NO\b"),
    (DocType.challan, r"DELIVERY\s+CHALLAN|LORRY\s+RECEIPT"),
    (DocType.po, r"PURCHASE\s+ORDER"),
    (DocType.contract, r"AGREEMENT|CONTRACT"),
    (DocType.invoice, r"TAX\s+INVOICE|\bINVOICE\b"),
]


def classify(filename: str, content: Optional[PdfContent]) -> tuple[DocType, float, str]:
    """Return (doc_type, confidence, method). First-page keywords beat filename."""
    if content and content.pages and content.pages[0].strip():
        head = content.pages[0][:600].upper()
        for dt, pat in _TEXT_HINTS:
            if re.search(pat, head):
                return dt, 0.9, "keywords"
    stem = os.path.basename(filename).lower()
    for dt, pat in _NAME_HINTS:
        if re.search(pat, stem):
            return dt, 0.7, "filename"
    return DocType.other, 0.2, "none"


# ---------------------------------------------------------------- chain
def _chain(mode: str, allow_fallback: bool) -> list[str]:
    order = {"claude": ["claude", "text", "fixture"], "text": ["text", "fixture"], "fixture": ["fixture"]}
    chain = order.get(mode, order["text"])
    return chain if allow_fallback else chain[:1]


def get_extractor(name: str) -> Extractor:
    if name == "fixture":
        from app.extraction.fixture import FixtureExtractor
        return FixtureExtractor()
    if name == "text":
        from app.extraction.text_extractor import TextExtractor
        return TextExtractor()
    if name == "claude":
        from app.extraction.claude_extractor import ClaudeExtractor
        return ClaudeExtractor()
    raise ValueError(f"Unknown extractor {name!r}")


def _usable(doc: Optional[BaseDoc], thr: float = 0.6) -> bool:
    if doc is None:
        return False
    for k in doc.__class__.model_fields:
        f = getattr(doc, k)
        if hasattr(f, "confidence") and f.value is not None and f.confidence >= thr:
            return True
    return False


def extract_file(f: InputFile, *, mode: Optional[str] = None, allow_fallback: bool = True) -> BaseDoc:
    """Extract one file. Raises ``UnreadableFileError`` for corrupt input."""
    mode = (mode or os.environ.get("EXTRACTOR", "text")).lower()
    content = read_document(f.data, f.filename)
    doc_type = f.doc_type_hint or classify(f.filename, content)[0]
    chain = _chain(mode, allow_fallback)
    candidate: Optional[BaseDoc] = None
    for i, name in enumerate(chain):
        try:
            doc = get_extractor(name).extract(f, content, doc_type)
        except Exception:  # noqa: BLE001 - an extractor failure must not kill the package
            doc = None
        if doc is not None:
            doc.extractor, doc.fallback = name, i > 0
            doc.filename, doc.page_count = f.filename, content.page_count
            if _usable(doc):
                return doc
            candidate = candidate or doc
    if candidate is not None:
        return candidate
    empty = DOC_MODELS[doc_type](filename=f.filename, page_count=content.page_count, extractor="none")
    return empty


def extract_package(files: list[InputFile], **kw) -> ExtractedPackage:
    return ExtractedPackage(documents=[extract_file(f, **kw) for f in files])
