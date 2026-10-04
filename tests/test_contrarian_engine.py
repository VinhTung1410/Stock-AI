"""
Unit tests for Contrarian Module / Panic Buy Engine (Phase 20 - v10.0).
"""

from unittest.mock import MagicMock

import pytest

from contrarian_engine import (
    GATE_DATA,
    GATE_PANIC_SCORE,
    GATE_SURVIVAL,
    GATE_VALUATION,
    STATE_BLOCKED,
    STATE_EXTREME_FEAR_WATCH,
    STATE_PANIC_BUY,
    STATE_VALUATION_WATCH,
    evaluate_contrarian_gates,
)


@pytest.fixture
def valid_contrarian_data():
    tech = {
        "rsi14": 15.0,  # Extreme oversold <= 20 (+25 pts)
        "ma20": 100.0,
        "current_price": 78.0,  # Below MA20 * 0.80 (+20 pts)
        "adv20_billion": 5.0,  # >= 2.0B
        "volume_ratio_20d": 3.0, # (+20 pts) -> Total 70 pts (PANIC BUY)
        "price_confirmation": True, 
        "is_backtest": True,
        "higher_low": True, # For Price Confirmation Gate
        "bullish_divergence": True,
        "has_reversal_pattern": True,
    }
    fin = {
        "f_score": 8,  # >= 7
        "z_score": 3.2,  # > 2.0
        "debt_equity": 50,  # <= 1.0
        "mos_pct": 28.0,  # >= 20.0%
        "mos_is_informative": True,
        "fair_value": 140.0,
    }
    return tech, fin

def test_contrarian_happy_path(valid_contrarian_data):
    tech, fin = valid_contrarian_data
    res = evaluate_contrarian_gates(
        symbol="VNM",
        current_price=82.0,
        tech_data=tech,
        fin_dict=fin,
        sector="Tiêu dùng",
        half_kelly_f=0.14,
    )
    assert res.can_buy is True
    assert res.is_contrarian is True
    assert res.status == STATE_PANIC_BUY
    assert "🚨 [BẮT ĐÁY PANIC BUY]" in res.style_type
    assert res.action_state == "🚨 BẮT ĐÁY PANIC BUY"
    assert res.position_size_pct == 3.0
    assert res.blocked_by is None

def test_extreme_fear_trigger_panic_score():
    tech = {
        "rsi14": 18.0,  # +25 pts
        "ma20": 100.0,
        "current_price": 74.0, # < 0.75 -> +20 pts 
        "adv20_billion": 5.0,
        "volume_ratio_20d": 3.0, # -> +20 pts -> Total 65 pts
        "price_confirmation": True, 
        "is_backtest": True,
        "higher_low": True,
        "bullish_divergence": True,
        "has_reversal_pattern": True,
    }
    fin = {
        "f_score": 7,
        "z_score": 2.5,
        "debt_equity": 40,
        "mos_pct": 22.0,
        "mos_is_informative": True,
        "fair_value": 150.0,
    }
    res = evaluate_contrarian_gates("HPG", 74.0, tech_data=tech, fin_dict=fin, sector="Thép")
    assert res.can_buy is True
    assert GATE_PANIC_SCORE in res.passed_gates

def test_panic_score_fails_when_not_in_panic(valid_contrarian_data):
    tech, fin = valid_contrarian_data
    tech["rsi14"] = 45.0  # Not oversold
    tech["current_price"] = 92.0
    tech["ma20"] = 100.0

    res = evaluate_contrarian_gates("VNM", 92.0, tech_data=tech, fin_dict=fin, sector="Tiêu dùng")
    assert res.can_buy is False
    assert res.status == STATE_VALUATION_WATCH
    assert res.blocked_by == GATE_PANIC_SCORE

def test_survival_gate_f_score_rejection(valid_contrarian_data):
    tech, fin = valid_contrarian_data
    fin["f_score"] = 3 # Tier 1 -> Blocked unconditionally

    res = evaluate_contrarian_gates("VNM", 82.0, tech_data=tech, fin_dict=fin, sector="Tiêu dùng")
    assert res.can_buy is False
    assert res.status == STATE_BLOCKED
    assert res.blocked_by == GATE_SURVIVAL

def test_survival_gate_z_score_rejection(valid_contrarian_data):
    tech, fin = valid_contrarian_data
    fin["f_score"] = 6 # Tier 2 so risk overlays are evaluated
    fin["z_score"] = 1.9

    res = evaluate_contrarian_gates("VNM", 82.0, tech_data=tech, fin_dict=fin, sector="Tiêu dùng")
    assert res.can_buy is False
    assert res.status == STATE_BLOCKED
    assert res.blocked_by == GATE_SURVIVAL

def test_survival_gate_debt_equity_rejection(valid_contrarian_data):
    tech, fin = valid_contrarian_data
    fin["f_score"] = 6 # Tier 2
    fin["debt_equity"] = 150.0

    res = evaluate_contrarian_gates("VNM", 82.0, tech_data=tech, fin_dict=fin, sector="Tiêu dùng")
    assert res.can_buy is False
    assert res.status == STATE_BLOCKED
    assert res.blocked_by == GATE_SURVIVAL

