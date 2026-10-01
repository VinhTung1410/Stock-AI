"""Unit tests for TASK-0014: Decision Records, Migration 0003 & Dispatcher Decoupling.

Validates:
- AC-7a: 4-Tier DecisionRecord schema (Facts, Inferences, Opinions, Counterfactual)
- AC-7b: Database methods (save_decision_record, get_decision_records, update_decision_forward_returns)
- AC-7f.1: SignalEngine & Dispatcher decoupling (SignalEvent, dispatch_signal_event, zero test leakage)
- AC-7f.2: Batch dispatch and Kill Switch alert dispatch
- AC-7f.3: Evidence-based Kill Switch calculation (triggers on Expectancy R < 0)
"""

from unittest.mock import MagicMock, patch

from db_manager import (
    check_evidence_kill_switch,
    get_decision_records,
    save_decision_record,
    update_decision_forward_returns,
)
from dispatcher import (
    SignalEvent,
    dispatch_decision_batch,
    dispatch_kill_switch_alert,
    dispatch_signal_event,
)


# =============================================================================
# AC-7a & AC-7f.1: SIGNAL EVENT & DISPATCHER DECOUPLING
# =============================================================================
class TestDispatcherDecoupling:
    """Test AC-7f.1: SignalEvent serialization and isolated dispatching."""

    def test_signal_event_serialization(self):
        """SignalEvent correctly instantiates and converts to dict."""
        event = SignalEvent(
            symbol="HPG",
            action="MUA",
            current_price=28.5,
            target_price=32.0,
            stop_loss=26.5,
            conviction_score=82.0,
            mos_pct=18.5,
            f_score=7,
        )
        d = event.to_dict()
        assert d["symbol"] == "HPG"
        assert d["action"] == "MUA"
        assert d["current_price"] == 28.5
        assert d["conviction_score"] == 82.0
        assert "timestamp" in d

    @patch("dispatcher.send_trade_signal_alert")
    def test_dispatch_signal_event_buy(self, mock_alert):
        """Buying SignalEvent triggers send_trade_signal_alert."""
        mock_alert.return_value = True
        event = SignalEvent(
            symbol="TCB",
            action="MUA",
            current_price=35.0,
            target_price=40.0,
            stop_loss=32.5,
            conviction_score=78.0,
            mos_pct=22.0,
            f_score=8,
        )
        success = dispatch_signal_event(event)
        assert success is True
        mock_alert.assert_called_once()
        call_kwargs = mock_alert.call_args[1]
        assert call_kwargs["symbol"] == "TCB"
        assert call_kwargs["action"] == "MUA"
        assert call_kwargs["current_price"] == 35.0

    @patch("dispatcher.send_trade_signal_alert")
    def test_dispatch_signal_event_reject_skipped(self, mock_alert):
        """REJECT or WATCH event does not trigger trade signal alert."""
        event = SignalEvent(
            symbol="VHM",
            action="REJECT",
            current_price=42.0,
            conviction_score=40.0,
        )
        success = dispatch_signal_event(event)
        assert success is True
        mock_alert.assert_not_called()

    @patch("dispatcher.send_discord_webhook")
    @patch("dispatcher.send_discord_dm")
    def test_dispatch_decision_batch(self, mock_dm, mock_webhook):
        """Decision batch summary dispatches cleanly to webhook & DM."""
        decisions = [
            {"symbol": "HPG", "decision": "BUY"},
            {"symbol": "TCB", "decision": "WATCH"},
            {"symbol": "VIC", "decision": "REJECT"},
        ]
        res = dispatch_decision_batch(decisions, session="NOON")
        assert res is True
        mock_webhook.assert_called_once()
        mock_dm.assert_called_once()

    @patch("dispatcher.send_discord_webhook")
    @patch("dispatcher.send_discord_dm")
    def test_dispatch_kill_switch_alert(self, mock_dm, mock_webhook):
        """Kill switch alert dispatches warning embed when triggered."""
        kill_data = {
            "is_triggered": True,
            "expectancy_r": -0.45,
            "sample_size": 20,
            "size_reduction_pct": 50.0,
            "reason": "Negative Expectancy (-0.45R)",
        }
        res = dispatch_kill_switch_alert(kill_data)
        assert res is True
        mock_webhook.assert_called_once()
        mock_dm.assert_called_once()


