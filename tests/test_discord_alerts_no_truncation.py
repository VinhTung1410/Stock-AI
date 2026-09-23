from discord_alerts import _append_field_chunks, _slice_long_content, split_ai_summary_into_fields


def test_slice_long_content_within_limit():
    short_text = "Dòng ngắn dưới 1000 ký tự."
    res = _slice_long_content(short_text, max_chars=1000)
    assert len(res) == 1
    assert res[0] == short_text


def test_slice_long_content_exceeding_limit():
    long_text = "Dòng phân tích 1.\n" * 80  # ~1440 ký tự
    res = _slice_long_content(long_text, max_chars=1000)
    assert len(res) >= 2
    for chunk in res:
        assert len(chunk) <= 1000
    # Đảm bảo tổng hợp nội dung không bị mất chữ
    recombined = "\n".join(res)
    assert "Dòng phân tích 1." in recombined


def test_append_field_chunks_preserves_parts():
    fields = []
    content = "Nội dung cần đẩy vào field."
    next_part = _append_field_chunks(fields, "Tiêu đề", content, start_part=1)
    assert len(fields) == 1
    assert fields[0]["name"] == "Tiêu đề"
    assert fields[0]["value"] == content
    assert next_part == 2


def test_split_ai_summary_into_fields_preserves_all_5_questions():
    """
    Xác thực rằng Section I dài chứa 5 câu hỏi chiến lược không bao giờ bị cắt xén,
    đặc biệt là Câu hỏi 5 ở cuối đoạn vẫn giữ nguyên 100% nội dung.
    """
    ai_text = """**I. ĐÁNH GIÁ CHIẾN LƯỢC PHIÊN TRƯA (11:30) & ĐÁNH GIÁ 5 CÂU HỎI CỐT TỬ**
- **Câu hỏi 1 (Nguyên nhân biến động):** Thị trường rung lắc phân hóa do áp lực chốt lời ngắn hạn ở nhóm cổ phiếu dẫn dắt sau chuỗi tăng điểm mạnh trước đó, dòng tiền có xu hướng luân chuyển sang các nhóm cổ phiếu cơ bản có nền tảng định giá an toàn.
- **Câu hỏi 2 (Định giá & MoS):** Các mã như FPT, MWG duy trì định giá hấp dẫn với MoS trên 15%, trong khi nhóm ngân hàng đã tiệm cận vùng P/B trung bình 3 năm và bước vào pha tích lũy kiểm định cung cầu.
- **Câu hỏi 3 (Chốt lời & Trailing Stop):** Vị thế MSB đã đạt lợi nhuận +32%, kích hoạt nâng Trailing Stop lên vùng 13.5k để bảo toàn tối đa thành quả danh mục, tránh bị mất lãi khi thị trường đảo chiều bất ngờ.
- **Câu hỏi 4 (Thesis Breaker):** Chưa có vị thế nào vi phạm luận điểm đầu tư cốt lõi hay suy giảm nền tảng tăng trưởng cơ bản của doanh nghiệp, các chỉ số tài chính quý gần nhất vẫn giữ vững cam kết kinh doanh.
- **Câu hỏi 5 (Tỷ trọng Tiền/Cổ phiếu):** Tỷ trọng hiện tại duy trì ở mức Cổ phiếu 70% và Tiền mặt 30%, nằm trong vùng an toàn tối ưu theo nguyên tắc quản trị rủi ro đa biến.

**II. CHI TIẾT DANH MỤC & HÀNH ĐỘNG QUẢN TRỊ RỦI RO**
- Chi tiết danh mục nắm giữ..."""

    fields = split_ai_summary_into_fields(ai_text)
    assert len(fields) >= 2

    # Kiểm tra tiêu đề có giữ nguyên cả (11:30) không bị cắt tại dấu ':'
    assert "11:30" in fields[0]["name"]

    # Kiểm tra tất cả 5 câu hỏi đều xuất hiện đầy đủ trong các fields
    all_values = " ".join(f["value"] for f in fields)
    assert "Câu hỏi 1" in all_values
    assert "Câu hỏi 2" in all_values
    assert "Câu hỏi 3" in all_values
    assert "Câu hỏi 4" in all_values
    assert "Câu hỏi 5 (Tỷ trọng Tiền/Cổ phiếu)" in all_values
    assert "nguyên tắc quản trị rủi ro đa biến." in all_values

    # Kiểm tra mọi field đều tuân thủ giới hạn < 1024 ký tự của Discord API
    for f in fields:
        assert len(f["value"]) <= 1024
        assert len(f["name"]) <= 256


