# 🎯 YÊU CẦU DỰ ÁN (CLIENT BRIEF)

**Tên dự án:** Stock-AI / AI Trading Bot  
**Ngày tạo:** 2026-09-24 | **Cập nhật:** 2026-09-24  
**Người yêu cầu (Client):** Tùng  
**Phiên bản yêu cầu:** v4.0 — Chuẩn hóa Thước đo Backtest, Nâng cấp Lõi Chiến lược Quant Core & Tích hợp Benchmark VN-Index  

---

## 1. TỔNG QUAN DỰ ÁN (EXECUTIVE SUMMARY)

- **Kế thừa thành quả các phiên bản trước:**
  - Hạ tầng cứng Backtest đã mô phỏng chuẩn xác cơ chế HOSE (trần/sàn ±7%, quy chế T+2.5, thuế phí 0.25%, trượt giá 15 bps, trần hấp thụ thanh khoản 5% ADV20, Audit Trail Supabase).
  - Tích hợp thành công giao diện Tab 6 (Backtest Dashboard, Bảng số liệu Regime, Paper Trading).
  - Hoàn thiện luồng Web-to-Discord hook cho khuyến nghị MUA và cô lập 100% mock Discord trong bộ kiểm thử tự động (Zero Test Leakage).

- **Vấn đề trọng yếu phát hiện tại v3.1 (Rà soát chuyên môn qua ca kiểm thử VIC):**
  1. **Đồng hồ đo Alpha/Beta bị tê liệt (Beta luôn = 1.0, Alpha = 0%):** Do `benchmark_returns` (chuỗi lợi suất VN-Index) không được truyền vào Backtest Engine, hệ thống luôn trả về giá trị mặc định. Điều này bóp méo hoàn toàn bức tranh rủi ro: VIC thực tế có $\beta = 1.78$ (siêu biến động) hay HPG $\beta = 0.66$ đều bị gán cào bằng là 1.0.
  2. **Bảng Regime bị rỗng dữ liệu (Cột Uptrend/Downtrend toàn số 0):** Thuật toán `MA200_SLOPE` đòi hỏi tối thiểu 200 nến mới bắt đầu có độ dốc. Khi kiểm thử khung 200 phiên, dữ liệu rơi hoàn toàn vào Sideways. Đồng thời, việc lấy nến của *chính cổ phiếu đó* thay vì *chỉ số thị trường chung VN-Index* là sai về mặt phương pháp luận (Regime Tautology).
  3. **Nghịch lý kiến trúc "Xe đua F1 gắn bánh xe đạp":** Hệ thống phân tích thực tế tích hợp rất nhiều lớp tinh vi (Piotroski F-Score, Altman Z-Score, Biên an toàn MoS, Kelly Criterion, Hard Gates, PM Arbitration). Nhưng Backtest Engine lại chỉ gắn duy nhất chiến lược thô sơ MA20/MA50 crossover. Kết quả là cổ phiếu High-Beta như VIC tăng thực tế +67% nhưng backtest lại báo lỗ -30% do liên tục bị dính bẫy tín hiệu (whipsaw). Kết quả này **hoàn toàn không phản ánh năng lực thật của hệ thống**.
  4. **Thiếu đường tham chiếu trực quan Buy & Hold:** Biểu đồ Equity Curve chỉ có một đường vốn chiến lược đơn độc, không thể đối chiếu xem chiến lược thắng hay thua so với việc mua nắm giữ thụ động (Buy & Hold) hay chỉ số VN-Index.
  5. **Trải nghiệm UX nhập vốn ban đầu:** Ô nhập tiền chưa có định dạng phân cách hàng nghìn (`100000000` thay vì `100,000,000`), gây bất tiện và dễ nhầm lẫn số chữ số 0.
  6. **Paper Trading chưa nối dây dữ liệu thực:** Giao diện Subtab 3 hiện vẫn dùng dữ liệu mô phỏng tĩnh, chưa kết nối với bảng tín hiệu `quant_signals` từ Supabase để theo dõi Implementation Shortfall thực tế.