# =============================================================================
# AC-7b: DATABASE METHODS (DECISION RECORDS & FORWARD RETURNS)
# =============================================================================
class TestDecisionRecordsDatabase:
    """Test AC-7b: CRUD operations for decision_records and forward returns."""

    @patch("db_manager.get_supabase_client")
    def test_save_decision_record_success(self, mock_supa):
        """Save decision record inserts into decision_records table."""
        mock_client = MagicMock()
        mock_supa.return_value = mock_client
        mock_client.table("decision_records").insert().execute.return_value = MagicMock(data=[{"id": "rec-1"}])

        rec = {
            "symbol": "SSI",
            "session": "NOON",
            "decision": "BUY",
            "facts": {"price": 30.0},
            "inferences": {"f_score": 7, "mos_pct": 16.0},
            "opinions": {"llm_decision": "MUA"},
            "counterfactual": {},
        }
        dec_id = save_decision_record(rec)
        assert dec_id is not None
        assert dec_id.startswith("DEC_SSI_")

    @patch("db_manager.get_supabase_client")
    def test_get_decision_records_with_filters(self, mock_supa):
        """Query decision records passes filters correctly."""
        mock_client = MagicMock()
        mock_supa.return_value = mock_client
        mock_query = mock_client.table("decision_records").select().order().limit()
        mock_query.eq.return_value = mock_query
        mock_query.execute.return_value = MagicMock(data=[{"symbol": "HPG", "decision": "BUY"}])

        res = get_decision_records(filters={"symbol": "HPG", "decision": "BUY"})
        assert len(res) == 1
        assert res[0]["symbol"] == "HPG"

    @patch("db_manager.get_supabase_client")
    def test_update_decision_forward_returns(self, mock_supa):
        """Forward returns upsert executes successfully."""
        mock_client = MagicMock()
        mock_supa.return_value = mock_client
        mock_client.table("decision_forward_returns").upsert().execute.return_value = MagicMock(data=[{"id": "fwd-1"}])

        ret_data = {
            "symbol": "HPG",
            "snapshot_price": 28.0,
            "t1_return_pct": 1.2,
            "t5_return_pct": 4.5,
            "vnindex_t5_pct": 2.0,
        }
        success = update_decision_forward_returns("DEC_HPG_1", ret_data)
        assert success is True


# =============================================================================
# AC-7f.3: EVIDENCE-BASED KILL SWITCH
# =============================================================================
class TestEvidenceKillSwitch:
    """Test AC-7f.3: Kill switch halts or reduces size when Expectancy R < 0."""

    @patch("db_manager.get_supabase_client")
    def test_kill_switch_triggered_on_negative_expectancy(self, mock_supa):
        """When average R across last 20 closed trades is negative, trigger Kill Switch."""
        mock_client = MagicMock()
        mock_supa.return_value = mock_client
        # 10 losing trades with -1.0R and 5 small wins with +0.5R -> average R = (-10 + 2.5) / 15 = -0.5R
        trades = [{"r_multiple": -1.0, "status": "STOP_LOSS"}] * 10 + [{"r_multiple": 0.5, "status": "TARGET_HIT"}] * 5
        mock_client.table("signal_lifecycle").select().in_().order().limit().execute.return_value = MagicMock(
            data=trades
        )

        res = check_evidence_kill_switch(lookback_trades=20)
        assert res["is_triggered"] is True
        assert res["expectancy_r"] < 0.0
        assert res["size_reduction_pct"] == 50.0

    @patch("db_manager.get_supabase_client")
    def test_kill_switch_not_triggered_on_positive_expectancy(self, mock_supa):
        """When average R is positive, Kill Switch is not triggered."""
        mock_client = MagicMock()
        mock_supa.return_value = mock_client
        trades = [{"r_multiple": 1.5, "status": "TARGET_HIT"}] * 8 + [{"r_multiple": -1.0, "status": "STOP_LOSS"}] * 4
        mock_client.table("signal_lifecycle").select().in_().order().limit().execute.return_value = MagicMock(
            data=trades
        )

        res = check_evidence_kill_switch(lookback_trades=20)
        assert res["is_triggered"] is False
        assert res["expectancy_r"] > 0.0
        assert res["size_reduction_pct"] == 0.0
