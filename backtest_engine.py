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

# Walk-Forward Timeline Constants (Phase 3a)
WALK_FORWARD_WINDOWS: Final[dict[str, tuple[str, str]]] = {
    "training": ("2018-01-01", "2019-12-31"),
    "validation": ("2020-01-01", "2021-12-31"),
    "oos": ("2022-01-01", "2024-12-31"),
}

# Crisis Stress Backtest Scenarios (Phase 3b - 11 Historical Events 2018–2024)
CRISIS_STRESS_REGIMES: Final[dict[str, dict[str, Any]]] = {
    "trade_war_2018": {
        "name": "Chiến tranh thương mại Mỹ - Trung (2018)",
        "start_date": "2018-03-01",
        "end_date": "2018-12-31",
        "market_drop_pct": -25.0,
    },
    "trump_tariff_2019": {
        "name": "Trump Tariff – 20 ngày đỏ lửa Thiên nga đen",
        "start_date": "2019-05-05",
        "end_date": "2019-05-31",
        "market_drop_pct": -5.0,
    },
    "covid_crash_2020": {
        "name": "Bùng phát đại dịch Covid-19 (2020)",
        "start_date": "2020-01-23",
        "end_date": "2020-03-31",
        "market_drop_pct": -35.0,
    },
    "covid_lockdown_2021": {
        "name": "Giãn cách xã hội nghiêm ngặt do Covid-19 (Delta 2021)",
        "start_date": "2021-07-09",
        "end_date": "2021-09-30",
        "market_drop_pct": -14.0,
    },
    "bull_market_2021": {
        "name": "Sóng Bull Market Bong bóng F0 (2021)",
        "start_date": "2021-01-01",
        "end_date": "2021-12-31",
        "market_drop_pct": 150.0,
    },
    "bond_crackdown_2022": {
        "name": "Sự kiện vi phạm TTCK & Trái phiếu doanh nghiệp (2022)",
        "start_date": "2022-03-29",
        "end_date": "2022-05-31",
        "market_drop_pct": -23.0,
    },
    "rate_hike_2022": {
        "name": "NHNN thắt chặt tiền tệ, tăng lãi suất sau nhiều năm (2022)",
        "start_date": "2022-09-23",
        "end_date": "2022-12-31",
        "market_drop_pct": -20.0,
    },
    "van_thinh_phat_2022": {
        "name": "Sự kiện Vạn Thịnh Phát & Ngân hàng SCB (2022)",
        "start_date": "2022-10-06",
        "end_date": "2022-11-16",
        "market_drop_pct": -25.0,
    },
    "fx_bill_tightening_2023": {
        "name": "Khối ngoại bán ròng kỷ lục & Hút tín phiếu SBV (Q3/2023)",
        "start_date": "2023-07-01",
        "end_date": "2023-09-30",
        "market_drop_pct": -18.0,
    },
    "fx_dxy_pressure_2024": {
        "name": "Đồng USD tăng giá mạnh & Tỷ giá kỷ lục (Q2/2024)",
        "start_date": "2024-04-01",
        "end_date": "2024-06-30",
        "market_drop_pct": -10.0,
    },
    "liquidity_dry_2024": {
        "name": "Sụt giảm thanh khoản, khối ngoại bán ròng và áp lực tỷ giá (Q3/2024)",
        "start_date": "2024-07-01",
        "end_date": "2024-09-30",
        "market_drop_pct": -5.0,
    },
}

# Historical Flash Crash Dates (Point drop >= 50 or single day >= 4%)
HISTORICAL_FLASH_CRASH_DATES: Final[list[str]] = [
    "2015-08-24",
    "2018-02-05",
    "2020-03-09",
    "2021-01-19",
    "2021-01-28",  # -73 pts
    "2022-04-25",  # -68 pts
    "2022-05-12",  # -62 pts
    "2023-08-18",  # -55 pts
    "2024-04-15",  # -60 pts
]

