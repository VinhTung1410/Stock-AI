# -*- coding: utf-8 -*-
"""Unit tests for TASK-0010: Phase 4 AI Validation, A/B Testing Arms, and AI Confidence Calibration."""

from quant_engine import (
    ARM_QUANT_AI,
    ARM_QUANT_ONLY,
    check_ai_calibration,
    compare_quant_vs_ai_arms,
)


class TestPhase4bAIConfidenceCalibration:
    """Test suite for Phase 4b: AI Confidence Calibration."""

    def test_check_ai_calibration_empty_and_invalid(self):
        """Empty list, None, or invalid items returns safe uncalibrated fallback."""
        res_none = check_ai_calibration(None)
        assert res_none["is_calibrated"] is False
        assert res_none["allow_kelly_sizing"] is False
        assert "warning" in res_none

        res_empty = check_ai_calibration([])
        assert res_empty["is_calibrated"] is False
        assert res_empty["total_evaluated_trades"] == 0

        res_invalid = check_ai_calibration(["not-a-dict", 123])
        assert res_invalid["total_evaluated_trades"] == 0

    def test_check_ai_calibration_insufficient_samples(self):
        """Fewer samples than min_observations_per_bucket triggers warning and disables Kelly."""
        trades = [
            {"ai_confidence": 75, "pnl_pct": 5.0},
            {"ai_confidence": 78, "pnl_pct": 3.0},
        ]
        res = check_ai_calibration(trades, min_observations_per_bucket=3)
        assert res["is_calibrated"] is False
        assert res["allow_kelly_sizing"] is False
        assert "Chưa có bucket nào đủ tối thiểu" in res["warning"]

    def test_check_ai_calibration_well_calibrated(self):
        """Well calibrated confidence matching actual win rate enables Kelly sizing."""
        trades = []
        # Bucket 70-80 (claimed 75%): 7 wins, 3 losses -> actual 70% (gap 0.05 <= 0.15)
        for _ in range(7):
            trades.append({"ai_confidence": 75, "pnl_pct": 4.0})
        for _ in range(3):
            trades.append({"ai_confidence": 75, "pnl_pct": -2.0})

        # Bucket 60-70 (claimed 65%): 6 wins, 4 losses -> actual 60% (gap 0.05 <= 0.15)
        for _ in range(6):
            trades.append({"ai_confidence": 65, "pnl_pct": 3.0})
        for _ in range(4):
            trades.append({"ai_confidence": 65, "pnl_pct": -2.5})

        res = check_ai_calibration(trades, min_observations_per_bucket=5)
        assert res["is_calibrated"] is True
        assert res["allow_kelly_sizing"] is True
        assert res["warning"] == ""
        assert res["brier_score"] is not None
        assert res["brier_score"] < 0.25

        b70 = res["buckets"]["70-80"]
        assert b70["n"] == 10
        assert b70["actual_win_rate"] == 0.7
        assert b70["calibration_gap"] == 0.05
        assert b70["is_calibrated"] is True

    def test_check_ai_calibration_overconfident_uncalibrated(self):
        """When AI claims 75-80% but actual win rate is only 30%, Kelly is blocked."""
        trades = []
        # Bucket 70-80: 3 wins, 7 losses -> actual 30% (gap 0.45 > 0.15)
        for _ in range(3):
            trades.append({"ai_confidence": 78, "pnl_pct": 5.0})
        for _ in range(7):
            trades.append({"ai_confidence": 78, "pnl_pct": -4.0})

        res = check_ai_calibration(trades, min_observations_per_bucket=5)
        assert res["is_calibrated"] is False
        assert res["allow_kelly_sizing"] is False
        assert "CẤM đưa ai_confidence vào công thức Half-Kelly" in res["warning"]

        b70 = res["buckets"]["70-80"]
        assert b70["actual_win_rate"] == 0.3
        assert b70["calibration_gap"] == 0.45
        assert b70["is_calibrated"] is False


class TestPhase4aABArmsComparison:
    """Test suite for Phase 4a: A/B Testing Arms (Quant-Only vs Quant+AI)."""

    def test_arm_constants(self):
        """Verify arm constant string definitions."""
        assert ARM_QUANT_ONLY == "QUANT_ONLY"
        assert ARM_QUANT_AI == "QUANT_AI"

    def test_compare_quant_vs_ai_arms_positive_alpha(self):
        """When AI filtering improves Sharpe and expectancy, verdict is POSITIVE_AI_ALPHA."""
        trades_a = [
            {"pnl_pct": 5.0}, {"pnl_pct": -3.0}, {"pnl_pct": 2.0}, {"pnl_pct": -4.0},
            {"pnl_pct": 3.0}, {"pnl_pct": -2.0}, {"pnl_pct": 1.0}, {"pnl_pct": -3.0},
        ]
        # AI filters out 3 losing trades, improving hit rate and expectancy
        trades_b = [
            {"pnl_pct": 5.0}, {"pnl_pct": 2.0}, {"pnl_pct": -4.0},
            {"pnl_pct": 3.0}, {"pnl_pct": 1.0},
        ]

        res = compare_quant_vs_ai_arms(
            trades_a, trades_b, cagr_a=8.0, cagr_b=15.0, sharpe_a=0.7, sharpe_b=1.2
        )

        assert res["incremental_sharpe"] == 0.5
        assert res["incremental_expectancy"] > 0.0
        assert res["ai_verdict"] == "POSITIVE_AI_ALPHA"
        assert "Giữ AI trong quy trình" in res["recommendation"]

    def test_compare_quant_vs_ai_arms_neutral_reporting(self):
        """When Sharpe delta is within 0.10, verdict is NEUTRAL_REPORTING_ONLY."""
        trades_a = [{"pnl_pct": 3.0}, {"pnl_pct": -2.0}, {"pnl_pct": 4.0}]
        trades_b = [{"pnl_pct": 3.0}, {"pnl_pct": -2.0}, {"pnl_pct": 4.0}]

        res = compare_quant_vs_ai_arms(
            trades_a, trades_b, cagr_a=10.0, cagr_b=10.5, sharpe_a=1.0, sharpe_b=1.05
        )

        assert abs(res["incremental_sharpe"]) <= 0.10
        assert res["ai_verdict"] == "NEUTRAL_REPORTING_ONLY"
        assert "tầng phân tích giải thích" in res["recommendation"]

    def test_compare_quant_vs_ai_arms_negative_drag(self):
        """When AI filtering causes underperformance, verdict is NEGATIVE_AI_DRAG."""
        trades_a = [
            {"pnl_pct": 10.0}, {"pnl_pct": 8.0}, {"pnl_pct": 6.0}, {"pnl_pct": -2.0}
        ]
        # AI falsely pruned the biggest winning trades
        trades_b = [
            {"pnl_pct": -2.0}, {"pnl_pct": 1.0}, {"pnl_pct": -1.0}
        ]

        res = compare_quant_vs_ai_arms(
            trades_a, trades_b, cagr_a=20.0, cagr_b=2.0, sharpe_a=1.6, sharpe_b=0.4
        )

        assert res["incremental_sharpe"] < -0.10
        assert res["ai_verdict"] == "NEGATIVE_AI_DRAG"
        assert "AI làm suy giảm hiệu năng" in res["recommendation"]
