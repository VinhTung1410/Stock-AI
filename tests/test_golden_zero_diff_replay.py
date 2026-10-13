# -*- coding: utf-8 -*-
"""Golden Zero-Diff Replay Test (TASK-0085 / OOS Freeze Governance).

Validates that metadata-only patches introduce ZERO behavioral or numerical
drift on the canonical universe from the 2026-10-13 baseline, and validates
the metadata enrichment fields and clustered bootstrap alpha engine.
"""

from unittest.mock import patch

import pytest

from alpha_attribution import (
    compute_clustered_bootstrap_alpha,
    evaluate_alpha_attribution,
)
from data_engine import LOGIC_VERSION, MODEL_VERSION, scan_market_opportunities


@pytest.fixture(autouse=True)
def mock_db_operations():
    """Mock database persistence to ensure pure in-memory test execution."""
    with patch("db_manager.save_decision_record", return_value="DEC_MOCK_GOLDEN"), \
         patch("db_manager.save_lifecycle_event", return_value="EVT_MOCK_GOLDEN"), \
         patch("db_manager.update_decision_forward_returns", return_value=True):
        yield


def test_zero_diff_replay_market_regime_switch():
    """Verify switching macro_regime causes ZERO decision or metric diffs on captured payloads."""
    sample_symbols = ["ACB", "CTG", "FPT", "DGC", "DIG", "NVL", "HPG", "STB", "VNM", "MWG"]

    saved_a = {}
    saved_b = {}

    def mock_save_a(payload):
        saved_a[payload["symbol"]] = payload
        return f"DEC_{payload['symbol']}_A"

    def mock_save_b(payload):
        saved_b[payload["symbol"]] = payload
        return f"DEC_{payload['symbol']}_B"

    # Run A: Baseline with macro_regime=None
    with patch("db_manager.save_decision_record", side_effect=mock_save_a):
        scan_market_opportunities(extra_symbols=sample_symbols, macro_regime=None, session_override="GOLDEN_TEST")

    # Run B: With explicit DOWNTREND
    with patch("db_manager.save_decision_record", side_effect=mock_save_b):
        scan_market_opportunities(extra_symbols=sample_symbols, macro_regime="DOWNTREND", session_override="GOLDEN_TEST")

    assert len(saved_a) == len(sample_symbols)
    assert len(saved_b) == len(sample_symbols)

    for sym in sample_symbols:
        a = saved_a[sym]
        b = saved_b[sym]

        assert a["decision"] == b["decision"], f"Decision drift on {sym}: {a['decision']} != {b['decision']}"
        assert a["primary_rejection_gate"] == b["primary_rejection_gate"], f"Gate drift on {sym}: {a['primary_rejection_gate']} != {b['primary_rejection_gate']}"
        assert a["facts"]["price"] == b["facts"]["price"]
        assert a["facts"]["mos_pct"] == b["facts"]["mos_pct"]
        assert a["facts"]["conviction"] == b["facts"]["conviction"]


def test_metadata_enrichment_fields_and_audit_flags():
    """Verify metadata enrichment fields are properly populated on decision records."""
    saved_payloads = {}

    def mock_save(payload):
        saved_payloads[payload["symbol"]] = payload
        return f"DEC_{payload['symbol']}"

    with patch("db_manager.save_decision_record", side_effect=mock_save):
        scan_market_opportunities(extra_symbols=["DGC", "HPG"], session_override="EOD_REPLAY_TEST")

    assert "DGC" in saved_payloads
    dgc_rec = saved_payloads["DGC"]
    assert dgc_rec["logic_version"] == LOGIC_VERSION
    assert dgc_rec["model_version"] == MODEL_VERSION
    assert "fv_price_ratio" in dgc_rec["facts"]
    assert "mos_review_flag" in dgc_rec["facts"]
    assert "is_canonical" in dgc_rec["facts"]
    assert dgc_rec["facts"]["is_canonical"] is True  # due to EOD in session_override


