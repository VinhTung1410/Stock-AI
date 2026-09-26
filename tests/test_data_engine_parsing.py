import pandas as pd
import pytest

from data_engine import (
    _is_valid_symbol,
    _normalize_column_names,
    _parse_numeric,
    _parse_sheet_portfolio,
    _parse_sheet_watchlist,
    _split_csv_rows,
)


@pytest.mark.offline
class TestDataEngineParsing:
    """Offline unit tests for Google Sheet parsing logic and data helpers."""

    def test_is_valid_symbol(self):
        assert _is_valid_symbol("FPT") is True
        assert _is_valid_symbol("MSB") is True
        assert _is_valid_symbol("") is False
        assert _is_valid_symbol("TOOLONG") is False
        assert _is_valid_symbol("12") is False

    def test_parse_numeric(self):
        assert _parse_numeric("1,000", is_int=True) == 1000
        assert _parse_numeric("1.000", is_int=True) == 1000
        assert _parse_numeric("220.0", is_int=True) == 220
        assert _parse_numeric("25.5") == 25.5
        assert _parse_numeric("66,66") == 66.66
        assert _parse_numeric("10,65") == 10.65
        assert _parse_numeric("21,21") == 21.21
        assert _parse_numeric(6666.0) == 66.66
        assert _parse_numeric("6666") == 66.66
        assert _parse_numeric(66660) == 66.66
        assert _parse_numeric("66660") == 66.66
        assert _parse_numeric("nan", default=0.0) == 0.0
        assert _parse_numeric(None, default=5.0) == 5.0
        assert _parse_numeric("invalid", default=0.0) == 0.0

    def test_normalize_column_names(self):
        df = pd.DataFrame({"Mã CP": ["FPT"], "Khối lượng": ["100"], "Giá vốn": ["100.5"]})
        normalized = _normalize_column_names(df)
        assert "symbol" in normalized.columns
        assert "volume" in normalized.columns
        assert "cost_price" in normalized.columns

    def test_parse_sheet_portfolio(self):
        df = pd.DataFrame({
            "symbol": ["FPT", "INVALID", "HPG"],
            "volume": ["1,000", "500", "0"],
            "cost_price": ["95.5", "20.0", "28.0"],
            "note": ["Core holding", "Skip", "Zero vol"],
        })
        portfolio = _parse_sheet_portfolio(df)
        assert len(portfolio) == 1
        assert portfolio[0]["symbol"] == "FPT"
        assert portfolio[0]["volume"] == 1000
        assert portfolio[0]["cost_price"] == 95.5

    def test_parse_sheet_watchlist(self):
        df = pd.DataFrame([
            ["MSB", "14.5", "Chờ mua giá tốt"],
            ["INVALID_CODE", "10.0", "Bỏ qua"],
        ])
        watchlist = _parse_sheet_watchlist(df)
        assert len(watchlist) == 1
        assert watchlist[0]["symbol"] == "MSB"
        assert watchlist[0]["target_buy"] == 14.5

    def test_split_csv_rows(self):
        df = pd.DataFrame({
            "symbol": ["FPT", "SSI"],
            "volume": ["1000", "0"],
            "cost_price": ["90.0", "30.0"],
            "target_buy": ["0", "28.5"],
            "type": ["HOLDING", "WATCH"],
            "note": ["Lãi tốt", "Theo dõi"],
        })
        portfolio, watchlist = _split_csv_rows(df)
        assert len(portfolio) == 1
        assert portfolio[0]["symbol"] == "FPT"
        assert len(watchlist) == 1
        assert watchlist[0]["symbol"] == "SSI"
