"""Unit tests for indicators.py — Financial indicators, quant scores, and smart money flows."""

import pandas as pd
import pytest

from indicators import (
    calculate_100_point_score,
    calculate_altman_z_score,
    calculate_atr,
    calculate_factor_exposures,
    calculate_valuation_triangle,
    calculate_vibe_quality_score,
    evaluate_smart_money_flow,
)


@pytest.mark.offline
class TestIndicators:
    """Test suite for indicators module."""

    def test_calculate_atr_standard(self):
        df = pd.DataFrame(
            {
                "high": [10.5, 11.0, 11.2, 11.5, 11.3, 11.6, 11.8, 12.0, 12.2, 12.1, 12.3, 12.5, 12.7, 12.8, 13.0],
                "low": [10.0, 10.2, 10.5, 10.8, 10.7, 10.9, 11.1, 11.3, 11.5, 11.4, 11.6, 11.8, 12.0, 12.1, 12.2],
                "close": [10.2, 10.8, 11.0, 11.2, 11.0, 11.4, 11.6, 11.8, 12.0, 11.8, 12.1, 12.4, 12.5, 12.6, 12.8],
            }
        )
        atr = calculate_atr(df, period=14)
        assert atr > 0.0

    def test_calculate_atr_insufficient_or_invalid(self):
        assert calculate_atr(None) == 0.0
        df_short = pd.DataFrame({"high": [10.0], "low": [9.0], "close": [9.5]})
        assert calculate_atr(df_short, period=14) == 0.0
        # Broken df causing exception
        df_bad = pd.DataFrame({"bad": [1, 2, 3]})
        assert calculate_atr(df_bad) == 0.0

    def test_piotroski_f_score_special_sectors(self):
        res_bank = calculate_vibe_quality_score({}, sector="Ngân hàng")
        assert res_bank["score"] == 6
        assert "Ngoại lệ" in res_bank["rating"]
        # P0 regression: ensure downstream keys are present (not None)
        assert isinstance(res_bank["passed"], list)
        assert isinstance(res_bank["failed"], list)
        assert isinstance(res_bank["unknown"], list)
        assert res_bank["data_completeness"] == 0.0
        assert "SECTOR EXEMPT" in res_bank["confidence"]

        res_re = calculate_vibe_quality_score({}, sector="Bất động sản")
        assert res_re["score"] == 6
        assert isinstance(res_re["passed"], list)
        assert isinstance(res_re["unknown"], list)

    def test_piotroski_f_score_precomputed(self):
        fin = {"f_score": 8}
        res = calculate_vibe_quality_score(fin)
        assert res["score"] == 8
        assert res["rating"] == "XUẤT SẮC"

    def test_piotroski_f_score_full_calculation(self):
        fin_perfect = {
            "roa": 5.0,
            "p_cf": 10.0,
            "roe": 20.0,
            "net_margin": 15.0,
            "debt_equity": 0.5,
            "current_ratio": 2.0,
            "financial_leverage": 150.0,
            "gross_margin": 25.0,
            "roic": 12.0,
        }
        res = calculate_vibe_quality_score(fin_perfect)
        assert res["score"] == 9
        assert res["rating"] == "XUẤT SẮC"
        assert 'ROA' in res['passed']

        fin_weak = {
            "roa": -2.0,
            "p_cf": -5.0,
            "roe": 3.0,
            "net_margin": 1.0,
            "debt_equity": 200.0,
            "current_ratio": 0.8,
            "financial_leverage": 400.0,
            "gross_margin": 5.0,
            "roic": 2.0,
        }
        res_w = calculate_vibe_quality_score(fin_weak)
        assert res_w["score"] == 0
        assert res_w["rating"] == "YẾU / RỦI RO"

    def test_cfo_scoring_prefers_cfo_to_assets(self):
        """cfo_to_assets (KBS) takes priority over p_cf (VCI) for CFO scoring."""
        base = {
            "roa": 5.0, "roe": 15.0, "net_margin": 10.0,
            "debt_equity": 50.0, "current_ratio": 2.0,
            "financial_leverage": 100.0, "gross_margin": 25.0, "roic": 10.0,
        }
        # cfo_to_assets positive → CFO passed
        fin_pos = {**base, "cfo_to_assets": 0.08}
        res = calculate_vibe_quality_score(fin_pos)
        assert "CFO" in res["passed"]

        # cfo_to_assets = 0.0 → KBS sentinel for missing data → unknown
        fin_zero = {**base, "cfo_to_assets": 0.0}
        res_zero = calculate_vibe_quality_score(fin_zero)
        assert "CFO" in res_zero["unknown"]

        # cfo_to_assets = 0.0 but p_cf available → fallback to VCI
        fin_zero_vci = {**base, "cfo_to_assets": 0.0, "p_cf": 8.5}
        res_zv = calculate_vibe_quality_score(fin_zero_vci)
        assert "CFO" in res_zv["passed"]

        # cfo_to_assets negative → real value, CFO failed
        fin_neg = {**base, "cfo_to_assets": -0.05}
        res_neg = calculate_vibe_quality_score(fin_neg)
        assert "CFO" in res_neg["failed"]

        # No cfo_to_assets, fallback to p_cf
        fin_fallback = {**base, "p_cf": 8.5}
        res_fb = calculate_vibe_quality_score(fin_fallback)
        assert "CFO" in res_fb["passed"]

    def test_altman_z_score_special_sectors_and_empty(self):
        res_bank = calculate_altman_z_score({}, sector="Ngân hàng")
        assert res_bank["z_score"] == 3.0

        res_empty = calculate_altman_z_score({})
        assert res_empty["z_score"] is None
        assert res_empty["icon"] == "⚪"

    def test_altman_z_score_precomputed(self):
        res_safe = calculate_altman_z_score({"z_score": 3.5})
        assert "XANH" in res_safe["zone"]
        assert res_safe["icon"] == "🟢"

        res_grey = calculate_altman_z_score({"z_score": 2.2})
        assert "XÁM" in res_grey["zone"]
        assert res_grey["icon"] == "🟡"

        res_red = calculate_altman_z_score({"z_score": 1.0})
        assert "ĐỎ" in res_red["zone"]
        assert res_red["icon"] == "🔴"

    def test_altman_z_score_calculation(self):
        fin_strong = {"roa": 15.0, "debt_equity": 0.3, "current_ratio": 2.5}
        res = calculate_altman_z_score(fin_strong)
        assert res["z_score"] >= 2.9
        assert res["icon"] == "🟢"

        fin_distressed = {"roa": -25.0, "debt_equity": 5.0, "current_ratio": 0.4}
        res_dist = calculate_altman_z_score(fin_distressed)
        assert res_dist["z_score"] < 2.9

    def test_valuation_triangle_scenarios(self):
        # Invalid price
        assert calculate_valuation_triangle(0)["price_base"] == 0.0

        # Normal stock
        res_norm = calculate_valuation_triangle(100.0, pe=15.0, pb=2.0)
        assert res_norm["price_bull"] == 125.0
        assert res_norm["price_base"] == 110.0
        assert res_norm["price_bear"] == 85.0
        assert not res_norm["is_cyclical"]

        # Cyclical peak stock (Steel with low PE)
        res_cyc_pe = calculate_valuation_triangle(100.0, pe=4.5, pb=1.2, sector="Thép")
        assert res_cyc_pe["is_cyclical"]
        assert res_cyc_pe["price_bull"] == 115.0
        assert res_cyc_pe["price_base"] == 102.0
        assert res_cyc_pe["price_bear"] == 78.0

        # Cyclical peak stock with low PB
        res_cyc_pb = calculate_valuation_triangle(100.0, pe=10.0, pb=0.6, sector="Dầu khí")
        assert res_cyc_pb["is_cyclical"]
        assert res_cyc_pb["price_bull"] == 115.0

    def test_calculate_100_point_score_grades(self):
        tech_strong = {
            "current_price": 50.0,
            "ma20": 48.0,
            "rsi": 55.0,
            "volume": 2000000,
            "vol_ma20": 1500000,
            "foreign_flow": {"net_val_bil": 15.0},
            "adv20_billion": 45.0,
        }
        fin_strong = {
            "roa": 12.0,
            "roe": 22.0,
            "f_score": 9,
            "z_score": 3.8,
            "debt_equity": 0.4,
            "current_ratio": 2.0,
        }
        mos_strong = {"mos_pct": 30.0}

        res_a_plus = calculate_100_point_score("TCB", tech_strong, fin_strong, mos_strong)
        assert res_a_plus["symbol"] == "TCB"
        assert res_a_plus["total_score"] >= 80.0
        assert res_a_plus["grade"] == "A+"
        assert "XUẤT SẮC" in res_a_plus["rating"]

        # Low score -> Grade C
        tech_weak = {
            "current_price": 20.0,
            "ma20": 25.0,
            "rsi": 25.0,
            "volume": 100000,
            "vol_ma20": 200000,
            "foreign_flow": {"net_val_bil": -25.0},
            "adv20_billion": 0.5,
        }
        fin_weak = {
            "roa": -5.0,
            "roe": -10.0,
            "f_score": 2,
            "z_score": 0.5,
        }
        mos_weak = {"mos_pct": -15.0}

        res_c = calculate_100_point_score("DUL", tech_weak, fin_weak, mos_weak)
        assert res_c["grade"] == "C"
        assert "YẾU" in res_c["rating"]

    def test_evaluate_smart_money_flow(self):
        # Heavy sell
        res_sell = evaluate_smart_money_flow(foreign_flow={"net_val_bil": -25.0}, prop_flow={"net_val_bil": -5.0})
        assert res_sell["heavy_selling"] is True
        assert res_sell["buy_allowed"] is False
        assert res_sell["status"] == "INSTITUTIONAL_HEAVY_DISTRIBUTION"

        # Strong accumulation
        res_acc = evaluate_smart_money_flow(foreign_flow={"net_val_bil": 20.0}, prop_flow={"net_val_bil": 10.0})
        assert res_acc["buy_allowed"] is True
        assert res_acc["status"] == "INSTITUTIONAL_STRONG_ACCUMULATION"

        # Neutral
        res_neu = evaluate_smart_money_flow(foreign_flow={"net_val_bil": 2.0}, prop_flow={"net_val_bil": 1.0})
        assert res_neu["status"] == "INSTITUTIONAL_NEUTRAL"

    def test_calculate_factor_exposures(self):
        # Insufficient data
        res_short = calculate_factor_exposures([0.01], [0.02])
        assert res_short["market_beta"] == 1.0
        assert res_short["market_r2"] == 0.0

        # Normal data
        r_asset = [0.01, 0.02, -0.01, 0.03, -0.02, 0.015, -0.005]
        r_mkt = [0.008, 0.015, -0.008, 0.025, -0.018, 0.012, -0.004]
        r_sec = [0.009, 0.018, -0.01, 0.028, -0.02, 0.014, -0.005]

        res = calculate_factor_exposures(r_asset, r_mkt, r_sec)
        assert res["market_beta"] > 0
        assert res["sector_beta"] is not None
        assert "idiosyncratic_alpha_pct" in res
