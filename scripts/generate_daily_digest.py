# -*- coding: utf-8 -*-
"""Daily Quant Research Digest Generator.

Automates the end-to-end post-market quant reporting pipeline:
1. Syncs today's decision records & lifecycle events from DB (via export_today_csv.py).
2. Calculates forward returns and updates institutional benchmarks (via update_forward_returns.py).
3. Aggregates decisions, gate statistics, watchlist state transitions, and multi-cohort forward returns.
4. Outputs a single, ultra-dense Markdown briefing (reports/daily_digest_YYYYMMDD.md) optimized for Claude / AI Analyst research.
"""

from __future__ import annotations

import argparse
import glob
import json
import logging
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from typing import Any

import numpy as np
import pandas as pd

# Windows UTF-8 Terminal Fix
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
LOGGER = logging.getLogger("daily_digest")

# SonarCloud S1192 Constants
SESSION_EOD = "EOD_CANONICAL"
DEC_BUY = "BUY"
DEC_WATCH = "WATCH"
DEC_REJECT = "REJECT"
COL_DECISION = "decision"
COL_SYMBOL = "symbol"
GATE_TECH = "TECH_CONFIRMATION"
GATE_RISK = "RISK_TRAP"
EVENT_WL_ADDED = "WATCHLIST_ADDED"
DIGEST_HORIZONS = (1, 3, 5, 10, 20)
EXPECTED_UNIVERSE_SIZE = 55
STAGE2_PROSPECTIVE_START = "2026-11-26"


def get_default_vn_date() -> str:
    """Return current date in Vietnam timezone (UTC+7) formatted as YYYY-MM-DD."""
    vn_tz = timezone(timedelta(hours=0))
    return datetime.now(vn_tz).strftime("%Y-%m-%d")


def _run_sub_step(cmd: list[str], step_name: str) -> bool:
    """Execute a python sub-step safely via subprocess."""
    LOGGER.info("[*] Bước: %s -> %s", step_name, " ".join(cmd))
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", check=False)
        if res.returncode == 0:
            LOGGER.info("[✓] %s hoàn tất thành công.", step_name)
            return True
        LOGGER.warning("[!] %s cảnh báo (mã lỗi %d): %s", step_name, res.returncode, res.stderr[-300:] if res.stderr else "N/A")
        return False
    except Exception:
        LOGGER.exception("Lỗi bất thường khi thực thi %s", step_name)
        return False


def run_pipeline_sync(
    target_date: str,
    skip_export: bool,
    skip_returns: bool,
    sync_db: bool = True,
    skip_stage2: bool = False,
) -> None:
    """Run underlying synchronization scripts (and Stage 2 shadow logger from 2026-11-26+) if not skipped."""
    py_exec = sys.executable

    if not skip_export:
        _run_sub_step([py_exec, os.path.join("scripts", "export_today_csv.py"), target_date], "Xuất CSV quyết định hôm nay")

    if not skip_returns:
        returns_cmd = [py_exec, os.path.join("scripts", "update_forward_returns.py"), "--up-to", target_date]
        if not sync_db:
            returns_cmd.append("--skip-db")
        step_name = "Cập nhật lợi nhuận đa kỳ & đồng bộ Supabase" if sync_db else "Cập nhật lợi nhuận đa kỳ"
        _run_sub_step(returns_cmd, step_name)

    if not skip_stage2 and target_date >= STAGE2_PROSPECTIVE_START:
        _run_sub_step(
            [py_exec, os.path.join("scripts", "stage2_shadow_logger.py"), target_date],
            "Ghi log Raw Score Giai đoạn 2 (cách ly data/stage2_shadow)",
        )


def _load_decision_records(target_date: str) -> pd.DataFrame:
    """Load decision_records CSV for the given target date."""
    date_code = target_date.replace("-", "")
    filename = f"decision_records_{date_code}.csv"
    if not os.path.exists(filename):
        LOGGER.warning("Không tìm thấy tệp %s", filename)
        return pd.DataFrame()
    return pd.read_csv(filename)


def _load_lifecycle_events(target_date: str) -> pd.DataFrame:
    """Load lifecycle_events CSV for the given target date."""
    date_code = target_date.replace("-", "")
    filename = f"lifecycle_events_{date_code}.csv"
    if not os.path.exists(filename):
        LOGGER.warning("Không tìm thấy tệp %s", filename)
        return pd.DataFrame()
    return pd.read_csv(filename)


