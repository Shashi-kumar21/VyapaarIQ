"""Estimated MSMED s.16 interest: compound, monthly rests, at 3x bank rate.

Full 30-day months compound; the remaining days accrue simple interest at the
monthly rate pro rata. This is an estimate and is always labelled as one.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Optional

from app.rules.config import get_config
from app.schemas import InterestEstimate


def estimate_interest(
    principal: float,
    due_date: Optional[date],
    as_of: date,
    cfg: Optional[dict[str, Any]] = None,
) -> InterestEstimate:
    cfg = cfg or get_config()
    annual = float(cfg["rbi"]["bank_rate_pct"]) * float(cfg["msmed"]["interest_multiplier"])
    monthly = annual / 100.0 / 12.0

    days_late = max(0, (as_of - due_date).days) if due_date else 0
    full_months, rem_days = divmod(days_late, 30)
    grown = principal * (1 + monthly) ** full_months * (1 + monthly * rem_days / 30)
    interest = round(grown - principal, 2) if days_late else 0.0

    formula = (
        f"P x (1 + {annual:.2f}%/12)^{full_months} x (1 + {annual:.2f}%/12 x {rem_days}/30) - P; "
        f"rate = {cfg['msmed']['interest_multiplier']} x RBI bank rate "
        f"{cfg['rbi']['bank_rate_pct']}%"
    )
    return InterestEstimate(
        principal=round(principal, 2),
        due_date=due_date,
        as_of=as_of,
        days_late=days_late,
        annual_rate_pct=round(annual, 4),
        interest=interest,
        formula=formula,
    )
