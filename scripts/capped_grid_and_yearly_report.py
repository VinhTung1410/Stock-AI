"""Yearly breakdown and Capped Sensitivity Grid.

Demonstrates:
1. Exact year-by-year metrics for Baseline, 1b Uncapped, and 1b Capped (at 3.0%)
2. Sensitivity grid across vol_window in [10, 20, 60], cap in [2.5%, 3.0%, 3.5%], k in [0.08..0.16]
3. Verifies how the 3% cap impacts the March 23, 2026 exit
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

from scripts.ablation_regime_study import calculate_metrics, load_environment, run_simulation


def generate_capped_alloc(df_vn, window=20, k=0.12, floor_b=0.015, cap_b=0.03):
    close = df_vn["close"]
    n = len(df_vn)
    ma200 = close.rolling(200, min_periods=50).mean()
    ret = close.pct_change().fillna(0.0)
    ann_vol = ret.rolling(window, min_periods=max(5, window // 2)).std() * np.sqrt(250) * 100.0

    alloc = []
    state = "SIDEWAYS"
    for i in range(n):
        c, m = close.iloc[i], ma200.iloc[i]
        v = ann_vol.iloc[i] if not pd.isna(ann_vol.iloc[i]) else 18.0
        dyn_band = min(cap_b, max(floor_b, (v / 100.0) * k)) if cap_b else max(floor_b, (v / 100.0) * k)

        if pd.isna(m) or m <= 0:
            alloc.append(0.5)
            continue
        if c > m * (1.0 + dyn_band):
            state = "UPTREND"
        elif c < m * (1.0 - dyn_band):
            state = "DOWNTREND"
        alloc.append(1.0 if state == "UPTREND" else (0.0 if state == "DOWNTREND" else 0.5))
    return pd.Series(alloc, index=df_vn["time"])


def run_yearly_and_grid():
    df_vn, eq_daily_ret = load_environment()
    close = df_vn["close"]
    n = len(df_vn)
    ma200 = close.rolling(200, min_periods=50).mean()

    # 1. Baseline
    alloc_base = []
    sb = "SIDEWAYS"
    for i in range(n):
        c, m = close.iloc[i], ma200.iloc[i]
        if pd.isna(m) or m <= 0:
            alloc_base.append(0.5)
            continue
        if c > m * 1.015:
            sb = "UPTREND"
        elif c < m * 0.985:
            sb = "DOWNTREND"
        alloc_base.append(1.0 if sb == "UPTREND" else (0.0 if sb == "DOWNTREND" else 0.5))
    s_alloc_base = pd.Series(alloc_base, index=df_vn["time"])

    # 2. 1b Uncapped
    s_alloc_1b_uncapped = generate_capped_alloc(df_vn, window=20, k=0.12, floor_b=0.015, cap_b=None)

    # 3. 1b Capped at 3.0%
    s_alloc_1b_capped3 = generate_capped_alloc(df_vn, window=20, k=0.12, floor_b=0.015, cap_b=0.03)

    sim_base, _ = run_simulation(df_vn, eq_daily_ret, s_alloc_base)
    sim_1b_uncapped, _ = run_simulation(df_vn, eq_daily_ret, s_alloc_1b_uncapped)
    sim_1b_capped3, _ = run_simulation(df_vn, eq_daily_ret, s_alloc_1b_capped3)

    # Yearly comparison
    print("=" * 90)
    print("BẢNG THEO DÕI TỪNG NĂM: BASELINE VS 1b UNCAPPED VS 1b CAPPED (3.0%)")
    print("=" * 90)
    years = [2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025, 2026]
    yearly_rows = []
    for y in years:
        s_date = f"{y}-01-01" if y > 2018 else "2018-10-08"
        e_date = f"{y}-12-31" if y < 2026 else "2026-10-06"

        b_slice = sim_base.loc[s_date:e_date]
        u_slice = sim_1b_uncapped.loc[s_date:e_date]
        c_slice = sim_1b_capped3.loc[s_date:e_date]

        b_ret = (b_slice.iloc[-1] / b_slice.iloc[0] - 1.0) * 100.0
        u_ret = (u_slice.iloc[-1] / u_slice.iloc[0] - 1.0) * 100.0
        c_ret = (c_slice.iloc[-1] / c_slice.iloc[0] - 1.0) * 100.0

        b_mdd = ((b_slice - b_slice.cummax()) / b_slice.cummax() * 100.0).min()
        u_mdd = ((u_slice - u_slice.cummax()) / u_slice.cummax() * 100.0).min()
        c_mdd = ((c_slice - c_slice.cummax()) / c_slice.cummax() * 100.0).min()

        yearly_rows.append(
            {
                "Year": y,
                "Baseline Return (%)": round(b_ret, 2),
                "Baseline MDD (%)": round(b_mdd, 2),
                "1b Uncapped Return (%)": round(u_ret, 2),
                "1b Uncapped MDD (%)": round(u_mdd, 2),
                "1b Capped (3%) Return (%)": round(c_ret, 2),
                "1b Capped (3%) MDD (%)": round(c_mdd, 2),
            }
        )

    df_years = pd.DataFrame(yearly_rows).set_index("Year")
    print(df_years.to_string())

    # Full period metrics
    m_base = calculate_metrics(sim_base)
    m_u = calculate_metrics(sim_1b_uncapped)
    m_c = calculate_metrics(sim_1b_capped3)

    print("\n" + "=" * 90)
    print("TỔNG HỢP TOÀN KỲ (2018 - 2026)")
    print("=" * 90)
    df_tot = pd.DataFrame(
        [m_base, m_u, m_c],
        index=[
            "Baseline (Binary MA200)",
            "1b Uncapped (max 1.5%, vol*0.12)",
            "1b Capped 3% (min 3%, max 1.5%, vol*0.12)",
        ],
    )
    print(df_tot.to_string())

    # Sensitivity Grid with Cap = 3.0% and windows [10, 20, 60]
    print("\n" + "=" * 90)
    print("LƯỚI ĐỘ NHẠY THAM SỐ CÓ TRẦN CAP = 3.0% (WINDOWS: 10, 20, 60)")
    print("=" * 90)
    grid_rows = []
    for w in [10, 20, 60]:
        for k in [0.08, 0.10, 0.12, 0.14, 0.16]:
            alloc_g = generate_capped_alloc(df_vn, window=w, k=k, floor_b=0.015, cap_b=0.03)
            s_g, to_g = run_simulation(df_vn, eq_daily_ret, alloc_g)
            m_g = calculate_metrics(s_g)
            grid_rows.append(
                {
                    "Window": w,
                    "k": k,
                    "CAGR": m_g["CAGR (%)"],
                    "MaxDD": m_g["Max Drawdown (%)"],
                    "Calmar": m_g["Calmar"],
                    "Turnover": round(to_g, 1),
                }
            )
    df_grid = pd.DataFrame(grid_rows)
    print(df_grid.to_string(index=False))


if __name__ == "__main__":
    run_yearly_and_grid()
