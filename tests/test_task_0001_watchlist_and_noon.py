"""
Unit tests for TASK-0001:
1. Noon report (11:30) 5-questions completeness, session title, and Question 5 fallback sanity check.
2. Automated Watchlist Discovery & Sync (sync_auto_watchlist) with manual preservation and Data Gate filters.
"""

import json
from unittest import mock

import pandas as pd

from ai_analyst import generate_portfolio_analysis
from data_engine import prune_unsuitable_watchlist, sync_auto_watchlist

# =====================================================================
# 1. KIỂM THỬ BÁO CÁO PHIÊN NGHỈ TRƯA (11:30) & 5 CÂU HỎI CỐT TỬ
# =====================================================================

@mock.patch("ai_analyst.call_gemini")
def test_generate_portfolio_analysis_noon_session_title_and_prompt(mock_call_gemini):
    """Test báo cáo phiên trưa đổi đúng tiêu đề phiên sáng và ngữ cảnh 11:30."""
    captured_prompt = {}

    def side_effect(client, prompt):
        captured_prompt["text"] = prompt
        return (
            "**I. TỔNG KẾT PHIÊN SÁNG (NGHỈ TRƯA) & ĐÁNH GIÁ 5 CÂU HỎI CỐT TỬ**\n"
            "- **Câu hỏi 1 (Nguyên nhân biến động):** VN-Index giằng co.\n"
            "- **Câu hỏi 2 (Định giá & MoS):** FPT còn rẻ.\n"
            "- **Câu hỏi 3 (Chốt lời & Trailing Stop):** Giữ nguyên stoploss.\n"
            "- **Câu hỏi 4 (Thesis Breaker):** Luận điểm an toàn.\n"
            "- **Câu hỏi 5 (Tỷ trọng Tiền/Cổ phiếu):** Cổ phiếu 70% / Tiền 30%.\n\n"
            "**II. CHI TIẾT DANH MỤC & HÀNH ĐỘNG QUẢN TRỊ RỦI RO**"
        )

    mock_call_gemini.side_effect = side_effect

    portfolio_df = pd.DataFrame([{"Mã CP": "FPT", "Thị giá (k)": 130.0, "Giá vốn (k)": 120.0, "Lãi/Lỗ (%)": 8.3}])
    res = generate_portfolio_analysis(portfolio_df, [], session_label="NOON")

    assert "TỔNG KẾT PHIÊN SÁNG (NGHỈ TRƯA)" in captured_prompt["text"]
    assert "11:30 TRƯA" in captured_prompt["text"]
    assert "Câu hỏi 1" in res
    assert "Câu hỏi 2" in res
    assert "Câu hỏi 3" in res
    assert "Câu hỏi 4" in res
    assert "Câu hỏi 5" in res


@mock.patch("ai_analyst.call_gemini")
def test_generate_portfolio_analysis_noon_fallback_q5_with_double_star(mock_call_gemini):
    """Test nếu Gemini nuốt Câu hỏi 5 thì Fallback tự động chèn trước **II."""
    mock_call_gemini.return_value = (
        "**I. TỔNG KẾT PHIÊN SÁNG (NGHỈ TRƯA) & ĐÁNH GIÁ 5 CÂU HỎI CỐT TỬ**\n"
        "- **Câu hỏi 1:** Biến động nhẹ.\n"
        "- **Câu hỏi 2:** Định giá tốt.\n"
        "- **Câu hỏi 3:** Nâng trailing stop.\n"
        "- **Câu hỏi 4:** Không vi phạm.\n\n"
        "**II. CHI TIẾT DANH MỤC & HÀNH ĐỘNG QUẢN TRỊ RỦI RO**"
    )

    portfolio_df = pd.DataFrame([{"Mã CP": "HPG", "Thị giá (k)": 28.0, "Giá vốn (k)": 26.0, "Lãi/Lỗ (%)": 7.7}])
    res = generate_portfolio_analysis(portfolio_df, [], session_label="11:30")

    assert "Câu hỏi 5" in res
    assert "**II. CHI TIẾT DANH MỤC" in res
    # Vị trí Câu hỏi 5 phải đứng trước **II.
    idx_q5 = res.find("Câu hỏi 5")
    idx_p2 = res.find("**II. CHI TIẾT DANH MỤC")
    assert idx_q5 < idx_p2


@mock.patch("ai_analyst.call_gemini")
def test_generate_portfolio_analysis_fallback_q5_with_pin_icon(mock_call_gemini):
    """Test fallback chèn trước 📌 II. nếu LLM trả về format icon."""
    mock_call_gemini.return_value = (
        "I. TỔNG KẾT PHIÊN\n"
        "- Câu hỏi 1: OK.\n"
        "- Câu hỏi 4: Không có rủi ro.\n\n"
        "📌 II. CHI TIẾT DANH MỤC"
    )

    portfolio_df = pd.DataFrame([{"Mã CP": "SSI", "Thị giá (k)": 35.0, "Giá vốn (k)": 32.0, "Lãi/Lỗ (%)": 9.4}])
    res = generate_portfolio_analysis(portfolio_df, [], session_label="ATC")

    assert "Câu hỏi 5" in res
    assert "📌 II." in res
    assert res.find("Câu hỏi 5") < res.find("📌 II.")


