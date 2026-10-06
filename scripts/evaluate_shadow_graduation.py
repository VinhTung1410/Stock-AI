"""Script to evaluate Contrarian Shadow Mode graduation (TASK-0074 / TASK-0075 / Phase 25).

Determines whether Contrarian Engine is statistically ready to issue RECOMMEND_BUY signals
using a multi-factor graduation gate (Expectancy, Profit Factor, Effective Sample Size, Hit Rate).
"""

from __future__ import annotations

import os
import sys
from datetime import datetime
from typing import Any, Dict, List, Optional

# Add project root to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from db_manager import get_decision_forward_returns, get_decision_records

# Multi-Factor Graduation Thresholds
MIN_SHADOW_SESSIONS = 60
MIN_EFFECTIVE_SAMPLES = 30
MIN_HIT_RATE_T10 = 0.55
MIN_PROFIT_FACTOR_T10 = 1.2
MIN_EXPECTANCY_T10 = 0.0
DEFAULT_TRANSACTION_COST_PCT = 0.35
EPISODE_WINDOW_DAYS = 5


def deduplicate_signal_episodes(records: List[Dict[str, Any]], window_days: int = EPISODE_WINDOW_DAYS) -> List[Dict[str, Any]]:
    """Group consecutive signals on the same symbol within window_days into a single episode."""
    if not records:
        return []

    # If records lack symbols (e.g. synthetic test fixtures), treat distinct items as independent
    has_symbols = any(bool(r.get("symbol")) for r in records)
    if not has_symbols:
        return list(records)

    sorted_records = sorted(
        records,
        key=lambda x: (str(x.get("symbol", "")), str(x.get("created_at") or x.get("session") or ""))
    )
    episodes: List[Dict[str, Any]] = []

    current_sym: Optional[str] = None
    last_dt: Optional[datetime] = None

    for r in sorted_records:
        sym = str(r.get("symbol", "")).strip().upper()
        if not sym:
            episodes.append(r)
            continue

        raw_date_str = str(r.get("created_at") or r.get("session") or "")[:10]
        try:
            curr_dt = datetime.strptime(raw_date_str, "%Y-%m-%d")
        except ValueError:
            episodes.append(r)
            continue

        if sym != current_sym or last_dt is None or (curr_dt - last_dt).days > window_days:
            episodes.append(r)
            current_sym = sym
            last_dt = curr_dt

    return episodes


def estimate_effective_sample_size(
    episodes: List[Dict[str, Any]], intra_cluster_corr: float = 0.5
) -> float:
    """Estimate statistically independent sample size (N_eff) adjusting for cross-sectional market shock correlation.

    Uses Kish's design effect formula: N_eff = N_episodes / (1 + (m - 1) * rho)
    where m is average signals per active session cluster, and rho is assumed cross-sectional correlation.
    """
    if not episodes:
        return 0.0

    date_counts: Dict[str, int] = {}
    for e in episodes:
        d = str(e.get("created_at") or e.get("session") or "")[:10]
        date_counts[d] = date_counts.get(d, 0) + 1

    total_episodes = len(episodes)
    active_dates = len(date_counts)
    if active_dates == 0:
        return 0.0

    mean_cluster_size = total_episodes / active_dates
    vif = 1.0 + max(0.0, mean_cluster_size - 1.0) * intra_cluster_corr
    n_eff = total_episodes / vif
    return round(n_eff, 1)


def _calculate_expectancy_and_pf(
    returns: List[float], cost_pct: float, risk_pct_default: float = 7.0
) -> tuple[float, float, float, float]:
    """Calculate average net return (expectancy), profit factor, average raw return, and R-multiple expectancy."""
    if not returns:
        return 0.0, 0.0, 0.0, 0.0

    net_returns = [r - cost_pct for r in returns]
    expectancy_pct = sum(net_returns) / len(net_returns)
    avg_raw_ret = sum(returns) / len(returns)

    # R-multiple: Net gain/loss normalized by initial risk (assumed 7% stop loss by default)
    r_multiples = [net_r / risk_pct_default for net_r in net_returns]
    expectancy_r = sum(r_multiples) / len(r_multiples)

    gains = sum(r for r in returns if r > 0.0)
    losses = sum(abs(r) for r in returns if r < 0.0)

    if losses > 0.0:
        profit_factor = round(gains / losses, 2)
    else:
        profit_factor = 99.0 if gains > 0.0 else 1.0

    return round(expectancy_pct, 3), profit_factor, round(avg_raw_ret, 2), round(expectancy_r, 2)


