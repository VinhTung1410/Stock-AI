"""Unit tests for TASK-0012: Phase 6 Stress Test Overhaul, Stationary Block Bootstrap & Risk Governance."""

import pandas as pd

from quant_engine import (
    VERDICT_COSTLY_PROTECTION,
    VERDICT_FAIR_TRADE,
    VERDICT_FREE_PROTECTION,
    VERDICT_HIGH_EFFICIENCY,
    calculate_sector_gate_insurance_roi,
    simulate_monte_carlo_drawdown,
)
from quant_valuation import (
    INSTITUTIONAL_CONSENSUS_TARGETS,
    check_institutional_target_freshness,
)
from tabs.tab_alpha_tracker import _build_crisis_stress_table, _render_crisis_bar_chart


class TestPhase6aBlockBootstrap:
    """Test suite for Phase 6a: Stationary Block Bootstrap Drawdown Simulation."""

    def test_simulate_monte_carlo_drawdown_empty_and_fallback(self):
        """Empty or invalid inputs safely return standard fallback dictionary."""
        res_empty = simulate_monte_carlo_drawdown([])
        assert res_empty["n_simulations"] == 0
        assert res_empty["median_drawdown_pct"] == 0.0
        assert res_empty["block_size"] == 1

        res_none = simulate_monte_carlo_drawdown(None)
        assert res_none["n_simulations"] == 0
        assert res_none["n_trades"] == 0

        res_nans = simulate_monte_carlo_drawdown([float("nan"), float("nan")])
        assert res_nans["n_simulations"] == 0

    def test_simulate_monte_carlo_drawdown_auto_block_size(self):
        """Auto block size chooses max(3, round(n^(1/3))) when block_size is None."""
        # N = 27 trades -> 27^(1/3) = 3.0 -> block_size = 3
        trades_27 = [2.0, -1.5, 3.0, -2.0] * 7  # 28 trades
        res = simulate_monte_carlo_drawdown(trades_27, n_simulations=500, random_state=42)

        assert res["n_simulations"] == 500
        assert res["n_trades"] == 28
        assert res["block_size"] == 3
        assert res["p99_drawdown_pct"] <= res["p95_drawdown_pct"] <= res["median_drawdown_pct"]
        assert 0.0 <= res["prob_drawdown_over_15pct"] <= 1.0

    def test_simulate_monte_carlo_drawdown_explicit_block_size_and_iid(self):
        """When block_size=1, simulation falls back to I.I.D. resampling."""
        trades = [5.0, -3.0, 7.0, -4.0, 2.0, -6.0, 4.0, -2.0, 8.0, -5.0]
        res_iid = simulate_monte_carlo_drawdown(trades, n_simulations=500, block_size=1, random_state=42)
        assert res_iid["block_size"] == 1
        assert res_iid["median_drawdown_pct"] <= 0.0

        res_b5 = simulate_monte_carlo_drawdown(trades, n_simulations=500, block_size=5, random_state=42)
        assert res_b5["block_size"] == 5
        assert res_b5["p99_drawdown_pct"] <= res_b5["p95_drawdown_pct"]

    def test_simulate_monte_carlo_drawdown_small_sample_edge(self):
        """Small samples (N < 3) safely clamp block_size to 1."""
        trades_2 = [3.0, -4.0]
        res = simulate_monte_carlo_drawdown(trades_2, n_simulations=100, block_size=None, random_state=42)
        assert res["block_size"] == 1
        assert res["n_trades"] == 2


