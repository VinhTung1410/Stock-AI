"""Unit tests for generate_daily_digest.py."""

from __future__ import annotations

import json
import os
import sys
from unittest.mock import MagicMock, patch

import pandas as pd

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from scripts.generate_daily_digest import (
    _compute_eod_decisions,
    _extract_regime_and_version,
    _extract_watchlist_additions,
    _format_markdown_report,
    _inspect_cohort_maturity,
    _is_horizon_maturing_today,
    _run_sub_step,
    generate_digest,
    get_default_vn_date,
    run_pipeline_sync,
)


def test_get_default_vn_date() -> None:
    dt_str = get_default_vn_date()
    assert len(dt_str) == 10
    assert dt_str.count("-") == 2


def test_extract_regime_and_version_empty() -> None:
    empty_df = pd.DataFrame()
    res = _extract_regime_and_version(empty_df)
    assert res["regime"] == "UNKNOWN"
    assert res["vnindex_price"] is None


def test_extract_regime_and_version_valid() -> None:
    facts = {
        "regime_features": {
            "regime": "DOWNTREND",
            "vnindex_price": 1774.15,
            "vnindex_ma200": 1796.65,
            "vnindex_vs_ma200_pct": -1.25,
        }
    }
    df = pd.DataFrame([
        {
            "facts": json.dumps(facts),
            "logic_version": "v15.0_frozen_20261013",
            "model_version": "v15.0_post_fix",
            "git_sha": "106e6c61afb263982aac2834263ac89e9c458bfd",
        }
    ])
    res = _extract_regime_and_version(df)
    assert res["regime"] == "DOWNTREND"
    assert res["vnindex_price"] == 1774.15
    assert res["git_sha"] == "106e6c61af"


def test_extract_regime_and_version_invalid_json() -> None:
    df = pd.DataFrame([
        {
            "facts": "invalid-json-string",
            "logic_version": "v15.0",
            "model_version": "v15.0",
            "git_sha": "12345",
        }
    ])
    res = _extract_regime_and_version(df)
    assert res["regime"] == "UNKNOWN"


def test_compute_eod_decisions_empty() -> None:
    res = _compute_eod_decisions(pd.DataFrame())
    assert res["total"] == 0
    assert res["buy"] == 0
    assert res["watch"] == 0
    assert res["reject"] == 0


def test_compute_eod_decisions_valid() -> None:
    df = pd.DataFrame([
        {"session": "EOD_CANONICAL", "symbol": "FPT", "decision": "WATCH", "primary_rejection_gate": "TECH_CONFIRMATION"},
        {"session": "EOD_CANONICAL", "symbol": "VNM", "decision": "BUY", "primary_rejection_gate": ""},
        {"session": "EOD_CANONICAL", "symbol": "VIC", "decision": "REJECT", "primary_rejection_gate": "RISK_TRAP"},
    ])
    res = _compute_eod_decisions(df)
    assert res["total"] == 3
    assert res["buy"] == 1
    assert res["watch"] == 1
    assert res["reject"] == 1
    assert "FPT" in res["watch_symbols"]
    assert res["gates"]["TECH_CONFIRMATION"] == 1


def test_compute_eod_decisions_no_session_column() -> None:
    df = pd.DataFrame([
        {"symbol": "FPT", "decision": "WATCH", "primary_rejection_gate": "TECH_CONFIRMATION"},
        {"symbol": "FPT", "decision": "REJECT", "primary_rejection_gate": "RISK_TRAP"},
    ])
    res = _compute_eod_decisions(df)
    assert res["total"] == 1
    assert res["reject"] == 1