KEY_START_DATE: Final[str] = "start_date"
KEY_END_DATE: Final[str] = "end_date"
KEY_STATUS: Final[str] = "status"
KEY_NO_DATA: Final[str] = "NO_DATA"
KEY_MARKET_DROP: Final[str] = "market_drop_pct"


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
    bps_factor = slippage_bps / 10000.0
    if is_buy:
        return price * (1.0 + bps_factor)
    return price * (1.0 - bps_factor)


def calculate_dynamic_slippage_bps(
    is_buy: bool,
    vol_ratio: float = 1.0,
    is_floor: bool = False,
    is_ceiling: bool = False,
    adv20_billion: float = 10.0,
    order_size_billion: float = 0.1,
) -> float:
    """Tính toán trượt giá động (Dynamic Slippage - Phase 2b) thay thế 15 bps cố định.

    - Base slippage: 15.0 bps.
    - Kịch trần & Mua: x4.0 (60 bps) do tranh mua trần khó khớp.
    - Kịch sàn & Bán: x5.0 (75 bps) do mất thanh khoản trắng bên mua.
    - Cạn kiệt thanh khoản (vol_ratio < 0.5): x2.0 base.
    - Khối lượng giao dịch đột biến (vol_ratio > 3.0): x1.5 base.
    - Tác động lệnh lớn (> 5% ADV20): tăng thêm theo tỷ trọng.
    - Giới hạn: trần tối đa 200 bps.
    """
    base_bps = DEFAULT_SLIPPAGE_BPS

    if is_ceiling and is_buy:
        base_bps *= 4.0
    elif is_floor and not is_buy:
        base_bps *= 5.0

    if vol_ratio < 0.5:
        base_bps *= 2.0
    elif vol_ratio > 3.0:
        base_bps *= 1.5

    if adv20_billion > 0:
        order_pct_adv = order_size_billion / adv20_billion
        if order_pct_adv > 0.05:
            base_bps *= 1.0 + order_pct_adv * 3.0

    return min(round(base_bps, 2), 200.0)


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

    buy_prev = buy_cond.shift(1, fill_value=False)
    buy_trigger = buy_cond & (~buy_prev)

    # Sell: Overbought climax or breakdown below MA20 * 0.95
    sell_cond = (rsi >= 75) | (close < ma20 * 0.95)
    sell_prev = sell_cond.shift(1, fill_value=False)
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

        stop_loss_hit = pnl_from_entry <= -7.0
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
        cash -= entry_val + entry_fee

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

        signals = signals.shift(1).fillna(0)

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
            bar_ctx = self._resolve_bar_context(i, close, open_p, signals, regimes, enforce_regime_gate)

            active_trade, cash, entry_idx = self._execute_bar_transition(
                i, curr_date, bar_ctx, (active_trade, cash, entry_idx), total_bars, adv20, symbol, trades
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


BacktestEngine = RegimeBacktestEngine


def _slice_by_dates(
    df_price: pd.DataFrame,
    start_date: str,
    end_date: str,
    signals: pd.Series | None = None,
    regimes: pd.Series | None = None,
    adv20: pd.Series | None = None,
    benchmark_returns: pd.Series | None = None,
) -> tuple[pd.DataFrame, pd.Series | None, pd.Series | None, pd.Series | None, pd.Series | None]:
    """Slice price history and auxiliary series within [start_date, end_date]."""
    if df_price.empty:
        return df_price, signals, regimes, adv20, benchmark_returns

    try:
        idx = pd.to_datetime(df_price.index)
        mask = (idx >= pd.to_datetime(start_date)) & (idx <= pd.to_datetime(end_date))
        sub_price = df_price.loc[mask]
    except Exception:
        sub_price = df_price.loc[start_date:end_date]

    def _slice_series(s: pd.Series | None) -> pd.Series | None:
        if s is None or s.empty:
            return s
        try:
            s_idx = pd.to_datetime(s.index)
            s_mask = (s_idx >= pd.to_datetime(start_date)) & (s_idx <= pd.to_datetime(end_date))
            return s.loc[s_mask]
        except Exception:
            return s.loc[start_date:end_date]

    return (
        sub_price,
        _slice_series(signals),
        _slice_series(regimes),
        _slice_series(adv20),
        _slice_series(benchmark_returns),
    )


def run_walk_forward_backtest(
    engine: RegimeBacktestEngine,
    df_price: pd.DataFrame,
    signals: pd.Series,
    regimes: pd.Series | None = None,
    adv20: pd.Series | None = None,
    benchmark_returns: pd.Series | None = None,
    symbol: str = "TEST",
    enforce_regime_gate: bool = False,
    windows: dict[str, tuple[str, str]] | None = None,
) -> dict[str, Any]:
    """Chạy kiểm định Walk-Forward phân tách Training, Validation và OOS (Phase 3a)."""
    target_windows = windows or WALK_FORWARD_WINDOWS
    results_by_window: dict[str, BacktestResult] = {}
    metrics_comparison: dict[str, dict[str, Any]] = {}

    for win_name, (start_dt, end_dt) in target_windows.items():
        sub_p, sub_sig, sub_reg, sub_adv, sub_bm = _slice_by_dates(
            df_price, start_dt, end_dt, signals, regimes, adv20, benchmark_returns
        )
        if sub_p.empty or (sub_sig is not None and sub_sig.empty):
            results_by_window[win_name] = BacktestResult()
            metrics_comparison[win_name] = {
                KEY_START_DATE: start_dt,
                KEY_END_DATE: end_dt,
                KEY_STATUS: KEY_NO_DATA,
            }
            continue

        res = engine.run_backtest(
            df_price=sub_p,
            signals=sub_sig,
            regimes=sub_reg,
            adv20=sub_adv,
            benchmark_returns=sub_bm,
            symbol=symbol,
            enforce_regime_gate=enforce_regime_gate,
        )
        results_by_window[win_name] = res
        sm = res.summary_metrics
        metrics_comparison[win_name] = {
            KEY_START_DATE: start_dt,
            KEY_END_DATE: end_dt,
            "total_trades": sm.get("total_trades", 0),
            "win_rate_pct": sm.get("win_rate_pct", 0.0),
            "cagr_pct": sm.get("cagr_pct", 0.0),
            "sharpe_ratio": sm.get("sharpe_ratio", 0.0),
            "max_drawdown_pct": sm.get("max_drawdown_pct", 0.0),
            "profit_factor": sm.get("profit_factor", 0.0),
        }

    return {
        "results_by_window": results_by_window,
        "metrics_comparison": metrics_comparison,
    }


def run_crisis_stress_matrix(
    engine: RegimeBacktestEngine,
    df_price: pd.DataFrame,
    signals: pd.Series,
    regimes: pd.Series | None = None,
    adv20: pd.Series | None = None,
    benchmark_returns: pd.Series | None = None,
    symbol: str = "TEST",
    enforce_regime_gate: bool = False,
    stress_regimes: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Chạy ma trận kiểm tra áp lực khủng hoảng qua 4 kịch bản sập lịch sử (Phase 3b)."""
    regimes_map = stress_regimes or CRISIS_STRESS_REGIMES
    period_results: dict[str, BacktestResult] = {}
    stress_summary: dict[str, dict[str, Any]] = {}

    for key, info in regimes_map.items():
        start_dt = info[KEY_START_DATE]
        end_dt = info[KEY_END_DATE]
        sub_p, sub_sig, sub_reg, sub_adv, sub_bm = _slice_by_dates(
            df_price, start_dt, end_dt, signals, regimes, adv20, benchmark_returns
        )

        if sub_p.empty or (sub_sig is not None and sub_sig.empty):
            period_results[key] = BacktestResult()
            stress_summary[key] = {
                "name": info["name"],
                KEY_MARKET_DROP: info.get(KEY_MARKET_DROP, 0.0),
                KEY_STATUS: KEY_NO_DATA,
            }
            continue

        res = engine.run_backtest(
            df_price=sub_p,
            signals=sub_sig,
            regimes=sub_reg,
            adv20=sub_adv,
            benchmark_returns=sub_bm,
            symbol=symbol,
            enforce_regime_gate=enforce_regime_gate,
        )
        period_results[key] = res
        sm = res.summary_metrics

        ret_pct = 0.0
        if not res.equity_curve.empty and res.equity_curve.iloc[0] > 0:
            ret_pct = round(((res.equity_curve.iloc[-1] / res.equity_curve.iloc[0]) - 1.0) * 100.0, 2)

        stress_summary[key] = {
            "name": info["name"],
            KEY_START_DATE: start_dt,
            KEY_END_DATE: end_dt,
            KEY_MARKET_DROP: info.get(KEY_MARKET_DROP, 0.0),
            "strategy_return_pct": ret_pct,
            "max_drawdown_pct": sm.get("max_drawdown_pct", 0.0),
            "total_trades": sm.get("total_trades", 0),
            "win_rate_pct": sm.get("win_rate_pct", 0.0),
            "profit_factor": sm.get("profit_factor", 0.0),
        }

    return {
        "period_results": period_results,
        "stress_summary": stress_summary,
    }


def scan_market_stress_events(
    df_benchmark: pd.DataFrame,
    point_drop_threshold: float = 50.0,
    pct_drop_threshold: float = 0.04,
    rolling_window: int = 20,
    rolling_drawdown_threshold: float = 0.10,
) -> dict[str, Any]:
    """Quét các sự kiện căng thẳng định lượng trên chỉ số VN-Index (Flash crash, % sụt giảm, đợt sập dốc)."""
    if df_benchmark.empty or "close" not in df_benchmark.columns:
        return {
            "drop_50pts_days": [],
            "drop_4pct_days": [],
            "sharp_drawdown_clusters": [],
            "total_stress_days": 0,
        }

    close = df_benchmark["close"].astype(float)
    point_diff = close.diff()
    pct_diff = close.pct_change()

    # 1. Flash crashes >= 50 points
    mask_pts = point_diff <= -abs(point_drop_threshold)
    drop_pts = [
        {"date": str(idx)[:10], "drop_points": round(float(val), 2), "close": round(float(c), 2)}
        for idx, val, c in zip(close.index[mask_pts], point_diff[mask_pts], close[mask_pts])
    ]

    # 2. Flash drops >= 4%
    mask_pct = pct_diff <= -abs(pct_drop_threshold)
    drop_pcts = [
        {"date": str(idx)[:10], "pct_change": round(float(val) * 100.0, 2), "close": round(float(c), 2)}
        for idx, val, c in zip(close.index[mask_pct], pct_diff[mask_pct], close[mask_pct])
    ]

    # 3. Rolling drawdown >= 10% trong vòng <= rolling_window phiên
    roll_max = close.rolling(rolling_window, min_periods=5).max()
    roll_dd = (close - roll_max) / roll_max
    mask_dd = roll_dd <= -abs(rolling_drawdown_threshold)
    dd_clusters = [
        {"date": str(idx)[:10], "rolling_drawdown_pct": round(float(dd) * 100.0, 2)}
        for idx, dd in zip(close.index[mask_dd], roll_dd[mask_dd])
    ]

    unique_dates = {d["date"] for d in drop_pts} | {d["date"] for d in drop_pcts}

    return {
        "drop_50pts_days": drop_pts,
        "drop_4pct_days": drop_pcts,
        "sharp_drawdown_clusters": dd_clusters,
        "total_stress_days": len(unique_dates),
    }


# =============================================================================
# PHASE 7d: EXIT HYPOTHESIS LAB (RESEARCH / REPORT-ONLY)
# =============================================================================

POLICY_A: Final[str] = "POLICY_A"  # Baseline: Lãi >= +12% chốt 50%, dời SL về BE (+0.3%)
POLICY_B: Final[str] = "POLICY_B"  # R-Multiple: Lãi >= +2R chốt 50%, dời SL lên +0.5R
POLICY_C: Final[str] = "POLICY_C"  # ATR Trailing: Trailing Stop liên tục 2.5 * ATR(14)
POLICY_D: Final[str] = "POLICY_D"  # All-or-Nothing: Giữ 100% đến Target 2 hoặc Hard Stop

EXIT_LAB_REPORT_DISCLAIMER: Final[str] = (
    "Kết quả từ Exit Hypothesis Lab chỉ phục vụ nghiên cứu và kiểm định học thuật (Report-Only). "
    "Nghiêm cấm tự ý thay đổi quy tắc thoát lệnh trên hệ thống live khi chưa có ADR mới được ký duyệt."
)


def _compute_bar_atr(bar: pd.Series, prev_close: float) -> float:
    """Helper to extract or approximate ATR(14) from bar."""
    if "atr14" in bar and pd.notna(bar["atr14"]) and float(bar["atr14"]) > 0:
        return float(bar["atr14"])
    high = float(bar.get("high", 0.0))
    low = float(bar.get("low", 0.0))
    tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
    return tr if tr > 0 else (high * 0.02)


def _simulate_policy_a(
    entry_price: float, initial_stop: float, target_price: float, ohlc_df: pd.DataFrame
) -> dict[str, Any]:
    """Policy A: Lãi >= +12% chốt 50%, dời Stop-Loss về Breakeven (+0.3% phí)."""
    r_val = max(entry_price - initial_stop, entry_price * 0.07)
    stop_price = initial_stop
    partial_done = False
    realized_cash_pnl = 0.0
    remaining_size = 1.0
    exit_reason = "BARS_EXHAUSTED"
    bars_held = len(ohlc_df)
    mfe = 0.0
    mae = 0.0

    for idx, (_, bar) in enumerate(ohlc_df.iterrows()):
        high = float(bar["high"])
        low = float(bar["low"])
        close = float(bar["close"])
        mfe = max(mfe, (high - entry_price) / entry_price)
        mae = min(mae, (low - entry_price) / entry_price)

        # 1. Conservative Check: Stop hit first
        if low <= stop_price:
            realized_cash_pnl += remaining_size * (stop_price - entry_price)
            exit_reason = "BREAKEVEN_STOP" if partial_done else "STOPPED_OUT"
            bars_held = idx + 1
            remaining_size = 0.0
            break

        # 2. Check Partial Profit +12%
        if not partial_done and high >= entry_price * 1.12:
            partial_exit_px = entry_price * 1.12
            realized_cash_pnl += 0.50 * (partial_exit_px - entry_price)
            remaining_size = 0.50
            partial_done = True
            stop_price = entry_price * 1.003  # BE + 0.3%

        # 3. Check Target Hit for remaining
        if high >= target_price:
            realized_cash_pnl += remaining_size * (target_price - entry_price)
            exit_reason = "TARGET_HIT"
            bars_held = idx + 1
            remaining_size = 0.0
            break

    if remaining_size > 0 and len(ohlc_df) > 0:
        last_close = float(ohlc_df.iloc[-1]["close"])
        realized_cash_pnl += remaining_size * (last_close - entry_price)

    pnl_pct = (realized_cash_pnl / entry_price) * 100.0
    r_mult = realized_cash_pnl / r_val
    return {
        "policy": POLICY_A,
        "pnl_pct": round(pnl_pct, 2),
        "r_multiple": round(r_mult, 2),
        "holding_bars": bars_held,
        "exit_reason": exit_reason,
        "mfe_pct": round(mfe * 100.0, 2),
        "mae_pct": round(mae * 100.0, 2),
    }


def _simulate_policy_b(
    entry_price: float, initial_stop: float, target_price: float, ohlc_df: pd.DataFrame
) -> dict[str, Any]:
    """Policy B: R-Multiple (Lãi >= +2R chốt 50%, dời SL lên +0.5R)."""
    r_val = max(entry_price - initial_stop, entry_price * 0.07)
    trigger_price = entry_price + 2.0 * r_val
    new_stop_price = entry_price + 0.5 * r_val
    stop_price = initial_stop
    partial_done = False
    realized_cash_pnl = 0.0
    remaining_size = 1.0
    exit_reason = "BARS_EXHAUSTED"
    bars_held = len(ohlc_df)
    mfe = 0.0
    mae = 0.0

    for idx, (_, bar) in enumerate(ohlc_df.iterrows()):
        high = float(bar["high"])
        low = float(bar["low"])
        close = float(bar["close"])
        mfe = max(mfe, (high - entry_price) / entry_price)
        mae = min(mae, (low - entry_price) / entry_price)

        if low <= stop_price:
            realized_cash_pnl += remaining_size * (stop_price - entry_price)
            exit_reason = "R_TRAILING_STOP" if partial_done else "STOPPED_OUT"
            bars_held = idx + 1
            remaining_size = 0.0
            break

        if not partial_done and high >= trigger_price:
            realized_cash_pnl += 0.50 * (trigger_price - entry_price)
            remaining_size = 0.50
            partial_done = True
            stop_price = new_stop_price

        if high >= target_price:
            realized_cash_pnl += remaining_size * (target_price - entry_price)
            exit_reason = "TARGET_HIT"
            bars_held = idx + 1
            remaining_size = 0.0
            break

    if remaining_size > 0 and len(ohlc_df) > 0:
        last_close = float(ohlc_df.iloc[-1]["close"])
        realized_cash_pnl += remaining_size * (last_close - entry_price)

    pnl_pct = (realized_cash_pnl / entry_price) * 100.0
    r_mult = realized_cash_pnl / r_val
    return {
        "policy": POLICY_B,
        "pnl_pct": round(pnl_pct, 2),
        "r_multiple": round(r_mult, 2),
        "holding_bars": bars_held,
        "exit_reason": exit_reason,
        "mfe_pct": round(mfe * 100.0, 2),
        "mae_pct": round(mae * 100.0, 2),
    }


def _simulate_policy_c(
    entry_price: float, initial_stop: float, ohlc_df: pd.DataFrame, atr_multiplier: float = 2.5
) -> dict[str, Any]:
    """Policy C: ATR Trailing Stop liên tục (Highest High - 2.5 * ATR14)."""
    r_val = max(entry_price - initial_stop, entry_price * 0.07)
    highest_high = entry_price
    stop_price = initial_stop
    exit_price = entry_price
    exit_reason = "BARS_EXHAUSTED"
    bars_held = len(ohlc_df)
    prev_close = entry_price
    mfe = 0.0
    mae = 0.0

    for idx, (_, bar) in enumerate(ohlc_df.iterrows()):
        high = float(bar["high"])
        low = float(bar["low"])
        close = float(bar["close"])
        mfe = max(mfe, (high - entry_price) / entry_price)
        mae = min(mae, (low - entry_price) / entry_price)

        # 1. Check if low breached current stop established prior to or at start of bar
        if low <= stop_price:
            exit_price = stop_price
            exit_reason = "TRAILING_STOP" if stop_price > initial_stop else "STOPPED_OUT"
            bars_held = idx + 1
            break

        # 2. Update trailing stop for subsequent bars based on new peak
        atr_val = _compute_bar_atr(bar, prev_close)
        highest_high = max(highest_high, high)
        dynamic_trail = highest_high - atr_multiplier * atr_val
        stop_price = max(stop_price, dynamic_trail)

        prev_close = close
        exit_price = close

    realized_cash_pnl = exit_price - entry_price
    pnl_pct = (realized_cash_pnl / entry_price) * 100.0
    r_mult = realized_cash_pnl / r_val
    return {
        "policy": POLICY_C,
        "pnl_pct": round(pnl_pct, 2),
        "r_multiple": round(r_mult, 2),
        "holding_bars": bars_held,
        "exit_reason": exit_reason,
        "mfe_pct": round(mfe * 100.0, 2),
        "mae_pct": round(mae * 100.0, 2),
    }


def _simulate_policy_d(
    entry_price: float, initial_stop: float, target_price: float, ohlc_df: pd.DataFrame
) -> dict[str, Any]:
    """Policy D: All-or-Nothing (Giữ 100% đến Target 2 hoặc Hard Stop)."""
    r_val = max(entry_price - initial_stop, entry_price * 0.07)
    exit_price = entry_price
    exit_reason = "BARS_EXHAUSTED"
    bars_held = len(ohlc_df)
    mfe = 0.0
    mae = 0.0

    for idx, (_, bar) in enumerate(ohlc_df.iterrows()):
        high = float(bar["high"])
        low = float(bar["low"])
        close = float(bar["close"])
        mfe = max(mfe, (high - entry_price) / entry_price)
        mae = min(mae, (low - entry_price) / entry_price)

        if low <= initial_stop:
            exit_price = initial_stop
            exit_reason = "STOPPED_OUT"
            bars_held = idx + 1
            break

        if high >= target_price:
            exit_price = target_price
            exit_reason = "TARGET_HIT"
            bars_held = idx + 1
            break

        exit_price = close

    realized_cash_pnl = exit_price - entry_price
    pnl_pct = (realized_cash_pnl / entry_price) * 100.0
    r_mult = realized_cash_pnl / r_val
    return {
        "policy": POLICY_D,
        "pnl_pct": round(pnl_pct, 2),
        "r_multiple": round(r_mult, 2),
        "holding_bars": bars_held,
        "exit_reason": exit_reason,
        "mfe_pct": round(mfe * 100.0, 2),
        "mae_pct": round(mae * 100.0, 2),
    }


def simulate_exit_policy(
    entry_price: float,
    initial_stop: float,
    target_price: float,
    ohlc_df: pd.DataFrame,
    policy: str = "A",
    atr_multiplier: float = 2.5,
) -> dict[str, Any]:
    """Mô phỏng đường đi của 1 vị thế theo 4 chiến lược thoát lệnh (Phase 7d).

    Hỗ trợ 4 policy:
    - 'A': Chốt 50% tại +12%, dời Stop-Loss về Breakeven (+0.3% phí).
    - 'B': Chốt 50% tại +2R, dời Stop-Loss lên +0.5R.
    - 'C': ATR Trailing Stop liên tục 2.5 * ATR(14).
    - 'D': All-or-Nothing (100% đến Target hoặc Hard Stop).
    """
    if ohlc_df is None or ohlc_df.empty or entry_price <= 0:
        return {
            "policy": policy,
            "pnl_pct": 0.0,
            "r_multiple": 0.0,
            "holding_bars": 0,
            "exit_reason": "INVALID_DATA",
            "mfe_pct": 0.0,
            "mae_pct": 0.0,
        }

    pol_upper = str(policy).upper().strip()
    if pol_upper in ("A", POLICY_A):
        return _simulate_policy_a(entry_price, initial_stop, target_price, ohlc_df)
    if pol_upper in ("B", POLICY_B):
        return _simulate_policy_b(entry_price, initial_stop, target_price, ohlc_df)
    if pol_upper in ("C", POLICY_C):
        return _simulate_policy_c(entry_price, initial_stop, ohlc_df, atr_multiplier)
    if pol_upper in ("D", POLICY_D):
        return _simulate_policy_d(entry_price, initial_stop, target_price, ohlc_df)

    return _simulate_policy_a(entry_price, initial_stop, target_price, ohlc_df)


def _compute_policy_summary(results: list[dict[str, Any]]) -> dict[str, Any]:
    """Helper calculating performance summary for a policy result set."""
    if not results:
        return {
            "expectancy_r": 0.0,
            "win_rate_pct": 0.0,
            "total_pnl_pct": 0.0,
            "max_drawdown_pct": 0.0,
            "avg_bars": 0.0,
        }
    r_vals = [r["r_multiple"] for r in results]
    pnl_vals = [r["pnl_pct"] for r in results]
    bars = [r["holding_bars"] for r in results]

    cum_pnl = np.cumsum(pnl_vals)
    peak = np.maximum.accumulate(cum_pnl)
    drawdowns = peak - cum_pnl
    max_dd = float(np.max(drawdowns)) if len(drawdowns) > 0 else 0.0

    return {
        "expectancy_r": round(float(np.mean(r_vals)), 3),
        "win_rate_pct": round(float(sum(1 for p in pnl_vals if p > 0) / len(pnl_vals) * 100.0), 2),
        "total_pnl_pct": round(float(sum(pnl_vals)), 2),
        "max_drawdown_pct": round(max_dd, 2),
        "avg_bars": round(float(np.mean(bars)), 1),
    }


def run_exit_hypothesis_lab(
    signals_with_ohlc: list[dict[str, Any]],
    n_bootstrap: int = 1_000,
    random_state: int = 42,
) -> dict[str, Any]:
    """Exit Hypothesis Lab (Phase 7d - Research / Report-Only).

    Thực hiện Replay song song 4 chiến lược thoát lệnh (A, B, C, D) trên cùng tập lệnh thực tế.
    Áp dụng Paired Bootstrap để đối chiếu phân phối R-Expectancy và tính p-value so với Baseline A.
    """
    if not signals_with_ohlc:
        return {
            "status": "EMPTY_DATA",
            "report_only": True,
            "disclaimer": EXIT_LAB_REPORT_DISCLAIMER,
            "policies": {},
            "paired_bootstrap": {},
            "sample_size": 0,
        }

    policy_results: dict[str, list[dict[str, Any]]] = {
        POLICY_A: [],
        POLICY_B: [],
        POLICY_C: [],
        POLICY_D: [],
    }

    for sig in signals_with_ohlc:
        ep = float(sig.get("entry_price", 0.0))
        sl = float(sig.get("initial_stop", ep * 0.93))
        tp = float(sig.get("target_price", ep * 1.20))
        df = sig.get("ohlc_df")
        if df is None or not isinstance(df, pd.DataFrame) or df.empty:
            continue

        for pol in (POLICY_A, POLICY_B, POLICY_C, POLICY_D):
            res = simulate_exit_policy(ep, sl, tp, df, policy=pol)
            policy_results[pol].append(res)

    sample_size = len(policy_results[POLICY_A])
    if sample_size == 0:
        return {
            "status": "NO_VALID_TRADES",
            "report_only": True,
            "disclaimer": EXIT_LAB_REPORT_DISCLAIMER,
            "policies": {},
            "paired_bootstrap": {},
            "sample_size": 0,
        }

    summaries = {pol: _compute_policy_summary(res_list) for pol, res_list in policy_results.items()}

    # Paired Bootstrap against Policy A
    rng = np.random.default_rng(random_state)
    paired_bootstrap_res: dict[str, Any] = {}
    r_a = np.array([r["r_multiple"] for r in policy_results[POLICY_A]])

    for pol in (POLICY_B, POLICY_C, POLICY_D):
        r_x = np.array([r["r_multiple"] for r in policy_results[pol]])
        diffs = np.zeros(n_bootstrap, dtype=float)

        for b in range(n_bootstrap):
            idx = rng.integers(0, sample_size, size=sample_size)
            diffs[b] = float(np.mean(r_x[idx]) - np.mean(r_a[idx]))

        ci_lower = float(np.percentile(diffs, 2.5))
        ci_upper = float(np.percentile(diffs, 97.5))
        p_val = float(np.mean(diffs <= 0.0))  # H0: Delta Expectancy <= 0

        paired_bootstrap_res[pol] = {
            "delta_expectancy_r": round(float(np.mean(diffs)), 3),
            "ci_95": (round(ci_lower, 3), round(ci_upper, 3)),
            "p_value_superiority": round(p_val, 4),
            "is_significantly_better": bool(ci_lower > 0.0 and p_val < 0.05),
        }

    return {
        "status": "SUCCESS",
        "report_only": True,
        "disclaimer": EXIT_LAB_REPORT_DISCLAIMER,
        "sample_size": sample_size,
        "policies": summaries,
        "paired_bootstrap": paired_bootstrap_res,
    }
