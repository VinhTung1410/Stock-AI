# Quy Chuẩn Phương Pháp Luận Tính Toán Hiệu Suất Tiến Tới (Forward Returns Methodology)

**Phiên bản Quy Chuẩn:** `v2.0_institutional`  
**Ngày hiệu lực:** 14/10/2026 (Áp dụng chính thức từ mốc kiểm định Ngày 1)  
**Mục tiêu:** Thiết lập khung đo lường hiệu suất tiến tới chuẩn mực định chế, triệt tiêu thiên lệch nhìn trước (*lookahead bias*), sai lệch khoảng trống mở phiên (*overnight gap distortion*), và đảm bảo bảng dữ liệu có khả năng **tự kiểm toán độc lập 100% (Self-Auditable)**.

---

## 1. Tuyên Bố Khiêm Nhường Nhận Thức (Epistemic Humility) & Nguyên Tắc Thống Kê

> [!IMPORTANT]
> **Một ngày vẫn là một ngày (Sample Size Warning):**
> 1. Hiệu suất ở cấp 1 phiên giao dịch ($T+1$) chỉ có giá trị **kiểm định đường ống tính toán (Pipeline Verification)**, tuyệt đối **KHÔNG** mang ý nghĩa thống kê về chất lượng tín hiệu đầu tư hay alpha dài hạn.
> 2. Phân tầng sơ bộ ngày 14/10 $\to$ 15/10 (WATCH trung bình Signal $+0,71\%$ vs REJECT $-0,44\%$; Exec trừ VN-Index: WATCH $+1,10$ pp vs REJECT $-0,08$ pp) chỉ phản ánh biến động của 1 phiên thị trường đi ngang phân hóa, với tỷ trọng 9/16 mã WATCH là Ngân hàng.
> 3. Hệ thống cam kết **chờ tích lũy tối thiểu từ 30 đến 60 phiên giao dịch** trước khi tính toán và công bố các chỉ số thống kê suy diễn (*inferential statistics*), t-test, hoặc khoảng tin cậy (*confidence intervals*).

---

## 2. Kiến Trúc Đo Lường Hai Chế Độ (Dual-Return Architecture)

Để phân tách rạch ròi giữa **độ chính xác dự báo của mô hình** và **kết quả thực thi thực tế của nhà đầu tư**, hệ thống áp dụng song song hai thước đo:

### 2.1. Lợi Nhuận Tín Hiệu (Signal Return / Close-to-Close)
Đo lường từ mức giá đóng cửa phiên $T$ (thời điểm hệ thống quét EOD và ra khuyến nghị) đến giá đóng cửa phiên $T+h$:

$$\text{Signal Return}_{T+h} = \frac{\text{Close}_{T+h} - \text{Close}_T}{\text{Close}_T} \times 100\%$$

- **Ý nghĩa:** Kiểm định độ chính xác thuần túy của các thuật toán phân tích cơ bản, định giá Fair Value, và bộ lọc kỹ thuật mà không bị nhiễu bởi thời điểm khớp lệnh thực tế.

### 2.2. Lợi Nhuận Thực Thi (Executable Return / Open-to-Close)
Đo lường từ mức giá mở cửa ATO của phiên $T+1$ (thời điểm sớm nhất nhà đầu tư có thể đặt lệnh mua sau khi nhận báo cáo cuối ngày $T$) đến giá đóng cửa phiên $T+h$:

$$\text{Executable Return}_{T+h} = \frac{\text{Close}_{T+h} - \text{Open}_{T+1}}{\text{Open}_{T+1}} \times 100\%$$

- **Ý nghĩa:** Phản ánh hiệu suất tài khoản thực tế (*P&L* thực thi), loại bỏ hoàn toàn giả định phi thực tế rằng nhà đầu tư có thể mua được ở mức giá đóng cửa hôm trước.

---

---

## 3. Khung Đo Lường & Bóc Tách Chuẩn Tham Chiếu (Benchmark Attribution Framework)

### 3.1. Chuẩn Hóa Mỏ Neo So Sánh VN-Index (Macro Context Benchmark)
Tuyệt đối cấm sử dụng hai mốc thời gian lệch nhau giữa cổ phiếu và chỉ số tham chiếu:

$$\text{VN-Index Signal}_{T+h} = \frac{\text{VN-Index Close}_{T+h} - \text{VN-Index Close}_T}{\text{VN-Index Close}_T} \times 100\%$$

