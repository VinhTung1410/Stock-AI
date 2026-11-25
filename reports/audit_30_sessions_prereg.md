# Pre-Registration: Kiểm toán 30 Phiên Hệ thống Đóng băng (`v15.0_frozen_20261013`)

**Ngày khóa tiêu chí gốc (v1.0):** `2026-11-12` (trước khi có dữ liệu `2026-11-13` → `2026-11-25`)  
**Bản cập nhật Addendum (v1.1):** `2026-11-12` (đồng bộ 1-1 với `scripts/audit_30_sessions.py` trước khi phát sinh dữ liệu `2026-11-13`)  
**Bản cập nhật Hành chính (v1.2):** `2026-11-25` *(chỉ điều chỉnh lịch nghỉ lễ `24/11 → 25/11`, định vị mốc 60 phiên là interim check, và ghi tường minh quy tắc bất khả hồi tố cho 5 cohort hậu kiểm `18/11–25/11`; **tuyệt đối không thay đổi bất kỳ ngưỡng số học hay quy tắc verdict nào của v1.1**)*  
**Phiên bản hệ thống đóng băng:** Logic `v15.0_frozen_20261013` | Model `v15.0_post_fix` | Commit `106e6c61af`  
**Quy tắc bất biến:** Không thay đổi logic tín hiệu, bộ lọc ngành, hay ngưỡng cổng `BUY/WATCH/REJECT` trong suốt kỳ quan sát 30 phiên (`2026-10-14` → `2026-11-25`, 30 phiên giao dịch thực tế bỏ qua ngày lễ `24/11`).

---

## 1. Ảnh chụp Mốc Cơ sở & Dry-Run (22 Phiên: `2026-10-14` → `2026-11-12`)

