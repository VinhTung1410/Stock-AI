"""Unit tests for TASK-0016: Exit Hypothesis Lab & Conviction Weights Statistical Validation (Phase 7d & 7e).

Criteria covered:
- AC-7d.1: Exit Simulator 4 Policies (A, B, C, D) on OHLC paths.
- AC-7d.2: Paired Bootstrap R-Expectancy comparison against Baseline A.
- AC-7d.3: Report-Only safety disclaimer enforcement.
- AC-7e.1: Pillar Spearman IC with informative MoS filtering.
- AC-7e.2: Benjamini–Hochberg FDR control and N < 100 sample warning.
"""

from __future__ import annotations

import pandas as pd
import pytest

from backtest_engine import (
    EXIT_LAB_REPORT_DISCLAIMER,
    POLICY_A,
    POLICY_B,
    POLICY_C,
    POLICY_D,
    run_exit_hypothesis_lab,
    simulate_exit_policy,
)
from quant_engine import (
    apply_benjamini_hochberg_fdr,
    calculate_pillar_spearman_ic,
)


class TestExitPolicySimulators:
    """AC-7d.1: Test individual execution logic of 4 exit policies on deterministic OHLC paths."""

    @pytest.fixture
    def trending_ohlc(self) -> pd.DataFrame:
        """Create a 10-bar deterministic bullish OHLC path starting from 100 to 130."""
        dates = pd.date_range("2026-01-01", periods=10, freq="B")
        data = [
            {"open": 100.0, "high": 105.0, "low": 98.0, "close": 104.0, "atr14": 3.0},   # Bar 1: +5%
            {"open": 104.0, "high": 109.0, "low": 102.0, "close": 108.0, "atr14": 3.0},  # Bar 2: +9%
            {"open": 108.0, "high": 113.0, "low": 107.0, "close": 112.5, "atr14": 3.0},  # Bar 3: +13% (Triggers Policy A & B)
            {"open": 112.5, "high": 118.0, "low": 111.0, "close": 116.0, "atr14": 3.0},  # Bar 4: +18%
            {"open": 116.0, "high": 122.0, "low": 115.0, "close": 121.0, "atr14": 3.0},  # Bar 5: +22% (Target 120 hit)
            {"open": 121.0, "high": 125.0, "low": 119.0, "close": 124.0, "atr14": 3.0},  # Bar 6
            {"open": 124.0, "high": 128.0, "low": 122.0, "close": 127.0, "atr14": 3.0},  # Bar 7
            {"open": 127.0, "high": 130.0, "low": 125.0, "close": 129.0, "atr14": 3.0},  # Bar 8
            {"open": 129.0, "high": 131.0, "low": 128.0, "close": 130.0, "atr14": 3.0},  # Bar 9
            {"open": 130.0, "high": 132.0, "low": 129.0, "close": 131.0, "atr14": 3.0},  # Bar 10
        ]
        return pd.DataFrame(data, index=dates)

    def test_policy_a_partial_profit_and_target_hit(self, trending_ohlc):
        """Policy A: reaches +12% at bar 3 (locks 50%), then reaches target 120 at bar 5."""
        res = simulate_exit_policy(
            entry_price=100.0,
            initial_stop=93.0,
            target_price=120.0,
            ohlc_df=trending_ohlc,
            policy="A",
        )
        assert res["policy"] == POLICY_A
        assert res["exit_reason"] == "TARGET_HIT"
        # 50% at 112 (+12%) and 50% at 120 (+20%) -> 6% + 10% = 16% total pnl
        assert res["pnl_pct"] == pytest.approx(16.0, rel=1e-2)
        assert res["r_multiple"] > 2.0
        assert res["holding_bars"] == 5

    def test_policy_a_breakeven_stop_after_partial(self):
        """Policy A: locks 50% at +12%, but then price reverses to breakeven."""
        data = [
            {"open": 100.0, "high": 105.0, "low": 99.0, "close": 104.0, "atr14": 2.0},
            {"open": 104.0, "high": 113.0, "low": 103.0, "close": 112.5, "atr14": 2.0},  # Hits +12%, SL -> 100.3
            {"open": 112.5, "high": 113.0, "low": 99.5, "close": 100.0, "atr14": 2.0},   # Dips below 100.3
        ]
        df = pd.DataFrame(data)
        res = simulate_exit_policy(100.0, 93.0, 125.0, df, policy="A")
        assert res["exit_reason"] == "BREAKEVEN_STOP"
        assert res["pnl_pct"] > 5.0  # 50% * 12% + 50% * 0.3% = 6.15%

    def test_policy_b_r_multiple_exit(self, trending_ohlc):
        """Policy B: R = 100 - 95 = 5. Target 2R = 110 (bar 3 hits 113). New SL = 102.5."""
        res = simulate_exit_policy(
            entry_price=100.0,
            initial_stop=95.0,  # R = 5
            target_price=120.0,
            ohlc_df=trending_ohlc,
            policy="B",
        )
        assert res["policy"] == POLICY_B
        assert res["exit_reason"] == "TARGET_HIT"
        assert res["r_multiple"] > 0

    def test_policy_c_atr_trailing_exit(self):
        """Policy C: Trailing stop = Highest High - 2.5 * ATR(14)."""
        data = [
            {"open": 100.0, "high": 110.0, "low": 99.0, "close": 108.0, "atr14": 2.0},  # HH=110, trail=105
            {"open": 108.0, "high": 115.0, "low": 107.0, "close": 114.0, "atr14": 2.0}, # HH=115, trail=110
            {"open": 114.0, "high": 114.5, "low": 109.0, "close": 110.0, "atr14": 2.0}, # Low=109 < 110 -> Trailing Stop!
        ]
        df = pd.DataFrame(data)
        res = simulate_exit_policy(100.0, 93.0, 130.0, df, policy="C", atr_multiplier=2.5)
        assert res["policy"] == POLICY_C
        assert res["exit_reason"] == "TRAILING_STOP"
        assert res["holding_bars"] == 3
        assert res["pnl_pct"] == pytest.approx(10.0, rel=1e-2)

    def test_policy_d_all_or_nothing(self, trending_ohlc):
        """Policy D: 100% position kept until Target 120 (bar 5)."""
        res = simulate_exit_policy(100.0, 93.0, 120.0, trending_ohlc, policy="D")
        assert res["policy"] == POLICY_D
        assert res["exit_reason"] == "TARGET_HIT"
        # 100% at 120 = +20% PnL
        assert res["pnl_pct"] == pytest.approx(20.0, rel=1e-2)
        assert res["holding_bars"] == 5

    def test_simulate_exit_empty_or_invalid(self):
        res = simulate_exit_policy(0.0, 0.0, 0.0, pd.DataFrame())
        assert res["exit_reason"] == "INVALID_DATA"
        assert res["pnl_pct"] == 0.0