def test_extract_watchlist_additions() -> None:
    assert _extract_watchlist_additions(pd.DataFrame()) == []

    df = pd.DataFrame([
        {"event_type": "AI_VETO_EVALUATED", "symbol": "HPG"},
        {"event_type": "WATCHLIST_ADDED", "symbol": "MBB"},
        {"event_type": "WATCHLIST_ADDED", "symbol": "FPT"},
        {"event_type": "WATCHLIST_ADDED", "symbol": "MBB"},  # duplicate
    ])
    res = _extract_watchlist_additions(df)
    assert res == ["FPT", "MBB"]


def test_inspect_cohort_maturity() -> None:
    df = pd.DataFrame([
        {
            "entry_date_t0": "2026-10-23",
            "entry_date_t1": "2026-10-26",
            "matured_t1": True,
            "matured_t3": True,
            "matured_t5": False,
            "vn_close_t3": 1763.55,
            "decision": "WATCH",
            "exec_t1_pct": -1.5,
            "excess_vs_universe_t1_pct": -0.5,
            "exec_t3_pct": -2.0,
            "excess_vs_universe_t3_pct": -1.0,
        },
        {
            "entry_date_t0": "2026-10-23",
            "entry_date_t1": "2026-10-26",
            "matured_t1": True,
            "matured_t3": True,
            "matured_t5": False,
            "vn_close_t3": 1763.55,
            "decision": "REJECT",
            "exec_t1_pct": -0.5,
            "excess_vs_universe_t1_pct": 0.5,
            "exec_t3_pct": 0.5,
            "excess_vs_universe_t3_pct": 1.5,
        },
    ])
    results = _inspect_cohort_maturity(df, target_date="2026-10-26", vn_close_today=1763.55)
    assert len(results) == 2  # T+1 and T+3
    assert results[0]["horizon"] == "T+1"
    assert results[0]["watch_exec"] == -1.5
    assert results[0]["rej_exec"] == -0.5
    assert results[1]["horizon"] == "T+3"


def test_format_markdown_report() -> None:
    regime = {
        "regime": "DOWNTREND",
        "vnindex_price": 1774.15,
        "vnindex_ma200": 1796.65,
        "vnindex_vs_ma200_pct": -1.25,
        "logic_version": "v15.0",
        "model_version": "v15.0",
        "git_sha": "abc1234",
    }
    stats = {
        "total": 55,
        "buy": 0,
        "watch": 15,
        "reject": 40,
        "gates": {"RISK_TRAP": 40, "TECH_CONFIRMATION": 15},
    }
    cohorts = [
        {
            "horizon": "T+1",
            "cohort_t0": "2026-10-23",
            "watch_n": 15,
            "watch_exec": -1.87,
            "watch_excess": -0.85,
            "rej_n": 40,
            "rej_exec": -0.70,
            "rej_excess": 0.32,
        }
    ]
    md = _format_markdown_report("2026-10-26", regime, stats, ["FPT", "MBB"], cohorts)
    assert "DAILY QUANT RESEARCH BRIEFING — 2026-10-26" in md
    assert "DOWNTREND" in md
    assert "Danh mục WATCHLIST tại EOD" in md
    assert "Tiền mặt (BUY=0)" in md
    assert "FPT" in md


def test_run_sub_step_success_and_failure() -> None:
    with patch("subprocess.run") as mock_sub:
        mock_sub.return_value = MagicMock(returncode=0, stderr="")
        assert _run_sub_step(["python", "--version"], "Check Version") is True

        mock_sub.return_value = MagicMock(returncode=1, stderr="Error occurred")
        assert _run_sub_step(["python", "bad_script.py"], "Bad Script") is False

        mock_sub.side_effect = Exception("System crash")
        assert _run_sub_step(["python", "bad_script.py"], "Exception Test") is False


