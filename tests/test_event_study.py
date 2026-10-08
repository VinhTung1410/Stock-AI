"""tests/test_event_study.py

Unit tests for event_study.py (Phase 27 - P1 Event Study Engine).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from event_study import (
    SIG_CONTROL_RANDOM,
    SIG_PANIC_70,
    SIG_RSI_30,
    build_stock_context,
    calculate_atr_array,
    calculate_rolling_beta,
    calculate_rsi_series,
    compute_signal_summary,
    extract_event_record,
    extract_forward_returns,
    scan_single_stock_events,
)


@pytest.fixture
def sample_price_df():
    """Generates 120 bars of synthetic OHLCV data."""
    dates = pd.date_range("2023-01-01", periods=120, freq="B")
    base_price = 50.0
    np.random.seed(42)
    daily_returns = np.random.normal(0.001, 0.02, size=120)
    prices = base_price * np.exp(np.cumsum(daily_returns))

    df = pd.DataFrame(
        {
            "time": dates,
            "open": prices * 0.99,
            "high": prices * 1.02,
            "low": prices * 0.98,
            "close": prices,
            "volume": np.random.uniform(500_000, 2_000_000, size=120),
        }
    )
    return df


@pytest.fixture
def sample_bench_series(sample_price_df):
    dates = sample_price_df["time"]
    b_prices = 1000.0 * np.exp(np.cumsum(np.random.normal(0.0005, 0.01, size=len(dates))))
    b_open = pd.Series(b_prices * 0.995, index=pd.DatetimeIndex(dates))
    b_close = pd.Series(b_prices, index=pd.DatetimeIndex(dates))
    return b_open, b_close


def test_calculate_rsi_series(sample_price_df):
    rsi = calculate_rsi_series(sample_price_df["close"])
    assert len(rsi) == len(sample_price_df)
    assert not rsi.dropna().empty
    assert (rsi.dropna() >= 0).all() and (rsi.dropna() <= 100).all()


def test_calculate_atr_array(sample_price_df):
    atr = calculate_atr_array(sample_price_df)
    assert len(atr) == len(sample_price_df)
    valid_atr = atr[~np.isnan(atr)]
    assert len(valid_atr) > 0
    assert (valid_atr > 0).all()


def test_calculate_rolling_beta(sample_price_df, sample_bench_series):
    _, b_close = sample_bench_series
    beta = calculate_rolling_beta(sample_price_df, b_close, window=50)
    assert len(beta) == len(sample_price_df)
    assert (beta >= 0.3).all() and (beta <= 2.5).all()


def test_build_stock_context(sample_price_df, sample_bench_series):
    b_open, b_close = sample_bench_series
    ctx = build_stock_context("TEST", sample_price_df, b_open, b_close)
    assert ctx is not None
    assert ctx.symbol == "TEST"
    assert ctx.n == len(sample_price_df)

    # Empty / short df returns None
    assert build_stock_context("TEST", pd.DataFrame(), b_open, b_close) is None
    assert build_stock_context("TEST", sample_price_df.iloc[:20], b_open, b_close) is None


def test_stock_context_exit_simulation(sample_price_df, sample_bench_series):
    b_open, b_close = sample_bench_series
    ctx = build_stock_context("TEST", sample_price_df, b_open, b_close)
    assert ctx is not None

    # Test stop loss hit
    exit_idx, exit_price, hit = ctx.simulate_exit(j0=10, end=30, stop_price=9999.0)
    assert hit is True
    assert exit_idx == 12  # Hits at j0 + 2 immediately because stop_price is huge

    # Test stop loss not hit
    exit_idx2, exit_price2, hit2 = ctx.simulate_exit(j0=10, end=30, stop_price=0.01)
    assert hit2 is False
    assert exit_idx2 == 30


def test_extract_forward_returns(sample_price_df, sample_bench_series):
    b_open, b_close = sample_bench_series
    ctx = build_stock_context("TEST", sample_price_df, b_open, b_close)
    fwd = extract_forward_returns(ctx, i=50, entry_price=ctx.o[51], beta=1.0)
    assert "ret_t5" in fwd
    assert "ret_t20" in fwd
    assert "alpha_t20" in fwd
    assert "alpha_adj_t20" in fwd


def test_extract_event_record(sample_price_df, sample_bench_series):
    b_open, b_close = sample_bench_series
    ctx = build_stock_context("TEST", sample_price_df, b_open, b_close)
    rec = extract_event_record(ctx, i=50, signal_name=SIG_RSI_30)
    assert rec is not None
    assert rec["symbol"] == "TEST"
    assert rec["signal"] == SIG_RSI_30
    assert "ret_t20" in rec
    assert "mae_pct" in rec
    assert "mfe_pct" in rec
    assert "hit_fixed8" in rec


def test_scan_single_stock_events(sample_price_df, sample_bench_series):
    b_open, b_close = sample_bench_series
    ctx = build_stock_context("TEST", sample_price_df, b_open, b_close)
    events = scan_single_stock_events(ctx, sample_price_df, b_close, cooldown=5, warmup=20)
    assert isinstance(events, list)
    # Random baseline should always emit sample events
    signals_present = {e["signal"] for e in events}
    assert SIG_CONTROL_RANDOM in signals_present


def test_compute_signal_summary():
    mock_events = pd.DataFrame(
        [
            {
                "signal": SIG_RSI_30,
                "ret_t5": 2.0,
                "ret_t20": 5.0,
                "ret_t60": 8.0,
                "alpha_t5": 1.5,
                "alpha_t20": 3.0,
                "alpha_t60": 4.0,
                "alpha_adj_t20": 2.5,
                "mae_pct": -3.0,
                "mfe_pct": 7.0,
            },
            {
                "signal": SIG_RSI_30,
                "ret_t5": -1.0,
                "ret_t20": 3.0,
                "ret_t60": 5.0,
                "alpha_t5": -0.5,
                "alpha_t20": 2.0,
                "alpha_t60": 3.0,
                "alpha_adj_t20": 1.8,
                "mae_pct": -4.0,
                "mfe_pct": 6.0,
            },
            {
                "signal": SIG_PANIC_70,
                "ret_t5": 4.0,
                "ret_t20": 8.0,
                "ret_t60": 12.0,
                "alpha_t5": 3.0,
                "alpha_t20": 6.0,
                "alpha_t60": 8.0,
                "alpha_adj_t20": 5.5,
                "mae_pct": -2.0,
                "mfe_pct": 10.0,
            },
        ]
    )

    summary = compute_signal_summary(mock_events)
    assert not summary.empty
    assert "Signal" in summary.columns
    assert "WinRate20 (%)" in summary.columns
    assert "Alpha20 (%)" in summary.columns

    rsi_row = summary[summary["Signal"] == SIG_RSI_30].iloc[0]
    assert rsi_row["N"] == 2
    assert rsi_row["WinRate20 (%)"] == 100.0
    assert rsi_row["Alpha20 (%)"] == 2.5
