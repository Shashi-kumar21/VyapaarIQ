"""Evaluate VyapaarIQ against samples/ground_truth.json (BUILD_SPEC §15, tasks T2.7 / T5.1).

Runs every sample package through extraction -> checks -> due date, compares with the
ground truth, and writes eval/report.md (and eval/results.json).

    .\\.venv\\Scripts\\python eval\\run_eval.py                 # text + fixture modes
    .\\.venv\\Scripts\\python eval\\run_eval.py --modes text    # one mode
    .\\.venv\\Scripts\\python eval\\run_eval.py --modes claude  # needs ANTHROPIC_API_KEY

Fallback is OFF here: each mode is measured on its own (the app itself falls back to fixture).
Numbers are on synthetic documents only; they say nothing about real-world scans.
"""

from __future__ import annotations

import argparse
import json
import statistics
import subprocess
import sys
import time
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path
from typing import Any, Optional

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "backend"))

from app.extraction.base import InputFile, extract_package  # noqa: E402
from app.matching.checks import state  # noqa: E402
from app.matching.normalize import normalize_ref  # noqa: E402
from app.pipeline import analyze  # noqa: E402
from app.rules.config import get_config  # noqa: E402

GT_PATH = REPO / "samples" / "ground_truth.json"
OUT_DIR = REPO / "samples" / "out"
TODAY = date(2026, 11, 23)  # same demo clock as the tests
ID_FIELDS = {"doc_no", "invoice_no", "po_no", "challan_no", "eway_no", "grn_no", "po_reference",
             "invoice_reference", "supplier_gstin", "buyer_gstin", "supplier_udyam", "irn", "vehicle_no"}
SKIP_FIELDS = {"line_items"}  # compared through C03/C06 rather than field by field
POSITIVE = {"fail", "missing"}  # a check "detects a defect" when it fails or reports missing evidence


# ---------------------------------------------------------------- comparison
def _norm(name: str, v: Any) -> Any:
    if v is None:
        return None
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return round(float(v), 2)
    if isinstance(v, date):
        return v.isoformat()
    s = str(v).strip()
    if name in ID_FIELDS:
        return normalize_ref(s)
    return " ".join(s.casefold().split())


def field_outcome(name: str, want: Any, got_field, thr: float) -> str:
    """correct | correct_absent (both empty) | wrong (confident and different: the dangerous one) |
    uncertain | missed | spurious."""
    st = state(got_field, thr)
    want_n = _norm(name, want)
    if st == "uncertain":
        return "uncertain"
    got_n = _norm(name, got_field.value)
    if want_n == got_n:
        return "correct_absent" if want_n is None else "correct"
    if want_n is None:
        return "spurious"
    if got_n is None:
        return "missed"
    return "wrong"


def _pr(tp: int, fp: int, fn: int) -> tuple[Optional[float], Optional[float]]:
    p = tp / (tp + fp) if tp + fp else None
    r = tp / (tp + fn) if tp + fn else None
    return p, r


