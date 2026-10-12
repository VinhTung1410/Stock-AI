import os
import sys

import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db_manager import get_supabase_client

client = get_supabase_client()
res = (
    client.table("decision_records")
    .select("*")
    .ilike("decision_id", "%20261012_EOD_REPLAY%")
    .order("symbol", desc=False)
    .execute()
)
records = res.data or []
rows = []
for r in records:
    facts = r.get("facts") or {}
    reasons = r.get("rejection_reasons") or []
    if isinstance(reasons, list):
        reasons_str = " | ".join(str(x) for x in reasons)
    else:
        reasons_str = str(reasons or "")

    rows.append({
        "decision_id": r.get("decision_id"),
        "symbol": r.get("symbol"),
        "decision": r.get("decision"),
        "session": r.get("session"),
        "primary_rejection_gate": r.get("primary_rejection_gate"),
        "price": facts.get("price"),
        "mos_pct": facts.get("mos_pct"),
        "conviction": facts.get("conviction"),
        "rejection_reasons": reasons_str,
        "model_version": r.get("model_version"),
        "git_sha": r.get("git_sha"),
        "created_at": r.get("created_at"),
    })

df = pd.DataFrame(rows)
csv_path = "decision_records_20261012_eod_shadow.csv"
df.to_csv(csv_path, index=False, encoding="utf-8-sig")
print(f"Successfully exported {len(df)} rows to {csv_path}")

print("\nKey Stock Comparison:")
for s in ["STB", "CTG", "ACB", "HPG", "FPT", "DIG", "KDH"]:
    match = df[df["symbol"] == s]
    if not match.empty:
        m = match.iloc[0]
        print(f"[{s}] Decision: {m['decision']:<6} | Gate: {m['primary_rejection_gate']:<18} | MoS: {str(m['mos_pct']):<8}% | Price: {m['price']}k")
