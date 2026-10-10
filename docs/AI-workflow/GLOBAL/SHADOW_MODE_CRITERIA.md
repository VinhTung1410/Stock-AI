# TIÊU CHÍ ĐÁNH GIÁ MÔ HÌNH SHADOW (PRE-REGISTERED SPECIFICATION)

> **Mã văn bản:** SPEC-SHADOW-001  
> **Trạng thái:** PRE-REGISTERED (Đăng ký trước khi nhìn dữ liệu OOS)  
> **Thời điểm xác lập (Timestamp):** `2026-10-10T12:00:00Z`  
> **Phạm vi áp dụng:** Toàn bộ hệ thống định giá 4 Archetypes (Bank, Real Estate, Cyclical, Compounder)  

---

## 1. Mục đích & Nguyên tắc cốt lõi

Mô hình Shadow (Shadow Valuation & Shadow IC) được thiết kế nhằm mục đích **kiểm tra độ hợp lý phân bố (distributional sanity)** và **phát hiện sai lệch mô hình (outlier / model dispersion detection)**, tuyệt đối **không** dùng chỉ số Information Coefficient (IC) ngắn hạn làm điều kiện tiên quyết duy nhất để kích hoạt hay loại bỏ mô hình khỏi môi trường Production.

---

## 2. Chứng minh toán học về Năng lực Thống kê (Statistical Power) của IC

### 2.1. Sai số chuẩn (Standard Error) của Rank IC
Với danh mục mẫu khoảng $N \approx 30$ cổ phiếu tại một thời điểm cắt ngang (cross-section):
$$\text{SE}(\text{IC}_t) \approx \frac{1}{\sqrt{N - 1}} = \frac{1}{\sqrt{29}} \approx 0.1857 \approx 0.19$$

### 2.2. Số kỳ độc lập tối thiểu để đạt mức ý nghĩa thống kê ($t > 2.0$)
Giả sử mô hình định giá có năng lực dự báo thực chất với Information Coefficient trung bình kỳ vọng là $\mu_{\text{IC}} = 0.05$ (mức chuẩn mực trong định lượng tài chính).  
Để $t$-statistic vượt ngưỡng tin cậy 95% ($t > 2.0$):
$$t = \frac{\bar{\text{IC}}}{\text{SE} / \sqrt{T}} = \frac{0.05}{0.1857 / \sqrt{T}} \ge 2.0 \implies \sqrt{T} \ge \frac{2.0 \times 0.1857}{0.05} = 7.428 \implies T \ge 55.2 \approx 58 \text{ kỳ độc lập}$$

### 2.3. Hệ quả về chu kỳ thời gian (Horizon)
- Với horizon dự phóng là **20 phiên giao dịch** (1 tháng):  
  Cần tối thiểu $58 \times 20 = 1,160$ phiên giao dịch độc lập không chồng lấn ($\approx 4.6$ năm dữ liệu lịch sử) để khẳng định $t > 2.0$.
- **Nguy cơ tự tương quan khi kiểm định 60 phiên liên tiếp:**  
  Nếu tính IC hàng ngày trên 60 phiên liên tục với horizon 20 phiên, thực chất chỉ có $60 / 20 = 3$ kỳ độc lập không chồng lấn. Các quan sát IC hàng ngày bị tự tương quan chuỗi nặng nề (autocorrelated up to lag 20), khiến sai số chuẩn naive bị bóp méo và $t$-statistic bị thổi phồng nhân tạo khoảng $\sqrt{20} \approx 4.5$ lần.

### 2.4. Quy định đo lường chuẩn hóa:
1. **Bắt buộc áp dụng hiệu chỉnh Newey-West (HAC):** Khi đo lường IC trên chuỗi rolling hàng ngày, phải dùng độ trễ tối thiểu $L = 20$ phiên để khử tự tương quan.
2. **Ưu tiên kỳ không chồng lấn (Non-overlapping buckets):** Lấy mẫu định kỳ 20 phiên/lần (monthly rebalance) thay vì rolling hàng ngày khi kết luận năng lực dự báo của mô hình.

---

## 3. Bãi bỏ các ngưỡng tuyệt đối phụ thuộc chế độ thị trường (Regime-Blind Hurdles)

### 3.1. Phê phán tiêu chí cũ
Tiêu chí cũ đề xuất: *“$\le 30\%$ mã có $\text{MoS} \ge 15\%$ ở thị trường cân bằng”*.  
**Sai lầm căn bản:** Tiêu chí này giả định ngầm rằng thị trường luôn ở trạng thái cân bằng. Trong thực tế, khi VN-Index trải qua pha sụt giảm sâu (Bear Market / Downtrend dài hạn), định giá toàn thị trường bị chiết khấu mạnh, việc $40\% - 60\%$ số mã có $\text{MoS} \ge 15\%$ là hiện tượng kinh tế hoàn toàn hợp lý và lành mạnh. Nếu dùng một ngưỡng tuyệt đối cứng nhắc sẽ dẫn tới **loại bỏ oan một mô hình định giá chính xác**.

### 3.2. Tiêu chí mới thay thế:
1. **Độ phân tán tương đối (Relative Dispersion):** So sánh phân bố MoS của danh mục với phân vị định giá lịch sử P/E và P/B của toàn chỉ số VN-Index thay vì dùng tỷ lệ phần trăm cố định.
2. **Giới hạn cận biên tính hợp lý (Sanity Range):**
   $$0.50 \le \frac{\text{Fair Value}}{\text{Thị giá hiện tại}} \le 2.00$$
   Bất kỳ cổ phiếu nào có Fair Value rơi ra ngoài khoảng $[0.50 \times \text{Price}, 2.00 \times \text{Price}]$ phải bị gắn cờ `EXTREME_VALUATION_DISPERSION` và yêu cầu kiểm toán tham số.

---

## 4. Ứng dụng nghiệp vụ của Mô hình Shadow trong Production

Mô hình Shadow được vận hành song song với mô hình chính thức với 3 nhiệm vụ cụ thể:

| STT | Ứng dụng | Cơ chế kích hoạt | Hành động của Hệ thống |
|---|---|---|---|
| **1** | **Tín hiệu Confidence nội sinh** | $\|\text{FV}_{\text{shadow}} - \text{FV}_{\text{main}}\| / \text{FV}_{\text{main}} > 15\%$ | Tự động hạ `confidence` từ `HIGH` xuống `MEDIUM`. Báo cáo ghi nhận cảnh báo phân tán mô hình. |
| **2** | **Chốt chặn ngoại lai (Outlier Gate)** | $\text{FV} / \text{Price} < 0.50$ hoặc $> 2.00$ | Khóa khuyến nghị MUA, yêu cầu xác minh lại BCTC và bội số định giá cơ sở. |
| **3** | **Kiểm toán dài hạn Out-of-Sample** | Tích lũy tối thiểu $T \ge 60$ kỳ không chồng lấn | Phân tích hồi quy Fama-MacBeth và Newey-West $t$-stat để hiệu chuẩn lại trọng số các mô hình. |

---

## 5. Cam kết kiểm toán (Audit Trail)
- Tiêu chí này được cam kết trực tiếp vào mã nguồn Git trước khi chạy bất kỳ chuỗi backtest OOS nào.
- Mọi điều chỉnh ngưỡng trong tương lai phải được ghi nhận dưới dạng một Architecture Decision Record (ADR) mới kèm theo phân tích năng lực thống kê tương đương.
