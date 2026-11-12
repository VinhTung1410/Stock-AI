# -*- coding: utf-8 -*-
"""Independent 30-Session Audit Engine for v15.0_frozen_20261013.

Read-only analytical audit over canonical_forward_returns_*.csv and reports/daily_digest_*.md:
1. Non-overlapping T+5 chains & T+1/T+3/T+5/T+10/T+20 horizon summaries.
2. Day-level IID & Moving-Block Bootstrap (L=5) confidence intervals.
3. Half-sample sign consistency check (<= 2026-10-23 vs >= 2026-10-26).
4. Within-sector stratification (Ngân hàng vs Phi ngân hàng), Leave-top-2-out,
   and Leave-Real-Estate-Out (Bất động sản dân dụng) concentration checks.
5. Unicode NFC & sector integrity assertions (fail loudly on missing/mismatched sector data).
6. Version sensitivity check excluding 2026-10-14 & Pure Out-of-Sample Appendix (T0 >= 2026-11-13).
7. Executable absolute returns net of 0.40% transaction cost & Watchlist churn statistics.
"""

from __future__ import annotations

import argparse
import glob
import logging
import math
import os
import re
import sys
import unicodedata
from typing import Any

import numpy as np
import pandas as pd

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
LOGGER = logging.getLogger("audit_30_sessions")

# SonarCloud S1192 Constants
DEC_WATCH = "WATCH"
DEC_REJECT = "REJECT"
COL_DECISION = "decision"
COL_SYMBOL = "symbol"
COL_SECTOR = "sector"
COL_ENTRY_T0 = "entry_date_t0"
SECTOR_BANK = unicodedata.normalize("NFC", "Ngân hàng")
SECTOR_NON_BANK = "Phi ngân hàng"
SECTOR_RES_RE = unicodedata.normalize("NFC", "Bất động sản dân dụng")
DEFAULT_FEE_PCT = 0.40
DEFAULT_EXCLUDE_DATE = "2026-10-14"
DEFAULT_HALF_SPLIT_DATE = "2026-10-23"
DEFAULT_POST_PREREG_START = "2026-11-13"
DEFAULT_BLOCK_LEN = 5
DEFAULT_N_BOOT = 5000
DEFAULT_SEED = 42
MIN_CHAINS_ABOVE_FEE = 3
MIN_BANK_SYMBOLS_IN_UNIVERSE = 8

VERDICT_PASS = "PASS (Đủ điều kiện chuyển sang Giai đoạn 2)"
VERDICT_CONDITIONAL = "REGIME-CONDITIONAL / SECTOR-DRIVEN"
VERDICT_FAIL = "FAIL / INCONCLUSIVE (Không chứng minh được edge vượt ngưỡng trong 30 phiên)"


def _normalize_nfc(value: Any) -> str:
    """Normalize text strings to Unicode NFC for reliable Vietnamese sector matching."""
    return unicodedata.normalize("NFC", str(value).strip())


def validate_sector_integrity(df: pd.DataFrame, min_bank_symbols: int = MIN_BANK_SYMBOLS_IN_UNIVERSE) -> None:
    """Fail loudly if sector column is missing or banking sector mapping broke (e.g. NFC/NFD mismatch)."""
    if df.empty:
        return
    if COL_SECTOR not in df.columns:
        raise ValueError(f"Thiếu cột bắt buộc '{COL_SECTOR}' trong dữ liệu canonical forward returns.")

    n_symbols = df[COL_SYMBOL].nunique() if COL_SYMBOL in df.columns else 0
    bank_rows = df[df[COL_SECTOR] == SECTOR_BANK]
    n_bank_syms = bank_rows[COL_SYMBOL].nunique() if COL_SYMBOL in bank_rows.columns else len(bank_rows)

    if n_symbols >= 20 and n_bank_syms < min_bank_symbols:
        raise ValueError(
            f"Cảnh báo lỗi hạ tầng ngành: chỉ tìm thấy {n_bank_syms} mã '{SECTOR_BANK}' "
            f"(kỳ vọng >= {min_bank_symbols} trên universe {n_symbols} mã)."
        )
    if n_bank_syms == 0:
        raise ValueError(f"Không tìm thấy bất kỳ mã nào thuộc ngành '{SECTOR_BANK}'.")