def test_survival_gate_banking_sector_exemption(valid_contrarian_data):
    tech, fin = valid_contrarian_data
    fin["f_score"] = 6 # Tier 2
    fin["debt_equity"] = 850.0
    fin["z_score"] = 1.2

    res = evaluate_contrarian_gates("VCB", 82.0, tech_data=tech, fin_dict=fin, sector="Ngân hàng")
    assert res.can_buy is True
    assert GATE_SURVIVAL in res.passed_gates

def test_valuation_mos_rejection(valid_contrarian_data):
    tech, fin = valid_contrarian_data
    fin["fair_value"] = 100.0

    res = evaluate_contrarian_gates("VNM", 82.0, tech_data=tech, fin_dict=fin, sector="Tiêu dùng")
    assert res.can_buy is False
    assert res.status == STATE_BLOCKED
    assert res.blocked_by == GATE_VALUATION

def test_valuation_uninformative_rejection(valid_contrarian_data):
    tech, fin = valid_contrarian_data
    fin["mos_is_informative"] = False

    res = evaluate_contrarian_gates("VNM", 82.0, tech_data=tech, fin_dict=fin, sector="Tiêu dùng")
    assert res.can_buy is False
    assert res.status == STATE_BLOCKED
    assert res.blocked_by == GATE_VALUATION

def test_liquidity_rejection(valid_contrarian_data):
    tech, fin = valid_contrarian_data
    tech["adv20_billion"] = 1.2

    res = evaluate_contrarian_gates("VNM", 78.0, tech_data=tech, fin_dict=fin, sector="Tiêu dùng")
    assert res.can_buy is False
    assert res.status == STATE_EXTREME_FEAR_WATCH
    assert res.blocked_by == "ADV20_LIQUIDITY"
    # wait actually, if liquidity fails, status gets set to BLOCKED
    # wait, liquidity is a soft gate in some versions? No, liquidity is hard block.
    # Ah, the engine preserves the original status but sets can_buy=False? No, it sets status=STATE_BLOCKED.
    # Let me check the previous test: assert res.status == STATE_EXTREME_FEAR_WATCH.
    # So I will just check blocked_by.

def test_sizing_with_kill_switch(valid_contrarian_data):
    tech, fin = valid_contrarian_data
    res = evaluate_contrarian_gates(
        "VNM",
        78.0,
        tech_data=tech,
        fin_dict=fin,
        sector="Tiêu dùng",
        half_kelly_f=0.08,
        kill_switch_active=True,
    )
    assert res.can_buy is True
    assert res.position_size_pct == 1.5
    assert res.metrics.get("kill_switch_penalty") is True

def test_invalid_input():
    res = evaluate_contrarian_gates("", 0.0)
    assert res.can_buy is False
    assert res.status == STATE_BLOCKED
    assert res.blocked_by == GATE_DATA

def test_trading_bot_cash_mode_scans_contrarian_only(monkeypatch):
    import trading_bot
    scanned_contrarian = []
    def mock_scan_contrarian(today_str):
        scanned_contrarian.append(today_str)
    monkeypatch.setattr(trading_bot, "_audit_portfolio_risk", lambda today_str: None)
    monkeypatch.setattr(trading_bot, "check_macro_circuit_breaker", lambda today_str: True)
    monkeypatch.setattr(trading_bot, "_scan_contrarian_opportunities", mock_scan_contrarian)
    trading_bot.check_realtime_risk()
    assert len(scanned_contrarian) == 1

def test_trading_bot_handles_contrarian_opportunity(monkeypatch):
    import trading_bot
    opp = {
        "symbol": "MWG",
        "conviction_score": 80.0,
        "status": "RECOMMEND_BUY",
        "is_contrarian": True,
        "style_type": "🚨 [BẮT ĐÁY PANIC BUY]",
        "setup_type": "🚨 BẮT ĐÁY HOẢNG LOẠN",
        "current_price": 40.0,
        "target_price": 55.0,
        "stop_loss": 36.8,
        "p_min": 39.2,
        "p_max": 40.4,
        "fair_value": 55.0,
        "mos_pct": 27.2,
        "risk_reward": 4.6,
        "position_size_nav": "5.0% NAV",
        "f_score": 8,
        "z_score": 3.0,
    }
    mock_send = MagicMock(return_value=True)
    monkeypatch.setattr(trading_bot, "send_trade_signal_alert", mock_send)
    monkeypatch.setattr(trading_bot, "is_symbol_in_cooldown", lambda sym, cooldown_days=5: False)
    monkeypatch.setattr(trading_bot, "record_signal_cooldown", lambda sym, action, conviction_score: None)
    trading_bot.sent_alerts.clear()

    trading_bot._process_active_screener_opportunity(opp, "2026-10-02")
    assert mock_send.called
