# -*- coding: utf-8 -*-
"""Unit tests for TASK-0009: Phase 3 Walk-Forward Optimization, Crisis Stress Matrix, and Bootstrap Sharpe CI."""

import numpy as np
import pandas as pd
import pytest

from backtest_engine import (
    KEY_MARKET_DROP,
    KEY_NO_DATA,
    KEY_STATUS,
    RegimeBacktestEngine,
    _slice_by_dates,
    run_crisis_stress_matrix,
    run_walk_forward_backtest,
)
from quant_engine import bootstrap_sharpe_ci


class TestPhase3cBootstrapSharpeCI:
    """Test suite for Phase 3c: Bootstrap Sharpe Confidence Interval."""

    def test_bootstrap_sharpe_empty_or_insufficient_data(self):
        """None, empty list, or single element returns fallback without raising error."""
        res_none = bootstrap_sharpe_ci(None)
        assert res_none["sharpe_point"] == 0.0
        assert res_none["is_statistically_significant"] is False
        assert "warning" in res_none

        res_empty = bootstrap_sharpe_ci([])
        assert res_empty["n_samples"] == 0
        assert res_empty["is_statistically_significant"] is False

        res_single = bootstrap_sharpe_ci([0.05])
        assert res_single["n_samples"] == 1
        assert res_single["is_statistically_significant"] is False

    def test_bootstrap_sharpe_all_nan_or_zero_volatility(self):
        """Array of NaNs or constant identical numbers handled gracefully."""
        res_nan = bootstrap_sharpe_ci([float("nan"), float("nan")])
        assert res_nan["n_samples"] == 0
        assert res_nan["is_statistically_significant"] is False

        res_const = bootstrap_sharpe_ci([0.01, 0.01, 0.01, 0.01])
        assert res_const["is_statistically_significant"] is False

    def test_bootstrap_sharpe_positive_edge_significant(self):
        """Strong positive return series should yield ci_lower > 0 and significance True."""
        rng = np.random.default_rng(123)
        # 100 observations with mean daily return +0.3% and std 0.5% (approx Sharpe > 3.0)
        returns = rng.normal(loc=0.003, scale=0.005, size=100)

        res = bootstrap_sharpe_ci(returns, n_bootstrap=2_000, random_state=42)

        assert res["sharpe_point"] > 1.0
        assert res["ci_lower"] > 0.0
        assert res["ci_upper"] > res["ci_lower"]
        assert res["is_statistically_significant"] is True
        assert res["p_value_zero"] < 0.05
        assert res["n_samples"] == 100

    def test_bootstrap_sharpe_noise_not_significant(self):
        """Pure noise return series with mean 0 should cross 0 and fail significance."""
        rng = np.random.default_rng(456)
        noise_returns = rng.normal(loc=0.0, scale=0.01, size=50)

        res = bootstrap_sharpe_ci(noise_returns, n_bootstrap=2_000, random_state=42)

        assert res["ci_lower"] <= 0.0
        assert res["is_statistically_significant"] is False
        assert "chứa giá trị <= 0" in res["warning"]

    def test_bootstrap_sharpe_effective_n_with_autocorrelation(self):
        """Positively autocorrelated returns should reduce effective sample size (ESS)."""
        # Create an AR(1) series with high positive correlation
        rng = np.random.default_rng(789)
        ar_returns = [0.01]
        for _ in range(50):
            ar_returns.append(0.8 * ar_returns[-1] + rng.normal(0, 0.005))

        res = bootstrap_sharpe_ci(ar_returns, n_bootstrap=1_000, random_state=42)
        assert res["effective_n"] < len(ar_returns)


class TestPhase3aWalkForwardBacktest:
    """Test suite for Phase 3a: Walk-Forward Optimization Framework."""

    @pytest.fixture
    def multi_year_data(self):
        """Generate synthetic daily price & signal series from 2018 through 2024."""
        dates = pd.date_range(start="2018-01-02", end="2024-12-31", freq="B")
        n = len(dates)
        rng = np.random.default_rng(42)

        # Geometric Brownian Motion with drift
        returns = rng.normal(loc=0.0003, scale=0.015, size=n)
        prices = 50.0 * np.exp(np.cumsum(returns))

        df_price = pd.DataFrame({
            "open": prices * 0.995,
            "high": prices * 1.01,
            "low": prices * 0.99,
            "close": prices,
            "volume": 500_000,
        }, index=dates)

        # Alternating buy and sell signals every 20 days
        signals = pd.Series(0, index=dates)
        for i in range(10, n, 30):
            signals.iloc[i] = 1
        for i in range(25, n, 30):
            signals.iloc[i] = -1

        return df_price, signals

    def test_walk_forward_backtest_three_windows(self, multi_year_data):
        """Execute walk-forward across training, validation, and OOS periods."""
        df_price, signals = multi_year_data
        engine = RegimeBacktestEngine(initial_capital=100_000_000.0)

        wf_res = run_walk_forward_backtest(engine, df_price, signals)

        assert "results_by_window" in wf_res
        assert "metrics_comparison" in wf_res

        comp = wf_res["metrics_comparison"]
        for win_key in ["training", "validation", "oos"]:
            assert win_key in comp
            assert "total_trades" in comp[win_key]
            assert "win_rate_pct" in comp[win_key]
            assert "sharpe_ratio" in comp[win_key]
            assert "cagr_pct" in comp[win_key]

        # Verify each window has independent BacktestResult
        for win_key in ["training", "validation", "oos"]:
            res = wf_res["results_by_window"][win_key]
            assert not res.equity_curve.empty

    def test_walk_forward_missing_window_reports_no_data(self):
        """When data doesn't span a window, that window returns NO_DATA status."""
        dates = pd.date_range(start="2023-01-01", end="2024-12-31", freq="B")
        df_price = pd.DataFrame({"close": 100.0, "open": 100.0}, index=dates)
        signals = pd.Series(0, index=dates)

        engine = RegimeBacktestEngine()
        wf_res = run_walk_forward_backtest(engine, df_price, signals)

        comp = wf_res["metrics_comparison"]
        assert comp["training"][KEY_STATUS] == KEY_NO_DATA
        assert comp["validation"][KEY_STATUS] == KEY_NO_DATA