def _extract_regime_and_version(dec_df: pd.DataFrame) -> dict[str, Any]:
    """Extract regime features, index status, and frozen logic versions from canonical EOD session."""
    res: dict[str, Any] = {
        "regime": "UNKNOWN",
        "vnindex_price": None,
        "vnindex_ma200": None,
        "vnindex_vs_ma200_pct": None,
        "logic_version": "v15.0_frozen_20261013",
        "model_version": "v15.0_post_fix",
        "git_sha": "unknown",
    }
    if dec_df.empty:
        return res

    sample = dec_df.iloc[0]
    res["logic_version"] = str(sample.get("logic_version") or res["logic_version"])
    res["model_version"] = str(sample.get("model_version") or res["model_version"])
    res["git_sha"] = str(sample.get("git_sha") or res["git_sha"])[:10]

    # Preference: extract strictly from EOD_CANONICAL to reflect actual end-of-day market close!
    eod = dec_df[dec_df["session"] == SESSION_EOD] if "session" in dec_df.columns else pd.DataFrame()
    if not eod.empty:
        target_df = eod
    else:
        fallback_session = dec_df["session"].iloc[0] if "session" in dec_df.columns and not dec_df.empty else "UNKNOWN"
        LOGGER.warning(
            "CẢNH BÁO [Regime Extraction]: Không tìm thấy session EOD_CANONICAL trong decision records, buộc phải fallback về session %s (dữ liệu có thể bị trễ 1 phiên)!",
            fallback_session,
        )
        res["fallback_warning"] = fallback_session
        target_df = dec_df

    for _, row in target_df.iterrows():
        raw_facts = row.get("facts")
        if not raw_facts or not isinstance(raw_facts, str):
            continue
        try:
            facts = json.loads(raw_facts)
            rf = facts.get("regime_features")
            if rf and isinstance(rf, dict):
                res["regime"] = rf.get("regime", res["regime"])
                res["vnindex_price"] = rf.get("vnindex_price")
                res["vnindex_ma200"] = rf.get("vnindex_ma200")
                res["vnindex_vs_ma200_pct"] = rf.get("vnindex_vs_ma200_pct")
                break
        except Exception:
            continue
    return res


def _compute_eod_decisions(dec_df: pd.DataFrame) -> dict[str, Any]:
    """Compute canonical EOD decision stats and gate distributions."""
    if dec_df.empty:
        return {"total": 0, "buy": 0, "watch": 0, "reject": 0, "gates": {}, "watch_symbols": []}

    if "session" in dec_df.columns:
        eod = dec_df[dec_df["session"] == SESSION_EOD]
    else:
        eod = pd.DataFrame()

    if eod.empty:
        eod = dec_df.drop_duplicates(subset=[COL_SYMBOL], keep="last")

    counts = eod[COL_DECISION].value_counts().to_dict() if COL_DECISION in eod.columns else {}
    gates = eod["primary_rejection_gate"].value_counts().head(5).to_dict() if "primary_rejection_gate" in eod.columns else {}

    watch_rows = eod[eod[COL_DECISION] == DEC_WATCH]
    watch_symbols = sorted(watch_rows[COL_SYMBOL].tolist()) if not watch_rows.empty else []

    return {
        "total": len(eod),
        "buy": counts.get(DEC_BUY, 0),
        "watch": counts.get(DEC_WATCH, 0),
        "reject": counts.get(DEC_REJECT, 0),
        "gates": gates,
        "watch_symbols": watch_symbols,
    }


def _extract_watchlist_additions(lc_df: pd.DataFrame) -> list[str]:
    """Extract list of symbols added to watchlist from lifecycle events."""
    if lc_df.empty or "event_type" not in lc_df.columns:
        return []
    wl_events = lc_df[lc_df["event_type"] == EVENT_WL_ADDED]
    return sorted(list(wl_events[COL_SYMBOL].unique())) if not wl_events.empty else []


def _collect_valid_canonical_files() -> tuple[list[str], list[str]]:
    """Collect valid canonical forward return files and genuine trading dates, skipping holiday duplicates."""
    dates_map: dict[str, str] = {}
    for fpath in sorted(glob.glob("canonical_forward_returns_*.csv")):
        m = re.search(r"(\d{8})", os.path.basename(fpath))
        if not m:
            continue
        d_str = m.group(1)
        fname_date = f"{d_str[:4]}-{d_str[4:6]}-{d_str[6:]}"
        try:
            head_df = pd.read_csv(fpath, nrows=1)
        except Exception:
            LOGGER.exception("Lỗi khi đọc header từ %s", fpath)
            continue
        if head_df.empty:
            continue
        entry_t0 = str(head_df.get("entry_date_t0", pd.Series([fname_date])).iloc[0]).strip()
        if entry_t0 != fname_date:
            LOGGER.warning(
                "Bỏ qua tệp ngoại lệ/ngày lễ %s (entry_date_t0=%s khác tên tệp %s)",
                fpath,
                entry_t0,
                fname_date,
            )
            continue
        dates_map[entry_t0] = fpath

    sorted_dates = sorted(dates_map.keys())
    return sorted_dates, [dates_map[d] for d in sorted_dates]


def _get_trading_calendar() -> list[str]:
    """Extract sorted list of unique genuine trading dates (YYYY-MM-DD) from forward return CSVs."""
    sorted_dates, _ = _collect_valid_canonical_files()
    return sorted_dates


def _compute_watchlist_delta(target_date: str, current_watch_symbols: list[str]) -> dict[str, Any]:
    """Compute watchlist state delta compared to the immediate previous trading session with EOD decision records."""
    dec_dates: set[str] = set()
    for fpath in glob.glob("decision_records_*.csv"):
        m = re.search(r"(\d{8})", os.path.basename(fpath))
        if not m:
            continue
        d_str = m.group(1)
        dec_dates.add(f"{d_str[:4]}-{d_str[4:6]}-{d_str[6:]}")

    prior_dates = sorted(d for d in dec_dates if d < target_date)
    prev_date = prior_dates[-1] if prior_dates else None

    if not prev_date:
        return {"added": [], "removed": [], "prev_symbols": [], "prev_date": None}

    prev_dec_df = _load_decision_records(prev_date)
    prev_stats = _compute_eod_decisions(prev_dec_df)
    prev_watch = set(prev_stats.get("watch_symbols", []))
    curr_watch = set(current_watch_symbols)

    added = sorted(list(curr_watch - prev_watch))
    removed = sorted(list(prev_watch - curr_watch))
    return {
        "added": added,
        "removed": removed,
        "prev_symbols": sorted(list(prev_watch)),
        "prev_date": prev_date,
    }


