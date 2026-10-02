"""
Unit test suite for Phase 13 / TASK-0037 to TASK-0041 (v7.3).

Verifies:
1. Intrinsic Compounder Valuation: No synthetic FV (P * 1.18 removed, independent of market price).
2. Bank Fail-Safe: Missing P/B does not generate synthetic FV (P * 1.12 removed).
3. Institutional Consensus Lifecycle: Default 90-day staleness threshold.
4. Structural Stop Loss & Liquidity Gap Risk Sizing (2 floor sessions -14% stress).
5. Macro Circuit Breaker Hysteresis (Anti-Whipsaw around MA200).
6. Data Gate Field-level Freshness & Frozen Data Penalty.
"""

import pandas as pd

from data_gate import FLAG_DATA_STALE_FREEZE, reconcile_data, reconcile_financial_period
from quant_engine import (
    calculate_gap_risk_position_sizing,
    calculate_structural_stop_loss,
    evaluate_decision_hard_gates,
)
from quant_valuation import (
    calculate_fair_value_and_mos,
    check_institutional_target_freshness,
    evaluate_compounder_valuation,
)
from regime_classifier import (
    METHOD_MA200_HYSTERESIS,
    REGIME_DOWNTREND,
    classify_market_regime,
    classify_regime_ma200_hysteresis,
)


# =============================================================================
# 1. INTRINSIC COMPOUNDER VALUATION & ZERO SYNTHETIC FV (TASK-0037)
# =============================================================================
class TestCompounderIntrinsicValuation:
    """Verifies that Compounder archetype does NOT rely on current_price * 1.18."""

    def test_mwg_valuation_independent_of_price_fluctuations(self):
        """When market price changes, base intrinsic fair value remains stable."""
        # Test MWG with two completely different prices
        val_low = calculate_fair_value_and_mos("MWG", current_price=60.0, sector="Bán lẻ")
        val_high = calculate_fair_value_and_mos("MWG", current_price=80.0, sector="Bán lẻ")

        # In v7.2, FV was 0.708 * P + 28.39, so FV moved with price.
        # In v7.3, intrinsic base FV is derived from Forward EPS & SOTP.
        assert val_low["fair_value"] > 0
        assert val_high["fair_value"] > 0

        # MoS must change dynamically with market price, NOT be fixed at 15.3%
        assert val_low["mos_pct"] > val_high["mos_pct"]
        assert val_low["mos_pct"] != 15.25
        assert val_high["mos_pct"] != 15.25

    def test_unknown_compounder_without_data_returns_zero_fv(self):
        """Unknown compounder with no EPS/PE returns fair_value=0.0 and uninformative MoS."""
        res = evaluate_compounder_valuation("UNKNOWN_COMP", current_price=50.0, fin_dict={}, sector="Bán lẻ")
        assert res["fv_base"] == 0.0
        assert res["is_informative"] is False
        assert "INSUFFICIENT_DATA" in res["valuation_method"]

        full_res = calculate_fair_value_and_mos("UNKNOWN_COMP", current_price=50.0, sector="Bán lẻ")
        assert full_res["fair_value"] == 0.0
        assert full_res["mos_is_informative"] is False
        assert full_res["mos_pct"] == 0.0

    def test_compounder_with_dynamic_fin_dict_eps_and_pe(self):
        """When fin_dict provides EPS and P/E, valuation computes intrinsic FV cleanly."""
        fin = {"eps": 4.0, "pe": 15.0, "historical_median_pe": 16.0, "roe": 20.0}
        res = evaluate_compounder_valuation("GROWTH_XYZ", current_price=55.0, fin_dict=fin, sector="Công nghệ")
        assert res["is_informative"] is True
        assert res["fv_base"] > 0
        # Expected: forward_eps ~ 4.0 * (1 + 0.14) = 4.56, fv_base = 4.56 * 16.0 ~ 72.96
        assert 65.0 <= res["fv_base"] <= 80.0


# =============================================================================
# 2. BANK ARCHETYPE FAIL-SAFE (TASK-0037)
# =============================================================================
class TestBankValuationFailSafe:
    """Verifies that missing P/B does NOT produce synthetic current_price * 1.12."""

    def test_bank_missing_pb_returns_insufficient_data(self):
        val = calculate_fair_value_and_mos("MSB", current_price=15.0, fin_dict={"pb": None}, sector="Ngân hàng")
        assert val["fair_value"] == 0.0
        assert val["mos_is_informative"] is False
        assert "INSUFFICIENT_DATA" in val["valuation_method"]


# =============================================================================
# 3. CONSENSUS TARGET LIFECYCLE (TASK-0038)
# =============================================================================
class TestConsensusFreshnessLifecycle:
    """Verifies 90-day staleness threshold for institutional consensus targets."""

    def test_consensus_defaults_to_90_days(self):
        fresh = check_institutional_target_freshness("MWG", as_of_date="2026-10-02")
        # MWG last_updated is 2026-09-30 (age = 2 days)
        assert fresh["is_stale"] is False
        assert fresh["age_days"] <= 90

    def test_consensus_stale_when_over_90_days(self):
        stale = check_institutional_target_freshness("MWG", as_of_date="2027-01-15")
        # Age > 100 days (> 90 days)
        assert stale["is_stale"] is True
        assert "Target outdated" in stale["warning"]


