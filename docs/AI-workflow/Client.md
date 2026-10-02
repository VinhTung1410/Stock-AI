# 🎯 YÊU CẦU DỰ ÁN (CLIENT BRIEF) - VERSION 8.0

**Tên dự án:** Stock-AI / AI Investment Decision & Research Platform  
**Phiên bản:** v8.0 — Phase 17: Risk Governance Completion (Hoàn Thiện Tầng Quản Trị Rủi Ro & Chuẩn Hóa Vị Thế)  
**Trọng tâm:** *"Đấu nối hoàn chỉnh Tầng 7 (Risk Governance & Position Sizing) vào `evaluate_entry_gates()`; chuyển đổi quy mô vị thế `position_size_pct` sang số thực `float` có tính toán thay vì chuỗi hard-code; thiết lập chuẩn enum canonical `RegimeState` và chuẩn hóa `check_regime_conflict`; khắc phục ánh xạ nhãn cảnh báo `send_trade_signal_alert` (THEO DÕI màu vàng 🟡, CẢNH BÁO màu cam ⚠️, không ngộ nhận thành BÁN 🔴); nâng cấp `detect_gdkhq_event` đối soát với lịch sự kiện doanh nghiệp thực `fetch_corporate_dividends` để tránh nhầm lẫn Gap-Down do tin xấu với chia cổ tức; bảo đảm Kill Switch thực sự cắt giảm $\ge 30\%$ quy mô giải ngân thực tế (số thực); và chuẩn hóa vùng kích hoạt Watchlist Value Buy RSI $\in [30, 50]$ kèm kiểm tra MoS và Macro."*

---

## 1. MỤC TIÊU PHIÊN BẢN v8.0 (PHASE 17: RISK GOVERNANCE COMPLETION)

1. **TASK-0058: Canonical `RegimeState` Enum & Conflict Resolver (Mục 17.0):**
   - **Vấn đề cốt tử:** Tồn tại hai định nghĩa regime song song (MA20/MA50 ngắn hạn vs MA200 dài hạn) và kiểm tra bằng chuỗi tự do, khiến `check_regime_conflict` có thể sai lệch hoặc thiếu chuẩn hóa.
   - **Giải pháp:**
     - Thiết lập enum canonical `RegimeState`: `UPTREND`, `SIDEWAYS`, `DOWNTREND`, `UNKNOWN`.
     - Cung cấp hàm `get_canonical_regime()` làm nguồn chân lý duy nhất (Single Source of Truth) từ MA200 hysteresis.
     - Cập nhật `check_regime_conflict()` làm việc trực tiếp hoặc chuẩn hóa qua `RegimeState`.

2. **TASK-0059: Wire Tầng 7 vào `evaluate_entry_gates()` & Position Sizing Float (Mục 17.1):**
   - **Vấn đề cốt tử:** Các hàm quản trị rủi ro `check_adv20_liquidity_absorption()`, `check_sector_concentration()`, `calculate_drawdown_controlled_sizing()` chưa được gọi trong Unified Entry Gate; `position_size_nav` trả về chuỗi hard-code `"15-20% NAV"`.
   - **Giải pháp:**
     - Đấu nối Tầng 7 (Risk Governance & Position Sizing) vào `evaluate_entry_gates()`.
     - Chặn tuyệt đối (`can_buy = False`, `position_size_pct = 0.0`) khi thanh khoản ADV20 < 2.0 tỷ VND.
     - Tính toán `position_size_pct: float` dựa trên Half-Kelly, Drawdown Breaker, Hysteresis Penalty và Liquidity Absorption.

3. **TASK-0060: Fix Alert Label & Color Mapping trong `send_trade_signal_alert` (Mục 17.2):**
   - **Vấn đề:** Mọi non-MUA action đều bị map thành "BÁN / HẠ TỶ TRỌNG" với màu đỏ `0xE74C3C`, khiến cảnh báo "THEO DÕI" hoặc "CẢNH BÁO" làm người dùng hoang mang như tín hiệu cắt lỗ/bán tháo.
   - **Giải pháp:**
     - Thiết lập bảng ánh xạ `ACTION_DISPLAY` chuẩn mực:
       - `MUA` / `TÍCH LŨY` / `BUY` $\rightarrow$ `🟢 MUA / TÍCH LŨY` (Xanh lá `0x2ECC71`).
       - `THEO DÕI` / `WATCH` $\rightarrow$ `🟡 THEO DÕI` (Vàng `0xF1C40F`).
       - `GIẢM` / `THOÁT` $\rightarrow$ `🔴 GIẢM / THOÁT` (Đỏ `0xE74C3C`).
       - `CẢNH BÁO` $\rightarrow$ `⚠️ CẢNH BÁO — KHÔNG PHẢI BÁN` (Cam `0xE67E22`).
       - `GDKHQ` $\rightarrow$ `📅 SỰ KIỆN GDKHQ` (Xanh dương `0x3498DB`).

4. **TASK-0061: Corporate Actions Shield với `fetch_corporate_dividends` Thật (Mục 17.3):**
   - **Vấn đề:** `detect_gdkhq_event` chỉ dựa trên suy đoán Opening Gap $\le -4.5\%$ và VN-Index $\ge -1.5\%$. Nếu cổ phiếu gap-down do tin xấu bất ngờ, hệ thống bỏ qua Stop-Loss vì ngộ nhận là chia cổ tức.
   - **Giải pháp:**
     - Tích hợp đối soát với sự kiện chia cổ tức thực qua `fetch_corporate_dividends()`.
     - Nếu có ngày GDKHQ hôm nay $\rightarrow$ xác nhận `"GDKHQ_CONFIRMED"`.
     - Nếu không có sự kiện GDKHQ $\rightarrow$ phân loại `"GAP_DOWN_NEWS"` để kiểm tra ngay ngưỡng Stop-Loss.

