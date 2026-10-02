"""
Unit tests for Phase 17: Risk Governance Completion (v8.0).

Tests:
- TASK-0058: Canonical RegimeState enum & check_regime_conflict.
- TASK-0059: Layer 7 (Risk Governance & Position Sizing Float) in evaluate_entry_gates.
- TASK-0060: Fix send_trade_signal_alert label and color mapping (Yellow for Watch, Orange for Caution).
- TASK-0061: detect_gdkhq_event with real fetch_corporate_dividends validation.
- TASK-0062: Numeric kill switch reduction of position_size_pct (float).
- TASK-0063: Watchlist Value Buy trigger RSI range [30, 50].
"""

from datetime import date
from unittest.mock import patch

import pandas as pd

from context_engine import check_regime_conflict
from data_engine import detect_gdkhq_event
from discord_alerts import send_trade_signal_alert
from entry_gates import (
    GATE_ADV20_LIQUIDITY,
    evaluate_entry_gates,
)
from regime_classifier import RegimeState, get_canonical_regime
from trading_bot import _evaluate_watchlist_buy_trigger


# --------------------------------------------------------------------------
# TASK-0058: Canonical RegimeState Enum & Conflict Resolver
# --------------------------------------------------------------------------
class TestCanonicalRegimeState:
    """Validate canonical RegimeState enum and single-source-of-truth resolver."""

    def test_regime_state_enum_values(self):
        """AC-58.1: RegimeState defines standard states."""
        assert RegimeState.UPTREND.value == "UPTREND"
        assert RegimeState.SIDEWAYS.value == "SIDEWAYS"
        assert RegimeState.DOWNTREND.value == "DOWNTREND"
        assert RegimeState.UNKNOWN.value == "UNKNOWN"

    def test_get_canonical_regime_from_tech_data(self):
        """AC-58.1: get_canonical_regime resolves MA200 hysteresis into RegimeState enum."""
        # Price > MA200 by 2% -> UPTREND
        vnindex_up = {"current_price": 1280.0, "ma200": 1250.0}
        assert get_canonical_regime(vn_index_data=vnindex_up) == RegimeState.UPTREND

        # Price < MA200 by 2% -> DOWNTREND
        vnindex_down = {"current_price": 1200.0, "ma200": 1250.0}
        assert get_canonical_regime(vn_index_data=vnindex_down) == RegimeState.DOWNTREND

        # Price within +/- 1.5% of MA200 -> SIDEWAYS
        vnindex_side = {"current_price": 1252.0, "ma200": 1250.0}
        assert get_canonical_regime(vn_index_data=vnindex_side) == RegimeState.SIDEWAYS

        # Empty/missing data -> UNKNOWN
        assert get_canonical_regime(vn_index_data=None) == RegimeState.UNKNOWN

    def test_check_regime_conflict_with_regime_state(self):
        """AC-58.1: check_regime_conflict accepts RegimeState enum or standard strings."""
        conflict, msg = check_regime_conflict(code_regime=RegimeState.UPTREND, analyst_regime=RegimeState.DOWNTREND)
        assert conflict is True
        assert "XUNG ĐỘT REGIME" in msg

        no_conflict, msg2 = check_regime_conflict(code_regime=RegimeState.UPTREND, analyst_regime=RegimeState.UPTREND)
        assert no_conflict is False
        assert "ĐỒNG THUẬN REGIME" in msg2


