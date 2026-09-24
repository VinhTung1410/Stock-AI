from unittest.mock import patch

import pandas as pd

from data_engine import (
    _parse_period_year_quarter,
    compute_pb,
    get_financial_ratios,
    resolve_sector_key,
)
from data_gate import reconcile_data
from quant_valuation import calculate_fair_value_and_mos


def test_pb_vcb_sept_2026():
    """Kiểm tra P/B của VCB nằm trong ngưỡng hợp lý (1.5 - 2.8x) theo Vietcap/HSC/BSC/TCBS."""
    mock_fin = {"bvps": 25.0, "pb": 2.33, "period": "2026-Q2"}
    mock_board = pd.DataFrame({("match", "match_price"): [58.25]})
    with patch("data_engine.get_financial_ratios", return_value=mock_fin), \
         patch("vnstock.Trading.price_board", return_value=mock_board):
        result = compute_pb("VCB", as_of_date="2026-09-23")
        assert result is not None, "P/B của VCB không được là None"
        assert 1.5 <= result <= 2.8, f"P/B={result} vượt ngưỡng hợp lý đã biết của VCB"


def test_pb_tcb_sept_2026():
    """Kiểm tra P/B của TCB nằm trong ngưỡng hợp lý (0.7 - 2.0x) theo TCBS/Vietcap."""
    mock_fin = {"bvps": 24.5, "pb": 1.12, "period": "2026-Q2"}
    mock_board = pd.DataFrame({("match", "match_price"): [27.44]})
    with patch("data_engine.get_financial_ratios", return_value=mock_fin), \
         patch("vnstock.Trading.price_board", return_value=mock_board):
        result = compute_pb("TCB", as_of_date="2026-09-23")
        assert result is not None, "P/B của TCB không được là None"
        assert 0.7 <= result <= 2.0, f"P/B={result} vượt ngưỡng hợp lý đã biết của TCB"


def test_pb_guardrail_blocks_abnormal_valuation():
    """Chốt chặn Guardrail phải phát hiện và chặn định giá bất thường (P/B=4.06x trên VCB)."""
    # 1. Test trong quant_valuation: Khi P/B=4.06x (ngoài ngưỡng 0.8-3.0x của bank_soe)
    val = calculate_fair_value_and_mos(
        symbol="VCB",
        current_price=58.9,
        fin_dict={"pb": 4.06, "roe": 16.7},
        sector="Ngân hàng"
    )
    assert val["valuation_rating"] == "CẦN XÁC MINH THỦ CÔNG"
    assert val["fair_value"] == 0.0
    assert "data_integrity_warning" in val

    # 2. Test trong data_gate: Reconcile data phải chặn recommendation
    gate_res = reconcile_data(
        symbol="VCB",
        tech_data={"current_price": 58.9, "sector": "Ngân hàng"},
        fin_data={"pb": 4.06, "roe": 16.7, "pe": 12.0, "f_score": 7, "z_score": 3.0, "period": "2026-Q2"}
    )
    assert gate_res["recommendation_allowed"] is False
    assert any("CẦN XÁC MINH THỦ CÔNG" in msg for msg in gate_res["conflicting_data"])


def test_pb_guardrail_allows_normal_valuation():
    """Guardrail phải cho phép định giá khi P/B nằm trong ngưỡng an toàn."""
    val = calculate_fair_value_and_mos(
        symbol="VCB",
        current_price=58.9,
        fin_dict={"pb": 2.33, "roe": 16.7},
        sector="Ngân hàng"
    )
    assert val["valuation_rating"] != "CẦN XÁC MINH THỦ CÔNG"
    assert val["fair_value"] > 0.0


def test_stale_vci_2018_data_is_rejected():
    """Hệ thống phải tự động từ chối dữ liệu bị đóng băng từ 2018 của VCI."""
    df_mock = pd.DataFrame({
        "item": ["P/B", "P/E", "ROE (%)"],
        "2018-Q4": [4.06, 16.75, 25.46]
    })
    with patch("data_engine._extract_kbs_ratios", return_value={}), \
         patch("vnstock.Vnstock") as mock_vnstock:
        mock_instance = mock_vnstock.return_value
        mock_v = mock_instance.stock.return_value
        mock_v.finance.ratio.return_value = df_mock
        ratios = get_financial_ratios("VCB")
        # P/B phải bị loại bỏ (None) vì 2018 quá cũ
        assert ratios.get("pb") is None
        assert ratios.get("audit_trail", {}).get("is_stale_legacy") is True


def test_resolve_sector_key():
    """Kiểm tra phân loại nhóm ngành áp dụng sanity range."""
    assert resolve_sector_key("VCB") == "bank_soe"
    assert resolve_sector_key("CTG") == "bank_soe"
    assert resolve_sector_key("TCB") == "bank_private"
    assert resolve_sector_key("ACB") == "bank_private"
    assert resolve_sector_key("VHM") == "real_estate"
    assert resolve_sector_key("FPT") == "default"


def test_parse_period_year_quarter():
    """Kiểm tra phân tích năm/quý từ chuỗi kỳ báo cáo."""
    assert _parse_period_year_quarter("2026-Q2") == (2026, 2)
    assert _parse_period_year_quarter("2025-Q4") == (2025, 4)
    assert _parse_period_year_quarter("2024") == (2024, 4)
    assert _parse_period_year_quarter(None) == (None, None)
