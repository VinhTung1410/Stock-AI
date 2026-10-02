# 🎯 YÊU CẦU DỰ ÁN (CLIENT BRIEF) - VERSION 7.3

**Tên dự án:** Stock-AI / AI Investment Decision & Research Platform  
**Phiên bản:** v7.3 — Phase 13: Core Valuation Re-Architecture, Structural Risk Protection & Macro Hysteresis (Tái cấu trúc Cốt lõi Định giá Thực chất, Quản trị Rủi ro Cấu trúc & Cơ chế Trễ Cổng Vĩ mô)  
**Trọng tâm:** *"Xóa bỏ triệt để công thức định giá tự sinh cơ học ($FV = P \times 1.18$) trong nhóm Compounder để chuyển sang mô hình Forward EPS $\times$ Historical Median P/E và SOTP đa mảng; thiết lập cơ chế khóa cứng (Hard Reject) tại Data Gate khi cờ `mos_is_informative=False`; chuẩn hóa vòng đời mỏ neo đồng thuận (Consensus Lifecycle $\le 90$ ngày); thay thế dừng lỗ cứng $-7\%$ bằng Dừng lỗ Cấu trúc Kỹ thuật (Structural Stop Loss) và định cỡ vị thế phòng vệ Gap sàn (Liquidity Gap Risk Sizing); bổ sung vùng đệm trễ (Hysteresis Buffer $\pm 1.5\% - 2.0\%$) cho Cổng Vĩ mô VN-Index MA200 nhằm triệt tiêu whipsaw; và siết chặt kiểm tra độ tươi dữ liệu theo từng trường (`as_of_date` per field)."*

---

## 1. MỤC TIÊU PHIÊN BẢN v7.3 (PHASE 13: VALUATION RE-ARCHITECTURE & STRUCTURAL RISK)

1. **TASK-0037: Fundamental Compounder Valuation & Hard Ban on Synthetic Fair Value (Mục 13.0):**
   - **Xóa bỏ vĩnh viễn công thức FV phụ thuộc thị giá:** 
     - Loại bỏ hoàn toàn dòng code `fv_base = current_price * 1.18` và công thức hòa trộn tuyến tính `fv = fv_base * 0.6 + (consensus * 0.85) * 0.4` (bản chất là $0.708 \times P + 28.39$). Đây là lỗi sai toán học nghiêm trọng biến biên an toàn (MoS) thành định đề luôn dương giả tạo ($15.3\%$).
   - **Triển khai Mô hình Định giá Nội tại Thực chất (Intrinsic Valuation):**
     - **Mô hình 1 (Forward EPS & Historical Median P/E):** Định giá dựa trên $Forward\_EPS_{1-2Y} \times Median\_PE_{3-5Y}$ (đã loại trừ P/E ngoại lai ở các quý tạo đỉnh/đáy lợi nhuận bất thường).
     - **Mô hình 2 (SOTP - Sum Of The Parts cho Tập đoàn Bán lẻ/Holding như MWG):**
       + Chuỗi bán lẻ ICT (TGDĐ/ĐMX): Định giá theo P/E của mảng kinh doanh trưởng thành (Cash-cow, P/E $10 - 12x$).
       + Chuỗi Bách Hóa Xanh (BHX): Định giá theo P/S hoặc DCF tương ứng với giai đoạn tăng trưởng có lãi thực tế (Turnaround Phase).
       + Các mảng khác (An Khang, EraBlue...): Định giá theo giá trị sổ sách (P/B) hoặc chiết khấu thận trọng.
     - **Nguyên tắc Fail-Safe:** Nếu không đủ dữ liệu tài chính hoặc dự phóng để tính Forward EPS / SOTP, hệ thống phải trả về `fair_value = None`, ghi nhận `valuation_status = "INSUFFICIENT_DATA"`. **Tuyệt đối cấm dùng bất kỳ hệ số nhân nào với thị giá hiện tại để bịa ra Fair Value.**

