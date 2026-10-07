import os
import glob
import pandas as pd
import numpy as np

# Configuration
CACHE_DIR = "data/replay_cache"
DISCOVERY_END_DATE = "2023-12-31"  # discovery up to 2023, hold 2024-2026 for out-of-sample

def calculate_market_observables(df_index: pd.DataFrame, stock_files: list) -> pd.DataFrame:
    print("Calculating Index Volatility, Drawdown & Momentum...")
    
    # Sort and ensure datetime
    df_index = df_index.sort_values("time").copy()
    
    # Momentum
    df_index['return_1d'] = df_index['close'].pct_change()
    df_index['return_5d'] = df_index['close'].pct_change(5)
    df_index['return_20d'] = df_index['close'].pct_change(20)
    
    # Drawdown from 20D / 50D High
    df_index['high_20d'] = df_index['high'].rolling(20).max()
    df_index['high_50d'] = df_index['high'].rolling(50).max()
    df_index['dd_20d'] = (df_index['close'] - df_index['high_20d']) / df_index['high_20d']
    df_index['dd_50d'] = (df_index['close'] - df_index['high_50d']) / df_index['high_50d']
    
    # ATR & Volatility Expansion
    df_index['tr0'] = abs(df_index['high'] - df_index['low'])
    df_index['tr1'] = abs(df_index['high'] - df_index['close'].shift())
    df_index['tr2'] = abs(df_index['low'] - df_index['close'].shift())
    df_index['tr'] = df_index[['tr0', 'tr1', 'tr2']].max(axis=1)
    df_index['atr_14'] = df_index['tr'].rolling(14).mean()
    df_index['atr_60'] = df_index['tr'].rolling(60).mean() # Baseline Volatility
    df_index['atr_expansion'] = df_index['atr_14'] / df_index['atr_60']
    
    # Volume / Turnover Shock
    df_index['vol_20d_ma'] = df_index['volume'].rolling(20).mean()
    df_index['volume_shock'] = df_index['volume'] / df_index['vol_20d_ma']
    
    # Forward Returns (Market level for pure state discovery)
    df_index['fwd_ret_1d'] = df_index['close'].shift(-1) / df_index['close'] - 1
    df_index['fwd_ret_5d'] = df_index['close'].shift(-5) / df_index['close'] - 1
    df_index['fwd_ret_20d'] = df_index['close'].shift(-20) / df_index['close'] - 1
    df_index['fwd_ret_60d'] = df_index['close'].shift(-60) / df_index['close'] - 1
    
    # MAE / MFE for 20D window (Simplified approximations based on close prices)
    df_index['fwd_min_20d'] = df_index['low'].rolling(20).min().shift(-20)
    df_index['fwd_max_20d'] = df_index['high'].rolling(20).max().shift(-20)
    df_index['mae_20d'] = (df_index['fwd_min_20d'] - df_index['close']) / df_index['close']
    df_index['mfe_20d'] = (df_index['fwd_max_20d'] - df_index['close']) / df_index['close']
    
    print("Calculating Market Breadth across all cached stocks...")
    all_breadth_data = []
    
    total_files = len(stock_files)
    for idx, f in enumerate(stock_files):
        if "VNINDEX" in f:
            continue
        try:
            sdf = pd.read_csv(f, parse_dates=["time"])
            sdf = sdf.sort_values("time")
            sdf['ma20'] = sdf['close'].rolling(20).mean()
            sdf['ma50'] = sdf['close'].rolling(50).mean()
            
            sdf['above_ma20'] = (sdf['close'] > sdf['ma20']).astype(int)
            sdf['above_ma50'] = (sdf['close'] > sdf['ma50']).astype(int)
            sdf['is_traded'] = 1  # basic proxy for active listing
            
            breadth_slice = sdf[['time', 'above_ma20', 'above_ma50', 'is_traded']].copy()
            all_breadth_data.append(breadth_slice)
        except Exception:
            pass
            
    breadth_df = pd.concat(all_breadth_data, ignore_index=True)
    breadth_agg = breadth_df.groupby("time").sum().reset_index()
    breadth_agg['pct_above_ma20'] = breadth_agg['above_ma20'] / breadth_agg['is_traded']
    breadth_agg['pct_above_ma50'] = breadth_agg['above_ma50'] / breadth_agg['is_traded']
    
    # Merge back to index
    df_combined = pd.merge(df_index, breadth_agg[['time', 'pct_above_ma20', 'pct_above_ma50']], on="time", how="left")
    
    return df_combined.dropna(subset=['pct_above_ma20', 'atr_expansion', 'dd_20d', 'volume_shock'])


def evaluate_state_predictive_power(df: pd.DataFrame, feature: str, bins: list, labels: list):
    """
    Groups the dataframe by quantiles/buckets of a feature and calculates 
    forward return statistics.
    """
    df_eval = df.copy()
    # Handle specific edges safely
    df_eval['bucket'] = pd.cut(df_eval[feature], bins=bins, labels=labels, include_lowest=True)
    
    results = []
    for bucket in labels:
        subset = df_eval[df_eval['bucket'] == bucket]
        n_samples = len(subset)
        if n_samples == 0:
            continue
            
        res = {
            "Bucket": bucket,
            "N": n_samples,
            "P(T+20 > 0)": (subset['fwd_ret_20d'] > 0).mean(),
            "Med T+20": subset['fwd_ret_20d'].median(),
            "Mean T+20": subset['fwd_ret_20d'].mean(),
            "Med T+60": subset['fwd_ret_60d'].median(),
            "Med MAE_20": subset['mae_20d'].median(),
            "Med MFE_20": subset['mfe_20d'].median(),
        }
        results.append(res)
        
    return pd.DataFrame(results)

