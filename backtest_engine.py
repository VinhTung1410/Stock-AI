"""Module: backtest_engine.py.

Deterministic quantitative backtest engine simulating Vietnamese stock market
realities: HOSE +/-7% ceiling/floor limits, T+2.5 execution lag, transaction fees,
selling tax, slippage (bps), and ADV20 absorption constraints.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Final

import numpy as np
import pandas as pd

from regime_classifier import REGIME_DOWNTREND, REGIME_SIDEWAYS, REGIME_UPTREND

# Constants (S1192)
REGIME_FULL: Final[str] = "FULL"
HOSE_CEILING_PCT: Final[float] = 0.069  # Near 7% ceiling limit
DEFAULT_FEE_RATE: Final[float] = 0.0015  # 0.15%
DEFAULT_TAX_RATE: Final[float] = 0.0010  # 0.10% sell tax
DEFAULT_SLIPPAGE_BPS: Final[float] = 15.0  # 15 basis points
RISK_FREE_RATE_ANNUAL: Final[float] = 0.045  # 4.5% annual rate

# Strategy Constants (S1192)
STRATEGY_QUANT_CORE: Final[str] = "QUANT_CORE"
STRATEGY_MA_CROSSOVER: Final[str] = "MA_CROSSOVER"
STRATEGY_RSI_REVERSION: Final[str] = "RSI_REVERSION"


@dataclass
class TradeRecord:
    """Representation of an individual completed or open trade."""

    symbol: str
    entry_date: pd.Timestamp
    entry_price: float
    shares: int
    exit_date: pd.Timestamp | None = None
    exit_price: float | None = None
    exit_reason: str = ""
    entry_fee: float = 0.0
    exit_fee: float = 0.0
    exit_tax: float = 0.0
    net_pnl: float = 0.0
    pnl_pct: float = 0.0
    holding_days: int = 0
    mfe_pct: float = 0.0  # Max Favorable Excursion
    mae_pct: float = 0.0  # Max Adverse Excursion
    regime: str = REGIME_SIDEWAYS
    is_filled: bool = True


@dataclass
class BacktestResult:
    """Consolidated backtest results and performance metrics."""

    trades: list[TradeRecord] = field(default_factory=list)
    equity_curve: pd.Series = field(default_factory=pd.Series)
    summary_metrics: dict[str, Any] = field(default_factory=dict)
    regime_metrics: dict[str, dict[str, Any]] = field(default_factory=dict)


def check_hose_ceiling_unfilled(
    price: float,
    reference_price: float,
    ceiling_limit: float = HOSE_CEILING_PCT,
) -> bool:
    """Determine if a buy order cannot be filled because price is at HOSE ceiling.

    Returns True if order is UNFILLED (at or above ceiling limit).
    """
    if reference_price <= 0:
        return False
    pct_change = (price - reference_price) / reference_price
    return pct_change >= ceiling_limit


def calculate_slippage_price(price: float, is_buy: bool, slippage_bps: float) -> float:
    """Apply adverse slippage in basis points to theoretical price."""
    bps_factor = (slippage_bps / 10000.0)
    if is_buy:
        return price * (1.0 + bps_factor)
    return price * (1.0 - bps_factor)


def can_execute_t_plus_2(entry_idx: int, current_idx: int) -> bool:
    """Enforce Vietnam T+2.5 settlement rule.

    Stock bought at trading day T (entry_idx) can strictly only be sold
    starting from the afternoon of T+2 (current_idx >= entry_idx + 2).
    """
    return current_idx >= entry_idx + 2


def _calculate_trade_pnl(
    entry_price: float,
    exit_price: float,
    shares: int,
    fee_rate: float,
    tax_rate: float,
) -> tuple[float, float, float, float, float]:
    """Calculate net PnL and friction costs for a trade."""
    entry_val = entry_price * shares
    exit_val = exit_price * shares

    entry_fee = entry_val * fee_rate
    exit_fee = exit_val * fee_rate
    exit_tax = exit_val * tax_rate

    gross_pnl = exit_val - entry_val
    net_pnl = gross_pnl - entry_fee - exit_fee - exit_tax
    pnl_pct = (net_pnl / entry_val) * 100.0 if entry_val > 0 else 0.0

    return net_pnl, pnl_pct, entry_fee, exit_fee, exit_tax


def calculate_performance_metrics(
    trades: list[TradeRecord],
    equity_curve: pd.Series,
    benchmark_returns: pd.Series | None = None,
    risk_free_rate: float = RISK_FREE_RATE_ANNUAL,
) -> dict[str, Any]:
    """Calculate institutional-grade quantitative performance metrics."""
    filled_trades = [t for t in trades if t.is_filled and t.exit_price is not None]
    total_trades = len(filled_trades)

    if total_trades == 0 or equity_curve.empty:
        return _build_empty_metrics(len(trades))

    # Basic trade statistics
    wins = [t for t in filled_trades if t.net_pnl > 0]
    losses = [t for t in filled_trades if t.net_pnl <= 0]
    win_rate = (len(wins) / total_trades) * 100.0

    gross_profit = sum(t.net_pnl for t in wins)
    gross_loss = abs(sum(t.net_pnl for t in losses))
    if gross_loss > 0:
        profit_factor = gross_profit / gross_loss
    elif gross_profit > 0:
        profit_factor = 99.0
    else:
        profit_factor = 0.0

    avg_win = (gross_profit / len(wins)) if wins else 0.0
    avg_loss = (gross_loss / len(losses)) if losses else 0.0
    expectancy = sum(t.net_pnl for t in filled_trades) / total_trades

    # Equity curve metrics
    daily_returns = equity_curve.pct_change().dropna()
    cagr = _calculate_cagr(equity_curve)
    max_dd, recovery_days = _calculate_drawdown(equity_curve)
    sharpe = _calculate_sharpe(daily_returns, risk_free_rate)
    sortino = _calculate_sortino(daily_returns, risk_free_rate)
    calmar = (cagr / abs(max_dd)) if max_dd != 0 else 0.0

    # Alpha & Beta vs Benchmark
    alpha, beta = _calculate_alpha_beta(daily_returns, benchmark_returns, risk_free_rate)

    # Average MFE/MAE
    avg_mfe = np.mean([t.mfe_pct for t in filled_trades]) if filled_trades else 0.0
    avg_mae = np.mean([t.mae_pct for t in filled_trades]) if filled_trades else 0.0

    return {
        "total_trades": total_trades,
        "unfilled_trades": len(trades) - total_trades,
        "win_rate_pct": round(win_rate, 2),
        "profit_factor": round(profit_factor, 2),
        "expectancy": round(expectancy, 2),
        "avg_win": round(avg_win, 2),
        "avg_loss": round(avg_loss, 2),
        "cagr_pct": round(cagr * 100.0, 2),
        "max_drawdown_pct": round(max_dd * 100.0, 2),
        "recovery_days": int(recovery_days),
        "sharpe_ratio": round(sharpe, 2),
        "sortino_ratio": round(sortino, 2),
        "calmar_ratio": round(calmar, 2),
        "alpha_pct": round(alpha * 100.0, 2),
        "beta": round(beta, 2),
        "avg_mfe_pct": round(float(avg_mfe), 2),
        "avg_mae_pct": round(float(avg_mae), 2),
    }


def _build_empty_metrics(total_signals: int) -> dict[str, Any]:
    """Return default empty metrics structure."""
    return {
        "total_trades": 0,
        "unfilled_trades": total_signals,
        "win_rate_pct": 0.0,
        "profit_factor": 0.0,
        "expectancy": 0.0,
        "avg_win": 0.0,
        "avg_loss": 0.0,
        "cagr_pct": 0.0,
        "max_drawdown_pct": 0.0,
        "recovery_days": 0,
        "sharpe_ratio": 0.0,
        "sortino_ratio": 0.0,
        "calmar_ratio": 0.0,
        "alpha_pct": 0.0,
        "beta": 1.0,
        "avg_mfe_pct": 0.0,
        "avg_mae_pct": 0.0,
    }


def _calculate_cagr(equity: pd.Series) -> float:
    """Calculate Compound Annual Growth Rate."""
    if len(equity) < 2 or equity.iloc[0] <= 0:
        return 0.0
    start_val = equity.iloc[0]
    end_val = equity.iloc[-1]
    years = len(equity) / 252.0
    if years <= 0:
        return 0.0
    return float((end_val / start_val) ** (1.0 / years) - 1.0)


def _calculate_drawdown(equity: pd.Series) -> tuple[float, int]:
    """Calculate Maximum Drawdown and maximum recovery days."""
    if equity.empty:
        return 0.0, 0
    cummax = equity.cummax()
    drawdown = (equity - cummax) / cummax
    max_dd = float(drawdown.min())

    # Recovery days calculation
    recovery_days = 0
    current_dd_days = 0
    for dd in drawdown:
        if dd < 0:
            current_dd_days += 1
            if current_dd_days > recovery_days:
                recovery_days = current_dd_days
        else:
            current_dd_days = 0

    return max_dd, recovery_days


def _calculate_sharpe(returns: pd.Series, risk_free_rate: float) -> float:
    """Calculate Annualized Sharpe Ratio."""
    if returns.empty or returns.std() == 0:
        return 0.0
    daily_rf = (1.0 + risk_free_rate) ** (1.0 / 252.0) - 1.0
    excess_returns = returns - daily_rf
    return float((excess_returns.mean() / returns.std()) * np.sqrt(252.0))


def _calculate_sortino(returns: pd.Series, risk_free_rate: float) -> float:
    """Calculate Annualized Sortino Ratio using downside deviation."""
    if returns.empty:
        return 0.0
    daily_rf = (1.0 + risk_free_rate) ** (1.0 / 252.0) - 1.0
    downside_returns = returns[returns < daily_rf]
    downside_std = downside_returns.std()
    if downside_std == 0 or np.isnan(downside_std):
        return 0.0
    excess_mean = (returns - daily_rf).mean()
    return float((excess_mean / downside_std) * np.sqrt(252.0))


def _calculate_alpha_beta(
    returns: pd.Series,
    benchmark_returns: pd.Series | None,
    risk_free_rate: float,
) -> tuple[float, float]:
    """Calculate Jensen's Alpha and Beta against the market benchmark."""
    if benchmark_returns is None or benchmark_returns.empty or returns.empty:
        return 0.0, 1.0

    ret_s = returns.copy()
    ret_b = benchmark_returns.copy()
    try:
        ret_s.index = pd.to_datetime(ret_s.index).normalize()
        ret_b.index = pd.to_datetime(ret_b.index).normalize()
    except Exception:
        pass

    aligned = pd.concat([ret_s, ret_b], axis=1, join="inner").dropna()
    if len(aligned) < 5:
        return 0.0, 1.0

    ret_strat = aligned.iloc[:, 0].astype(float)
    ret_bench = aligned.iloc[:, 1].astype(float)

    cov_matrix = np.cov(ret_strat, ret_bench)
    bench_var = cov_matrix[1, 1]
    if bench_var == 0 or np.isnan(bench_var):
        return 0.0, 1.0

    beta = float(cov_matrix[0, 1] / bench_var)
    strat_annual = ret_strat.mean() * 252.0
    bench_annual = ret_bench.mean() * 252.0
    alpha = float(strat_annual - (risk_free_rate + beta * (bench_annual - risk_free_rate)))

    return alpha, beta


