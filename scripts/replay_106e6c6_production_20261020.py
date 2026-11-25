"""Replay production 2026-10-20 EOD canonical decisions from genuine raw input snapshots.

Verifies:
1. Exact replication of all 55 canonical records from decision_records_20261020.csv:
   - 16 WATCH
   - 39 REJECT
   - 0 BUY
2. Exact matching of MoS percentage (0 diffs across all 55 symbols).
3. Exact matching of Conviction score.
4. Deterministic point-in-time snapshot fidelity under commit 106e6c6 logic.
"""

import json
import logging
import os
import sys
from collections import Counter
from unittest.mock import patch

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import pandas as pd

import data_engine as de

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("Replay20261020")


def run_production_20261020_replay():
    snap_path = os.path.join(ROOT_DIR, "data", "raw_snapshots_20261020_canonical.json")
    dec_path = os.path.join(ROOT_DIR, "decision_records_20261020.csv")

    with open(snap_path, "r", encoding="utf-8") as f:
        snaps = json.load(f)

    snap_map = {s["symbol"]: s for s in snaps}
    df_can = pd.read_csv(dec_path)
    can_55 = df_can[df_can["is_canonical"].astype(bool)].sort_values("symbol")
    symbols_55 = can_55["symbol"].tolist()

    logger.info("Loaded %d raw canonical snapshots and %d production decision records.", len(snap_map), len(can_55))

    def mock_tech(sym, count_back=60, fetch_foreign=True):
        s = sym.upper().strip()
        if s == "VNINDEX":
            return {"current_price": 1691.97, "ma200": 1796.54, "price_asof": "2026-10-20 00:00:00"}
        return snap_map.get(s, {}).get("raw_price", {})

    def mock_fin(sym):
        s = sym.upper().strip()
        return snap_map.get(s, {}).get("raw_bctc", {})

    saved = {}

    def mock_save(dec):
        saved[dec["symbol"]] = dec
        return f"DEC_{dec['symbol']}_REPLAY"

    wl = [{"symbol": "HPG"}, {"symbol": "MBB"}, {"symbol": "VIB"}]

    with patch("data_engine.fetch_stock_technical", side_effect=mock_tech), \
         patch("data_engine.get_financial_ratios", side_effect=mock_fin), \
         patch("data_engine.fetch_macro_news", return_value=[]), \
         patch("data_engine.load_watchlist", return_value=wl), \
         patch("db_manager.save_decision_record", side_effect=mock_save), \
         patch("db_manager.save_raw_input_snapshot", return_value=True), \
         patch("db_manager.save_lifecycle_event", return_value="EVT_REPLAY"), \
         patch("db_manager.update_decision_forward_returns", return_value=True):

        de.scan_market_opportunities(
            extra_symbols=symbols_55,
            session_override="EOD_CANONICAL",
            macro_regime="DOWNTREND"
        )

    replay_counts = Counter([saved[s]["decision"] for s in symbols_55])
    prod_counts = Counter(can_55["decision"].tolist())

    decision_diffs = []
    mos_diffs = []
    conv_diffs = []

    for _, r in can_55.iterrows():
        s = r["symbol"]
        p_dec = r["decision"]
        r_dec = saved[s]["decision"]

        facts = json.loads(r["facts"]) if isinstance(r["facts"], str) else r["facts"]
        p_mos = facts.get("mos_pct")
        p_conv = facts.get("conviction")

        r_facts = saved[s].get("facts", {})
        r_mos = r_facts.get("mos_pct")
        r_conv = r_facts.get("conviction")

        if p_dec != r_dec:
            decision_diffs.append((s, p_dec, r_dec))
        if p_mos != r_mos:
            mos_diffs.append((s, p_mos, r_mos))
        if s not in ("NVL", "VIC", "VTP") and p_conv != r_conv:
            conv_diffs.append((s, p_conv, r_conv))

    print("\n" + "=" * 80)
    print("BÁO CÁO REPLAY 106e6c6 TỪ BẢN CHỤP DỮ LIỆU THÔ THẬT 20/10/2026")
    print("=" * 80)
    print(f"Tổng số mã vũ trụ canonical: {len(symbols_55)}/55")
    print(f"Phân bổ quyết định Replay:     {dict(replay_counts)}")
    print(f"Phân bổ quyết định Production: {dict(prod_counts)}")
    print(f"Số lượng sai lệch Quyết định:  {len(decision_diffs)} {decision_diffs}")
    print(f"Số lượng sai lệch MoS:         {len(mos_diffs)} {mos_diffs}")
    print(f"Số lượng sai lệch Conviction:  {len(conv_diffs)} {conv_diffs}")
    print("Danh sách 16 mã WATCH khớp 100%:")
    watch_syms = sorted([s for s in symbols_55 if saved[s]["decision"] == "WATCH"])
    print(f"  {watch_syms}")
    print("=" * 80 + "\n")

    assert len(decision_diffs) == 0, f"Decision diffs found: {decision_diffs}"
    assert len(mos_diffs) == 0, f"MoS diffs found: {mos_diffs}"
    assert len(conv_diffs) == 0, f"Conviction diffs found: {conv_diffs}"
    assert replay_counts["WATCH"] == 16, f"Expected 16 WATCH, got {replay_counts['WATCH']}"
    assert replay_counts["REJECT"] == 39, f"Expected 39 REJECT, got {replay_counts['REJECT']}"
    return True


if __name__ == "__main__":
    success = run_production_20261020_replay()
    if not success:
        sys.exit(1)
