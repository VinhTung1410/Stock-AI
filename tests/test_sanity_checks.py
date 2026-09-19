"""
Deterministic quant logic tests — validates mathematical consistency
of the core quantitative engine without any external API calls.

Tests cover:
- Weighted R:R calculation
- Trailing stop clamping & profit protection
- Value vs Technical signal separation
- Fair value methodology (SOTP for VIC)
- Market regime risk budgeting
- Full portfolio sanity check engine
"""
import pandas as pd
import pytest

from quant_engine import (
    calculate_weighted_entry_and_rr,
    evaluate_decision_hard_gates,
    evaluate_holding_position,
    evaluate_market_regime,
)
from quant_sanity_check import (
    run_full_portfolio_sanity_check,
)
from quant_valuation import calculate_fair_value_and_mos


@pytest.mark.offline
class TestWeightedRR:
    """Verify R:R is calculated from weighted average entry, not current price."""

    def test_weighted_entry_calculation(self):
        result = calculate_weighted_entry_and_rr(
            entry_prices=[72.0, 70.0, 68.0],
            weights=[0.30, 0.40, 0.30],
            target_price=82.0,
            stop_loss=65.0,
        )
        assert result["weighted_entry"] == pytest.approx(70.0, abs=1e-4)
        assert result["reward"] == pytest.approx(12.0, abs=1e-4)
        assert result["risk"] == pytest.approx(5.0, abs=1e-4)
        assert result["rr_ratio"] == pytest.approx(2.40, abs=1e-4)


@pytest.mark.offline
class TestTrailingStop:
    """Validate trailing stop logic: clamp below current price,
    never label a profitable position as 'cut loss'."""

    def test_clamp_below_current_price(self):
        row = {"symbol": "MSB", "avg_price": 12.42, "volume": 1000}
        tech_data = {"current_price": 12.80, "ma20": 13.10, "atr": 0.35}

        pos = evaluate_holding_position(row, tech_data)

        # Trailing stop must be < current price
        assert pos["trailing_stop"] < 12.80, (
            f"Trailing Stop ({pos['trailing_stop']}) >= Current (12.80)"
        )
        # Must be clamped to at most 96% of current price
        assert pos["trailing_stop"] <= round(12.80 * 0.96, 2)

    def test_no_cut_loss_label_when_profitable(self):
        row = {"symbol": "MSB", "avg_price": 12.42, "volume": 1000}
        tech_data = {"current_price": 12.80, "ma20": 13.10, "atr": 0.35}

        pos = evaluate_holding_position(row, tech_data)

        assert "cắt lỗ" not in pos["detail"].lower(), (
            "Profitable position must not use 'cut loss' wording"
        )
        assert "cắt lỗ" not in pos["action"].lower()


@pytest.mark.offline
class TestValueVsTechnical:
    """MoS > 0 but price below MA20 should be WATCH, not AVOID/TRAP."""

    def test_good_value_weak_technical_is_watch(self):
        gate = evaluate_decision_hard_gates(
            current_price=57.0,
            p_bull=0.25,
            p_base=0.55,
            p_bear=0.20,
            price_bull=75.0,
            price_base=65.0,
            price_bear=52.0,
            atr=1.5,
            symbol="MWG",
            sector="Bán lẻ",
            tech_data={"current_price": 57.0, "ma20": 59.0, "ma50": 60.0, "rsi": 42.0},
        )

        assert "TRÁNH BẪY" not in gate["decision_tag"]
        assert "BẪY" not in gate["decision_tag"]
        assert "THEO DÕI" in gate["action_state"], (
            f"Expected WATCH state, got: {gate['action_state']}"
        )


@pytest.mark.offline
class TestValuation:
    """Verify archetype-specific valuation models and methodology metadata."""

    def test_vic_uses_sotp_methodology(self):
        val = calculate_fair_value_and_mos("VIC", current_price=42.0)

        assert "SOTP" in val.get("valuation_method", ""), (
            "VIC (real estate conglomerate) must use SOTP/RNAV model"
        )
        assert val.get("confidence") in ["HIGH", "MEDIUM", "LOW"]
        assert val.get("price_target") is not None


@pytest.mark.offline
class TestMarketRegime:
    """Validate multi-variable market regime classification and risk budgeting."""

    def test_risk_budgeting_with_healthy_market(self):
        regime = evaluate_market_regime(
            vnindex_tech={
                "current_price": 1285.0,
                "ma20": 1280.0,
                "ma50": 1260.0,
                "rsi": 58.0,
                "vol_ratio": 1.15,
            },
            market_breadth_pct=62.0,
            portfolio_drawdown_pct=-1.5,
            margin_exposure_pct=10.0,
        )

        assert regime["regime"] in ["BULLISH", "NEUTRAL", "CORRECTION", "RISK-OFF"]
        assert regime["risk_budget_score"] > 0


@pytest.mark.offline
class TestSanityCheckEngine:
    """Run the full sanity check engine on a mock portfolio."""

    def test_clean_portfolio_passes(self):
        df_portfolio = pd.DataFrame([
            {
                "symbol": "MSB",
                "market_price": 12.80,
                "avg_cost": 12.42,
                "pnl_pct": 3.06,
                "trailing_stop": 12.28,
                "action": "NẮM GIỮ",
                "note": "Bảo toàn lợi nhuận, nâng trailing stop lên 12.28k.",
            },
            {
                "symbol": "FPT",
                "market_price": 135.0,
                "avg_cost": 130.0,
                "pnl_pct": 3.85,
                "trailing_stop": 129.5,
                "action": "NẮM GIỮ",
                "note": "Xu hướng tăng duy trì tốt.",
            },
        ])

        all_passed, issues, _ = run_full_portfolio_sanity_check(df_portfolio)
        assert all_passed is True, f"Sanity check failed: {issues}"