def breakdown_by_regime(
    trades: list[TradeRecord],
    equity_curve: pd.Series,
    benchmark_returns: pd.Series | None = None,
    regimes: pd.Series | None = None,
) -> dict[str, dict[str, Any]]:
    """Partition performance metrics across market regimes: Full, Uptrend, Downtrend, Sideways."""
    breakdown: dict[str, dict[str, Any]] = {}

    # 1. Full metrics
    breakdown[REGIME_FULL] = calculate_performance_metrics(trades, equity_curve, benchmark_returns)

    # 2. Per-regime trade subsets
    for reg in (REGIME_UPTREND, REGIME_DOWNTREND, REGIME_SIDEWAYS):
        sub_trades = [t for t in trades if t.regime == reg]
        if regimes is not None and not equity_curve.empty:
            aligned_regimes = regimes.reindex(equity_curve.index).ffill().bfill()
            mask_np = (aligned_regimes == reg).to_numpy(dtype=bool)
            daily_ret = equity_curve.pct_change().fillna(0.0)
            reg_daily_ret = daily_ret.copy()
            reg_daily_ret.iloc[~mask_np] = 0.0
            sub_equity = (1.0 + reg_daily_ret).cumprod() * (equity_curve.iloc[0] if not equity_curve.empty else 1.0)

            sub_bench = None
            if benchmark_returns is not None and not benchmark_returns.empty:
                aligned_bench = benchmark_returns.reindex(equity_curve.index).fillna(0.0)
                aligned_bench.iloc[~mask_np] = 0.0
                sub_bench = aligned_bench

            breakdown[reg] = calculate_performance_metrics(sub_trades, sub_equity, sub_bench)
        else:
            breakdown[reg] = calculate_performance_metrics(sub_trades, pd.Series([1.0, 1.0]))

    return breakdown


