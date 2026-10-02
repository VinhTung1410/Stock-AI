# 🎯 YÊU CẦU DỰ ÁN (CLIENT BRIEF) - VERSION 7.5

**Tên dự án:** Stock-AI / AI Investment Decision & Research Platform  
**Phiên bản:** v7.5 — Phase 15: Unified Entry Gate (Cơ chế Kiểm Soát Cổng Vào Thống Nhất 7 Tầng & Chuẩn hóa Điểm Vào Lệnh)  
**Trọng tâm:** *"Hợp nhất toàn bộ 4 nhánh ra quyết định vào lệnh (Watchlist Alert, Market Scanner, 2-Pass Web Report, và Smart Investment Committee) qua một cổng kiểm soát thống nhất duy nhất `evaluate_entry_gates()` trong module mới `entry_gates.py`. Triệt tiêu hoàn toàn tình trạng phân mảnh logic bảo vệ vốn nơi scanner bỏ qua Macro Gate, Watchlist hard-code conviction=75 và fail-open, 2-Pass ngầm định archetype GROWTH, và Smart Committee bị ảo giác LLM lấn át phân tích định lượng. Đồng bộ hóa chặt chẽ thời điểm kích hoạt Cooldown chỉ sau khi Discord dispatch thành công; và chuẩn hóa ánh xạ trạng thái Active Screener."*

---

## 1. MỤC TIÊU PHIÊN BẢN v7.5 (PHASE 15: UNIFIED ENTRY GATE)

1. **TASK-0046: Unified Entry Gate Engine (`entry_gates.py` - Mục 15.0):**
   - **Vấn đề cốt tử:** Cả 4 luồng ra quyết định (`Watchlist Alert`, `scan_market_opportunities`, `2-Pass Web`, `Smart Committee`) áp dụng các bộ lọc chắp vá, không đồng nhất, dẫn đến rò rỉ rủi ro nghiêm trọng khi mã xấu vượt qua một số luồng kiểm tra lỏng lẻo.
   - **Giải pháp:**
     - Xây dựng module mới `entry_gates.py` với hàm trung tâm `evaluate_entry_gates()`, thực thi tuần tự 7 tầng cổng kiểm định:
       - **Tầng 0 (Macro Regime):** Chặn toàn bộ lệnh MUA khi VN-Index ở trạng thái `DOWNTREND` (kèm Macro Hysteresis). Có fail-safe: nếu thiếu dữ liệu VN-Index $\rightarrow$ cảnh báo WARNING và giảm 50% vị thế, không fail-open.
       - **Tầng 1 (Data Gate):** Freshness + BCTC sanity check. Block nếu `score < 65` hoặc `recommendation_allowed=False`.
       - **Tầng 2 (Financial Health):** F-Score $\le 3$ hoặc Z-Score Distress $\rightarrow$ Block.
       - **Tầng 3 (Valuation & MoS):** Yêu cầu `mos_is_informative=True` và `mos_pct \ge threshold[archetype]`.
       - **Tầng 4 (Technical Trend & Momentum):** Yêu cầu `tech_signal \in BULLISH_SET`. Chặn bắt dao rơi khi cổ phiếu nằm dưới MA20/MA50 dốc xuống.
       - **Tầng 5 (Quant Conviction):** Yêu cầu `conviction_score \ge 60`.
       - **Tầng 6 (PM Veto / Governance):** Chặn nếu có cờ VETO từ Portfolio Guard hoặc các điều kiện xung đột danh mục.
     - Trả về cấu trúc chuẩn `EntryGateResult` chứa đầy đủ: `can_buy` (bool), `blocked_by` (tên tầng chặn), `blocking_reason`, `metrics`, và `position_size_multiplier`.

2. **TASK-0047: Macro Gate Wiring Across All Execution Paths (Mục 15.1):**
   - **Vấn đề:** Market Scanner (`scan_market_opportunities`) và Smart Committee hiện tại không chặn khuyến nghị Mua khi VN-Index Downtrend nếu chỉ nhìn vào tín hiệu kỹ thuật đơn lẻ của cổ phiếu.
   - **Giải pháp:** Tích hợp `evaluate_entry_gates()` vào `scan_market_opportunities()`, đảm bảo khi thị trường Downtrend thì Scanner trả về 0 BUY alerts.

3. **TASK-0048: Discord-Confirmed Cooldown Timing (Mục 15.2):**
   - **Vấn đề:** `record_signal_cooldown` hiện đang được gọi trước khi gửi cảnh báo Discord hoặc chạy độc lập, khiến mã bị khóa cooldown dù Discord alert thất bại (network timeout, rate limit).
   - **Giải pháp:** Di chuyển lệnh ghi nhận cooldown chỉ thực thi sau khi nhận được phản hồi xác nhận `success=True` từ webhook/dispatcher Discord.

