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
COHORT_DATA_ERROR = "DATA_ERROR"

DATA_ERROR_KEYWORDS = ("EXCEPTION", "TECH_FETCH", "TECH_INCOMPLETE", "DATA_GATE", "INCOMPLETE_DATA")


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
    deduplicate_symbol_date: bool = True,
    oos_start_date: str | None = None,
) -> Dict[str, Any]:
    """Đo lường Alpha chênh lệch giữa các nhóm thuần tập (Cohorts): REJECT vs WATCH vs BUY.

    - Loại trừ các bản ghi lỗi dữ liệu (DATA_ERROR) khỏi nhóm đối chứng REJECT.
    - Giữ 1 bản ghi chuẩn (canonical record) cho mỗi cặp (symbol, date) để tránh lệch trọng số.
    - Báo cáo số quan sát trưởng thành (n) cho từng mốc T+5, T+20, T+60.
    - Hỗ trợ cờ Out-Of-Sample (oos_start_date) để bóc tách dữ liệu out-of-sample sạch.
    """
    if not evaluated_records:
        return {
            "status": "EMPTY_DATA",
            "is_sample_sufficient": False,
            "unique_sessions": 0,
            "cohort_metrics": {},
            "alpha_spreads": {},
        }

    # 0. Loại trừ các bản ghi thử nghiệm ngầm (is_shadow == True)
    clean_records = [
        r for r in evaluated_records
        if not (
            r.get("is_shadow") is True
            or (isinstance(r.get("facts"), dict) and r["facts"].get("is_shadow") is True)
        )
    ]

    # 1. Deduplicate: giữ bản ghi chuẩn cho mỗi (symbol, decision_date)
    records_to_process = clean_records
    if deduplicate_symbol_date:
        dedup_dict = {}
        for r in clean_records:
            sym = str(r.get("symbol", "")).upper().strip()
            dt = str(r.get("decision_date", ""))[:10]
            if sym and dt:
                dedup_dict[(sym, dt)] = r
            else:
                dedup_dict[id(r)] = r
        records_to_process = list(dedup_dict.values())

    # Lọc thuần tập Out-Of-Sample (OOS) nếu được yêu cầu
    if oos_start_date:
        records_to_process = [
            r for r in records_to_process
            if str(r.get("decision_date", ""))[:10] >= str(oos_start_date)[:10]
        ]

    # Đếm số phiên duy nhất
    dates = {r.get("decision_date") for r in records_to_process if r.get("decision_date")}
    unique_sessions = len(dates)
    is_sample_sufficient = unique_sessions >= min_clean_sessions

    # Đếm quan sát đã trưởng thành theo từng mốc chân trời
    matured_counts = {
        f"t{h}_matured_n": sum(1 for r in records_to_process if r.get(f"fwd_ret_t{h}") is not None)
        for h in horizons
    }

    cohorts = {COHORT_BUY: [], COHORT_WATCH: [], COHORT_REJECT: [], COHORT_DATA_ERROR: []}
    for r in records_to_process:
        dec = str(r.get("decision", "")).upper()
        rej_gate = str(r.get("primary_rejection_gate", "")).upper()
        reason = str(r.get("reason", "")).upper()

        # Tách lỗi dữ liệu khỏi nhóm đối chứng REJECT định lượng
        is_data_err = any(kw in dec or kw in rej_gate or kw in reason for kw in DATA_ERROR_KEYWORDS)
        if is_data_err:
            cohorts[COHORT_DATA_ERROR].append(r)
        elif "BUY" in dec or "OPPORTUNITY" in dec:
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
            metrics[f"t{h}_n"] = len(vals)
            if vals:
                metrics[f"t{h}_mean"] = round(float(np.mean(vals)), 2)
                metrics[f"t{h}_median"] = round(float(np.median(vals)), 2)
                metrics[f"t{h}_win_rate"] = round(float(np.sum(np.array(vals) > 0) / len(vals)) * 100.0, 1)
            else:
                metrics[f"t{h}_mean"] = None
                metrics[f"t{h}_median"] = None
                metrics[f"t{h}_win_rate"] = None
        cohort_metrics[c_name] = metrics

    # Tính Alpha Spreads (Chênh lệch so với nhóm REJECT chuẩn định lượng)
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

    # Phân tầng theo ngành (Industry Stratification) để khử nhiễu beta ngành
    sector_strata = {}
    sectors = {r.get("sector") for r in records_to_process if r.get("sector")}
    for sec in sectors:
        sec_records = [r for r in records_to_process if r.get("sector") == sec]
        sec_watch = [r for r in sec_records if "WATCH" in str(r.get("decision", "")).upper()]
        sec_rej = [
            r for r in sec_records
            if "REJECT" in str(r.get("decision", "")).upper()
            and not any(kw in str(r.get("primary_rejection_gate", "")) for kw in DATA_ERROR_KEYWORDS)
        ]
        sec_m = {"count": len(sec_records), "watch_count": len(sec_watch), "reject_count": len(sec_rej)}
        for h in horizons:
            w_vals = [r[f"fwd_ret_t{h}"] for r in sec_watch if r.get(f"fwd_ret_t{h}") is not None]
            r_vals = [r[f"fwd_ret_t{h}"] for r in sec_rej if r.get(f"fwd_ret_t{h}") is not None]
            if w_vals and r_vals:
                sec_m[f"alpha_watch_vs_reject_t{h}"] = round(float(np.mean(w_vals) - np.mean(r_vals)), 2)
            else:
                sec_m[f"alpha_watch_vs_reject_t{h}"] = None
        sector_strata[sec] = sec_m

    status = (
        "SAMPLE_SIZE_OK"
        if is_sample_sufficient
        else f"INSUFFICIENT_SAMPLE (Current {unique_sessions}/{min_clean_sessions} clean sessions)"
    )

    return {
        "status": status,
        "is_sample_sufficient": is_sample_sufficient,
        "unique_sessions": unique_sessions,
        "matured_counts": matured_counts,
        "cohort_metrics": cohort_metrics,
        "alpha_spreads": alpha_spreads,
        "sector_strata": sector_strata,
    }


