# -*- coding: utf-8 -*-
"""Unit tests for Bank Direct BVPS Valuation and Archetype Synchronization across Entry Gates.

Covers:
- Bank valuation using BVPS directly (breaking price-to-FV circular dependency).
- Dynamic MoS responsiveness to price changes in bank archetype.
- Financial health layer archetype exemption (BANK and REAL_ESTATE exempt from industrial Z-score).
- Compounder EPS unit normalization and Shadow Mode for non-benchmark compounders.
- Automatic sector resolution in run_pipeline via SECTOR_MAP.
"""

from entry_gates import (
    GATE_FINANCIAL_HEALTH,
    EntryGateResult,
    _check_financial_health_layer,
    evaluate_entry_gates,
)
from quant_engine import run_pipeline
from quant_valuation import (
    VAL_RATING_EXPENSIVE,
    VAL_RATING_MANUAL_VERIFY,
    calculate_fair_value_and_mos,
    evaluate_compounder_valuation,
)


def test_bank_valuation_uses_direct_bvps_and_breaks_circular_loop():
    """Verify bank fair value is anchored to fundamental BVPS and does not move with price."""
    fin_data = {
        "bvps": 17796.69,  # ACB: 17.80 kVND
        "roe": 16.33,
    }

    # At price = 25.4
    val_p1 = calculate_fair_value_and_mos("ACB", current_price=25.4, fin_dict=fin_data, sector="Ngân hàng")
    assert val_p1["archetype"] == "BANK"
    assert val_p1["mos_is_informative"] is True
    assert val_p1["fair_value"] > 25.0

    # If price drops 50% to 12.7, Fair Value MUST stay constant, and MoS MUST increase
    val_p2 = calculate_fair_value_and_mos("ACB", current_price=12.7, fin_dict=fin_data, sector="Ngân hàng")
    assert val_p2["fair_value"] == val_p1["fair_value"], "FV must not collapse when market price drops"
    assert val_p2["mos_pct"] > val_p1["mos_pct"], "MoS must increase when stock becomes cheaper"


def test_bank_valuation_rejects_when_bvps_missing():
    """Verify bank valuation fails closed without BVPS instead of faking BVPS from price."""
    fin_no_bvps = {
        "pb": 1.2,
        "roe": 18.0,
    }
    val = calculate_fair_value_and_mos("ACB", current_price=25.0, fin_dict=fin_no_bvps, sector="Ngân hàng")
    assert val["mos_is_informative"] is False
    assert val["fair_value"] == 0.0


def test_financial_health_layer_archetype_exemption_when_sector_empty():
    """Verify banks and real estate pass financial health layer even if sector is empty."""
    res_bank = EntryGateResult(can_buy=True)
    fin_bank = {"z_score": 0.5, "f_score": 6}  # Z-score 0.5 would fail industrial threshold (1.8)

    # Calling with empty sector but archetype='BANK'
    passed_bank = _check_financial_health_layer(
        fin_dict=fin_bank, sector="", result=res_bank, archetype="BANK"
    )
    assert passed_bank is True
    assert GATE_FINANCIAL_HEALTH in res_bank.passed_gates

    # Industrial company with empty sector and Z-score 0.5 must fail
    res_ind = EntryGateResult(can_buy=True)
    passed_ind = _check_financial_health_layer(
        fin_dict=fin_bank, sector="", result=res_ind, archetype="GROWTH_COMPOUNDER"
    )
    assert passed_ind is False
    assert res_ind.blocked_by == GATE_FINANCIAL_HEALTH
    assert GATE_FINANCIAL_HEALTH in res_ind.failed_gates


def test_evaluate_entry_gates_resolves_archetype_and_exempts_bank():
    """Verify evaluate_entry_gates automatically classifies CTG as BANK and exempts from Z-score."""
    fin_ctg = {"z_score": 0.8, "f_score": 7, "pb": 1.61, "bvps": 31635.24, "roe": 21.05}
    gate_res = evaluate_entry_gates(
        symbol="CTG",
        current_price=29.5,
        fin_dict=fin_ctg,
        sector="",  # Sector left empty intentionally
        tech_data={"adv20_billion": 50.0, "current_price": 29.5},
    )
    # CTG must NOT be blocked by FINANCIAL_HEALTH
    assert gate_res.blocked_by != GATE_FINANCIAL_HEALTH


def test_compounder_eps_unit_normalization_and_shadow_mode():
    """Verify EPS > 500 is normalized to kVND and non-benchmarks are tagged SHADOW."""
    fin_generic = {"eps": 4500.0, "roe": 15.0}  # 4500 VND/cp
    comp_eval = evaluate_compounder_valuation("GENERIC_GROWTH", current_price=50.0, fin_dict=fin_generic)
    assert comp_eval["input_source"] == "BCTC_DYNAMIC_SHADOW"
    assert comp_eval["is_informative"] is False
    assert comp_eval["fv_base"] > 0.0  # Computed in shadow mode without corrupting gating

    # Benchmark symbol FPT must be BCTC_DYNAMIC and informative
    fpt_eval = evaluate_compounder_valuation("FPT", current_price=110.0, fin_dict={"eps": 5988.0, "roe": 25.0})
    assert fpt_eval["input_source"] == "BCTC_DYNAMIC"
    assert fpt_eval["is_informative"] is True


