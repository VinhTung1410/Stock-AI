"""Unit tests for Multi-Factor Shadow Graduation & Metric Hardening (TASK-0075 / Phase 25).

Tests Expectancy, Profit Factor, Signal Deduplication, and Anomaly Warnings offline without live API.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from contrarian_engine import _calculate_panic_score_with_breakdown, evaluate_contrarian_gates
from scripts.evaluate_shadow_graduation import (
    _calculate_expectancy_and_pf,
    deduplicate_signal_episodes,
    evaluate_shadow_graduation,
)
from scripts.update_shadow_returns import update_shadow_records_forward_returns


def test_deduplicate_signal_episodes_clusters_consecutive_days():
    """Verify that multiple signals on the same symbol within 5 days are collapsed into 1 episode."""
    raw_records = [
        {"symbol": "PNJ", "created_at": "2026-10-01 09:30:00", "t10_return_pct": 5.0},
        {"symbol": "PNJ", "created_at": "2026-10-02 09:30:00", "t10_return_pct": 4.0},
        {"symbol": "PNJ", "created_at": "2026-10-03 09:30:00", "t10_return_pct": 3.0},
        {"symbol": "PNJ", "created_at": "2026-10-04 09:30:00", "t10_return_pct": 2.0},
        {"symbol": "PNJ", "created_at": "2026-10-15 09:30:00", "t10_return_pct": -1.0},  # New episode (> 5 days)
        {"symbol": "FPT", "created_at": "2026-10-02 09:30:00", "t10_return_pct": 6.0},  # Different symbol
    ]
    episodes = deduplicate_signal_episodes(raw_records, window_days=5)
    # Expected: 2 episodes for PNJ (Oct 1 and Oct 15) + 1 episode for FPT = 3 episodes
    assert len(episodes) == 3
    symbols = [e["symbol"] for e in episodes]
    assert symbols.count("PNJ") == 2
    assert symbols.count("FPT") == 1


def test_expectancy_and_profit_factor_negative_expectancy_case():
    """Client proof: 60% win rate with +1% gain and 40% loss with -3% loss must yield negative expectancy."""
    # 6 trades of +1.0%, 4 trades of -3.0%
    returns = [1.0, 1.0, 1.0, 1.0, 1.0, 1.0, -3.0, -3.0, -3.0, -3.0]
    expectancy, profit_factor, avg_raw, expectancy_r = _calculate_expectancy_and_pf(returns, cost_pct=0.35)

    # Raw expected value: 0.6 * 1.0 - 0.4 * 3.0 = 0.6 - 1.2 = -0.6%
    # Net expectancy after 0.35% cost: -0.6% - 0.35% = -0.95%
    assert expectancy < 0.0
    assert expectancy == pytest.approx(-0.95, abs=0.01)
    assert expectancy_r < 0.0  # R-multiple expectancy must be negative

    # Profit factor: total gains (6.0) / total losses (12.0) = 0.50
    assert profit_factor == pytest.approx(0.5, abs=0.01)
    assert avg_raw == pytest.approx(-0.6, abs=0.01)


def test_graduation_blocks_when_expectancy_is_negative_even_with_high_winrate():
    """Client Requirement: High Win Rate (60%) with negative expectancy must fail graduation."""
    # 30 samples, 60% win rate (+1%), 40% loss (-3%)
    mock_returns = [1.0] * 18 + [-3.0] * 12
    records = [
        {
            "decision_id": f"dec_{i}",
            "symbol": f"SYM_{i}",
            "session": f"2026-08-{i%28 + 1:02d}",
            "created_at": f"2026-08-{i%28 + 1:02d} 10:00:00",
            "t10_return_pct": mock_returns[i],
        }
        for i in range(30)
    ]
    # Add dummy sessions to satisfy >= 60 distinct sessions
    for s in range(65):
        records.append({
            "decision_id": f"dummy_{s}",
            "symbol": "DUMMY",
            "session": f"2026-05-{s:02d}",
            "created_at": f"2026-05-{s:02d} 10:00:00",
            "t10_return_pct": None,
        })

    report = evaluate_shadow_graduation(records=records, cost_pct=0.35)
    assert report["can_graduate"] is False
    assert report["hit_rate_t10"] == 0.60
    assert report["expectancy_t10"] < 0.0
    reasons_str = " ".join(report["reasons"])
    assert "Kỳ vọng toán học Expectancy T+10" in reasons_str
    assert "Profit Factor" in reasons_str


def test_graduation_passes_when_all_multi_factor_criteria_are_met():
    """Successful graduation when distinct sessions >= 60, N_eff >= 30, Hit rate > 55%, E(R) > 0, PF >= 1.2."""
    records = []
    # 35 independent episodes across 65 dates
    for i in range(35):
        # 25 winning trades of +6.0%, 10 losing trades of -2.0%
        ret = 6.0 if i < 25 else -2.0
        records.append({
            "decision_id": f"dec_{i}",
            "symbol": f"STOCK_{i}",
            "session": f"2026-01-{(i * 2) % 28 + 1:02d}",
            "created_at": f"2026-01-{(i * 2) % 28 + 1:02d} 10:00:00",
            "t10_return_pct": ret,
        })

    # Pad sessions up to 65 distinct dates
    for s in range(65):
        records.append({
            "decision_id": f"pad_{s}",
            "symbol": f"PAD_{s}",
            "session": f"2026-02-{s % 28 + 1:02d}_{s}",
            "created_at": f"2026-02-{s % 28 + 1:02d} 10:00:00",
            "t10_return_pct": None,
        })

    report = evaluate_shadow_graduation(records=records, cost_pct=0.35)
    assert report["can_graduate"] is True
    assert report["effective_sample_size"] == 35
    assert report["hit_rate_t10"] > 0.55
    assert report["expectancy_t10"] > 0.0
    assert report["profit_factor_t10"] >= 1.2
    assert "Đạt toàn bộ tiêu chuẩn tốt nghiệp Shadow Mode." in report["reasons"]


def test_evaluate_shadow_graduation_empty_records():
    """Empty database or records returns safe default rejection."""
    report = evaluate_shadow_graduation(records=[])
    assert report["can_graduate"] is False
    assert report["total_signals"] == 0
    assert report["effective_sample_size"] == 0
    assert "Chưa có bản ghi SHADOW_BUY nào" in report["reasons"][0]


def test_panic_score_breakdown_explains_pnj_rsi_discrepancy():
    """Explain PNJ case: RSI 9.2 provides max 30 points to RSI score, but lacks volume shock/gap."""
    tech_data_rsi_only = {
        "rsi14": 9.2,
        "ma20": 100.0,
        "volume_ratio_20d": 1.0,
        "atr_ratio_14d": 1.0,
        "has_gap_down": False,
    }
    # Current price is 90 (10% below MA20 -> ma20_score = (10-5)*2 = 10)
    score, breakdown = _calculate_panic_score_with_breakdown(90.0, tech_data_rsi_only)
    assert breakdown["rsi_score"] == 30.0
    assert breakdown["ma20_drawdown_score"] == 10.0
    assert breakdown["volume_shock_score"] == 0.0
    assert breakdown["atr_expansion_score"] == 0.0
    assert breakdown["gap_down_score"] == 0.0
    assert score == 40.0


def test_contrarian_engine_flags_anomalous_high_mos():
    """Client observation: DXG/DIG MoS +99.9% must trigger anomalous high MoS warning."""
    fin_dict = {
        "f_score": 8,
        "f_score_details": {
            "score": 8,
            "data_completeness": 1.0,
            "passed": ["positive_net_income", "positive_cfo"],
            "failed": [],
        },
        "debt_equity": 0.8,
        "cfo": 1000.0,
        "p_cf": 5.0,
        "mos_pct": 99.9,
        "mos_is_informative": True,
        "fair_value": 100000.0,
    }
    tech_data = {
        "rsi14": 28.0,
        "ma20": 20.0,
        "volume_ratio_20d": 2.0,
        "atr_ratio_14d": 1.5,
        "has_gap_down": False,
    }
    result = evaluate_contrarian_gates(
        symbol="DXG",
        current_price=10.0,
        sector="Bất động sản",
        fin_dict=fin_dict,
        tech_data=tech_data,
    )
    assert "anomalous_high_mos_warning" in result.metrics
    assert "cực đoan (>= 90%)" in result.metrics["anomalous_high_mos_warning"]
    assert "panic_score_breakdown" in result.metrics


def test_update_shadow_records_forward_returns_idempotent():
    """Verify that update_shadow_records_forward_returns reads immutable snapshot_price and calls upsert."""
    records = [
        {
            "decision_id": "dec_1",
            "symbol": "FPT",
            "price": 120.0,
            "facts": {"snapshot_price": 120.0},
            "t1_return_pct": 1.5,
            "t5_return_pct": 3.0,
            "t10_return_pct": 5.5,
            "t20_return_pct": 7.0,
        },
        {
            "decision_id": "dec_invalid",
            "symbol": "VNM",
            "price": 0.0,
            "facts": {"snapshot_price": 0.0},
        },
    ]

    with patch("scripts.update_shadow_returns.update_decision_forward_returns", return_value=True) as mock_upsert:
        updated = update_shadow_records_forward_returns(records)
        assert updated == 1
        assert mock_upsert.call_count == 1
        mock_upsert.assert_called_once_with(
            "dec_1",
            {
                "symbol": "FPT",
                "snapshot_price": 120.0,
                "t1_return_pct": 1.5,
                "t5_return_pct": 3.0,
                "t10_return_pct": 5.5,
                "t20_return_pct": 7.0,
            },
        )


def test_estimate_effective_sample_size_accounts_for_market_shock_clustering():
    """Verify that multiple episodes occurring on the same market shock date reduce N_eff below raw count."""
    from scripts.evaluate_shadow_graduation import estimate_effective_sample_size

    # Case 1: 10 episodes on 10 separate days -> N_eff == 10
    spread_episodes = [{"session": f"2026-01-{i+1:02d}"} for i in range(10)]
    assert estimate_effective_sample_size(spread_episodes, intra_cluster_corr=0.5) == 10.0

    # Case 2: 10 episodes clustered on only 2 market shock dates (5 each)
    clustered_episodes = (
        [{"session": "2026-01-05"} for _ in range(5)]
        + [{"session": "2026-01-10"} for _ in range(5)]
    )
    # Mean cluster size = 5. VIF = 1 + (5 - 1) * 0.5 = 3.0. N_eff = 10 / 3.0 = 3.3
    n_eff = estimate_effective_sample_size(clustered_episodes, intra_cluster_corr=0.5)
    assert n_eff == 3.3
    assert n_eff < 10.0