- **Mục tiêu phiên bản 4.0:**
  1. **Chuẩn hóa thước đo định lượng:** Nạp chuỗi dữ liệu VN-Index làm Benchmark để tính toán chính xác Alpha, Beta thực của từng mã cổ phiếu và vẽ đường so sánh Buy & Hold trực quan.
  2. **Chuẩn hóa bộ phân loại Regime theo VN-Index:** Xác định trạng thái thị trường dựa trên VN-Index thay vì từng mã riêng lẻ; linh hoạt ngưỡng nến (MA100 hoặc nạp đủ 400+ nến) để bảng 4 cột hiển thị đầy đủ dữ liệu Uptrend/Downtrend/Sideways.
  3. **Xây dựng chiến lược lõi "Quant Core Strategy":** Đưa bộ tiêu chí thực tế của hệ thống (F-Score $\ge 6$, MoS $\ge 15\%$, Z-Score $> 1.8$, RSI $< 70$, Hard Gates & ATR Stop-loss) vào làm chiến lược kiểm thử chính bên cạnh chiến lược kỹ thuật thuần túy.
  4. **Kết nối luồng Forward Testing (Paper Trading) với Supabase:** Hiển thị danh mục lệnh ảo phát sinh từ tín hiệu thực tế của bot để kiểm chứng trượt giá.
  5. **Hoàn thiện UX:** Định dạng số tiền nhập liệu trực quan (`100,000,000 VND`).

---

## 2. CHÂN DUNG NGƯỜI DÙNG (USER PERSONAS)

- **Nhóm 1 (Nhà đầu tư cá nhân / Client):**
  - Cần đánh giá trung thực: "Cổ phiếu này nếu áp dụng đúng phương pháp định lượng của bot thì lời hay lỗ so với nắm giữ thông thường?".
  - Cần số liệu Beta, Alpha, Winrate, Max Drawdown chính xác để biết mức độ rủi ro của từng mã (ví dụ: VIC biến động gấp đôi thị trường, VNM phòng thủ).
  - Cần giao diện nhập số tiền thân thiện, dễ đọc, có dấu phẩy ngăn cách hàng nghìn.
- **Nhóm 2 (Chuyên gia Quản lý Quỹ & Tư vấn Đầu tư Chuyên nghiệp):**
  - Cần kiểm chứng năng lực sinh Alpha thực thụ của hệ thống kết hợp FA + TA + Macro + Micro.
  - Cần bóc tách hiệu quả chiến lược theo từng Regime thị trường (thắng ở Uptrend, bảo toàn vốn ở Downtrend, phòng ngừa whipsaw ở Sideways).
  - Cần đối soát trượt giá thực tế (Implementation Shortfall) qua Paper Trading giữa giá tín hiệu phát ra và giá khớp thị trường.
  - Tuyệt đối không chấp nhận hiện tượng "overfitting" hay "làm số liệu đẹp nhân tạo".

---

## 3. TÍNH NĂNG CỐT LÕI (CORE FEATURES - MUST HAVE - v4.0)

### Feature 1: Chuẩn hóa Thước đo Alpha / Beta & Tích hợp Benchmark VN-Index
- **Nạp chuỗi dữ liệu Benchmark:**
  - Tích hợp hàm lấy dữ liệu lịch sử của chỉ số `VNINDEX` qua `vnstock` tương ứng với khoảng thời gian kiểm định của cổ phiếu.
  - Truyền `benchmark_returns` vào `engine.run_backtest()`.
- **Tính toán chuẩn xác:**
  - Tính Covariance và Variance giữa chuỗi lợi suất cổ phiếu và VN-Index để cho ra **Beta thực** (ví dụ: VIC $\approx 1.78$, HPG $\approx 0.66$).
  - Tính **Alpha Jensen** annualized chuẩn xác dựa trên mô hình CAPM hoặc chênh lệch CAGR so với Benchmark.
