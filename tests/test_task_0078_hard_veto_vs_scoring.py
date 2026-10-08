"""Unit tests for TASK-0078: Decoupled Hard Veto & Conviction Scoring System."""


from entry_gates import (
    ACTION_ACCUMULATE,
    ACTION_WATCH,
    GATE_ADV20_LIQUIDITY,
    GATE_DATA_GATE,
    GATE_FINANCIAL_HEALTH,
    GATE_MACRO_REGIME,
    GATE_PM_VETO,
    GATE_QUANT_CONVICTION,
    GATE_TECHNICAL_MOMENTUM,
    GATE_VALUATION_MOS,
    evaluate_entry_gates,
)

MOCK_TECH_BASE = {
    "current_price": 50.0,
    "ma20": 48.0,
    "ma50": 46.0,
    "rsi14": 56.0,
    "adv20_billion": 15.0,
    "tech_signal": "BULLISH_CONFIRMED",
}

MOCK_FIN_HEALTHY = {
    "f_score": 8,
    "z_score": 3.5,
    "roe": 22.0,
    "pe": 12.0,
    "pb": 1.5,
    "mos_pct": 20.0,
    "mos_is_informative": True,
    "period": "2026-Q2",
}


class TestTask0078HardVetoFailFast:
    """Verify that only existential fatal errors trigger Hard Veto (Fail-fast)."""

    def test_hard_veto_macro_downtrend(self):
        res = evaluate_entry_gates(
            symbol="HPG",
            current_price=50.0,
            fin_dict=MOCK_FIN_HEALTHY,
            tech_data=MOCK_TECH_BASE,
            macro_regime="DOWNTREND",
            conviction_score=85.0,
        )
        assert res.can_buy is False
        assert res.blocked_by == GATE_MACRO_REGIME

    def test_hard_veto_data_gate_stale(self):
        stale_fin = {**MOCK_FIN_HEALTHY, "period": "2023-Q1"}
        res = evaluate_entry_gates(
            symbol="HPG",
            current_price=50.0,
            fin_dict=stale_fin,
            tech_data=MOCK_TECH_BASE,
            macro_regime="UPTREND",
            conviction_score=85.0,
        )
        assert res.can_buy is False
        assert res.blocked_by == GATE_DATA_GATE

    def test_hard_veto_thesis_breaker_f_score(self):
        bad_fin = {**MOCK_FIN_HEALTHY, "f_score": 3}
        res = evaluate_entry_gates(
            symbol="HPG",
            current_price=50.0,
            fin_dict=bad_fin,
            tech_data=MOCK_TECH_BASE,
            macro_regime="UPTREND",
            conviction_score=85.0,
        )
        assert res.can_buy is False
        assert res.blocked_by == GATE_FINANCIAL_HEALTH

    def test_hard_veto_thesis_breaker_z_score_distress(self):
        distress_fin = {**MOCK_FIN_HEALTHY, "f_score": 6, "z_score": 1.10}
        res = evaluate_entry_gates(
            symbol="HPG",
            current_price=50.0,
            fin_dict=distress_fin,
            tech_data=MOCK_TECH_BASE,
            macro_regime="UPTREND",
            conviction_score=85.0,
            sector="Thép",
        )
        assert res.can_buy is False
        assert res.blocked_by == GATE_FINANCIAL_HEALTH

    def test_hard_veto_overvalued_mos_below_threshold(self):
        overvalued_fin = {**MOCK_FIN_HEALTHY, "mos_pct": -5.0}
        res = evaluate_entry_gates(
            symbol="HPG",
            current_price=50.0,
            fin_dict=overvalued_fin,
            tech_data=MOCK_TECH_BASE,
            macro_regime="UPTREND",
            conviction_score=85.0,
        )
        assert res.can_buy is False
        assert res.blocked_by == GATE_VALUATION_MOS

    def test_hard_veto_illiquid_adv20(self):
        illiquid_tech = {**MOCK_TECH_BASE, "adv20_billion": 0.8}
        res = evaluate_entry_gates(
            symbol="HPG",
            current_price=50.0,
            fin_dict=MOCK_FIN_HEALTHY,
            tech_data=illiquid_tech,
            macro_regime="UPTREND",
            conviction_score=85.0,
        )
        assert res.can_buy is False
        assert res.blocked_by == GATE_ADV20_LIQUIDITY

    def test_hard_veto_falling_knife(self):
        falling_tech = {**MOCK_TECH_BASE, "tech_signal": "FALLING_KNIFE"}
        res = evaluate_entry_gates(
            symbol="HPG",
            current_price=50.0,
            fin_dict=MOCK_FIN_HEALTHY,
            tech_data=falling_tech,
            macro_regime="UPTREND",
            conviction_score=85.0,
        )
        assert res.can_buy is False
        assert res.blocked_by == GATE_TECHNICAL_MOMENTUM
        assert any("FALLING_KNIFE" in r for r in res.blocking_reasons)

    def test_hard_veto_pm_veto(self):
        res = evaluate_entry_gates(
            symbol="HPG",
            current_price=50.0,
            fin_dict=MOCK_FIN_HEALTHY,
            tech_data=MOCK_TECH_BASE,
            macro_regime="UPTREND",
            conviction_score=85.0,
            pm_veto=True,
        )
        assert res.can_buy is False
        assert res.blocked_by == GATE_PM_VETO


