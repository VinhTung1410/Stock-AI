import json
import os
import sys

import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db_manager import get_supabase_client

client = get_supabase_client()
if not client:
    print("Error: Supabase client not available.")
    sys.exit(1)

# 1. Export decision_records
res = (
    client.table("decision_records")
    .select("*")
    .ilike("decision_id", "%20261012_EOD_REPLAY_V2%")
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

    gates_failed_raw = facts.get("gates_failed", [])
    gates_failed_str = ", ".join(gates_failed_raw) if isinstance(gates_failed_raw, list) else str(gates_failed_raw or "")

    rows.append({
        "decision_id": r.get("decision_id"),
        "symbol": r.get("symbol"),
        "decision": r.get("decision"),
        "session": r.get("session"),
        "primary_rejection_gate": r.get("primary_rejection_gate"),
        "price": facts.get("price"),
        "mos_pct": facts.get("mos_pct"),
        "conviction": facts.get("conviction"),
        "input_source": facts.get("input_source"),
        "gates_failed": gates_failed_str,
        "informative": facts.get("informative"),
        "price_source": facts.get("price_source"),
        "price_asof": facts.get("price_asof"),
        "rejection_reasons": reasons_str,
        "facts": json.dumps(facts, ensure_ascii=False),
        "model_version": r.get("model_version"),
        "git_sha": r.get("git_sha"),
        "created_at": r.get("created_at"),
    })

df = pd.DataFrame(rows)
csv_path = "decision_records_20261012_eod_shadow.csv"
df.to_csv(csv_path, index=False, encoding="utf-8-sig")
print(f"Successfully exported {len(df)} decision rows to {csv_path}")

# 2. Export decision_lifecycle_events
evt_res = (
    client.table("decision_lifecycle_events")
    .select("*")
    .ilike("correlation_id", "%20261012_EOD_REPLAY_V2%")
    .order("symbol", desc=False)
    .execute()
)
evt_records = evt_res.data or []
evt_rows = []
for e in evt_records:
    edata = e.get("event_data") or {}
    evt_rows.append({
        "created_at": e.get("created_at"),
        "symbol": e.get("symbol"),
        "event_type": e.get("event_type"),
        "correlation_id": e.get("correlation_id"),
        "source": edata.get("source"),
        "decision": edata.get("decision"),
        "ai_action": edata.get("ai_action"),
        "sizing_factor": edata.get("sizing_factor"),
        "market_price": edata.get("price"),
        "primary_rejection_gate": edata.get("gate"),
        "rejection_reasons": " | ".join(str(x) for x in edata.get("reasons", [])) if isinstance(edata.get("reasons"), list) else str(edata.get("reasons") or ""),
        "model_version": e.get("model_version"),
        "git_sha": e.get("git_sha"),
    })

df_evt = pd.DataFrame(evt_rows)
evt_csv_path = "lifecycle_events_20261012_eod_shadow.csv"
df_evt.to_csv(evt_csv_path, index=False, encoding="utf-8-sig")
print(f"Successfully exported {len(df_evt)} lifecycle rows to {evt_csv_path}")

print("\nKey Stock Comparison:")
for s in ["STB", "CTG", "ACB", "HPG", "FPT", "DIG", "KDH", "GVR", "ANV", "VHC"]:
    match = df[df["symbol"] == s]
    if not match.empty:
        m = match.iloc[0]
        print(f"[{s}] Decision: {m['decision']:<6} | Gate: {m['primary_rejection_gate']:<18} | MoS: {str(m['mos_pct']):<8}% | Price: {m['price']}k | Source: {m['input_source']}")