def load_canonical_returns(data_dir: str = ".") -> pd.DataFrame:
    """Load and concatenate canonical_forward_returns_*.csv files with NFC sector normalization."""
    pattern = os.path.join(data_dir, "canonical_forward_returns_*.csv")
    files = sorted(glob.glob(pattern))
    frames: list[pd.DataFrame] = []
    for fpath in files:
        try:
            df = pd.read_csv(fpath)
            if not df.empty:
                if COL_SECTOR in df.columns:
                    df[COL_SECTOR] = df[COL_SECTOR].map(_normalize_nfc)
                frames.append(df)
        except Exception:
            LOGGER.exception("Lỗi khi đọc tệp canonical forward returns: %s", fpath)
    if not frames:
        return pd.DataFrame()
    combined = pd.concat(frames, ignore_index=True)
    validate_sector_integrity(combined)
    return combined


def parse_digest_reports(reports_dir: str = "reports") -> dict[str, Any]:
    """Parse horizon spreads, statistical flags, and BUY counts from daily_digest_*.md files."""
    pattern = os.path.join(reports_dir, "daily_digest_2026*.md")
    files = sorted(glob.glob(pattern))
    horizon_rows: list[dict[str, Any]] = []
    buy_counts: list[int] = []
    gaps: list[float] = []

    for fpath in files:
        try:
            with open(fpath, encoding="utf-8") as fh:
                content = fh.read()
        except Exception:
            LOGGER.exception("Lỗi khi đọc digest: %s", fpath)
            continue

        m_cnt = re.search(r"BUY:\s*\*\*(\d+)\*\*", content)
        if m_cnt:
            buy_counts.append(int(m_cnt.group(1)))

        m_gap = re.search(r"vs MA200:\s*([+\-\d.]+)%", content)
        if m_gap:
            gaps.append(float(m_gap.group(1)))

        for line in content.splitlines():
            m = re.match(
                r"\|\s*\*\*T\+(\d+)\*\*\s*\((\d{4}-\d{2}-\d{2})\)\s*\|\s*\*\*([+\-\d.]+)%\*\*\s*\|.*\|\s*(.+?)\s*\|$",
                line,
            )
            if m:
                horizon_rows.append({
                    "horizon": int(m.group(1)),
                    COL_ENTRY_T0: m.group(2),
                    "diff_mean": float(m.group(3)),
                    "is_flagged": "Ngoài biên nhiễu" in m.group(4),
                })

    return {
        "n_sessions": len(files),
        "horizon_df": pd.DataFrame(horizon_rows),
        "buy_nonzero_days": sum(1 for b in buy_counts if b > 0),
        "min_gap_pct": min(gaps) if gaps else None,
        "max_gap_pct": max(gaps) if gaps else None,
    }


def compute_cohort_spread_df(df: pd.DataFrame, horizon: int = 5) -> pd.DataFrame:
    """Compute per-cohort WATCH, REJECT, Universe means and W-R spread for a matured horizon."""
    matured_col = f"matured_t{horizon}"
    exec_col = f"exec_t{horizon}_pct"
    if df.empty or matured_col not in df.columns or exec_col not in df.columns:
        return pd.DataFrame()

    matured = df[df[matured_col] == True]  # noqa: E712
    if matured.empty:
        return pd.DataFrame()

    piv = matured.groupby([COL_ENTRY_T0, COL_DECISION])[exec_col].mean().unstack()
    univ = matured.groupby(COL_ENTRY_T0)[exec_col].mean()

    if DEC_WATCH not in piv.columns or DEC_REJECT not in piv.columns:
        return pd.DataFrame()

    out = pd.DataFrame({
        "watch_mean": piv[DEC_WATCH],
        "reject_mean": piv[DEC_REJECT],
        "universe_mean": univ,
    }).dropna()
    out["diff_w_r"] = out["watch_mean"] - out["reject_mean"]
    return out.sort_index()


def compute_non_overlapping_chains(
    spread_series: pd.Series,
    step: int = DEFAULT_BLOCK_LEN,
    fee_pct: float = DEFAULT_FEE_PCT,
) -> list[dict[str, Any]]:
    """Split a chronological cohort spread series into staggered non-overlapping chains."""
    s = spread_series.dropna().sort_index()
    if s.empty:
        return []

    chains: list[dict[str, Any]] = []
    for offset in range(step):
        sub = s.iloc[offset::step]
        if sub.empty:
            continue
        mean_val = float(sub.mean())
        chains.append({
            "chain_id": offset + 1,
            "dates": list(sub.index),
            "values": [float(v) for v in sub.values],
            "n": len(sub),
            "mean": mean_val,
            "above_fee": mean_val > fee_pct,
        })
    return chains


