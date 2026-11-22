"""Fixture extractor: returns ground-truth fields for known sample files.

Guarantees the demo works offline. Matches by file SHA-256, then by filename.
Documents it produces are always labelled with ``extractor="fixture"``.
"""

from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

from app.extraction.pdf_text import PdfContent
from app.schemas import DOC_MODELS, BaseDoc, DocType

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_GT = REPO_ROOT / "samples" / "ground_truth.json"


@lru_cache(maxsize=4)
def _index(path: str) -> tuple[dict[str, dict], dict[str, dict]]:
    p = Path(path)
    if not p.exists():
        return {}, {}
    gt = json.loads(p.read_text(encoding="utf-8"))
    by_hash, by_name = {}, {}
    for pkg in gt.get("packages", []):
        for f in pkg["files"]:
            by_hash[f["sha256"]] = f
            by_name[f["filename"].lower()] = f
    return by_hash, by_name


def lookup(sha256: str, filename: str, gt_path: Optional[str] = None) -> Optional[dict]:
    by_hash, by_name = _index(gt_path or os.environ.get("GROUND_TRUTH", str(DEFAULT_GT)))
    return by_hash.get(sha256) or by_name.get(os.path.basename(filename).lower())


def doc_from_fields(doc_type: DocType, fields: dict[str, Any], confidence: float = 1.0) -> BaseDoc:
    model = DOC_MODELS[doc_type]
    data: dict[str, Any] = {}
    for name, info in model.model_fields.items():
        if name in ("doc_type", "filename", "page_count", "extractor", "fallback"):
            continue
        data[name] = {"value": fields.get(name), "confidence": confidence, "source_page": 1}
    return model(**data)


class FixtureExtractor:
    name = "fixture"

    def extract(self, f, content: PdfContent, doc_type: DocType) -> Optional[BaseDoc]:
        rec = lookup(f.sha256, f.filename)
        if rec is None:
            return None
        return doc_from_fields(DocType(rec["doc_type"]), rec["fields"])
