# V13 Momentum Research Plan (Exploratory)

## 1. Bối cảnh
Dự án V12 nhằm tìm kiếm Alpha bắt đáy (Contrarian) bằng `DD60` đã khép lại với kết quả: Không tìm thấy hiệu ứng contrarian cỡ $\ge 0.03$ trên tập 56 mã Large/Mid-cap sống sót.
Trong quá trình chạy V12, hai tín hiệu phụ (`RSI14` và `Rev5`) cho thấy IC dương (hiệu ứng Momentum). Tuy nhiên, đây là phát hiện **thăm dò (exploratory)** được nhìn thấy *sau khi mở dữ liệu*, và chưa được kiểm soát đa kiểm định (M=9 phép thử) cũng như chưa được trung hòa (Neutralization) để lọc bỏ Beta, Size, và Industry.
V13 được mở ra để kiểm định chặt chẽ giả thuyết Momentum này.

## 2. Giả thuyết (Hypothesis)
**Momentum:** Các cổ phiếu có đà tăng trưởng mạnh (đo bằng RSI14) sẽ tiếp tục vượt trội hơn so với thị trường trong 20 ngày giao dịch tiếp theo.

## 3. Khung Dữ liệu (Dataset)
- **Tập Discovery:** Sử dụng lại đúng Panel Data đã đóng băng của V12 (Hash: `78c042d45b71879b6bcfbcdb2d310203d398a11ef6bd9ddb2dcf4b804a108d54`), giới hạn từ `2018-01-02` đến `2023-11-30`.
- **Lưu ý về Survivorship Bias:** Universe 56 mã hiện tại mang sẵn thiên lệch sống sót (có xu hướng tăng và ổn định). Điều này ưu ái cho Momentum. Mọi kết quả IC dương cần được chiết khấu độ tin cậy.

## 4. Biến Số
- **Feature:** `RSI14`. (Chọn 1 đại diện duy nhất để tránh P-hacking).
- **Target (Dependent Variable):** `ret_D1_to_D20` = `(Close(D+20) - Open(D+1)) / Open(D+1)`. Đây là mức lợi suất có thể giao dịch được (Tradable Return) sau khi loại bỏ hiệu ứng qua đêm `D -> D+1` (Microstructure).

## 5. Trung Hòa (Neutralization)
Để đảm bảo tín hiệu Momentum không phải là proxy của các rủi ro hệ thống, Feature sẽ được trung hòa thông qua Cross-sectional Regression với các biến kiểm soát:
1. **Industry (Xấp xỉ):** Phân loại thô thành 3 nhóm: `Bank`, `Real_Estate`, `Others`.
2. **Size / Liquidity Proxy:** Xếp hạng `adv_20d` (mặc dù bị méo do volume chưa điều chỉnh, đây là proxy duy nhất hiện có). Có thể dùng log(ADV) hoặc rank(ADV).
3. **Beta / Market Return:** IC sẽ tính toán trên thặng dư lợi suất (Relative Return).

## 6. Tiêu Chí Quyết Định (Pre-registered Criteria)
1. **Residual Alpha:** Mean Rank IC của tín hiệu RSI14 *sau khi trung hòa* phải khác 0 với ý nghĩa thống kê $t_{NW} \ge 2.5$ (Ngưỡng cao hơn do penalty từ đa kiểm định Holm-Bonferroni của đợt quét trước).
2. **OOS Validation:** NẾU vượt qua được Discovery, tín hiệu mới được quyền chạy 1 LẦN DUY NHẤT trên tập **Semi-Holdout (2024 - 2026)**. Để Pass hoàn toàn, $t_{NW}$ trên Holdout phải $\ge 2.0$ cùng dấu.
3. Không xem xét Turnover hay Chi phí giao dịch cho đến khi Alpha được chứng minh.

## 7. Nhật Ký (Specification Log)
Sẽ được ghi chép vào `CONTRARIAN_V13_SPECIFICATION_LOG.md` sau khi chạy.