def calculate_buy_and_hold_equity(
    df_price: pd.DataFrame,
    initial_capital: float = 100_000_000.0,
) -> pd.Series:
    """Calculate Buy & Hold equity curve starting with initial capital."""
    if df_price.empty or "close" not in df_price.columns:
        return pd.Series(dtype=float)
    close = df_price["close"].astype(float)
    start_p = close.iloc[0]
    if start_p <= 0:
        return pd.Series(initial_capital, index=df_price.index)
    return (close / start_p) * initial_capital


def calculate_normalized_benchmark_equity(
    df_benchmark: pd.DataFrame,
    target_index: pd.Index,
    initial_capital: float = 100_000_000.0,
) -> pd.Series:
    """Normalize benchmark index (e.g. VNINDEX) to align with target dates and initial capital."""
    if df_benchmark.empty or "close" not in df_benchmark.columns:
        return pd.Series(initial_capital, index=target_index)

    bench = df_benchmark.copy()
    if "time" in bench.columns:
        bench["time"] = pd.to_datetime(bench["time"]).dt.normalize()
        bench = bench.set_index("time")
    else:
        bench.index = pd.to_datetime(bench.index).normalize()

    tgt_norm = pd.to_datetime(target_index).normalize()
    close_bench = bench["close"].astype(float)
    aligned = close_bench.reindex(tgt_norm).ffill().bfill()
    start_p = aligned.iloc[0] if not aligned.empty else 0.0
    if start_p <= 0:
        return pd.Series(initial_capital, index=target_index)

    res = (aligned / start_p) * initial_capital
    res.index = target_index
    return res


