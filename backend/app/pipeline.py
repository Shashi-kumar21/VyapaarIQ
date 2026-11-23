"""Extracted package -> checks -> score -> due date -> actions -> graph.

Pure orchestration over deterministic modules; no I/O, no LLM.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Optional

from app.matching.checks import DuplicateLookup, run_checks, state
from app.matching.graph import build_graph
from app.rules.config import get_config
from app.rules.due_date import compute_due_date
from app.rules.interest import estimate_interest
from app.schemas import Analysis, DocType, DueDateResult, ExtractedPackage, InterestEstimate
from app.scoring.actions import build_actions
from app.scoring.score import compute_score


def known_value(f, thr: float):
    """The field's value only if it was read at or above the confidence threshold, else None."""
    return f.value if f is not None and state(f, thr) == "known" else None


def due_date_for(pkg: ExtractedPackage, cfg: dict[str, Any]) -> DueDateResult:
    thr = float(cfg["extraction"]["uncertain_below"])

    def known(f):
        return f.value if state(f, thr) == "known" else None

    grn, ch = pkg.first(DocType.grn), pkg.first(DocType.challan)
    terms_days, has_terms = None, False
    for t in (DocType.contract, DocType.po, DocType.invoice):
        d = pkg.first(t)
        if d is None:
            continue
        if known(d.payment_terms_days) is not None:
            terms_days, has_terms = int(d.payment_terms_days.value), True
            break
        # terms text present but days unparsed, or the field is unreadable:
        # written terms may exist -> due date becomes "uncertain", not "no terms"
        if known(d.payment_terms_text) is not None or state(d.payment_terms_days, thr) == "uncertain":
            has_terms = True
    return compute_due_date(
        grn_date=known(grn.grn_date) if grn else None,
        challan_received_date=known(ch.received_date) if ch else None,
        delivery_date=known(ch.challan_date) if ch else None,
        terms_days=terms_days,
        has_written_terms=has_terms,
        cfg=cfg,
    )


def analyze(pkg: ExtractedPackage, *, duplicate_lookup: Optional[DuplicateLookup] = None,
            today: Optional[date] = None, cfg: Optional[dict[str, Any]] = None) -> Analysis:
    if cfg is None:
        cfg = get_config()
    today = today or date.today()
    checks = run_checks(pkg, duplicate_lookup=duplicate_lookup, cfg=cfg)
    score = compute_score(checks, cfg)
    due = due_date_for(pkg, cfg)
    inv = pkg.first(DocType.invoice)
    thr = float(cfg["extraction"]["uncertain_below"])
    # Rule 3: a value read below the confidence threshold is never used in a calculation.
    total = known_value(inv.total, thr) if inv else None
    if total is not None and total >= 0:
        interest = estimate_interest(total, due.due_date, today, cfg)
    else:
        bank = float(cfg["rbi"]["bank_rate_pct"]) * float(cfg["msmed"]["interest_multiplier"])
        interest = InterestEstimate(principal=0.0, due_date=due.due_date, as_of=today, days_late=0,
                                    annual_rate_pct=round(bank, 4), interest=None, computable=False,
                                    formula="Not computable: the invoice total could not be read reliably "
                                            "(needs human check).")
    extractors = {d.extractor for d in pkg.documents if d.extractor}
    return Analysis(
        invoice_no=known_value(inv.invoice_no, thr) or known_value(inv.doc_no, thr),
        buyer_name=known_value(inv.buyer_name, thr),
        amount_total=total,
        checks=checks,
        score=score,
        due=due,
        interest=interest,
        actions=build_actions(checks, due, today=today, cfg=cfg),
        graph=build_graph(pkg, checks),
        extractor_used=",".join(sorted(extractors)) or None,
        fallback_used=any(getattr(d, "fallback", False) for d in pkg.documents),
    )
