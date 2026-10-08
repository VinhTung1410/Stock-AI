# 🎯 YÊU CẦU DỰ ÁN (CLIENT BRIEF) - VERSION 15.0

**Tên dự án:** Stock-AI / AI Investment Decision & Research Platform  
**Phiên bản:** v14.1 — Phase 26: Production Architecture Refactoring (BUY / HOLD / SELL Redesign)  
**Trọng tâm:** *"Dọn dẹp Technical Debt và nâng cấp Bot lên chuẩn Production-grade. Tái thiết kế toàn bộ luồng HOLD/SELL theo thứ tự: THESIS CÒN NGUYÊN? -> ĐỊNH GIÁ HẤP DẪN? -> TREND TỐT? (Bỏ tư duy bán chỉ vì P/L). Khắc phục lỗi Regime Tautology (Dùng duy nhất MA200 VN-Index). Tách bạch rõ ràng giữa hệ thống chặn Hard Veto và hệ thống chấm điểm Conviction Scoring."*

---

## 1. MỤC TIÊU PHIÊN BẢN v15.0 (PHASE 26)

1. **TASK-0075: Nối dây SELL & Tái thiết kế HOLD/SELL Thesis Engine (P0) — `[HOÀN THÀNH - DONE]`:**
   - Thay đổi cấu trúc quyết định BÁN: `THESIS INTACT?` → `VALUATION STILL ATTRACTIVE?` → `TREND STILL HEALTHY?`. Lợi nhuận (P/L) chỉ là input phụ, không phải yếu tố quyết định cốt lõi.
   - Bắt buộc truyền `fin_dict` và `sector` vào hàm `evaluate_holding_position` và `_build_portfolio_quant_summary` để kích hoạt nhánh kiểm tra Thesis Breaker (Z-Score, F-Score) cho tất cả các mã (kể cả đang LÃI).

2. **TASK-0076: Sửa lỗi Regime Tautology & Cổng Vĩ Mô (P0) — `[HOÀN THÀNH - DONE]`:**
   - Hợp nhất và sử dụng duy nhất một hàm `get_market_regime()` lấy MA200 Hysteresis từ chuỗi VN-Index làm *Single Source of Truth* cho toàn bộ hệ thống (tránh việc cổ phiếu dùng MA200 của chính nó để đo Vĩ mô).
   - Nhận định của chuyên gia TCBS chỉ dùng để tham khảo, không được ghi đè quy tắc định lượng.
   - Loại bỏ việc gán cứng `conviction_score=75.0` tại các cổng quét 2-pass để giải phóng hệ thống Risk.

3. **TASK-0077: Thống nhất Threshold & Calibrate Kelly Sizing (P1) — `[HOÀN THÀNH - DONE]`:**
   - Gom toàn bộ các ngưỡng rải rác (MoS 12%, 15%, Stop-loss 7%, 8%, v.v.) vào một Policy Constants duy nhất. Sửa các lỗi từ vựng chuỗi hành động (như "🟢 TÍCH LŨY" vs "MUA").
   - Kelly Sizing: Chuyển từ Kelly dựa trên xác suất chủ quan sang Fixed Risk Sizing (VD: $\le 1-1.5\%$ NAV tại điểm Stop-loss cấu trúc). Chỉ kích hoạt phân bổ Kelly phân số khi đã Calibrate đủ bằng chứng giao dịch thật (>100 lệnh).

4. **TASK-0078: Tách bạch Hard Veto và Conviction Scoring (P2) — `[HOÀN THÀNH - DONE]`:**
   - **Hard Veto:** Chặn cứng (Fail-fast) với các lỗi sinh tử: Data invalid, Thanh khoản kém, Thesis Breaker, Định giá quá đắt, R:R thấp, Bẫy nặng, Market Circuit Breaker.
   - **Scoring System:** Chuyển các yếu tố như RSI, MA20, Dòng tiền khối ngoại, Catalyst thành tín hiệu cộng/trừ điểm (`Conviction Score`) thay vì dùng làm rào cản từ chối lệ lệnh (Reject gate).

---

## 2. KẾ THỪA CÁC CHỐT CHẶN PHIÊN BẢN TRƯỚC (v6.1 - v14.0)

1. **Phase 25 (v14.0):** Contrarian P0 Remediation, Golden Fixtures, Scan Observability & Shadow Mode 60 Phiên.
2. **Phase 24 (v13.0):** Reversal Confirmed & Entry Eligible Layer (Price Action, Higher Low, Volume Confirm).
3. **Phase 23 (v12.0):** Advanced FQ-Score 3-Tier Architecture & Risk Overlays (CFO Proxy, Decoupled Hard Veto).
4. **Phase 22 (v11.1):** Contrarian Quant & Architecture Upgrade (Valuation Watch, F-Score Data Confidence).
5. **Phase 21 (v10.1):** Data Resilience & Fallback Valuation.
6. **Phase 20 (v10.0):** Contrarian 4-State Machine (Continuous Panic Score).
7. **Phase 19 (v9.0):** Contrarian 5-Layer Framework (Quality De-rating vs Value Trap, Event Risk VETO).
8. **Phase 18 (v8.1):** Contrarian Panic Buy Module cơ bản (RSI <= 30).
9. **Phase 17 (v8.0):** Risk Governance Completion.
10. **Phase 16 (v7.6):** Signal Integrity & Audit Cleanup.
11. **Phase 15 (v7.5):** Unified Entry Gate (7 tầng thống nhất, Macro Gate toàn tuyến).
12. **Phase 14 (v7.4):** Data & Valuation Plumbing.
13. **Phase 13 (v7.3):** Core Valuation Re-Architecture.

---

## 3. NGUYÊN TẮC QUẢN TRỊ RỦI RO & BẢO TOÀN KIẾN TRÚC

- **P0 First Before Thresholds:** Không bao giờ tinh chỉnh ngưỡng định lượng khi kiến trúc cốt lõi (Thesis Engine, Macro Gate) còn lỗi.
- **Single Source of Truth:** Bất cứ tham số nào (MoS, Stop-loss, Macro Regime) cũng chỉ được định nghĩa và đánh giá tại MỘT nguồn duy nhất.
- **Evidence-First (Không Test API Sống):** Golden test dựa trên fixture thực nghiệm bất biến. Không để CI phụ thuộc vào tính sẵn sàng của mạng hoặc API bên ngoài.
- **Shadow Mode Quarantine:** Bất kỳ chiến lược hoặc thay đổi kiến trúc nào cũng bắt buộc trải qua thử nghiệm và đạt kỳ vọng xác suất thực tế trước khi cấp quyền can thiệp vào tài khoản vốn thật.

---

## 4. TIÊU CHUẨN KỸ THUẬT (QUALITY GATE)

- **SonarCloud:** Cognitive Complexity < 15 (S3776), `logging.exception()` trong except (S8572), không trùng lặp chuỗi $\ge 3$ lần (S1192), duplicate lines density $\le 3.0\%$. Zero duplicate logic giữa sync/async.
- **Ruff:** `ruff check --fix .` đảm bảo exit code 0 và imports chuẩn `isort`.
- **Test Coverage:** $\ge 80\%$ (mục tiêu $85 - 95\%+$) cho toàn bộ module contrarian và governance mới; 100% unit tests pass.
- **Local Workspace Hygiene:** Không stage hay commit bất kỳ file nghiên cứu nội bộ nào (`stock_ai_roadmap.md`, `Client.md`, `idea.md`...).
