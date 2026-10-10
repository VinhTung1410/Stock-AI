# -*- coding: utf-8 -*-
"""Unit tests for Triangle Arbitration, Model Dispersion, Causal Chains, and Parameter Hardening.

Covers:
- Triangle Arbitration: API P/B distorted vs BCTC BVPS verified -> effective_pb and informative maintained.
- STB Floor Clamping: target_pb_raw negative (-0.07) clamped to floor (0.90) and flagged.
- FPT Model Dispersion: spread between primary and shadow models detected as confidence signal.
- GVR Stock-Specific Median PE: historical 13.5x prevents blunt 8.5x distortion.
- Causal Chains: entry gate failure chain logged (VALUATION_MOS -> QUANT_CONVICTION).
"""

from entry_gates import GATE_QUANT_CONVICTION, GATE_VALUATION_MOS, evaluate_entry_gates
from quant_valuation import (
    calculate_fair_value_and_mos,
    evaluate_cyclical_valuation,
    evaluate_real_estate_valuation,
    reconcile_pb_triangle_arbitration,
)


def test_triangle_arbitration_validates_bctc_bvps_when_api_pb_distorted():
    """Verify Triangle Arbitration accepts BCTC BVPS and arbitrates effective_pb."""
    # CTG case: Price = 29.5, API P/B = 1.61, BCTC BVPS = 31,635 VND
    fin_ctg = {
        "bvps": 31635.24,
        "pb": 1.61,
        "roe": 21.05,
        "audit_trail": {"source": "KBS_Primary", "period": "2026-Q2"},
    }
    res = reconcile_pb_triangle_arbitration(
        symbol="CTG",
        current_price=29.5,
        pb=1.61,
        bvps_val=31.635,
        fin_dict=fin_ctg,
    )
    assert res["pb_arbitrated"] is True
    assert res["pb_reconcile_failed"] is False
    assert res["effective_pb"] == 0.93


def test_triangle_arbitration_fails_closed_when_bctc_audit_missing():
    """Verify Triangle Arbitration rejects when BVPS has no BCTC audit trail."""
    fin_unverified = {
        "bvps": 30000.0,
        "pb": 2.5,
    }
    res = reconcile_pb_triangle_arbitration(
        symbol="UNKNOWN",
        current_price=10.0,
        pb=2.5,
        bvps_val=30.0,
        fin_dict=fin_unverified,
    )
    assert res["pb_arbitrated"] is False
    assert res["pb_reconcile_failed"] is True


def test_real_estate_triangle_arbitration_for_dig():
    """Verify Real Estate valuation uses Triangle Arbitration for DIG."""
    # DIG case: Price = 9.4, API P/B = 1.83, BVPS = 12,728 VND
    fin_dig = {
        "bvps": 12728.0,
        "pb": 1.83,
        "roe": 4.01,
        "audit_trail": {"source": "KBS_Primary", "period": "2026-Q2"},
    }
    re_res = evaluate_real_estate_valuation("DIG", current_price=9.4, fin_dict=fin_dig, sector="Bất động sản")
    assert re_res["pb_arbitrated"] is True
    assert re_res["effective_pb"] == 0.74
    assert re_res["is_informative"] is True
    assert re_res["confidence"] == "LOW" or re_res["confidence"] == "MEDIUM"


def test_stb_pb_clamp_tracking():
    """Verify STB target_pb_raw and is_pb_clamped are correctly captured."""
    fin_stb = {
        "bvps": 33267.0,
        "roe": 40.41,  # API corrupted ROE
        "pb": 2.02,
        "audit_trail": {"source": "KBS_Primary", "period": "2026-Q2"},
    }
    val = calculate_fair_value_and_mos("STB", current_price=67.3, fin_dict=fin_stb, sector="Ngân hàng")
    assert val["is_pb_clamped"] is True
    assert val["target_pb_raw"] is not None
    assert val["target_pb_raw"] < 0.5  # raw justified P/B is negative or very low
    assert val["fair_value"] == 29.94  # 33.27k * 0.90


def test_fpt_model_dispersion_detection():
    """Verify FPT detects model dispersion between primary and shadow models."""
    val_fpt = calculate_fair_value_and_mos("FPT", current_price=57.9, fin_dict={}, sector="Công nghệ")
    assert val_fpt["archetype"] == "GROWTH_COMPOUNDER"
    assert val_fpt["model_dispersion_pct"] is not None
    assert val_fpt["model_dispersion_pct"] > 15.0
    assert val_fpt["confidence"] == "MEDIUM"


def test_gvr_stock_specific_cyclical_median_pe():
    """Verify GVR uses historical 13.5x multiple instead of flat 8.5x."""
    fin_gvr = {
        "eps": 1615.0,
        "audit_trail": {"source": "KBS_Primary", "period": "2026-Q2"},
    }
    cyc_res = evaluate_cyclical_valuation("GVR", current_price=32.85, fin_dict=fin_gvr, sector="Tài nguyên Cơ bản")
    # Base EPS 1.615k * 13.5x = 21.80k
    assert cyc_res["fv_base"] >= 20.0
    # Sanity ratio FV / Price must be >= 0.50
    ratio = cyc_res["fv_base"] / 32.85
    assert ratio >= 0.50


def test_causal_chains_logged_in_entry_gates():
    """Verify entry gates log causal chain when valuation MoS causes conviction failure."""
    gate_res = evaluate_entry_gates(
        symbol="STB",
        current_price=67.3,
        fin_dict={"bvps": 33267.0, "roe": 4.99},
        tech_data={"current_price": 67.3, "adv20_billion": 50.0},
        sector="Ngân hàng",
        archetype="BANK",
        conviction_score=20.0,
    )
    assert GATE_VALUATION_MOS in gate_res.failed_gates
    assert GATE_QUANT_CONVICTION in gate_res.failed_gates
    assert "VALUATION_MOS -> QUANT_CONVICTION" in gate_res.causal_chains
