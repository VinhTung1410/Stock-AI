# Quy Tắc Đăng Ký Trước Tín Hiệu Mua & Quản Trị Vị Thế Thực Chiến (Pre-Registered BUY Rules Protocol)

> **Cơ Chế Bảo Chứng Liêm Chính (Cryptographic Integrity):**  
> - **Git Commit Hash Xác Lập:** [`ff1b0cf3144b3abd1fa229fdf533fbe103c108ff`](https://github.com/VinhTung1410/Stock-AI/commit/ff1b0cf3144b3abd1fa229fdf533fbe103c108ff)  
> - **Git Annotated Tag Bảo Chứng:** `v15.0-buy-protocol`  
> - **Dấu Thời Gian Commit Thực Tế:** `2026-10-22T23:26:41+02:00` (Khóa chặt trước phiên giao dịch tiếp theo)  
> - **Mã Nguồn Baseline Được Dẫn Chiếu:** Commit `106e6c6` (Production v15.0)  
> Mọi quy tắc kích hoạt mua, định cỡ vị thế, ngưỡng cắt lỗ neo giá vào, cơ chế thoát lệnh, và ràng buộc danh mục dưới đây là **hoàn toàn xác định (deterministic), không có tham số mơ hồ**.

---

## 1. Định Nghĩa Tín Hiệu Mua Đóng Băng (Frozen Baseline BUY Signal - Commit 106e6c6)

Một cổ phiếu chỉ kích hoạt tín hiệu MUA khi và chỉ khi thỏa mãn đồng thời **toàn bộ 4 cổng điều kiện**:

1. **Cổng 1: Biên An Toàn Định Giá (Valuation MoS Gate):**
   - $\text{MoS} \ge +15,0\%$ (Biên an toàn tối thiểu so với Giá trị Hợp lý Fair Value tính theo mô hình Gordon Growth / DDM).
   - Cổng dữ liệu: `data_gate` trả về `recommendation_allowed = True` (dữ liệu tài chính không bị lỗi thời nghiêm trọng `is_stale = False`).
   - Loại trừ tuyệt đối: Cổ phiếu bị gắn cờ `RISK_TRAP` hoặc `ACCOUNTING_ANOMALY`.

2. **Cổng 2: Xác Nhận Kỹ Thuật Baseline (Technical Gate):**
   - **Vị thế giá:** Thị giá đóng cửa nằm trên đường trung bình động MA100 ngày ($P \ge MA100$).
   - **Xác nhận thanh khoản:** Khối lượng giao dịch phiên kích hoạt đạt **$V \ge MA20$** (khối lượng $\ge$ trung bình 20 phiên gần nhất, tương ứng `vol_ratio >= 1.0`).

3. **Cổng 3: Điểm Thuyết Phục Đa Chiều (Conviction Matrix):**
   - Điểm thuyết phục tổng hợp: $\text{Conviction Score} \ge 70/100$ điểm (hoặc $\text{Conviction} \ge 60/100$ nếu có Catalyst được xác nhận trong Watchlist).
   - Dựa trên ma trận chấm điểm 4 trụ cột: Piotroski F-Score $\ge 6$, MoS %, Sức mạnh kỹ thuật, và Dòng tiền tích lũy.
   - **Minh bạch Watchlist Bonus:** Khoản cộng điểm danh mục theo dõi (`watchlist_bonus = 10.0`) được bóc tách và ghi nhận riêng biệt trong trường `facts["watchlist_bonus"]` của bản ghi quyết định, đảm bảo không bị lẫn vào điểm định lượng gốc.

4. **Cổng 4: Trọng Tài Quản Trị Rủi Ro PM (Gatekeeper & Risk Arbitrations):**
   - **Falling Knife Breaker:** $P \ge 0,90 \times MA200$ (Cấm bắt dao rơi nếu giá cách MA200 quá $-10\%$).
   - **FOMO Protection:** $P \le 1,15 \times MA20$ (Cấm mua đuổi nếu giá tăng nóng vượt $+15\%$ so với MA20).
   - **Cyclical Peak Breaker:** Không mua cổ phiếu chu kỳ tại vùng đỉnh P/E cực thấp giả tạo.

---

## 2. Định Cỡ Vị Thế Cố Định (Fixed 14.28% NAV Allocation)

### 2.1. Bản chất toán học của Fixed Sizing
- **Mức chịu rủi ro danh mục ($\text{Risk\_NAV}$):** Cố định đúng **$1,0\%$ tổng NAV**.
- **Khoảng cách cắt lỗ chuẩn ($\text{Risk\_on\_Trade}$):** Được cố định ở mức **$7,0\%$**.
- **Quy mô giải ngân:**
  $$\text{Position Size} = \frac{\text{Risk\_NAV}}{\text{Risk\_on\_Trade}} = \frac{1,0\%}{7,0\%} = \mathbf{14,28\% \text{ NAV}}$$
- Do trần vị thế tối đa được khống chế ở mức $14,28\%$ NAV, trên thực tế mọi lệnh mua mới đều có **quy mô cố định duy nhất đúng bằng 14,28% NAV**.

---

## 3. Bộ Đệm Rủi Ro Chu Kỳ Thanh Toán T+2.5 (HOSE Settlement Buffer)

- **Chu kỳ thực tế:** Cổ phiếu mua tại $T+0$ chỉ khả dụng để đặt lệnh bán vào **phiên chiều ngày $T+2$** (sau 13:00).
- **Kịch bản xấu nhất (2 cây sàn liên tiếp -14%):**
  - Nếu cổ phiếu giảm sàn phiên $T+1$ ($-7\%$) và tiếp tục mất thanh khoản sàn phiên sáng $T+2$ ($-7\%$):
    $$\text{Drawdown}_{\text{worst}} = (1 - 0,07)^2 - 1 = -13,51\% \approx \mathbf{-14,0\%}$$
- **Kiểm định mức độ an toàn danh mục:**
  $$\Delta \text{NAV} = \mathbf{14,28\% \text{ NAV}} \times (-14,0\%) = \mathbf{-2,00\% \text{ NAV}}$$
- Mức tổn thất tối đa của danh mục trong kịch bản xấu nhất bị khóa thanh khoản được chặn đứng tại đúng **$-2,00\%$ NAV**, hoàn toàn không đe dọa ngưỡng an toàn tổng thể ($10\%$ Drawdown Breaker).

---

## 4. Công Thức Cắt Lỗ Cố Định Neo Theo Giá Vào (Entry-Anchored Stop Loss)

Khắc phục triệt để lỗi Stop-loss trôi (Floating Stop): Ngưỡng cắt lỗ được **cố định vĩnh viễn theo Giá vào lệnh (Entry Price)** ngay tại thời điểm khớp lệnh:

$$\text{Base Stop} = \min\left( \text{SwingLow}_{5d}, \text{Entry Price} - 1.5 \times ATR_{14} \right)$$

**Kẹp biên độ an toàn (Safety Clamping):**
$$\text{Stop Loss Price} = \max\left( \text{Entry Price} \times 0,92, \, \min\left( \text{Entry Price} \times 0,95, \, \text{Base Stop} \right) \right)$$
- **Sàn cắt lỗ tối đa:** $-8,0\%$ dưới giá vào lệnh.
- **Trần cắt lỗ tối thiểu:** $-5,0\%$ dưới giá vào lệnh.

---

## 5. Quy Tắc Thoát Lệnh Xác Định (Deterministic Exit Rules)

### 5.1. Lộ trình Chốt Lời Xác Định (Fixed Profit Targets)
- **Target 1 ($P/L \ge +15,0\%$):** Bán chốt lời chủ động **đúng 40% khối lượng vị thế**.
- **Target 2 ($P/L \ge +25,0\%$):** Bán chốt lời tiếp **đúng 30% khối lượng vị thế**.
- **Phần còn lại (đúng 30% khối lượng):** Thả nổi theo Trailing Stop động để bắt trọn xu hướng lớn.

### 5.2. Công Thức Trailing Stop Động & Khóa Hòa Vốn (Khoảng Cách Cố Định 6.0%)
| Mức sinh lời vị thế ($P/L$) | Hành động quản trị | Ngưỡng chặn bảo vệ mới | Mục tiêu kiểm soát |
| :--- | :--- | :--- | :--- |
| **$-5,0\% \ge P/L \ge -8,0\%$** | **STOP LOSS HARD** | Bán dứt khoát 100% vị thế | Chặn đứng rủi ro, bảo toàn vốn |
| **$-5,0\% < P/L < +5,0\%$** | **HOLD (Thesis Intact)** | Neo tại $\text{Stop Loss}$ ban đầu | Chờ đợi xu hướng hình thành |
| **$P/L \ge +5,0\%$** | **Nâng Stop Phòng Thủ** | $\text{Stop} = \max(\text{Stop ban đầu}, \text{Entry} \times 0,98)$ | Thu hẹp rủi ro về mức tối đa $-2\%$ |
| **$P/L \ge +12,0\%$** | **BREAKEVEN LOCK** | Dời Stop lên đúng $\text{Entry Price}$ | Biến vị thế thành giao dịch rủi ro bằng 0 (Risk-Free) |
| **$P/L \ge +15,0\%$** | **DYNAMIC TRAILING** | $\text{Trailing Stop} = \max(\text{Entry} \times 1,06, \, \mathbf{P_{\max} \times 0,94})$ | Bảo vệ tối thiểu $+6\%$ lãi, neo cách đỉnh $6,0\%$ |

*Trong đó $P_{\max}$ là thị giá đóng cửa cao nhất đạt được kể từ khi mở vị thế.*

### 5.3. Giới Hạn Thời Gian Vị Thế (Time Stop / TTL)
- Nếu sau **15 phiên giao dịch ($T+15$)** kể từ ngày mở vị thế mà cổ phiếu không tạo ra lợi nhuận ($P/L \le 0\%$) và không vi phạm ngưỡng cắt lỗ, hệ thống kích hoạt lệnh **Time Stop Exit (Tất toán hòa vốn/lỗ nhẹ)** để giải phóng sức mua cho các cơ hội mới.

### 5.4. Ràng Buộc Danh Mục & Khống Chế Ngành (Portfolio Constraints)
- **Số vị thế tối đa (Max Concurrent Positions):** Tối đa **5 vị thế** đồng thời trong danh mục.
  - Tỷ trọng cổ phiếu tối đa: $5 \times 14,28\% = \mathbf{71,4\% \text{ NAV}}$.
  - Tỷ trọng tiền mặt dự phòng tối thiểu: $\mathbf{28,6\% \text{ NAV}}$.
- **Giới Hạn Ngành (Sector Concentration Limit):** Tối đa **$30,0\%$ NAV** cho bất kỳ nhóm ngành đơn lẻ nào (ví dụ: nhóm Ngân hàng tối đa 2 vị thế $= 28,56\% \le 30,0\%$).

### 5.5. Hết Hạn Lệnh & Xử Lý Khi Mở Cửa Kịch Trần (Execution Controls)
- **Hết hạn lệnh (Order Expiration):** Tất cả các lệnh điều kiện kích hoạt mua là **Day Order (GTD phiên)**. Nếu đến phiên ATC mà các điều kiện giá và khối lượng chưa được kích hoạt, lệnh tự động hủy và phải tái đánh giá lại ở phiên tiếp theo.
- **Xử lý khi mở cửa kịch trần (Strict Ban on Ceiling Gap-ups):** Nếu cổ phiếu mở phiên ATO tăng kịch trần ($+6,9\%$ đến $+7,0\%$), **NGHIÊM CẤM MUA ĐUỔI**. Lệnh mua bị hủy tự động do rủi ro điều chỉnh kỹ thuật và bất lợi biên an toàn T+2.5.

---

## 6. Phân Định Giữa Frozen Baseline (v15.0) Và Challenger (v15.1-Candidate)

- **Baseline v15.0 (Commit `106e6c6`):** Chỉ dùng các tiêu chuẩn đã kiểm định: $P \ge MA100$, $V \ge MA20$, $\text{MoS} \ge 15\%$, $\text{Conviction} \ge 70$, Fixed Sizing $14,28\%$. Đây là hệ thống duy nhất chịu trách nhiệm về kết quả kiểm định OOS 60 phiên.
- **Challenger v15.1-Candidate (Nghiên cứu riêng biệt):** Các tiêu chí mới như MACD Histogram dương, RSI dao động $42 \le RSI \le 65$, mẫu nến đảo chiều, hay cờ `per_share_stale` được xếp vào nhánh **Challenger A/B Test**; không được tự ý gộp vào làm sai lệch hành vi của bản đóng băng.
