# -*- coding: utf-8 -*-
"""Unit tests for Lifecycle Events & Forward Returns Wiring (Audit Trail & Performance Attribution)."""

from unittest.mock import MagicMock, patch

import pandas as pd

from db_manager import (
    EVENT_AI_VETO_EVALUATED,
    get_lifecycle_events,
    save_lifecycle_event,
    update_decision_forward_returns,
)
from scripts.update_forward_returns import (
    _calculate_benchmarks_and_excess,
    _calculate_record_payload,
    _is_valid_ticker,
    _normalize_date,
    calc_exchange_ceiling_floor,
    calc_hose_ceiling_floor,
    filter_canonical_and_deduplicate,
    get_hose_tick_size,
    simulate_sector_stratified_baseline,
)


class TestUpdateDecisionForwardReturnsFallback:
    """Test resilience of update_decision_forward_returns when upsert raises error."""

    @patch("db_manager.get_supabase_client")
    def test_upsert_fallback_to_select_and_update(self, mock_get_client):
        """When upsert fails with missing unique constraint, it falls back to select and update."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        # Mock upsert raising 42P10
        mock_client.table("decision_forward_returns").upsert().execute.side_effect = Exception(
            "no unique or exclusion constraint matching ON CONFLICT"
        )

        # Mock select finding existing record
        mock_select = MagicMock()
        mock_select.data = [{"id": "uuid-1", "decision_id": "DEC_FPT_01"}]
        mock_client.table("decision_forward_returns").select().eq().limit().execute.return_value = mock_select

        # Mock update succeeding
        mock_update = MagicMock()
        mock_update.data = [{"id": "uuid-1", "decision_id": "DEC_FPT_01"}]
        mock_client.table("decision_forward_returns").update().eq().execute.return_value = mock_update

        res = update_decision_forward_returns(
            "DEC_FPT_01",
            {"symbol": "FPT", "snapshot_price": 60.0, "t1_return_pct": 2.5},
        )
        assert res is True
        mock_client.table("decision_forward_returns").update().eq().execute.assert_called_once()

    @patch("db_manager.get_supabase_client")
    def test_upsert_fallback_to_select_and_insert(self, mock_get_client):
        """When upsert fails and no existing record found, it falls back to insert."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        # Mock upsert raising exception
        mock_client.table("decision_forward_returns").upsert().execute.side_effect = Exception("42P10 error")

        # Mock select finding no record
        mock_select = MagicMock()
        mock_select.data = []
        mock_client.table("decision_forward_returns").select().eq().limit().execute.return_value = mock_select

        # Mock insert succeeding
        mock_insert = MagicMock()
        mock_insert.data = [{"id": "new-uuid", "decision_id": "DEC_HPG_01"}]
        mock_client.table("decision_forward_returns").insert().execute.return_value = mock_insert

        res = update_decision_forward_returns(
            "DEC_HPG_01",
            {"symbol": "HPG", "snapshot_price": 28.0, "t5_return_pct": 5.0},
        )
        assert res is True
        mock_client.table("decision_forward_returns").insert().execute.assert_called_once()


