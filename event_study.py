"""event_study.py

Event Study Engine for Quantitative Signals (Phase 27 - P1).
Empirically tests isolated contrarian and technical signals (RSI < 30, Panic >= 70,
Price Confirmation, Divergence, etc.) against VN-Index Benchmark across 3-5+ years.

Key Principles:
  - Point-in-time calculation (no look-ahead bias).
  - Forward returns measured at T+5, T+10, T+20, T+60.
  - Beta-adjusted Alpha (Blume shrunk towards 1.0) and Benchmark Alpha.
  - MAE (Max Adverse Excursion) and MFE (Max Favorable Excursion).
  - Stop loss simulation: Fixed -8% vs Structural Stop Loss.
  - Statistical significance (t-stat, p-value on alpha).
"""

from __future__ import annotations

import argparse
import glob
import logging
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from contrarian_engine import (
    CONTRARIAN_STOP_LOSS_PCT,
    ContrarianResult,
    _calculate_panic_score,
    _check_price_confirmation,
)
from contrarian_features import compute_contrarian_features

logger = logging.getLogger("event_study")

HORIZONS = (5, 10, 20, 60)
MAX_HOLD = 60
STRUCT_STOP_MIN_PCT = 0.05
STRUCT_STOP_MAX_PCT = 0.12

# Constants for signals
SIG_RSI_30 = "RSI <= 30 (Extreme Oversold)"
SIG_RSI_35 = "RSI <= 35 (Oversold)"
SIG_PANIC_70 = "Panic Score >= 70 (Multifactor Panic)"
SIG_PANIC_CONFIRM = "Panic >= 70 + Conf >= 40 (Confirmed Reversal)"
SIG_CONFIRM_ALONE = "Price Conf >= 40 (Reversal Alone)"
SIG_BULLISH_DIV = "Bullish Divergence"
SIG_HIGHER_LOW = "Higher Low"
SIG_MKT_PANIC = "Market DD <= -10% + Panic >= 70"
SIG_CONTROL_RANDOM = "Random Baseline (Control)"

ALL_SIGNALS = (
    SIG_RSI_30,
    SIG_RSI_35,
    SIG_PANIC_70,
    SIG_PANIC_CONFIRM,
    SIG_CONFIRM_ALONE,
    SIG_BULLISH_DIV,
    SIG_HIGHER_LOW,
    SIG_MKT_PANIC,
    SIG_CONTROL_RANDOM,
)


