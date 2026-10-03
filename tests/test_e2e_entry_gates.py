"""Integration tests for Phase 14: Data & Valuation Plumbing (v7.4 / TASK-0042 to TASK-0045).

Tests:
1. MoS differs across archetypes when genuine fin_dict is provided, and mos_is_informative is True.
2. mos_is_informative is False when fin_dict is empty/missing for CYCLICAL and REAL_ESTATE.
3. Portfolio key mapping handles Vietnamese column names correctly, activating Trailing Stop for profitable holdings.
4. load_market_context checks staleness against current date by default.
5. evaluate_decision_hard_gates receives symbol, fin_dict, sector, and tech_data.
"""

from datetime import date
from unittest.mock import patch

import pandas as pd

from context_engine import load_market_context
from portfolio_guard import evaluate_holding_position
from quant_engine import evaluate_decision_hard_gates
from quant_valuation import calculate_fair_value_and_mos

MOCK_FIN_BANK = {
    "pb": 1.6,
    "roe": 18.0,
    "period": "2026-Q2",
}

MOCK_FIN_STEEL = {
    "pe": 9.5,
    "pb": 1.2,
    "eps_history": [2400, 3100, 2800, 3500, 2900],
    "period": "2026-Q2",
}

MOCK_FIN_GROWTH = {
    "forward_eps": 7.5,
    "median_pe": 19.0,
    "eps": 6.8,
    "period": "2026-Q2",
}

MOCK_FIN_REAL_ESTATE = {
    "bvps": 42.0,
    "pb": 1.1,
    "roe": 14.0,
    "debt_equity": 0.8,
    "period": "2026-Q2",
}


def test_mos_differs_by_archetype_with_genuine_fin_dict():
    """AC-42.1: Verify MoS differs by archetype and mos_is_informative is True when fin_dict is provided."""
    bank = calculate_fair_value_and_mos("BID", current_price=45.0, fin_dict=MOCK_FIN_BANK, sector="Ngân hàng")
    steel = calculate_fair_value_and_mos("HPG", current_price=28.0, fin_dict=MOCK_FIN_STEEL, sector="Thép")
    growth = calculate_fair_value_and_mos("FPT", current_price=110.0, fin_dict=MOCK_FIN_GROWTH, sector="Công nghệ")
    real_estate = calculate_fair_value_and_mos("VHM", current_price=40.0, fin_dict=MOCK_FIN_REAL_ESTATE, sector="Bất động sản")

    assert bank["mos_pct"] != steel["mos_pct"]
    assert steel["mos_pct"] != growth["mos_pct"]
    assert growth["mos_pct"] != real_estate["mos_pct"]

    assert bank["mos_is_informative"] is True
    assert steel["mos_is_informative"] is True
    assert growth["mos_is_informative"] is True
    assert real_estate["mos_is_informative"] is True


def test_mos_uninformative_when_fin_dict_missing_for_cyclical_and_real_estate():
    """AC-42.3: Verify mos_is_informative is False for CYCLICAL and REAL_ESTATE when fin_dict is empty."""
    steel_empty = calculate_fair_value_and_mos("HPG", current_price=28.0, fin_dict={}, sector="Thép")
    re_empty = calculate_fair_value_and_mos("VHM", current_price=40.0, fin_dict={}, sector="Bất động sản")

    assert steel_empty["mos_is_informative"] is False, "Empty fin_dict in CYCLICAL must yield mos_is_informative=False"
    assert re_empty["mos_is_informative"] is False, "Empty fin_dict in REAL_ESTATE must yield mos_is_informative=False"

    # Hard gate must block BUY when mos_is_informative is False
    gate_res = evaluate_decision_hard_gates(
        current_price=28.0,
        p_bull=0.4,
        p_base=0.4,
        p_bear=0.2,
        price_bull=35.0,
        price_base=30.0,
        price_bear=24.0,
        symbol="HPG",
        fin_dict={},
        sector="Thép",
    )
    assert gate_res.get("gate_mos_passed") is False
    assert gate_res.get("mos_is_informative") is False
    assert gate_res.get("action_state") != "🟢 VALUE BUY"