- **Hiển thị trực quan trên UI:**
  - Cập nhật số liệu Alpha, Beta động trên thẻ KPI và Bảng 4 Cột Regime.

### Feature 2: Chuẩn hóa Phân loại Regime Thị trường Dựa trên VN-Index
- **Sửa đổi phương pháp luận:**
  - Chuyển đổi dữ liệu đầu vào của `classify_market_regime()` từ nến cổ phiếu sang **nến chỉ số VN-Index**.
  - Tránh triệt để lỗi "Regime Tautology" (lấy mã tự phân loại cho chính nó).
- **Khắc phục tình trạng rỗng dữ liệu:**
  - Điều chỉnh ngưỡng nến hoặc nạp đủ lịch sử dữ liệu (tối thiểu 300 - 400 nến cho VN-Index) để đường MA/Momentum hình thành đầy đủ.
  - Cho phép chọn chế độ phân loại: `MA100/MA200 Slope` hoặc `Momentum & Volatility` (nhạy hơn với khung ngắn hạn).
  - Đảm bảo các cột `Uptrend`, `Downtrend`, `Sideways` trong bảng số liệu có đầy đủ các chỉ số (Trades, Win Rate, CAGR, Max Drawdown) mang ý nghĩa kinh tế thực.

### Feature 3: Xây dựng Chiến lược Kiểm thử Lõi "Quant Core Strategy"
- **Xóa bỏ thế độc quyền của MA Crossover:**
  - Bổ sung bộ chọn chiến lược (Strategy Selector) trên giao diện Backtest:
    1. `MA Crossover (Trend Following)` (MA20/MA50 — cơ bản để tham khảo).
    2. `Quant Core (FA + TA + Risk Gates)` (Chiến lược phản ánh thực tế logic của Stock-AI).
    3. `RSI & Mean Reversion` (Bắt đáy điều chỉnh).
- **Quy tắc của "Quant Core Strategy":**
  - **Tín hiệu MUA:** Cổ phiếu thỏa mãn đồng thời:
    - Điểm Piotroski F-Score $\ge 6$ (Sức khỏe tài chính tốt).
    - Biên an toàn định giá MoS $\ge 15\%$ (Định giá hấp dẫn).
    - Altman Z-Score $> 1.8$ (An toàn phá sản).
    - RSI $< 70$ (Không mua đuổi vùng quá mua).
    - Vượt qua Data Gate và Hard Gates.
  - **Tín hiệu BÁN:**
    - Chạm ngưỡng Stop-Loss biến động (ví dụ: gãy $2 \times \text{ATR}$ hoặc $-7\%$).
    - RSI vượt 75 (Chốt lời chủ động vùng quá mua).
    - Biên an toàn suy giảm mạnh ($\text{MoS} < -25\%$).
    - Gãy luận điểm đầu tư (PM Arbitration Thesis Breaker).

### Feature 4: Biểu đồ Equity Curve Đa Đường (Chiến lược vs. Buy & Hold vs. VN-Index)
- **Trực quan hóa so sánh đa chiều:**
  - Vẽ đồng thời trên biểu đồ biến động vốn (Equity Curve):
    1. **Đường vốn Chiến lược (Strategy Equity)**.
    2. **Đường vốn Nắm giữ thụ động (Buy & Hold Equity)** của chính cổ phiếu đó.
    3. **Đường chỉ số VN-Index chuẩn hóa** (khởi điểm quy về 100 hoặc mức vốn ban đầu).
  - Giúp nhà đầu tư và chuyên gia nhận diện ngay lập tức chiến lược đang sinh Alpha dương hay thua kém thị trường chung.

### Feature 5: Đấu nối Dữ liệu Thực cho Paper Trading (Forward Testing)
- **Kết nối Supabase:**
  - Nối Subtab 3 với bảng `quant_signals` trên Supabase để kéo danh mục các lệnh ảo đã phát sinh trong các phiên gần nhất.