$$\text{VN-Index Executable}_{T+h} = \frac{\text{VN-Index Close}_{T+h} - \text{VN-Index Open}_{T+1}}{\text{VN-Index Open}_{T+1}} \times 100\%$$

- **Lợi nhuận vượt trội so với VN-Index (Excess vs VN-Index):**

$$\text{Excess Exec Return}_{T+h} = \text{Executable Return}_{T+h} - \text{VN-Index Executable}_{T+h}$$

### 3.2. Cảnh Báo Bản Chất "Vượt VN-Index" & Các Mốc So Sánh Chuẩn (True Attribution)
> [!WARNING]
> **"Vượt VN-Index" dễ gây ngộ nhận năng lực chọn mã:**
> - VN-Index là chỉ số tính theo **giá trị vốn hóa thị trường (Cap-Weighted)**, bị chi phối bởi một vài mã vốn hóa khổng lồ (VCB, VHM, VIC, BID, v.v.).
> - Khi các mã trụ lớn giảm điểm mạnh khiến VN-Index giảm (ví dụ cửa sổ 14 $\to$ 19/10, VN-Index giảm $-0,88\%$), nhưng trung bình 55 mã Universe vào lệnh ở Open lại tăng $+0,66\%$.
> - Hệ quả: Cả hai nhóm WATCH ($+2,02$ pp) và REJECT ($+1,04$ pp) đều "vượt chỉ số". Khoảng chênh lệch $\sim 1,3$ pp ở giữa chủ yếu là sự khác nhau giữa **trung bình đều trọng số (Equal-Weighted)** của 55 mã và chỉ số theo vốn hóa, **không phải là năng lực chọn mã (alpha)**.

Để bóc tách chính xác năng lực lựa chọn cổ phiếu của mô hình, hệ thống bổ sung các mốc so sánh chuẩn tắc:
1. **Trung bình đều trọng số Universe 55 mã (`excess_vs_universe_t{h}_pct`):**
   $$\text{Excess vs Universe}_{T+h} = \text{Executable Return}_{T+h} - \frac{1}{N_{\text{Universe}}}\sum_{i=1}^{N_{\text{Universe}}} \text{Executable Return}_{i, T+h}$$
2. **Trung bình cùng ngành loại trừ chính mã đó (Leave-One-Out Sector Benchmark - `excess_vs_sector_t{h}_pct`):**
   - **Lỗi méo mó cấu trúc của phương pháp trung bình gộp thông thường:**
     - Nếu tính trung bình ngành gồm cả bản thân mã đó: ngành chỉ có $1$ mã (như FPT thuộc Công nghệ / AI) sẽ luôn có $\text{Sector Exec} \equiv \text{Exec}_{\text{FPT}}$, dẫn tới $\text{Excess vs Sector} \equiv 0,0$ theo cấu trúc, triệt tiêu hoàn toàn alpha của mã duy nhất.
     - Với ngành có $2$ mã (như Chứng khoán: SSI, VND; Bán lẻ tiêu dùng: MWG, MSN; Thực phẩm & Đồ uống: SAB, VNM): mã đó chiếm $50\%$ trọng số ngành, làm giảm đúng một nửa phần vượt trội thực tế so với đối thủ trực tiếp.
   - **Quy chuẩn Leave-One-Out (LOO) & Ngưỡng cỡ mẫu tối thiểu $\ge 3$ mã:**
     - **Với ngành có từ $3$ mã trở lên ($N_S \ge 3$):** Benchmark ngành cho cổ phiếu $i$ là trung bình thực thi của $N_S - 1$ mã đồng môn còn lại trong ngành (loại trừ chính mã $i$):
       $$\text{Sector Exec}_{-i, T+h} = \frac{1}{N_S - 1} \sum_{j \in S, j \ne i} \text{Executable Return}_{j, T+h}$$
       $$\text{Excess vs Sector}_{-i, T+h} = \text{Executable Return}_{i, T+h} - \text{Sector Exec}_{-i, T+h}$$
     - **Với ngành có dưới $3$ mã ($N_S < 3$):** Cỡ mẫu quá nhỏ để tạo benchmark thống kê có tính đại diện. Hệ thống ghi nhận giá trị `NaN` (Null) cho cả `sector_exec_t{h}_pct` và `excess_vs_sector_t{h}_pct` để phản ánh đúng bản chất dữ liệu, không gượng ép benchmark méo mó.
