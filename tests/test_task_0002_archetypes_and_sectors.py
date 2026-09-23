"""
Unit tests for TASK-0002:
1. Archetype classification & metadata details (GROWTH_COMPOUNDER, CYCLICAL, BANK, REAL_ESTATE).
2. Protection of Value/Compounder holdings (e.g. FPT, MWG) against premature MA20 & short-term stop-loss triggers.
3. Sector-based Watchlist evaluation & grouping (group_watchlist_by_sector).
4. Auto-Watchlist discovery enrichment with sector & archetype metadata.
"""

import json
from unittest import mock

import pandas as pd

from data_engine import evaluate_watchlist, group_watchlist_by_sector, sync_auto_watchlist
from quant_valuation import get_stock_archetype_details
from trading_bot import _check_single_holding_risk, sent_alerts

# =====================================================================
# 1. KIỂM THỬ PHÂN LOẠI ARCHETYPE & METADATA CHI TIẾT
# =====================================================================

def test_archetype_classification_and_metadata():
    """Kiểm tra phân loại đúng 4 Archetype và gán đúng chiến lược & mô hình định giá."""
    # FPT -> Compounder tăng trưởng
    fpt_info = get_stock_archetype_details("FPT", "Công nghệ")
    assert fpt_info["archetype"] == "GROWTH_COMPOUNDER"
    assert fpt_info["default_strategy"] == "VALUE"
    assert fpt_info["holding_shield"] is True
    assert "P/E" in fpt_info["valuation_model"]

    # HPG -> Hàng hóa chu kỳ
    hpg_info = get_stock_archetype_details("HPG", "Thép")
    assert hpg_info["archetype"] == "CYCLICAL"
    assert hpg_info["default_strategy"] == "CYCLICAL"
    assert hpg_info["holding_shield"] is False
    assert "Mid-Cycle" in hpg_info["valuation_model"]

    # VCB -> Ngân hàng
    vcb_info = get_stock_archetype_details("VCB", "Ngân hàng")
    assert vcb_info["archetype"] == "BANK"
    assert vcb_info["default_strategy"] == "FINANCIAL"
    assert "P/B" in vcb_info["valuation_model"]

    # VHM -> Bất động sản
    vhm_info = get_stock_archetype_details("VHM", "Bất động sản")
    assert vhm_info["archetype"] == "REAL_ESTATE"
    assert "RNAV" in vhm_info["valuation_model"]


# =====================================================================
# 2. KIỂM THỬ BẢO VỆ VỊ THẾ DÀI HẠN (FPT KHÔNG BỊ BÁN NON)
# =====================================================================

@mock.patch("trading_bot.send_trade_signal_alert")
@mock.patch("data_engine.fetch_stock_technical")
def test_fpt_growth_compounder_ignores_ma20_breakdown(mock_fetch_tech, mock_send_alert):
    """Test FPT gãy MA20 với volume đột biến KHÔNG bị kích hoạt lệnh bán cắt lỗ."""
    mock_fetch_tech.return_value = {
        "current_price": 128.0,
        "status_ma20": "DƯỚI MA20",
        "vol_ratio": 2.5,  # Bán tháo vol lớn
        "rsi14": 45.0,
        "trap_info": {"is_trap": False}
    }

    row = {
        "Mã CP": "FPT",
        "Thị giá (k)": 128.0,
        "Giá vốn (k)": 135.0,
        "Lãi/Lỗ (%)": -5.19,  # Lỗ nhẹ -5%
        "Vol/TB20": 2.5,
        "Vị thế MA20": "DƯỚI MA20",
        "RSI(14)": 45.0,
        "Chiến lược": "SWING",  # Dù user chưa set VALUE, hệ thống tự nhận diện FPT là COMPOUNDER
        "Ngành": "Công nghệ"
    }

    sent_alerts.clear()
    _check_single_holding_risk(row, "2026-09-24", vnindex_chg_pct=-0.5)

    # KHÔNG được gửi bất kỳ tín hiệu BÁN nào
    mock_send_alert.assert_not_called()


@mock.patch("trading_bot.send_trade_signal_alert")
@mock.patch("data_engine.fetch_stock_technical")
def test_fpt_value_holding_triggers_alert_on_deep_loss(mock_fetch_tech, mock_send_alert):
    """Test FPT nếu lỗ sâu quá ngưỡng an toàn (> 15%) thì kích hoạt cảnh báo rà soát."""
    mock_fetch_tech.return_value = {
        "current_price": 110.0,
        "status_ma20": "DƯỚI MA20",
        "vol_ratio": 1.0,
        "rsi14": 30.0,
        "trap_info": {"is_trap": False}
    }

    row = {
        "Mã CP": "FPT",
        "Thị giá (k)": 110.0,
        "Giá vốn (k)": 135.0,
        "Lãi/Lỗ (%)": -18.5,  # Lỗ sâu -18.5%
        "Vol/TB20": 1.0,
        "Vị thế MA20": "DƯỚI MA20",
        "RSI(14)": 30.0,
        "Chiến lược": "VALUE",
        "Ngành": "Công nghệ"
    }

    sent_alerts.clear()
    _check_single_holding_risk(row, "2026-09-24", vnindex_chg_pct=-1.0)

    # ĐƯỢC gửi cảnh báo rủi ro sâu
    assert mock_send_alert.called
    args = mock_send_alert.call_args[0]
    assert args[0] == "FPT"
    assert args[1] == "CẢNH BÁO"