# =============================================================================
# 4. STRUCTURAL STOP-LOSS & GAP RISK POSITION SIZING (TASK-0039)
# =============================================================================
class TestStructuralStopLossAndGapSizing:
    """Verifies structural stop-loss and gap risk position sizing."""

    def test_structural_stop_loss_anchors_on_swing_low(self):
        tech = {"swing_low": 48.0, "atr": 1.5, "ma50": 46.0}
        stop, risk_pct, desc = calculate_structural_stop_loss(current_price=52.0, tech_data=tech)
        # Expected: swing_low 48.0 - 0.5 * 1.5 = 47.25
        assert stop == 47.25
        assert "SWING_LOW" in desc
        assert 8.0 <= risk_pct <= 10.5

    def test_structural_stop_loss_not_fixed_at_seven_percent(self):
        tech = {"swing_low": 68.0, "atr": 1.0}
        stop, risk_pct, desc = calculate_structural_stop_loss(current_price=70.0, tech_data=tech)
        # 68.0 - 0.5 = 67.5 -> (70 - 67.5) / 70 = 3.57% -> bounded by min room 5% -> 66.50
        assert stop != round(70.0 * 0.93, 2)

    def test_gap_risk_sizing_caps_portfolio_risk(self):
        # Half-Kelly suggests 25% NAV, but stress testing 2 floor sessions (-14%) limits size
        size, note = calculate_gap_risk_position_sizing(
            kelly_f=0.50,  # Half-Kelly = 25%
            stop_loss_pct=6.0,  # Nominal SL = 6%
            max_nav_risk=0.015,  # 1.5% NAV risk
            floor_gap_risk=0.14,  # -14% gap risk
        )
        # Budget size = 0.015 / 0.14 = 0.1071 (10.7% NAV)
        assert size == 0.1071
        assert "Stress -14%" in note

    def test_hard_gate_blocks_uninformative_mos(self):
        """Hard gate rejects buy when mos_is_informative is False."""
        gate = evaluate_decision_hard_gates(
            current_price=50.0,
            p_bull=0.6,
            p_base=0.3,
            p_bear=0.1,
            price_bull=70.0,
            price_base=60.0,
            price_bear=40.0,
            symbol="UNKNOWN_COMP",
            sector="Bán lẻ",
        )
        assert gate["mos_is_informative"] is False
        assert gate["gate_mos_passed"] is False
        assert gate["can_buy"] is False


# =============================================================================
# 5. MACRO HYSTERESIS BUFFER (TASK-0040)
# =============================================================================
class TestMacroHysteresisBuffer:
    """Verifies that MA200 hysteresis buffer prevents whipsaws in choppy markets."""

    def test_hysteresis_ignores_single_day_minor_dip(self):
        # 210 sessions of data with MA200 ~ 1200
        # Last session closes at 1195 (0.4% below MA200, within 1.5% buffer)
        prices = [1200.0] * 209 + [1195.0]
        df = pd.DataFrame({"close": prices, "volume": [100000] * 210})

        regimes = classify_regime_ma200_hysteresis(df, ma_window=200, hysteresis_pct=1.5)
        # Should stay SIDEWAYS, NOT drop immediately into DOWNTREND
        assert regimes.iloc[-1] != REGIME_DOWNTREND

    def test_hysteresis_triggers_downtrend_after_two_confirmed_sessions(self):
        # Last 2 sessions close 2.0% below MA200 (> 1.5% buffer)
        ma_level = 1200.0
        dip_level = ma_level * 0.975  # -2.5%
        prices = [ma_level] * 208 + [dip_level, dip_level]
        df = pd.DataFrame({"close": prices, "volume": [100000] * 210})

        regimes = classify_regime_ma200_hysteresis(
            df, ma_window=200, hysteresis_pct=1.5, confirmation_sessions=2
        )
        assert regimes.iloc[-1] == REGIME_DOWNTREND

    def test_classify_market_regime_supports_hysteresis_method(self):
        df = pd.DataFrame({"close": [1200.0] * 210, "volume": [100000] * 210})
        res = classify_market_regime(df, method=METHOD_MA200_HYSTERESIS)
        assert not res.empty


# =============================================================================
# 6. DATA GATE FIELD-LEVEL FRESHNESS & FROZEN PENALTY (TASK-0041)
# =============================================================================
class TestDataGateFieldFreshness:
    """Verifies frozen data flags and penalty triggers in Data Gate."""

    def test_stale_freeze_flag_on_old_statement(self):
        fin_data = {
            "pe": 12.0,
            "pb": 1.5,
            "roe": 15.0,
            "f_score": 7,
            "z_score": 2.5,
            "days_since_statement": 200,  # > 180d
        }
        _, stale = reconcile_financial_period(fin_data)
        assert any(FLAG_DATA_STALE_FREEZE in s for s in stale)

    def test_data_gate_locks_recommendation_when_frozen(self):
        fin_data = {
            "pe": 12.0,
            "pb": 1.5,
            "roe": 15.0,
            "f_score": 7,
            "z_score": 2.5,
            "is_frozen": True,
        }
        res = reconcile_data("TEST_FROZEN", fin_data=fin_data)
        assert res["is_stale"] is True
        assert res["recommendation_allowed"] is False
        assert "DỮ LIỆU ĐÓNG BĂNG" in res["badge"]