def compute_block_bootstrap_ci(
    values: np.ndarray,
    block_len: int = DEFAULT_BLOCK_LEN,
    n_boot: int = DEFAULT_N_BOOT,
    alpha: float = 0.05,
    seed: int = DEFAULT_SEED,
) -> dict[str, float | None]:
    """Compute day-level IID and moving-block bootstrap confidence intervals."""
    arr = np.asarray(values, dtype=float)
    arr = arr[~np.isnan(arr)]
    n = len(arr)
    if n == 0:
        return {
            "mean": None,
            "iid_ci_low": None,
            "iid_ci_high": None,
            "block_se": None,
            "block_ci_low": None,
            "block_ci_high": None,
        }

    rng = np.random.default_rng(seed)
    iid_means = np.array([rng.choice(arr, size=n, replace=True).mean() for _ in range(n_boot)])

    eff_len = min(max(block_len, 1), n)
    blocks = [arr[i : i + eff_len] for i in range(n - eff_len + 1)]
    n_blocks = int(math.ceil(n / eff_len))
    block_means = np.empty(n_boot)
    for idx in range(n_boot):
        chosen = rng.integers(0, len(blocks), size=n_blocks)
        sampled = np.concatenate([blocks[c] for c in chosen])[:n]
        block_means[idx] = sampled.mean()

    low_q = 100.0 * (alpha / 2.0)
    high_q = 100.0 * (1.0 - alpha / 2.0)
    return {
        "mean": float(arr.mean()),
        "iid_ci_low": float(np.percentile(iid_means, low_q)),
        "iid_ci_high": float(np.percentile(iid_means, high_q)),
        "block_se": float(np.std(block_means)),
        "block_ci_low": float(np.percentile(block_means, low_q)),
        "block_ci_high": float(np.percentile(block_means, high_q)),
    }


def compute_half_sample_stats(
    spread_df: pd.DataFrame,
    split_date: str = DEFAULT_HALF_SPLIT_DATE,
) -> dict[str, Any]:
    """Check sign consistency between first half (<= split_date) and second half (> split_date)."""
    if spread_df.empty:
        return {
            "split_date": split_date,
            "half1_n": 0,
            "half1_mean": None,
            "half2_n": 0,
            "half2_mean": None,
            "opposite_halves": False,
        }

    h1 = spread_df[spread_df.index <= split_date]["diff_w_r"]
    h2 = spread_df[spread_df.index > split_date]["diff_w_r"]
    h1_mean = float(h1.mean()) if not h1.empty else None
    h2_mean = float(h2.mean()) if not h2.empty else None
    opposite = (h1_mean is not None and h2_mean is not None) and ((h1_mean * h2_mean) < 0.0)
    return {
        "split_date": split_date,
        "half1_n": len(h1),
        "half1_mean": h1_mean,
        "half2_n": len(h2),
        "half2_mean": h2_mean,
        "opposite_halves": opposite,
    }


def _summarize_group_spread(sub_df: pd.DataFrame, horizon: int) -> dict[str, Any]:
    """Compute cohort-equal-weighted WATCH vs REJECT spread for a subset dataframe."""
    spread_df = compute_cohort_spread_df(sub_df, horizon=horizon)
    if spread_df.empty:
        return {"n_cohorts": 0, "mean_watch": None, "mean_reject": None, "mean_diff": None, "pos_count": 0}
    diffs = spread_df["diff_w_r"]
    return {
        "n_cohorts": len(spread_df),
        "mean_watch": float(spread_df["watch_mean"].mean()),
        "mean_reject": float(spread_df["reject_mean"].mean()),
        "mean_diff": float(diffs.mean()),
        "pos_count": int((diffs > 0).sum()),
    }