def test_run_pipeline_auto_resolves_sector_from_sector_map():
    """Verify run_pipeline auto-resolves sector and tracks failed_gates and price_source."""
    tech_mock = {
        "current_price": 29.5,
        "adv20_billion": 30.0,
        "ma20": 29.0,
        "rsi": 52.0,
        "vol_ratio": 1.1,
        "price_source": "REALTIME",
    }
    fin_mock = {"bvps": 31635.24, "pb": 1.61, "roe": 21.05}
    res = run_pipeline("CTG", current_price=29.5, fin_dict=fin_mock, tech_data=tech_mock)
    assert res["symbol"] == "CTG"
    assert res["archetype"] == "BANK"
    assert res["price_source"] == "REALTIME"
    assert isinstance(res.get("failed_gates"), list)


def test_universal_price_invariance_across_all_archetypes():
    """Universal test: keeping fundamentals constant and halving price (P * 0.5) must NOT change FV."""
    archetype_test_cases = [
        {
            "symbol": "ACB",
            "sector": "Ngân hàng",
            "price": 20.15,
            "fin": {"bvps": 17796.69, "roe": 16.33, "pb": 1.43},
        },
        {
            "symbol": "GVR",
            "sector": "Hóa chất",
            "price": 32.85,
            "fin": {"eps": 1614.75, "pe": 17.15, "pb": 1.73},
        },
        {
            "symbol": "DIG",
            "sector": "Bất động sản",
            "price": 9.40,
            "fin": {"bvps": 10839.26, "roe": 8.0, "pb": 1.15},
        },
        {
            "symbol": "FPT",
            "sector": "Công nghệ",
            "price": 57.90,
            "fin": {"eps": 5988.42, "roe": 25.0, "historical_median_pe": 19.0},
        },
    ]

    for tc in archetype_test_cases:
        p1 = tc["price"]
        p2 = p1 * 0.5

        val1 = calculate_fair_value_and_mos(tc["symbol"], current_price=p1, fin_dict=tc["fin"], sector=tc["sector"])
        val2 = calculate_fair_value_and_mos(tc["symbol"], current_price=p2, fin_dict=tc["fin"], sector=tc["sector"])

        fv1 = val1["fair_value"]
        fv2 = val2["fair_value"]
        assert fv1 > 0.0, f"{tc['symbol']} FV should be positive"
        assert fv1 == fv2, f"{tc['symbol']} FV changed with price: {fv1} vs {fv2} (Price loop detected!)"

        if val1["mos_pct"] is not None and val2["mos_pct"] is not None:
            assert val2["mos_pct"] > val1["mos_pct"], (
                f"{tc['symbol']} MoS must increase when price halves: {val1['mos_pct']} -> {val2['mos_pct']}"
            )


def test_stb_roe_anomaly_override_and_justified_pb_floor():
    """Verify STB API ROE anomaly (40.41%) is overridden to BCTC ROE (4.99%), hitting target P/B floor 0.90."""
    stb_fin = {
        "roe": 40.41,  # Distorted API ROE
        "pb": 1.71,
        "bvps": 33261.34,
    }
    val = calculate_fair_value_and_mos("STB", current_price=67.3, fin_dict=stb_fin, sector="Ngân hàng")
    assert val["archetype"] == "BANK"
    # Target P/B must hit floor 0.90, so FV ~ 33.26 * 0.90 = 29.93k
    assert 29.8 <= val["fair_value"] <= 30.1
    # MoS must be strongly negative (-124% to -126%), completely rejecting buy recommendations
    assert val["mos_pct"] < -100.0
    assert val["valuation_rating"] == VAL_RATING_EXPENSIVE


def test_ctg_pb_discrepancy_triggers_data_reconcile_hard_gate():
    """Verify CTG P/B discrepancy (>30%) turns off mos_is_informative and drops confidence to LOW."""
    ctg_fin = {
        "roe": 21.05,
        "pb": 1.61,  # API P/B
        "bvps": 31635.24,  # BCTC BVPS ~ 31.64k -> at price 29.5, calc_pb = 29.5 / 31.64 = 0.93 -> discrepancy 42.2% > 30%
    }
    val = calculate_fair_value_and_mos("CTG", current_price=29.5, fin_dict=ctg_fin, sector="Ngân hàng")
    assert val["mos_is_informative"] is False
    assert val["confidence"] == "LOW"
    assert val["mos_pct"] is None
    assert val["valuation_rating"] == VAL_RATING_MANUAL_VERIFY


def test_all_layers_accumulate_in_failed_gates():
    """Verify evaluate_entry_gates collects all failing gates across layers without early termination."""
    from entry_gates import GATE_FINANCIAL_HEALTH, GATE_QUANT_CONVICTION, GATE_VALUATION_MOS

    # Stock failing FINANCIAL_HEALTH, VALUATION_MOS, and QUANT_CONVICTION
    res = evaluate_entry_gates(
        symbol="SSI",
        current_price=19.0,
        fin_dict={},
        tech_data={"adv20_billion": 50.0, "current_price": 19.0},
        sector="Dịch vụ tài chính",
        archetype="UNCLASSIFIED",
        conviction_score=20.0,
    )
    assert res.can_buy is False
    assert GATE_FINANCIAL_HEALTH in res.failed_gates
    assert GATE_VALUATION_MOS in res.failed_gates
    assert GATE_QUANT_CONVICTION in res.failed_gates
    assert res.blocked_by == GATE_FINANCIAL_HEALTH
