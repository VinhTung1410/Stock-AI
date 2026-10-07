import pandas as pd
import numpy as np
import argparse

def pure_numpy_ols(X, y):
    """Solve OLS using pure NumPy to avoid statsmodels DLL block"""
    # X shape: (N, K), y shape: (N,)
    try:
        # beta = (X^T X)^-1 X^T y
        inv_XTX = np.linalg.pinv(X.T @ X)
        beta = inv_XTX @ X.T @ y
        return beta
    except np.linalg.LinAlgError:
        return np.full(X.shape[1], np.nan)

def newey_west_mean_tstat(y, lag=20):
    """Pure NumPy Newey-West HAC t-stat for mean of y"""
    y = np.asarray(y)
    y = y[~np.isnan(y)]
    T = len(y)
    if T <= lag:
        return np.nan, np.nan
    
    mean_y = np.mean(y)
    y_centered = y - mean_y
    
    gamma_0 = np.sum(y_centered**2) / T
    sum_cov = 0
    for j in range(1, lag + 1):
        gamma_j = np.sum(y_centered[j:] * y_centered[:-j]) / T
        weight = 1 - (j / (lag + 1))
        sum_cov += weight * gamma_j
        
    omega = gamma_0 + 2 * sum_cov
    if omega <= 0:
        se = np.std(y) / np.sqrt(T) if T > 0 else np.nan
    else:
        se = np.sqrt(omega / T)
        
    if se == 0:
        return mean_y, np.nan
    return mean_y, mean_y / se

def winsorize_series(s, limits=(0.01, 0.01)):
    q_low = s.quantile(limits[0])
    q_high = s.quantile(1 - limits[1])
    return s.clip(lower=q_low, upper=q_high)

def rank_standardize(s):
    # Ranks from 1 to N, then map to [-0.5, 0.5]
    ranks = s.rank()
    return (ranks - 1) / (len(ranks) - 1) - 0.5

