# 🏛️ ARCHITECTURE DECISION RECORD: ADR-0002
# ĐỐI SOÁT & THỐNG NHẤT BỘ THAM SỐ QUANT CORE THỰC THI (RECONCILIATION & LIVE THRESHOLDS LOCK)

- **Trạng thái:** `ACCEPTED` (Đã đối soát và phê duyệt)
- **Ngày ban hành:** 2026-09-28
- **Tác giả:** Finance Lead & Product Owner
- **Phạm vi:** `quant_engine.py`, `ai_analyst.py`, `trading_bot.py`, `backtest_engine.py`

---

## 1. Bối cảnh & Lý do Lập ADR (Context)

Trong quá trình vận hành hệ thống định lượng Stock-AI, đã phát sinh độ lệch pha giữa văn bản kiến trúc ban đầu (`ADR-0001-quant-core-thresholds.md`) và mã nguồn vận hành thực tế (Production Code):
1. **Ngưỡng Conviction:** `ADR-0001` ghi nhận `conviction_min >= 55.0`, trong khi mã nguồn thực thi live (`trading_bot.py:455`, `README.md`) yêu cầu `conviction_score >= 70.0` để kích hoạt lệnh **BUY**, và dùng mức `55.0` làm ngưỡng đưa vào danh mục theo dõi (**WATCHLIST**).
2. **Trọng số 4 Trụ Cột (4 Pillars):** Mã nguồn thực tế phân bổ 40% Cơ bản (FA), 25% Kỹ thuật (TA), 20% Dòng tiền (Money Flow), 15% Vĩ mô & Tin tức (News/Macro).
3. **Quyền hạn của AI:** AI Committee chỉ được phép Veto (bác bỏ) hoặc giảm quy mô vị thế; tuyệt đối không có quyền mở lệnh MUA khi các cổng định lượng không đạt.

Nhằm bảo đảm tính minh bạch, nhất quán và ngăn ngừa rủi ro sai lệch bằng chứng (Evidence Integrity), `ADR-0002` chính thức đối soát và xác nhận các tham số vận hành live là nguồn sự thật duy nhất (Single Source of Truth).

---

## 2. Quyết định Kiến trúc & Bộ Tham Số Khóa (Decision)

Đóng băng vĩnh viễn bộ thông số thực thi chuẩn mực:

| Tham số / Chỉ số | Giá trị Khóa (Locked Value) | Diễn giải & Phân loại Vận hành |
|---|---|---|
| **BUY Conviction Threshold** | $\ge 70.0$ / 100 | Ngưỡng bắt buộc để phát lệnh khuyến nghị MUA (Tier 1 High Conviction). |
| **WATCH Conviction Threshold** | $\ge 55.0$ / 100 | Ngưỡng phân loại ứng viên tiềm năng đưa vào danh sách theo dõi (Watchlist). |
| **Trọng số Cơ bản (FA Weight)** | $40\%$ (0.40) | Ưu tiên sức khỏe BCTC, F-Score, Z-Score và Biên an toàn (MoS). |
| **Trọng số Kỹ thuật (TA Weight)** | $25\%$ (0.25) | Tín hiệu xu hướng MA20/MA50, RSI(14) và mô hình giá. |
| **Trọng số Dòng tiền (Flow Weight)**| $20\%$ (0.20) | Khối ngoại, tự doanh và đột biến khối lượng (Vol Ratio). |
| **Trọng số Tin tức / Vĩ mô** | $15\%$ (0.15) | Tin tức CafeF, kiểm soát rủi ro vĩ mô và chỉ số VN-Index. |
| **F-Score tối thiểu** | $\ge 6$ / 9 | Piotroski F-Score sàng lọc chất lượng tài chính. |
| **Biên an toàn (MoS)** | $\ge 15.0\%$ | Chiết khấu thị giá so với Fair Value (với `mos_is_informative = True`). |
| **Altman Z-Score** | $> 1.80$ | Ranh giới an toàn tài chính, loại bỏ nguy cơ kiệt quệ phá sản. |
| **RSI(14) trần (Entry)** | $< 70.0$ | Chống FOMO mua đuổi trong vùng quá mua. |
| **ADV20 Hấp thụ tối đa** | $\le 10\%$ Order | Đảm bảo tính thanh khoản, kiểm soát trượt giá thị trường. |
| **Giới hạn tỷ trọng ngành** | $\le 25\%$ NAV | Sector Concentration Gate, tối đa 3 mã/ngành. |
| **Quyền hạn của AI (LLM Gate)** | **VETO ONLY** | AI chỉ có quyền từ chối hoặc hạ size; cấm tự ý cấp quyền MUA (`can_buy`). |

---

## 3. Hệ quả Thực thi & Kiểm Toán Tự Động (Enforcement)

1. Cập nhật hằng số `LOCKED_QUANT_THRESHOLDS` trong `quant_engine.py` bao gồm đầy đủ `buy_conviction_min = 70.0` và `watch_conviction_min = 55.0`.
2. Thiết lập unit test tự động đối chiếu các hằng số này để phát hiện ngay lập tức bất kỳ hành vi sửa đổi trái phép nào.
3. Mọi phiên bản báo cáo kiểm toán, Decision Record và Forward Testing bắt buộc phải tham chiếu phiên bản `ADR-0002`.
