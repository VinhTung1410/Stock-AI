# TASK-0082: Statistical Validation Engine Specification (v2 - Hardened)

## 1. Mục Tiêu (Objective)
Xây dựng engine kiểm định thống kê (Statistical Validation Engine) nhằm đánh giá kết quả của Ablation Testing và Event Study một cách khoa học, định lượng và triệt để. Engine loại bỏ hoàn toàn các kết luận cảm tính, chặn đứng data snooping / p-hacking và phân định rạch ròi giữa "Exploratory" (thăm dò) và "Confirmatory" (xác nhận).

Phiên bản v2 được củng cố toán học:
1. Sửa lỗi vòng lặp đo power: Đo power với hiệu ứng cố định dựa trên $SE_{\text{true}}$ của quần thể (tính độc lập), tách power khỏi cổng an toàn chặn lỗi.
2. Cú sốc ngoại lai $+26\%$ (VIC) được đưa về tâm kỳ vọng bằng $0$ ($E[\text{shock}] = 0$).
3. Ngưỡng gom cụm chính mặc định là **20 phiên** (khớp cửa sổ nắm giữ T+20 để triệt tiêu chồng lấn chuỗi), kiểm tra độ nhạy tại 5 và 10 phiên.
4. Thêm kiểm định phụ thuộc chuỗi liên cụm $\phi \in \{0.1, 0.2, 0.3\}$ và tích hợp sai số chuẩn Newey–West (Bartlett lag-1) theo chuỗi cụm.
5. Khóa sự kiện biên thống nhất theo `(symbol, panic_date)` để loại bỏ thiên lệch lệch pha vào lệnh.
6. Kiểm định cắt bỏ (Ablation) được thực hiện bằng gom cụm trên **hợp của hai tập** ($V \cup B$) và đo hiệu số ghép cặp $\theta_{\text{diff}} = \alpha(\text{marginal}) - \alpha(\text{baseline})$.

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
- **Hệ quả thống kê trên dữ liệu hiện tại ($G \approx 9-13$, Cluster $SE \approx 3.5\%$):**
  - Với phân phối Student $t$ ($df = G - 1$):
    - Để đạt nhãn **ALPHA** (vượt ngưỡng Holm $m=40$): Cần $\hat{\theta} > 2.5\% + t_{\text{Holm}} \times SE \approx 15.8\%$.
    - Để đạt nhãn **KHÔNG CÓ HIỆU ỨNG ĐÁNG KỂ** (TOST nằm gọn trong $[-\delta, +\delta]$): Cần $SE < \delta / t_{\text{Holm}} \approx 0.65\%$.
  - Do $SE$ thực tế ($\approx 3.5\%$) lớn hơn $0.65\%$, engine được dự báo trước là sẽ trả về **INCONCLUSIVE** cho hầu hết các biến thể trên tập dữ liệu lịch sử hiện hữu.

### 2.2. Quy Tắc Quyết Định Động (Dynamic Verdict Rules) & Hiệu Chỉnh Holm
- **Họ giả thuyết (Hypothesis Family) tích lũy cố định:** $m = 40$ phép thử được chốt trước (9 từ V12, 8 từ V13, 7 từ TASK-0080, 7 từ TASK-0081, 9 từ TASK-0082).
- **Quy tắc dán nhãn cho biến thể $j$ ($j = 1, \dots, m$):**
  1. **ALPHA:** $p$-value hiệu chỉnh Holm của kiểm định một phía $H_0: \theta_j \le \delta$ đạt $p_j^{\text{Holm}} < 0.05$.
  2. **KHÔNG CÓ HIỆU ỨNG ĐÁNG KỂ:** Cả hai kiểm định tương đương một phía (TOST) cho $H_{01}: \theta_j \le -\delta$ và $H_{02}: \theta_j \ge +\delta$ đều bị bác bỏ ở mức ý nghĩa hiệu chỉnh Holm $\alpha = 0.05$.
  3. **INCONCLUSIVE:** Tất cả các trường hợp còn lại.
- **Xử lý số lượng giả thuyết thực $n < m$:** Khi chỉ có $n < 40$ giả thuyết được kiểm định trong một lượt chạy, thuật toán Holm áp dụng đúng bộ nhân $(m, m-1, \dots, m-n+1)$, coi các giả thuyết chưa có p-value có $p = 1.0$.

### 2.3. Phương Pháp Ước Lượng & Sai Số Chuẩn Bền Vững (Robust SE)
- **Phương pháp chính (Primary):** **Student-t ($df = G - 1$)** trên trung bình các cụm, tích hợp **Cluster Newey–West (Bartlett lag-1)**:
  $$\hat{V}_{\text{NW}} = \frac{1}{G} (\hat{\gamma}_0 + \hat{\gamma}_1) \times \frac{G}{G - 1}, \quad SE_{\text{robust}} = \sqrt{\max(\hat{V}_{\text{NW}}, SE_{\text{iid}}^2)}$$
  giúp bảo toàn độ bao phủ khi các đợt sập có tương quan liên cụm $\phi > 0$.
- **Phương pháp kiểm tra độ nhạy (Secondary / Sensitivity):** **Studentized Wild Cluster Bootstrap (Bootstrap-t)** sử dụng trọng số **Webb 6-point**.
- **Estimand:** **Trung bình của các trung bình cụm** (Mean of cluster means).

