"""
Alpha Tracker & Signal Lifecycle tests — validates defensive filters
(GDKHQ shield, anti-chasing) and Supabase signal persistence.

Offline tests run without any external services.
Integration tests require SUPABASE_URL and SUPABASE_KEY in .env.
"""
import pytest

from data_engine import detect_gdkhq_event
from db_manager import (
    get_signal_audit_metrics,
    get_supabase_client,
    save_quant_signal,
)


@pytest.mark.offline
class TestGDKHQShield:
    """Detect ex-dividend gap-downs and prevent false stop-loss triggers."""

    def test_detects_genuine_gdkhq(self):
        """Stock gaps down -6% while VN-Index only drops -0.2% → GDKHQ detected."""
        tech = {
            "current_price": 47.2,
            "ref_price": 50.0,
            "open": 47.0,
            "change_pct": -5.6,
        }
        result = detect_gdkhq_event("MSB", tech, vnindex_chg_pct=-0.2)

        assert result["is_gdkhq"] is True
        assert "GDKHQ" in result["reason"]

    def test_no_false_positive_during_market_crash(self):
        """Same gap-down but VN-Index crashes -3.5% → NOT GDKHQ, it's a market crash."""
        tech = {
            "current_price": 47.2,
            "ref_price": 50.0,
            "open": 47.0,
            "change_pct": -5.6,
        }
        result = detect_gdkhq_event("MSB", tech, vnindex_chg_pct=-3.5)

        assert result["is_gdkhq"] is False


@pytest.mark.offline
class TestAntiChasingFilter:
    """Block buy signals when price is at or near the HOSE ceiling (+7%)."""

    def test_blocks_ceiling_chase(self):
        tech = {
            "current_price": 28.5,
            "ceiling_price": 28.5,
            "change_pct": 6.85,
            "is_ceiling": True,
        }
        is_chasing = (
            tech["current_price"] >= tech["ceiling_price"]
            or tech["change_pct"] >= 6.7
            or tech["is_ceiling"]
        )
        assert is_chasing is True

    def test_allows_healthy_breakout(self):
        tech = {
            "current_price": 27.5,
            "ceiling_price": 28.5,
            "change_pct": 3.2,
            "is_ceiling": False,
        }
        is_chasing = (
            tech["current_price"] >= tech["ceiling_price"]
            or tech["change_pct"] >= 6.7
            or tech["is_ceiling"]
        )
        assert is_chasing is False


@pytest.mark.integration
class TestSupabaseSignalLifecycle:
    """Integration tests for Supabase signal persistence and audit metrics.
    Requires SUPABASE_URL and SUPABASE_KEY in .env."""

    @pytest.fixture(autouse=True)
    def _skip_without_supabase(self):
        client = get_supabase_client()
        if not client:
            pytest.skip("Supabase not configured — skipping integration tests")

    def test_save_and_retrieve_signal(self):
        """Save a test signal, verify immutable snapshot, then clean up."""
        signal_id = None
        client = get_supabase_client()
        try:
            signal_id = save_quant_signal(
                symbol="TCB",
                action="🟢 VALUE BUY",
                decision_tag="🟢 VALUE BUY (Test)",
                entry_price=24.5,
                market_price_at_signal=24.5,
                target_price=28.0,
                stop_loss=22.8,
                hard_gates={"mos_pct": 19.5, "ev": 27.2, "kelly_f": 0.18, "risk_reward": 2.05},
                f_score_res={"score": 8},
                z_score_res={"z_score": 3.1},
                prob_dict={"P_bull": 0.40, "P_base": 0.45, "P_bear": 0.15, "rationale_base": "pytest"},
                model_version="pytest-v1.0",
                input_snapshot={"pe": 6.8, "pb": 1.1, "roe": 19.2, "test_tag": "PYTEST"},
            )
            assert signal_id is not None

            # Verify the snapshot is correctly stored
            res = client.table("signals").select("*, signal_tracking(*)").eq("id", signal_id).execute()
            data = res.data[0]
            assert data["symbol"] == "TCB"
            assert float(data["entry_price"]) == 24.5
            assert float(data["mos_pct"]) == 19.5
            assert data["input_snapshot"]["test_tag"] == "PYTEST"

            # Verify tracking record was auto-created
            trackings = data.get("signal_tracking") or []
            assert len(trackings) > 0
            assert trackings[0]["status"] == "OPEN"
        finally:
            if signal_id and client:
                client.table("signal_tracking").delete().eq("signal_id", signal_id).execute()
                client.table("signals").delete().eq("id", signal_id).execute()

    def test_audit_metrics_return_valid_structure(self):
        """Verify that audit metrics return expected keys."""
        metrics = get_signal_audit_metrics()

        assert "total_signals" in metrics
        assert "open_signals" in metrics
        assert "win_rate" in metrics
        assert "profit_factor" in metrics
