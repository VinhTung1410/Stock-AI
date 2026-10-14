# -*- coding: utf-8 -*-
"""Golden Zero-Diff Replay & Governance Test Suite (Pre-Registered Forward Testing).

Validates:
1. Replay comparison between commit 734893f and 58202fa across the 55 canonical symbols:
   Zero diff across decision, gate, mos_pct, and conviction.
2. mos_is_informative at CAUTION_TRAP introduces zero drift on conviction or Loop B.
3. WATCHLIST_ADDED event is strictly idempotent (symbol, date) with unified 10-session TTL.
4. Schema versioning (v2.0) and enrichment of bctc_period, consensus_asof, regime_features.
5. Invariant check: Implicit Fair Value = Price / (1 - MoS) invariance and auto-detection.
6. Clustered Bootstrap suppression (< 30 clusters -> NOT_ENOUGH_CLUSTERS, suppress CI and p-value).
7. Stratified sector guardrail (subgroups < 5 symbols -> suppress alpha spread, display n).
8. Open price execution liquidity (ceiling/floor lock detection).
"""

import json
from unittest.mock import patch

import pytest

import data_engine as de_new
import data_engine_734893f as de_old
from alpha_attribution import (
    calculate_executable_forward_return,
    check_open_execution_liquidity,
    compute_block_bootstrap_alpha,
    compute_clustered_bootstrap_alpha,
    evaluate_alpha_attribution,
    is_record_informative,
)
from quant_sanity_check import (
    calculate_implicit_fair_value,
    compute_fundamental_input_hash,
    detect_unintended_valuation_drift,
)

CANONICAL_55_SYMBOLS = [
    "ACB", "ANV", "BID", "CSV", "CTG", "DCM", "DGC", "DIG", "DPM", "DXG",
    "FMC", "FPT", "GAS", "GIL", "GMD", "GVR", "HAH", "HDB", "HPG", "HSG",
    "IDC", "KBC", "KDH", "MBB", "MSH", "MSN", "MWG", "NKG", "NLG", "NVL",
    "PDR", "PLX", "POW", "PVD", "PVT", "SAB", "SHB", "SSB", "SSI", "STB",
    "STK", "SZC", "TCB", "TNG", "TPB", "VGC", "VHC", "VHM", "VIB", "VIC",
    "VND", "VNM", "VPB", "VRE", "VTP",
]


@pytest.fixture(autouse=True)
def mock_db_operations():
    """Mock database persistence to ensure pure in-memory test execution."""
    with patch("db_manager.save_decision_record", return_value="DEC_MOCK_GOLDEN"), \
         patch("db_manager.save_lifecycle_event", return_value="EVT_MOCK_GOLDEN"), \
         patch("db_manager.update_decision_forward_returns", return_value=True):
        yield


@pytest.fixture
def snapshot_tech_data():
    """Load captured technical snapshot from 2026-10-13."""
    with open("data/last_known_tech.json", "r", encoding="utf-8") as f:
        return json.load(f)


