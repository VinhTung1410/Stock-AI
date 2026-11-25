"""Unit tests for scripts/audit_30_sessions.py."""

from __future__ import annotations

import os
import sys
import unicodedata

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from scripts.audit_30_sessions import (
    DEC_REJECT,
    DEC_WATCH,
    SECTOR_BANK,
    SECTOR_NON_BANK,
    SECTOR_RES_RE,
    VERDICT_CONDITIONAL,
    VERDICT_FAIL,
    VERDICT_PASS,
    compute_block_bootstrap_ci,
    compute_cohort_spread_df,
    compute_concentration_sensitivity,
    compute_half_sample_stats,
    compute_leave_sector_out,
    compute_non_overlapping_chains,
    compute_post_prereg_appendix,
    compute_watchlist_churn,
    compute_within_sector_stats,
    evaluate_prereg_verdict,
    format_audit_markdown,
    load_canonical_returns,
    main,
    parse_digest_reports,
    run_audit,
    validate_sector_integrity,
)


def _make_sample_canonical_df() -> pd.DataFrame:
    """Create deterministic synthetic canonical forward returns across 6 trading dates."""
    dates = [
        "2026-10-14",
        "2026-10-15",
        "2026-10-16",
        "2026-10-26",
        "2026-10-27",
        "2026-11-13",
    ]
    rows = []
    for idx, dt in enumerate(dates):
        # Bank WATCH (2 stocks) vs Bank REJECT (1 stock)
        rows.append({"entry_date_t0": dt, "symbol": "ACB", "decision": DEC_WATCH, "sector": SECTOR_BANK, "matured_t5": True, "exec_t5_pct": 1.0 + 0.1 * idx, "matured_t1": True, "exec_t1_pct": 0.3, "matured_t3": True, "exec_t3_pct": 0.6})
        rows.append({"entry_date_t0": dt, "symbol": "MBB", "decision": DEC_WATCH, "sector": SECTOR_BANK, "matured_t5": True, "exec_t5_pct": 0.8 + 0.1 * idx, "matured_t1": True, "exec_t1_pct": 0.2, "matured_t3": True, "exec_t3_pct": 0.5})
        rows.append({"entry_date_t0": dt, "symbol": "VCB", "decision": DEC_REJECT, "sector": SECTOR_BANK, "matured_t5": True, "exec_t5_pct": 0.1, "matured_t1": True, "exec_t1_pct": -0.1, "matured_t3": True, "exec_t3_pct": 0.0})
        # Non-bank WATCH (2 stocks, one flipping on day 3) vs Non-bank REJECT (1 stock)
        rows.append({"entry_date_t0": dt, "symbol": "DXG", "decision": DEC_WATCH, "sector": SECTOR_RES_RE, "matured_t5": True, "exec_t5_pct": 3.0, "matured_t1": True, "exec_t1_pct": 0.8, "matured_t3": True, "exec_t3_pct": 1.5})
        rows.append({"entry_date_t0": dt, "symbol": "DIG", "decision": DEC_REJECT if idx == 2 else DEC_WATCH, "sector": SECTOR_RES_RE, "matured_t5": True, "exec_t5_pct": 1.2, "matured_t1": True, "exec_t1_pct": 0.1, "matured_t3": True, "exec_t3_pct": 0.4})
        rows.append({"entry_date_t0": dt, "symbol": "FPT", "decision": DEC_WATCH, "sector": "Công nghệ / AI", "matured_t5": True, "exec_t5_pct": 0.4, "matured_t1": True, "exec_t1_pct": 0.1, "matured_t3": True, "exec_t3_pct": 0.2})
        rows.append({"entry_date_t0": dt, "symbol": "HPG", "decision": DEC_REJECT, "sector": "Thép & Vật liệu", "matured_t5": True, "exec_t5_pct": -0.5, "matured_t1": True, "exec_t1_pct": -0.3, "matured_t3": True, "exec_t3_pct": -0.4})
    return pd.DataFrame(rows)


