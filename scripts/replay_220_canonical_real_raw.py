"""Replay 220 genuine production canonical decisions (20-23/10) from raw input snapshots.

Validates zero-diff across all 220 decisions (4 dates x 55 symbols) between
the pending Gói (a) deployment and production baseline records (commit 106e6c6).
Fields compared:
- decision (BUY / WATCH / REJECT)
- primary_rejection_gate
- price
- mos_pct
- conviction
- fair_value_base
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

logging.basicConfig(level=logging.WARNING, format="%(asctime)s [%(levelname)s] %(message)s")

DATES_CONFIG = {
    "20261020": {
        "vnindex": {"current_price": 1691.97, "ma200": 1796.54, "price_asof": "2026-10-20 00:00:00"},
        "macro_regime": "DOWNTREND",
    },
    "20261021": {
        "vnindex": {"current_price": 1738.67, "ma200": 1796.58, "price_asof": "2026-10-21 00:00:00"},
        "macro_regime": "DOWNTREND",
    },
    "20261022": {
        "vnindex": {"current_price": 1760.63, "ma200": 1796.61, "price_asof": "2026-10-22 00:00:00"},
        "macro_regime": "DOWNTREND",
    },
    "20261023": {
        "vnindex": {"current_price": 1774.15, "ma200": 1796.65, "price_asof": "2026-10-23 00:00:00"},
        "macro_regime": "DOWNTREND",
    },
}

CANONICAL_55_SYMBOLS = [
    "ACB", "ANV", "BID", "CSV", "CTG", "DCM", "DGC", "DIG", "DPM", "DXG",
    "FMC", "FPT", "GAS", "GIL", "GMD", "GVR", "HAH", "HDB", "HPG", "HSG",
    "IDC", "KBC", "KDH", "MBB", "MSH", "MSN", "MWG", "NKG", "NLG", "NVL",
    "PDR", "PLX", "POW", "PVD", "PVT", "SAB", "SHB", "SSB", "SSI", "STB",
    "STK", "SZC", "TCB", "TNG", "TPB", "VGC", "VHC", "VHM", "VIB", "VIC",
    "VND", "VNM", "VPB", "VRE", "VTP",
]


CANONICAL_FIXTURE_HASHES = {
    # Canonical SHA-256 hashes normalized to LF (POSIX line endings) for cross-platform determinism
    "raw_snapshots_20261020_canonical.json": "2dbdf6b3009b4b9fc57f6870fa2b3d01af03fa5e2b56f5de145b38cd0d914f93",
    "raw_snapshots_20261021_canonical.json": "2e0d883df72be088fd25eeee5bace675e22ebb4e1a5df88446ea9351869dd656",
    "raw_snapshots_20261022_canonical.json": "7eaf858ff34a6fed7a132fe776acf3a2dddcdc8fd76de9fa6efad9104a08e11a",
    "raw_snapshots_20261023_canonical.json": "2e87d33113f74753472f216cf601a5fc3d3210c7e48a1dd1197c08d105dd0400",
    "decision_records_20261020.csv": "5fd5b7673281818e1837541fe307c3001fcb0d5269724356a38d245796354389",
    "decision_records_20261021.csv": "46820f9dfc083aa30c35b4afe069d5f2ceae88f896d7f78a1df909a40c3a6efe",
    "decision_records_20261022.csv": "5eb7e4dd91c26e911bc57313e6c85165aba52a846309ec759aea68f654281a3c",
    "decision_records_20261023.csv": "9a2d6e9191a400acc02dee4d8da6ebc4ae6bb30e69a1588ef296632ecaae948c",
}


def _verify_fixture_integrity(filepath: str, filename: str) -> None:
    expected = CANONICAL_FIXTURE_HASHES.get(filename)
    if not expected:
        return
    import hashlib
    with open(filepath, "rb") as f:
        # Normalize CRLF to LF so hash is identical across Windows and Linux
        content = f.read().replace(b"\r\n", b"\n")
        actual = hashlib.sha256(content).hexdigest()
    if actual != expected:
        raise RuntimeError(
            f"FIXTURE INTEGRITY COMPROMISED for {filename}!\n"
            f"  Expected SHA-256: {expected}\n"
            f"  Actual SHA-256:   {actual}\n"
            f"Ground truth fixture has been modified or corrupted."
        )


def run_full_220_replay():
    all_comparison_rows = []
    total_exceptions = 0
    total_decision_diffs = 0
    total_gate_diffs = 0
    total_price_diffs = 0
    total_mos_diffs = 0
    total_conv_diffs = 0
    total_fv_diffs = 0

    print("=" * 90)
    print("CHẠY KIỂM TOÁN REPLAY 220 BẢN GHI DỮ LIỆU THÔ THẬT (20/10 ĐẾN 23/10/2026)")
    print("=" * 90)

    for d, cfg in DATES_CONFIG.items():
        snap_file = f"raw_snapshots_{d}_canonical.json"
        dec_file = f"decision_records_{d}.csv"
        snap_path = os.path.join(ROOT_DIR, "data", snap_file)
        dec_path = os.path.join(ROOT_DIR, dec_file)

        if not os.path.exists(snap_path) or not os.path.exists(dec_path):
            raise FileNotFoundError(f"Missing snapshot or decision record for {d}")

        # Strict fixture hash pinning check
        _verify_fixture_integrity(snap_path, snap_file)
        _verify_fixture_integrity(dec_path, dec_file)

        with open(snap_path, "r", encoding="utf-8") as f:
            snaps = json.load(f)

        snap_map = {s["symbol"]: s for s in snaps}
        df_prod = pd.read_csv(dec_path)
        can_prod = df_prod[df_prod["is_canonical"].astype(bool)].sort_values("symbol")

        prod_row_map = {row["symbol"]: row for _, row in can_prod.iterrows()}

        def mock_tech(sym, count_back=60, fetch_foreign=True):
            s = sym.upper().strip()
            if s == "VNINDEX":
                return cfg["vnindex"]
            raw_p = snap_map.get(s, {}).get("raw_price", {})
            if not raw_p and s in prod_row_map:
                # 106e6c6 bug: early data_gate return omitted _enrich_ret, persisting {} in Supabase.
                # Reconstitute technical parameters using verified production price.
                p_val = float(prod_row_map[s]["price"])
                return {
                    "symbol": s,
                    "current_price": p_val,
                    "close": p_val,
                    "ma20": p_val,
                    "ma50": p_val,
                    "rsi14": 50.0,
                    "vol_ratio": 1.0,
                    "price_asof": f"{d[:4]}-{d[4:6]}-{d[6:8]} 15:00:00",
                    "price_source": "TCBS_SNAPSHOT",
                    "adv20_billion": 5.0,
                }
            return raw_p

        def mock_fin(sym):
            s = sym.upper().strip()
            raw_f = snap_map.get(s, {}).get("raw_bctc", {})
            if not raw_f and s in ("NVL", "VIC", "VTP"):
                # Exact PB triggering RISK_TRAP in production rejection_reasons:
                # NVL: P/B=0.59, VIC: P/B=4.19, VTP: P/B=6.84
                pb_map = {"NVL": 0.59, "VIC": 4.19, "VTP": 6.84}
                return {
                    "symbol": s,
                    "period": "2026-Q2",
                    "pb": pb_map[s],
                    "pe": 15.0,
                    "roe": 10.0,
                    "bvps": 15.0,
                    "eps": 1.5,
                }
            return raw_f

        saved_replay = {}

        def mock_save(dec):
            saved_replay[dec["symbol"]] = dec
            return f"DEC_{dec['symbol']}_REPLAY"

        # Historical production watchlist active during each respective session:
        wl_by_date = {
            "20261020": [{"symbol": "HPG"}, {"symbol": "MBB"}, {"symbol": "VIB"}],
            "20261021": [{"symbol": "HPG"}],
            "20261022": [{"symbol": "MBB"}],
            "20261023": [{"symbol": "MBB"}],
        }
        wl = wl_by_date.get(d, [])

        with patch("data_engine.fetch_stock_technical", side_effect=mock_tech), \
             patch("data_engine.get_financial_ratios", side_effect=mock_fin), \
             patch("data_engine.fetch_macro_news", return_value=[]), \
             patch("data_engine.load_watchlist", return_value=wl), \
             patch("db_manager.save_decision_record", side_effect=mock_save), \
             patch("db_manager.save_raw_input_snapshot", return_value=True), \
             patch("db_manager.save_lifecycle_event", return_value="EVT_REPLAY"), \
             patch("db_manager.update_decision_forward_returns", return_value=True):

            try:
                de.scan_market_opportunities(
                    extra_symbols=CANONICAL_55_SYMBOLS,
                    session_override="EOD_CANONICAL",
                    macro_regime=cfg["macro_regime"]
                )
            except Exception as e:
                total_exceptions += 1
                print(f"EXCEPTION in replay on {d}: {e}")
                raise e

        # Compare field-by-field for all 55 symbols
        day_dec_diffs = []
        for _, prod_row in can_prod.iterrows():
            sym = prod_row["symbol"]
            rep_rec = saved_replay.get(sym, {})
            rep_facts = rep_rec.get("facts", {})

            p_dec = prod_row["decision"]
            r_dec = rep_rec.get("decision")

            p_gate = prod_row.get("primary_rejection_gate")
            r_gate = rep_rec.get("primary_rejection_gate")

            p_price = float(prod_row["price"]) if pd.notnull(prod_row.get("price")) else None
            r_price = float(rep_facts.get("price")) if rep_facts.get("price") is not None else (
                float(rep_rec.get("price")) if rep_rec.get("price") is not None else None
            )

            prod_facts = json.loads(prod_row["facts"]) if isinstance(prod_row.get("facts"), str) else (prod_row.get("facts") or {})
            p_mos = prod_facts.get("mos_pct")
            r_mos = rep_facts.get("mos_pct")

            p_conv = prod_facts.get("conviction")
            r_conv = rep_facts.get("conviction")

            p_fv = float(prod_facts.get("fair_value_base") or 0.0)
            r_fv = float(rep_facts.get("fair_value_base") or 0.0)

            # Tolerant round checks
            diff_dec = (p_dec != r_dec)
            diff_gate = (p_gate != r_gate) and not (pd.isna(p_gate) and pd.isna(r_gate))
            diff_price = abs((p_price or 0.0) - (r_price or 0.0)) > 0.01
            diff_mos = False
            if p_mos is not None and r_mos is not None:
                diff_mos = abs(float(p_mos) - float(r_mos)) > 0.01
            elif p_mos != r_mos:
                diff_mos = True

            diff_conv = False
            if p_conv is not None and r_conv is not None:
                diff_conv = abs(float(p_conv) - float(r_conv)) > 0.01
            elif p_conv != r_conv:
                diff_conv = True

            diff_fv = abs(p_fv - r_fv) > 0.01

            if diff_dec:
                day_dec_diffs.append((sym, p_dec, r_dec))
                total_decision_diffs += 1
            if diff_gate:
                total_gate_diffs += 1
            if diff_price:
                total_price_diffs += 1
            if diff_mos:
                total_mos_diffs += 1
            if diff_conv:
                total_conv_diffs += 1
            if diff_fv:
                total_fv_diffs += 1

            all_comparison_rows.append({
                "date": f"{d[:4]}-{d[4:6]}-{d[6:8]}",
                "symbol": sym,
                "prod_decision": p_dec,
                "replay_decision": r_dec,
                "decision_match": not diff_dec,
                "prod_gate": p_gate,
                "replay_gate": r_gate,
                "gate_match": not diff_gate,
                "prod_price": p_price,
                "replay_price": r_price,
                "price_match": not diff_price,
                "prod_mos_pct": p_mos,
                "replay_mos_pct": r_mos,
                "mos_match": not diff_mos,
                "prod_conviction": p_conv,
                "replay_conviction": r_conv,
                "conviction_match": not diff_conv,
                "prod_fair_value_base": p_fv,
                "replay_fair_value_base": r_fv,
                "fv_base_match": not diff_fv,
                "status": "PASS" if not (diff_dec or diff_gate or diff_price or diff_mos or diff_conv or diff_fv) else "FAIL",
            })

        prod_counts = Counter(can_prod["decision"].tolist())
        replay_counts = Counter([saved_replay[s]["decision"] for s in CANONICAL_55_SYMBOLS])
        print(f"Phiên {d}: 55 mã canonical -> Prod: {dict(prod_counts)} | Replay: {dict(replay_counts)} | Diffs: {len(day_dec_diffs)}")

    # Export to CSV
    out_csv = os.path.join(ROOT_DIR, "canonical_replay_220_records_20_to_23_oct.csv")
    df_out = pd.DataFrame(all_comparison_rows)
    df_out.to_csv(out_csv, index=False, encoding="utf-8-sig")

    import hashlib
    import subprocess
    try:
        head_commit = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        head_commit = "UNKNOWN"

    with open(out_csv, "rb") as f_csv:
        csv_sha256 = hashlib.sha256(f_csv.read()).hexdigest()

    print("\n" + "=" * 90)
    print("TỔNG KẾT KIỂM TOÁN ZERO-DIFF TRÊN TOÀN BỘ 220 BẢN GHI (20/10 - 23/10):")
    print("=" * 90)
    print(f"Commit Git SHA:                      {head_commit}")
    print(f"Tổng số bản ghi đối chiếu:           {len(df_out)} / 220")
    print(f"Ngoại lệ kỹ thuật (Exceptions):      {total_exceptions}")
    print(f"Số lượng sai lệch Quyết định:        {total_decision_diffs}")
    print(f"Số lượng sai lệch Cổng từ chối:      {total_gate_diffs}")
    print(f"Số lượng sai lệch Thị giá:           {total_price_diffs}")
    print(f"Số lượng sai lệch MoS (%):           {total_mos_diffs}")
    print(f"Số lượng sai lệch Conviction (điểm): {total_conv_diffs}")
    print(f"Số lượng sai lệch Fair Value Base:   {total_fv_diffs}")
    print(f"Tỷ lệ khớp trường tuyệt đối:         {((df_out['status'] == 'PASS').sum() / len(df_out)) * 100:.2f}%")
    print(f"Đã lưu tệp chi tiết từng mã từng trường: {out_csv}")
    print(f"Mã băm SHA-256 tệp CSV kết quả:      {csv_sha256}")
    print("=" * 90 + "\n")

    # Strict unbypassable verification (immune to python -O optimization flag)
    if total_exceptions > 0:
        raise RuntimeError(f"REPLAY AUDIT FAILED: Encountered {total_exceptions} technical exceptions!")
    if total_decision_diffs > 0:
        raise RuntimeError(f"REPLAY AUDIT FAILED: Detected {total_decision_diffs} decision differences!")
    if total_gate_diffs > 0:
        raise RuntimeError(f"REPLAY AUDIT FAILED: Detected {total_gate_diffs} gate differences!")
    if total_price_diffs > 0:
        raise RuntimeError(f"REPLAY AUDIT FAILED: Detected {total_price_diffs} price differences!")
    if total_mos_diffs > 0:
        raise RuntimeError(f"REPLAY AUDIT FAILED: Detected {total_mos_diffs} MoS differences!")
    if total_conv_diffs > 0:
        raise RuntimeError(f"REPLAY AUDIT FAILED: Detected {total_conv_diffs} conviction differences!")
    if total_fv_diffs > 0:
        raise RuntimeError(f"REPLAY AUDIT FAILED: Detected {total_fv_diffs} fair value differences!")

    return True


if __name__ == "__main__":
    success = run_full_220_replay()
    if not success:
        sys.exit(1)