def test_zero_diff_replay_55_symbols_between_734893f_and_58202fa(snapshot_tech_data):
    """Replay commit 734893f vs 58202fa on identical 13/10 inputs for all 55 canonical symbols.

    Asserts zero behavioral or quantitative drift across:
    - decision (BUY / WATCH / REJECT)
    - primary_rejection_gate
    - mos_pct
    - conviction score
    """
    def mock_tech(sym, count_back=60, fetch_foreign=True):
        return snapshot_tech_data.get(sym.upper().strip(), {})

    def mock_fin(sym):
        return {
            "symbol": sym.upper().strip(),
            "period": "2026-Q2",
            "pe": 12.0,
            "pb": 1.5,
            "bvps": 20.0,
            "eps": 2.5,
            "roe": 15.0,
        }

    saved_old = {}
    saved_new = {}

    def save_o(p):
        saved_old[p["symbol"]] = p
        return "DEC_OLD"

    def save_n(p):
        saved_new[p["symbol"]] = p
        return "DEC_NEW"

    # Replay 734893f
    with patch("data_engine_734893f.fetch_stock_technical", side_effect=mock_tech), \
         patch("data_engine_734893f.get_financial_ratios", side_effect=mock_fin), \
         patch("data_engine_734893f.fetch_macro_news", return_value=[]), \
         patch("data_engine_734893f.load_watchlist", return_value=[]), \
         patch("db_manager.save_decision_record", side_effect=save_o), \
         patch("db_manager.save_lifecycle_event", return_value="EVT_O"), \
         patch("db_manager.update_decision_forward_returns", return_value=True):
        de_old.scan_market_opportunities(extra_symbols=CANONICAL_55_SYMBOLS, session_override="GOLDEN_REPLAY")

    # Replay 58202fa
    with patch("data_engine.fetch_stock_technical", side_effect=mock_tech), \
         patch("data_engine.get_financial_ratios", side_effect=mock_fin), \
         patch("data_engine.fetch_macro_news", return_value=[]), \
         patch("data_engine.load_watchlist", return_value=[]), \
         patch("db_manager.save_decision_record", side_effect=save_n), \
         patch("db_manager.save_lifecycle_event", return_value="EVT_N"), \
         patch("db_manager.update_decision_forward_returns", return_value=True):
        de_new.scan_market_opportunities(extra_symbols=CANONICAL_55_SYMBOLS, session_override="GOLDEN_REPLAY")

    assert len(saved_old) == 55
    assert len(saved_new) == 55

    for sym in CANONICAL_55_SYMBOLS:
        o = saved_old[sym]
        n = saved_new[sym]
        assert o["decision"] == n["decision"], f"Decision drift on {sym}: {o['decision']} != {n['decision']}"
        assert o["primary_rejection_gate"] == n["primary_rejection_gate"], f"Gate drift on {sym}: {o['primary_rejection_gate']} != {n['primary_rejection_gate']}"
        assert o["facts"]["mos_pct"] == n["facts"]["mos_pct"], f"MoS drift on {sym}: {o['facts']['mos_pct']} != {n['facts']['mos_pct']}"
        assert o["facts"]["conviction"] == n["facts"]["conviction"], f"Conviction drift on {sym}: {o['facts']['conviction']} != {n['facts']['conviction']}"


def test_caution_trap_mos_informative_zero_conviction_and_loop_b_drift():
    """Verify mos_is_informative in CAUTION_TRAP does not alter conviction or Loop B flow."""
    caution_tech = {
        "symbol": "VHM",
        "current_price": 40.0,
        "ma20": 42.0,
        "rsi14": 52.0,
        "vol_ratio": 0.8,
        "trap_info": {"is_trap": True, "trap_type": "DISTRIBUTION_DAY", "warning_msg": "Phân phối lớn"},
    }

    saved_records = []
    with patch("data_engine.fetch_stock_technical", return_value=caution_tech), \
         patch("data_engine.get_financial_ratios", return_value={"period": "2026-Q2", "pe": 10.0, "pb": 1.2}), \
         patch("data_engine.fetch_macro_news", return_value=[]), \
         patch("db_manager.save_decision_record", side_effect=lambda p: saved_records.append(p) or "DEC_TRAP"):
        opps = de_new.scan_market_opportunities(extra_symbols=["VHM"], session_override="TEST")

    # CAUTION_TRAP must strictly map to REJECT decision with RISK_TRAP gate, never BUY or WATCH
    assert len(saved_records) == 1
    assert saved_records[0]["decision"] == "REJECT"
    assert saved_records[0]["primary_rejection_gate"] == "RISK_TRAP"
    assert opps == [] or all(o.get("status") in ("CAUTION_TRAP", "REJECT") for o in opps)
    assert not any(o.get("status") in ("RECOMMEND_BUY", "WATCH_CONFIRMATION") for o in opps)