# --------------------------------------------------------------------------
# TASK-0059: Layer 7 Risk Governance & Position Sizing Float
# --------------------------------------------------------------------------
class TestLayer7RiskGovernance:
    """Validate Layer 7 integration into evaluate_entry_gates and numeric position sizing."""

    def test_adv20_liquidity_gate_blocks_under_2_billion(self):
        """AC-58.2: evaluate_entry_gates blocks when ADV20 < 2.0 billion VND."""
        fin = {
            "period": "2026-Q2",
            "pe": 10.0,
            "pb": 1.2,
            "roe": 18.0,
            "f_score": 8,
            "z_score": 3.0,
            "mos_pct": 25.0,
            "mos_is_informative": True,
        }
        tech = {"current_price": 50.0, "ma20": 48.0, "ma50": 46.0, "rsi14": 55.0, "adv20_billion": 1.2}

        res = evaluate_entry_gates(
            symbol="PENNY",
            current_price=50.0,
            fin_dict=fin,
            tech_data=tech,
            sector="Công nghệ",
            macro_regime="UPTREND",
            adv20_billion=1.2,
        )

        assert res.can_buy is False
        assert res.blocked_by == GATE_ADV20_LIQUIDITY
        assert res.position_size_pct == 0.0
        assert any("ADV20" in r for r in res.blocking_reasons)

    def test_layer7_calculates_float_position_size(self):
        """AC-58.2: evaluate_entry_gates produces a calculated float position_size_pct."""
        fin = {
            "period": "2026-Q2",
            "pe": 10.0,
            "pb": 1.2,
            "roe": 18.0,
            "f_score": 8,
            "z_score": 3.0,
            "mos_pct": 25.0,
            "mos_is_informative": True,
        }
        tech = {
            "current_price": 50.0,
            "ma20": 48.0,
            "ma50": 46.0,
            "rsi14": 55.0,
            "adv20_billion": 15.0,  # 15 billion VND ADV20
        }

        res = evaluate_entry_gates(
            symbol="HPG",
            current_price=50.0,
            fin_dict=fin,
            tech_data=tech,
            sector="Thép",
            macro_regime="UPTREND",
            adv20_billion=15.0,
            half_kelly_f=0.12,
        )

        assert res.can_buy is True
        assert isinstance(res.position_size_pct, float)
        assert 0.05 <= res.position_size_pct <= 0.15
        assert res.metrics.get("position_size_nav") is not None


# --------------------------------------------------------------------------
# TASK-0060: Alert Label & Color Mapping
# --------------------------------------------------------------------------
class TestAlertLabelAndColorMapping:
    """Validate that send_trade_signal_alert does not label WATCH / CAUTION as SELL."""

    @patch("discord_alerts.DISCORD_BOT_TOKEN", None)
    @patch("discord_alerts.send_discord_webhook", return_value=True)
    def test_watch_action_displays_yellow_not_sell(self, mock_webhook):
        """AC-58.3: Action 'THEO DÕI' or 'WATCH' displays yellow (0xF1C40F) and icon 🟡."""
        send_trade_signal_alert(
            symbol="FPT",
            action="THEO DÕI",
            current_price=135.0,
            trigger_reason="Chờ điểm cân bằng",
        )
        assert mock_webhook.called
        kwargs = mock_webhook.call_args[1] if mock_webhook.call_args[1] else mock_webhook.call_args[0][0]
        embeds = kwargs.get("embeds") if isinstance(kwargs, dict) else mock_webhook.call_args[1].get("embeds")
        if not embeds and mock_webhook.call_args.kwargs.get("embeds"):
            embeds = mock_webhook.call_args.kwargs.get("embeds")
        embed = embeds[0]

        assert embed["color"] == 0xF1C40F  # Yellow
        assert "🟡" in embed["title"]
        assert "THEO DÕI" in embed["title"]
        assert "BÁN" not in embed["title"]

    @patch("discord_alerts.DISCORD_BOT_TOKEN", None)
    @patch("discord_alerts.send_discord_webhook", return_value=True)
    def test_caution_action_displays_orange(self, mock_webhook):
        """AC-58.3: Action 'CẢNH BÁO' displays orange (0xE67E22) and icon ⚠️."""
        send_trade_signal_alert(
            symbol="VHM",
            action="CẢNH BÁO",
            current_price=42.0,
            trigger_reason="Phát hiện rủi ro phân phối",
        )
        assert mock_webhook.called
        embeds = mock_webhook.call_args.kwargs.get("embeds") or mock_webhook.call_args[0][0].get("embeds")
        embed = embeds[0]

        assert embed["color"] == 0xE67E22  # Orange
        assert "⚠️" in embed["title"]
        assert "CẢNH BÁO" in embed["title"]
        assert "BÁN / HẠ TỶ TRỌNG" not in embed["title"]


