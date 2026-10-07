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
- **Phụ (Độ nhạy):** Thặng dư lợi suất sau khi trừ `Beta × Index_Return` và trung hòa hiệu ứng Ngành (Industry neutral).

## 4. Phương Pháp Thống Kê
- **Cross-sectional Spearman IC:** Tính Rank IC từng ngày giữa feature rank và forward relative return.
- **T-Stat & Newey-West:** Tính Mean IC và t-stat của chuỗi IC theo ngày, sử dụng sai số chuẩn Newey-West (lag >= 20) để khắc phục tự tương quan do overlapping forward returns.
- **Kiểm tra song song:** Lấy mẫu không chồng lấn (non-overlapping, mỗi 20 ngày lấy 1 mẫu) để đối chiếu kết quả.
- **Phân vị (Deciles):** Đo spread lợi suất giữa `Decile thấp nhất` (giảm sâu nhất) trừ đi `Decile cao nhất`, kiểm tra tính đơn điệu của lợi suất qua 10 deciles.
- **Phân rã (Decomposition):** Xem xét IC theo từng năm và theo Market Regime (VNI tăng/giảm, VNI vol cao/thấp).
- **Kiểm soát đa so sánh:** Tập trung vào kết quả chính: `DD60, T+20, relative so với median`. Các phép thử khác chỉ mang tính chất thăm dò.

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

## 8. Thứ Tự Triển Khai
1. Commit bản plan này vào Git.
2. Xây dựng bảng Panel (Ngày × Mã), dọn dẹp dữ liệu chia tách, cổ tức, thanh khoản.
3. Chạy IC cho tính năng chính (DD60, T+20) trên 2018-2023.
4. Chạy các kiểm tra độ nhạy (Beta-neutral, Industry-neutral).
5. Chỉ mở Holdout 2024-2026 nếu thỏa mãn Tiêu Chí Quyết Định.
