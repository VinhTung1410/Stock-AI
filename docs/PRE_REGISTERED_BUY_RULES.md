# Quy Tắc Đăng Ký Trước Tín Hiệu Mua & Quản Trị Vị Thế Thực Chiến (Pre-Registered > **Cơ Chế Bảo Chứng & Nhật Ký Phát Hành Công Khai (Public Audit Trail):**  
> - **Dòng Thời Gian Đóng Băng & Bằng Chứng Replay Zero-Diff (Audit Timeline & Replay Evidence):**
>   - **Phiên 13/10/2026:** Vận hành trên commit `734893f3452663aec02debe52c314fffae22fe97` (`734893f`, 262 bản ghi quyết định).
>   - **Phiên 14/10/2026:** Vận hành trên commit `8d353f522150b8ce2551554bd5e32261c29db5c8` (`8d353f5`, 201 bản ghi quyết định).
>   - **Commit Đóng Băng `106e6c6`:** Được hoàn tất và lưu vào Git vào lúc `2026-10-14T20:20:38Z`. Do đó, phiên giao dịch đầu tiên vận hành chính thức trên commit `106e6c6` mang nhãn `logic_version = v15.0_frozen_20261013` là **ngày 15/10/2026** (200 bản ghi quyết định).
>   - **Chứng Minh Replay Zero-Diff:** Bài kiểm toán tại [`tests/test_golden_zero_diff_replay.py`](file:///c:/Users/Window/Desktop/Stock%20-%20learning/tests/test_golden_zero_diff_replay.py) và bảng kết quả [`replay_diff_summary.csv`](file:///c:/Users/Window/Desktop/Stock%20-%20learning/replay_diff_summary.csv) xác nhận: Toàn bộ 55/55 mã cổ phiếu canonical có **độ lệch bằng 0 (Zero-Diff)** trên 100% các tiêu chí `decision` (BUY/WATCH/REJECT), `primary_rejection_gate`, `mos_pct`, và `conviction` giữa `734893f`, `8d353f5` và `106e6c6`. Do đó, tính nhất quán định lượng của kỷ nguyên v15.0 được bảo đảm liền mạch từ 13/10, và chính thức mang định danh commit `106e6c6` từ 15/10.
>   - **Tag đóng băng v15.0 (`v15.0_frozen_20261013`):** Tag object `f958ff2b9ec09e8636c18045e18eb6c9bec8f505` (`f958ff2`), được tạo vào lúc **2026-10-20T08:31:24Z** bởi `VinhTung1410`. Việc gắn tag sau ngày 15/10 phản ánh quy trình nghiệm thu độc lập, được bảo chứng bằng commit hash `106e6c6`.
>   - **Tag giao thức mua v15.0 (`v15.0-buy-protocol`):** Tag object `ce421ba1d7d8793c011745a9ec09d17613102891` (`ce421ba`), được tạo local vào lúc `2026-10-22T21:27:14Z` bởi `VinhTung1410` tại commit `c304749`.
>   - **Thời Điểm Đẩy Máy Chủ Thực Tế (Remote Push Timestamp):** Theo nhật ký push, tag `v15.0-buy-protocol` (`[new tag]`) và các commit `ff1b0cf`, `c304749`, `784e5c9` được đẩy lên remote `origin/dev` trong đợt đẩy lúc **2026-10-24T08:55:40Z**.
>   - **Điểm Neo Thận Trọng Cho Đăng Ký Trước (Conservative Pre-Registration Anchor):** Được xác định chính thức là **2026-10-24 08:55:40Z**. Điểm neo này vẫn đảm bảo tính độc lập tuyệt đối và **diễn ra trước bất kỳ tín hiệu MUA nào** (vì xuyên suốt từ ngày bắt đầu OOS đến hết phiên 23/10 hệ thống hoàn toàn chưa phát sinh bất kỳ lệnh MUA nào, 100% đều là WATCH hoặc REJECT).
>   - **Tag kiểm toán v15.0 (`v15.0-buy-protocol-audited`):** Tag object `b2e964d8ba632e1a05f0312c813005a17227e44e` (`b2e964d`), được tạo tại commit `784e5c9` đồng thời trong đợt đối soát 24/10.
> - **Mã Nguồn Baseline Được Dẫn Chiếu:** Commit `106e6c6` (Production v15.0).
> Mọi quy tắc kích hoạt mua, định cỡ vị thế, ngưỡng cắt lỗ neo giá vào, cơ chế thoát lệnh, và ràng buộc danh mục dưới đây là **hoàn toàn xác định (deterministic), không có tham số mơ hồ**.

---

## 1. Định Nghĩa Tín Hiệu Mua Đóng Băng & Cơ Chế Chặn Fail-Closed (Option 1 Execution Gate)

Hệ thống phân tách rạch ròi thành 2 phạm vi:
1. **Phạm vi Bản Đóng Băng (v15.0):** Duy trì 100% tính nguyên vẹn của bộ máy quyết định đóng băng `106e6c6` (`logic_version = v15.0_frozen_20261013`). Toàn bộ cơ chế chặn vòng lặp tự tham chiếu được đưa sang **Lớp Thực thi Giao dịch Giả định ([`paper_trading.py`](file:///c:/Users/Window/Desktop/Stock%20-%20learning/paper_trading.py)) theo cơ chế Fail-Closed**.
2. **Phạm vi Thay Đổi Logic (Challenger / v15.1):** Mọi điều chỉnh về tiêu chí tự thêm vào Watchlist hoặc thay đổi khóa xếp hạng sơ cấp sẽ được tách riêng sang nhánh nghiên cứu Challenger và chỉ có hiệu lực khi nâng `logic_version = v15.1` bắt đầu kỷ nguyên mới.

### Bốn Cổng Kích Hoạt Tín Hiệu Mua Baseline (Commit 106e6c6)

1. **Cổng 1: Biên An Toàn Định Giá (Valuation MoS Gate):**
   - $\text{MoS} \ge +15,0\%$ (Biên an toàn tối thiểu so với Giá trị Hợp lý Fair Value tính theo mô hình Gordon Growth / DDM).
   - Cổng dữ liệu: `data_gate` trả về `recommendation_allowed = True` (dữ liệu tài chính không bị lỗi thời nghiêm trọng `is_stale = False`).
   - Loại trừ tuyệt đối: Cổ phiếu bị gắn cờ `RISK_TRAP` hoặc `ACCOUNTING_ANOMALY`.

2. **Cổng 2: Xác Nhận Kỹ Thuật Baseline (Technical Gate):**
   - **Vị thế giá:** Thị giá đóng cửa nằm trên đường trung bình động MA100 ngày ($P \ge MA100$).
   - **Xác nhận thanh khoản phiên kích hoạt:** Khối lượng giao dịch phiên kích hoạt đạt **$V \ge 1,0 \times MA20$** (khối lượng $\ge$ trung bình 20 phiên gần nhất, tương ứng `vol_ratio >= 1.0`). Giữ nguyên chuẩn 1.0 theo đúng logic đóng băng của commit `106e6c6`.
   - **Thanh khoản nền tảng (Data Gate):** Giá trị giao dịch trung bình 20 phiên đạt $\text{ADV20} \ge 2,0\text{ tỷ VND}$ tính Point-in-time đến ngày $T_0$ (`executable_size_ok = True`).

3. **Cổng 3: Điểm Thuyết Phục & Cổng Chặn Fail-Closed Tại Lớp Thực Thi (Option 1 Fail-Closed Gate):**
   - **Core Engine v15.0 (`data_engine.py`):** Giữ nguyên điều kiện đóng băng gốc của commit `106e6c6`: $\text{Conviction} \ge 70$. Đồng thời, bộ máy làm giàu telemetry không xâm lấn trong `facts`: ghi nhận song song `conviction_score`, `conviction_ex_watchlist`, `watchlist_bonus`, `is_in_watchlist`.
   - **Cơ Chế Chặn Fail-Closed Tại Lớp Thực Thi (`paper_trading.py`):** Lớp thực thi giao dịch giả định bắt buộc kiểm tra nghiêm ngặt trước khi khớp:
     - **Trường hợp thiếu dữ liệu xác minh (Missing / None):** Khóa chặn ngay lập tức theo cơ chế **Fail-Closed**, không cho lệnh đi qua, gắn trạng thái $\mathbf{BUY\_UNVERIFIED}$ với lý do: *"BUY blocked: conviction_ex_watchlist missing (fail-closed verification gate)"*.
     - **Trường hợp điểm tự thân dưới ngưỡng ($< 70,0$):** Chặn lệnh khớp, gắn trạng thái $\mathbf{BUY\_SUPPRESSED\_WATCHLIST}$ với lý do: *"BUY suppressed: conviction_ex_watchlist < 70.0 (anti-reflexive execution gate)"*.
     - **Chỉ khi $\mathbf{\text{Conviction\_ex\_watchlist} \ge 70,0}$:** Lệnh mới được coi là hợp lệ để tiếp tục chuyển qua kiểm tra Cooldown và Ngân sách tín hiệu hàng ngày.
   - **Bản chụp Danh sách Theo dõi (Watchlist Snapshots):** Hệ thống tự động sao lưu bản chụp hàng ngày tại `data/snapshots/watchlist_snapshot_YYYYMMDD.json` phục vụ đối soát PIT.

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

### 5.0. Thời Điểm Khớp Lệnh Thực Thi (Deterministic Execution Timing)
- **Lệnh MUA:** Thực thi duy nhất tại **giá mở cửa ATO của phiên kế tiếp ($T+1$)** sau khi tín hiệu thỏa mãn đầy đủ 4 Cổng chốt phiên EOD tại $T_0$. Loại bỏ hoàn toàn sự mơ hồ giữa phiên đóng cửa và phiên kế tiếp: **quy ước duy nhất là phiên kế tiếp ($T+1$)**.
- **Lệnh BÁN (Chốt lời, Cắt lỗ, Trailing Stop):** Kích hoạt và thực thi tại **phiên kế tiếp ($T+1$)** ngay khi thị giá chạm hoặc xuyên thủng ngưỡng điều kiện tương ứng.

### 5.1. Lộ trình Chốt Lời Xác Định Từng Phần (Staged Partial Profit Targets)
- **Target 1 ($P/L \ge +15,0\%$):** Bán chốt lời chủ động **đúng 40% khối lượng vị thế** (chốt một phần, bảo toàn lợi nhuận).
- **Target 2 ($P/L \ge +25,0\%$):** Bán chốt lời tiếp **đúng 30% khối lượng vị thế**.
- **Phần còn lại (đúng 30% khối lượng):** Thả nổi theo Trailing Stop động 6,0% tính từ đỉnh cao nhất để tối ưu hóa lợi nhuận theo sóng lớn (tuyệt đối không bán 100% tại Target 1 để còn vị thế áp dụng Trailing Stop).

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

---

## 7. Nhật Ký Thay Đổi Có Ngày (Dated Changelog - Pre-First-BUY Era)

*Toàn bộ các cập nhật và làm rõ dưới đây đều được hoàn tất và ký chốt trước khi có bất kỳ tín hiệu MUA thực tế đầu tiên nào (tính đến hết phiên 23/10 toàn thị trường có 0 tín hiệu MUA).*

| Ngày (UTC) | Hạng mục thay đổi | Chi tiết kỹ thuật & Cam kết nghiệm thu | Trạng thái bảo chứng |
| :--- | :--- | :--- | :--- |
| **2026-10-13** | **Khởi đầu Kỷ nguyên Đóng băng v15.0** | Vận hành phiên 13/10 trên commit `734893f` (152 bản ghi quyết định chuẩn). Bằng chứng replay zero-diff tại [`test_golden_zero_diff_replay.py`](file:///c:/Users/Window/Desktop/Stock%20-%20learning/tests/test_golden_zero_diff_replay.py) chứng minh 55/55 mã khớp 100% không lệch 1 điểm so với `106e6c6`. | ZERO-DIFF CHỨNG MINH |
| **2026-10-14** | **Commit Đóng Băng `106e6c6`** | Vận hành phiên 14/10 trên commit `8d353f5` (201 bản ghi, zero-diff). Commit `106e6c6` được lưu vào Git lúc 20:20:38Z để đưa vào vận hành thực tế từ phiên 15/10. | ĐÃ COMMIT |
| **2026-10-15** | **Phiên Đầu Tiên Mang Commit `106e6c6`** | Vận hành chính thức trên commit `106e6c6` (200 bản ghi), chính thức hiển thị `logic_version = v15.0_frozen_20261013` trong schema dữ liệu. | PROD-FROZEN |
| **2026-10-20** | **Tạo Git Tag `v15.0_frozen_20261013`** | Tạo tag `f958ff2` (08:31:24Z) trỏ tới commit `106e6c6` nhằm phục vụ nghiệm thu kiểm toán độc lập. | HOÀN TẤT |
| **2026-10-22** | **Đăng ký Giao thức Mua v15.0** | Tạo tag `ce421ba` (21:27:14Z) tại commit `c304749`, đăng ký trước quy mô vị thế 14.28% NAV và quy tắc cắt lỗ neo giá vào. | HOÀN TẤT |
| **2026-10-24** | **Kiểm toán Tái thẩm định v15.0** | Commit `784e5c9` (08:54:54Z), tạo tag `b2e964d` (08:55:15Z), đẩy công khai lên `origin/dev` lúc 08:55:40Z (trước bất kỳ tín hiệu MUA đầu tiên nào). | HOÀN TẤT |
| **2026-10-24** | **Chốt Cơ Chế Fail-Closed (Option 1)** | Giữ nguyên 100% logic core engine `106e6c6` (`logic_version = v15.0`). Triển khai bộ lọc chặn Fail-Closed tại lớp thực thi `paper_trading.py`: chặn `BUY_UNVERIFIED` khi thiếu/sai `conviction_ex_watchlist` và `BUY_SUPPRESSED_WATCHLIST` khi `< 70.0`. Gated Challenger v15.1 sau cờ `ENABLE_CHALLENGER_V15_1 = False`. | HOÀN TẤT & ĐĂNG KÝ TRƯỚC |
| **2026-10-24** | **Kế hoạch Triển khai Gói (a) Production** | Phát hành Gói (a) (Telemetry + Cổng Fail-Closed) trước phiên thứ Hai 27/10/2026. Kiểm toán khởi động `APP_ENV=production`, xác nhận xuất hiện trường `conviction_ex_watchlist` và 0 tín hiệu MUA bị lọt lưới. | SẴN SÀNG TRIỂN KHAI |