# =====================================================================
# 3. KIỂM THỬ METADATA NGÀNH TRONG WATCHLIST & GOM NHÓM THEO NGÀNH
# =====================================================================

@mock.patch("data_engine.fetch_stock_technical")
def test_evaluate_watchlist_enriches_sector_archetype(mock_fetch_tech):
    """Test evaluate_watchlist bổ sung đầy đủ Cụm ngành, Archetype, Chiến lược và Mô hình định giá."""
    mock_fetch_tech.return_value = {
        "current_price": 100.0,
        "change_pct": 1.5,
        "status_ma20": "TRÊN MA20",
        "vol_ratio": 1.2,
        "rsi14": 55.0,
        "foreign_flow": {"net_val_bil": 15.0},
        "trap_info": {"is_trap": False}
    }

    watchlist = [
        {"symbol": "FPT", "target_buy": 120.0, "note": "Công nghệ thông tin"},
        {"symbol": "HPG", "target_buy": 26.0, "note": "Sản xuất thép"},
        {"symbol": "TCB", "target_buy": 22.0, "note": "Ngân hàng TMCP"}
    ]

    df = evaluate_watchlist(watchlist)

    assert "Cụm ngành" in df.columns
    assert "Archetype" in df.columns
    assert "Chiến lược" in df.columns
    assert "Mô hình định giá" in df.columns

    fpt_row = df[df["Mã CP"] == "FPT"].iloc[0]
    assert fpt_row["Archetype"] == "GROWTH_COMPOUNDER"
    assert "Công nghệ" in fpt_row["Cụm ngành"]

    hpg_row = df[df["Mã CP"] == "HPG"].iloc[0]
    assert hpg_row["Archetype"] == "CYCLICAL"

    tcb_row = df[df["Mã CP"] == "TCB"].iloc[0]
    assert tcb_row["Archetype"] == "BANK"


def test_group_watchlist_by_sector():
    """Test hàm group_watchlist_by_sector gom nhóm DataFrame chuẩn xác theo từng ngành."""
    data = [
        {"Mã CP": "FPT", "Cụm ngành": "💻 Công nghệ & Tiêu dùng Tăng trưởng", "Thị giá (k)": 130.0},
        {"Mã CP": "MWG", "Cụm ngành": "💻 Công nghệ & Tiêu dùng Tăng trưởng", "Thị giá (k)": 65.0},
        {"Mã CP": "HPG", "Cụm ngành": "🏭 Hàng hóa & Sản xuất Chu kỳ", "Thị giá (k)": 28.0},
    ]
    df = pd.DataFrame(data)

    grouped = group_watchlist_by_sector(df)

    assert len(grouped) == 2
    assert "💻 Công nghệ & Tiêu dùng Tăng trưởng" in grouped
    assert "🏭 Hàng hóa & Sản xuất Chu kỳ" in grouped
    assert len(grouped["💻 Công nghệ & Tiêu dùng Tăng trưởng"]) == 2
    assert len(grouped["🏭 Hàng hóa & Sản xuất Chu kỳ"]) == 1


def test_sync_auto_watchlist_enriches_sector_archetype(tmp_path):
    """Test sync_auto_watchlist gắn kèm đầy đủ sector, archetype và strategy vào từng item mới."""
    wl_file = tmp_path / "watchlist.json"
    with open(wl_file, "w", encoding="utf-8") as f:
        json.dump([], f)

    mock_opportunities = [
        {
            "symbol": "FPT",
            "current_price": 135.0,
            "target_price": 150.0,
            "conviction_score": 88.0,
            "mos_pct": 22.0,
            "status": "RECOMMEND_BUY",
            "sector": "Công nghệ"
        },
        {
            "symbol": "BSR",
            "current_price": 24.0,
            "target_price": 28.0,
            "conviction_score": 80.0,
            "mos_pct": 18.0,
            "status": "RECOMMEND_BUY",
            "sector": "Dầu khí"
        }
    ]

    updated = sync_auto_watchlist(opportunities=mock_opportunities, filepath=str(wl_file), max_auto=5)

    assert len(updated) == 2
    fpt_item = next(x for x in updated if x["symbol"] == "FPT")
    assert fpt_item["archetype"] == "GROWTH_COMPOUNDER"
    assert fpt_item["strategy"] == "VALUE"

    bsr_item = next(x for x in updated if x["symbol"] == "BSR")
    assert bsr_item["archetype"] == "CYCLICAL"
    assert bsr_item["strategy"] == "CYCLICAL"
