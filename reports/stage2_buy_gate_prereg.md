# Pre-Registration Giai đoạn 2: Thử nghiệm Shadow Cổng `BUY` & Bộ lọc Regime

**Ngày khóa tiêu chí:** `2026-11-12` *(Bản bổ sung trước Phiên 31 ngày `2026-11-25`: đồng bộ mốc ngày lễ `24/11` và khóa định nghĩa `raw score` 55 mã, `Rank IC`, đối chứng kép và chỉ tiêu chính duy nhất)*  
**Trạng thái hiện tại:** **CHƯA KÍCH HOẠT** — chỉ bắt đầu thu thập dữ liệu sau khi hoàn tất đóng sổ Giai đoạn 1 (`v15.0_frozen_20261013`, mốc phiên 30 rơi vào **`2026-11-25`** do ngày `24/11` nghỉ lễ; 5 cohort hậu kiểm `18/11 → 25/11` đáo hạn `T+5` đầu tháng 12/`2026-12-02`).  
**Mục tiêu nghiên cứu:** Đánh giá xem việc nới lỏng có kiểm soát cổng `GATE_MACRO_REGIME` đối với các mã đã vượt qua toàn bộ 6 cổng nội tại (kèm theo dõi `raw score` liên tục toàn rổ 55 mã) có mang lại alpha thực nghiệm dương sau chi phí hay không, đồng thời kiểm soát rủi ro sụt giảm (drawdown).

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

### Quy tắc Đo lường Phản thực tế (`Counterfactual Execution`) & Ghi Log `Raw Score` 55 Mã
1. **Nhánh Phản thực tế Toàn phần (`Counterfactual Pass-6-Gates`):**
   * Vì `VN-Index` đang ở `-5.35%` dưới `MA200` (`25/11`), `Arm A` (`>= -2%`) và `Arm C` (`>= -3%`) có nguy cơ tiếp tục phát sinh `0` lệnh trong suốt 60 phiên nếu thị trường vẫn suy thoái sâu.
   * Nếu một nhánh Macro (`Arm A/B/C`) không mở cổng trong 60 phiên, kết luận chính thức cho nhánh đó là **`INSUFFICIENT_SAMPLE (do cổng Macro đóng)`** — **tuyệt đối không hạ ngưỡng**.
   * Do đó, Giai đoạn 2 đồng thời đo lường nhánh phản thực tế **`Counterfactual Pass-6-Gates`**: mọi mã thỏa mãn 6 cổng nội tại tại $T_0$ đều được giả định vào lệnh tại giá **`Open_T+1`** và đóng tại **`Close_T+h`**, **kể cả vào những ngày cổng Macro vẫn đóng**, nhằm tích lũy đủ dữ liệu phân tách chất lượng chọn cổ phiếu với cổng thị trường.
2. **Bắt buộc Ghi Log `Raw Score` Liên tục cho Toàn bộ 55 Mã Mỗi Ngày:**
   * Mỗi phiên từ ngày kích hoạt Giai đoạn 2, lưu tách riêng toàn bộ trạng thái và điểm số thô tại $T_0$ cho **toàn bộ 55 mã trong Universe** (không chỉ các mã qua cổng) vào tệp/bảng riêng biệt hoàn toàn với Giai đoạn 1: `symbol`, `sector`, `decision`, `conviction`, `mos_pct`, `rsi_14`, `pct_vs_ma20`, `pct_vs_ma100`, `vol_vs_ma20`, `vnindex_vs_ma200_pct`, cờ đỗ/trượt từng cổng `1..6`, và cờ `pass_6_internal_gates`.
   * Dữ liệu 55 mã này là **sản phẩm khoa học cốt lõi** của Giai đoạn 2 trong trường hợp các nhánh `Arm A/B/C` tiếp tục cho `0` lệnh.

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

