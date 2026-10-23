"""Ablation Study: Rigorous component-by-component testing of Regime improvements.

Tests on 55 Stocks + VN-Index (2018-2026):
1. Baseline: Binary MA200 (Current logic: +/-1.5% fixed hysteresis)
2. Ablation 1a: Min Holding Window (>=15 trading days in a state before allowing next flip)
3. Ablation 1b: Volatility-Adjusted Dynamic Hysteresis Band
4. Ablation 1c: Asymmetric Re-entry (Fast exit 0%, Staged re-entry: 50% on cross, 100% after 10 days)
5. Ablation 2: Pure Downside Volatility Targeting (Semi-deviation, ignores upside vol)
6. Ablation 1c + 2: Combined Asymmetric Re-entry + Downside Vol Targeting

Evaluates:
- In-Sample (2018-10-08 -> 2022-12-31)
- Out-of-Sample (2023-01-01 -> 2026-10-06)
- Full Period (2018-2026)
- Metrics: CAGR (Net), Max Drawdown, Sharpe, Calmar, Annual Turnover (%), Discrete Flips
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

CACHE_DIR = os.path.join(ROOT_DIR, "data", "replay_cache")


def load_environment():
    vn_file = os.path.join(CACHE_DIR, "VNINDEX_2018-01-01_2026-10-06.csv")
    df_vn = pd.read_csv(vn_file)
    df_vn["time"] = pd.to_datetime(df_vn["time"])
    df_vn = df_vn.sort_values("time").reset_index(drop=True)

    import glob

    stock_files = glob.glob(os.path.join(CACHE_DIR, "*_2018-01-01_2026-10-06.csv"))
    stocks_data = {}
    for f in stock_files:
        sym = os.path.basename(f).split("_")[0].upper()
        if sym != "VNINDEX":
            df_s = pd.read_csv(f)
            df_s["time"] = pd.to_datetime(df_s["time"])
            stocks_data[sym] = df_s.sort_values("time").reset_index(drop=True)

    # Build price matrix & equal weight return
    price_matrix = pd.DataFrame(index=df_vn["time"])
    for sym in sorted(list(stocks_data.keys())):
        price_matrix[sym] = stocks_data[sym].set_index("time")["close"].reindex(df_vn["time"])
    price_matrix = price_matrix.ffill().bfill()
    eq_daily_ret = price_matrix.pct_change().fillna(0.0).mean(axis=1)

    return df_vn, eq_daily_ret


def run_simulation(df_vn, eq_daily_ret, alloc_series, fee_rate=0.0025, rf_annual=0.045):
    """Simulate asset allocation overlay with fee on turnover and 4.5% risk-free rate."""
    n_days = len(df_vn)
    rf_daily = (1.0 + rf_annual) ** (1.0 / 250.0) - 1.0
    equity = [100.0]
    turnover = 0.0
    prev_alloc = 0.0

    for i in range(1, n_days):
        alloc = alloc_series.iloc[i - 1]
        turnover_i = abs(alloc - prev_alloc)
        turnover += turnover_i
        fee_cost = turnover_i * fee_rate
        prev_alloc = alloc

        ret_i = alloc * eq_daily_ret.iloc[i] + (1.0 - alloc) * rf_daily - fee_cost
        equity.append(equity[-1] * (1.0 + ret_i))

    series = pd.Series(equity, index=df_vn["time"])
    annual_turnover_pct = (turnover / (n_days / 250.0)) * 100.0
    return series, annual_turnover_pct


def calculate_metrics(series, rf_annual=0.045):
    years = len(series) / 250.0
    tot_ret = (series.iloc[-1] / series.iloc[0]) - 1.0
    cagr = ((1.0 + tot_ret) ** (1.0 / years) - 1.0) * 100.0

    cummax = series.cummax()
    dd = (series - cummax) / cummax * 100.0
    mdd = dd.min()

    d_ret = series.pct_change().dropna()
    rf_daily = (1.0 + rf_annual) ** (1.0 / 250.0) - 1.0
    excess_ret = d_ret - rf_daily
    ann_std = d_ret.std() * np.sqrt(250)
    sharpe = (excess_ret.mean() / d_ret.std()) * np.sqrt(250) if d_ret.std() > 0 else 0.0
    calmar = cagr / abs(mdd) if abs(mdd) > 0 else 0.0

    return {
        "Total Return (%)": round(tot_ret * 100.0, 2),
        "CAGR (%)": round(cagr, 2),
        "Max Drawdown (%)": round(mdd, 2),
        "Sharpe": round(sharpe, 2),
        "Calmar": round(calmar, 2),
    }


def generate_regime_allocations(df_vn):
    """Generate allocation series for each ablation variant."""
    close = df_vn["close"]
    n = len(df_vn)
    ma200 = close.rolling(200, min_periods=50).mean()

    # Daily returns and 20-day downside semi-deviation
    ret = close.pct_change().fillna(0.0)
    downside_ret = ret.apply(lambda x: x if x < 0 else 0.0)
    downside_vol20 = np.sqrt((downside_ret**2).rolling(20, min_periods=10).mean()) * np.sqrt(250) * 100.0
    ann_vol20 = ret.rolling(20, min_periods=10).std() * np.sqrt(250) * 100.0

    # 1. Baseline: Binary MA200 (+/-1.5% fixed)
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

    # 2. Ablation 1a: Min Holding Window (>= 15 trading days before allowing flip)
    alloc_1a = []
    state_1a = "SIDEWAYS"
    days_in_state = 0
    for i in range(n):
        c, m = close.iloc[i], ma200.iloc[i]
        days_in_state += 1
        if pd.isna(m) or m <= 0:
            alloc_1a.append(0.5)
            continue

        target_state = state_1a
        if c > m * 1.015:
            target_state = "UPTREND"
        elif c < m * 0.985:
            target_state = "DOWNTREND"

        # Only allow flip if days_in_state >= 15
        if target_state != state_1a and days_in_state >= 15:
            state_1a = target_state
            days_in_state = 0

        alloc_1a.append(1.0 if state_1a == "UPTREND" else (0.0 if state_1a == "DOWNTREND" else 0.5))

    # 3. Ablation 1b: Volatility-Adjusted Dynamic Hysteresis Band
    # band = max(1.5%, vol20 * 0.12) -> e.g. vol 20% -> band 2.4%
    alloc_1b = []
    state_1b = "SIDEWAYS"
    for i in range(n):
        c, m = close.iloc[i], ma200.iloc[i]
        v = ann_vol20.iloc[i] if not pd.isna(ann_vol20.iloc[i]) else 18.0
        dyn_band = max(0.015, (v / 100.0) * 0.12)

        if pd.isna(m) or m <= 0:
            alloc_1b.append(0.5)
            continue
        if c > m * (1.0 + dyn_band):
            state_1b = "UPTREND"
        elif c < m * (1.0 - dyn_band):
            state_1b = "DOWNTREND"
        alloc_1b.append(1.0 if state_1b == "UPTREND" else (0.0 if state_1b == "DOWNTREND" else 0.5))

    # 4. Ablation 1c: Asymmetric Re-entry (Fast exit 0%, Staged re-entry: 50% on cross, 100% after 10 days)
    alloc_1c = []
    state_1c = "SIDEWAYS"
    days_above_ma = 0
    for i in range(n):
        c, m = close.iloc[i], ma200.iloc[i]
        if pd.isna(m) or m <= 0:
            alloc_1c.append(0.5)
            continue

        if c < m * 0.985:
            state_1c = "DOWNTREND"
            days_above_ma = 0
            cur_alloc = 0.0
        elif c > m * 1.015:
            days_above_ma += 1
            state_1c = "UPTREND"
            if days_above_ma >= 10:
                cur_alloc = 1.0
            else:
                cur_alloc = 0.5  # Staged entry 50%
        else:
            cur_alloc = 0.5 if state_1c == "SIDEWAYS" else (1.0 if state_1c == "UPTREND" else 0.0)

        alloc_1c.append(cur_alloc)

    # 5. Ablation 2: Pure Downside Volatility Target
    # Baseline alloc modulated by downside vol scalar: target downside vol = 10%
    alloc_2 = []
    for i in range(n):
        base_a = alloc_base[i]
        d_vol = downside_vol20.iloc[i] if not pd.isna(downside_vol20.iloc[i]) else 10.0
        # If downside vol > 10%, scale down
        scalar = min(1.0, 11.0 / max(d_vol, 7.0))
        alloc_2.append(round(base_a * scalar, 4))

    # 6. Ablation Combined (1c + 2): Asymmetric Re-entry + Downside Vol Target
    alloc_comb = []
    for i in range(n):
        a_1c = alloc_1c[i]
        d_vol = downside_vol20.iloc[i] if not pd.isna(downside_vol20.iloc[i]) else 10.0
        scalar = min(1.0, 11.0 / max(d_vol, 7.0))
        alloc_comb.append(round(a_1c * scalar, 4))

    variants = {
        "Baseline (Binary MA200)": pd.Series(alloc_base, index=df_vn["time"]),
        "Ablation 1a (Min Hold >= 15d)": pd.Series(alloc_1a, index=df_vn["time"]),
        "Ablation 1b (Dynamic Vol Band)": pd.Series(alloc_1b, index=df_vn["time"]),
        "Ablation 1c (Asymmetric Re-entry)": pd.Series(alloc_1c, index=df_vn["time"]),
        "Ablation 2 (Downside Vol Target)": pd.Series(alloc_2, index=df_vn["time"]),
        "Ablation 1c+2 (Asymmetric + DownVol)": pd.Series(alloc_comb, index=df_vn["time"]),
    }
    return variants


def run_ablation_study():
    df_vn, eq_daily_ret = load_environment()
    variants = generate_regime_allocations(df_vn)

    results = {}
    turnovers = {}
    flips_count = {}

    for name, alloc in variants.items():
        s, to = run_simulation(df_vn, eq_daily_ret, alloc)
        results[name] = s
        turnovers[name] = to
        # Count discrete direction changes
        diffs = alloc.diff().abs()
        flips_count[name] = int((diffs > 0.05).sum())

    # Build comparison tables for In-Sample (2018-2022), Out-of-Sample (2023-2026), and Full
    windows = {
        "In-Sample (2018-10-08 -> 2022-12-31)": ("2018-10-08", "2022-12-31"),
        "Out-of-Sample (2023-01-01 -> 2026-10-06)": ("2023-01-01", "2026-10-06"),
        "Full Period (2018-2026)": ("2018-10-08", "2026-10-06"),
    }

    print("=" * 90)
    print("KẾT QUẢ ABLATION STUDY ĐỊNH LƯỢNG (IN-SAMPLE VS OUT-OF-SAMPLE)")
    print("=" * 90)

    for w_name, (start, end) in windows.items():
        print(f"\n--- {w_name} ---")
        rows = []
        for name in variants.keys():
            s_window = results[name].loc[start:end]
            m = calculate_metrics(s_window)
            m["Model"] = name
            m["Annual Turnover (%)"] = round(turnovers[name], 1)
            # count flips in window
            alloc_w = variants[name].loc[start:end]
            m["Discrete Flips"] = int((alloc_w.diff().abs() > 0.05).sum())
            rows.append(m)
        df_w = pd.DataFrame(rows).set_index("Model")
        cols = ["CAGR (%)", "Max Drawdown (%)", "Sharpe", "Calmar", "Annual Turnover (%)", "Discrete Flips"]
        print(df_w[cols].to_string())


if __name__ == "__main__":
    run_ablation_study()
