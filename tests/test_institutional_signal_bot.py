"""Unit tests for Institutional Signal Bot enhancements.

Validates:
1. Institutional Trade Signal Card with full execution, quant, and thesis fields.
2. Partial Profit Lock alert triggering (Phase 5d).
3. Macro Circuit Breaker alert and Cash Mode blocking buy signals.
4. Active Market Screener integration into trading_bot daemon.
5. Strict zero network test leakage (all Discord and HTTP calls mocked).
"""

from __future__ import annotations

import pandas as pd
import pytest

import trading_bot
from discord_alerts import (
    send_partial_take_profit_alert,
    send_regime_circuit_breaker_alert,
    send_trade_signal_alert,
)


@pytest.fixture(autouse=True)
def reset_bot_state():
    """Reset shared trading bot sets and state between tests."""
    trading_bot.sent_alerts.clear()
    trading_bot.sent_scheduled_reports.clear()
    trading_bot.last_market_scan_time = 0.0
    yield
    trading_bot.sent_alerts.clear()
    trading_bot.sent_scheduled_reports.clear()


def test_send_trade_signal_alert_institutional_fields(monkeypatch):
    """Verify send_trade_signal_alert constructs rich institutional fields."""
    captured_embeds = []

    def mock_dm(embeds=None, **_):
        if embeds:
            captured_embeds.extend(embeds)
        return True

    monkeypatch.setattr("discord_alerts.DISCORD_BOT_TOKEN", "mock_token")
    monkeypatch.setattr("discord_alerts.DISCORD_USER_ID", "mock_user")
    monkeypatch.setattr("discord_alerts.send_discord_dm", mock_dm)

    success = send_trade_signal_alert(
        symbol="FPT",
        action="MUA",
        current_price=135.0,
        trigger_reason="Breakout nền tích lũy 3 tuần",
        target_price=150.0,
        stop_loss=127.0,
        entry_range=(134.0, 136.0),
        target_price_t2=165.0,
        risk_reward=2.5,
        position_size_nav="12% NAV",
        conviction_score=85.0,
        quant_metrics={
            "f_score": 8,
            "mos_pct": 22.5,
            "z_score": 3.4,
            "tech_status": "TRÊN MA20",
            "rsi": 58.2,
        },
        catalysts=["Tăng trưởng mảng AI/Cloud +45%", "Ký hợp đồng lớn tại Nhật Bản"],
        thesis_breaker="Gãy ngưỡng hỗ trợ 127.0k hoặc LNST tăng trưởng dưới 15%",
        strategy_style="⚡ LƯỚT SÓNG T+ / BREAKOUT",
    )

    assert success is True
    assert len(captured_embeds) == 1
    embed = captured_embeds[0]

    assert "FPT" in embed["title"]
    assert "MUA" in embed["title"]
    assert "BREAKOUT" in embed["title"]
    assert "KHÔNG phải tư vấn đầu tư" in embed["description"]

    field_names_lower = [f["name"].lower() for f in embed["fields"]]
    assert any("vùng gom mua" in name for name in field_names_lower)
    assert any("mục tiêu t1" in name or "target" in name for name in field_names_lower)
    assert any("mục tiêu t2" in name or "fair value" in name for name in field_names_lower)
    assert any("stop loss" in name for name in field_names_lower)
    assert any("tỷ lệ r:r" in name for name in field_names_lower)
    assert any("half-kelly" in name for name in field_names_lower)
    assert any("conviction" in name for name in field_names_lower)
    assert any("bảo chứng định lượng" in name for name in field_names_lower)
    assert any("luận điểm xúc tác" in name for name in field_names_lower)
    assert any("thesis breaker" in name for name in field_names_lower)


def test_send_partial_take_profit_alert(monkeypatch):
    """Verify send_partial_take_profit_alert formats lock fraction and breakeven stop."""
    captured_embeds = []

    def mock_dm(embeds=None, **_):
        if embeds:
            captured_embeds.extend(embeds)
        return True

    monkeypatch.setattr("discord_alerts.DISCORD_BOT_TOKEN", "mock_token")
    monkeypatch.setattr("discord_alerts.DISCORD_USER_ID", "mock_user")
    monkeypatch.setattr("discord_alerts.send_discord_dm", mock_dm)

    success = send_partial_take_profit_alert(
        symbol="MWG",
        current_price=68.5,
        entry_price=60.0,
        gain_pct=14.17,
        new_stop_price=60.0,
        lock_fraction=0.5,
    )

    assert success is True
    assert len(captured_embeds) == 1
    embed = captured_embeds[0]

    assert "TARGET 1" in embed["title"]
    assert "MWG" in embed["title"]
    assert "+14.2%" in embed["title"]
    assert "50%" in embed["description"]
    assert "Risk-Free" in embed["description"]