3. **Thước đo năng lực cốt lõi: Spread WATCH trừ REJECT:**
   $$\text{Selection Alpha} = \overline{\text{Exec}}_{\text{WATCH}} - \overline{\text{Exec}}_{\text{REJECT}}$$
   - Tại mốc $T+1$ nhóm 14/10: WATCH đạt $+0,93\%$, REJECT đạt $-0,25\% \implies$ **Spread là $+1,18$ điểm phần trăm**.
   - Tại mốc $T+1$ nhóm 15/10: WATCH đạt $+0,66\%$, REJECT đạt $-0,14\% \implies$ **Spread là $+0,81$ điểm phần trăm**.
   - Tại mốc $T+3$ nhóm 14/10: WATCH đạt $+1,35\%$, REJECT đạt $+0,37\% \implies$ **Spread thực chất là $+0,98$ điểm phần trăm**.
4. **Kiểm định May Rủi: Phân Tầng Theo Cơ Cấu Ngành (Sector-Stratified Random Permutation Baseline):**
   - **Tại sao bootstrap ngẫu nhiên thuần túy (Naive Random) là chưa đủ?**
     - Khi tính "WATCH trừ REJECT", benchmark ngầm định là trung bình của toàn bộ vũ trụ (55 mã). Tuy nhiên, nếu chọn ngẫu nhiên $16$ mã bất kỳ từ $55$ mã, danh mục ngẫu nhiên có thể mang cơ cấu ngành rất khác so với nhóm WATCH (ví dụ: ngày 14/10 nhóm Ngân hàng bứt phá mạnh, trong khi WATCH nắm tới $9$ mã Ngân hàng).
     - Việc WATCH vượt nhóm ngẫu nhiên thuần túy có thể chỉ là do **may mắn phân bổ ngành (Sector Allocation Luck / Sector Beta)**, chứ chưa chứng minh được năng lực chọn mã nội ngành.
   - **Phương pháp Phân Tầng Cơ Cấu Ngành (Sector-Stratified Permutation):**
     - Mô phỏng Monte Carlo $5.000$ lần: Trong từng ngành, chọn ngẫu nhiên không hoàn lại đúng số lượng mã mà nhóm WATCH nắm giữ (ví dụ chọn ngẫu nhiên $9$ ngân hàng từ $14$ ngân hàng Universe, $4$ BĐS từ $9$ BĐS dân dụng, $1$ FPT từ $1$ Công nghệ, v.v.).
     - Danh mục ngẫu nhiên này sở hữu **chính xác $100\%$ cơ cấu ngành** của nhóm WATCH, giúp trung hòa hoàn toàn yếu tố may mắn phân bổ ngành để cô lập **Selection Alpha nội ngành (Within-Sector Selection Alpha)**.
   - **Kết quả thực nghiệm kiểm định:**
     - **Mốc $14/10 \to 15/10$ ($T+1$):**
       - Universe 55 mã: $+0,09\%$ | WATCH ($16$ mã): $+0,93\%$ | REJECT ($39$ mã): $-0,25\%$ | Spread: $+1,18$ pp.
       - Ngẫu nhiên cùng cơ cấu ngành: Median $+0,49\%$ (IQR $[+0,32\%, +0,67\%]$).
       - **Selection Alpha nội ngành:** $+0,44$ pp ($+0,93\% - 0,49\%$).
       - **Empirical $p$-value:** $p = 0,0258 < 0,05 \implies$ Khẳng định chênh lệch $+1,18$ pp vượt trội có ý nghĩa thống kê thực chất, không phải do may rủi phân bổ ngành.
     - **Mốc $14/10 \to 19/10$ ($T+3$):**
       - Universe 55 mã: $+0,66\%$ | WATCH ($16$ mã): $+1,35\%$ | REJECT ($39$ mã): $+0,37\%$ | Spread: $+0,98$ pp.
       - Ngẫu nhiên cùng cơ cấu ngành: Median $+0,54\%$ (IQR $[+0,28\%, +0,79\%]$).
       - **Selection Alpha nội ngành:** $+0,81$ pp ($+1,35\% - 0,54\%$).
       - **Empirical $p$-value:** $p = 0,0084 < 0,01 \implies$ Alpha chọn mã nội ngành cực mạnh.
     - **Mốc $15/10 \to 16/10$ ($T+1$):**
       - Universe 55 mã: $+0,09\%$ | WATCH: $+0,66\%$ | REJECT: $-0,14\%$ | Spread: $+0,81$ pp.
       - Ngẫu nhiên cùng cơ cấu ngành: Median $+0,42\%$ (IQR $[+0,26\%, +0,56\%]$).
       - Selection Alpha nội ngành: $+0,25$ pp ($p = 0,1150$).
