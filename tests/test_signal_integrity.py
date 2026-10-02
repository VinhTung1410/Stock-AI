# ==============================================================================
# Tests for Phase 16: Signal Integrity & Audit Cleanup (TASK-0052 - TASK-0057)
# ==============================================================================
from datetime import date, datetime, time, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

import db_manager
from data_engine import (
    _build_auto_watchlist_candidate,
    prune_unsuitable_watchlist,
)
from db_manager import (
    check_symbol_recent_signal,
    count_trading_days,
    save_quant_signal,
    save_signal_lifecycle,
)


@pytest.mark.offline
class TestSignalIntegrityTASK52To57:
    """Comprehensive test suite for Phase 16 Signal Integrity & Audit Cleanup."""

    # --------------------------------------------------------------------------
    # TASK-0052: Conditional save_quant_signal (BUY_ACTIONS only)
    # --------------------------------------------------------------------------
    @patch("db_manager.get_supabase_client")
    def test_save_quant_signal_blocks_non_buy_decisions(self, mock_get_client):
        """AC-52.1: Non-BUY decisions (THEO DÕI, GIẢM, TỪ CHỐI) must NOT be saved to signals."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        # Test non-buy actions
        non_buy_actions = ["🟡 THEO DÕI", "🔴 GIẢM / THOÁT", "HOLD", "TỪ CHỐI", "CẢNH BÁO"]
        for action in non_buy_actions:
            result = save_quant_signal(
                symbol="SSI",
                action=action,
                decision_tag="Test Watch",
                entry_price=35.0,
            )
            assert result is None, f"Action '{action}' should NOT be saved to signals table!"

        mock_client.table.assert_not_called()

    @patch("db_manager.get_supabase_client")
    def test_save_quant_signal_accepts_valid_buy_actions(self, mock_get_client):
        """AC-52.1: Valid BUY actions must be saved and create OPEN tracking records."""
        mock_client = MagicMock()
        mock_table = MagicMock()
        mock_insert = MagicMock()
        mock_insert.execute.return_value = MagicMock(data=[{"id": 888}])
        mock_table.insert.return_value = mock_insert
        mock_client.table.return_value = mock_table
        mock_get_client.return_value = mock_client

        valid_buys = ["🟢 MUA", "🟢 TÍCH LŨY", "🟢 ACCUMULATE", "🟢 VALUE BUY", "RECOMMEND_BUY", "MUA", "BUY"]
        for buy_act in valid_buys:
            sig_id = save_quant_signal(
                symbol="MWG",
                action=buy_act,
                decision_tag="Valid Buy",
                entry_price=50.0,
                target_price=60.0,
                stop_loss=46.0,
                hard_gates={"mos_pct": 20.0},
            )
            assert sig_id == 888

    # --------------------------------------------------------------------------
    # TASK-0053: Cooldown Key Matching Fix (MUA, TÍCH LŨY, ACCUMULATE, BUY)
    # --------------------------------------------------------------------------
    @patch("db_manager.get_supabase_client")
    def test_check_symbol_recent_signal_matches_all_buy_keywords(self, mock_get_client):
        """AC-52.2: check_symbol_recent_signal matches Vietnamese and English buy actions."""
        mock_client = MagicMock()
        mock_table = MagicMock()
        mock_select = MagicMock()
        mock_eq = MagicMock()
        mock_gte = MagicMock()
        mock_or = MagicMock()

        mock_client.table.return_value = mock_table
        mock_table.select.return_value = mock_select
        mock_select.eq.return_value = mock_eq
        mock_eq.gte.return_value = mock_gte
        mock_gte.or_.return_value = mock_or

        # Case 1: Database returns a record with action "🟢 MUA"
        mock_or.execute.return_value = MagicMock(
            data=[{"id": 1, "symbol": "TCB", "action": "🟢 MUA", "created_at": "2026-10-01T10:00:00Z"}]
        )
        mock_get_client.return_value = mock_client

        assert check_symbol_recent_signal("TCB", days=5) is True

        # Case 2: Database returns a record with action "🟢 TÍCH LŨY"
        mock_or.execute.return_value = MagicMock(
            data=[{"id": 2, "symbol": "MBB", "action": "🟢 TÍCH LŨY", "created_at": "2026-10-01T10:00:00Z"}]
        )
        assert check_symbol_recent_signal("MBB", days=5) is True

        # Case 3: Database returns no records
        mock_or.execute.return_value = MagicMock(data=[])
        assert check_symbol_recent_signal("HPG", days=5) is False

    # --------------------------------------------------------------------------
    # TASK-0054: save_signal_lifecycle Adapter & Calibration Fields
    # --------------------------------------------------------------------------
    @patch("db_manager.get_supabase_client")
    def test_save_signal_lifecycle_adapter_maps_target_and_stop_price(self, mock_get_client):
        """AC-52.3: Adapter maps initial_target_price -> target_price and ensures all calibration fields."""
        mock_client = MagicMock()
        mock_table = MagicMock()
        mock_insert = MagicMock()

        captured_row = {}

        def mock_insert_fn(row):
            captured_row.update(row)
            return mock_insert

        mock_insert.execute.return_value = MagicMock(data=[{"id": "uuid-99", "symbol": "FPT"}])
        mock_table.insert.side_effect = mock_insert_fn
        mock_client.table.return_value = mock_table
        mock_get_client.return_value = mock_client

        # Caller passes initial_target_price and initial_stop_price without target_price/stop_loss_price
        payload = {
            "symbol": "FPT",
            "entry_price": 130.0,
            "initial_target_price": 155.0,
            "initial_stop_price": 120.0,
            "f_score": 8,
            "mos_pct": 19.5,
        }
        res = save_signal_lifecycle(payload)
        assert res is not None

        # Verify the 5 essential calibration fields are properly populated
        assert captured_row.get("entry_price") == 130.0
        assert captured_row.get("target_price") == 155.0
        assert captured_row.get("initial_target_price") == 155.0
        assert captured_row.get("stop_loss_price") == 120.0
        assert captured_row.get("initial_stop_price") == 120.0
        assert captured_row.get("f_score") == 8
        assert captured_row.get("mos_pct") == 19.5

    # --------------------------------------------------------------------------
    # TASK-0055: Time-Aware Audit Fill & Trading Days Elapsed
    # --------------------------------------------------------------------------
    def test_count_trading_days_skips_weekends_and_same_day(self):
        """AC-52.4: count_trading_days accurately counts business days."""
        # Same day -> 0 days elapsed
        fri = date(2026, 10, 2)
        assert count_trading_days(fri, fri) == 0

        # Friday to Monday -> 1 trading day (skips Sat & Sun)
        mon = date(2026, 10, 5)
        assert count_trading_days(fri, mon) == 1

        # Friday to next Friday -> 5 trading days
        next_fri = date(2026, 10, 9)
        assert count_trading_days(fri, next_fri) == 5

        # With holiday
        holiday = {date(2026, 10, 6)}  # Tuesday is a holiday
        assert count_trading_days(fri, next_fri, holidays=holiday) == 4

    @patch("db_manager.get_supabase_client")
    @patch("data_engine.fetch_stock_technical")
    def test_time_aware_audit_fill_after_1130(self, mock_fetch_tech, mock_get_client):
        """AC-52.4: Signal fired after 11:30 on day T=0 uses closing price, not morning low/high."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        # Mock VNINDEX tech data
        mock_fetch_tech.side_effect = lambda sym: {
            "VNINDEX": {"current_price": 1280.0, "change_pct": 0.5},
            "DGC": {
                "current_price": 100.0,  # Closing price
                "high": 115.0,  # Morning high spike (above target 110.0)
                "low": 90.0,  # Morning low dip (below stop 93.0)
            },
        }.get(sym)

        # Signal fired at 14:15 on T=0
        now_vn = datetime.now(timezone(timedelta(hours=7)))
        signal_created_at = datetime.combine(now_vn.date(), time(14, 15)).replace(
            tzinfo=timezone(timedelta(hours=7))
        ).isoformat()

        fake_open_signals = [
            {
                "id": 101,
                "symbol": "DGC",
                "entry_price": 100.0,
                "target_price": 110.0,
                "stop_loss": 93.0,
                "created_at": signal_created_at,
                "tracking": {"id": 201, "status": "OPEN", "max_favorable_price": 100.0, "max_adverse_price": 100.0},
            }
        ]

        with patch("db_manager.fetch_open_signals", return_value=fake_open_signals):
            mock_table = MagicMock()
            mock_update = MagicMock()
            mock_eq = MagicMock()
            mock_client.table.return_value = mock_table
            mock_table.update.return_value = mock_update
            mock_update.eq.return_value = mock_eq

            res = db_manager.update_daily_tracking()
            assert res["status"] == "SUCCESS"

            # Check what was updated in tracking
            update_call = mock_table.update.call_args[0][0]
            # Since signal fired after 11:30 on T=0, it should NOT trigger morning high (115) or morning low (90)
            # Both high_p and low_p should be treated as curr_p (100.0)
            assert update_call.get("status", "OPEN") == "OPEN"
            assert update_call.get("max_favorable_price") == 100.0
            assert update_call.get("max_adverse_price") == 100.0

    # --------------------------------------------------------------------------
    # TASK-0056: Entry Zone target_buy (support level or 5% discount)
    # --------------------------------------------------------------------------
    def test_build_auto_watchlist_candidate_entry_zone_discount(self):
        """AC-52.5: target_buy is anchored to support_level or current_price * 0.95."""
        manual_symbols = set()

        # Case 1: With explicit support level in tech
        opp_with_support = {
            "symbol": "VHM",
            "current_price": 45.0,
            "target_price": 60.0,  # Fair value target upside
            "support_level": 42.5,  # Real support level
            "conviction_score": 75.0,
            "mos_pct": 25.0,
            "mos_is_informative": True,
            "status": "RECOMMEND_BUY",
            "sector": "🏢 Bất động sản Dân dụng",
        }
        cand1 = _build_auto_watchlist_candidate(opp_with_support, manual_symbols)
        assert cand1 is not None
        assert cand1["target_buy"] == 42.5
        assert cand1["target_buy"] < opp_with_support["current_price"]

        # Case 2: Without support level -> fallback to current_price * 0.95 (5% pullback)
        opp_no_support = {
            "symbol": "FPT",
            "current_price": 130.0,
            "target_price": 160.0,
            "conviction_score": 80.0,
            "mos_pct": 18.0,
            "mos_is_informative": True,
            "status": "RECOMMEND_BUY",
            "sector": "💻 Công nghệ & Tiêu dùng Tăng trưởng",
        }
        cand2 = _build_auto_watchlist_candidate(opp_no_support, manual_symbols)
        assert cand2 is not None
        assert cand2["target_buy"] == round(130.0 * 0.95, 2)  # 123.5
        assert cand2["target_buy"] < opp_no_support["current_price"]

    # --------------------------------------------------------------------------
    # TASK-0057: Manual Watchlist Protection Flag (is_manual_protected)
    # --------------------------------------------------------------------------
    @patch("data_engine.update_google_sheet_watchlist")
    @patch("data_engine._calculate_item_mos", return_value=10.0)
    def test_prune_unsuitable_watchlist_preserves_manual_protected_items(self, mock_mos, mock_sheet, tmp_path):
        """AC-52.6: Items with is_manual_protected=True are skipped by prune, even when overheated/trap."""
        test_file = tmp_path / "watchlist_protected.json"

        # Mock watchlist with 1 protected user stock and 1 unprotected auto stock
        wl_data = [
            {
                "symbol": "MWG",
                "is_manual_protected": True,
                "added_by": "user",
                "is_auto": False,
                "target_buy": 50.0,
                "note": "Cổ phiếu chiến lược dài hạn",
            },
            {
                "symbol": "FOMO",
                "is_manual_protected": False,
                "is_auto": True,
                "target_buy": 30.0,
                "note": "Mã auto bong bóng",
            },
        ]

        # Both stocks have trap/FOMO triggers
        tech_map = {
            "MWG": {"current_price": 55.0, "rsi14": 82.0, "trap_info": {"is_trap": True, "trap_type": "FALLING_KNIFE"}},
            "FOMO": {"current_price": 35.0, "rsi14": 85.0, "trap_info": {"is_trap": True, "trap_type": "BULL_TRAP"}},
        }

        # Run prune with prune_manual=True (standard daily run)
        retained, pruned = prune_unsuitable_watchlist(
            watchlist=wl_data,
            filepath=str(test_file),
            prune_manual=True,
            tech_map=tech_map,
            notify_discord=False,
            force_override=False,
        )

        retained_symbols = [r["symbol"] for r in retained]
        pruned_symbols = [p["symbol"] for p in pruned]

        # MWG must be retained with warning, FOMO must be pruned
        assert "MWG" in retained_symbols, "Protected manual item MWG should NOT be pruned!"
        assert "FOMO" in pruned_symbols, "Unprotected auto item FOMO must be pruned!"

        mwg_item = next(r for r in retained if r["symbol"] == "MWG")
        assert "[⚠️ CẢNH BÁO:" in mwg_item["note"], "Protected item must receive warning note!"

        # Now test with force_override=True -> even protected items can be pruned
        retained2, pruned2 = prune_unsuitable_watchlist(
            watchlist=wl_data,
            filepath=str(test_file),
            prune_manual=True,
            tech_map=tech_map,
            notify_discord=False,
            force_override=True,
        )
        assert "MWG" in [p["symbol"] for p in pruned2], "force_override=True must allow pruning protected items!"