def _load_target_date_prices(target_date: str) -> dict[str, float]:
    """Load symbol to close/price map for target_date if available."""
    d_code = target_date.replace("-", "")
    fwd_path = f"canonical_forward_returns_{d_code}.csv"
    if os.path.exists(fwd_path):
        try:
            tdf = pd.read_csv(fwd_path)
            if COL_SYMBOL in tdf.columns and "close_t0" in tdf.columns:
                return dict(zip(tdf[COL_SYMBOL], tdf["close_t0"].astype(float)))
        except Exception:
            LOGGER.exception("Lỗi khi đọc giá tham chiếu từ %s", fwd_path)

    dec_path = f"decision_records_{d_code}.csv"
    if os.path.exists(dec_path):
        try:
            ddf = pd.read_csv(dec_path)
            if COL_SYMBOL in ddf.columns and "price" in ddf.columns:
                return dict(zip(ddf[COL_SYMBOL], ddf["price"].astype(float)))
        except Exception:
            LOGGER.exception("Lỗi khi đọc giá tham chiếu từ %s", dec_path)
    return {}


def _horizon_sort_key(item: dict[str, Any]) -> int:
    """Sort key helper to order horizons numerically: T+1, T+3, T+5, T+10, T+20."""
    h_str = str(item.get("horizon", "T+0")).replace("T+", "").strip()
    try:
        return int(h_str)
    except ValueError:
        return 999


def _is_horizon_maturing_today(
    fwd_df: pd.DataFrame,
    horizon_num: int,
    target_date: str,
    vn_close_today: float | None,
    expected_exit_date: str | None,
    trading_calendar: list[str] | None = None,
) -> bool:
    """Check if a specific horizon (1, 3, 5, 10, 20) matured on target_date."""
    if not bool(fwd_df.get(f"matured_t{horizon_num}", pd.Series([False])).iloc[0]):
        return False

    # 1. Direct exit date column match
    ex_date = str(fwd_df.get(f"exit_date_t{horizon_num}", pd.Series([None])).iloc[0])
    if ex_date == target_date:
        return True

    # 1b. For T+1, entry_date_t1 is the executable entry / exit date
    if horizon_num == 1:
        t1_date = str(fwd_df.get("entry_date_t1", pd.Series([None])).iloc[0])
        if t1_date == target_date:
            return True

    # 2. Expected horizon date mapping match
    if expected_exit_date and expected_exit_date == target_date:
        return True

    # 3. Fallback: VN-Index close matching within tolerance
    if vn_close_today is not None and vn_close_today > 0:
        close_val = float(fwd_df.get(f"vn_close_t{horizon_num}", pd.Series([0.0])).iloc[0] or 0.0)
        if close_val > 0 and abs(close_val - vn_close_today) < 0.05:
            return True

    # 4. Trading calendar offset match (for T+10, T+20 when exit date column is omitted)
    if trading_calendar and "entry_date_t0" in fwd_df.columns:
        t0 = str(fwd_df["entry_date_t0"].iloc[0])
        if t0 in trading_calendar and target_date in trading_calendar:
            idx_t0 = trading_calendar.index(t0)
            idx_tgt = trading_calendar.index(target_date)
            if idx_tgt - idx_t0 == horizon_num:
                return True

    return False


def _calc_trimmed_mean(series: pd.Series, proportion: float = 0.10) -> float | None:
    """Calculate symmetric trimmed mean (cutting proportion from both ends)."""
    s = series.dropna().sort_values()
    n = len(s)
    if n == 0:
        return None
    k = int(n * proportion)
    if k > 0 and 2 * k < n:
        s = s.iloc[k:-k]
    return float(s.mean())


def _calc_bootstrap_diff_ci(
    w_vals: np.ndarray,
    r_vals: np.ndarray,
    n_boot: int = 1000,
    alpha: float = 0.05,
    random_state: int = 42,
) -> tuple[float, float, float]:
    """Calculate bootstrap standard error and 95% confidence interval for mean(w) - mean(r)."""
    if len(w_vals) == 0 or len(r_vals) == 0:
        return 0.0, 0.0, 0.0
    rng = np.random.default_rng(random_state)
    boot_diffs = np.empty(n_boot)
    for i in range(n_boot):
        b_w = rng.choice(w_vals, size=len(w_vals), replace=True)
        b_r = rng.choice(r_vals, size=len(r_vals), replace=True)
        boot_diffs[i] = b_w.mean() - b_r.mean()
    se = float(np.std(boot_diffs))
    ci_low = float(np.percentile(boot_diffs, 100 * (alpha / 2)))
    ci_high = float(np.percentile(boot_diffs, 100 * (1 - alpha / 2)))
    return se, ci_low, ci_high


