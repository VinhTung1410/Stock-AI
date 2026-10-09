# 🎯 YÊU CẦU DỰ ÁN (CLIENT BRIEF) - VERSION 15.0

**Tên dự án:** Stock-AI / AI Investment Decision & Research Platform  
**Phiên bản:** v15.0 — Phase 28: Lifecycle Event-Sourcing & Institutional AI Governance (Tái Cấu Trúc Vòng Đời Quyết Định & Chuẩn Hóa Lớp AI)  
**Trọng tâm:** *"Kiểm toán dữ liệu thực tế (`decision_records`) cho thấy pipeline đang bị đứt gãy giữa sàng lọc và thực thi (chỉ có log WATCH, thiếu bước 2–4, không có BUY thực tế). Đồng thời, MoS bị che giấu lỗi bằng trần 99.9%/zeroing, kịch bản Bull/Bear bị hardcode cứng (x1.25 / x0.85), và watchlist bị lặp vô trạng thái (17 mã lặp lại 5 ngày liên tiếp). Phase 28 tái cấu trúc hệ thống từ 'Bộ lọc tĩnh (Static Screener)' sang 'Hệ thống vòng đời hướng sự kiện (Event-Sourced Lifecycle Pipeline)' với cơ chế AI Veto-Only thực thụ và đo lường Alpha chuẩn mực."*

---

## 1. MỤC TIÊU PHIÊN BẢN v15.0 (PHASE 28)

1. **TASK-0082: Data Gate & Quant Valuation Normalization (P0 - Blocker) — `[HOÀN THÀNH]`:**
   - **Tách bạch Null vs 0 & Xóa trần MoS 99.9%:** Loại bỏ hoàn toàn cơ chế che giấu lỗi `fail-silently`. Phân định 3 trạng thái MoS rõ ràng: `Valid`, `Negative`, và `Null/Uncalculated`.
   - **Fix Lỗi Đơn Vị BVPS:** Khắc phục lỗi lệch đơn vị VND sang k VND trong `quant_valuation.py` khiến MoS nhảy vọt lên 99.9%.
   - **Dẹp bỏ Hardcoded Scenarios (x1.25 / x0.85):** Chuyển việc tính toán biên kịch bản Bull/Bear về Quant Engine (dựa trên phân vị P/E, P/B quantile hoặc DCF/Graham) kèm các chỉ số toán học Risk/Reward ($R:R$) và Expected Value ($EV$).
   - **Hard Stop Thiếu Dữ Liệu:** Kích hoạt `INCOMPLETE_DATA` tại Data Gate khi thiếu dữ liệu nền tảng, dừng dòng xử lý thay vì gán giá trị mặc định.

2. **TASK-0083: Dual-Loop State Machine & Watchlist TTL (P1 - Critical) — `[HOÀN THÀNH]`:**
   - **Tách biệt 2 Luồng Thực Thi:** Loop A (Universe Screener EOD) lọc mã gán nhãn `WATCH` đẩy vào Active Watchlist; Loop B (Watchlist Monitor Intraday) chỉ theo dõi các mã trong Active Watchlist chờ kích hoạt `TRIGGER_ACTIVATED`.
   - **Cơ chế Watchlist TTL:** Thiết lập tuổi thọ 10 phiên (`watch_ttl_days = 10`). Sau 10 phiên không có điểm mua hoặc luận điểm suy yếu sẽ tự động `EXPIRED`/`DROPPED`.

3. **TASK-0084: AI Analyst Veto-Only Governance (P2 - Normal) — `[HOÀN THÀNH]`:**
   - **Nguyên tắc Veto-Only:** LLM tuyệt đối không được cấp quyền nâng hạng mua (`can_buy = False` bất khả xâm phạm từ LLM) và không làm toán định giá.
   - **Nhiệm vụ Hội đồng AI:** Khi Quant kích hoạt điểm mua, AI thẩm định định tính và chỉ có quyền: `PASS`, `VETO`, hoặc `REDUCE SIZING` dựa trên tin tức bất lợi, rủi ro quản trị, hoặc chu kỳ suy thoái.

