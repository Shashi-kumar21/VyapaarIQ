"""Evaluation harness (eval/run_eval.py, T2.7 / T5.1) and the extraction bugs it found."""

import importlib.util
import json
from pathlib import Path

import pytest

from app.extraction.base import InputFile, extract_file

from .conftest import OUT

REPO = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def ev():
    spec = importlib.util.spec_from_file_location("run_eval", REPO / "eval" / "run_eval.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def gt(ground_truth):
    return ground_truth


def test_fixture_mode_is_a_perfect_upper_bound(ev, gt):
    s = ev.summarize(ev.run_mode(gt, "fixture"))
    assert s["field_accuracy"] == 1.0 and s["fields_wrong_confident"] == 0
    assert s["detect_precision"] == 1.0 and s["detect_recall"] == 1.0
    assert s["blocker_vs_clean_correct"] == s["packages"] == 28
    assert s["due_date_correct"] == 28


def test_text_mode_is_never_confidently_wrong(ev, gt):
    """Rule 3 in numbers: text extraction may abstain (uncertain) but must not guess."""
    r = ev.run_mode(gt, "text")
    s = ev.summarize(r)
    assert s["fields_wrong_confident"] == 0, r["field_failures"][:5]
    assert s["false_positives"] == 0
    assert s["detect_precision"] == 1.0
    # every package-level mistake is on a package with a scanned document
    for p in r["packages"]:
        if p["expected_blocker"] != p["predicted_blocker"] or p["due_expected"] != p["due_got"]:
            assert p["scan"], p


def test_report_is_written(ev, gt, tmp_path):
    results = [ev.run_mode(gt, "fixture")]
    text = ev.write_report(results, tmp_path / "report.md")
    assert "# VyapaarIQ evaluation report" in text and "Synthetic documents only" in text
    assert "| Due date correct | 28 / 28 |" in text
    assert json.dumps(results, default=str)  # results.json is serialisable


def test_field_outcome_categories(ev):
    from app.schemas import F

    assert ev.field_outcome("invoice_no", "SPC/26-27/0101", F(value="spc-26-27-0101", confidence=0.9), 0.6) == "correct"
    assert ev.field_outcome("total", 100.0, F(value=100.004, confidence=0.9), 0.6) == "correct"
    assert ev.field_outcome("total", 100.0, F(value=99.0, confidence=0.9), 0.6) == "wrong"
    assert ev.field_outcome("total", 100.0, F(value=99.0, confidence=0.3), 0.6) == "uncertain"
    assert ev.field_outcome("total", 100.0, F(value=None, confidence=0.9), 0.6) == "missed"
    assert ev.field_outcome("irn", None, F(value="abc", confidence=0.9), 0.6) == "spurious"


# ---------------------------------------------------------------- regressions found by the eval
def _extract(pkg, name):
    path = OUT / pkg / f"{pkg}_{name}.pdf"
    return extract_file(InputFile(path.name, path.read_bytes()), mode="text", allow_fallback=False)


def test_truncated_irn_is_not_trusted(ground_truth):
    inv = _extract("PKG01", "invoice")
    assert inv.irn.confidence < 0.6  # only a prefix is printed on the invoice
    assert inv.irn.value and "..." not in inv.irn.value


def test_received_by_ignores_stamp_text_on_the_same_line(ground_truth):
    ch = _extract("PKG03", "challan")
    assert ch.received_by_name.value == "R. Patil"
