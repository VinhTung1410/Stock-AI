"""Unified script to export decision_records and decision_lifecycle_events to CSV.

Easily customize the target date directly via the TARGET_DATE variable below,
or optionally pass the date via CLI argument:
    python scripts/export_today_csv.py
    python scripts/export_today_csv.py 2026-10-16
    python scripts/export_today_csv.py --date 2026-10-16
"""

import json
import logging
import os
import sys
from datetime import datetime, timedelta

import pandas as pd

# ==============================================================================
# CẤU HÌNH NGÀY CẦN XUẤT (Bạn có thể tự chỉnh sửa ngày trực tiếp tại đây)
# ==============================================================================
TARGET_DATE = "2026-10-19"  # Định dạng: YYYY-MM-DD (VD: 2026-10-16, 2026-10-19...)
# ==============================================================================

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db_manager import get_supabase_client

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
LOGGER = logging.getLogger(__name__)

# Constants to satisfy SonarCloud S1192
DECISION_COL = "decision"
LOGIC_VERSION_COL = "logic_version"
SYMBOL_COL = "symbol"


def get_target_date() -> str:
    """Retrieve target date from CLI arguments if provided, else fallback to TARGET_DATE constant."""
    if len(sys.argv) > 1 and not sys.argv[1].startswith("-"):
        return sys.argv[1].strip()
    for i, arg in enumerate(sys.argv):
        if arg in ("--date", "-d") and i + 1 < len(sys.argv):
            return sys.argv[i + 1].strip()
    return TARGET_DATE


def compute_utc_range_for_vn_date(target_date_str: str) -> tuple[str, str]:
    """
    Convert Vietnam date (YYYY-MM-DD, UTC+7) to UTC timestamp boundary.
    Start: 00:00:00 VN time -> Previous day 17:00:00 UTC
    End:   24:00:00 VN time -> Target day 17:00:00 UTC
    """
    target_dt = datetime.strptime(target_date_str, "%Y-%m-%d")
    prev_dt = target_dt - timedelta(days=1)
    start_utc = f"{prev_dt.strftime('%Y-%m-%d')}T17:00:00+00:00"
    end_utc = f"{target_dt.strftime('%Y-%m-%d')}T17:00:00+00:00"
    return start_utc, end_utc


def _format_reasons(reasons_raw: object) -> str:
    """Format list or raw reasons into string."""
    if isinstance(reasons_raw, list):
        return " | ".join(str(x) for x in reasons_raw)
    return str(reasons_raw or "")


def _format_gates(gates_raw: object) -> str:
    """Format list of failed gates into comma-separated string."""
    if isinstance(gates_raw, list):
        return ", ".join(gates_raw)
    return str(gates_raw or "")


def _determine_monitor_reason(r: dict, facts: dict) -> str:
    """Determine explicit reason for monitoring/scanning this symbol."""
    if facts.get("monitor_reason"):
        return str(facts["monitor_reason"])
    if facts.get("is_canonical"):
        return "RECONSTRUCTED_CANONICAL_EOD"
    sym = str(r.get(SYMBOL_COL, "")).upper().strip()
    session = str(r.get("session", "")).upper()
    if sym == "HPG":
        return "RECONSTRUCTED_MANUAL_SEED"
    if sym in ("MBB", "VIB"):
        return "RECONSTRUCTED_AUTO_WATCHLIST_ATO"
    if session in ("MORNING", "NOON", "AFTERNOON"):
        return "RECONSTRUCTED_WATCHLIST_INTRADAY"
    return "RECONSTRUCTED_SCHEDULED_SCAN"