def run_fama_macbeth(df, feature_col, ret_col, controls, min_n=30, placebo=False):
    betas = []
    days = []
    
    # Pre-calculate grouped data for iteration
    grouped = df.groupby('time')
    
    for time, group in grouped:
        if placebo:
            group = group.copy()
            group[feature_col] = np.random.permutation(group[feature_col].values)
            
        subset = group[[ret_col, feature_col] + controls].dropna()
        if len(subset) < min_n:
            continue
            
        # Y is dependent variable (return)
        Y = subset[ret_col].values
        
        # X matrix: [Constant, Feature, Control1, Control2, ...]
        N = len(Y)
        X = np.column_stack((np.ones(N), subset[feature_col].values))
        for ctrl in controls:
            X = np.column_stack((X, subset[ctrl].values))
            
        # Run OLS for this day
        day_beta = pure_numpy_ols(X, Y)
        
        # day_beta[1] is the coefficient for the feature
        betas.append(day_beta)
        days.append(time)
        
    if len(betas) == 0:
        return None
        
    beta_df = pd.DataFrame(betas, index=days, columns=['Constant', feature_col] + controls)
    return beta_df

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--placebo', action='store_true')
    parser.add_argument('--diagnostics', action='store_true')
    parser.add_argument('--oos', action='store_true')
    args = parser.parse_args()

    # Load data
    df = pd.read_csv('data/v12_panel_data.csv', parse_dates=['time'])
    
    if args.diagnostics:
        print("=== PANEL DIAGNOSTICS ===")
        print(f"Min date: {df['time'].min().date()}")
        print(f"Max date: {df['time'].max().date()}")
        print(f"Unique days: {df['time'].nunique()}")
        print("Days per year:")
        print(df['time'].dt.year.value_counts().sort_index().to_string())
        print(f"Duplicates (symbol, time): {df.duplicated(subset=['symbol', 'time']).sum()}")
        exit(0)

    # Calculate Beta (60d vs VNINDEX proxy)
    # We don't have VNINDEX in the panel since it was filtered to 56 stocks.
    # We will use the EQUAL-WEIGHTED return of the 56 stocks as the market proxy for Beta.
    df['ret_1d'] = df.groupby('symbol')['close'].pct_change()
    ew_market = df.groupby('time')['ret_1d'].mean()
    df = df.merge(ew_market.rename('mkt_ret'), left_on='time', right_index=True, how='left')
    
    # Calculate 60d Beta using pure numpy rolling covariance
    print("Calculating Rolling Beta...")
    betas = pd.Series(index=df.index, dtype=float)
    for sym, g in df.groupby('symbol'):
        cov = g['ret_1d'].rolling(60).cov(g['mkt_ret'])
        var = g['mkt_ret'].rolling(60).var()
        betas.loc[g.index] = cov / var
    df['beta_60d'] = betas
    
    # Calculate ADV 20d
    df['turnover'] = df['close'] * df['volume']
    df['adv_20d'] = df.groupby('symbol')['turnover'].rolling(20).mean().reset_index(0, drop=True)
    
    # Rough Industry mapping (3 groups: Bank, Real Estate/Securities, Others)
    bank_symbols = ['VCB', 'BID', 'CTG', 'MBB', 'TCB', 'VPB', 'ACB', 'HDB', 'STB', 'VIB', 'SHB', 'SSB', 'TPB']
    real_estate_sec_symbols = ['VHM', 'VIC', 'VRE', 'NVL', 'PDR', 'KDH', 'NLG', 'DXG', 'DIG', 'SSI', 'VND', 'VCI', 'HCM']
    
    def map_industry(sym):
        if sym in bank_symbols: return 'Bank'
        elif sym in real_estate_sec_symbols: return 'Real_Estate_Sec'
        else: return 'Other'
        
    df['industry'] = df['symbol'].apply(map_industry)
    # Create Dummy variables
    df['ind_Bank'] = (df['industry'] == 'Bank').astype(float)
    df['ind_Real_Estate'] = (df['industry'] == 'Real_Estate_Sec').astype(float)
    # 'Other' is the base case, so we only need 2 dummies.

    if args.oos:
        df_train = df[df['time'] >= '2024-01-01'].copy()
        print("\n=== V13 FAMA-MACBETH SEMI-HOLDOUT (OOS) 2024-2026 ===")
    else:
        df_train = df[(df['time'] >= '2018-01-01') & (df['time'] < '2023-12-01')].copy()
        print("\n=== V13 FAMA-MACBETH RESIDUAL MOMENTUM EVALUATION ===")
        
    # Require minimum data
    df_train = df_train.dropna(subset=['beta_60d', 'adv_20d', 'RSI14', 'close']).copy()

    # Define target returns
    df_train['open_d1'] = df_train.groupby('symbol')['open'].shift(-1)
    df_train['close_d1'] = df_train.groupby('symbol')['close'].shift(-1)
    df_train['close_d20'] = df_train.groupby('symbol')['close'].shift(-20)
    
    df_train['R_overnight'] = df_train['open_d1'] / df_train['close'] - 1
    df_train['R_first_session'] = df_train['close_d1'] / df_train['open_d1'] - 1
    df_train['R_post_D1'] = df_train['close_d20'] / df_train['close_d1'] - 1
    df_train['R_info'] = df_train['close_d20'] / df_train['close'] - 1
    df_train['R_tradable'] = df_train['close_d20'] / df_train['open_d1'] - 1
    
    targets = ['R_overnight', 'R_first_session', 'R_post_D1', 'R_info', 'R_tradable']
    
    # Winsorize target returns by day (1% / 99%) and rank standardize features
    print("Standardizing features and winsorizing targets...")
    def prep_day(g):
        for tgt in targets:
            g[tgt] = winsorize_series(g[tgt])
        g['rank_RSI14'] = rank_standardize(g['RSI14'])
        g['rank_beta'] = rank_standardize(g['beta_60d'])
        g['rank_adv'] = rank_standardize(g['adv_20d'])
        return g
        
    df_train = df_train.groupby('time').apply(prep_day, include_groups=False).reset_index(level='time')

    controls = ['rank_beta', 'rank_adv', 'ind_Bank', 'ind_Real_Estate']
    feature = 'rank_RSI14'
    
    if args.placebo:
        print("=== RUNNING V13 PLACEBO PIPELINE (200 Iterations) ===")
        t_stats = []
        for i in range(200):
            res_df = run_fama_macbeth(df_train, feature, 'R_tradable', controls, min_n=30, placebo=True)
            lam_RSI = res_df[feature].values
            _, t_nw = newey_west_mean_tstat(lam_RSI, lag=20)
            t_stats.append(t_nw)
            if (i+1) % 20 == 0:
                print(f"Iter {i+1}/200...")
        
        t_stats = np.array(t_stats)
        fpr = np.mean(np.abs(t_stats) > 2.0) * 100
        print(f"\nPlacebo Mean t_NW: {np.nanmean(t_stats):.4f}")
        print(f"Placebo Std t_NW: {np.nanstd(t_stats):.4f}")
        print(f"False Positive Rate (|t|>2): {fpr:.2f}%")
        exit(0)

    print(f"Sample: {df_train['time'].min().date()} to {df_train['time'].max().date()}")
    
    results = []
    for tgt in targets:
        res_df = run_fama_macbeth(df_train, feature, tgt, controls, min_n=30)
        lam_series = res_df[feature].values
        mean_lam, t_nw = newey_west_mean_tstat(lam_series, lag=20)
        
        # Calculate years same sign
        years = res_df.index.year
        yearly_mean = res_df.groupby(years)[feature].mean()
        sign = 1 if mean_lam > 0 else -1
        years_same_sign = sum(np.sign(yearly_mean) == sign)
        
        results.append({
            'Target': tgt,
            'lambda_RSI': mean_lam,
            't_NW': t_nw,
            'Years_Same_Sign': f"{years_same_sign}/{len(yearly_mean)}"
        })
        
    res_df = pd.DataFrame(results)
    pd.set_option('display.float_format', lambda x: '%.6f' % x)
    print("\n--- LAMBDA RSI (Controlling for Beta, ADV, Industry) ---")
    print(res_df.to_string(index=False))
    
    # Calculate raw lambdas without controls to see the difference
    print("\n--- DIAGNOSTICS: Lambda RSI (No Controls) ---")
    res_raw = run_fama_macbeth(df_train, feature, 'R_tradable', [], min_n=30)
    lam_raw = res_raw[feature].values
    mean_raw, t_raw = newey_west_mean_tstat(lam_raw, lag=20)
    print(f"Target: R_tradable")
    print(f"Raw lambda_RSI: {mean_raw:.6f} (t_NW: {t_raw:.2f})")
    print(f"Residual lambda_RSI: {results[-1]['lambda_RSI']:.6f} (t_NW: {results[-1]['t_NW']:.2f})")
    reduction = (1 - results[-1]['lambda_RSI'] / mean_raw) * 100 if mean_raw != 0 else 0
    print(f"Effect reduction after controls: {reduction:.1f}%")
