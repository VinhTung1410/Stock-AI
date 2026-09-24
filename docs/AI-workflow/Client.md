# 🎯 YÊU CẦU DỰ ÁN (CLIENT BRIEF)

**Tên dự án:** Stock-AI / AI Trading Bot  
**Ngày tạo:** 2026-09-24 | **Cập nhật:** 2026-09-24  
**Người yêu cầu (Client):** Tùng  
**Phiên bản yêu cầu:** v4.1 — Chuẩn hóa Thước đo Backtest, Lõi Chiến lược Regime-First Alignment, Quản trị Rủi ro & Tích hợp Smart Money Flow Tracking  

---

## 1. TỔNG QUAN DỰ ÁN (EXECUTIVE SUMMARY)

- **Kế thừa thành quả các phiên bản trước:**
  - Hạ tầng cứng Backtest đã mô phỏng chuẩn xác cơ chế HOSE (trần/sàn ±7%, quy chế T+2.5, thuế phí 0.25%, trượt giá 15 bps, trần hấp thụ thanh khoản 5% ADV20, Audit Trail Supabase).
  - Tích hợp thành công giao diện Tab 6 (Backtest Dashboard, Bảng số liệu Regime, Paper Trading).
  - Hoàn thiện luồng Web-to-Discord hook cho khuyến nghị MUA và cô lập 100% mock Discord trong bộ kiểm thử tự động (Zero Test Leakage).

- **Định vị lại triết lý cốt lõi của Client & Ban Cố vấn Tài chính (Paradigm Shift):**
  1. **Bản chất của Backtest không phải là PnL tĩnh:** Mục tiêu tối thượng của backtest không phải là tìm kiếm một con số lợi nhuận (PnL/CAGR) đẹp nhân tạo hay phán xét bot đúng/sai một vài deal đơn lẻ, mà là **đo lường năng lực nương theo pha thị trường (Market Regime Alignment)**:
     - Trong **Uptrend (Bull Market):** Bot có nhận diện được sóng lớn, kiên nhẫn để lãi chạy (ride the trend), hạn chế chốt non?
     - Trong **Sideways/Choppy:** Bot có né được các bẫy tín hiệu giả (whipsaw)?
     - Trong **Downtrend/Crash:** Bot có phát tín hiệu **Phòng thủ triệt để (Cash Mode)** để bảo toàn vốn trước các đợt sập khốc liệt của VN-Index hay không?
  2. **Giải mã ý tưởng "Nương theo Quỹ đầu tư (Smart Money Tracking)":**
     - *Điểm mù của việc đọc tin tức/báo cáo quỹ truyền thống:* Báo cáo tháng (Monthly Factsheet) hoặc tin tức quỹ mua mới có độ trễ lớn (T+30 đến T+45) — khi tin ra giá đã chạy hoặc quỹ chuẩn bị chốt lời (Exit Liquidity). Đồng thời quỹ tương hỗ bị ràng buộc pháp lý luôn giữ 80-95% cổ phiếu nên **quỹ không thể giúp nhà đầu tư né sập** (năm 2022 NAV quỹ sụt giảm -30% đến -40%).
     - *Chuyển hóa thành Lợi thế Cạnh tranh Định lượng (Institutional Edge):* Danh mục mua của quỹ chỉ dùng làm **Bộ lọc Watchlist Cơ bản uy tín** (đã qua kiểm toán, thanh khoản chuẩn). Điểm kích hoạt lệnh (Trigger) phải chuyển sang theo dõi **Dòng tiền Khối ngoại & Tự doanh hàng ngày (End-of-Day Net Flow)** và **Giao dịch Thỏa thuận đột biến (Block Trade)** theo thời gian thực.
  3. **Đảo ngược Kiến trúc Thực thi (Regime-First Architecture):**
     - Chuyển từ mô hình thụ động: `Tín hiệu Kỹ thuật -> Lọc Regime (hậu kiểm)` sang quy trình quỹ chuẩn mực:
     ```
     [1. Macro Regime Gate] ──> [2. Smart Money Watchlist] ──> [3. Quant Trigger] ──> [4. Dynamic Risk Sizing] ──> [5. Execution]
     ```