def compute_within_sector_stats(df: pd.DataFrame, horizon: int = 5) -> dict[str, dict[str, Any]]:
    """Evaluate WATCH vs REJECT spread separately inside Banking and Non-Banking subsets."""
    if df.empty:
        return {SECTOR_BANK: _summarize_group_spread(pd.DataFrame(), horizon), SECTOR_NON_BANK: _summarize_group_spread(pd.DataFrame(), horizon)}

    validate_sector_integrity(df)
    norm_sector = df[COL_SECTOR].map(_normalize_nfc)
    bank_df = df[norm_sector == SECTOR_BANK]
    non_bank_df = df[norm_sector != SECTOR_BANK]
    return {
        SECTOR_BANK: _summarize_group_spread(bank_df, horizon),
        SECTOR_NON_BANK: _summarize_group_spread(non_bank_df, horizon),
    }


def compute_leave_sector_out(
    df: pd.DataFrame,
    sector_name: str = SECTOR_RES_RE,
    horizon: int = 5,
) -> dict[str, Any]:
    """Check whether T+h W-R spread holds when residential real estate is excluded."""
    if df.empty:
        return {"sector_excluded": sector_name, "ex_watch_diff": None, "ex_both_diff": None}

    validate_sector_integrity(df)
    target_sec = _normalize_nfc(sector_name)
    norm_sector = df[COL_SECTOR].map(_normalize_nfc)

    ex_watch_df = df[~((df[COL_DECISION] == DEC_WATCH) & (norm_sector == target_sec))]
    ex_both_df = df[norm_sector != target_sec]

    sp_watch = compute_cohort_spread_df(ex_watch_df, horizon=horizon)
    sp_both = compute_cohort_spread_df(ex_both_df, horizon=horizon)

    return {
        "sector_excluded": target_sec,
        "ex_watch_diff": float(sp_watch["diff_w_r"].mean()) if not sp_watch.empty else None,
        "ex_both_diff": float(sp_both["diff_w_r"].mean()) if not sp_both.empty else None,
    }


def compute_concentration_sensitivity(df: pd.DataFrame, horizon: int = 5, top_k: int = 2) -> dict[str, Any]:
    """Measure leave-top-k-WATCH-contributors-out (by cumulative cohort sum) on T+h W-R spread."""
    matured_col = f"matured_t{horizon}"
    exec_col = f"exec_t{horizon}_pct"
    if df.empty or matured_col not in df.columns or exec_col not in df.columns:
        return {"top_contributors": [], "base_diff": None, "trimmed_diff": None}

    matured = df[df[matured_col] == True]  # noqa: E712
    base_spread = compute_cohort_spread_df(matured, horizon=horizon)
    if base_spread.empty:
        return {"top_contributors": [], "base_diff": None, "trimmed_diff": None}

    watch_rows = matured[matured[COL_DECISION] == DEC_WATCH]
    sym_stats = (
        watch_rows.groupby(COL_SYMBOL)[exec_col]
        .agg(["count", "mean", "sum"])
        .sort_values("sum", ascending=False)
    )
    top_syms = list(sym_stats.head(top_k).index)
    top_details = [
        {"symbol": sym, "count": int(row["count"]), "mean_exec": float(row["mean"]), "sum_exec": float(row["sum"])}
        for sym, row in sym_stats.head(top_k).iterrows()
    ]

    trimmed_df = matured[~((matured[COL_DECISION] == DEC_WATCH) & (matured[COL_SYMBOL].isin(top_syms)))]
    trimmed_spread = compute_cohort_spread_df(trimmed_df, horizon=horizon)

    return {
        "top_contributors": top_details,
        "base_diff": float(base_spread["diff_w_r"].mean()),
        "trimmed_diff": float(trimmed_spread["diff_w_r"].mean()) if not trimmed_spread.empty else None,
    }


def compute_post_prereg_appendix(
    spread_df: pd.DataFrame,
    start_date: str = DEFAULT_POST_PREREG_START,
    fee_pct: float = DEFAULT_FEE_PCT,
) -> dict[str, Any]:
    """Summarize strictly out-of-sample cohorts with T0 >= start_date."""
    if spread_df.empty:
        return {"start_date": start_date, "n": 0, "mean_diff": None, "pos_count": 0, "watch_mean": None, "watch_net": None}

    sub = spread_df[spread_df.index >= start_date]
    if sub.empty:
        return {"start_date": start_date, "n": 0, "mean_diff": None, "pos_count": 0, "watch_mean": None, "watch_net": None}

    w_mean = float(sub["watch_mean"].mean())
    return {
        "start_date": start_date,
        "n": len(sub),
        "mean_diff": float(sub["diff_w_r"].mean()),
        "pos_count": int((sub["diff_w_r"] > 0).sum()),
        "watch_mean": w_mean,
        "watch_net": w_mean - fee_pct,
    }