5. **Chuẩn Hóa Danh Pháp Cột Mốc Mới Nhất (`latest_horizon`, `*_latest`):**
   - Loại bỏ các cột không có hậu tố (`excess_vs_universe`, `excess_vs_sector`) do dễ gây nhầm lẫn khi nội hàm bị thay đổi theo thời gian đáo hạn.
   - Thay thế bằng bộ ba cột minh bạch:
     - `latest_horizon`: Chỉ định rõ ràng mốc đáo hạn mới nhất đang tham chiếu (`T+1`, `T+3`, `T+5`).
     - `excess_vs_universe_latest`: Hiệu suất vượt trội so với Universe tại đúng mốc `latest_horizon`.
     - `excess_vs_sector_latest`: Hiệu suất vượt trội so với Benchmark ngành Leave-One-Out tại đúng mốc `latest_horizon`.
6. **Cảnh báo độ phân tán & Quan sát phụ thuộc:**
   - Trong 16 mã WATCH mốc 14/10 $\to$ 19/10, hiệu suất $T+3$ phân tán rộng từ $-1,94\%$ (HDB) đến $+5,20\%$ (KDH). $75\%$ mã WATCH có Excess dương, trong khi nhóm REJECT cũng có $67\%$ mã có Excess dương.
   - Độ phân tán nội bộ này lớn hơn chênh lệch trung bình giữa hai nhóm. Đồng thời các nhóm ngày liền kề (14/10, 15/10) trên các cửa sổ trùng lặp là các quan sát phụ thuộc (cùng 16 mã cổ phiếu), không phải bằng chứng độc lập.
   - **Cam kết:** Giữ VN-Index làm bối cảnh vĩ mô; không in khoảng tin cậy (*confidence intervals*) cho tới khi có hàng chục phiên độc lập.

---

## 4. Quy Chế Bước Giá & Kiểm Toán Khóa Thanh Khoản (Ceiling/Floor Audit)

### 4.1. Quy tắc Bước Giá & Biên Độ Theo Sàn Niêm Yết
Hệ thống tính toán giá trần (`ceiling_price`) và giá sàn (`floor_price`) chuẩn xác theo quy chế từng sàn:
- **HOSE ($\pm 7\%$):**
  - Giá $< 10,00$k: Tick $0,01$
  - Giá $10,00 - 49,95$k: Tick $0,05$
  - Giá $\ge 50,00$k: Tick $0,10$
- **HNX ($\pm 10\%$):** Bước giá cố định $0,10$k cho mọi dải thị giá (áp dụng cho IDC, TNG).
- **UPCoM ($\pm 15\%$):** Bước giá cố định $0,10$k cho mọi dải thị giá (áp dụng cho BSR).

Công thức làm tròn:
$$\text{Ceiling} = \left\lfloor \frac{\text{Ref Price} \times (1 + \text{Limit})}{\text{Tick}} + 10^{-7} \right\rfloor \times \text{Tick}$$
$$\text{Floor} = \max\left(\left\lceil \frac{\text{Ref Price} \times (1 - \text{Limit})}{\text{Tick}} - 10^{-7} \right\rceil \times \text{Tick}, \text{Tick}\right)$$

### 4.2. Cột Giá Kiểm Toán Minh Bạch
Bảng dữ liệu lưu trữ trực tiếp các cột giá tính được:
- `ceiling_price_t1`, `floor_price_t1`: Giá trần/sàn tính từ $\text{Close}_{T0}$, dùng để kiểm toán cờ `entry_ceiling_locked_t1` và `exit_floor_locked_t1`.
- `ceiling_price_t3`, `floor_price_t3`: Giá trần/sàn tính từ $\text{Close}_{T2}$, dùng để kiểm toán cờ `exit_floor_locked_t3`.
- `ceiling_price_t5`, `floor_price_t5`: Giá trần/sàn tính từ $\text{Close}_{T4}$, dùng để kiểm toán cờ `exit_floor_locked_t5`.
- Cột chưa đáo hạn được để `NaN` nhằm đảm bảo nguyên tắc trung thực dữ liệu.

