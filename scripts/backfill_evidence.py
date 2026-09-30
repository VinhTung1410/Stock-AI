import logging

from db_manager import get_supabase_client

logging.basicConfig(level=logging.INFO)

def backfill_signal_lifecycle():
    client = get_supabase_client()
    if not client:
        print("Failed to get Supabase client")
        return
        
    res = client.table('signals').select('id, symbol, created_at, entry_price, target_price, stop_loss, f_score, mos_pct, signal_tracking(*)').execute()
    signals = res.data or []
    
    count = 0
    for s in signals:
        sig_id = str(s['id'])
        tracking = s.get('signal_tracking')
        track = tracking[0] if tracking else {}
        
        status = track.get('status', 'OPEN')
        pnl = track.get('actual_pnl_pct')
        
        r_multiple = None
        if s.get('stop_loss') and s.get('entry_price') and pnl is not None:
            risk_pct = abs(s['entry_price'] - s['stop_loss']) / s['entry_price'] * 100
            if risk_pct > 0:
                r_multiple = round(pnl / risk_pct, 2)
                
        row = {
            "signal_id": sig_id,
            "symbol": s['symbol'],
            "entry_price": s.get('entry_price'),
            "f_score": s.get('f_score', 0),
            "mos_pct": s.get('mos_pct', 0.0),
            "target_price": s.get('target_price'),
            "initial_stop_price": s.get('stop_loss'),
            "status": status,
            "exit_price": track.get('exit_price'),
            "pnl_pct": pnl,
            "r_multiple": r_multiple,
            "exit_reason": track.get('loss_attribution'),
            "created_at": s.get('created_at')
        }
        
        try:
            client.table('signal_lifecycle').upsert(row, on_conflict='signal_id').execute()
            count += 1
            print(f"Upserted {s['symbol']} ({sig_id})")
        except Exception as e:
            print(f"Error upserting {sig_id}: {e}")
            
    print(f"Successfully backfilled {count} signals to signal_lifecycle.")

if __name__ == "__main__":
    backfill_signal_lifecycle()
