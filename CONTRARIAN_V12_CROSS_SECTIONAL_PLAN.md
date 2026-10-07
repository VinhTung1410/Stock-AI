# Research Plan: CONTRARIAN V12 - Cross-Sectional Alpha

## 0. Câu Hỏi Nghiên Cứu (Cố định)
*"Trong cùng một ngày, nhóm cổ phiếu có drawdown sâu hơn (hoặc RSI thấp hơn) có relative return T+20 cao hơn phần còn lại của rổ không, sau khi kiểm soát beta, ngành và thanh khoản?"*

## 1. Universe và Dữ Liệu
- **Bộ lọc thanh khoản:** Chỉ đưa vào rổ (universe) các mã thỏa mãn ADV 20 ngày > 5 tỷ VNĐ (giúp giảm hiệu ứng bid-ask bounce và các cổ phiếu quá nhỏ không thể giao dịch).
- **Hạn chế Survivorship Bias:** Universe mặc định chỉ chứa mã còn niêm yết ở thời điểm hiện tại. Do đó kết quả sẽ bị thổi phồng ở nhóm giảm sâu. Bất kỳ IC dương nào cũng là cận trên (upper bound), và IC âm hoặc quanh 0 sẽ đáng tin cậy hơn.
- **Entry & Xử lý NaN:** 
  - Tính toán feature dựa trên `Close(D)`.
  - Vào lệnh: Cố định trước là `Open(D+1)`. (Sẽ lưu cả `Close(D+1)` để kiểm tra độ nhạy).
  - Quy tắc xử lý thiếu giá thoát: Nếu `Open(D+1)` hợp lệ nhưng `Close(D+21)` bị thiếu (NaN), không `dropna()` ngầm. Giữ nguyên và báo cáo số lượng, hoặc điền bằng giá trị gần nhất.

## 2. Features (Ít và cố định)
- `Stock_DD_60d`: Drawdown từ đỉnh 60 ngày.
- `RSI_14`: Chỉ báo RSI 14 ngày.
- `Short_term_reversal_5d`: Lợi suất 5 ngày (để cô lập hiệu ứng microstructure/bid-ask bounce).
- **Transformation:** Mỗi feature chuyển thành `rank (percentile)` từ 0 đến 1 trong cùng một ngày, để loại bỏ ảnh hưởng của biến động thị trường chung (Cross-sectional normalization).

## 3. Biến Phụ Thuộc (Dependent Variable)
- **Chính:** `Relative Return T+20` = Lợi suất T+20 của cổ phiếu - Median lợi suất T+20 của universe trong cùng ngày hôm đó.
- **Phụ (Độ nhạy):** Thặng dư lợi suất sau khi trừ `Beta × Index_Return` và trung hòa hiệu ứng Ngành (Industry neutral - dùng phương pháp xấp xỉ).

## 4. Phương Pháp Thống Kê
- **Statistical Power (Sức mạnh thống kê):** Do Universe giới hạn ở $N \approx 56$, sai số chuẩn của IC mỗi ngày là $1/\sqrt{56} \approx 0.13$. Với khoảng 75-90 điểm độc lập hiệu dụng, $SE_{mean} \approx 0.015$. Để đạt $t \ge 2$, **Minimum Detectable Effect (MDE)** cần có là $IC \ge 0.03$. Đây là một rào cản rất lớn. Nếu kết quả ra âm hoặc $t < 2$, đó là do *thiếu power* chứ chưa hẳn là bác bỏ tuyệt đối.
- **Cross-sectional Spearman IC:** Tính Rank IC từng ngày giữa feature rank và forward relative return.
- **T-Stat & Newey-West:** Tính Mean IC và t-stat của chuỗi IC theo ngày, sử dụng sai số chuẩn Newey-West (lag >= 20).
- **Phân vị (Quintiles):** Do $N=56$ quá nhỏ, chuyển từ Decile sang **Quintile** (~11 mã mỗi rổ). Đo spread lợi suất giữa Q1 (thấp nhất) trừ Q5 (cao nhất).
- **Trung hòa Ngành (Approximate):** Vì không có dữ liệu ngành Point-in-time, dùng phân loại ngành tĩnh (Static Industry Dummy: Bank, Real Estate, Others) đưa vào hồi quy. Kết quả sẽ được dán nhãn *approximate*.

