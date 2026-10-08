"""tests/test_statistical_replay_adapter.py

Unit tests for statistical_replay_adapter.py.
Verifies:
  - Matched-date peer calculations with Open(D+1) -> Close(D+20)
  - PIT trailing 60-day rolling beta estimation
  - Synthetic known-alpha detection (yields ALPHA when true alpha is large)
  - Synthetic zero-alpha detection (yields INCONCLUSIVE when effect is small)
  - Marginal ablation testing with G < 5 -> "KHÔNG THỂ KIỂM ĐỊNH (G < 5)"
  - Distinct calculation of Rejection Hurdle vs MDE for power 80%
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from statistical_replay_adapter import (
    STATUS_CANNOT_TEST_G_TOO_SMALL,
    MatchedDatePeerEngine,
    TradeEvent,
    evaluate_variant_statistics,
)
from statistical_validation_engine import VERDICT_ALPHA, VERDICT_INCONCLUSIVE


@pytest.fixture
def mock_price_cache():
    dates = pd.date_range("2023-01-01", periods=150, freq="B")
    cache = {}

    # Benchmark VNINDEX
    np.random.seed(42)
    b_ret = np.random.normal(0.0005, 0.01, size=len(dates))
    b_prices = 1000.0 * np.exp(np.cumsum(b_ret))
    cache["VNINDEX"] = pd.DataFrame(
        {
            "time": dates,
            "open": b_prices * 0.995,
            "high": b_prices * 1.01,
            "low": b_prices * 0.99,
            "close": b_prices,
            "volume": 100_000_000,
        }
    )

    # 15 Peer stocks
    for sym_idx in range(15):
        s_ret = np.random.normal(0.0005, 0.02, size=len(dates))
        s_prices = 50.0 * np.exp(np.cumsum(s_ret))
        cache[f"STOCK_{sym_idx}"] = pd.DataFrame(
            {
                "time": dates,
                "open": s_prices * 0.99,
                "high": s_prices * 1.02,
                "low": s_prices * 0.98,
                "close": s_prices,
                "volume": 1_000_000,
            }
        )

    return cache


def test_matched_date_peer_engine(mock_price_cache):
    engine = MatchedDatePeerEngine(mock_price_cache, bench_symbol="VNINDEX")
    signal_date = pd.to_datetime("2023-03-01")

    # Stock 0 is active, all others are peers
    base_ret, n_peers = engine.compute_peer_baseline(
        signal_date, active_symbols=["STOCK_0"], holding_bars=20
    )
    assert n_peers == 14
    assert np.isfinite(base_ret)

    # Check PIT rolling beta
    beta = engine.compute_rolling_beta("STOCK_0", signal_date, window=60)
    assert np.isfinite(beta)
    assert beta > 0


def test_adapter_synthetic_known_alpha_detection():
    # Construct 13 clusters with large true alpha (+22%)
    dates = pd.date_range("2023-01-01", periods=13, freq="25D")
    events: list[TradeEvent] = []

    for idx, d in enumerate(dates):
        # 3 events per cluster with high excess alpha
        for s in ["AAA", "BBB", "CCC"]:
            events.append(
                TradeEvent(
                    symbol=s,
                    signal_date=d,
                    entry_date=d + pd.Timedelta(days=1),
                    exit_date=d + pd.Timedelta(days=25),
                    entry_price=10.0,
                    exit_price=12.5,
                    ret_tradable=25.0,
                    peer_baseline_ret=3.0,
                    excess_alpha=22.0 + np.random.normal(0, 1.0),
                    beta_adj_alpha=20.0,
                )
            )

    res = evaluate_variant_statistics("Known_Alpha_Variant", events, gap_bars=20)
    assert res.g_clusters == 13
    assert res.theta_hat_alpha > 20.0
    # Must declare ALPHA because alpha exceeds rejection hurdle under Holm
    assert VERDICT_ALPHA in res.verdict
    assert res.rejection_hurdle_holm > res.rejection_hurdle_nominal
    assert res.mde_holm > res.mde_nominal


def test_adapter_synthetic_zero_alpha_inconclusive():
    # Construct 13 clusters with tiny alpha (+0.5%)
    dates = pd.date_range("2023-01-01", periods=13, freq="25D")
    events: list[TradeEvent] = []

    for idx, d in enumerate(dates):
        for s in ["AAA", "BBB", "CCC"]:
            events.append(
                TradeEvent(
                    symbol=s,
                    signal_date=d,
                    entry_date=d + pd.Timedelta(days=1),
                    exit_date=d + pd.Timedelta(days=25),
                    entry_price=10.0,
                    exit_price=10.05,
                    ret_tradable=0.5,
                    peer_baseline_ret=0.0,
                    excess_alpha=0.5 + np.random.normal(0, 3.5),
                    beta_adj_alpha=0.2,
                )
            )

    res = evaluate_variant_statistics("Zero_Alpha_Variant", events, gap_bars=20)
    assert res.g_clusters == 13
    # Must declare INCONCLUSIVE because effect is smaller than MDE
    assert VERDICT_INCONCLUSIVE in res.verdict


def test_adapter_marginal_too_few_clusters():
    # Baseline has 10 clusters
    base_dates = pd.date_range("2023-01-01", periods=10, freq="25D")
    base_events = [
        TradeEvent(
            symbol="AAA",
            signal_date=d,
            entry_date=d + pd.Timedelta(days=1),
            exit_date=d + pd.Timedelta(days=25),
            entry_price=10.0,
            exit_price=10.5,
            ret_tradable=5.0,
            peer_baseline_ret=1.0,
            excess_alpha=4.0,
            beta_adj_alpha=3.0,
        )
        for d in base_dates
    ]

    # Relaxed variant adds only 2 new signals in 2 distinct dates (G_marginal = 2 < 5)
    relaxed_dates = pd.date_range("2024-01-01", periods=2, freq="25D")
    marginal_events = [
        TradeEvent(
            symbol="BBB",
            signal_date=d,
            entry_date=d + pd.Timedelta(days=1),
            exit_date=d + pd.Timedelta(days=25),
            entry_price=10.0,
            exit_price=10.5,
            ret_tradable=5.0,
            peer_baseline_ret=1.0,
            excess_alpha=4.0,
            beta_adj_alpha=3.0,
        )
        for d in relaxed_dates
    ]
    all_relaxed_events = base_events + marginal_events

    res = evaluate_variant_statistics(
        "Marginal_Ablation_Variant",
        all_relaxed_events,
        baseline_events=base_events,
        gap_bars=20,
    )
    # Since G_marginal = 2 < 5, engine must guard and return STATUS_CANNOT_TEST_G_TOO_SMALL
    assert res.marginal_clusters == 2
    assert res.verdict == STATUS_CANNOT_TEST_G_TOO_SMALL