# =====================================================================
# 2. KIỂM THỬ TỰ ĐỘNG KHÁM PHÁ & ĐỒNG BỘ WATCHLIST (SYNC AUTO WATCHLIST)
# =====================================================================

def test_sync_auto_watchlist_preserves_manual_items(tmp_path):
    """Test bảo toàn 100% các mã do người dùng tự nhập tay trong Watchlist."""
    wl_file = tmp_path / "watchlist.json"
    initial_watchlist = [
        {"symbol": "HPG", "target_buy": 27.5, "note": "Tôi tự thêm tay", "is_auto": False},
        {"symbol": "MWG", "target_buy": 60.0, "note": "Chiến lược bán lẻ"}
    ]
    with open(wl_file, "w", encoding="utf-8") as f:
        json.dump(initial_watchlist, f)

    mock_opportunities = [
        {
            "symbol": "FPT",
            "current_price": 135.0,
            "target_price": 150.0,
            "conviction_score": 85.0,
            "mos_pct": 20.0,
            "status": "RECOMMEND_BUY"
        },
        {
            "symbol": "HPG",  # Trùng với mã manual của user
            "current_price": 28.0,
            "target_price": 32.0,
            "conviction_score": 90.0,
            "mos_pct": 18.0,
            "status": "RECOMMEND_BUY"
        }
    ]

    updated = sync_auto_watchlist(opportunities=mock_opportunities, filepath=str(wl_file), max_auto=3)

    symbols = [x["symbol"] for x in updated]
    assert "HPG" in symbols
    assert "MWG" in symbols
    assert "FPT" in symbols

    # Mã HPG của user không bị biến thành mã auto và giữ nguyên nội dung gốc
    hpg_item = next(x for x in updated if x["symbol"] == "HPG")
    assert "Tôi tự thêm tay" in hpg_item["note"]
    assert hpg_item.get("is_auto", False) is False

    # Mã FPT được thêm mới với cờ is_auto
    fpt_item = next(x for x in updated if x["symbol"] == "FPT")
    assert fpt_item["is_auto"] is True
    assert "[AUTO_DISCOVERY]" in fpt_item["note"]


def test_sync_auto_watchlist_caps_max_auto(tmp_path):
    """Test số lượng mã tự động thêm vào không vượt quá max_auto."""
    wl_file = tmp_path / "watchlist.json"
    with open(wl_file, "w", encoding="utf-8") as f:
        json.dump([], f)

    opportunities = [
        {"symbol": f"M{i}", "current_price": 20.0 + i, "conviction_score": 75.0, "mos_pct": 16.0, "status": "RECOMMEND_BUY"}
        for i in range(10)
    ]

    updated = sync_auto_watchlist(opportunities=opportunities, filepath=str(wl_file), max_auto=4)

    assert len(updated) == 4
    for item in updated:
        assert item["is_auto"] is True


def test_sync_auto_watchlist_filters_out_data_gate_rejects(tmp_path):
    """Test loại bỏ hoàn toàn các mã vi phạm Data Gate (CAUTION_TRAP / DATA_CONFLICT)."""
    wl_file = tmp_path / "watchlist.json"
    with open(wl_file, "w", encoding="utf-8") as f:
        json.dump([], f)

    opportunities = [
        {
            "symbol": "VCB",
            "current_price": 90.0,
            "conviction_score": 80.0,
            "mos_pct": 25.0,
            "status": "CAUTION_TRAP"  # Bị Data Gate chặn
        },
        {
            "symbol": "SSI",
            "current_price": 35.0,
            "conviction_score": 78.0,
            "mos_pct": 18.0,
            "status": "RECOMMEND_BUY"
        }
    ]

    updated = sync_auto_watchlist(opportunities=opportunities, filepath=str(wl_file), max_auto=5)

    symbols = [x["symbol"] for x in updated]
    assert "SSI" in symbols
    assert "VCB" not in symbols


def test_sync_auto_watchlist_graceful_on_missing_file(tmp_path):
    """Test khởi tạo an toàn khi file watchlist chưa tồn tại."""
    wl_file = tmp_path / "non_existent_watchlist.json"
    assert not wl_file.exists()

    opportunities = [
        {"symbol": "TCB", "current_price": 25.0, "conviction_score": 82.0, "mos_pct": 22.0, "status": "RECOMMEND_BUY"}
    ]

    updated = sync_auto_watchlist(opportunities=opportunities, filepath=str(wl_file), max_auto=2)
    assert len(updated) == 1
    assert updated[0]["symbol"] == "TCB"
    assert wl_file.exists()