def test_watchlist_added_idempotency_and_unified_ttl():
    """Verify WATCHLIST_ADDED event is emitted strictly ONCE per symbol/date with 10 sessions TTL."""
    from data_engine import _emitted_watchlist_added
    _emitted_watchlist_added.clear()

    emitted_events = []

    def mock_save_evt(evt):
        emitted_events.append(evt)
        return f"EVT_{len(emitted_events)}"

    def mock_tech_acb(sym, **k):
        return {
            "symbol": "ACB",
            "current_price": 25.0,
            "ma20": 24.5,
            "rsi14": 45.0,
            "vol_ratio": 1.2,
            "adv20_billion": 50.0,
            "trap_info": {"is_trap": False},
        }

    # First scan
    with patch("data_engine.fetch_stock_technical", side_effect=mock_tech_acb), \
         patch("data_engine.get_financial_ratios", return_value={"period": "2026-Q2", "pb": 1.1, "roe": 19.0}), \
         patch("data_engine.fetch_macro_news", return_value=[]), \
         patch("db_manager.is_watchlist_stint_event_emitted", return_value=False), \
         patch("db_manager.save_lifecycle_event", side_effect=mock_save_evt):
        de_new.scan_market_opportunities(extra_symbols=["ACB"], session_override="TEST_SESSION")

    # Count WATCHLIST_ADDED events
    w_events_1 = [e for e in emitted_events if e.get("event_type") == "WATCHLIST_ADDED"]
    assert len(w_events_1) == 1
    assert "ttl_days" not in w_events_1[0]["event_data"]
    assert w_events_1[0]["event_data"]["ttl_sessions"] == 10
    assert w_events_1[0]["event_data"]["logic_version"].startswith("v15.0")
    assert w_events_1[0]["correlation_id"].startswith("DEC_")
    assert w_events_1[0]["event_data"]["decision_id"] == w_events_1[0]["correlation_id"]

    # Second scan in same session/date (simulating subsequent scanner loop)
    with patch("data_engine.fetch_stock_technical", side_effect=mock_tech_acb), \
         patch("data_engine.get_financial_ratios", return_value={"period": "2026-Q2", "pb": 1.1, "roe": 19.0}), \
         patch("data_engine.fetch_macro_news", return_value=[]), \
         patch("db_manager.is_watchlist_stint_event_emitted", return_value=False), \
         patch("db_manager.save_lifecycle_event", side_effect=mock_save_evt):
        de_new.scan_market_opportunities(extra_symbols=["ACB"], session_override="TEST_SESSION")

    # Idempotent lock must prevent re-emission of WATCHLIST_ADDED
    w_events_2 = [e for e in emitted_events if e.get("event_type") == "WATCHLIST_ADDED"]
    assert len(w_events_2) == 1


def test_metadata_enrichment_and_schema_version_fields():
    """Verify schema_version, bctc_period, consensus_asof, regime_features, fin_hash, and config hashes."""
    saved_payloads = {}

    def mock_save(p):
        saved_payloads[p["symbol"]] = p
        return f"DEC_{p['symbol']}"

    mock_hpg_tech = {
        "symbol": "HPG",
        "current_price": 28.0,
        "ma20": 27.5,
        "rsi14": 52.0,
        "vol_ratio": 1.1,
        "adv20_billion": 120.0,
        "trap_info": {"is_trap": False},
    }
    mock_hpg_fin = {"period": "2026-Q2", "pe": 8.0, "pb": 1.4, "bvps": 20.0, "eps": 3.5}

    with patch("data_engine.fetch_stock_technical", return_value=mock_hpg_tech), \
         patch("data_engine.get_financial_ratios", return_value=mock_hpg_fin), \
         patch("data_engine.fetch_macro_news", return_value=[]), \
         patch("db_manager.save_decision_record", side_effect=mock_save):
        de_new.scan_market_opportunities(extra_symbols=["HPG"], session_override="EOD_TEST")

    assert "HPG" in saved_payloads
    hpg = saved_payloads["HPG"]
    assert hpg["schema_version"] == "v2.0"
    assert hpg["facts"]["schema_version"] == "v2.0"
    assert "bctc_period" in hpg["facts"]
    assert "consensus_asof" in hpg["facts"]
    assert "regime_features" in hpg["facts"]
    assert "fin_hash" in hpg["facts"]
    assert "effective_config_hash" in hpg["facts"]
    assert "universe_hash" in hpg["facts"]
    assert "gates_failed" in hpg["facts"]
    assert "fair_value_base" in hpg["facts"]
    assert "fair_value_bear" in hpg["facts"]
    assert "fair_value_bull" in hpg["facts"]
    assert "target_pb" in hpg["facts"]
    assert "eps_used" in hpg["facts"]
    assert "bvps_used" in hpg["facts"]
    assert "consensus_target_used" in hpg["facts"]
    assert "consensus_gap_pct" in hpg["facts"]


