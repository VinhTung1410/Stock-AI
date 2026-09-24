# 🎯 YÊU CẦU DỰ ÁN (CLIENT BRIEF)

**Tên dự án:** Stock-AI / AI Trading Bot  
**Ngày tạo:** 2026-09-24  
**Người yêu cầu (Client):** Tùng  
**Phiên bản yêu cầu:** v3.0 — Kiểm chứng Hiệu suất & Vận hành  

---

## 1. TỔNG QUAN DỰ ÁN (EXECUTIVE SUMMARY)

- **Vấn đề hiện tại (Pain points):**
  1. **Không có bằng chứng hiệu suất:** Hệ thống Stock-AI đã có kiến trúc phòng thủ tốt (Data Gate, Sanity Check, Portfolio Guard, PM Arbitration) nhưng chưa có bất kỳ con số nào chứng minh nó kiếm được tiền — không có Sharpe Ratio, Max Drawdown, so sánh với VN-Index. Người ngoài không phân biệt được "hệ thống tốt" với "hệ thống chỉ trông có vẻ tốt".
  2. **Ngưỡng/trọng số cứng chưa được kiểm chứng:** Ngưỡng 70 điểm conviction, trọng số 40/25/20/15 cho 4 trụ phân tích, cooldown 5 ngày, tối đa 2 BUY/ngày, tối đa 8 vị thế — tất cả đều chưa có giải thích thực nghiệm. Nếu đổi thành 60 hoặc 80, kết quả thay đổi thế nào?
  3. **Chưa đo chênh lệch giá lý thuyết vs giá khớp thực tế:** Tín hiệu phát ra ở giá X, nhưng lệnh thực tế khớp ở giá nào? Trượt bao nhiêu bps? Bao nhiêu lệnh không khớp được (kịch trần, thanh khoản mỏng)?
  4. **Ranh giới "copilot" vs "bot tự động" chưa rõ:** Tài liệu gọi là copilot (hỗ trợ quyết định) nhưng `trading_bot.py` chạy 24/7 tự động phát tín hiệu. Hai mức độ này có yêu cầu kiểm chứng và rủi ro rất khác nhau.

- **Giải pháp mong muốn:** Xây dựng **2 tính năng kiểm chứng** để chuyển hệ thống từ giai đoạn "xây dựng" sang giai đoạn "chứng minh":
  1. **Backtest theo từng giai đoạn thị trường (Regime Backtest):** Chạy backtest lõi định lượng trên dữ liệu lịch sử, phân tách kết quả theo Uptrend / Downtrend / Sideways, bao gồm đầy đủ chi phí giao dịch và mô phỏng đặc thù HOSE.
  2. **Forward Testing / Paper Trading 3-6 tháng:** Chạy hệ thống trên dữ liệu thực, ghi nhận tín hiệu bất biến trước khi biết kết quả, đo trượt giá (Implementation Shortfall) và so sánh với backtest.

---

## 2. CHÂN DUNG NGƯỜI DÙNG (USER PERSONAS)

- **Nhóm 1 (Nhà đầu tư cá nhân / Client):** Cần biết hệ thống có lời hay lỗ qua các giai đoạn thị trường khác nhau trước khi tin tưởng cấp vốn thật. Muốn thấy bảng kết quả backtest rõ ràng (đường vốn, drawdown, so sánh VN-Index) và báo cáo paper trading hàng tháng. Cần cảnh báo khi hệ thống vi phạm tiêu chí đạt/không đạt.
- **Nhóm 2 (Nhà quản lý danh mục / Người đánh giá bên ngoài):** Cần xem báo cáo backtest tách theo regime, kiểm tra không có look-ahead bias, đánh giá khoảng tin cậy thống kê. Cần thấy sự trung thực: kết quả xấu + phân tích nguyên nhân thuyết phục hơn đường vốn hoàn hảo.

---

## 3. TÍNH NĂNG CỐT LÕI (CORE FEATURES - MUST HAVE)

