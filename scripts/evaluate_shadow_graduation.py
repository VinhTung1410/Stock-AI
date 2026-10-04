"""
Script to evaluate Contrarian Shadow Mode graduation (TASK-0074 / Phase 25).
Determines whether Contrarian Engine is statistically ready to issue RECOMMEND_BUY signals.
"""

from __future__ import annotations

import os
import sys
from typing import Any, Dict

# Add project root to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from db_manager import get_decision_forward_returns, get_decision_records

MIN_SAMPLES_T10 = 30
MIN_HIT_RATE_T10 = 0.55
MIN_SHADOW_SESSIONS = 60


def evaluate_shadow_graduation(limit: int = 500) -> Dict[str, Any]:
    """Check whether Contrarian Shadow Mode qualifies for graduation to live trading.

    Criteria:
    1. At least 60 trial trading sessions / distinct dates.
    2. At least 30 closed SHADOW_BUY observations with T+10 forward return.
    3. T+10 hit rate > 55% (positive alpha).
    """
    records = get_decision_records(filters={"decision": "SHADOW_BUY"}, limit=limit)
    total_records = len(records)
    if total_records == 0:
        return {
            "can_graduate": False,
            "total_signals": 0,
            "t10_sample_count": 0,
            "hit_rate_t10": 0.0,
            "avg_return_t10": 0.0,
            "distinct_sessions": 0,
            "reasons": ["Chưa có bản ghi SHADOW_BUY nào trong cơ sở dữ liệu."],
        }

    dec_ids = [r.get("decision_id") for r in records if r.get("decision_id")]
    fwd_map = {}
    if dec_ids:
        fwd_records = get_decision_forward_returns(decision_ids=dec_ids, limit=limit)
        fwd_map = {f["decision_id"]: f for f in fwd_records if "decision_id" in f}

    distinct_sessions = len(set(r.get("session") or r.get("created_at", "")[:10] for r in records))
    with_t10 = []
    for r in records:
        dec_id = r.get("decision_id")
        fwd_ret = r.get("t10_return_pct")
        if fwd_ret is None and dec_id and dec_id in fwd_map:
            fwd_ret = fwd_map[dec_id].get("t10_return_pct")
        if fwd_ret is not None:
            with_t10.append({"t10_return_pct": fwd_ret, "symbol": r.get("symbol")})
    sample_count = len(with_t10)

    reasons = []
    if distinct_sessions < MIN_SHADOW_SESSIONS:
        reasons.append(f"Chưa đủ {MIN_SHADOW_SESSIONS} phiên thử nghiệm (hiện có: {distinct_sessions}).")

    if sample_count < MIN_SAMPLES_T10:
        reasons.append(f"Chưa đủ {MIN_SAMPLES_T10} mẫu có kết quả T+10 (hiện có: {sample_count}).")
        return {
            "can_graduate": False,
            "total_signals": total_records,
            "t10_sample_count": sample_count,
            "hit_rate_t10": 0.0,
            "avg_return_t10": 0.0,
            "distinct_sessions": distinct_sessions,
            "reasons": reasons,
        }

    positive_t10 = sum(1 for r in with_t10 if float(r.get("t10_return_pct", 0.0)) > 0.0)
    hit_rate = round(positive_t10 / sample_count, 3)
    avg_ret = round(sum(float(r.get("t10_return_pct", 0.0)) for r in with_t10) / sample_count, 2)

    if hit_rate <= MIN_HIT_RATE_T10:
        reasons.append(f"Tỷ lệ thắng T+10 ({hit_rate*100:.1f}%) chưa vượt ngưỡng {MIN_HIT_RATE_T10*100:.0f}%.")

    can_grad = len(reasons) == 0

    return {
        "can_graduate": can_grad,
        "total_signals": total_records,
        "t10_sample_count": sample_count,
        "hit_rate_t10": hit_rate,
        "avg_return_t10": avg_ret,
        "distinct_sessions": distinct_sessions,
        "reasons": reasons if not can_grad else ["Đạt toàn bộ tiêu chuẩn tốt nghiệp Shadow Mode."],
    }


def should_graduate_from_shadow() -> bool:
    """Convenience boolean helper."""
    res = evaluate_shadow_graduation()
    return res["can_graduate"]


if __name__ == "__main__":
    report = evaluate_shadow_graduation()
    print("Contrarian Shadow Mode Graduation Report:")
    print(f"  - Can Graduate: {report['can_graduate']}")
    print(f"  - Total Signals: {report['total_signals']}")
    print(f"  - T+10 Samples: {report['t10_sample_count']}")
    print(f"  - Hit Rate T+10: {report['hit_rate_t10']*100:.1f}%")
    print(f"  - Reasons: {report['reasons']}")