* **Định nghĩa Tín hiệu Độc lập & Đơn vị Khối Bootstrap:** Một tín hiệu `SHADOW_BUY` được coi là độc lập trên phương diện tần suất cổ phiếu nếu thỏa mãn quy tắc làm nguội **5 phiên liên tiếp** (`cooldown >= 5` phiên giao dịch) đối với cùng một mã chứng khoán. Tuy nhiên, quy tắc cooldown theo mã **không loại bỏ được tương quan cùng chiều giữa các cổ phiếu Ngân hàng xuất hiện trong cùng một phiên**. Vì vậy, trong mọi kiểm định suy diễn thống kê (`Moving-Block Bootstrap`, `L=5`), **đơn vị khối (block unit) bắt buộc là ngày giao dịch $T_0$**, không coi từng lệnh cổ phiếu trong cùng một ngày là các quan sát độc lập.
* **Số tín hiệu tối thiểu:** Tối thiểu **`20` tín hiệu `SHADOW_BUY` độc lập** đã đáo hạn đủ $T+5$ và $T+10$ cho mỗi nhánh được đánh giá (lưu ý `20` tín hiệu phần lớn là Ngân hàng thực chất tương ứng vài cụm tương quan theo ngày).
* **Quy tắc Xử lý Thiếu Mẫu (Sample Scarcity Handling):**
  * **Đồng hồ Thời gian Độc lập:** Quy tắc thời gian '30 phiên mới và gia hạn tối đa 60 phiên' của Giai đoạn 2 là một **đồng hồ đo độc lập hoàn toàn**, bắt đầu đếm $T=1$ kể từ ngày chính thức kích hoạt Giai đoạn 2 (sau khi có báo cáo đóng sổ chính thức của Giai đoạn 1). Tuyệt đối **không nhầm lẫn hay gộp chung** với mốc 30 phiên hoặc kỳ phản nghiệm 60 phiên của Giai đoạn 1.
  * Giai đoạn 2 chạy tối thiểu **30 phiên giao dịch mới**.
  * Nếu sau 30 phiên, số tín hiệu độc lập của một nhánh đạt `< 20`, thời gian thu thập dữ liệu được tự động gia hạn tối đa tới **60 phiên** (theo chuẩn `MIN_SHADOW_SESSIONS = 60` trong `scripts/evaluate_shadow_graduation.py`).
  * Nếu sau 60 phiên vẫn **`< 20` tín hiệu độc lập** (hoặc cổng Macro không mở), nhánh đó được phân loại chính thức vào trạng thái: **`INSUFFICIENT_SAMPLE`**. Đây là **kết quả nghiên cứu hợp lệ**, tuyệt đối **không kích hoạt việc hạ ngưỡng** hay nới tiêu chí để gom thêm tín hiệu.
* **Cảnh báo Chế độ Thị trường (`Regime Conditionality`):** Nếu toàn bộ giai đoạn thu thập dữ liệu chỉ nằm trong pha `DOWNTREND`, mọi kết luận về `SHADOW_BUY` và `Rank IC` đều chỉ mang tính **có điều kiện (`Downtrend-Only Conditional`)**, không được khái quát hóa sang pha `UPTREND`.

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

## 6. Chỉ số Đánh giá, Đối chứng Kép & Tiêu chuẩn Tốt nghiệp

### Chỉ tiêu Chính Duy nhất (Single Primary Metric — Chống Lạm phát Đa kiểm định)
Để tránh bẫy đa kiểm định khi thử đồng thời 3 nhánh $\times$ 2 kỳ hạn $\times$ nhiều chỉ số, chỉ tiêu quyết định chính duy nhất được khóa trước là:
* **Primary Metric:** **`Net Excess Return ở kỳ hạn T+5` (`Open_T+1 → Close_T+5` trừ `0.40%` phí)** của nhánh **`Counterfactual Pass-6-Gates`** (và của nhánh Macro kích hoạt chính `Arm B` nếu phát sinh đủ mẫu), kiểm định qua **`Moving-Block Bootstrap (L=5)` theo ngày $T_0$** với yêu cầu:
  * $\text{Mean}(\text{Net Exec T+5}) > 0.00\%$ **VÀ** cận dưới 95% Block Bootstrap $\text{CI}_{\text{low}} > 0.00\%$.
* Mọi cặp nhánh/kỳ hạn phụ khác ($T+10$, `Arm A`, `Arm C`) chỉ mang tính chẩn đoán phụ trợ; nếu trích dẫn thành phát hiện mới bắt buộc hiệu chỉnh đa kiểm định (Holm-Bonferroni).

### Chỉ tiêu Liên tục trên 55 Mã (`Rank IC`) & Quy tắc Chống `Threshold Mining`
1. **Đo lường Sức mạnh Xếp hạng (`Spearman Rank IC`):**
   * Tính hệ số tương quan thứ hạng Spearman hàng ngày giữa điểm thô **`conviction`** (và riêng **`mos_pct`**) tại $T_0$ trên **toàn bộ 55 mã** với lợi suất khớp lệnh **`Exec T+5`** (và phụ trợ `Exec T+10`).
   * Báo cáo chuỗi IC theo ngày: Mean IC, tỷ lệ phiên `IC > 0`, và 95% Block Bootstrap CI ($L=5$) theo ngày $T_0$.