def test_run_pipeline_sync() -> None:
    with patch("scripts.generate_daily_digest._run_sub_step") as mock_step:
        # Default sync_db=True should NOT have --skip-db
        run_pipeline_sync("2026-10-27", skip_export=False, skip_returns=False)
        assert mock_step.call_count == 2
        returns_cmd = mock_step.call_args_list[1][0][0]
        assert "--up-to" in returns_cmd
        assert "2026-10-27" in returns_cmd
        assert "--skip-db" not in returns_cmd

        # sync_db=False should pass --skip-db
        mock_step.reset_mock()
        run_pipeline_sync("2026-10-27", skip_export=False, skip_returns=False, sync_db=False)
        assert mock_step.call_count == 2
        returns_cmd_skip = mock_step.call_args_list[1][0][0]
        assert "--skip-db" in returns_cmd_skip

        mock_step.reset_mock()
        run_pipeline_sync("2026-10-27", skip_export=True, skip_returns=True)
        assert mock_step.call_count == 0


def test_is_horizon_maturing_today_variants() -> None:
    # Not matured
    unmatured_df = pd.DataFrame([{"matured_t3": False}])
    assert not _is_horizon_maturing_today(unmatured_df, 3, "2026-10-27", None, None)

    # Direct exit date match
    direct_match_df = pd.DataFrame([{"matured_t3": True, "exit_date_t3": "2026-10-27"}])
    assert _is_horizon_maturing_today(direct_match_df, 3, "2026-10-27", None, None)

    # Expected date match
    exp_match_df = pd.DataFrame([{"matured_t5": True}])
    assert _is_horizon_maturing_today(exp_match_df, 5, "2026-10-27", None, "2026-10-27")

    # Fallback close tolerance match
    close_match_df = pd.DataFrame([{"matured_t3": True, "vn_close_t3": 1761.85}])
    assert _is_horizon_maturing_today(close_match_df, 3, "2026-10-27", 1761.87, None)

    # Mismatch
    mismatch_df = pd.DataFrame([{"matured_t3": True, "vn_close_t3": 1750.0}])
    assert not _is_horizon_maturing_today(mismatch_df, 3, "2026-10-27", 1761.87, None)


def test_inspect_cohort_maturity_all_three_horizons() -> None:
    df = pd.DataFrame([
        {
            "entry_date_t0": "2026-10-20",
            "exit_date_t1": "2026-10-21",
            "exit_date_t3": "2026-10-23",
            "exit_date_t5": "2026-10-27",
            "matured_t1": True,
            "matured_t3": True,
            "matured_t5": True,
            "decision": "WATCH",
            "exec_t1_pct": 1.0,
            "excess_vs_universe_t1_pct": 0.5,
            "exec_t3_pct": 2.0,
            "excess_vs_universe_t3_pct": 1.0,
            "exec_t5_pct": 0.8,
            "excess_vs_universe_t5_pct": -0.3,
        },
        {
            "entry_date_t0": "2026-10-20",
            "exit_date_t1": "2026-10-21",
            "exit_date_t3": "2026-10-23",
            "exit_date_t5": "2026-10-27",
            "matured_t1": True,
            "matured_t3": True,
            "matured_t5": True,
            "decision": "REJECT",
            "exec_t1_pct": -0.5,
            "excess_vs_universe_t1_pct": -0.5,
            "exec_t3_pct": 1.5,
            "excess_vs_universe_t3_pct": 0.5,
            "exec_t5_pct": 1.2,
            "excess_vs_universe_t5_pct": 0.1,
        },
    ])
    # Target date 2026-10-27 should only match T+5
    results = _inspect_cohort_maturity(df, target_date="2026-10-27", vn_close_today=None)
    assert len(results) == 1
    assert results[0]["horizon"] == "T+5"
    assert results[0]["cohort_t0"] == "2026-10-20"
    assert results[0]["watch_exec"] == 0.8
    assert results[0]["rej_exec"] == 1.2


def test_generate_digest_e2e(tmp_path: object) -> None:
    out_dir = str(tmp_path)
    # Target date with existing CSVs
    out_file = generate_digest("2026-10-26", skip_sync=True, output_dir=out_dir)
    assert os.path.exists(out_file)
    with open(out_file, "r", encoding="utf-8") as f:
        content = f.read()
    assert "DAILY QUANT RESEARCH BRIEFING — 2026-10-26" in content
    assert "DOWNTREND" in content


