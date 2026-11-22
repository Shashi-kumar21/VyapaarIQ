"""Acceptance date and due date (BUILD_SPEC §7 "Due-date logic").

Pure function; every result carries a reasoning string naming the rule used.

* MSMED s.15 limits (45-day cap, 15-day default) apply only to micro and small
  suppliers (``supplier.enterprise_class``). For others, written terms apply
  as written and the 15-day figure is shown as an assumption.
* ``has_written_terms=True`` with ``terms_days=None`` means terms exist but the
  number of days could not be read: the result is marked ``uncertain``.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Optional

from app.rules.config import get_config
from app.schemas import DueDateResult

MSMED_CLASSES = ("micro", "small")


def compute_due_date(
    *,
    grn_date: Optional[date],
    challan_received_date: Optional[date],
    delivery_date: Optional[date],
    terms_days: Optional[int],
    has_written_terms: bool,
    enterprise_class: Optional[str] = None,
    cfg: Optional[dict[str, Any]] = None,
) -> DueDateResult:
    if cfg is None:
        cfg = get_config()
    if terms_days is not None and terms_days < 0:
        raise ValueError("terms_days cannot be negative")
    msmed = cfg["msmed"]
    cls = (enterprise_class or cfg["supplier"]["enterprise_class"]).lower()
    applies = cls in MSMED_CLASSES
    max_days = int(msmed["max_terms_days"])
    no_agreement_days = int(msmed["no_agreement_days"])
    deemed_offset = int(msmed["deemed_acceptance_offset_days"])

    # 1. Acceptance date
    if grn_date:
        acceptance, basis = grn_date, "grn"
        acc_reason = f"Acceptance {grn_date.isoformat()} taken from the GRN date."
    elif challan_received_date:
        acceptance, basis = challan_received_date, "challan_received"
        acc_reason = (
            f"No GRN; acceptance {challan_received_date.isoformat()} taken from the "
            "received date on the delivery challan."
        )
    elif delivery_date:
        acceptance = delivery_date + timedelta(days=deemed_offset)
        basis = "deemed"
        acc_reason = (
            f"No GRN or signed receipt; deemed acceptance {acceptance.isoformat()} = "
            f"delivery {delivery_date.isoformat()} + {deemed_offset} days (estimated, verify)."
        )
    else:
        return DueDateResult(
            acceptance_date=None, acceptance_basis="unknown", terms_days_applied=None,
            terms_basis="unknown", due_date=None, msmed_applies=applies,
            reasoning="Cannot compute a due date: no GRN, receipt or delivery date found.",
        )

    # 2. Terms
    uncertain = False
    if has_written_terms and terms_days is None:
        applied, terms_basis, uncertain = no_agreement_days, "written_terms_unreadable", True
        terms_reason = (
            "Written payment terms appear on the documents but the number of days could not "
            f"be read; a {no_agreement_days}-day figure is shown only as a placeholder. "
            "Verify the terms manually."
        )
    elif has_written_terms:
        if applies and terms_days > max_days:
            applied, terms_basis = max_days, "written_terms_capped"
            terms_reason = (
                f"Written terms of {terms_days} days exceed the MSMED s.15 limit; "
                f"capped at {max_days} days."
            )
        else:
            applied, terms_basis = terms_days, "written_terms"
            terms_reason = f"Written terms of {terms_days} days applied."
    elif applies:
        applied, terms_basis = no_agreement_days, "no_written_terms"
        terms_reason = (
            f"No written payment terms found; MSMED s.15 default of "
            f"{no_agreement_days} days applied."
        )
    else:
        applied, terms_basis, uncertain = no_agreement_days, "no_written_terms", True
        terms_reason = (
            f"No written payment terms found and MSMED s.15 does not apply to a {cls} "
            f"enterprise; {no_agreement_days} days assumed. Verify the agreed terms."
        )

    due = acceptance + timedelta(days=applied)
    label = "uncertain estimate" if uncertain else "estimated"
    reasoning = f"{acc_reason} {terms_reason} Due date {due.isoformat()} ({label})."
    return DueDateResult(
        acceptance_date=acceptance, acceptance_basis=basis, terms_days_applied=applied,
        terms_basis=terms_basis, due_date=due, reasoning=reasoning,
        uncertain=uncertain, msmed_applies=applies,
    )
