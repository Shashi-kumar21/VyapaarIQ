from datetime import date

import pytest

from app.rules.config import get_config
from app.rules.due_date import compute_due_date
from app.rules.interest import estimate_interest
from app.schemas import Check, CheckStatus, RiskTier, Severity
from app.scoring.score import compute_score

D = date


# ---------------------------------------------------------------- due date
def test_grn_date_wins_and_written_terms_apply():
    r = compute_due_date(
        grn_date=D(2026, 3, 10),
        challan_received_date=D(2026, 3, 5),
        delivery_date=D(2026, 3, 5),
        terms_days=30,
        has_written_terms=True,
    )
    assert r.acceptance_basis == "grn"
    assert r.terms_basis == "written_terms"
    assert r.due_date == D(2026, 4, 9)
    assert "GRN" in r.reasoning


def test_challan_received_used_when_no_grn():
    r = compute_due_date(
        grn_date=None,
        challan_received_date=D(2026, 3, 5),
        delivery_date=D(2026, 3, 4),
        terms_days=30,
        has_written_terms=True,
    )
    assert r.acceptance_basis == "challan_received"
    assert r.due_date == D(2026, 4, 4)


def test_deemed_acceptance_from_delivery_plus_offset():
    r = compute_due_date(
        grn_date=None,
        challan_received_date=None,
        delivery_date=D(2026, 3, 1),
        terms_days=30,
        has_written_terms=True,
    )
    assert r.acceptance_basis == "deemed"
    assert r.acceptance_date == D(2026, 3, 16)
    assert r.due_date == D(2026, 4, 15)
    assert "deemed" in r.reasoning


def test_terms_above_45_are_capped():
    r = compute_due_date(
        grn_date=D(2026, 1, 1), challan_received_date=None, delivery_date=None,
        terms_days=90, has_written_terms=True,
    )
    assert r.terms_basis == "written_terms_capped"
    assert r.terms_days_applied == 45
    assert r.due_date == D(2026, 2, 15)


def test_no_written_terms_uses_15_days():
    r = compute_due_date(
        grn_date=D(2026, 1, 1), challan_received_date=None, delivery_date=None,
        terms_days=None, has_written_terms=False,
    )
    assert r.terms_basis == "no_written_terms"
    assert r.due_date == D(2026, 1, 16)


def test_unknown_when_no_dates():
    r = compute_due_date(
        grn_date=None, challan_received_date=None, delivery_date=None,
        terms_days=30, has_written_terms=True,
    )
    assert r.due_date is None and r.acceptance_basis == "unknown"


def test_config_override_changes_limits():
    cfg = get_config()
    cfg["msmed"]["max_terms_days"] = 30
    r = compute_due_date(
        grn_date=D(2026, 1, 1), challan_received_date=None, delivery_date=None,
        terms_days=45, has_written_terms=True, cfg=cfg,
    )
    assert r.terms_days_applied == 30


# ---------------------------------------------------------------- interest
def _cfg(rate=6.0):
    cfg = get_config()
    cfg["rbi"]["bank_rate_pct"] = rate
    cfg["msmed"]["interest_multiplier"] = 3
    return cfg


def test_no_interest_before_due():
    r = estimate_interest(100000, D(2026, 5, 1), D(2026, 4, 1), cfg=_cfg())
    assert r.days_late == 0 and r.interest == 0.0


def test_one_full_month_at_18pct():
    r = estimate_interest(100000, D(2026, 1, 1), D(2026, 1, 31), cfg=_cfg())
    assert r.days_late == 30
    assert r.annual_rate_pct == 18.0
    assert r.interest == pytest.approx(1500.0)


def test_compounds_monthly():
    r = estimate_interest(100000, D(2026, 1, 1), D(2026, 3, 2), cfg=_cfg())  # 60 days
    assert r.interest == pytest.approx(100000 * (1.015**2 - 1), abs=0.01)


def test_partial_month_is_pro_rata():
    r = estimate_interest(100000, D(2026, 1, 1), D(2026, 1, 16), cfg=_cfg())  # 15 days
    assert r.interest == pytest.approx(750.0)
    assert "3 x RBI bank rate" in r.formula


def test_missing_due_date_gives_zero():
    r = estimate_interest(100000, None, D(2026, 1, 16), cfg=_cfg())
    assert r.interest == 0.0


# ---------------------------------------------------------------- scoring
def _c(cid, status, sev):
    return Check(check_id=cid, name=cid, status=status, severity=sev, detail="")


def test_clean_scores_100_low():
    s = compute_score([_c("C01", CheckStatus.passed, Severity.blocker)])
    assert s.score == 100 and s.tier == RiskTier.low and s.penalties == []


def test_c10_override_and_tiers():
    s = compute_score([_c("C10", CheckStatus.missing, Severity.blocker)])
    assert s.score == 70 and s.tier == RiskTier.medium
    assert s.penalties[0].points == 30


def test_mixed_penalties_and_clamp():
    checks = [
        _c("C01", CheckStatus.fail, Severity.blocker),     # 25
        _c("C07", CheckStatus.fail, Severity.warning),     # 10
        _c("C04", CheckStatus.uncertain, Severity.blocker),  # 5
        _c("C13", CheckStatus.fail, Severity.info),        # 0
    ]
    s = compute_score(checks)
    assert s.score == 60 and s.tier == RiskTier.medium
    assert [p.check_id for p in s.penalties] == ["C01", "C07", "C04"]

    many = [_c(f"C0{i}", CheckStatus.fail, Severity.blocker) for i in range(1, 6)]
    assert compute_score(many).score == 0
    assert compute_score(many).tier == RiskTier.high
