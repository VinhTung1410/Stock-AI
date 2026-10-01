from unittest import mock

import numpy as np
import pandas as pd
import pytest

from ai_analyst import generate_portfolio_analysis
from data_engine import (
    _LAST_KNOWN_TECH_CACHE,
    _TECH_CACHE,
    fetch_stock_technical,
)
from quant_engine import evaluate_market_regime

pytestmark = pytest.mark.offline


@pytest.fixture(autouse=True)
def clear_tech_caches():
    """Clear in-memory technical cache before each test to ensure test isolation."""
    _TECH_CACHE.clear()
    yield
    _TECH_CACHE.clear()


def test_fetch_stock_technical_calculates_delta_points_and_ma_diff():
    """AC-17.1: Verify fetch_stock_technical accurately calculates diff_points, diff_ma20, diff_ma50."""
    dates = pd.date_range("2026-01-01", periods=60)
    # Generate prices: baseline 1200 with an uptrend up to 1285.50
    closes = np.linspace(1200, 1285.50, 60)
    # Yesterday close: closes[-2], Today close: closes[-1]
    df_mock = pd.DataFrame(
        {
            "time": dates,
            "open": closes - 2.0,
            "high": closes + 5.0,
            "low": closes - 5.0,
            "close": closes,
            "volume": [1000000] * 60,
        }
    )

    with mock.patch("vnstock.api.quote.Quote.history", return_value=df_mock):
        res = fetch_stock_technical("VNINDEX", fetch_foreign=False)

        assert res is not None
        assert "diff_points" in res
        assert "diff_ma20" in res
        assert "diff_ma50" in res

        expected_diff = round(float(closes[-1] - closes[-2]), 2)
        assert res["diff_points"] == expected_diff
        assert res["current_price"] == round(float(closes[-1]), 2)
        assert res["ref_price"] == round(float(closes[-2]), 2)

        # MA20 and MA50 differences
        ma20_val = res["ma20"]
        assert ma20_val is not None
        assert res["diff_ma20"] == round(res["current_price"] - ma20_val, 2)

        ma50_val = res["ma50"]
        assert ma50_val is not None
        assert res["diff_ma50"] == round(res["current_price"] - ma50_val, 2)

        # Check persistence in _LAST_KNOWN_TECH_CACHE
        assert "VNINDEX" in _LAST_KNOWN_TECH_CACHE
        assert _LAST_KNOWN_TECH_CACHE["VNINDEX"]["diff_points"] == expected_diff


def test_fetch_stock_technical_falls_back_to_cache_preventing_zero():
    """AC-17.1: Verify technical fetch falls back gracefully to _LAST_KNOWN_TECH_CACHE without returning 0.00."""
    _LAST_KNOWN_TECH_CACHE["VNINDEX"] = {
        "symbol": "VNINDEX",
        "current_price": 1285.50,
        "ref_price": 1275.00,
        "diff_points": 10.50,
        "change_pct": 0.82,
        "ma20": 1270.00,
        "ma50": 1260.00,
        "diff_ma20": 15.50,
        "diff_ma50": 25.50,
        "status_ma20": "Nằm TRÊN MA20 (Khả quan)",
        "rsi14": 58.5,
    }

    # Simulate network error / empty dataframe from vnstock
    with mock.patch("vnstock.api.quote.Quote.history", return_value=pd.DataFrame()):
        res = fetch_stock_technical("VNINDEX")
        assert res["current_price"] == 1285.50
        assert res["diff_points"] == 10.50
        assert res["change_pct"] == 0.82
        assert res["current_price"] > 0


@mock.patch("ai_analyst.call_gemini")
def test_generate_portfolio_analysis_auto_fetches_vnindex_and_populates_prompt(mock_call_gemini):
    """AC-17.2: Verify generate_portfolio_analysis auto-fetches VNINDEX when vnindex_tech is None."""
    mock_call_gemini.return_value = (
        "**I. TỔNG KẾT PHIÊN ATC & ĐÁNH GIÁ 5 CÂU HỎI CỐT TỬ**\n"
        "- **Câu hỏi 1 (Nguyên nhân biến động):** Thị trường tăng trưởng mạnh.\n"
        "- **Câu hỏi 2 (Định giá & MoS):** Cổ phiếu FPT còn hấp dẫn.\n"
        "- **Câu hỏi 3 (Chốt lời & Trailing Stop):** Duy trì vị thế.\n"
        "- **Câu hỏi 4 (Thesis Breaker):** Luận điểm nguyên vẹn.\n"
        "- **Câu hỏi 5 (Tỷ trọng Tiền/Cổ phiếu):** 70% Cổ phiếu / 30% Tiền.\n\n"
        "**II. CHI TIẾT DANH MỤC & HÀNH ĐỘNG QUẢN TRỊ RỦI RO**\n"
        "• Cổ phiếu **FPT** — 🟢 BẢO VỆ THÀNH QUẢ"
    )

    fake_vnindex = {
        "symbol": "VNINDEX",
        "current_price": 1288.60,
        "ref_price": 1280.00,
        "diff_points": 8.60,
        "change_pct": 0.67,
        "ma20": 1270.00,
        "ma50": 1255.00,
        "status_ma20": "Nằm TRÊN MA20 (Khả quan)",
        "rsi14": 62.0,
        "vol_ratio": 1.25,
    }

    portfolio_df = pd.DataFrame([{"Mã CP": "FPT", "Thị giá (k)": 135.0, "Giá vốn (k)": 120.0, "Lãi/Lỗ (%)": 12.5}])

    with mock.patch("data_engine.fetch_stock_technical", return_value=fake_vnindex) as mock_fetch:
        result = generate_portfolio_analysis(portfolio_df, [], vnindex_tech=None, session_label="ATC")

        mock_fetch.assert_called_once_with("VNINDEX")

        # Verify prompt passed to Gemini contains real VN-Index values and delta points
        called_prompt = mock_call_gemini.call_args[0][1]
        assert "1288.60 điểm" in called_prompt
        assert "+8.60 điểm" in called_prompt
        assert "+0.67%" in called_prompt
        assert "1270.00 điểm" in called_prompt
        assert "62.0" in called_prompt
        assert "ở mức **0.00 điểm**" not in called_prompt
        assert "Điểm số đóng cửa phiên gần nhất: 0.00 điểm" not in called_prompt

        # Verify no hardcoded 70/30 in prompt risk budget
        regime_expected = evaluate_market_regime(fake_vnindex)
        assert f"Cổ phiếu {regime_expected['stock_pct']} | Tiền mặt {regime_expected['cash_pct']}" in called_prompt
        assert result is not None


