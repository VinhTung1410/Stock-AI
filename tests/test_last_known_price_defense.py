from unittest import mock

import pandas as pd

from data_engine import (
    _LAST_KNOWN_PRICE_CACHE,
    _LAST_KNOWN_TECH_CACHE,
    _TECH_CACHE,
    evaluate_portfolio,
    fetch_stock_technical,
    get_last_known_price,
    set_last_known_price,
)


def test_last_known_price_caching():
    set_last_known_price("TEST_SYM", 45.5)
    assert get_last_known_price("TEST_SYM") == 45.5
    assert get_last_known_price("test_sym") == 45.5


def test_fetch_stock_technical_falls_back_to_last_known_tech():
    _TECH_CACHE.clear()
    _LAST_KNOWN_TECH_CACHE["MOCK_SYM"] = {
        "symbol": "MOCK_SYM",
        "current_price": 50.0,
        "status_ma20": "TRÊN MA20",
        "rsi14": 55.0,
    }

    # Giả lập vnstock Quote.history bị lỗi hoặc trả về rỗng (Rate limit / timeout)
    with mock.patch("vnstock.api.quote.Quote.history", return_value=pd.DataFrame()):
        res = fetch_stock_technical("MOCK_SYM")
        assert res.get("current_price") == 50.0
        assert res.get("status_ma20") == "TRÊN MA20"


def test_evaluate_portfolio_uses_last_known_price_when_tech_fails():
    _TECH_CACHE.clear()
    _LAST_KNOWN_PRICE_CACHE["FPT"] = 63.50

    portfolio = [{"symbol": "FPT", "volume": 220, "cost_price": 66.66}]

    # Giả lập fetch_stock_technical trả về rỗng hoàn toàn {}
    with mock.patch("data_engine.fetch_stock_technical", return_value={}):
        df_eval = evaluate_portfolio(portfolio)
        assert not df_eval.empty
        # Thị giá phải là 63.50 (từ cache), TUYỆT ĐỐI không được fallback về giá vốn 66.66
        assert float(df_eval["Thị giá (k)"].iloc[0]) == 63.50
        assert float(df_eval["Lãi/Lỗ (%)"].iloc[0]) < 0