def _calc_cohort_horizon_stats(
    fwd_df: pd.DataFrame,
    t0_date: str,
    horizon: str,
    exec_col: str,
    excess_col: str,
    price_map: dict[str, float] | None = None,
) -> dict[str, Any]:
    """Calculate comprehensive statistical distribution of executable forward returns for a cohort horizon."""
    watch_mask = fwd_df[COL_DECISION] == DEC_WATCH
    rej_mask = fwd_df[COL_DECISION] == DEC_REJECT

    has_exec = exec_col in fwd_df.columns and fwd_df[exec_col].notna().any()

    if has_exec:
        exec_s = fwd_df[exec_col]
    elif price_map and "open_t1" in fwd_df.columns:
        curr_p = fwd_df[COL_SYMBOL].map(price_map)
        open_p = fwd_df["open_t1"]
        valid = open_p.notna() & curr_p.notna() & (open_p > 0)
        exec_s = pd.Series(np.nan, index=fwd_df.index)
        exec_s[valid] = ((curr_p[valid] - open_p[valid]) / open_p[valid]) * 100.0
    else:
        exec_s = pd.Series(np.nan, index=fwd_df.index)

    valid_u = exec_s.dropna()
    u_n = len(valid_u)
    u_mean = float(valid_u.mean()) if u_n > 0 else None
    u_median = float(valid_u.median()) if u_n > 0 else None
    u_trimmed = _calc_trimmed_mean(valid_u, 0.10) if u_n > 0 else None
    u_win_rate = float((valid_u > 0).mean() * 100.0) if u_n > 0 else None

    # Watch stats
    w_valid = exec_s[watch_mask].dropna()
    w_n = len(w_valid)
    w_mean = float(w_valid.mean()) if w_n > 0 else None
    w_median = float(w_valid.median()) if w_n > 0 else None
    w_trimmed = _calc_trimmed_mean(w_valid, 0.10) if w_n > 0 else None
    w_win = float((w_valid > 0).mean() * 100.0) if w_n > 0 else None
    w_excess = float(w_mean - u_mean) if w_mean is not None and u_mean is not None else None

    # Reject stats
    r_valid = exec_s[rej_mask].dropna()
    r_n = len(r_valid)
    r_mean = float(r_valid.mean()) if r_n > 0 else None
    r_median = float(r_valid.median()) if r_n > 0 else None
    r_trimmed = _calc_trimmed_mean(r_valid, 0.10) if r_n > 0 else None
    r_win = float((r_valid > 0).mean() * 100.0) if r_n > 0 else None
    r_excess = float(r_mean - u_mean) if r_mean is not None and u_mean is not None else None

    # Bootstrap SE of difference (Watch - Reject)
    diff_mean = (w_mean - r_mean) if w_mean is not None and r_mean is not None else None
    diff_median = (w_median - r_median) if w_median is not None and r_median is not None else None
    boot_se, ci_low, ci_high = _calc_bootstrap_diff_ci(w_valid.values, r_valid.values, n_boot=1000)

    # Cash Defense vs Benchmarks
    cash_vs_u = -u_mean if u_mean is not None else None
    cash_vs_w = -w_mean if w_mean is not None else None

    return {
        "cohort_t0": t0_date,
        "horizon": horizon,
        "watch_n": w_n,
        "watch_exec": w_mean,
        "watch_median": w_median,
        "watch_trimmed": w_trimmed,
        "watch_win_rate": w_win,
        "watch_excess": w_excess,
        "rej_n": r_n,
        "rej_exec": r_mean,
        "rej_median": r_median,
        "rej_trimmed": r_trimmed,
        "rej_win_rate": r_win,
        "rej_excess": r_excess,
        "universe_n": u_n,
        "universe_exec": u_mean,
        "universe_median": u_median,
        "universe_trimmed": u_trimmed,
        "universe_win_rate": u_win_rate,
        "diff_mean": diff_mean,
        "diff_median": diff_median,
        "boot_se": boot_se,
        "ci_low": ci_low,
        "ci_high": ci_high,
        "cash_vs_u": cash_vs_u,
        "cash_vs_w": cash_vs_w,
    }


def _inspect_cohort_maturity(
    fwd_df: pd.DataFrame,
    target_date: str,
    vn_close_today: float | None,
    calendar: list[str] | None = None,
    price_map: dict[str, float] | None = None,
) -> list[dict[str, Any]]:
    """Inspect forward returns dataframe to detect which horizons matured on target_date."""
    results: list[dict[str, Any]] = []
    if fwd_df.empty or "entry_date_t0" not in fwd_df.columns:
        return results

    t0_date = str(fwd_df["entry_date_t0"].iloc[0])
    d_code = t0_date.replace("-", "")

    expected_h_dates: dict[int, str] = {}
    try:
        from scripts.enrich_forward_returns_valuation_events import TARGET_DATES_HORIZONS

        expected_h_dates = TARGET_DATES_HORIZONS.get(d_code, {})
    except Exception:
        pass

    for h in DIGEST_HORIZONS:
        exp_d = expected_h_dates.get(h)
        if _is_horizon_maturing_today(fwd_df, h, target_date, vn_close_today, exp_d, trading_calendar=calendar):
            results.append(_calc_cohort_horizon_stats(
                fwd_df,
                t0_date,
                f"T+{h}",
                f"exec_t{h}_pct",
                f"excess_vs_universe_t{h}_pct",
                price_map=price_map,
            ))

    return results