### Feature 1: Engine Backtest theo Regime (Regime Backtest Engine)
- Xây dựng mô-đun phân loại giai đoạn thị trường bằng quy tắc khách quan (VN-Index so với MA200 + độ dốc MA200, hoặc lợi suất N tháng cuộn + biến động), cố định trước khi xem kết quả.
- Backtest **chỉ phần lõi định lượng** (quant_engine, quant_valuation, conviction score, các rào chắn). **KHÔNG backtest phần LLM** do rò rỉ dữ liệu huấn luyện.
- Mô phỏng đầy đủ đặc thù HOSE:
  - Biên độ giá ±7% (HNX ±10%, UPCoM ±15%): lệnh mua khi giá kịch trần KHÔNG khớp.
  - T+2.5: cổ phiếu mua không bán được trong T, T+1, sáng T+2. Đếm theo ngày giao dịch (bỏ cuối tuần + ngày lễ).
  - Phí môi giới hai chiều + thuế bán (dùng mức phí thực tế).
  - Thanh khoản: giới hạn kích thước lệnh theo % ADV20 (tái sử dụng từ Data Gate).
  - Quy tắc khớp thận trọng: khớp ở giá bất lợi, không khớp khi kịch trần/sàn.
- Báo cáo đầy đủ theo regime: CAGR, Max Drawdown, thời gian phục hồi, Sharpe, Sortino, Calmar, Win Rate, Profit Factor, Expectancy, MFE/MAE, Alpha/Beta so với VN-Index & VN30, số lệnh mỗi regime, khoảng tin cậy bootstrap.
- Kiểm tra độ bền: độ nhạy tham số (thử ngưỡng 60/70/80, trọng số khác nhau), walk-forward, hai định nghĩa regime khác nhau.

### Feature 2: Hệ thống Forward Testing / Paper Trading
- Đóng băng phiên bản mã và tham số khi bắt đầu (git tag). Nếu sửa logic giữa chừng, ghi rõ ranh giới phiên bản.
- Tận dụng snapshot bất biến (`signals`) trong Supabase đã có: ghi thời điểm tín hiệu, giá quyết định, giá thị trường tại lúc đó — tất cả **trước khi biết kết quả**.
- Giữ nguyên 100% quy tắc hiện tại: 2 BUY/ngày, Portfolio Guard, cooldown 5 ngày, 8 vị thế tối đa.
- Chạy tối thiểu 3 tháng, lý tưởng 6 tháng. **Bắt đầu ghi nhận dữ liệu song song với backtest** vì thời gian trôi không mua lại được.
- Báo cáo hàng tháng: đường vốn giả lập, drawdown, so sánh với backtest cùng giai đoạn.

### Feature 3: Đo Implementation Shortfall (Trượt giá & Chất lượng Thực thi)
- Trượt giá vào lệnh: (giá khớp giả lập − giá quyết định) / giá quyết định, tính bằng bps.
- Trượt giá ra lệnh: tương tự cho lệnh bán / cắt lỗ.
- Tỷ lệ khớp: số lệnh khớp / số lệnh phát tín hiệu.
- Phân tích tín hiệu bị bỏ lỡ: lợi nhuận của các lệnh không khớp được (kiểm tra thiên lệch).
- Độ trễ: thời gian từ tín hiệu đến lệnh có thể thực thi (đặc biệt tại 08:45 / 11:30 / 14:45).
- So sánh chênh lệch lợi nhuận paper trading vs backtest cho cùng giai đoạn.

### Feature 4: Ablation — So sánh "Chỉ Quant" vs "Quant + AI"
- Chạy song song 2 nhánh trong Forward Testing: (a) chỉ lõi định lượng, (b) lõi + LLM diễn giải.
- Đo xem phần LLM có thực sự cải thiện kết quả hay không.
- Nếu LLM không cải thiện, ghi nhận trung thực: nó vẫn có giá trị giải thích nhưng không phải nguồn alpha.

---

## 4. ĐỊNH HƯỚNG VÀ RÀNG BUỘC KỸ THUẬT (TECHNICAL CONSTRAINTS)

