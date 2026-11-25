import json
import os
import sys

import pandas as pd

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)
from unittest.mock import patch

import data_engine as de_new
import data_engine_734893f as de_old
from tests.test_golden_zero_diff_replay import CANONICAL_55_SYMBOLS

with open('data/last_known_tech.json', 'r', encoding='utf-8') as f:
    tech_data = json.load(f)

with open('data/cached_fin_55.json', 'r', encoding='utf-8') as f:
    fin_cache = json.load(f)

def mock_tech(sym, count_back=60, fetch_foreign=True):
    return tech_data.get(sym.upper().strip(), {})

def mock_fin(sym):
    return fin_cache.get(sym.upper().strip(), {
        "symbol": sym.upper().strip(),
        "period": "2026-Q2",
        "pe": 12.0,
        "pb": 1.5,
        "bvps": 20000.0,
        "eps": 2500.0,
        "roe": 15.0,
    })

saved_old = {}
saved_new = {}

with patch('data_engine_734893f.fetch_stock_technical', side_effect=mock_tech), \
     patch('data_engine_734893f.get_financial_ratios', side_effect=mock_fin), \
     patch('data_engine_734893f.fetch_macro_news', return_value=[]), \
     patch('data_engine_734893f.load_watchlist', return_value=[]), \
     patch('db_manager.save_decision_record', side_effect=lambda r: saved_old.update({r['symbol']: r}) or 'DEC_OLD'), \
     patch('db_manager.save_lifecycle_event', return_value='EVT_O'), \
     patch('db_manager.update_decision_forward_returns', return_value=True):
    de_old.scan_market_opportunities(extra_symbols=CANONICAL_55_SYMBOLS, session_override='GOLDEN_REPLAY')

with patch('data_engine.fetch_stock_technical', side_effect=mock_tech), \
     patch('data_engine.get_financial_ratios', side_effect=mock_fin), \
     patch('data_engine.fetch_macro_news', return_value=[]), \
     patch('data_engine.load_watchlist', return_value=[]), \
     patch('db_manager.save_decision_record', side_effect=lambda r: saved_new.update({r['symbol']: r}) or 'DEC_NEW'), \
     patch('db_manager.save_lifecycle_event', return_value='EVT_N'), \
     patch('db_manager.update_decision_forward_returns', return_value=True):
    de_new.scan_market_opportunities(extra_symbols=CANONICAL_55_SYMBOLS, session_override='GOLDEN_REPLAY')

rows = []
for s in CANONICAL_55_SYMBOLS:
    o = saved_old.get(s, {})
    n = saved_new.get(s, {})
    fo = o.get('facts', {})
    fn = n.get('facts', {})
    rows.append({
        'symbol': s,
        'old_dec': o.get('decision'),
        'new_dec': n.get('decision'),
        'old_gate': o.get('primary_rejection_gate'),
        'new_gate': n.get('primary_rejection_gate'),
        'old_mos': o.get('mos_pct'),
        'new_mos': n.get('mos_pct'),
        'old_conv': o.get('conviction'),
        'new_conv': n.get('conviction'),
        'old_p': o.get('price'),
        'new_p': n.get('price'),
        'old_fv': fo.get('fair_value_base'),
        'new_fv': fn.get('fair_value_base'),
        'diff': (o.get('decision') != n.get('decision') or o.get('primary_rejection_gate') != n.get('primary_rejection_gate') or o.get('mos_pct') != n.get('mos_pct'))
    })

df = pd.DataFrame(rows)
df.to_csv('replay_diff_summary.csv', index=False)
print('Total symbols:', len(df), 'Diffs:', df['diff'].sum())