# =====================================================================
# 3. KIỂM THỬ THANH LỌC CỔ PHIẾU QUÁ HOT HOẶC KHÔNG PHÙ HỢP (PRUNE)
# =====================================================================

def test_prune_unsuitable_watchlist_removes_overheated_auto(tmp_path):
    """Test mã auto bị quá mua (RSI > 75) hoặc MoS < -25% tự động bị xóa khỏi Watchlist."""
    wl_file = tmp_path / "watchlist.json"
    initial = [
        {"symbol": "HOT1", "target_buy": 50.0, "is_auto": True, "note": "[AUTO_DISCOVERY] Cổ phiếu A"},
        {"symbol": "HOT2", "target_buy": 30.0, "is_auto": True, "note": "[AUTO_DISCOVERY] Cổ phiếu B"},
        {"symbol": "SAFE1", "target_buy": 20.0, "is_auto": True, "note": "[AUTO_DISCOVERY] Cổ phiếu C"},
    ]
    with open(wl_file, "w", encoding="utf-8") as f:
        json.dump(initial, f)

    mock_tech = {
        "HOT1": {"current_price": 60.0, "rsi14": 82.0, "trap_info": {"is_trap": False}},  # Quá mua RSI > 75
        "HOT2": {"current_price": 45.0, "rsi14": 65.0, "trap_info": {"is_trap": False}},  # Sẽ có MoS âm sâu
        "SAFE1": {"current_price": 20.0, "rsi14": 55.0, "trap_info": {"is_trap": False}},
    }

    with mock.patch("quant_valuation.calculate_fair_value_and_mos") as mock_val:
        def val_side_effect(symbol, current_price, sector):
            if symbol == "HOT2":
                return {"fair_value": 30.0, "mos_pct": -33.3}  # MoS < -25%
            return {"fair_value": current_price * 1.2, "mos_pct": 20.0}

        mock_val.side_effect = val_side_effect

        retained, pruned = prune_unsuitable_watchlist(filepath=str(wl_file), tech_map=mock_tech)

        retained_syms = [x["symbol"] for x in retained]
        pruned_syms = [x["symbol"] for x in pruned]

        assert "SAFE1" in retained_syms
        assert "HOT1" in pruned_syms
        assert "HOT2" in pruned_syms
        assert "HOT1" not in retained_syms
        assert "HOT2" not in retained_syms


def test_prune_unsuitable_watchlist_removes_trap_auto(tmp_path):
    """Test mã auto dính bẫy giá (is_trap == True) tự động bị thanh lọc."""
    wl_file = tmp_path / "watchlist.json"
    initial = [
        {"symbol": "TRAP1", "target_buy": 25.0, "is_auto": True, "note": "[AUTO_DISCOVERY]"},
        {"symbol": "GOOD1", "target_buy": 40.0, "is_auto": True, "note": "[AUTO_DISCOVERY]"}
    ]
    with open(wl_file, "w", encoding="utf-8") as f:
        json.dump(initial, f)

    mock_tech = {
        "TRAP1": {"current_price": 24.0, "rsi14": 50.0, "trap_info": {"is_trap": True, "trap_type": "BULL_TRAP"}},
        "GOOD1": {"current_price": 40.0, "rsi14": 52.0, "trap_info": {"is_trap": False}}
    }

    retained, pruned = prune_unsuitable_watchlist(filepath=str(wl_file), tech_map=mock_tech)

    assert len(retained) == 1
    assert retained[0]["symbol"] == "GOOD1"
    assert len(pruned) == 1
    assert pruned[0]["symbol"] == "TRAP1"
    assert "Dính bẫy giá" in pruned[0]["reason"]


def test_prune_unsuitable_watchlist_warns_manual_item_without_deleting(tmp_path):
    """Test mã thủ công của người dùng không bị xóa, chỉ được gắn cờ cảnh báo rủi ro."""
    wl_file = tmp_path / "watchlist.json"
    initial = [
        {"symbol": "MY_STOCK", "target_buy": 100.0, "is_auto": False, "note": "Hàng chiến lược dài hạn"}
    ]
    with open(wl_file, "w", encoding="utf-8") as f:
        json.dump(initial, f)

    mock_tech = {
        "MY_STOCK": {"current_price": 120.0, "rsi14": 79.0, "trap_info": {"is_trap": False}}
    }

    retained, pruned = prune_unsuitable_watchlist(filepath=str(wl_file), tech_map=mock_tech, prune_manual=False)

    # Không bị xóa
    assert len(retained) == 1
    assert len(pruned) == 0
    assert retained[0]["symbol"] == "MY_STOCK"
    # Ghi chú được gắn thêm cảnh báo
    assert "[⚠️ CẢNH BÁO:" in retained[0]["note"]
    assert "Hàng chiến lược dài hạn" in retained[0]["note"]

