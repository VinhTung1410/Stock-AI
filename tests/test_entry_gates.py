"""
Integration & Unit Test Suite for Phase 15: Unified Entry Gate (v7.5).

Covers:
- TASK-0046: 7-layer unified entry gate evaluate_entry_gates() in entry_gates.py.
- TASK-0047: Macro gate wiring across all paths (DOWNTREND blocks all BUYs).
- TASK-0048: Discord-confirmed cooldown timing.
- TASK-0049: 2-Pass archetype & sector wiring (UNKNOWN blocks BUY, no GROWTH fallback).
- TASK-0050: Smart Committee Quant Hard Gate Arbitrator.
- TASK-0051: Active Screener status mapping (RECOMMEND_BUY -> HIGH_CONVICTION).
"""


from entry_gates import (
    EntryGateResult,
    evaluate_entry_gates,
)

# =============================================================================
# MOCK FIXTURES & DATA
# =============================================================================

MOCK_TECH_BULLISH = {
    "current_price": 50.0,
    "ma20": 48.0,
    "ma50": 45.0,
    "rsi": 55.0,
    "rsi14": 55.0,
    "vol_ratio": 1.5,
    "status_ma20": "UPTREND",
    "tech_signal": "BULLISH_CONFIRMED",
    "adv20_billion": 25.0,
}

MOCK_TECH_FALLING_KNIFE = {
    "current_price": 40.0,
    "ma20": 48.0,
    "ma50": 52.0,
    "rsi": 32.0,
    "rsi14": 32.0,
    "vol_ratio": 2.0,
    "status_ma20": "DOWNTREND",
    "tech_signal": "FALLING_KNIFE",
    "adv20_billion": 20.0,
}

MOCK_FIN_HEALTHY = {
    "period": "2026-Q2",
    "f_score": 8,
    "z_score": 3.5,
    "pe": 12.0,
    "pb": 1.8,
    "roe": 22.0,
    "debt_equity": 0.5,
    "forward_eps": 5.0,
}

MOCK_FIN_DISTRESS = {
    "period": "2026-Q2",
    "f_score": 2,
    "z_score": 0.95,
    "pe": 45.0,
    "pb": 4.5,
    "roe": 3.0,
    "debt_equity": 3.2,
}


# =============================================================================
# TESTS: 7-LAYER GATES (TASK-0046)
# =============================================================================

def test_layer_0_macro_downtrend_blocks_buy():
    """Tầng 0: Macro Downtrend phải chặn 100% lệnh MUA."""
    res = evaluate_entry_gates(
        symbol="FPT",
        current_price=50.0,
        fin_dict=MOCK_FIN_HEALTHY,
        tech_data=MOCK_TECH_BULLISH,
        sector="Công nghệ",
        archetype="GROWTH_COMPOUNDER",
        macro_regime="DOWNTREND",
        caller="SCAN",
        conviction_score=80.0,
    )
    assert isinstance(res, EntryGateResult)
    assert res.can_buy is False
    assert res.blocked_by == "MACRO_REGIME"
    assert res.position_size_multiplier == 0.0
    assert any("DOWNTREND" in r for r in res.blocking_reasons)


def test_layer_0_macro_failsafe_warning_and_halves_size():
    """Tầng 0: Thiếu dữ liệu vĩ mô kích hoạt Fail-Safe: cảnh báo & giảm 50% size, không block hẳn."""
    res = evaluate_entry_gates(
        symbol="FPT",
        current_price=50.0,
        fin_dict=MOCK_FIN_HEALTHY,
        tech_data=MOCK_TECH_BULLISH,
        sector="Công nghệ",
        archetype="GROWTH_COMPOUNDER",
        macro_regime=None,  # Missing VN-Index data
        caller="SCAN",
        conviction_score=80.0,
    )
    assert res.can_buy is True
    assert res.position_size_multiplier == 0.5
    assert any("MACRO_FAILSAFE" in r or "50%" in r for r in res.blocking_reasons)
    assert "MACRO_REGIME" in res.passed_gates


def test_layer_1_data_gate_stale_or_missing_blocks_buy():
    """Tầng 1: Data gate không đạt chuẩn hoặc BCTC stale -> Block."""
    stale_fin = {**MOCK_FIN_HEALTHY, "period": "2023-Q1"}  # > 1 year old
    res = evaluate_entry_gates(
        symbol="FPT",
        current_price=50.0,
        fin_dict=stale_fin,
        tech_data=MOCK_TECH_BULLISH,
        sector="Công nghệ",
        macro_regime="UPTREND",
        caller="SCAN",
        conviction_score=80.0,
    )
    assert res.can_buy is False
    assert res.blocked_by == "DATA_GATE"
    assert res.position_size_multiplier == 0.0