# ---------------------------------------------------------------- one mode
def run_mode(gt: dict, mode: str) -> dict:
    thr = float(get_config()["extraction"]["uncertain_below"])
    fields: dict[str, Counter] = defaultdict(Counter)
    field_failures: list[str] = []
    checks: dict[str, Counter] = defaultdict(Counter)
    check_failures: list[str] = []
    pkg_rows: list[dict] = []
    seen: set[tuple[str, str]] = set()

    for pkg in gt["packages"]:
        pid = pkg["package_id"]
        files = [InputFile(f["filename"], (OUT_DIR / pid / f["filename"]).read_bytes()) for f in pkg["files"]]
        t0 = time.perf_counter()
        extracted = extract_package(files, mode=mode, allow_fallback=False)

        def lookup(no, gstin, name, _seen=frozenset(seen), _code=pkg["buyer_code"]):
            return (normalize_ref(no), _code) in _seen

        a = analyze(extracted, duplicate_lookup=lookup, today=TODAY)
        ms = (time.perf_counter() - t0) * 1000
        if a.invoice_no:
            seen.add((normalize_ref(a.invoice_no), pkg["buyer_code"]))

        # fields
        for f, doc in zip(pkg["files"], extracted.documents):
            dt = f["doc_type"] + (" (scan)" if f["scan"] else "")
            for name, want in f["fields"].items():
                if name in SKIP_FIELDS or not hasattr(doc, name):
                    continue
                out = field_outcome(name, want, getattr(doc, name), thr)
                fields[dt][out] += 1
                if out in ("wrong", "spurious", "missed"):
                    field_failures.append(f"{pid} {f['filename']} `{name}`: {out} (want {want!r}, "
                                          f"got {getattr(doc, name).value!r})")

        # checks
        got = {c.check_id: c.status.value for c in a.checks}
        sev = {c.check_id: c.severity.value for c in a.checks}
        wrong_checks = []
        for cid, want in pkg["expected"]["checks"].items():
            g = got[cid]
            want_pos, got_pos = want in POSITIVE, g in POSITIVE
            c = checks[cid]
            if want == g == "missing" and sev[cid] == "info":
                # skipped (e.g. C06/C07 with no challan): a consequence of another check, not a detection
                c["skipped"] += 1
            elif g == "uncertain":
                c["uncertain"] += 1
                c["fn" if want_pos else "abstain_tn"] += 1
            elif want_pos and got_pos:
                c["tp"] += 1
            elif got_pos:
                c["fp"] += 1
            elif want_pos:
                c["fn"] += 1
            else:
                c["tn"] += 1
            if g != want:
                wrong_checks.append(f"{cid} want {want} got {g}")
        if wrong_checks:
            check_failures.append(f"{pid} {pkg['defects'] or ['clean']}: " + "; ".join(wrong_checks))

        # package-level
        flagged = any(got[c] in POSITIVE and sev[c] == "blocker" for c in got)
        unsure_blocker = any(got[c] == "uncertain" and sev[c] == "blocker" for c in got)
        # no confident blocker but an unreadable blocker check = the system abstained
        verdict = "blocker" if flagged else "uncertain" if unsure_blocker else "clean"
        exp = pkg["expected"]
        pkg_rows.append({
            "package": pid, "defects": pkg["defects"], "scan": any(f["scan"] for f in pkg["files"]),
            "expected_blocker": exp["has_blocker"], "predicted_blocker": flagged, "uncertain_blocker": unsure_blocker,
            "verdict": verdict,
            "due_expected": exp["due_date"], "due_got": a.due.due_date.isoformat() if a.due.due_date else None,
            "basis_expected": exp["acceptance_basis"], "basis_got": a.due.acceptance_basis,
            "score": a.score.score, "tier": a.score.tier.value, "ms": round(ms, 1),
        })
    return {"mode": mode, "threshold": thr, "fields": {k: dict(v) for k, v in fields.items()},
            "field_failures": field_failures, "checks": {k: dict(v) for k, v in checks.items()},
            "check_failures": check_failures, "packages": pkg_rows}


# ---------------------------------------------------------------- summary + report
def summarize(r: dict) -> dict:
    tot = Counter()
    for c in r["fields"].values():
        tot.update(c)
    n = sum(tot.values())
    pk = r["packages"]
    exp_v = lambda p: "blocker" if p["expected_blocker"] else "clean"  # noqa: E731
    blocker_ok = sum(p["verdict"] == exp_v(p) for p in pk)
    blocker_unsure = sum(p["verdict"] == "uncertain" for p in pk)
    blocker_wrong = len(pk) - blocker_ok - blocker_unsure
    defective = [p for p in pk if p["expected_blocker"]]
    caught = sum(p["verdict"] == "blocker" for p in defective)
    due_ok = sum(p["due_expected"] == p["due_got"] for p in pk)
    basis_ok = sum(p["basis_expected"] == p["basis_got"] for p in pk)
    allc = Counter()
    for c in r["checks"].values():
        allc.update(c)
    p, rec = _pr(allc["tp"], allc["fp"], allc["fn"])
    return {
        "fields_total": n, "field_accuracy": (tot["correct"] + tot["correct_absent"]) / n if n else None,
        "fields_wrong_confident": tot["wrong"] + tot["spurious"], "fields_uncertain": tot["uncertain"],
        "fields_missed": tot["missed"],
        "detect_precision": p, "detect_recall": rec, "checks_uncertain": allc["uncertain"],
        "false_positives": allc["fp"],
        "cross_doc": " · ".join(
            f"{cid} {pct(_pr(*(r['checks'].get(cid, {}).get(k, 0) for k in ('tp', 'fp', 'fn')))[0])} / "
            f"{pct(_pr(*(r['checks'].get(cid, {}).get(k, 0) for k in ('tp', 'fp', 'fn')))[1])}"
            for cid in ("C01", "C04")),
        "packages": len(pk), "blocker_vs_clean_correct": blocker_ok, "blocker_uncertain": blocker_unsure,
        "blocker_wrong": blocker_wrong, "defective_caught": caught, "defective": len(defective),
        "fields_correct_absent": tot["correct_absent"], "due_date_correct": due_ok,
        "acceptance_basis_correct": basis_ok,
        "median_ms": statistics.median(x["ms"] for x in pk) if pk else None,
        "max_ms": max((x["ms"] for x in pk), default=None),
    }


def pct(x: Optional[float]) -> str:
    return "n/a" if x is None else f"{100 * x:.1f}%"


