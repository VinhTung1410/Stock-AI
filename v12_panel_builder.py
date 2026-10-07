import os
import glob
import hashlib
import pandas as pd
import numpy as np

CACHE_DIR = "data/replay_cache"
OUTPUT_FILE = "data/v12_panel_data.csv"
SPEC_LOG = "CONTRARIAN_V12_SPECIFICATION_LOG.md"

def calc_rsi(series, periods=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).fillna(0)
    loss = (-delta.where(delta < 0, 0)).fillna(0)
    avg_gain = gain.rolling(window=periods, min_periods=periods).mean()
    avg_loss = loss.rolling(window=periods, min_periods=periods).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def build_panel():
    print("=== V12 PANEL BUILDER ===")
    
    # 1. Deduplicate & Load Data
    stock_files = glob.glob(f"{CACHE_DIR}/*2026-10-07.csv") + glob.glob(f"{CACHE_DIR}/*2026-10-06.csv") + glob.glob(f"{CACHE_DIR}/*2024-12-31.csv")
    stock_files = [f for f in stock_files if "VNINDEX" not in f]
    
    all_dfs = []
    for f in stock_files:
        try:
            symbol = os.path.basename(f).split('_')[0]
            df = pd.read_csv(f, parse_dates=["time"])
            df['time'] = df['time'].dt.normalize() # NORMALIZE TIMESTAMPS
            df['symbol'] = symbol
            all_dfs.append(df)
        except:
            pass
            
    full_df = pd.concat(all_dfs, ignore_index=True)
    full_df = full_df.sort_values(by=['symbol', 'time'])
    # Keep last observed data when duplicated
    full_df = full_df.drop_duplicates(subset=['symbol', 'time'], keep='last')
    
    # 2. Master Trading Calendar
    master_calendar = pd.DataFrame({'time': sorted(full_df['time'].unique())})
    symbols = full_df['symbol'].unique()
    
    print(f"Total Unique Symbols: {len(symbols)}")
    print(f"Total Trading Days: {len(master_calendar)}")
    
    # Static Industry Mapping (Approximation)
    banks = ['ACB', 'BID', 'CTG', 'HDB', 'MBB', 'SHB', 'STB', 'TCB', 'TPB', 'VCB', 'VIB', 'VPB', 'SSB', 'EIB', 'LPB', 'MSB', 'OCB', 'SGB', 'BAB', 'NVB', 'PGB', 'KLB', 'BVB']
    real_estate = ['DIG', 'DXG', 'KBC', 'KDH', 'NLG', 'NVL', 'PDR', 'VHM', 'VIC', 'VRE', 'CEO', 'HDG', 'CRE', 'TCH', 'SCR', 'HDC', 'IJC', 'NBB', 'SJS', 'SZC', 'VGC']
    
    def get_industry(sym):
        if sym in banks: return 'Bank'
        if sym in real_estate: return 'Real_Estate'
        return 'Others'
    
    panel_rows = []
    
    for sym in symbols:
        sym_df = full_df[full_df['symbol'] == sym].copy()
        sym_df = pd.merge(master_calendar, sym_df, on='time', how='left')
        
        # Flags
        sym_df['observed'] = sym_df['close'].notna().astype(int)
        
        # Forward fill prices for suspended days
        sym_df['close'] = sym_df['close'].ffill()
        sym_df['open'] = sym_df['open'].ffill()
        sym_df['high'] = sym_df['high'].ffill()
        sym_df['low'] = sym_df['low'].ffill()
        
        # Volume fill 0 for missing days
        sym_df['volume'] = sym_df['volume'].fillna(0)
        sym_df['volume_zero'] = (sym_df['volume'] == 0).astype(int)
        
        sym_df['symbol'] = sym
        sym_df['industry_static_nonPIT'] = get_industry(sym)
        
        # Features (D <= D)
        sym_df['high_60d'] = sym_df['high'].rolling(60).max()
        sym_df['DD60'] = (sym_df['close'] - sym_df['high_60d']) / sym_df['high_60d']
        sym_df['depth_DD60'] = -sym_df['DD60'] # Positive depth means deeper drawdown
        sym_df['RSI14'] = calc_rsi(sym_df['close'], 14)
        sym_df['Rev5'] = sym_df['close'].pct_change(5)
        
        # Liquidity proxy (Volume * Close) -> Caution: volume is unadjusted, so value is backward-distorted
        sym_df['adv_20d'] = (sym_df['volume'] * sym_df['close']).rolling(20).mean()
        
        # Outcomes (Decomposition)
        # Entry is Close(D) for primary, Open(D+1) for decomposition
        sym_df['open_d1'] = sym_df['open'].shift(-1)
        sym_df['close_d20'] = sym_df['close'].shift(-20)
        
        # Returns
        sym_df['ret_D_to_D20'] = (sym_df['close_d20'] - sym_df['close']) / sym_df['close']
        sym_df['ret_D_to_D1'] = (sym_df['open_d1'] - sym_df['close']) / sym_df['close']
        sym_df['ret_D1_to_D20'] = (sym_df['close_d20'] - sym_df['open_d1']) / sym_df['open_d1']
        
        # Missing future flag (Right-censoring)
        sym_df['missing_future'] = sym_df['close_d20'].isna().astype(int)
        
        panel_rows.append(sym_df)
        
    panel_df = pd.concat(panel_rows, ignore_index=True)
    
    # Calculate Cross-Sectional Ranks (Daily)
    # Only calculate ranks if observed == 1 and adv_20d > 0
    valid_mask = (panel_df['observed'] == 1) & (panel_df['adv_20d'] > 0)
    
    panel_df.loc[valid_mask, 'rank_depth_DD60'] = panel_df[valid_mask].groupby('time')['depth_DD60'].rank(pct=True)
    panel_df.loc[valid_mask, 'rank_RSI14'] = panel_df[valid_mask].groupby('time')['RSI14'].rank(pct=True)
    panel_df.loc[valid_mask, 'rank_Rev5'] = panel_df[valid_mask].groupby('time')['Rev5'].rank(pct=True)
    
    # Calculate Relative Returns (Only for quintiles/reporting)
    median_ret = panel_df[valid_mask].groupby('time')['ret_D_to_D20'].transform('median')
    panel_df['relative_ret_D_to_D20'] = panel_df['ret_D_to_D20'] - median_ret
    
    # Drop rows before 60-day warmup
    panel_df = panel_df.dropna(subset=['DD60'])
    
    # Save
    panel_df.to_csv(OUTPUT_FILE, index=False)
    
    # Hash
    with open(OUTPUT_FILE, "rb") as f:
        file_hash = hashlib.sha256(f.read()).hexdigest()
        
    print(f"\nPanel built and saved to {OUTPUT_FILE}")
    print(f"Data Hash (SHA-256): {file_hash}")
    
    # Write to SPEC_LOG
    with open(SPEC_LOG, "a", encoding="utf-8") as f:
        f.write(f"\n## Panel Build Log\n")
        f.write(f"- **Symbols:** {len(symbols)}\n")
        f.write(f"- **Total Rows:** {len(panel_df)}\n")
        f.write(f"- **Dedup Rule:** Keep 'last' on (symbol, time)\n")
        f.write(f"- **Missing Future (Right Censor) Rows:** {panel_df['missing_future'].sum()}\n")
        f.write(f"- **Zero Volume Rows:** {panel_df['volume_zero'].sum()}\n")
        f.write(f"- **Panel Hash:** `{file_hash}`\n")
        
if __name__ == "__main__":
    build_panel()
