# TASK-0082: Statistical Validation Engine Specification

## 1. Mục Tiêu (Objective)
Xây dựng engine kiểm định thống kê (Statistical Validation Engine) nhằm đánh giá kết quả của Ablation Testing và Event Study một cách khoa học, định lượng và triệt để. Engine loại bỏ hoàn toàn các kết luận cảm tính, chặn đứng data snooping / p-hacking và phân định rạch ròi giữa "Exploratory" (thăm dò) và "Confirmatory" (xác nhận).

---

## 2. Thông Số Định Lượng & Quy Chuẩn Toán Học (Chốt Cố Định Trước Khi Chạy)

### 2.1. Ngưỡng Kinh Tế $\delta$ (Economic Significance Hurdle)
- **Giá trị cố định:** $\delta = 2.50\%$ (Lợi suất ròng vượt trội tối thiểu T+20).
- **Cơ sở phân rã cấu thành (Breakdown):**
  1. Phí giao dịch 2 chiều (Mua + Bán): $0.15\% \times 2 = 0.30\%$.
  2. Thuế thu nhập bán chứng khoán: $0.10\%$.
  3. Trượt giá thực tế (Slippage / Market Impact tại Open D+1 và Close D+20): $0.30\% \times 2 = 0.60\%$.
  4. Chi phí cơ hội / Chi phí vốn T+20 (Giả định $10\%/\text{năm}$, 250 phiên): $10\% \times (20 / 250) = 0.80\%$.
  5. Phần bù ma sát thanh khoản & rủi ro kẹt hàng T+2.5: $0.70\%$.
  $$\delta = 0.30\% + 0.10\% + 0.60\% + 0.80\% + 0.70\% = 2.50\%$$
- **Hệ quả thống kê trên dữ liệu hiện tại ($G \approx 13$, Cluster $SE \approx 3.5\%$):**
  - Với phân phối Student $t$ ($df = 12$, $t_{\text{crit}} = 2.179$ tại $\alpha = 0.05$):
    - Để đạt nhãn **ALPHA** (Cận dưới CI $> \delta$): Cần $\hat{\theta} > 2.5\% + 2.179 \times 3.5\% = 10.13\%$.
    - Để đạt nhãn **KHÔNG CÓ HIỆU ỨNG ĐÁNG KỂ** (TOST nằm gọn trong $[-\delta, +\delta]$): Cần $SE < \delta / t_{\text{crit}} \approx 2.5\% / 2.179 \approx 1.15\%$.
  - Do $SE$ thực tế ($\approx 3.5\%$) lớn hơn $1.15\%$, engine được dự báo trước là sẽ trả về **INCONCLUSIVE** cho hầu hết các biến thể trên tập dữ liệu lịch sử hiện hữu. Đây là kết quả trung thực và khách quan.

### 2.2. Quy Tắc Quyết Định Động (Dynamic Verdict Rules) & Hiệu Chỉnh Holm
- **Họ giả thuyết (Hypothesis Family) tích lũy cố định:** $m = 40$ phép thử được chốt trước, bao gồm:
  - 9 phép thử V12.
  - 8 phép thử V13.
  - 7 phép thử TASK-0080.
  - 7 phép thử TASK-0081.
  - 9 phép thử biến thể TASK-0082.
- **Quy tắc dán nhãn cho biến thể $j$ ($j = 1, \dots, m$):**
  1. **ALPHA:** $p$-value hiệu chỉnh Holm của kiểm định một phía $H_0: \theta_j \le \delta$ đạt $p_j^{\text{Holm}} < 0.05$.
  2. **KHÔNG CÓ HIỆU ỨNG ĐÁNG KỂ:** Cả hai kiểm định tương đương một phía (TOST) cho $H_{01}: \theta_j \le -\delta$ và $H_{02}: \theta_j \ge +\delta$ đều bị bác bỏ ở mức ý nghĩa hiệu chỉnh Holm $\alpha = 0.05$.
  3. **INCONCLUSIVE:** Tất cả các trường hợp còn lại (bao gồm khi khoảng tin cậy bao trùm cả $0$ lẫn $\delta$, hoặc MDE quá lớn).
- **Công thức MDE (Minimum Detectable Effect):**
  $$MDE = (t_{0.975, df=G-1} + t_{0.80, df=G-1}) \times SE \approx (2.179 + 0.873) \times SE \approx 3.05 \times SE$$
  (Tính thuần túy từ Cluster SE và Power $80\%$, tuyệt đối không lấy từ hiệu ứng quan sát).

