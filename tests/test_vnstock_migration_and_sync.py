import os
from unittest import mock

import pandas as pd

from data_engine import (
    _SESSION_PRUNED_SYMBOLS,
    fetch_foreign_trading_flow,
    get_financial_ratios,
    get_shares_outstanding,
    load_watchlist,
    prune_unsuitable_watchlist,
)


def test_get_financial_ratios_with_modern_api():
    """Kiểm tra get_financial_ratios tương thích với vnstock.api.financial.Finance."""
    mock_df_kbs = pd.DataFrame(
        {
            "item": [
                "Chỉ số giá thị trường trên thu nhập (P/E)",
                "Chỉ số giá thị trường trên giá trị sổ sách (P/B)",
                "Giá trị sổ sách của cổ phiếu (BVPS)",
                "ROE bình quân 4 quý gần nhất",
            ],
            "2026-Q2": [15.5, 2.1, 30000.0, 22.5],
        }
    )
    from data_engine import _financial_cache
    _financial_cache.clear()

    with mock.patch("vnstock.api.financial.Finance.ratio", return_value=mock_df_kbs):
        ratios = get_financial_ratios("FPT")
        assert ratios["symbol"] == "FPT"
        assert ratios["period"] == "2026-Q2"
        assert ratios["pe"] == 15.5
        assert ratios["pb"] == 2.1
        assert ratios["bvps"] == 30000.0
        assert ratios["roe"] == 22.5


def test_get_shares_outstanding_with_modern_api():
    """Kiểm tra get_shares_outstanding tương thích với vnstock.api.company.Company."""
    mock_ov = pd.DataFrame([{"issue_share": 1885759064.0}])
    with mock.patch("vnstock.api.company.Company.overview", return_value=mock_ov):
        shares = get_shares_outstanding("FPT")
        assert shares == 1885759064.0


def test_fetch_foreign_flow_with_modern_api():
    """Kiểm tra fetch_foreign_trading_flow tương thích với vnstock.api.trading.Trading."""
    mock_board = pd.DataFrame(
        [
            {
                ("match", "foreign_buy_value"): 50e9,
                ("match", "foreign_sell_value"): 20e9,
                ("match", "foreign_buy_volume"): 500000,
                ("match", "foreign_sell_volume"): 200000,
            }
        ]
    )
    with mock.patch("vnstock.api.trading.Trading.price_board", return_value=mock_board):
        flow = fetch_foreign_trading_flow("FPT")
        assert flow["buy_val_bil"] == 50.0
        assert flow["sell_val_bil"] == 20.0
        assert flow["net_val_bil"] == 30.0
        assert "Mua ròng" in flow["status_vi"]


def test_load_watchlist_intelligent_merge(tmp_path):
    """Kiểm tra load_watchlist giữ lại các mã is_auto: True khi Google Sheet tải về."""
    test_json = tmp_path / "test_watchlist.json"
    local_initial = [
        {"symbol": "MSR", "target_buy": 50.0, "is_auto": False, "note": "Thủ công cũ"},
        {"symbol": "TCB", "target_buy": 32.0, "is_auto": True, "note": "[AUTO_DISCOVERY] Điểm 75/100"},
    ]
    import json

    with open(test_json, "w", encoding="utf-8") as f:
        json.dump(local_initial, f)

    sheet_data = [
        {"symbol": "MSR", "target_buy": 52.0, "note": "Thủ công mới từ Sheet"},
        {"symbol": "HPG", "target_buy": 25.0, "note": "Thủ công thêm trên Sheet"},
    ]

    with (
        mock.patch.dict(os.environ, {"GOOGLE_SHEET_URL": "https://docs.google.com/test"}),
        mock.patch("data_engine.PATH_WATCHLIST_JSON", str(test_json)),
        mock.patch("data_engine.fetch_google_sheet_data", return_value=([], sheet_data)),
    ):
        merged = load_watchlist(filepath=str(test_json))
        symbols = [item["symbol"] for item in merged]
        assert "MSR" in symbols
        assert "HPG" in symbols
        assert "TCB" in symbols  # Mã tự động phải được giữ lại
        tcb_item = next(it for it in merged if it["symbol"] == "TCB")
        assert tcb_item["is_auto"] is True


def test_prune_and_blacklist_in_session(tmp_path):
    """Kiểm tra khi thanh lọc: ghi nhận mã vào _SESSION_PRUNED_SYMBOLS và không bị hồi sinh."""
    test_json = tmp_path / "test_wl_prune.json"
    import json

    initial = [
        {"symbol": "FOMO_STOCK", "target_buy": 100.0, "is_auto": True, "note": "Hot"},
        {"symbol": "SAFE_STOCK", "target_buy": 50.0, "is_auto": False, "note": "An toan"},
    ]
    with open(test_json, "w", encoding="utf-8") as f:
        json.dump(initial, f)

    fake_tech_map = {
        "FOMO_STOCK": {"current_price": 100.0, "rsi14": 85.0},  # RSI > 75 FOMO
        "SAFE_STOCK": {"current_price": 50.0, "rsi14": 50.0},
    }

    _SESSION_PRUNED_SYMBOLS.clear()
    with (
        mock.patch("data_engine.fetch_stock_technical", side_effect=lambda s: fake_tech_map.get(s, {})),
        mock.patch("discord_alerts.send_watchlist_pruned_alert"),
    ):
        retained, pruned = prune_unsuitable_watchlist(filepath=str(test_json), prune_manual=True)
        assert len(pruned) == 1
        assert pruned[0]["symbol"] == "FOMO_STOCK"
        assert "FOMO_STOCK" in _SESSION_PRUNED_SYMBOLS

        # Giả lập Google Sheet vẫn còn mã FOMO_STOCK tải về
        sheet_data = [
            {"symbol": "FOMO_STOCK", "target_buy": 100.0, "note": "Old sheet row"},
            {"symbol": "SAFE_STOCK", "target_buy": 50.0, "note": "An toan"},
        ]
        with (
            mock.patch.dict(os.environ, {"GOOGLE_SHEET_URL": "https://docs.google.com/test"}),
            mock.patch("data_engine.fetch_google_sheet_data", return_value=([], sheet_data)),
        ):
            reloaded = load_watchlist(filepath=str(test_json))
            reloaded_symbols = [it["symbol"] for it in reloaded]
            # FOMO_STOCK phải bị chặn không được phục hồi
            assert "FOMO_STOCK" not in reloaded_symbols
            assert "SAFE_STOCK" in reloaded_symbols
