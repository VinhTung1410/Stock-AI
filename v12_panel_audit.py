import os
import glob
import pandas as pd
import numpy as np

CACHE_DIR = "data/replay_cache"

def main():
    print("=== V12 PANEL DATA PIPELINE AUDIT (V2) ===\n")
    
    stock_files = glob.glob(f"{CACHE_DIR}/*2026-10-07.csv") + glob.glob(f"{CACHE_DIR}/*2026-10-06.csv") + glob.glob(f"{CACHE_DIR}/*2024-12-31.csv")
    stock_files = [f for f in stock_files if "VNINDEX" not in f]
    
    # Read all files
    all_dfs = []
    for f in stock_files:
        try:
            symbol = os.path.basename(f).split('_')[0]
            df = pd.read_csv(f, parse_dates=["time"])
            df['symbol'] = symbol
            df['source_file'] = os.path.basename(f)
            all_dfs.append(df)
        except:
            pass
            
    if not all_dfs:
        return
        
    full_df = pd.concat(all_dfs, ignore_index=True)
    
    print("\n--- 1. DEDUPLICATION AUDIT ---")
    print(f"Total rows before dedup: {len(full_df)}")
    
    # Sort and check for conflicts before dropping
    full_df = full_df.sort_values(by=['symbol', 'time', 'source_file'])
    
    # Check conflicts: same symbol and time, but different close price
    dups = full_df[full_df.duplicated(subset=['symbol', 'time'], keep=False)]
    conflicts = 0
    if len(dups) > 0:
        std_by_day = dups.groupby(['symbol', 'time'])['close'].std()
        conflicts = (std_by_day > 0.01).sum()
    
    print(f"Rows with duplicated (symbol, time): {len(dups)}")
    print(f"Conflicts (different close prices on same day): {conflicts}")
    
    full_df = full_df.drop_duplicates(subset=['symbol', 'time'], keep='last')
    print(f"Total rows after dedup: {len(full_df)}")
    print(f"Total unique symbols: {full_df['symbol'].nunique()}")
    
    print("\n--- 2. ACTIVE STOCKS BY YEAR (DEDUPLICATED) ---")
    full_df['year'] = full_df['time'].dt.year
    active_by_year = full_df.groupby('year')['symbol'].nunique()
    for y, count in active_by_year.items():
        print(f"  {y}: {count} stocks")
        
    print("\n--- 3. PRICE ADJUSTMENT TEST (BY EXCHANGE LIMITS) ---")
    # Define simple exchange limits proxy
    # HNX: IDC, SHB, VND (temp), TNG, PVS... (assume 10%)
    # UPCOM: BSR, VTP, GVR, VIB (pre-HOSE)... (assume 15%)
    # HOSE: 7%
    full_df['ret'] = full_df.groupby('symbol')['close'].pct_change()
    
    def get_limit(sym):
        if sym in ['BSR', 'VTP']: return 0.155
        if sym in ['TNG', 'IDC', 'SHB', 'VND', 'ACB']: return 0.105
        return 0.075
        
    full_df['limit'] = full_df['symbol'].apply(get_limit)
    bad = full_df[full_df['ret'].abs() > full_df['limit']]
    
    print(f"Total instances of |pct_change| > Exch_Limit: {len(bad)}")
    if len(bad) > 0:
        print(bad.groupby('symbol').size().sort_values(ascending=False).head(10))

    print("\n--- 4. VOLUME ADJUSTMENT TEST ---")
    # Check if 'close * volume' has massive jumps when prices have drops
    # Usually, if price is backward adjusted (divided by 2), but volume is not multiplied by 2,
    # the historical `volume` is small, so `close * volume` for historical dates will be very small.
    # We will just print the median volume and median value for 2018 vs 2026 for a highly-split stock like FPT
    fpt = full_df[full_df['symbol'] == 'FPT'].copy()
    if not fpt.empty:
        fpt['val'] = fpt['close'] * fpt['volume']
        med_val_2018 = fpt[fpt['year'] == 2018]['val'].median()
        med_val_2026 = fpt[fpt['year'] == 2026]['val'].median()
        med_vol_2018 = fpt[fpt['year'] == 2018]['volume'].median()
        med_vol_2026 = fpt[fpt['year'] == 2026]['volume'].median()
        print("FPT 2018 Median Volume:", med_vol_2018)
        print("FPT 2026 Median Volume:", med_vol_2026)
        print("FPT 2018 Median Value (close*vol):", med_val_2018)
        print("FPT 2026 Median Value (close*vol):", med_val_2026)

if __name__ == "__main__":
    main()
