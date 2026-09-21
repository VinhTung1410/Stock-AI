from unittest import mock

import pandas as pd
import pytest

from ai_analyst import generate_portfolio_analysis
from data_engine import fetch_corporate_dividends

pytestmark = pytest.mark.offline


def test_fetch_corporate_dividends_success():
    """Test lấy cổ tức thành công, mock Vnstock."""
    with mock.patch("vnstock.Vnstock") as MockVnstock:
        # Giả lập DataFrame trả về
        mock_df = pd.DataFrame({
            "ex_right_date": ["2026-09-21"],
            "exercise_date": ["2026-10-15"],
            "value": [2000]
        })
        mock_stock_instance = MockVnstock.return_value.stock.return_value
        mock_stock_instance.company.dividends.return_value = mock_df
        
        df = fetch_corporate_dividends("FPT")
        assert df is not None
        assert len(df) == 1
        assert df.iloc[0]["ex_right_date"] == "2026-09-21"


def test_fetch_corporate_dividends_exception():
    """Test lỗi lấy cổ tức."""
    with mock.patch("vnstock.Vnstock") as MockVnstock:
        MockVnstock.side_effect = Exception("Network Error")
        df = fetch_corporate_dividends("FPT")
        assert df is None


@mock.patch("ai_analyst.call_gemini")
def test_generate_portfolio_analysis_fallback_q5(mock_call_gemini):
    """Test AI Analyst nếu Gemini nuốt chữ Câu 5 thì Regex Fallback phải chèn vào."""
    # Giả lập Gemini trả về thiếu câu 5, nhưng có đánh dấu 📌 II.
    mock_call_gemini.return_value = "I. TỔNG KẾT PHIÊN\n- Câu hỏi 1: Tăng.\n- Câu hỏi 4: Không.\n\n📌 II. CHI TIẾT DANH MỤC"
    
    # Tạo dummy df
    portfolio_df = pd.DataFrame([{"Mã CP": "FPT", "Thị giá (k)": 100, "Giá vốn (k)": 90, "Lãi/Lỗ (%)": 11.1}])
    
    result = generate_portfolio_analysis(portfolio_df, [])
    
    # Đảm bảo fallback đã chèn Câu hỏi 5 vào đúng chỗ
    assert "Câu hỏi 5" in result
    assert "📌 II." in result


def test_trading_bot_value_strategy_skips_stoploss():
    """Test _check_single_holding_risk bỏ qua MA20 và StopLoss cho strategy VALUE."""
    from trading_bot import _check_single_holding_risk
    
    row = {
        "Mã CP": "FPT",
        "Thị giá (k)": 80.0,
        "Giá vốn (k)": 100.0,  # Lỗ 20%
        "Lãi/Lỗ (%)": -20.0,
        "Chiến lược": "VALUE",
        "Vị thế MA20": "DƯỚI",
        "Vol/TB20": 2.0
    }
    
    with mock.patch("data_engine.fetch_stock_technical") as mock_tech:
        mock_tech.return_value = {"current_price": 80.0}
        with mock.patch("data_engine.detect_gdkhq_event") as mock_gdkhq:
            mock_gdkhq.return_value = {"is_gdkhq": False}
            with mock.patch("trading_bot._handle_stop_loss") as mock_sl:
                with mock.patch("trading_bot._handle_ma20_breakdown") as mock_ma20:
                    _check_single_holding_risk(row, "2026-09-21", -1.0)
                    
                    # Cả 2 hàm cắt lỗ và MA20 đều KHÔNG được gọi vì chiến lược là VALUE
                    mock_sl.assert_not_called()
                    mock_ma20.assert_not_called()


def test_sync_corporate_actions():
    """Test đồng bộ cổ tức trong scripts/sync_corporate_actions.py."""
    from scripts.sync_corporate_actions import (
        _check_and_notify_gdkhq,
        _get_gdkhq_column,
        sync_corporate_actions,
    )

    # 1. Test _get_gdkhq_column
    assert _get_gdkhq_column(pd.DataFrame(columns=["ex_right_date"])) == "ex_right_date"
    assert _get_gdkhq_column(pd.DataFrame(columns=["unknown_col"])) is None

    # 2. Test _check_and_notify_gdkhq with None df
    with mock.patch("scripts.sync_corporate_actions.fetch_corporate_dividends", return_value=None):
        assert not _check_and_notify_gdkhq("FPT", 100.0, "2026-09-21")

    # 3. Test _check_and_notify_gdkhq with matching event
    matching_df = pd.DataFrame({"ex_right_date": ["2026-09-21"]})
    with mock.patch("scripts.sync_corporate_actions.fetch_corporate_dividends", return_value=matching_df):
        with mock.patch("scripts.sync_corporate_actions.get_supabase_client", return_value=mock.MagicMock()):
            assert _check_and_notify_gdkhq("FPT", 100.0, "2026-09-21")

    # 4. Test _check_and_notify_gdkhq exception handling
    with mock.patch("scripts.sync_corporate_actions.fetch_corporate_dividends", side_effect=Exception("DB fail")):
        assert not _check_and_notify_gdkhq("FPT", 100.0, "2026-09-21")

    # 5. Test sync_corporate_actions with empty portfolio
    with mock.patch("scripts.sync_corporate_actions.load_portfolio", return_value=[]):
        sync_corporate_actions()

    # 6. Test sync_corporate_actions with active update
    sample_portfolio = [{"symbol": "FPT", "cost_price": 100.0}]
    with mock.patch("scripts.sync_corporate_actions.load_portfolio", return_value=sample_portfolio):
        with mock.patch("scripts.sync_corporate_actions._check_and_notify_gdkhq", return_value=True):
            with mock.patch("scripts.sync_corporate_actions.save_portfolio") as mock_save:
                sync_corporate_actions()
                mock_save.assert_called_once_with(sample_portfolio)
