import glob
import json
import os

import pandas as pd

TECH_PATH = "data/last_known_tech.json"
adv20_map = {}
if os.path.exists(TECH_PATH):
    with open(TECH_PATH, "r", encoding="utf-8") as f:
        tdata = json.load(f)
        for sym, d in tdata.items():
            adv20_map[sym.upper().strip()] = float(d.get("adv20_billion", 0.0))

records_files = sorted(glob.glob("decision_records_*.csv"))
for rf in records_files:
    df = pd.read_csv(rf)
    if "facts" not in df.columns:
        continue
    updated_facts = []
    for _, row in df.iterrows():
        sym = str(row.get("symbol", "")).upper().strip()
        f_raw = row.get("facts")
        if isinstance(f_raw, str):
            try:
                f_dict = json.loads(f_raw)
            except Exception:
                f_dict = {}
        elif isinstance(f_raw, dict):
            f_dict = f_raw
        else:
            f_dict = {}

        adv = adv20_map.get(sym, 0.0)
        f_dict["adv20_value"] = round(adv, 3)
        f_dict["executable_size_ok"] = bool(adv >= 2.0)
        updated_facts.append(json.dumps(f_dict, ensure_ascii=False))

    df["facts"] = updated_facts
    df.to_csv(rf, index=False)
    print(f"Updated {rf}: {len(df)} rows with adv20_value and executable_size_ok in facts.")