def _find_maturing_cohorts(target_date: str, vn_close_today: float | None) -> list[dict[str, Any]]:
    """Scan valid canonical forward return files and find horizons maturing today."""
    calendar, fwd_files = _collect_valid_canonical_files()
    cohort_stats: list[dict[str, Any]] = []
    price_map = _load_target_date_prices(target_date)

    for fpath in fwd_files:
        try:
            df = pd.read_csv(fpath)
            stats = _inspect_cohort_maturity(df, target_date, vn_close_today, calendar=calendar, price_map=price_map)
            cohort_stats.extend(stats)
        except Exception:
            LOGGER.exception("Lỗi khi đọc file forward returns: %s", fpath)

    cohort_stats.sort(key=_horizon_sort_key)
    return cohort_stats


def _format_section_4_anomalies(cohorts: list[dict[str, Any]], stats: dict[str, Any], delta_info: dict[str, Any]) -> list[str]:
    """Format Section 4 with rigorous statistical anomalies and question framing."""
    lines = [
        "### 4. BẤT THƯỜNG ĐỊNH LƯỢNG (ANOMALIES) & CÂU HỎI NGHIÊN CỨU CHO CLAUDE",
    ]

    if cohorts:
        lines.append("| Kỳ hạn | Diff Mean (W − R) | Diff Median | Bootstrap SE | 95% CI Bootstrap | Trạng thái Thống kê |")
        lines.append("| :--- | :---: | :---: | :---: | :---: | :---: |")
        for c in cohorts:
            dm_val = c.get("diff_mean")
            if dm_val is None and c.get("watch_exec") is not None and c.get("rej_exec") is not None:
                dm_val = c["watch_exec"] - c["rej_exec"]
            dm = f"{dm_val:+.2f}%" if dm_val is not None else "N/A"

            dmed_val = c.get("diff_median")
            if dmed_val is None and c.get("watch_median") is not None and c.get("rej_median") is not None:
                dmed_val = c["watch_median"] - c["rej_median"]
            dmed = f"{dmed_val:+.2f}%" if dmed_val is not None else "N/A"

            boot_se = c.get("boot_se", 0.0)
            se_str = f"{boot_se:.2f}%" if boot_se is not None else "N/A"

            ci_l = c.get("ci_low", 0.0)
            ci_h = c.get("ci_high", 0.0)
            ci_str = f"[{ci_l:+.2f}%, {ci_h:+.2f}%]" if c.get("ci_low") is not None else "N/A"

            # Unified noise flag criterion: 0 outside 95% Bootstrap Confidence Interval
            if ci_l is not None and ci_h is not None and (ci_l > 0 or ci_h < 0):
                status = "**Ngoài biên nhiễu**"
            else:
                status = "Trong biên nhiễu (0 ∈ 95% CI)"
            lines.append(f"| **{c.get('horizon', 'T+?')}** ({c.get('cohort_t0', 'N/A')}) | **{dm}** | {dmed} | {se_str} | {ci_str} | {status} |")
        lines.append("")
        lines.append("*(Ghi chú phương pháp luận: Tiêu chuẩn cờ nhiễu duy nhất: Nhãn 'Ngoài biên nhiễu' khi 0 nằm ngoài Khoảng tin cậy Bootstrap 95% [CI_low, CI_high]. Lưu ý chưa hiệu chỉnh đa kiểm định (multi-testing correction); các kỳ hạn T+1, T+3, T+5, T+10 cùng kết thúc phiên hôm nay là các cửa sổ thời gian chồng lấn (overlapping windows), không được coi là các quan sát độc lập.)*")
        lines.append("")

    q_idx = 1
    # Check if there is any signal outside noise based on 95% CI
    outliers = [c for c in cohorts if c.get("ci_low") is not None and c.get("ci_high") is not None and (c["ci_low"] > 0 or c["ci_high"] < 0)]
    if outliers:
        h_names = ", ".join(o["horizon"] for o in outliers)
        lines.append(f"{q_idx}. **Kiểm định hiện tượng phân kỳ ngoài nhiễu ({len(outliers)}/{len(cohorts)} cờ):** Kỳ hạn {h_names} ghi nhận độ lệch giữa WATCH và REJECT vượt ngoài biên nhiễu (0 nằm ngoài 95% CI Bootstrap). Cần lưu ý chưa hiệu chỉnh đa kiểm định khi diễn giải kết quả.")
        q_idx += 1
    else:
        lines.append(f"{q_idx}. **Độ lệch trong biên nhiễu:** Toàn bộ chênh lệch giữa WATCH và REJECT tại các mốc đáo hạn hôm nay đều nằm trong biên nhiễu (0 nằm trong Khoảng tin cậy Bootstrap 95%, tương thích với giả thuyết không có sự khác biệt có ý nghĩa thống kê trên mẫu đơn lẻ). Cần tiếp tục theo dõi qua các chuỗi cohort rời nhau.")
        q_idx += 1

    if stats["buy"] == 0:
        lines.append(f"{q_idx}. **Đánh giá hiệu quả phòng vệ Tiền mặt (BUY = 0):** Trong Downtrend, hệ thống nắm giữ 100% tiền mặt. Đối chiếu mức lợi suất của Tiền mặt (0.0%) so với đà giảm của Universe để đánh giá mức độ bảo toàn vốn qua từng chu kỳ.")
        q_idx += 1

    watch_cnt = stats["watch"]
    lines.append(f"{q_idx}. **Hành động tiếp theo:** Với danh sách {watch_cnt} mã trong Watchlist tại EOD, nhóm ngành nào (Bank, Bất động sản, Sản xuất) có xác suất xác nhận ngừng rơi sớm nhất?")
    lines.append("")
    return lines