4. **TASK-0049: 2-Pass Archetype & Sector Wiring (Mục 15.3):**
   - **Vấn đề:** 2-Pass Web report default archetype về `GROWTH` nếu không rõ sector, dẫn đến định giá sai lệch (ví dụ BID bị gán PE tăng trưởng).
   - **Giải pháp:** Truyền `symbol`, tra cứu chính xác `sector` từ danh bạ chuẩn; nếu archetype là `UNKNOWN` và không đủ thông tin $\rightarrow$ tự động Block BUY, tuyệt đối không default `GROWTH`.

5. **TASK-0050: Smart Committee Quant Hard Gate Arbitrator (Mục 15.4):**
   - **Vấn đề:** Smart Committee cho phép LLM quyết định `STRONG_BUY` ngay cả khi MoS âm hoặc vi phạm Data Gate.
   - **Giải pháp:** Chạy `evaluate_entry_gates()` sau khi nhận output từ LLM. LLM chỉ có quyền Veto (hạ bậc khuyến nghị hoặc từ chối) chứ không thể mở cổng Mua nếu Quant Engine đã đánh dấu vi phạm.

6. **TASK-0051: Active Screener Status Mapping Fix (Mục 15.5):**
   - **Vấn đề:** Active Screener lọc trạng thái không khớp giữa `RECOMMEND_BUY` và `HIGH_CONVICTION`, khiến danh sách cơ hội hiển thị rỗng.
   - **Giải pháp:** Chuẩn hóa ánh xạ trạng thái giữa kết quả của Quant Engine và giao diện hiển thị Screener.

---

## 2. KẾ THỪA CÁC CHỐT CHẶN PHIÊN BẢN TRƯỚC (v6.1 - v7.4)

1. **Phase 14 (v7.4):** Data & Valuation Plumbing (Dẫn truyền `fin_dict` thực vào toàn bộ mô hình định giá, sửa ánh xạ cột tiếng Việt danh mục P&L/Trailing Stop, khóa cứng `mos_is_informative=False` cho Cyclical/BĐS khi thiếu BCTC, so khớp độ tươi ngày hiện tại cho Context Engine).
2. **Phase 13 (v7.3):** Core Valuation Re-Architecture, Structural Risk Protection & Macro Hysteresis (Forward EPS $\times$ Median P/E, SOTP MWG, Structural Stop-loss, Macro Hysteresis $\pm 1.5\%$, `FLAG_DATA_STALE_FREEZE`).
3. **Phase 12 (v7.2):** Compounder & Retail Flow Gatekeeper (Anti-Synthetic MoS, Chuẩn hóa `target_buy`, Bộ lọc xu hướng trung hạn MA100/MA200, Phạt xả ròng khối ngoại).
4. **Phase 11 (v7.1):** Cyclical Valuation Overhaul (Peak Earnings Trap, Normalized EPS 5 năm, Regional Peer Benchmark, Sector Risk Flags).
5. **Phase 10 (v7.0):** Real Estate & Holding Valuation Overhaul (SOTP Sanity Check, Core Earnings Ratio, Survival Gate, P/B Mean Reversion Guardrail).
6. **Phase 8 (v6.3):** Context Engine & PTKT Hàng ngày (Báo cáo TCBS vào `market_context.json`, Code MA200 luôn thắng nhận định chuyên gia).
7. **Phase 1-7 (v5.1 - v6.2):** Evidence Integrity, Signal Lifecycle bất biến, Data Gate nhị phân cứng, 4 tầng Fact/Inference/Hypothesis.

---

## 3. NGUYÊN TẮC QUẢN TRỊ RỦI RO & BẢO TOÀN KIẾN TRÚC

- **Single Gatekeeper Principle (Một Cổng Kiểm Soát Duy Nhất):** Không một luồng thực thi nào được phép tự quyết định mua mà không đi qua `evaluate_entry_gates()`.
- **Quant Rules Over LLM (Định Lượng Thắng Định Tính):** LLM chỉ là công cụ tổng hợp bằng chứng và phát hiện rủi ro phi cấu trúc (Veto). Nếu mô hình định lượng không cấp phép, LLM không có quyền mua.
- **Fail-Safe Macro Exposure:** Nếu mất kết nối vĩ mô, hệ thống tự động co cụm phòng thủ (giảm size 50%), không mạo hiểm giải ngân toàn phần.
- **Transaction Idempotency:** Chỉ khóa cooldown khi lệnh thông báo/giao dịch đã thực sự được dispatch thành công.

---

## 4. TIÊU CHUẨN KỸ THUẬT (QUALITY GATE)

- **SonarCloud:** Cognitive Complexity < 15 (S3776), `logging.exception()` trong except (S8572), không trùng lặp chuỗi $\ge 3$ lần (S1192), duplicate lines density $\le 3.0\%$.
- **Ruff:** `ruff check --fix .` đảm bảo exit code 0 và imports chuẩn `isort`.
- **Test Coverage:** $\ge 80\%$ (mục tiêu $85 - 95\%+$) cho module `entry_gates.py` và các điểm tích hợp.
- **TDD (Test-Driven Development):** Viết unit & integration tests `tests/test_entry_gates.py` kiểm thử đầy đủ 7 tầng, 4 callers, các trường hợp biên và fail-safe.