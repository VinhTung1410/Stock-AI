# -*- coding: utf-8 -*-
"""Unit tests for TASK-0029 -> TASK-0032: Cyclical Valuation Overhaul.

Covers:
- Peak Earnings Trap Detection (P/E < 6.5x + gross margin collapsing >= 2 quarters)
- Normalized Mid-Cycle EPS (5-year trimmed mean)
- Regional Peer Comparison Benchmark (P/B vs. Asian peer medians)
- Sector-Specific Risk Flags (Oil & Gas DSI > 45d, policy expiring, steel dumping)
- Overhauled CYCLICAL fair value branch in calculate_fair_value_and_mos
"""

from data_engine import calculate_trimmed_normalized_eps
from data_gate import (
    FLAG_CHINA_DUMPING_RISK,
    FLAG_INVENTORY_BUILDUP,
    FLAG_INVENTORY_RISK,
    FLAG_MARGIN_TREND_DOWN,
    FLAG_PEAK_EARNINGS_TRAP,
    FLAG_POLICY_EXPIRING,
    FLAG_SINGLE_PLANT_RISK,
    check_sector_risk_flags,
    reconcile_data,
)
from quant_valuation import (
    FLAG_PEER_PREMIUM_EXTREME,
    FLAG_PEER_PREMIUM_WARNING,
    VAL_RATING_EXPENSIVE,
    calculate_fair_value_and_mos,
    check_cyclical_peer_benchmark,
    check_peak_earnings_trap,
    evaluate_cyclical_valuation,
)


# ==============================================================================
# TASK-0030: Normalized EPS Tests
# ==============================================================================
def test_trimmed_normalized_eps_standard_5_years():
    """Test 5-year series: drops min and max, averages remaining 3 years."""
    # 5 years: [1000, 2000, 3000, 4000, 10000] (peak 10000 dropped, min 1000 dropped)
    # Remaining: 2000, 3000, 4000 -> Mean = 3000.0
    history = [1000.0, 2000.0, 3000.0, 4000.0, 10000.0]
    res = calculate_trimmed_normalized_eps(history)

    assert res["normalized_eps"] == 3000.0
    assert res["is_normalized"] is True
    assert res["min_removed"] == 1000.0
    assert res["max_removed"] == 10000.0


def test_trimmed_normalized_eps_insufficient_history_fallback():
    """Test when history has < 3 points: simple average without trimming."""
    history = [2000.0, 4000.0]
    res = calculate_trimmed_normalized_eps(history)

    assert res["normalized_eps"] == 3000.0
    assert res["is_normalized"] is False
    assert res["sample_size"] == 2


def test_trimmed_normalized_eps_empty_or_none():
    """Test empty or None history."""
    assert calculate_trimmed_normalized_eps([])["normalized_eps"] is None
    assert calculate_trimmed_normalized_eps(None)["normalized_eps"] is None


# ==============================================================================
# TASK-0029: Peak Earnings Trap Tests
# ==============================================================================
def test_peak_earnings_trap_triggered():
    """Test classic trap: P/E < 6.5x and margins drop >= 2 consecutive quarters."""
    res = check_peak_earnings_trap(
        symbol="BSR",
        pe=5.8,
        gross_margin_trend="DOWN",
        margin_quarters_down=2,
    )
    assert res["is_peak_trap"] is True
    assert res["warning"] == FLAG_PEAK_EARNINGS_TRAP
    assert res["fv_discount"] == 0.20
    assert res["cap_rating"] is True
    assert res["recommendation_allowed"] is False


def test_peak_earnings_trap_not_triggered_healthy_margin():
    """Test low P/E but margin expanding -> NOT a trap."""
    res = check_peak_earnings_trap(
        symbol="BSR",
        pe=5.5,
        gross_margin_trend="UP",
        margin_quarters_down=0,
    )
    assert res["is_peak_trap"] is False
    assert res["warning"] is None
    assert res["fv_discount"] == 0.0


def test_peak_earnings_trap_not_triggered_high_pe():
    """Test margin dropping but P/E already high (> 6.5x) -> not the classic cheap trap."""
    res = check_peak_earnings_trap(
        symbol="BSR",
        pe=12.0,
        gross_margin_trend="DOWN",
        margin_quarters_down=3,
    )
    assert res["is_peak_trap"] is False


# ==============================================================================
# TASK-0031: Regional Peer Comparison Benchmark Tests
# ==============================================================================
def test_cyclical_peer_benchmark_premium_over_2x():
    """Test BSR case: P/B = 2.1x vs Asian refinery median 1.0x (ratio > 2.0x)."""
    res = check_cyclical_peer_benchmark("BSR", current_pb=2.1, current_pe=5.8, sector="Dầu khí")

    assert res["benchmark_key"] == "OIL_REFINING"
    assert res["cap_rating"] is True
    assert res["fv_discount"] == 0.15
    assert res["warning"] == FLAG_PEER_PREMIUM_EXTREME


def test_cyclical_peer_benchmark_moderate_premium():
    """Test steel case: P/B = 1.35x vs median 0.85x (ratio ~ 1.59x > 1.5x, <= 2.0x)."""
    res = check_cyclical_peer_benchmark("HPG", current_pb=1.35, current_pe=10.0, sector="Thép")

    assert res["benchmark_key"] == "STEEL"
    assert res["cap_rating"] is False
    assert res["fv_discount"] == 0.10
    assert res["warning"] == FLAG_PEER_PREMIUM_WARNING


