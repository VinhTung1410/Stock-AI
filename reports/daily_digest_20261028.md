# DAILY QUANT RESEARCH BRIEFING — 2026-10-28

### 1. BỐI CẢNH THỊ TRƯỜNG & HỆ THỐNG (REGIME CONTEXT)
- **Market Regime:** `DOWNTREND` (VN-Index: 1761.87 | MA200: 1796.41 | vs MA200: -1.92%)
- **System Freeze Version:** Logic `v15.0_frozen_20261013` | Model `v15.0_post_fix` | Commit `106e6c61af`

### 2. QUYẾT ĐỊNH CUỐI PHIÊN HÔM NAY (EOD CANONICAL T0 - 55 MÃ)
- **Phân bổ:** BUY: **0** (0.0%) | WATCH: **16** (29.1%) | REJECT: **39** (70.9%)
- **Cổng loại trừ chính (Top Rejection Gates):** `RISK_TRAP`: 39, `TECH_CONFIRMATION`: 16
- **Mã chuyển trạng thái WATCHLIST hôm nay (16 mã):** `ACB`, `BID`, `CTG`, `DGC`, `DIG`, `DXG`, `FPT`, `HDB`, `KDH`, `MBB`, `NLG`, `SHB`, `SSB`, `TPB`, `VIB`, `VNM`

### 3. ĐO LƯỜNG KẾT QUẢ ĐA KỲ (MULTI-COHORT FORWARD RETURNS ĐÁO HẠN HÔM NAY)
| Kỳ hạn đáo hạn | Cohort gốc (T0) | Nhóm | Số lượng | Exec Return TB (%) | Excess vs Universe (55 mã đều, %) |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **T+1** đáo hạn hôm nay | 2026-10-27 | **WATCH** | 16 | **+0.05%** | **-0.20%** |
| | 2026-10-27 | **REJECT** | 39 | **+0.33%** | **+0.08%** |
| **T+3** đáo hạn hôm nay | 2026-10-23 | **WATCH** | 15 | **-1.91%** | **-0.69%** |
| | 2026-10-23 | **REJECT** | 40 | **-0.96%** | **+0.26%** |
| **T+5** đáo hạn hôm nay | 2026-10-21 | **WATCH** | 15 | **-1.43%** | **-1.39%** |
| | 2026-10-21 | **REJECT** | 40 | **+0.48%** | **+0.52%** |
| **T+10** đáo hạn hôm nay | 2026-10-14 | **WATCH** | 16 | **+2.74%** | **-0.83%** |
| | 2026-10-14 | **REJECT** | 39 | **+3.92%** | **+0.34%** |

*(Benchmark của cột Excess là trung bình đều toàn bộ 55 mã Universe: Excess = Return − Mean_Universe. Do đó hiệu số Excess giữa WATCH và REJECT bằng đúng hiệu số Exec thô.)*

### 4. BẤT THƯỜNG ĐỊNH LƯỢNG (ANOMALIES) & CÂU HỎI NGHIÊN CỨU CHO CLAUDE
1. **Hiện tượng Reversed Excess Return:** Nhóm `REJECT` sinh excess return cao hơn nhóm `WATCH` tại các mốc đáo hạn hôm nay. Hãy phân tích xem đây là hiệu ứng bật nảy kỹ thuật (Beta/Oversold rally) của nhóm đầu cơ hay do nhóm cơ bản tốt bị đè giá trong Downtrend?
2. **Hiệu quả phòng vệ của cổng Kỹ thuật (`TECH_CONFIRMATION`):** Hệ thống chặn 100% lệnh MUA (BUY = 0) và đưa 16 mã vào diện theo dõi (WATCH). Kiểm tra xem kỷ luật này đã giúp tránh được bao nhiêu % thua lỗ trước đà rơi của thị trường?
3. **Hành động tiếp theo:** Với danh sách 16 mã trong Watchlist, nhóm ngành nào (Bank, Bất động sản, Sản xuất) có xác suất xác nhận ngừng rơi sớm nhất?
