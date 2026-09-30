# 🎯 YÊU CẦU DỰ ÁN (CLIENT BRIEF) - VERSION 6.4

**Tên dự án:** Stock-AI / AI Investment Decision & Research Platform  
**Phiên bản:** v6.4 — Phase 9: System Rigor & De-Risking (Tinh chỉnh Rủi ro & Kiến trúc)  
**Trọng tâm:** *"Giải quyết nợ kỹ thuật bằng cách module hóa hệ thống, đồng thời siết chặt các chốt chặn rủi ro định lượng (Kelly Cap, Hysteresis, Sector Exceptions) nhằm bảo vệ vốn tuyệt đối trước các pha sụt giảm cực đoan của thị trường."*

---

## 1. MỤC TIÊU PHIÊN BẢN v6.4 (PHASE 9: SYSTEM RIGOR & DE-RISKING)

1. **Refactor God Modules (Dọn dẹp Nợ kỹ thuật):**
   - Tách `quant_engine.py` (hơn 2200 dòng) thành các module con chuyên biệt: `indicators.py` (tính toán chỉ báo) và `portfolio_guard.py` (quản trị rủi ro & tỷ trọng).
   - Áp dụng Facade Pattern (Re-export) để không làm đứt gãy các hệ thống phụ thuộc (`ai_analyst.py`, `trading_bot.py`).
   - Sửa lỗi tương thích thư viện `vnstock` v0.2 (chuẩn hóa `source="VCI"`).

2. **Cập nhật Cơ sở Dữ liệu & Nhật ký Quyết định (Supabase Migration):**
   - Bổ sung `migrations/0005_audit_fields.sql` để thêm các cột `prompt_version`, `model_version`, và `raw_response` vào bảng `decision_records`.
   - Giúp team Audit dễ dàng traceback và hồi quy lại nguyên nhân khi LLM đưa ra nhận định sai lệch.
   - **Lưu ý:** Yêu cầu chạy script SQL này trực tiếp trên giao diện Supabase (SQL Editor).

3. **Tinh chỉnh Rủi ro Tài chính (Quantitative Risk Adjustments):**
   - **Ngoại lệ Ngành (Sector Exceptions):** Bỏ phạt Altman Z-Score và nới lỏng Piotroski F-Score cho các doanh nghiệp ngành Ngân hàng (Banking) và Bất động sản (Real Estate) do đặc thù đòn bẩy tài chính (logic tại `indicators.py`).
   - **Trần Tỷ trọng (Kelly Hard-Cap):** Đặt ngưỡng tối đa (ví dụ 15% NAV/vị thế) cho kết quả của Half-Kelly để chống rủi ro tập trung (Concentration Risk).
   - **Hysteresis cho Regime Conflict:** Yêu cầu tín hiệu nhiễu xu hướng giữa Hệ thống và Chuyên gia phải xuất hiện liên tiếp $\ge 2$ phiên mới kích hoạt lệnh phạt giảm 50% quy mô vốn.
   - **Drawdown Breaker Cấp Danh Mục:** Cấm mở vị thế mới nếu tổng NAV danh mục sụt giảm vượt mức cho phép trong một chu kỳ ngắn.

---

## 2. KẾ THỪA CÁC MỤC TIÊU PHIÊN BẢN TRƯỚC (v6.1 - v6.3)

1. **Context Engine & Báo cáo Hàng ngày (v6.3 - Phase 8):**
   - Trích xuất dữ liệu PTKT từ file PDF (TCBS) vào `market_context.json`.
   - Nếu Code báo UPTREND nhưng Chuyên gia cảnh báo DOWNTREND: Bật cờ `regime_conflict = True` và giảm 50% quy mô vị thế.
2. **Bản vá Báo cáo ATC & Single Source of Truth VN-Index (Hotfix v6.1.1):**
   - Khắc phục VN-Index 0.00 điểm bằng auto-fetch fallback.
3. **Hạ tầng Bằng chứng Quyết định Bất biến (v6.1):**
   - Replay audit idempotent, lưu vết 4 tầng FACT, INFERENCE, OPINION, COUNTERFACTUAL trong `decision_records`.
   - Evidence-Based Kill Switch giảm 50% size khi Expectancy 20 lệnh gần nhất < 0.
4. **Thắt chặt AI Governance:**
   - Veto Only: LLM chỉ có quyền Veto hoặc giảm vị thế; không được tự cấp quyền mua.

---

## 3. NGUYÊN TẮC QUẢN TRỊ RỦI RO & BẢO TOÀN KIẾN TRÚC

- **Zero-Democracy Risk Gate:** Báo cáo bên ngoài chỉ là nguồn tham khảo (INFERENCE), không bao giờ có quyền ghi đè luật toán học của Quant Gate.
- **Tuyệt Đối Không Sáng Tác Dữ Liệu (Zero-Fabrication):** Mọi trường dữ liệu trích xuất từ báo cáo phải trung thực 100% với nội dung văn bản.
- **Fail-Safe & Graceful Degradation:** Mất kết nối, thiếu file, file hỏng hoặc stale data KHÔNG ĐƯỢC PHÉP làm sập luồng phân tích chính.
- **Single Source of Truth (SSOT):** Tham số phân bổ vốn và regime gốc luôn phát xuất từ hệ thống Quantitative Engine.

---

## 4. TIÊU CHUẨN KỸ THUẬT (QUALITY GATE)

- **SonarCloud:** Cognitive Complexity < 15 (S3776), `logging.exception()` trong except (S8572), không trùng lặp chuỗi >= 3 lần (S1192).
- **Ruff:** Tự động sắp xếp import và định dạng code với `ruff check --fix .`, bảo đảm exit code 0.
- **Test Coverage:** >= 80% cho toàn bộ logic mới; 100% I/O ngoài (PDF, File, Gemini) được mock chặt chẽ khi kiểm thử.