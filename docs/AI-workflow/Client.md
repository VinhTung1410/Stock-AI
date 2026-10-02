# 🎯 YÊU CẦU DỰ ÁN (CLIENT BRIEF) - VERSION 11.0

**Tên dự án:** Stock-AI / AI Investment Decision & Research Platform  
**Phiên bản:** v11.0 — Phase 21: Data Resilience & Fallback Valuation  
**Trọng tâm:** *"Sau thành công của Contrarian State Machine, hệ thống đã chạy xuất sắc trên toàn thị trường nhưng vấp phải sự cố dữ liệu rác (False Positive Tickers) và Zero FV. Trọng tâm Phase 21 là xây dựng **Resilience Engine** để bot bọc lỗi (try-except) toàn bộ khi quét thị trường, cùng với cơ chế **KBS-First Fallback Valuation** để tránh lỗi toán học khi định giá các cổ phiếu mảng Tài chính có FV = 0."*

---

## 1. MỤC TIÊU PHIÊN BẢN v11.0 (PHASE 21)

1. **TASK-0073: Data Resilience Engine (Quét toàn thị trường không Crash):**
   - **Vấn đề cốt tử:** API vnstock/VCI bị treo hoặc quăng lỗi `ValueError` khi gặp mã lạ (ví dụ "GOOD1" do RSS parser nhận nhầm).
   - **Giải pháp:** Đã bọc `try-except` cho luồng kéo dữ liệu VCI trong `get_financial_ratios`. Bất cứ mã nào lỗi API sẽ bị skip thay vì crash toàn bộ tiến trình.

2. **TASK-0074: Fallback Valuation & Zero FV Protection:**
   - **Vấn đề cốt tử:** Cổ phiếu mảng tài chính (như SSI) thỉnh thoảng bị trả về Fair Value = 0, dẫn tới lỗi `ZeroDivisionError` ở hàm tính MoS.
   - **Giải pháp:** Đã bọc điều kiện `price_base > 0` trong `quant_engine.py` và áp dụng chiến thuật KBS-First, Fallback VCI cho dữ liệu BCTC.

2. **TASK-0071: Continuous Panic Score (0-100):**
   - **Vấn đề cốt tử:** Đánh giá hoảng loạn bằng Binary (True/False cho RSI <= 30) quá cứng nhắc và mất mát thông tin.
   - **Giải pháp:** Viết thuật toán tính điểm hoảng loạn liên tục (0-100) kết hợp đa yếu tố: RSI, khoảng cách so với MA20, Drawdown, Volume Abnormality.

3. **TASK-0072: Cập Nhật Output Semantics & Test:**
   - **Vấn đề cốt tử:** Việc dùng từ "Capitulation", "Call-margin" bừa bãi khi chưa có Volume Spike làm hỏng chất lượng lập luận của AI.
   - **Giải pháp:** Sửa đổi hệ thống từ vựng, không gọi là Call-margin nếu không có bằng chứng. Cập nhật Output của Mocktest thành 3 nhóm rõ ràng: BUY CANDIDATE, WATCHLIST, BLOCKED để trực quan hóa năng lực nhận diện của AI.

---

## 2. KẾ THỪA CÁC CHỐT CHẶN PHIÊN BẢN TRƯỚC (v6.1 - v9.0)

1. **Phase 19 (v9.0):** Contrarian 5-Layer Framework (Phân biệt Quality De-rating vs Value Trap, Event Risk VETO).
2. **Phase 18 (v8.1):** Contrarian Panic Buy Module cơ bản (RSI <= 30).
3. **Phase 17 (v8.0):** Risk Governance Completion.
4. **Phase 16 (v7.6):** Signal Integrity & Audit Cleanup.
5. **Phase 15 (v7.5):** Unified Entry Gate (7 tầng thống nhất, Macro Gate toàn tuyến, 2-Pass chuẩn hóa ngành, Smart Committee Quant Arbitrator).
6. **Phase 14 (v7.4):** Data & Valuation Plumbing.
7. **Phase 13 (v7.3):** Core Valuation Re-Architecture (Forward EPS, Macro Hysteresis, Structural Stop-loss).
8. **Phase 12 (v7.2):** Compounder & Retail Flow (Anti-Synthetic MoS, xu hướng trung hạn).
9. **Phase 11 (v7.1):** Cyclical Valuation Overhaul.
10. **Phase 10 (v7.0):** Real Estate & Holding Valuation Overhaul.

---

## 3. NGUYÊN TẮC QUẢN TRỊ RỦI RO & BẢO TOÀN KIẾN TRÚC

- **Dual-Track Isolation (Cách Ly Song Luồng):** Trend-Following và Contrarian là 2 triết lý giao dịch đối nghịch, hoạt động trên hai đường ray độc lập. Không được nới lỏng các chốt chặn MA20/MA50 của Trend-Following để phục vụ bắt đáy.
- **Extreme Quality for Extreme Panic:** Càng hoảng loạn thì tiêu chuẩn chất lượng tài chính (Fundamental Integrity) càng phải cao hơn bình thường.
- **Semantic Integrity:** Không đánh đồng "Cổ phiếu tốt chưa có điểm mua" với "Cổ phiếu rác". AI Copilot phải giải thích được khác biệt này.

---

## 4. TIÊU CHUẨN KỸ THUẬT (QUALITY GATE)

- **SonarCloud:** Cognitive Complexity < 15 (S3776), `logging.exception()` trong except (S8572), không trùng lặp chuỗi $\ge 3$ lần (S1192), duplicate lines density $\le 3.0\%$. Zero duplicate logic giữa sync/async.
- **Ruff:** `ruff check --fix .` đảm bảo exit code 0 và imports chuẩn `isort`.
- **Test Coverage:** $\ge 80\%$ (mục tiêu $85 - 95\%+$) cho `contrarian_engine.py` mới; bắt buộc test trường hợp bẫy Value Trap.
- **TDD (Test-Driven Development):** Viết unit tests trước khi sửa logic chính để đảm bảo cấu trúc State Machine không phá vỡ 465 test hiện tại.