Số liệu đối chiếu trực tiếp từ dry-run [audit_30_sessions.py](file:///c:/Users/Window/Desktop/Stock%20-%20learning/scripts/audit_30_sessions.py) trên 22 file `canonical_forward_returns_2026*.csv` và 22 báo cáo `reports/daily_digest_2026*.md`:

* **Chênh lệch `WATCH − REJECT` (`Exec Return`):**
  * `T+1` (`21` cohort): `+0.094%` (`13/21` dương, `6` cờ ngoài biên nhiễu)
  * `T+3` (`19` cohort): `+0.177%` (`12/19` dương, `2` cờ)
  * `T+5` (`17` cohort): `+0.345%` (`10/17` dương, `3` cờ)
  * `T+10` (`12` cohort): `+0.727%` (`7/12` dương, `3` cờ)
  * `T+20` (`2` cohort): `+1.610%` (`2/2` dương, `0` cờ)
* **5 chuỗi `T+5` không chồng lấn (cách nhau 5 phiên, trung bình 5 chuỗi = `+0.34%`, `2/5` vượt `+0.40%`):**
  * Chuỗi 1 (`10/14, 10/21, 10/28, 11/04`): `+0.51%` *(loại `14/10` còn `+0.39%`)*
  * Chuỗi 2 (`10/15, 10/22, 10/29, 11/05`): `+0.20%`
  * Chuỗi 3 (`10/16, 10/23, 10/30`): `-0.10%`
  * Chuỗi 4 (`10/19, 10/26, 11/02`): `+0.12%`
  * Chuỗi 5 (`10/20, 10/27, 11/03`): `+0.98%`
  * *Độ nhạy loại `2026-10-14` (giữ nguyên khung 5 chuỗi):* Mean 5 chuỗi còn `+0.32%` (`1/5` chuỗi `> +0.40%`).
* **Kiểm định Bootstrap tại mốc 22 phiên (`T+5`):**
  * Day-level IID 95% CI: `[-0.36%, +1.01%]`
  * Moving-Block Bootstrap (`L=5`): 95% CI = `[-0.95%, +1.31%]` (SE: `+0.59%`)
* **Phân kỳ hai nửa & Nội ngành (`T+5`):**
  * Hai nửa mẫu: `<= 23/10` (`n=8`): `-0.87%` vs `>= 26/10` (`n=9`): `+1.42%` (`opposite_halves = True`).
  * Nội ngành: `Ngân hàng` (`+0.23%`, `11/17` dương) | `Phi ngân hàng` (`+0.76%`, `10/17` dương).
  * **Leave-Real-Estate-Out (`Bất động sản dân dụng`):** loại khỏi `WATCH` còn **`-0.38%`**; loại khỏi cả `WATCH & REJECT` còn **`-0.20%`**.
  * **Leave-top-2-out (theo tổng đóng góp):** loại `KDH` (`+3.34%`) và `DIG` (`+2.96%`) làm `W−R` giảm từ `+0.34%` xuống **`+0.01%`**.
* **Lợi suất tuyệt đối & Cổng `BUY`:**
  * `T+5` `WATCH` = `+0.60%` (sau phí `0.40%` còn `+0.20%`) vs `Universe` `+0.37%`.
  * `BUY = 0` cả 22/22 phiên (`VN-Index` `1689.84–1774.15`, gap vs `MA200` từ `-5.95%` đến `-1.25%`).

---

## 2. Bộ Tiêu chí Quyết định Khóa trước (Đồng bộ 1-1 với Code)

### Mốc đánh giá & Phụ lục Out-of-Sample thuần
* **Mốc chính (Phiên 30 — dự kiến `2026-11-24`, thực tế `2026-11-25` do nghỉ lễ `24/11`):** Có `30` cohort `T0`, trong đó `25` cohort đáo hạn `T+5` (`2026-10-14` → `2026-11-17`, 5 quan sát/chuỗi). *(Xem Mục 5 Addendum cập nhật ngày lễ).*
* **Mốc hậu kiểm (dự kiến `2026-12-01`, thực tế đầu tháng 12/`2026-12-02`):** 5 cohort cuối (`18/11, 19/11, 20/11, 23/11, 25/11`) đáo hạn nốt `T+5`. **Quy tắc bắt buộc:** 5 cohort cuối này chỉ được báo cáo trong **Phụ lục Hậu kiểm riêng (Out-of-window Check)** nhằm kiểm tra độ ổn định kết luận, **tuyệt đối không gộp ngược vào mẫu chính 25 cohort để tính lại p-value hay lật ngược verdict phiên 30**.
* **Phụ lục Out-of-Sample thuần (`T0 >= 2026-11-13`):** Vì bộ tiêu chí khóa vào ngày `2026-11-12` sau khi đã quan sát 22 phiên, `22` phiên đầu là mẫu **in-sample đối với việc đặt ngưỡng**. Nhóm cohort có `T0 >= 2026-11-13` (gồm `3` cohort `T+5` tại mốc chính: `13/11, 16/11, 17/11`) là dữ liệu **out-of-sample thuần**. Do cỡ mẫu nhỏ và sức mạnh thống kê rất thấp, phụ lục này **chỉ mang tính mô tả**, không dùng để lật ngược phán quyết chính.

### Lưu ý về Sức mạnh Thống kê (Statistical Power)
* Với ~`5` khối quan sát hiệu dụng không chồng lấn (`SD ~ 1.5%`, block length `L=5`), nửa độ rộng của `95% CI` vào khoảng `1.2–1.5%`. Để `CI_low > 0%`, trung bình mẫu thực tế phải đạt cỡ `> +1.2%`.
* Ngược lại, chỉ tiêu `>= 3/5` chuỗi `> +0.40%` khi đứng riêng lẻ vẫn có xác suất dương giả ~`10–13%` dưới giả thuyết không (`SE ~ 0.65%/chuỗi`). Do đó **Moving-Block Bootstrap (`L=5`) là lớp bảo vệ thống kê chính**, còn `PASS` được hiểu là **đủ điều kiện chuyển sang nghiên cứu Giai đoạn 2**, không đồng nghĩa chứng minh tuyệt đối alpha vĩnh viễn.

### Lớp 1 — Hiệu suất tương đối (`W − R`) trên chuỗi không chồng lấn & Block Bootstrap
1. `passed_mean`: Trung bình 5 chuỗi `T+5` không chồng lấn `> +0.40%` **VÀ** tối thiểu `3/5` chuỗi `> +0.40%`.
2. `passed_boot`: Moving-Block Bootstrap theo ngày `T0` (`L = 5`, `n_boot = 5000`, `seed = 42`) có cận dưới `95% CI > 0.00%`.

### Lớp 2 — Kiểm soát Ngành, Tập trung Mã, Hai Nửa & Độ nhạy (`AND` toàn phần)
> **Minh bạch bậc tự do (Post-hoc Disclosure):** Cả ranh giới chia hai nửa mẫu (`<= 2026-10-23` vs `> 2026-10-23`) lẫn nhóm nhạy cảm `Bất động sản dân dụng` (`DXG, KDH, DIG, NLG, PDR` — lấy nguyên từ cột `sector` cố định trong `UNIVERSE_METADATA` của `update_forward_returns.py`) đều được xác định **sau khi quan sát 22 phiên đầu (`14/10 → 12/11`)**. Cả hai định nghĩa này được cố định nguyên trạng và commit cùng bản khóa trước phiên `13/11` để không phát sinh thêm bậc tự do trong 8 phiên cuối.

Tất cả các điều kiện sau phải đồng thời thỏa mãn trong code (`passed_layer2 = True`):
1. `both_sectors_pos`: `W−R T+5` nội ngành dương ở **cả hai** nhóm (`Ngân hàng > 0%` **VÀ** `Phi ngân hàng > 0%`). *(Dữ liệu ngành chuẩn hóa Unicode NFC; báo lỗi ngay nếu thiếu cột `sector` hoặc số mã Ngân hàng `< 8`)*.
2. `leave_re_pos`: Loại bỏ hoàn toàn nhóm `Bất động sản dân dụng` (`DXG, KDH, DIG, NLG, PDR`) khỏi `WATCH` lẫn khỏi cả `WATCH & REJECT` vẫn giữ `W−R T+5 > 0%`.
3. `trimmed_pos`: Loại bỏ **Top-2 mã đóng góp tích lũy lớn nhất** trong `WATCH` vẫn giữ `W−R T+5 > 0%`.
4. `consistent_halves`: Hai nửa mẫu (`<= 2026-10-23` vs `> 2026-10-23`) **không trái dấu** (`half1_mean * half2_mean >= 0`).
5. `sensitivity_no_flip`: Loại cohort `2026-10-14` (giữ nguyên khung 5 chuỗi ban đầu) **không làm thay đổi** kết quả đạt/trượt `passed_mean` của Lớp 1.

### Lớp 3 — Kiểm tra Bù đắp Chi phí Giao dịch (`WATCH Exec − 0.40%`)
* Điều kiện: `Mean(WATCH Exec T+5) − 0.40% > 0.00%`.
* **Quy ước diễn giải:** Lớp 3 phụ thuộc mạnh vào xu hướng chung của thị trường (nếu VN-Index hồi trong 8 phiên tới, `WATCH − 0.40% > 0%` dễ đạt ngay cả khi không có kỹ năng chọn mã); còn điều kiện `WATCH > Universe` thực chất trùng lặp về mặt đại số với `W−R > 0%`. Vì vậy **Lớp 3 chỉ là điều kiện cần để bù phí khi đọc chung với Lớp 1**, không dùng làm bằng chứng độc lập về alpha.

---

## 3. Ma trận Kết luận tại Phiên 30

**Thứ tự ưu tiên đánh giá trong code (`evaluate_prereg_verdict`):**
1. Kiểm tra `PASS`: chỉ đạt khi `L1.passed_mean` **AND** `L1.passed_boot` **AND** `L2.passed_layer2` **AND** `L3.passed_layer3` đều `True`.
2. Nếu không đạt `PASS`, kiểm tra điều kiện tiên quyết của `REGIME-CONDITIONAL`: `L1.passed_mean` **AND** `L3.passed_layer3`. Vì vậy, các kiểm tra của **Lớp 2** (bao gồm `opposite_halves`, `leave_re_pos`, `trimmed_pos`) và `L1.passed_boot` **chỉ có tác dụng phân loại sang `REGIME-CONDITIONAL` khi `L1.passed_mean` và `L3.passed_layer3` đã đạt**.
3. Nếu không đạt `L1.passed_mean` **OR** không đạt `L3.passed_layer3`, hệ thống trả thẳng về **`FAIL / INCONCLUSIVE`** bất kể `opposite_halves` là `True` hay `False` (đúng như kết quả dry-run 22 phiên).

| Kết luận | Điều kiện logic trong code | Ý nghĩa & Hành động |
| :--- | :--- | :--- |
| **PASS (Đủ điều kiện chuyển sang Giai đoạn 2)** | `L1.passed_mean` **AND** `L1.passed_boot` **AND** `L2.passed_layer2` **AND** `L3.passed_layer3` | Hệ thống vượt qua cả ngưỡng thực tế lẫn kiểm định phụ thuộc chuỗi/ngành/tập trung. Đủ điều kiện chuyển sang thiết kế kiểm thử cổng `BUY` ở Giai đoạn 2. |
| **REGIME-CONDITIONAL / SECTOR-DRIVEN** | `L1.passed_mean` **AND** `L3.passed_layer3`, nhưng trượt `L1.passed_boot` **OR** trượt `L2.passed_layer2` (ví dụ hai nửa trái dấu hoặc phụ thuộc cụm BĐS). | Có chênh lệch danh nghĩa trên `W−R`, nhưng chưa loại trừ được nhiễu phụ thuộc chuỗi, tính mùa vụ theo pha thị trường, hoặc tập trung ngành. Không nâng trọng số trực tiếp; nghiên cứu tách điều kiện regime/ngành. |
| **FAIL / INCONCLUSIVE (Không chứng minh được edge vượt ngưỡng trong 30 phiên)** | Không đạt `L1.passed_mean` **OR** không đạt `L3.passed_layer3`. | Trong phạm vi 30 phiên, **không chứng minh được** `WATCH` tạo ra hiệu suất vượt ngưỡng chi phí (gộp cả khả năng chưa có edge thật lẫn không đủ sức mạnh thống kê với ~5 khối độc lập). Không mở rộng quy mô; rà soát lại `TECH_CONFIRMATION` / `RISK_TRAP`. |

---

## 4. Điều kiện Dừng sớm & Phạm vi Giai đoạn 2 (Cổng `BUY`)

* **Điều kiện dừng sớm duy nhất trước phiên 30:**
  1. Pipeline hoặc Data Gate phát sinh lỗi dữ liệu nghiêm trọng không thể khắc phục ngay trong ngày, hoặc
  2. Chủ động sửa logic/tham số hệ thống — khi đó bắt buộc **reset bộ đếm về 0** và không gộp mẫu cũ với mẫu mới.
* **Cách ly các khám phá mới:** Từ sau thời điểm commit & tag bản khóa trước phiên `2026-11-13`, chỉ chạy nguyên trạng `scripts/audit_30_sessions.py` và đọc kết quả; mọi ý tưởng/giả thuyết phát sinh thêm phải đưa vào mục khám phá riêng và **không** được phép chỉnh sửa tiêu chí hay ảnh hưởng đến phán quyết của kỳ 30 phiên này.
* **Tách riêng Giai đoạn 2 — Kiểm thử Cổng Regime / `BUY`:**
  * Do `BUY = 0` toàn bộ `22` phiên đầu (tại thời điểm khóa `12/11`, và tiếp tục `0/30` đến hết phiên `30` ngày `25/11`), `30` phiên này chỉ kiểm định được năng lực phân hạng `WATCH vs REJECT` và trạng thái phòng vệ `Cash (0%)` trong `DOWNTREND`.
  * Sau khi đóng sổ phiên 30, thiết kế riêng một thử nghiệm **Shadow / Paper-trade Cổng `BUY`** (xem `stage2_buy_gate_prereg.md` v2.0) mà không làm nhiễu dữ liệu kiểm toán của bản `v15.0_frozen_20261013`.

---

## 5. Addendum: Mối quan hệ giữa Mốc 30 Phiên (v1.1/v1.2) và Khung Phản nghiệm 60 Phiên (Protocol Gốc)

Nhằm đảm bảo tính minh bạch khoa học tuyệt đối và tránh tranh luận "kết luận chính thức là ở phiên 30 hay phiên 60":

1. **Phán quyết Khóa Phiên 30 (`2026-11-25` thực tế thay cho `2026-11-24` nghỉ lễ / Hậu kiểm `2026-12-02`):**
   * Mốc 30 phiên là **kiểm tra chính thức với phán quyết (verdict) đã đóng băng** cho khung kiểm toán v1.1/v1.2 (đánh giá trên `25` cohort `T+5` `14/10 → 17/11` với 5 chuỗi quan sát không chồng lấn). *(Do ngày `24/11` nghỉ lễ, phiên 30 dịch sang `25/11` và mốc hậu kiểm 5 cohort cuối `18/11–25/11` dịch sang đầu tháng 12/`2026-12-02`)*.
   * Tiêu chí và các ngưỡng số học tại mốc này là bất biến, tuyệt đối **không thay đổi hay di chuyển cột gôn**.
   * Nếu kết quả phiên 30 trả về `FAIL / INCONCLUSIVE`, nó mang ý nghĩa chuẩn xác là: *"Hệ thống không chứng minh được edge vượt ngưỡng chi phí trong phạm vi 30 phiên"*. Phán quyết này không đóng cửa việc thu thập dữ liệu tiếp theo.

2. **Khung Phản nghiệm Mở rộng 60 Phiên (Điểm Kiểm tra Giữa kỳ cho $\sigma$):**
   * Kỳ 60 phiên trong protocol gốc là khung phản nghiệm mở rộng đóng vai trò **điểm kiểm tra giữa kỳ (interim statistical power check)** nhằm ước lượng lại độ lệch chuẩn $\sigma$ tin cậy hơn và tích lũy mẫu cho các kỳ hạn dài hơn ($T+10$ và $T+20$) — lưu ý ước tính thô cho thấy để đủ sức mạnh thống kê đầy đủ cho $T+5/T+10$ thường cần tới `~190–250` phiên, nên mốc 60 phiên dùng để đánh giá lại độ lớn $\sigma$ trước khi quyết định độ dài tiếp theo, không phải ngưỡng kết luận cuối cùng.
   * Việc chạy tiếp từ phiên 31 đến phiên 60 diễn ra trên cùng một nền tảng đóng băng `v15.0_frozen_20261013` (cùng một epoch, không reset).
   * **Quy tắc Bất khả Hồi tố (No-Retroactive Overwrite):** Cả 5 cohort hậu kiểm (`18/11 → 25/11`) lẫn kỳ 60 phiên đều có báo cáo/phụ lục độc lập riêng. Kết quả tại hai mốc này **tuyệt đối không được dùng để lật ngược hay viết lại verdict đã khóa trên 25 cohort `T+5` (`14/10 → 17/11`) tại phiên 30**. Nếu các mốc sau cho kết quả khác, ghi nhận như thông tin/phát hiện mới của khung thời gian dài hơn, không thay thế phán quyết phiên 30.
   * **Ghi chú điều chỉnh ngày lễ `2026-11-24`:** Vì `2026-11-24` là ngày lễ thị trường Việt Nam đóng cửa, phiên 30 thực tế rơi vào ngày **`2026-11-25`**, và 5 cohort hậu kiểm cuối kỳ là **`18/11, 19/11, 20/11, 23/11, 25/11`**. Toàn bộ ngưỡng số học và logic kiểm định vẫn giữ nguyên bất biến.

3. **Ghi chú về Quy tắc Dừng 1–3 trong Protocol Gốc:**
   * *Quy tắc 1 (Kém hiệu quả thống kê W−R lệch âm > −5% với p < 0.05):* Với độ lệch chuẩn cấp cohort ~1.5%–2.0% và W−R thực tế dao động quanh 0%, biên lệch âm tới −5% mang tính giả định cực đoan và gần như không thể kích hoạt trên thực tế trong 30–60 phiên.
   * *Quy tắc 2 (Sụt giảm danh mục 15% / Drawdown):* Khi `BUY = 0` trong suốt Downtrend, danh mục giữ $100\%$ Tiền mặt (lợi suất $0.00\%$), do đó quy tắc sụt giảm danh mục $15\%$ gần như không thể kích hoạt trong Giai đoạn 1.
   * *Quy tắc 3 (Tê liệt phát tín hiệu 45 phiên):* Việc không phát sinh lệnh mua (`BUY = 0`) suốt 30–45 phiên là hệ quả cấu trúc dự kiến của cổng `GATE_MACRO_REGIME` khi VN-Index nằm dưới `MA200`, không phải sự cố tê liệt hệ thống. Quy tắc này chỉ mang ý nghĩa vận hành đối soát hoặc khi Giai đoạn 2 chạy thử nghiệm giải ngân.