def _generate_ma_crossover_signals(close: pd.Series) -> pd.Series:
    """Generate MA20 / MA50 crossover signals."""
    ma20 = close.rolling(20, min_periods=10).mean()
    ma50 = close.rolling(50, min_periods=20).mean()
    signals = pd.Series(0, index=close.index)
    bullish = (ma20 > ma50) & (ma20.shift(1) <= ma50.shift(1))
    bearish = (ma20 < ma50) & (ma20.shift(1) >= ma50.shift(1))
    signals[bullish] = 1
    signals[bearish] = -1
    return signals


def _generate_rsi_reversion_signals(close: pd.Series) -> pd.Series:
    """Generate RSI Mean Reversion signals."""
    delta = close.diff()
    gain = delta.where(delta > 0, 0.0).rolling(14, min_periods=7).mean()
    loss = (-delta.where(delta < 0, 0.0)).rolling(14, min_periods=7).mean()
    rs = gain / loss.replace(0, np.nan)
    rsi = 100.0 - (100.0 / (1.0 + rs))

    signals = pd.Series(0, index=close.index)
    signals[(rsi < 35) & (rsi.shift(1) >= 35)] = 1
    signals[(rsi > 65) & (rsi.shift(1) <= 65)] = -1
    return signals


def _generate_quant_core_signals(
    df_price: pd.DataFrame,
    f_score: int = 7,
    mos_pct: float = 20.0,
    z_score: float = 2.5,
    regimes: pd.Series | None = None,
    enforce_regime_gate: bool = False,
) -> pd.Series:
    """Generate Quant Core Strategy signals based on FA health, MoS, and TA momentum."""
    close = df_price["close"].astype(float)
    signals = pd.Series(0, index=close.index)

    # Fundamental Gate validation
    fa_passed = (f_score >= 6) and (mos_pct >= 15.0) and (z_score > 1.8)
    if not fa_passed:
        return signals

    # Technical timing & risk triggers
    ma20 = close.rolling(20, min_periods=10).mean()
    ma50 = close.rolling(50, min_periods=20).mean()

    delta = close.diff()
    gain = delta.where(delta > 0, 0.0).rolling(14, min_periods=7).mean()
    loss = (-delta.where(delta < 0, 0.0)).rolling(14, min_periods=7).mean()
    rs = gain / loss.replace(0, np.nan)
    rsi = 100.0 - (100.0 / (1.0 + rs)).fillna(50.0)

    # Buy: Upward trend, reasonable RSI (not overbought FOMO)
    buy_cond = (close >= ma20) & (ma20 >= ma50 * 0.98) & (rsi < 70) & (rsi >= 40)

    # Macro Regime Gate (Cash Mode): Block buys during Downtrend
    if enforce_regime_gate and regimes is not None:
        aligned_regimes = regimes.reindex(close.index).fillna(REGIME_SIDEWAYS)
        buy_cond = buy_cond & (aligned_regimes != REGIME_DOWNTREND)

    buy_prev = buy_cond.shift(1).fillna(False).astype(bool)
    buy_trigger = buy_cond & (~buy_prev)

    # Sell: Overbought climax or breakdown below MA20 * 0.95
    sell_cond = (rsi >= 75) | (close < ma20 * 0.95)
    sell_prev = sell_cond.shift(1).fillna(False).astype(bool)
    sell_trigger = sell_cond & (~sell_prev)

    signals[buy_trigger] = 1
    signals[sell_trigger] = -1
    return signals


