"""Unit tests for TASK-0077: Unified Policy Constants & Calibrated Kelly Sizing."""

import pytest

from policy_constants import (
    ACTION_ACCUMULATE,
    ACTION_BUY,
    ACTION_EXIT_OVERVALUED,
    ACTION_EXIT_THESIS,
    ACTION_HOLD,
    ACTION_PARTIAL_PROFIT,
    ACTION_REDUCE,
    ACTION_STOP_LOSS,
    ACTION_WATCH,
    ARCHETYPE_MOS_THRESHOLDS,
    ATR_STOP_MULTIPLIER,
    BREAKEVEN_LOCK_TARGET_PCT,
    BUY_ACTIONS,
    BUY_CONVICTION_MIN,
    DEFAULT_MIN_MOS_PCT,
    DRAWDOWN_BREAKER_PCT,
    DRAWDOWN_HALF_SIZE_PCT,
    F_SCORE_MIN,
    FIXED_RISK_NAV_PCT,
    HARD_STOP_LOSS_PCT,
    MAX_ADV20_ABSORPTION_PCT,
    MAX_FIXED_RISK_NAV_PCT,
    MAX_POSITION_SIZE_NAV_PCT,
    MAX_POSITIONS_PER_SECTOR,
    MAX_SECTOR_EXPOSURE_PCT,
    MIN_ADV20_BILLION,
    MIN_TRADES_FOR_KELLY_CALIBRATION,
    OVERVALUED_MOS_THRESHOLD,
    PARTIAL_TAKE_PROFIT_PCT,
    PROFIT_TRAIL_THRESHOLD_PCT,
    RSI_MAX_ENTRY,
    STRUCTURAL_STOP_LOSS_PCT,
    WARNING_LOSS_PCT,
    WATCH_CONVICTION_MIN,
    Z_SCORE_MIN,
)
from portfolio_guard import (
    calculate_drawdown_controlled_sizing,
    calculate_fixed_risk_position_size,
    evaluate_sell_thesis,
)


class TestTask0077PolicyConstants:
    """Verify single source of truth policy constants exist and match specifications."""

    def test_canonical_action_vocabulary(self):
        assert ACTION_BUY == "🟢 MUA"
        assert ACTION_ACCUMULATE == "🟢 TÍCH LŨY"
        assert ACTION_WATCH == "🟡 THEO DÕI"
        assert ACTION_HOLD == "🟡 NẮM GIỮ"
        assert ACTION_REDUCE == "🟠 HẠ TỶ TRỌNG"
        assert ACTION_STOP_LOSS == "🔴 CẮT LỖ KỸ THUẬT"
        assert ACTION_EXIT_THESIS == "🔴 THOÁT VỊ THẾ (THESIS BREAKER)"
        assert ACTION_EXIT_OVERVALUED == "🔴 CHỐT LỜI / THOÁT VỊ THẾ (ĐỊNH GIÁ ĐẮT ĐỎ)"
        assert ACTION_PARTIAL_PROFIT == "🟢 BẢO VỆ THÀNH QUẢ / CHỐT LỜI TỪNG PHẦN"

        # Signal routing sets
        assert ACTION_BUY in BUY_ACTIONS
        assert ACTION_ACCUMULATE in BUY_ACTIONS
        assert "MUA" in BUY_ACTIONS

    def test_valuation_and_risk_thresholds(self):
        assert DEFAULT_MIN_MOS_PCT == 15.0
        assert OVERVALUED_MOS_THRESHOLD == 0.0
        assert ARCHETYPE_MOS_THRESHOLDS["BANK"] == 10.0
        assert ARCHETYPE_MOS_THRESHOLDS["GROWTH"] == 15.0

        assert STRUCTURAL_STOP_LOSS_PCT == 7.0
        assert HARD_STOP_LOSS_PCT == 8.0
        assert WARNING_LOSS_PCT == 5.0
        assert PARTIAL_TAKE_PROFIT_PCT == 20.0
        assert PROFIT_TRAIL_THRESHOLD_PCT == 8.0
        assert BREAKEVEN_LOCK_TARGET_PCT == 12.0
        assert ATR_STOP_MULTIPLIER == 2.0

    def test_sizing_and_calibration_policy(self):
        assert FIXED_RISK_NAV_PCT == 0.01
        assert MAX_FIXED_RISK_NAV_PCT == 0.015
        assert MAX_POSITION_SIZE_NAV_PCT == 0.15
        assert MAX_SECTOR_EXPOSURE_PCT == 0.25
        assert MAX_POSITIONS_PER_SECTOR == 3
        assert MIN_TRADES_FOR_KELLY_CALIBRATION == 100
        assert DRAWDOWN_BREAKER_PCT == 10.0
        assert DRAWDOWN_HALF_SIZE_PCT == 5.0
        assert MIN_ADV20_BILLION == 2.0
        assert MAX_ADV20_ABSORPTION_PCT == 0.10

    def test_conviction_and_quality_gates(self):
        assert BUY_CONVICTION_MIN == 70.0
        assert WATCH_CONVICTION_MIN == 55.0
        assert F_SCORE_MIN == 6
        assert Z_SCORE_MIN == 1.80
        assert RSI_MAX_ENTRY == 70.0


