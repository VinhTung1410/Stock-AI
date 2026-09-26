# -*- coding: utf-8 -*-
"""Unit tests for TASK-0008: Phase 2 Risk Fixes, Dynamic Slippage, and Gemini Rate Limiter."""

from unittest.mock import patch

from ai_analyst import _GEMINI_RATE_TRACKER, check_and_track_gemini_call
from backtest_engine import calculate_dynamic_slippage_bps
from quant_engine import MAX_POSITIONS_PER_SECTOR, check_sector_concentration


class TestPhase2aSectorConcentrationGate:
    """Test suite for Phase 2a: Sector Concentration Gate."""

    def test_check_sector_concentration_empty_inputs(self):
        """Empty symbol returns False; empty portfolio returns True."""
        allowed, reason = check_sector_concentration("", [])
        assert allowed is False
        assert "INVALID_SYMBOL" in reason

        allowed, reason = check_sector_concentration("FPT", [])
        assert allowed is True
        assert "SECTOR_CONCENTRATION_OK" in reason

    def test_check_sector_concentration_within_limit(self):
        """Allow when sector has fewer than MAX_POSITIONS_PER_SECTOR (3) positions."""
        portfolio = [
            {"symbol": "SSI"},
            {"symbol": "VND"},
            {"symbol": "HPG"},
        ]
        # SSI, VND are "Chứng khoán" (2). Adding VCI (3rd) is allowed.
        allowed, reason = check_sector_concentration("VCI", portfolio)
        assert allowed is True
        assert "SECTOR_CONCENTRATION_OK" in reason

    def test_check_sector_concentration_blocks_when_full(self):
        """Block when sector already has MAX_POSITIONS_PER_SECTOR (3) positions."""
        portfolio = [
            {"symbol": "SSI"},
            {"symbol": "VND"},
            {"symbol": "VCI"},
            {"symbol": "HPG"},
        ]
        custom_map = {
            "SSI": "Chứng khoán",
            "VND": "Chứng khoán",
            "VCI": "Chứng khoán",
            "HCM": "Chứng khoán",
            "HPG": "Thép",
        }
        # 3 positions in Chứng khoán. Adding HCM (4th) must be blocked.
        allowed, reason = check_sector_concentration("HCM", portfolio, sector_map=custom_map)
        assert allowed is False
        assert "Sector Gate Blocked" in reason
        assert "Chứng khoán" in reason
        assert f"3/{MAX_POSITIONS_PER_SECTOR}" in reason

    def test_check_sector_concentration_accepts_ma_cp_key(self):
        """Ensure check_sector_concentration supports Vietnamese column 'Mã CP'."""
        portfolio = [
            {"Mã CP": "SSI"},
            {"Mã CP": "VND"},
            {"Mã CP": "VCI"},
        ]
        custom_map = {
            "SSI": "Chứng khoán",
            "VND": "Chứng khoán",
            "VCI": "Chứng khoán",
            "HCM": "Chứng khoán",
        }
        allowed, reason = check_sector_concentration("HCM", portfolio, sector_map=custom_map)
        assert allowed is False


class TestPhase2bDynamicSlippage:
    """Test suite for Phase 2b: Dynamic Slippage Model."""

    def test_dynamic_slippage_base_normal(self):
        """Normal conditions yield base 15.0 bps."""
        bps = calculate_dynamic_slippage_bps(is_buy=True, vol_ratio=1.0)
        assert bps == 15.0

    def test_dynamic_slippage_ceiling_buy(self):
        """Buying at HOSE ceiling multiplies base bps by 4.0 (60 bps)."""
        bps = calculate_dynamic_slippage_bps(is_buy=True, is_ceiling=True)
        assert bps == 60.0

    def test_dynamic_slippage_floor_sell(self):
        """Panic selling at HOSE floor multiplies base bps by 5.0 (75 bps)."""
        bps = calculate_dynamic_slippage_bps(is_buy=False, is_floor=True)
        assert bps == 75.0

    def test_dynamic_slippage_liquidity_conditions(self):
        """Volume depletion doubles slippage; high volume increases by 1.5x."""
        low_vol_bps = calculate_dynamic_slippage_bps(is_buy=True, vol_ratio=0.3)
        assert low_vol_bps == 30.0

        high_vol_bps = calculate_dynamic_slippage_bps(is_buy=True, vol_ratio=3.5)
        assert high_vol_bps == 22.5

    def test_dynamic_slippage_large_order_and_max_cap(self):
        """Large order relative to ADV20 scales slippage and is strictly capped at 200 bps."""
        # 1.0 bil order on 5.0 bil ADV20 (20% ADV20 > 5%)
        bps = calculate_dynamic_slippage_bps(
            is_buy=True,
            is_ceiling=True,  # 60 bps base
            adv20_billion=5.0,
            order_size_billion=1.0,  # 20% ADV
        )
        assert bps > 60.0
        assert bps <= 200.0

        # Extreme conditions capped at 200 bps
        extreme_bps = calculate_dynamic_slippage_bps(
            is_buy=False,
            is_floor=True,
            vol_ratio=0.1,
            adv20_billion=1.0,
            order_size_billion=5.0,
        )
        assert extreme_bps == 200.0


class TestPhase2cGeminiRateLimitCircuitBreaker:
    """Test suite for Phase 2c: Gemini Rate Limit Sliding Window."""

    def test_gemini_rate_tracker_within_buffer(self):
        """Calls within 12 RPM buffer return True."""
        _GEMINI_RATE_TRACKER["calls"] = []
        _GEMINI_RATE_TRACKER["limit_hit"] = False

        for _ in range(11):
            assert check_and_track_gemini_call() is True

    @patch("discord_alerts.send_gemini_rate_limit_alert")
    def test_gemini_rate_tracker_hits_limit(self, mock_alert):
        """When reaching 12 calls in 60s, return False and dispatch Discord alert."""
        _GEMINI_RATE_TRACKER["calls"] = [100.0] * 12
        _GEMINI_RATE_TRACKER["limit_hit"] = False

        with patch("time.time", return_value=120.0):
            res = check_and_track_gemini_call(pending_symbols=["FPT", "MWG"])
            assert res is False
            assert _GEMINI_RATE_TRACKER["limit_hit"] is True
            mock_alert.assert_called_once()
            call_kwargs = mock_alert.call_args[1]
            assert call_kwargs["current_rpm"] == 12
            assert "FPT" in call_kwargs["dropped_symbols"]