4. **TASK-0085: Event-Sourced Audit Trail & Alpha Attribution (P3 - Normal) — `[HOÀN THÀNH]`:**
   - **Tách Schema sang Event-Sourced:** Bổ sung `save_lifecycle_event` và `get_lifecycle_events` trong `db_manager.py` với khóa liên kết `correlation_id` (nối về `decision_id`), chuẩn hóa hệ thống hằng số sự kiện (`WATCHLIST_ADDED`, `TRIGGER_ACTIVATED`, `AI_VETO_EVALUATED`, `EXECUTION_ORDERED`, `EXECUTION_CANCELLED`, `WATCHLIST_EXPIRED`).
   - **Alpha Attribution Engine (`alpha_attribution.py`):** Xây dựng engine đo lường Forward Return ($T+5, T+20, T+60$), bóc tách phân phối tỷ suất sinh lời và tính Alpha Spread giữa `BUY` vs `REJECT` và `WATCH` vs `REJECT`.
   - **Kiểm Soát Kích Thước Mẫu (60 Phiên Sạch):** Bắt buộc chốt chặn tối thiểu 60 phiên Out-Of-Sample sạch; tự động gắn cảnh báo `INSUFFICIENT_SAMPLE` nếu chưa đủ số phiên kiểm định.

---

## 2. KẾ THỪA CÁC CHỐT CHẶN PHIÊN BẢN TRƯỚC (v6.1 - v14.2)

1. **Phase 27 (v14.2):** Empirical Validation & System Un-strangling (Surgical Fixes, Xóa Double Penalty, Event Study & Ablation Testing).
2. **Phase 26 (v14.1):** Production Architecture Refactoring (`policy_constants.py` SSOT, Luồng SELL Thesis-driven, Tách Hard Veto vs Conviction).
3. **Phase 25 (v14.0):** Contrarian P0 Remediation, Golden Fixtures, Scan Observability & Shadow Mode 60 Phiên.
4. **Phase 24 (v13.0):** Reversal Confirmed & Entry Eligible Layer (Price Action, Higher Low, Volume Confirm).
5. **Phase 23 (v12.0):** Advanced FQ-Score 3-Tier Architecture & Risk Overlays (CFO Proxy, Decoupled Hard Veto).
6. **Phase 22 (v11.1):** Contrarian Quant & Architecture Upgrade (Valuation Watch, F-Score Data Confidence).
7. **Phase 21 (v10.1):** Data Resilience & Fallback Valuation.
8. **Phase 20 (v10.0):** Contrarian 4-State Machine (Continuous Panic Score).
9. **Phase 19 (v9.0):** Contrarian 5-Layer Framework (Quality De-rating vs Value Trap, Event Risk VETO).
10. **Phase 18 (v8.1):** Contrarian Panic Buy Module cơ bản (RSI <= 30).
11. **Phase 17 (v8.0):** Risk Governance Completion.
12. **Phase 16 (v7.6):** Signal Integrity & Audit Cleanup.
13. **Phase 15 (v7.5):** Unified Entry Gate (7 tầng thống nhất, Macro Gate toàn tuyến).
14. **Phase 14 (v7.4):** Data & Valuation Plumbing.
15. **Phase 13 (v7.3):** Core Valuation Re-Architecture.

---

## 3. NGUYÊN TẮC QUẢN TRỊ RỦI RO & BẢO TOÀN KIẾN TRÚC

- **P0 First Before Thresholds:** Không bao giờ tinh chỉnh ngưỡng định lượng khi kiến trúc cốt lõi (Thesis Engine, Macro Gate, Data Gate) còn lỗi.
- **Single Source of Truth:** Bất cứ tham số nào (MoS, Stop-loss, Macro Regime) cũng chỉ được định nghĩa và đánh giá tại MỘT nguồn duy nhất.
- **Evidence-First (Không Test API Sống):** Golden test dựa trên fixture thực nghiệm bất biến. Không để CI phụ thuộc vào tính sẵn sàng của mạng hoặc API bên ngoài.
- **Shadow Mode Quarantine:** Bất kỳ chiến lược hoặc thay đổi kiến trúc nào cũng bắt buộc trải qua thử nghiệm và đạt kỳ vọng xác suất thực tế trước khi cấp quyền can thiệp vào tài khoản vốn thật.

---

## 4. TIÊU CHUẨN KỸ THUẬT (QUALITY GATE)

- **SonarCloud:** Cognitive Complexity < 15 (S3776), `logging.exception()` trong except (S8572), không trùng lặp chuỗi $\ge 3$ lần (S1192), duplicate lines density $\le 3.0\%$. Zero duplicate logic giữa sync/async.
- **Ruff:** `ruff check --fix .` đảm bảo exit code 0 và imports chuẩn `isort`.
- **Test Coverage:** $\ge 80\%$ (mục tiêu $85 - 95\%+$) cho toàn bộ module quant, valuation và governance mới; 100% unit tests pass.
- **Local Workspace Hygiene:** Không stage hay commit bất kỳ file nghiên cứu nội bộ nào (`stock_ai_roadmap.md`, `Client.md`, `idea.md`...).