2. **Quy tắc Chống `Threshold Mining`:**
   * Nghiêm cấm thay đổi hay dò lại các ngưỡng (`conviction >= 70`, `MoS >= 15%`, `RSI >= 45`) sau khi đã nhìn thấy dữ liệu phân tích.
   * Nếu muốn nghiên cứu tối ưu ngưỡng từ kho `raw score` 55 mã, **bắt buộc tách đôi mẫu theo trục thời gian**: một nửa đầu để khám phá ngưỡng mới và nửa sau hoàn toàn mới (chưa từng quan sát khi đặt ngưỡng) để kiểm định Out-of-Sample.

### Đối chứng Kép (`Dual Benchmark Control` — Tính trên cùng Cohort $T_0$)
Mỗi cohort $T_0$ có tín hiệu `SHADOW_BUY` (qua 6 cổng nội tại) bắt buộc phải đối chiếu song song với **cả hai rổ đối chứng** trong đúng cùng ngày $T_0$ đó:
1. **`Universe (55 mã)`:** Kiểm tra `SHADOW_BUY − Universe T+5` để đo lợi thế tuyệt đối so với mặt bằng thị trường chung.
2. **`WATCH-không-qua-cổng` (nhóm `WATCH` trượt ít nhất 1 cổng kỹ thuật/MoS/conviction):** Kiểm tra `SHADOW_BUY − WATCH_Failed_Internal T+5` để cô lập xem 6 cổng nội tại có thực sự tăng thêm giá trị chọn lọc ngoài việc chỉ nghiêng về cổ phiếu Ngân hàng / vốn hóa lớn hay không.

### Chỉ số Phụ & Định nghĩa `Max Drawdown` (Chỉ tiêu Mô tả ở Mẫu Nhỏ)
1. **Lợi suất $T+10$ & Tỷ lệ Thắng Sau Phí (`Net Hit Rate`):**
   * $\text{Mean}(\text{SHADOW\_BUY Exec T+10}) - 0.40\% > 0.00\%$; `Net Hit Rate` $\ge 50\%$ ở $T+5$ và $\ge 55\%$ ở $T+10$.
2. **Đánh giá `Max Drawdown` (`-5.0%` — Chỉ tiêu Mô tả):**
   * **Cách tính tường minh:** Tính trên đường NAV giả lập của **danh mục đều trọng số theo cohort ngày** (với chu kỳ nắm giữ 5 phiên, mỗi ngày $T_0$ kích hoạt được cấp tối đa `1/5` vốn, chia đều cho các mã `SHADOW_BUY` trong ngày đó; ngày không có tín hiệu giữ Tiền mặt `0%`).
   * **Vai trò diễn giải:** Với mẫu nhỏ vài chục lệnh, chỉ cần một nhịp giảm đồng pha của cụm Ngân hàng là đủ chạm ngưỡng `-5.0%`. Do đó `Max Drawdown` được ghi nhận là **chỉ tiêu mô tả/cảnh báo rủi ro** cho tới khi tích lũy đủ số cụm ngày $T_0$ độc lập.
3. **Tỷ lệ Nhiễu Đảo Pha (`Whipsaw Rate`):**
   * Tỷ lệ lần mở cổng `SHADOW_BUY` (trên các nhánh `Arm A/B/C`) nhưng điều kiện `Regime` lại sập dưới ngưỡng trong vòng $\le 5$ phiên kế tiếp $\le 25\%$.

---

## 7. Rào cản Kích hoạt & Kỷ luật Cách ly Dữ liệu

* Tuyệt đối không viết code thực thi hay kích hoạt cờ chạy `SHADOW_BUY` trước khi có báo cáo đóng sổ chính thức của Giai đoạn 1 (`reports/audit_30_sessions_final.md`).
* Mọi dữ liệu thử nghiệm của Giai đoạn 2 phải được ghi nhận độc lập dưới nhãn `decision = SHADOW_BUY`, tuyệt đối không ghi đè hay sửa đổi các tệp `canonical_forward_returns_*.csv` thuộc Giai đoạn 1.
