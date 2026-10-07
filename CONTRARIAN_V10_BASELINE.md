# Research Finding: CONTRARIAN V1.0 BASELINE

## 1. Overview
- **Hypothesis**: Sử dụng chiến lược bắt đáy (Contrarian) dựa trên các tín hiệu kỹ thuật kết hợp với Regime Gate để bảo vệ vốn.
- **Status**: `COMPLETED (PHASE 1)`
- **Verdict**: 
  - **Regime Gate**: `APPROVED` (Tiếp tục sử dụng như một cơ chế phòng thủ - Tầng 0).
  - **Contrarian Signal**: `WATCH` (Chưa đủ bằng chứng để cấu thành điểm mua độc lập có Alpha).

## 2. Kết quả kiểm thử (Backtest Results)
### 2.1. Đánh giá Regime Gate (Bảo hiểm danh mục)
Chia đôi mẫu dữ liệu (Split-sample test):

| Giai đoạn | MaxDD (Buy & Hold → Cash Mode) | Lợi suất (Buy & Hold → Cash Mode) |
|-----------|--------------------------------|-----------------------------------|
| 2019-2021 | -35.7% → -14.3% | +67.9% → +60.4% |
| 2022-2026 | -40.3% → -20.3% | -15.5% → -12.3% |

**Nhận định từ Financial/Risk Expert:**
- **Chức năng**: Regime Gate hoạt động đúng với bản chất của một khoản bảo hiểm (Insurance), không phải công cụ tạo Alpha.
- **Đánh đổi (Trade-off)**: Chi phí cơ hội trong thị trường giá lên (bỏ lỡ ~7.5% trong 2019-2021) là mức giá hợp lý để cắt giảm ~50% Max Drawdown trong khủng hoảng.
- **Hạn chế**: 
  - Vẫn chịu lỗ -12.3% và MaxDD -20.3% ở nửa sau do độ trễ của tín hiệu (chỉ kích hoạt sau khi đã có nhịp giảm).
  - Tham số Hysteresis (được chốt ở ADR-026) được đưa ra *sau* khi các đợt giảm lớn đã xảy ra, tiềm ẩn rủi ro Overfitting nhẹ.
- **Mức độ bằng chứng**: Trung bình-thấp. Tính nhất quán có ở 2 nửa mẫu, nhưng thực tế chỉ đại diện cho 2 cuộc khủng hoảng lớn (Covid 2020 và đợt giảm 2022). Placebo test mới đạt ~90% (dưới ngưỡng mục tiêu 95%).

### 2.2. Đánh giá Contrarian Signal (Tín hiệu mua ngược xu hướng)
- **Kết quả**: Các tín hiệu kỹ thuật thuần túy (Technical Contrarian) không chứng minh được lợi thế xác suất rõ rệt (Alpha).
- **Quyết định**: Giữ ở radar `WATCH`. Tín hiệu bắt đáy chưa đủ điều kiện để kích hoạt lệnh BUY nếu không có thêm sự xác nhận từ Fundamentals (FA) hoặc dòng tiền.

## 3. Kết luận & Khuyến nghị triển khai (Next Steps)
1. **System Architecture**:
   - Tích hợp **Regime Gate** vào Tầng 0 (Risk Management Layer) của hệ thống.
   - Chức năng: Block/Chặn các lệnh mở mua mới (Open Long) khi thị trường bước vào Downtrend. 
   - *Lưu ý*: Gate không tự động thanh lý danh mục, các vị thế hiện tại sẽ do hệ thống Trailing Stop / Stop-loss xử lý.
2. **Next Experiments**:
   - **Thử nghiệm Tầng 0 (Portfolio Level Backtest)**: Chạy backtest trên rổ cổ phiếu thực tế, bật/tắt `enforce_regime_gate` ở cấp độ danh mục để đo lường hiệu ứng phối hợp cùng stop-loss. (Lưu ý: sẽ fix cứng `f_score=7`, `mos_pct=20`, `z_score=2.5` để cô lập biến số).
   - **Xác thực Fundamental Data Gate**: Kiểm tra số lượng cột/quý của `Finance(...).ratio()` để quyết định khả năng kiểm định cắt ngang (cross-sectional) cho Data Gate.