def generate_signals_by_strategy(
    df_price: pd.DataFrame,
    strategy: str = STRATEGY_QUANT_CORE,
    f_score: int = 7,
    mos_pct: float = 20.0,
    z_score: float = 2.5,
    regimes: pd.Series | None = None,
    enforce_regime_gate: bool = False,
) -> pd.Series:
    """Generate sequential trade signals according to selected investment strategy."""
    if df_price.empty or "close" not in df_price.columns:
        return pd.Series(dtype=int)

    close = df_price["close"].astype(float)
    if strategy == STRATEGY_MA_CROSSOVER:
        return _generate_ma_crossover_signals(close)
    if strategy == STRATEGY_RSI_REVERSION:
        return _generate_rsi_reversion_signals(close)
    return _generate_quant_core_signals(
        df_price,
        f_score=f_score,
        mos_pct=mos_pct,
        z_score=z_score,
        regimes=regimes,
        enforce_regime_gate=enforce_regime_gate,
    )




class RegimeBacktestEngine:
    """Deterministic Simulation Engine executing long-only strategies on Vietnam market."""

    def __init__(
        self,
        initial_capital: float = 100_000_000.0,
        fee_rate: float = DEFAULT_FEE_RATE,
        tax_rate: float = DEFAULT_TAX_RATE,
        slippage_bps: float = DEFAULT_SLIPPAGE_BPS,
        max_position_adv_pct: float = 0.05,
    ) -> None:
        self.initial_capital = initial_capital
        self.fee_rate = fee_rate
        self.tax_rate = tax_rate
        self.slippage_bps = slippage_bps
        self.max_position_adv_pct = max_position_adv_pct

    def _process_exit(
        self,
        active_trade: TradeRecord,
        curr_date: Any,
        curr_close: float,
        curr_sig: int,
        entry_idx: int,
        i: int,
        total_bars: int,
        cash: float,
        trades: list[TradeRecord],
    ) -> tuple[TradeRecord | None, float]:
        """Evaluate T+2.5 exit conditions and update active trade."""
        pnl_from_entry = ((curr_close - active_trade.entry_price) / active_trade.entry_price) * 100.0
        active_trade.mfe_pct = max(active_trade.mfe_pct, pnl_from_entry)
        active_trade.mae_pct = min(active_trade.mae_pct, pnl_from_entry)

        stop_loss_hit = (pnl_from_entry <= -7.0)
        is_exit = (curr_sig == -1) or stop_loss_hit or (i == total_bars - 1)

        if not (can_execute_t_plus_2(entry_idx, i) and is_exit):
            return active_trade, cash

        fill_exit = calculate_slippage_price(curr_close, is_buy=False, slippage_bps=self.slippage_bps)
        net_pnl, pnl_pct, _, exit_fee, exit_tax = _calculate_trade_pnl(
            active_trade.entry_price, fill_exit, active_trade.shares, self.fee_rate, self.tax_rate
        )
        active_trade.exit_date = curr_date
        active_trade.exit_price = fill_exit
        active_trade.exit_fee = exit_fee
        active_trade.exit_tax = exit_tax
        active_trade.net_pnl = net_pnl
        active_trade.pnl_pct = pnl_pct
        active_trade.holding_days = i - entry_idx
        if stop_loss_hit:
            active_trade.exit_reason = "STOP_LOSS"
        elif curr_sig == -1:
            active_trade.exit_reason = "SIGNAL"
        else:
            active_trade.exit_reason = "END_OF_DATA"

        cash += (fill_exit * active_trade.shares) - exit_fee - exit_tax
        trades.append(active_trade)
        return None, cash

    def _process_entry(
        self,
        curr_date: Any,
        curr_open: float,
        prev_close: float,
        curr_regime: str,
        i: int,
        cash: float,
        adv20: pd.Series | None,
        symbol: str,
        trades: list[TradeRecord],
    ) -> tuple[TradeRecord | None, float, int]:
        """Evaluate order execution, HOSE ceiling restrictions, and ADV20 limits."""
        if check_hose_ceiling_unfilled(curr_open, prev_close):
            unfilled_record = TradeRecord(
                symbol=symbol,
                entry_date=curr_date,
                entry_price=curr_open,
                shares=0,
                is_filled=False,
                exit_reason="UNFILLED_CEILING",
                regime=curr_regime,
            )
            trades.append(unfilled_record)
            return None, cash, -1

        fill_entry = calculate_slippage_price(curr_open, is_buy=True, slippage_bps=self.slippage_bps)
        allocation_capital = cash * 0.95
        shares = int(allocation_capital // fill_entry)

        if adv20 is not None and i < len(adv20):
            max_shares_adv = int(adv20.iloc[i] * self.max_position_adv_pct)
            if max_shares_adv > 0:
                shares = min(shares, max_shares_adv)

        if shares <= 0:
            return None, cash, -1

        entry_val = fill_entry * shares
        entry_fee = entry_val * self.fee_rate
        cash -= (entry_val + entry_fee)

        active_trade = TradeRecord(
            symbol=symbol,
            entry_date=curr_date,
            entry_price=fill_entry,
            shares=shares,
            entry_fee=entry_fee,
            regime=curr_regime,
            is_filled=True,
        )
        return active_trade, cash, i

    def _resolve_bar_context(
        self,
        i: int,
        close: pd.Series,
        open_p: pd.Series,
        signals: pd.Series,
        regimes: pd.Series | None,
        enforce_regime_gate: bool,
    ) -> tuple[float, float, float, str, int]:
        """Resolve pricing, market regime, and gated signal for the current simulation bar."""
        curr_close = close.iloc[i]
        curr_open = open_p.iloc[i]
        prev_close = close.iloc[i - 1] if i > 0 else curr_open
        curr_regime = regimes.iloc[i] if (regimes is not None and i < len(regimes)) else REGIME_SIDEWAYS
        curr_sig = signals.iloc[i] if i < len(signals) else 0

        # Macro Circuit Breaker (Cash Mode): Suppress buy signals during Downtrend
        if enforce_regime_gate and curr_regime == REGIME_DOWNTREND and curr_sig == 1:
            curr_sig = 0

        return curr_close, curr_open, prev_close, curr_regime, curr_sig

    def _execute_bar_transition(
        self,
        i: int,
        curr_date: Any,
        bar_ctx: tuple[float, float, float, str, int],
        pos_state: tuple[TradeRecord | None, float, int],
        total_bars: int,
        adv20: pd.Series | None,
        symbol: str,
        trades: list[TradeRecord],
    ) -> tuple[TradeRecord | None, float, int]:
        """Process exit or entry for active/new position at the current bar."""
        curr_close, curr_open, prev_close, curr_regime, curr_sig = bar_ctx
        active_trade, cash, entry_idx = pos_state

        if active_trade is not None:
            active_trade, cash = self._process_exit(
                active_trade, curr_date, curr_close, curr_sig, entry_idx, i, total_bars, cash, trades
            )
            return active_trade, cash, entry_idx

        if curr_sig == 1 and cash > 0:
            new_trade, cash, new_idx = self._process_entry(
                curr_date, curr_open, prev_close, curr_regime, i, cash, adv20, symbol, trades
            )
            if new_trade is not None:
                return new_trade, cash, new_idx

        return None, cash, entry_idx

    def run_backtest(
        self,
        df_price: pd.DataFrame,
        signals: pd.Series,
        regimes: pd.Series | None = None,
        adv20: pd.Series | None = None,
        benchmark_returns: pd.Series | None = None,
        symbol: str = "TEST",
        enforce_regime_gate: bool = False,
    ) -> BacktestResult:
        """Run sequential backtest honoring HOSE ceiling, T+2.5, stop-loss, and liquidation rules."""
        if df_price.empty or "close" not in df_price.columns:
            return BacktestResult()

        trades: list[TradeRecord] = []
        equity = [self.initial_capital]
        cash = self.initial_capital
        active_trade: TradeRecord | None = None
        entry_idx: int = -1

        close = df_price["close"].astype(float)
        open_p = df_price["open"].astype(float) if "open" in df_price.columns else close
        total_bars = len(df_price)

        for i in range(total_bars):
            curr_date = df_price.index[i]
            bar_ctx = self._resolve_bar_context(
                i, close, open_p, signals, regimes, enforce_regime_gate
            )

            active_trade, cash, entry_idx = self._execute_bar_transition(
                i, curr_date, bar_ctx, (active_trade, cash, entry_idx),
                total_bars, adv20, symbol, trades
            )

            curr_close = bar_ctx[0]
            curr_pos_val = (active_trade.shares * curr_close) if active_trade else 0.0
            equity.append(cash + curr_pos_val)

        equity_curve = pd.Series(equity[1:], index=df_price.index)
        summary = calculate_performance_metrics(trades, equity_curve, benchmark_returns)
        regime_break = breakdown_by_regime(trades, equity_curve, benchmark_returns, regimes)

        return BacktestResult(
            trades=trades,
            equity_curve=equity_curve,
            summary_metrics=summary,
            regime_metrics=regime_break,
        )
