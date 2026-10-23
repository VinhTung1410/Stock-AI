"""Comparison Script: Old Logic vs New Logic (Alpha Tracker Engine).

Compares:
1. Baseline Old Logic:
   - Exit at RSI >= 75 (Chốt non)
   - Exit at MA20 * 0.95 (Bán tháo khi rũ bỏ nhẹ)
   - No Trailing Stop
   - Strict Cash Mode (100% blocked in Downtrend)
2. Proposed New Logic:
   - No RSI 75 cap (Ăn trọn thân sóng tăng)
   - Loosened shakeout tolerance (chỉ thoát khi gãy MA50 * 0.98)
   - Trailing Stop 10-12% theo đỉnh cao nhất (Peak Trailing Stop)
   - RS Probe (Thăm dò 25% khi cổ phiếu giữ MA50 trong pha VN-Index Downtrend)
"""

import os
import sys

import numpy as np
import pandas as pd

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from backtest_engine import (  # noqa: E402
    RegimeBacktestEngine,
    generate_signals_by_strategy,
)
from regime_classifier import classify_market_regime  # noqa: E402

CACHE_DIR = os.path.join(ROOT_DIR, "data", "replay_cache")


def load_cached_ticker(symbol: str) -> pd.DataFrame:
    file_path = os.path.join(CACHE_DIR, f"{symbol}_2018-01-01_2026-10-06.csv")
    if not os.path.exists(file_path):
        # Fallback to other cached dates if needed
        file_path = os.path.join(CACHE_DIR, f"{symbol}_2018-01-01_2024-12-31.csv")
    df = pd.read_csv(file_path)
    df["time"] = pd.to_datetime(df["time"])
    df = df.sort_values("time").reset_index(drop=True)
    df = df.set_index("time")
    return df


def generate_old_baseline_signals(df_price: pd.DataFrame, regimes: pd.Series) -> pd.Series:
    """Simulate old baseline rules: RSI >= 75 sell, MA20*0.95 sell, hard Cash Mode."""
    close = df_price["close"].astype(float)
    signals = pd.Series(0, index=close.index)

    ma20 = close.rolling(20, min_periods=10).mean()
    ma50 = close.rolling(50, min_periods=20).mean()

    delta = close.diff()
    gain = delta.where(delta > 0, 0.0).rolling(14, min_periods=7).mean()
    loss = (-delta.where(delta < 0, 0.0)).rolling(14, min_periods=7).mean()
    rs = gain / loss.replace(0, np.nan)
    rsi = 100.0 - (100.0 / (1.0 + rs)).fillna(50.0)

    # Buy: Upward trend, reasonable RSI
    buy_cond = (close >= ma20) & (ma20 >= ma50 * 0.98) & (rsi < 70) & (rsi >= 40)

    # Old Cash mode: 100% blocked in downtrend
    aligned_regimes = regimes.reindex(close.index).fillna("SIDEWAYS")
    buy_cond = buy_cond & (aligned_regimes != "DOWNTREND")

    buy_prev = buy_cond.shift(1, fill_value=False)
    buy_trigger = buy_cond & (~buy_prev)

    # Old Sell: premature RSI >= 75 or MA20 * 0.95 breakdown
    sell_cond = (rsi >= 75) | (close < ma20 * 0.95)
    sell_prev = sell_cond.shift(1, fill_value=False)
    sell_trigger = sell_cond & (~sell_prev)

    signals[buy_trigger] = 1
    signals[sell_trigger] = -1
    return signals