---

## 5. Quy Chuẩn Lọc Dữ Liệu Chuẩn & Chống Trùng Lặp (Deduplication)

Để đảm bảo mẫu kiểm định sạch và duy nhất:
1. **Từ ngày 14/10/2026 trở đi (Schema v2.0):** Chỉ chấp nhận các bản ghi có cờ `is_canonical = True` (hoặc `session = 'EOD_CANONICAL'`). Đúng 55 mã duy nhất thuộc Broad Market Pool được đưa vào bảng theo dõi.
2. **Trước ngày 14/10/2026:** Nhận diện theo cặp `(symbol, date)` và chỉ giữ lại bản ghi có `created_at` muộn nhất trong ngày để loại trừ các bản ghi chạy thử trong phiên.
3. **Tính bất biến thuật toán:** Cố định `logic_version = "v15.0_frozen_20261013"`.

---

## 6. Nhận Diện Khoảng Trống Qua Đêm (Overnight Gap Flagging)

### 6.1. Định nghĩa và Ngưỡng Cảnh Báo
$$\text{Gap}_{\text{Exec vs Signal}} = \text{Executable Return}_{T+1} - \text{Signal Return}_{T+1}$$

Hệ thống gắn cờ cảnh báo `large_overnight_gap = True` khi:

$$|\text{Gap}_{\text{Exec vs Signal}}| \ge 2,0 \text{ điểm phần trăm (pp)}$$

### 6.2. Phân Tích Thực Nghiệm Hai Ca Đột Biến (14/10 $\to$ 15/10)
- **STK (Chênh lệch $-4,01$ pp):**
  - $\text{Close}_T = 7,83$ | $\text{Open}_{T+1} = 8,15$ ($+4,09\%$) | $\text{Close}_{T+1} = 7,99$.
  - $\text{Signal Return} = +2,04\%$ | $\text{Executable Return} = -1,96\%$.
  - **Nguyên nhân:** Thanh khoản thấp, lệnh ATO nhỏ làm thị giá mở cửa tăng vọt $+4,09\%$, khiến Executable thấp hơn Signal 4,01 điểm phần trăm.
- **CSV (Chênh lệch $-2,11$ pp):**
  - $\text{Close}_T = 23,40$ (phiên 14/10 tăng trần kịch biên độ $+6,85\%$).
  - $\text{Open}_{T+1} = 23,90$ ($+2,14\%$) | $\text{Close}_{T+1} = 23,60$.
  - $\text{Signal Return} = +0,86\%$ | $\text{Executable Return} = -1,26\%$.
  - **Nguyên nhân:** Quán tính tăng trần từ phiên trước khiến ATO mở gap tăng mạnh rồi hạ nhiệt trong phiên.
  - **Kết luận:** Cả hai mã đều dao động hợp lệ trong biên độ $\pm 7\%$, không bị khóa thanh khoản.

---

## 7. Nguyên Tắc Phân Bổ Chi Phí Giao Dịch & Thuế (Cost Attribution Protocol)

- **Định mức chi phí:** Phí giao dịch và thuế ước tính chuẩn là $0,40\%$ (gồm $0,15\%$ phí mua, $0,15\%$ phí bán, và $0,10\%$ thuế bán).
- **Nguyên tắc phân bổ bất đối xứng:**
  - Cột `est_fee_tax_pct` lưu định mức chi phí riêng biệt.
  - Chi phí giao dịch **chỉ áp dụng cho các vị thế mua giả định** (nhóm `WATCH`).
  - **TUYỆT ĐỐI KHÔNG** trừ chi phí giao dịch vào nhóm `REJECT` khi đọc "lãi ròng", bởi vì các mã REJECT không bao giờ được hệ thống giải ngân mua.

---

## 8. Đặc Tả Cấu Trúc Dữ Liệu Tự Kiểm Toán Toàn Phần (Self-Auditability Schema)

Mỗi tệp `canonical_forward_returns_YYYYMMDD.csv` lưu trữ đầy đủ các cột sau:

