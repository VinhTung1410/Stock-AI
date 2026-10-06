"""Shadow Mode Validation Script — Verify live Supabase data integrity (TASK-0075 / Phase 25).

Checks:
1. SHADOW_BUY records exist in decision_records table
2. Forward returns data in decision_forward_returns table
3. Data consistency: snapshot_price > 0, decision_id linkage
4. Horizon coverage: which T+N horizons have been populated
5. Graduation readiness evaluation with live data
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from db_manager import get_decision_forward_returns, get_decision_records
from scripts.evaluate_shadow_graduation import evaluate_shadow_graduation


def validate_shadow_data():
    """Run comprehensive validation against live Supabase data."""
    print("=" * 70)
    print("SHADOW MODE VALIDATION REPORT")
    print("=" * 70)

    # ---------------------------------------------------------------
    # 1. Query SHADOW_BUY records
    # ---------------------------------------------------------------
    print("\n[1/5] Querying SHADOW_BUY decision records...")
    shadow_records = get_decision_records(filters={"decision": "SHADOW_BUY"}, limit=500)
    print(f"  Total SHADOW_BUY records: {len(shadow_records)}")

    if not shadow_records:
        print("  >> No SHADOW_BUY records found. Shadow Mode has not generated any signals yet.")
        print("  >> This is expected if the system has not encountered panic conditions.")
        _print_all_decisions_summary()
        _run_graduation_check(shadow_records)
        return

    # ---------------------------------------------------------------
    # 2. Analyze record quality
    # ---------------------------------------------------------------
    print("\n[2/5] Analyzing SHADOW_BUY record quality...")
    symbols = set()
    sessions = set()
    valid_snapshot = 0
    missing_decision_id = 0
    missing_facts = 0

    for r in shadow_records:
        symbols.add(r.get("symbol", "UNKNOWN"))
        sessions.add(r.get("session") or str(r.get("created_at", ""))[:10])
        if not r.get("decision_id"):
            missing_decision_id += 1
        facts = r.get("facts", {})
        if not facts:
            missing_facts += 1
        else:
            snap = facts.get("snapshot_price") or r.get("price", 0)
            if snap and float(snap) > 0:
                valid_snapshot += 1

    print(f"  Unique symbols: {len(symbols)} -> {sorted(symbols)}")
    print(f"  Unique sessions/dates: {len(sessions)}")
    print(f"  Valid snapshot_price: {valid_snapshot}/{len(shadow_records)}")
    print(f"  Missing decision_id: {missing_decision_id}")
    print(f"  Missing facts: {missing_facts}")

    # Show latest 5 records
    print("\n  Latest SHADOW_BUY records:")
    for r in shadow_records[:5]:
        facts = r.get("facts", {})
        print(f"    - {r.get('symbol', '?')} | {r.get('session', '?')} | "
              f"decision_id={r.get('decision_id', 'N/A')[:20]}... | "
              f"snap_price={facts.get('snapshot_price', 'N/A')} | "
              f"panic_score={facts.get('panic_score', 'N/A')} | "
              f"mos_pct={facts.get('mos_pct', 'N/A')}")

    # ---------------------------------------------------------------
    # 3. Query forward returns
    # ---------------------------------------------------------------
    print("\n[3/5] Querying decision_forward_returns...")
    dec_ids = [r.get("decision_id") for r in shadow_records if r.get("decision_id")]
    fwd_records = []
    if dec_ids:
        fwd_records = get_decision_forward_returns(decision_ids=dec_ids, limit=500)
    print(f"  Forward return records found: {len(fwd_records)}")
    print(f"  Coverage: {len(fwd_records)}/{len(dec_ids)} decision_ids have forward returns")

    if fwd_records:
        # Analyze horizon coverage
        horizons = {
            "t1_return_pct": 0, "t3_return_pct": 0,
            "t5_return_pct": 0, "t10_return_pct": 0,
            "t20_return_pct": 0, "vnindex_t5_pct": 0,
            "vnindex_t20_pct": 0,
        }
        for f in fwd_records:
            for h in horizons:
                if f.get(h) is not None:
                    horizons[h] += 1

        print("\n  Horizon coverage:")
        for h, count in horizons.items():
            bar = "#" * min(count, 30)
            print(f"    {h:20s}: {count:3d}/{len(fwd_records)} {bar}")

        # Show latest 5 forward returns
        print("\n  Latest forward return records:")
        for f in fwd_records[:5]:
            print(f"    - dec_id={str(f.get('decision_id', '?'))[:20]}... | "
                  f"symbol={f.get('symbol', '?')} | "
                  f"snap={f.get('snapshot_price', 'N/A')} | "
                  f"T+1={f.get('t1_return_pct', 'N/A')} | "
                  f"T+5={f.get('t5_return_pct', 'N/A')} | "
                  f"T+10={f.get('t10_return_pct', 'N/A')} | "
                  f"T+20={f.get('t20_return_pct', 'N/A')}")

    # ---------------------------------------------------------------
    # 4. Data integrity checks
    # ---------------------------------------------------------------
    print("\n[4/5] Data integrity checks...")
    issues = []

    # Check: decision_ids in fwd_records match shadow_records
    fwd_dec_ids = {f.get("decision_id") for f in fwd_records}
    orphaned_fwd = fwd_dec_ids - set(dec_ids)
    if orphaned_fwd:
        issues.append(f"  WARN: {len(orphaned_fwd)} forward return records have no matching SHADOW_BUY decision")

    # Check: snapshot_price consistency
    for f in fwd_records:
        snap = f.get("snapshot_price")
        if snap is not None and float(snap) <= 0:
            issues.append(f"  ERROR: Forward return for {f.get('decision_id')} has invalid snapshot_price={snap}")

    # Check: T+10 with value 0.0 (could be breakeven or error)
    zero_t10 = [f for f in fwd_records if f.get("t10_return_pct") == 0.0]
    if zero_t10:
        issues.append(f"  INFO: {len(zero_t10)} records have t10_return_pct=0.0 (exact breakeven — verify if genuine)")

    if issues:
        for issue in issues:
            print(issue)
    else:
        print("  All integrity checks passed.")

    # ---------------------------------------------------------------
    # 5. Graduation evaluation with live data
    # ---------------------------------------------------------------
    _run_graduation_check(shadow_records, fwd_records if fwd_records else None)


def _print_all_decisions_summary():
    """Print summary of all decision types to understand pipeline activity."""
    print("\n  [INFO] Checking all decision types for context...")
    all_records = get_decision_records(limit=50)
    if not all_records:
        print("  >> No decision records found at all in database.")
        return

    decision_types = {}
    for r in all_records:
        d = r.get("decision", "UNKNOWN")
        decision_types[d] = decision_types.get(d, 0) + 1

    print(f"  Latest {len(all_records)} decisions breakdown:")
    for dtype, count in sorted(decision_types.items(), key=lambda x: -x[1]):
        print(f"    {dtype}: {count}")


def _run_graduation_check(shadow_records, fwd_records=None):
    """Run graduation evaluation and print report."""
    print("\n[5/5] Running Shadow Mode Graduation Evaluation...")
    print("-" * 50)

    if not shadow_records:
        report = evaluate_shadow_graduation(records=[])
    elif fwd_records is not None:
        report = evaluate_shadow_graduation(records=shadow_records, fwd_records=fwd_records)
    else:
        report = evaluate_shadow_graduation(records=shadow_records)

    print(f"  Can Graduate:          {report['can_graduate']}")
    print(f"  Raw Signals (N_raw):   {report['n_raw_signals']}")
    print(f"  Episodes (N_episodes): {report['n_episodes']}")
    print(f"  N_eff (estimated):     {report['n_eff_estimated']}")
    print(f"  Distinct Sessions:     {report['n_distinct_sessions']}")
    print(f"  T+10 Sample Count:     {report['t10_sample_count']}")
    print(f"  Hit Rate T+10:         {report['hit_rate_t10']*100:.1f}%")
    print(f"  Expectancy T+10:       {report['expectancy_t10']:+.2f}%")
    print(f"  Expectancy (R-mult):   {report['expectancy_r']:+.2f}R")
    print(f"  Profit Factor T+10:    {report['profit_factor_t10']:.2f}")
    print(f"  Avg Return T+10:       {report['avg_return_t10']:+.2f}%")
    print(f"  Stage Gate Notice:     {report['stage_gate_notice']}")
    print("  Reasons:")
    for reason in report.get("reasons", []):
        print(f"    - {reason}")

    print("\n" + "=" * 70)
    if report["can_graduate"]:
        print("VERDICT: SHADOW MODE QUALIFIES FOR GRADUATION (pending Research Review + ADR)")
    else:
        print("VERDICT: SHADOW MODE NOT YET READY FOR GRADUATION")
    print("=" * 70)


if __name__ == "__main__":
    validate_shadow_data()
