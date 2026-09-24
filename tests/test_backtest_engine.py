"""Unit tests for backtest_engine.py."""

from __future__ import annotations

import pandas as pd

from backtest_engine import (
    RegimeBacktestEngine,
    TradeRecord,
    calculate_performance_metrics,
    calculate_slippage_price,
    can_execute_t_plus_2,
    check_hose_ceiling_unfilled,
)
from regime_classifier import REGIME_SIDEWAYS, REGIME_UPTREND


def test_hose_ceiling_unfilled():
    """Verify buy order is blocked when price hits HOSE 7% ceiling limit."""
    ref_price = 100.0
    # +7% ceiling
    ceiling_price = 107.0
    assert check_hose_ceiling_unfilled(ceiling_price, ref_price) is True

    # Normal price +2%
    normal_price = 102.0
    assert check_hose_ceiling_unfilled(normal_price, ref_price) is False

    # Zero reference price edge case
    assert check_hose_ceiling_unfilled(100.0, 0.0) is False


def test_slippage_calculation():
    """Verify adverse slippage in basis points."""
    base_price = 100.0
    # 15 bps = 0.15% -> Buy price should be 100.15
    buy_slip = calculate_slippage_price(base_price, is_buy=True, slippage_bps=15.0)
    assert round(buy_slip, 4) == 100.15

    # 15 bps = 0.15% -> Sell price should be 99.85
    sell_slip = calculate_slippage_price(base_price, is_buy=False, slippage_bps=15.0)
    assert round(sell_slip, 4) == 99.85


def test_t_plus_2_settlement_rule():
    """Enforce Vietnam T+2.5 rule: Can strictly only sell starting at T+2."""
    entry_idx = 5
    # T (day 5) -> Cannot sell
    assert can_execute_t_plus_2(entry_idx, 5) is False
    # T+1 (day 6) -> Cannot sell
    assert can_execute_t_plus_2(entry_idx, 6) is False
    # T+2 (day 7) -> Allowed to sell in afternoon session
    assert can_execute_t_plus_2(entry_idx, 7) is True
    # T+3 (day 8) -> Allowed to sell
    assert can_execute_t_plus_2(entry_idx, 8) is True


def test_calculate_performance_metrics_and_regime():
    """Verify quant performance metrics calculations."""
    entry_d = pd.Timestamp("2024-01-02")
    exit_d = pd.Timestamp("2024-01-10")

    trades = [
        TradeRecord(
            symbol="HPG",
            entry_date=entry_d,
            entry_price=25.0,
            exit_price=28.0,
            exit_date=exit_d,
            shares=1000,
            net_pnl=2800.0,
            pnl_pct=11.2,
            regime=REGIME_UPTREND,
            is_filled=True,
        ),
        TradeRecord(
            symbol="SSI",
            entry_date=entry_d,
            entry_price=30.0,
            exit_price=28.5,
            exit_date=exit_d,
            shares=1000,
            net_pnl=-1600.0,
            pnl_pct=-5.3,
            regime=REGIME_SIDEWAYS,
            is_filled=True,
        ),
    ]

    dates = pd.date_range("2024-01-01", periods=10, freq="B")
    equity_curve = pd.Series([100000.0 + i * 500 for i in range(10)], index=dates)

    metrics = calculate_performance_metrics(trades, equity_curve)

    assert metrics["total_trades"] == 2
    assert metrics["win_rate_pct"] == 50.0
    assert metrics["profit_factor"] > 1.0
    assert metrics["expectancy"] == 600.0
    assert metrics["max_drawdown_pct"] <= 0.0


def test_empty_backtest_run():
    """Empty dataframe should safely return empty BacktestResult."""
    engine = RegimeBacktestEngine()
    res = engine.run_backtest(pd.DataFrame(), pd.Series(dtype=int))
    assert len(res.trades) == 0
    assert res.equity_curve.empty


def test_full_backtest_flow_with_ceiling_and_t2():
    """Run sequential simulation with ceiling block and T+2 holding period."""
    engine = RegimeBacktestEngine(initial_capital=50_000_000.0)

    dates = pd.date_range("2024-01-01", periods=15, freq="B")
    # Day 0: 50, Day 1: 53.6 (+7.2% ceiling), Day 2: 52, Day 3-10: 55-60
    prices = [50.0, 53.6, 52.0, 54.0, 55.0, 56.0, 57.0, 58.0, 59.0, 60.0, 58.0, 57.0, 56.0, 55.0, 55.0]
    df_price = pd.DataFrame({"close": prices, "open": prices}, index=dates)

    # Signals: Buy on day 1 (hits ceiling -> unfilled), Buy on day 2 (fills), Sell on day 3 (T+1 -> blocked), Sell on day 5 (T+3 -> fills)
    signals = pd.Series(0, index=dates)
    signals.iloc[1] = 1  # Blocked by ceiling
    signals.iloc[2] = 1  # Should fill
    signals.iloc[3] = -1  # Blocked by T+2 rule
    signals.iloc[5] = -1  # Executes sell

    regimes = pd.Series(REGIME_UPTREND, index=dates)

    result = engine.run_backtest(df_price, signals, regimes)

    # We expect 2 trade records: 1 UNFILLED_CEILING and 1 Completed trade
    assert len(result.trades) == 2
    unfilled = [t for t in result.trades if not t.is_filled]
    filled = [t for t in result.trades if t.is_filled]

    assert len(unfilled) == 1
    assert unfilled[0].exit_reason == "UNFILLED_CEILING"

    assert len(filled) == 1
    assert filled[0].net_pnl > 0  # Bought at ~52, sold at ~56
    assert filled[0].holding_days >= 2  # Ensured T+2 holding
