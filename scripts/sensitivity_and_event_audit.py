"""Audit Script: Sensitivity Grid, Event-by-Event Comparison, and Extended Risk Metrics.

Covers:
1. Verification of Ablation 2 (Downside Vol Target) Gross vs Net
2. Sensitivity Grid for Ablation 1b: k in [0.06..0.20], floor in [1.0%..2.5%], window in [10, 20, 60]
3. Event-by-event breakdown of Flips in 2020, 2022, and 2026
4. Extended Risk Metrics: Ulcer Index, Average Drawdown, Time Underwater (%)
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


def compute_extended_risk_metrics(series):
    """Compute Ulcer Index, Average Drawdown, Time Underwater."""
    cummax = series.cummax()
    dd_pct = (series - cummax) / cummax * 100.0

    # Ulcer Index = sqrt(mean(dd_pct^2))
    ulcer_index = np.sqrt((dd_pct**2).mean())
    avg_dd = dd_pct[dd_pct < 0].mean() if (dd_pct < 0).any() else 0.0
    time_underwater = (dd_pct < -0.1).mean() * 100.0

    return {
        "Ulcer Index": round(ulcer_index, 2),
        "Avg Drawdown (%)": round(avg_dd, 2),
        "Time Underwater (%)": round(time_underwater, 1),
    }


def audit_ablation_2_gross(df_vn, eq_daily_ret):
    close = df_vn["close"]
    ma200 = close.rolling(200, min_periods=50).mean()
    n = len(df_vn)

    ret = close.pct_change().fillna(0.0)
    downside_ret = ret.apply(lambda x: x if x < 0 else 0.0)
    downside_vol20 = np.sqrt((downside_ret**2).rolling(20, min_periods=10).mean()) * np.sqrt(250) * 100.0

    alloc_base = []
    state_b = "SIDEWAYS"
    for i in range(n):
        c, m = close.iloc[i], ma200.iloc[i]
        if pd.isna(m) or m <= 0:
            alloc_base.append(0.5)
            continue
        if c > m * 1.015:
            state_b = "UPTREND"
        elif c < m * 0.985:
            state_b = "DOWNTREND"
        alloc_base.append(1.0 if state_b == "UPTREND" else (0.0 if state_b == "DOWNTREND" else 0.5))

    alloc_2 = []
    for i in range(n):
        b = alloc_base[i]
        d_vol = downside_vol20.iloc[i] if not pd.isna(downside_vol20.iloc[i]) else 10.0
        scalar = min(1.0, 11.0 / max(d_vol, 7.0))
        alloc_2.append(round(b * scalar, 4))

    s_alloc_2 = pd.Series(alloc_2, index=df_vn["time"])
    s_net, to_net = run_simulation(df_vn, eq_daily_ret, s_alloc_2, fee_rate=0.0025)
    s_gross, to_gross = run_simulation(df_vn, eq_daily_ret, s_alloc_2, fee_rate=0.0)

    m_net = calculate_metrics(s_net)
    m_gross = calculate_metrics(s_gross)

    return m_gross, m_net, to_net


def run_sensitivity_grid_1b(df_vn, eq_daily_ret):
    close = df_vn["close"]
    ma200 = close.rolling(200, min_periods=50).mean()
    ret = close.pct_change().fillna(0.0)
    n = len(df_vn)

    k_values = [0.06, 0.08, 0.10, 0.12, 0.14, 0.16, 0.18, 0.20]
    floor_values = [0.010, 0.015, 0.020, 0.025]
    windows = [10, 20, 60]

    grid_results = []

    for w in windows:
        ann_vol = ret.rolling(w, min_periods=max(5, w // 2)).std() * np.sqrt(250) * 100.0
        for floor_b in floor_values:
            for k in k_values:
                alloc_grid = []
                state_g = "SIDEWAYS"
                for i in range(n):
                    c, m = close.iloc[i], ma200.iloc[i]
                    v = ann_vol.iloc[i] if not pd.isna(ann_vol.iloc[i]) else 18.0
                    dyn_band = max(floor_b, (v / 100.0) * k)

                    if pd.isna(m) or m <= 0:
                        alloc_grid.append(0.5)
                        continue
                    if c > m * (1.0 + dyn_band):
                        state_g = "UPTREND"
                    elif c < m * (1.0 - dyn_band):
                        state_g = "DOWNTREND"
                    alloc_grid.append(1.0 if state_g == "UPTREND" else (0.0 if state_g == "DOWNTREND" else 0.5))

                s_alloc = pd.Series(alloc_grid, index=df_vn["time"])
                s_sim, to_sim = run_simulation(df_vn, eq_daily_ret, s_alloc, fee_rate=0.0025)
                m = calculate_metrics(s_sim)
                flips = int((s_alloc.diff().abs() > 0.05).sum())

                # Also test In-Sample and Out-of-Sample
                s_is = s_sim.loc[:"2022-12-31"]
                m_is = calculate_metrics(s_is)
                s_oos = s_sim.loc["2023-01-01":]
                m_oos = calculate_metrics(s_oos)

                grid_results.append(
                    {
                        "vol_window": w,
                        "floor_band (%)": floor_b * 100.0,
                        "k_multiplier": k,
                        "CAGR_Full": m["CAGR (%)"],
                        "MaxDD_Full": m["Max Drawdown (%)"],
                        "Calmar_Full": m["Calmar"],
                        "Turnover": round(to_sim, 1),
                        "Flips": flips,
                        "CAGR_IS": m_is["CAGR (%)"],
                        "MaxDD_IS": m_is["Max Drawdown (%)"],
                        "CAGR_OOS": m_oos["CAGR (%)"],
                        "MaxDD_OOS": m_oos["Max Drawdown (%)"],
                    }
                )

    return pd.DataFrame(grid_results)


def trace_event_by_event_flips(df_vn):
    """Trace exact flips of Baseline vs 1b in 2020, 2022, 2026."""
    close = df_vn["close"]
    ma200 = close.rolling(200, min_periods=50).mean()
    ret = close.pct_change().fillna(0.0)
    ann_vol20 = ret.rolling(20, min_periods=10).std() * np.sqrt(250) * 100.0
    n = len(df_vn)

    # Base
    base_states = []
    sb = "SIDEWAYS"
    for i in range(n):
        c, m = close.iloc[i], ma200.iloc[i]
        if pd.isna(m) or m <= 0:
            base_states.append("SIDEWAYS")
            continue
        if c > m * 1.015:
            sb = "UPTREND"
        elif c < m * 0.985:
            sb = "DOWNTREND"
        base_states.append(sb)

    # 1b
    b1_states = []
    s1 = "SIDEWAYS"
    for i in range(n):
        c, m = close.iloc[i], ma200.iloc[i]
        v = ann_vol20.iloc[i] if not pd.isna(ann_vol20.iloc[i]) else 18.0
        dyn_band = max(0.015, (v / 100.0) * 0.12)
        if pd.isna(m) or m <= 0:
            b1_states.append("SIDEWAYS")
            continue
        if c > m * (1.0 + dyn_band):
            s1 = "UPTREND"
        elif c < m * (1.0 - dyn_band):
            s1 = "DOWNTREND"
        b1_states.append(s1)

    df_flips = pd.DataFrame(
        {
            "time": df_vn["time"],
            "close": close,
            "ma200": ma200,
            "ann_vol20": ann_vol20,
            "base_state": base_states,
            "b1_state": b1_states,
        }
    ).set_index("time")

    # Filter key event windows: 2020, 2022, 2026
    events = {
        "2020 Covid (Jan-Dec 2020)": ("2020-01-01", "2020-12-31"),
        "2022 Bear Market (Jan-Dec 2022)": ("2022-01-01", "2022-12-31"),
        "2026 Whipsaw Period (Feb-Oct 2026)": ("2026-02-15", "2026-10-06"),
    }

    event_logs = {}
    for ev_name, (st, en) in events.items():
        ev_df = df_flips.loc[st:en]
        base_chg = ev_df[ev_df["base_state"] != ev_df["base_state"].shift(1)].copy()
        b1_chg = ev_df[ev_df["b1_state"] != ev_df["b1_state"].shift(1)].copy()
        event_logs[ev_name] = {
            "base_flips": base_chg[["close", "ma200", "base_state"]],
            "b1_flips": b1_chg[["close", "ma200", "ann_vol20", "b1_state"]],
        }

    return event_logs


if __name__ == "__main__":
    df_vn, eq_daily_ret = load_environment()

    # 1. Ablation 2 Gross vs Net
    m_gross2, m_net2, to2 = audit_ablation_2_gross(df_vn, eq_daily_ret)
    print("=" * 80)
    print("1. XÁC MINH ABLATION 2 (DOWNSIDE VOL TARGET) GROSS VS NET")
    print("=" * 80)
    print(
        f"Gross CAGR: {m_gross2['CAGR (%)']}% | Net CAGR: {m_net2['CAGR (%)']}% | Fee Drag: {m_gross2['CAGR (%)'] - m_net2['CAGR (%)']:.2f}%/yr"
    )
    print(f"Annual Turnover: {to2:.1f}%")
    print(f"Khoảng cách vs Baseline Net (15.54%): {15.54 - m_net2['CAGR (%)']:.2f}%")
    fee_part = m_gross2["CAGR (%)"] - m_net2["CAGR (%)"]
    strat_part = 15.54 - m_gross2["CAGR (%)"]
    print(
        f"Phân tách: Do ma sát phí = {fee_part:.2f}% ({fee_part / (15.54 - m_net2['CAGR (%)']) * 100:.1f}%), Do hạ tỷ trọng thị trường = {strat_part:.2f}% ({strat_part / (15.54 - m_net2['CAGR (%)']) * 100:.1f}%)"
    )

    # 2. Extended Risk Metrics for Baseline vs 1b
    from scripts.ablation_regime_study import generate_regime_allocations

    variants = generate_regime_allocations(df_vn)
    s_base, _ = run_simulation(df_vn, eq_daily_ret, variants["Baseline (Binary MA200)"])
    s_1b, _ = run_simulation(df_vn, eq_daily_ret, variants["Ablation 1b (Dynamic Vol Band)"])

    print("\n" + "=" * 80)
    print("2. BỘ CHỈ SỐ RỦI RO MỞ RỘNG (EXTENDED RISK METRICS)")
    print("=" * 80)
    risk_base = compute_extended_risk_metrics(s_base)
    risk_1b = compute_extended_risk_metrics(s_1b)
    df_risk = pd.DataFrame([risk_base, risk_1b], index=["Baseline (Binary MA200)", "Ablation 1b (Dynamic Vol Band)"])
    print(df_risk.to_string())

    # 3. Event-by-event Flips
    print("\n" + "=" * 80)
    print("3. BẢNG THEO DÕI TỪNG SỰ KIỆN (EVENT-BY-EVENT FLIPS)")
    print("=" * 80)
    event_logs = trace_event_by_event_flips(df_vn)
    for ev_name, data in event_logs.items():
        print(f"\n--- {ev_name} ---")
        print("BASELINE FLIPS:")
        for idx, row in data["base_flips"].iterrows():
            print(
                f"  {idx.strftime('%Y-%m-%d')}: Close={row['close']:.1f}, MA200={row['ma200']:.1f} -> State={row['base_state']}"
            )
        print("ABLATION 1b FLIPS:")
        for idx, row in data["b1_flips"].iterrows():
            v = row["ann_vol20"]
            dyn_b = max(1.5, v * 0.12)
            print(
                f"  {idx.strftime('%Y-%m-%d')}: Close={row['close']:.1f}, MA200={row['ma200']:.1f}, Vol={v:.1f}% (Band +/-{dyn_b:.1f}%) -> State={row['b1_state']}"
            )

    # 4. Sensitivity Grid for 1b
    print("\n" + "=" * 80)
    print("4. LƯỚI ĐỘ NHẠY THAM SỐ ABLATION 1b (WINDOW=20, FLOOR=1.5%)")
    print("=" * 80)
    grid_df = run_sensitivity_grid_1b(df_vn, eq_daily_ret)
    # Focus on window=20, floor=1.5%
    slice_20_15 = grid_df[(grid_df["vol_window"] == 20) & (grid_df["floor_band (%)"] == 1.5)]
    print(
        slice_20_15[
            ["k_multiplier", "CAGR_Full", "MaxDD_Full", "Calmar_Full", "Flips", "CAGR_IS", "CAGR_OOS", "MaxDD_OOS"]
        ].to_string(index=False)
    )

    print("\nLưới Floor Band (k=0.12, Window=20):")
    slice_floor = grid_df[(grid_df["vol_window"] == 20) & (grid_df["k_multiplier"] == 0.12)]
    print(
        slice_floor[["floor_band (%)", "CAGR_Full", "MaxDD_Full", "Calmar_Full", "Flips", "MaxDD_OOS"]].to_string(
            index=False
        )
    )