def compute_watchlist_churn(df: pd.DataFrame) -> dict[str, Any]:
    """Compute day-to-day WATCH basket stability and symbol boundary flip counts."""
    if df.empty or COL_ENTRY_T0 not in df.columns:
        return {"n_days": 0, "changed_days": 0, "core_symbols": [], "flips": []}

    dates = sorted(df[COL_ENTRY_T0].unique())
    prev_set: set[str] | None = None
    core_set: set[str] | None = None
    flips: list[dict[str, Any]] = []

    for dt in dates:
        curr_set = set(df[(df[COL_ENTRY_T0] == dt) & (df[COL_DECISION] == DEC_WATCH)][COL_SYMBOL])
        core_set = curr_set if core_set is None else (core_set & curr_set)
        if prev_set is not None and curr_set != prev_set:
            flips.append({
                "date": dt,
                "added": sorted(curr_set - prev_set),
                "removed": sorted(prev_set - curr_set),
            })
        prev_set = curr_set

    return {
        "n_days": len(dates),
        "changed_days": len(flips),
        "core_symbols": sorted(core_set) if core_set else [],
        "flips": flips,
    }


def _check_layer1_pass(chains: list[dict[str, Any]], boot: dict[str, float | None], fee_pct: float) -> dict[str, Any]:
    """Evaluate Pre-registration Layer 1 criteria (chains mean, chain count, block bootstrap)."""
    if not chains:
        return {"chain_mean": None, "chains_above_fee": 0, "passed_mean": False, "passed_boot": False}

    chain_mean = float(np.mean([c["mean"] for c in chains]))
    chains_above = sum(1 for c in chains if c["above_fee"])
    ci_low = boot.get("block_ci_low")
    passed_mean = chain_mean > fee_pct and chains_above >= MIN_CHAINS_ABOVE_FEE
    passed_boot = ci_low is not None and ci_low > 0.0
    return {
        "chain_mean": chain_mean,
        "chains_above_fee": chains_above,
        "passed_mean": passed_mean,
        "passed_boot": passed_boot,
    }


def _check_layer2_pass(
    sector_stats: dict[str, dict[str, Any]],
    leave_re: dict[str, Any],
    conc: dict[str, Any],
    half_stats: dict[str, Any],
    sens_no_14: dict[str, Any],
    l1_passed_mean: bool,
) -> dict[str, bool]:
    """Evaluate strict Pre-registration Layer 2 criteria (AND logic across sector, RE, top-2, half-sign, 14/10)."""
    bank_diff = sector_stats.get(SECTOR_BANK, {}).get("mean_diff")
    non_bank_diff = sector_stats.get(SECTOR_NON_BANK, {}).get("mean_diff")
    both_sectors_pos = (bank_diff is not None and bank_diff > 0.0) and (non_bank_diff is not None and non_bank_diff > 0.0)
    leave_re_pos = (leave_re.get("ex_watch_diff") is not None and leave_re["ex_watch_diff"] > 0.0) and (
        leave_re.get("ex_both_diff") is not None and leave_re["ex_both_diff"] > 0.0
    )
    trimmed_pos = conc.get("trimmed_diff") is not None and conc["trimmed_diff"] > 0.0
    consistent_halves = not half_stats.get("opposite_halves", False)
    sens_no_flip = sens_no_14.get("passed_mean") == l1_passed_mean
    passed_l2 = both_sectors_pos and leave_re_pos and trimmed_pos and consistent_halves and sens_no_flip
    return {
        "both_sectors_pos": both_sectors_pos,
        "leave_re_pos": leave_re_pos,
        "trimmed_pos": trimmed_pos,
        "consistent_halves": consistent_halves,
        "sensitivity_no_flip": sens_no_flip,
        "passed_layer2": passed_l2,
    }