class TestTask0078DecoupledScoringSystem:
    """Verify that non-fatal technical signals do NOT hard-veto and rely on Conviction Scoring."""

    def test_consolidation_base_does_not_hard_veto(self):
        # Stock is consolidating below MA20 but has great fundamentals and high conviction (75.0)
        consolidating_tech = {
            **MOCK_TECH_BASE,
            "current_price": 49.0,
            "ma20": 50.0,
            "tech_signal": "CONSOLIDATION_BASE",
        }
        res = evaluate_entry_gates(
            symbol="HPG",
            current_price=49.0,
            fin_dict=MOCK_FIN_HEALTHY,
            tech_data=consolidating_tech,
            macro_regime="UPTREND",
            conviction_score=75.0,
        )
        # Should NOT be blocked by technical momentum!
        assert res.can_buy is True
        assert GATE_TECHNICAL_MOMENTUM in res.passed_gates
        assert res.action_state == ACTION_ACCUMULATE

    def test_weak_below_ma20_does_not_hard_veto_and_passes_to_scoring(self):
        # Stock is slightly weak below MA20, but not falling knife
        weak_tech = {
            **MOCK_TECH_BASE,
            "current_price": 48.0,
            "ma20": 50.0,
            "tech_signal": "WEAK_BELOW_MA20",
        }
        # With conviction >= 70, it passes
        res = evaluate_entry_gates(
            symbol="HPG",
            current_price=48.0,
            fin_dict=MOCK_FIN_HEALTHY,
            tech_data=weak_tech,
            macro_regime="UPTREND",
            conviction_score=72.0,
        )
        assert res.can_buy is True
        assert GATE_TECHNICAL_MOMENTUM in res.passed_gates

    def test_moderate_conviction_routes_to_watchlist(self):
        # Conviction 60.0 (< 70 but >= 55) -> Blocked from buy, routes to WATCH
        res = evaluate_entry_gates(
            symbol="HPG",
            current_price=50.0,
            fin_dict=MOCK_FIN_HEALTHY,
            tech_data=MOCK_TECH_BASE,
            macro_regime="UPTREND",
            conviction_score=60.0,
        )
        assert res.can_buy is False
        assert res.blocked_by == GATE_QUANT_CONVICTION
        assert res.action_state == ACTION_WATCH

    def test_low_conviction_rejected(self):
        # Conviction 45.0 (< 55) -> Blocked by GATE_QUANT_CONVICTION
        res = evaluate_entry_gates(
            symbol="HPG",
            current_price=50.0,
            fin_dict=MOCK_FIN_HEALTHY,
            tech_data=MOCK_TECH_BASE,
            macro_regime="UPTREND",
            conviction_score=45.0,
        )
        assert res.can_buy is False
        assert res.blocked_by == GATE_QUANT_CONVICTION