### 2.3. Phương Pháp Ước Lượng Chính Cho Mẫu Nhỏ ($G \approx 13$)
- **Phương pháp chính (Primary):** **Student-t ($df = G - 1$)** trên trung bình các cụm. Kết quả mô phỏng nghiệm thu chứng minh Student-t hiệu chỉnh chính xác ở bậc tự do 12 (đạt coverage ~94.8% trong dải 1 SE danh nghĩa), vượt trội so với bootstrap percentile/studentized ở mẫu cực nhỏ.
- **Phương pháp kiểm tra độ nhạy (Secondary / Sensitivity):** **Studentized Wild Cluster Bootstrap (Bootstrap-t)** sử dụng trọng số **Webb 6-point** ($w \in \{-\sqrt{1.5}, -1, -\sqrt{0.5}, \sqrt{0.5}, 1, \sqrt{1.5}\}$).
- **Estimand:** **Trung bình của các trung bình cụm** (Mean of cluster means, gán trọng số ngang nhau cho từng episode).
- **Quy tắc quyết định thống nhất (Unified Decision Rule):**
  - Kiểm định một phía: $H_0: \theta \le \delta$ đối chiếu $H_1: \theta > \delta$.
  - Thống kê kiểm định: $t = (\hat{\theta} - \delta) / SE$.
  - p-value một phía: $p = 1.0 - \text{Student-}t.\text{cdf}(t, df=G-1)$.
  - Quyết định `ALPHA`: Yêu cầu $\hat{\theta} > \delta$ VÀ $p^{\text{Holm}} < 0.05$.
  - Quyết định `KHÔNG CÓ HIỆU ỨNG ĐÁNG KỂ`: Kiểm định tương đương TOST hai phía trong $[-\delta, +\delta]$ với $p_{\text{TOST}}^{\text{Holm}} < 0.05$.

### 2.4. Luật Gom Cụm (Clustering) & Giới Hạn Chuỗi
- **Luật cơ sở:** Các sự kiện cách nhau $\le 10$ phiên giao dịch thuộc cùng 1 cụm.
- **Giới hạn độ dài tối đa (Chaining Limit):** Tối đa 40 phiên giao dịch cho một cụm. Nếu một đợt kéo dài $> 40$ phiên, tự động cắt thành các cụm kế tiếp có độ dài tối đa 40 phiên. Báo cáo số lượng cụm bị cắt (`split_clusters_count`) như một cảnh báo phụ thuộc.
- **Kiểm tra độ nhạy gom cụm:** Chạy song song ngưỡng khoảng cách 5, 10 và 20 phiên. Báo cáo $G$ và độ dài cụm lớn nhất. Nếu số lượng cụm biến động $> 30\%$, tự động kích hoạt cờ cảnh báo: `SENSITIVE_TO_CLUSTERING_PARAMETER`.

### 2.5. Kiểm Định Ablation Theo Hiệu Số Sự Kiện Biên (Marginal Difference)
- **Định nghĩa tập biên:** Sự kiện biên là sự kiện bị cổng kiểm thử loại bỏ ở baseline nhưng được cho phép khi cổng đó bị tắt.
- **Xử lý lệch pha vào lệnh:** Cổng Price Confirmation làm trễ điểm vào lệnh (8–17 phiên). Kiểm tra tập lồng nhau (Superset assertion) được thực hiện trên **tập ứng viên tín hiệu thô** (Signal candidate dates), đảm bảo $\text{Candidates}_{\text{relaxed}} \supseteq \text{Candidates}_{\text{baseline}}$.
- **Ngưỡng cụm biên tối thiểu:** Nếu số cụm biên $G_{\text{marginal}} < 5$, engine không chạy kiểm định giả thuyết alpha mà in rõ: `KHÔNG ĐỦ CỤM BIÊN (G_marginal < 5)`.
- **Cổng an toàn rủi ro:** Các chốt chặn ADV20, MoS Macro Downtrend, F-Score Survival được đánh giá bằng **Chỉ số rủi ro** (Max Drawdown, Win Rate sụp đổ, Tail loss) và **Binding Count**, không đánh giá bằng Alpha. Cột Binding Count là bắt buộc.

### 2.6. Quy Ước Giá, Matched-Date Peers & Xử Lý Dữ Liệu Thiếu
- **Quy ước lợi suất khả thi (Tradable Return):** Thống nhất với V13:
  $$R_{\text{tradable}} = \frac{\text{Close}(D+20)}{\text{Open}(D+1)} - 1$$
- **Matched-Date Peers:**
  - Định nghĩa: Các mã cổ phiếu trong vũ trụ KHÔNG kích hoạt tín hiệu tại ngày $D$.
  - Số lượng tối thiểu: Phải có ít nhất $N_{\text{peers}} \ge 10$ mã tại ngày $D$.
  - Primary baseline: Toàn bộ rổ peers hợp lệ.
  - Secondary baseline: Cùng nhóm ngành (gán nhãn approximate do phân loại ngành non-PIT).