class TestTickerValidationAndPayloadCalculation:
    """Test ticker validation and forward return calculation helper."""

    def test_is_valid_ticker(self):
        assert _is_valid_ticker("FPT") is True
        assert _is_valid_ticker("hpg") is True
        assert _is_valid_ticker("VNINDEX") is True
        assert _is_valid_ticker("GOOD1") is False
        assert _is_valid_ticker("AB") is False
        assert _is_valid_ticker("123") is False

    def test_calculate_record_payload_accuracy(self):
        series_map = {
            "FPT": {
                "dates": ["2026-10-01", "2026-10-02", "2026-10-05", "2026-10-06", "2026-10-07", "2026-10-08"],
                "prices": {
                    "2026-10-01": 100.0,
                    "2026-10-02": 102.0,  # T+1 -> +2.0%
                    "2026-10-05": 103.0,
                    "2026-10-06": 105.0,  # T+3 -> +5.0%
                    "2026-10-07": 106.0,
                    "2026-10-08": 110.0,  # T+5 -> +10.0%
                },
            },
            "VNINDEX": {
                "dates": ["2026-10-01", "2026-10-02", "2026-10-05", "2026-10-06", "2026-10-07", "2026-10-08"],
                "prices": {
                    "2026-10-01": 1200.0,
                    "2026-10-08": 1260.0,  # +5.0%
                },
            },
        }

        rec = {
            "decision_id": "DEC_FPT_20261001_001",
            "symbol": "FPT",
            "created_at": "2026-10-01T09:30:00+07:00",
            "facts": {"snapshot_price": 100.0},
        }

        payload = _calculate_record_payload(rec, series_map)
        assert payload is not None
        assert payload["decision_id"] == "DEC_FPT_20261001_001"
        assert payload["snapshot_price"] == 100.0
        assert payload["t1_return_pct"] == 2.0
        assert payload["t3_return_pct"] == 5.0
        assert payload["t5_return_pct"] == 10.0
        assert payload["t10_return_pct"] is None
        assert payload["vnindex_t5_pct"] == 5.0

    def test_get_hose_tick_size(self):
        assert get_hose_tick_size(8.5) == 0.01
        assert get_hose_tick_size(20.5) == 0.05
        assert get_hose_tick_size(55.0) == 0.10

    def test_calc_hose_ceiling_floor(self):
        # HPG at 20.80
        ceil_p, floor_p = calc_hose_ceiling_floor(20.80)
        assert ceil_p == 22.25
        assert floor_p == 19.35

        # Stock at 8.00 (tick 0.01)
        ceil_p, floor_p = calc_hose_ceiling_floor(8.00)
        assert ceil_p == 8.56
        assert floor_p == 7.44

    def test_calc_exchange_ceiling_floor(self):
        # HNX (+-10%, tick 0.10)
        ceil_p, floor_p = calc_exchange_ceiling_floor(40.0, "HNX")
        assert ceil_p == 44.0
        assert floor_p == 36.0

        # UPCOM (+-15%, tick 0.10)
        ceil_p, floor_p = calc_exchange_ceiling_floor(20.0, "UPCOM")
        assert ceil_p == 23.0
        assert floor_p == 17.0

        # HOSE fallback
        ceil_p, floor_p = calc_exchange_ceiling_floor(20.80, "HOSE")
        assert ceil_p == 22.25
        assert floor_p == 19.35

    def test_filter_canonical_and_deduplicate(self):
        records = [
            # Pre-14/10: should take latest created_at
            {"symbol": "HPG", "created_at": "2026-10-05T08:45:00", "facts": {"snapshot_price": 20.0}},
            {"symbol": "HPG", "created_at": "2026-10-05T13:15:00", "facts": {"snapshot_price": 20.5}},
            # Post-14/10: should only take is_canonical=True
            {"symbol": "HPG", "created_at": "2026-10-14T08:45:00", "is_canonical": False},
            {"symbol": "HPG", "created_at": "2026-10-14T15:00:00", "is_canonical": True},
        ]
        filtered = filter_canonical_and_deduplicate(records)
        assert len(filtered) == 2
        assert filtered[0]["created_at"] == "2026-10-05T13:15:00"
        assert filtered[1]["created_at"] == "2026-10-14T15:00:00"

    def test_calculate_dual_returns_with_ohlc(self):
        series_map = {
            "HPG": {
                "dates": ["2026-10-14", "2026-10-15"],
                "prices": {"2026-10-14": 20.80, "2026-10-15": 20.75},
                "ohlc": {
                    "2026-10-14": {"open": 20.45, "high": 20.90, "low": 20.35, "close": 20.80},
                    "2026-10-15": {"open": 20.60, "high": 21.05, "low": 20.60, "close": 20.75},
                },
            },
            "VNINDEX": {
                "dates": ["2026-10-14", "2026-10-15"],
                "prices": {"2026-10-14": 1704.87, "2026-10-15": 1698.35},
                "ohlc": {
                    "2026-10-14": {"open": 1720.91, "high": 1722.65, "low": 1700.74, "close": 1704.87},
                    "2026-10-15": {"open": 1701.20, "high": 1709.54, "low": 1694.77, "close": 1698.35},
                },
            },
        }

        rec = {
            "decision_id": "DEC_HPG_20261014_150057",
            "symbol": "HPG",
            "created_at": "2026-10-14T15:00:57+00:00",
            "is_canonical": True,
            "facts": {"snapshot_price": 20.80},
        }

        payload = _calculate_record_payload(rec, series_map)
        assert payload is not None
        # Signal T+1: (20.75 - 20.80) / 20.80 = -0.240%
        assert payload["signal_returns"][1] == -0.240
        # VN-Index Signal T+1: (1698.35 - 1704.87) / 1704.87 = -0.382%
        assert payload["vnindex_signal"][1] == -0.382
        # Executable T+1: (20.75 - 20.60) / 20.60 = +0.728%
        assert payload["executable_returns"][1] == 0.728
        # VN-Index Executable T+1: (1698.35 - 1701.20) / 1701.20 = -0.168%
        assert payload["vnindex_executable"][1] == -0.168
        # Entry ceiling locked
        assert payload["entry_ceiling_locked"] is False
        # Matured horizons
        assert payload["matured_horizons"] == [1]
        # Ceilings and floors audit values
        assert payload["ceilings"][1] == 22.25
        assert payload["floors"][1] == 19.35