# --------------------------------------------------------------------------
# TASK-0061: Corporate Actions Shield with Real Dividends
# --------------------------------------------------------------------------
class TestCorporateActionsShield:
    """Validate detect_gdkhq_event cross-checks with real fetch_corporate_dividends."""

    @patch("data_engine.fetch_corporate_dividends")
    def test_detect_gdkhq_confirmed_when_ex_date_matches(self, mock_div):
        """AC-58.4: Gap-down <= -4.5% with dividend ex_date on today -> GDKHQ_CONFIRMED."""
        today_str = date.today().isoformat()
        # Mock corporate events DataFrame
        mock_div.return_value = pd.DataFrame([
            {"ex_date": today_str, "event_type": "Cổ tức tiền mặt", "value": 1500}
        ])

        tech = {"current_price": 95.0, "ref_price": 100.0, "open": 95.0}  # Gap down -5%
        res = detect_gdkhq_event(symbol="VNM", tech_dict=tech, vnindex_chg_pct=-0.5, event_date=today_str)

        assert res["is_gdkhq"] is True
        assert res["event_type"] == "GDKHQ_CONFIRMED"

    @patch("data_engine.fetch_corporate_dividends")
    def test_detect_gdkhq_gap_down_news_when_no_dividend_event(self, mock_div):
        """AC-58.4: Gap-down <= -4.5% with NO dividend event -> GAP_DOWN_NEWS (must check stop loss)."""
        today_str = date.today().isoformat()
        # Mock no dividend events or different date
        mock_div.return_value = pd.DataFrame([
            {"ex_date": "2026-05-15", "event_type": "Cổ tức tiền mặt", "value": 1000}
        ])

        tech = {"current_price": 95.0, "ref_price": 100.0, "open": 95.0}  # Gap down -5%
        res = detect_gdkhq_event(symbol="VNM", tech_dict=tech, vnindex_chg_pct=-0.5, event_date=today_str)

        assert res["is_gdkhq"] is False
        assert res["event_type"] == "GAP_DOWN_NEWS"


# --------------------------------------------------------------------------
# TASK-0062: Numeric Kill Switch Reduction
# --------------------------------------------------------------------------
class TestNumericKillSwitch:
    """Validate kill switch cuts position_size_pct by 50% as a numeric float."""

    def test_kill_switch_reduces_position_size_by_half(self):
        """AC-58.5: When kill_switch_active=True, position_size_pct is reduced by 50%."""
        fin = {
            "period": "2026-Q2",
            "pe": 10.0,
            "pb": 1.2,
            "roe": 18.0,
            "f_score": 8,
            "z_score": 3.0,
            "mos_pct": 25.0,
            "mos_is_informative": True,
        }
        tech = {"current_price": 50.0, "ma20": 48.0, "ma50": 46.0, "rsi14": 55.0, "adv20_billion": 15.0}

        base_res = evaluate_entry_gates(
            symbol="HPG",
            current_price=50.0,
            fin_dict=fin,
            tech_data=tech,
            sector="Thép",
            macro_regime="UPTREND",
            adv20_billion=15.0,
            half_kelly_f=0.12,
            kill_switch_active=False,
        )

        kill_res = evaluate_entry_gates(
            symbol="HPG",
            current_price=50.0,
            fin_dict=fin,
            tech_data=tech,
            sector="Thép",
            macro_regime="UPTREND",
            adv20_billion=15.0,
            half_kelly_f=0.12,
            kill_switch_active=True,
        )

        assert base_res.can_buy is True
        assert kill_res.can_buy is True
        # Numeric reduction >= 30% (50% reduction)
        assert kill_res.position_size_pct == round(base_res.position_size_pct * 0.5, 4)


# --------------------------------------------------------------------------
# TASK-0063: Watchlist Value Buy Trigger RSI Range
# --------------------------------------------------------------------------
class TestWatchlistValueBuyTrigger:
    """Validate disciplined Value Buy trigger: RSI in [30, 50], not falling knife."""

    def test_watchlist_trigger_rsi_in_range_30_50(self):
        """AC-58.6: RSI in [30, 50] triggers Value Buy when macro and MoS are healthy."""
        tech_valid = {
            "current_price": 40.0,
            "status_ma20": "TRÊN",
            "vol_ratio": 1.1,
            "rsi14": 42.0,  # Within [30, 50]
        }
        triggered, reason = _evaluate_watchlist_buy_trigger(
            target_buy=0.0,
            curr_p=40.0,
            tech=tech_valid,
            strategy_type="VALUE_BUY",
        )
        assert triggered is True
        assert "VALUE BUY" in reason or "RSI" in reason

    def test_watchlist_trigger_rejects_falling_knife_rsi_under_30(self):
        """AC-58.6: RSI < 30 without support does NOT trigger Value Buy (knife protection)."""
        tech_knife = {
            "current_price": 40.0,
            "status_ma20": "DƯỚI",
            "vol_ratio": 0.8,
            "rsi14": 24.0,  # Extremely low, falling knife
        }
        triggered, _ = _evaluate_watchlist_buy_trigger(
            target_buy=0.0,
            curr_p=40.0,
            tech=tech_knife,
            strategy_type="VALUE_BUY",
        )
        assert triggered is False
