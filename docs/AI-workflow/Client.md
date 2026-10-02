# 🎯 YÊU CẦU DỰ ÁN (CLIENT BRIEF) - VERSION 7.6

**Tên dự án:** Stock-AI / AI Investment Decision & Research Platform  
**Phiên bản:** v7.6 — Phase 16: Signal Integrity & Audit Cleanup (Chuẩn Hóa Dữ Liệu Tín Hiệu & Dọn Dẹp Bảng Kiểm Toán)  
**Trọng tâm:** *"Khắc phục triệt để tình trạng ô nhiễm dữ liệu có hệ thống tại bảng `signals` và `signal_lifecycle` do việc lưu vô điều kiện các quyết định THEO DÕI / GIẢM / HẠ TỶ TRỌNG như lệnh mua thật, làm sai lệch kết quả kiểm định Alpha/Sharpe và làm nghẽn trần mở vị thế MAX_OPEN_POSITIONS; sửa lỗi truy vấn Cooldown Supabase chỉ lọc '%BUY%' làm sót các lệnh '🟢 MUA'; chuẩn hóa adapter `save_signal_lifecycle` giải quyết xung đột key `target_price` vs `initial_target_price` để phục hồi pipeline Calibration/IC/A-B Testing; chuẩn hóa cơ chế khớp giá kiểm toán Time-Aware và đếm `days_elapsed` theo phiên giao dịch thực tế; sửa lỗi `target_buy` trong Watchlist tự động tránh kích hoạt tức thì sau cooldown; và bổ sung cờ `is_manual_protected` bảo vệ danh mục người dùng theo dõi."*

---

## 1. MỤC TIÊU PHIÊN BẢN v7.6 (PHASE 16: SIGNAL INTEGRITY & AUDIT CLEANUP)

1. **TASK-0052: Conditional `save_quant_signal` (Mục 16.0):**
   - **Vấn đề cốt tử:** Hàm `save_quant_signal` hiện đang lưu mọi quyết định (kể cả "THEO DÕI", "GIẢM / THOÁT", "TỪ CHỐI") vào bảng `signals`. Hậu quả: các bản ghi theo dõi bị đối soát như lệnh mua Long đang mở, chiếm dụng hạn mức tối đa `MAX_OPEN_POSITIONS` và tạo cooldown giả.
   - **Giải pháp:**
     - Thiết lập bộ lọc `BUY_ACTIONS = {"🟢 MUA", "🟢 TÍCH LŨY", "🟢 ACCUMULATE", "🟢 VALUE BUY", "RECOMMEND_BUY", "MUA", "BUY"}`.
     - `save_quant_signal` CHỈ ĐƯỢC GHI vào bảng `signals` khi hành động nằm trong `BUY_ACTIONS`.

2. **TASK-0053: Cooldown Key Matching Fix (Mục 16.1):**
   - **Vấn đề cốt tử:** Hàm `check_symbol_recent_signal` và truy vấn database Supabase chỉ lọc `action LIKE '%BUY%'`, trong khi hệ thống lưu nhãn tiếng Việt `action = '🟢 MUA'` hoặc `'🟢 TÍCH LŨY'`. Hậu quả: Cooldown Supabase bỏ sót hầu hết các tín hiệu Mua thực tế, dẫn đến việc bắn cảnh báo lặp lại cho cùng một mã.
   - **Giải pháp:**
     - Mở rộng điều kiện kiểm tra cooldown: `WHERE action LIKE '%MUA%' OR action LIKE '%TÍCH LŨY%' OR action LIKE '%ACCUMULATE%' OR action LIKE '%BUY%'`.

3. **TASK-0054: `save_signal_lifecycle` Adapter & Calibration Fields (Mục 16.2):**
   - **Vấn đề:** Caller truyền `initial_target_price` nhưng `save_signal_lifecycle` đọc key `target_price`, dẫn đến trường giá mục tiêu trong DB bị ghi nhận bằng 0 (`target=0`), làm tê liệt các pipeline AI Calibration, Spearman IC, và A/B Testing.
   - **Giải pháp:**
     - Bổ sung adapter: `target_price = kwargs.get("target_price") or kwargs.get("initial_target_price", 0.0)`.
     - Đảm bảo điền đầy đủ 5 trường hiệu chuẩn: `entry_price`, `target_price`, `stop_loss`, `f_score`, `mos_pct`.

4. **TASK-0055: Time-Aware Audit Fill & Trading Days Elapsed (Mục 16.3):**
   - **Vấn đề:** Khớp lệnh kiểm toán (Audit Fill) đang lấy giá High/Low của toàn phiên mà không quan tâm giờ phát tín hiệu (nếu tín hiệu phát lúc 14:15 nhưng khớp giá Low buổi sáng là phi thực tế). Ngoài ra `days_elapsed` đang tính theo ngày lịch làm sai lệch chu kỳ T+5, T+20, T+60.
   - **Giải pháp:**
     - Tín hiệu phát sau 11:30 chỉ được khớp theo giá đóng cửa (Closing price) của phiên.
     - Tính `days_elapsed` dựa trên số ngày giao dịch thực tế (bỏ qua Thứ 7, Chủ Nhật và ngày lễ).

5. **TASK-0056: Entry Zone `target_buy` (Mục 16.4):**
   - **Vấn đề:** Hàm tạo ứng viên Watchlist tự động gán `target_buy = target_price` hoặc bằng thị giá hiện tại, khiến mã vừa hết 5 ngày cooldown là lại tự động kích hoạt bắn Mua ngay lập tức.
   - **Giải pháp:**
     - Neo `target_buy` theo vùng giá chiết khấu/hỗ trợ an toàn: `target_buy = tech_data.get("support_level", current_price * 0.95)` (yêu cầu chiết khấu tối thiểu 3-5% từ đỉnh hiện tại mới kích hoạt).

6. **TASK-0057: Manual Watchlist Protection Flag (Mục 16.5):**
   - **Vấn đề:** Cơ chế tự động dọn dẹp Watchlist (`prune_unsuitable_watchlist`) có thể xóa nhầm các mã cổ phiếu chiến lược do người dùng tự tay thêm vào khi thị trường điều chỉnh ngắn hạn (dính FALLING_KNIFE tạm thời).
   - **Giải pháp:**
     - Bổ sung cờ `is_manual_protected: True` và `added_by: "user"`.
     - Hàm prune bắt buộc bỏ qua không xóa các mục có `is_manual_protected=True` trừ khi có cờ `force_override=True`.

---

## 2. KẾ THỪA CÁC CHỐT CHẶN PHIÊN BẢN TRƯỚC (v6.1 - v7.5)

1. **Phase 15 (v7.5):** Unified Entry Gate (`entry_gates.py` 7 tầng thống nhất, Macro Gate toàn tuyến, Discord-confirmed cooldown, 2-Pass chuẩn hóa ngành, Smart Committee Quant Arbitrator).
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