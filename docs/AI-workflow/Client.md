# 🎯 YÊU CẦU DỰ ÁN (CLIENT BRIEF) - VERSION 6.2

**Tên dự án:** Stock-AI / AI Investment Decision & Research Platform  
**Phiên bản:** v6.2 — Wiring Institutional Evidence Framework & Kill Switch  
**Trọng tâm:** *"Khắc phục triệt để các lỗi và tích hợp hệ thống lưu vết vĩnh viễn (Immutable Evidence) cho mọi quyết định, gắn hệ thống Kill Switch chặn chuỗi lệnh thua liên tiếp."*

---

## 1. MỤC TIÊU PHIÊN BẢN v6.1 & BẢN VÁ v6.1.1

1. **Bản vá Khắc phục Lỗ hổng Báo cáo Phiên ATC (TASK-0017 - Hotfix v6.1.1):**
   - **Khắc phục VN-Index 0.00 điểm:** Bổ sung cơ chế auto-fetch fallback `fetch_stock_technical("VNINDEX")` và sử dụng `_LAST_KNOWN_TECH_CACHE["VNINDEX"]` khi gọi `generate_portfolio_analysis()` nếu `vnindex_tech` bị thiếu hoặc API gặp sự cố.
   - **Chuẩn hóa tính toán Delta điểm số & khoảng cách MA:** Bổ sung trường `diff_points` ($P_{\text{close}} - P_{\text{ref}}$), `diff_ma20`, `diff_ma50` trong `data_engine.fetch_stock_technical()` và truyền đầy đủ vào Prompt Gemini để phân tích chi tiết biến động điểm số thực tế.
   - **Xóa bỏ xung đột tỷ lệ Tiền/Cổ phiếu (Single Source of Truth):** Loại bỏ hoàn toàn dict hardcode `stock_pct: 70% / cash_pct: 30%` tại `ai_analyst.py:341`, hợp nhất 100% việc tính toán tỷ trọng sang `quant_engine.evaluate_market_regime()`, đảm bảo sự đồng nhất tuyệt đối giữa phiên Sáng (ATO) và Chiều (ATC).
   - **Tối ưu hóa API Calling tại Trading Bot:** Tại `trading_bot.trigger_scheduled_report()`, chủ động kéo `vnindex_tech = fetch_stock_technical("VNINDEX")` một lần và truyền tham số trực tiếp vào `generate_portfolio_analysis()` để tối ưu độ trễ.

2. **Chuẩn hóa tính toàn vẹn dữ liệu (TASK-0013 Prerequisite):**
   - Sửa cách tính Alpha theo đúng chu kỳ nắm giữ vị thế (từ ngày mua tới ngày bán, không lấy biến động 1 phiên).
   - Replay audit idempotent, quy tắc bảo thủ (chạm cả Target & Stop cùng ngày -> tính STOP trước), gắn cờ `t_plus_2_locked`.
   - Loại bỏ mục tiêu consensus quá hạn > 180 ngày khỏi Fair Value, gắn cờ `mos_is_informative` phân định MoS thực chất.
   - Data Gate dùng số liệu BCTC thật từ `get_financial_ratios()`, trả về `INSUFFICIENT_DATA` khi thiếu.
   - Ký duyệt `ADR-0002` đối soát tham số live (Conviction >= 70, weights 40/25/20/15).

3. **Lưu vết quyết định Universe Panel (TASK-0014):**
   - Ghi nhận `DecisionRecord` cho toàn bộ các mã trong danh mục quét: **BUY**, **WATCH**, và **REJECT**.
   - Bóc tách 4 tầng dữ liệu: **FACT** (giá, BCTC), **INFERENCE** (F-Score, Z-Score, RSI, MoS), **OPINION** (nhận định LLM), **COUNTERFACTUAL** (cổng từ chối chính, lý do từ chối để đo ROI của risk gate).
   - Tạo migration `migrations/0003_decision_records.sql` (bảng `decision_records`, `decision_forward_returns` với trigger PostgreSQL cấm sửa/xóa).

4. **Phân tách Kiến trúc Signal Engine ↔ Presentation (TASK-0014):**
   - `ai_analyst.py` chỉ làm nhiệm vụ phân tích logic và trả về `dataclass SignalEvent` độc lập, test được 100% offline.
   - Module `dispatcher.py` chuyên trách định dạng Discord Embed và gửi Webhook/DM.
   - Thêm Subtab 5 "Nhật Ký Quyết Định" trên Dashboard (`tabs/tab_alpha_tracker.py`) để tra cứu lịch sử quyết định BUY/WATCH/REJECT và biến động T+5, T+20.
   - Tích hợp Evidence-Based Kill Switch: Tự động giảm 50% size khi Expectancy theo R của 20 vị thế gần nhất < 0.