def test_portfolio_vietnamese_column_mapping_and_trailing_stop():
    """AC-42.2: Verify portfolio evaluation correctly maps Vietnamese column names and sets trailing stop for profit."""
    from ai_analyst import _build_portfolio_quant_summary

    # Case 1: DataFrame with "Giá TB (k)", "Giá hiện tại (k)", "Giá cao (k)"
    df_vn1 = pd.DataFrame(
        [
            {
                "Mã CP": "FPT",
                "Giá TB (k)": 100.0,
                "Giá hiện tại (k)": 115.0,
                "Giá cao (k)": 118.0,
                "Khối lượng": 1000,
            }
        ]
    )

    row_dict = df_vn1.iloc[0].to_dict()
    tech_data = {"current_price": 115.0, "atr": 2.5, "ma20": 110.0}
    pos_res = evaluate_holding_position(row_dict, tech_data)

    assert pos_res["is_profit"] is True
    assert pos_res["entry_price"] == 100.0
    assert pos_res["curr_price"] == 115.0
    assert pos_res["pl_pct"] == 15.0
    assert pos_res["trailing_stop"] > 100.0

    summary_text = _build_portfolio_quant_summary(df_vn1)
    assert "TRAIL" in summary_text.upper()
    assert "Lãi: +15.0%" in summary_text

    # Case 2: DataFrame with "Giá vốn (k)", "Thị giá (k)"
    df_vn2 = pd.DataFrame(
        [
            {
                "Mã CP": "MWG",
                "Giá vốn (k)": 60.0,
                "Thị giá (k)": 70.0,
                "Giá cao (k)": 72.0,
                "Khối lượng": 500,
            }
        ]
    )
    row_dict2 = df_vn2.iloc[0].to_dict()
    pos_res2 = evaluate_holding_position(row_dict2, {"current_price": 70.0, "atr": 1.5, "ma20": 65.0})
    assert pos_res2["is_profit"] is True
    assert pos_res2["entry_price"] == 60.0
    assert pos_res2["pl_pct"] > 0


def test_market_context_staleness_check_default(tmp_path):
    """AC-42.4: Verify load_market_context checks staleness against current date by default."""
    stale_file = tmp_path / "stale_context.json"
    stale_file.write_text(
        '{"date": "2020-01-01", "source": "TCBS", "market_regime_analyst": "UPTREND"}',
        encoding="utf-8",
    )

    # Calling without current_date should detect that 2020-01-01 != today
    ctx = load_market_context(filepath=stale_file)
    assert ctx.is_valid is False
    assert ctx.date == "2020-01-01"

    # When allow_stale=True, it should be accepted
    ctx_allowed = load_market_context(filepath=stale_file, allow_stale=True)
    assert ctx_allowed.is_valid is True

    # Fresh file with today's date should pass
    today_str = str(date.today())
    fresh_file = tmp_path / "fresh_context.json"
    fresh_file.write_text(
        f'{{"date": "{today_str}", "source": "TCBS", "market_regime_analyst": "UPTREND"}}',
        encoding="utf-8",
    )
    ctx_fresh = load_market_context(filepath=fresh_file)
    assert ctx_fresh.is_valid is True
    assert ctx_fresh.date == today_str