class TestPhase3bCrisisStressMatrix:
    """Test suite for Phase 3b: Crisis Stress Backtest Matrix."""

    def test_crisis_stress_matrix_all_four_scenarios(self):
        """Stress matrix covers 2018 Trade War, 2020 COVID, 2022 Bond Crash, and 2021 Bull."""
        dates = pd.date_range(start="2018-01-01", end="2024-12-31", freq="B")
        df_price = pd.DataFrame({
            "close": np.linspace(20.0, 80.0, len(dates)),
            "open": np.linspace(20.0, 80.0, len(dates)),
        }, index=dates)
        signals = pd.Series(0, index=dates)
        # Inject signals in each stress period
        signals.iloc[100] = 1
        signals.iloc[115] = -1

        engine = RegimeBacktestEngine()
        res = run_crisis_stress_matrix(engine, df_price, signals)

        assert "period_results" in res
        assert "stress_summary" in res

        summary = res["stress_summary"]
        expected_keys = [
            "trade_war_2018",
            "trump_tariff_2019",
            "covid_crash_2020",
            "covid_lockdown_2021",
            "bull_market_2021",
            "bond_crackdown_2022",
            "rate_hike_2022",
            "van_thinh_phat_2022",
            "fx_bill_tightening_2023",
            "fx_dxy_pressure_2024",
            "liquidity_dry_2024",
        ]
        for key in expected_keys:
            assert key in summary
            assert KEY_MARKET_DROP in summary[key]
            assert "name" in summary[key]

    def test_slice_by_dates_utility(self):
        """_slice_by_dates correctly handles DatetimeIndex, string bounds, and None series."""
        dates = pd.date_range(start="2020-01-01", end="2020-05-31", freq="D")
        df = pd.DataFrame({"close": np.arange(len(dates))}, index=dates)
        sig = pd.Series(1, index=dates)

        sub_df, sub_sig, sub_reg, sub_adv, sub_bm = _slice_by_dates(
            df, "2020-02-01", "2020-02-28", sig, None, None, None
        )

        assert len(sub_df) == 28
        assert len(sub_sig) == 28
        assert sub_reg is None
        assert sub_adv is None
        assert sub_bm is None

    def test_scan_market_stress_events(self):
        """scan_market_stress_events detects 50pt drops, 4% drops, and sharp drawdowns."""
        from backtest_engine import HISTORICAL_FLASH_CRASH_DATES, scan_market_stress_events

        # 1. Verify historical dates list is non-empty and well formatted
        assert len(HISTORICAL_FLASH_CRASH_DATES) >= 9
        assert "2021-01-28" in HISTORICAL_FLASH_CRASH_DATES
        assert "2022-04-25" in HISTORICAL_FLASH_CRASH_DATES

        # 2. Empty df returns safe fallback
        empty_res = scan_market_stress_events(pd.DataFrame())
        assert empty_res["total_stress_days"] == 0

        # 3. Synthetic benchmark with an injected flash crash
        dates = pd.date_range(start="2023-08-01", end="2023-08-31", freq="B")
        prices = [1240.0] * len(dates)
        # Inject -55 point drop on 2023-08-18 (approx -4.4%)
        idx_18 = dates.get_loc("2023-08-18")
        prices[idx_18] = 1185.0
        for k in range(idx_18 + 1, len(prices)):
            prices[k] = 1180.0

        df_bm = pd.DataFrame({"close": prices}, index=dates)
        stress_res = scan_market_stress_events(df_bm, point_drop_threshold=50.0, pct_drop_threshold=0.04)

        assert len(stress_res["drop_50pts_days"]) >= 1
        assert stress_res["drop_50pts_days"][0]["date"] == "2023-08-18"
        assert stress_res["drop_50pts_days"][0]["drop_points"] == -55.0

        assert len(stress_res["drop_4pct_days"]) >= 1
        assert stress_res["drop_4pct_days"][0]["date"] == "2023-08-18"
        assert stress_res["total_stress_days"] >= 1