def _format_markdown_report(
    target_date: str,
    regime: dict[str, Any],
    stats: dict[str, Any],
    cohorts: Any,
    delta_info: Any = None,
    missing_data_symbols: list[str] | None = None,
) -> str:
    """Assemble final clean Markdown briefing for Claude / AI Analyst."""
    if isinstance(cohorts, list) and cohorts and isinstance(cohorts[0], str):
        wl_symbols = cohorts
        actual_cohorts = delta_info if isinstance(delta_info, list) else []
        actual_delta = {"added": [], "removed": [], "prev_symbols": []}
        if not stats.get("watch_symbols"):
            stats["watch_symbols"] = wl_symbols
    else:
        actual_cohorts = cohorts if isinstance(cohorts, list) else []
        actual_delta = delta_info if isinstance(delta_info, dict) else {"added": [], "removed": [], "prev_symbols": []}
    lines: list[str] = [
        f"# DAILY QUANT RESEARCH BRIEFING — {target_date}",
        "",
    ]

    # Prominent Data Gate Warning if data is incomplete
    if missing_data_symbols:
        lines.append(f"> [!WARNING] **CẢNH BÁO DATA GATE:** Dữ liệu universe chưa trọn vẹn ({EXPECTED_UNIVERSE_SIZE - len(missing_data_symbols)}/{EXPECTED_UNIVERSE_SIZE} mã). Các mã thiếu: {', '.join(missing_data_symbols)}.")
        lines.append("")

    if regime.get("fallback_warning"):
        lines.append(f"> [!WARNING] **CẢNH BÁO REGIME:** Thiếu dữ liệu phiên EOD_CANONICAL, hệ thống phải trích xuất từ phiên `{regime['fallback_warning']}`. Chỉ số thị trường và trạng thái MA200 có thể bị lệch 1 phiên so với diễn biến cuối ngày!")
        lines.append("")

    lines.append("### 1. BỐI CẢNH THỊ TRƯỜNG & HỆ THỐNG (REGIME CONTEXT)")
    p_val = f"{regime['vnindex_price']:.2f}" if regime["vnindex_price"] else "N/A"
    ma_val = f"{regime['vnindex_ma200']:.2f}" if regime["vnindex_ma200"] else "N/A"
    gap_val = f"{regime['vnindex_vs_ma200_pct']:+.2f}%" if regime["vnindex_vs_ma200_pct"] is not None else "N/A"

    lines.append(f"- **Market Regime:** `{regime['regime']}` (VN-Index: {p_val} | MA200: {ma_val} | vs MA200: {gap_val})")
    lines.append(f"- **System Freeze Version:** Logic `{regime['logic_version']}` | Model `{regime['model_version']}` | Commit `{regime['git_sha']}`")
    lines.append("")

    lines.append(f"### 2. QUYẾT ĐỊNH CUỐI PHIÊN HÔM NAY (EOD CANONICAL T0 - {stats['total']} MÃ)")
    tot = max(stats["total"], 1)
    b_pct = (stats["buy"] / tot) * 100
    w_pct = (stats["watch"] / tot) * 100
    r_pct = (stats["reject"] / tot) * 100

    lines.append(f"- **Phân bổ:** BUY: **{stats['buy']}** ({b_pct:.1f}%) | WATCH: **{stats['watch']}** ({w_pct:.1f}%) | REJECT: **{stats['reject']}** ({r_pct:.1f}%)")

    gates_str = ", ".join(f"`{k}`: {v}" for k, v in stats["gates"].items()) if stats["gates"] else "Không có"
    lines.append(f"- **Cổng loại trừ chính (Top Rejection Gates):** {gates_str}")

    watch_syms = stats.get("watch_symbols", [])
    wl_display = ", ".join(f"`{s}`" for s in watch_syms) if watch_syms else "Không có mã"
    lines.append(f"- **Danh mục WATCHLIST tại EOD ({len(watch_syms)} mã):** {wl_display}")

    # Watchlist delta string
    delta_parts = []
    if actual_delta.get("added"):
        delta_parts.append(f"[+ Thêm mới: {', '.join(f'`{s}`' for s in delta_info['added'])}]")
    if actual_delta.get("removed"):
        delta_parts.append(f"[- Loại bỏ: {', '.join(f'`{s}`' for s in delta_info['removed'])}]")
    if not delta_parts:
        delta_str = "[Không có biến động so với phiên trước]"
    else:
        delta_str = " ".join(delta_parts)

    prev_lbl = f"so với {delta_info['prev_date']}" if actual_delta.get("prev_date") else "so với phiên trước"
    lines.append(f"- **Biến động trạng thái ({prev_lbl}):** {delta_str}")
    lines.append("")

    lines.append("### 3. ĐO LƯỜNG KẾT QUẢ ĐA KỲ (MULTI-COHORT FORWARD RETURNS ĐÁO HẠN HÔM NAY)")
    if actual_cohorts:
        lines.append("| Kỳ hạn | Cohort T0 | Nhóm | N | Exec Mean (%) | Median (%) | Trimmed 10% (%) | Win Rate (%) | Excess vs Universe (%) |")
        lines.append("| :--- | :---: | :--- | :---: | :---: | :---: | :---: | :---: | :---: |")
        for c in actual_cohorts:
            w_m = f"{c.get('watch_exec'):+.2f}%" if c.get("watch_exec") is not None else "N/A"
            w_med = f"{c.get('watch_median'):+.2f}%" if c.get("watch_median") is not None else "N/A"
            w_tri = f"{c.get('watch_trimmed'):+.2f}%" if c.get("watch_trimmed") is not None else "N/A"
            w_win = f"{c.get('watch_win_rate'):.1f}%" if c.get("watch_win_rate") is not None else "N/A"
            w_exc = f"{c.get('watch_excess'):+.2f}%" if c.get("watch_excess") is not None else "N/A"

            r_m = f"{c.get('rej_exec'):+.2f}%" if c.get("rej_exec") is not None else "N/A"
            r_med = f"{c.get('rej_median'):+.2f}%" if c.get("rej_median") is not None else "N/A"
            r_tri = f"{c.get('rej_trimmed'):+.2f}%" if c.get("rej_trimmed") is not None else "N/A"
            r_win = f"{c.get('rej_win_rate'):.1f}%" if c.get("rej_win_rate") is not None else "N/A"
            r_exc = f"{c.get('rej_excess'):+.2f}%" if c.get("rej_excess") is not None else "N/A"

            u_m = f"{c.get('universe_exec'):+.2f}%" if c.get("universe_exec") is not None else "N/A"
            u_med = f"{c.get('universe_median'):+.2f}%" if c.get("universe_median") is not None else "N/A"
            u_tri = f"{c.get('universe_trimmed'):+.2f}%" if c.get("universe_trimmed") is not None else "N/A"
            u_win = f"{c.get('universe_win_rate'):.1f}%" if c.get("universe_win_rate") is not None else "N/A"

            u_n = c.get('universe_n', EXPECTED_UNIVERSE_SIZE)
            cash_vs_u_val = c.get('cash_vs_u')
            cash_vs_u_str = f"Phòng vệ vs Universe: {cash_vs_u_val:+.2f}%" if cash_vs_u_val is not None else "N/A"

            lines.append(f"| **{c['horizon']}** đáo hạn hôm nay | {c['cohort_t0']} | **WATCH** | {c['watch_n']} | **{w_m}** | {w_med} | {w_tri} | {w_win} | **{w_exc}** |")
            lines.append(f"| | {c['cohort_t0']} | **REJECT** | {c['rej_n']} | **{r_m}** | {r_med} | {r_tri} | {r_win} | **{r_exc}** |")
            lines.append(f"| | {c['cohort_t0']} | **Universe (55 mã)** | {u_n} | {u_m} | {u_med} | {u_tri} | {u_win} | 0.00% |")
            lines.append(f"| | {c['cohort_t0']} | **Tiền mặt (BUY=0)** | — | **0.00%** | 0.00% | 0.00% | — | *{cash_vs_u_str}* |")
        lines.append("")
        lines.append("> **Quy ước & Chú thích kỹ thuật:**")
        lines.append("> - **Định nghĩa Exec Return:** `(Close_T+h − Open_T+1) / Open_T+1 × 100%`. Vào lệnh tại giá Mở cửa ngày T+1, đóng vị thế tại giá Đóng cửa ngày T+h. Chưa trừ thuế & phí giao dịch ước tính (0.40%).")
        lines.append("> - **Universe Benchmark:** Tính trung bình đều (Equal-Weighted, 55 mã), kèm Median và Trimmed Mean (cắt 10% hai đầu). Khác với VN-Index vốn được tính theo trọng số vốn hóa (Market-cap Weighted).")
        lines.append("> - **Đo lường Cổng an toàn:** Hiệu quả của cổng chặn Mua (BUY=0) được đo bằng lợi suất Tiền mặt (0.00%) so với đà giảm của Universe/WATCH.")
    else:
        lines.append("*Không có cohort nào chạm mốc đáo hạn trong phiên hôm nay.*")
    lines.append("")

    lines.extend(_format_section_4_anomalies(actual_cohorts, stats, actual_delta))
    return "\n".join(lines)