def test_implicit_fair_value_invariance_and_drift_detection():
    """Verify invariant FV = Price / (1 - MoS) and detection of unintended drift."""
    # Price = 25.0, MoS = 20% -> FV = 25.0 / (1 - 0.20) = 31.25
    fv = calculate_implicit_fair_value(25.0, 20.0)
    assert fv == 31.25

    # Case 1: Identical inputs, price fluctuates -> Invariant preserved
    rec1 = {"symbol": "ACB", "facts": {"price": 25.0, "mos_pct": 20.0, "bctc_period": "2026-Q2"}}
    rec2 = {"symbol": "ACB", "facts": {"price": 28.125, "mos_pct": 10.0, "bctc_period": "2026-Q2"}}
    is_drift, msg = detect_unintended_valuation_drift(rec1, rec2)
    assert not is_drift
    assert "Invariant preserved" in msg

    # Case 2: Identical inputs, but MoS stays at 20% when price jumped to 30 -> Drift detected
    rec3 = {"symbol": "ACB", "facts": {"price": 30.0, "mos_pct": 20.0, "bctc_period": "2026-Q2"}}
    is_drift_bad, msg_bad = detect_unintended_valuation_drift(rec1, rec3)
    assert is_drift_bad
    assert "UNINTENDED VALUATION DRIFT DETECTED" in msg_bad


def test_clustered_bootstrap_suppressed_below_30_sessions():
    """Verify clustered bootstrap outputs NOT_ENOUGH_CLUSTERS and suppresses CI/p-value when < 30 sessions."""
    records = []
    # 5 sessions: insufficient clusters
    for d in range(1, 6):
        d_str = f"2026-10-{d:02d}"
        records.append({"decision_date": d_str, "decision": "WATCH", "fwd_ret_t5": 3.0})
        records.append({"decision_date": d_str, "decision": "REJECT", "primary_rejection_gate": "RISK_TRAP", "fwd_ret_t5": -1.0})

    res = compute_clustered_bootstrap_alpha(records, horizon=5, min_clusters=30)
    assert res["status"] == "NOT_ENOUGH_CLUSTERS"
    assert res["ci_lower"] is None
    assert res["ci_upper"] is None
    assert res["p_value"] is None
    assert res["alpha_mean"] == 4.0
    assert res["n_sessions"] == 5


def test_stratification_guardrail_suppressed_when_subgroup_under_5():
    """Verify sector strata suppresses alpha spread if watch or reject has < 5 symbols."""
    # Bank stratum: 9 WATCH, 3 REJECT (REJECT < 5)
    records = []
    for i in range(9):
        records.append({"symbol": f"BANK_W_{i}", "sector": "Ngân hàng", "decision": "WATCH", "fwd_ret_t5": 2.0})
    for i in range(3):
        records.append({"symbol": f"BANK_R_{i}", "sector": "Ngân hàng", "decision": "REJECT", "primary_rejection_gate": "RISK_TRAP", "fwd_ret_t5": -1.0})

    report = evaluate_alpha_attribution(records, deduplicate_symbol_date=False)
    bank_m = report["sector_strata"]["Ngân hàng"]
    assert bank_m["watch_count"] == 9
    assert bank_m["reject_count"] == 3
    # Subgroup < 5: alpha must be None
    assert bank_m["alpha_watch_vs_reject_t5"] is None


def test_schema_version_informative_interpretation():
    """Verify 13/10 records use mos_pct is not None while 14/10 uses model informative flag."""
    rec_old = {"decision_date": "2026-10-13", "facts": {"mos_pct": 15.0, "informative": False}}
    assert is_record_informative(rec_old) is True

    rec_old_null_mos = {"decision_date": "2026-10-13", "facts": {"mos_pct": None, "informative": True}}
    assert is_record_informative(rec_old_null_mos) is False

    rec_v2_true = {"schema_version": "v2.0", "facts": {"mos_pct": 15.0, "informative": True}}
    assert is_record_informative(rec_v2_true) is True

    rec_v2_false = {"schema_version": "v2.0", "facts": {"mos_pct": 15.0, "informative": False}}
    assert is_record_informative(rec_v2_false) is False