def test_scan_market_opportunities_mwg_pipeline_valuation_method():
    """Verify scan_market_opportunities for MWG uses genuine valuation method, not fallback."""
    from data_engine import scan_market_opportunities

    mock_tech = {
        "current_price": 72.0,
        "ma20": 70.0,
        "ma50": 68.0,
        "ma100": 65.0,
        "rsi14": 52.0,
        "vol_ratio": 1.1,
        "change_pct": 1.2,
        "atr14": 1.5,
    }
    mock_fin = {
        "period": "2026-Q2",
        "pe": 16.0,
        "pb": 2.8,
        "forward_eps": 5.0,
        "roe": 18.0,
    }

    with (
        patch("data_engine.fetch_stock_technical", return_value=mock_tech),
        patch("data_engine.get_financial_ratios", return_value=mock_fin),
        patch("data_engine.fetch_macro_news", return_value=[]),
        patch("data_engine.load_watchlist", return_value=[]),
    ):
        results = scan_market_opportunities(extra_symbols=["MWG"])
        assert len(results) > 0
        mwg_res = next((r for r in results if r["symbol"] == "MWG"), None)
        assert mwg_res is not None
        assert "FALLBACK" not in str(mwg_res.get("valuation_method", "")).upper()
        assert mwg_res["mos_is_informative"] is True


def test_smart_committee_receives_fin_dict_and_sector():
    """Verify _prepare_smart_committee_context passes fin_dict and sector into calculate_fair_value_and_mos."""
    from ai_analyst import _prepare_smart_committee_context

    mock_tech = {"current_price": 45.0, "status_ma20": "TRÊN MA20", "rsi14": 55.0}
    mock_fin = {"pb": 1.8, "roe": 19.0, "period": "2026-Q2"}

    with (
        patch("data_gate.reconcile_data", return_value={"gate_passed": True, "recommendation_allowed": True}),
        patch("quant_valuation.calculate_fair_value_and_mos") as mock_val,
    ):
        mock_val.return_value = {
            "fair_value": 50.0,
            "mos_pct": 10.0,
            "mos_is_informative": True,
            "valuation_method": "Justified P/B",
            "confidence": "HIGH",
        }
        _prepare_smart_committee_context("BID", tech_data=mock_tech, fin_data=mock_fin)

        mock_val.assert_called_once()
        _, kwargs = mock_val.call_args
        assert kwargs.get("fin_dict") == mock_fin
        assert kwargs.get("sector") == "Ngân hàng"


def test_quantamental_2pass_passes_full_params_to_hard_gates():
    """Verify generate_quantamental_2pass_report passes symbol, fin_dict, sector, and tech_data to evaluate_decision_hard_gates."""
    from ai_analyst import generate_quantamental_2pass_report

    mock_tech = {
        "current_price": 100.0,
        "status_ma20": "TRÊN MA20",
        "rsi14": 50.0,
        "atr14": 2.0,
        "adv20_billion": 50.0,
    }
    mock_fin = {"period": "2026-Q2", "pe": 18.0, "pb": 3.0, "roe": 22.0}

    with (
        patch("data_engine.fetch_stock_technical", return_value=mock_tech),
        patch("data_engine.get_financial_ratios", return_value=mock_fin),
        patch("data_engine.fetch_macro_news", return_value=[]),
        patch("ai_analyst.call_gemini", return_value='{"P_bull": 0.4, "P_base": 0.4, "P_bear": 0.2}'),
        patch("data_engine.is_symbol_in_cooldown", return_value=False),
        patch("data_engine.get_today_buy_signal_count", return_value=0),
        patch("data_engine.load_portfolio", return_value={}),
        patch("quant_engine.evaluate_decision_hard_gates") as mock_gate,
    ):
        mock_gate.return_value = {
            "action_state": "🟢 VALUE BUY",
            "mos_pct": 15.0,
            "ev": 110.0,
            "stop_loss": 94.0,
            "price_target": 120.0,
            "risk_reward": 2.5,
            "kelly_f": 0.12,
            "position_size_nav": "10% NAV",
            "decision_tag": "BUY",
        }
        generate_quantamental_2pass_report("FPT")

        mock_gate.assert_called_once()
        _, kwargs = mock_gate.call_args
        assert kwargs.get("symbol") == "FPT"
        assert kwargs.get("fin_dict") == mock_fin
        assert kwargs.get("sector") == "Công nghệ / AI"
        assert kwargs.get("tech_data") == mock_tech

