"""Unit tests for TASK-0013: Evidence Integrity & ADR-0002 (Phase 7.0).

Validates:
- AC-7.0a: Holding-period Alpha calculation (T_in -> T_out vs VN-Index & VN30)
- AC-7.0b: Idempotent Replay & Conservative Exit (STOP before TARGET on same bar) + T+2.5 lock
- AC-7.0c: Stale consensus de-weighting (>180d) in Fair Value & MoS
- AC-7.0d: mos_is_informative flag for synthetic multiplier vs genuine valuation
- AC-7.0e: Real financial ratios in Data Gate & INSUFFICIENT_DATA handling
- AC-7.0f: Technical timing test UI classification
- AC-7.0g: ADR-0002 reconciliation and LOCKED_QUANT_THRESHOLDS verification
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from db_manager import (
    calculate_holding_period_benchmark_return,
    replay_signal_path,
    update_daily_tracking,
)
from quant_engine import LOCKED_QUANT_THRESHOLDS
from quant_valuation import calculate_fair_value_and_mos


# =============================================================================
# 7.0a: HOLDING-PERIOD ALPHA & BENCHMARK RETURNS
# =============================================================================
class TestHoldingPeriodAlpha:
    """Test AC-7.0a: Alpha = PnL - Benchmark_Return(T_in -> T_out)."""

    def test_calculate_holding_period_benchmark_return_with_df(self):
        """Verify holding period return aligns between start_date and end_date."""
        dates = pd.date_range("2026-01-01", periods=10, freq="D")
        closes = [1200.0, 1210.0, 1220.0, 1230.0, 1240.0, 1250.0, 1260.0, 1270.0, 1280.0, 1300.0]
        df_bench = pd.DataFrame({"time": dates, "close": closes})

        # From Day 0 (1200) to Day 9 (1300) -> Return = (1300-1200)/1200 = +8.33%
        ret = calculate_holding_period_benchmark_return(
            benchmark_symbol="VNINDEX",
            start_date="2026-01-01",
            end_date="2026-01-10",
            benchmark_df=df_bench,
        )
        assert ret == pytest.approx(8.33, abs=0.05)

    def test_calculate_holding_period_benchmark_fallback(self):
        """Verify fallback daily change is returned if benchmark df is empty."""
        ret = calculate_holding_period_benchmark_return(
            benchmark_symbol="VNINDEX",
            start_date="2026-01-01",
            end_date="2026-01-10",
            benchmark_df=pd.DataFrame(),
            fallback_daily_chg=-1.5,
        )
        assert ret == -1.5

    @patch("db_manager.get_supabase_client")
    @patch("data_engine.fetch_stock_technical")
    @patch("db_manager.fetch_open_signals")
    def test_update_daily_tracking_holding_alpha(self, mock_signals, mock_tech, mock_supa):
        """Verify update_daily_tracking calculates holding-period alpha."""
        mock_client = MagicMock()
        mock_supa.return_value = mock_client

        # VNINDEX today change is +0.5%, but over the whole period index was +3.0%
        mock_tech.side_effect = lambda sym: {
            "VNINDEX": {"current_price": 1250.0, "change_pct": 0.5},
            "HPG": {"current_price": 28.0, "high": 28.0, "low": 24.0},
        }.get(sym)

        # Signal entered 5 days ago at 25.0, target 28.0 (+12.0%)
        mock_signals.return_value = [
            {
                "id": "sig-1",
                "symbol": "HPG",
                "entry_price": 25.0,
                "target_price": 28.0,
                "stop_loss": 23.5,
                "created_at": (datetime.now(timezone.utc) - timedelta(days=5)).isoformat(),
                "tracking": {"id": "trk-1"},
            }
        ]

        with patch("db_manager.calculate_holding_period_benchmark_return", return_value=3.0):
            res = update_daily_tracking()

        assert res["status"] == "SUCCESS"
        mock_client.table("signal_tracking").update.assert_called()
        update_args = mock_client.table("signal_tracking").update.call_args[0][0]
        assert update_args["status"] == "TARGET_HIT"
        assert update_args["actual_pnl_pct"] == 12.0
        # Alpha should be 12.0 - 3.0 = 9.0%, NOT 12.0 - 0.5 = 11.5%
        assert update_args["pnl_vs_vnindex"] == 9.0


# =============================================================================
# 7.0b: IDEMPOTENT REPLAY & CONSERVATIVE EXIT & T+2.5 LOCK
# =============================================================================
class TestIdempotentReplayAndConservativeExit:
    """Test AC-7.0b: replay_signal_path priority STOP over TARGET when both breach on same bar."""

    def test_conservative_exit_stop_before_target_same_bar(self):
        """When high >= target AND low <= stop in the same bar, system MUST exit via STOP_LOSS."""
        # Entry at 100, Target at 112 (+12%), Stop at 93 (-7%)
        # Bar 1 hits high=115 and low=90 in the very same day!
        dates = pd.date_range("2026-02-01", periods=3, freq="D")
        df_ohlc = pd.DataFrame(
            {
                "time": dates,
                "open": [100.0, 100.0, 100.0],
                "high": [101.0, 115.0, 105.0],
                "low": [99.0, 90.0, 98.0],
                "close": [100.0, 95.0, 102.0],
            }
        )

        sig = {
            "symbol": "TEST",
            "entry_price": 100.0,
            "target_price": 112.0,
            "stop_loss": 93.0,
            "created_at": "2026-02-01",
        }

        res = replay_signal_path(sig, df_ohlc)
        # Conservative check: STOP_LOSS MUST take priority over TARGET_HIT!
        assert res["status"] == "STOP_LOSS"
        assert res["exit_price"] == 93.0
        assert res["actual_pnl_pct"] == -7.0
        assert res["exit_bar"] == 1
        assert res["t_plus_2_locked"] is True  # Exit at bar 1 (< 2 bars) is before T+2.5

    def test_replay_signal_path_idempotency(self):
        """Running replay multiple times produces identical outcome."""
        dates = pd.date_range("2026-03-01", periods=5, freq="D")
        df_ohlc = pd.DataFrame(
            {
                "time": dates,
                "open": [50.0, 51.0, 52.0, 55.0, 56.5],
                "high": [51.0, 53.0, 54.0, 57.0, 57.5],
                "low": [49.5, 50.5, 51.5, 54.0, 55.0],
                "close": [50.5, 52.5, 53.5, 56.5, 57.0],
            }
        )
        sig = {
            "symbol": "SSI",
            "entry_price": 50.0,
            "target_price": 56.0,
            "stop_loss": 46.5,
            "created_at": "2026-03-01",
        }

        res1 = replay_signal_path(sig, df_ohlc)
        res2 = replay_signal_path(sig, df_ohlc)

        assert res1 == res2
        assert res1["status"] == "TARGET_HIT"
        assert res1["exit_price"] == 56.0
        assert res1["exit_bar"] == 3
        assert res1["t_plus_2_locked"] is False  # Exit at bar 3 (>= 2 bars)


# =============================================================================
# 7.0c & 7.0d: VALUATION STALE CONSENSUS & INFORMATIVE MOS
# =============================================================================
class TestValuationFreshnessAndMoS:
    """Test AC-7.0c & AC-7.0d: Stale consensus de-weighting and informative MoS flag."""

    @patch("quant_valuation.check_institutional_target_freshness")
    def test_stale_consensus_target_excluded_from_fair_value(self, mock_freshness):
        """Consensus targets older than 180 days must be stripped with consensus_stale = True."""
        mock_freshness.return_value = {
            "symbol": "FPT",
            "has_target": True,
            "is_stale": True,
            "age_days": 250,
            "warning": "Target outdated by 250 days",
        }

        # Provide a stale consensus target of 160.0
        res = calculate_fair_value_and_mos(
            symbol="FPT",
            current_price=100.0,
            sector="Công nghệ",
            consensus_target=160.0,
        )

        assert res["consensus_stale"] is True
        assert res["confidence"] == "LOW"
        # Stale target must NOT override price_target
        assert res["price_target"] != 160.0

    def test_growth_archetype_uninformative_mos(self):
        """Growth stock using fixed 1.18x multiplier has mos_is_informative = False."""
        res = calculate_fair_value_and_mos(
            symbol="MWG",
            current_price=60.0,
            sector="Bán lẻ",
            consensus_target=0.0,
        )
        assert res["archetype"] == "GROWTH_COMPOUNDER"
        assert res["mos_is_informative"] is False


# =============================================================================
# 7.0e: REAL DATA GATE
# =============================================================================
class TestRealDataGate:
    """Test AC-7.0e: scan_market_opportunities returns INSUFFICIENT_DATA when missing BCTC."""

    @patch("data_engine.get_financial_ratios", return_value={})
    @patch("data_engine.fetch_stock_technical")
    def test_scan_market_opportunities_insufficient_data(self, mock_tech, _mock_fin):
        """When financial ratios are empty, opportunities must be rejected with INSUFFICIENT_DATA."""
        from data_engine import scan_market_opportunities

        mock_tech.return_value = {
            "current_price": 50.0,
            "ma20": 48.0,
            "ma50": 45.0,
            "rsi14": 55.0,
            "vol_ratio": 1.5,
            "change_pct": 1.2,
        }

        results = scan_market_opportunities(extra_symbols=["HPG"])
        hpg_res = next((r for r in results if r["symbol"] == "HPG"), None)
        assert hpg_res is not None
        assert hpg_res["status"] == "INSUFFICIENT_DATA"
        assert hpg_res["gate_passed"] is False


# =============================================================================
# 7.0g: ADR-0002 RECONCILIATION THRESHOLDS
# =============================================================================
class TestADR0002Reconciliation:
    """Test AC-7.0g: Verify LOCKED_QUANT_THRESHOLDS match ADR-0002."""

    def test_adr_0002_thresholds_exact_match(self):
        """Verify frozen values in quant_engine match ADR-0002 specification."""
        assert LOCKED_QUANT_THRESHOLDS["buy_conviction_min"] == 70.0
        assert LOCKED_QUANT_THRESHOLDS["watch_conviction_min"] == 55.0
        assert LOCKED_QUANT_THRESHOLDS["f_score_min"] == 6
        assert LOCKED_QUANT_THRESHOLDS["mos_min_pct"] == 15.0
        assert LOCKED_QUANT_THRESHOLDS["z_score_min"] == 1.80
        assert LOCKED_QUANT_THRESHOLDS["rsi_max_entry"] == 70.0
        assert LOCKED_QUANT_THRESHOLDS["sector_exposure_max_pct"] == 0.25
        assert LOCKED_QUANT_THRESHOLDS["pillar_weights"]["fa"] == 0.40
        assert LOCKED_QUANT_THRESHOLDS["pillar_weights"]["ta"] == 0.25
        assert LOCKED_QUANT_THRESHOLDS["pillar_weights"]["flow"] == 0.20
        assert LOCKED_QUANT_THRESHOLDS["pillar_weights"]["macro_news"] == 0.15
        assert LOCKED_QUANT_THRESHOLDS["adr_version"] == "ADR-0002"