def calculate_rsi_series(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def calculate_atr_array(df: pd.DataFrame, period: int = 14) -> np.ndarray:
    h = df["high"].astype(float)
    low = df["low"].astype(float)
    c = df["close"].astype(float)
    prev_c = c.shift(1)
    tr = pd.concat([h - low, (h - prev_c).abs(), (low - prev_c).abs()], axis=1).max(axis=1)
    return tr.rolling(period).mean().to_numpy()


def calculate_rolling_beta(df: pd.DataFrame, bench_close: pd.Series, window: int = 120) -> np.ndarray:
    b = bench_close.reindex(pd.DatetimeIndex(df["time"]), method="ffill")
    r_s = df["close"].astype(float).reset_index(drop=True).pct_change()
    r_b = pd.Series(b.to_numpy(float)).pct_change()
    cov = r_s.rolling(window, min_periods=40).cov(r_b)
    var = r_b.rolling(window, min_periods=40).var()
    beta = cov / var
    # Blume shrinkage: 0.67 * raw + 0.33 * 1.0, clipped between 0.3 and 2.5
    return (0.67 * beta + 0.33).clip(0.3, 2.5).fillna(1.0).to_numpy()


@dataclass
class StockContext:
    symbol: str
    n: int
    dates: pd.Series
    o: np.ndarray
    h: np.ndarray
    l: np.ndarray
    c: np.ndarray
    atr: np.ndarray
    beta: np.ndarray
    bench_open: pd.Series
    bench_close: pd.Series

    def get_bench_return(self, j_entry: int, j_exit: int) -> float:
        d_entry = self.dates.iloc[j_entry]
        d_exit = self.dates.iloc[j_exit]
        b0 = self.bench_open.asof(d_entry)
        b1 = self.bench_close.asof(d_exit)
        if pd.isna(b0) or pd.isna(b1) or b0 <= 0:
            return np.nan
        return float((b1 / b0 - 1.0) * 100.0)

    def simulate_exit(self, j0: int, end: int, stop_price: float) -> Tuple[int, float, bool]:
        # T+2.5 settlement: stop loss active from j0 + 2
        for j in range(j0 + 2, end + 1):
            if self.l[j] <= stop_price:
                exec_price = min(stop_price, self.o[j])
                return j, exec_price, True
        return end, float(self.c[end]), False


def build_stock_context(
    symbol: str, df: pd.DataFrame, bench_open: pd.Series, bench_close: pd.Series
) -> Optional[StockContext]:
    if df is None or len(df) < 50:
        return None
    sorted_df = df.sort_values("time").drop_duplicates("time").reset_index(drop=True)
    return StockContext(
        symbol=symbol,
        n=len(sorted_df),
        dates=sorted_df["time"].reset_index(drop=True),
        o=sorted_df["open"].to_numpy(float),
        h=sorted_df["high"].to_numpy(float),
        l=sorted_df["low"].to_numpy(float),
        c=sorted_df["close"].to_numpy(float),
        atr=calculate_atr_array(sorted_df),
        beta=calculate_rolling_beta(sorted_df, bench_close),
        bench_open=bench_open,
        bench_close=bench_close,
    )


def extract_forward_returns(
    ctx: StockContext, i: int, entry_price: float, beta: float
) -> Dict[str, float]:
    res: Dict[str, float] = {}
    j0 = i + 1
    for h in HORIZONS:
        k = j0 + h
        if k < ctx.n:
            ret = (ctx.c[k] / entry_price - 1.0) * 100.0
            b_ret = ctx.get_bench_return(j0, k)
            res[f"ret_t{h}"] = round(ret, 2)
            res[f"bench_t{h}"] = round(b_ret, 2) if np.isfinite(b_ret) else np.nan
            res[f"alpha_t{h}"] = round(ret - b_ret, 2) if np.isfinite(b_ret) else np.nan
            res[f"alpha_adj_t{h}"] = round(ret - beta * b_ret, 2) if np.isfinite(b_ret) else np.nan
        else:
            res[f"ret_t{h}"] = np.nan
            res[f"bench_t{h}"] = np.nan
            res[f"alpha_t{h}"] = np.nan
            res[f"alpha_adj_t{h}"] = np.nan
    return res


def extract_event_record(ctx: StockContext, i: int, signal_name: str) -> Optional[Dict[str, Any]]:
    j0 = i + 1
    if j0 >= ctx.n:
        return None
    entry_price = float(ctx.o[j0])
    end = min(j0 + MAX_HOLD, ctx.n - 1)
    if entry_price <= 0 or end < j0 + 2:
        return None

    beta = float(ctx.beta[i])
    atr = ctx.atr[i] if np.isfinite(ctx.atr[i]) else entry_price * 0.03

    # Structural Stop Loss (Swing low 10d - 0.5 ATR, bounded -5% to -12%)
    anchor = float(ctx.l[max(0, i - 9) : i + 1].min())
    cand = anchor - 0.5 * atr
    stop_struct = max(
        min(cand, entry_price * (1.0 - STRUCT_STOP_MIN_PCT)),
        entry_price * (1.0 - STRUCT_STOP_MAX_PCT),
    )
    stop_fixed = entry_price * (1.0 - CONTRARIAN_STOP_LOSS_PCT)

    fwd_returns = extract_forward_returns(ctx, i, entry_price, beta)

    # MAE & MFE
    mae_pct = (ctx.l[j0 : end + 1].min() / entry_price - 1.0) * 100.0
    mfe_pct = (ctx.h[j0 : end + 1].max() / entry_price - 1.0) * 100.0

    # Simulate exits
    _, p_fixed, hit_fixed = ctx.simulate_exit(j0, end, stop_fixed)
    _, p_struct, hit_struct = ctx.simulate_exit(j0, end, stop_struct)

    record: Dict[str, Any] = {
        "symbol": ctx.symbol,
        "signal_date": str(ctx.dates.iloc[i].date()),
        "signal": signal_name,
        "entry_price": round(entry_price, 2),
        "beta": round(beta, 2),
        "mae_pct": round(mae_pct, 2),
        "mfe_pct": round(mfe_pct, 2),
        "ret_fixed8": round((p_fixed / entry_price - 1.0) * 100.0, 2),
        "hit_fixed8": hit_fixed,
        "ret_struct": round((p_struct / entry_price - 1.0) * 100.0, 2),
        "hit_struct": hit_struct,
    }
    record.update(fwd_returns)
    return record


def scan_single_stock_events(
    ctx: StockContext,
    df: pd.DataFrame,
    bench_close: pd.Series,
    cooldown: int = 10,
    warmup: int = 50,
) -> List[Dict[str, Any]]:
    """Evaluates all isolated signals across historical bars for a single stock."""
    c_series = df["close"].astype(float)
    ma20 = c_series.rolling(20).mean().to_numpy()
    rsi = calculate_rsi_series(c_series).to_numpy()
    bench_dd = (bench_close / bench_close.rolling(60, min_periods=20).max() - 1.0) * 100.0

    feat_cache: Dict[int, Dict[str, Any]] = {}

    def get_tech(idx: int) -> Dict[str, Any]:
        if idx not in feat_cache:
            tech = {"rsi14": float(rsi[idx]), "ma20": float(ma20[idx]), "is_backtest": True}
            tech.update(compute_contrarian_features(df.iloc[: idx + 1]))
            feat_cache[idx] = tech
        return feat_cache[idx]

    def get_conf_score(idx: int) -> float:
        res = ContrarianResult(symbol=ctx.symbol, can_buy=False)
        _check_price_confirmation(float(ctx.c[idx]), get_tech(idx), res)
        return float(res.metrics.get("price_confirmation_score", 0.0))

    last_signal_idx: Dict[str, int] = {}
    events: List[Dict[str, Any]] = []

    def try_emit(sig_name: str, idx: int) -> None:
        if idx - last_signal_idx.get(sig_name, -999) < cooldown:
            return
        rec = extract_event_record(ctx, idx, sig_name)
        if rec is not None:
            last_signal_idx[sig_name] = idx
            events.append(rec)

    # Precompute panic scores in single pass
    panic_scores = np.zeros(ctx.n)
    for i in range(warmup, ctx.n - 2):
        if np.isfinite(rsi[i]) and rsi[i] <= 50.0:
            panic_scores[i] = _calculate_panic_score(float(ctx.c[i]), get_tech(i))

    for i in range(warmup, ctx.n - 2):
        r_val = rsi[i]
        if not np.isfinite(r_val):
            continue

        panic = panic_scores[i]
        conf = get_conf_score(i)
        b_dd = bench_dd.asof(ctx.dates.iloc[i])

        # 1. RSI <= 30
        if r_val <= 30.0:
            try_emit(SIG_RSI_30, i)

        # 2. RSI <= 35
        if r_val <= 35.0:
            try_emit(SIG_RSI_35, i)

        # 3. Panic Score >= 70 (Standalone Panic day)
        if panic >= 70.0:
            try_emit(SIG_PANIC_70, i)

        # 4. Confirmed Reversal: Had Panic >= 70 in past 10 bars AND Conf >= 40 today
        p_max_10 = float(panic_scores[max(0, i - 10) : i + 1].max())
        if p_max_10 >= 70.0 and conf >= 40.0:
            try_emit(SIG_PANIC_CONFIRM, i)

        # 5. Price Conf >= 40 alone (without panic)
        if conf >= 40.0:
            try_emit(SIG_CONFIRM_ALONE, i)

        tech = get_tech(i)

        # 6. Bullish Divergence
        if tech.get("bullish_divergence", False):
            try_emit(SIG_BULLISH_DIV, i)

        # 7. Higher Low
        if tech.get("higher_low", False):
            try_emit(SIG_HIGHER_LOW, i)

        # 8. Market DD <= -10% + Panic >= 70
        if pd.notna(b_dd) and b_dd <= -10.0 and panic >= 70.0:
            try_emit(SIG_MKT_PANIC, i)

    # 9. Control Random Sample
    rng = np.random.default_rng(42 + sum(ord(ch) for ch in ctx.symbol))
    valid_indices = np.arange(warmup, ctx.n - MAX_HOLD - 2)
    if len(valid_indices) > 0:
        sample_size = min(30, len(valid_indices))
        for rand_idx in sorted(rng.choice(valid_indices, size=sample_size, replace=False)):
            rec = extract_event_record(ctx, int(rand_idx), SIG_CONTROL_RANDOM)
            if rec is not None:
                events.append(rec)

    return events


def compute_signal_summary(df_events: pd.DataFrame) -> pd.DataFrame:
    """Aggregates metrics and statistical tests per signal."""
    summary_rows: List[Dict[str, Any]] = []

    for sig in ALL_SIGNALS:
        sub = df_events[df_events["signal"] == sig]
        n_obs = len(sub)
        if n_obs == 0:
            continue

        r20 = sub["ret_t20"].dropna()
        a20 = sub["alpha_t20"].dropna()
        b_adj20 = sub["alpha_adj_t20"].dropna()

        win_rate = (r20 > 0).mean() * 100.0 if len(r20) > 0 else 0.0
        alpha_win_rate = (a20 > 0).mean() * 100.0 if len(a20) > 0 else 0.0

        mean_r5 = sub["ret_t5"].mean()
        mean_r20 = r20.mean()
        mean_r60 = sub["ret_t60"].mean()

        mean_a5 = sub["alpha_t5"].mean()
        mean_a20 = a20.mean()
        mean_a60 = sub["alpha_t60"].mean()
        mean_beta_a20 = b_adj20.mean()

        mae = sub["mae_pct"].mean()
        mfe = sub["mfe_pct"].mean()
        rr_ratio = abs(mfe / mae) if mae != 0 else np.nan

        # Two-sided t-test against 0 for Alpha T+20
        if len(a20) > 2 and a20.std() > 0:
            se = a20.std() / np.sqrt(len(a20))
            t_stat = mean_a20 / se
        else:
            t_stat = 0.0

        summary_rows.append(
            {
                "Signal": sig,
                "N": n_obs,
                "WinRate20 (%)": round(win_rate, 1),
                "AlphaWin20 (%)": round(alpha_win_rate, 1),
                "MeanRet20 (%)": round(mean_r20, 2),
                "Alpha20 (%)": round(mean_a20, 2),
                "BetaAdjAlpha20 (%)": round(mean_beta_a20, 2),
                "t-stat": round(t_stat, 2),
                "Alpha5 (%)": round(mean_a5, 2),
                "Alpha60 (%)": round(mean_a60, 2),
                "MAE (%)": round(mae, 2),
                "MFE (%)": round(mfe, 2),
                "R/R": round(rr_ratio, 2),
            }
        )

    return pd.DataFrame(summary_rows)


def load_cached_ticker_data(
    symbol: str, cache_dir: str = "data/replay_cache"
) -> Optional[pd.DataFrame]:
    pattern = os.path.join(cache_dir, f"{symbol}_*.csv")
    matches = glob.glob(pattern)
    if not matches:
        return None
    # Pick the largest/most comprehensive file
    best_file = max(matches, key=os.path.getsize)
    try:
        df = pd.read_csv(best_file, parse_dates=["time"])
        return df.sort_values("time").drop_duplicates("time").reset_index(drop=True)
    except Exception:
        logger.exception("Error loading cached CSV for %s", symbol)
        return None


def run_event_study(
    symbols: Optional[List[str]] = None,
    cache_dir: str = "data/replay_cache",
    cooldown: int = 10,
    start_date: Optional[str] = None,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Runs event study across tickers using cached historical daily bars."""
    bench_df = load_cached_ticker_data("VNINDEX", cache_dir)
    if bench_df is None or bench_df.empty:
        raise RuntimeError("VNINDEX historical cache not found in data/replay_cache.")

    bench_df = bench_df.sort_values("time").drop_duplicates("time").reset_index(drop=True)
    bench_open = pd.Series(bench_df["open"].to_numpy(float), index=pd.DatetimeIndex(bench_df["time"]))
    bench_close = pd.Series(bench_df["close"].to_numpy(float), index=pd.DatetimeIndex(bench_df["time"]))

    if not symbols:
        # Discover all available symbols in cache_dir
        all_files = glob.glob(os.path.join(cache_dir, "*_*.csv"))
        sym_set = {os.path.basename(f).split("_")[0] for f in all_files}
        symbols = sorted([s for s in sym_set if s != "VNINDEX"])

    all_events: List[Dict[str, Any]] = []

    for sym in symbols:
        df = load_cached_ticker_data(sym, cache_dir)
        if df is None or len(df) < 60:
            continue
        if start_date:
            df = df[df["time"] >= pd.to_datetime(start_date)].reset_index(drop=True)
            if len(df) < 60:
                continue

        ctx = build_stock_context(sym, df, bench_open, bench_close)
        if ctx is None:
            continue

        sym_events = scan_single_stock_events(ctx, df, bench_close, cooldown=cooldown)
        all_events.extend(sym_events)

    df_events = pd.DataFrame(all_events)
    if df_events.empty:
        return df_events, pd.DataFrame()

    summary_df = compute_signal_summary(df_events)
    return df_events, summary_df


def main():
    parser = argparse.ArgumentParser(description="Event Study Engine for Isolated Signals (Phase 27 - P1)")
    parser.add_argument("--symbols", nargs="+", default=None, help="Specific symbols to test (e.g. HPG SSI FPT)")
    parser.add_argument("--all", action="store_true", help="Run across all cached stocks")
    parser.add_argument("--cache-dir", default="data/replay_cache", help="Path to cache directory")
    parser.add_argument("--start", default="2018-01-01", help="Start date filter (YYYY-MM-DD)")
    parser.add_argument("--cooldown", type=int, default=10, help="Signal cooldown bars")
    parser.add_argument("--output-csv", default=None, help="Save detailed events to CSV")

    args = parser.parse_args()

    symbols = None if args.all or not args.symbols else args.symbols
    print(f"\n[EVENT STUDY ENGINE] Running empirical study from {args.start}...")
    df_events, summary = run_event_study(
        symbols=symbols,
        cache_dir=args.cache_dir,
        cooldown=args.cooldown,
        start_date=args.start,
    )

    if summary.empty:
        print("No event records generated.")
        return

    print("\n" + "=" * 115)
    print("EMPIRICAL SIGNAL EVENT STUDY RESULTS (BENCHMARK: VN-INDEX)")
    print("=" * 115)
    print(summary.to_string(index=False))
    print("=" * 115 + "\n")

    if args.output_csv and not df_events.empty:
        df_events.to_csv(args.output_csv, index=False)
        print(f"Detailed events ({len(df_events)} records) saved to {args.output_csv}")


if __name__ == "__main__":
    main()
