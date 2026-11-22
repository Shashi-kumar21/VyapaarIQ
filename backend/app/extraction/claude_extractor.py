"""Claude extractor (T2.3): text-first, PDF/image input for scanned docs.

Returns ``None`` when the API is not configured so the chain falls back.
Validates with Pydantic and retries once on a schema/JSON failure.
"""

from __future__ import annotations

import base64
from typing import Any, Optional

from pydantic import ValidationError

from app.extraction.pdf_text import IMAGE_EXT, PdfContent
from app.llm.client import ClaudeClient, LLMBadJSON, LLMUnavailable, llm_configured
from app.llm.prompts import SYSTEM, field_names, user_prompt
from app.schemas import DOC_MODELS, BaseDoc, DocType

MAX_TEXT_CHARS = 60_000


def _content(f, content: PdfContent, doc_type: DocType) -> list[dict]:
    prompt = {"type": "text", "text": user_prompt(doc_type)}
    if not content.is_scanned and content.text.strip():
        text = content.text[:MAX_TEXT_CHARS]
        return [{"type": "text", "text": f"<document>\n{text}\n</document>"}, prompt]
    data = base64.standard_b64encode(f.data).decode("ascii")
    name = f.filename.lower()
    if name.endswith(IMAGE_EXT):
        media = "image/png" if name.endswith(".png") else "image/jpeg"
        block = {"type": "image", "source": {"type": "base64", "media_type": media, "data": data}}
    else:
        block = {"type": "document",
                 "source": {"type": "base64", "media_type": "application/pdf", "data": data}}
    return [block, prompt]


def _normalise(raw: Any, doc_type: DocType) -> dict[str, Any]:
    """Keep only known fields; coerce bare values into {"value": ...}."""
    if not isinstance(raw, dict):
        raise LLMBadJSON("Expected a JSON object.")
    out = {}
    for name in field_names(doc_type):
        v = raw.get(name)
        if isinstance(v, dict) and "value" in v:
            out[name] = {"value": v.get("value"), "confidence": float(v.get("confidence") or 0.0),
                         "source_page": v.get("source_page")}
        elif v is not None:
            out[name] = {"value": v, "confidence": 0.5}
    return out


class ClaudeExtractor:
    name = "claude"

    def __init__(self, client: Optional[ClaudeClient] = None):
        self._client = client

    def extract(self, f, content: PdfContent, doc_type: DocType) -> Optional[BaseDoc]:
        if self._client is None:
            if not llm_configured():
                return None
            try:
                self._client = ClaudeClient()
            except LLMUnavailable:
                return None
        model = DOC_MODELS[doc_type]
        blocks = _content(f, content, doc_type)
        last_err: Optional[Exception] = None
        for _ in range(2):  # one retry on bad JSON / schema failure
            try:
                raw = self._client.complete_json(SYSTEM, blocks)
                return model(**_normalise(raw, doc_type))
            except (LLMBadJSON, ValidationError, ValueError, TypeError) as exc:
                last_err = exc
            except LLMUnavailable:
                return None
        raise ValueError(f"Claude extraction failed validation twice: {type(last_err).__name__}")
