"""Buyer reliability from the supplier's own payment history (BUILD_SPEC §8).

Pure function over (due_date, paid_on) pairs; not a credit score.
"""

from __future__ import annotations

from datetime import date
from statistics import median
from typing import Any, Optional

from pydantic import BaseModel

from app.rules.config import get_config


class BuyerProfile(BaseModel):
    invoices_considered: int
    median_days_late: Optional[float] = None
    pct_paid_late: Optional[float] = None
    pct_paid_over_30_late: Optional[float] = None
    trend: Optional[str] = None  # improving | worsening | stable
    trend_detail: Optional[str] = None
    label: str  # Reliable | Mixed | Slow | Insufficient history
    note: str = "Based only on this supplier's own invoice history. Not a credit rating."


def compute_profile(history: list[tuple[date, date]], cfg: Optional[dict[str, Any]] = None) -> BuyerProfile:
    """``history`` = [(due_date, paid_on), ...] in any order."""
    if cfg is None:
        cfg = get_config()
    bp = cfg["buyer_profile"]
    rows = sorted((d, p) for d, p in history if d and p)
    n = len(rows)
    if n < int(bp["min_history"]):
        return BuyerProfile(invoices_considered=n, label="Insufficient history")
    late = [(p - d).days for d, p in rows]
    med = float(median(late))
    pct_late = round(100 * sum(x > 0 for x in late) / n, 1)
    pct_30 = round(100 * sum(x > 30 for x in late) / n, 1)

    trend = trend_detail = None
    if n >= 6:
        recent, prev = median(late[-3:]), median(late[:-3])
        delta = recent - prev
        trend = "worsening" if delta > 5 else "improving" if delta < -5 else "stable"
        trend_detail = f"median of last 3 = {recent:g} days vs {prev:g} days before"

    if med <= bp["reliable_max_median_late"] and pct_30 <= bp["reliable_max_pct_over_30"]:
        label = "Reliable"
    elif med >= bp["slow_min_median_late"] or pct_30 >= bp["slow_min_pct_over_30"]:
        label = "Slow"
    else:
        label = "Mixed"
    return BuyerProfile(invoices_considered=n, median_days_late=med, pct_paid_late=pct_late,
                        pct_paid_over_30_late=pct_30, trend=trend, trend_detail=trend_detail, label=label)
