# Research Plan: CONTRARIAN V11 - Market State Discovery

## 1. Triết Lý Nghiên Cứu (Research Philosophy)
V11 thay đổi hoàn toàn tư duy tiếp cận: **Không tìm một indicator khác thay thế MA200 để làm Gate 0.**
Nhiệm vụ của V11 là trả lời câu hỏi cốt lõi:
> *"Có tồn tại một observable market state (trạng thái thị trường quan sát được) có conditional predictive information đối với contrarian opportunity hay không?"*

Market State Classifier phải chứng minh được giá trị thông tin (Information Value) trên dữ liệu trước, rồi mới được quyền trở thành **Candidate Gate 0**. Nếu không tìm thấy statistical justification, V11 sẽ kết luận "Bỏ Gate 0".

## 2. Quy trình Nghiên Cứu Chống Overfitting (Strict Pipeline)
Để tránh vòng lặp "Parameter Mining" (tuning ngưỡng 15% -> 10% -> 8% trên cùng 1 dataset), V11 áp dụng pipeline khép kín:

```text
Frozen Historical Data
        │
        ▼
Market Observable Dataset (Vector)
        │
        ▼
Conditional Forward Return Study (Discovery Data)
        │
        ▼
Statistical Evidence (Effect size, Hit rate, MAE/MFE)
        │
        ▼
Hypothesis & Threshold Frozen
        │
        ▼
OUT-OF-SAMPLE / HOLDOUT VALIDATION
        │
        ▼
Candidate Gate 0
```

## 3. Vector Market State Ưu Tiên (Observables)
Không chọn một biến đơn lẻ, V11 test một vector các quan sát đo lường mức độ stress của thị trường:

| Nhóm | Biến cần test (Observable) | Mức độ ưu tiên |
|------|---------------------------|----------------|
| **Breadth** | % cổ phiếu > MA20 | ⭐⭐⭐⭐⭐ |
| **Breadth** | % cổ phiếu > MA50 | ⭐⭐⭐⭐⭐ |
| **Breadth** | % cổ phiếu > MA200 | ⭐⭐⭐⭐ |
| **Volatility** | VNIndex ATR / ATR baseline | ⭐⭐⭐⭐⭐ |
| **Volatility** | Realized volatility | ⭐⭐⭐⭐ |
| **Drawdown** | Khoảng cách VNIndex đến đỉnh 20D/50D | ⭐⭐⭐⭐ |
| **Momentum** | Lợi suất VNIndex 5D/20D | ⭐⭐⭐⭐ |
| **Liquidity** | Market-wide turnover shock | ⭐⭐⭐⭐ |
| **Foreign flow** | Net foreign value | ⭐⭐⭐ |

*Ghi chú: Sẽ bắt đầu discovery với Breadth + Volatility + Drawdown.*

## 4. Discovery Study (v11_forward_return_study.py)
Nghiên cứu đầu tiên **TUYỆT ĐỐI KHÔNG** chứa bất kỳ quy tắc Buy/Sell, RSI, MoS, F-Score, hay Position Sizing nào.

**Mục tiêu:** Ánh xạ từ `Observable State` → `Forward Outcome` của toàn thị trường.
- Chia state thành các quantiles/buckets (Ví dụ: Breadth < 10%, 10-20%, 20-40%, 40-60%, > 60%).
- Đo lường tại các mốc `T+1`, `T+5`, `T+20`, `T+60`.
- Các metric:
  - `P(Return > 0)` (Hit rate)
  - `Median Return`, `Mean Return`
  - `MAE (Maximum Adverse Excursion)`
  - `MFE (Maximum Favorable Excursion)`

## 5. Kết Luận V11: Bằng Chứng Phủ Định (Negative Findings)
Sau quá trình đi qua Discovery -> OOS Validation -> Episode-level Audit, hệ thống V11 đã được đóng băng với các kết luận âm tính có giá trị cao, được xác nhận thông qua số liệu:

### A. Gate 0 (Khủng hoảng thị trường)
- **Gate 0.A (Extreme Crash: Index DD < -15% & ATR > 1.5x):** 
  - Điều kiện `ATR > 1.5x` là **dư thừa (redundant)**. Trong 30 ngày thị trường rơi > -15%, có tới 27 ngày (90%) ATR tự động bung rộng cơ học. 
  - Bản thân quy tắc Naive (Index DD < -15%) **chưa được kiểm chứng độ hiệu quả**. Trong suốt 2018-2026, nó chỉ tạo ra N ≈ 3 episodes độc lập (3/2020, 10/2022, 4/2025). Giao dịch 3 lần trong 8 năm không thể tạo thành một hệ thống định lượng (Trading System) có sức mạnh thống kê.
- **Gate 0.B (Silent Bleed: Index DD < -8% & ATR < 1.0x):**
  - **Không đủ dữ liệu.** Bộ lọc này tạo ra một ô mẫu N=20 ngày trong 6 năm (~1 episode). Bất kỳ kết quả nào ở đây đều không có ý nghĩa thống kê.

### B. Tầng 1 (Stock DD < -25%)
- **Không đủ bằng chứng:** Trong 7 đợt sập (Episodes), nhóm cổ phiếu giảm cực sâu (DD < -25%) thắng nhóm cổ phiếu giảm nhẹ (DD >= -25%) ở 4/7 đợt (p-value ~ 0.50). Kết quả này cho thấy không có bằng chứng thống kê nào để kết luận Tầng 1 tạo ra alpha, thay vì khẳng định "chắc chắn không có alpha".
- Giả thuyết Rủi ro High Beta: Ở đợt sập 10/2022, nhóm này tạo ra MAE -21.57%. Dù chỉ là 1 episode (giả thuyết, chưa kiểm chứng đầy đủ), nó đưa ra cảnh báo về việc cổ phiếu giảm sâu có thể tiếp tục khuyếch đại đà giảm của thị trường chung.

### C. Bias Cảnh Báo (Survivorship Bias)
- Hạn chế của Universe: Tập dữ liệu gốc chỉ bao gồm các mã còn niêm yết ở hiện tại (2026). Các cổ phiếu giảm cực sâu rồi phá sản/hủy niêm yết hoàn toàn vắng mặt trong mẫu. Do đó, kết quả lợi suất dương của tập cổ phiếu "giảm sâu" chắc chắn bị thổi phồng, dù chúng ta **chưa định lượng được mức độ thổi phồng** là bao nhiêu.
- Execution Realism: Mua ở Open(D+1) trong hoảng loạn đối diện rủi ro mở trần (trắng bên bán - không khớp) hoặc mở sàn (khớp lệnh nhưng kẹt T+2.5).

## 6. Định Hướng Mới (Pivot)
Dừng toàn bộ việc xây dựng Transaction Realism / Scale-in / Engine cho V11 (Timing-based Contrarian). 

**Hướng đi tiếp theo:** Chuyển sang nghiên cứu **Cross-sectional Relative Return** ở cấp độ ngày. 
Thay vì cố gắng "timing" khủng hoảng với N=3 episodes (Time-series), hãy đo lường Information Coefficient (IC) của các đặc trưng cổ phiếu (ví dụ: Stock Drawdown, RSI) để xem chúng có dự báo được lợi suất vượt trội (Relative Return) của cổ phiếu so với nhóm ngành / Index trên hàng nghìn ngày giao dịch liên tiếp hay không. Đây là hướng đi có N đủ lớn để sức mạnh thống kê phát huy tác dụng.