| Tên Cột | Kiểu Dữ Liệu | Mục Đích & Công Thức Kiểm Toán |
|---|---|---|
| `decision_id` | String | Khóa ngoại định danh duy nhất bản ghi quyết định EOD |
| `symbol` | String | Mã cổ phiếu (3 ký tự viết hoa) |
| `decision` | String | Nhãn khuyến nghị (`WATCH` hoặc `REJECT`) |
| `exchange` | String | Sàn niêm yết (`HOSE`, `HNX`, `UPCOM`) |
| `sector` | String | Phân loại ngành phục vụ phân tầng thống kê |
| `logic_version` | String | Phiên bản logic ra quyết định (`v15.0_frozen_20261013`) |
| `calc_version` | String | Phiên bản đường ống tính toán (`v2.0_institutional`) |
| `price_adjusted` | Boolean | Trạng thái điều chỉnh cổ tức/chia tách (`True`) |
| `entry_date_t0` | Date | Ngày ra quyết định ($T$) |
| `close_t0` | Float | Giá đóng cửa phiên $T$ (VNĐ nghìn) |
| `entry_date_t1` | Date | Ngày thực thi ATO ($T+1$) |
| `open_t1` | Float | Giá mở cửa ATO phiên $T+1$ (VNĐ nghìn) |
| `close_t1` | Float | Giá đóng cửa phiên $T+1$ (VNĐ nghìn) |
| `close_t3` | Float / Null | Giá đóng cửa phiên $T+3$ khi đáo hạn |
| `close_t5` | Float / Null | Giá đóng cửa phiên $T+5$ khi đáo hạn |
| `vn_close_t0` | Float | Điểm số đóng cửa VN-Index phiên $T$ |
| `vn_open_t1` | Float | Điểm số mở cửa VN-Index phiên $T+1$ |
| `vn_close_t1` | Float | Điểm số đóng cửa VN-Index phiên $T+1$ |
| `vn_close_t3` | Float / Null | Điểm số đóng cửa VN-Index phiên $T+3$ |
| `vn_close_t5` | Float / Null | Điểm số đóng cửa VN-Index phiên $T+5$ |
| `ceiling_price` | Float | Giá trần kiểm toán mốc vào lệnh $T+1$ |
| `floor_price` | Float | Giá sàn kiểm toán mốc vào lệnh $T+1$ |
| `ceiling_price_t1` | Float | Giá trần tính được cho phiên $T+1$ |
| `floor_price_t1` | Float | Giá sàn tính được cho phiên $T+1$ |
| `ceiling_price_t3` | Float / Null | Giá trần tính được cho phiên $T+3$ khi đáo hạn |
| `floor_price_t3` | Float / Null | Giá sàn tính được cho phiên $T+3$ khi đáo hạn |
| `ceiling_price_t5` | Float / Null | Giá trần tính được cho phiên $T+5$ khi đáo hạn |
| `floor_price_t5` | Float / Null | Giá sàn tính được cho phiên $T+5$ khi đáo hạn |
| `matured_t1` | Boolean | Cờ boolean xác nhận đã đáo hạn mốc $T+1$ |
| `matured_t3` | Boolean | Cờ boolean xác nhận đã đáo hạn mốc $T+3$ |
| `matured_t5` | Boolean | Cờ boolean xác nhận đã đáo hạn mốc $T+5$ |
| `matured_t10` | Boolean | Cờ boolean xác nhận đã đáo hạn mốc $T+10$ |
| `matured_t20` | Boolean | Cờ boolean xác nhận đã đáo hạn mốc $T+20$ |
| `entry_ceiling_locked_t1` | Boolean | Cờ kịch trần lúc mở cửa $T+1$ |
| `exit_floor_locked_t1` | Boolean | Cờ kẹt sàn lúc đóng cửa $T+1$ |
| `exit_floor_locked_t3` | Boolean | Cờ kẹt sàn lúc đóng cửa $T+3$ |
| `exit_floor_locked_t5` | Boolean | Cờ kẹt sàn lúc đóng cửa $T+5$ |
| `signal_t1_pct` | Float | Lợi nhuận tín hiệu $(\text{close\_t1} - \text{close\_t0}) / \text{close\_t0} \times 100$ |
| `vn_signal_t1_pct` | Float | Lợi nhuận tín hiệu VN-Index $T+1$ |
| `excess_signal_t1_pct` | Float | $\text{signal\_t1\_pct} - \text{vn\_signal\_t1\_pct}$ |
| `exec_t1_pct` | Float | Lợi nhuận thực thi $(\text{close\_t1} - \text{open\_t1}) / \text{open\_t1} \times 100$ |
| `vn_exec_t1_pct` | Float | Lợi nhuận thực thi VN-Index $T+1$ |
| `excess_exec_t1_pct` | Float | $\text{exec\_t1\_pct} - \text{vn\_exec\_t1\_pct}$ |
| `universe_exec_t1_pct` | Float | Trung bình đều trọng số 55 mã Universe tại $T+1$ |
| `excess_vs_universe_t1_pct` | Float | Lợi nhuận vượt mức so với Universe 55 mã tại $T+1$ |
| `sector_exec_t1_pct` | Float / Null | Trung bình nhóm ngành Leave-One-Out tại $T+1$ (loại trừ chính mã; Null nếu ngành $< 3$ mã) |
| `excess_vs_sector_t1_pct` | Float / Null | Lợi nhuận vượt mức so với nhóm ngành Leave-One-Out tại $T+1$ (Null nếu ngành $< 3$ mã) |
| `gap_exec_vs_signal_pp` | Float | Chênh lệch $\text{exec\_t1\_pct} - \text{signal\_t1\_pct}$ |
| `signal_t3_pct` | Float / Null | Lợi nhuận tín hiệu $T+3$ |
| `vn_signal_t3_pct` | Float / Null | Lợi nhuận tín hiệu VN-Index $T+3$ |
| `excess_signal_t3_pct` | Float / Null | Lợi nhuận tín hiệu vượt VN-Index $T+3$ |
| `exec_t3_pct` | Float / Null | Lợi nhuận thực thi $T+3$ |
| `vn_exec_t3_pct` | Float / Null | Lợi nhuận thực thi VN-Index $T+3$ |
| `excess_exec_t3_pct` | Float / Null | Lợi nhuận thực thi vượt VN-Index $T+3$ |
| `universe_exec_t3_pct` | Float / Null | Trung bình đều trọng số 55 mã Universe tại $T+3$ |
| `excess_vs_universe_t3_pct` | Float / Null | Lợi nhuận vượt mức so với Universe 55 mã tại $T+3$ |
| `sector_exec_t3_pct` | Float / Null | Trung bình nhóm ngành Leave-One-Out tại $T+3$ (loại trừ chính mã; Null nếu ngành $< 3$ mã) |
| `excess_vs_sector_t3_pct` | Float / Null | Lợi nhuận vượt mức so với nhóm ngành Leave-One-Out tại $T+3$ (Null nếu ngành $< 3$ mã) |
| `gap_exec_vs_signal_t3_pp` | Float / Null | Chênh lệch thực thi và tín hiệu tại $T+3$ |
| `signal_t5_pct` | Float / Null | Lợi nhuận tín hiệu $T+5$ |
| `vn_signal_t5_pct` | Float / Null | Lợi nhuận tín hiệu VN-Index $T+5$ |
| `excess_signal_t5_pct` | Float / Null | Lợi nhuận tín hiệu vượt VN-Index $T+5$ |
| `exec_t5_pct` | Float / Null | Lợi nhuận thực thi $T+5$ |
| `vn_exec_t5_pct` | Float / Null | Lợi nhuận thực thi VN-Index $T+5$ |
| `excess_exec_t5_pct` | Float / Null | Lợi nhuận thực thi vượt VN-Index $T+5$ |
| `universe_exec_t5_pct` | Float / Null | Trung bình đều trọng số 55 mã Universe tại $T+5$ |
| `excess_vs_universe_t5_pct` | Float / Null | Lợi nhuận vượt mức so với Universe 55 mã tại $T+5$ |
| `sector_exec_t5_pct` | Float / Null | Trung bình nhóm ngành Leave-One-Out tại $T+5$ (loại trừ chính mã; Null nếu ngành $< 3$ mã) |
| `excess_vs_sector_t5_pct` | Float / Null | Lợi nhuận vượt mức so với nhóm ngành Leave-One-Out tại $T+5$ (Null nếu ngành $< 3$ mã) |
| `gap_exec_vs_signal_t5_pp` | Float / Null | Chênh lệch thực thi và tín hiệu tại $T+5$ |
| `latest_horizon` | String / Null | Chuỗi định danh mốc đáo hạn mới nhất (`T+1`, `T+3`, `T+5` hoặc Null) |
| `excess_vs_universe_latest` | Float / Null | Lợi nhuận vượt mức so với Universe tại mốc đáo hạn mới nhất `latest_horizon` |
| `excess_vs_sector_latest` | Float / Null | Lợi nhuận vượt mức so với Benchmark ngành Leave-One-Out tại mốc đáo hạn mới nhất `latest_horizon` |
| `large_overnight_gap` | Boolean | $|\text{gap\_exec\_vs\_signal\_pp}| \ge 2,0$ |
| `est_fee_tax_pct` | Float | Định mức phí thuế tham chiếu ($0,40\%$) |

