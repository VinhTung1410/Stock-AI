# Pre-Registration Giai đoạn 2: Thử nghiệm Shadow Cổng `BUY` & Bộ lọc Regime

**Ngày khóa tiêu chí:** `2026-11-12` (soạn thảo trước trong thời gian chờ đóng sổ 30 phiên Giai đoạn 1 để tránh thiên kiến theo kết quả phiên 30)  
**Trạng thái hiện tại:** **CHƯA KÍCH HOẠT** — chỉ bắt đầu thu thập dữ liệu sau khi hoàn tất đóng sổ Giai đoạn 1 (`v15.0_frozen_20261013`, mốc `2026-11-24` / `2026-12-01`).  
**Mục tiêu nghiên cứu:** Đánh giá xem việc nới lỏng có kiểm soát cổng `GATE_MACRO_REGIME` đối với các mã đã vượt qua toàn bộ 6 cổng nội tại có mang lại alpha thực nghiệm dương sau chi phí hay không, đồng thời kiểm soát rủi ro sụt giảm (drawdown).

---

## 1. Công bố Giả thuyết Khám phá Sau Xem Dữ liệu (Post-Hoc Disclosure)

> [!WARNING] Cảnh báo Phương pháp luận & Đếm Thử nghiệm (Snooping Counter #93)
> * **Nguồn gốc giả thuyết:** Ý tưởng thiết lập các nhánh thử nghiệm `SHADOW_BUY` xuất phát từ quan sát thực nghiệm khám phá trên **22 phiên giao dịch** (`14/10/2026` → `12/11/2026`) của Giai đoạn 1.
> * **Tính chất trong mẫu (In-Sample):** 22 phiên này đóng vai trò tập dữ liệu khám phá (exploratory dataset) dùng để hình thành giả thuyết (hypothesis generation). Tuyệt đối **không được trích dẫn** dữ liệu của 22 phiên này như bằng chứng kiểm định ngoài mẫu (out-of-sample validation).
> * **Kiểm toán Snooping:** Chuỗi phân tích này đã được ghi nhận chi tiết thành từng bước riêng biệt vào `data/snooping_counter.json` (từ `S1_SPLIT_23OCT` đến `S7_COOLDOWN_SECTOR`, đưa tổng số lần kiểm toán/snooping từ 86 lên **93**). Mọi kết luận khoa học về Giai đoạn 2 chỉ được rút ra từ các phiên giao dịch phát sinh hoàn toàn mới sau ngày kích hoạt.

---

## 2. Định nghĩa Mã nguồn Tường minh của `SHADOW_BUY`

Để tránh hiện tượng nới lỏng tùy tiện hoặc lẫn lộn khái niệm, một bản ghi chỉ được gán nhãn `SHADOW_BUY` cho một nhánh thử nghiệm khi thỏa mãn **toàn bộ 6 tầng cổng nội tại** trong kiến trúc 7 cổng sản xuất, duy nhất cổng `GATE_MACRO_REGIME` được đánh giá theo tiêu chí riêng của từng nhánh:

```
[KIẾN TRÚC 7 CỔNG KIỂM SOÁT]
1. GATE_DATA_HEALTH: Dữ liệu giá/khối lượng/BCTC hợp lệ, không stale (Data Gate Pass)
2. GATE_FINANCIAL_HEALTH: Điểm tài chính đạt chuẩn, không cảnh báo nợ/dòng tiền
3. GATE_VALUATION_MOS: Biên an toàn định giá MoS >= 15.0%
4. GATE_TECHNICAL_MOMENTUM: Động lượng kỹ thuật đồng thuận:
   - Giá P >= MA100
   - Giá P >= MA20
   - Chỉ số RSI(14) >= 45.0
   - Khối lượng V >= 1.0 * MA20_Volume
5. GATE_QUANT_CONVICTION: Điểm định lượng Conviction >= 70 / 100
6. GATE_PM_VETO: Không vướng bẫy rủi ro (No Bull Trap, No Falling Knife, No Veto)
---------------------------------------------------------------------------------
7. GATE_MACRO_REGIME: Cổng vĩ mô duy nhất được thử nghiệm nới lỏng (tùy theo Arm)
```

### Chi tiết các Nhánh Thử nghiệm (Candidate Arms — Chỉ chạy Shadow)

| Nhánh | Định nghĩa điều kiện mở cổng `SHADOW_BUY` | Quy mô vị thế giả định | Ràng buộc kỹ thuật |
| :--- | :--- | :--- | :--- |
| **Arm 0 (Baseline)** | Theo logic đóng băng `v15.0`: `UPTREND` chuẩn (`VN-Index >= MA200`, `Slope(MA200) >= -0.5%`). | `0%` khi `DOWNTREND`; `100%` trần khi `UPTREND` | Nhánh đối chứng giữ `100% Cash (0.00%)` trong `DOWNTREND`. |
| **Arm A (MA200 Proximity Buffer)** | `vs MA200 >= -2.0%` **VÀ** `VN-Index > MA20` **VÀ** `Slope(MA20) > 0` duy trì tối thiểu `2` phiên liên tiếp. | Tối đa `50%` ngân sách vị thế (nửa Kelly) | Vùng đệm sát dưới `MA200` khi động lượng ngắn hạn đã xác nhận hồi phục. |
| **Arm B (Hysteresis & Volume Confirm)** | Áp dụng `classify_regime_ma200_hysteresis` (`reentry_pct = +1.0%`, `confirmation_sessions = 2`, `vol_surge_mult = 1.3`) từ `regime_classifier.py`. | `75%–100%` ngân sách vị thế | Kiểm tra hàm giảm nhiễu whipsaw đã tích hợp trong codebase. |
| **Arm C (Breadth + MA200 Floor)** | `vs MA200 >= -3.0%` **VÀ** tỷ lệ mã trong Universe 55 mã đóng cửa trên `MA20 >= 40%` trong `>= 2` phiên liên tiếp. | Tối đa `50%` ngân sách vị thế | Đòi hỏi độ rộng thị trường đồng thuận trước khi mở mua sớm dưới `MA200`. |

> **Ràng buộc đóng băng bậc tự do:** Cố định đúng `3` nhánh thử (`Arm A, B, C`) so với `Arm 0`. Tuyệt đối không điều chỉnh tham số, không thêm các mức đệm tùy biến (`-1.5%`, `-2.5%`) trong suốt quá trình thử nghiệm.

---

## 3. Thực tế Mẫu Khám phá 22 Phiên (Baseline Mô tả Khách quan)

Qua phân tích 93 bản ghi có `conviction >= 70` trong 22 phiên (`14/10` → `12/11/2026`):

1. **Phân tách 43 vs 50 bản ghi:**
   * **43 bản ghi (46.2%):** Thỏa mãn đầy đủ toàn bộ 6 cổng nội tại (`P >= MA100`, `P >= MA20`, `RSI >= 45`, `MoS >= 15%`, `conviction >= 70`, `watch_reason == []`). Nhóm này bị chặn duy nhất bởi `GATE_MACRO_REGIME` và rơi về lý do mô tả `"chờ tín hiệu xác nhận dòng tiền"`.
   * **50 bản ghi (53.8%):** Dù có `conviction >= 70` và `MoS >= 15%`, nhóm này vẫn trượt ít nhất một tiêu chí kỹ thuật nội tại (chủ yếu là $P < MA100$ hoặc $RSI < 45$).
2. **Hiệu ứng Cooldown 5 Phiên & Độ tập trung ngành:**
   * Khi áp dụng quy tắc giãn cách tối thiểu 5 phiên (`cooldown = 5`) cho mỗi cổ phiếu để tránh trùng lặp tín hiệu, 43 bản ghi này cô đọng lại thành đúng **16 tín hiệu độc lập**.
   * Độ tập trung ngành ở mức cực đoan: **14/16 tín hiệu (87.5%) là Ngân hàng** (`HDB`, `TPB`, `VIB`, `MBB`, `CTG`), chỉ có **2/16 tín hiệu (12.5%) là BĐS dân dụng** (`DXG`, `NLG`).
3. **Hiệu suất Thực nghiệm Mô tả (Chưa qua kiểm chứng alpha):**
   * Lợi suất khớp lệnh trung bình $T+5$ (`Exec T+5`) của 43 bản ghi này chỉ đạt **`+0.02%`** (trung vị `0.00%`).
   * Con số này **thấp hơn nhiều** so với chi phí giao dịch 2 chiều `0.40%` (lợi suất ròng âm `-0.38%`).
   * Trong khi đó, phần còn lại của rổ WATCH (những mã trượt kỹ thuật $P < MA100$ hoặc $RSI < 45$) có lợi suất trung bình `+0.84%` nhờ nhịp nảy kỹ thuật mạnh từ vùng quá bán của nhóm BĐS dân dụng.
   * **Cảnh báo Diễn giải Thực nghiệm [GIẢ THUYẾT, CHƯA KIỂM CHỨNG]:** Sự chênh lệch giữa nhóm WATCH còn lại (`+0.84%`) và nhóm 43 lượt (`+0.02%`) là một phát hiện mô tả. Một giả thuyết hợp lý là hiện tượng phân kỳ ngành và bất đối xứng độ biến động (nhóm BĐS dân dụng có thể bật nảy kỹ thuật từ vùng quá bán sâu, trong khi nhóm Ngân hàng dao động hẹp quanh nền tích lũy), nhưng cơ chế nhân quả này **chưa được kiểm định chặt chẽ**. Tuyệt đối **không được quy kết nguyên nhân rằng 'cổng kỹ thuật làm hại hiệu suất'**.
   * **Kết luận khoa học:** Việc một cổ phiếu đạt chuẩn 6 tầng nội tại trong Downtrend **hoàn toàn chưa chứng minh được nó tạo ra alpha dương**. Nhãn `SHADOW_BUY` chỉ thể hiện trạng thái kỹ thuật và định giá, không đồng nghĩa với lợi nhuận.

---

## 4. Quy mô Mẫu & Quy tắc Cooldown trong Thử nghiệm

* **Định nghĩa Tín hiệu Độc lập:** Một tín hiệu `SHADOW_BUY` được coi là độc lập nếu thỏa mãn quy tắc làm nguội **5 phiên liên tiếp** (`cooldown >= 5` phiên giao dịch) đối với cùng một mã chứng khoán. Các lượt kích hoạt cùng mã trong vòng 5 phiên kế tiếp chỉ được tính là tái xác nhận vị thế, không tính tăng cỡ mẫu $N$.
* **Số tín hiệu tối thiểu:** Tối thiểu **`20` tín hiệu `SHADOW_BUY` độc lập** đã đáo hạn đủ $T+5$ và $T+10$ cho mỗi nhánh được đánh giá.
* **Quy tắc Xử lý Thiếu Mẫu (Sample Scarcity Handling):**
  * **Đồng hồ Thời gian Độc lập:** Quy tắc thời gian '30 phiên mới và gia hạn tối đa 60 phiên' của Giai đoạn 2 là một **đồng hồ đo độc lập hoàn toàn**, bắt đầu đếm $T=1$ kể từ ngày chính thức kích hoạt Giai đoạn 2 (sau khi có báo cáo đóng sổ chính thức của Giai đoạn 1). Tuyệt đối **không nhầm lẫn hay gộp chung** với mốc 30 phiên hoặc kỳ phản nghiệm 60 phiên của Giai đoạn 1.
  * Giai đoạn 2 chạy tối thiểu **30 phiên giao dịch mới**.
  * Nếu sau 30 phiên, số tín hiệu độc lập của một nhánh đạt `< 20`, thời gian thu thập dữ liệu được tự động gia hạn tối đa tới **60 phiên** (theo chuẩn `MIN_SHADOW_SESSIONS = 60` trong `scripts/evaluate_shadow_graduation.py`).
  * Nếu sau 60 phiên vẫn **`< 20` tín hiệu độc lập**, nhánh đó được phân loại chính thức vào trạng thái: **`INSUFFICIENT_SAMPLE` (Hệ thống quá khắt khe / Thiếu mẫu thống kê trong pha suy thoái)**. Đây là một kết quả nghiên cứu hợp lệ, tuyệt đối không cưỡng ép hạ chuẩn để gom thêm tín hiệu.

---

## 5. Báo cáo Kép & Khử Thiên kiến Tập trung Ngành (Dual Reporting)

Do quan sát khám phá cho thấy nhóm Ngân hàng chiếm tới 87.5% số lượt thỏa mãn 6 cổng nội tại, Giai đoạn 2 bắt buộc phải áp dụng chuẩn **Báo cáo Kép (Dual Reporting)** với các ràng buộc phương pháp luận rõ ràng:

1. **Chỉ số Toàn bộ Danh mục (Aggregate Performance):** Đánh giá trên toàn bộ các tín hiệu `SHADOW_BUY` độc lập.
2. **Chẩn đoán Phân rã Khử Ngân hàng (Ex-Banking Diagnostic — Chỉ mang tính mô tả):**
   * Do số lượng tín hiệu độc lập ngoài ngành Ngân hàng trong pha Downtrend rất khan hiếm (ước tính chỉ khoảng $\approx 2$ tín hiệu trên 22 phiên), nhánh Ex-Banking chỉ đóng vai trò **chẩn đoán định tính/mô tả bối cảnh** (contextual diagnostic).
   * Tuyệt đối **không dùng nhánh Ex-Banking làm tiêu chí định lượng độc lập để quyết định đỗ/trượt tốt nghiệp** nhằm tránh bẫy thống kê cỡ mẫu siêu nhỏ ($N \le 5$).
3. **Ràng buộc Đa dạng hóa Ngành & Phân loại Tốt nghiệp (Sector Independence Rule):**
   * **Đánh giá Thực tế Khả thi trong Downtrend:** Với việc dữ liệu 22 phiên cho thấy 14/16 (87.5%) tín hiệu độc lập tập trung ở nhóm Ngân hàng, trong chế độ thị trường Downtrend kéo dài, điều kiện để đạt chuẩn tốt nghiệp toàn hệ thống (`GRADUATED_SYSTEM_WIDE`) thực tế **gần như chắc chắn không thể xảy ra**. Đây là một giới hạn cơ cấu dự kiến trước, không nên kỳ vọng sai; trần phân loại thực tế khả dĩ nhất của Giai đoạn 2 trong môi trường hiện tại là `GRADUATED_BANKING_SPECIFIC` hoặc `INSUFFICIENT_SAMPLE`.
   * **Chuẩn Tốt nghiệp Toàn diện (`GRADUATED_SYSTEM_WIDE`):** Không có ngành đơn lẻ nào chiếm $> 60\%$ tổng số tín hiệu độc lập trong chu kỳ thử nghiệm (chỉ khả thi nếu thị trường có sự lan tỏa dòng tiền đồng thuận sang các ngành sản xuất/bán lẻ/bất động sản).
   * **Chuẩn Tốt nghiệp Chuyên biệt Ngành (`GRADUATED_BANKING_SPECIFIC`):** Nếu nhóm Ngân hàng chiếm $> 60\%$ số tín hiệu độc lập, nhánh thử nghiệm chỉ được công nhận tốt nghiệp có điều kiện chuyên biệt cho cổ phiếu Ngân hàng khi và chỉ khi thỏa mãn đầy đủ các ngưỡng số học định lượng:
     1. $\text{Mean}(\text{SHADOW\_BUY Exec T+5}) - 0.40\% > 0.00\%$
     2. $\text{Mean}(\text{SHADOW\_BUY Exec T+10}) - 0.40\% > 0.00\%$
     3. Block Bootstrap 95% $\text{CI}_{\text{low}} > 0.00\%$ (khối $L=5$)
     4. $\text{Max Drawdown} \le -5.0\%$
     5. Tỷ lệ thắng ròng $\text{Net Hit Rate} \ge 50\%$
     6. **Rào cản triển khai:** Kết quả này tuyệt đối **không được phép mở rộng sang các ngành khác** cho đến khi tích lũy đủ tối thiểu $\ge 10$ tín hiệu phi ngân hàng độc lập để kiểm định riêng.

---

## 6. Chỉ số Đánh giá & Tiêu chuẩn Tốt nghiệp (Graduation Criteria)

### Chỉ số Chính (Primary Metrics — Tính trên giá khớp thực tế `Open_T+1 → Close_T+h`)
1. **Lợi suất Ròng Vượt Tiền mặt (`Net Excess vs Cash`):**
   * $\text{Mean}(\text{SHADOW\_BUY Exec T+5}) - 0.40\% > 0.00\%$ **VÀ** $\text{Mean}(\text{SHADOW\_BUY Exec T+10}) - 0.40\% > 0.00\%$.
   * Đánh giá qua Block Bootstrap 95% CI (khối $L=5$) với cận dưới $\text{CI}_{\text{low}} > 0.00\%$.
2. **Đánh đổi Rủi ro sụt giảm vs Chi phí Cơ hội (`Drawdown vs Arm 0`):**
   * `Max Drawdown` mô phỏng danh mục của nhánh thử nghiệm **không vượt quá `-5.0%`** trong suốt chu kỳ thử nghiệm.
   * `Calmar Ratio` và `Profit Factor` phải vượt trội nhánh `Arm 0` trong các phiên có giải ngân.

### Chỉ số Phụ (Secondary Diagnostic Metrics)
1. **Tỷ lệ Thắng Sau Phí (`Net Hit Rate`):**
   * Tỷ lệ lệnh có $\text{Exec Return} - 0.40\% > 0.00\%$ đạt $\ge 50\%$ ở $T+5$ và hướng tới $\ge 55\%$ ở $T+10$.
2. **Tỷ lệ Nhiễu Đảo Pha (`Whipsaw Rate`):**
   * Tỷ lệ lần mở cổng `SHADOW_BUY` nhưng điều kiện `Regime` lại tái lập tín hiệu suy thoái sâu chỉ trong vòng $\le 5$ phiên kế tiếp phải $\le 25\%$.
3. **Alpha Vượt Trội Rổ Cơ sở:**
   * So sánh chênh lệch giữa `SHADOW_BUY` vs phần còn lại của `WATCH` và `Universe (55 mã)` để đảm bảo alpha đến từ năng lực chọn lọc của hệ thống chứ không chỉ do may mắn theo nhịp hồi chung.

---

## 7. Rào cản Kích hoạt & Kỷ luật Cách ly Dữ liệu

* Tuyệt đối không viết code thực thi hay kích hoạt cờ chạy `SHADOW_BUY` trước khi có báo cáo đóng sổ chính thức của Giai đoạn 1 (`reports/audit_30_sessions_final.md`).
* Mọi dữ liệu thử nghiệm của Giai đoạn 2 phải được ghi nhận độc lập dưới nhãn `decision = SHADOW_BUY`, tuyệt đối không ghi đè hay sửa đổi các tệp `canonical_forward_returns_*.csv` thuộc Giai đoạn 1.