def run_comparison():
    symbols = ["FPT", "HPG", "DGC", "SSI", "MWG"]
    df_vni = load_cached_ticker("VNINDEX")
    regimes = classify_market_regime(df_vni)
    vni_returns = df_vni["close"].pct_change().fillna(0.0)

    rows = []

    print("\n" + "=" * 90)
    print("KIỂM ĐỊNH ĐỐI CHỨNG ALPHA TRACKER: LOGIC CŨ VS LOGIC MỚI (2018 - 2026)")
    print("=" * 90)

    for sym in symbols:
        df_p = load_cached_ticker(sym)
        aligned_vni_ret = vni_returns.reindex(df_p.index).fillna(0.0)
        aligned_regimes = regimes.reindex(df_p.index).ffill().bfill()

        # 1. OLD LOGIC: Hard RSI 75 exit, MA20*0.95 sell, No trailing stop, No RS probe
        old_sigs = generate_old_baseline_signals(df_p, aligned_regimes)
        engine_old = RegimeBacktestEngine(
            initial_capital=100_000_000.0,
            enable_trailing_stop=False,
            allow_rs_probe=False,
        )
        res_old = engine_old.run_backtest(
            df_price=df_p,
            signals=old_sigs,
            regimes=aligned_regimes,
            benchmark_returns=aligned_vni_ret,
            symbol=sym,
            enforce_regime_gate=True,
        )
        m_old = res_old.summary_metrics

        # 2. NEW LOGIC: No RSI 75 cap, loosened shakeout stop, Trailing Stop 10%, RS Probe
        new_sigs = generate_signals_by_strategy(
            df_p,
            regimes=aligned_regimes,
            enforce_regime_gate=True,
            allow_rs_probe=True,
        )
        engine_new = RegimeBacktestEngine(
            initial_capital=100_000_000.0,
            enable_trailing_stop=True,
            trailing_stop_pct=10.0,
            allow_rs_probe=True,
            probe_allocation_pct=0.25,
        )
        res_new = engine_new.run_backtest(
            df_price=df_p,
            signals=new_sigs,
            regimes=aligned_regimes,
            benchmark_returns=aligned_vni_ret,
            symbol=sym,
            enforce_regime_gate=True,
        )
        m_new = res_new.summary_metrics

        # Exit reason breakdown
        old_exit_reasons = {}
        for t in res_old.trades:
            old_exit_reasons[t.exit_reason] = old_exit_reasons.get(t.exit_reason, 0) + 1

        new_exit_reasons = {}
        for t in res_new.trades:
            new_exit_reasons[t.exit_reason] = new_exit_reasons.get(t.exit_reason, 0) + 1

        probe_trades = sum(1 for t in res_new.trades if t.is_probe)

        ret_old = (
            ((res_old.equity_curve.iloc[-1] / res_old.equity_curve.iloc[0]) - 1.0) * 100.0
            if not res_old.equity_curve.empty
            else 0.0
        )
        ret_new = (
            ((res_new.equity_curve.iloc[-1] / res_new.equity_curve.iloc[0]) - 1.0) * 100.0
            if not res_new.equity_curve.empty
            else 0.0
        )

        rows.append(
            {
                "Mã CP": sym,
                "Cũ - Lãi/Lỗ (%)": f"{ret_old:+.1f}%",
                "Mới - Lãi/Lỗ (%)": f"{ret_new:+.1f}%",
                "Chênh lệch Return": f"{(ret_new - ret_old):+.1f}%",
                "Cũ - CAGR": f"{m_old.get('cagr_pct', 0.0):.1f}%",
                "Mới - CAGR": f"{m_new.get('cagr_pct', 0.0):.1f}%",
                "Cũ - Sharpe": f"{m_old.get('sharpe_ratio', 0.0):.2f}",
                "Mới - Sharpe": f"{m_new.get('sharpe_ratio', 0.0):.2f}",
                "Cũ - Max DD": f"{m_old.get('max_drawdown_pct', 0.0):.1f}%",
                "Mới - Max DD": f"{m_new.get('max_drawdown_pct', 0.0):.1f}%",
                "Cũ - Profit Factor": f"{m_old.get('profit_factor', 0.0):.2f}x",
                "Mới - Profit Factor": f"{m_new.get('profit_factor', 0.0):.2f}x",
                "Trailing Stop": new_exit_reasons.get("TRAILING_STOP", 0),
                "RS Probe": probe_trades,
            }
        )

    df_comp = pd.DataFrame(rows)
    print(df_comp.to_string(index=False))
    print("=" * 90)

    # Save summary
    out_path = os.path.join(ROOT_DIR, "data", "alpha_tracker_exit_logic_comparison.csv")
    df_comp.to_csv(out_path, index=False, encoding="utf-8-sig")
    print(f"Đã lưu kết quả so sánh vào: {out_path}\n")

    # Run Ablation: Isolated effect of Trailing Stop vs RS Probe
    print("\n" + "=" * 90)
    print("PHÂN TÍCH BÓC TÁCH TỪNG CƠ CHẾ (ABLATION STUDY):")
    print("1. Baseline (Old Logic: RSI 75 cap + MA20 5% stop + Strict Cash Mode)")
    print("2. + Trailing Stop (Bỏ RSI 75 + Nới lỏng rũ bỏ + Trailing Stop 10% + Strict Cash Mode)")
    print("3. + Trailing Stop & RS Probe (Full New Logic: Trailing Stop 10% + Thăm dò 25% khi giữ MA50)")
    print("=" * 90)

    ablation_rows = []
    for sym in symbols:
        df_p = load_cached_ticker(sym)
        aligned_vni_ret = vni_returns.reindex(df_p.index).fillna(0.0)
        aligned_regimes = regimes.reindex(df_p.index).ffill().bfill()

        # Config 1: Old Logic
        old_sigs = generate_old_baseline_signals(df_p, aligned_regimes)
        res_old = RegimeBacktestEngine(
            enable_trailing_stop=False,
            allow_rs_probe=False,
        ).run_backtest(
            df_p, old_sigs, aligned_regimes, benchmark_returns=aligned_vni_ret, symbol=sym, enforce_regime_gate=True
        )

        # Config 2: Trailing Stop Only (No RS Probe, Strict Cash Mode)
        ts_only_sigs = generate_signals_by_strategy(
            df_p,
            regimes=aligned_regimes,
            enforce_regime_gate=True,
            allow_rs_probe=False,
        )
        res_ts_only = RegimeBacktestEngine(
            enable_trailing_stop=True,
            trailing_stop_pct=10.0,
            allow_rs_probe=False,
        ).run_backtest(
            df_p, ts_only_sigs, aligned_regimes, benchmark_returns=aligned_vni_ret, symbol=sym, enforce_regime_gate=True
        )

        # Config 3: Trailing Stop + RS Probe (Full New Logic)
        full_new_sigs = generate_signals_by_strategy(
            df_p,
            regimes=aligned_regimes,
            enforce_regime_gate=True,
            allow_rs_probe=True,
        )
        res_full_new = RegimeBacktestEngine(
            enable_trailing_stop=True,
            trailing_stop_pct=10.0,
            allow_rs_probe=True,
            probe_allocation_pct=0.25,
        ).run_backtest(
            df_p,
            full_new_sigs,
            aligned_regimes,
            benchmark_returns=aligned_vni_ret,
            symbol=sym,
            enforce_regime_gate=True,
        )

        ret_1 = ((res_old.equity_curve.iloc[-1] / res_old.equity_curve.iloc[0]) - 1.0) * 100.0
        ret_2 = ((res_ts_only.equity_curve.iloc[-1] / res_ts_only.equity_curve.iloc[0]) - 1.0) * 100.0
        ret_3 = ((res_full_new.equity_curve.iloc[-1] / res_full_new.equity_curve.iloc[0]) - 1.0) * 100.0

        m1 = res_old.summary_metrics
        m2 = res_ts_only.summary_metrics
        m3 = res_full_new.summary_metrics

        ablation_rows.append(
            {
                "Mã CP": sym,
                "1. Cũ (Return)": f"{ret_1:+.1f}%",
                "2. + Trailing Stop": f"{ret_2:+.1f}%",
                "3. + Trailing & RS Probe": f"{ret_3:+.1f}%",
                "1. Cũ (PF)": f"{m1.get('profit_factor', 0.0):.2f}x",
                "2. TS Only (PF)": f"{m2.get('profit_factor', 0.0):.2f}x",
                "3. Full New (PF)": f"{m3.get('profit_factor', 0.0):.2f}x",
                "1. Cũ (MDD)": f"{m1.get('max_drawdown_pct', 0.0):.1f}%",
                "3. Full New (MDD)": f"{m3.get('max_drawdown_pct', 0.0):.1f}%",
            }
        )

    df_abl = pd.DataFrame(ablation_rows)
    print(df_abl.to_string(index=False))
    print("=" * 90)


if __name__ == "__main__":
    run_comparison()
