"""
Script to backfill historical decision records into decision_lifecycle_events table.
Maps existing decisions (BUY / WATCH / REJECT) into event-sourced audit trail (TASK-0085).
"""

from __future__ import annotations

import logging
import os
import sys

# Add project root to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db_manager import (
    EVENT_AI_VETO_EVALUATED,
    get_current_git_sha,
    get_supabase_client,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


def backfill_decision_lifecycle_events(limit: int = 1000, batch_size: int = 100, since_date: str = None) -> int:
    """Read decision_records from Supabase and populate decision_lifecycle_events in batches."""
    client = get_supabase_client()
    if not client:
        logging.error("Supabase client is not available. Check SUPABASE_URL and SUPABASE_KEY.")
        return 0

    # 1. Fetch existing decision_records
    query = client.table("decision_records").select("*").order("created_at", desc=False).limit(limit)
    if since_date:
        query = query.gte("created_at", f"{since_date}T00:00:00+00:00")
    res = query.execute()
    records = res.data or []
    if not records:
        logging.info("No decision records found to backfill.")
        return 0

    logging.info("Found %d decision records. Checking existing lifecycle events...", len(records))

    # 2. Fetch existing correlation_ids in decision_lifecycle_events to avoid duplicate inserts
    evt_res = client.table("decision_lifecycle_events").select("correlation_id").limit(5000).execute()
    existing_corr_ids = {e["correlation_id"] for e in (evt_res.data or []) if e.get("correlation_id")}
    logging.info("Existing lifecycle events count: %d", len(existing_corr_ids))

    # 3. Prepare missing events
    rows_to_insert = []
    current_git_sha = get_current_git_sha()
    for idx, r in enumerate(records):
        dec_id = r.get("decision_id")
        if not dec_id or dec_id in existing_corr_ids:
            continue

        sym = r.get("symbol", "").upper().strip()
        facts = r.get("facts", {}) or {}
        inferences = r.get("inferences", {}) or {}

        price = float(facts.get("snapshot_price") or facts.get("price") or facts.get("market_price") or 0.0)
        dec_type = r.get("decision", "REJECT")
        has_llm = bool(inferences and (inferences.get("pm_decision") or inferences.get("fa_view")))
        if dec_type == "BUY":
            ai_action = "PASS"
            sizing = 1.0
        elif dec_type == "WATCH":
            ai_action = "NOT_EVALUATED"
            sizing = None
        else:
            ai_action = "VETO"
            sizing = 0.0

        rows_to_insert.append({
            "event_id": f"EVT_{sym}_{dec_id}",
            "correlation_id": dec_id,
            "symbol": sym,
            "event_type": EVENT_AI_VETO_EVALUATED,
            "event_data": {
                "source": "LLM" if has_llm else "RULE",
                "decision": dec_type,
                "ai_action": ai_action,
                "sizing_factor": sizing,
                "primary_rejection_gate": r.get("primary_rejection_gate"),
                "rejection_reasons": r.get("rejection_reasons", []),
                "market_price": price,
                "quality_score": facts.get("quality_score"),
                "data_quality": facts.get("data_quality"),
                "pm_decision": inferences.get("pm_decision"),
                "raw_pm_decision": inferences.get("raw_pm_decision"),
            },
            "market_regime": "UNKNOWN",
            "model_version": r.get("model_version") or "v15.0_phase28",
            "git_sha": r.get("git_sha") or current_git_sha,
            "created_at": r.get("created_at") or r.get("decision_time"),
        })
        existing_corr_ids.add(dec_id)

    logging.info("Prepared %d new lifecycle events to insert in batches of %d", len(rows_to_insert), batch_size)

    # 4. Insert in batches
    count_inserted = 0
    for i in range(0, len(rows_to_insert), batch_size):
        chunk = rows_to_insert[i : i + batch_size]
        try:
            ins_res = client.table("decision_lifecycle_events").insert(chunk).execute()
            if ins_res.data:
                count_inserted += len(ins_res.data)
                logging.info("Inserted batch %d..%d (%d items)", i, i + len(chunk), len(ins_res.data))
        except Exception:
            logging.exception("Failed to insert chunk %d..%d", i, i + len(chunk))

    logging.info("Backfill complete. Total inserted in this run: %d", count_inserted)
    return count_inserted


if __name__ == "__main__":
    import argparse
    from datetime import datetime

    parser = argparse.ArgumentParser(description="Backfill decision lifecycle events")
    parser.add_argument("--all", action="store_true", help="Backfill all historical records")
    parser.add_argument("--since", type=str, default=None, help="Filter records since YYYY-MM-DD")
    args = parser.parse_args()

    filter_since = None if args.all else (args.since or datetime.now().strftime("%Y-%m-%d"))
    backfill_decision_lifecycle_events(since_date=filter_since)