def test_watchlist_added_event_emitted_for_watch():
    """Verify WATCHLIST_ADDED audit event is emitted strictly for WATCH decisions."""
    emitted_events = []

    def mock_save_evt(evt):
        emitted_events.append(evt)
        return f"EVT_{evt.get('symbol')}"

    with patch("db_manager.save_decision_record", return_value="DEC_WATCH_001"), \
         patch("db_manager.save_lifecycle_event", side_effect=mock_save_evt):
        # ACB is known to evaluate to WATCH on 2026-10-13
        scan_market_opportunities(extra_symbols=["ACB"], session_override="TEST_WATCH")

    event_types = [e["event_type"] for e in emitted_events if e["symbol"] == "ACB"]
    assert "AI_VETO_EVALUATED" in event_types
    # If ACB is WATCH, it must emit WATCHLIST_ADDED
    assert "WATCHLIST_ADDED" in event_types


def test_clustered_bootstrap_alpha_computation():
    """Verify clustered bootstrap by date produces empirical CI and p-value."""
    records = []
    # 5 sessions, each with 2 WATCH and 2 REJECT
    for day in range(1, 6):
        d_str = f"2026-10-{day:02d}"
        records.append({"decision_date": d_str, "decision": "WATCH", "fwd_ret_t5": 3.0 + day * 0.5})
        records.append({"decision_date": d_str, "decision": "WATCH", "fwd_ret_t5": 4.0 + day * 0.5})
        records.append({"decision_date": d_str, "decision": "REJECT", "primary_rejection_gate": "RISK_TRAP", "fwd_ret_t5": -1.0})
        records.append({"decision_date": d_str, "decision": "REJECT", "primary_rejection_gate": "RISK_TRAP", "fwd_ret_t5": -2.0})

    boot_res = compute_clustered_bootstrap_alpha(records, horizon=5, n_resamples=500, random_seed=42)
    assert boot_res["status"] == "BOOTSTRAP_OK"
    assert boot_res["alpha_mean"] > 0.0
    assert boot_res["ci_lower"] is not None
    assert boot_res["ci_upper"] is not None
    assert boot_res["ci_lower"] <= boot_res["ci_upper"]
    assert boot_res["p_value"] <= 0.05  # WATCH distinctly outperformed REJECT


def test_sector_strata_breakdown_in_attribution():
    """Verify evaluate_alpha_attribution outputs sector_strata and matured_counts."""
    records = [
        {"symbol": "ACB", "sector": "Ngân hàng", "decision_date": "2026-10-13", "decision": "WATCH", "fwd_ret_t5": 3.0},
        {"symbol": "VPB", "sector": "Ngân hàng", "decision_date": "2026-10-13", "decision": "REJECT", "primary_rejection_gate": "RISK_TRAP", "fwd_ret_t5": -1.0},
        {"symbol": "DIG", "sector": "Bất động sản", "decision_date": "2026-10-13", "decision": "WATCH", "fwd_ret_t5": 2.0},
        {"symbol": "NVL", "sector": "Bất động sản", "decision_date": "2026-10-13", "decision": "REJECT", "primary_rejection_gate": "RISK_TRAP", "fwd_ret_t5": -2.0},
        {"symbol": "SHADOW_MOCK", "is_shadow": True, "decision_date": "2026-10-13", "decision": "BUY", "fwd_ret_t5": 10.0},
    ]

    report = evaluate_alpha_attribution(records, deduplicate_symbol_date=True)
    assert "sector_strata" in report
    assert "matured_counts" in report
    assert "Ngân hàng" in report["sector_strata"]
    assert "Bất động sản" in report["sector_strata"]

    bank_stratum = report["sector_strata"]["Ngân hàng"]
    assert bank_stratum["alpha_watch_vs_reject_t5"] == 4.0  # 3.0 - (-1.0)
    # Ensure is_shadow was excluded
    assert report["cohort_metrics"]["BUY"]["count"] == 0