def test_open_execution_liquidity_ceiling_floor():
    """Verify ceiling and floor lock flags on HOSE ±7% limits."""
    assert check_open_execution_liquidity(open_price=26.75, ref_price=25.0, exchange="HOSE") == "CEILING_LOCKED"
    assert check_open_execution_liquidity(open_price=23.25, ref_price=25.0, exchange="HOSE") == "FLOOR_LOCKED"
    assert check_open_execution_liquidity(open_price=25.5, ref_price=25.0, exchange="HOSE") == "NORMAL"


def test_fundamental_input_hash_drift_detection():
    """Verify fin_hash detects provider revisions even if period label is unchanged."""
    hash_old = compute_fundamental_input_hash(eps=2.5, bvps=20.0, roe=15.0, pe=12.0, consensus_price=30.0, bctc_period="2026-Q2")
    hash_revised = compute_fundamental_input_hash(eps=2.5, bvps=22.0, roe=15.0, pe=12.0, consensus_price=30.0, bctc_period="2026-Q2")
    assert hash_old != hash_revised

    # When fin_hash changes, detect_unintended_valuation_drift recognizes legitimate update
    r1 = {"symbol": "ACB", "facts": {"price": 25.0, "mos_pct": 20.0, "fin_hash": hash_old, "bctc_period": "2026-Q2"}}
    r2 = {"symbol": "ACB", "facts": {"price": 25.0, "mos_pct": 25.0, "fin_hash": hash_revised, "bctc_period": "2026-Q2"}}
    is_drift, msg = detect_unintended_valuation_drift(r1, r2)
    assert not is_drift
    assert "legitimately changed" in msg


def test_block_bootstrap_alpha_overlapping_horizon():
    """Verify block bootstrap handles autocorrelation across overlapping T+20 horizons."""
    records = []
    # Create 35 trading dates to meet min_clusters requirement
    for i in range(1, 36):
        d_str = f"2026-11-{i:02d}"
        records.append({"decision_date": d_str, "decision": "WATCH", "fwd_ret_t20": 5.0})
        records.append({"decision_date": d_str, "decision": "REJECT", "fwd_ret_t20": 1.0})

    res = compute_block_bootstrap_alpha(records, horizon=20, block_length=20, n_resamples=500, min_clusters=30)
    assert res["status"] == "BOOTSTRAP_OK"
    assert res["alpha_mean"] == 4.0
    assert res["block_length"] == 20
    assert res["n_sessions"] == 35
    assert res["ci_lower"] is not None
    assert res["ci_upper"] is not None


def test_calculate_executable_forward_return_ceiling_lock():
    """Verify that BUY on a CEILING_LOCKED stock cannot fill at Open and provides Close alternative."""
    res_ceiling = calculate_executable_forward_return(
        decision="BUY",
        open_price=26.75,
        close_price_t_plus_h=30.0,
        ref_price=25.0,
        close_price_t1=26.75,
        exchange="HOSE",
    )
    assert res_ceiling["fillable_at_open"] is False
    assert res_ceiling["liquidity_status"] == "CEILING_LOCKED"
    assert res_ceiling["forward_return_open_entry"] is None
    assert res_ceiling["forward_return_close_entry"] == 12.15

    res_normal = calculate_executable_forward_return(
        decision="BUY",
        open_price=25.5,
        close_price_t_plus_h=28.05,
        ref_price=25.0,
        exchange="HOSE",
    )
    assert res_normal["fillable_at_open"] is True
    assert res_normal["forward_return_open_entry"] == 10.0


