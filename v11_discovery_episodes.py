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
    
    # Forward Returns for VNINDEX (Benchmark) - Entry at OPEN(D+1)
    # shift(-1) gets next day's open. shift(-20) gets close at D+20.
    df['idx_open_d1'] = df['open'].shift(-1)
    df['idx_fwd_20d'] = df['close'].shift(-20) / df['idx_open_d1'] - 1
    
    return df.dropna(subset=['atr_expansion', 'dd_20d'])

def process_stock_tech(sdf: pd.DataFrame, df_market: pd.DataFrame) -> pd.DataFrame:
    sdf = sdf.sort_values("time").copy()
    
    sdf['stock_high_20d'] = sdf['high'].rolling(20).max()
    sdf['stock_dd_20d'] = (sdf['close'] - sdf['stock_high_20d']) / sdf['stock_high_20d']
    
    # Execution Realism: Entry at Open(D+1)
    sdf['open_d1'] = sdf['open'].shift(-1)
    sdf['fwd_ret_20d'] = sdf['close'].shift(-20) / sdf['open_d1'] - 1
    
    # MAE/MFE relative to entry price Open(D+1)
    sdf['fwd_min_20d'] = sdf['low'].rolling(20).min().shift(-20)
    sdf['fwd_max_20d'] = sdf['high'].rolling(20).max().shift(-20)
    sdf['mae_20d'] = (sdf['fwd_min_20d'] - sdf['open_d1']) / sdf['open_d1']
    sdf['mfe_20d'] = (sdf['fwd_max_20d'] - sdf['open_d1']) / sdf['open_d1']
    
    market_cols = df_market[['time', 'dd_20d', 'atr_expansion', 'idx_fwd_20d']].rename(columns={
        'dd_20d': 'market_dd_20d', 
        'atr_expansion': 'market_atr_exp'
    })
    sdf = pd.merge(sdf, market_cols, on='time', how='inner')
    
    # Relative return vs VNIndex (both entered at Open D+1)
    sdf['rel_ret_20d'] = sdf['fwd_ret_20d'] - sdf['idx_fwd_20d']
    
    return sdf.dropna(subset=['stock_dd_20d', 'fwd_ret_20d', 'market_atr_exp', 'open_d1'])

def get_episodes(eligible_dates, max_gap_days=15):
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

def main():
    index_files = glob.glob(f"{CACHE_DIR}/VNINDEX*2026-10-*.csv")
    if not index_files:
        return
        
    df_market = calculate_market_observables(pd.read_csv(index_files[-1], parse_dates=["time"]))
    
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
    
    # Focus strictly on Discovery period
    df_disc = df_all[df_all['time'] <= DISCOVERY_END_DATE].copy()
    
    # Frozen Gate 0 Rules
    cond_extreme = (df_disc['market_dd_20d'] < -0.15) & (df_disc['market_atr_exp'] >= 1.5)
    cond_silent = (df_disc['market_dd_20d'] < -0.08) & (df_disc['market_atr_exp'] < 1.0)
    df_eligible = df_disc[cond_extreme | cond_silent].copy()
    
    episodes = get_episodes(df_eligible['time'].unique(), max_gap_days=15)
    
    episode_results = []
    
    for idx, ep_dates in enumerate(episodes):
        ep_df = df_eligible[df_eligible['time'].isin(ep_dates)]
        
        # Group C: Stock DD < -25%
        group_C = ep_df[ep_df['stock_dd_20d'] < -0.25]
        
        n_signals = len(group_C)
        if n_signals == 0:
            continue
            
        # Benchmarks
        # Market median return for this episode (from index)
        idx_returns = df_market[df_market['time'].isin(ep_dates)]['idx_fwd_20d']
        idx_med = idx_returns.median()
        
        # Naive benchmark: Group D (Eligible but DD >= -25%)
        group_D = ep_df[ep_df['stock_dd_20d'] >= -0.25]
        med_D = group_D['fwd_ret_20d'].median() if not group_D.empty else np.nan
        
        c_med = group_C['fwd_ret_20d'].median()
        c_rel_med = group_C['rel_ret_20d'].median()
        c_mae = group_C['mae_20d'].median()
        
        episode_results.append({
            "Episode": idx + 1,
            "Date": min(ep_dates).strftime('%Y-%m'),
            "N(C)": n_signals,
            "Group C Med": c_med,
            "Index Med": idx_med,
            "Group D Med": med_D,
            "C - Index": c_rel_med,
            "C - Group D": c_med - med_D if not np.isnan(med_D) else np.nan,
            "Med MAE(C)": c_mae
        })
        
    res_df = pd.DataFrame(episode_results)
    
    print("=== V11 EPISODE-LEVEL VALIDATION (DISCOVERY DATA) ===")
    print("Execution: Entry at Open(D+1)")
    
    if res_df.empty:
        print("No episodes with Group C signals.")
        return
        
    # Formatting
    format_cols = ['Group C Med', 'Index Med', 'Group D Med', 'C - Index', 'C - Group D', 'Med MAE(C)']
    for col in format_cols:
        res_df[col] = res_df[col].apply(lambda x: f"{x:.2%}" if pd.notnull(x) else "N/A")
        
    print(res_df.to_markdown(index=False))
    
    print("\n--- EPISODE-LEVEL STATISTICS (N=8) ---")
    win_vs_idx = sum(1 for r in episode_results if r['C - Index'] > 0)
    win_vs_D = sum(1 for r in episode_results if r['C - Group D'] > 0)
    
    c_med_agg = np.median([r['Group C Med'] for r in episode_results])
    idx_med_agg = np.median([r['Index Med'] for r in episode_results])
    
    print(f"Total Episodes with Signals: {len(episode_results)}")
    print(f"Group C Outperforms VNINDEX: {win_vs_idx}/{len(episode_results)} episodes")
    print(f"Group C Outperforms Group D (Mild DD): {win_vs_D}/{len(episode_results)} episodes")
    print(f"Aggregated Episode Median (Group C): {c_med_agg:.2%}")
    print(f"Aggregated Episode Median (VNIndex): {idx_med_agg:.2%}")

if __name__ == "__main__":
    main()