def generate_digest(
    target_date: str,
    skip_sync: bool = False,
    skip_export: bool = False,
    skip_returns: bool = False,
    sync_db: bool = True,
    output_dir: str = "reports",
    skip_stage2: bool = False,
) -> str:
    """Generate daily research digest end-to-end and save to file."""
    LOGGER.info("=== BẮT ĐẦU TẠO BÁO CÁO DAILY RESEARCH DIGEST CHO NGÀY: %s ===", target_date)

    if not skip_sync:
        run_pipeline_sync(
            target_date,
            skip_export=skip_export,
            skip_returns=skip_returns,
            sync_db=sync_db,
            skip_stage2=skip_stage2,
        )

    dec_df = _load_decision_records(target_date)

    regime = _extract_regime_and_version(dec_df)
    decision_stats = _compute_eod_decisions(dec_df)
    delta_info = _compute_watchlist_delta(target_date, decision_stats.get("watch_symbols", []))

    # Data Gate validation on target date forward returns file
    d_code = target_date.replace("-", "")
    fwd_today_path = f"canonical_forward_returns_{d_code}.csv"
    missing_data_symbols: list[str] = []
    vn_close_today: float | None = None

    if os.path.exists(fwd_today_path):
        try:
            today_fwd = pd.read_csv(fwd_today_path)
            if "symbol" in today_fwd.columns and len(today_fwd) < EXPECTED_UNIVERSE_SIZE:
                dec_syms = set(decision_stats.get("watch_symbols", []) + [r.get("symbol") for _, r in dec_df.iterrows() if r.get("symbol")])
                missing_data_symbols = sorted(list(dec_syms - set(today_fwd["symbol"])))
                LOGGER.warning("Data Gate: File %s chỉ có %d/%d mã! Thiếu: %s", fwd_today_path, len(today_fwd), EXPECTED_UNIVERSE_SIZE, missing_data_symbols)
            if "vn_close_t0" in today_fwd.columns and not today_fwd.empty:
                vn_close_today = float(today_fwd["vn_close_t0"].iloc[0])
        except Exception:
            LOGGER.exception("Lỗi khi đọc %s", fwd_today_path)

    if vn_close_today is None:
        for f in glob.glob("canonical_forward_returns_*.csv"):
            try:
                cf = pd.read_csv(f)
                if cf.get("entry_date_t1", pd.Series([None])).iloc[0] == target_date:
                    vn_close_today = float(cf["vn_close_t1"].iloc[0])
                    break
            except Exception:
                continue

    cohort_stats = _find_maturing_cohorts(target_date, vn_close_today)

    report_content = _format_markdown_report(
        target_date,
        regime,
        decision_stats,
        cohort_stats,
        delta_info,
        missing_data_symbols=missing_data_symbols,
    )

    if not re.fullmatch(r"\d{8}", d_code):
        raise ValueError(f"Invalid target_date format: {target_date}")
    base_real = os.path.realpath(output_dir)
    cwd_real = os.path.realpath(os.getcwd())
    tmp_real = os.path.realpath(tempfile.gettempdir())
    if not (
        base_real == cwd_real
        or base_real.startswith(cwd_real + os.sep)
        or base_real == tmp_real
        or base_real.startswith(tmp_real + os.sep)
    ):
        raise ValueError(f"Unsafe output_dir: {output_dir}")
    os.makedirs(base_real, exist_ok=True)
    out_file = os.path.realpath(os.path.join(base_real, f"daily_digest_{d_code}.md"))
    if not out_file.startswith(base_real + os.sep):
        raise ValueError(f"Unsafe output path: {out_file}")
    with open(out_file, "w", encoding="utf-8") as f:
        f.write(report_content)

    LOGGER.info("[✓] ĐÃ TẠO BÁO CÁO THÀNH CÔNG: %s (%d dòng)", out_file, len(report_content.splitlines()))
    return out_file


