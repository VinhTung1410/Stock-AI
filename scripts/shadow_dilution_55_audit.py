"""Shadow Dilution Audit on all 55 Canonical Stocks.

Runs detect_and_adjust_post_bctc_dilution side-by-side with production baseline.
Computes:
- Original vs Adjusted BVPS & EPS
- Cumulative Dilution Factor
- Original vs Shadow Fair Value & MoS %
- Recalculated Conviction Score (reflecting MoS Pillar 1 valuation shifts)
- Decision Impact (Whether WATCH drops to REJECT when MoS < 8% and Conviction < 55)
"""

import argparse
import json
import os
import sys

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import pandas as pd

from data_engine import detect_and_adjust_post_bctc_dilution


def get_valuation_pillar_points(mos_pct: float | None) -> float:
    """Calculate Pillar 1 (Valuation & MoS) points on 40-pt institutional scale."""
    if mos_pct is None:
        return 0.0
    if mos_pct >= 25.0:
        return 40.0
    if mos_pct >= 15.0:
        return 30.0
    if mos_pct >= 8.0:
        return 20.0
    if mos_pct >= 0.0:
        return 10.0
    return 0.0


def run_audit(target_date: str = "20261023"):
    dec_file = os.path.join(ROOT_DIR, f"decision_records_{target_date}.csv")
    if not os.path.exists(dec_file):
        raise FileNotFoundError(f"Decision records file not found: {dec_file}")

    dec_df = pd.read_csv(dec_file)
    canonical_df = dec_df[dec_df["is_canonical"].astype(bool)] if "is_canonical" in dec_df.columns else dec_df

    # Load corporate events
    ca_path = os.path.join(ROOT_DIR, "scratch", "corporate_events_with_prices.json")
    if os.path.exists(ca_path):
        with open(ca_path, "r", encoding="utf-8") as f:
            ca_audits = json.load(f)
        ca_map = {item["symbol"]: item["events"] for item in ca_audits}
    else:
        ca_map = {}

    results = []

    for _, r in canonical_df.iterrows():
        sym = r["symbol"]
        facts = json.loads(r["facts"]) if isinstance(r["facts"], str) else (r["facts"] if isinstance(r["facts"], dict) else {})
        
        orig_dec = r["decision"]
        price = float(r["price"]) if pd.notna(r["price"]) else 0.0
        orig_mos = float(r["mos_pct"]) if pd.notna(r["mos_pct"]) else None
        orig_conv = float(r["conviction"]) if pd.notna(r["conviction"]) else 0.0
        
        # Primary FV field is fair_value_base
        orig_fv = r.get("fair_value_base")
        if pd.isna(orig_fv) or orig_fv is None:
            orig_fv = facts.get("fair_value_base") or facts.get("fair_value")
        orig_fv = float(orig_fv) if (orig_fv is not None and pd.notna(orig_fv)) else None

        orig_bvps = facts.get("bvps_used") or facts.get("bvps_for_fv")
        orig_eps = facts.get("eps_used")
        period = facts.get("bctc_period") or "2026-Q2"
        sector = facts.get("sector") or ""

        events = ca_map.get(sym, [])
        formatted_ca = []
        for ev in events:
            if ev.get("ratio", 0) > 0 and ev.get("ex_date"):
                formatted_ca.append({
                    "ex_date": ev["ex_date"],
                    "event_code": ev.get("event_code", "ISS"),
                    "exercise_ratio": ev["ratio"]
                })

        dil_res = detect_and_adjust_post_bctc_dilution(
            symbol=sym,
            bctc_period=period,
            bvps=orig_bvps,
            eps=orig_eps,
            corporate_actions=formatted_ca
        )

        factor = dil_res["cumulative_dilution_factor"]
        adj_bvps = dil_res["adjusted_bvps"]
        adj_eps = dil_res["adjusted_eps"]
        is_stale = dil_res["per_share_stale"]

        # Fair Value scales proportionally with per-share metrics (FV' = FV / factor)
        if orig_fv and factor > 1.0:
            adj_fv = round(orig_fv / factor, 2)
            adj_mos = round(((adj_fv - price) / adj_fv) * 100, 2) if adj_fv > 0 else orig_mos
        else:
            adj_fv = orig_fv
            adj_mos = orig_mos

        # Recalculate Conviction: Pillar 1 Valuation score reflects the updated MoS
        orig_val_pts = get_valuation_pillar_points(orig_mos)
        adj_val_pts = get_valuation_pillar_points(adj_mos)
        val_diff = adj_val_pts - orig_val_pts
        adj_conv = round(max(0.0, min(100.0, orig_conv + val_diff)), 1)

        # Shadow Decision Gatekeeper:
        # In data_engine.py: stays in WATCH if (conviction >= 55.0) or (mos_pct >= 8.0)
        shadow_dec = orig_dec
        note = "STABLE"

        if orig_dec == "WATCH":
            stays_watch = (adj_conv >= 55.0) or (adj_mos is not None and adj_mos >= 8.0)
            if not stays_watch:
                shadow_dec = "REJECT"
                note = f"DROPPED_TO_REJECT (MoS {orig_mos}% -> {adj_mos}%, conv {orig_conv} -> {adj_conv})"
            else:
                note = f"WATCH_CONFIRMED (MoS {orig_mos}% -> {adj_mos}%, conv {orig_conv} -> {adj_conv})"
        elif is_stale:
            note = f"DILUTED (Factor {factor:.4f})"

        results.append({
            "symbol": sym,
            "sector": sector,
            "price": price,
            "period": period,
            "dilution_factor": factor,
            "is_stale": is_stale,
            "orig_bvps": orig_bvps,
            "adj_bvps": adj_bvps,
            "orig_fv": orig_fv,
            "adj_fv": adj_fv,
            "orig_mos": orig_mos,
            "adj_mos": adj_mos,
            "orig_conviction": orig_conv,
            "adj_conviction": adj_conv,
            "orig_decision": orig_dec,
            "shadow_decision": shadow_dec,
            "note": note
        })

    res_df = pd.DataFrame(results)
    
    # Save outputs
    out_csv = os.path.join(ROOT_DIR, "data", "shadow_dilution_55_audit.csv")
    res_df.to_csv(out_csv, index=False, encoding="utf-8-sig")
    
    scratch_csv = os.path.join(ROOT_DIR, "scratch", f"shadow_dilution_55_audit_{target_date}.csv")
    res_df.to_csv(scratch_csv, index=False, encoding="utf-8-sig")

    print(f"Shadow Dilution Audit ({target_date}) completed for {len(res_df)} stocks!")
    print(f"Saved to: {out_csv} and {scratch_csv}")

    print("\n" + "=" * 105)
    print(f"TÁC ĐỘNG SHADOW LÊN CÁC MÃ WATCH NGÀY {target_date}")
    print("=" * 105)
    watch_df = res_df[res_df["orig_decision"] == "WATCH"]
    for _, r in watch_df.iterrows():
        chg = "==> DROPPED" if r["orig_decision"] != r["shadow_decision"] else "    KEPT"
        print(f"{r['symbol']:5} | Dilution: {r['dilution_factor']:.4f} | FV: {str(r['orig_fv']):6} -> {str(r['adj_fv']):6} | MoS: {str(r['orig_mos']):6}% -> {str(r['adj_mos']):6}% | Conv: {r['orig_conviction']:4.1f} -> {r['adj_conviction']:4.1f} | {chg:12} -> {r['shadow_decision']:6}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", type=str, default="20261023", help="Target date YYYYMMDD")
    args = parser.parse_args()
    run_audit(args.date)
