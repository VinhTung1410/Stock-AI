"""Unit tests for backtest_engine.py."""

from __future__ import annotations

import pandas as pd

from backtest_engine import (
    REGIME_FULL,
    RegimeBacktestEngine,
    TradeRecord,
    breakdown_by_regime,
    calculate_performance_metrics,
    calculate_slippage_price,
    can_execute_t_plus_2,
    check_hose_ceiling_unfilled,
)
from regime_classifier import REGIME_DOWNTREND, REGIME_SIDEWAYS, REGIME_UPTREND


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


def test_alpha_beta_with_benchmark():
    """Verify Alpha and Beta calculations when benchmark returns are provided."""
    dates = pd.date_range("2024-01-01", periods=30, freq="B")
    strat_prices = [100.0 + i * 2.0 for i in range(30)]  # +2% per day
    bench_prices = [100.0 + i * 1.0 for i in range(30)]  # +1% per day

    equity_curve = pd.Series(strat_prices, index=dates)
    bench_curve = pd.Series(bench_prices, index=dates)
    bench_returns = bench_curve.pct_change().dropna()

    trades = [
        TradeRecord(
            symbol="VIC",
            entry_date=dates[0],
            entry_price=100.0,
            exit_price=150.0,
            exit_date=dates[-1],
            shares=100,
            net_pnl=5000.0,
            pnl_pct=50.0,
            is_filled=True,
        )
    ]

    metrics = calculate_performance_metrics(trades, equity_curve, benchmark_returns=bench_returns)
    assert "beta" in metrics
    assert "alpha_pct" in metrics
    # Beta should be calculated and non-zero
    assert metrics["beta"] > 0.0


def test_buy_and_hold_and_benchmark_equity():
    """Verify Buy & Hold equity and normalized benchmark equity helper functions."""
    from backtest_engine import (
        calculate_buy_and_hold_equity,
        calculate_normalized_benchmark_equity,
    )

    dates = pd.date_range("2024-01-01", periods=10, freq="B")
    df_price = pd.DataFrame({"close": [10.0 + i for i in range(10)]}, index=dates)

    bh = calculate_buy_and_hold_equity(df_price, initial_capital=100_000_000.0)
    assert len(bh) == 10
    assert bh.iloc[0] == 100_000_000.0
    assert bh.iloc[-1] == 190_000_000.0  # 19.0 / 10.0 * 100M

    df_bench = pd.DataFrame({"close": [1000.0 + i * 10 for i in range(10)]}, index=dates)
    norm_bench = calculate_normalized_benchmark_equity(df_bench, dates, initial_capital=100_000_000.0)
    assert len(norm_bench) == 10
    assert norm_bench.iloc[0] == 100_000_000.0


def test_generate_signals_by_strategy():
    """Verify signal generation across strategies."""
    from backtest_engine import (
        STRATEGY_MA_CROSSOVER,
        STRATEGY_QUANT_CORE,
        STRATEGY_RSI_REVERSION,
        generate_signals_by_strategy,
    )

    dates = pd.date_range("2024-01-01", periods=60, freq="B")
    prices = [20.0 + (i * 0.5) for i in range(60)]
    df_p = pd.DataFrame({"close": prices, "open": prices}, index=dates)

    # 1. MA Crossover
    sig_ma = generate_signals_by_strategy(df_p, strategy=STRATEGY_MA_CROSSOVER)
    assert len(sig_ma) == 60

    # 2. RSI Reversion
    sig_rsi = generate_signals_by_strategy(df_p, strategy=STRATEGY_RSI_REVERSION)
    assert len(sig_rsi) == 60

    # 3. Quant Core (FA pass)
    sig_core = generate_signals_by_strategy(df_p, strategy=STRATEGY_QUANT_CORE, f_score=8, mos_pct=25.0, z_score=3.0)
    assert len(sig_core) == 60

    # 4. Quant Core (FA fail -> zero signals)
    sig_fail = generate_signals_by_strategy(df_p, strategy=STRATEGY_QUANT_CORE, f_score=4, mos_pct=5.0, z_score=1.2)
    assert (sig_fail == 0).all()


def test_stop_loss_trigger():
    """Verify that a drop beyond -7% triggers STOP_LOSS exit reason upon T+2."""
    dates = pd.date_range("2024-01-01", periods=10, freq="B")
    # Price plummets from 50 to 40 (-20%)
    prices = [50.0, 50.0, 48.0, 42.0, 40.0, 39.0, 38.0, 38.0, 38.0, 38.0]
    df_price = pd.DataFrame({"close": prices, "open": prices}, index=dates)

    signals = pd.Series(0, index=dates)
    signals.iloc[1] = 1  # Buy on day 1 (price 50)
    # No sell signal, stop loss should trigger automatically on day 3 or 4

    engine = RegimeBacktestEngine(initial_capital=100_000_000.0)
    result = engine.run_backtest(df_price, signals, symbol="VIC")

    filled = [t for t in result.trades if t.is_filled]
    assert len(filled) == 1
    assert filled[0].exit_reason == "STOP_LOSS"
    assert filled[0].net_pnl < 0


def test_breakdown_by_regime_with_unaligned_benchmark_and_regimes():
    """Verify breakdown_by_regime handles mismatched index lengths without IndexingError."""
    dates_stock = pd.date_range("2024-01-01", periods=20, freq="B")
    dates_bench = pd.date_range("2023-10-01", periods=60, freq="B")  # Different length and start

    equity_curve = pd.Series([100_000_000.0 * (1.0 + 0.001 * i) for i in range(20)], index=dates_stock)
    bench_returns = pd.Series([0.002] * 60, index=dates_bench)
    regimes = pd.Series([REGIME_UPTREND] * 10 + [REGIME_SIDEWAYS] * 10, index=dates_stock)

    trades = [
        TradeRecord(
            symbol="HPG",
            entry_date=dates_stock[1],
            entry_price=25.0,
            exit_price=27.0,
            exit_date=dates_stock[8],
            shares=1000,
            net_pnl=2000.0,
            pnl_pct=8.0,
            regime=REGIME_UPTREND,
            is_filled=True,
        )
    ]

    breakdown = breakdown_by_regime(trades, equity_curve, bench_returns, regimes)

    assert REGIME_FULL in breakdown
    assert REGIME_UPTREND in breakdown
    assert REGIME_DOWNTREND in breakdown
    assert REGIME_SIDEWAYS in breakdown
    assert breakdown[REGIME_UPTREND]["total_trades"] == 1
    assert breakdown[REGIME_DOWNTREND]["total_trades"] == 0

