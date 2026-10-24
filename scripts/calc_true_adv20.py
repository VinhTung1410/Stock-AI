import io
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

from vnstock.api.quote import Quote

for sym in ['FMC', 'GIL']:
    q = Quote(symbol=sym, source='VCI')
    df = q.history(start='2026-08-15', end='2026-10-24')
    df['time'] = df['time'].astype(str).str[:10]
    df['val_vnd'] = df['close'] * 1000.0 * df['volume']
    df['val_bil'] = df['val_vnd'] / 1e9
    
    # 20 sessions ending 2026-10-13 (inclusive)
    df_13 = df[df['time'] <= '2026-10-13'].tail(20)
    adv20_13 = df_13['val_bil'].mean()
    vol_ma20_13 = df_13['volume'].mean()
    
    # 20 sessions ending 2026-10-23 (inclusive)
    df_23 = df[df['time'] <= '2026-10-23'].tail(20)
    adv20_23 = df_23['val_bil'].mean()
    vol_ma20_23 = df_23['volume'].mean()
    
    print(f'*** {sym} ***')
    print(f'At 13/10: Range {df_13.iloc[0]["time"]} to {df_13.iloc[-1]["time"]}')
    print(f'At 13/10: VOL_MA20 = {vol_ma20_13:.1f} CP, ADV20 = {adv20_13:.3f} ty VND')
    print(f'At 23/10: Range {df_23.iloc[0]["time"]} to {df_23.iloc[-1]["time"]}')
    print(f'At 23/10: VOL_MA20 = {vol_ma20_23:.1f} CP, ADV20 = {adv20_23:.3f} ty VND')
    
    # Print 20 sessions table for 13/10
    print(f'--- OHLCV 20 sessions ending 13/10 for {sym} ---')
    print(df_13[['time', 'open', 'high', 'low', 'close', 'volume', 'val_bil']].to_string(index=False))