## 5. Tiêu Chí Quyết Định (Pre-registered Criteria)
*(Chốt trước khi chạy code)*
- **CÓ TÍN HIỆU:** Mean IC khác 0 ở mức t-stat Newey-West $\ge 2$, cùng dấu ở $\ge 70\%$ số năm, và không biến mất sau khi trung hòa Beta và Ngành.
- **KHÔNG CÓ TÍN HIỆU:** Mean IC dao động quanh dải nhiễu (t-stat < 2), hoặc liên tục đổi dấu qua các năm.
- **KHÔNG ĐỦ BẰNG CHỨNG:** Nằm giữa hai trường hợp trên (Kết quả hợp lệ, kết luận là chưa đủ căn cứ).
- **Tín hiệu ngược:** Nếu Mean IC ÂM có ý nghĩa (Cổ phiếu giảm sâu tiếp tục giảm sâu - Momentum), đây là một phát hiện hợp lệ và được ghi nhận, không bị coi là lỗi.

## 6. Chia Dữ Liệu
- **Discovery (Train):** Chốt toàn bộ thiết kế hệ thống, lựa chọn feature, t-stat trên giai đoạn **2018 - 2023**.
- **Holdout (OOS):** Giữ riêng **2024 - 2026**. Chỉ chạy bài test một lần duy nhất lên tập OOS này sau khi mọi quyết định trên tập Discovery đã đóng băng.

## 7. Chi Phí Thực Thi & Tính Khả Thi
*(Chỉ thực hiện nếu Bước 5 kết luận CÓ TÍN HIỆU)*
- Tính toán Turnover của chiến lược Decile (mỗi bao nhiêu ngày phải đảo hàng).
- Trừ phí giao dịch, thuế, trượt giá (bid-ask spread), thanh khoản.
- Không thực hiện Long/Short (vì Việt Nam không cho bán khống). Báo cáo sẽ đo lường thực thi cho chân Long (Ví dụ: Mua Decile 10).

## 5. Tiêu Chí Quyết Định (Pre-registered Criteria & Thresholds)
*(Chốt trước khi chạy code)*

**5.1. Ngưỡng PASS cho Primary Feature (DD60, T+20, Baseline Median)**
- **Mean IC:** Phải khác 0 ở mức ý nghĩa thống kê với $t \ge 2.0$ (dùng sai số chuẩn Newey-West với lag $\ge 19$).
- **Độ ổn định:** Cùng dấu ở $\ge 5/6$ năm trong tập Discovery (2018-2023).
- **Trung hòa (Neutralization Gate):** Kết quả (t-stat $\ge 2.0$) không được biến mất sau khi kiểm soát Beta, Ngành, và Size/Thanh khoản.
  - *Quy tắc:* Nếu Raw PASS nhưng Residual FAIL $\rightarrow$ Lợi thế do Beta/Ngành/Size chứ không phải do DD60. Bác bỏ giả thuyết.
  - *Quy tắc:* Nếu Raw FAIL nhưng Residual PASS $\rightarrow$ Chưa đủ kết luận, cần nghiên cứu sâu hơn về hiệu ứng che khuất.

**5.2. Ngưỡng cho Secondary Features (RSI14, Rev5)**
- Do tương quan mạnh với DD60, RSI14 không được coi là bằng chứng độc lập. Các feature phụ này chịu tiêu chuẩn kiểm soát đa so sánh (ví dụ hiệu chỉnh Holm hoặc yêu cầu t-stat $\ge 2.5$).