- **Tính toán Implementation Shortfall thực:**
  - Tự động lấy giá đóng cửa hoặc giá khớp thực tế trong phiên để tính độ lệch giá (Slippage/Shortfall theo bps) so với giá khuyến nghị ban đầu của bot.
  - Hiển thị bảng đối soát minh bạch: Mã, Ngày khuyến nghị, Giá đề xuất, Giá khớp ảo, Mức trượt giá, Lãi/lỗ tạm tính.

### Feature 6: Tối ưu Trải nghiệm Nhập liệu & Giao diện (UX/UI Enhancements)
- **Định dạng số tiền:**
  - Thêm định dạng hiển thị phân tách dấu phẩy hàng nghìn cho ô nhập vốn ban đầu (ví dụ: hiển thị `100,000,000 VND`).
  - Cho phép người dùng nhập nhanh bằng các nút gợi ý: `50 Triệu`, `100 Triệu`, `500 Triệu`, `1 Tỷ`.
- **Cảnh báo giới hạn mô phỏng chuẩn mực CFA:**
  - Đặt banner khuyến cáo minh bạch: *"Hiệu suất quá khứ không đảm bảo kết quả tương lai. Backtest đã trừ phí 0.15%, thuế 0.1%, trượt giá 15 bps và giới hạn trần HOSE. Không phản ánh tác động thị trường của quy mô vốn lớn."*

---

## 4. ĐỊNH HƯỚNG VÀ RÀNG BUỘC KỸ THUẬT (TECHNICAL CONSTRAINTS)

- **Bộ tiêu chuẩn chất lượng SonarCloud:**
  - Độ phức tạp nhận thức (Cognitive Complexity) của mọi hàm mới phải **$< 15$** (S3776).
  - Xử lý ngoại lệ chuẩn: dùng `logging.exception("...")` trong khối except (S8572).
  - Không trùng lặp chuỗi ký tự $\ge 3$ lần (S1192).
  - Sắp xếp import theo Ruff / isort tiêu chuẩn (Ruff I001).
  - Độ bao phủ kiểm thử (Test Coverage) cho các hàm tính toán mới phải $\ge 80\%$.
- **Nguyên tắc Kiểm định Định lượng (Quant Guardrails):**
  - **Point-in-Time Data:** Dữ liệu BCTC dùng cho F-Score/Z-Score chỉ được nạp tại thời điểm báo cáo đã công bố, tuyệt đối không rò rỉ dữ liệu tương lai (Look-ahead Bias).
  - **Zero LLM Backtest:** Tuyệt đối không gọi API LLM trong vòng lặp backtest; chỉ kiểm tra lõi logic định lượng xác định (Deterministic Quant Rules).
  - **Chống Overfitting:** Nghiêm cấm hành vi tinh chỉnh tham số tùy tiện chỉ để đường vốn một mã (như VIC) trông đẹp mắt. Báo cáo phải phản ánh trung thực cả những nhịp sụt giảm trong thị trường Sideways/Downtrend.
- **An toàn Môi trường Test:**
  - 100% unit tests liên quan đến Backtest, Paper Trading và Alerts phải được mock I/O triệt để, không phát sinh network request ra Discord/Telegram.

---

## 5. YÊU CẦU PHI CHỨC NĂNG (NON-FUNCTIONAL REQUIREMENTS)

- **Hiệu năng (Performance):**
  - Thời gian chạy Backtest 1 năm kèm bóc tách Regime và Benchmark VN-Index phải hoàn tất trong **$< 3.5$ giây**.
- **Tính Minh bạch & Khách quan (Auditability):**
  - Mọi giao dịch ảo và chỉ số đo lường (CAGR, Sharpe, Max Drawdown, Alpha, Beta) phải có công thức toán học minh bạch, sẵn sàng xuất báo cáo PDF/Markdown chuẩn mực cho nhà đầu tư tổ chức.
- **Ngôn ngữ:** 100% Tiếng Việt chuẩn Unicode, thuật ngữ tài chính chuẩn mực (CFA / UBCKNN).

---

