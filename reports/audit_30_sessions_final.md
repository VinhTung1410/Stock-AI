# BÁO CÁO KIỂM TOÁN HỆ THỐNG (2026-10-14 → 2026-11-25)

- **Số phiên canonical:** `30` | **Digest:** `30` | **Số phiên BUY > 0:** `0`
- **KẾT LUẬN THEO TIÊU CHÍ KHÓA TRƯỚC:** **`FAIL / INCONCLUSIVE (Không chứng minh được edge vượt ngưỡng trong 30 phiên)`**

### 1. LỚP 1 — 5 CHUỖI T+5 KHÔNG CHỒNG LẤN & BLOCK BOOTSTRAP
| Chuỗi | Số điểm | Các ngày T0 | Mean W−R (%) | Vượt phí 0.40% |
| :---: | :---: | :--- | :---: | :---: |
| 1 | 5 | 2026-10-14, 2026-10-21, 2026-10-28, 2026-11-04, 2026-11-11 | **+0.57%** | Có |
| 2 | 5 | 2026-10-15, 2026-10-22, 2026-10-29, 2026-11-05, 2026-11-12 | **+0.17%** | Không |
| 3 | 5 | 2026-10-16, 2026-10-23, 2026-10-30, 2026-11-06, 2026-11-13 | **+0.04%** | Không |
| 4 | 5 | 2026-10-19, 2026-10-26, 2026-11-02, 2026-11-09, 2026-11-16 | **+0.09%** | Không |
| 5 | 5 | 2026-10-20, 2026-10-27, 2026-11-03, 2026-11-10, 2026-11-17 | **+0.51%** | Có |

- **Trung bình 5 chuỗi T+5:** `+0.28%` (`2/5` chuỗi > +0.40%)
- **Day-level IID 95% CI:** `[-0.20%, +0.75%]`
- **Moving-Block Bootstrap (L=5) 95% CI:** `[-0.45%, +1.26%]` (SE: `+0.44%`)

### 2. LỚP 2 — ĐỘ ĐỒNG NHẤT HAI NỬA, PHÂN RÃ NGÀNH & TẬP TRUNG MÃ
- **Hai nửa mẫu (`<= 2026-10-23` vs `> 2026-10-23`):** Nửa 1 (`n=8`) `-0.87%` | Nửa 2 (`n=17`) `+0.82%` | Trái dấu: `True`
- **Ngân hàng:** `n=25` cohort | WATCH `-0.52%` | REJECT `-0.56%` | W−R **`+0.04%`** (`13/25` dương)
- **Phi ngân hàng:** `n=25` cohort | WATCH `+0.01%` | REJECT `-0.58%` | W−R **`+0.59%`** (`15/25` dương)
- **Leave-Real-Estate-Out (loại `Bất động sản dân dụng`):** Loại khỏi WATCH: **`-0.37%`** | Loại khỏi cả WATCH & REJECT: **`-0.21%`**
- **Leave-top-2-out (theo tổng đóng góp):** Top-2 WATCH: `KDH` (+2.43%), `NLG` (+2.01%) → W−R còn **`-0.06%`** (gốc `+0.28%`)
- **Độ nhạy loại `2026-10-14`:** Chuỗi 1 còn `+0.49%` | Mean toàn kỳ `+0.25%` | Mean 5 chuỗi **`+0.26%`** (`2/5` chuỗi > +0.40%, Layer 1 flip: `False`)

### 3. LỚP 3 — LỢI SUẤT TUYỆT ĐỐI & ĐỘ ỔN ĐỊNH WATCHLIST *(đọc kèm Lớp 1)*
- **T+1 (`n=29`):** WATCH `-0.01%` (sau phí `-0.41%`) | REJECT `-0.09%` | Universe `-0.07%`
- **T+3 (`n=27`):** WATCH `-0.17%` (sau phí `-0.57%`) | REJECT `-0.26%` | Universe `-0.23%`
- **T+5 (`n=25`):** WATCH `-0.32%` (sau phí `-0.72%`) | REJECT `-0.59%` | Universe `-0.50%`
- **Watchlist Churn:** Đổi rổ `13/29` lần chuyển phiên | Core cố định: `14` mã

### 4. PHỤ LỤC OUT-OF-SAMPLE THUẦN (`T0 >= 2026-11-13`)
- **Số cohort T+5 đáo hạn sau khóa tiêu chí:** `3` (`2026-11-13`, `2026-11-16`, `2026-11-17`) | **Mean W−R:** `-0.43%` (`0/3` dương) | **WATCH sau phí 0.40%:** `-3.63%`
- *(Ghi chú phương pháp luận: Với cỡ mẫu chỉ gồm `3` cohort đáo hạn tại mốc chính, phụ lục Out-of-Sample thuần có sức mạnh thống kê rất thấp và **chỉ mang tính mô tả**, không dùng để diễn giải lại hoặc lật ngược verdict chính).*

---

