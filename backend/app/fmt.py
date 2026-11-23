"""Small display helpers shared by follow-ups and the dispute pack."""

from __future__ import annotations

from datetime import date
from typing import Optional


def inr(x: Optional[float], symbol: str = "₹", paise: bool = False) -> str:
    """Indian digit grouping: 240000 -> '₹2,40,000'; with ``paise=True`` -> '₹2,40,000.00'.

    Whole rupees by default. Use ``symbol="Rs. "`` where the font cannot draw the rupee sign.
    """
    if x is None:
        return "-"
    sign = "-" if x < 0 else ""
    text = f"{abs(x):.2f}" if paise else f"{abs(x):.0f}"
    whole, _, frac = text.partition(".")
    if len(whole) > 3:
        head, tail = whole[:-3], whole[-3:]
        groups = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        if head:
            groups.insert(0, head)
        whole = ",".join(groups + [tail])
    return f"{sign}{symbol}{whole}" + (f".{frac}" if frac else "")


def d(x: Optional[date]) -> str:
    """Readable date for letters: 2026-10-02 -> '02 Oct 2026'."""
    return x.strftime("%d %b %Y") if x else "not determined"