def _check_graduation_conditions(
    distinct_sessions: int,
    effective_samples: int,
    hit_rate: float,
    expectancy: float,
    profit_factor: float,
) -> List[str]:
    """Audit metric thresholds and return list of blocking reasons."""
    reasons = []
    if distinct_sessions < MIN_SHADOW_SESSIONS:
        reasons.append(
            f"Chưa đủ {MIN_SHADOW_SESSIONS} phiên thử nghiệm (hiện có: {distinct_sessions})."
        )
    if effective_samples < MIN_EFFECTIVE_SAMPLES:
        reasons.append(
            f"Chưa đủ {MIN_EFFECTIVE_SAMPLES} episodes độc lập có kết quả T+10 (hiện có: {effective_samples})."
        )
    if hit_rate <= MIN_HIT_RATE_T10:
        reasons.append(
            f"Tỷ lệ thắng T+10 ({hit_rate*100:.1f}%) chưa vượt ngưỡng {MIN_HIT_RATE_T10*100:.0f}%."
        )
    if expectancy <= MIN_EXPECTANCY_T10:
        reasons.append(
            f"Kỳ vọng toán học Expectancy T+10 ({expectancy:+.2f}%) không đạt ngưỡng > {MIN_EXPECTANCY_T10}% (sau chi phí)."
        )
    if profit_factor < MIN_PROFIT_FACTOR_T10:
        reasons.append(
            f"Profit Factor ({profit_factor:.2f}) chưa đạt ngưỡng tối thiểu {MIN_PROFIT_FACTOR_T10:.1f}."
        )
    return reasons