def test_layer_2_financial_health_f_score_le_3_blocks_buy():
    """Tầng 2: F-Score <= 3 -> Block."""
    weak_fin = {**MOCK_FIN_HEALTHY, "f_score": 3}
    res = evaluate_entry_gates(
        symbol="FPT",
        current_price=50.0,
        fin_dict=weak_fin,
        tech_data=MOCK_TECH_BULLISH,
        sector="Công nghệ",
        macro_regime="UPTREND",
        caller="WATCHLIST",
        conviction_score=75.0,
    )
    assert res.can_buy is False
    assert res.blocked_by == "FINANCIAL_HEALTH"
    assert any("F-Score" in r for r in res.blocking_reasons)


def test_layer_2_financial_health_z_score_distress_blocks_buy():
    """Tầng 2: Z-Score < 1.23 (vùng kiệt quệ phá sản) -> Block đối với phi tài chính."""
    distress_fin = {**MOCK_FIN_HEALTHY, "f_score": 6, "z_score": 1.10}
    res = evaluate_entry_gates(
        symbol="HPG",
        current_price=25.0,
        fin_dict=distress_fin,
        tech_data=MOCK_TECH_BULLISH,
        sector="Thép",
        macro_regime="UPTREND",
        caller="SCAN",
        conviction_score=75.0,
    )
    assert res.can_buy is False
    assert res.blocked_by == "FINANCIAL_HEALTH"
    assert any("Z-Score" in r for r in res.blocking_reasons)


def test_layer_3_valuation_mos_uninformative_or_below_threshold_blocks():
    """Tầng 3: MoS không informative hoặc dưới ngưỡng của archetype -> Block."""
    # Archetype BANK requires MoS >= 10.0%
    fin_expensive = {**MOCK_FIN_HEALTHY, "pb": 2.5, "roe": 12.0}
    res = evaluate_entry_gates(
        symbol="BID",
        current_price=50.0,
        fin_dict=fin_expensive,
        tech_data=MOCK_TECH_BULLISH,
        sector="Ngân hàng",
        archetype="BANK",
        macro_regime="UPTREND",
        caller="SCAN",
        conviction_score=75.0,
    )
    assert res.can_buy is False
    assert res.blocked_by == "VALUATION_MOS"


def test_layer_4_technical_momentum_falling_knife_blocks():
    """Tầng 4: tech_signal không thuộc BULLISH_SET -> Block."""
    res = evaluate_entry_gates(
        symbol="MWG",
        current_price=40.0,
        fin_dict=MOCK_FIN_HEALTHY,
        tech_data=MOCK_TECH_FALLING_KNIFE,
        sector="Bán lẻ",
        archetype="GROWTH_COMPOUNDER",
        macro_regime="UPTREND",
        caller="WATCHLIST",
        conviction_score=75.0,
    )
    assert res.can_buy is False
    assert res.blocked_by == "TECHNICAL_MOMENTUM"
    assert any("FALLING_KNIFE" in r or "BULLISH_SET" in r for r in res.blocking_reasons)


def test_layer_5_conviction_below_60_blocks():
    """Tầng 5: conviction_score < 60 -> Block."""
    res = evaluate_entry_gates(
        symbol="FPT",
        current_price=50.0,
        fin_dict=MOCK_FIN_HEALTHY,
        tech_data=MOCK_TECH_BULLISH,
        sector="Công nghệ",
        archetype="GROWTH_COMPOUNDER",
        macro_regime="UPTREND",
        caller="SCAN",
        conviction_score=55.0,
    )
    assert res.can_buy is False
    assert res.blocked_by == "QUANT_CONVICTION"
    assert any("Conviction" in r for r in res.blocking_reasons)


def test_layer_6_pm_veto_blocks():
    """Tầng 6: PM Veto flag kích hoạt -> Block."""
    res = evaluate_entry_gates(
        symbol="FPT",
        current_price=50.0,
        fin_dict=MOCK_FIN_HEALTHY,
        tech_data=MOCK_TECH_BULLISH,
        sector="Công nghệ",
        archetype="GROWTH_COMPOUNDER",
        macro_regime="UPTREND",
        caller="COMMITTEE",
        conviction_score=85.0,
        pm_veto=True,
    )
    assert res.can_buy is False
    assert res.blocked_by == "PM_VETO"
    assert any("Veto" in r for r in res.blocking_reasons)


