# Pre-Registration Giai đoạn 2: Thử nghiệm Shadow Cổng `BUY` & Bộ lọc Regime

**Ngày khóa tiêu chí:** `2026-11-12` (soạn trước trong thời gian chờ đóng sổ 30 phiên Giai đoạn 1 để tránh thiên kiến theo kết quả phiên 30)  
**Trạng thái hiện tại:** **CHƯA KÍCH HOẠT** — chỉ bắt đầu thu thập dữ liệu sau khi hoàn tất đóng sổ Giai đoạn 1 (`v15.0_frozen_20261013`, mốc `2026-11-24` / `2026-12-01`).  
**Mục tiêu:** Giải quyết điểm mù lớn nhất của Giai đoạn 1 (`BUY = 0` suốt `22` phiên đầu khi `VN-Index` dao động dưới `MA200` từ `-5.95%` đến `-1.25%`) thông qua thử nghiệm `SHADOW_BUY` hoàn toàn tách biệt với luồng sản xuất.

---

## 1. Các Nhánh Ngưỡng Thử nghiệm (Candidate Arms — Chỉ chạy Shadow)

Tất cả các nhánh chỉ được phép chọn từ các mã đã qua `WATCH` (`TECH_CONFIRMATION` / `RISK_TRAP` giữ nguyên), chỉ thay đổi điều kiện của `GATE_MACRO_REGIME` (`entry_gates.py` / `regime_classifier.py`):

| Nhánh | Định nghĩa điều kiện mở cổng `SHADOW_BUY` | Quy mô vị thế giả định | Ghi chú kỹ thuật |
| :--- | :--- | :--- | :--- |
| **Arm 0 (Baseline)** | Theo logic đóng băng `v15.0`: `UPTREND` chuẩn (`VN-Index >= MA200`, `Slope(MA200) >= -0.5%`). | `0%` khi `DOWNTREND`; `100%` trần khi `UPTREND` | Nhánh đối chứng giữ `100% Cash (0.00%)` trong `DOWNTREND`. |
| **Arm A (MA200 Proximity Buffer)** | `vs MA200 >= -2.0%` **VÀ** `VN-Index > MA20` **VÀ** `Slope(MA20) > 0` duy trì tối thiểu `2` phiên liên tiếp. | Tối đa `50%` ngân sách vị thế (nửa Kelly) | Kiểm tra vùng đệm ngay sát dưới `MA200` khi động lượng ngắn hạn đã đảo chiều. |
| **Arm B (Hysteresis & Volume Confirm)** | Áp dụng `classify_regime_ma200_hysteresis` (`reentry_pct = +1.0%`, `confirmation_sessions = 2`, `vol_surge_mult = 1.3`) từ `regime_classifier.py`. | `75%–100%` ngân sách vị thế | Kiểm tra hàm có sẵn trong repo nhằm giảm whipsaw quanh `MA200`. |
| **Arm C (Breadth + MA200 Floor)** | `vs MA200 >= -3.0%` **VÀ** tỷ lệ mã trong Universe 55 mã đóng cửa trên `MA20 >= 40%` trong `>= 2` phiên liên tiếp. | Tối đa `50%` ngân sách vị thế | Đảm bảo độ rộng thị trường đồng thuận trước khi mở mua sớm dưới `MA200`. |

> **Ràng buộc chống bùng nổ bậc tự do:** Cố định đúng `3` nhánh thử (`Arm A, B, C`) so với `Arm 0`. Không tinh chỉnh thêm các mức đệm khác (`-1.5%`, `-2.5%`, v.v.) sau khi đã bắt đầu chạy Giai đoạn 2.

---

## 2. Quy mô Mẫu & Số Phiên Tối thiểu

* **Số phiên quan sát tối thiểu:** **`30` phiên giao dịch mới** tính từ ngày khởi động Giai đoạn 2 (tách biệt hoàn toàn, không gộp mẫu với `30` phiên Giai đoạn 1).
* **Số tín hiệu `SHADOW_BUY` tối thiểu:** Tối thiểu **`20` lệnh `SHADOW_BUY` độc lập** (không tính lặp cùng một mã trong vòng `5` phiên liên tiếp) đã đáo hạn đủ `T+5` và `T+10` cho nhánh được đánh giá.
* **Quy tắc gia hạn nếu thị trường vẫn đóng băng:** Nếu sau `30` phiên đầu mà một nhánh phát sinh `< 10` tín hiệu `SHADOW_BUY`, tiếp tục chạy tối đa tới **`60` phiên** (khớp `MIN_SHADOW_SESSIONS = 60` trong `scripts/evaluate_shadow_graduation.py`). Nếu đến phiên `60` vẫn `< 10` tín hiệu, ghi nhận nhánh đó không đủ tần suất hoạt động trong chế độ thị trường mục tiêu.

---

## 3. Chỉ số Đánh giá & Tiêu chí Tốt nghiệp (Graduation Criteria)

### Chỉ số chính (Primary Metrics — tính trên giá khớp `Open_T+1 → Close_T+h`)
1. **Lợi suất ròng vượt Tiền mặt (`Net Excess vs Cash`):**
   * `Mean(SHADOW_BUY Exec T+5) − 0.40% > 0.00%` và `Mean(SHADOW_BUY Exec T+10) − 0.40% > 0.00%` (đánh giá theo cụm ngày `T0` không chồng lấn hoặc block bootstrap theo ngày để tránh phóng đại cỡ mẫu).
2. **Đánh đổi Rủi ro sụt giảm vs Chi phí cơ hội (`Drawdown vs Arm 0`):**
   * `Max Drawdown` mô phỏng ở cấp danh mục của nhánh thử nghiệm **không vượt quá `-5.0%`** trong pha thử nghiệm, và `Calmar / Profit Factor` phải vượt nhánh `Arm 0` trong các phiên có mở vị thế.

### Chỉ số phụ (Secondary Diagnostic Metrics)
1. **Tỷ lệ thắng sau phí (`Net Hit Rate`):** Số lệnh `SHADOW_BUY` có `Exec Return − 0.40% > 0%` đạt `>= 50%` ở `T+5` và hướng tới `>= 55%` ở `T+10` (tham chiếu `MIN_HIT_RATE_T10 = 0.55`).
2. **Tỷ lệ nhiễu đảo pha (`Whipsaw Rate`):** Tỷ lệ lần mở cổng `SHADOW_BUY` nhưng điều kiện `Regime` lại sập xuống dưới ngưỡng chỉ trong vòng `<= 5` phiên kế tiếp (yêu cầu `<= 25%`).
3. **Alpha gia tăng so với rổ cơ sở:** `SHADOW_BUY` có vượt trội trung bình `WATCH` toàn kỳ và `Universe (55 mã)` hay chỉ hưởng lợi từ nhịp hồi chung của chỉ số.

---

## 4. Điều kiện Kích hoạt & Cách ly

* Chỉ được phép viết code/bật cờ `SHADOW_BUY` **sau khi** có báo cáo đóng sổ chính thức của Giai đoạn 1 (`reports/audit_30_sessions_final.md`).
* Mọi kết quả Giai đoạn 2 lưu tách riêng bằng nhãn `decision = SHADOW_BUY`, tuyệt đối không trộn vào bảng `canonical_forward_returns_*.csv` của Giai đoạn 1.
