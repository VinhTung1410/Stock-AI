"""
V2 system tests — validates the full quantamental pipeline including
archetype classification, fair value, holding position evaluation,
market regime, and the 100-point scoring engine.
"""
import pytest

from quant_engine import (
    calculate_100_point_score,
    evaluate_holding_position,
    evaluate_market_regime,
)
from quant_valuation import (
    calculate_fair_value_and_mos,
    classify_stock_archetype,
)


@pytest.mark.offline
class TestArchetypeClassification:
    """Verify stocks are classified into the correct valuation archetype."""

    @pytest.mark.parametrize("symbol,sector,expected", [
        ("MSB", "Ngân hàng", "BANK"),
        ("FPT", "Công nghệ", "GROWTH_COMPOUNDER"),
        ("HPG", "Thép", "CYCLICAL"),
        ("BSR", "Dầu khí", "CYCLICAL"),
        ("VHM", "Bất động sản", "REAL_ESTATE"),
    ])
    def test_classification(self, symbol, sector, expected):
        assert classify_stock_archetype(symbol, sector) == expected


@pytest.mark.offline
class TestFairValueAndMoS:
    """Verify fair value calculation returns valid structure for each archetype."""

    @pytest.mark.parametrize("symbol,price,sector", [
        ("MSB", 15.0, "Ngân hàng"),
        ("FPT", 75.0, "Công nghệ"),
        ("HPG", 26.0, "Thép"),
        ("VHM", 42.0, "Bất động sản"),
    ])
    def test_returns_valid_structure(self, symbol, price, sector):
        result = calculate_fair_value_and_mos(symbol, price, sector=sector)

        assert "fair_value" in result
        assert "mos_pct" in result
        assert "valuation_rating" in result
        assert "valuation_method" in result


@pytest.mark.offline
class TestHoldingPosition:
    """Validate position evaluation logic for both profitable and losing positions."""

    def test_profitable_position_uses_trailing_stop(self):
        """Profitable position should activate trailing stop, never say 'cut loss'."""
        row = {"symbol": "MSB", "avg_price": 12.5, "volume": 2000, "market_price": 15.0}
        tech = {"current_price": 15.0, "atr": 0.45, "ma20": 14.2}

        result = evaluate_holding_position(row, tech)

        assert result["pl_pct"] > 0
        assert "CẮT LỖ" not in result["action"].upper()
        assert result["trailing_stop"] >= 12.5, "Trailing stop must protect capital"

    def test_losing_position_has_stop_loss(self):
        """Losing position should have a stop loss and thesis breaker assessment."""
        row = {"symbol": "FPT", "avg_price": 78.0, "volume": 1000, "market_price": 75.0}
        tech = {"current_price": 75.0, "atr": 1.8, "ma20": 76.5}

        result = evaluate_holding_position(row, tech)

        assert result["pl_pct"] < 0
        assert "stop_loss" in result
        assert "thesis_breaker" in result


@pytest.mark.offline
class TestMarketRegime:
    """Test market regime classification under different VN-Index conditions."""

    @pytest.mark.parametrize("name,tech_data", [
        ("VN-Index above MA20+MA50", {"current_price": 1320, "ma20": 1300, "ma50": 1280, "rsi": 62}),
        ("VN-Index below MA20", {"current_price": 1270, "ma20": 1290, "ma50": 1260, "rsi": 44}),
        ("VN-Index deep correction", {"current_price": 1220, "ma20": 1280, "ma50": 1270, "rsi": 32}),
    ])
    def test_regime_classification(self, name, tech_data):
        regime = evaluate_market_regime(tech_data)

        assert regime["regime"] in ["BULLISH", "NEUTRAL", "CORRECTION", "RISK-OFF"]
        assert "stock_pct" in regime
        assert "cash_pct" in regime


@pytest.mark.offline
class TestScoringEngine:
    """Validate the 100-point multi-pillar scoring system."""

    def test_score_structure_and_range(self):
        fin = {
            "roe": 19.5, "roa": 2.2, "debt_equity": 0.8, "current_ratio": 1.5,
            "gross_margin": 22.0, "net_margin": 14.0, "p_cf": 12.0, "roic": 15.0,
        }
        tech = {
            "current_price": 75.0, "ma20": 73.0, "rsi": 54.0,
            "volume": 3500000, "vol_ma20": 3000000,
            "adv20_billion": 260.0, "foreign_flow": {"net_val_bil": 15.0},
        }
        mos = {"mos_pct": 21.0}

        result = calculate_100_point_score("FPT", tech, fin, mos)

        assert 0 <= result["total_score"] <= 100
        assert result["grade"] is not None
        assert result["rating"] is not None
        assert "pillar_fundamental" in result["breakdown"]
        assert "pillar_valuation" in result["breakdown"]
        assert "pillar_technical" in result["breakdown"]
        assert "pillar_smart_flow" in result["breakdown"]
