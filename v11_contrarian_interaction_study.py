import os
import glob
import pandas as pd
import numpy as np

CACHE_DIR = "data/replay_cache"
DISCOVERY_END_DATE = "2023-12-31"

def calculate_market_observables(df_index: pd.DataFrame) -> pd.DataFrame:
    df_index = df_index.sort_values("time").copy()
    
    # Drawdown from 20D High
    df_index['high_20d'] = df_index['high'].rolling(20).max()
    df_index['dd_20d'] = (df_index['close'] - df_index['high_20d']) / df_index['high_20d']
    
    # ATR Expansion
    df_index['tr0'] = abs(df_index['high'] - df_index['low'])
    df_index['tr1'] = abs(df_index['high'] - df_index['close'].shift())
    df_index['tr2'] = abs(df_index['low'] - df_index['close'].shift())
    df_index['tr'] = df_index[['tr0', 'tr1', 'tr2']].max(axis=1)
    df_index['atr_14'] = df_index['tr'].rolling(14).mean()
    df_index['atr_60'] = df_index['tr'].rolling(60).mean()
    df_index['atr_expansion'] = df_index['atr_14'] / df_index['atr_60']
    
    return df_index.dropna(subset=['atr_expansion', 'dd_20d'])

def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).fillna(0)
    loss = (-delta.where(delta < 0, 0)).fillna(0)
    avg_gain = gain.rolling(window=period, min_periods=period).mean()
    avg_loss = loss.rolling(window=period, min_periods=period).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def main():
    print("=== V11 STOCK SELECTION INTERACTION ===")
    index_files = glob.glob(f"{CACHE_DIR}/VNINDEX*.csv")
    if not index_files:
        print("VNINDEX cache not found!")
        return
        
    df_index = pd.read_csv(index_files[0], parse_dates=["time"])
    df_obs = calculate_market_observables(df_index)
    
    # Restrict to Discovery Period
    df_obs = df_obs[df_obs['time'] <= DISCOVERY_END_DATE].copy()
    
    # Define Gate 0 Eligible States
    cond_extreme_crash = (df_obs['dd_20d'] < -0.15) & (df_obs['atr_expansion'] >= 1.5)
    cond_silent_bleed = (df_obs['dd_20d'] < -0.08) & (df_obs['atr_expansion'] < 1.0)
    
    eligible_dates = df_obs[cond_extreme_crash | cond_silent_bleed]['time'].tolist()
    print(f"Found {len(eligible_dates)} Eligible Market Days (Extreme Crash + Silent Bleed) in Discovery phase.")
    
    stock_files = glob.glob(f"{CACHE_DIR}/*.csv")
    all_stock_obs = []
    
    print("Calculating Stock Technicals...")
    for f in stock_files:
        if "VNINDEX" in f:
            continue
        try:
            sdf = pd.read_csv(f, parse_dates=["time"])
            sdf = sdf.sort_values("time")
            
            # Forward returns for stock
            sdf['fwd_ret_20d'] = sdf['close'].shift(-20) / sdf['close'] - 1
            sdf['fwd_ret_60d'] = sdf['close'].shift(-60) / sdf['close'] - 1
            
            # Tech indicators
            sdf['high_20d'] = sdf['high'].rolling(20).max()
            sdf['stock_dd_20d'] = (sdf['close'] - sdf['high_20d']) / sdf['high_20d']
            sdf['rsi_14'] = calculate_rsi(sdf['close'], 14)
            sdf['ma20'] = sdf['close'].rolling(20).mean()
            sdf['dist_ma20'] = (sdf['close'] - sdf['ma20']) / sdf['ma20']
            
            # Filter only eligible dates
            sdf_eligible = sdf[sdf['time'].isin(eligible_dates)].copy()
            if not sdf_eligible.empty:
                all_stock_obs.append(sdf_eligible[['time', 'close', 'fwd_ret_20d', 'fwd_ret_60d', 'stock_dd_20d', 'rsi_14', 'dist_ma20']])
        except Exception as e:
            pass
            
    if not all_stock_obs:
        print("No stock data found for eligible dates.")
        return
        
    df_stocks = pd.concat(all_stock_obs, ignore_index=True).dropna()
    print(f"Total Stock-Day Observations in Eligible States: {len(df_stocks)}")
    
    # Bucket by Stock RSI
    print("\n--- Interaction: Market Eligible State + Stock RSI ---")
    rsi_bins = [0, 30, 45, 60, 100]
    rsi_labels = ["1. RSI < 30 (Oversold)", "2. RSI 30-45", "3. RSI 45-60", "4. RSI > 60"]
    df_stocks['rsi_bucket'] = pd.cut(df_stocks['rsi_14'], bins=rsi_bins, labels=rsi_labels)
    
    results = []
    for bucket in rsi_labels:
        subset = df_stocks[df_stocks['rsi_bucket'] == bucket]
        n_samples = len(subset)
        if n_samples == 0:
            continue
        results.append({
            "Stock RSI": bucket,
            "Observations": n_samples,
            "P(T+20>0)": (subset['fwd_ret_20d'] > 0).mean(),
            "Med T+20": subset['fwd_ret_20d'].median(),
            "Mean T+20": subset['fwd_ret_20d'].mean(),
            "Med T+60": subset['fwd_ret_60d'].median()
        })
        
    res_df = pd.DataFrame(results)
    print(res_df.to_markdown(index=False, floatfmt=".2%"))
    
    # Bucket by Stock Drawdown
    print("\n--- Interaction: Market Eligible State + Stock Drawdown ---")
    dd_bins = [-1.0, -0.25, -0.15, -0.05, 1.0]
    dd_labels = ["1. Crash < -25%", "2. DD -25% to -15%", "3. DD -15% to -5%", "4. Mild/Positive > -5%"]
    df_stocks['dd_bucket'] = pd.cut(df_stocks['stock_dd_20d'], bins=dd_bins, labels=dd_labels)
    
    results_dd = []
    for bucket in dd_labels:
        subset = df_stocks[df_stocks['dd_bucket'] == bucket]
        n_samples = len(subset)
        if n_samples == 0:
            continue
        results_dd.append({
            "Stock Drawdown": bucket,
            "Observations": n_samples,
            "P(T+20>0)": (subset['fwd_ret_20d'] > 0).mean(),
            "Med T+20": subset['fwd_ret_20d'].median(),
            "Mean T+20": subset['fwd_ret_20d'].mean(),
            "Med T+60": subset['fwd_ret_60d'].median()
        })
        
    res_dd_df = pd.DataFrame(results_dd)
    print(res_dd_df.to_markdown(index=False, floatfmt=".2%"))

if __name__ == "__main__":
    main()