def test_sync_canonical_returns_to_supabase_mock() -> None:
    from scripts.update_forward_returns import sync_canonical_returns_to_supabase

    # Empty df
    assert sync_canonical_returns_to_supabase(pd.DataFrame()) == 0

    # No client
    df = pd.DataFrame([{"decision_id": "DEC_1", "symbol": "FPT", "close_t0": 100.0, "exec_t1_pct": 1.5}])
    with patch("scripts.update_forward_returns.get_supabase_client", return_value=None):
        assert sync_canonical_returns_to_supabase(df, client=None) == 0

    # Successful upsert
    mock_client = MagicMock()
    mock_table = MagicMock()
    mock_upsert = MagicMock()
    mock_res = MagicMock()
    mock_res.data = [{"decision_id": "DEC_1"}]
    mock_upsert.execute.return_value = mock_res
    mock_table.upsert.return_value = mock_upsert
    mock_client.table.return_value = mock_table

    synced = sync_canonical_returns_to_supabase(df, client=mock_client)
    assert synced == 1
    mock_table.upsert.assert_called_once()


def test_regime_extraction_4_days() -> None:
    """A2 test: Verify regime extraction across 4 days (27-30/10) takes EOD canonical price and MA200."""
    from scripts.generate_daily_digest import _extract_regime_and_version, _load_decision_records

    # Expected closing prices, MA200, and vs_ma200_pct for EOD canonical session
    expected = {
        "2026-10-27": {"price": 1761.87, "ma200": 1796.41, "vs_ma200_pct": -1.92},
        "2026-10-28": {"price": 1766.65, "ma200": 1796.16, "vs_ma200_pct": -1.64},
        "2026-10-29": {"price": 1755.61, "ma200": 1795.63, "vs_ma200_pct": -2.23},
        "2026-10-30": {"price": 1741.62, "ma200": 1795.06, "vs_ma200_pct": -2.98},
    }
    for date_str, exp in expected.items():
        df = _load_decision_records(date_str)
        assert not df.empty, f"Missing decision records for {date_str}"
        reg = _extract_regime_and_version(df)
        assert abs(reg["vnindex_price"] - exp["price"]) < 0.01, f"{date_str} got {reg['vnindex_price']}, expected {exp['price']}"
        assert abs(reg["vnindex_ma200"] - exp["ma200"]) < 0.01, f"{date_str} got {reg['vnindex_ma200']}, expected {exp['ma200']}"
        assert abs(reg["vnindex_vs_ma200_pct"] - exp["vs_ma200_pct"]) < 0.01, f"{date_str} got {reg['vnindex_vs_ma200_pct']}, expected {exp['vs_ma200_pct']}"
        assert reg["regime"] == "DOWNTREND"


def test_watchlist_delta_computation() -> None:
    """B1 test: Verify watchlist delta correctly identifies TCB addition and BID transitions."""
    from scripts.generate_daily_digest import _compute_eod_decisions, _compute_watchlist_delta, _load_decision_records
    
    dec29 = _load_decision_records("2026-10-29")
    stats29 = _compute_eod_decisions(dec29)
    delta29 = _compute_watchlist_delta("2026-10-29", stats29["watch_symbols"])
    assert "TCB" in delta29["added"]
    assert "BID" in delta29["removed"]
    assert len(stats29["watch_symbols"]) == 16

    dec30 = _load_decision_records("2026-10-30")
    stats30 = _compute_eod_decisions(dec30)
    delta30 = _compute_watchlist_delta("2026-10-30", stats30["watch_symbols"])
    assert "BID" in delta30["added"]
    assert len(delta30["removed"]) == 0
    assert len(stats30["watch_symbols"]) == 17


