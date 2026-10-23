"""Backtest VN30 Basket across 200 and 500 trading sessions.

Compares:
- Old Logic: Hard RSI 75 profit cap, MA20*0.95 tight shakeout stop, strict Cash Mode.
- New Logic: Peak Trailing Stop (10%), loosened shakeout stop (MA50 breakdown), RS Probe sleeve (25%).

Outputs full comparative diagnostics for both 200-bar and 500-bar horizons.
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

VN30_TICKERS = [
    "ACB",
    "BID",
    "CTG",
    "FPT",
    "GAS",
    "GVR",
    "HDB",
    "HPG",
    "MBB",
    "MSN",
    "MWG",
    "PLX",
    "POW",
    "SAB",
    "SHB",
    "SSB",
    "SSI",
    "STB",
    "TCB",
    "TPB",
    "VHM",
    "VIB",
    "VIC",
    "VNM",
    "VPB",
    "VRE",
]


def load_cached_ticker(symbol: str) -> pd.DataFrame:
    file_path = os.path.join(CACHE_DIR, f"{symbol}_2018-01-01_2026-10-06.csv")
    if not os.path.exists(file_path):
        file_path = os.path.join(CACHE_DIR, f"{symbol}_2018-01-01_2024-12-31.csv")
    if not os.path.exists(file_path):
        return pd.DataFrame()
    df = pd.read_csv(file_path)
    df["time"] = pd.to_datetime(df["time"])
    df = df.sort_values("time").reset_index(drop=True)
    df = df.set_index("time")
    return df


def generate_old_baseline_signals(df_price: pd.DataFrame, regimes: pd.Series) -> pd.Series:
    """Old baseline rules: RSI >= 75 sell, MA20*0.95 sell, hard Cash Mode."""
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


def run_horizon_backtest(horizon_bars: int, df_vni: pd.DataFrame, regimes: pd.Series, vni_returns: pd.Series):
    """Run backtest comparison across VN30 for a specific lookback horizon."""
    vni_sub = df_vni.tail(horizon_bars)
    start_date = vni_sub.index[0].strftime("%d/%m/%Y")
    end_date = vni_sub.index[-1].strftime("%d/%m/%Y")

    print("\n" + "=" * 105)
    print(f"BÁO CÁO KIỂM ĐỊNH RỔ CỔ PHIẾU VN30 - KHUNG THỜI GIAN {horizon_bars} PHIÊN ({start_date} -> {end_date})")
    print("=" * 105)

    rows = []
    engine_old = RegimeBacktestEngine(initial_capital=100_000_000.0, enable_trailing_stop=False, allow_rs_probe=False)
    engine_new = RegimeBacktestEngine(
        initial_capital=100_000_000.0,
        enable_trailing_stop=True,
        trailing_stop_pct=10.0,
        allow_rs_probe=True,
        probe_allocation_pct=0.25,
    )

    for sym in VN30_TICKERS:
        df_full = load_cached_ticker(sym)
        if df_full.empty or len(df_full) < horizon_bars:
            continue

        df_p = df_full.tail(horizon_bars)
        aligned_vni_ret = vni_returns.reindex(df_p.index).fillna(0.0)
        aligned_regimes = regimes.reindex(df_p.index).ffill().bfill()

        # 1. Old Logic
        old_sigs = generate_old_baseline_signals(df_p, aligned_regimes)
        res_old = engine_old.run_backtest(
            df_price=df_p,
            signals=old_sigs,
            regimes=aligned_regimes,
            benchmark_returns=aligned_vni_ret,
            symbol=sym,
            enforce_regime_gate=True,
        )
        m_old = res_old.summary_metrics
        ret_old = (
            ((res_old.equity_curve.iloc[-1] / res_old.equity_curve.iloc[0]) - 1.0) * 100.0
            if not res_old.equity_curve.empty
            else 0.0
        )

        # 2. New Logic
        new_sigs = generate_signals_by_strategy(
            df_p,
            regimes=aligned_regimes,
            enforce_regime_gate=True,
            allow_rs_probe=True,
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
        ret_new = (
            ((res_new.equity_curve.iloc[-1] / res_new.equity_curve.iloc[0]) - 1.0) * 100.0
            if not res_new.equity_curve.empty
            else 0.0
        )

        trailing_exits = sum(1 for t in res_new.trades if t.exit_reason == "TRAILING_STOP")
        probe_trades = sum(1 for t in res_new.trades if t.is_probe)

        rows.append(
            {
                "Mã CP": sym,
                "Lãi Cũ (%)": ret_old,
                "Lãi Mới (%)": ret_new,
                "Delta Net (%)": ret_new - ret_old,
                "PF Cũ": m_old.get("profit_factor", 0.0),
                "PF Mới": m_new.get("profit_factor", 0.0),
                "MDD Cũ (%)": m_old.get("max_drawdown_pct", 0.0),
                "MDD Mới (%)": m_new.get("max_drawdown_pct", 0.0),
                "Lệnh Cũ": m_old.get("total_trades", 0),
                "Lệnh Mới": m_new.get("total_trades", 0),
                "Trailing Stop": trailing_exits,
                "RS Probe": probe_trades,
            }
        )

    df_res = pd.DataFrame(rows)

    # Format for display
    df_disp = df_res.copy()
    df_disp["Lãi Cũ (%)"] = df_disp["Lãi Cũ (%)"].map(lambda x: f"{x:+.1f}%")
    df_disp["Lãi Mới (%)"] = df_disp["Lãi Mới (%)"].map(lambda x: f"{x:+.1f}%")
    df_disp["Delta Net (%)"] = df_disp["Delta Net (%)"].map(lambda x: f"{x:+.1f}%")
    df_disp["PF Cũ"] = df_disp["PF Cũ"].map(lambda x: f"{x:.2f}x")
    df_disp["PF Mới"] = df_disp["PF Mới"].map(lambda x: f"{x:.2f}x")
    df_disp["MDD Cũ (%)"] = df_disp["MDD Cũ (%)"].map(lambda x: f"{x:.1f}%")
    df_disp["MDD Mới (%)"] = df_disp["MDD Mới (%)"].map(lambda x: f"{x:.1f}%")

    print(df_disp.to_string(index=False))

    # Portfolio Aggregates
    avg_ret_old = df_res["Lãi Cũ (%)"].mean()
    avg_ret_new = df_res["Lãi Mới (%)"].mean()
    avg_pf_old = df_res["PF Cũ"].replace(0, np.nan).mean()
    avg_pf_new = df_res["PF Mới"].replace(0, np.nan).mean()
    avg_mdd_old = df_res["MDD Cũ (%)"].mean()
    avg_mdd_new = df_res["MDD Mới (%)"].mean()
    better_count = (df_res["Lãi Mới (%)"] > df_res["Lãi Cũ (%)"]).sum()
    total_count = len(df_res)

    print("\n" + "-" * 105)
    print(f"📊 CHỈ SỐ BÌNH QUÂN TOÀN RỔ VN30 ({total_count} MÃ) - KHUNG {horizon_bars} PHIÊN:")
    print(
        f"- Lợi nhuận bình quân toàn rổ: Cũ = {avg_ret_old:+.2f}%  -->  Mới = {avg_ret_new:+.2f}%  (Chênh lệch: {avg_ret_new - avg_ret_old:+.2f}%)"
    )
    print(f"- Profit Factor bình quân:    Cũ = {avg_pf_old:.2f}x    -->  Mới = {avg_pf_new:.2f}x")
    print(f"- Max Drawdown bình quân:      Cũ = {avg_mdd_old:.1f}%   -->  Mới = {avg_mdd_new:.1f}%")
    print(f"- Số mã có hiệu suất tốt hơn:  {better_count}/{total_count} mã ({better_count / total_count * 100:.1f}%)")
    print("-" * 105)

    csv_path = os.path.join(ROOT_DIR, "data", f"vn30_backtest_{horizon_bars}_bars.csv")
    df_res.to_csv(csv_path, index=False, encoding="utf-8-sig")
    print(f"-> Đã lưu bảng chi tiết ra: {csv_path}")

    return {
        "horizon": horizon_bars,
        "count": total_count,
        "avg_ret_old": avg_ret_old,
        "avg_ret_new": avg_ret_new,
        "delta_ret": avg_ret_new - avg_ret_old,
        "avg_pf_old": avg_pf_old,
        "avg_pf_new": avg_pf_new,
        "avg_mdd_old": avg_mdd_old,
        "avg_mdd_new": avg_mdd_new,
        "better_count": better_count,
        "df": df_res,
    }


def main():
    df_vni = load_cached_ticker("VNINDEX")
    if df_vni.empty:
        print("Lỗi: Không tìm thấy dữ liệu VNINDEX trong cache.")
        return

    regimes = classify_market_regime(df_vni)
    vni_returns = df_vni["close"].pct_change().fillna(0.0)

    res_200 = run_horizon_backtest(200, df_vni, regimes, vni_returns)
    res_500 = run_horizon_backtest(500, df_vni, regimes, vni_returns)

    print("\n" + "=" * 105)
    print("🏆 BẢNG TỔNG KẾT SO SÁNH ĐỐI CHỨNG RỔ VN30 (200 PHIÊN VS 500 PHIÊN)")
    print("=" * 105)
    summary_data = [
        {
            "Khung thời gian": "200 Phiên (~1 Năm gần nhất)",
            "Lợi nhuận TB (Cũ)": f"{res_200['avg_ret_old']:+.2f}%",
            "Lợi nhuận TB (Mới)": f"{res_200['avg_ret_new']:+.2f}%",
            "Chênh lệch": f"{res_200['delta_ret']:+.2f}%",
            "Profit Factor (Cũ -> Mới)": f"{res_200['avg_pf_old']:.2f}x -> {res_200['avg_pf_new']:.2f}x",
            "Max Drawdown (Cũ -> Mới)": f"{res_200['avg_mdd_old']:.1f}% -> {res_200['avg_mdd_new']:.1f}%",
            "Tỷ lệ mã vượt trội": f"{res_200['better_count']}/{res_200['count']} ({res_200['better_count'] / res_200['count'] * 100:.1f}%)",
        },
        {
            "Khung thời gian": "500 Phiên (~2 Năm gần nhất)",
            "Lợi nhuận TB (Cũ)": f"{res_500['avg_ret_old']:+.2f}%",
            "Lợi nhuận TB (Mới)": f"{res_500['avg_ret_new']:+.2f}%",
            "Chênh lệch": f"{res_500['delta_ret']:+.2f}%",
            "Profit Factor (Cũ -> Mới)": f"{res_500['avg_pf_old']:.2f}x -> {res_500['avg_pf_new']:.2f}x",
            "Max Drawdown (Cũ -> Mới)": f"{res_500['avg_mdd_old']:.1f}% -> {res_500['avg_mdd_new']:.1f}%",
            "Tỷ lệ mã vượt trội": f"{res_500['better_count']}/{res_500['count']} ({res_500['better_count'] / res_500['count'] * 100:.1f}%)",
        },
    ]
    df_sum = pd.DataFrame(summary_data)
    print(df_sum.to_string(index=False))
    print("=" * 105)

    sum_path = os.path.join(ROOT_DIR, "data", "vn30_backtest_summary_comparison.csv")
    df_sum.to_csv(sum_path, index=False, encoding="utf-8-sig")
    print(f"\nĐã lưu báo cáo tổng kết ra: {sum_path}\n")


if __name__ == "__main__":
    main()