def export_decision_records(client: object, target_date: str, start_utc: str, end_utc: str) -> pd.DataFrame:
    """Fetch decision_records for given date range and save to CSV."""
    LOGGER.info("Fetching decision_records for %s (UTC: %s -> %s)...", target_date, start_utc, end_utc)
    res = (
        client.table("decision_records")
        .select("*")
        .gte("created_at", start_utc)
        .lt("created_at", end_utc)
        .order("created_at", desc=False)
        .limit(5000)
        .execute()
    )
    records = res.data or []
    LOGGER.info("Retrieved %d decision_records.", len(records))

    rows = []
    for r in records:
        facts = r.get("facts") or {}
        reasons_str = _format_reasons(r.get("rejection_reasons"))
        gates_failed_str = _format_gates(facts.get("gates_failed"))

        rows.append({
            "id": r.get("id"),
            "decision_id": r.get("decision_id"),
            "symbol": r.get(SYMBOL_COL),
            "decision_time": r.get("decision_time"),
            "session": r.get("session"),
            "decision": r.get(DECISION_COL),
            "primary_rejection_gate": r.get("primary_rejection_gate"),
            "price": facts.get("price"),
            "fair_value_base": facts.get("fair_value_base"),
            "mos_pct": facts.get("mos_pct"),
            "target_pb": facts.get("target_pb"),
            "target_pb_gordon": facts.get("target_pb_gordon"),
            "target_pb_clamped": facts.get("target_pb_clamped"),
            "effective_pb": facts.get("effective_pb"),
            "bvps_for_fv": facts.get("bvps_for_fv"),
            "bvps_provider": facts.get("bvps_provider"),
            "conviction": facts.get("conviction"),
            "conviction_valuation": facts.get("conviction_valuation"),
            "conviction_technical": facts.get("conviction_technical"),
            "conviction_catalyst": facts.get("conviction_catalyst"),
            "conviction_liquidity": facts.get("conviction_liquidity"),
            "conviction_foreign_penalty": facts.get("conviction_foreign_penalty"),
            "val_confidence": facts.get("val_confidence"),
            "input_source": facts.get("input_source"),
            "gates_failed": gates_failed_str,
            "informative": facts.get("informative"),
            "price_source": facts.get("price_source"),
            "price_asof": facts.get("price_asof"),
            "fv_price_ratio": facts.get("fv_price_ratio"),
            "mos_review_flag": facts.get("mos_review_flag"),
            "is_canonical": facts.get("is_canonical"),
            "monitor_reason": _determine_monitor_reason(r, facts),
            "rejection_reasons": reasons_str,
            "facts": json.dumps(facts, ensure_ascii=False) if facts else "",
            "inferences": json.dumps(r.get("inferences"), ensure_ascii=False) if r.get("inferences") else "",
            "opinions": json.dumps(r.get("opinions"), ensure_ascii=False) if r.get("opinions") else "",
            "counterfactual": json.dumps(r.get("counterfactual"), ensure_ascii=False) if r.get("counterfactual") else "",
            "logic_version": r.get(LOGIC_VERSION_COL) or facts.get(LOGIC_VERSION_COL),
            "model_version": r.get("model_version"),
            "git_sha": r.get("git_sha"),
            "created_at": r.get("created_at"),
        })

    df = pd.DataFrame(rows)
    # Bỏ các cột hoàn toàn rỗng đối với bản phát hành đóng băng (106e6c6) để tránh 203/203 hàng rỗng
    empty_unreleased_cols = [
        "target_pb_gordon",
        "target_pb_clamped",
        "effective_pb",
        "bvps_for_fv",
        "bvps_provider",
        "val_confidence",
        "conviction_valuation",
        "conviction_technical",
        "conviction_catalyst",
        "conviction_liquidity",
        "conviction_foreign_penalty",
    ]
    cols_to_drop = [c for c in empty_unreleased_cols if c in df.columns and df[c].isna().all()]
    if cols_to_drop:
        df = df.drop(columns=cols_to_drop)
        LOGGER.info("Dropped %d all-null unreleased columns: %s", len(cols_to_drop), cols_to_drop)

    csv_path = f"decision_records_{target_date.replace('-', '')}.csv"
    df.to_csv(csv_path, index=False, encoding="utf-8-sig")
    LOGGER.info("Successfully saved %d records to %s", len(df), csv_path)
    return df