def test_empty_inputs_and_edge_cases(tmp_path) -> None:
    empty_loaded = load_canonical_returns(str(tmp_path))
    assert empty_loaded.empty

    digest_empty = parse_digest_reports(str(tmp_path))
    assert digest_empty["n_sessions"] == 0
    assert digest_empty["buy_nonzero_days"] == 0

    assert compute_cohort_spread_df(pd.DataFrame(), horizon=5).empty
    assert compute_non_overlapping_chains(pd.Series(dtype=float)) == []
    assert compute_watchlist_churn(pd.DataFrame())["n_days"] == 0
    assert compute_half_sample_stats(pd.DataFrame())["opposite_halves"] is False
    assert compute_post_prereg_appendix(pd.DataFrame())["n"] == 0

    boot_empty = compute_block_bootstrap_ci(np.array([]))
    assert boot_empty["mean"] is None
    assert boot_empty["block_ci_low"] is None


def test_sector_integrity_validation_and_nfd_normalization(tmp_path) -> None:
    # Missing sector column should raise loudly
    no_sec_df = pd.DataFrame([{"entry_date_t0": "2026-10-14", "symbol": "ACB", "decision": DEC_WATCH}])
    with pytest.raises(ValueError, match="sector"):
        validate_sector_integrity(no_sec_df)

    # Universe >= 20 symbols with < 8 bank symbols should raise loudly
    bad_rows = [{"entry_date_t0": "2026-10-14", "symbol": f"SYM{i}", "sector": "Khác"} for i in range(25)]
    bad_rows[0]["sector"] = SECTOR_BANK
    with pytest.raises(ValueError, match="Ngân hàng"):
        validate_sector_integrity(pd.DataFrame(bad_rows))

    # NFD Vietnamese strings in CSV must be normalized to NFC upon load
    df = _make_sample_canonical_df()
    df["sector"] = df["sector"].map(lambda s: unicodedata.normalize("NFD", s))
    df.to_csv(tmp_path / "canonical_forward_returns_20261014.csv", index=False)
    loaded = load_canonical_returns(str(tmp_path))
    assert SECTOR_BANK in set(loaded["sector"])
    assert SECTOR_RES_RE in set(loaded["sector"])


def test_non_overlapping_chains_and_block_bootstrap() -> None:
    dates = [f"2026-10-{d:02d}" for d in range(10, 20)]
    s = pd.Series([0.6, 0.2, 0.5, 0.1, 0.8, 0.7, 0.3, 0.5, 0.2, 0.9], index=dates)
    chains = compute_non_overlapping_chains(s, step=5, fee_pct=0.40)
    assert len(chains) == 5
    assert chains[0]["dates"] == ["2026-10-10", "2026-10-15"]
    assert abs(chains[0]["mean"] - 0.65) < 1e-9
    assert chains[0]["above_fee"] is True
    assert chains[1]["above_fee"] is False

    boot1 = compute_block_bootstrap_ci(s.values, block_len=5, n_boot=300, seed=42)
    boot2 = compute_block_bootstrap_ci(s.values, block_len=5, n_boot=300, seed=42)
    assert boot1 == boot2
    assert boot1["iid_ci_low"] <= boot1["mean"] <= boot1["iid_ci_high"]
    assert boot1["block_ci_low"] <= boot1["block_ci_high"]


def test_within_sector_leave_re_half_sample_and_churn() -> None:
    df = _make_sample_canonical_df()
    sec = compute_within_sector_stats(df, horizon=5)
    assert sec[SECTOR_BANK]["n_cohorts"] == 6
    assert sec[SECTOR_BANK]["mean_diff"] > 0
    assert sec[SECTOR_NON_BANK]["n_cohorts"] == 6
    assert sec[SECTOR_NON_BANK]["mean_diff"] > 0

    leave_re = compute_leave_sector_out(df, sector_name=SECTOR_RES_RE, horizon=5)
    assert leave_re["ex_watch_diff"] > 0
    assert leave_re["ex_both_diff"] > 0

    conc = compute_concentration_sensitivity(df, horizon=5, top_k=1)
    assert conc["top_contributors"][0]["symbol"] == "DXG"
    assert conc["trimmed_diff"] < conc["base_diff"]

    spread = compute_cohort_spread_df(df, horizon=5)
    half = compute_half_sample_stats(spread, split_date="2026-10-23")
    assert half["half1_n"] == 3
    assert half["half2_n"] == 3
    assert half["opposite_halves"] is False

    oos = compute_post_prereg_appendix(spread, start_date="2026-11-13")
    assert oos["n"] == 1
    assert oos["pos_count"] == 1

    churn = compute_watchlist_churn(df)
    assert churn["n_days"] == 6
    assert churn["changed_days"] == 2
    assert set(churn["core_symbols"]) == {"ACB", "DXG", "FPT", "MBB"}