2. **TASK-0038: MoS Informative Hard Gate & Consensus Lifecycle Management (Mục 13.1):**
   - **Hard Gate cho cờ `mos_is_informative`:**
     - Nếu `mos_is_informative == False` (hoặc `fair_value is None`), Data Gate và Decision Gate phải **loại bỏ hoàn toàn điểm Trụ cột Định giá (Valuation Pillar Score)**, không cấp điểm MoS trong Conviction Score.
     - Khóa cứng khuyến nghị MUA theo trường phái Giá trị / Compounder; chỉ cho phép chuyển sang trạng thái theo dõi kỹ thuật (`WATCH_TECHNICAL`) với điều kiện kỹ thuật xuất sắc độc lập.
   - **Chuẩn hóa Vòng đời Mỏ neo Đồng thuận (Consensus Target Lifecycle):**
     - Mọi dữ liệu mục tiêu giá của CTCK phải kèm theo metadata đầy đủ: `as_of_date`, `source` (CTCK: SSI, HSC, VCSC, Mirae Asset...), `target_price`, `analyst_thesis`.
     - **Ngưỡng quá hạn nghiêm ngặt (Max Staleness):** Nếu báo cáo định giá có tuổi thọ $> 90$ ngày so với ngày đánh giá hiện tại, mỏ neo bị coi là hết hạn (`is_expired = True`) và tự động bị loại khỏi mô hình định giá.

3. **TASK-0039: Structural Stop Loss & Liquidity Gap Risk Sizing (Mục 13.2):**
   - **Bãi bỏ Stop Loss cứng cơ học $-7\%$:**
     - Công thức `max(price - 2*ATR, price * 0.93)` tạo ra ngưỡng cắt lỗ $-7\%$ trùng đúng biên độ sàn 1 phiên của sàn HOSE, rất dễ rơi vào vùng quét thanh khoản (Liquidity Hunt) hoặc bị mắc kẹt khi cổ phiếu giảm sàn trắng bên mua (nhốt thanh khoản).
   - **Xác lập Dừng lỗ theo Cấu trúc Kỹ thuật (Structural Stop Loss):**
     - Điểm dừng lỗ phải được neo vào các mốc hỗ trợ cấu trúc thị trường thực tế: Đáy swing low gần nhất, đường trung bình quan trọng (MA50/MA100), hoặc cạnh dưới của hộp tích lũy (Base Support / Volume Profile POC) trừ đi một vùng đệm dao động $0.5 \times ATR(14)$.
   - **Định cỡ Vị thế Phòng vệ Rủi ro Gap Sàn (Liquidity Gap Risk Sizing):**
     - Nếu khoảng cách từ giá mua đến Stop-loss cấu trúc lớn (ví dụ $> 8 - 10\%$), hệ thống không được đẩy stop-loss lên cao vô căn cứ, mà phải **giảm quy mô vị thế (Position Size)** để giữ rủi ro tối đa trên mỗi thương vụ $\le 1.0\% - 1.5\%$ NAV.
     - Stress-test kịch bản Gap sàn 2 phiên liên tiếp (mức giảm $-14\%$) trước khi thanh khoản mở lại, đảm bảo tổn thất danh mục không vượt trần Risk Budget.

4. **TASK-0040: Macro Hysteresis Buffer & Anti-Whipsaw Filter (Mục 13.3):**
   - **Loại bỏ cơ chế ngắt nhị phân tức thời quanh MA200:**
     - Việc đóng/mở lệnh mua ngay khi VN-Index dao động quanh MA200 tạo ra tín hiệu giả liên tục (Whipsaw), gây thiệt hại mua đỉnh bán đáy khi thị trường đi ngang giằng co.
   - **Thiết lập Vùng đệm Trễ (Hysteresis Band):**
     - **Kích hoạt Phòng vệ Cứng (Hard Defensive Mode):** Chỉ kích hoạt khi VN-Index đóng cửa dưới MA200 với biên độ $> 1.5\%$ trong tối thiểu $\ge 2$ phiên liên tiếp, hoặc gãy MA200 với thanh khoản bán tháo lớn ($> 1.3 \times ADV20$).
     - **Mở lại Giải ngân (Re-entry Recovery Mode):** Chỉ mở lại việc tìm kiếm vị thế mua khi VN-Index đóng cửa vượt lại MA200 với đệm an toàn $+1.0\%$ và có xác nhận hồi phục của dòng tiền (phiên nỗ lực hồi phục hoặc bùng nổ theo đà FTD).

5. **TASK-0041: Field-Level Data Gate Freshness & Frozen Data Penalties (Mục 13.4):**
   - **Kiểm soát độ tươi theo từng trường dữ liệu (Field-Level Freshness):**
     - Data Gate phải theo dõi `as_of_date` cho từng nhóm chỉ tiêu tài chính: Báo cáo tài chính (Doanh thu, Lợi nhuận gộp, EPS), Chỉ số định giá thị trường (P/E, P/B, EV/EBITDA), và Dòng tiền (Operating Cash Flow).
   - **Xử phạt Dữ liệu Đóng băng (Frozen/Stale Data Penalty):**
     - Doanh nghiệp chậm công bố BCTC quá hạn quy định hoặc dữ liệu tài chính không có cập nhật mới $> 180$ ngày sẽ bị gắn cờ `DATA_STALE_FREEZE`, tự động trừ điểm uy tín dữ liệu và khóa quyền tham gia đề xuất đầu tư.