## 6. LỊCH SỬ RỦI RO & BÀI HỌC XƯƠNG MÁU (KNOWN RISKS & LESSONS LEARNED)

*Bài học từ v1.0 — v3.1 (Vẫn duy trì hiệu lực):*
1. **Sự cố dữ liệu BCTC đóng băng (Stale Data Incident):** Dữ liệu cũ quá 2 quý phải bị khóa khuyến nghị (`recommendation_allowed = False`).
2. **Bẫy thanh khoản cổ phiếu nhỏ (Penny Liquidity Trap):** ADV20 < 300k cấm khuyến nghị tỷ trọng lớn.
3. **Ảo giác AI & FOMO Đỉnh sóng:** Luôn có bộ lọc trọng tài PM Arbitration chặn lệnh khi RSI > 75.
4. **Bội chi Token LLM (Token Cost Runaway):** Lọc trước bằng code Python (0 token), chỉ gửi dữ liệu nén cho LLM.
5. **Look-ahead bias trong Backtest:** Chỉ dùng dữ liệu Point-in-time cho BCTC, không backtest phần LLM.
6. **Đứt gãy Liên kết Web $\rightarrow$ Discord:** Tín hiệu Mua quan trọng trên Web phải đồng thời bắn về Discord DM của Client.
7. **Rò rỉ Môi trường Test ra Kênh Thật:** 100% test case bắt buộc phải mock toàn bộ I/O bên ngoài.
8. **Spam Thông báo Thanh lọc:** Chỉ quét dọn Watchlist duy nhất 1 lần trước ATO (08:45).

*Bài học MỚI từ sự cố kiểm thử v3.1 & Báo cáo Đánh giá Chuyên sâu:*
9. **Lỗi "Đồng hồ đo sai" (Dead Metrics Trap — Beta luôn bằng 1.0):**
   - *Bài học:* Khi không truyền dữ liệu Benchmark vào Engine, các chỉ số rủi ro cốt lõi (Alpha, Beta) bị tê liệt và trả về mặc định. Việc này dẫn đến kết luận sai lầm về mức độ rủi ro hệ thống của cổ phiếu (ví dụ: VIC High-Beta nhưng bị coi như trung tính). **Mọi kiểm định định lượng bắt buộc phải có chuỗi Benchmark thị trường thật đi kèm.**
10. **Nghịch lý "Xe đua F1 gắn bánh xe đạp" (Strategy Mismatch in Backtest):**
    - *Bài học:* Đánh giá một hệ thống phân tích phức hợp (TA + FA + Risk Gate) bằng một chiến lược MA crossover thô sơ sách giáo khoa là sai lầm nghiêm trọng. Chiến lược MA crossover liên tục bị whipsaw ở các cổ phiếu High-Beta, dẫn đến kết quả backtest lỗ nặng (-30%) dù cổ phiếu tăng +67%. **Engine Backtest phải phản ánh đúng chiến lược Quant Core mà hệ thống thực tế đang vận hành.**
11. **Lỗi logic tự quy chiếu trong phân loại Regime (Regime Tautology):**
    - *Bài học:* Dùng nến của chính cổ phiếu để phân loại trạng thái thị trường (Regime) là sai về phương pháp luận tài chính. Trạng thái thị trường (Uptrend/Downtrend/Sideways) phải được xác định từ **chỉ số toàn thị trường (VN-Index)** để đo lường khả năng thích ứng của chiến lược trong từng hoàn cảnh vĩ mô.
12. **Bẫy Overfitting & Tâm lý "Làm đẹp số liệu":**
    - *Bài học:* Tuyệt đối không điều chỉnh tham số hồi quy để "làm đẹp" đường vốn của một mã riêng biệt. Một hệ thống định lượng chuyên nghiệp chứng minh được lý do tại sao nó chịu drawdown trong thị trường đi ngang (Sideways) có giá trị thực tế cao hơn gấp nhiều lần một đường cong vốn tăng trưởng thẳng tắp nhưng bị nghi ngờ overfitting.
