# Research Finding: PORTFOLIO LAYER 0 (REGIME GATE) EVALUATION

## 1. Mục tiêu (Objective)
Đo lường hiệu quả của **Tầng 0 (Macro Circuit Breaker / Regime Gate)** đối với toàn bộ danh mục cổ phiếu (Portfolio Level).
Kiểm định xem việc sử dụng đường MA200 (MA200 Hysteresis) để bật **Cash Mode** (cấm mở mua mới khi VN-Index dưới MA200) có thực sự giúp giảm Max Drawdown cho một chiến lược chủ động như kỳ vọng hay không.

## 2. Thông số Backtest (Setup)
- **Giai đoạn**: 2018-01-01 đến nay.
- **Vũ trụ cổ phiếu**: 55 mã thuộc `BROAD_MARKET_POOL`.
- **Tín hiệu giao dịch**: Chiến lược `Quant Core` (F_score=7, MoS=20, Z_score=2.5 kết hợp tín hiệu Kỹ thuật cơ bản).
- **Vốn khởi điểm**: 100,000,000 VND / mã (giả lập Equal Weight).
- **Kịch bản so sánh**:
  - `NO GATE`: Giao dịch 100% dựa vào tín hiệu cổ phiếu, không quan tâm vĩ mô.
  - `WITH REGIME GATE`: Áp dụng luật cấm mua khi VN-Index vào Downtrend (dưới MA200).

## 3. Kết quả (Results)

| Metric | NO GATE (Buy & Hold Core) | WITH REGIME GATE (Cash Mode) |
|---|---|---|
| **Tổng vốn ban đầu** | 5,500,000,000 đ | 5,500,000,000 đ |
| **Vốn cuối kỳ** | 6,962,032,470 đ | 6,873,915,658 đ |
| **CAGR (Lợi nhuận năm)** | 3.02% | 2.86% |
| **Max Drawdown (Sụt giảm)**| -27.51% | -28.59% |
| **Recovery Days (Hồi phục)**| 625 | 758 |
| **Tổng số lệnh (Trades)** | 3048 | 2398 |

## 4. Phân tích (Analysis)
Kết quả thực tế đi ngược lại hoàn toàn với giả thuyết lý thuyết ban đầu: Regime Gate làm **Max Drawdown tệ hơn** (từ -27.51% thành -28.59%), thời gian kẹp hàng lâu hơn (tăng từ 625 lên 758 ngày) và làm **giảm CAGR**.

Nguyên nhân gốc rễ:
1. **Gate làm việc hiệu quả về mặt cơ học**: Nó thực sự đã chặn được hơn 600 lệnh mua mù quáng trong Downtrend (bảo vệ nguồn vốn).
2. **Sát thủ giấu mặt - "Độ trễ" của MA200 (Lagging nature)**: 
   - MA200 phản ứng quá chậm với các cú sập (Flash Crash). Khi thị trường mới bắt đầu rơi, MA200 vẫn giữ trend tăng, khiến hệ thống không kịp bật khiên bảo vệ.
   - Khi thị trường tạo đáy và phục hồi hình chữ V (V-shape recovery - đặc sản của thị trường Việt Nam sau khủng hoảng), giá đã nảy lên rất mạnh nhưng MA200 vẫn báo Downtrend. Hệ thống bị ép "ngồi ngoài" và **bỏ lỡ hoàn toàn nhịp sóng hồi mang lại Alpha lớn nhất**.
   - Đến khi MA200 ngóc đầu lên báo hiệu Uptrend, giá cổ phiếu đã tăng một đoạn dài. Việc mua đuổi lúc này khiến hệ thống dính các nhịp điều chỉnh ngắn hạn (chỉnh đỉnh).

## 5. Kết luận & Hành động (Conclusion & Action)
- **KẾT LUẬN CHÍNH THỨC**: Bật Cash Mode tự động (Hard Gate) sử dụng MA200 **KHÔNG** bảo vệ được danh mục. Trái lại, nó tạo ra chi phí cơ hội khổng lồ do lỡ nhịp bắt đáy phục hồi của thị trường chung.
- **HÀNH ĐỘNG**: 
  - Đóng băng việc sử dụng `MA200 Hysteresis` như một "Macro Circuit Breaker" cứng rập khuôn.
  - Chuyển hướng nghiên cứu sang một bộ lọc Vĩ mô Tầng 0 nhạy bén hơn (Leading Indicators) như: **Market Breadth** (Độ rộng thị trường), **Index RSI** (Quá bán của VNI), hoặc đánh giá dòng tiền khối ngoại/tự doanh thay vì sử dụng thuần túy chỉ báo trung bình giá trễ (Trend-following).