class TestLifecycleEventsWiring:
    """Test saving lifecycle events in-memory and validation."""

    def test_save_lifecycle_event_veto_evaluated(self):
        with patch("db_manager.get_supabase_client", return_value=None):
            evt = {
                "symbol": "TCB",
                "correlation_id": "DEC_TCB_20261012_01",
                "event_type": EVENT_AI_VETO_EVALUATED,
                "event_data": {"ai_action": "REDUCE_SIZING", "sizing_factor": 0.5},
            }
            res = save_lifecycle_event(evt)
            assert res is not None

            events = get_lifecycle_events(correlation_id="DEC_TCB_20261012_01")
            assert len(events) >= 1
            assert events[0]["event_type"] == EVENT_AI_VETO_EVALUATED
            assert events[0]["event_data"]["sizing_factor"] == 0.5

    def test_save_lifecycle_event_watchlist_removed(self):
        from db_manager import EVENT_WATCHLIST_REMOVED

        with patch("db_manager.get_supabase_client", return_value=None):
            evt = {
                "symbol": "NVL",
                "correlation_id": "WL_REM_NVL_20261019_150000",
                "event_type": EVENT_WATCHLIST_REMOVED,
                "event_data": {"reason": "Gãy hỗ trợ MA20", "current_price": 10.5},
            }
            res = save_lifecycle_event(evt)
            assert res is not None

            events = get_lifecycle_events(correlation_id="WL_REM_NVL_20261019_150000")
            assert len(events) >= 1
            assert events[0]["event_type"] == EVENT_WATCHLIST_REMOVED
            assert events[0]["event_data"]["current_price"] == 10.5

    def test_save_lifecycle_event_rejects_boolean_correlation_id(self):

        # Must reject boolean True/False, empty string, string "True"/"False", and non-string
        invalid_corrs = [True, False, "True", "False", "true", "", "   ", 12345, None]
        for bad_corr in invalid_corrs:
            evt = {
                "symbol": "FPT",
                "correlation_id": bad_corr,
                "event_type": EVENT_AI_VETO_EVALUATED,
                "event_data": {"price": 100.0},
            }
            res = save_lifecycle_event(evt)
            assert res is None, f"Expected None for invalid correlation_id: {bad_corr}"

    def test_can_write_to_database_guard(self, monkeypatch):
        from db_manager import can_write_to_database, is_production_environment

        monkeypatch.setenv("APP_ENV", "production")
        assert is_production_environment() is True
        assert can_write_to_database() is True

        monkeypatch.setenv("APP_ENV", "prod")
        assert is_production_environment() is True
        assert can_write_to_database() is True

        monkeypatch.setenv("APP_ENV", "development")
        monkeypatch.delenv("ALLOW_DEV_LIVE_WRITES", raising=False)
        monkeypatch.delenv("SUPABASE_DEV_URL", raising=False)
        assert is_production_environment() is False
        assert can_write_to_database() is False

        monkeypatch.setenv("APP_ENV", "testing")
        assert is_production_environment() is False
        assert can_write_to_database() is False