def evaluate_prereg_verdict(summary: dict[str, Any], fee_pct: float = DEFAULT_FEE_PCT) -> dict[str, Any]:
    """Classify audit outcome strictly against the pre-registered 3-layer decision matrix."""
    l1 = _check_layer1_pass(summary["chains_t5"], summary["bootstrap_t5"], fee_pct)
    l2 = _check_layer2_pass(
        summary["sector_t5"],
        summary["leave_re_t5"],
        summary["concentration_t5"],
        summary["half_sample_t5"],
        summary["sensitivity_no_14"],
        l1["passed_mean"],
    )

    abs_t5 = summary["absolute_returns"].get("T+5", {})
    w_mean = abs_t5.get("watch_mean")
    net_w = (w_mean - fee_pct) if w_mean is not None else None
    passed_l3 = net_w is not None and net_w > 0.0

    if l1["passed_mean"] and l1["passed_boot"] and l2["passed_layer2"] and passed_l3:
        verdict = VERDICT_PASS
    elif l1["passed_mean"] and passed_l3:
        verdict = VERDICT_CONDITIONAL
    else:
        verdict = VERDICT_FAIL

    return {
        "verdict": verdict,
        "layer1": l1,
        "layer2": l2,
        "layer3": {"watch_net_pct": net_w, "passed_layer3": passed_l3},
    }


def run_audit(
    data_dir: str = ".",
    reports_dir: str = "reports",
    exclude_date: str = DEFAULT_EXCLUDE_DATE,
    fee_pct: float = DEFAULT_FEE_PCT,
    block_len: int = DEFAULT_BLOCK_LEN,
) -> dict[str, Any]:
    """Execute full read-only audit across canonical CSVs and daily digest reports."""
    raw_df = load_canonical_returns(data_dir=data_dir)
    digest_info = parse_digest_reports(reports_dir=reports_dir)

    spread_t5 = compute_cohort_spread_df(raw_df, horizon=5)
    chains_t5 = compute_non_overlapping_chains(
        spread_t5["diff_w_r"] if not spread_t5.empty else pd.Series(dtype=float),
        step=block_len,
        fee_pct=fee_pct,
    )
    boot_t5 = compute_block_bootstrap_ci(
        spread_t5["diff_w_r"].values if not spread_t5.empty else np.array([]),
        block_len=block_len,
    )

    sens_df = raw_df[raw_df[COL_ENTRY_T0] != exclude_date] if not raw_df.empty else raw_df
    sens_spread = compute_cohort_spread_df(sens_df, horizon=5)
    sens_chains = []
    for c in chains_t5:
        kept = [(d, v) for d, v in zip(c["dates"], c["values"]) if d != exclude_date]
        if not kept:
            continue
        mean_val = float(np.mean([v for _, v in kept]))
        sens_chains.append({
            "chain_id": c["chain_id"],
            "dates": [d for d, _ in kept],
            "values": [v for _, v in kept],
            "n": len(kept),
            "mean": mean_val,
            "above_fee": mean_val > fee_pct,
        })
    sens_l1 = _check_layer1_pass(sens_chains, boot_t5, fee_pct)

    abs_returns: dict[str, dict[str, float | int | None]] = {}
    for h in (1, 3, 5):
        sp = compute_cohort_spread_df(raw_df, horizon=h)
        if not sp.empty:
            abs_returns[f"T+{h}"] = {
                "n": len(sp),
                "watch_mean": float(sp["watch_mean"].mean()),
                "reject_mean": float(sp["reject_mean"].mean()),
                "universe_mean": float(sp["universe_mean"].mean()),
                "diff_mean": float(sp["diff_w_r"].mean()),
            }

    summary: dict[str, Any] = {
        "n_canonical_dates": int(raw_df[COL_ENTRY_T0].nunique()) if not raw_df.empty else 0,
        "date_range": (
            (str(raw_df[COL_ENTRY_T0].min()), str(raw_df[COL_ENTRY_T0].max()))
            if not raw_df.empty
            else (None, None)
        ),
        "digest_info": digest_info,
        "chains_t5": chains_t5,
        "bootstrap_t5": boot_t5,
        "half_sample_t5": compute_half_sample_stats(spread_t5),
        "sector_t5": compute_within_sector_stats(raw_df, horizon=5),
        "leave_re_t5": compute_leave_sector_out(raw_df, sector_name=SECTOR_RES_RE, horizon=5),
        "concentration_t5": compute_concentration_sensitivity(raw_df, horizon=5, top_k=2),
        "sensitivity_no_14": {
            "excluded_date": exclude_date,
            "n_cohorts": len(sens_spread),
            "overall_mean": float(sens_spread["diff_w_r"].mean()) if not sens_spread.empty else None,
            "chain_mean": sens_l1["chain_mean"],
            "chain_1_mean": sens_chains[0]["mean"] if sens_chains else None,
            "chains_above_fee": sens_l1["chains_above_fee"],
            "passed_mean": sens_l1["passed_mean"],
        },
        "post_prereg_t5": compute_post_prereg_appendix(spread_t5, fee_pct=fee_pct),
        "absolute_returns": abs_returns,
        "watchlist_churn": compute_watchlist_churn(raw_df),
    }
    summary["evaluation"] = evaluate_prereg_verdict(summary, fee_pct=fee_pct)
    return summary


