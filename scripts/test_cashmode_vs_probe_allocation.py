"""Quantitative Study: Hard Cash Mode (0%) vs Probe Sleeve (10% - 15% - 25%) in Downtrend.

Answers the user question:
"Bật cashmode khi dưới MA200 có thật sự hoàn hảo hay nên thả 10-15% để thăm dò khi có cổ phiếu tốt - ngược sóng giảm?"

Tests:
1. Policy 0: Strict Cash Mode (0% - Khóa mua 100% khi VN-Index < MA200)
2. Policy 1: Probe Sleeve 10% (Thả 10% vốn thăm dò khi CP giữ MA50)
3. Policy 2: Probe Sleeve 15% (Thả 15% vốn thăm dò khi CP giữ MA50)
4. Policy 3: Probe Sleeve 25% (Thả 25% vốn thăm dò khi CP giữ MA50)
5. Policy 4: No Cash Mode (100% Full size bất chấp VN-Index)

Evaluates:
- Full Cycle (2018 - 2026, 1.995 bars) across VN30
- Covid Crash & V-Bottom 2020
- Bond / Credit Bear Market 2022
- Recent 500 bars & 200 bars
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


def run_portfolio_simulation(df_vni, regimes, vni_returns, policy_name, allow_probe, probe_pct, enforce_gate):
    """Run portfolio simulation across 26 VN30 stocks under given policy."""
    stock_equities = []
    trades_all = []

    for sym in VN30_TICKERS:
        df_p = load_cached_ticker(sym)
        if df_p.empty or len(df_p) < 100:
            continue

        aligned_vni_ret = vni_returns.reindex(df_p.index).fillna(0.0)
        aligned_regimes = regimes.reindex(df_p.index).ffill().bfill()

        sigs = generate_signals_by_strategy(
            df_p,
            regimes=aligned_regimes,
            enforce_regime_gate=enforce_gate,
            allow_rs_probe=allow_probe,
        )

        engine = RegimeBacktestEngine(
            initial_capital=100_000_000.0,
            enable_trailing_stop=True,
            trailing_stop_pct=10.0,
            allow_rs_probe=allow_probe,
            probe_allocation_pct=probe_pct,
        )

        res = engine.run_backtest(
            df_price=df_p,
            signals=sigs,
            regimes=aligned_regimes,
            benchmark_returns=aligned_vni_ret,
            symbol=sym,
            enforce_regime_gate=enforce_gate,
        )

        if not res.equity_curve.empty:
            # Normalized equity to 100
            norm_eq = (res.equity_curve / res.equity_curve.iloc[0]) * 100.0
            stock_equities.append(norm_eq)
            trades_all.extend(res.trades)

    if not stock_equities:
        return {}

    # Equal-weight portfolio equity curve
    df_eq_matrix = pd.concat(stock_equities, axis=1).ffill().bfill()
    port_equity = df_eq_matrix.mean(axis=1)

    total_ret = ((port_equity.iloc[-1] / port_equity.iloc[0]) - 1.0) * 100.0
    years = len(port_equity) / 250.0
    cagr = ((port_equity.iloc[-1] / port_equity.iloc[0]) ** (1.0 / max(years, 0.5)) - 1.0) * 100.0

    cummax = port_equity.cummax()
    dd = (port_equity - cummax) / cummax * 100.0
    max_dd = float(dd.min())

    ret_d = port_equity.pct_change().dropna()
    ann_vol = float(ret_d.std() * np.sqrt(250) * 100.0)
    excess_ret = ret_d - (0.045 / 250.0)
    sharpe = float((excess_ret.mean() / ret_d.std()) * np.sqrt(250)) if ret_d.std() > 0 else 0.0
    calmar = abs(cagr / max_dd) if abs(max_dd) > 0 else 0.0

    probe_count = sum(1 for t in trades_all if t.is_probe)
    total_trades = len(trades_all)
    wins = [t.net_pnl for t in trades_all if t.net_pnl > 0]
    losses = [abs(t.net_pnl) for t in trades_all if t.net_pnl < 0]
    pf = (sum(wins) / sum(losses)) if losses and sum(losses) > 0 else (99.0 if wins else 0.0)
    wr = (len(wins) / total_trades * 100.0) if total_trades > 0 else 0.0

    return {
        "policy": policy_name,
        "equity": port_equity,
        "total_ret": total_ret,
        "cagr": cagr,
        "max_dd": max_dd,
        "sharpe": sharpe,
        "calmar": calmar,
        "ann_vol": ann_vol,
        "profit_factor": pf,
        "win_rate": wr,
        "total_trades": total_trades,
        "probe_trades": probe_count,
    }


def slice_period_metrics(eq_series, start_dt, end_dt):
    """Slice equity series within [start_dt, end_dt] and compute return and MDD."""
    try:
        sub = eq_series.loc[start_dt:end_dt]
        if sub.empty or len(sub) < 5:
            return 0.0, 0.0
        ret = ((sub.iloc[-1] / sub.iloc[0]) - 1.0) * 100.0
        cummax = sub.cummax()
        dd = (sub - cummax) / cummax * 100.0
        return ret, float(dd.min())
    except Exception:
        return 0.0, 0.0


def main():
    df_vni = load_cached_ticker("VNINDEX")
    if df_vni.empty:
        print("Lỗi: Không tìm thấy dữ liệu VNINDEX.")
        return

    regimes = classify_market_regime(df_vni)
    vni_returns = df_vni["close"].pct_change().fillna(0.0)

    policies = [
        ("1. Hard Cash Mode (0% Mua khi VNI < MA200)", False, 0.00, True),
        ("2. Thăm dò Nhỏ (Probe 10% khi CP giữ MA50)", True, 0.10, True),
        ("3. Thăm dò Chuẩn (Probe 15% khi CP giữ MA50)", True, 0.15, True),
        ("4. Thăm dò Mạnh (Probe 25% khi CP giữ MA50)", True, 0.25, True),
        ("5. Bỏ Cash Mode (100% Full Size mọi lúc)", False, 0.95, False),
    ]

    results = []
    print("\n" + "=" * 115)
    print("🔬 NGHIÊN CỨU ĐỊNH LƯỢNG: HARD CASH MODE (0%) VS THẢ THĂM DÒ (10% - 15% - 25%) TRONG DOWNTREND")
    print("Dữ liệu: 26 Cổ phiếu VN30 + VN-Index (2018 - 2026, 1.995 phiên)")
    print("=" * 115)

    for name, allow_p, p_pct, enf_gate in policies:
        res = run_portfolio_simulation(df_vni, regimes, vni_returns, name, allow_p, p_pct, enf_gate)
        results.append(res)

    # 1. Full Period Summary
    print("\n" + "=" * 115)
    print("BẢNG 1: HIỆU SUẤT TOÀN KỲ (2018 - 2026) TRÊN RỔ DANH MỤC VN30")
    print("=" * 115)
    t1_rows = []
    for r in results:
        t1_rows.append(
            {
                "Chiến lược": r["policy"],
                "Tổng Lãi (%)": f"{r['total_ret']:+.2f}%",
                "CAGR (%)": f"{r['cagr']:.2f}%",
                "Max Drawdown": f"{r['max_dd']:.2f}%",
                "Sharpe": f"{r['sharpe']:.2f}",
                "Calmar": f"{r['calmar']:.2f}",
                "Profit Factor": f"{r['profit_factor']:.2f}x",
                "Win Rate": f"{r['win_rate']:.1f}%",
                "Số Lệnh": r["total_trades"],
                "Lệnh Thăm Dò": r["probe_trades"],
            }
        )
    df_t1 = pd.DataFrame(t1_rows)
    print(df_t1.to_string(index=False))

    # 2. Crisis Stress Breakdown
    print("\n" + "=" * 115)
    print("BẢNG 2: BÓC TÁCH HIỆU SUẤT QUA 3 GIAI ĐOẠN KHỦNG HOẢNG & ĐẢO CHIỀU LỊCH SỬ")
    print("=" * 115)
    periods = [
        ("Covid Crash & V-Bottom (01/2020 -> 12/2020)", "2020-01-01", "2020-12-31"),
        ("Đại suy thoái Trái phiếu / Bắt bớ (04/2022 -> 11/2022)", "2022-04-01", "2022-11-30"),
        ("Sóng Phục hồi & Tích lũy (01/2023 -> 10/2026)", "2023-01-01", "2026-10-06"),
    ]

    t2_rows = []
    for p_label, p_start, p_end in periods:
        row = {"Giai đoạn": p_label}
        for r in results:
            ret, mdd = slice_period_metrics(r["equity"], p_start, p_end)
            col_name = r["policy"].split(" (")[0]
            row[f"{col_name} (Lãi)"] = f"{ret:+.1f}%"
            row[f"{col_name} (MDD)"] = f"{mdd:.1f}%"
        t2_rows.append(row)

    df_t2 = pd.DataFrame(t2_rows)
    # Transpose for easier reading
    print(df_t2.T.to_string())

    # 3. Horizon 200 & 500 bars
    print("\n" + "=" * 115)
    print("BẢNG 3: HIỆU SUẤT KHUNG 200 PHIÊN VÀ 500 PHIÊN GẦN NHẤT")
    print("=" * 115)
    t3_rows = []
    for r in results:
        ret_200, mdd_200 = slice_period_metrics(r["equity"], df_vni.index[-200], df_vni.index[-1])
        ret_500, mdd_500 = slice_period_metrics(r["equity"], df_vni.index[-500], df_vni.index[-1])
        t3_rows.append(
            {
                "Chiến lược": r["policy"],
                "200P Lãi (%)": f"{ret_200:+.2f}%",
                "200P MDD": f"{mdd_200:.2f}%",
                "500P Lãi (%)": f"{ret_500:+.2f}%",
                "500P MDD": f"{mdd_500:.2f}%",
            }
        )
    df_t3 = pd.DataFrame(t3_rows)
    print(df_t3.to_string(index=False))

    # Save to CSV
    csv_path = os.path.join(ROOT_DIR, "data", "cashmode_vs_probe_study.csv")
    df_t1.to_csv(csv_path, index=False, encoding="utf-8-sig")
    print(f"\n-> Đã lưu bảng tổng hợp ra: {csv_path}\n")


if __name__ == "__main__":
    main()