def test_extreme_return_guardrail_5_sessions() -> None:
    """Sanity check guardrail: No single stock forward return may drop below -15% in <= 5 sessions.
    
    Protects against unadjusted corporate actions / splits (e.g., TCB -33% unadjusted ratio 1.5).
    Any positive moves > 15% must be verified to not exceed theoretical cumulative price limits.
    """
    import glob
    files = sorted(glob.glob("canonical_forward_returns_*.csv"))
    assert len(files) >= 11, "Must check at least 11 canonical cohort files"

    for f in files:
        df = pd.read_csv(f)
        for col in ["exec_t1_pct", "exec_t3_pct", "exec_t5_pct"]:
            if col not in df.columns:
                continue
            # 1. No unadjusted crash below -15%
            crashes = df[df[col].fillna(0.0) < -15.0]
            assert crashes.empty, f"Severe negative return violation in {f} ({col}): {crashes[['symbol', col]].to_dict(orient='records')}"
            
            # 2. Positive moves capped below +25% for 5-session window
            spikes = df[df[col].fillna(0.0) > 25.0]
            assert spikes.empty, f"Unrealistic upward return spike in {f} ({col}): {spikes[['symbol', col]].to_dict(orient='records')}"


def test_post_holiday_and_normal_day_digest_regression(tmp_path: object) -> None:
    """Regression test: post-holiday session (2026-11-25 after 2026-11-24 holiday) vs normal session (2026-11-23).

    Verifies that:
    1. Holiday orphan canonical CSV (20261124 pointing to 2026-11-25) does not hijack Watchlist diff
       or shift T+10 / T+20 maturity on 2026-11-25.
    2. Normal trading day (2026-11-23) compares against 2026-11-20 and outputs all matured horizons.
    """
    from scripts.generate_daily_digest import _compute_eod_decisions, _compute_watchlist_delta, _load_decision_records

    out_dir = str(tmp_path)

    # 1. Post-holiday session: 2026-11-25 (2026-11-24 was holiday, previous trading session was 2026-11-23)
    dec25 = _load_decision_records("2026-11-25")
    stats25 = _compute_eod_decisions(dec25)
    delta25 = _compute_watchlist_delta("2026-11-25", stats25["watch_symbols"])
    assert delta25["prev_date"] == "2026-11-23", f"Expected prev trading date 2026-11-23, got {delta25['prev_date']}"
    assert delta25["added"] == ["PDR"], f"Expected only PDR added vs 2026-11-23, got {delta25['added']}"
    assert delta25["removed"] == []

    digest25_path = generate_digest("2026-11-25", skip_sync=True, output_dir=out_dir)
    with open(digest25_path, encoding="utf-8") as fh:
        md25 = fh.read()
    assert "so với 2026-11-23" in md25
    assert "**T+1** đáo hạn hôm nay | 2026-11-23" in md25
    assert "**T+3** đáo hạn hôm nay | 2026-11-19" in md25
    assert "**T+5** đáo hạn hôm nay | 2026-11-17" in md25
    assert "**T+10** đáo hạn hôm nay | 2026-11-10" in md25
    assert "**T+20** đáo hạn hôm nay | 2026-10-27" in md25

    # 2. Normal trading day: 2026-11-23 (previous session 2026-11-20)
    dec23 = _load_decision_records("2026-11-23")
    stats23 = _compute_eod_decisions(dec23)
    delta23 = _compute_watchlist_delta("2026-11-23", stats23["watch_symbols"])
    assert delta23["prev_date"] == "2026-11-20"

    digest23_path = generate_digest("2026-11-23", skip_sync=True, output_dir=out_dir)
    with open(digest23_path, encoding="utf-8") as fh:
        md23 = fh.read()
    assert "**T+10** đáo hạn hôm nay | 2026-11-09" in md23
    assert "**T+20** đáo hạn hôm nay | 2026-10-26" in md23


