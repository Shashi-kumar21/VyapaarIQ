"""30/60-day cash-at-risk forecast (BUILD_SPEC §9). Transparent heuristic, not ML.

expected_date = due_date + buyer median days late (0 when history is
insufficient). An open invoice is *at risk* when its tier is High, its due
date is unknown, its expected date has already passed (still unpaid), or its
expected date falls beyond the window.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Optional

FORMULA = ("expected payment date = due date + buyer's median days late (0 if fewer than the minimum "
           "history); at risk = risk tier High, or due date unknown, or expected date already passed, "
           "or expected date beyond the window; suspected duplicates (C14 failed) and invoices whose total could not be read reliably are "
           "excluded")
NOTE = "Illustrative forecast from synthetic demo history. Not a prediction of buyer payment."
WINDOWS = (30, 60)


@dataclass
class OpenInvoice:
    id: int
    invoice_no: Optional[str]
    buyer_id: Optional[int]
    buyer_name: Optional[str]
    amount: Optional[float]  # None = total could not be read reliably
    due_date: Optional[date]
    risk_tier: Optional[str]
    buyer_median_late: Optional[float]  # None = insufficient history
    duplicate_suspect: bool = False  # C14 failed: same number + buyer already on record


def forecast(invoices: list[OpenInvoice], today: date, days: int) -> dict:
    """Duplicate suspects (C14 failed) and unverified amounts are listed under ``excluded``
    and left out of every total."""
    if days not in WINDOWS:
        raise ValueError(f"days must be one of {WINDOWS}")
    horizon = today + timedelta(days=days)
    buckets = {"overdue": 0.0, "next_30": 0.0, "days_31_60": 0.0, "beyond_60": 0.0, "unknown": 0.0}
    rows, excluded = [], []
    open_total = expected_in_window = at_risk = 0.0
    for inv in invoices:
        if inv.amount is None:
            excluded.append({"id": inv.id, "invoice_no": inv.invoice_no, "buyer_name": inv.buyer_name,
                             "amount": None, "reason": "amount_unverified (total not read reliably)"})
            continue
        amt = float(inv.amount)
        if inv.duplicate_suspect:
            excluded.append({"id": inv.id, "invoice_no": inv.invoice_no, "buyer_name": inv.buyer_name,
                             "amount": round(amt, 2), "reason": "duplicate_suspect (C14 failed)"})
            continue
        open_total += amt
        lag = round(inv.buyer_median_late) if inv.buyer_median_late is not None else 0
        expected = inv.due_date + timedelta(days=lag) if inv.due_date else None
        reasons = []
        if inv.risk_tier == "High":
            reasons.append("risk tier High")
        if expected is None:
            reasons.append("due date unknown")
            buckets["unknown"] += amt
        else:
            delta = (expected - today).days
            key = ("overdue" if delta < 0 else "next_30" if delta <= 30
                   else "days_31_60" if delta <= 60 else "beyond_60")
            buckets[key] += amt
            if delta < 0:
                reasons.append(f"unpaid {-delta} day(s) after expected date")
            if expected > horizon:
                reasons.append(f"expected after {horizon.isoformat()}")
        risky = bool(reasons)
        if risky:
            at_risk += amt
        elif expected is not None:
            expected_in_window += amt
        rows.append({
            "id": inv.id, "invoice_no": inv.invoice_no, "buyer_id": inv.buyer_id, "buyer_name": inv.buyer_name,
            "amount": round(amt, 2), "due_date": inv.due_date, "risk_tier": inv.risk_tier,
            "buyer_median_days_late": inv.buyer_median_late, "lag_days_applied": lag,
            "expected_date": expected, "at_risk": risky, "reasons": reasons,
        })
    rows.sort(key=lambda r: (r["expected_date"] or date.max, r["id"]))
    return {
        "as_of": today, "days": days, "window_end": horizon,
        "totals": {"open": round(open_total, 2), "expected_in_window": round(expected_in_window, 2),
                   "at_risk": round(at_risk, 2), "count": len(rows),
                   "excluded_count": len(excluded),
                   "excluded_amount": round(sum(e["amount"] or 0.0 for e in excluded), 2)},
        "buckets": [{"key": k, "amount": round(v, 2)} for k, v in buckets.items()],
        "invoices": rows, "excluded": excluded, "formula": FORMULA, "note": NOTE,
    }
