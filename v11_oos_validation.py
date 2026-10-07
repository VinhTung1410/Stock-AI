import os
import glob
import pandas as pd
import numpy as np

CACHE_DIR = "data/replay_cache"
DISCOVERY_END_DATE = "2023-12-31"

def calculate_market_observables(df_index: pd.DataFrame) -> pd.DataFrame:
    df = df_index.sort_values("time").copy()
    
    # Drawdown from 20D High (using ONLY past data up to day D)
    df['high_20d'] = df['high'].rolling(20).max()
    df['dd_20d'] = (df['close'] - df['high_20d']) / df['high_20d']
    
    # ATR Expansion (using ONLY past data up to day D)
    df['tr0'] = abs(df['high'] - df['low'])
    df['tr1'] = abs(df['high'] - df['close'].shift(1))
    df['tr2'] = abs(df['low'] - df['close'].shift(1))
    df['tr'] = df[['tr0', 'tr1', 'tr2']].max(axis=1)
    df['atr_14'] = df['tr'].rolling(14).mean()
    df['atr_60'] = df['tr'].rolling(60).mean()
    df['atr_expansion'] = df['atr_14'] / df['atr_60']
    
    return df.dropna(subset=['atr_expansion', 'dd_20d'])

def process_stock_tech(sdf: pd.DataFrame, df_market: pd.DataFrame) -> pd.DataFrame:
    sdf = sdf.sort_values("time").copy()
    
    # Stock Drawdown
    sdf['stock_high_20d'] = sdf['high'].rolling(20).max()
    sdf['stock_dd_20d'] = (sdf['close'] - sdf['stock_high_20d']) / sdf['stock_high_20d']
    
    # Forward Returns (Assuming entry at Close of Day D)
    # T+k returns: close(D+k) / close(D) - 1
    sdf['fwd_ret_1d'] = sdf['close'].shift(-1) / sdf['close'] - 1
    sdf['fwd_ret_5d'] = sdf['close'].shift(-5) / sdf['close'] - 1
    sdf['fwd_ret_20d'] = sdf['close'].shift(-20) / sdf['close'] - 1
    sdf['fwd_ret_60d'] = sdf['close'].shift(-60) / sdf['close'] - 1
    
    # Forward MAE and MFE (Lookahead for 20 days starting D+1)
    # rolling(20) at index D+20 covers D+1 to D+20. shift(-20) moves it to D.
    sdf['fwd_min_20d'] = sdf['low'].rolling(20).min().shift(-20)
    sdf['fwd_max_20d'] = sdf['high'].rolling(20).max().shift(-20)
    
    sdf['mae_20d'] = (sdf['fwd_min_20d'] - sdf['close']) / sdf['close']
    sdf['mfe_20d'] = (sdf['fwd_max_20d'] - sdf['close']) / sdf['close']
    
    # Merge Market state back into stock frame to get Date Eligibility
    market_cols = df_market[['time', 'dd_20d', 'atr_expansion']].rename(columns={
        'dd_20d': 'market_dd_20d', 
        'atr_expansion': 'market_atr_exp'
    })
    sdf = pd.merge(sdf, market_cols, on='time', how='inner')
    
    return sdf.dropna(subset=['stock_dd_20d', 'fwd_ret_20d', 'fwd_ret_60d', 'market_atr_exp'])

def summarize_group(name: str, df: pd.DataFrame) -> dict:
    if df.empty:
        return {"Group": name, "N": 0}
        
    return {
        "Group": name,
        "N": len(df),
        "P(T+1>0)": (df['fwd_ret_1d'] > 0).mean(),
        "P(T+5>0)": (df['fwd_ret_5d'] > 0).mean(),
        "P(T+20>0)": (df['fwd_ret_20d'] > 0).mean(),
        "P(T+60>0)": (df['fwd_ret_60d'] > 0).mean(),
        "T20_Mean": df['fwd_ret_20d'].mean(),
        "T20_Med": df['fwd_ret_20d'].median(),
        "T20_P25": df['fwd_ret_20d'].quantile(0.25),
        "T20_P75": df['fwd_ret_20d'].quantile(0.75),
        "T20_Med_MAE": df['mae_20d'].median(),
        "T20_Med_MFE": df['mfe_20d'].median(),
    }

def main():
    print("=== V11 OUT-OF-SAMPLE VALIDATION ===")
    index_files = glob.glob(f"{CACHE_DIR}/VNINDEX*2026-10-*.csv")
    if not index_files:
        print("VNINDEX 2026 file not found")
        return
        
    df_market = calculate_market_observables(pd.read_csv(index_files[-1], parse_dates=["time"]))
    
    # We load ALL stocks matching 2026 pattern
    stock_files = glob.glob(f"{CACHE_DIR}/*2026-10-*.csv")
    all_stocks_data = []
    
    for f in stock_files:
        if "VNINDEX" in f: continue
        try:
            sdf = pd.read_csv(f, parse_dates=["time"])
            sdf = process_stock_tech(sdf, df_market)
            all_stocks_data.append(sdf)
        except Exception:
            pass
            
    df_all = pd.concat(all_stocks_data, ignore_index=True)
    
    # -------------------------------------------------------------
    # STRICT OUT-OF-SAMPLE FILTER (2024-2026)
    # -------------------------------------------------------------
    df_oos = df_all[df_all['time'] > DISCOVERY_END_DATE].copy()
    print(f"Holdout Period: {df_oos['time'].min().date()} to {df_oos['time'].max().date()}")
    print(f"Total Out-Of-Sample Observations (Stock-Days): {len(df_oos)}")
    
    # Define Gate 0:
    cond_extreme = (df_oos['market_dd_20d'] < -0.15) & (df_oos['market_atr_exp'] >= 1.5)
    cond_silent = (df_oos['market_dd_20d'] < -0.08) & (df_oos['market_atr_exp'] < 1.0)
    cond_gate0 = cond_extreme | cond_silent
    
    # Group A: All stocks
    df_A = df_oos
    
    # Group B: Gate 0 Eligible (Market state is Eligible)
    df_B = df_oos[cond_gate0]
    
    # Group C: Gate 0 Eligible + Stock DD < -25%
    df_C = df_oos[cond_gate0 & (df_oos['stock_dd_20d'] < -0.25)]
    
    # Group D: Gate 0 Eligible + Stock DD >= -25%
    df_D = df_oos[cond_gate0 & (df_oos['stock_dd_20d'] >= -0.25)]
    
    results = [
        summarize_group("A. All Stocks (Baseline)", df_A),
        summarize_group("B. Gate 0 Eligible", df_B),
        summarize_group("C. Gate 0 + Stock DD < -25%", df_C),
        summarize_group("D. Gate 0 + Stock DD >= -25%", df_D)
    ]
    
    res_df = pd.DataFrame(results)
    
    # Formatting for better readability
    pct_cols = ['P(T+1>0)', 'P(T+5>0)', 'P(T+20>0)', 'P(T+60>0)', 'T20_Mean', 'T20_Med', 'T20_P25', 'T20_P75', 'T20_Med_MAE', 'T20_Med_MFE']
    for col in pct_cols:
        if col in res_df.columns:
            res_df[col] = res_df[col].apply(lambda x: f"{x:.2%}" if pd.notnull(x) else "N/A")
            
    print("\n--- OOS VALIDATION RESULTS ---")
    print(res_df.to_markdown(index=False))

if __name__ == "__main__":
    main()
