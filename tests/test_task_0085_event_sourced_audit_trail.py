# -*- coding: utf-8 -*-
"""Unit tests for TASK-0085: Event-Sourced Audit Trail & Alpha Attribution (Phase 28 - v15.0)."""

from unittest.mock import patch

import pandas as pd

from alpha_attribution import (
    compute_forward_returns,
    evaluate_alpha_attribution,
)
from db_manager import (
    EVENT_AI_VETO_EVALUATED,
    EVENT_TRIGGER_ACTIVATED,
    EVENT_WATCHLIST_ADDED,
    get_lifecycle_events,
    save_lifecycle_event,
)


def test_save_and_get_lifecycle_events_in_memory():
    """AC-01: Verify event-sourced lifecycle events can be saved and queried by correlation_id."""
    with patch("db_manager.get_supabase_client", return_value=None):
        corr_id = "DEC_TEST_VNM_20261009_001"
        evt_1 = {
            "symbol": "VNM",
            "correlation_id": corr_id,
            "event_type": EVENT_WATCHLIST_ADDED,
            "event_data": {"initial_mos": 18.5, "reason": "Passed Screener"},
            "market_regime": "SIDEWAY",
        }
        evt_2 = {
            "symbol": "VNM",
            "correlation_id": corr_id,
            "event_type": EVENT_TRIGGER_ACTIVATED,
            "event_data": {"price": 68.5, "signal": "EMA20_CROSS"},
            "market_regime": "SIDEWAY",
        }
        evt_3 = {
            "symbol": "VNM",
            "correlation_id": corr_id,
            "event_type": EVENT_AI_VETO_EVALUATED,
            "event_data": {"ai_action": "PASS", "sizing_factor": 1.0},
            "market_regime": "SIDEWAY",
        }

        id_1 = save_lifecycle_event(evt_1)
        id_2 = save_lifecycle_event(evt_2)
        id_3 = save_lifecycle_event(evt_3)

        assert id_1 is not None
        assert id_2 is not None
        assert id_3 is not None

        # Query by correlation_id
        events = get_lifecycle_events(correlation_id=corr_id)
        assert len(events) >= 3
        types = [e["event_type"] for e in events]
        assert EVENT_WATCHLIST_ADDED in types
        assert EVENT_TRIGGER_ACTIVATED in types
        assert EVENT_AI_VETO_EVALUATED in types

        # Query by event_type
        veto_events = get_lifecycle_events(correlation_id=corr_id, event_type=EVENT_AI_VETO_EVALUATED)
        assert len(veto_events) == 1
        assert veto_events[0]["event_data"]["sizing_factor"] == 1.0


def test_compute_forward_returns_basic():
    """AC-02: Calculate T+5, T+20, T+60 forward returns correctly against historical price series."""
    # Build 70-day mock price series for FPT
    dates = pd.date_range("2026-01-01", periods=70, freq="B").strftime("%Y-%m-%d").tolist()
    prices = [100.0 + i for i in range(70)]  # linear price rise: 100, 101, ...
    price_df = pd.DataFrame({
        "symbol": ["FPT"] * 70,
        "date": dates,
        "close": prices,
    })

    records = [
        {"symbol": "FPT", "decision_date": dates[0], "decision": "BUY"},
        {"symbol": "FPT", "decision_date": dates[10], "decision": "WATCH"},
    ]

    evaluated = compute_forward_returns(records, price_df, horizons=(5, 20, 60))
    assert len(evaluated) == 2

    # Record 0 at index 0 (price 100):
    # T+5 is index 5 (price 105) -> (105-100)/100 = 5.0%
    # T+20 is index 20 (price 120) -> (120-100)/100 = 20.0%
    # T+60 is index 60 (price 160) -> (160-100)/100 = 60.0%
    r0 = evaluated[0]
    assert r0["fwd_ret_t5"] == 5.0
    assert r0["fwd_ret_t20"] == 20.0
    assert r0["fwd_ret_t60"] == 60.0

    # Record 1 at index 10 (price 110):
    # T+5 is index 15 (price 115) -> (115-110)/110 = 4.55%
    # T+20 is index 30 (price 130) -> (130-110)/110 = 18.18%
    # T+60 is index 70 -> exceeds length, should be None
    r1 = evaluated[1]
    assert r1["fwd_ret_t5"] == 4.55
    assert r1["fwd_ret_t20"] == 18.18
    assert r1["fwd_ret_t60"] is None


