# -*- coding: utf-8 -*-
"""Unit tests for TASK-0082: Data Gate & Quant Valuation Normalization (Phase 28 - v15.0)."""

from indicators import calculate_valuation_triangle
from quant_engine import evaluate_decision_hard_gates
from quant_valuation import evaluate_real_estate_valuation


def test_real_estate_bvps_normalization_vnd_to_kvnd():
    """AC-01: BVPS raw in VND (e.g. 15,000 VND) must be normalized to kVND (15.0)

    to prevent MoS from blowing up to 99.9%.
    """
    sym = "DXG"
    curr_price = 15.0  # kVND
    fin_dict = {
        "bvps": 15000.0,  # VND raw from API
        "pb": 1.0,
        "roe": 10.0,
        "debt_equity": 0.8,
    }

    res = evaluate_real_estate_valuation(symbol=sym, current_price=curr_price, fin_dict=fin_dict, sector="Bất động sản")

    # Fair value must be in reasonable kVND range, not 15,000 * 1.15 = 17,250!
    assert 10.0 <= res["fv_base"] <= 30.0
    mos = round(((res["fv_base"] - curr_price) / res["fv_base"]) * 100, 2)
    assert mos < 60.0  # Must never be +99.9%
    assert res["is_informative"] is True


def test_real_estate_bvps_already_kvnd():
    """BVPS already in kVND scale (< 500) should not be divided again."""
    sym = "NLG"
    curr_price = 25.0
    fin_dict = {
        "bvps": 22.0,  # kVND
        "pb": 1.14,
        "roe": 12.0,
        "debt_equity": 0.5,
    }

    res = evaluate_real_estate_valuation(symbol=sym, current_price=curr_price, fin_dict=fin_dict, sector="Bất động sản")
    assert 15.0 <= res["fv_base"] <= 40.0
    assert res["is_informative"] is True


def test_uninformative_mos_no_fake_positive_fallback():
    """AC-02: Missing fundamentals must not produce fake positive MoS (e.g. 9.1%)

    and must be tagged as uninformative with can_buy = False.
    """
    current_price = 50.0
    # Simulate missing/empty fundamental data
    fin_dict = {}

    gate = evaluate_decision_hard_gates(
        current_price=current_price,
        p_bull=0.25,
        p_base=0.50,
        p_bear=0.25,
        price_bull=60.0,
        price_base=55.0,
        price_bear=40.0,
        symbol="UNKNOWN_STOCK",
        fin_dict=fin_dict,
        sector="Công nghệ",
    )

    assert gate["can_buy"] is False
    assert gate["action_state"] == "🟡 THEO DÕI"
    assert "Thiếu dữ liệu BCTC tin cậy" in gate["decision_tag"]
    # MoS must not be fabricated from price_base fallback
    assert gate["gate_mos_passed"] is False


def test_calculate_valuation_triangle_quant_anchor():
    """AC-03: When fair_value is provided, scenarios must anchor to fair_value

    instead of naive scalar multipliers (x1.25 / x0.85).
    """
    curr_price = 100.0
    fv = 120.0
    fv_bull = 140.0
    fv_bear = 95.0

    res = calculate_valuation_triangle(
        current_price=curr_price,
        pe=15.0,
        pb=2.0,
        sector="Công nghệ",
        fair_value=fv,
        fv_bull=fv_bull,
        fv_bear=fv_bear,
    )

    assert res["price_base"] == 120.0
    assert res["price_bull"] == 140.0
    assert res["price_bear"] == 95.0
    assert res["has_quant_anchor"] is True
    assert res["rr_ratio"] > 0


def test_calculate_valuation_triangle_backward_compatible():
    """AC-04: Legacy calls without fair_value must retain exact backward compatibility."""
    res_zero = calculate_valuation_triangle(0)
    assert res_zero["price_base"] == 0.0

    res_norm = calculate_valuation_triangle(100.0, pe=15.0, pb=2.0)
    assert res_norm["price_bull"] == 125.0
    assert res_norm["price_base"] == 110.0
    assert res_norm["price_bear"] == 85.0
    assert res_norm["has_quant_anchor"] is False

    res_cyc = calculate_valuation_triangle(100.0, pe=4.5, pb=1.2, sector="Thép")
    assert res_cyc["is_cyclical"] is True
    assert res_cyc["price_bull"] == 115.0
    assert res_cyc["price_base"] == 102.0
    assert res_cyc["price_bear"] == 78.0