class TestExitHypothesisLab:
    """AC-7d.2 & AC-7d.3: Test Paired Bootstrap & Report-Only disclaimer."""

    def test_run_exit_hypothesis_lab_empty(self):
        res = run_exit_hypothesis_lab([])
        assert res["status"] == "EMPTY_DATA"
        assert res["report_only"] is True
        assert res["disclaimer"] == EXIT_LAB_REPORT_DISCLAIMER

    def test_run_exit_hypothesis_lab_paired_bootstrap(self):
        """Verify lab runs paired bootstrap on simulated trade universe."""
        signals = []
        for i in range(15):
            df = pd.DataFrame([
                {"open": 50.0, "high": 55.0, "low": 48.0, "close": 54.0, "atr14": 1.5},
                {"open": 54.0, "high": 62.0, "low": 53.0, "close": 61.0, "atr14": 1.5},  # +20% gain
                {"open": 61.0, "high": 63.0, "low": 60.0, "close": 62.0, "atr14": 1.5},
            ])
            signals.append({
                "symbol": f"SYM_{i}",
                "entry_price": 50.0,
                "initial_stop": 46.5,
                "target_price": 60.0,
                "ohlc_df": df,
            })

        lab_res = run_exit_hypothesis_lab(signals, n_bootstrap=500, random_state=42)
        assert lab_res["status"] == "SUCCESS"
        assert lab_res["report_only"] is True
        assert lab_res["sample_size"] == 15
        assert POLICY_A in lab_res["policies"]
        assert POLICY_B in lab_res["policies"]
        assert POLICY_C in lab_res["policies"]
        assert POLICY_D in lab_res["policies"]

        # Check paired bootstrap metrics
        pb = lab_res["paired_bootstrap"]
        assert POLICY_B in pb
        assert "delta_expectancy_r" in pb[POLICY_B]
        assert "ci_95" in pb[POLICY_B]
        assert "p_value_superiority" in pb[POLICY_B]
        assert isinstance(pb[POLICY_B]["is_significantly_better"], bool)


