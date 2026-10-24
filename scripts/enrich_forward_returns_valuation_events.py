import json
import os

import pandas as pd

VAL_CSV = "data/valuation_events.csv"
evt_pub_map = {}
evt_det_map = {}
if os.path.exists(VAL_CSV):
    val_df = pd.read_csv(VAL_CSV)
    for _, r in val_df.iterrows():
        s = str(r.get("symbol", "")).upper().strip()
        pub_d = str(r.get("bctc_published_date", "")).strip()[:10]
        det_d = str(r.get("bctc_detected_date", pub_d)).strip()[:10]
        if s and pub_d and pub_d != "nan":
            evt_pub_map[s] = pub_d
            evt_det_map[s] = det_d
else:
    evt_pub_map = {"VPB": "2026-10-20", "TCB": "2026-10-21"}
    evt_det_map = {"VPB": "2026-10-20", "TCB": "2026-10-21"}

TECH_PATH = "data/last_known_tech.json"
adv20_map = {}
if os.path.exists(TECH_PATH):
    with open(TECH_PATH, "r", encoding="utf-8") as f:
        tdata = json.load(f)
        for sym, d in tdata.items():
            adv20_map[sym.upper().strip()] = float(d.get("adv20_billion", 0.0))

target_dates_horizons = {
    "20261014": {1: "2026-10-15", 3: "2026-10-19", 5: "2026-10-21"},
    "20261015": {1: "2026-10-16", 3: "2026-10-20", 5: "2026-10-22"},
    "20261016": {1: "2026-10-19", 3: "2026-10-21", 5: "2026-10-23"},
    "20261019": {1: "2026-10-20", 3: "2026-10-22", 5: "2026-10-26"},
    "20261020": {1: "2026-10-21", 3: "2026-10-23", 5: "2026-10-27"},
    "20261021": {1: "2026-10-22", 3: "2026-10-26", 5: "2026-10-28"},
    "20261022": {1: "2026-10-23", 3: "2026-10-27", 5: "2026-10-29"},
}

target_dates_max_matured = {
    "20261014": "2026-10-21",  # T+5 matured on 21/10
    "20261015": "2026-10-22",  # T+5 matured on 22/10
    "20261016": "2026-10-23",  # T+5 matured on 23/10
    "20261019": "2026-10-22",  # T+3 matured on 22/10
    "20261020": "2026-10-23",  # T+3 matured on 23/10
    "20261021": "2026-10-22",  # T+1 matured on 22/10
    "20261022": "2026-10-23",  # T+1 matured on 23/10
}

for date_code, h_dates in target_dates_horizons.items():
    csv_file = f"canonical_forward_returns_{date_code}.csv"
    if not os.path.exists(csv_file):
        continue
    df = pd.read_csv(csv_file)
    t0_date = f"{date_code[:4]}-{date_code[4:6]}-{date_code[6:8]}"
    max_mat_date = target_dates_max_matured.get(date_code)

    crosses_t1_list = []
    crosses_t3_list = []
    crosses_t5_list = []
    crosses_list = []
    bctc_pub_list = []
    bctc_det_list = []
    adv20_list = []
    exec_size_ok_list = []

    for _, row in df.iterrows():
        sym = str(row.get("symbol", "")).upper().strip()
        pub_d = evt_pub_map.get(sym)
        det_d = evt_det_map.get(sym)
        adv = adv20_map.get(sym, 0.0)
        adv20_list.append(round(adv, 3))
        exec_size_ok_list.append(bool(adv >= 2.0))

        if pub_d:
            bctc_pub_list.append(pub_d)
            bctc_det_list.append(det_d)
            c1 = bool(t0_date < pub_d <= h_dates[1])
            c3 = bool(t0_date < pub_d <= h_dates[3])
            c5 = bool(t0_date < pub_d <= h_dates[5])
            crosses_t1_list.append(c1)
            crosses_t3_list.append(c3)
            crosses_t5_list.append(c5)
            crosses = bool(t0_date < pub_d <= max_mat_date) if max_mat_date else False
            crosses_list.append(crosses)
        else:
            bctc_pub_list.append(None)
            bctc_det_list.append(None)
            crosses_t1_list.append(False)
            crosses_t3_list.append(False)
            crosses_t5_list.append(False)
            crosses_list.append(False)

    df["adv20_value"] = adv20_list
    df["executable_size_ok"] = exec_size_ok_list
    df["crosses_t1"] = crosses_t1_list
    df["crosses_t3"] = crosses_t3_list
    df["crosses_t5"] = crosses_t5_list
    df["crosses_valuation_event"] = crosses_list
    df["bctc_published_date"] = bctc_pub_list
    df["bctc_detected_date"] = bctc_det_list

    # Reorder columns neatly
    drop_cols = {
        "adv20_value", "executable_size_ok", "crosses_t1", "crosses_t3",
        "crosses_t5", "crosses_valuation_event", "bctc_published_date", "bctc_detected_date"
    }
    cols = [c for c in df.columns if c not in drop_cols]
    if "large_overnight_gap" in cols:
        pos_gap = cols.index("large_overnight_gap") + 1
        cols = cols[:pos_gap] + ["adv20_value", "executable_size_ok"] + cols[pos_gap:]
    if "est_fee_tax_pct" in cols:
        pos_fee = cols.index("est_fee_tax_pct") + 1
        cols = cols[:pos_fee] + ["crosses_t1", "crosses_t3", "crosses_t5", "crosses_valuation_event", "bctc_published_date", "bctc_detected_date"] + cols[pos_fee:]
    df = df[cols]

    df.to_csv(csv_file, index=False)

    t1_true = [df.at[i, "symbol"] for i, val in enumerate(crosses_t1_list) if val]
    t3_true = [df.at[i, "symbol"] for i, val in enumerate(crosses_t3_list) if val]
    t5_true = [df.at[i, "symbol"] for i, val in enumerate(crosses_t5_list) if val]
    thin_liquidity = [df.at[i, "symbol"] for i, val in enumerate(exec_size_ok_list) if not val]
    print(f"Updated {csv_file}: {len(df)} rows")
    print(f"  thin_liquidity (adv20 < 2.0 bil): {thin_liquidity}")
    print(f"  crosses_t1: {t1_true}")
    print(f"  crosses_t3: {t3_true}")
    print(f"  crosses_t5: {t5_true}")
