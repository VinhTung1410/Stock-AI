import csv
import json
import os
import sys
from unittest.mock import patch

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

import data_engine as de
from logic_manifest import LOGIC_VERSION, SCHEMA_VERSION_CANONICAL, get_build_hash
from tests.test_golden_zero_diff_replay import CANONICAL_55_SYMBOLS


def export_replay_csv(output_path: str = "canonical_replay_55_symbols_20261013.csv"):
    with open("data/last_known_tech.json", "r", encoding="utf-8") as f:
        tech_data = json.load(f)

    def mock_tech(sym, count_back=60, fetch_foreign=True):
        return tech_data.get(sym.upper().strip(), {})

    def mock_fin(sym):
        return {
            "symbol": sym.upper().strip(),
            "period": "2026-Q2",
            "pe": 12.0,
            "pb": 1.5,
            "bvps": 20.0,
            "eps": 2.5,
            "roe": 15.0,
        }

    saved_records = {}

    def mock_save(record):
        saved_records[record["symbol"]] = record
        return f"DEC_EXP_{record['symbol']}"

    with patch("data_engine.fetch_stock_technical", side_effect=mock_tech), \
         patch("data_engine.get_financial_ratios", side_effect=mock_fin), \
         patch("data_engine.fetch_macro_news", return_value=[]), \
         patch("data_engine.load_watchlist", return_value=[]), \
         patch("db_manager.save_decision_record", side_effect=mock_save), \
         patch("db_manager.save_lifecycle_event", return_value="EVT_MOCK"), \
         patch("db_manager.update_decision_forward_returns", return_value=True):
        de.scan_market_opportunities(extra_symbols=CANONICAL_55_SYMBOLS, session_override="CANONICAL_REPLAY_20261013")

    build_hash = get_build_hash()

    fieldnames = [
        "symbol",
        "session",
        "decision",
        "primary_rejection_gate",
        "gates_failed",
        "mos_pct",
        "conviction",
        "price",
        "fair_value",
        "bctc_period",
        "consensus_asof",
        "fin_hash",
        "effective_config_hash",
        "universe_hash",
        "input_source",
        "schema_version",
        "logic_version",
        "build_hash",
    ]

    rows = []
    for sym in CANONICAL_55_SYMBOLS:
        rec = saved_records.get(sym, {})
        facts = rec.get("facts", {})
        gates_failed_list = facts.get("gates_failed", [])
        gates_failed_str = "; ".join(gates_failed_list) if isinstance(gates_failed_list, list) else str(gates_failed_list)

        row = {
            "symbol": sym,
            "session": rec.get("session", "CANONICAL_REPLAY_20261013"),
            "decision": rec.get("decision", "UNKNOWN"),
            "primary_rejection_gate": rec.get("primary_rejection_gate", "NONE"),
            "gates_failed": gates_failed_str,
            "mos_pct": rec.get("mos_pct"),
            "conviction": rec.get("conviction"),
            "price": facts.get("current_price"),
            "fair_value": facts.get("fair_value"),
            "bctc_period": facts.get("bctc_period"),
            "consensus_asof": facts.get("consensus_asof"),
            "fin_hash": facts.get("fin_hash"),
            "effective_config_hash": facts.get("effective_config_hash"),
            "universe_hash": facts.get("universe_hash"),
            "input_source": facts.get("input_source"),
            "schema_version": rec.get("schema_version", SCHEMA_VERSION_CANONICAL),
            "logic_version": rec.get("logic_version", LOGIC_VERSION),
            "build_hash": build_hash,
        }
        rows.append(row)

    with open(output_path, "w", newline="", encoding="utf-8-sig") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Exported {len(rows)} canonical decision records to {output_path}")


if __name__ == "__main__":
    export_replay_csv()