def test_all_gates_pass_healthy_stock():
    """Tất cả 7 tầng đạt chuẩn -> can_buy=True, full size."""
    res = evaluate_entry_gates(
        symbol="FPT",
        current_price=50.0,
        fin_dict={
            "period": "2026-Q2",
            "f_score": 8,
            "z_score": 3.8,
            "roe": 25.0,
            "pe": 16.0,
            "pb": 3.0,
            "forward_eps": 5.0,
            "target_pe": 20.0,  # Fair value = 100k, current = 50k -> MoS = 50%
        },
        tech_data=MOCK_TECH_BULLISH,
        sector="Công nghệ",
        archetype="GROWTH_COMPOUNDER",
        macro_regime="UPTREND",
        caller="TWO_PASS",
        conviction_score=85.0,
    )
    assert res.can_buy is True
    assert res.blocked_by is None
    assert res.position_size_multiplier == 1.0
    assert len(res.passed_gates) >= 5


# =============================================================================
# TESTS: CALLER SPECIFICS & CROSS-PATH MATRIX (TASK-0047 -> TASK-0051)
# =============================================================================

def test_two_pass_unknown_archetype_blocks_buy():
    """TASK-0049: 2-Pass khi gặp mã không rõ ngành nghề -> tự động block, không default GROWTH."""
    res = evaluate_entry_gates(
        symbol="XYZ_UNKNOWN",
        current_price=20.0,
        fin_dict=MOCK_FIN_HEALTHY,
        tech_data=MOCK_TECH_BULLISH,
        sector="",  # Unknown sector
        archetype="UNKNOWN",
        macro_regime="UPTREND",
        caller="TWO_PASS",
        conviction_score=80.0,
    )
    assert res.can_buy is False
    assert res.blocked_by == "VALUATION_MOS"
    assert any("archetype" in r.lower() or "ngành" in r.lower() for r in res.blocking_reasons)


def test_active_screener_status_mapping():
    """TASK-0051: Screener status RECOMMEND_BUY khớp chuẩn với HIGH_CONVICTION."""
    from trading_bot import _process_active_screener_opportunity

    sent = False

    def mock_send(*args, **kwargs):
        nonlocal sent
        sent = True
        return True

    # Monkeypatching send_trade_signal_alert
    import trading_bot
    original_send = trading_bot.send_trade_signal_alert
    original_cooldown = trading_bot.is_symbol_in_cooldown
    trading_bot.send_trade_signal_alert = mock_send
    trading_bot.is_symbol_in_cooldown = lambda *a, **k: False
    trading_bot.sent_alerts.clear()

    try:
        opp = {
            "symbol": "FPT",
            "current_price": 50.0,
            "conviction_score": 85.0,
            "status": "RECOMMEND_BUY",  # Data engine outputs RECOMMEND_BUY
        }
        _process_active_screener_opportunity(opp, today_str="2026-10-02")
        assert sent is True, "Active screener should accept status RECOMMEND_BUY"
    finally:
        trading_bot.send_trade_signal_alert = original_send
        trading_bot.is_symbol_in_cooldown = original_cooldown


def test_cooldown_only_on_discord_success():
    """TASK-0048: record_signal_cooldown chỉ được gọi khi Discord gửi thành công (success=True)."""
    import trading_bot

    cooldown_called = False

    def mock_cooldown(*args, **kwargs):
        nonlocal cooldown_called
        cooldown_called = True

    original_send = trading_bot.send_trade_signal_alert
    original_cooldown = trading_bot.record_signal_cooldown
    trading_bot.record_signal_cooldown = mock_cooldown
    trading_bot.is_symbol_in_cooldown = lambda *a, **k: False
    trading_bot.sent_alerts.clear()

    try:
        # Case A: Discord returns False (failed)
        trading_bot.send_trade_signal_alert = lambda *a, **k: False
        opp = {
            "symbol": "TCB",
            "current_price": 30.0,
            "conviction_score": 85.0,
            "status": "RECOMMEND_BUY",
        }
        trading_bot._process_active_screener_opportunity(opp, today_str="2026-10-02")
        assert cooldown_called is False, "Cooldown should NOT be recorded if Discord fails"

        # Case B: Discord returns True (success)
        trading_bot.send_trade_signal_alert = lambda *a, **k: True
        trading_bot._process_active_screener_opportunity(opp, today_str="2026-10-02")
        assert cooldown_called is True, "Cooldown MUST be recorded when Discord succeeds"
    finally:
        trading_bot.send_trade_signal_alert = original_send
        trading_bot.record_signal_cooldown = original_cooldown


