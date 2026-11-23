"""Small display helpers shared by follow-ups and the dispute pack."""

from __future__ import annotations

from datetime import date
from typing import Optional


def inr(x: Optional[float], symbol: str = "₹") -> str:
    """Indian digit grouping, rounded to whole rupees: 240000 -> '₹2,40,000'.

    Use ``symbol="Rs. "`` where the font cannot draw the rupee sign (PDF core fonts).
    """
    if x is None:
        return "-"
    sign = "-" if x < 0 else ""
    whole = f"{abs(x):.0f}"
    if len(whole) > 3:
        head, tail = whole[:-3], whole[-3:]
        groups = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        if head:
            groups.insert(0, head)
        whole = ",".join(groups + [tail])
    return f"{sign}{symbol}{whole}"


def d(x: Optional[date]) -> str:
    """Readable date for letters: 2026-10-02 -> '02 Oct 2026'."""
    return x.strftime("%d %b %Y") if x else "not determined"
