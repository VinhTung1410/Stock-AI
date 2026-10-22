"""Shadow Dilution Audit on all 55 Canonical Stocks (2026-10-20 EOD).

Runs detect_and_adjust_post_bctc_dilution side-by-side with production baseline.
Computes:
- Original vs Adjusted BVPS & EPS
- Cumulative Dilution Factor
- Original vs Shadow Fair Value & MoS %
- Decision Impact (Whether WATCH drops to REJECT due to MoS < 15%)
"""

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
from quant_valuation import calculate_fair_value_and_mos

# 1. Load canonical decisions
dec_df = pd.read_csv(os.path.join(ROOT_DIR, "decision_records_20261020.csv"))
dec_map = {}
for _, r in dec_df[dec_df["is_canonical"].astype(bool)].iterrows():
    facts = json.loads(r["facts"]) if isinstance(r["facts"], str) else r["facts"]
    dec_map[r["symbol"]] = {
        "decision": r["decision"],
        "price": r["price"],
        "mos_pct": r["mos_pct"],
        "conviction": r["conviction"],
        "fair_value": facts.get("fair_value"),
        "target_pb": facts.get("target_pb"),
        "sector": facts.get("sector")
    }

# 2. Load canonical raw snapshots
with open(os.path.join(ROOT_DIR, "data", "raw_snapshots_20261020_canonical.json"), "r", encoding="utf-8") as f:
    snaps = json.load(f)
snap_map = {s["symbol"]: s for s in snaps}

# 3. Load audited corporate events
with open(os.path.join(ROOT_DIR, "scratch", "corporate_events_with_prices.json"), "r", encoding="utf-8") as f:
    ca_audits = json.load(f)
ca_map = {item["symbol"]: item["events"] for item in ca_audits}

results = []

for sym in sorted(dec_map.keys()):
    dec_info = dec_map[sym]
    snap_info = snap_map.get(sym, {})
    fin_raw = snap_info.get("raw_bctc", {})
    tech_raw = snap_info.get("raw_price", {})

    curr_p = dec_info["price"] or tech_raw.get("current_price") or tech_raw.get("close")
    orig_bvps = fin_raw.get("bvps")
    orig_eps = fin_raw.get("eps")
    period = fin_raw.get("period")
    orig_dec = dec_info["decision"]
    orig_mos = dec_info["mos_pct"]
    orig_fv = dec_info["fair_value"]
    sector = dec_info.get("sector") or ""

    events = ca_map.get(sym, [])

    # Format corporate actions for detect_and_adjust_post_bctc_dilution
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

    # Re-evaluate valuation with adjusted BVPS & EPS
    adj_fin = dict(fin_raw) if fin_raw else {}
    if adj_bvps:
        adj_fin["bvps"] = adj_bvps
    if adj_eps:
        adj_fin["eps"] = adj_eps

    try:
        val_res = calculate_fair_value_and_mos(
            symbol=sym,
            current_price=curr_p,
            fin_dict=adj_fin,
            sector=sector
        )
        adj_fv = val_res.get("fair_value")
        adj_mos = val_res.get("mos_pct")
    except Exception:
        adj_fv = orig_fv / factor if (orig_fv and factor > 1.0) else orig_fv
        adj_mos = round(((adj_fv - curr_p) / adj_fv) * 100, 2) if (adj_fv and curr_p) else orig_mos

    # Shadow Decision Logic:
    # If original was WATCH, does it hold MoS >= 15.0%?
    shadow_dec = orig_dec
    note = "STABLE"

    if orig_dec == "WATCH":
        if adj_mos is not None and adj_mos < 15.0:
            shadow_dec = "REJECT"
            note = f"DROPPED_MOS_THRESHOLD (MoS {orig_mos}% -> {adj_mos}%)"
        else:
            note = f"WATCH_CONFIRMED (MoS {orig_mos}% -> {adj_mos}%)"
    elif is_stale:
        note = f"DILUTED (Factor {factor:.4f})"

    results.append({
        "symbol": sym,
        "sector": sector,
        "price": curr_p,
        "period": period,
        "dilution_factor": factor,
        "is_stale": is_stale,
        "orig_bvps": orig_bvps,
        "adj_bvps": adj_bvps,
        "orig_fv": orig_fv,
        "adj_fv": round(adj_fv, 2) if adj_fv else None,
        "orig_mos": orig_mos,
        "adj_mos": adj_mos,
        "orig_decision": orig_dec,
        "shadow_decision": shadow_dec,
        "note": note
    })

res_df = pd.DataFrame(results)
out_csv = os.path.join(ROOT_DIR, "scratch", "shadow_dilution_55_audit.csv")
res_df.to_csv(out_csv, index=False, encoding="utf-8-sig")

print(f"Shadow Dilution Audit completed for {len(res_df)} stocks! Saved to {out_csv}")

# Print summary of WATCH stocks affected
print("\n" + "=" * 90)
print("TÁC ĐỘNG SHADOW LÊN 16 MÃ WATCH")
print("=" * 90)
watch_df = res_df[res_df["orig_decision"] == "WATCH"]
for _, r in watch_df.iterrows():
    chg = "==>" if r["orig_decision"] != r["shadow_decision"] else "   "
    print(f"{r['symbol']:5} | Dilution: {r['dilution_factor']:.4f} | BVPS: {str(r['orig_bvps']):8} -> {str(r['adj_bvps']):8} | MoS: {str(r['orig_mos']):6}% -> {str(r['adj_mos']):6}% | {chg} {r['orig_decision']:5} -> {r['shadow_decision']:6} | {r['note']}")
