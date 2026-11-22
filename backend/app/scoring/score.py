"""score = 100 - sum(penalties), clamped 0..100; tier from config (§7)."""

from __future__ import annotations

from typing import Any, Iterable, Optional

from app.rules.config import get_config
from app.schemas import Check, CheckStatus, Penalty, RiskTier, ScoreBreakdown


def penalty_for(check: Check, cfg: dict[str, Any]) -> int:
    if check.status == CheckStatus.passed or check.severity.value == "info":
        return 0
    sc = cfg["scoring"]
    if check.status == CheckStatus.uncertain:
        return int(sc["penalties"]["uncertain"])
    override = sc.get("overrides", {}).get(check.check_id)
    if override is not None:
        return int(override)
    return int(sc["penalties"][check.severity.value])


def tier_for(score: int, cfg: dict[str, Any]) -> RiskTier:
    tiers = cfg["scoring"]["tiers"]
    if score >= int(tiers["low_min"]):
        return RiskTier.low
    if score >= int(tiers["medium_min"]):
        return RiskTier.medium
    return RiskTier.high


def compute_score(checks: Iterable[Check], cfg: Optional[dict[str, Any]] = None) -> ScoreBreakdown:
    if cfg is None:
        cfg = get_config()
    penalties: list[Penalty] = []
    for c in checks:
        pts = penalty_for(c, cfg)
        if pts:
            penalties.append(
                Penalty(check_id=c.check_id, status=c.status, severity=c.severity, points=pts)
            )
    score = max(0, min(100, 100 - sum(p.points for p in penalties)))
    return ScoreBreakdown(score=score, tier=tier_for(score, cfg), penalties=penalties)
