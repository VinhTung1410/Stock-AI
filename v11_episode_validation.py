import os
import glob
import pandas as pd
import numpy as np

CACHE_DIR = "data/replay_cache"
DISCOVERY_END_DATE = "2023-12-31"

def calculate_market_observables(df_index: pd.DataFrame) -> pd.DataFrame:
    df = df_index.sort_values("time").copy()
    
    df['high_20d'] = df['high'].rolling(20).max()
    df['dd_20d'] = (df['close'] - df['high_20d']) / df['high_20d']
    
    df['tr0'] = abs(df['high'] - df['low'])
    df['tr1'] = abs(df['high'] - df['close'].shift(1))
    df['tr2'] = abs(df['low'] - df['close'].shift(1))
    df['tr'] = df[['tr0', 'tr1', 'tr2']].max(axis=1)
    df['atr_14'] = df['tr'].rolling(14).mean()
    df['atr_60'] = df['tr'].rolling(60).mean()
    df['atr_expansion'] = df['atr_14'] / df['atr_60']
    
    # Forward Returns for VNINDEX (Benchmark)
    df['idx_fwd_20d'] = df['close'].shift(-20) / df['close'] - 1
    
    return df.dropna(subset=['atr_expansion', 'dd_20d'])

def process_stock_tech(sdf: pd.DataFrame, df_market: pd.DataFrame) -> pd.DataFrame:
    sdf = sdf.sort_values("time").copy()
    
    sdf['stock_high_20d'] = sdf['high'].rolling(20).max()
    sdf['stock_dd_20d'] = (sdf['close'] - sdf['stock_high_20d']) / sdf['stock_high_20d']
    
    sdf['fwd_ret_20d'] = sdf['close'].shift(-20) / sdf['close'] - 1
    sdf['fwd_ret_60d'] = sdf['close'].shift(-60) / sdf['close'] - 1
    
    sdf['fwd_min_20d'] = sdf['low'].rolling(20).min().shift(-20)
    sdf['fwd_max_20d'] = sdf['high'].rolling(20).max().shift(-20)
    
    sdf['mae_20d'] = (sdf['fwd_min_20d'] - sdf['close']) / sdf['close']
    sdf['mfe_20d'] = (sdf['fwd_max_20d'] - sdf['close']) / sdf['close']
    
    market_cols = df_market[['time', 'dd_20d', 'atr_expansion', 'idx_fwd_20d']].rename(columns={
        'dd_20d': 'market_dd_20d', 
        'atr_expansion': 'market_atr_exp'
    })
    sdf = pd.merge(sdf, market_cols, on='time', how='inner')
    
    # Relative return
    sdf['rel_ret_20d'] = sdf['fwd_ret_20d'] - sdf['idx_fwd_20d']
    
    return sdf.dropna(subset=['stock_dd_20d', 'fwd_ret_20d', 'fwd_ret_60d', 'market_atr_exp'])

def get_episodes(eligible_dates, max_gap_days=15):
    """Cluster eligible dates into episodes based on a max gap of days."""
    if len(eligible_dates) == 0:
        return []
    
    dates = sorted(eligible_dates)
    episodes = []
    current_ep = [dates[0]]
    
    for i in range(1, len(dates)):
        gap = (dates[i] - dates[i-1]).days
        if gap <= max_gap_days:
            current_ep.append(dates[i])
        else:
            episodes.append(current_ep)
            current_ep = [dates[i]]
            
    if current_ep:
        episodes.append(current_ep)
        
    return episodes