5. **Thắt chặt AI Governance & Kiểm Soát Gọi Gemini (TASK-0015):**
   - **Veto Only:** LLM chỉ có quyền Veto hoặc giảm vị thế; quyền cấp phép mua (`can_buy`) và sizing Half-Kelly phụ thuộc 100% vào Quant Core.
   - **Wrapper tập trung & làm sạch Prompt Injection:** Gom toàn bộ các lệnh gọi Gemini qua wrapper kiểm soát 15 RPM, vệ sinh đầu vào tin tức/văn bản.
   - **Fail-Safe Parser Pass 1:** Parse lỗi Pass 1 lập tức bật cờ `pass1_parse_failed` và từ chối mở vị thế (cấm fallback 25/50/25).
   - **Độ ổn định & Tái lập:** Khóa cứng `temperature = 0.0`, lưu đầy đủ `prompt_hash`, `input_hash`, `model_id`.
   - **Calibration Horizon 60 phiên:** Hiệu chuẩn xác suất kịch bản Pass 1 và AI confidence theo chu kỳ 60 phiên giao dịch (khớp vòng đời EXPIRED).

6. **Exit Hypothesis Lab & Conviction Weights Statistical Validation (TASK-0016):**
   - **Exit Hypothesis Lab (Chế độ chỉ báo cáo nghiên cứu):**
     + So sánh song song 4 chiến lược chốt lời/cắt lỗ (A: Hiện tại +12% chốt 50% dời BE; B: R-Multiple +2R chốt 50% dời +0.5R; C: ATR Trailing 2.5x; D: All-or-Nothing đến Target 2).
     + Đánh giá bằng phương pháp **Paired Bootstrap** (1,000 resamples), đối chiếu Expectancy theo R ($\text{PnL}/R$), Win Rate, Max Drawdown.
     + Giữ chế độ chỉ báo cáo (Report-Only), không tự ý đổi quy tắc live nếu chưa có ADR mới.
   - **Kiểm định Trọng số Conviction (Thu thập trước, Hồi quy sau):**
     + Tính toán **Spearman IC** giữa từng trụ cột định lượng thô (`s_mos`, `s_fscore`, `s_ta`, `s_flow`) với Alpha thực tế $T+20$.
     + Loại trừ các bản ghi có `mos_is_informative = False` để chống nhiễu định giá.
     + Áp dụng kiểm định hiệu chỉnh đa biến **Benjamini–Hochberg** kiểm soát False Discovery Rate (FDR $\le 0.05$).
     + Cảnh báo mẫu nhỏ (`INSUFFICIENT_SAMPLE`) khi cỡ mẫu $< 100$ hoặc $N_{\text{eff}}$ chưa đủ.

---

## 2. NGUYÊN TẮC QUẢN TRỊ RỦI RO & BẢO TOÀN KIẾN TRÚC

- **Zero-Democracy Risk Gate:** Cổng rủi ro là mã code Python nhị phân xác định, LLM tuyệt đối không được biểu quyết hay làm mềm luật cắt lỗ.
- **AI Chỉ Giảm Rủi Ro:** LLM chỉ có quyền Veto (bác bỏ) hoặc giảm size, không được tự ý cấp quyền mua (`can_buy`).
- **Phê Duyệt Có Kiểm Soát:** Mọi thay đổi về luật hay ngưỡng kích hoạt chỉ được cập nhật qua ADR có ký duyệt của con người.
- **Single Source of Truth (SSOT):** Mọi tham số phân bổ tỷ trọng (stock_pct, cash_pct) và market regime phải bắt nguồn duy nhất từ `quant_engine.evaluate_market_regime()`.

---

## 3. TIÊU CHUẨN KỸ THUẬT (QUALITY GATE)

- **SonarCloud:** Cognitive Complexity < 15 (S3776), `logging.exception()` trong except (S8572), không trùng lặp chuỗi >= 3 lần (S1192).
- **Ruff:** Tự động sắp xếp import và định dạng code với `ruff check --fix .`.
- **Test Coverage:** >= 80% cho toàn bộ logic mới; 100% I/O bên ngoài (Discord, Gemini, DB) phải được mock khi test.\n