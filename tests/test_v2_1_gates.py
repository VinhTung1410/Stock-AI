"""
Unit tests for Release v2.1 Operational Gates:
- Gap #1: Freshness Gate & Cross-Validation Gate (data_gate.py)
- Gap #4: Half-Kelly Position Sizing (quant_engine.py)
- Gap #6: ADV20 Liquidity 3-Tier Thresholds (quant_engine.py)
- Gap #5: Portfolio Sector Concentration Guardrail (quant_engine.py)
- Gap #2: Deterministic PM Arbitration Rules & Thesis Breaker Integration (ai_analyst.py)
"""

from datetime import datetime, timedelta

import pytest

from ai_analyst import (
    STATE_AVOID,
    STATE_INSUFFICIENT_DATA,
    STATE_RISK_ELEVATED,
    STATE_STRONG_OPPORTUNITY,
    STATE_WAIT_BETTER_ENTRY,
    STATE_WATCHLIST,
    _extract_views,
    arbitrate_pm_decision,
)
from data_gate import (
    BADGE_STALE_LOCKED,
    reconcile_data,
    reconcile_market_cap_consistency,
    reconcile_price_freshness,
)
from quant_engine import (
    check_portfolio_concentration,
    evaluate_decision_hard_gates,
)


def _eval_helper(current_price: float, price_base: float, adv20: float, tech_data: dict = None) -> dict:
    return evaluate_decision_hard_gates(
        current_price=current_price,
        p_bull=0.3,
        p_base=0.5,
        p_bear=0.2,
        price_bull=price_base * 1.2,
        price_base=price_base,
        price_bear=current_price * 0.9,
        atr=1.5,
        adv20_billion=adv20,
        tech_data=tech_data or {"current_price": current_price, "ma20": current_price * 0.98, "rsi": 55.0}
    )


@pytest.mark.offline
class TestFreshnessAndCrossValidationGate:
    """Test suite for Gap #1 Freshness & Cross-Validation Gate."""

    def test_stale_financial_statements_locks_recommendation(self):
        """BCTC older than 2 quarters must lock recommendation_allowed to False."""
        tech = {"current_price": 58.8, "close": 58.8, "ref_price": 58.5}
        fin = {
            "roe": 16.7,
            "f_score": 7,
            "z_score": 2.5,
            "pe": 14.0,
            "pb": 1.6,
            "latest_quarter": 4,
            "latest_year": 2018  # 30 quarters old (VCB incident scenario)
        }
        res = reconcile_data(symbol="VCB", tech_data=tech, fin_data=fin)

        assert res["is_stale"] is True
        assert res["gate_passed"] is False
        assert res["recommendation_allowed"] is False
        assert BADGE_STALE_LOCKED in res["badge"]
        assert any("Financial Statements" in s for s in res["stale_data"])

    def test_stale_market_price_timestamp_flagged(self):
        """Price data older than 7 calendar days (~5 trading days) is flagged as stale."""
        old_date = (datetime.now() - timedelta(days=12)).strftime("%Y-%m-%d")
        tech = {"current_price": 33.15, "close": 33.15, "as_of_date": old_date}
        issues = reconcile_price_freshness(tech)
        assert len(issues) >= 1
        assert "Market Price Stale" in issues[0]

        res = reconcile_data(symbol="TCB", tech_data=tech)
        assert res["is_stale"] is True
        assert res["recommendation_allowed"] is False

    def test_fresh_market_price_passes(self):
        """Fresh price data within 2 days passes freshness audit."""
        recent_date = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        tech = {"current_price": 33.15, "close": 33.15, "as_of_date": recent_date}
        issues = reconcile_price_freshness(tech)
        assert len(issues) == 0

    def test_cross_validation_mismatch_catches_wrong_fields(self):
        """Implied price = market_cap / shares mismatch > 15% triggers conflict."""
        fin = {
            "market_cap_bil": 100000.0,
            "shares_outstanding": 1000000000.0
        }
        issues = reconcile_market_cap_consistency(reconciled_price=50.0, fin_data=fin)
        assert len(issues) >= 1
        assert "Cross-Validation Mismatch" in issues[0]

        res = reconcile_data(symbol="WRONG", tech_data={"current_price": 50.0}, fin_data=fin)
        assert res["gate_passed"] is False
        assert res["recommendation_allowed"] is False
        assert any("Cross-Validation Mismatch" in c for c in res["conflicting_data"])

    def test_cross_validation_clean_alignment(self):
        """Implied price matching market price within 15% passes without conflict."""
        fin = {
            "market_cap_bil": 492149.0,
            "shares_outstanding": 8355675094.0
        }
        issues = reconcile_market_cap_consistency(reconciled_price=58.8, fin_data=fin)
        assert len(issues) == 0


