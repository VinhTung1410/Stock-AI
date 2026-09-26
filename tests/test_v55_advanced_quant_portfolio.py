# -*- coding: utf-8 -*-
"""Unit tests for TASK-0011: Phase 5 Advanced Portfolio Optimization, Monte Carlo Tail Risk, and Partial Profit Lock."""

import numpy as np

from quant_engine import (
    calculate_factor_exposures,
    evaluate_partial_profit_lock,
    optimize_portfolio_risk_parity,
    simulate_monte_carlo_drawdown,
)


class TestPhase5aMonteCarloDrawdown:
    """Test suite for Phase 5a: Monte Carlo Drawdown & Tail Risk Simulation."""

    def test_monte_carlo_empty_or_invalid(self):
        """Empty list or non-numeric list returns clean fallback."""
        res_empty = simulate_monte_carlo_drawdown([])
        assert res_empty["n_simulations"] == 0
        assert res_empty["median_drawdown_pct"] == 0.0

        res_none = simulate_monte_carlo_drawdown(None)
        assert res_none["n_simulations"] == 0

    def test_monte_carlo_distribution(self):
        """Simulation produces valid P99 <= P95 <= Median ordering and probabilities."""
        rng = np.random.default_rng(123)
        # 25 trade returns with mixed positive and negative values
        trades = list(rng.normal(loc=1.5, scale=5.0, size=25))

        res = simulate_monte_carlo_drawdown(trades, n_simulations=1_000, random_state=42)

        assert res["n_simulations"] == 1_000
        assert res["n_trades"] == 25
        assert res["p99_drawdown_pct"] <= res["p95_drawdown_pct"]
        assert res["p95_drawdown_pct"] <= res["median_drawdown_pct"]
        assert 0.0 <= res["prob_drawdown_over_15pct"] <= 1.0
        assert res["max_consecutive_losses"] >= 0


class TestPhase5bRiskParitySizing:
    """Test suite for Phase 5b: Risk Parity / Equal Risk Contribution Sizing."""

    def test_risk_parity_empty(self):
        """Empty input dict returns empty dict."""
        assert optimize_portfolio_risk_parity({}) == {}

    def test_risk_parity_inverse_proportionality(self):
        """Low volatility assets receive higher weights than high volatility assets."""
        vols = {"VCB": 1.0, "HPG": 2.0, "NVL": 4.0}
        weights = optimize_portfolio_risk_parity(vols, max_weight=0.60)

        assert weights["VCB"] > weights["HPG"]
        assert weights["HPG"] > weights["NVL"]
        assert abs(sum(weights.values()) - 1.0) < 0.005

    def test_risk_parity_max_weight_capping(self):
        """No asset exceeds max_weight (25%) when enough assets are present."""
        vols = {
            "VCB": 0.5,  # Very low volatility, would dominate if uncapped
            "HPG": 2.5,
            "NVL": 4.0,
            "DIG": 5.0,
            "PDR": 5.5,
        }
        weights = optimize_portfolio_risk_parity(vols, max_weight=0.25)

        assert weights["VCB"] <= 0.2501
        assert abs(sum(weights.values()) - 1.0) < 0.005
        for sym, w in weights.items():
            assert w <= 0.2501


class TestPhase5cFactorExposures:
    """Test suite for Phase 5c: Multi-Factor Beta Decomposition."""

    def test_factor_exposures_empty_or_short(self):
        """Insufficient data returns safe fallback metrics."""
        res = calculate_factor_exposures([0.01, 0.02], [0.01, 0.02])
        assert res["market_beta"] == 1.0
        assert res["market_r2"] == 0.0

    def test_factor_exposures_market_and_sector(self):
        """Calculates market beta, market R2, and sector beta correctly."""
        rng = np.random.default_rng(42)
        n = 100
        market = rng.normal(0.0005, 0.01, size=n)
        sector = 0.8 * market + rng.normal(0, 0.005, size=n)
        # Asset has high beta ~1.5 to market plus idiosyncratic noise
        asset = 1.5 * market + rng.normal(0, 0.004, size=n)

        res = calculate_factor_exposures(asset, market, sector)

        assert abs(res["market_beta"] - 1.5) < 0.25
        assert res["market_r2"] > 0.5
        assert res["sector_beta"] is not None
        assert "idiosyncratic_alpha_pct" in res


class TestPhase5dPartialProfitLock:
    """Test suite for Phase 5d: Partial Profit Taking & Breakeven Stop."""

    def test_partial_profit_lock_not_triggered(self):
        """When gain is below target_profit_pct (12%), partial take profit is False."""
        res = evaluate_partial_profit_lock(entry_price=20.0, current_high=21.5, current_price=21.0, target_profit_pct=12.0)
        assert res["partial_take_profit"] is False
        assert res["lock_fraction"] == 0.0
        assert res["new_stop_price"] is None
        assert res["status"] == "TRAIL_IN_PROGRESS"

    def test_partial_profit_lock_triggered(self):
        """When gain reaches or exceeds 12%, lock 50% profit and move stop to break-even."""
        res = evaluate_partial_profit_lock(entry_price=20.0, current_high=23.0, current_price=22.4, target_profit_pct=12.0)
        assert res["partial_take_profit"] is True
        assert res["lock_fraction"] == 0.50
        assert res["new_stop_price"] == 20.0
        assert res["status"] == "TARGET_1_REACHED_BREAKEVEN_LOCKED"

    def test_partial_profit_lock_invalid_entry(self):
        """Invalid entry price returns safe fallback."""
        res = evaluate_partial_profit_lock(entry_price=0.0, current_high=23.0, current_price=22.0)
        assert res["partial_take_profit"] is False
        assert res["status"] == "INVALID_ENTRY_PRICE"