- **Tech Stack:** Python 3.10+, Streamlit, Vnstock (>= 4.0.6), Supabase PostgreSQL, Apache ECharts.
- **Tích hợp:** Discord Webhook (cảnh báo kết quả paper trading hàng tháng), Supabase (lưu snapshot tín hiệu + kết quả backtest).
- **Quy chuẩn chất lượng:** SonarCloud (Cognitive Complexity < 15, S8572 logging.exception, Ruff I001), Unit Test Coverage >= 80% trên mọi mô-đun mới (backtest engine, regime classifier, shortfall tracker).
- **Ngân sách hạ tầng:** Ưu tiên Supabase Free Tier + Streamlit Community Cloud. Chi phí API Gemini tối đa 10$/tháng. Backtest chạy offline (không cần API).
- **Ràng buộc đặc thù cho Backtest:**
  - Dùng dữ liệu **point-in-time** cho BCTC: chỉ "nhìn thấy" báo cáo tài chính sau ngày công bố (cộng thêm độ trễ an toàn). Nếu không có point-in-time, ghi rõ đây là giới hạn.
  - Bao gồm cả mã bị hủy niêm yết / đình chỉ (chống survivorship bias). Nếu dữ liệu không đủ, ghi rõ.
  - Chia dữ liệu: in-sample / out-of-sample / validation. Dùng walk-forward, kết quả OOS không được sụp đổ so với IS.
- **Ràng buộc đặc thù cho Paper Trading:**
  - Đóng băng phiên bản (git tag) khi bắt đầu.
  - Quy tắc khớp giả lập phải thận trọng (giá bất lợi, không khớp kịch trần/sàn, giới hạn % thanh khoản).
  - Áp mức haircut cho kết quả vì paper trading không tạo tác động thị trường.

---

## 5. YÊU CẦU PHI CHỨC NĂNG (NON-FUNCTIONAL REQUIREMENTS)

- **Tái lập được (Reproducibility):** Ghi rõ phiên bản mã (git commit hash), khoảng thời gian dữ liệu, tham số hệ thống trong mỗi báo cáo để người khác tái lập kết quả.
- **Trung thực (Honesty):** Báo cáo cả kết quả xấu. Một báo cáo nói "hệ thống thua lỗ trong sideways vì lý do X, đã điều chỉnh Y" có giá trị hơn đường vốn tăng hoàn hảo (nguy cơ overfitting).
- **Độ tin cậy:** 100% dữ liệu phải qua Data Gate. Nếu dữ liệu bất thường → từ chối, không đưa số liệu ảo.
- **Ngôn ngữ:** 100% Tiếng Việt chuẩn Unicode, không dùng chữ Hán/tiếng Trung.
- **Tiêu chí đạt/không đạt (đặt TRƯỚC khi chạy, KHÔNG chỉnh sau):**

| Nhóm | Tiêu chí |
|---|---|
| **Rủi ro** | Max Drawdown paper trading không vượt ngưỡng X% (Client tự đặt trước) |
| **Nhất quán** | Lợi nhuận paper trading nằm trong khoảng chấp nhận được so với backtest cùng giai đoạn |
| **Thực thi** | Trượt giá trung bình dưới N bps; tỷ lệ khớp trên M% |
| **Vận hành** | Không có sự cố dữ liệu/hạ tầng chưa xử lý; không vi phạm rào chắn (vượt 8 vị thế, quá 2 BUY/ngày) |
| **Hành vi** | Không có lệnh nào phát ra khi Data Gate / Sanity Check lẽ ra phải chặn |

- **Thời hạn kỳ vọng:**
  - Backtest Engine: hoàn thành dev + QA trong 2-4 tuần.
  - Paper Trading: bắt đầu ghi nhận dữ liệu ngay (song song backtest), chạy chính thức 3-6 tháng.
  - Ablation: chạy song song trong giai đoạn paper trading.

---

## 6. LỊCH SỬ RỦI RO & BÀI HỌC XƯƠNG MÁU (KNOWN RISKS & LESSONS LEARNED)

*Bài học cũ (vẫn còn hiệu lực):*