@pytest.mark.offline
class TestKellyAndLiquidityTiers:
    """Test suite for Gap #4 Half-Kelly & Gap #6 ADV20 Liquidity Tiers."""

    def test_half_kelly_calculation(self):
        """Half-Kelly should be exactly half of positive Kelly f*, or 0.0."""
        tech = {"current_price": 58.8, "ma20": 55.0, "rsi": 55.0}

        res = _eval_helper(current_price=58.8, price_base=75.0, adv20=25.0, tech_data=tech)
        assert "half_kelly_f" in res
        if res["kelly_f"] > 0:
            assert res["half_kelly_f"] == round(res["kelly_f"] * 0.5, 2)
        else:
            assert res["half_kelly_f"] == 0.0

    def test_adv20_below_2_bil_blocks_buy(self):
        """ADV20 < 2 bil strictly blocks position to 0% NAV."""
        res = _eval_helper(current_price=20.0, price_base=30.0, adv20=1.2)
        assert res["can_buy"] is False
        assert res["position_size_nav"] == "0% NAV"
        assert "Thanh khoản quá thấp" in res["decision_tag"]

    def test_adv20_moderate_2_to_10_bil_caps_position(self):
        """ADV20 between 2 and 10 bil caps allocation at 5-8% NAV to prevent slippage."""
        tech = {"current_price": 33.0, "ma20": 30.0, "rsi": 58.0}
        res = _eval_helper(current_price=33.0, price_base=45.0, adv20=6.5, tech_data=tech)
        assert res["can_buy"] is True
        assert res["position_size_nav"] == "5% - 8% NAV"
        assert "Cảnh báo trượt giá" in res["decision_tag"]

    def test_adv20_high_liquidity_tier_1_conviction(self):
        """ADV20 >= 10 bil qualifies for Tier 1 High Conviction 15-20% NAV."""
        tech = {"current_price": 33.0, "ma20": 30.0, "rsi": 58.0}
        res = _eval_helper(current_price=33.0, price_base=45.0, adv20=35.0, tech_data=tech)
        assert res["can_buy"] is True
        assert res["position_size_nav"] == "15% - 20% NAV"
        assert "VALUE BUY" in res["decision_tag"]


@pytest.mark.offline
class TestPortfolioSectorConcentration:
    """Test suite for Gap #5 Portfolio Sector Concentration Guardrail."""

    def test_dual_bank_concentration_retains_highest_conviction(self):
        """Recommending two banks in same session downgrades duplicate to Watchlist."""
        candidates = [
            {
                "symbol": "TCB",
                "sector": "NGÂN HÀNG",
                "mos_pct": 18.0,
                "risk_reward": 2.1,
                "f_score": 7,
                "action_state": "🟢 MUA",
                "position_size_nav": "15% - 20% NAV"
            },
            {
                "symbol": "VCB",
                "sector": "NGÂN HÀNG",
                "mos_pct": 22.0,
                "risk_reward": 2.5,
                "f_score": 8,
                "action_state": "🟢 MUA",
                "position_size_nav": "15% - 20% NAV"
            }
        ]

        result = check_portfolio_concentration(candidates, max_per_sector=1)
        assert len(result["approved_candidates"]) == 1
        assert len(result["downgraded_candidates"]) == 1
        assert len(result["warnings"]) == 1

        assert result["approved_candidates"][0]["symbol"] == "VCB"
        downgraded = result["downgraded_candidates"][0]
        assert downgraded["symbol"] == "TCB"
        assert downgraded["action_state"] == "🟡 THEO DÕI"
        assert "Cảnh báo tập trung danh mục" in downgraded["decision_tag"]

    def test_diverse_sectors_all_approved(self):
        """Candidates from different sectors are all approved."""
        candidates = [
            {"symbol": "VCB", "sector": "NGÂN HÀNG", "mos_pct": 20.0},
            {"symbol": "HPG", "sector": "THÉP", "mos_pct": 25.0},
            {"symbol": "VHM", "sector": "BẤT ĐỘNG SẢN", "mos_pct": 19.0}
        ]
        result = check_portfolio_concentration(candidates, max_per_sector=1)
        assert len(result["approved_candidates"]) == 3
        assert len(result["downgraded_candidates"]) == 0
        assert len(result["warnings"]) == 0