def evaluate_interaction(df: pd.DataFrame):
    results = []
    
    # Define interaction states
    conditions = {
        "1. Normal Market (Breadth > 40%, ATR < 1.2x)": (df['pct_above_ma20'] > 0.40) & (df['atr_expansion'] < 1.2),
        "2. Falling Knife (Drawdown < -5%, ATR 1.2-1.5x)": (df['dd_20d'] < -0.05) & (df['atr_expansion'] >= 1.2) & (df['atr_expansion'] < 1.5),
        "3. Panic Spike (Drawdown < -8%, ATR > 1.5x)": (df['dd_20d'] < -0.08) & (df['atr_expansion'] >= 1.5),
        "4. Extreme Crash (Drawdown < -15%, ATR > 1.5x)": (df['dd_20d'] < -0.15) & (df['atr_expansion'] >= 1.5),
        "5. Silent Bleed (Drawdown < -8%, Vol Shock < 1.0x)": (df['dd_20d'] < -0.08) & (df['atr_expansion'] < 1.0),
    }
    
    for name, cond in conditions.items():
        subset = df[cond]
        n_samples = len(subset)
        if n_samples == 0:
            continue
            
        res = {
            "Interaction State": name,
            "N": n_samples,
            "P(T+20>0)": (subset['fwd_ret_20d'] > 0).mean(),
            "Med T+5": subset['fwd_ret_5d'].median(),
            "Med T+20": subset['fwd_ret_20d'].median(),
            "Mean T+20": subset['fwd_ret_20d'].mean(),
            "Med T+60": subset['fwd_ret_60d'].median(),
            "Med MAE_20": subset['mae_20d'].median(),
            "Med MFE_20": subset['mfe_20d'].median(),
        }
        results.append(res)
    return pd.DataFrame(results)

def main():
    print("=== V11 MARKET STATE DISCOVERY ===")
    index_files = glob.glob(f"{CACHE_DIR}/VNINDEX*.csv")
    if not index_files:
        print("VNINDEX cache not found!")
        return
        
    df_index = pd.read_csv(index_files[0], parse_dates=["time"])
    stock_files = glob.glob(f"{CACHE_DIR}/*.csv")
    
    # 1. Prepare observable dataset
    df_obs = calculate_market_observables(df_index, stock_files)
    
    # 2. Split Discovery vs Holdout
    discovery_df = df_obs[df_obs['time'] <= DISCOVERY_END_DATE].copy()
    holdout_df = df_obs[df_obs['time'] > DISCOVERY_END_DATE].copy()
    
    print(f"\nDiscovery Sample Size: {len(discovery_df)} days (Up to {DISCOVERY_END_DATE})")
    
    # 3. Analyze Market Breadth (% > MA20)
    print("\n--- 1. Market Breadth: % > MA20 ---")
    breadth_bins = [0.0, 0.10, 0.20, 0.40, 0.60, 1.0]
    breadth_labels = ["< 10%", "10-20%", "20-40%", "40-60%", "> 60%"]
    b_stats = evaluate_state_predictive_power(discovery_df, 'pct_above_ma20', breadth_bins, breadth_labels)
    print(b_stats.to_markdown(index=False, floatfmt=".2%"))
    
    # 4. Analyze ATR Expansion (Volatility Shock)
    print("\n--- 2. Volatility Shock: ATR 14D / ATR 60D ---")
    atr_bins = [0.0, 0.8, 1.0, 1.2, 1.5, 5.0]
    atr_labels = ["< 0.8x (Calm)", "0.8-1.0x", "1.0-1.2x", "1.2-1.5x (Elevated)", "> 1.5x (Shock)"]
    v_stats = evaluate_state_predictive_power(discovery_df, 'atr_expansion', atr_bins, atr_labels)
    print(v_stats.to_markdown(index=False, floatfmt=".2%"))

    # 5. Analyze Drawdown (Distance from 20D High)
    print("\n--- 3. Drawdown: Distance from 20D High ---")
    dd_bins = [-1.0, -0.15, -0.08, -0.04, -0.01, 1.0]
    dd_labels = ["< -15% (Crash)", "-15% to -8%", "-8% to -4%", "-4% to -1%", "Near High"]
    d_stats = evaluate_state_predictive_power(discovery_df, 'dd_20d', dd_bins, dd_labels)
    print(d_stats.to_markdown(index=False, floatfmt=".2%"))
    
    # 6. Analyze Turnover Shock
    print("\n--- 4. Turnover Shock: Volume / 20D MA ---")
    vol_bins = [0.0, 0.5, 0.8, 1.2, 1.5, 5.0]
    vol_labels = ["< 0.5x (Dead)", "0.5-0.8x (Low)", "0.8-1.2x (Normal)", "1.2-1.5x (High)", "> 1.5x (Spike)"]
    vo_stats = evaluate_state_predictive_power(discovery_df, 'volume_shock', vol_bins, vol_labels)
    print(vo_stats.to_markdown(index=False, floatfmt=".2%"))

    # 7. Interaction Study
    print("\n--- 5. INTERACTION STUDY (DUAL OBSERVABLES) ---")
    i_stats = evaluate_interaction(discovery_df)
    print(i_stats.to_markdown(index=False, floatfmt=".2%"))

if __name__ == "__main__":
    main()
