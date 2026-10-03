import copy

from contrarian_engine import (
    GATE_EVENT_RISK,
    GATE_SURVIVAL,
    STATE_BLOCKED,
    STATE_EXTREME_FEAR_WATCH,
    STATE_PANIC_BUY,
    STATE_VALUATION_WATCH,
    evaluate_contrarian_gates,
)

# Ratios thô như get_financial_ratios trả về (KHÔNG có f_score/z_score) + MoS đã tính sẵn
FIN = {
    "roa": 12.0,
    "p_cf": 8.0,
    "roe": 20.0,
    "net_margin": 15.0,
    "debt_equity": 0.3,
    "current_ratio": 2.0,
    "financial_leverage": 1.5,
    "gross_margin": 30.0,
    "roic": 18.0,
    "mos_pct": 28.0,
    "mos_is_informative": True,
    "fair_value": 130.0,
}

TECH = {
    "rsi14": 22.0,
    "ma20": 110.0,
    "adv20_billion": 50.0,
    "volume_ratio_20d": 3.5,
    "atr_ratio_14d": 2.1,
    "has_gap_down": True,
    "risk_keywords": [],
    "price_confirmation": True,
    "higher_low": True,
    "bullish_divergence": True,
    "is_backtest": True,
}


def run(tech=None, fin=None):
    if tech is None:
        tech = TECH
    if fin is None:
        fin = FIN
    return evaluate_contrarian_gates(
        "FPT", 80.0, copy.deepcopy(tech), copy.deepcopy(fin), sector="Công nghệ / AI", macro_regime="UPTREND"
    )


def test_diamond_reaches_panic_buy():
    r = run()
    assert r.status == STATE_PANIC_BUY and r.can_buy, (r.status, r.blocked_by, r.blocking_reasons)


def test_governance_veto():
    r = run(tech={**TECH, "risk_keywords": ["kiểm toán ngoại trừ"]})
    assert r.status == STATE_BLOCKED and r.blocked_by == GATE_EVENT_RISK


def test_weak_fundamentals_blocked_at_survival():
    r = run(
        fin={**FIN, "roa": -2.0, "p_cf": -1.0, "roe": 2.0, "net_margin": -3.0, "current_ratio": 0.7, "gross_margin": 5.0, "roic": 1.0}
    )
    assert r.status == STATE_BLOCKED and r.blocked_by == GATE_SURVIVAL


def test_not_panicking_is_normal():
    assert run(tech={**TECH, "rsi14": 55.0, "ma20": 80.0, "volume_ratio_20d": 1.0, "atr_ratio_14d": 1.0, "has_gap_down": False}).status == STATE_VALUATION_WATCH


def test_extreme_fear_without_confirmation_is_watch_only():
    r = run(tech={**TECH, "price_confirmation": False})
    assert r.status == STATE_EXTREME_FEAR_WATCH and not r.can_buy