def test_scan_market_opportunities_with_macro_downtrend_returns_zero_buys(monkeypatch):
    """TASK-0047: Khi VN-Index DOWNTREND, scanner trả về 0 khuyến nghị RECOMMEND_BUY."""
    from data_engine import scan_market_opportunities

    # Mock fetch_stock_technical and get_financial_ratios to return healthy stock data
    monkeypatch.setattr(
        "data_engine.fetch_stock_technical",
        lambda sym: {
            "current_price": 50.0,
            "ma20": 48.0,
            "ma50": 45.0,
            "rsi": 55.0,
            "rsi14": 55.0,
            "vol_ratio": 1.5,
            "status_ma20": "UPTREND",
            "tech_signal": "BULLISH_CONFIRMED",
            "adv20_billion": 25.0,
        },
    )
    monkeypatch.setattr(
        "data_engine.get_financial_ratios",
        lambda sym: {
            "period": "2026-Q2",
            "f_score": 8,
            "z_score": 3.5,
            "pe": 12.0,
            "pb": 1.8,
            "roe": 22.0,
            "forward_eps": 5.0,
            "target_pe": 20.0,
        },
    )

    opps = scan_market_opportunities(extra_symbols=["FPT"], macro_regime="DOWNTREND")
    buys = [o for o in opps if o.get("status") == "RECOMMEND_BUY"]
    assert len(buys) == 0, f"Downtrend must yield 0 BUY recommendations, got {buys}"


def test_smart_committee_overridden_when_quant_gate_fails(monkeypatch):
    """TASK-0050: Smart Committee có LLM đề xuất STRONG_OPPORTUNITY nhưng MoS âm hoặc vi phạm gate -> PM Overridden."""
    import ai_analyst

    mock_llm_response = """
    FA View: TĂNG TRƯỞNG
    TA View: TÍCH CỰC
    Red Team: Rủi ro sụt giảm 10%
    PM Decision: STRONG_OPPORTUNITY
    """

    monkeypatch.setattr("ai_analyst.call_gemini", lambda *a, **k: mock_llm_response)
    monkeypatch.setattr("ai_analyst.get_ai_client", lambda: None)
    monkeypatch.setattr("db_manager.save_decision_record", lambda *a, **k: None)

    # Price 100k, fair value ~20k -> MoS negative
    tech_data = {
        "current_price": 100.0,
        "ma20": 98.0,
        "ma50": 95.0,
        "rsi": 55.0,
        "rsi14": 55.0,
        "vol_ratio": 1.5,
        "status_ma20": "UPTREND",
        "tech_signal": "BULLISH_CONFIRMED",
        "adv20_billion": 25.0,
    }
    fin_data = {
        "period": "2026-Q2",
        "f_score": 8,
        "z_score": 3.5,
        "pe": 50.0,
        "pb": 5.0,
        "roe": 10.0,
    }

    res = ai_analyst.analyze_stock_with_smart_committee(
        symbol="FPT",
        tech_data=tech_data,
        fin_data=fin_data,
        news_items=[],
    )

    assert res["status"] == "SUCCESS"
    assert res["pm_decision"] != "STRONG_OPPORTUNITY", "Quant gate failure must veto LLM STRONG_OPPORTUNITY"
    assert res["is_overridden"] is True
    assert "Quant Entry Gate Veto" in res["override_reason"] or "Veto-Only" in res["override_reason"]


def test_two_pass_bid_bank_valuation_not_growth():
    """TASK-0049: 2-Pass với BID (ngân hàng) sử dụng Justified P/B, không default GROWTH."""
    from quant_valuation import calculate_fair_value_and_mos

    fin_bank = {
        "period": "2026-Q2",
        "pb": 1.8,
        "roe": 18.0,
        "f_score": 7,
    }
    val = calculate_fair_value_and_mos("BID", current_price=45.0, fin_dict=fin_bank, sector="Ngân hàng")
    assert val["archetype"] == "BANK"
    assert "Justified P/B" in val["valuation_method"]