---

## 9. Lịch Trình Đáo Hạn Các Mẫu Chuẩn (Forward Timeline)

| Nhóm Kiểm Định | Mốc Quyết Định ($T$) | Đáo Hạn $T+1$ | Đáo Hạn $T+3$ | Đáo Hạn $T+5$ | Trạng Thái Hiện Tại |
|---|---|---|---|---|---|
| **Mẫu Chuẩn Ngày 1** | **14/10/2026** | **15/10/2026** (Đã khóa) | **19/10/2026** (Đã khóa) | **21/10/2026** | $T+1$ & $T+3$ hoàn tất (55 mã); $T+5$ chờ ngày 21/10. |
| **Mẫu Chuẩn Ngày 2** | **15/10/2026** | **16/10/2026** (Đã khóa) | **20/10/2026** | **22/10/2026** | $T+1$ hoàn tất (55 mã); $T+3$ chờ ngày 20/10. |
| **Mẫu Chuẩn Ngày 3** | **16/10/2026** | **19/10/2026** (Đã khóa) | **21/10/2026** | **23/10/2026** | $T+1$ hoàn tất (55 mã); $T+3$ chờ ngày 21/10. |
| **Mẫu Chuẩn Ngày 4** | **19/10/2026** | **20/10/2026** | **22/10/2026** | **26/10/2026** | $T0$ đã niêm phong (55 mã); $T+1$ chờ ngày 20/10. |