5. **TASK-0062: Kill Switch Giảm Quy Mô Vị Thế Bằng Số Thực (Mục 17.4):**
   - **Vấn đề:** Khi kích hoạt Kill Switch phòng thủ, hệ thống chỉ nối chuỗi văn bản cảnh báo mà không thực sự cắt giảm `position_size_pct`.
   - **Giải pháp:**
     - Khi Kill Switch hoặc Regime Conflict Hysteresis hoạt động, nhân giảm $50\%$ giá trị `position_size_pct` thật (`actual_size = base_size * 0.5`).

6. **TASK-0063: Chuẩn Hóa Vùng Kích Hoạt Watchlist Value Buy (Mục 17.5):**
   - **Vấn đề:** Điều kiện kích hoạt cũ `RSI <= 32` là hành vi bắt đáy dao rơi rủi ro, mâu thuẫn với chiến lược Value Buy đầu tư giá trị trung dài hạn.
   - **Giải pháp:**
     - Điều kiện kích hoạt Value Buy chuẩn mực: $RSI \in [30, 50]$ AND `tech_signal` $\in$ `BULLISH_SET` AND $MoS \ge threshold$ AND Macro $\ne$ `DOWNTREND`.

---

## 2. KẾ THỪA CÁC CHỐT CHẶN PHIÊN BẢN TRƯỚC (v6.1 - v7.6)

1. **Phase 16 (v7.6):** Signal Integrity & Audit Cleanup (Chỉ lưu `BUY_ACTIONS`, Cooldown Multi-key, Adapter Lifecycle đầy đủ 5 trường calibration, Time-aware Audit fill, Entry Zone 5% discount, Bảo vệ Watchlist thủ công `is_manual_protected`).
2. **Phase 15 (v7.5):** Unified Entry Gate (`entry_gates.py` 7 tầng thống nhất, Macro Gate toàn tuyến, Discord-confirmed cooldown, 2-Pass chuẩn hóa ngành, Smart Committee Quant Arbitrator).
2. **Phase 14 (v7.4):** Data & Valuation Plumbing (Dẫn truyền `fin_dict` thực vào toàn bộ mô hình định giá, sửa ánh xạ cột tiếng Việt danh mục P&L/Trailing Stop, khóa cứng `mos_is_informative=False` cho Cyclical/BĐS khi thiếu BCTC).
3. **Phase 13 (v7.3):** Core Valuation Re-Architecture, Structural Risk Protection & Macro Hysteresis (Forward EPS $\times$ Median P/E, SOTP MWG, Structural Stop-loss, Macro Hysteresis $\pm 1.5\%$).
4. **Phase 12 (v7.2):** Compounder & Retail Flow Gatekeeper (Anti-Synthetic MoS, Chuẩn hóa `target_buy`, Bộ lọc xu hướng trung hạn MA100/MA200, Phạt xả ròng khối ngoại).
5. **Phase 11 (v7.1):** Cyclical Valuation Overhaul (Peak Earnings Trap, Normalized EPS 5 năm, Regional Peer Benchmark, Sector Risk Flags).
6. **Phase 10 (v7.0):** Real Estate & Holding Valuation Overhaul (SOTP Sanity Check, Core Earnings Ratio, Survival Gate, P/B Mean Reversion Guardrail).
7. **Phase 8 (v6.3):** Context Engine & PTKT Hàng ngày (Báo cáo TCBS vào `market_context.json`, Code MA200 luôn thắng nhận định chuyên gia).
8. **Phase 1-7 (v5.1 - v6.2):** Evidence Integrity, Signal Lifecycle bất biến, Data Gate nhị phân cứng, 4 tầng Fact/Inference/Hypothesis.

---

## 3. NGUYÊN TẮC QUẢN TRỊ RỦI RO & BẢO TOÀN KIẾN TRÚC

- **Signal Purity Principle (Bảo Toàn Tính Thuần Khiết Của Tín Hiệu):** Bảng `signals` chỉ đại diện cho các vị thế giải ngân vốn thực tế. Mọi phân tích theo dõi, cảnh báo hay thoát hàng không được phép giả mạo lệnh Long.
- **Auditing Realism (Kiểm Toán Thực Tế Khắt Khe):** Không kiểm toán trên các mức giá không thể khớp trong thực tế (như giá đáy buổi sáng cho tín hiệu phát buổi chiều).
- **User Preference Sovereignty:** Watchlist do người dùng tự tay chọn phải được tôn trọng và bảo vệ tuyệt đối trước các thuật toán prune tự động.

---

## 4. TIÊU CHUẨN KỸ THUẬT (QUALITY GATE)

- **SonarCloud:** Cognitive Complexity < 15 (S3776), `logging.exception()` trong except (S8572), không trùng lặp chuỗi $\ge 3$ lần (S1192), duplicate lines density $\le 3.0\%$.
- **Ruff:** `ruff check --fix .` đảm bảo exit code 0 và imports chuẩn `isort`.
- **Test Coverage:** $\ge 80\%$ (mục tiêu $85 - 95\%+$) cho logic mới; 100% test case kiểm thử biên, cooldown, adapter và prune protection.
- **TDD (Test-Driven Development):** Viết unit & integration tests `tests/test_signal_integrity.py` kiểm thử đầy đủ các kịch bản lỗi trước khi chỉnh sửa mã nguồn.