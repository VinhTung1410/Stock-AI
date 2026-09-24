"""Unit tests for TASK-0004:
1. Web-to-Discord hook in ai_analyst.py when action_state is MUA/BUY.
2. Strict gate for watchlist pruning: strictly ATO 08:45 once daily.
3. Test isolation verification (no real network alerts).
"""

from __future__ import annotations

from unittest import mock

import pandas as pd


def test_web_to_discord_hook_triggers_on_buy(monkeypatch):
    """Verify generate_quantamental_2pass_report triggers Discord DM alert when action is MUA."""
    captured_alerts = []

    def mock_send_alert(symbol, action, current_price, trigger_reason, target_price=None, stop_loss=None):
        captured_alerts.append({
            "symbol": symbol,
            "action": action,
            "current_price": current_price,
            "target_price": target_price,
            "stop_loss": stop_loss,
            "trigger_reason": trigger_reason,
        })
        return True

    monkeypatch.setattr("discord_alerts.send_trade_signal_alert", mock_send_alert)

    mock_client = mock.MagicMock()
    mock_resp = mock.MagicMock()
    mock_resp.text = '{"P_bull": 0.5, "P_base": 0.3, "P_bear": 0.2, "rationale_bull": "Tốt", "rationale_base": "Bình thường", "rationale_bear": "Xấu"}'
    mock_client.models.generate_content.return_value = mock_resp

    with mock.patch("ai_analyst.get_ai_client", return_value=mock_client):
        with mock.patch("ai_analyst.call_gemini", return_value="AI Institutional CFA Report Text"):
            with mock.patch("data_engine.fetch_stock_technical", return_value={"current_price": 33.0, "rsi14": 55.0, "status_ma20": "TRÊN MA20", "adv20_billion": 10.0}):
                with mock.patch("data_engine.get_financial_ratios", return_value={"pe": 7.5, "pb": 1.1, "roe": 22.0, "debt_equity": 0.5}):
                    with mock.patch("data_engine.fetch_macro_news", return_value=[]):
                        with mock.patch("quant_engine.check_data_gate", return_value={"passed": True, "daily_value_billion": 10.0}):
                            with mock.patch("quant_engine.calculate_piotroski_f_score", return_value={"score": 7, "rating": "RẤT MẠNH"}):
                                with mock.patch("quant_engine.calculate_altman_z_score", return_value={"z_score": 2.8, "zone": "AN TOÀN", "icon": "🟢"}):
                                    with mock.patch("quant_engine.calculate_valuation_triangle", return_value={"price_bull": 45.0, "price_base": 38.0, "price_bear": 30.0}):
                                        with mock.patch("quant_engine.evaluate_decision_hard_gates", return_value={
                                            "action_state": "🟢 KHUYẾN NGHỊ MUA",
                                            "decision_tag": "TÍCH SẢN GIÁ TRỊ",
                                            "mos_pct": 20.0,
                                            "price_target": 45.0,
                                            "stop_loss": 30.0,
                                            "downside_pct": 9.1,
                                            "ev": 40.0,
                                            "risk_reward": 2.5,
                                            "risk_reward_ratio": 2.5,
                                            "kelly_f": 0.15,
                                            "kelly_f_star": 0.15,
                                            "position_size_nav": "10% NAV",
                                        }):
                                            with mock.patch("db_manager.save_quant_signal", return_value=37):
                                                from ai_analyst import generate_quantamental_2pass_report

                                                res = generate_quantamental_2pass_report("TCB")
                                                assert res["status"] == "SUCCESS"

    # Verify Discord alert was fired with exact ticker and BUY action
    assert len(captured_alerts) == 1
    alert = captured_alerts[0]
    assert alert["symbol"] == "TCB"
    assert alert["action"] == "MUA"
    assert alert["current_price"] == 33.0
    assert alert["target_price"] == 45.0
    assert alert["stop_loss"] == 30.0
    assert "[WEB AI ANALYST]" in alert["trigger_reason"]


def test_trading_bot_ato_prune_gate(monkeypatch):
    """Verify watchlist pruning only runs strictly at ATO 08:45 once daily."""
    import trading_bot

    prune_called_count = 0

    def mock_sync_watchlist(prune_manual=False):
        nonlocal prune_called_count
        prune_called_count += 1
        return []

    monkeypatch.setattr("trading_bot.sync_auto_watchlist", mock_sync_watchlist)
    monkeypatch.setattr("trading_bot.load_portfolio", lambda: [])
    monkeypatch.setattr("trading_bot.load_watchlist", lambda: [])
    monkeypatch.setattr("trading_bot.evaluate_portfolio", lambda p: pd.DataFrame())
    monkeypatch.setattr("trading_bot.evaluate_watchlist", lambda w: pd.DataFrame())
    monkeypatch.setattr("trading_bot.fetch_macro_news", lambda **k: [])
    monkeypatch.setattr("trading_bot.scan_market_opportunities", lambda **k: [])
    monkeypatch.setattr("trading_bot.generate_morning_strategy_report", lambda *a, **k: "Report")
    monkeypatch.setattr("trading_bot.generate_portfolio_analysis", lambda *a, **k: "Report")
    monkeypatch.setattr("trading_bot.format_portfolio_embed", lambda *a, **k: {})
    monkeypatch.setattr("trading_bot.send_discord_dm", lambda *a, **k: True)
    monkeypatch.setattr("trading_bot.send_discord_webhook", lambda *a, **k: True)

    trading_bot.last_ato_pruned_date = ""

    # 1. ATO 08:45 first run -> Pruning executes
    trading_bot.trigger_scheduled_report("08:45", "Báo cáo đầu phiên ATO")
    assert prune_called_count == 1

    # 2. ATO 08:45 repeated run same day -> Gated! Does not re-run
    trading_bot.trigger_scheduled_report("08:45", "Báo cáo lặp lại")
    assert prune_called_count == 1

    # 3. Lunch report 11:30 -> Does not prune
    trading_bot.trigger_scheduled_report("11:30", "Báo cáo phiên trưa")
    assert prune_called_count == 1
