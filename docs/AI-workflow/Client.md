# 🎯 YÊU CẦU DỰ ÁN (CLIENT BRIEF) - VERSION 12.0

**Tên dự án:** Stock-AI / AI Investment Decision & Research Platform  
**Phiên bản:** v12.0 — Phase 23: Advanced F-Score 3-Tier Architecture & Macro Overlays  
**Trọng tâm:** *"Nâng cấp kiến trúc Fundamental (F-Score) từ Hard Gate 7/9 sang mô hình 3-Tier linh hoạt (Block < 4, Conditional 4-6, Full Eligibility >= 7) được bảo kê bằng Data Confidence tracking. Bổ sung các lớp Macro/Risk Overlays độc lập (Z-Score, D/E, Liquidity stress) để block Value Trap chính xác thay vì chỉ phụ thuộc điểm số tổng hợp."*

---

## 1. MỤC TIÊU PHIÊN BẢN v12.0 (PHASE 23)

1. **TASK-23.1: F-Score 3-Tier Architecture:** Đập bỏ rule `F-Score < 7 -> BLOCKED`. Triển khai cấu trúc 3 tầng: `F < 4 (Hard Block)`, `F 4-6 (Conditional Contrarian)`, `F >= 7 (Full Eligibility)`.
2. **TASK-23.2: Fundamental Quality Conditional Gate:** Xây dựng logic phân tích rổ Conditional (F-Score 4-6) kết hợp với chu kỳ (Cyclical). Cấp quyền `VALUATION_WATCH` hoặc `PANIC_BUY` nếu CFO dương, nợ an toàn, và tổn thương mang tính chu kỳ (temporary deterioration). Nếu CFO âm, margin giảm liên tục $\rightarrow$ `VALUE_TRAP`.
3. **TASK-23.3: Hard Veto Risk Overlays:** Áp đặt các rule cứng độc lập với F-Score: Block khi Altman Z-Score vùng nguy hiểm, D/E quá cao, nguy cơ thanh khoản, hoặc Event Risk.
4. **TASK-23.4: Data Explainability Propagation:** Tận dụng `FScoreResult` (passed, failed, unknown, completeness) để cấp context cho AI/Analyst khi ra quyết định thay vì chỉ cung cấp điểm vô hồn.

---

## 2. KẾ THỪA CÁC CHỐT CHẶN PHIÊN BẢN TRƯỚC (v6.1 - v11.1)

1. **Phase 22 (v11.1):** Contrarian Quant & Architecture Upgrade (Valuation Watch, F-Score Data Confidence).
2. **Phase 21 (v10.1):** Data Resilience & Fallback Valuation.
3. **Phase 20 (v10.0):** Contrarian 4-State Machine (Output 4 trạng thái linh hoạt).
4. **Phase 19 (v9.0):** Contrarian 5-Layer Framework (Phân biệt Quality De-rating vs Value Trap, Event Risk VETO).
5. **Phase 18 (v8.1):** Contrarian Panic Buy Module cơ bản (RSI <= 30).
6. **Phase 17 (v8.0):** Risk Governance Completion.
7. **Phase 16 (v7.6):** Signal Integrity & Audit Cleanup.
8. **Phase 15 (v7.5):** Unified Entry Gate (7 tầng thống nhất, Macro Gate toàn tuyến).
9. **Phase 14 (v7.4):** Data & Valuation Plumbing.
10. **Phase 13 (v7.3):** Core Valuation Re-Architecture (Forward EPS, Macro Hysteresis).
11. **Phase 12 (v7.2):** Compounder & Retail Flow (Anti-Synthetic MoS).

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
