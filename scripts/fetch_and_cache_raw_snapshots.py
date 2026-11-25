import json
import os
import sys

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)
import pandas as pd

from db_manager import get_supabase_client

client = get_supabase_client()
if not client:
    raise RuntimeError("Cannot connect to Supabase")

DATES = ["20261020", "20261021", "20261022", "20261023"]

for d in DATES:
    df = pd.read_csv(f"decision_records_{d}.csv")
    can_df = df[df["is_canonical"].astype(bool)].sort_values("symbol")
    can_ids = can_df["decision_id"].tolist()
    
    out_file = f"data/raw_snapshots_{d}_canonical.json"
    if os.path.exists(out_file):
        with open(out_file, "r", encoding="utf-8") as f:
            existing = json.load(f)
        if len(existing) == 55:
            print(f"{d}: already cached with 55 snapshots at {out_file}")
            continue

    print(f"Fetching 55 raw snapshots for {d} from Supabase...")
    res = client.table("raw_input_snapshots").select("*").in_("decision_id", can_ids).execute()
    data = res.data or []
    print(f"Fetched {len(data)} snapshots for {d}")
    
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"Saved to {out_file}")
