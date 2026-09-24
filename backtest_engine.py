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
    profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else (99.0 if gross_profit > 0 else 0.0)

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
    if benchmark_returns is None or benchmark_returns.empty:
        return 0.0, 1.0

    aligned = pd.concat([returns, benchmark_returns], axis=1, join="inner").dropna()
    if len(aligned) < 20:
        return 0.0, 1.0

    ret_strat = aligned.iloc[:, 0]
    ret_bench = aligned.iloc[:, 1]

    cov_matrix = np.cov(ret_strat, ret_bench)
    bench_var = cov_matrix[1, 1]
    if bench_var == 0:
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
) -> dict[str, dict[str, Any]]:
    """Partition performance metrics across market regimes: Full, Uptrend, Downtrend, Sideways."""
    breakdown: dict[str, dict[str, Any]] = {}

    # 1. Full metrics
    breakdown[REGIME_FULL] = calculate_performance_metrics(trades, equity_curve, benchmark_returns)

    # 2. Per-regime trade subsets
    for reg in (REGIME_UPTREND, REGIME_DOWNTREND, REGIME_SIDEWAYS):
        sub_trades = [t for t in trades if t.regime == reg]
        breakdown[reg] = calculate_performance_metrics(sub_trades, pd.Series([1.0, 1.0]))
        # Note: Equity curve per regime is isolated to trade metrics

    return breakdown


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

    def run_backtest(
        self,
        df_price: pd.DataFrame,
        signals: pd.Series,
        regimes: pd.Series | None = None,
        adv20: pd.Series | None = None,
    ) -> BacktestResult:
        """Run sequential backtest honoring HOSE ceiling, T+2.5, and liquidation rules."""
        if df_price.empty or "close" not in df_price.columns:
            return BacktestResult()

        trades: list[TradeRecord] = []
        equity = [self.initial_capital]
        cash = self.initial_capital
        active_trade: TradeRecord | None = None
        entry_idx: int = -1

        close = df_price["close"].astype(float)
        open_p = df_price["open"].astype(float) if "open" in df_price.columns else close

        for i in range(len(df_price)):
            curr_date = df_price.index[i]
            curr_close = close.iloc[i]
            curr_open = open_p.iloc[i]
            prev_close = close.iloc[i - 1] if i > 0 else curr_open
            curr_regime = regimes.iloc[i] if (regimes is not None and i < len(regimes)) else REGIME_SIDEWAYS
            curr_sig = signals.iloc[i] if i < len(signals) else 0

            # 1. Check existing position exit (Only allowed starting afternoon of T+2)
            if active_trade is not None:
                active_trade.mfe_pct = max(active_trade.mfe_pct, ((curr_close - active_trade.entry_price) / active_trade.entry_price) * 100.0)
                active_trade.mae_pct = min(active_trade.mae_pct, ((curr_close - active_trade.entry_price) / active_trade.entry_price) * 100.0)

                # Check T+2.5 condition
                if can_execute_t_plus_2(entry_idx, i) and (curr_sig == -1 or i == len(df_price) - 1):
                    # Execute sell
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
                    active_trade.exit_reason = "SIGNAL" if curr_sig == -1 else "END_OF_DATA"

                    cash += (fill_exit * active_trade.shares) - exit_fee - exit_tax
                    trades.append(active_trade)
                    active_trade = None

            # 2. Check buy signal if no active position
            elif curr_sig == 1 and cash > 0:
                # Check HOSE ceiling limit
                if check_hose_ceiling_unfilled(curr_open, prev_close):
                    # Cannot buy if kịch trần
                    unfilled_record = TradeRecord(
                        symbol="TEST",
                        entry_date=curr_date,
                        entry_price=curr_open,
                        shares=0,
                        is_filled=False,
                        exit_reason="UNFILLED_CEILING",
                        regime=curr_regime,
                    )
                    trades.append(unfilled_record)
                else:
                    # Execute buy
                    fill_entry = calculate_slippage_price(curr_open, is_buy=True, slippage_bps=self.slippage_bps)
                    allocation_capital = cash * 0.95  # 95% allocated
                    shares = int(allocation_capital // fill_entry)

                    # Check ADV20 cap if provided
                    if adv20 is not None and i < len(adv20):
                        max_shares_adv = int(adv20.iloc[i] * self.max_position_adv_pct)
                        if max_shares_adv > 0:
                            shares = min(shares, max_shares_adv)

                    if shares > 0:
                        entry_val = fill_entry * shares
                        entry_fee = entry_val * self.fee_rate
                        cash -= (entry_val + entry_fee)

                        active_trade = TradeRecord(
                            symbol="TEST",
                            entry_date=curr_date,
                            entry_price=fill_entry,
                            shares=shares,
                            entry_fee=entry_fee,
                            regime=curr_regime,
                            is_filled=True,
                        )
                        entry_idx = i

            # Update daily portfolio equity
            curr_pos_val = (active_trade.shares * curr_close) if active_trade else 0.0
            equity.append(cash + curr_pos_val)

        equity_curve = pd.Series(equity[1:], index=df_price.index)
        summary = calculate_performance_metrics(trades, equity_curve)
        regime_break = breakdown_by_regime(trades, equity_curve)

        return BacktestResult(
            trades=trades,
            equity_curve=equity_curve,
            summary_metrics=summary,
            regime_metrics=regime_break,
        )
