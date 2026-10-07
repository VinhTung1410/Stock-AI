# V13 Momentum Specification Log

## Discovery Phase (2018-02-23 to 2023-11-30)
- **Hash:** `78c042d45b71879b6bcfbcdb2d310203d398a11ef6bd9ddb2dcf4b804a108d54` (Same as V12, 56 symbols, deduped)
- **Feature:** RSI14 (Rank Standardized)
- **Controls:** Beta 60d (Ranked), ADV 20d (Ranked), Industry Dummies (Bank, Real_Estate_Sec)

### Predictions vs Reality
- **Prediction:** λ_RSI sẽ giảm ~45%, xác suất t_NW >= 2.5 chỉ 35%.
- **Reality:** λ_RSI không hề giảm mà TĂNG NHẸ (+4.5%) sau khi Neutralize! t_NW đạt 2.74. 

### Pre-Registered Criteria Audit
1. **λ_RSI (R_tradable, đủ controls) > 0:** `0.013979` -> PASS
2. **t_NW ≥ 2.5:** `2.74` -> PASS
3. **Cùng dấu ≥ 5/6 năm:** `5/6` -> PASS
4. **Continuation (λ_tradable ≥ 50% λ_info):** `0.0139` vs `0.0137` (~100%) -> PASS

### Diagnostics
- **R_tradable (Raw, No Controls):** λ = 0.0133 (t = 2.35)
- **R_tradable (Residual, With Controls):** λ = 0.0139 (t = 2.74)
- *Conclusion:* Hiệu ứng Momentum không những độc lập với Beta, Industry, và Size, mà các biến kiểm soát này còn giúp loại bỏ nhiễu, làm TĂNG độ sắc nét của tín hiệu.

### Quyết định Discovery Gate
**PASS.** Tín hiệu Residual Momentum của RSI14 chính thức vượt qua Discovery Gate. Được phép tiến vào vòng chạy **MỘT LẦN DUY NHẤT** trên tập Semi-Holdout OOS (2024-2026).

---

## OOS Semi-Holdout (2024-01-02 to 2026-10-07)
Chỉ chạy một lần duy nhất với code/ruleset đã đóng băng từ vòng Discovery.

### Results
- **λ_RSI (Residual):** `0.004754`
- **t_NW:** `0.62`
- **λ_OOS / λ_Disc:** `0.00475 / 0.01397` = `34.1%`
- **Cùng dấu (Same Sign):** Có (Cả hai đều dương).

### Diagnostics
- **R_tradable (Raw, No Controls):** λ = 0.0087 (t = 1.01)
- **R_tradable (Residual, With Controls):** λ = 0.0047 (t = 0.62)
- *Reduction:* Khác với tập Discovery, khi áp dụng sang OOS, các biến Controls đã kéo tụt hiệu ứng Momentum xuống tới `45.6%`. 

### Quyết định OOS
**INCONCLUSIVE.** (Cùng dấu nhưng dưới ngưỡng).
Hiệu ứng Momentum không bị đảo chiều (không phải Failure), nhưng đã sụp đổ về mặt cường độ (chỉ còn 1/3) và mất hoàn toàn ý nghĩa thống kê ($t < 2.0$). 
Không đủ bằng chứng để xác nhận đây là một Alpha bền vững, đặc biệt trên tập dữ liệu vốn đã được thiên vị cho Momentum (Survivorship Bias).
