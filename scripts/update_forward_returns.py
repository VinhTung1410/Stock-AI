"""
Script to compute and update forward returns (T+1, T+3, T+5, T+10, T+20) for all decision records.
Populates and maintains the decision_forward_returns table in Supabase.
"""

from __future__ import annotations

import logging
import os
import sys
from datetime import datetime, timedelta
from typing import Any

# Add project root to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data_engine import _fetch_history_with_fallback
from db_manager import (
    get_supabase_client,
    update_decision_forward_returns,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


def _is_valid_ticker(sym: str) -> bool:
    """Validate 3-letter uppercase stock ticker."""
    s = sym.upper().strip()
    return (len(s) == 3 and s.isalpha()) or s == "VNINDEX"


def _build_price_series(symbols: set[str], start_date: str, end_date: str) -> dict[str, dict[str, Any]]:
    """Fetch daily price series for valid symbols and VNINDEX.
    
    Returns:
        {symbol: {"dates": [d0, d1, ...], "prices": {date: close_price}}}
    """
    series_map = {}
    valid_syms = sorted([s for s in symbols if _is_valid_ticker(s)])
    if "VNINDEX" not in valid_syms:
        valid_syms.append("VNINDEX")

    total = len(valid_syms)
    logging.info("Starting price history fetch for %d valid tickers...", total)

    for idx, sym in enumerate(valid_syms):
        try:
            df = _fetch_history_with_fallback(sym, start_date=start_date, end_date=end_date)
            if df is not None and not df.empty and "time" in df.columns and "close" in df.columns:
                df["date_str"] = df["time"].astype(str).str[:10]
                sorted_df = df.sort_values("date_str").drop_duplicates(subset=["date_str"])
                dates = list(sorted_df["date_str"])
                prices = {d: float(c) for d, c in zip(dates, sorted_df["close"])}
                series_map[sym] = {"dates": dates, "prices": prices}
                logging.info("[%d/%d] Fetched %s: %d trading sessions", idx + 1, total, sym, len(dates))
            else:
                series_map[sym] = {"dates": [], "prices": {}}
                logging.warning("[%d/%d] Empty history for %s", idx + 1, total, sym)
        except Exception:
            logging.exception("Error fetching price history for %s", sym)
            series_map[sym] = {"dates": [], "prices": {}}

    return series_map


def _calculate_record_payload(
    rec: dict[str, Any],
    series_map: dict[str, dict[str, Any]],
) -> dict[str, Any] | None:
    """Compute forward returns payload for a single decision record."""
    dec_id = rec.get("decision_id")
    sym = rec.get("symbol", "").upper().strip()
    if not dec_id or not sym or sym not in series_map:
        return None

    facts = rec.get("facts", {}) or {}
    snap_price = float(facts.get("snapshot_price") or facts.get("price") or facts.get("market_price") or 0.0)
    if snap_price <= 0.0:
        return None

    raw_date = str(rec.get("created_at") or rec.get("decision_time") or "")[:10]
    sym_series = series_map[sym]
    dates = sym_series["dates"]
    prices = sym_series["prices"]
    if not dates:
        return None

    # Tìm phiên gần nhất vào hoặc sau ngày quyết định
    matching_idx = None
    for i, d in enumerate(dates):
        if d >= raw_date:
            matching_idx = i
            break

    if matching_idx is None:
        return None

    vn_series = series_map.get("VNINDEX", {})
    vn_dates = vn_series.get("dates", [])
    vn_prices = vn_series.get("prices", {})

    horizons = (1, 3, 5, 10, 20)
    ret_horizons = {}
    for h in horizons:
        target_idx = matching_idx + h
        if target_idx < len(dates):
            p_h = prices[dates[target_idx]]
            ret_horizons[f"t{h}_return_pct"] = round(((p_h - snap_price) / snap_price) * 100.0, 3)
        else:
            ret_horizons[f"t{h}_return_pct"] = None

    # VNINDEX returns
    vnindex_t5 = None
    vnindex_t20 = None
    if vn_dates:
        vn_match_idx = None
        for i, d in enumerate(vn_dates):
            if d >= raw_date:
                vn_match_idx = i
                break
        if vn_match_idx is not None:
            vn_p0 = vn_prices.get(vn_dates[vn_match_idx], 0.0)
            if vn_p0 > 0:
                if vn_match_idx + 5 < len(vn_dates):
                    vn_p5 = vn_prices.get(vn_dates[vn_match_idx + 5], 0.0)
                    vnindex_t5 = round(((vn_p5 - vn_p0) / vn_p0) * 100.0, 3)
                if vn_match_idx + 20 < len(vn_dates):
                    vn_p20 = vn_prices.get(vn_dates[vn_match_idx + 20], 0.0)
                    vnindex_t20 = round(((vn_p20 - vn_p0) / vn_p0) * 100.0, 3)

    return {
        "decision_id": dec_id,
        "symbol": sym,
        "snapshot_price": snap_price,
        "t1_return_pct": ret_horizons["t1_return_pct"],
        "t3_return_pct": ret_horizons["t3_return_pct"],
        "t5_return_pct": ret_horizons["t5_return_pct"],
        "t10_return_pct": ret_horizons["t10_return_pct"],
        "t20_return_pct": ret_horizons["t20_return_pct"],
        "vnindex_t5_pct": vnindex_t5,
        "vnindex_t20_pct": vnindex_t20,
    }


def update_all_decision_forward_returns(limit: int = 1000) -> int:
    """Fetch all decision records, calculate T+1..T+20 forward returns, and update DB."""
    client = get_supabase_client()
    if not client:
        logging.error("Supabase client is not available.")
        return 0

    # 1. Fetch decision records
    res = client.table("decision_records").select("*").order("created_at", desc=False).limit(limit).execute()
    records = res.data or []
    if not records:
        logging.info("No decision records found.")
        return 0

    logging.info("Fetched %d decision records from Supabase.", len(records))

    # 2. Extract distinct symbols and determine date range
    symbols = {r["symbol"].upper().strip() for r in records if r.get("symbol")}
    start_date = (datetime.now() - timedelta(days=90)).strftime("%Y-%m-%d")
    end_date = datetime.now().strftime("%Y-%m-%d")

    logging.info("Fetching price series from %s to %s for %d symbols...", start_date, end_date, len(symbols))
    series_map = _build_price_series(symbols, start_date=start_date, end_date=end_date)

    # 3. Check existing rows in decision_forward_returns
    fwd_res = client.table("decision_forward_returns").select("decision_id").limit(5000).execute()
    existing_fwd_ids = {f["decision_id"] for f in (fwd_res.data or []) if f.get("decision_id")}
    logging.info("Existing forward return records count: %d", len(existing_fwd_ids))

    # 4. Process each decision record
    inserts = []
    updates = 0

    for rec in records:
        payload = _calculate_record_payload(rec, series_map)
        if not payload:
            continue

        dec_id = payload["decision_id"]
        if dec_id in existing_fwd_ids:
            if update_decision_forward_returns(dec_id, payload):
                updates += 1
        else:
            inserts.append(payload)

    # 5. Batch insert new records (chunks of 100)
    new_inserts_count = 0
    batch_size = 100
    for i in range(0, len(inserts), batch_size):
        chunk = inserts[i : i + batch_size]
        try:
            ins_res = client.table("decision_forward_returns").insert(chunk).execute()
            if ins_res.data:
                new_inserts_count += len(ins_res.data)
                logging.info("Inserted %d forward return records (batch %d..%d)", len(ins_res.data), i, i + len(chunk))
        except Exception:
            logging.exception("Failed to insert chunk %d..%d into decision_forward_returns", i, i + len(chunk))

    total_processed = new_inserts_count + updates
    logging.info(
        "Forward returns processing complete: %d inserted, %d updated (Total: %d).",
        new_inserts_count,
        updates,
        total_processed,
    )
    return total_processed


if __name__ == "__main__":
    count = update_all_decision_forward_returns()
    print(f"Processed {count} forward return records.")
