"""Estimated MSMED s.16 interest: compound, monthly rests, at 3x bank rate.

Full 30-day months compound; the remaining days accrue simple interest at the
monthly rate pro rata. This is an estimate and is always labelled as one.
Returns ``interest=None, computable=False`` when there is no due date or the
supplier is not micro/small (s.16 does not apply).
"""

from __future__ import annotations

from datetime import date
from typing import Any, Optional

from app.rules.config import get_config
from app.rules.due_date import MSMED_CLASSES
from app.schemas import InterestEstimate


def estimate_interest(
    principal: float,
    due_date: Optional[date],
    as_of: date,
    cfg: Optional[dict[str, Any]] = None,
    enterprise_class: Optional[str] = None,
) -> InterestEstimate:
    if cfg is None:
        cfg = get_config()
    if principal < 0:
        raise ValueError("principal cannot be negative")
    mult = float(cfg["msmed"]["interest_multiplier"])
    bank = float(cfg["rbi"]["bank_rate_pct"])
    annual = bank * mult
    cls = (enterprise_class or cfg["supplier"]["enterprise_class"]).lower()

    def not_computable(reason: str) -> InterestEstimate:
        return InterestEstimate(principal=round(principal, 2), due_date=due_date, as_of=as_of,
                                days_late=0, annual_rate_pct=round(annual, 4), interest=None,
                                computable=False, formula=f"Not computable: {reason}")

    if cls not in MSMED_CLASSES:
        return not_computable(f"MSMED s.16 interest applies to micro/small suppliers, not {cls}.")
    if due_date is None:
        return not_computable("no due date could be determined.")

    monthly = annual / 100.0 / 12.0
    days_late = max(0, (as_of - due_date).days)
    full_months, rem_days = divmod(days_late, 30)
    grown = principal * (1 + monthly) ** full_months * (1 + monthly * rem_days / 30)
    interest = round(grown - principal, 2) if days_late else 0.0

    formula = (
        f"P x (1 + {annual:.2f}%/12)^{full_months} x (1 + {annual:.2f}%/12 x {rem_days}/30) - P; "
        f"rate = {mult:g} x RBI bank rate {bank}%"
    )
    return InterestEstimate(
        principal=round(principal, 2), due_date=due_date, as_of=as_of, days_late=days_late,
        annual_rate_pct=round(annual, 4), interest=interest, formula=formula,
    )