- **Mục tiêu phiên bản 4.1:**
  1. **Chuẩn hóa thước đo định lượng:** Nạp chuỗi dữ liệu VN-Index làm Benchmark để tính toán chính xác Alpha, Beta thực của từng mã cổ phiếu và vẽ đường so sánh Buy & Hold trực quan.
  2. **Chuẩn hóa bộ phân loại Regime theo VN-Index:** Xác định trạng thái thị trường dựa trên VN-Index thay vì từng mã riêng lẻ; linh hoạt ngưỡng nến để bảng 4 cột hiển thị đầy đủ dữ liệu Uptrend/Downtrend/Sideways.
  3. **Xây dựng chiến lược lõi "Quant Core Strategy":** Đưa bộ tiêu chí thực tế của hệ thống (F-Score $\ge 6$, MoS $\ge 15\%$, Z-Score $> 1.8$, RSI $< 70$, Hard Gates & ATR Stop-loss) vào làm chiến lược kiểm thử chính.
  4. **Kích hoạt Chốt chặn Vĩ mô (Macro Circuit Breaker / Cash Mode):** Tự động khóa toàn bộ lệnh Mua khi VN-Index gãy MA50/MA200 hoặc Market Breadth xấu, bảo toàn vốn tuyệt đối khi thị trường sập.
  5. **Mô-đun Theo dõi Dòng tiền Thông minh (Smart Money Flow Engine):** Tích hợp dữ liệu gom/xả ròng EOD của Khối ngoại và Tự doanh làm bộ lọc xác nhận tín hiệu.
  6. **Cơ chế Quản trị Vốn Thu hẹp Drawdown (Drawdown-Controlled Sizing):** Giảm 50% quy mô vị thế khi gặp chuỗi thua liên tiếp (Losing Streak).
  7. **Kết nối luồng Forward Testing (Paper Trading) với Supabase:** Hiển thị danh mục lệnh ảo phát sinh từ tín hiệu thực tế của bot để kiểm chứng trượt giá.
  8. **Hoàn thiện UX:** Định dạng số tiền nhập liệu trực quan (`100,000,000 VND`).

---

## 2. CHÂN DUNG NGƯỜI DÙNG (USER PERSONAS)

- **Nhóm 1 (Nhà đầu tư cá nhân / Client):**
  - Cần đánh giá trung thực: "Hệ thống này có thực sự giúp tôi giữ tiền, thoát khỏi các đợt sập như năm 2022 và kiếm lời bền vững khi vào sóng tăng không?".
  - Cần số liệu Beta, Alpha, Winrate, Max Drawdown chính xác để biết mức độ rủi ro của từng mã.
  - Cần công cụ cảnh báo "Đứng ngoài - Ôm tiền mặt (Cash Mode)" để chống lại tâm lý ngứa tay mua đuổi khi thị trường chung đang downtrend.
  - Cần giao diện nhập số tiền thân thiện, dễ đọc, có dấu phẩy ngăn cách hàng nghìn.
- **Nhóm 2 (Chuyên gia Quản lý Quỹ & Tư vấn Đầu tư Lão luyện):**
  - Đòi hỏi quy trình kỷ luật: **Regime-First** (Thị trường quyết định tỷ trọng, cổ phiếu quyết định điểm vào).
  - Cần bóc tách hiệu quả chiến lược theo từng Regime thị trường (thắng ở Uptrend, bảo toàn vốn ở Downtrend, phòng ngừa whipsaw ở Sideways).
  - Đánh giá chất lượng tín hiệu qua mức độ đồng thuận của 3 tầng: Vĩ mô (Regime) + Dòng tiền tổ chức (Smart Money Flow) + Kỹ thuật định lượng (Quant Trigger).
  - Cần cơ chế kiểm soát rủi ro thích ứng (Adaptive Drawdown Sizing) và kiểm tra thanh khoản thực tế (`ADV20 >= 10x OrderSize`).

---

## 3. TÍNH NĂNG CỐT LÕI (CORE FEATURES - MUST HAVE - v4.1)

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
    3. **Đường chỉ số VN-Index chuẩn hóa** (khởi điểm quy về mức vốn ban đầu).
  - Giúp nhận diện rõ: Khi thị trường sụp đổ, đường vốn chiến lược có đi ngang (giữ tiền) trong khi Buy & Hold và VN-Index cắm đầu hay không.

### Feature 5: Chốt chặn Vĩ mô & Chế độ Phòng thủ (Macro Circuit Breaker / Cash Mode)
- **Cơ chế bảo vệ tài khoản khỏi sập:**
  - Khi VN-Index gãy MA50 ngày hoặc độ dốc MA200 quay đầu giảm (Xác nhận Downtrend Regime):
    - **Hard Stop:** Khóa 100% quyền mở vị thế mua mới (`allow_new_entries = False`).
    - **Khuyến nghị thoái vốn:** Kích hoạt trailing stop chủ động hạ tỷ trọng cổ phiếu về $0 - 30\%$, ưu tiên bảo toàn vốn.
  - Triết lý: *"Cash is a position"* — Đứng ngoài trong downtrend là một quyết định đầu tư chủ động xuất sắc nhất.

### Feature 6: Tích hợp Dòng tiền Thông minh (Smart Money Flow & Whale Watchlist)
- **Whale Watchlist (Bộ lọc Cơ bản):**
  - Danh mục cổ phiếu mua mới từ báo cáo của các quỹ lớn (Dragon Capital, VinaCapital, Pyn Elite...) được đưa vào Watchlist nền tảng (chứng thực về thanh khoản và nội tại).