def evaluate_shadow_graduation(
    limit: int = 500,
    records: Optional[List[Dict[str, Any]]] = None,
    fwd_records: Optional[List[Dict[str, Any]]] = None,
    cost_pct: float = DEFAULT_TRANSACTION_COST_PCT,
) -> Dict[str, Any]:
    """Check whether Contrarian Shadow Mode qualifies for graduation to live trading.

    Multi-Factor Criteria:
    1. At least 60 trial trading sessions / distinct dates.
    2. At least 30 independent episodes with T+10 return.
    3. T+10 hit rate > 55%.
    4. Expectancy E(R) > 0.0% after round-trip transaction costs.
    5. Profit Factor >= 1.2.
    """
    if records is None:
        records = get_decision_records(filters={"decision": "SHADOW_BUY"}, limit=limit)

    total_records = len(records)
    if total_records == 0:
        return {
            "can_graduate": False,
            "n_raw_signals": 0,
            "n_episodes": 0,
            "n_distinct_sessions": 0,
            "n_eff_estimated": 0.0,
            "total_signals": 0,
            "effective_sample_size": 0,
            "t10_sample_count": 0,
            "hit_rate_t10": 0.0,
            "expectancy_pct": 0.0,
            "expectancy_t10": 0.0,
            "expectancy_r": 0.0,
            "profit_factor_t10": 0.0,
            "avg_return_t10": 0.0,
            "distinct_sessions": 0,
            "reasons": ["Chưa có bản ghi SHADOW_BUY nào trong cơ sở dữ liệu."],
            "stage_gate_notice": "Shadow Graduation là điều kiện chuyển sang vòng Research Review + ADR, không phải giấy phép tự động mở giao dịch tiền thật.",
        }

    # Fetch forward returns if not provided
    fwd_map: Dict[str, Dict[str, Any]] = {}
    if fwd_records is None:
        dec_ids = [r.get("decision_id") for r in records if r.get("decision_id")]
        if dec_ids:
            fwd_list = get_decision_forward_returns(decision_ids=dec_ids, limit=limit)
            fwd_map = {f["decision_id"]: f for f in fwd_list if "decision_id" in f}
    else:
        fwd_map = {f["decision_id"]: f for f in fwd_records if "decision_id" in f}

    distinct_sessions = len({r.get("session") or str(r.get("created_at", ""))[:10] for r in records})

    # Group into episodes to prevent repeat signals from inflating sample size
    episodes = deduplicate_signal_episodes(records, window_days=EPISODE_WINDOW_DAYS)

    valid_episodes_t10: List[Dict[str, Any]] = []
    valid_t10_returns: List[float] = []
    for r in episodes:
        dec_id = r.get("decision_id")
        fwd_ret = r.get("t10_return_pct")
        if fwd_ret is None and dec_id and dec_id in fwd_map:
            fwd_ret = fwd_map[dec_id].get("t10_return_pct")
        # Distinguish None (unmatured) from 0.0 (breakeven)
        if fwd_ret is not None:
            valid_t10_returns.append(float(fwd_ret))
            valid_episodes_t10.append(r)

    effective_sample_count = len(valid_t10_returns)
    n_eff_estimated = estimate_effective_sample_size(valid_episodes_t10)

    if effective_sample_count == 0:
        return {
            "can_graduate": False,
            "n_raw_signals": total_records,
            "n_episodes": len(episodes),
            "n_distinct_sessions": distinct_sessions,
            "n_eff_estimated": 0.0,
            "total_signals": total_records,
            "effective_sample_size": 0,
            "t10_sample_count": 0,
            "hit_rate_t10": 0.0,
            "expectancy_pct": 0.0,
            "expectancy_t10": 0.0,
            "expectancy_r": 0.0,
            "profit_factor_t10": 0.0,
            "avg_return_t10": 0.0,
            "distinct_sessions": distinct_sessions,
            "reasons": [f"Chưa có mẫu T+10 nào (cần tối thiểu {MIN_EFFECTIVE_SAMPLES} episodes)."],
            "stage_gate_notice": "Shadow Graduation là điều kiện chuyển sang vòng Research Review + ADR, không phải giấy phép tự động mở giao dịch tiền thật.",
        }

    positive_t10 = sum(1 for ret in valid_t10_returns if ret > 0.0)
    hit_rate = round(positive_t10 / effective_sample_count, 3)

    expectancy_pct, profit_factor, avg_ret, expectancy_r = _calculate_expectancy_and_pf(valid_t10_returns, cost_pct)

    reasons = _check_graduation_conditions(
        distinct_sessions=distinct_sessions,
        effective_samples=effective_sample_count,
        hit_rate=hit_rate,
        expectancy=expectancy_pct,
        profit_factor=profit_factor,
    )

    can_grad = len(reasons) == 0

    return {
        "can_graduate": can_grad,
        "n_raw_signals": total_records,
        "n_episodes": len(episodes),
        "n_distinct_sessions": distinct_sessions,
        "n_eff_estimated": n_eff_estimated,
        "total_signals": total_records,
        "effective_sample_size": effective_sample_count,
        "t10_sample_count": effective_sample_count,
        "hit_rate_t10": hit_rate,
        "expectancy_pct": expectancy_pct,
        "expectancy_t10": expectancy_pct,
        "expectancy_r": expectancy_r,
        "profit_factor_t10": profit_factor,
        "avg_return_t10": avg_ret,
        "distinct_sessions": distinct_sessions,
        "reasons": reasons if not can_grad else ["Đạt toàn bộ tiêu chuẩn tốt nghiệp Shadow Mode."],
        "stage_gate_notice": "Shadow Graduation là điều kiện chuyển sang vòng Research Review + ADR, không phải giấy phép tự động mở giao dịch tiền thật.",
    }


def should_graduate_from_shadow() -> bool:
    """Convenience boolean helper."""
    res = evaluate_shadow_graduation()
    return res["can_graduate"]


if __name__ == "__main__":
    report = evaluate_shadow_graduation()
    print("Contrarian Shadow Mode Graduation Report (Multi-Factor):")
    print(f"  - Can Graduate: {report['can_graduate']}")
    print(f"  - Raw Signals (N_raw): {report['n_raw_signals']}")
    print(f"  - Episodes (N_episodes): {report['n_episodes']}")
    print(f"  - Effective Samples (N_eff estimated): {report['n_eff_estimated']}")
    print(f"  - Distinct Sessions: {report['n_distinct_sessions']}")
    print(f"  - Hit Rate T+10: {report['hit_rate_t10']*100:.1f}%")
    print(f"  - Expectancy (%): {report['expectancy_pct']:+.2f}%")
    print(f"  - Expectancy (R-Multiple): {report['expectancy_r']:+.2f}R")
    print(f"  - Profit Factor T+10: {report['profit_factor_t10']:.2f}")
    print(f"  - Stage Gate Notice: {report['stage_gate_notice']}")
    print(f"  - Reasons: {report['reasons']}")