def summarize_episode(ep_id: int, start, end, df: pd.DataFrame, df_market: pd.DataFrame) -> dict:
    if df.empty:
        return {}
        
    n_signals = len(df)
    n_stocks = df['symbol'].nunique() if 'symbol' in df.columns else "N/A"
    
    # Calculate market metrics for the episode
    # Average VNIndex forward return for the dates in this episode
    idx_returns = df_market[df_market['time'].isin(df['time'].unique())]['idx_fwd_20d']
    med_idx_20d = idx_returns.median()
    
    return {
        "Episode": f"Ep #{ep_id}",
        "Period": f"{start.date()} to {end.date()}",
        "Signals": n_signals,
        # "Stocks": n_stocks,
        "Win Rate (T20)": f"{(df['fwd_ret_20d'] > 0).mean():.2%}",
        "Med T20": f"{df['fwd_ret_20d'].median():.2%}",
        "Idx T20": f"{med_idx_20d:.2%}",
        "Med Rel T20": f"{df['rel_ret_20d'].median():.2%}",
        "Med MAE": f"{df['mae_20d'].median():.2%}",
        "Med MFE": f"{df['mfe_20d'].median():.2%}"
    }

def main():
    print("=== V11 EPISODE VALIDATION (OUT-OF-SAMPLE) ===")
    index_files = glob.glob(f"{CACHE_DIR}/VNINDEX*2026-10-*.csv")
    if not index_files:
        return
        
    df_market = calculate_market_observables(pd.read_csv(index_files[-1], parse_dates=["time"]))
    
    # We load ALL stocks matching 2026 pattern
    stock_files = glob.glob(f"{CACHE_DIR}/*2026-10-*.csv")
    all_stocks_data = []
    
    for f in stock_files:
        if "VNINDEX" in f: continue
        try:
            sdf = pd.read_csv(f, parse_dates=["time"])
            symbol = os.path.basename(f).split('_')[0]
            sdf['symbol'] = symbol
            sdf = process_stock_tech(sdf, df_market)
            all_stocks_data.append(sdf)
        except Exception:
            pass
            
    df_all = pd.concat(all_stocks_data, ignore_index=True)
    df_oos = df_all[df_all['time'] > DISCOVERY_END_DATE].copy()
    
    # Define Gate 0:
    cond_extreme = (df_oos['market_dd_20d'] < -0.15) & (df_oos['market_atr_exp'] >= 1.5)
    cond_silent = (df_oos['market_dd_20d'] < -0.08) & (df_oos['market_atr_exp'] < 1.0)
    cond_gate0 = cond_extreme | cond_silent
    
    df_eligible = df_oos[cond_gate0].copy()
    eligible_dates = df_eligible['time'].unique()
    
    episodes = get_episodes(eligible_dates, max_gap_days=15)
    print(f"Discovered {len(episodes)} Independent Episodes in OOS.")
    
    # Analyze by Episode
    results_B = []
    results_C = []
    results_D = []
    
    for idx, ep_dates in enumerate(episodes):
        ep_id = idx + 1
        start = min(ep_dates)
        end = max(ep_dates)
        
        # Data for this episode
        ep_df = df_eligible[df_eligible['time'].isin(ep_dates)]
        ep_C = ep_df[ep_df['stock_dd_20d'] < -0.25]
        ep_D = ep_df[ep_df['stock_dd_20d'] >= -0.25]
        
        # Group C
        sum_C = summarize_episode(ep_id, start, end, ep_C, df_market)
        if sum_C: sum_C['Group'] = "C. DD < -25%"
        
        # Group D
        sum_D = summarize_episode(ep_id, start, end, ep_D, df_market)
        if sum_D: sum_D['Group'] = "D. DD >= -25%"
        
        if sum_C: results_C.append(sum_C)
        if sum_D: results_D.append(sum_D)
        
    print("\n--- EPISODE VALIDATION: GROUP C (Stock DD < -25%) ---")
    if results_C:
        print(pd.DataFrame(results_C).to_markdown(index=False))
    
    print("\n--- EPISODE VALIDATION: GROUP D (Stock DD >= -25%) ---")
    if results_D:
        print(pd.DataFrame(results_D).to_markdown(index=False))
        
    print("\n--- SUMMARY OF INDEPENDENCE ---")
    print(f"Total Crises (Episodes): {len(episodes)}")
    win_episodes_c = sum(1 for r in results_C if float(r['Med Rel T20'].strip('%')) > 0)
    print(f"Group C Outperforms VNINDEX in {win_episodes_c}/{len(results_C)} episodes.")

if __name__ == "__main__":
    main()