- **Beta-adjustment:** Tính Beta lăn (rolling 60 sessions) chỉ sử dụng dữ liệu $\le D$ (không look-ahead). Báo cáo thêm dòng Alpha đã điều chỉnh Beta.
- **Dữ liệu thiếu / Đình chỉ giao dịch:** Nếu cổ phiếu bị hủy niêm yết, đình chỉ giao dịch hoặc thiếu giá tại $D+20$, báo cáo số lượng cụ thể và gán giá trị phạt (thay vì âm thầm dùng `dropna()`).
- **Thiên lệch sống sót (Survivorship Bias):** Bắt buộc in cảnh báo thiên lệch sống sót trên mọi bảng kết quả.

### 2.7. Quy Tắc Dừng Forward Confirmation & Đóng Băng Cấu Hình
- **Thời điểm đóng băng:** Dữ liệu $\le$ ngày 2026-10-08 là **Exploratory**. Dữ liệu sau thời điểm đóng băng mới được đưa vào **Confirmatory**.
- **Cấu hình đóng băng cố định:** Hash commit của `contrarian_engine.py` với bộ tham số chuẩn:
  - `Panic Score >= 70`
  - `Confirmation Score >= 40`
  - `Piotroski F-Score >= 7`
  - `ADV20 >= 2 tỷ VND`
  - `MoS >= 15%` (phạt +5% khi downtrend)
- **Quy tắc dừng:** Số cụm forward tối thiểu $G_{\text{forward}} \ge 10$. Đánh giá duy nhất một lần khi đạt đủ $G = 10$. Nghiêm cấm đánh giá lũy tiến nếu không có hàm Alpha Spending (O'Brien-Fleming).
- **Tính toàn vẹn dữ liệu:** Dữ liệu forward phải có đóng dấu thời gian (timestamp), băm SHA-256 theo từng episode và cấm ghi đè.

---

## 3. Quy Chuẩn Acceptance Test Của Engine (Kiểm Chứng Placebo Bắt Buộc)

Engine thống kê phải vượt qua Acceptance Test mô phỏng Monte Carlo ($N_{\text{sim}} = 10,000$ lần) trước khi được phép chạy trên dữ liệu thật.

### 3.1. Thiết Kế Mô Phỏng Giống Dữ Liệu Thật
- Số cụm $G = 13$.
- Kích thước cụm không đều: lấy mẫu ngẫu nhiên từ 1 đến 12 quan sát mỗi cụm.
- Phân phối lợi suất đuôi dày và lệch: Lệch phải (Chi-square 3 tự do), sai số Student-$t$ ($df = 4$), có 10% xác suất xuất hiện cú nhảy ngoại lai $+26\%$ (như VIC).
- Có tương quan nội cụm (Intra-cluster correlation $\rho \approx 0.25$).
- Hoán vị ngày tín hiệu theo **khối cụm (Block permutation)** để bảo toàn cấu trúc cụm.

### 3.2. Tiêu Chí Nghiệm Thu Bằng Số (Hard Numerical Pass/Fail Gates tại N=10,000)
1. **False Positive tại $H_0 (\theta = 0)$:** $\le 1.0\%$.
2. **False Positive tại biên $H_0 (\theta = \delta = 2.5\%)$:** $\le 5.0\%$.
3. **Extreme Tail False Positive tại ngưỡng Holm ($\alpha = 0.05 / 40 = 0.00125$):** $\le 0.20\%$.
4. **Family-Wise Error Rate (FWER) Holm $m = 40$ tại biên:** $\le 5.5\%$.
5. **Power tại $\theta = \delta + MDE_{\text{Holm}}$ với Holm $m = 40$:** $80.0\% \pm 3.5\%$.
6. **95% Confidence Interval Coverage (Student-t $df=12$):** $[94.0\%, 96.0\%]$.
7. **Wild Cluster Bootstrap Coverage:** $[92.0\%, 96.0\%]$.
8. **TOST Type I Error tại biên $\theta = \pm \delta$ dưới Holm $m = 40$:** $\le 1.0\%$.
9. **Định danh TOST khi $\theta = 0$ ($G = 100$, $SE < 1.0\%$):** $\ge 90.0\%$.

**CƠ CHẾ KHÓA AN TOÀN:** Nếu Acceptance Test không đạt bất kỳ tiêu chí nào nêu trên, engine sẽ tự động dừng và khóa (raise `RuntimeError`), cấm chạy trên dữ liệu lịch sử thật.