- **Tín hiệu Dòng tiền Real-time (EOD Flow Confirmation):**
  - Không mua theo tin tức trễ. Hệ thống theo dõi chuỗi mua ròng hàng ngày của **Khối ngoại & Tự doanh**:
  - Tín hiệu mua hợp lệ khi: Xuất hiện chuỗi mua ròng liên tiếp 3 - 5 phiên với khối lượng đột biến tại vùng tích lũy/breakout nền giá.

### Feature 7: Quản trị Vốn Thích ứng & Kiểm soát Drawdown (Drawdown-Controlled Sizing)
- **Cơ chế Co lại Quy mô Vị thế:**
  - Nếu hệ thống dính 2 lệnh thua liên tiếp hoặc tài khoản chạm mức drawdown tạm thời $> 5\%$: Tự động hạ quy mô lệnh xuống $50\%$ so với mức tính toán của Half-Kelly.
  - Ngăn ngừa triệt để tâm lý "gỡ gạc" (Revenge Trading) của nhà đầu tư cá nhân.
- **Ràng buộc Thanh khoản Thực tế:**
  - Kiểm tra `ADV20 >= 10x OrderSize` trước khi phát tín hiệu để đảm bảo lệnh thực tế không tự đẩy giá hoặc kẹt thanh khoản.

### Feature 8: Đấu nối Dữ liệu Thực cho Paper Trading (Forward Testing)
- **Kết nối Supabase:**
  - Nối Subtab 3 với bảng `quant_signals` trên Supabase để kéo danh mục các lệnh ảo đã phát sinh trong các phiên gần nhất.
- **Tính toán Implementation Shortfall thực:**
  - Tự động lấy giá đóng cửa hoặc giá khớp thực tế trong phiên để tính độ lệch giá (Slippage/Shortfall theo bps) so với giá khuyến nghị ban đầu của bot.

### Feature 9: Tối ưu Trải nghiệm Nhập liệu & Giao diện (UX/UI Enhancements)
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
  - **Chống Overfitting:** Nghiêm cấm hành vi tinh chỉnh tham số tùy tiện chỉ để đường vốn một mã trông đẹp mắt. Báo cáo phải phản ánh trung thực cả những nhịp sụt giảm trong thị trường Sideways/Downtrend.
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

*Bài học MỚI từ v3.1 — v4.1 & Đối thoại cùng Quản lý Quỹ:*
9. **Lỗi "Đồng hồ đo sai" (Dead Metrics Trap — Beta luôn bằng 1.0):**
   - Không truyền dữ liệu Benchmark làm tê liệt Alpha, Beta. Mọi kiểm định định lượng bắt buộc phải có chuỗi Benchmark VN-Index thật đi kèm.
10. **Nghịch lý "Xe đua F1 gắn bánh xe đạp" (Strategy Mismatch in Backtest):**
    - Đánh giá hệ thống phức hợp bằng chiến lược MA thô sơ dẫn đến kết quả sai lệch hoàn toàn. Engine Backtest phải phản ánh đúng chiến lược Quant Core.
11. **Lỗi logic tự quy chiếu trong phân loại Regime (Regime Tautology):**
    - Phải xác định trạng thái thị trường từ **chỉ số toàn thị trường (VN-Index)**, không lấy nến từng mã riêng lẻ.
12. **Bẫy Overfitting & Tâm lý "Làm đẹp số liệu":**
    - Đo lường khả năng thích ứng thị trường và bảo toàn vốn có giá trị cao gấp nhiều lần một đường vốn tăng trưởng dốc đứng do "nắn nót" tham số.
13. **Cạm bẫy "Bắt chước Quỹ" (Fund Copycat Trap) & Độ trễ Báo cáo:**
    - Tin tức và báo cáo tháng của quỹ có độ trễ lớn (T+30 đến T+45). Mua theo tin tức quỹ dễ biến nhà đầu tư thành thanh khoản chốt lời (Exit Liquidity). Quỹ không giúp né sập thị trường vì họ bị ràng buộc luật giữ 80-95% cổ phiếu. Danh mục quỹ chỉ được dùng làm Watchlist nội tại, quyết định vào lệnh phải do Dòng tiền EOD + Kỹ thuật xác nhận.
14. **Tư duy Regime Alignment — "Bảo toàn vốn trước khi tìm kiếm lợi nhuận":**
    - Thước đo bot tốt không phải là PnL tĩnh, mà là sự nhịp nhàng với thị trường: Vào sóng mạnh trong Uptrend, và tuyệt đối kích hoạt **Cash Mode** đứng ngoài khi Downtrend để né trọn các đợt sập lịch sử.
15. **Hành vi "Trả thù thị trường" (Revenge Trading Trap):**
    - Phải áp dụng cơ chế tự động hạ $50\%$ quy mô vốn sau chuỗi thua liên tiếp (Drawdown-Controlled Sizing) để cứu nhà đầu tư khỏi sự phá vỡ kỷ luật giao dịch.

