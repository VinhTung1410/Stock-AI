"""Unit tests for portfolio_guard.py — Position evaluation, concentration guards, risk parity, and drawdown sizing."""

import pytest

from portfolio_guard import (
    calculate_drawdown_controlled_sizing,
    check_adv20_liquidity_absorption,
    check_portfolio_concentration,
    check_sector_concentration,
    evaluate_holding_position,
    evaluate_partial_profit_lock,
    optimize_portfolio_risk_parity,
)


@pytest.mark.offline
class TestPortfolioGuard:
    """Test suite for portfolio risk constraints and management."""

    def test_evaluate_holding_profitable_large_gain(self):
        row = {"symbol": "HPG", "avg_price": 20.0, "volume": 1000}
        tech = {"current_price": 25.0, "atr": 0.5, "ma20": 24.0}
        # pl_pct = +25% >= 20%
        res = evaluate_holding_position(row, tech)
        assert res["status"] == "PROFITABLE"
        assert res["is_profit"] is True
        assert res["trailing_stop"] < 25.0
        assert "BẢO VỆ THÀNH QUẢ" in res["action"]

    def test_evaluate_holding_profitable_moderate_gain(self):
        row = {"symbol": "MBB", "avg_price": 20.0, "volume": 1000}
        tech = {"current_price": 22.0, "atr": 0.4, "ma20": 21.0}
        # pl_pct = +10% (between 8% and 20%)
        res = evaluate_holding_position(row, tech)
        assert res["is_profit"] is True
        assert res["trailing_stop"] < 22.0
        assert "TIẾP TỤC NẮM GIỮ" in res["action"]

    def test_evaluate_holding_profitable_small_gain(self):
        row = {"symbol": "FPT", "avg_price": 100.0, "volume": 100}
        tech = {"current_price": 103.0, "atr": 1.0, "ma20": 101.0}
        # pl_pct = +3% (< 8%)
        res = evaluate_holding_position(row, tech)
        assert res["is_profit"] is True
        assert res["trailing_stop"] <= 100.0
        assert "THEO DÕI ĐÀ TĂNG" in res["action"]

    def test_evaluate_holding_loss_mild(self):
        row = {"symbol": "VNM", "avg_price": 70.0, "volume": 100}
        tech = {"current_price": 68.0, "atr": 1.0}
        # loss = -2.86% (<= 5%)
        res = evaluate_holding_position(row, tech)
        assert res["status"] == "LOSS"
        assert res["is_profit"] is False
        assert "THEO DÕI BIẾN ĐỘNG" in res["action"]

    def test_evaluate_holding_loss_moderate(self):
        row = {"symbol": "VNM", "avg_price": 70.0, "volume": 100}
        tech = {"current_price": 65.5, "atr": 1.0}
        # loss = -6.4% (between 5% and 8%)
        res = evaluate_holding_position(row, tech)
        assert res["status"] == "LOSS"
        assert "QUẢN TRỊ RỦI RO" in res["action"]

    def test_evaluate_holding_loss_severe(self):
        row = {"symbol": "VNM", "avg_price": 70.0, "volume": 100}
        tech = {"current_price": 62.0, "atr": 1.0}
        # loss = -11.4% (> 8%)
        res = evaluate_holding_position(row, tech)
        assert res["status"] == "LOSS"
        assert "CẮT LỖ KỸ THUẬT" in res["action"]

    def test_evaluate_holding_thesis_breaker_triggered(self):
        row = {"symbol": "NVL", "avg_price": 15.0, "volume": 1000}
        tech = {"current_price": 14.5, "atr": 0.5}
        # Bad financials: F-score < 4 or Distress Zone
        fin_bad = {"roa": -10.0, "debt_equity": 6.0, "f_score": 2, "z_score": 0.8}
        res = evaluate_holding_position(row, tech, fin_dict=fin_bad)
        assert res["status"] == "LOSS"
        assert "THOÁT VỊ THẾ" in res["action"]
        assert "THESIS BREAKER" in res["action"]

    def test_check_portfolio_concentration_dedup(self):
        candidates = [
            {"symbol": "VCB", "sector": "Ngân hàng", "mos_pct": 15.0, "risk_reward": 2.5, "f_score": 8},
            {"symbol": "MBB", "sector": "Ngân hàng", "mos_pct": 10.0, "risk_reward": 2.0, "f_score": 7},
            {"symbol": "HPG", "sector": "Thép", "mos_pct": 20.0, "risk_reward": 2.2, "f_score": 8},
        ]
        res = check_portfolio_concentration(candidates, max_per_sector=1)
        assert len(res["approved_candidates"]) == 2
        approved_syms = [c["symbol"] for c in res["approved_candidates"]]
        assert "VCB" in approved_syms
        assert "HPG" in approved_syms
        assert len(res["downgraded_candidates"]) == 1
        assert res["downgraded_candidates"][0]["symbol"] == "MBB"

    def test_calculate_drawdown_controlled_sizing(self):
        # Non-positive Kelly
        size, reason = calculate_drawdown_controlled_sizing(0.0)
        assert size == 0.0
        assert reason == "KELLY_NON_POSITIVE"

        # Hard Drawdown >= 10%
        size, reason = calculate_drawdown_controlled_sizing(0.12, current_drawdown_pct=11.5)
        assert size == 0.0
        assert reason == "DRAWDOWN_BREAKER_TRIGGERED"

        # Defensive half size (DD >= 5% or 2 consecutive losses)
        size, reason = calculate_drawdown_controlled_sizing(0.10, consecutive_losses=2)
        assert size == 0.05
        assert reason == "DRAWDOWN_DEFENSE_HALF_SIZE"

        # Regime hysteresis penalty
        size, reason = calculate_drawdown_controlled_sizing(0.10, regime_hysteresis_penalty=True)
        assert size == 0.05
        assert reason == "REGIME_CONFLICT_HALF_SIZE"

        # Standard Half-Kelly capped at 15%
        size, reason = calculate_drawdown_controlled_sizing(0.20)
        assert size == 0.15
        assert reason == "STANDARD_HALF_KELLY"

    def test_check_adv20_liquidity_absorption(self):
        # ADV20 zero or negative
        passed, val, reason = check_adv20_liquidity_absorption(100_000_000, 0)
        assert passed is False
        assert reason == "ADV20_ZERO_OR_NEGATIVE"

        # Order exceeds 10% ADV20
        passed, allowed, reason = check_adv20_liquidity_absorption(
            order_val_vnd=150_000_000, adv20_vnd=1_000_000_000, max_absorption_pct=0.10
        )
        assert passed is False
        assert allowed == 100_000_000
        assert reason == "EXCEEDS_MAX_ADV20_ABSORPTION"

        # Order within limit
        passed, allowed, reason = check_adv20_liquidity_absorption(order_val_vnd=80_000_000, adv20_vnd=1_000_000_000)
        assert passed is True
        assert allowed == 80_000_000

    def test_check_sector_concentration_limits(self):
        # Invalid symbol
        passed, reason = check_sector_concentration("", [])
        assert not passed

        # Empty portfolio -> OK
        passed, reason = check_sector_concentration("HPG", [])
        assert passed is True

        sector_map = {"HPG": "Thép", "HSG": "Thép", "NKG": "Thép", "TLH": "Thép"}
        current_portfolio = [{"symbol": "HPG"}, {"symbol": "HSG"}, {"symbol": "NKG"}]
        # 3 already in Thép -> 4th blocked
        passed, reason = check_sector_concentration("TLH", current_portfolio, sector_map=sector_map)
        assert passed is False
        assert "Sector Gate Blocked" in reason

    def test_optimize_portfolio_risk_parity(self):
        vols = {"A": 0.20, "B": 0.40, "C": 0.10}
        weights = optimize_portfolio_risk_parity(vols, max_weight=0.50)
        assert len(weights) == 3
        # Lower volatility stock C should have the highest weight
        assert weights["C"] > weights["A"] > weights["B"]
        assert round(sum(weights.values()), 2) == 1.0

    def test_evaluate_partial_profit_lock(self):
        # Invalid entry
        res_inv = evaluate_partial_profit_lock(0.0, 10.0, 10.0)
        assert res_inv["status"] == "INVALID_ENTRY_PRICE"

        # Target reached (+15% gain on 100 entry)
        res_tp = evaluate_partial_profit_lock(entry_price=100.0, current_high=115.0, current_price=112.0)
        assert res_tp["partial_take_profit"] is True
        assert res_tp["lock_fraction"] == 0.50
        assert res_tp["new_stop_price"] == 100.0

        # Target not yet reached
        res_trail = evaluate_partial_profit_lock(entry_price=100.0, current_high=108.0, current_price=106.0)
        assert res_trail["partial_take_profit"] is False
        assert res_trail["status"] == "TRAIL_IN_PROGRESS"