class TestPhase6dSectorGateInsuranceRoi:
    """Test suite for Phase 6d: Sector Gate Insurance ROI & Risk Attribution."""

    def test_calculate_sector_gate_insurance_roi_high_efficiency(self):
        """When MDD reduction is >= 2x CAGR sacrifice, verdict is HIGH_EFFICIENCY_INSURANCE."""
        # Upside Cost: 22 - 18 = 4%. Protection Benefit: 35 - 15 = 20%. ROI = 20 / 4 = 5.0
        res = calculate_sector_gate_insurance_roi(
            cagr_without_gate=22.0,
            cagr_with_gate=18.0,
            mdd_without_gate=-35.0,
            mdd_with_gate=-15.0,
        )
        assert res["upside_cost_pct"] == 4.0
        assert res["protection_benefit_pct"] == 20.0
        assert res["insurance_roi"] == 5.0
        assert res["verdict"] == VERDICT_HIGH_EFFICIENCY

    def test_calculate_sector_gate_insurance_roi_fair_trade(self):
        """When MDD reduction is 1x to 2x CAGR sacrifice, verdict is FAIR_RISK_TRADE."""
        # Upside Cost: 20 - 16 = 4%. Protection Benefit: 25 - 20 = 5%. ROI = 5 / 4 = 1.25
        res = calculate_sector_gate_insurance_roi(
            cagr_without_gate=20.0,
            cagr_with_gate=16.0,
            mdd_without_gate=-25.0,
            mdd_with_gate=-20.0,
        )
        assert res["insurance_roi"] == 1.25
        assert res["verdict"] == VERDICT_FAIR_TRADE

    def test_calculate_sector_gate_insurance_roi_costly_protection(self):
        """When MDD reduction is less than CAGR sacrifice, verdict is COSTLY_PROTECTION."""
        # Upside Cost: 25 - 15 = 10%. Protection Benefit: 30 - 25 = 5%. ROI = 0.50
        res = calculate_sector_gate_insurance_roi(
            cagr_without_gate=25.0,
            cagr_with_gate=15.0,
            mdd_without_gate=-30.0,
            mdd_with_gate=-25.0,
        )
        assert res["insurance_roi"] == 0.5
        assert res["verdict"] == VERDICT_COSTLY_PROTECTION

    def test_calculate_sector_gate_insurance_roi_free_protection(self):
        """When CAGR with gate is >= CAGR without gate, protection is essentially free."""
        res = calculate_sector_gate_insurance_roi(
            cagr_without_gate=18.0,
            cagr_with_gate=19.5,
            mdd_without_gate=-30.0,
            mdd_with_gate=-12.0,
        )
        assert res["upside_cost_pct"] == 0.0
        assert res["protection_benefit_pct"] == 18.0
        assert res["insurance_roi"] == 999.0
        assert res["verdict"] == VERDICT_FREE_PROTECTION


class TestPhase6eTargetFreshnessValidator:
    """Test suite for Phase 6e: Valuation Target Freshness Governance."""

    def test_all_consensus_targets_have_last_updated(self):
        """All institutional targets must have a valid last_updated date string."""
        for sym, data in INSTITUTIONAL_CONSENSUS_TARGETS.items():
            assert "last_updated" in data, f"{sym} missing last_updated"
            # Verify format YYYY-MM-DD
            parts = data["last_updated"].split("-")
            assert len(parts) == 3, f"{sym} invalid date format: {data['last_updated']}"

    def test_check_institutional_target_freshness_fresh(self):
        """Target updated within 180 days is classified as fresh."""
        res = check_institutional_target_freshness(
            symbol="HPG",
            as_of_date="2026-11-01",  # 31 days after 2026-10-01
            max_age_days=180,
        )
        assert res["has_target"] is True
        assert res["is_stale"] is False
        assert res["age_days"] == 31
        assert res["warning"] == "FRESH"

    def test_check_institutional_target_freshness_stale(self):
        """Target older than 180 days triggers stale warning."""
        res = check_institutional_target_freshness(
            symbol="FPT",
            as_of_date="2027-06-01",  # ~243 days after 2026-10-01
            max_age_days=180,
        )
        assert res["has_target"] is True
        assert res["is_stale"] is True
        assert res["age_days"] > 180
        assert "Target outdated" in res["warning"]

    def test_check_institutional_target_freshness_unknown_symbol(self):
        """Unknown ticker returns has_target=False without crashing."""
        res = check_institutional_target_freshness(symbol="NONEXISTENT_999")
        assert res["has_target"] is False
        assert res["is_stale"] is False
        assert res["warning"] == "NO_INSTITUTIONAL_TARGET"


class TestPhase6bUiHelpers:
    """Test suite for Phase 6b: UI Table & Chart helper functions."""

    def test_build_crisis_stress_table_formatting(self):
        """_build_crisis_stress_table formats dictionary into structured DataFrame."""
        summary_mock = {
            "covid": {
                "name": "Bùng phát Covid-19",
                "start_date": "2020-01-23",
                "end_date": "2020-03-31",
                "market_drop_pct": -35.0,
                "strategy_return_pct": -8.5,
                "max_drawdown_pct": 10.2,
                "win_rate_pct": 50.0,
                "total_trades": 6,
            }
        }
        df = _build_crisis_stress_table(summary_mock)
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 1
        assert "VN-Index Giảm (%)" in df.columns
        assert df.iloc[0]["VN-Index Giảm (%)"] == "-35.0%"
        assert df.iloc[0]["Chiến Lược Lãi/Lỗ (%)"] == "-8.50%"

    def test_render_crisis_bar_chart_empty_safe(self):
        """_render_crisis_bar_chart handles empty or None summary cleanly."""
        _render_crisis_bar_chart({})
        _render_crisis_bar_chart(None)