def test_send_regime_circuit_breaker_alert(monkeypatch):
    """Verify send_regime_circuit_breaker_alert handles DOWNTREND and recovery."""
    captured_embeds = []

    def mock_dm(embeds=None, **_):
        if embeds:
            captured_embeds.extend(embeds)
        return True

    monkeypatch.setattr("discord_alerts.DISCORD_BOT_TOKEN", "mock_token")
    monkeypatch.setattr("discord_alerts.DISCORD_USER_ID", "mock_user")
    monkeypatch.setattr("discord_alerts.send_discord_dm", mock_dm)

    # 1. DOWNTREND -> Cash Mode
    send_regime_circuit_breaker_alert(
        regime="DOWNTREND",
        reason="VN-Index thủng MA200 kèm độ dốc âm",
        vnindex_price=1210.5,
    )
    assert len(captured_embeds) == 1
    assert "DOWNTREND" in captured_embeds[0]["title"]
    assert "CASH MODE" in captured_embeds[0]["description"]

    # 2. Recovery -> Healthy
    send_regime_circuit_breaker_alert(
        regime="UPTREND",
        reason="VN-Index vượt lại MA200",
        vnindex_price=1295.0,
    )
    assert len(captured_embeds) == 2
    assert "UPTREND" in captured_embeds[1]["title"]


def test_trading_bot_macro_circuit_breaker_blocks_buys(monkeypatch):
    """Verify Macro Circuit Breaker halts all new buy scans when in Downtrend."""
    # Mock VN-Index series in downtrend
    df_downtrend = pd.DataFrame({
        "close": [1300.0 - i * 5 for i in range(220)],
    })

    monkeypatch.setattr("data_engine.fetch_stock_historical", lambda *a, **k: df_downtrend)
    monkeypatch.setattr("regime_classifier.classify_market_regime", lambda df: pd.Series(["DOWNTREND"] * len(df)))

    circuit_alert_sent = False

    def mock_circuit_alert(regime, reason, vnindex_price=None):
        nonlocal circuit_alert_sent
        circuit_alert_sent = True
        return True

    monkeypatch.setattr("trading_bot.send_regime_circuit_breaker_alert", mock_circuit_alert)

    watchlist_scanned = False
    active_screener_scanned = False

    def mock_scan_watchlist(today_str):
        nonlocal watchlist_scanned
        watchlist_scanned = True

    def mock_scan_active(today_str):
        nonlocal active_screener_scanned
        active_screener_scanned = True

    monkeypatch.setattr("trading_bot._scan_watchlist_opportunities", mock_scan_watchlist)
    monkeypatch.setattr("trading_bot._scan_active_market_opportunities", mock_scan_active)
    monkeypatch.setattr("trading_bot._audit_portfolio_risk", lambda today_str: None)

    # Execute check_realtime_risk
    trading_bot.check_realtime_risk()

    assert circuit_alert_sent is True
    assert watchlist_scanned is False
    assert active_screener_scanned is False


def test_trading_bot_partial_profit_lock_triggers(monkeypatch):
    """Verify holding in portfolio with >= 12% profit triggers partial profit lock alert."""
    profit_lock_alert_triggered = False

    def mock_take_profit_alert(symbol, current_price, entry_price, gain_pct, new_stop_price, lock_fraction=0.5):
        nonlocal profit_lock_alert_triggered
        profit_lock_alert_triggered = True
        return True

    monkeypatch.setattr("trading_bot.send_partial_take_profit_alert", mock_take_profit_alert)

    # Calling _handle_partial_profit_lock with +15% gain
    triggered = trading_bot._handle_partial_profit_lock(
        symbol="TCB",
        curr_price=23.0,
        cost_price=20.0,
        high_price=23.5,
        today_str="2026-09-28",
    )

    assert triggered is True
    assert profit_lock_alert_triggered is True

    # Repeated call on same day should be suppressed by sent_alerts cooldown
    second_run = trading_bot._handle_partial_profit_lock(
        symbol="TCB",
        curr_price=23.0,
        cost_price=20.0,
        high_price=23.5,
        today_str="2026-09-28",
    )
    assert second_run is False


def test_trading_bot_active_screener_dispatches_signal(monkeypatch):
    """Verify Active Market Screener dispatches High Conviction opportunities."""
    mock_opp = {
        "symbol": "MBB",
        "status": "HIGH_CONVICTION",
        "conviction_score": 82.0,
        "current_price": 25.0,
        "target_price": 28.5,
        "stop_loss": 23.6,
        "fair_value": 31.0,
        "mos_pct": 24.0,
        "risk_reward": 2.5,
        "position_size_nav": "15% NAV",
        "style_type": "⚡ LƯỚT SÓNG T+ / BREAKOUT",
        "setup_type": "Breakout nền phẳng kèm Vol x2.1",
        "story": "Tăng trưởng tín dụng Q3 vượt 18%",
        "f_score": 8,
        "z_score": 2.9,
    }

    dispatched_signal = None

    def mock_send_signal(symbol, action, current_price, trigger_reason, **kwargs):
        nonlocal dispatched_signal
        dispatched_signal = {
            "symbol": symbol,
            "action": action,
            "current_price": current_price,
            "trigger_reason": trigger_reason,
            "kwargs": kwargs,
        }
        return True

    monkeypatch.setattr("trading_bot.send_trade_signal_alert", mock_send_signal)
    monkeypatch.setattr("trading_bot.record_signal_cooldown", lambda *a, **k: None)
    monkeypatch.setattr("trading_bot.is_symbol_in_cooldown", lambda *a, **k: False)

    trading_bot._process_active_screener_opportunity(mock_opp, today_str="2026-09-28")

    assert dispatched_signal is not None
    assert dispatched_signal["symbol"] == "MBB"
    assert dispatched_signal["action"] == "MUA"
    assert dispatched_signal["kwargs"]["conviction_score"] == 82.0
    assert dispatched_signal["kwargs"]["risk_reward"] == 2.5
    assert dispatched_signal["kwargs"]["position_size_nav"] == "15% NAV"
