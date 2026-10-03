"""
Unit tests for Contrarian 4-State Machine (Phase 20 / TASK-0070)
(Formerly TASK-0069 5-Layer Framework)
"""

import pytest

from contrarian_engine import (
    STATE_BLOCKED,
    STATE_NEAR_PANIC_WATCH,
    STATE_PANIC_BUY,
    STYLE_CONTRARIAN_PANIC_BUY,
    STYLE_WATCH_ZONE,
    evaluate_contrarian_gates,
)


@pytest.fixture
def fpt_derating_data():
    """FPT: Bị bán lây, tài chính vững mạnh, không có event risk."""
    tech = {
        "rsi14": 32.0,  # NEAR PANIC WATCH
        "ma20": 100.0,
        "current_price": 82.0,
        "adv20_billion": 50.0,
        "risk_keywords": "",
        "price_confirmation": True,  # Có tín hiệu đảo chiều
        "is_backtest": True,
    }
    fin = {
        "f_score": 8,
        "z_score": 4.5,
        "debt_equity": 0.5,
        "mos_pct": 35.0,
        "mos_is_informative": True,
        "margin_trend": "stable",
        "fair_value": 140.0,
    }
    return tech, fin

@pytest.fixture
def dgc_value_trap_data():
    """DGC: Bị bán tháo do sự kiện kiểm toán hoặc LN suy giảm (Value Trap)."""
    tech = {
        "rsi14": 20.0,
        "ma20": 80.0,
        "current_price": 60.0,
        "adv20_billion": 30.0,
        "risk_keywords": ["kiểm toán ngoại trừ"],  # Event Risk!
        "price_confirmation": True,
        "is_backtest": True,
    }
    fin = {
        "f_score": 7,
        "z_score": 3.0,
        "debt_equity": 0.2,
        "mos_pct": 40.0,
        "mos_is_informative": True,
        "margin_trend": "down_2_quarters",  # Fundamental Damage!
        "fair_value": 100.0,
    }
    return tech, fin


def test_fpt_derating_watch_only(fpt_derating_data):
    """FPT (RSI 32) đủ điều kiện Quality, vào NEAR-PANIC WATCH. Không mua dù có price confirm."""
    tech, fin = fpt_derating_data
    res = evaluate_contrarian_gates("FPT", 82.0, tech_data=tech, fin_dict=fin, sector="Công nghệ")
    assert res.can_buy is False
    assert res.status == STATE_NEAR_PANIC_WATCH
    assert res.style_type == STYLE_WATCH_ZONE


def test_fpt_derating_buy(fpt_derating_data):
    """FPT rớt thêm (RSI <= 30), có confirm -> Mua."""
    tech, fin = fpt_derating_data
    tech["rsi14"] = 28.0
    res = evaluate_contrarian_gates("FPT", 82.0, tech_data=tech, fin_dict=fin, sector="Công nghệ")
    assert res.can_buy is True
    assert res.status == STATE_PANIC_BUY
    assert res.style_type == STYLE_CONTRARIAN_PANIC_BUY


def test_dgc_value_trap_event_risk(dgc_value_trap_data):
    """DGC bị VETO ngay vì dính từ khóa kiểm toán ngoại trừ, dù RSI 20."""
    tech, fin = dgc_value_trap_data
    fin["margin_trend"] = "stable"
    res = evaluate_contrarian_gates("DGC", 60.0, tech_data=tech, fin_dict=fin, sector="Hóa chất")
    assert res.can_buy is False
    assert res.status == STATE_BLOCKED
    assert res.blocked_by == "GOVERNANCE_EVENT_RISK"
    assert any("kiểm toán ngoại trừ" in r for r in res.blocking_reasons)


def test_dgc_value_trap_fundamental_damage(dgc_value_trap_data):
    """DGC bị chặn vì LNST/biên gộp lao dốc (Earnings Revision down), dù RSI 20."""
    tech, fin = dgc_value_trap_data
    tech["risk_keywords"] = []  # Bỏ event risk để test fundamental damage
    res = evaluate_contrarian_gates("DGC", 60.0, tech_data=tech, fin_dict=fin, sector="Hóa chất")
    assert res.can_buy is False
    assert res.status == STATE_BLOCKED
    assert res.blocked_by == "SURVIVAL_QUALITY"
    assert any("VALUE TRAP!" in r for r in res.blocking_reasons)


def test_downtrend_macro_regime_hurdle(fpt_derating_data):
    """Trong DOWNTREND, yêu cầu MoS >= 30% thay vì 20%."""
    tech, fin = fpt_derating_data
    fin["fair_value"] = 128.0  # Tạo Stress-MoS ~24.8% (Pass ở Uptrend nhưng Fail ở Downtrend)
    
    # 1. Uptrend -> Pass Quality Gate (Vào Near Panic)
    res_up = evaluate_contrarian_gates("FPT", 82.0, tech_data=tech, fin_dict=fin, sector="Công nghệ", macro_regime="UPTREND")
    assert res_up.status == STATE_NEAR_PANIC_WATCH

    # 2. Downtrend -> Blocked by Valuation
    res_down = evaluate_contrarian_gates("FPT", 82.0, tech_data=tech, fin_dict=fin, sector="Công nghệ", macro_regime="DOWNTREND")
    assert res_down.can_buy is False
    assert res_down.status == STATE_BLOCKED
    assert res_down.blocked_by == "VALUATION_MOS"
    assert any("L4 Stress-MoS" in r for r in res_down.blocking_reasons)