class TestTask0077FixedRiskSizingAndKellyCalibration:
    """Verify Fixed Risk Sizing mathematical precision and Kelly calibration gate."""

    def test_fixed_risk_sizing_standard(self):
        # Entry 100, Stop 93 (7% risk on trade), NAV risk 1% -> 0.01 / 0.07 = 0.1429 (14.29% NAV)
        size = calculate_fixed_risk_position_size(entry_price=100.0, stop_loss_price=93.0)
        assert size == pytest.approx(0.1429, rel=1e-3)
        assert size <= MAX_POSITION_SIZE_NAV_PCT

    def test_fixed_risk_sizing_tight_stop_capped_at_max_cap(self):
        # Entry 100, Stop 98 (2% risk on trade), NAV risk 1% -> 0.01 / 0.02 = 50% -> Capped at 15%
        size = calculate_fixed_risk_position_size(entry_price=100.0, stop_loss_price=98.0)
        assert size == MAX_POSITION_SIZE_NAV_PCT

    def test_fixed_risk_sizing_wide_stop(self):
        # Entry 100, Stop 80 (20% risk on trade), NAV risk 1% -> 0.01 / 0.20 = 5% NAV
        size = calculate_fixed_risk_position_size(entry_price=100.0, stop_loss_price=80.0)
        assert size == 0.05

    def test_fixed_risk_sizing_invalid_inputs_fallback(self):
        # Zero entry price
        assert calculate_fixed_risk_position_size(entry_price=0.0, stop_loss_price=90.0) == 0.0
        # Negative entry price
        assert calculate_fixed_risk_position_size(entry_price=-50.0, stop_loss_price=45.0) == 0.0
        # Stop loss >= entry price (defaults to 7% structural stop)
        size = calculate_fixed_risk_position_size(entry_price=100.0, stop_loss_price=105.0)
        assert size == pytest.approx(0.1429, rel=1e-3)

    def test_uncalibrated_trades_enforces_fixed_risk_sizing(self):
        # Trades = 50 (<= 100) -> Fixed Risk Sizing enforced even if half_kelly_f was high
        size, label = calculate_drawdown_controlled_sizing(
            half_kelly_f=0.25,
            total_calibrated_trades=50,
            is_calibrated=True,
            entry_price=100.0,
            stop_loss_price=93.0,
        )
        assert label == "FIXED_RISK_SIZING_UNCALIBRATED"
        assert size == pytest.approx(0.1429, rel=1e-3)

    def test_uncalibrated_flag_enforces_fixed_risk_sizing(self):
        # Trades = 150 but is_calibrated = False -> Fixed Risk Sizing enforced
        size, label = calculate_drawdown_controlled_sizing(
            half_kelly_f=0.20,
            total_calibrated_trades=150,
            is_calibrated=False,
            entry_price=100.0,
            stop_loss_price=93.0,
        )
        assert label == "FIXED_RISK_SIZING_UNCALIBRATED"
        assert size == pytest.approx(0.1429, rel=1e-3)

    def test_calibrated_trades_over_100_unlocks_kelly_sizing(self):
        # Trades = 120 (> 100) and is_calibrated = True -> Kelly unlocked!
        size, label = calculate_drawdown_controlled_sizing(
            half_kelly_f=0.12,
            total_calibrated_trades=120,
            is_calibrated=True,
            entry_price=100.0,
            stop_loss_price=93.0,
        )
        assert label == "STANDARD_HALF_KELLY"
        assert size == 0.12

    def test_evaluate_sell_thesis_with_policy_constants(self):
        # 1. Thesis Breaker (Z-Score Red) -> ACTION_EXIT_THESIS
        fin_bad = {"roe": 5.0, "f_score": 2, "z_score": 1.0}
        res_tb = evaluate_sell_thesis(
            symbol="HPG",
            entry_price=28.0,
            curr_price=30.0,
            volume=1000,
            pl_pct=7.14,
            pl_val=2000000,
            atr=1.0,
            ma20=27.0,
            fin_dict=fin_bad,
            sector="Thép",
        )
        assert res_tb["action"] == ACTION_EXIT_THESIS
        assert res_tb["sell_status"] == "THESIS_BROKEN"

        # 2. Overvalued (MoS < 0) -> ACTION_EXIT_OVERVALUED
        fin_over = {"roe": 20.0, "f_score": 8, "z_score": 3.5, "fair_value": 25.0}  # curr_price 30 > fair_value 25
        res_ov = evaluate_sell_thesis(
            symbol="HPG",
            entry_price=28.0,
            curr_price=30.0,
            volume=1000,
            pl_pct=7.14,
            pl_val=2000000,
            atr=1.0,
            ma20=27.0,
            fin_dict=fin_over,
            sector="Thép",
        )
        assert res_ov["action"] == ACTION_EXIT_OVERVALUED
        assert res_ov["sell_status"] == "OVERVALUED"

        # 3. Hard Stop Loss (pl_pct <= -8.0%) -> ACTION_STOP_LOSS
        res_sl = evaluate_sell_thesis(
            symbol="HPG",
            entry_price=30.0,
            curr_price=27.0,  # -10%
            volume=1000,
            pl_pct=-10.0,
            pl_val=-3000000,
            atr=1.0,
            ma20=29.0,
            fin_dict={"f_score": 8, "z_score": 3.5, "fair_value": 35.0},
            sector="Thép",
        )
        assert res_sl["action"] == ACTION_STOP_LOSS
        assert res_sl["sell_status"] == "STOP_LOSS"

        # 4. Partial Profit (pl_pct >= 20.0%) -> ACTION_PARTIAL_PROFIT
        res_tp = evaluate_sell_thesis(
            symbol="HPG",
            entry_price=25.0,
            curr_price=31.0,  # +24%
            volume=1000,
            pl_pct=24.0,
            pl_val=6000000,
            atr=1.0,
            ma20=28.0,
            fin_dict={"f_score": 8, "z_score": 3.5, "fair_value": 40.0},
            sector="Thép",
        )
        assert res_tp["action"] == ACTION_PARTIAL_PROFIT
        assert res_tp["sell_status"] == "TAKE_PROFIT_PARTIAL"