class TestLeaveOneOutBenchmarksAndLatestHorizons:
    """Test Leave-One-Out sector benchmarks, NaN threshold (< 3 stocks), and *_latest columns."""

    def test_leave_one_out_and_nan_threshold(self):
        # 6 stocks across 3 sectors:
        # Sector "Tech": 1 stock (FPT) -> count < 3 -> LOO is None/NaN
        # Sector "Securities": 2 stocks (SSI, VND) -> count < 3 -> LOO is None/NaN
        # Sector "Steel": 3 stocks (HPG, HSG, NKG) -> count >= 3 -> LOO calculated
        data = [
            {"symbol": "FPT", "sector": "Tech", "decision": "WATCH", "exec_t1_pct": 3.0, "matured_t1": True, "matured_t3": False},
            {"symbol": "SSI", "sector": "Securities", "decision": "REJECT", "exec_t1_pct": 2.0, "matured_t1": True, "matured_t3": False},
            {"symbol": "VND", "sector": "Securities", "decision": "REJECT", "exec_t1_pct": 4.0, "matured_t1": True, "matured_t3": False},
            {"symbol": "HPG", "sector": "Steel", "decision": "WATCH", "exec_t1_pct": 1.0, "matured_t1": True, "matured_t3": False},
            {"symbol": "HSG", "sector": "Steel", "decision": "REJECT", "exec_t1_pct": 3.0, "matured_t1": True, "matured_t3": False},
            {"symbol": "NKG", "sector": "Steel", "decision": "REJECT", "exec_t1_pct": 5.0, "matured_t1": True, "matured_t3": False},
        ]
        df = pd.DataFrame(data)
        res = _calculate_benchmarks_and_excess(df)

        # Tech (1 stock): LOO benchmark and excess must be None
        fpt = res[res["symbol"] == "FPT"].iloc[0]
        assert fpt["sector_exec_t1_pct"] is None
        assert fpt["excess_vs_sector_t1_pct"] is None

        # Securities (2 stocks): LOO benchmark and excess must be None
        ssi = res[res["symbol"] == "SSI"].iloc[0]
        assert ssi["sector_exec_t1_pct"] is None
        assert ssi["excess_vs_sector_t1_pct"] is None

        # Steel (3 stocks: 1.0, 3.0, 5.0):
        # HPG (1.0): peer average is (3.0 + 5.0)/2 = 4.0 -> excess = 1.0 - 4.0 = -3.0
        hpg = res[res["symbol"] == "HPG"].iloc[0]
        assert hpg["sector_exec_t1_pct"] == 4.0
        assert hpg["excess_vs_sector_t1_pct"] == -3.0

        # HSG (3.0): peer average is (1.0 + 5.0)/2 = 3.0 -> excess = 3.0 - 3.0 = 0.0
        hsg = res[res["symbol"] == "HSG"].iloc[0]
        assert hsg["sector_exec_t1_pct"] == 3.0
        assert hsg["excess_vs_sector_t1_pct"] == 0.0

        # NKG (5.0): peer average is (1.0 + 3.0)/2 = 2.0 -> excess = 5.0 - 2.0 = +3.0
        nkg = res[res["symbol"] == "NKG"].iloc[0]
        assert nkg["sector_exec_t1_pct"] == 2.0
        assert nkg["excess_vs_sector_t1_pct"] == 3.0

        # Latest horizon aliases
        assert res["latest_horizon"].iloc[0] == "T+1"
        assert "excess_vs_universe_latest" in res.columns
        assert "excess_vs_sector_latest" in res.columns
        # Ambiguous un-suffixed columns must be removed
        assert "excess_vs_universe" not in res.columns
        assert "excess_vs_sector" not in res.columns

    def test_latest_horizon_precedence(self):
        # If both T+1 and T+3 are matured, latest_horizon should be "T+3"
        data = [
            {"symbol": "HPG", "sector": "Steel", "decision": "WATCH", "exec_t1_pct": 1.0, "exec_t3_pct": 2.5, "matured_t1": True, "matured_t3": True},
            {"symbol": "HSG", "sector": "Steel", "decision": "REJECT", "exec_t1_pct": 2.0, "exec_t3_pct": 3.5, "matured_t1": True, "matured_t3": True},
            {"symbol": "NKG", "sector": "Steel", "decision": "REJECT", "exec_t1_pct": 3.0, "exec_t3_pct": 4.5, "matured_t1": True, "matured_t3": True},
        ]
        df = pd.DataFrame(data)
        res = _calculate_benchmarks_and_excess(df)
        assert res["latest_horizon"].iloc[0] == "T+3"
        assert res["excess_vs_universe_latest"].iloc[0] == res["excess_vs_universe_t3_pct"].iloc[0]