def main() -> None:
    """CLI Entrypoint."""
    parser = argparse.ArgumentParser(description="Automated Daily Quant Research Digest Generator.")
    parser.add_argument("date", nargs="?", default=None, help="Target date in YYYY-MM-DD or YYYYMMDD format. Default is today.")
    parser.add_argument("--date", "-d", dest="flag_date", default=None, help="Explicit target date flag.")
    parser.add_argument("--skip-sync", action="store_true", help="Skip running export_today_csv and update_forward_returns.")
    parser.add_argument("--skip-export", action="store_true", help="Skip running export_today_csv.")
    parser.add_argument("--skip-returns", action="store_true", help="Skip running update_forward_returns.")
    parser.add_argument("--skip-stage2", action="store_true", help="Skip running Stage 2 raw-score shadow logger.")
    parser.add_argument("--skip-db", "--no-db", dest="skip_db", action="store_true", help="Bỏ qua cập nhật bảng Supabase DB.")
    parser.add_argument("--sync-db", dest="sync_db", action="store_true", default=None, help="Đồng bộ kết quả forward returns lên Supabase (mặc định bật).")
    parser.add_argument("--output-dir", default="reports", help="Output directory for reports (default: reports).")
    args = parser.parse_args()

    raw_date = args.flag_date or args.date or get_default_vn_date()
    raw_date = raw_date.strip()
    if len(raw_date) == 8 and raw_date.isdigit():
        target_date = f"{raw_date[:4]}-{raw_date[4:6]}-{raw_date[6:]}"
    else:
        target_date = raw_date
    datetime.strptime(target_date, "%Y-%m-%d")

    cwd_real = os.path.realpath(os.getcwd())
    safe_out_dir = os.path.realpath(os.path.join(cwd_real, args.output_dir))
    if os.path.commonpath([cwd_real, safe_out_dir]) != cwd_real:
        raise ValueError(f"Unsafe output directory: {args.output_dir}")

    sync_db_flag = False if args.skip_db else True

    out_path = generate_digest(
        target_date=target_date,
        skip_sync=args.skip_sync,
        skip_export=args.skip_export,
        skip_returns=args.skip_returns,
        sync_db=sync_db_flag,
        output_dir=safe_out_dir,
        skip_stage2=args.skip_stage2,
    )
    print("\n" + "=" * 70)
    print(f"BÁO CÁO ĐÃ SẴN SÀNG CHO CLAUDE: {out_path}")
    print("=" * 70)


if __name__ == "__main__":
    main()