def export_lifecycle_events(client: object, target_date: str, start_utc: str, end_utc: str) -> pd.DataFrame:
    """Fetch decision_lifecycle_events for given date range and save to CSV."""
    LOGGER.info("Fetching decision_lifecycle_events for %s...", target_date)
    evt_res = (
        client.table("decision_lifecycle_events")
        .select("*")
        .gte("created_at", start_utc)
        .lt("created_at", end_utc)
        .order("created_at", desc=False)
        .limit(5000)
        .execute()
    )
    evt_records = evt_res.data or []
    LOGGER.info("Retrieved %d decision_lifecycle_events.", len(evt_records))

    evt_rows = []
    for e in evt_records:
        edata = e.get("event_data") or {}
        reasons_str = _format_reasons(edata.get("reasons"))

        evt_rows.append({
            "id": e.get("id"),
            "event_id": e.get("event_id"),
            "correlation_id": e.get("correlation_id"),
            "symbol": e.get(SYMBOL_COL),
            "event_type": e.get("event_type"),
            "source": edata.get("source"),
            "decision": edata.get(DECISION_COL),
            "ai_action": edata.get("ai_action"),
            "sizing_factor": edata.get("sizing_factor"),
            "market_price": edata.get("price"),
            "primary_rejection_gate": edata.get("gate"),
            "rejection_reasons": reasons_str,
            "market_regime": e.get("market_regime"),
            "logic_version": e.get(LOGIC_VERSION_COL) or edata.get(LOGIC_VERSION_COL),
            "model_version": e.get("model_version"),
            "git_sha": e.get("git_sha"),
            "created_at": e.get("created_at"),
            "event_data": json.dumps(edata, ensure_ascii=False) if edata else "",
        })

    df_evt = pd.DataFrame(evt_rows)
    evt_csv_path = f"lifecycle_events_{target_date.replace('-', '')}.csv"
    df_evt.to_csv(evt_csv_path, index=False, encoding="utf-8-sig")
    LOGGER.info("Successfully saved %d events to %s", len(df_evt), evt_csv_path)
    return df_evt


def print_summary(target_date: str, df_dec: pd.DataFrame, df_evt: pd.DataFrame) -> None:
    """Print telemetry and distribution summary."""
    print(f"\n--- SUMMARY {target_date} ---")
    print(f"Decision records count: {len(df_dec)}")
    if not df_dec.empty:
        print("\nDecision distribution:\n", df_dec[DECISION_COL].value_counts().to_string())
        print("\nTop Rejection Gates:\n", df_dec["primary_rejection_gate"].value_counts().head(10).to_string())
        print("\nUnique symbols count:", df_dec[SYMBOL_COL].nunique())
        print("\nLogic versions:\n", df_dec[LOGIC_VERSION_COL].value_counts().to_string())
        print("\nGit SHAs:\n", df_dec["git_sha"].value_counts().to_string())
    print(f"\nLifecycle events total count: {len(df_evt)}")
    if not df_evt.empty:
        # Quy tắc lọc dev leak: git_sha c170a71..., symbol OVERHEATED, hoặc correlation_id 'True'
        dev_leak_mask = (
            df_evt["git_sha"].fillna("").str.startswith("c170a71")
            | (df_evt[SYMBOL_COL] == "OVERHEATED")
            | (df_evt["correlation_id"].astype(str).str.strip().str.lower() == "true")
        )
        df_prod_evt = df_evt[(~dev_leak_mask) & (df_evt["event_type"] != "AUDIT_CORRECTION")]
        dev_leak_count = dev_leak_mask.sum()
        corr_count = (df_evt["event_type"] == "AUDIT_CORRECTION").sum()
        if dev_leak_count > 0:
            print(f"\n⚠️ DEV LEAKS DETECTED (git_sha=c170a71... | symbol=OVERHEATED | correlation_id='True'): {dev_leak_count} rows (INVALIDATED by {corr_count} audit correction records)")
        print(f"\nCanonical Production Lifecycle Events: {len(df_prod_evt)}")
        print("\nEvent type distribution (Production Canonical):\n", df_prod_evt["event_type"].value_counts().to_string())
        print("\nEvents Logic versions:\n", df_prod_evt[LOGIC_VERSION_COL].value_counts().to_string())
        print("\nGit SHAs (Events):\n", df_evt["git_sha"].value_counts().to_string())


def main() -> None:
    """Main execution function to export both tables."""
    target_date = get_target_date()
    client = get_supabase_client()
    if not client:
        LOGGER.error("Supabase client not available.")
        sys.exit(1)

    start_utc, end_utc = compute_utc_range_for_vn_date(target_date)
    df_dec = export_decision_records(client, target_date, start_utc, end_utc)
    df_evt = export_lifecycle_events(client, target_date, start_utc, end_utc)
    print_summary(target_date, df_dec, df_evt)


if __name__ == "__main__":
    main()