def _fmt_pct(val: float | None) -> str:
    """Format percentage value safely for markdown tables."""
    return f"{val:+.2f}%" if val is not None else "N/A"


def format_audit_markdown(summary: dict[str, Any], fee_pct: float = DEFAULT_FEE_PCT) -> str:
    """Render structured audit results as a concise Markdown report."""
    start_d, end_d = summary["date_range"]
    ev = summary["evaluation"]
    boot = summary["bootstrap_t5"]
    half = summary["half_sample_t5"]
    sec = summary["sector_t5"]
    leave_re = summary["leave_re_t5"]
    conc = summary["concentration_t5"]
    sens = summary["sensitivity_no_14"]
    oos = summary["post_prereg_t5"]
    churn = summary["watchlist_churn"]
    d_info = summary["digest_info"]

    lines = [
        f"# BÁO CÁO KIỂM TOÁN HỆ THỐNG ({start_d or 'N/A'} → {end_d or 'N/A'})",
        "",
        f"- **Số phiên canonical:** `{summary['n_canonical_dates']}` | **Digest:** `{d_info['n_sessions']}` | **Số phiên BUY > 0:** `{d_info['buy_nonzero_days']}`",
        f"- **KẾT LUẬN THEO TIÊU CHÍ KHÓA TRƯỚC:** **`{ev['verdict']}`**",
        "",
        "### 1. LỚP 1 — 5 CHUỖI T+5 KHÔNG CHỒNG LẤN & BLOCK BOOTSTRAP",
        "| Chuỗi | Số điểm | Các ngày T0 | Mean W−R (%) | Vượt phí 0.40% |",
        "| :---: | :---: | :--- | :---: | :---: |",
    ]
    for c in summary["chains_t5"]:
        flag = "Có" if c["above_fee"] else "Không"
        lines.append(f"| {c['chain_id']} | {c['n']} | {', '.join(c['dates'])} | **{_fmt_pct(c['mean'])}** | {flag} |")

    l1 = ev["layer1"]
    lines.extend([
        "",
        f"- **Trung bình 5 chuỗi T+5:** `{_fmt_pct(l1['chain_mean'])}` (`{l1['chains_above_fee']}/{len(summary['chains_t5'])}` chuỗi > +{fee_pct:.2f}%)",
        f"- **Day-level IID 95% CI:** `[{_fmt_pct(boot['iid_ci_low'])}, {_fmt_pct(boot['iid_ci_high'])}]`",
        f"- **Moving-Block Bootstrap (L=5) 95% CI:** `[{_fmt_pct(boot['block_ci_low'])}, {_fmt_pct(boot['block_ci_high'])}]` (SE: `{_fmt_pct(boot['block_se'])}`)",
        "",
        "### 2. LỚP 2 — ĐỘ ĐỒNG NHẤT HAI NỬA, PHÂN RÃ NGÀNH & TẬP TRUNG MÃ",
        f"- **Hai nửa mẫu (`<= {half['split_date']}` vs `> {half['split_date']}`):** Nửa 1 (`n={half['half1_n']}`) `{_fmt_pct(half['half1_mean'])}` | Nửa 2 (`n={half['half2_n']}`) `{_fmt_pct(half['half2_mean'])}` | Trái dấu: `{half['opposite_halves']}`",
    ])
    for s_name in (SECTOR_BANK, SECTOR_NON_BANK):
        st = sec.get(s_name, {})
        lines.append(
            f"- **{s_name}:** `n={st.get('n_cohorts', 0)}` cohort | WATCH `{_fmt_pct(st.get('mean_watch'))}` | REJECT `{_fmt_pct(st.get('mean_reject'))}` | W−R **`{_fmt_pct(st.get('mean_diff'))}`** (`{st.get('pos_count', 0)}/{st.get('n_cohorts', 0)}` dương)"
        )

    top_str = ", ".join(f"`{t['symbol']}` ({t['mean_exec']:+.2f}%)" for t in conc.get("top_contributors", [])) or "N/A"
    lines.extend([
        f"- **Leave-Real-Estate-Out (loại `{leave_re['sector_excluded']}`):** Loại khỏi WATCH: **`{_fmt_pct(leave_re['ex_watch_diff'])}`** | Loại khỏi cả WATCH & REJECT: **`{_fmt_pct(leave_re['ex_both_diff'])}`**",
        f"- **Leave-top-2-out (theo tổng đóng góp):** Top-2 WATCH: {top_str} → W−R còn **`{_fmt_pct(conc.get('trimmed_diff'))}`** (gốc `{_fmt_pct(conc.get('base_diff'))}`)",
        f"- **Độ nhạy loại `{sens['excluded_date']}`:** Chuỗi 1 còn `{_fmt_pct(sens['chain_1_mean'])}` | Mean toàn kỳ `{_fmt_pct(sens['overall_mean'])}` | Mean 5 chuỗi **`{_fmt_pct(sens['chain_mean'])}`** (`{sens['chains_above_fee']}/5` chuỗi > +{fee_pct:.2f}%, Layer 1 flip: `{not ev['layer2']['sensitivity_no_flip']}`)",
        "",
        "### 3. LỚP 3 — LỢI SUẤT TUYỆT ĐỐI & ĐỘ ỔN ĐỊNH WATCHLIST *(đọc kèm Lớp 1)*",
    ])
    for h_key, vals in summary["absolute_returns"].items():
        w_net = vals["watch_mean"] - fee_pct if vals.get("watch_mean") is not None else None
        lines.append(
            f"- **{h_key} (`n={vals['n']}`):** WATCH `{_fmt_pct(vals['watch_mean'])}` (sau phí `{_fmt_pct(w_net)}`) | REJECT `{_fmt_pct(vals['reject_mean'])}` | Universe `{_fmt_pct(vals['universe_mean'])}`"
        )
    lines.extend([
        f"- **Watchlist Churn:** Đổi rổ `{churn['changed_days']}/{max(churn['n_days'] - 1, 0)}` lần chuyển phiên | Core cố định: `{len(churn['core_symbols'])}` mã",
        "",
        f"### 4. PHỤ LỤC OUT-OF-SAMPLE THUẦN (`T0 >= {oos['start_date']}`)",
        f"- **Số cohort T+5 đáo hạn sau khóa tiêu chí:** `{oos['n']}` | **Mean W−R:** `{_fmt_pct(oos['mean_diff'])}` (`{oos['pos_count']}/{oos['n']}` dương) | **WATCH sau phí {fee_pct:.2f}%:** `{_fmt_pct(oos['watch_net'])}`",
    ])
    return "\n".join(lines)