def test_compute_forward_returns_empty_and_missing():
    """Verify forward return calculation handles empty dataframe and missing symbols gracefully."""
    empty_df = pd.DataFrame()
    records = [{"symbol": "FPT", "decision_date": "2026-01-01"}]
    assert compute_forward_returns(records, empty_df) == []

    # Symbol not in price_df
    price_df = pd.DataFrame({"symbol": ["MWG"], "date": ["2026-01-01"], "close": [50.0]})
    res = compute_forward_returns(records, price_df)
    assert len(res) == 1
    assert res[0]["fwd_ret_t5"] is None


def test_evaluate_alpha_attribution_insufficient_sample():
    """AC-03: Guard against insufficient sample (< 60 clean sessions)."""
    # 4 distinct sessions, well below 60
    records = [
        {"decision_date": "2026-01-01", "decision": "BUY", "fwd_ret_t5": 4.0, "fwd_ret_t20": 10.0, "fwd_ret_t60": 15.0},
        {"decision_date": "2026-01-02", "decision": "REJECT", "fwd_ret_t5": -2.0, "fwd_ret_t20": -5.0, "fwd_ret_t60": -8.0},
        {"decision_date": "2026-01-03", "decision": "WATCH", "fwd_ret_t5": 1.0, "fwd_ret_t20": 2.0, "fwd_ret_t60": 3.0},
        {"decision_date": "2026-01-04", "decision": "BUY", "fwd_ret_t5": 6.0, "fwd_ret_t20": 12.0, "fwd_ret_t60": 18.0},
    ]

    report = evaluate_alpha_attribution(records, min_clean_sessions=60)
    assert report["is_sample_sufficient"] is False
    assert report["unique_sessions"] == 4
    assert "INSUFFICIENT_SAMPLE" in report["status"]

    # Cohort metrics should still be calculated
    metrics = report["cohort_metrics"]
    assert metrics["BUY"]["count"] == 2
    assert metrics["BUY"]["t5_mean"] == 5.0  # mean of 4.0 and 6.0
    assert metrics["REJECT"]["count"] == 1
    assert metrics["REJECT"]["t5_mean"] == -2.0

    # Alpha spreads: BUY vs REJECT at T+5 = 5.0 - (-2.0) = +7.0
    spreads = report["alpha_spreads"]
    assert spreads["alpha_buy_vs_reject_t5"] == 7.0


def test_evaluate_alpha_attribution_sufficient_sample():
    """AC-03: When unique sessions >= 60, status is OOS_VERIFIED."""
    records = []
    for i in range(65):
        records.append({
            "decision_date": f"2026-01-{i+1:02d}",
            "decision": "BUY" if i % 2 == 0 else "REJECT",
            "fwd_ret_t5": 2.5 if i % 2 == 0 else -1.0,
            "fwd_ret_t20": 5.0 if i % 2 == 0 else -2.0,
            "fwd_ret_t60": 10.0 if i % 2 == 0 else -4.0,
        })

    report = evaluate_alpha_attribution(records, min_clean_sessions=60)
    assert report["is_sample_sufficient"] is True
    assert report["unique_sessions"] == 65
    assert report["status"] == "OOS_VERIFIED"
    assert report["alpha_spreads"]["alpha_buy_vs_reject_t5"] == 3.5  # 2.5 - (-1.0)