def compute_clustered_bootstrap_alpha(
    records: List[Dict[str, Any]],
    cohort_a: str = COHORT_WATCH,
    cohort_b: str = COHORT_REJECT,
    horizon: int = 5,
    n_resamples: int = 1000,
    random_seed: int = 42,
) -> Dict[str, Any]:
    """Tính Khoảng tin cậy Bootstrap theo Cụm Ngày (Clustered Bootstrap by Trading Date).

    Bảo toàn tính tương quan chéo giữa các cổ phiếu được định giá trong cùng một phiên giao dịch.
    """
    key = f"fwd_ret_t{horizon}"
    by_date: Dict[str, Dict[str, List[float]]] = {}
    for r in records:
        val = r.get(key)
        if val is None:
            continue
        dt = str(r.get("decision_date") or "")[:10]
        if not dt:
            continue
        dec = str(r.get("decision", "")).upper()
        rej_gate = str(r.get("primary_rejection_gate", "")).upper()
        if any(kw in dec or kw in rej_gate for kw in DATA_ERROR_KEYWORDS):
            continue

        c = COHORT_WATCH if "WATCH" in dec else (COHORT_BUY if "BUY" in dec else COHORT_REJECT)
        if dt not in by_date:
            by_date[dt] = {COHORT_BUY: [], COHORT_WATCH: [], COHORT_REJECT: []}
        by_date[dt][c].append(float(val))

    dates = list(by_date.keys())
    if len(dates) < 2:
        return {
            "status": "INSUFFICIENT_SESSIONS",
            "alpha_mean": None,
            "ci_lower": None,
            "ci_upper": None,
            "p_value": None,
            "n_sessions": len(dates),
        }

    rng = np.random.default_rng(random_seed)
    sampled_spreads = []

    for _ in range(n_resamples):
        sampled_dates = rng.choice(dates, size=len(dates), replace=True)
        vals_a = [v for d in sampled_dates for v in by_date[d][cohort_a]]
        vals_b = [v for d in sampled_dates for v in by_date[d][cohort_b]]

        if vals_a and vals_b:
            spread = float(np.mean(vals_a) - np.mean(vals_b))
            sampled_spreads.append(spread)

    if not sampled_spreads:
        return {
            "status": "NO_PAIRED_DATA",
            "alpha_mean": None,
            "ci_lower": None,
            "ci_upper": None,
            "p_value": None,
            "n_sessions": len(dates),
        }

    spreads_arr = np.array(sampled_spreads)
    ci_lower = float(np.percentile(spreads_arr, 2.5))
    ci_upper = float(np.percentile(spreads_arr, 97.5))
    alpha_mean = float(np.mean(spreads_arr))
    p_val = float(np.mean(spreads_arr <= 0.0))

    return {
        "status": "BOOTSTRAP_OK",
        "alpha_mean": round(alpha_mean, 2),
        "ci_lower": round(ci_lower, 2),
        "ci_upper": round(ci_upper, 2),
        "p_value": round(p_val, 4),
        "n_sessions": len(dates),
        "n_resamples": n_resamples,
    }