class TestPillarSpearmanIC:
    """AC-7e.1: Test Spearman IC and informative MoS filtering."""

    def test_spearman_ic_filters_uninformative_mos(self):
        """Records with mos_is_informative=False must be excluded from s_mos correlation."""
        records = []
        # 10 records with informative MoS (positive correlation)
        for i in range(10):
            records.append({
                "s_mos": float(10 + i * 2),
                "s_fscore": 7,
                "s_ta": 50.0,
                "s_flow": 1.0,
                "alpha_t20": float(2.0 + i * 1.5),
                "mos_is_informative": True,
            })
        # 5 records with uninformative MoS (synthetic fixed 1.18x)
        for i in range(5):
            records.append({
                "s_mos": 15.25,
                "s_fscore": 6,
                "s_ta": 45.0,
                "s_flow": -1.0,
                "alpha_t20": float(-5.0 + i),
                "mos_is_informative": False,
            })

        res = calculate_pillar_spearman_ic(records, min_observations=5)
        assert res["status"] == "SUCCESS"
        assert res["total_records"] == 15
        # Informative ratio should be 10 / 15 = 0.67
        assert res["informative_mos_ratio"] == pytest.approx(0.67, abs=0.02)
        # s_mos evaluated on exactly 10 informative observations
        assert res["pillars"]["s_mos"]["n_obs"] == 10
        assert res["pillars"]["s_mos"]["ic"] > 0.9  # Perfect monotonic order

    def test_spearman_ic_insufficient_observations(self):
        """When n_obs < min_observations, status must be INSUFFICIENT_OBSERVATIONS."""
        records = [{"s_mos": 10.0, "alpha_t20": 2.0, "mos_is_informative": True}]
        res = calculate_pillar_spearman_ic(records, min_observations=30)
        assert res["pillars"]["s_mos"]["status"] == "INSUFFICIENT_OBSERVATIONS"
        assert res["pillars"]["s_mos"]["ic"] == 0.0


class TestBenjaminiHochbergFDR:
    """AC-7e.2: Test Benjamini-Hochberg FDR control and sample size warning."""

    def test_benjamini_hochberg_controls_fdr(self):
        p_values = {
            "s_mos": 0.005,
            "s_fscore": 0.012,
            "s_ta": 0.045,
            "s_flow": 0.250,
        }
        fdr_res = apply_benjamini_hochberg_fdr(p_values, alpha=0.05, total_sample_size=150)
        assert fdr_res["total_hypotheses"] == 4
        assert fdr_res["warning"] == ""  # Sample >= 100, no warning
        assert fdr_res["results"]["s_mos"]["is_significant"] is True
        assert fdr_res["results"]["s_fscore"]["is_significant"] is True
        assert fdr_res["results"]["s_flow"]["is_significant"] is False

    def test_benjamini_hochberg_warns_small_sample(self):
        """When total_sample_size < 100, must emit INSUFFICIENT_SAMPLE warning."""
        p_values = {"s_mos": 0.01, "s_fscore": 0.02}
        fdr_res = apply_benjamini_hochberg_fdr(p_values, alpha=0.05, total_sample_size=45)
        assert "INSUFFICIENT_SAMPLE" in fdr_res["warning"]
        assert "N=45 < 100" in fdr_res["warning"]