def test_cyclical_peer_benchmark_fair_or_discount():
    """Test chemicals at fair value vs median (P/B = 1.0x vs median 1.1x)."""
    res = check_cyclical_peer_benchmark("DGC", current_pb=1.0, current_pe=9.0, sector="Hóa chất")

    assert res["cap_rating"] is False
    assert res["fv_discount"] == 0.0
    assert res["warning"] is None


# ==============================================================================
# TASK-0032: Sector-Specific Risk Flags Tests
# ==============================================================================
def test_sector_risk_flags_oil_gas_bsr_scenario():
    """Test Oil & Gas flags for high DSI, declining margin, and single plant."""
    fin_data = {
        "dsi": 52.0,  # > 45 days
        "single_plant_risk": True,
        "policy_expiring": True,
        "gross_margin_trend": "DOWN",
        "margin_quarters_down": 2,
    }
    res = check_sector_risk_flags("BSR", fin_data=fin_data, sector="Dầu khí")

    assert res["is_cyclical"] is True
    assert FLAG_INVENTORY_RISK in res["risk_flags"]
    assert FLAG_MARGIN_TREND_DOWN in res["risk_flags"]
    assert FLAG_POLICY_EXPIRING in res["risk_flags"]
    assert FLAG_SINGLE_PLANT_RISK in res["risk_flags"]
    assert res["fv_discount"] >= 0.20


def test_sector_risk_flags_steel_scenario():
    """Test Steel flags for China dumping and inventory buildup."""
    fin_data = {
        "china_dumping_risk": True,
        "inventory_buildup": True,
    }
    res = check_sector_risk_flags("HPG", fin_data=fin_data, sector="Thép")

    assert res["is_cyclical"] is True
    assert FLAG_CHINA_DUMPING_RISK in res["risk_flags"]
    assert FLAG_INVENTORY_BUILDUP in res["risk_flags"]


def test_data_gate_reconcile_with_cyclical_flags():
    """Test Data Gate integration: Cyclical risk flags recorded in sector_risks."""
    tech_data = {"close": 28.0, "reference": 28.0, "exchange": "HOSE"}
    fin_data = {
        "pe": 5.8,
        "dsi": 52.0,
        "gross_margin_trend": "DOWN",
        "margin_quarters_down": 2,
        "sector": "Dầu khí",
    }

    reconciled = reconcile_data(
        symbol="BSR",
        tech_data=tech_data,
        fin_data=fin_data,
    )

    assert reconciled["symbol"] == "BSR"
    assert reconciled["sector_risks"]["is_cyclical"] is True
    assert FLAG_INVENTORY_RISK in reconciled["sector_risks"]["risk_flags"]
    assert FLAG_MARGIN_TREND_DOWN in reconciled["sector_risks"]["risk_flags"]


# ==============================================================================
# End-to-End Cyclical Valuation Engine Tests
# ==============================================================================
def test_evaluate_cyclical_valuation_peak_trap():
    """Test evaluate_cyclical_valuation directly with peak trap and peer premium."""
    fin_dict = {
        "pe": 5.8,
        "pb": 2.1,
        "gross_margin_trend": "DOWN",
        "margin_quarters_down": 2,
        "dsi": 50.0,
        "single_plant_risk": True,
        "policy_expiring": True,
        "eps_history": [1200.0, 2500.0, 3200.0, 4100.0, 9500.0],
    }
    current_price = 28000.0

    eval_res = evaluate_cyclical_valuation(
        symbol="BSR",
        current_price=current_price,
        fin_dict=fin_dict,
        sector="Dầu khí",
    )

    assert eval_res["peak_earnings_trap"]["is_peak_trap"] is True
    assert eval_res["peer_benchmark"]["cap_rating"] is True
    assert eval_res["confidence"] == "LOW"
    assert eval_res["recommendation_allowed"] is False
    assert eval_res["normalized_eps"] == 3266.67
    assert eval_res["fv_base"] < current_price


def test_calculate_fair_value_and_mos_cyclical_archetype():
    """Test full integration in calculate_fair_value_and_mos for CYCLICAL archetype."""
    fin_dict = {
        "pe": 6.0,
        "pb": 2.1,
        "gross_margin_trend": "DOWN",
        "margin_quarters_down": 2,
        "sector": "Dầu khí",
        "eps_history": [1000.0, 2000.0, 3000.0, 4000.0, 9000.0],
    }
    current_price = 27300.0

    result = calculate_fair_value_and_mos(
        symbol="BSR",
        current_price=current_price,
        fin_dict=fin_dict,
        sector="Dầu khí",
    )

    assert result["archetype"] == "CYCLICAL"
    assert result["valuation_rating"] == VAL_RATING_EXPENSIVE
    assert result["confidence"] == "LOW"
    assert result["peak_earnings_trap"]["is_peak_trap"] is True
    assert result["peer_benchmark"]["cap_rating"] is True
    assert result["normalized_eps"] == 3000.0
    assert result["mos_pct"] < 0
