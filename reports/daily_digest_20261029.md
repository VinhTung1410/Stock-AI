# DAILY QUANT RESEARCH BRIEFING — 2026-10-29

### 1. BỐI CẢNH THỊ TRƯỜNG & HỆ THỐNG (REGIME CONTEXT)
- **Market Regime:** `DOWNTREND` (VN-Index: 1755.61 | MA200: 1795.63 | vs MA200: -2.23%)
- **System Freeze Version:** Logic `v15.0_frozen_20261013` | Model `v15.0_post_fix` | Commit `106e6c61af`

### 2. QUYẾT ĐỊNH CUỐI PHIÊN HÔM NAY (EOD CANONICAL T0 - 55 MÃ)
- **Phân bổ:** BUY: **0** (0.0%) | WATCH: **16** (29.1%) | REJECT: **39** (70.9%)
- **Cổng loại trừ chính (Top Rejection Gates):** `RISK_TRAP`: 39, `TECH_CONFIRMATION`: 16
- **Danh mục WATCHLIST tại EOD (16 mã):** `ACB`, `CTG`, `DGC`, `DIG`, `DXG`, `FPT`, `HDB`, `KDH`, `MBB`, `NLG`, `SHB`, `SSB`, `TCB`, `TPB`, `VIB`, `VNM`
- **Biến động trạng thái (so với 2026-10-28):** [+ Thêm mới: `TCB`] [- Loại bỏ: `BID`]

### 3. ĐO LƯỜNG KẾT QUẢ ĐA KỲ (MULTI-COHORT FORWARD RETURNS ĐÁO HẠN HÔM NAY)
| Kỳ hạn | Cohort T0 | Nhóm | N | Exec Mean (%) | Median (%) | Trimmed 10% (%) | Win Rate (%) | Excess vs Universe (%) |
| :--- | :---: | :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **T+1** đáo hạn hôm nay | 2026-10-28 | **WATCH** | 16 | **-0.80%** | -0.68% | -0.76% | 12.5% | **+0.46%** |
| | 2026-10-28 | **REJECT** | 39 | **-1.45%** | -1.32% | -1.41% | 20.5% | **-0.19%** |
| | 2026-10-28 | **Universe (55 mã)** | 55 | -1.26% | -1.20% | -1.18% | 18.2% | 0.00% |
| | 2026-10-28 | **Tiền mặt (BUY=0)** | — | **0.00%** | 0.00% | 0.00% | — | *Phòng vệ vs Universe: +1.26%* |
| **T+3** đáo hạn hôm nay | 2026-10-26 | **WATCH** | 15 | **-0.62%** | +0.00% | -0.56% | 46.7% | **+0.65%** |
| | 2026-10-26 | **REJECT** | 40 | **-1.51%** | -1.33% | -1.48% | 27.5% | **-0.24%** |
| | 2026-10-26 | **Universe (55 mã)** | 55 | -1.26% | -1.11% | -1.22% | 32.7% | 0.00% |
| | 2026-10-26 | **Tiền mặt (BUY=0)** | — | **0.00%** | 0.00% | 0.00% | — | *Phòng vệ vs Universe: +1.26%* |
| **T+5** đáo hạn hôm nay | 2026-10-22 | **WATCH** | 15 | **-1.36%** | -0.51% | -1.26% | 26.7% | **-0.05%** |
| | 2026-10-22 | **REJECT** | 40 | **-1.29%** | -1.56% | -1.63% | 25.0% | **+0.02%** |
| | 2026-10-22 | **Universe (55 mã)** | 55 | -1.31% | -1.49% | -1.52% | 25.5% | 0.00% |
| | 2026-10-22 | **Tiền mặt (BUY=0)** | — | **0.00%** | 0.00% | 0.00% | — | *Phòng vệ vs Universe: +1.31%* |
| **T+10** đáo hạn hôm nay | 2026-10-15 | **WATCH** | 16 | **+1.03%** | +1.14% | +1.28% | 75.0% | **-1.03%** |
| | 2026-10-15 | **REJECT** | 39 | **+2.49%** | +1.94% | +2.16% | 69.2% | **+0.42%** |
| | 2026-10-15 | **Universe (55 mã)** | 55 | +2.06% | +1.92% | +1.81% | 70.9% | 0.00% |
| | 2026-10-15 | **Tiền mặt (BUY=0)** | — | **0.00%** | 0.00% | 0.00% | — | *Phòng vệ vs Universe: -2.06%* |