1. **Sự cố dữ liệu BCTC đóng băng (Stale Data Incident):**
   - *Bài học:* Dữ liệu của một số mã lớn (ví dụ VCB) từng bị kẹt ở BCTC nhiều năm trước, dẫn đến tính P/B ảo (4.06x). Client yêu cầu: Bất kỳ mã nào có BCTC cũ quá 2 quý PHẢI bị khóa khuyến nghị (`recommendation_allowed = False`). Thà không có số liệu còn hơn số liệu sai.
   - *Ảnh hưởng đến backtest:* Phải dùng point-in-time data. Nếu dùng BCTC theo ngày kết thúc kỳ thay vì ngày công bố → look-ahead bias nghiêm trọng.
2. **Bẫy thanh khoản cổ phiếu nhỏ (Penny Liquidity Trap):**
   - *Bài học:* Các mã thanh khoản dưới 300k cp/phiên (ADV20 < 300k) khi thị trường giảm rất dễ "trắng bên mua". Cấm khuyến nghị mua lướt sóng hoặc tỷ trọng lớn với nhóm này.
   - *Ảnh hưởng đến backtest:* Giới hạn kích thước lệnh theo % ADV20 trong mô phỏng, không mặc định khớp hết.
3. **Ảo giác AI & FOMO Đỉnh sóng:**
   - *Bài học:* AI LLM đọc tin tức tích cực có xu hướng hưng phấn quá đà khi cổ phiếu đã tăng nóng (RSI > 75). Phải luôn có PM Arbitration để chặn lệnh FOMO.
   - *Ảnh hưởng đến backtest:* KHÔNG backtest phần LLM. Dùng ablation trong Forward Testing để đánh giá trung thực.
4. **Bội chi Token LLM (Token Cost Runaway):**
   - *Bài học:* Gửi toàn bộ dữ liệu thô hàng nghìn dòng vào prompt làm tăng vọt chi phí API. Phải lọc trước bằng code Python (0 token) và chỉ gửi dữ liệu tóm tắt tinh gọn cho LLM.

*Rủi ro MỚI liên quan đến Backtest & Paper Trading:*

5. **Look-ahead bias trong F-Score/Z-Score (Bẫy nguy hiểm nhất):**
   - *Rủi ro:* Piotroski F-Score, Altman Z-Score dùng dữ liệu BCTC. Nếu dùng số liệu quý theo ngày kết thúc kỳ thay vì ngày công bố, backtest "biết trước" kết quả → số liệu đẹp nhưng vô giá trị.
   - *Xử lý:* Dùng dữ liệu point-in-time. Nếu không có, ghi rõ giới hạn, không tuyên bố kết quả là sạch.
6. **Overfitting ngưỡng/trọng số (Data Snooping):**
   - *Rủi ro:* Ngưỡng 70, trọng số 40/25/20/15, cooldown 5 ngày... nếu được "chỉnh cho ra kết quả đẹp" trên in-sample thì OOS sẽ sụp đổ.
   - *Xử lý:* Chia dữ liệu nghiêm ngặt, walk-forward, báo cáo độ nhạy tham số. Một con số đẹp nhưng sai còn tệ hơn không có con số.
7. **Kích thước mẫu nhỏ (Low Trade Count):**
   - *Rủi ro:* Với tối đa 2 BUY/ngày + cooldown 5 ngày, mỗi regime có thể chỉ có vài chục lệnh. Dưới ~30 lệnh rất khó kết luận thống kê.
   - *Xử lý:* Báo cáo số lệnh mỗi regime + khoảng tin cậy bootstrap. Tách rõ "kết luận vận hành" (đủ tin cậy) vs "kết luận hiệu suất" (cần thời gian dài hơn).
8. **Paper trading chỉ phủ 1 regime:**
   - *Rủi ro:* 3-6 tháng có thể rơi vào chỉ uptrend hoặc sideways. Không kiểm chứng được 2 regime còn lại.
   - *Xử lý:* Ghi rõ regime đã phủ, không ngoại suy. Kết hợp với kết quả backtest để bù đắp.
