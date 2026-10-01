# 🎯 YÊU CẦU DỰ ÁN (CLIENT BRIEF) - VERSION 7.2

**Tên dự án:** Stock-AI / AI Investment Decision & Research Platform  
**Phiên bản:** v7.2 — Phase 12: Compounder & Retail Valuation Integrity & Trend/Flow Gatekeeper (Chấm dứt Ảo ảnh Biên an toàn MoS Giả định, Chuẩn hóa Target Buy, và Bộ lọc Xu hướng / Dòng tiền Ngoại)  
**Trọng tâm:** *"Triệt tiêu hoàn toàn hiện tượng biên an toàn tự sinh cơ học (Synthetic MoS Tautology $15.3\% = \frac{1.18 - 1}{1.18}$) khi dữ liệu mỏ neo định giá bị quá hạn (stale); chuẩn hóa trường `target_buy` trong Watchlist (cấm gán bằng thị giá `current_price`); thiết lập bộ lọc xu hướng trung hạn (MA100/MA200) và điểm phạt xả ròng khối ngoại (Foreign Net Flow Penalty) cho bộ chấm điểm Conviction; bổ sung ngưỡng dừng lỗ bằng số cứng (Numerical Hard Stop) cho cơ chế `LongTermHoldingShield`; và cập nhật luận điểm phân tích doanh nghiệp bán lẻ (MWG: BHX có lãi, rủi ro chiết khấu holding)."*

---

## 1. MỤC TIÊU PHIÊN BẢN v7.2 (PHASE 12: VALUATION INTEGRITY & FLOW GATEKEEPER)

1. **TASK-0033: Anti-Synthetic MoS & Target Buy Integrity (Mục 12.0):**
   - **Xóa bỏ ảo ảnh MoS tự sinh:** Khi cổ phiếu thuộc nhóm `GROWTH_COMPOUNDER` (hoặc bất kỳ nhóm nào) bị quá hạn mỏ neo định giá đồng thuận (`consensus_stale == True` hoặc `cons_target <= 0`) và phải dùng hệ số nhân cố định, hệ thống đã đánh dấu cờ `mos_is_informative = False`.
   - **Chặn nạp Watchlist rác:** Hàm `_build_auto_watchlist_candidate()` và `sync_auto_watchlist()` trong `data_engine.py` **tuyệt đối không được sử dụng MoS giả định** này để đưa cổ phiếu vào Watchlist dưới mác `[AUTO_DISCOVERY]`.
   - **Sửa lỗi gán nhầm Target Buy:** Cấm tuyệt đối fallback `target_p = current_price` khi `target_price` là `None`. Nếu cổ phiếu đang ở trạng thái theo dõi (`WATCH_CONFIRMATION`), `target_buy` phải để `None` hoặc tính theo vùng mua kỹ thuật chiết khấu (Entry Zone), không được biến thị giá thành giá mục tiêu mua.
   - **Minh bạch hóa Logging:** Ghi nhận đầy đủ thông số: `current_price`, `fair_value`, `mos_pct`, `mos_is_informative`, `price_target`, `as_of_date` và công thức tính.

2. **TASK-0034: Trend Filter (MA100/MA200) & Foreign Flow Penalty (Mục 12.1):**
   - **Đánh giá Kỹ thuật đa khung thời gian:**
     - Không chỉ nhìn MA20 ngắn hạn. Nếu thị giá nằm dưới **MA100** hoặc **MA200**, cấm gán nhãn "tích lũy trên các mốc hỗ trợ", khóa khuyến nghị `RECOMMEND_BUY`, hạ xuống trạng thái `WATCH_RECOVERY` hoặc `HIGH_RISK_REBOUND`.
   - **Điểm phạt xả ròng Khối ngoại (Foreign Net Flow Penalty):**
     - Tích hợp vào `calculate_conviction_score()`: Nếu khối ngoại bán ròng liên tục $\ge 3$ phiên hoặc bán ròng giá trị lớn ($> 50$ tỷ/phiên), trừ ngay **$10 - 15$ điểm Conviction** để phản ánh áp lực đè giá thực tế của dòng tiền tổ chức.
   - **Phân tách thanh khoản:** Phân định rõ giữa thanh khoản quy mô (Volume) và gia tốc thanh khoản (Volume Decay so với bình quân các quý trước).