**5.3. Tiêu chí D $\rightarrow$ D+1 Decomposition (Microstructure)**
- Kết quả IC bắt buộc báo cáo thành 3 cột: `D -> D+20`, `D -> D+1`, và `D+1 -> D+20`.
- *Quy tắc:* Nếu phần lớn IC đến từ đoạn `D -> D+1` và đoạn `D+1 -> D+20` không có ý nghĩa thống kê $\rightarrow$ Hiệu ứng bị chi phối bởi Microstructure/Bid-ask bounce. Không thể thực thi giao dịch. Bác bỏ hệ thống.

**5.4. Tiêu chí Semi-Holdout (2024-2026)**
- Gọi đây là **Semi-Holdout** vì dữ liệu thị trường và cổ phiếu giai đoạn này đã bị nhìn thấy (dùng để mô tả) trong V11. Do đó, giá trị xác nhận của tập này yếu hơn một Holdout hoàn toàn mù.
- **Ngưỡng PASS OOS:** Mean IC phải cùng dấu với Discovery, $t \ge 1.645$ (một phía), và Effect Size (Mean IC) không sụt giảm quá $50\%$ so với Discovery.
- Nếu OOS yếu (t-stat thấp nhưng vẫn cùng chiều): Báo cáo "Chưa đủ kết luận", không gán nhãn thất bại hay thành công.

## 6. Chia Dữ Liệu & Nhật Ký
- **Discovery (Train):** 2018 - 2023.
- **Semi-Holdout (OOS):** 2024 - 2026.
- **Hash Data:** Cố định phiên bản dữ liệu (hash của Panel) trước khi chạy Primary IC để chống data-snooping. Hash hiện tại: `78c042d45b71879b6bcfbcdb2d310203d398a11ef6bd9ddb2dcf4b804a108d54` (Đã chuẩn hóa time và dedup triệt để).
- **Specification Log:** Ghi chép nhật ký mọi biến thể đã chạy, kể cả những cấu hình bị bỏ, để ngăn chặn P-hacking.

## 7. Thứ Tự Triển Khai Thực Tế

**GIAI ĐOẠN 1: DATA AUDIT (DỪNG SỚM NẾU KHÔNG ĐẠT)**
1. Audit Schema: Kiểm tra Giá điều chỉnh (Adjusted Close), Sự kiện doanh nghiệp (Corporate Actions), tính Point-in-time của Phân loại Ngành.
2. Cổng kiểm duyệt (Gate): Nếu dữ liệu không phải Adjusted Price, thiếu Volume/ADV, hoặc ngành không PIT $\rightarrow$ **KẾT LUẬN: V12 CHƯA CHẠY ĐƯỢC.** Phải sửa Data Pipeline, tuyệt đối không dùng proxy hạ chuẩn.
3. Audit Panel Integrity: Đếm số lượng mã (N) theo từng năm để định lượng Survivorship Bias. Kiểm tra xử lý ngày đình chỉ giao dịch (tránh giá lặp tạo return 0 giả).

**GIAI ĐOẠN 2: PRIMARY IC EVALUATION (DISCOVERY)**
4. Tính toán Feature: DD60, RSI14, Rev5.
5. Chạy Phân rã Microstructure: Báo cáo IC cho `D->D+20`, `D->D+1`, `D+1->D+20`.
6. Chạy Thống kê: Deciles (kiểm tra tính đơn điệu), Rank IC theo ngày, t-stat Newey-West.
7. Trung hòa: Loại bỏ Beta, Ngành, Size/Thanh khoản. Đánh giá lại IC trên phần dư (Residuals).
8. Quyết định (Discovery Decision): Áp dụng Tiêu chí 5.1. Nếu FAIL $\rightarrow$ DỪNG. Nếu PASS $\rightarrow$ Chuyển sang Giai đoạn 3.

**GIAI ĐOẠN 3: SEMI-HOLDOUT VALIDATION**
9. Áp dụng quy tắc lên tập 2024-2026. Đánh giá theo tiêu chí 5.4.
10. Tổng hợp ước lượng cho toàn bộ giai đoạn Pooled 2018-2026.