@pytest.mark.offline
class TestDeterministicPMArbitration:
    """Test suite for Gap #2 Deterministic PM Arbitration Rules."""

    def test_data_gate_rejected_forces_insufficient_data(self):
        """When recommendation is not allowed by Data Gate, arbitration forces INSUFFICIENT_DATA."""
        final, overridden, reason = arbitrate_pm_decision(
            raw_decision=STATE_STRONG_OPPORTUNITY,
            recommendation_allowed=False
        )
        assert final == STATE_INSUFFICIENT_DATA
        assert overridden is True
        assert "Data Gate" in reason

    def test_thesis_breaker_financial_distress_forces_avoid(self):
        """When F-Score < 4 or Z-Score Red Zone, arbitration forces AVOID."""
        final, overridden, reason = arbitrate_pm_decision(
            raw_decision=STATE_STRONG_OPPORTUNITY,
            f_score=3,
            z_zone="Vùng nguy hiểm phá sản"
        )
        assert final == STATE_AVOID
        assert overridden is True
        assert "Thesis Breaker" in reason

    def test_fa_bullish_ta_bearish_falling_knife_forces_wait_better_entry(self):
        """When FA Bullish but TA Bearish, arbitration blocks STRONG_OPPORTUNITY to WAIT_BETTER_ENTRY."""
        final, overridden, reason = arbitrate_pm_decision(
            raw_decision=STATE_STRONG_OPPORTUNITY,
            fa_view="BULLISH",
            ta_view="BEARISH"
        )
        assert final == STATE_WAIT_BETTER_ENTRY
        assert overridden is True
        assert "bắt dao rơi" in reason.lower()

    def test_fa_bearish_ta_bullish_fomo_forces_risk_elevated(self):
        """When FA Bearish but TA Bullish, arbitration blocks BUY decisions to RISK_ELEVATED."""
        final, overridden, reason = arbitrate_pm_decision(
            raw_decision=STATE_STRONG_OPPORTUNITY,
            fa_view="BEARISH",
            ta_view="BULLISH"
        )
        assert final == STATE_RISK_ELEVATED
        assert overridden is True
        assert "FOMO" in reason

    def test_red_team_downside_over_25_forces_watchlist(self):
        """When Red Team downside risk > 25%, arbitration caps decision at WATCHLIST."""
        final, overridden, reason = arbitrate_pm_decision(
            raw_decision=STATE_STRONG_OPPORTUNITY,
            fa_view="BULLISH",
            ta_view="BULLISH",
            red_team_downside=28.5
        )
        assert final == STATE_WATCHLIST
        assert overridden is True
        assert "Red Team" in reason

    def test_aligned_high_conviction_retains_strong_opportunity(self):
        """When all gates pass and views align, STRONG_OPPORTUNITY is preserved."""
        final, overridden, _ = arbitrate_pm_decision(
            raw_decision=STATE_STRONG_OPPORTUNITY,
            fa_view="BULLISH",
            ta_view="BULLISH",
            red_team_downside=12.0,
            f_score=8,
            z_zone="Vùng an toàn",
            recommendation_allowed=True
        )
        assert final == STATE_STRONG_OPPORTUNITY
        assert overridden is False

    def test_extract_views_from_report_text(self):
        """Helper correctly parses FA and TA views from formatted markdown text."""
        sample = """
        === BƯỚC 1: ĐÁNH GIÁ CƠ BẢN (FA VIEW) ===
        FA VIEW: BULLISH - Định giá rất hấp dẫn
        === BƯỚC 2: ĐÁNH GIÁ KỸ THUẬT (TA VIEW) ===
        TA VIEW: BEARISH - Nằm dưới MA20
        """
        views = _extract_views(sample)
        assert views["fa_view"] == "BULLISH"
        assert views["ta_view"] == "BEARISH"

    def test_invalid_decision_state_fallbacks_to_watchlist(self):
        """Invalid decision candidate falls back to WATCHLIST."""
        final, overridden, _ = arbitrate_pm_decision(raw_decision="INVALID_STATE")
        assert final == STATE_WATCHLIST
        assert overridden is False

    def test_empty_candidates_in_portfolio_concentration(self):
        """Empty candidate list returns empty lists cleanly."""
        res = check_portfolio_concentration([])
        assert res["approved_candidates"] == []
        assert res["downgraded_candidates"] == []
