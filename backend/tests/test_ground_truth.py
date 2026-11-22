"""End-to-end engine test: sample PDFs -> extraction -> checks/due date vs ground truth."""

from datetime import date

import pytest

from app.extraction.base import InputFile, extract_package
from app.matching.normalize import normalize_ref
from app.pipeline import analyze
from app.schemas import CheckStatus, DocType

from .conftest import OUT

TODAY = date(2026, 11, 23)


def _run_all(gt, mode):
    seen: set[tuple[str, str]] = set()
    results = []
    for pkg in gt["packages"]:
        files = [InputFile(f["filename"], (OUT / pkg["package_id"] / f["filename"]).read_bytes())
                 for f in pkg["files"]]
        extracted = extract_package(files, mode=mode, allow_fallback=False)

        def lookup(no, gstin, name, _seen=frozenset(seen)):
            return (normalize_ref(no), pkg["buyer_code"]) in _seen

        a = analyze(extracted, duplicate_lookup=lookup, today=TODAY)
        seen.add((normalize_ref(a.invoice_no), pkg["buyer_code"]))
        results.append((pkg, extracted, a))
    return results


@pytest.fixture(scope="module")
def fixture_results(ground_truth):
    return _run_all(ground_truth, "fixture")


def test_fixture_mode_matches_every_expected_check(fixture_results):
    errors = []
    for pkg, _, a in fixture_results:
        got = {c.check_id: c.status.value for c in a.checks}
        for cid, want in pkg["expected"]["checks"].items():
            if got[cid] != want:
                errors.append(f"{pkg['package_id']} {pkg['defects']} {cid}: want {want}, got {got[cid]}")
    assert not errors, "\n".join(errors)


def test_fixture_mode_due_dates(fixture_results):
    for pkg, _, a in fixture_results:
        exp = pkg["expected"]
        assert a.due.acceptance_basis == exp["acceptance_basis"], pkg["package_id"]
        assert (a.due.due_date.isoformat() if a.due.due_date else None) == exp["due_date"], pkg["package_id"]


def test_clean_packages_score_low_risk_and_grn_missing_is_flagged(fixture_results):
    for pkg, _, a in fixture_results:
        if not pkg["defects"]:
            assert a.score.score >= 85, (pkg["package_id"], a.score)
        if pkg["defects"] == ["missing_grn"]:
            assert a.score.tier.value in ("Medium", "High")
            assert a.actions and a.actions[0].check_id == "C10"
            assert a.actions[0].due_by is not None


def test_graph_marks_missing_grn(fixture_results):
    for pkg, _, a in fixture_results:
        nodes = {n.id: n.status for n in a.graph.nodes}
        if "missing_grn" in pkg["defects"]:
            assert nodes["grn"] == "missing"
        if not pkg["defects"]:
            assert all(s == "ok" for s in nodes.values()), (pkg["package_id"], nodes)


def test_classifier_on_digital_samples(ground_truth):
    from app.extraction.base import classify
    from app.extraction.pdf_text import read_document

    for pkg in ground_truth["packages"]:
        for f in pkg["files"]:
            content = read_document((OUT / pkg["package_id"] / f["filename"]).read_bytes(), f["filename"])
            dt, _, _ = classify("upload.pdf", content)  # no filename hint
            if not f["scan"]:
                assert dt == DocType(f["doc_type"]), f["filename"]


def test_text_mode_on_digital_packages(ground_truth):
    """Text extractor must reproduce expected checks on packages with no scanned doc.

    Packages containing a scan may legitimately return ``uncertain`` for the
    checks that depend on the scanned document, but never a wrong pass/fail.
    """
    errors = []
    for pkg, extracted, a in _run_all(ground_truth, "text"):
        has_scan = any(f["scan"] for f in pkg["files"])
        got = {c.check_id: c.status for c in a.checks}
        for cid, want in pkg["expected"]["checks"].items():
            g = got[cid]
            if g.value == want:
                continue
            if has_scan and g == CheckStatus.uncertain:
                continue
            errors.append(f"{pkg['package_id']} {pkg['defects']} {cid}: want {want}, got {g.value}")
    assert not errors, "\n".join(errors)