---

## 2. KẾ THỪA CÁC CHỐT CHẶN PHIÊN BẢN TRƯỚC (v6.1 - v7.2)

1. **Compounder & Retail Flow Gatekeeper (v7.2 - Phase 12):**
   - Anti-Synthetic MoS in Auto-Watchlist (`mos_is_informative == False` không được tự duyệt Watchlist), Chuẩn hóa `target_buy` (cấm gán bằng `current_price`), Bộ lọc xu hướng trung hạn MA100/MA200, Phạt xả ròng khối ngoại (Foreign Net Flow Penalty), Ngưỡng dừng số cứng cho `LongTermHoldingShield`.
2. **Cyclical Valuation Overhaul (v7.1 - Phase 11):**
   - Peak Earnings Trap Detector (`check_peak_earnings_trap()`), Normalized EPS 5 năm (`calculate_normalized_cyclical_earnings()`), Regional Peer Benchmark, Sector Risk Flags cho Dầu khí & Thép.
3. **Real Estate & Holding Valuation Overhaul (v7.0 - Phase 10):**
   - SOTP Sanity Check cho Holding Company (VIC), Core Earnings Ratio, Survival Gate, P/B Mean Reversion Guardrail.
4. **Context Engine & PTKT Hàng ngày (v6.3 - Phase 8):**
   - Trích xuất bối cảnh chuyên gia từ PDF TCBS vào `market_context.json`, Code MA200 luôn thắng nhận định chuyên gia.
5. **Hạ tầng Bằng chứng & Audit Idempotent (v6.1 - v6.2):**
   - Lưu vết 4 tầng FACT, INFERENCE, OPINION, COUNTERFACTUAL trong `decision_records`, Veto Only cho AI Committee.

---

## 3. NGUYÊN TẮC QUẢN TRỊ RỦI RO & BẢO TOÀN KIẾN TRÚC

- **Zero-Synthetic Valuation Principle:** Giá trị nội tại (Fair Value) bắt buộc phải xuất phát từ các biến số cơ bản của doanh nghiệp (Doanh thu, Lợi nhuận, Dòng tiền, Tài sản). Cấm tuyệt đối mọi hình thức phái sinh Fair Value từ thị giá cổ phiếu.
- **Structural Over Fixed Rule:** Quản trị rủi ro và điểm dừng lỗ phải thích ứng với cấu trúc thị trường, các vùng thanh khoản thực tế và biên độ biến động (ATR), không dùng các con số phần trăm cứng nhắc gây mất thanh khoản.
- **Macro Hysteresis Stability:** Cổng vĩ mô phải có độ trễ hợp lý để lọc bỏ nhiễu ngắn hạn, bảo vệ hệ thống khỏi hiện tượng kích hoạt và đảo chiều quyết định liên tục.
- **Single Source of Truth (SSOT):** Toàn bộ tham số định giá, trạng thái MoS, và ngưỡng rủi ro cấu trúc bắt nguồn từ `quant_valuation.py`, được kiểm duyệt qua `data_gate.py` và thực thi đồng nhất trong `quant_engine.py` và `portfolio_guard.py`.

---

## 4. TIÊU CHUẨN KỸ THUẬT (QUALITY GATE)

- **SonarCloud:** Cognitive Complexity < 15 (S3776), `logging.exception()` trong except (S8572), không trùng lặp chuỗi $\ge 3$ lần (S1192), duplicate lines density $\le 3.0\%$.
- **Ruff:** `ruff check --fix .` đảm bảo exit code 0 và imports chuẩn `isort`.
- **Test Coverage:** $\ge 80\%$ (mục tiêu $85 - 95\%+$) cho toàn bộ logic mới; 100% test case kiểm thử biên, fail-safe branch, và kịch bản gap sàn.
- **Walk-Forward Validation:** Các tham số định lượng (RSI, ATR buffer, Hysteresis band) phải được đối soát qua dữ liệu lịch sử nhiều chu kỳ để tránh tối ưu hóa quá mức (overfitting).