### 2.4. Luật Gom Cụm Mặc Định & Giới Hạn Chuỗi
- **Khoảng cách mặc định:** **20 phiên giao dịch** (khớp với chu kỳ nắm giữ T+20 để các cụm không bị chồng lấn cửa sổ lợi suất).
- **Giới hạn độ dài tối đa (Chaining Limit):** Tối đa 40 phiên giao dịch cho một cụm. Báo cáo `split_clusters_count`.
- **Kiểm tra độ nhạy gom cụm:** So sánh kết quả tại các khoảng cách 5, 10 và 20 phiên. Kích hoạt cờ cảnh báo `SENSITIVE_TO_CLUSTERING_PARAMETER` nếu số lượng cụm biến động $> 30\%$.

### 2.5. Kiểm Định Ablation Ghép Cặp (Paired Marginal Difference)
- **Khóa sự kiện thống nhất:** `(symbol, panic_date)` — điểm kích hoạt hoảng loạn đầu tiên. Cùng một đợt hoảng loạn được đo lợi suất từ cùng một điểm tham chiếu để không đo sai lệch thời gian vào lệnh.
- **Gom cụm trên hợp của hai tập:** Gom cụm được thực hiện trên $V \cup B$ (hợp giữa biến thể và baseline) để bảo toàn cấu trúc chuỗi thời gian giống hệt nhau.
- **Estimand kiểm định:** Hiệu số ghép cặp theo cụm:
  $$\Delta_g = \alpha(\text{marginal})_g - \alpha(\text{baseline})_g$$
  Kiểm định câu hỏi cốt lõi: Các cơ hội bị cổng loại bỏ có alpha kém hơn baseline không? ($H_0: \theta_{\text{diff}} \le 0$).
- **Ngưỡng cụm biên tối thiểu:** Nếu số cụm biên $G_{\text{marginal}} < 5$, engine không chạy kiểm định giả thuyết alpha mà gắn nhãn: `KHÔNG THỂ KIỂM ĐỊNH (G < 5)`.
- **Chốt an toàn rủi ro:** Các cổng ADV20, MoS Macro Downtrend, F-Score Survival được đánh giá qua **Binding Count** và hồ sơ rủi ro Drawdown/Tail-loss.

### 2.6. Matched-Date Peers & Bẫy Loại Bỏ Đợt Hoảng Loạn
- **Quy ước lợi suất khả thi (Tradable Return):** $R_{\text{tradable}} = \text{Close}(D+20) / \text{Open}(D+1) - 1$.
- **Lọc Peers $N_{\text{peers}} \ge 10$ & Fallback:**
  - Vào các ngày hoảng loạn diện rộng (nhiều mã kích hoạt cùng lúc), nếu số peers không hoảng loạn $< 10$, hệ thống **không loại bỏ ngày sự kiện** mà chuyển sang cơ chế dự phòng: lấy lợi suất VN-Index điều chỉnh Beta lăn 60 phiên (`PEERS_BELOW_10_FALLBACK_BENCHMARK`).
  - Ghi nhận chi tiết nhật ký kiểm toán (Audit log) số ngày và số sự kiện kích hoạt dự phòng để đảm bảo không thiên vị bỏ các đợt sập mạnh nhất.

---

## 3. Quy Chuẩn Acceptance Test (Mô Phỏng Monte Carlo N=10,000)

### 3.1. Thiết Kế DGP Phi Gaussian & Cú Sốc Ngoại Lai Chuẩn Hóa
- Số cụm $G = 13$ (df = 12).
- Cú sốc thị trường chung lệch phải (Chi-square $df = 3$).
- Cú nhảy ngoại lai $+26\%$ (như VIC) với xác suất $10\%$, được đưa về tâm kỳ vọng bằng $0$:
  $$\text{Shock} = (26.0 - 2.6) \text{ khi kích hoạt, và } -2.6 \text{ khi không kích hoạt}$$
  đảm bảo $E[\text{Shock}] = 0$ tuyệt đối dưới giả thuyết vô hiệu $H_0$.

### 3.2. Tiêu Chí Nghiệm Thu An Toàn (Safety Gates - N=10,000)
1. **False Positive tại $H_0 (\theta = 0)$:** $\le 1.0\%$.
2. **False Positive tại biên $H_0 (\theta = \delta = 2.5\%)$:** $\le 5.0\%$.
3. **Extreme Tail False Positive tại ngưỡng Holm ($\alpha = 0.05 / 40 = 0.00125$):** $\le 0.20\%$.
4. **Family-Wise Error Rate (FWER) Holm $m = 40$ tại biên:** $\le 5.5\%$.
5. **95% Confidence Interval Coverage (Student-t $df=12$):** $[93.5\%, 96.5\%]$.
6. **Wild Cluster Bootstrap Coverage:** $[92.0\%, 96.5\%]$.
7. **TOST Type I Error tại biên $\theta = \pm \delta$ dưới Holm $m = 40$:** $\le 1.0\%$.
8. **Định danh TOST khi $\theta = 0$ ($G = 100$, $SE < 1.0\%$):** $\ge 90.0\%$.

### 3.3. Đo Lường Báo Cáo Thông Tin (Informational Metrics)
- **Empirical Power với Hiệu Ứng Cố Định:**
  - $SE_{\text{true}}$ được tính trước từ 50,000 mẫu độc lập dưới DGP null.
  - Hiệu ứng cố định chèn vào: $\theta_{\text{target}} = \delta + (t_{\text{Holm}} + t_{\text{power}}) \times SE_{\text{true}}$.
  - Power được báo cáo độc lập phản ánh năng lực phát hiện thật trên dữ liệu lệch và đuôi dày (không làm cổng pass/fail).
- **Chẩn đoán phụ thuộc chuỗi liên cụm:** Báo cáo tỷ lệ Coverage, Single FP và FWER tại các mức $\phi \in \{0.1, 0.2, 0.3\}$.