class TestSectorStratifiedBaselineSimulation:
    """Test Sector-Stratified Random Permutation Baseline simulation."""

    def test_simulate_sector_stratified_baseline_accuracy(self):
        # 8 stocks in 2 sectors:
        # Bank: 4 stocks, WATCH picks 2
        # RealEstate: 4 stocks, WATCH picks 1
        data = [
            {"symbol": "VCB", "sector": "Bank", "decision": "WATCH", "exec_t1_pct": 4.0, "matured_t1": True},
            {"symbol": "BID", "sector": "Bank", "decision": "WATCH", "exec_t1_pct": 5.0, "matured_t1": True},
            {"symbol": "CTG", "sector": "Bank", "decision": "REJECT", "exec_t1_pct": 1.0, "matured_t1": True},
            {"symbol": "MBB", "sector": "Bank", "decision": "REJECT", "exec_t1_pct": 2.0, "matured_t1": True},
            {"symbol": "VHM", "sector": "RealEstate", "decision": "WATCH", "exec_t1_pct": 3.0, "matured_t1": True},
            {"symbol": "VIC", "sector": "RealEstate", "decision": "REJECT", "exec_t1_pct": 0.5, "matured_t1": True},
            {"symbol": "VRE", "sector": "RealEstate", "decision": "REJECT", "exec_t1_pct": 1.0, "matured_t1": True},
            {"symbol": "NVL", "sector": "RealEstate", "decision": "REJECT", "exec_t1_pct": 1.5, "matured_t1": True},
        ]
        df = pd.DataFrame(data)
        sim = simulate_sector_stratified_baseline(df, horizon=1, n_simulations=1000, seed=42)

        assert sim is not None
        assert sim["horizon"] == "T+1"
        assert sim["n_watch"] == 3
        assert sim["n_reject"] == 5
        # WATCH mean = (4.0 + 5.0 + 3.0) / 3 = 4.0
        assert sim["watch_mean"] == 4.0
        # REJECT mean = (1.0 + 2.0 + 0.5 + 1.0 + 1.5) / 5 = 1.2
        assert sim["reject_mean"] == 1.2
        assert sim["observed_spread"] == 2.8
        # Because WATCH picked the top stocks in both Bank and RealEstate:
        # Selection alpha should be strictly positive
        assert sim["selection_alpha_vs_sector_baseline"] > 0
        assert 0.0 <= sim["p_value_watch_return"] <= 1.0
        assert 0.0 <= sim["p_value_spread"] <= 1.0

    def test_simulate_sector_stratified_baseline_edge_cases(self):
        # Empty df
        assert simulate_sector_stratified_baseline(pd.DataFrame(), horizon=1) is None

        # Missing horizon column
        df = pd.DataFrame([{"symbol": "FPT", "sector": "Tech", "decision": "WATCH"}])
        assert simulate_sector_stratified_baseline(df, horizon=1) is None

        # No WATCH decisions (all REJECT)
        df_no_watch = pd.DataFrame([
            {"symbol": "HPG", "sector": "Steel", "decision": "REJECT", "exec_t1_pct": 1.0, "matured_t1": True},
            {"symbol": "HSG", "sector": "Steel", "decision": "REJECT", "exec_t1_pct": 2.0, "matured_t1": True},
        ])
        assert simulate_sector_stratified_baseline(df_no_watch, horizon=1) is None

    def test_normalize_date(self):
        assert _normalize_date("20261015") == "2026-10-15"
        assert _normalize_date("2026-10-15") == "2026-10-15"
        assert _normalize_date("  20261016  ") == "2026-10-16"