@mock.patch("ai_analyst.call_gemini")
def test_generate_portfolio_analysis_single_source_of_truth_consistency(mock_call_gemini):
    """AC-17.2: Verify question 5 fallback uses evaluate_market_regime (Single Source of Truth)."""
    # Gemini forgets question 5
    mock_call_gemini.return_value = (
        "**I. TỔNG KẾT PHIÊN ATC & ĐÁNH GIÁ 5 CÂU HỎI CỐT TỬ**\n"
        "- **Câu hỏi 1:** Tăng tốt.\n"
        "- **Câu hỏi 2:** Ổn định.\n\n"
        "**II. CHI TIẾT DANH MỤC**\n"
        "Chi tiết danh mục nắm giữ..."
    )

    # Downtrend mock: should lead to defensive allocation (e.g. 30% stock or cash mode)
    defensive_vnindex = {
        "symbol": "VNINDEX",
        "current_price": 1150.0,
        "ref_price": 1180.0,
        "diff_points": -30.0,
        "change_pct": -2.54,
        "ma20": 1220.0,
        "ma50": 1240.0,
        "status_ma20": "Nằm DƯỚI MA20 (Thận trọng)",
        "rsi14": 32.0,
        "vol_ratio": 0.7,
    }

    portfolio_df = pd.DataFrame([{"Mã CP": "HPG", "Thị giá (k)": 25.0, "Giá vốn (k)": 28.0, "Lãi/Lỗ (%)": -10.7}])

    expected_regime = evaluate_market_regime(defensive_vnindex)

    result = generate_portfolio_analysis(portfolio_df, [], vnindex_tech=defensive_vnindex, session_label="ATC")

    # Verify Question 5 fallback matches expected_regime 100%
    assert "Câu hỏi 5 (Tỷ trọng Tiền/Cổ phiếu)" in result
    assert f"Cổ phiếu {expected_regime['stock_pct']} / Tiền mặt {expected_regime['cash_pct']}" in result
    # Crucially ensure it did NOT fallback to the old hardcoded 70% / 30%
    if expected_regime["stock_pct"] != "70%":
        assert "Cổ phiếu 70% / Tiền mặt 30%" not in result


@mock.patch("trading_bot.send_discord_webhook")
@mock.patch("trading_bot.send_discord_dm")
@mock.patch("trading_bot.load_portfolio")
@mock.patch("trading_bot.evaluate_portfolio")
@mock.patch("trading_bot.load_watchlist")
@mock.patch("trading_bot.evaluate_watchlist")
@mock.patch("trading_bot.fetch_macro_news")
@mock.patch("trading_bot.generate_portfolio_analysis")
@mock.patch("data_engine.fetch_stock_technical")
def test_trading_bot_trigger_scheduled_report_prefetches_vnindex(
    mock_fetch_tech,
    mock_gen_portfolio,
    mock_fetch_news,
    mock_eval_wl,
    mock_load_wl,
    mock_eval_port,
    mock_load_port,
    mock_send_dm,
    mock_send_wh,
):
    """AC-17.3: Verify trading_bot pre-fetches VN-Index once and passes it to generate_portfolio_analysis."""
    from trading_bot import trigger_scheduled_report

    mock_load_port.return_value = [{"symbol": "FPT", "volume": 100, "cost_price": 100.0}]
    mock_eval_port.return_value = pd.DataFrame(
        [{"Mã CP": "FPT", "Thị giá (k)": 110.0, "Giá vốn (k)": 100.0, "Lãi/Lỗ (%)": 10.0}]
    )
    mock_load_wl.return_value = []
    mock_eval_wl.return_value = None
    mock_fetch_news.return_value = []
    mock_fetch_tech.return_value = {"symbol": "VNINDEX", "current_price": 1280.0, "diff_points": 5.0}
    mock_gen_portfolio.return_value = "Mock Report Output"

    trigger_scheduled_report("14:45", "Báo cáo Phiên ATC")

    # Assert fetch_stock_technical was called for VNINDEX
    mock_fetch_tech.assert_called_with("VNINDEX")

    # Assert generate_portfolio_analysis received the pre-fetched vnindex_tech
    assert mock_gen_portfolio.called
    kwargs = mock_gen_portfolio.call_args[1]
    assert kwargs.get("vnindex_tech") == {"symbol": "VNINDEX", "current_price": 1280.0, "diff_points": 5.0}
    assert kwargs.get("session_label") == "ATC"
