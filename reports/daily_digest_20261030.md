# DAILY QUANT RESEARCH BRIEFING — 2026-10-30

### 1. BỐI CẢNH THỊ TRƯỜNG & HỆ THỐNG (REGIME CONTEXT)
- **Market Regime:** `DOWNTREND` (VN-Index: 1741.62 | MA200: 1795.06 | vs MA200: -2.98%)
- **System Freeze Version:** Logic `v15.0_frozen_20261013` | Model `v15.0_post_fix` | Commit `106e6c61af`

### 2. QUYẾT ĐỊNH CUỐI PHIÊN HÔM NAY (EOD CANONICAL T0 - 55 MÃ)
- **Phân bổ:** BUY: **0** (0.0%) | WATCH: **17** (30.9%) | REJECT: **38** (69.1%)
- **Cổng loại trừ chính (Top Rejection Gates):** `RISK_TRAP`: 38, `TECH_CONFIRMATION`: 17
- **Danh mục WATCHLIST tại EOD (17 mã):** `ACB`, `BID`, `CTG`, `DGC`, `DIG`, `DXG`, `FPT`, `HDB`, `KDH`, `MBB`, `NLG`, `SHB`, `SSB`, `TCB`, `TPB`, `VIB`, `VNM`
- **Biến động trạng thái (so với 2026-10-29):** [+ Thêm mới: `BID`]

### 3. ĐO LƯỜNG KẾT QUẢ ĐA KỲ (MULTI-COHORT FORWARD RETURNS ĐÁO HẠN HÔM NAY)
| Kỳ hạn | Cohort T0 | Nhóm | N | Exec Mean (%) | Median (%) | Trimmed 10% (%) | Win Rate (%) | Excess vs Universe (%) |
| :--- | :---: | :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **T+1** đáo hạn hôm nay | 2026-10-29 | **WATCH** | 16 | **-1.30%** | -1.20% | -1.28% | 12.5% | **-0.30%** |
| | 2026-10-29 | **REJECT** | 38 | **-0.87%** | -0.98% | -0.77% | 26.3% | **+0.13%** |
| | 2026-10-29 | **Universe (55 mã)** | 54 | -1.00% | -1.08% | -0.92% | 22.2% | 0.00% |
| | 2026-10-29 | **Tiền mặt (BUY=0)** | — | **0.00%** | 0.00% | 0.00% | — | *Phòng vệ vs Universe: +1.00%* |
| **T+3** đáo hạn hôm nay | 2026-10-27 | **WATCH** | 16 | **-1.79%** | -1.41% | -1.72% | 12.5% | **+0.46%** |
| | 2026-10-27 | **REJECT** | 38 | **-2.44%** | -2.10% | -2.24% | 7.9% | **-0.19%** |
| | 2026-10-27 | **Universe (55 mã)** | 54 | -2.24% | -1.81% | -2.09% | 9.3% | 0.00% |
| | 2026-10-27 | **Tiền mặt (BUY=0)** | — | **0.00%** | 0.00% | 0.00% | — | *Phòng vệ vs Universe: +2.24%* |
| **T+5** đáo hạn hôm nay | 2026-10-23 | **WATCH** | 15 | **-3.78%** | -2.69% | -3.75% | 6.7% | **-0.08%** |
| | 2026-10-23 | **REJECT** | 39 | **-3.67%** | -3.64% | -3.60% | 10.3% | **+0.03%** |
| | 2026-10-23 | **Universe (55 mã)** | 54 | -3.70% | -3.55% | -3.63% | 9.3% | 0.00% |
| | 2026-10-23 | **Tiền mặt (BUY=0)** | — | **0.00%** | 0.00% | 0.00% | — | *Phòng vệ vs Universe: +3.70%* |
| **T+10** đáo hạn hôm nay | 2026-10-16 | **WATCH** | 15 | **-1.59%** | -1.14% | -1.40% | 26.7% | **-1.42%** |
| | 2026-10-16 | **REJECT** | 40 | **+0.36%** | -0.65% | -0.01% | 42.5% | **+0.53%** |
| | 2026-10-16 | **Universe (55 mã)** | 55 | -0.17% | -0.79% | -0.46% | 38.2% | 0.00% |
| | 2026-10-16 | **Tiền mặt (BUY=0)** | — | **0.00%** | 0.00% | 0.00% | — | *Phòng vệ vs Universe: +0.17%* |

> **Quy ước & Chú thích kỹ thuật:**
> - **Định nghĩa Exec Return:** `(Close_T+h − Open_T+1) / Open_T+1 × 100%`. Vào lệnh tại giá Mở cửa ngày T+1, đóng vị thế tại giá Đóng cửa ngày T+h. Chưa trừ thuế & phí giao dịch ước tính (0.40%).
> - **Universe Benchmark:** Tính trung bình đều (Equal-Weighted, 55 mã), kèm Median và Trimmed Mean (cắt 10% hai đầu). Khác với VN-Index vốn được tính theo trọng số vốn hóa (Market-cap Weighted).
> - **Đo lường Cổng an toàn:** Hiệu quả của cổng chặn Mua (BUY=0) được đo bằng lợi suất Tiền mặt (0.00%) so với đà giảm của Universe/WATCH.

### 4. BẤT THƯỜNG ĐỊNH LƯỢNG (ANOMALIES) & CÂU HỎI NGHIÊN CỨU CHO CLAUDE
| Kỳ hạn | Diff Mean (W − R) | Diff Median | Bootstrap SE | 95% CI Bootstrap | Trạng thái Thống kê |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **T+1** (2026-10-29) | **-0.43%** | -0.22% | 0.44% | [-1.29%, +0.44%] | Trong biên nhiễu (|Δ| ≤ 2×SE) |
| **T+3** (2026-10-27) | **+0.65%** | +0.70% | 0.65% | [-0.64%, +1.90%] | Trong biên nhiễu (|Δ| ≤ 2×SE) |
| **T+5** (2026-10-23) | **-0.11%** | +0.95% | 0.86% | [-1.82%, +1.46%] | Trong biên nhiễu (|Δ| ≤ 2×SE) |
| **T+10** (2026-10-16) | **-1.95%** | -0.49% | 1.20% | [-4.37%, +0.32%] | Trong biên nhiễu (|Δ| ≤ 2×SE) |

*(Ghi chú phương pháp luận: Các kỳ hạn T+1, T+3, T+5, T+10 cùng kết thúc phiên hôm nay nên là các cửa sổ thời gian chồng lấn (overlapping windows), không được coi là các quan sát độc lập. Trạng thái 'Reversed' chỉ có ý nghĩa khi dấu chênh lệch nhất quán trên các khối thời gian rời nhau.)*

1. **Độ lệch trong biên nhiễu:** Toàn bộ chênh lệch giữa WATCH và REJECT tại các mốc đáo hạn hôm nay đều nằm trong biên $2\times SE$ (tương thích với giả thuyết không có sự khác biệt có ý nghĩa thống kê trên mẫu đơn lẻ). Cần tiếp tục theo dõi qua các chuỗi cohort rời nhau.
2. **Đánh giá hiệu quả phòng vệ Tiền mặt (BUY = 0):** Trong Downtrend, hệ thống nắm giữ 100% tiền mặt. Đối chiếu mức lợi suất của Tiền mặt (0.0%) so với đà giảm của Universe để đánh giá mức độ bảo toàn vốn qua từng chu kỳ.
3. **Hành động tiếp theo:** Với danh sách 17 mã trong Watchlist tại EOD, nhóm ngành nào (Bank, Bất động sản, Sản xuất) có xác suất xác nhận ngừng rơi sớm nhất?