> **Quy ước & Chú thích kỹ thuật:**
> - **Định nghĩa Exec Return:** `(Close_T+h − Open_T+1) / Open_T+1 × 100%`. Vào lệnh tại giá Mở cửa ngày T+1, đóng vị thế tại giá Đóng cửa ngày T+h. Chưa trừ thuế & phí giao dịch ước tính (0.40%).
> - **Universe Benchmark:** Tính trung bình đều (Equal-Weighted, 55 mã), kèm Median và Trimmed Mean (cắt 10% hai đầu). Khác với VN-Index vốn được tính theo trọng số vốn hóa (Market-cap Weighted).
> - **Đo lường Cổng an toàn:** Hiệu quả của cổng chặn Mua (BUY=0) được đo bằng lợi suất Tiền mặt (0.00%) so với đà giảm của Universe/WATCH.

### 4. BẤT THƯỜNG ĐỊNH LƯỢNG (ANOMALIES) & CÂU HỎI NGHIÊN CỨU CHO CLAUDE
| Kỳ hạn | Diff Mean (W − R) | Diff Median | Bootstrap SE | 95% CI Bootstrap | Trạng thái Thống kê |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **T+1** (2026-10-28) | **+0.64%** | +0.64% | 0.37% | [-0.09%, +1.38%] | Trong biên nhiễu (|Δ| ≤ 2×SE) |
| **T+3** (2026-10-26) | **+0.89%** | +1.33% | 0.81% | [-0.73%, +2.45%] | Trong biên nhiễu (|Δ| ≤ 2×SE) |
| **T+5** (2026-10-22) | **-0.07%** | +1.06% | 1.05% | [-2.22%, +1.91%] | Trong biên nhiễu (|Δ| ≤ 2×SE) |
| **T+10** (2026-10-15) | **-1.45%** | -0.80% | 1.45% | [-4.60%, +1.21%] | Trong biên nhiễu (|Δ| ≤ 2×SE) |

*(Ghi chú phương pháp luận: Các kỳ hạn T+1, T+3, T+5, T+10 cùng kết thúc phiên hôm nay nên là các cửa sổ thời gian chồng lấn (overlapping windows), không được coi là các quan sát độc lập. Trạng thái 'Reversed' chỉ có ý nghĩa khi dấu chênh lệch nhất quán trên các khối thời gian rời nhau.)*

1. **Độ lệch trong biên nhiễu:** Toàn bộ chênh lệch giữa WATCH và REJECT tại các mốc đáo hạn hôm nay đều nằm trong biên $2\times SE$ (tương thích với giả thuyết không có sự khác biệt có ý nghĩa thống kê trên mẫu đơn lẻ). Cần tiếp tục theo dõi qua các chuỗi cohort rời nhau.
2. **Đánh giá hiệu quả phòng vệ Tiền mặt (BUY = 0):** Trong Downtrend, hệ thống nắm giữ 100% tiền mặt. Đối chiếu mức lợi suất của Tiền mặt (0.0%) so với đà giảm của Universe để đánh giá mức độ bảo toàn vốn qua từng chu kỳ.
3. **Hành động tiếp theo:** Với danh sách 16 mã trong Watchlist tại EOD, nhóm ngành nào (Bank, Bất động sản, Sản xuất) có xác suất xác nhận ngừng rơi sớm nhất?