### 5. DATA ANOMALIES & ĐÍNH CHÍNH NGOẠI LỆ NGÀY LỄ (`2026-11-24` → `2026-11-25`)
1. **Dịch chuyển lịch nghỉ lễ `2026-11-24`:** Thị trường Việt Nam đóng cửa nghỉ lễ ngày `2026-11-24`. Do đó phiên giao dịch thứ 30 (`T0` thứ 30) thực tế rơi vào ngày **`2026-11-25`**, và chuỗi `25` cohort `T+5` đáo hạn (`14/10 → 17/11`, mỗi chuỗi đúng `5` quan sát) đã hoàn tất trọn vẹn tại ngày `25/11`.
2. **Tính toàn vẹn chuỗi lợi suất `T+5` cohort `2026-11-17`:** Chuỗi 5 phiên giao dịch thực tế của cohort `17/11` gồm **`18/11, 19/11, 20/11, 23/11, 25/11`** (đủ 5 quan sát liên tiếp, bỏ qua ngày lễ `24/11`). Giá trị `T+5` đáo hạn ngày `25/11` (`WATCH -3.09%`, `REJECT -2.46%`, `Diff -0.63%`) không bị méo.
3. **Khoanh vùng tệp ngoại lệ `canonical_forward_returns_20261124.csv`:** Tồn tại tệp `canonical_forward_returns_20261124.csv` (không có `decision_records_20261124.csv` tương ứng) chứa giá `close_t0` và `entry_date_t0 = 2026-11-25`. Tệp này từng gây ra hai lỗi hiển thị ở tầng báo cáo `daily_digest_20261125.md` (báo thêm mới 18 mã do so sánh với `24/11` rỗng, và dịch chỉ số lịch khiến khuyết dòng `T+10` cohort `10/11` và `T+20` cohort `27/10`).
   * **Biện pháp đã áp dụng:** Đã cập nhật logic đọc lịch phiên giao dịch thực tế (khớp `entry_date_t0 == tên tệp`, đối chiếu trạng thái với phiên giao dịch liền trước `2026-11-23`) trong `scripts/generate_daily_digest.py` và bộ lọc deduplicate trong `scripts/audit_30_sessions.py`, tái tạo sạch `reports/daily_digest_20261125.md` kèm bộ test hồi quy trong `tests/test_daily_digest.py`. Không có bất kỳ chỉnh sửa nào đối với logic tín hiệu đóng băng `v15.0_frozen_20261013`.

---

### 6. CẢNH BÁO CHẾ ĐỘ THỊ TRƯỜNG (`REGIME CONDITIONALITY`) & LỘ TRÌNH KẾ TIẾP
1. **Giới hạn pha thị trường:** Toàn bộ `30` phiên quan sát (`2026-10-14 → 2026-11-25`) diễn ra trọn vẹn trong pha **`DOWNTREND`** (`VN-Index` dao động dưới `MA200` từ `-1.25%` đến `-5.35%`, `BUY = 0` ở cả `30/30` phiên).
   * Ở góc độ phòng vệ, việc giữ `100% Tiền mặt (0.00%)` đã tránh được chuỗi tuần giảm sâu cuối kỳ (`Universe T+5` đạt `-0.50%` trên toàn kỳ và giảm mạnh `-0.96%` tới `-3.76%` ở các cohort `09/11 → 17/11`).
   * Tuy nhiên, mọi kết luận về `WATCH − REJECT` và hiệu suất phòng vệ chỉ mang tính **có điều kiện trong pha Downtrend**, không thể ngoại suy sang pha `UPTREND`.
2. **Chấp nhận thẳng Verdict `FAIL / INCONCLUSIVE`:** Trên 25 cohort `T+5` khóa trước, trung bình 5 chuỗi đạt `+0.28%` (`2/5` chuỗi > `+0.40%`), Block Bootstrap 95% CI là `[-0.45%, +1.26%]`, hai nửa mẫu trái dấu (`-0.87%` vs `+0.82%`), và khi loại nhóm BĐS dân dụng hoặc Top-2 đóng góp (`KDH`, `NLG`) thì `W−R` đảo về âm (`-0.37%` / `-0.06%`). Hệ thống kết luận thẳng là **chưa chứng minh được alpha vượt ngưỡng chi phí trong 30 phiên**.
3. **Định vị Mốc 60 Phiên (`31 → 60`):** Tiếp tục thu thập phiên `31 → 60` trên cùng nền tảng `v15.0_frozen_20261013` đóng vai trò **điểm kiểm tra giữa kỳ (interim power check)** để ước lượng lại $\sigma$ và tích lũy mẫu $T+10 / T+20$ (không dùng để lật lại verdict phiên 30; ước tính đủ lực thống kê dài hạn cần `~190–250` phiên).

---

### 7. KHUNG PHỤ LỤC HẬU KIỂM (`OUT-OF-WINDOW CHECK`: 5 COHORT CUỐI `18/11 → 25/11`)
* **Danh sách 5 cohort cuối chưa đáo hạn `T+5` tại ngày `25/11`:** `2026-11-18`, `2026-11-19`, `2026-11-20`, `2026-11-23`, `2026-11-25` (dự kiến đáo hạn `T+5` đầy đủ vào đầu tháng 12/`2026-12-02`).
* **Quy tắc Bất khả Hồi tố (Locked):** Khi 5 cohort này đáo hạn đủ `T+5`, kết quả của chúng chỉ được điền vào phụ lục này để kiểm tra độ ổn định định tính của kết luận, **tuyệt đối không gộp ngược vào mẫu chính `25` cohort để tính lại p-value hay sửa đổi phán quyết `FAIL / INCONCLUSIVE` của Mốc 30 phiên**.
* *Trạng thái tại `2026-11-25`:* `Chờ đáo hạn T+5 (0/5 matured)`.
