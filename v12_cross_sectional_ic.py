import pandas as pd
import numpy as np
from scipy.stats import spearmanr
import argparse

def daily_ic(g, feat, ret, min_n=30):
    subset = g[[feat, ret]].dropna()
    if len(subset) >= min_n:
        # Check if feature has enough variance to rank
        if subset[feat].nunique() > 1:
            return spearmanr(subset[feat], subset[ret])[0]
    return np.nan

def newey_west_mean_tstat(y, lag=20):
    T = len(y)
    if T <= lag:
        return np.nan
    mean_y = np.mean(y)
    y_centered = y - mean_y
    
    # Gamma 0 (variance)
    gamma_0 = np.sum(y_centered**2) / T
    
    # Gamma j (autocovariances)
    sum_cov = 0
    for j in range(1, lag + 1):
        gamma_j = np.sum(y_centered[j:] * y_centered[:-j]) / T
        weight = 1 - (j / (lag + 1))
        sum_cov += weight * gamma_j
        
    omega = gamma_0 + 2 * sum_cov
    
    # Guard against negative omega due to finite sample / approximation
    if omega <= 0:
        se = np.std(y) / np.sqrt(T) # fallback to standard error
    else:
        se = np.sqrt(omega / T)
        
    if se == 0:
        return mean_y, np.nan
    return mean_y, mean_y / se

def eval_ic(df, feature, ret_col, min_n=30, label="", placebo=False):
    if placebo:
        # Permute the feature randomly within the day
        df = df.copy()
        df[feature] = df.groupby('time')[feature].transform(np.random.permutation)
        
    ic = df.groupby('time').apply(daily_ic, feature, ret_col, min_n=min_n, include_groups=False).dropna()
    if len(ic) == 0:
        return None
        
    y = ic.values
    # Pure NumPy Newey-West to avoid statsmodels DLL block
    mean_ic, t_nw = newey_west_mean_tstat(y, lag=20)
    
    # Calculate years with same sign
    years_sign = ic.groupby(ic.index.year).mean()
    expected_sign = np.sign(mean_ic)
    years_same_sign = (np.sign(years_sign) == expected_sign).sum()
    total_years = len(years_sign)
    
    # Non-overlapping robustness (every 20 days)
    ic_nonoverlap = ic.iloc[::20]
    mean_nonoverlap = ic_nonoverlap.mean()
    t_nonoverlap = (mean_nonoverlap / (ic_nonoverlap.std() / np.sqrt(len(ic_nonoverlap)))) if len(ic_nonoverlap) > 1 else np.nan
    
    autocorr = ic.autocorr(1)
    
    return {
        'Label': label,
        'Mean_IC': mean_ic,
        't_NW': t_nw,
        'Autocorr(1)': autocorr,
        'Years_Same_Sign': f"{years_same_sign}/{total_years}",
        'NonOverlap_Mean': mean_nonoverlap,
        'NonOverlap_t': t_nonoverlap,
        'N_Days': len(ic)
    }

def run_placebo_test(df, feature, ret_col, n_runs=200):
    print(f"\n=== RUNNING PLACEBO TEST ({n_runs} Iterations) ===")
    t_stats = []
    for i in range(n_runs):
        res = eval_ic(df, feature, ret_col, min_n=30, label="", placebo=True)
        if res:
            t_stats.append(res['t_NW'])
    
    t_stats = np.array(t_stats)
    t_stats = t_stats[~np.isnan(t_stats)]
    if len(t_stats) == 0:
        print("Failed to run placebo.")
        return
        
    fp_rate = (np.abs(t_stats) > 2.0).mean()
    print(f"Mean t_NW: {t_stats.mean():.4f} (Expected ~ 0)")
    print(f"Std t_NW: {t_stats.std():.4f} (Expected ~ 1)")
    print(f"False Positive Rate (|t| > 2): {fp_rate:.2%} (Expected ~ 5%)")
    if fp_rate > 0.10:
        print("WARNING: Placebo test failed! False Positive rate is too high. Check temporal overlap.")
    else:
        print("Placebo test PASSED.")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--placebo", action="store_true", help="Run 200 placebo permutations")
    args = parser.parse_args()

    print("=== V12 CROSS-SECTIONAL IC EVALUATION ===")
    df = pd.read_csv("data/v12_panel_data.csv", parse_dates=["time"])
    
    # Discovery Period (2018 - 2023)
    # Purge: Drop last 20 trading days of 2023 so D+20 return doesn't leak into 2024 holdout
    # Approximate by dropping December 2023 entirely
    df_train = df[(df['time'] >= '2018-01-01') & (df['time'] < '2023-12-01')].copy()
    
    print(f"Discovery sample (Purged): {df_train['time'].min().date()} to {df_train['time'].max().date()}")
    print(f"Total rows: {len(df_train)}")
    
    if args.placebo:
        run_placebo_test(df_train, 'depth_DD60', 'ret_D_to_D20', n_runs=200)
        return

    # Print criteria
    print("\n--- PRE-REGISTERED CRITERIA ---")
    print("1. Mean IC differs from 0 with Newey-West |t| >= 2.0 (lag=20).")
    print("2. Stability: Same sign in >= 5/6 years.")
    print("3. Power warning: With N=56, SE(mean_ic) ~ 0.015. Requires |IC| >= 0.03 for t=2.")
    print("4. Decomposition: Effect must not be entirely driven by D -> D+1.")
    
    features = [
        ('Primary: depth_DD60', 'rank_depth_DD60'),
        ('Secondary: RSI14', 'rank_RSI14'),
        ('Secondary: Rev5', 'rank_Rev5')
    ]
    
    horizons = [
        ('D -> D+20', 'ret_D_to_D20'),
        ('D -> D+1 (Microstructure)', 'ret_D_to_D1'),
        ('D+1 -> D+20 (Tradable)', 'ret_D1_to_D20')
    ]
    
    for f_label, feat in features:
        print(f"\n--- {f_label} ---")
        results = []
        for h_label, ret_col in horizons:
            res = eval_ic(df_train, feat, ret_col, label=h_label)
            if res:
                results.append(res)
        
        if results:
            res_df = pd.DataFrame(results)
            print(res_df[['Label', 'Mean_IC', 't_NW', 'Autocorr(1)', 'Years_Same_Sign', 'NonOverlap_t', 'N_Days']].to_string(index=False))

    # Calculate Quintiles for DD60 (D -> D+20)
    print("\n--- DD60 QUINTILE RETURNS (D -> D+20) ---")
    df_train = df_train.dropna(subset=['depth_DD60', 'ret_D_to_D20'])
    df_train['quintile'] = df_train.groupby('time')['depth_DD60'].transform(
        lambda x: pd.qcut(x, 5, labels=False, duplicates='drop') if len(x) >= 30 else np.nan
    )
    
    q_ret = df_train.groupby(['time', 'quintile'])['relative_ret_D_to_D20'].mean().reset_index()
    q_mean = q_ret.groupby('quintile')['relative_ret_D_to_D20'].mean() * 100 # In percentage
    print("Quintiles (0 = shallowest drawdown, 4 = deepest drawdown / highest depth):")
    for q in sorted(q_mean.index):
        print(f"  Q{int(q)}: {q_mean[q]:.2f}% relative return")
    
    if 0 in q_mean and 4 in q_mean:
        print(f"Spread (Q4 - Q0): {q_mean[4] - q_mean[0]:.2f}%")

if __name__ == "__main__":
    main()
