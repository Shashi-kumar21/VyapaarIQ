"""Rule and scoring unit tests against a FIXED config (independent of config.yaml)."""

import copy
from datetime import date

import pytest

from app.rules.due_date import compute_due_date
from app.rules.interest import estimate_interest
from app.schemas import Check, CheckStatus, RiskTier, Severity
from app.scoring.score import compute_score

D = date

FIXED = {
    "supplier": {"enterprise_class": "small"},
    "msmed": {"max_terms_days": 45, "no_agreement_days": 15,
              "deemed_acceptance_offset_days": 15, "interest_multiplier": 3},
    "rbi": {"bank_rate_pct": 6.0},
    "scoring": {"penalties": {"blocker": 25, "warning": 10, "info": 0, "uncertain": 5},
                "overrides": {"C10": 30}, "tiers": {"low_min": 85, "medium_min": 60}},
}


@pytest.fixture()
def cfg():
    return copy.deepcopy(FIXED)


def due(cfg, **kw):
    base = dict(grn_date=None, challan_received_date=None, delivery_date=None,
                terms_days=30, has_written_terms=True)
    base.update(kw)
    return compute_due_date(cfg=cfg, **base)


# ---------------------------------------------------------------- due date
def test_grn_date_wins_and_written_terms_apply(cfg):
    r = due(cfg, grn_date=D(2026, 3, 10), challan_received_date=D(2026, 3, 5), delivery_date=D(2026, 3, 5))
    assert (r.acceptance_basis, r.terms_basis, r.due_date) == ("grn", "written_terms", D(2026, 4, 9))
    assert "GRN" in r.reasoning and not r.uncertain and r.msmed_applies


def test_challan_received_used_when_no_grn(cfg):
    r = due(cfg, challan_received_date=D(2026, 3, 5), delivery_date=D(2026, 3, 4))
    assert r.acceptance_basis == "challan_received" and r.due_date == D(2026, 4, 4)


def test_deemed_acceptance_from_delivery_plus_offset(cfg):
    r = due(cfg, delivery_date=D(2026, 3, 1))
    assert r.acceptance_basis == "deemed" and r.acceptance_date == D(2026, 3, 16)
    assert r.due_date == D(2026, 4, 15) and "deemed" in r.reasoning


def test_deemed_offset_is_configurable(cfg):
    cfg["msmed"]["deemed_acceptance_offset_days"] = 0  # s.2(b) reading: delivery day itself
    assert due(cfg, delivery_date=D(2026, 3, 1)).acceptance_date == D(2026, 3, 1)


def test_terms_above_45_are_capped_for_small(cfg):
    r = due(cfg, grn_date=D(2026, 1, 1), terms_days=90)
    assert (r.terms_basis, r.terms_days_applied, r.due_date) == ("written_terms_capped", 45, D(2026, 2, 15))


def test_no_written_terms_uses_15_days(cfg):
    r = due(cfg, grn_date=D(2026, 1, 1), terms_days=None, has_written_terms=False)
    assert r.terms_basis == "no_written_terms" and r.due_date == D(2026, 1, 16) and not r.uncertain


def test_unreadable_terms_are_uncertain_not_absent(cfg):
    r = due(cfg, grn_date=D(2026, 1, 1), terms_days=None, has_written_terms=True)
    assert r.terms_basis == "written_terms_unreadable" and r.uncertain
    assert "could not be read" in r.reasoning and "No written payment terms" not in r.reasoning


def test_medium_supplier_no_msmed_cap(cfg):
    cfg["supplier"]["enterprise_class"] = "medium"
    r = due(cfg, grn_date=D(2026, 1, 1), terms_days=90)
    assert not r.msmed_applies and r.terms_basis == "written_terms" and r.terms_days_applied == 90
    r2 = due(cfg, grn_date=D(2026, 1, 1), terms_days=None, has_written_terms=False)
    assert r2.uncertain and "does not apply" in r2.reasoning


def test_explicit_class_overrides_config(cfg):
    r = due(cfg, grn_date=D(2026, 1, 1), terms_days=90, enterprise_class="micro")
    assert r.terms_days_applied == 45


def test_unknown_when_no_dates(cfg):
    r = due(cfg)
    assert r.due_date is None and r.acceptance_basis == "unknown"


def test_zero_terms_allowed_negative_rejected(cfg):
    assert due(cfg, grn_date=D(2026, 1, 1), terms_days=0).due_date == D(2026, 1, 1)
    with pytest.raises(ValueError):
        due(cfg, grn_date=D(2026, 1, 1), terms_days=-5)


