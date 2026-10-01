"""Unit tests for Phase 10: Real Estate & Holding Company Valuation Overhaul (TASK-0024 -> 0028).

Covers:
- TASK-0024: SOTP Sanity Check for Holding Companies / Conglomerates
- TASK-0025: Quality of Earnings Gate (Core Earnings Ratio)
- TASK-0026: Survival Gate (Normalized EBITDA, Debt Overload, Refinancing Risk, Interest Coverage)
- TASK-0027: Cash Cow vs Cash Burner Prompt Injection
- TASK-0028: P/B Mean Reversion Guardrail for REAL_ESTATE
"""


from ai_analyst import _format_committee_prompt_context
from data_engine import (
    calculate_core_earnings_ratio,
    calculate_normalized_ebitda,
    get_holding_subsidiary_structure,
)
from data_gate import (
    GATE_DEBT_OVERLOAD,
    GATE_INTEREST_COVERAGE_CRITICAL,
    GATE_REFINANCING_RISK,
    reconcile_data,
    reconcile_real_estate_survival_gate,
)
from quant_valuation import (
    VAL_RATING_ATTRACTIVE,
    VAL_RATING_EXPENSIVE,
    VAL_RATING_FAIR_VALUE,
    VAL_RATING_VERY_CHEAP,
    calculate_fair_value_and_mos,
    check_real_estate_pb_guardrail,
    check_sotp_holding_sanity,
    evaluate_real_estate_valuation,
)

# =============================================================================
# TASK-0024: SOTP SANITY CHECK TESTS
# =============================================================================

class TestSOTPHoldingSanity:
    """Validate SOTP calculations and holding anomaly flags."""

    def test_get_holding_structure_known_holding(self):
        vic_info = get_holding_subsidiary_structure("VIC")
        assert vic_info["is_holding"] is True
        assert len(vic_info["listed_subsidiaries"]) >= 2
        assert "VHM" in [s["symbol"] for s in vic_info["listed_subsidiaries"]]
        assert "VinFast" in vic_info["unlisted_segments"]

    def test_get_holding_structure_non_holding(self):
        fpt_info = get_holding_subsidiary_structure("FPT")
        assert fpt_info["is_holding"] is False
        assert fpt_info["listed_subsidiaries"] == []

    def test_sotp_sanity_normal_ratio(self):
        # Parent market cap 150k bil, subsidiary value ~120k bil -> ratio ~80%
        res = check_sotp_holding_sanity("VIC", parent_market_cap=150000.0)
        assert res["is_holding"] is True
        assert res["sotp_ratio"] is not None
        assert res["has_critical_block"] is False

    def test_sotp_sanity_anomaly_between_30_and_50(self):
        # High parent market cap (e.g. 300k bil) drops ratio to ~40%
        res = check_sotp_holding_sanity("VIC", parent_market_cap=300000.0)
        assert res["is_holding"] is True
        assert "SOTP_ANOMALY" in res["flags"]
        assert res["fv_discount"] >= 0.10

    def test_sotp_sanity_critical_under_30(self):
        # Speculative fever parent market cap 450k bil drops ratio below 30%
        res = check_sotp_holding_sanity("VIC", parent_market_cap=450000.0)
        assert res["is_holding"] is True
        assert res["has_critical_block"] is True
        assert "SOTP_DISCOUNT_CRITICAL" in res["flags"]
        assert res["fv_discount"] >= 0.20


# =============================================================================
# TASK-0025: QUALITY OF EARNINGS GATE TESTS
# =============================================================================