def main() -> None:
    """CLI entrypoint for running the read-only 30-session audit."""
    parser = argparse.ArgumentParser(description="Independent 30-session audit script.")
    parser.add_argument("--data-dir", default=".", help="Directory containing canonical_forward_returns_*.csv")
    parser.add_argument("--reports-dir", default="reports", help="Directory containing daily_digest_*.md")
    parser.add_argument("--output", default=None, help="Optional output markdown file path")
    parser.add_argument("--exclude-date", default=DEFAULT_EXCLUDE_DATE, help="Version-mismatch date for sensitivity check")
    parser.add_argument("--fee", type=float, default=DEFAULT_FEE_PCT, help="Round-trip transaction fee pct (default 0.40)")
    parser.add_argument("--block-len", type=int, default=DEFAULT_BLOCK_LEN, help="Block length for moving-block bootstrap")
    args = parser.parse_args()

    summary = run_audit(
        data_dir=args.data_dir,
        reports_dir=args.reports_dir,
        exclude_date=args.exclude_date,
        fee_pct=args.fee,
        block_len=args.block_len,
    )
    md = format_audit_markdown(summary, fee_pct=args.fee)
    if args.output:
        os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as fh:
            fh.write(md)
        LOGGER.info("Đã xuất báo cáo kiểm toán: %s", args.output)
    print(md)


if __name__ == "__main__":
    main()
