# -*- coding: utf-8 -*-
"""Unit tests for Lifecycle Events & Forward Returns Wiring (Audit Trail & Performance Attribution)."""

from unittest.mock import MagicMock, patch

from db_manager import (
    EVENT_AI_VETO_EVALUATED,
    get_lifecycle_events,
    save_lifecycle_event,
    update_decision_forward_returns,
)
from scripts.update_forward_returns import (
    _calculate_record_payload,
    _is_valid_ticker,
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
