# 🎯 YÊU CẦU DỰ ÁN (CLIENT BRIEF) - VERSION 15.0

**Tên dự án:** Stock-AI / AI Investment Decision & Research Platform  
**Phiên bản:** v14.2 — Phase 27: Empirical Validation & System Un-strangling (Đo Lường & Gỡ Rào Cản)  
**Trọng tâm:** *"Kiến trúc hiện tại bị mắc kẹt trong 'Governance-heavy' (quá nhiều chốt chặn rủi ro không được kiểm chứng), dẫn đến hiện tượng bóp nghẹt hệ thống (Double Penalty) và gần như không phát tín hiệu. Phase 27 chuyển hướng triệt để sang 'Đo trước khi thêm' (Measure before adding) thông qua Event Study, Ablation Testing và gỡ bỏ 4 lỗi logic chí mạng."*

---

## 1. MỤC TIÊU PHIÊN BẢN v14.2 (PHASE 27)

1. **TASK-0079: Surgical Fixes & Gỡ Phạt Kép (P0) — `[HOÀN THÀNH]`:**
   - **Fix 4 Lỗi Logic Core:** Đã vá lỗ hổng F-Score Tier 2 (chặn điểm 4-6), sửa lỗi Kelly sizing (chặn tuyệt đối Kelly $\le 0$), chuẩn hóa đơn vị đòn bẩy `debt_equity`, và xử lý look-ahead bias qua việc điều chỉnh ngưỡng cấu trúc nến.
   - **Xóa Double Penalty:** Đã bỏ ép `stress_haircut` trực tiếp làm giảm Fair Value. Hệ thống test đã xanh 100%.

2. **TASK-0080: Xây dựng Event Study Engine (P1) — `[CHƯA BẮT ĐẦU - TODO]`:**
   - **Khung Kiểm Chứng:** Code script độc lập (`event_study.py` hoặc tools tương đương) để backtest các tín hiệu đơn lẻ (VD: RSI < 30, CFO > 0) trên toàn bộ lịch sử 3-5 năm.
   - **Mục Tiêu:** Xác nhận Forward Return (T+5, T+10, T+20) có thực sự tạo ra Alpha so với Benchmark không trước khi đưa vào PM layer. Ngưng bổ sung các rule cảm tính.

3. **TASK-0081: Ablation Testing / Kiểm thử Cắt bỏ (P2) — `[CHƯA BẮT ĐẦU - TODO]`:**
   - **Tối Ưu Luật Cứng:** Tắt thử nghiệm nghiêm ngặt từng Gate một (Thanh khoản, Định giá, Vĩ mô) để đo lường Trade-off giữa Sample Size và Win Rate.
   - **Nguyên tắc YAGNI:** Cổng nào làm mất 80% cơ hội nhưng chỉ cứu được 2% Win Rate sẽ bị loại bỏ vĩnh viễn khỏi hệ thống.

---

## 2. KẾ THỪA CÁC CHỐT CHẶN PHIÊN BẢN TRƯỚC (v6.1 - v14.1)

1. **Phase 26 (v14.1):** Production Architecture Refactoring (`policy_constants.py` SSOT, Luồng SELL Thesis-driven, Tách Hard Veto vs Conviction).
2. **Phase 25 (v14.0):** Contrarian P0 Remediation, Golden Fixtures, Scan Observability & Shadow Mode 60 Phiên.
3. **Phase 24 (v13.0):** Reversal Confirmed & Entry Eligible Layer (Price Action, Higher Low, Volume Confirm).
4. **Phase 23 (v12.0):** Advanced FQ-Score 3-Tier Architecture & Risk Overlays (CFO Proxy, Decoupled Hard Veto).
5. **Phase 22 (v11.1):** Contrarian Quant & Architecture Upgrade (Valuation Watch, F-Score Data Confidence).
6. **Phase 21 (v10.1):** Data Resilience & Fallback Valuation.
7. **Phase 20 (v10.0):** Contrarian 4-State Machine (Continuous Panic Score).
8. **Phase 19 (v9.0):** Contrarian 5-Layer Framework (Quality De-rating vs Value Trap, Event Risk VETO).
9. **Phase 18 (v8.1):** Contrarian Panic Buy Module cơ bản (RSI <= 30).
10. **Phase 17 (v8.0):** Risk Governance Completion.
11. **Phase 16 (v7.6):** Signal Integrity & Audit Cleanup.
12. **Phase 15 (v7.5):** Unified Entry Gate (7 tầng thống nhất, Macro Gate toàn tuyến).
13. **Phase 14 (v7.4):** Data & Valuation Plumbing.
14. **Phase 13 (v7.3):** Core Valuation Re-Architecture.

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