class TestQualityOfEarningsGate:
    """Validate Core Earnings Ratio and Earnings Quality Tiers."""

    def test_high_quality_earnings(self):
        # Gross profit 100, SG&A 25 -> Core 75; PBT 100 -> ratio 75%
        res = calculate_core_earnings_ratio(gross_profit=100.0, sga_expense=25.0, pbt=100.0)
        assert res["quality_tier"] == "EARNINGS_QUALITY_HIGH"
        assert res["core_earnings_ratio"] == 0.75
        assert res["fv_discount"] == 0.0
        assert res["confidence"] == "HIGH"

    def test_medium_quality_earnings(self):
        # Gross profit 80, SG&A 30 -> Core 50; PBT 100 -> ratio 50%
        res = calculate_core_earnings_ratio(gross_profit=80.0, sga_expense=30.0, pbt=100.0)
        assert res["quality_tier"] == "EARNINGS_QUALITY_MEDIUM"
        assert res["core_earnings_ratio"] == 0.50
        assert res["fv_discount"] == 0.0
        assert res["confidence"] == "MEDIUM"

    def test_low_quality_earnings_one_off_sales(self):
        # Gross profit 50, SG&A 35 -> Core 15; PBT 100 (85 from asset sale) -> ratio 15%
        res = calculate_core_earnings_ratio(gross_profit=50.0, sga_expense=35.0, pbt=100.0)
        assert res["quality_tier"] == "EARNINGS_QUALITY_LOW"
        assert res["core_earnings_ratio"] == 0.15
        assert res["fv_discount"] == 0.15
        assert res["confidence"] == "LOW"

    def test_negative_pbt_triggers_low_and_penalty(self):
        res = calculate_core_earnings_ratio(gross_profit=50.0, sga_expense=20.0, pbt=-10.0)
        assert res["quality_tier"] == "EARNINGS_QUALITY_LOW"
        assert res["warning"] == "EARNINGS_QUALITY_NEGATIVE_PBT"
        assert res["fv_discount"] == 0.20
        assert res["confidence"] == "LOW"

    def test_missing_data_graceful_fallback(self):
        res = calculate_core_earnings_ratio(gross_profit=None, sga_expense=None, pbt=None)
        assert res["core_earnings_ratio"] is None
        assert res["fv_discount"] == 0.0


# =============================================================================
# TASK-0026: SURVIVAL GATE & NORMALIZED EBITDA TESTS
# =============================================================================

class TestSurvivalGate:
    """Validate Normalized EBITDA and Real Estate Survival Gate checks."""

    def test_calculate_normalized_ebitda(self):
        # Reported 100, abnormal fin income 40, asset sale 20 -> normalized 40
        norm = calculate_normalized_ebitda(
            reported_ebitda=100.0,
            abnormal_fin_income=40.0,
            other_profit=20.0
        )
        assert norm == 40.0

    def test_gate1_debt_overload_blocks_buy(self):
        fin_data = {
            "normalized_ebitda": 20.0,
            "net_debt": 140.0,  # 7.0x > 5.0x
        }
        res = reconcile_real_estate_survival_gate("VIC", fin_data=fin_data, sector="Bất động sản")
        assert res["survival_passed"] is False
        assert res["has_critical_block"] is True
        assert any(GATE_DEBT_OVERLOAD in issue for issue in res["issues"])

    def test_gate2_refinancing_risk_discounts_fv(self):
        fin_data = {
            "short_term_debt": 50.0,
            "total_debt": 100.0,  # 50% > 40%
        }
        res = reconcile_real_estate_survival_gate("VHM", fin_data=fin_data, sector="Bất động sản")
        assert res["applied_discounts"] >= 0.10
        assert any(GATE_REFINANCING_RISK in w for w in res["warnings"])

    def test_gate3_interest_coverage_critical_blocks_buy(self):
        fin_data = {
            "normalized_ebitda": 10.0,
            "interest_expense": 10.0,  # 1.0x < 1.5x
        }
        res = reconcile_real_estate_survival_gate("NVL", fin_data=fin_data, sector="Bất động sản")
        assert res["survival_passed"] is False
        assert res["has_critical_block"] is True
        assert any(GATE_INTEREST_COVERAGE_CRITICAL in issue for issue in res["issues"])

    def test_survival_gate_integration_in_reconcile_data(self):
        gate_res = reconcile_data(
            symbol="VIC",
            tech_data={"current_price": 45.0, "sector": "Bất động sản"},
            fin_data={
                "normalized_ebitda": 10.0,
                "net_debt": 80.0,  # 8x > 5x
                "period": "2026-Q2"
            }
        )
        assert gate_res["recommendation_allowed"] is False
        assert any(GATE_DEBT_OVERLOAD in c for c in gate_res["conflicting_data"])


# =============================================================================
# TASK-0028: P/B MEAN REVERSION GUARDRAIL FOR REAL ESTATE
# =============================================================================