def test_config_override_changes_limits(cfg):
    cfg["msmed"]["max_terms_days"] = 30
    assert due(cfg, grn_date=D(2026, 1, 1), terms_days=45).terms_days_applied == 30


# ---------------------------------------------------------------- interest
def test_no_interest_before_due(cfg):
    r = estimate_interest(100000, D(2026, 5, 1), D(2026, 4, 1), cfg=cfg)
    assert r.days_late == 0 and r.interest == 0.0 and r.computable


def test_one_full_month_at_18pct(cfg):
    r = estimate_interest(100000, D(2026, 1, 1), D(2026, 1, 31), cfg=cfg)
    assert r.days_late == 30 and r.annual_rate_pct == 18.0
    assert r.interest == pytest.approx(1500.0)


def test_compounds_monthly(cfg):
    r = estimate_interest(100000, D(2026, 1, 1), D(2026, 3, 2), cfg=cfg)  # 60 days
    assert r.interest == pytest.approx(100000 * (1.015**2 - 1), abs=0.01)


def test_partial_month_is_pro_rata(cfg):
    r = estimate_interest(100000, D(2026, 1, 1), D(2026, 1, 16), cfg=cfg)  # 15 days
    assert r.interest == pytest.approx(750.0) and "3 x RBI bank rate" in r.formula


def test_missing_due_date_is_not_computable(cfg):
    r = estimate_interest(100000, None, D(2026, 1, 16), cfg=cfg)
    assert r.interest is None and not r.computable and r.formula.startswith("Not computable")


def test_medium_supplier_interest_not_applicable(cfg):
    cfg["supplier"]["enterprise_class"] = "medium"
    r = estimate_interest(100000, D(2026, 1, 1), D(2026, 3, 1), cfg=cfg)
    assert r.interest is None and not r.computable and "micro/small" in r.formula


def test_negative_principal_rejected(cfg):
    with pytest.raises(ValueError):
        estimate_interest(-1, D(2026, 1, 1), D(2026, 2, 1), cfg=cfg)


# ---------------------------------------------------------------- scoring
def _c(cid, status, sev):
    return Check(check_id=cid, name=cid, status=status, severity=sev, detail="")


P, F, M, U = CheckStatus.passed, CheckStatus.fail, CheckStatus.missing, CheckStatus.uncertain
B, W, I = Severity.blocker, Severity.warning, Severity.info


def test_clean_scores_100_low(cfg):
    s = compute_score([_c("C01", P, B)], cfg)
    assert s.score == 100 and s.tier == RiskTier.low and s.penalties == []


def test_c10_override(cfg):
    s = compute_score([_c("C10", M, B)], cfg)
    assert s.score == 70 and s.tier == RiskTier.medium and s.penalties[0].points == 30


def test_missing_on_warning_costs_warning_points(cfg):
    assert compute_score([_c("C09", M, W)], cfg).score == 90


def test_info_never_penalised_even_uncertain(cfg):
    assert compute_score([_c("C13", F, I), _c("C13", U, I), _c("C06", M, I)], cfg).score == 100


def test_uncertain_costs_5(cfg):
    assert compute_score([_c("C04", U, B)], cfg).score == 95


@pytest.mark.parametrize("checks,score,tier", [
    ([_c("C07", F, W), _c("C04", U, B)], 85, RiskTier.low),                       # boundary 85
    ([_c("C07", F, W), _c("C04", U, B), _c("C08", U, W)], 80, RiskTier.medium),
    ([_c("C01", F, B), _c("C07", F, W), _c("C04", U, B)], 60, RiskTier.medium),   # boundary 60
    ([_c("C01", F, B), _c("C07", F, W), _c("C04", U, B), _c("C08", U, W)], 55, RiskTier.high),
])
def test_tier_boundaries(cfg, checks, score, tier):
    s = compute_score(checks, cfg)
    assert (s.score, s.tier) == (score, tier)


def test_tier_just_below_boundaries(cfg):
    cfg["scoring"]["penalties"]["uncertain"] = 6
    assert compute_score([_c("C07", F, W), _c("C04", U, B)], cfg).tier == RiskTier.medium  # 84
    assert compute_score([_c("C01", F, B), _c("C07", F, W), _c("C04", U, B)], cfg).tier == RiskTier.high  # 59


def test_clamped_at_zero(cfg):
    many = [_c(f"C0{i}", F, B) for i in range(1, 6)]
    s = compute_score(many, cfg)
    assert s.score == 0 and s.tier == RiskTier.high