def test_send_watchlist_pruned_alert_formats_correctly(monkeypatch):
    """Test định dạng Rich Embed báo cáo lý do thanh lọc Watchlist vào Discord DM."""
    from discord_alerts import send_watchlist_pruned_alert

    captured_embeds = []

    def mock_send_discord_dm(content=None, embeds=None):
        nonlocal captured_embeds
        captured_embeds = embeds or []
        return True

    monkeypatch.setattr("discord_alerts.DISCORD_BOT_TOKEN", "mock_token")
    monkeypatch.setattr("discord_alerts.DISCORD_USER_ID", "mock_user")
    monkeypatch.setattr("discord_alerts.send_discord_dm", mock_send_discord_dm)

    pruned_data = [
        {
            "symbol": "HOT_STOCK",
            "reason": "RSI=82.5 quá mua/FOMO; MoS=-30.0% đắt hơn định giá",
            "is_auto": False,
            "current_price": 55.0,
            "rsi": 82.5,
            "mos_pct": -30.0,
        },
        {
            "symbol": "TRAP_STOCK",
            "reason": "Dính bẫy giá (BULL_TRAP)",
            "is_auto": True,
            "current_price": 24.0,
            "rsi": 65.0,
            "mos_pct": 5.0,
        },
    ]

    success = send_watchlist_pruned_alert(pruned_data)
    assert success is True
    assert len(captured_embeds) == 1
    emb = captured_embeds[0]

    assert "THANH LỌC WATCHLIST" in emb["title"]
    assert len(emb["fields"]) == 2

    # Kiểm tra phân loại nguồn (User thêm vs Bot tự động)
    assert "👤 Bạn đã thêm thủ công" in emb["fields"][0]["name"]
    assert "HOT_STOCK" in emb["fields"][0]["name"]
    assert "RSI=82.5" in emb["fields"][0]["value"]
    assert "Thị giá: `55.00k`" in emb["fields"][0]["value"]

    assert "🤖 Bot phát hiện tự động" in emb["fields"][1]["name"]
    assert "TRAP_STOCK" in emb["fields"][1]["name"]
    assert "Dính bẫy giá" in emb["fields"][1]["value"]


def test_prune_unsuitable_watchlist_deletes_manual_item_when_enabled(tmp_path, monkeypatch):
    """Test bot tự động xóa cả mã người dùng nhập tay nếu quá hot và gọi gửi DM báo cáo lý do."""
    import json

    from data_engine import prune_unsuitable_watchlist

    wl_file = tmp_path / "watchlist.json"
    initial = [
        {"symbol": "OVERHEATED", "target_buy": 100.0, "is_auto": False, "note": "Mã tôi tự thêm"},
        {"symbol": "HEALTHY", "target_buy": 50.0, "is_auto": False, "note": "Mã bình thường"},
    ]
    with open(wl_file, "w", encoding="utf-8") as f:
        json.dump(initial, f)

    mock_tech = {
        "OVERHEATED": {"current_price": 130.0, "rsi14": 81.0, "trap_info": {"is_trap": False}},
        "HEALTHY": {"current_price": 48.0, "rsi14": 52.0, "trap_info": {"is_trap": False}},
    }

    alert_called_with = []

    def mock_alert(pruned_items):
        nonlocal alert_called_with
        alert_called_with.extend(pruned_items)
        return True

    monkeypatch.setattr("discord_alerts.send_watchlist_pruned_alert", mock_alert)

    # Chạy với prune_manual=True (mặc định) và notify_discord=True
    retained, pruned = prune_unsuitable_watchlist(
        filepath=str(wl_file), tech_map=mock_tech, prune_manual=True, notify_discord=True
    )

    # Mã OVERHEATED phải bị xóa
    assert len(retained) == 1
    assert retained[0]["symbol"] == "HEALTHY"

    assert len(pruned) == 1
    assert pruned[0]["symbol"] == "OVERHEATED"
    assert pruned[0]["is_auto"] is False
    assert "RSI=81.0 quá mua/FOMO" in pruned[0]["reason"]

    # Đã kích hoạt hàm bắn DM
    assert len(alert_called_with) == 1
    assert alert_called_with[0]["symbol"] == "OVERHEATED"

