# 🎯 YÊU CẦU DỰ ÁN (CLIENT BRIEF) - VERSION 6.1

**Tên dự án:** Stock-AI / AI Investment Decision & Research Platform  
**Phiên bản:** v6.1 — Decision Record Universe Panel, Migration 0003 & Dispatcher Decoupling (TASK-0014)  
**Trọng tâm:** *"Không thêm tính năng mới. Xây hạ tầng bằng chứng (Evidence Integrity) và lưu vết TẠI SAO (WHY) cho toàn bộ Universe."*

---

## 1. MỤC TIÊU PHIÊN BẢN v6.1

1. **Chuẩn hóa tính toàn vẹn dữ liệu (TASK-0013 Prerequisite):**
   - Sửa cách tính Alpha theo đúng chu kỳ nắm giữ vị thế (từ ngày mua tới ngày bán, không lấy biến động 1 phiên).
   - Replay audit idempotent, quy tắc bảo thủ (chạm cả Target & Stop cùng ngày -> tính STOP trước), gắn cờ `t_plus_2_locked`.
   - Loại bỏ mục tiêu consensus quá hạn > 180 ngày khỏi Fair Value, gắn cờ `mos_is_informative` phân định MoS thực chất.
   - Data Gate dùng số liệu BCTC thật từ `get_financial_ratios()`, trả về `INSUFFICIENT_DATA` khi thiếu.
   - Ký duyệt `ADR-0002` đối soát tham số live (Conviction >= 70, weights 40/25/20/15).

2. **Lưu vết quyết định Universe Panel (TASK-0014):**
   - Ghi nhận `DecisionRecord` cho toàn bộ các mã trong danh mục quét: **BUY**, **WATCH**, và **REJECT**.
   - Bóc tách 4 tầng dữ liệu: **FACT** (giá, BCTC), **INFERENCE** (F-Score, Z-Score, RSI, MoS), **OPINION** (nhận định LLM), **COUNTERFACTUAL** (cổng từ chối chính, lý do từ chối để đo ROI của risk gate).
   - Tạo migration `migrations/0003_decision_records.sql` (bảng `decision_records`, `decision_forward_returns` với trigger PostgreSQL cấm sửa/xóa).

3. **Phân tách Kiến trúc Signal Engine ↔ Presentation (TASK-0014):**
   - `ai_analyst.py` chỉ làm nhiệm vụ phân tích logic và trả về `dataclass SignalEvent` độc lập, test được 100% offline.
   - Module `dispatcher.py` chuyên trách định dạng Discord Embed và gửi Webhook/DM.
   - Thêm Subtab 5 "Nhật Ký Quyết Định" trên Dashboard (`tabs/tab_alpha_tracker.py`) để tra cứu lịch sử quyết định BUY/WATCH/REJECT và biến động T+5, T+20.
   - Tích hợp Evidence-Based Kill Switch: Tự động giảm 50% size khi Expectancy theo R của 20 vị thế gần nhất < 0.

4. **Thắt chặt AI Governance & Kiểm Soát Gọi Gemini (TASK-0015):**
   - **Veto Only:** LLM chỉ có quyền Veto hoặc giảm vị thế; quyền cấp phép mua (`can_buy`) và sizing Half-Kelly phụ thuộc 100% vào Quant Core.
   - **Wrapper tập trung & làm sạch Prompt Injection:** Gom toàn bộ các lệnh gọi Gemini qua wrapper kiểm soát 15 RPM, vệ sinh đầu vào tin tức/văn bản.
   - **Fail-Safe Parser Pass 1:** Parse lỗi Pass 1 lập tức bật cờ `pass1_parse_failed` và từ chối mở vị thế (cấm fallback 25/50/25).
   - **Độ ổn định & Tái lập:** Khóa cứng `temperature = 0.0`, lưu đầy đủ `prompt_hash`, `input_hash`, `model_id`.
   - **Calibration Horizon 60 phiên:** Hiệu chuẩn xác suất kịch bản Pass 1 và AI confidence theo chu kỳ 60 phiên giao dịch (khớp vòng đời EXPIRED).

---

## 2. NGUYÊN TẮC QUẢN TRỊ RỦI RO & BẢO TOÀN KIẾN TRÚC

- **Zero-Democracy Risk Gate:** Cổng rủi ro là mã code Python nhị phân xác định, LLM tuyệt đối không được biểu quyết hay làm mềm luật cắt lỗ.
- **AI Chỉ Giảm Rủi Ro:** LLM chỉ có quyền Veto (bác bỏ) hoặc giảm size, không được tự ý cấp quyền mua (`can_buy`).
- **Phê Duyệt Có Kiểm Soát:** Mọi thay đổi về luật hay ngưỡng kích hoạt chỉ được cập nhật qua ADR có ký duyệt của con người.

---

## 3. TIÊU CHUẨN KỸ THUẬT (QUALITY GATE)

- **SonarCloud:** Cognitive Complexity < 15 (S3776), `logging.exception()` trong except (S8572), không trùng lặp chuỗi >= 3 lần (S1192).
- **Ruff:** Tự động sắp xếp import và định dạng code với `ruff check --fix .`.
- **Test Coverage:** >= 80% cho toàn bộ logic mới; 100% I/O bên ngoài (Discord, Gemini, DB) phải được mock khi test.\n