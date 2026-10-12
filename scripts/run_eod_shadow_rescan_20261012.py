"""
Script to execute Method A: EOD Shadow / Re-scored Rescan for Day 2026-10-12.
Evaluates the 55 active stocks from 12/10 using the hardened quant engine,
stores immutable shadow decision records, lifecycle events, and forward returns.
"""

from __future__ import annotations

import logging
import os
import sys
import time
from typing import List

# Set utf-8 stdout
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data_engine import scan_market_opportunities
from db_manager import get_supabase_client

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# 55 real stocks scanned on 2026-10-12 (skipping mock 'GOOD1')
SYMBOLS_55: List[str] = [
    "ACB", "ANV", "BID", "CSV", "CTG", "DCM", "DGC", "DIG", "DPM", "DXG",
    "FMC", "FPT", "GAS", "GIL", "GMD", "GVR", "HAH", "HDB", "HPG", "HSG",
    "IDC", "KBC", "KDH", "MBB", "MSH", "MSN", "MWG", "NKG", "NLG", "NVL",
    "PDR", "PLX", "POW", "PVD", "PVT", "SAB", "SHB", "SSB", "SSI", "STB",
    "STK", "SZC", "TCB", "TNG", "TPB", "VGC", "VHC", "VHM", "VIB", "VIC",
    "VND", "VNM", "VPB", "VRE", "VTP",
]


def run_eod_shadow_rescan(batch_size: int = 5, delay_between_batches: float = 1.0) -> list[dict]:
    """Execute EOD shadow rescan for 55 stocks in batches."""
    client = get_supabase_client()
    existing_eod_symbols = set()
    if client:
        try:
            res = (
                client.table("decision_records")
                .select("symbol")
                .ilike("decision_id", "%20261012_EOD_REPLAY%")
                .execute()
            )
            for r in res.data or []:
                if r.get("symbol"):
                    existing_eod_symbols.add(r["symbol"].upper().strip())
            logging.info("Existing EOD_REPLAY records in DB: %d", len(existing_eod_symbols))
        except Exception as e:
            logging.warning("Could not query existing EOD records: %e", e)

    pending_symbols = [s for s in SYMBOLS_55 if s not in existing_eod_symbols]
    logging.info("Pending symbols to evaluate: %d / %d", len(pending_symbols), len(SYMBOLS_55))

    all_results = []
    # If some were already saved (e.g. STB, CTG, ACB), keep track
    for s in existing_eod_symbols:
        all_results.append({"symbol": s, "status": "ALREADY_SAVED"})

    total_batches = (len(pending_symbols) + batch_size - 1) // batch_size
    for b_idx in range(0, len(pending_symbols), batch_size):
        chunk = pending_symbols[b_idx : b_idx + batch_size]
        curr_batch_num = (b_idx // batch_size) + 1
        logging.info("--> Processing batch [%d/%d]: %s", curr_batch_num, total_batches, chunk)

        try:
            batch_results = scan_market_opportunities(
                extra_symbols=chunk,
                session_override="EOD_REPLAY",
                model_version_override="v15.0_post_fix",
                is_shadow_override=True,
            )
            all_results.extend(batch_results)
            logging.info("Batch [%d/%d] done. Evaluated %d items.", curr_batch_num, total_batches, len(batch_results))
        except Exception:
            logging.exception("Error processing batch %s", chunk)

        if b_idx + batch_size < len(pending_symbols):
            time.sleep(delay_between_batches)

    return all_results


if __name__ == "__main__":
    results = run_eod_shadow_rescan()
    logging.info("EOD Shadow Rescan completed. Total evaluated: %d", len(results))
