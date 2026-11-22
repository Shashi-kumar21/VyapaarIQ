"""LLM layer and extractor chain, fully offline."""

import pytest

from app.extraction.base import InputFile, classify, extract_file
from app.extraction.claude_extractor import ClaudeExtractor
from app.extraction.pdf_text import PdfContent, UnreadableFileError
from app.llm.client import LLMBadJSON, parse_json
from app.matching.normalize import gstin_valid, normalize_party, parse_amount, parse_date, party_similarity
from app.schemas import DocType

from .conftest import OUT


# ---------------------------------------------------------------- JSON parsing
def test_parse_json_strips_fences_and_prose():
    assert parse_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert parse_json('Here you go: {"a": {"b": 2}} thanks') == {"a": {"b": 2}}
    with pytest.raises(LLMBadJSON):
        parse_json("no json here")


class FakeClient:
    def __init__(self, replies):
        self.replies, self.calls = list(replies), 0

    def complete_json(self, system, content, max_tokens=8000):
        self.calls += 1
        r = self.replies.pop(0)
        if isinstance(r, Exception):
            raise r
        return r


def _content():
    return PdfContent(pages=["TAX INVOICE\nInvoice No: X-1"], page_count=1)


def test_claude_extractor_validates_and_retries_once():
    good = {"invoice_no": {"value": "X-1", "confidence": 0.95, "source_page": 1},
            "invoice_date": {"value": "2026-10-01", "confidence": 0.9, "source_page": 1},
            "total": 1180.0, "unexpected_field": "ignored"}
    fake = FakeClient([LLMBadJSON("bad"), good])
    doc = ClaudeExtractor(client=fake).extract(InputFile("a.pdf", b"x"), _content(), DocType.invoice)
    assert fake.calls == 2
    assert doc.invoice_no.value == "X-1" and doc.invoice_no.confidence == 0.95
    assert doc.invoice_date.value.isoformat() == "2026-10-01"
    assert doc.total.value == 1180.0 and doc.total.confidence == 0.5  # bare value -> low-ish confidence


def test_claude_extractor_gives_up_after_two_failures():
    fake = FakeClient([LLMBadJSON("x"), {"invoice_date": {"value": "not a date", "confidence": 1}}])
    with pytest.raises(ValueError):
        ClaudeExtractor(client=fake).extract(InputFile("a.pdf", b"x"), _content(), DocType.invoice)


def test_claude_returns_none_without_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)
    assert ClaudeExtractor().extract(InputFile("a.pdf", b"x"), _content(), DocType.invoice) is None


# ---------------------------------------------------------------- chain
def _sample(pkg="PKG02", name="PKG02_invoice_scan.pdf"):
    return InputFile(name, (OUT / pkg / name).read_bytes())


def test_claude_mode_without_key_falls_back_to_text(monkeypatch, ground_truth):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    doc = extract_file(_sample("PKG01", "PKG01_invoice.pdf"), mode="claude")
    assert doc.extractor == "text" and doc.fallback is True
    assert doc.invoice_no.value == "SPC/26-27/0101"


def test_scanned_doc_falls_back_to_fixture_with_badge(ground_truth):
    doc = extract_file(_sample(), mode="text")
    assert doc.extractor == "fixture" and doc.fallback is True
    assert doc.invoice_no.value == "SPC/26-27/0102"


def test_scanned_doc_without_fallback_is_uncertain(ground_truth):
    doc = extract_file(_sample(), mode="text", allow_fallback=False)
    assert doc.extractor == "text" and doc.invoice_no.value is None and doc.invoice_no.confidence == 0.0


def test_corrupt_pdf_raises_clear_error():
    with pytest.raises(UnreadableFileError):
        extract_file(InputFile("broken.pdf", b"%PDF-1.4 garbage"), mode="text")


def test_classifier_filename_fallback():
    assert classify("scan_grn_0042.jpg", None)[0] == DocType.grn
    assert classify("Lorry receipt.pdf", None)[0] == DocType.challan
    assert classify("random.pdf", None)[0] == DocType.other


# ---------------------------------------------------------------- normalise
def test_party_normalisation():
    assert normalize_party("Kaveri Auto Assemblies Pvt. Ltd.") == "KAVERI AUTO ASSEMBLIES"
    assert party_similarity("Sahyadri Pumps & Valves LLP", "Sahyadri Pumps and Valves LLP") == 1.0
    assert party_similarity("Kaveri Auto Assemblies Private Limited", "Kaveri Motors & Traders Pvt Ltd") < 0.9


def test_gstin_and_values():
    assert gstin_valid("27AAECS4821K1Z6")
    assert not gstin_valid("27AAECS4821K1Z7")  # bad checksum
    assert not gstin_valid("27AAECS4821K")
    assert parse_amount("₹2,40,000.50") == 240000.5
    assert parse_amount("Rs. 1,180/-") == 1180.0
    assert parse_date("02 Sep 2026").isoformat() == "2026-09-02"
    assert parse_date("04/09/2026").isoformat() == "2026-09-04"
    assert parse_date("garbage") is None
