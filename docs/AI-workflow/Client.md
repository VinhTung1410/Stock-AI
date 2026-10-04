# 🎯 YÊU CẦU DỰ ÁN (CLIENT BRIEF) - VERSION 14.0

**Tên dự án:** Stock-AI / AI Investment Decision & Research Platform  
**Phiên bản:** v14.0 — Phase 25: Contrarian P0 Remediation, Golden Fixtures, Scan Observability & Shadow Mode  
**Trọng tâm:** *"Sửa lỗi P0 (tên trạng thái, bộ feature, nhánh B) trước khi tinh chỉnh bất kỳ ngưỡng nào. Chuyển đổi toàn bộ test sang Golden Test dùng fixture ghi lại từ BCTC thật (không gọi API sống). Bổ sung biểu đồ phân phối lý do block & completeness kèm cảnh báo khẩn cấp khi 100% mã bị chặn cùng lý do. Kích hoạt Contrarian ở chế độ Shadow/Report-only trong 60 phiên, lưu vết vào decision_records & decision_forward_returns để lấy bằng chứng thực nghiệm trước khi cấp quyền RECOMMEND_BUY."*

---

## 1. MỤC TIÊU PHIÊN BẢN v14.0 (PHASE 25)

1. **TASK-0071: Fix P0 State Machine, Feature Set & Branch B (P0):**
   - Chuẩn hóa Enum State đồng nhất với spec TASK-0070 §1.2: `STATE_NEAR_PANIC_WATCH`, `STATE_EXTREME_FEAR_WATCH`, `STATE_NORMAL`.
   - Tách biệt độc lập Nhánh B (Archetype Overlays cho Banking, Real Estate, Securities, Non-financial) thành helper `_check_archetype_specific_gates`.
   - Sửa lỗi trùng lặp ngưỡng L24–25 (`CONTRARIAN_MAX_RSI_NORMAL` trùng `CONTRARIAN_MAX_RSI_WATCH = 35.0`).
   - Ban hành văn bản kiến trúc `ADR-0009-Contrarian-State-Machine.md`.

2. **TASK-0072: Golden Tests bằng Fixture Ghi Lại (No Live API):**
   - Thu thập snapshot BCTC thật qua `scripts/record_fixtures.py`, lưu JSON tĩnh tại `tests/fixtures/` (`fpt_q4_2024.json`, `vnm_q4_2024.json`, `hpg_cfo_neg.json`).
   - Xây dựng `tests/test_golden_contrarian.py` kiểm định: FPT/VNM với BCTC thật phải pass Survival Gate (tier $\ge 2$); mã có CFO âm bắt buộc bị chặn tại `SURVIVAL_QUALITY`.
   - Phân lập test live bằng marker `@pytest.mark.live` (loại khỏi CI).

3. **TASK-0073: Scan Block Distribution & 100% Homogeneous Gate Alarm:**
   - Xây dựng `get_scan_block_distribution(session_id: str) -> dict` trong `db_manager.py`.
   - Thiết lập cơ chế phát hiện bất thường: nếu 100% mã bị chặn bởi cùng một gate duy nhất, kích hoạt cờ `alarm_100pct_same_gate` và gửi cảnh báo khẩn qua Discord.
   - Thêm biểu đồ Bar chart phân phối Gate và đồng hồ Completeness ratio vào Streamlit tab `tab_alpha_tracker.py`.

4. **TASK-0074: Contrarian Shadow/Report-Only Mode 60 Phiên:**
   - Mặc định bật `SHADOW_MODE_ACTIVE = True`: không phát lệnh `RECOMMEND_BUY` thật, chuyển trạng thái thành `SHADOW_BUY` (`can_buy = False`).
   - Ghi nhận đầy đủ facts/context vào `decision_records` với `primary_rejection_gate = "SHADOW_MODE"`.
   - Cron script `scripts/update_shadow_returns.py` cập nhật forward returns T+1, T+5, T+10, T+20.
   - Cổng tốt nghiệp shadow (`should_graduate_from_shadow()`): $\ge 60$ phiên, $\ge 30$ mẫu T+10, Hit rate $> 55\%$.

---

## 2. KẾ THỪA CÁC CHỐT CHẶN PHIÊN BẢN TRƯỚC (v6.1 - v13.0)

1. **Phase 24 (v13.0):** Reversal Confirmed & Entry Eligible Layer (Price Action, Higher Low, Volume Confirm).
2. **Phase 23 (v12.0):** Advanced FQ-Score 3-Tier Architecture & Risk Overlays (CFO Proxy, Decoupled Hard Veto).
3. **Phase 22 (v11.1):** Contrarian Quant & Architecture Upgrade (Valuation Watch, F-Score Data Confidence).
4. **Phase 21 (v10.1):** Data Resilience & Fallback Valuation.
5. **Phase 20 (v10.0):** Contrarian 4-State Machine (Continuous Panic Score).
6. **Phase 19 (v9.0):** Contrarian 5-Layer Framework (Quality De-rating vs Value Trap, Event Risk VETO).
7. **Phase 18 (v8.1):** Contrarian Panic Buy Module cơ bản (RSI <= 30).
8. **Phase 17 (v8.0):** Risk Governance Completion.
9. **Phase 16 (v7.6):** Signal Integrity & Audit Cleanup.
10. **Phase 15 (v7.5):** Unified Entry Gate (7 tầng thống nhất, Macro Gate toàn tuyến).
11. **Phase 14 (v7.4):** Data & Valuation Plumbing.
12. **Phase 13 (v7.3):** Core Valuation Re-Architecture.

---

## 3. NGUYÊN TẮC QUẢN TRỊ RỦI RO & BẢO TOÀN KIẾN TRÚC

- **P0 First Before Thresholds:** Không bao giờ tinh chỉnh ngưỡng định lượng khi cấu trúc state machine và danh pháp enum đang bị lệch.
- **Evidence-First (Không Test API Sống):** Golden test dựa trên fixture thực nghiệm bất biến. Không để CI phụ thuộc vào tính sẵn sàng của mạng hoặc API bên ngoài.
- **Observability Over False Positives:** Không ăn mừng khi 100% mã bị chặn; một đợt quét đồng nhất 100% cùng lý do là dấu hiệu hỏng hóc hệ thống cần báo động khẩn cấp.
- **Shadow Mode Quarantine:** Chiến lược mới bắt buộc phải trải qua 60 phiên thử nghiệm và đạt kỳ vọng xác suất thực tế trước khi cấp quyền can thiệp vào tài khoản vốn thật.

---

## 4. TIÊU CHUẨN KỸ THUẬT (QUALITY GATE)

- **SonarCloud:** Cognitive Complexity < 15 (S3776), `logging.exception()` trong except (S8572), không trùng lặp chuỗi $\ge 3$ lần (S1192), duplicate lines density $\le 3.0\%$. Zero duplicate logic giữa sync/async.
- **Ruff:** `ruff check --fix .` đảm bảo exit code 0 và imports chuẩn `isort`.
- **Test Coverage:** $\ge 80\%$ (mục tiêu $85 - 95\%+$) cho toàn bộ module contrarian và governance mới; 100% unit tests pass.
- **Local Workspace Hygiene:** Không stage hay commit bất kỳ file nghiên cứu nội bộ nào (`stock_ai_roadmap.md`, `danh_gia_he_thong_quy_fund.md`, `idea.md`...).

