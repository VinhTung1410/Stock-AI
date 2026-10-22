import os

import pandas as pd

VAL_CSV = "data/valuation_events.csv"
if os.path.exists(VAL_CSV):
    val_df = pd.read_csv(VAL_CSV)
    evt_map = {}
    for _, r in val_df.iterrows():
        s = str(r.get("symbol", "")).upper().strip()
        pub_d = str(r.get("bctc_published_date", "")).strip()[:10]
        if s and pub_d and pub_d != "nan":
            evt_map[s] = pub_d
else:
    evt_map = {"VPB": "2026-10-20", "TCB": "2026-10-21"}

target_dates_max_matured = {
    "20261014": "2026-10-21",  # T+5 matured on 21/10
    "20261015": "2026-10-20",  # T+3 matured on 20/10
    "20261016": "2026-10-21",  # T+3 matured on 21/10
    "20261019": "2026-10-20",  # T+1 matured on 20/10
    "20261020": "2026-10-21",  # T+1 matured on 21/10
}

for date_code, max_mat_date in target_dates_max_matured.items():
    csv_file = f"canonical_forward_returns_{date_code}.csv"
    if not os.path.exists(csv_file):
        continue
    df = pd.read_csv(csv_file)
    t0_date = f"{date_code[:4]}-{date_code[4:6]}-{date_code[6:8]}"
    
    crosses_list = []
    bctc_pub_list = []
    for _, row in df.iterrows():
        sym = str(row.get("symbol", "")).upper().strip()
        pub_d = evt_map.get(sym)
        if pub_d:
            bctc_pub_list.append(pub_d)
            crosses = bool(t0_date < pub_d <= max_mat_date)
            crosses_list.append(crosses)
        else:
            bctc_pub_list.append(None)
            crosses_list.append(False)
            
    df["crosses_valuation_event"] = crosses_list
    df["bctc_published_date"] = bctc_pub_list
    df.to_csv(csv_file, index=False)
    
    crosses_true = [df.at[i, "symbol"] for i, val in enumerate(crosses_list) if val]
    print(f"Updated {csv_file}: {len(df)} rows, crosses_valuation_event=True: {crosses_true}")