class TestRealEstatePBGuardrail:
    """Validate P/B Guardrail on Real Estate stocks."""

    def test_pb_normal_range(self):
        res = check_real_estate_pb_guardrail("VHM", current_pb=1.4)
        assert res["guardrail_triggered"] is False
        assert res["level"] == "NORMAL"
        assert res["cap_rating"] is False

    def test_pb_elevated_premium_between_2_and_3_sigma(self):
        # Real Estate mean 1.5, std 0.8 -> 2σ = 3.1, 3σ = 3.9. PB = 3.5
        res = check_real_estate_pb_guardrail("KDH", current_pb=3.5)
        assert res["guardrail_triggered"] is True
        assert res["level"] == "ELEVATED_PREMIUM"
        assert res["warning"] == "PB_ELEVATED_PREMIUM"
        assert res["fv_discount"] == 0.10
        assert res["cap_rating"] is False

    def test_pb_extreme_premium_above_3_sigma(self):
        # VIC mean 2.5, std 1.2 -> 3σ = 6.1. TCBS reported PB = 10.5
        res = check_real_estate_pb_guardrail("VIC", current_pb=10.5)
        assert res["guardrail_triggered"] is True
        assert res["level"] == "EXTREME_PREMIUM"
        assert res["warning"] == "PB_EXTREME_PREMIUM"
        assert res["cap_rating"] is True
        assert res["fv_discount"] == 0.15


# =============================================================================
# E2E VALUATION & TCBS VIC CASE RECONCILIATION
# =============================================================================

class TestRealEstateValuationE2E:
    """End-to-End tests verifying Real Estate valuation improvements."""

    def test_evaluate_real_estate_valuation_structure(self):
        res = evaluate_real_estate_valuation(
            symbol="VHM",
            current_price=42.0,
            fin_dict={"pb": 1.2, "bvps": 35.0, "roe": 15.0, "debt_equity": 0.8},
            sector="Bất động sản"
        )
        assert "fv_base" in res
        assert "sotp_check" in res
        assert "earnings_quality" in res
        assert "survival_gate" in res
        assert "pb_guardrail" in res
        assert res["fv_base"] > 0

    def test_vic_tcbs_anomaly_blocks_attractive_rating(self):
        """TCBS report case for VIC: PB=10.5x, low core earnings, debt overload."""
        val = calculate_fair_value_and_mos(
            symbol="VIC",
            current_price=45.0,
            fin_dict={
                "pb": 10.5,
                "bvps": 20.0,
                "roe": 5.0,
                "debt_equity": 2.5,
                "gross_profit": 30.0,
                "sga_expense": 25.0,
                "pbt": 100.0,  # 85% asset sales -> core ratio 5%
                "normalized_ebitda": 15.0,
                "net_debt": 120.0,  # 8.0x
                "sotp_ratio": 0.28,  # < 30%
            },
            sector="Bất động sản"
        )

        # 1. MoS must be informative (not naive current_price * 1.15)
        assert val["mos_is_informative"] is True

        # 2. Must trigger warning flags
        assert val["pb_guardrail"]["guardrail_triggered"] is True
        assert val["pb_guardrail"]["warning"] == "PB_EXTREME_PREMIUM"
        assert val["earnings_quality"]["quality_tier"] == "EARNINGS_QUALITY_LOW"
        assert val["survival_gate"]["has_critical_block"] is True

        # 3. Rating MUST NOT be ATTRACTIVE or VERY CHEAP despite model calculation
        assert val["valuation_rating"] in (VAL_RATING_FAIR_VALUE, VAL_RATING_EXPENSIVE)
        assert val["valuation_rating"] not in (VAL_RATING_ATTRACTIVE, VAL_RATING_VERY_CHEAP)
        assert val["confidence"] == "LOW"


# =============================================================================
# TASK-0027: CASH COW VS CASH BURNER PROMPT TESTS
# =============================================================================

class TestPromptEngineeringHolding:
    """Validate prompt context generation for holding company analysis."""

    def test_prompt_includes_holding_and_cash_burner_requirements(self):
        val_res = calculate_fair_value_and_mos(
            symbol="VIC",
            current_price=45.0,
            fin_dict={"pb": 10.5, "bvps": 20.0, "sotp_ratio": 0.35},
            sector="Bất động sản"
        )
        gate_res = {"data_quality": "HIGH", "quality_score": 90.0}
        prompt = _format_committee_prompt_context(
            sym="VIC",
            tech_data={"current_price": 45.0, "ma20": 44.0, "ma50": 43.0, "rsi14": 55.0, "vol_ratio": 1.2},
            gate_res=gate_res,
            val_res=val_res,
            f_score_res={"score": 5, "rating": "Ổn"},
            z_score_res={"z_score": 1.8, "zone": "GREY"},
            news_items=[{"title": "VIC ra mắt sản phẩm mới"}]
        )

        assert "Cấu trúc SOTP Vốn hóa niêm yết" in prompt
        assert "Cash Cow" in prompt
        assert "Cash Burner" in prompt
        assert "Cross-Subsidy" in prompt
