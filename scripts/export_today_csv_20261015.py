import json
import os
import sys

import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db_manager import get_supabase_client


def export_today_data():
    client = get_supabase_client()
    if not client:
        print("Error: Supabase client not available.")
        sys.exit(1)

    # 1. Export decision_records for 2026-10-15
    print("Fetching decision_records for 2026-10-15...")
    res = (
        client.table("decision_records")
        .select("*")
        .gte("created_at", "2026-10-14T17:00:00+00:00")
        .lt("created_at", "2026-10-15T17:00:00+00:00")
        .order("created_at", desc=False)
        .limit(2000)
        .execute()
    )
    records = res.data or []
    print(f"Retrieved {len(records)} decision_records.")

    rows = []
    for r in records:
        facts = r.get("facts") or {}
        reasons = r.get("rejection_reasons") or []
        if isinstance(reasons, list):
            reasons_str = " | ".join(str(x) for x in reasons)
        else:
            reasons_str = str(reasons or "")

        gates_failed_raw = facts.get("gates_failed", [])
        gates_failed_str = (
            ", ".join(gates_failed_raw)
            if isinstance(gates_failed_raw, list)
            else str(gates_failed_raw or "")
        )

        rows.append({
            "id": r.get("id"),
            "decision_id": r.get("decision_id"),
            "symbol": r.get("symbol"),
            "decision_time": r.get("decision_time"),
            "session": r.get("session"),
            "decision": r.get("decision"),
            "primary_rejection_gate": r.get("primary_rejection_gate"),
            "price": facts.get("price"),
            "mos_pct": facts.get("mos_pct"),
            "conviction": facts.get("conviction"),
            "input_source": facts.get("input_source"),
            "gates_failed": gates_failed_str,
            "informative": facts.get("informative"),
            "price_source": facts.get("price_source"),
            "price_asof": facts.get("price_asof"),
            "fv_price_ratio": facts.get("fv_price_ratio"),
            "mos_review_flag": facts.get("mos_review_flag"),
            "is_canonical": facts.get("is_canonical"),
            "rejection_reasons": reasons_str,
            "facts": json.dumps(facts, ensure_ascii=False) if facts else "",
            "inferences": json.dumps(r.get("inferences"), ensure_ascii=False) if r.get("inferences") else "",
            "opinions": json.dumps(r.get("opinions"), ensure_ascii=False) if r.get("opinions") else "",
            "counterfactual": json.dumps(r.get("counterfactual"), ensure_ascii=False) if r.get("counterfactual") else "",
            "logic_version": r.get("logic_version") or facts.get("logic_version"),
            "model_version": r.get("model_version"),
            "git_sha": r.get("git_sha"),
            "created_at": r.get("created_at"),
        })

    df_dec = pd.DataFrame(rows)
    dec_csv_path = "decision_records_20261015.csv"
    df_dec.to_csv(dec_csv_path, index=False, encoding="utf-8-sig")
    print(f"Successfully saved {len(df_dec)} records to {dec_csv_path}")

    # 2. Export decision_lifecycle_events for 2026-10-15
    print("\nFetching decision_lifecycle_events for 2026-10-15...")
    evt_res = (
        client.table("decision_lifecycle_events")
        .select("*")
        .gte("created_at", "2026-10-14T17:00:00+00:00")
        .lt("created_at", "2026-10-15T17:00:00+00:00")
        .order("created_at", desc=False)
        .limit(2000)
        .execute()
    )
    evt_records = evt_res.data or []
    print(f"Retrieved {len(evt_records)} decision_lifecycle_events.")

    evt_rows = []
    for e in evt_records:
        edata = e.get("event_data") or {}
        reasons = edata.get("reasons", [])
        if isinstance(reasons, list):
            reasons_str = " | ".join(str(x) for x in reasons)
        else:
            reasons_str = str(reasons or "")

        evt_rows.append({
            "id": e.get("id"),
            "event_id": e.get("event_id"),
            "correlation_id": e.get("correlation_id"),
            "symbol": e.get("symbol"),
            "event_type": e.get("event_type"),
            "source": edata.get("source"),
            "decision": edata.get("decision"),
            "ai_action": edata.get("ai_action"),
            "sizing_factor": edata.get("sizing_factor"),
            "market_price": edata.get("price"),
            "primary_rejection_gate": edata.get("gate"),
            "rejection_reasons": reasons_str,
            "market_regime": e.get("market_regime"),
            "logic_version": e.get("logic_version") or edata.get("logic_version"),
            "model_version": e.get("model_version"),
            "git_sha": e.get("git_sha"),
            "created_at": e.get("created_at"),
            "event_data": json.dumps(edata, ensure_ascii=False) if edata else "",
        })

    df_evt = pd.DataFrame(evt_rows)
    evt_csv_path = "lifecycle_events_20261015.csv"
    df_evt.to_csv(evt_csv_path, index=False, encoding="utf-8-sig")
    print(f"Successfully saved {len(df_evt)} events to {evt_csv_path}")

    # Summary
    print("\n--- SUMMARY 2026-10-15 ---")
    print(f"Decision records count: {len(df_dec)}")
    if not df_dec.empty:
        print("\nDecision distribution:\n", df_dec["decision"].value_counts().to_string())
        print("\nTop Rejection Gates:\n", df_dec["primary_rejection_gate"].value_counts().head(10).to_string())
        print("\nUnique symbols count:", df_dec["symbol"].nunique())
        print("\nLogic versions:\n", df_dec["logic_version"].value_counts().to_string())
        print("\nGit SHAs:\n", df_dec["git_sha"].value_counts().to_string())
    print(f"\nLifecycle events count: {len(df_evt)}")
    if not df_evt.empty:
        print("\nEvent type distribution:\n", df_evt["event_type"].value_counts().to_string())
        print("\nEvents Logic versions:\n", df_evt["logic_version"].value_counts().to_string())


if __name__ == "__main__":
    export_today_data()
