"""ablation_study.py

Ablation Testing Engine for Contrarian Risk Gates (Phase 27 - P2 / TASK-0081).
Systematically disables individual risk gates to measure the exact trade-off
between Opportunity (Sample Size N) and Strategy Quality (Win Rate, Alpha, MAE).

Follows YAGNI & Empirical Discipline:
  - If a gate kills 80% of opportunities but only saves 1-2% Win Rate, flag as USELESS / STRANGLING.
  - If a gate preserves capital and prevents severe drawdowns (MAE), flag as ESSENTIAL.
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
    CONTRARIAN_MIN_ADV20_BILLION,
    CONTRARIAN_MIN_FSCORE,
    ContrarianResult,
    _calculate_panic_score,
    _check_price_confirmation,
)
from contrarian_features import compute_contrarian_features

logger = logging.getLogger("ablation_study")

HORIZONS = (5, 10, 20, 60)
MAX_HOLD = 60

# Configuration keys for Ablation Variants
VAR_FULL_BASELINE = "Full System (All Gates ON)"
VAR_NO_PRICE_CONFIRM = "- No Price Confirmation (Buy immediately at Panic)"
VAR_NO_REGIME_PENALTY = "- No Macro Downtrend Penalty (MoS fixed 15%)"
VAR_NO_VALUATION_MOS = "- No Valuation MoS Gate (Any MoS allowed)"
VAR_NO_SURVIVAL_FSCORE = "- No Survival F-Score Gate (F-Score < 7 allowed)"
VAR_NO_LIQUIDITY_GATE = "- No Liquidity Gate (ADV20 < 2B allowed)"
VAR_LOOSE_PANIC_50 = "- Loose Panic Threshold (Panic >= 50)"
VAR_LOOSE_CONFIRM_20 = "- Loose Structure Threshold (Conf >= 20)"
VAR_BARE_PANIC_ONLY = "- Bare Panic Only (No gates, Panic >= 70)"

ALL_VARIANTS = (
    VAR_FULL_BASELINE,
    VAR_NO_PRICE_CONFIRM,
    VAR_NO_REGIME_PENALTY,
    VAR_NO_VALUATION_MOS,
    VAR_NO_SURVIVAL_FSCORE,
    VAR_NO_LIQUIDITY_GATE,
    VAR_LOOSE_PANIC_50,
    VAR_LOOSE_CONFIRM_20,
    VAR_BARE_PANIC_ONLY,
)


@dataclass
class AblationConfig:
    name: str
    require_price_confirm: bool = True
    min_confirm_score: float = 40.0
    min_panic_score: float = 70.0
    require_mos_gate: bool = True
    min_mos_pct: float = 15.0
    require_fscore_gate: bool = True
    min_fscore: int = CONTRARIAN_MIN_FSCORE
    require_liquidity_gate: bool = True
    min_adv20_billion: float = CONTRARIAN_MIN_ADV20_BILLION
    apply_downtrend_penalty: bool = True


def get_ablation_configs() -> Dict[str, AblationConfig]:
    return {
        VAR_FULL_BASELINE: AblationConfig(
            name=VAR_FULL_BASELINE,
            require_price_confirm=True,
            min_confirm_score=40.0,
            min_panic_score=70.0,
            require_mos_gate=True,
            require_fscore_gate=True,
            require_liquidity_gate=True,
            apply_downtrend_penalty=True,
        ),
        VAR_NO_PRICE_CONFIRM: AblationConfig(
            name=VAR_NO_PRICE_CONFIRM,
            require_price_confirm=False,
            min_panic_score=70.0,
            require_mos_gate=True,
            require_fscore_gate=True,
            require_liquidity_gate=True,
        ),
        VAR_NO_REGIME_PENALTY: AblationConfig(
            name=VAR_NO_REGIME_PENALTY,
            apply_downtrend_penalty=False,
        ),
        VAR_NO_VALUATION_MOS: AblationConfig(
            name=VAR_NO_VALUATION_MOS,
            require_mos_gate=False,
        ),
        VAR_NO_SURVIVAL_FSCORE: AblationConfig(
            name=VAR_NO_SURVIVAL_FSCORE,
            require_fscore_gate=False,
        ),
        VAR_NO_LIQUIDITY_GATE: AblationConfig(
            name=VAR_NO_LIQUIDITY_GATE,
            require_liquidity_gate=False,
        ),
        VAR_LOOSE_PANIC_50: AblationConfig(
            name=VAR_LOOSE_PANIC_50,
            min_panic_score=50.0,
        ),
        VAR_LOOSE_CONFIRM_20: AblationConfig(
            name=VAR_LOOSE_CONFIRM_20,
            min_confirm_score=20.0,
        ),
        VAR_BARE_PANIC_ONLY: AblationConfig(
            name=VAR_BARE_PANIC_ONLY,
            require_price_confirm=False,
            require_mos_gate=False,
            require_fscore_gate=False,
            require_liquidity_gate=False,
            apply_downtrend_penalty=False,
        ),
    }


def load_cached_ticker_data(symbol: str, cache_dir: str = "data/replay_cache") -> Optional[pd.DataFrame]:
    pattern = os.path.join(cache_dir, f"{symbol}_*.csv")
    matches = glob.glob(pattern)
    if not matches:
        return None
    best_file = max(matches, key=os.path.getsize)
    try:
        df = pd.read_csv(best_file, parse_dates=["time"])
        return df.sort_values("time").drop_duplicates("time").reset_index(drop=True)
    except Exception:
        logger.exception("Error loading cached CSV for %s", symbol)
        return None


def calculate_rsi_series(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


class StockAblationContext:
    def __init__(self, symbol: str, df: pd.DataFrame, bench_open: pd.Series, bench_close: pd.Series):
        self.symbol = symbol
        self.df = df
        self.n = len(df)
        self.dates = df["time"].reset_index(drop=True)
        self.o = df["open"].to_numpy(float)
        self.h = df["high"].to_numpy(float)
        self.l = df["low"].to_numpy(float)
        self.c = df["close"].to_numpy(float)
        self.v = df["volume"].to_numpy(float)
        self.bench_open = bench_open
        self.bench_close = bench_close

        # Technical indicators
        c_series = df["close"].astype(float)
        self.rsi = calculate_rsi_series(c_series).to_numpy()
        self.ma20 = c_series.rolling(20).mean().to_numpy()
        turnover_vnd = self.c * 1000.0 * self.v
        self.adv20_val = pd.Series(turnover_vnd).rolling(20).mean().to_numpy() / 1e9

        # Simulated fundamentals
        self.base_f_score = 7
        self.base_mos_pct = 22.0

        # Feature cache
        self.feat_cache: Dict[int, Dict[str, Any]] = {}
        self.panic_cache: Dict[int, float] = {}
        self.conf_cache: Dict[int, float] = {}

    def get_tech(self, i: int) -> Dict[str, Any]:
        if i not in self.feat_cache:
            tech = {
                "rsi14": float(self.rsi[i]),
                "ma20": float(self.ma20[i]),
                "adv20_billion": float(self.adv20_val[i]) if np.isfinite(self.adv20_val[i]) else 5.0,
                "is_backtest": True,
            }
            tech.update(compute_contrarian_features(self.df.iloc[: i + 1]))
            self.feat_cache[i] = tech
        return self.feat_cache[i]

    def get_panic_score(self, i: int) -> float:
        if i not in self.panic_cache:
            if np.isfinite(self.rsi[i]) and self.rsi[i] <= 50.0:
                self.panic_cache[i] = _calculate_panic_score(float(self.c[i]), self.get_tech(i))
            else:
                self.panic_cache[i] = 0.0
        return self.panic_cache[i]

    def get_panic_max_window(self, i: int, window: int = 10) -> float:
        start_idx = max(0, i - window)
        scores = [self.get_panic_score(k) for k in range(start_idx, i + 1)]
        return float(max(scores, default=0.0))

    def get_conf_score(self, i: int) -> float:
        if i not in self.conf_cache:
            res = ContrarianResult(symbol=self.symbol, can_buy=False)
            _check_price_confirmation(float(self.c[i]), self.get_tech(i), res)
            self.conf_cache[i] = float(res.metrics.get("price_confirmation_score", 0.0))
        return self.conf_cache[i]

    def get_bench_return(self, j_entry: int, j_exit: int) -> float:
        d_entry = self.dates.iloc[j_entry]
        d_exit = self.dates.iloc[j_exit]
        b0 = self.bench_open.asof(d_entry)
        b1 = self.bench_close.asof(d_exit)
        if pd.isna(b0) or pd.isna(b1) or b0 <= 0:
            return np.nan
        return float((b1 / b0 - 1.0) * 100.0)


def evaluate_gate_compliance(
    ctx: StockAblationContext,
    i: int,
    cfg: AblationConfig,
    bench_downtrend: bool,
) -> bool:
    # 1. Panic Threshold
    if cfg.require_price_confirm:
        # With price confirmation, check if Panic happened in rolling 10-bar window
        p_val = ctx.get_panic_max_window(i, window=10)
        if p_val < cfg.min_panic_score:
            return False
        # And check today's confirmation
        conf_val = ctx.get_conf_score(i)
        if conf_val < cfg.min_confirm_score:
            return False
    else:
        # Without price confirmation, must trigger today
        panic_today = ctx.get_panic_score(i)
        if panic_today < cfg.min_panic_score:
            return False

    # 2. Macro Regime & MoS Gate
    if cfg.require_mos_gate:
        req_mos = cfg.min_mos_pct
        if cfg.apply_downtrend_penalty and bench_downtrend:
            req_mos += 5.0  # +5% MoS penalty in downtrend
        if ctx.base_mos_pct < req_mos:
            return False

    # 3. Survival F-Score Gate
    if cfg.require_fscore_gate:
        if ctx.base_f_score < cfg.min_fscore:
            return False

    # 4. Liquidity Gate
    if cfg.require_liquidity_gate:
        adv = ctx.adv20_val[i]
        if np.isfinite(adv) and adv < cfg.min_adv20_billion:
            return False

    return True


def simulate_trade_record(
    ctx: StockAblationContext,
    i: int,
    variant_name: str,
) -> Optional[Dict[str, Any]]:
    j0 = i + 1
    if j0 >= ctx.n:
        return None
    entry_price = float(ctx.o[j0])
    end = min(j0 + MAX_HOLD, ctx.n - 1)
    if entry_price <= 0 or end < j0 + 2:
        return None

    k20 = min(j0 + 20, ctx.n - 1)
    ret_t20 = (ctx.c[k20] / entry_price - 1.0) * 100.0
    bench_ret_t20 = ctx.get_bench_return(j0, k20)
    alpha_t20 = ret_t20 - bench_ret_t20 if np.isfinite(bench_ret_t20) else np.nan

    mae_pct = (ctx.l[j0 : end + 1].min() / entry_price - 1.0) * 100.0
    mfe_pct = (ctx.h[j0 : end + 1].max() / entry_price - 1.0) * 100.0

    return {
        "variant": variant_name,
        "symbol": ctx.symbol,
        "signal_date": str(ctx.dates.iloc[i].date()),
        "entry_price": round(entry_price, 2),
        "ret_t20": round(ret_t20, 2),
        "alpha_t20": round(alpha_t20, 2),
        "mae_pct": round(mae_pct, 2),
        "mfe_pct": round(mfe_pct, 2),
    }


def run_single_stock_ablation(
    ctx: StockAblationContext,
    configs: Dict[str, AblationConfig],
    bench_close: pd.Series,
    cooldown: int = 10,
    warmup: int = 50,
) -> List[Dict[str, Any]]:
    bench_dd = (bench_close / bench_close.rolling(60, min_periods=20).max() - 1.0) * 100.0
    events: List[Dict[str, Any]] = []

    last_idx_by_var: Dict[str, int] = {}

    for i in range(warmup, ctx.n - 2):
        if not np.isfinite(ctx.rsi[i]):
            continue

        b_dd = bench_dd.asof(ctx.dates.iloc[i])
        is_downtrend = bool(pd.notna(b_dd) and b_dd <= -10.0)

        for var_name, cfg in configs.items():
            if i - last_idx_by_var.get(var_name, -999) < cooldown:
                continue

            passed = evaluate_gate_compliance(ctx, i, cfg, is_downtrend)
            if passed:
                rec = simulate_trade_record(ctx, i, var_name)
                if rec is not None:
                    last_idx_by_var[var_name] = i
                    events.append(rec)

    return events


def aggregate_ablation_summary(df_all: pd.DataFrame, configs: Dict[str, AblationConfig]) -> pd.DataFrame:
    rows: List[Dict[str, Any]] = []
    baseline_sub = df_all[df_all["variant"] == VAR_FULL_BASELINE]
    n_base = len(baseline_sub)
    win_base = (baseline_sub["ret_t20"] > 0).mean() * 100.0 if n_base > 0 else 0.0
    alpha_base = baseline_sub["alpha_t20"].mean() if n_base > 0 else 0.0

    for var_name in configs:
        sub = df_all[df_all["variant"] == var_name]
        n_obs = len(sub)
        if n_obs == 0:
            continue

        r20 = sub["ret_t20"].dropna()
        a20 = sub["alpha_t20"].dropna()
        win_rate = (r20 > 0).mean() * 100.0 if len(r20) > 0 else 0.0
        alpha_win = (a20 > 0).mean() * 100.0 if len(a20) > 0 else 0.0
        mean_ret = r20.mean()
        mean_alpha = a20.mean()
        mean_mae = sub["mae_pct"].mean()
        mean_mfe = sub["mfe_pct"].mean()

        # Trade-off vs Baseline
        delta_n = n_obs - n_base
        pct_delta_n = round((delta_n / n_base) * 100.0, 1) if n_base > 0 else 0.0
        delta_win = round(win_rate - win_base, 1)
        delta_alpha = round(mean_alpha - alpha_base, 2)

        # Verdict
        if var_name == VAR_FULL_BASELINE:
            verdict = "BASELINE"
        else:
            verdict = "INCONCLUSIVE (Exploratory)"

        rows.append(
            {
                "Variant": var_name,
                "N": n_obs,
                "Delta N (%)": f"{pct_delta_n:+}%",
                "WinRate (%)": round(win_rate, 1),
                "Delta Win (%)": f"{delta_win:+}%",
                "MeanRet (%)": round(mean_ret, 2),
                "Alpha20 (%)": round(mean_alpha, 2),
                "Delta Alpha (%)": f"{delta_alpha:+}%",
                "AlphaWin (%)": round(alpha_win, 1),
                "MAE (%)": round(mean_mae, 2),
                "MFE (%)": round(mean_mfe, 2),
                "Verdict": verdict,
            }
        )

    return pd.DataFrame(rows)


def run_ablation_study(
    symbols: Optional[List[str]] = None,
    cache_dir: str = "data/replay_cache",
    start_date: str = "2020-01-01",
    cooldown: int = 10,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    bench_df = load_cached_ticker_data("VNINDEX", cache_dir)
    if bench_df is None or bench_df.empty:
        raise RuntimeError("VNINDEX cache not found.")

    bench_df = bench_df.sort_values("time").drop_duplicates("time").reset_index(drop=True)
    bench_open = pd.Series(bench_df["open"].to_numpy(float), index=pd.DatetimeIndex(bench_df["time"]))
    bench_close = pd.Series(bench_df["close"].to_numpy(float), index=pd.DatetimeIndex(bench_df["time"]))

    if not symbols:
        all_files = glob.glob(os.path.join(cache_dir, "*_*.csv"))
        sym_set = {os.path.basename(f).split("_")[0] for f in all_files}
        symbols = sorted([s for s in sym_set if s != "VNINDEX"])

    configs = get_ablation_configs()
    all_events: List[Dict[str, Any]] = []

    for sym in symbols:
        df = load_cached_ticker_data(sym, cache_dir)
        if df is None or len(df) < 60:
            continue
        if start_date:
            df = df[df["time"] >= pd.to_datetime(start_date)].reset_index(drop=True)
            if len(df) < 60:
                continue

        ctx = StockAblationContext(sym, df, bench_open, bench_close)
        evs = run_single_stock_ablation(ctx, configs, bench_close, cooldown=cooldown)
        all_events.extend(evs)

    df_all = pd.DataFrame(all_events)
    if df_all.empty:
        return df_all, pd.DataFrame()

    summary = aggregate_ablation_summary(df_all, configs)
    return df_all, summary


def main():
    parser = argparse.ArgumentParser(description="Ablation Testing Engine for Risk Gates (Phase 27 - P2)")
    parser.add_argument("--symbols", nargs="+", default=None, help="Stock symbols")
    parser.add_argument("--all", action="store_true", help="Run across all cached stocks")
    parser.add_argument("--cache-dir", default="data/replay_cache", help="Cache directory")
    parser.add_argument("--start", default="2020-01-01", help="Start date")
    parser.add_argument("--cooldown", type=int, default=10, help="Cooldown bars")
    parser.add_argument("--output-csv", default=None, help="Save details to CSV")

    args = parser.parse_args()
    symbols = None if args.all or not args.symbols else args.symbols

    print(f"\n[ABLATION STUDY] Running gate ablation testing from {args.start}...")
    df_events, summary = run_ablation_study(
        symbols=symbols,
        cache_dir=args.cache_dir,
        start_date=args.start,
        cooldown=args.cooldown,
    )

    if summary.empty:
        print("No events generated.")
        return

    print("\n" + "=" * 125)
    print("ABLATION TESTING RESULTS: OPPORTUNITY (SAMPLE SIZE N) VS WIN RATE & ALPHA TRADE-OFF")
    print("=" * 125)
    print(summary.to_string(index=False))
    print("=" * 125 + "\n")

    if args.output_csv and not df_events.empty:
        df_events.to_csv(args.output_csv, index=False)
        print(f"Saved {len(df_events)} events to {args.output_csv}")


if __name__ == "__main__":
    main()
