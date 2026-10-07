# V12 Specification Log

## Panel Build Log
- **Symbols:** 56
- **Total Rows:** 79932 (Discovery period after purging)
- **Dedup Rule:** Keep 'last' on (symbol, time)
- **Hash:** `78c042d45b71879b6bcfbcdb2d310203d398a11ef6bd9ddb2dcf4b804a108d54`

## Run 1: Primary IC Evaluation (Discovery 2018-2023)
- **Time of run:** 2026-10-07
- **Results:**
  - Placebo test passed (FPR = 5.0%, Mean = 0.03, Std = 1.04).
  - `depth_DD60` `D -> D+20`: Mean IC = -0.007, t_NW = -0.32 (SE ~ 0.022, 95% CI ~ [-0.05, 0.04]).
  - `depth_DD60` `D -> D+1`: Mean IC = +0.035, t_NW = 5.98.
  - `depth_DD60` Quintile Spread (Q4 - Q0) = -0.10% (Q4 is deepest drawdown, meaning deepest underperformed shallowest slightly).
  - `RSI14` `D -> D+20`: Mean IC = +0.043, t_NW = 2.67.
  - `RSI14` `D+1 -> D+20` (Open(D+1) -> Close(D+20)): Mean IC = +0.044, t_NW = 2.74 (Unadjusted Momentum effect).
  - `Rev5` `D -> D+20`: Mean IC = +0.023, t_NW = 2.06.
  - `Rev5` `D+1 -> D+20` (Open(D+1) -> Close(D+20)): Mean IC = +0.024, t_NW = 2.15 (Unadjusted Momentum effect).
- **Decision:** V12-DD60 CLOSED. Không tìm thấy hiệu ứng contrarian cỡ >= 0.03 trên universe sống sót (56 mã). Khoảng tin cậy [-0.05, 0.04] chứa MDE, do đó kết luận là "không đủ power để tìm thấy hiệu ứng", tuy nhiên sự hỗ trợ từ survivorship bias đáng lẽ phải đẩy IC lên cao nhưng không xảy ra. Tín hiệu Momentum từ RSI/Rev5 là phát hiện exploratory (thăm dò) chưa qua điều chỉnh đa kiểm định (Holm m=9) và chưa trung hòa. Chuyển hướng khảo sát Momentum sang V13.