def write_report(results: list[dict], path: Path) -> str:
    def git(*a):
        return subprocess.run(["git", *a], cwd=REPO, capture_output=True, text=True).stdout.strip()
    # "-dirty" when code differs from the commit; the report's own output files do not count.
    dirty = git("status", "--porcelain", "--", ".", ":!eval/report.md", ":!eval/results.json")
    commit = (git("rev-parse", "--short", "HEAD") or "unknown") + ("-dirty" if dirty else "")
    L = ["# VyapaarIQ evaluation report", "",
         f"_Generated by `eval/run_eval.py` on commit `{commit}`, demo date {TODAY.isoformat()}. "
         "Synthetic documents only (28 packages, fictional companies). These numbers do not describe "
         "real-world scans. Fallback between extractors is switched off so each mode is measured alone._", "",
         "## Summary", "",
         "| Metric | " + " | ".join(f"`{r['mode']}`" for r in results) + " |",
         "|---|" + "---|" * len(results)]
    sums = [summarize(r) for r in results]

    def row(label, fn):
        L.append(f"| {label} | " + " | ".join(fn(s) for s in sums) + " |")

    row("Field extraction accuracy (exact, normalised)", lambda s: f"{pct(s['field_accuracy'])} of {s['fields_total']}")
    row("… of which correct because the field is absent on both sides", lambda s: str(s["fields_correct_absent"]))
    row("**Wrong but confident** fields (the dangerous kind)", lambda s: str(s["fields_wrong_confident"]))
    row("Fields left `uncertain` (needs human check)", lambda s: str(s["fields_uncertain"]))
    row("Fields confidently reported absent but present", lambda s: str(s["fields_missed"]))
    row("Defect detection precision (all checks)", lambda s: pct(s["detect_precision"]))
    row("Defect detection recall (uncertain counts as a miss; skipped checks excluded)",
        lambda s: pct(s["detect_recall"]))
    row("Cross-document match C01 / C04 (precision / recall)", lambda s: s["cross_doc"])
    row("False alarms (check failed on a good document)", lambda s: str(s["false_positives"]))
    row("Checks returned `uncertain`", lambda s: str(s["checks_uncertain"]))
    row("Package verdict (blocker vs clean): confident and correct",
        lambda s: f"{s['blocker_vs_clean_correct']} / {s['packages']}")
    row("… abstained (a blocker check was `uncertain`, needs human check)",
        lambda s: f"{s['blocker_uncertain']} / {s['packages']}")
    row("… confidently wrong", lambda s: f"{s['blocker_wrong']} / {s['packages']}")
    row("Defective packages flagged with a blocker", lambda s: f"{s['defective_caught']} / {s['defective']}")
    row("Due date correct", lambda s: f"{s['due_date_correct']} / {s['packages']}")
    row("Acceptance basis correct", lambda s: f"{s['acceptance_basis_correct']} / {s['packages']}")
    row("Median / max processing time per package", lambda s: f"{s['median_ms']:.0f} ms / {s['max_ms']:.0f} ms")
    L += ["", "**How to read it.**",
          "",
          "- `fixture` reads the ground truth and is an upper bound. It checks the engine (checks, due dates), "
          "not extraction.",
          "- `text` is real extraction (PyMuPDF + regex) on the generated PDFs. Scanned pages have no text "
          "layer, so `text` reports them as `uncertain` instead of guessing (rule 3).",
          f"- A field counts as correct only on an exact match after normalisation: IDs compared without "
          f"spaces or punctuation, names case-insensitively, amounts to the paisa. Confidence below "
          f"{results[0]['threshold']} counts as `uncertain`, never as correct.", ""]

    for r, s in zip(results, sums):
        L += [f"## Mode `{r['mode']}`", "", "### Field extraction by document type", "",
              "| Doc type | Fields | Correct | Wrong (confident) | Uncertain | Missed | Spurious |",
              "|---|---|---|---|---|---|---|"]
        for dt in sorted(r["fields"]):
            c = Counter(r["fields"][dt])
            n = sum(c.values())
            L.append(f"| {dt} | {n} | {pct(c['correct'] / n if n else None)} | {c['wrong']} | {c['uncertain']} | "
                     f"{c['missed']} | {c['spurious']} |")
        L += ["", "### Defect detection by check", "",
              "| Check | TP | FP | FN | TN | Uncertain | Skipped | Precision | Recall |",
              "|---|---|---|---|---|---|---|---|---|"]
        for cid in sorted(r["checks"]):
            c = Counter(r["checks"][cid])
            p, rec = _pr(c["tp"], c["fp"], c["fn"])
            L.append(f"| {cid} | {c['tp']} | {c['fp']} | {c['fn']} | {c['tn']} | {c['uncertain']} | {c['skipped']} | "
                     f"{pct(p)} | {pct(rec)} |")
        L += ["", "_An `uncertain` result on a package that has the defect is counted as FN (a miss). On a "
              "package without the defect it is counted in neither TN nor FP. *Skipped* = an info check reporting "
              "`missing` because its input document is absent (e.g. C06/C07 with no challan). It agrees with the "
              "ground truth but is not scored, since it is not an independent detection._"]
        cm = Counter((p["expected_blocker"], p["verdict"]) for p in r["packages"])
        unsure = [p["package"] for p in r["packages"] if p["verdict"] == "uncertain"]
        L += ["", "### Package classification (has a blocker?)", "",
              "| | predicted blocker | uncertain (abstained) | predicted clean |", "|---|---|---|---|",
              f"| **expected blocker** | {cm[(True, 'blocker')]} | {cm[(True, 'uncertain')]} | {cm[(True, 'clean')]} |",
              f"| **expected clean** | {cm[(False, 'blocker')]} | {cm[(False, 'uncertain')]} | {cm[(False, 'clean')]} |",
              "", f"Abstained: {', '.join(unsure) or 'none'}. An abstention on a defective package is a miss "
              "for the user until a person checks it.", ""]
        bad_due = [p for p in r["packages"] if p["due_expected"] != p["due_got"]]
        L += ["### Failure cases", ""]
        if not (r["check_failures"] or r["field_failures"] or bad_due):
            L += ["None.", ""]
        if r["check_failures"]:
            L += ["**Checks that differ from the ground truth:**", ""] + [f"- {x}" for x in r["check_failures"]] + [""]
        if bad_due:
            L += ["**Due dates that differ:**", ""] + [
                f"- {p['package']} {p['defects'] or ['clean']}: want {p['due_expected']} ({p['basis_expected']}), "
                f"got {p['due_got']} ({p['basis_got']})" for p in bad_due] + [""]
        if r["field_failures"]:
            shown = r["field_failures"][:40]
            L += ["**Field errors (wrong, missed or spurious):**", ""] + [f"- {x}" for x in shown]
            if len(r["field_failures"]) > len(shown):
                L.append(f"- … and {len(r['field_failures']) - len(shown)} more (see `eval/results.json`)")
            L.append("")
    L += ["## Known limits", "",
          "- Synthetic layouts are cleaner than real invoices; real-world accuracy will be lower.",
          "- Line items are evaluated through C03/C06 (quantities, rates), not field by field.",
          "- In `text` mode the invoice `irn` is always `uncertain`: the sample invoices print only the first "
          "32 characters (`…`), so the full IRN is not on the page. `due_date_text` is not extracted by the "
          "`text` extractor at all, so it is always `uncertain` too. Together these account for every "
          "uncertain field on digital invoices.",
          "- The `claude` extractor is not in this report unless run with an API key (`--modes claude`).",
          "- Processing time is measured in-process (no HTTP, no disk upload).",
          "- C14 (duplicate) uses the ground-truth buyer code for its history lookup, so this harness does not "
          "test buyer identification. The API resolves the buyer from the extracted GSTIN/name "
          "(covered by `backend/tests/test_api.py`).", ""]
    text = "\n".join(L)
    path.write_text(text, encoding="utf-8")
    return text


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Evaluate extraction + checks against ground truth.")
    ap.add_argument("--modes", default="text,fixture", help="comma list of: text, fixture, claude")
    ap.add_argument("--out", default=str(REPO / "eval" / "report.md"))
    args = ap.parse_args(argv)
    if not GT_PATH.exists():
        print("samples/ground_truth.json missing", file=sys.stderr)
        return 2
    if not OUT_DIR.exists() or not any(OUT_DIR.glob("PKG*/*.pdf")):
        # Not regenerated here: samples/generate.py also rewrites the committed ground_truth.json
        # (scan PDFs are not byte-for-byte reproducible), which would change what is measured.
        print("samples/out/ is empty. Run: .\\.venv\\Scripts\\python samples\\generate.py", file=sys.stderr)
        return 2
    gt = json.loads(GT_PATH.read_text(encoding="utf-8"))
    results = [run_mode(gt, m.strip()) for m in args.modes.split(",") if m.strip()]
    out = Path(args.out)
    write_report(results, out)
    out.with_name("results.json").write_text(json.dumps(results, indent=1, default=str), encoding="utf-8")
    for r in results:
        s = summarize(r)
        print(f"[{r['mode']}] fields {pct(s['field_accuracy'])} (wrong-confident {s['fields_wrong_confident']}, "
              f"uncertain {s['fields_uncertain']}) | detection P {pct(s['detect_precision'])} "
              f"R {pct(s['detect_recall'])} | blocker {s['blocker_vs_clean_correct']}/{s['packages']} | "
              f"due {s['due_date_correct']}/{s['packages']} | median {s['median_ms']:.0f} ms")
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