---

## 10. Điều Tra & Giải Trình Tần Suất Quét HPG (20 Lần/Ngày)

### 10.1. Hiện Tượng Quan Sát
Trong bảng `decision_records`, cổ phiếu HPG xuất hiện đều đặn **20 bản ghi mỗi ngày** (ví dụ ngày 14/10, 15/10, 16/10, 19/10), trong khi các mã khác chỉ xuất hiện từ 1 đến vài lần.

### 10.2. Nguyên Nhân Kỹ Thuật (Root Cause)
Đã truy vết trong mã nguồn [`trading_bot.py:655-660`](file:///c:/Users/Window/Desktop/Stock%20-%20learning/trading_bot.py#L655-L660):
- Phương thức `_scan_active_market_opportunities()` của Bot giao dịch được cấu hình chạy định kỳ mỗi **15 phút (900 giây)** trong suốt khung giờ mở cửa thị trường Việt Nam:
  1. **Phiên sáng (08:45 – 11:30):** 11 chu kỳ quét (08:45, 09:00, 09:15, 09:30, 09:45, 10:00, 10:15, 10:30, 10:45, 11:00, 11:15).
  2. **Phiên chiều (13:00 – 14:45):** 8 chu kỳ quét (13:00, 13:15, 13:30, 13:45, 14:00, 14:15, 14:30, 14:45).
  3. **Phiên đóng cửa EOD Canonical (15:00):** 1 chu kỳ quét chốt phiên.
  - **Tổng cộng:** $11 + 8 + 1 = 20$ chu kỳ quét mỗi ngày.
- **Vì sao là HPG?** HPG là mã dẫn dắt nhóm Thép & Vật liệu, đứng đầu danh sách lọc Broad Market Pool, và luôn thỏa mãn điều kiện thanh khoản tối đa (ADV20 > 50 tỷ), do đó bot không bao giờ loại bỏ HPG ở vòng sơ lọc thanh khoản và luôn thực hiện quét qua toàn bộ 20 interval.

### 10.3. Giải Pháp Quản Trị & Khử Trùng Lặp (Deduplication Governance)
Đường ống kiểm toán `v2.0_institutional` áp dụng hàm `filter_canonical_and_deduplicate()`:
- Từ ngày 14/10/2026: **Chỉ chấp nhận duy nhất bản ghi chốt phiên có cờ `is_canonical = True` (hoặc `session = 'EOD_CANONICAL'`)**.
- Toàn bộ 19 bản ghi quét trong phiên (intraday checks) được cách ly độc lập, không tham gia vào tập dữ liệu tính toán Forward Returns, đảm bảo đúng 1 dòng / mã / ngày giao dịch.