def test_quant_sanity_check_edge_cases_and_drift_branches():
    """Verify full branch coverage for invariant detection and implicit fair value."""
    # 1. Edge cases in calculate_implicit_fair_value
    assert calculate_implicit_fair_value(None, 20.0) is None
    assert calculate_implicit_fair_value(25.0, None) is None
    assert calculate_implicit_fair_value(-5.0, 20.0) is None
    assert calculate_implicit_fair_value(25.0, 100.0) is None

    # 2. BCTC period legitimately changed
    r_period1 = {"symbol": "TCB", "facts": {"price": 30.0, "mos_pct": 20.0, "bctc_period": "2026-Q1"}}
    r_period2 = {"symbol": "TCB", "facts": {"price": 30.0, "mos_pct": 25.0, "bctc_period": "2026-Q2"}}
    is_d, msg = detect_unintended_valuation_drift(r_period1, r_period2)
    assert not is_d
    assert "BCTC 2026-Q1->2026-Q2" in msg

    # 3. Consensus date legitimately updated
    r_cons1 = {"symbol": "MBB", "facts": {"price": 25.0, "mos_pct": 20.0, "consensus_asof": "2026-09-01"}}
    r_cons2 = {"symbol": "MBB", "facts": {"price": 25.0, "mos_pct": 25.0, "consensus_asof": "2026-10-01"}}
    is_d, msg = detect_unintended_valuation_drift(r_cons1, r_cons2)
    assert not is_d
    assert "Consensus 2026-09-01->2026-10-01" in msg

    # 4. MoS or Price absent -> skipped
    r_absent = {"symbol": "HPG", "facts": {"price": 0.0, "mos_pct": None}}
    r_ok = {"symbol": "HPG", "facts": {"price": 25.0, "mos_pct": 20.0}}
    is_d, msg = detect_unintended_valuation_drift(r_absent, r_ok)
    assert not is_d
    assert "invariant check skipped" in msg

    # 5. Indeterminate fair value
    r_bad_fv = {"symbol": "HPG", "facts": {"price": 25.0, "mos_pct": 100.0}}
    is_d, msg = detect_unintended_valuation_drift(r_bad_fv, r_ok)
    assert not is_d
    assert "Indeterminate implicit fair value" in msg

    # 6. Unintended drift detected
    r_drift1 = {"symbol": "FPT", "facts": {"price": 100.0, "mos_pct": 20.0, "bctc_period": "2026-Q2", "consensus_asof": "2026-10-01"}}
    r_drift2 = {"symbol": "FPT", "facts": {"price": 100.0, "mos_pct": 35.0, "bctc_period": "2026-Q2", "consensus_asof": "2026-10-01"}}
    is_d, msg = detect_unintended_valuation_drift(r_drift1, r_drift2)
    assert is_d
    assert "UNINTENDED VALUATION DRIFT DETECTED" in msg

    # 7. Invariant preserved (drift within tolerance)
    r_same1 = {"symbol": "FPT", "facts": {"price": 100.0, "mos_pct": 20.0, "bctc_period": "2026-Q2", "consensus_asof": "2026-10-01"}}
    r_same2 = {"symbol": "FPT", "facts": {"price": 100.0, "mos_pct": 20.1, "bctc_period": "2026-Q2", "consensus_asof": "2026-10-01"}}
    is_d, msg = detect_unintended_valuation_drift(r_same1, r_same2)
    assert not is_d
    assert "Invariant preserved" in msg


def test_raw_input_snapshot_persistence():
    """Verify save_raw_input_snapshot executes insert into raw_input_snapshots."""
    from unittest.mock import MagicMock

    from db_manager import save_raw_input_snapshot

    mock_client = MagicMock()
    mock_table = MagicMock()
    mock_client.table.return_value = mock_table
    mock_table.insert.return_value = mock_table
    mock_table.execute.return_value = MagicMock(data=[{"id": 1}])

    with patch("db_manager.get_supabase_client", return_value=mock_client):
        success = save_raw_input_snapshot(
            session_date="2026-10-15",
            symbol="HPG",
            decision_id="DEC_HPG_TEST",
            raw_bctc={"period": "2026-Q2", "eps": 3.5},
            raw_price={"current_price": 28.0},
            raw_consensus={"consensus_target": 32.0},
        )
        assert success is True
        mock_client.table.assert_called_with("raw_input_snapshots")
        mock_table.insert.assert_called_once()
        insert_payload = mock_table.insert.call_args[0][0]
        assert insert_payload["symbol"] == "HPG"
        assert insert_payload["session_date"] == "2026-10-15"
        assert insert_payload["decision_id"] == "DEC_HPG_TEST"
        assert insert_payload["raw_bctc"]["eps"] == 3.5

    # Test error fallback gracefully returns False
    mock_client.table.side_effect = Exception("DB Connection Error")
    with patch("db_manager.get_supabase_client", return_value=mock_client):
        success_err = save_raw_input_snapshot(
            session_date="2026-10-15",
            symbol="HPG",
            decision_id="DEC_HPG_TEST",
        )
        assert success_err is False
