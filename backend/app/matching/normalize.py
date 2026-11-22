"""Normalisation helpers: party names, GSTIN, references, dates, amounts."""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Optional

from rapidfuzz import fuzz

_GSTIN_RE = re.compile(r"^\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]$")
_CHARS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
_LEGAL_SUFFIXES = {
    "PVT", "PRIVATE", "LTD", "LIMITED", "LLP", "CO", "COMPANY", "INC", "CORP",
    "THE", "M/S", "MS",
}


# ------------------------------------------------------------------ parties
def normalize_party(name: Optional[str]) -> str:
    if not name:
        return ""
    s = name.upper().replace("&", " AND ")
    s = re.sub(r"[^A-Z0-9 ]+", " ", s)
    tokens = [t for t in s.split() if t not in _LEGAL_SUFFIXES]
    return " ".join(tokens)


def party_similarity(a: Optional[str], b: Optional[str]) -> float:
    na, nb = normalize_party(a), normalize_party(b)
    if not na or not nb:
        return 0.0
    return fuzz.token_sort_ratio(na, nb) / 100.0


# ------------------------------------------------------------------ GSTIN
def normalize_gstin(g: Optional[str]) -> str:
    return re.sub(r"\s+", "", g or "").upper()


def gstin_checksum(first14: str) -> str:
    total = 0
    for i, ch in enumerate(first14):
        prod = _CHARS.index(ch) * (2 if i % 2 else 1)
        total += prod // 36 + prod % 36
    return _CHARS[(36 - total % 36) % 36]


def gstin_valid(g: Optional[str]) -> bool:
    s = normalize_gstin(g)
    if not _GSTIN_RE.match(s):
        return False
    return gstin_checksum(s[:14]) == s[14]


# ------------------------------------------------------------------ refs
def normalize_ref(ref: Optional[str]) -> str:
    """Compare document numbers ignoring case, spaces and separators."""
    return re.sub(r"[^A-Z0-9]", "", (ref or "").upper())


def refs_match(a: Optional[str], b: Optional[str]) -> bool:
    na, nb = normalize_ref(a), normalize_ref(b)
    return bool(na) and na == nb


def desc_similarity(a: Optional[str], b: Optional[str]) -> float:
    if not a or not b:
        return 0.0
    return fuzz.token_sort_ratio(a.upper(), b.upper()) / 100.0


# ------------------------------------------------------------------ values
_DATE_FORMATS = ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%d.%m.%Y", "%d %b %Y", "%d %B %Y",
                 "%d-%b-%Y", "%d-%b-%y", "%d/%m/%y", "%b %d, %Y")


def parse_date(s: Optional[str]) -> Optional[date]:
    if not s:
        return None
    if isinstance(s, date):
        return s
    t = re.sub(r"\s+", " ", str(s).strip().rstrip(".,"))
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(t, fmt).date()
        except ValueError:
            continue
    return None


def parse_amount(s: Optional[str]) -> Optional[float]:
    if s is None:
        return None
    if isinstance(s, (int, float)):
        return float(s)
    t = re.sub(r"(?i)(rs\.?|inr|₹|/-)", "", str(s)).replace(",", "").strip()
    m = re.search(r"-?\d+(?:\.\d+)?", t)
    return float(m.group()) if m else None
