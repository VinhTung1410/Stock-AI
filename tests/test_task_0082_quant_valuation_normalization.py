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


def test_calculate_fair_value_and_mos_across_all_four_archetypes():
    """AC-05: Verify calculate_fair_value_and_mos fail-closed logic across BANK, REAL_ESTATE, CYCLICAL, COMPOUNDER."""
    from quant_valuation import calculate_fair_value_and_mos

    # 1. BANK: Valid P/B
    bank_val = calculate_fair_value_and_mos("ACB", current_price=25.0, fin_dict={"pb": 1.2, "roe": 18.0}, sector="Ngân hàng")
    assert bank_val["mos_is_informative"] is True
    assert bank_val["mos_pct"] is not None

    # BANK: Missing P/B -> fail-closed, no synthetic 1.05x price fallback
    bank_no_pb = calculate_fair_value_and_mos("UNKNOWN_BANK", current_price=25.0, fin_dict={}, sector="Ngân hàng")
    assert bank_no_pb["mos_is_informative"] is False
    assert bank_no_pb["mos_pct"] is None
    assert bank_no_pb["fair_value"] == 0.0

    # 2. REAL_ESTATE: BVPS in raw VND (18,000 VND) normalized to 18.0 kVND
    re_val = calculate_fair_value_and_mos("DXG", current_price=15.0, fin_dict={"bvps": 18000.0, "pb": 1.0, "roe": 10.0}, sector="Bất động sản")
    assert re_val["mos_is_informative"] is True
    assert re_val["mos_pct"] is not None
    assert re_val["mos_pct"] < 60.0  # NOT 99.9%!

    # REAL_ESTATE: Missing BCTC -> fail-closed
    re_empty = calculate_fair_value_and_mos("DXG", current_price=15.0, fin_dict={}, sector="Bất động sản")
    assert re_empty["mos_is_informative"] is False
    assert re_empty["mos_pct"] is None

    # 3. CYCLICAL: Missing EPS and P/E -> fail-closed
    cyc_empty = calculate_fair_value_and_mos("HPG", current_price=28.0, fin_dict={}, sector="Thép")
    assert cyc_empty["mos_is_informative"] is False
    assert cyc_empty["mos_pct"] is None

    # 4. COMPOUNDER: Missing EPS and no consensus -> fail-closed
    comp_empty = calculate_fair_value_and_mos("UNKNOWN_TECH", current_price=50.0, fin_dict={}, sector="Công nghệ")
    assert comp_empty["mos_is_informative"] is False
    assert comp_empty["mos_pct"] is None

    # 5. Ratio bounds check: FV / Price ratio < 0.25 or > 4.0 must be deemed uninformative
    insane_re = calculate_fair_value_and_mos("DXG", current_price=10.0, fin_dict={"bvps": 5000000.0, "pb": 1.0}, sector="Bất động sản")
    assert insane_re["mos_is_informative"] is False
    assert insane_re["mos_pct"] is None


def test_floor_clamped_uninformative_and_none_mos():
    """Verify that stocks clamped by the 40% floor (HSG, VIC) are flagged as FLOOR_CLAMPED

    with informative = False and mos_pct = None.
    """
    from quant_valuation import calculate_fair_value_and_mos

    # VIC: SOTP/RNAV heavily discounted with high leverage -> hits 0.40 * current_price floor
    vic_res = calculate_fair_value_and_mos(
        "VIC",
        current_price=227.9,
        fin_dict={"bvps": 91160.0, "pb": 2.5, "roe": 2.0, "debt_equity": 3.0},
        sector="Bất động sản",
    )
    assert vic_res["is_floor_clamped"] is True
    assert vic_res["mos_is_informative"] is False
    assert vic_res["mos_pct"] is None
    assert vic_res["input_source"] == "FLOOR_CLAMPED"

    # HSG: Cyclical deep discount -> hits 40% floor
    hsg_res = calculate_fair_value_and_mos(
        "HSG",
        current_price=10.0,
        fin_dict={"eps": 0.0667, "pe": 150.0},
        sector="Thép",
    )
    assert hsg_res["is_floor_clamped"] is True
    assert hsg_res["mos_is_informative"] is False
    assert hsg_res["mos_pct"] is None


def test_unclassified_archetype_for_financials_and_utilities():
    """Verify securities, insurance, and utilities are tagged as UNCLASSIFIED without fabricated valuations."""
    from quant_valuation import calculate_fair_value_and_mos, classify_stock_archetype

    for sym in ["SSI", "VND", "BVH", "GAS", "BCM"]:
        arch = classify_stock_archetype(sym)
        assert arch == "UNCLASSIFIED"

        res = calculate_fair_value_and_mos(sym, current_price=20.0, fin_dict={})
        assert res["archetype"] == "UNCLASSIFIED"
        assert res["fair_value"] == 0.0
        assert res["mos_pct"] is None
        assert res["mos_is_informative"] is False
        assert res["input_source"] == "UNCLASSIFIED_SECTOR"


def test_hardcoded_benchmark_requires_dated_freshness():
    """Verify that hardcoded compounder benchmarks without verified timestamps are uninformative."""
    from unittest.mock import patch

    from quant_valuation import COMPOUNDER_FUNDAMENTAL_BENCHMARKS, calculate_fair_value_and_mos

    # FPT with undated benchmark must not claim informative = True
    bench_undated = dict(COMPOUNDER_FUNDAMENTAL_BENCHMARKS.get("FPT", {}))
    bench_undated["last_updated"] = None
    with patch.dict(COMPOUNDER_FUNDAMENTAL_BENCHMARKS, {"FPT": bench_undated}):
        fpt_res = calculate_fair_value_and_mos("FPT", current_price=60.0, fin_dict={})
        assert fpt_res["input_source"] == "HARDCODED_BENCHMARK"
        assert fpt_res["mos_is_informative"] is False
        assert fpt_res["mos_pct"] is None


def test_run_pipeline_propagation_none_mos():
    """Verify that when MoS is None, Valuation pillar receives 0 points,

    decision is WATCH, and cannot buy.
    """
    from quant_engine import run_pipeline

    res = run_pipeline("SSI", current_price=20.0, fin_dict={}, tech_data={"current_price": 20.0, "ma20": 19.5, "rsi": 54.0, "vol_ratio": 1.2, "adv20_billion": 50.0})
    assert res["mos_pct"] is None
    assert res["mos_is_informative"] is False
    assert res["can_buy"] is False
    assert "THEO DÕI" in res["action_state"]
    assert res["conviction_breakdown"]["valuation"] == 0.0
    assert res["conviction_score"] < 70.0
