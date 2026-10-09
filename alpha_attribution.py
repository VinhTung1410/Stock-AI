# -*- coding: utf-8 -*-
"""Alpha Attribution Engine for Strategy & Decision Evaluation (Phase 28 - v15.0).

Đo lường và bóc tách tỷ suất sinh lời Forward Return (T+5, T+20, T+60)
giữa 3 nhóm quyết định: REJECT vs WATCH vs BUY kèm kiểm soát Market Regime.
"""

from typing import Any, Dict, List

import numpy as np
import pandas as pd

COHORT_BUY = "BUY"
COHORT_WATCH = "WATCH"
COHORT_REJECT = "REJECT"


def compute_forward_returns(
    records: List[Dict[str, Any]],
    price_df: pd.DataFrame,
    horizons: tuple = (5, 20, 60),
) -> List[Dict[str, Any]]:
    """Tính toán lợi nhuận tương lai (Forward Returns) tại các mốc T+5, T+20, T+60

    cho từng bản ghi quyết định đầu tư.
    """
    if price_df.empty or not records:
        return []

    # Chuẩn hóa price_df (cột 'date', 'symbol', 'close')
    df = price_df.copy()
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")

    # Tạo pivot hoặc lookup nhanh: {(symbol, date): close_price}
    price_lookup = {}
    date_series_by_sym = {}
    for sym, group in df.groupby("symbol"):
        sorted_g = group.sort_values("date")
        dates = list(sorted_g["date"])
        closes = list(sorted_g["close"])
        date_series_by_sym[sym] = dates
        for d, c in zip(dates, closes):
            price_lookup[(sym, d)] = float(c)

    results = []
    for rec in records:
        r_copy = dict(rec)
        sym = r_copy.get("symbol", "").upper().strip()
        raw_dt = r_copy.get("decision_date") or r_copy.get("decision_time") or r_copy.get("created_at") or ""
        dt_str = str(raw_dt)[:10]

        r_copy["decision_date"] = dt_str
        dates_list = date_series_by_sym.get(sym, [])

        if sym not in date_series_by_sym or dt_str not in dates_list:
            for h in horizons:
                r_copy[f"fwd_ret_t{h}"] = None
            results.append(r_copy)
            continue

        idx = dates_list.index(dt_str)
        p0 = price_lookup.get((sym, dt_str), 0.0)

        for h in horizons:
            target_idx = idx + h
            if p0 > 0 and target_idx < len(dates_list):
                target_date = dates_list[target_idx]
                p_h = price_lookup.get((sym, target_date), 0.0)
                ret_h = round(((p_h - p0) / p0) * 100.0, 2)
                r_copy[f"fwd_ret_t{h}"] = ret_h
            else:
                r_copy[f"fwd_ret_t{h}"] = None

        results.append(r_copy)

    return results


def evaluate_alpha_attribution(
    evaluated_records: List[Dict[str, Any]],
    min_clean_sessions: int = 60,
    horizons: tuple = (5, 20, 60),
) -> Dict[str, Any]:
    """Đo lường Alpha chênh lệch giữa các nhóm thuần tập (Cohorts): REJECT vs WATCH vs BUY.

    Enforces Minimum Clean Sample Size rule:
    Nếu số phiên sạch < min_clean_sessions (60 phiên), đánh dấu INSUFFICIENT_SAMPLE.
    """
    if not evaluated_records:
        return {
            "status": "EMPTY_DATA",
            "is_sample_sufficient": False,
            "unique_sessions": 0,
            "cohort_metrics": {},
            "alpha_spreads": {},
        }

    # Đếm số phiên duy nhất
    dates = {r.get("decision_date") for r in evaluated_records if r.get("decision_date")}
    unique_sessions = len(dates)
    is_sample_sufficient = unique_sessions >= min_clean_sessions

    cohorts = {COHORT_BUY: [], COHORT_WATCH: [], COHORT_REJECT: []}
    for r in evaluated_records:
        dec = str(r.get("decision", "")).upper()
        if "BUY" in dec or "OPPORTUNITY" in dec:
            cohorts[COHORT_BUY].append(r)
        elif "WATCH" in dec:
            cohorts[COHORT_WATCH].append(r)
        else:
            cohorts[COHORT_REJECT].append(r)

    cohort_metrics = {}
    for c_name, c_records in cohorts.items():
        metrics = {"count": len(c_records)}
        for h in horizons:
            key = f"fwd_ret_t{h}"
            vals = [r[key] for r in c_records if r.get(key) is not None]
            if vals:
                metrics[f"t{h}_mean"] = round(float(np.mean(vals)), 2)
                metrics[f"t{h}_median"] = round(float(np.median(vals)), 2)
                metrics[f"t{h}_win_rate"] = round(float(np.sum(np.array(vals) > 0) / len(vals)) * 100.0, 1)
            else:
                metrics[f"t{h}_mean"] = None
                metrics[f"t{h}_median"] = None
                metrics[f"t{h}_win_rate"] = None
        cohort_metrics[c_name] = metrics

    # Tính Alpha Spreads (Chênh lệch so với nhóm REJECT)
    alpha_spreads = {}
    reject_m = cohort_metrics.get(COHORT_REJECT, {})
    buy_m = cohort_metrics.get(COHORT_BUY, {})
    watch_m = cohort_metrics.get(COHORT_WATCH, {})

    for h in horizons:
        rej_ret = reject_m.get(f"t{h}_mean")
        buy_ret = buy_m.get(f"t{h}_mean")
        watch_ret = watch_m.get(f"t{h}_mean")

        alpha_buy = round(buy_ret - rej_ret, 2) if (buy_ret is not None and rej_ret is not None) else None
        alpha_watch = round(watch_ret - rej_ret, 2) if (watch_ret is not None and rej_ret is not None) else None

        alpha_spreads[f"alpha_buy_vs_reject_t{h}"] = alpha_buy
        alpha_spreads[f"alpha_watch_vs_reject_t{h}"] = alpha_watch

    status = (
        "OOS_VERIFIED"
        if is_sample_sufficient
        else f"INSUFFICIENT_SAMPLE (Current {unique_sessions}/{min_clean_sessions} clean sessions)"
    )

    return {
        "status": status,
        "is_sample_sufficient": is_sample_sufficient,
        "unique_sessions": unique_sessions,
        "cohort_metrics": cohort_metrics,
        "alpha_spreads": alpha_spreads,
    }