def test_evaluate_prereg_verdict_all_branches() -> None:
    base_chains = [{"chain_id": i, "mean": 0.8, "above_fee": True} for i in range(1, 6)]
    base_summary = {
        "chains_t5": base_chains,
        "bootstrap_t5": {"block_ci_low": 0.25, "block_ci_high": 1.35},
        "half_sample_t5": {"opposite_halves": False},
        "sector_t5": {SECTOR_BANK: {"mean_diff": 0.3}, SECTOR_NON_BANK: {"mean_diff": 0.9}},
        "leave_re_t5": {"ex_watch_diff": 0.2, "ex_both_diff": 0.3},
        "concentration_t5": {"trimmed_diff": 0.4},
        "sensitivity_no_14": {"passed_mean": True},
        "absolute_returns": {"T+5": {"watch_mean": 0.95, "universe_mean": 0.30}},
    }
    res_pass = evaluate_prereg_verdict(base_summary, fee_pct=0.40)
    assert res_pass["verdict"] == VERDICT_PASS

    # Opposite halves must deterministically force CONDITIONAL even with positive boot CI
    opp_summary = dict(base_summary)
    opp_summary["half_sample_t5"] = {"opposite_halves": True}
    assert evaluate_prereg_verdict(opp_summary, fee_pct=0.40)["verdict"] == VERDICT_CONDITIONAL

    # Negative leave-RE-out must force CONDITIONAL even with positive boot CI
    re_fail_summary = dict(base_summary)
    re_fail_summary["leave_re_t5"] = {"ex_watch_diff": -0.2, "ex_both_diff": -0.1}
    assert evaluate_prereg_verdict(re_fail_summary, fee_pct=0.40)["verdict"] == VERDICT_CONDITIONAL

    # Failed Layer 1 chains must force FAIL even when opposite_halves is True
    fail_summary = dict(base_summary)
    fail_summary["chains_t5"] = [{"chain_id": i, "mean": 0.2, "above_fee": False} for i in range(1, 6)]
    fail_summary["half_sample_t5"] = {"opposite_halves": True}
    assert evaluate_prereg_verdict(fail_summary, fee_pct=0.40)["verdict"] == VERDICT_FAIL


def test_run_audit_end_to_end_and_cli(tmp_path, monkeypatch) -> None:
    df = _make_sample_canonical_df()
    for dt, grp in df.groupby("entry_date_t0"):
        grp.to_csv(tmp_path / f"canonical_forward_returns_{dt.replace('-', '')}.csv", index=False)

    rep_dir = tmp_path / "reports"
    rep_dir.mkdir()
    (rep_dir / "daily_digest_20261021.md").write_text(
        "- **Market Regime:** `DOWNTREND` (VN-Index: 1700.00 | MA200: 1780.00 | vs MA200: -4.49%)\n"
        "- **Phân bổ:** BUY: **0** (0.0%) | WATCH: **5** | REJECT: **2**\n"
        "| **T+5** (2026-10-14) | **+1.20%** | +1.00% | 0.50% | [+0.10%, +2.20%] | **Ngoài biên nhiễu** |\n",
        encoding="utf-8",
    )

    summary = run_audit(data_dir=str(tmp_path), reports_dir=str(rep_dir), block_len=5)
    assert summary["n_canonical_dates"] == 6
    assert summary["digest_info"]["n_sessions"] == 1
    assert summary["digest_info"]["buy_nonzero_days"] == 0

    md = format_audit_markdown(summary)
    assert "BÁO CÁO KIỂM TOÁN HỆ THỐNG" in md
    assert "Leave-Real-Estate-Out" in md
    assert "PHỤ LỤC OUT-OF-SAMPLE THUẦN" in md

    out_path = tmp_path / "out_audit.md"
    monkeypatch.setattr(
        sys,
        "argv",
        ["audit_30_sessions.py", "--data-dir", str(tmp_path), "--reports-dir", str(rep_dir), "--output", str(out_path)],
    )
    main()
    assert out_path.exists()
    assert "BÁO CÁO KIỂM TOÁN HỆ THỐNG" in out_path.read_text(encoding="utf-8")