3. **TASK-0035: Numerical Exit Rules cho LongTermHoldingShield (Mục 12.2):**
   - Khắc phục lỗ hổng thả trôi rủi ro của `LongTermHoldingShield`:
     - Bỏ qua rung lắc $-5\%$ đến $-7\%$ là cần thiết cho tích sản, nhưng **phải có chốt chặn số cứng (Numerical Circuit Breaker)**:
       - Cảnh báo khẩn cấp hoặc kích hoạt bán phòng vệ khi thị giá vi phạm mốc hỗ trợ trọng yếu (ví dụ: đóng cửa dưới $68.5k$ với Vol $> 1.5 \times ADV20$).
       - Cảnh báo vỡ luận điểm kinh doanh cơ bản nếu biên lợi nhuận gộp quý gần nhất sụt giảm dưới $20\%$ hoặc nợ xấu/trả chậm gia tăng đột biến.

4. **TASK-0036: Retail & Compounder Valuation Update (Mục 12.3):**
   - Cập nhật dữ liệu mỏ neo định giá mới cho nhóm Bán lẻ / Compounder (MWG, PNJ, FPT) với `last_updated` mới và Target Price cập nhật từ các báo cáo CTCK gần nhất.
   - Cập nhật luận điểm chất xúc tác: Bách Hóa Xanh đã bước qua điểm hòa vốn sang giai đoạn có lãi thực tế; bổ sung đánh giá rủi ro chiết khấu công ty mẹ (Holding discount) khi tái cấu trúc chuỗi.

---

## 2. KẾ THỪA CÁC CHỐT CHẶN PHIÊN BẢN TRƯỚC (v6.1 - v7.1)

1. **Cyclical Valuation Overhaul (v7.1 - Phase 11):**
   - Peak Earnings Trap Detector (`check_peak_earnings_trap()`), Normalized EPS 5 năm (`calculate_normalized_cyclical_earnings()`), Regional Peer Benchmark (`check_cyclical_peer_benchmark()`), Sector Risk Flags cho Dầu khí & Thép.
2. **Real Estate & Holding Valuation Overhaul (v7.0 - Phase 10):**
   - SOTP Sanity Check cho Holding Company (VIC), Core Earnings Ratio, Survival Gate, P/B Mean Reversion Guardrail.
3. **Context Engine & PTKT Hàng ngày (v6.3 - Phase 8):**
   - Trích xuất bối cảnh chuyên gia từ PDF TCBS vào `market_context.json`, Code MA200 luôn thắng nhận định chuyên gia.
4. **Hạ tầng Bằng chứng & Audit Idempotent (v6.1 - v6.2):**
   - Lưu vết 4 tầng FACT, INFERENCE, OPINION, COUNTERFACTUAL trong `decision_records`, Veto Only cho AI Committee.

---

## 3. NGUYÊN TẮC QUẢN TRỊ RỦI RO & BẢO TOÀN KIẾN TRÚC

- **Zero-Democracy Risk Gate:** MoS cơ học tự sinh ($1.18 \times P$) là dữ liệu vô giá trị (Uninformative); cấm sử dụng để kích hoạt lệnh mua hay nạp vào danh sách gợi ý.
- **Single Source of Truth (SSOT):** Tham số định giá, trạng thái MoS (`mos_is_informative`), và vùng mua bắt nguồn từ `quant_valuation.py` và được chuẩn hóa đồng nhất trong `data_engine.py`.
- **Fail-Safe & Graceful Degradation:** Khi mỏ neo định giá bị stale, hệ thống phải thành thật báo cáo `mos_is_informative: False`, hạ `confidence = "LOW"` và chuyển sang chế độ theo dõi kỹ thuật thuần túy, không tạo ra ảo ảnh an toàn.

---

## 4. TIÊU CHUẨN KỸ THUẬT (QUALITY GATE)

- **SonarCloud:** Cognitive Complexity < 15 (S3776), `logging.exception()` trong except (S8572), không trùng lặp chuỗi $\ge 3$ lần (S1192), duplicate lines density $\le 3.0\%$.
- **Ruff:** `ruff check --fix .` đảm bảo exit code 0.
- **Test Coverage:** $\ge 80\%$ (mục tiêu $85 - 95\%+$) cho toàn bộ logic mới; 100% test case kiểm thử biên và fail-safe branch.