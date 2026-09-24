# 🎯 YÊU CẦU DỰ ÁN (CLIENT BRIEF)

**Tên dự án:** Stock-AI / AI Trading Bot  
**Ngày tạo:** 2026-09-24  
**Người yêu cầu (Client):** Tùng  
**Phiên bản yêu cầu:** v3.1 — Tích hợp UI Backtest/Paper Trading, Nối dây Discord DM & Chuẩn hóa Kênh Cảnh báo  

---

## 1. TỔNG QUAN DỰ ÁN (EXECUTIVE SUMMARY)

- **Vấn đề hiện tại (Pain points):**
  1. **Không có bằng chứng hiệu suất & thiếu giao diện trực quan:** Đã xây dựng xong tầng lõi backend Backtest và Paper Trading (`TASK-0003`) nhưng chưa có giao diện trực quan (UI) trên Streamlit (cả Local và PROD) để người dùng bấm chọn mã, xem biểu đồ đường vốn và bảng số liệu so sánh theo 3 Regime thị trường.
  2. **Đứt gãy kênh cảnh báo Discord DM từ Web:** Khi người dùng phân tích cổ phiếu trên Tab 5 (AI Strategy Analysis) và hệ thống cho tín hiệu MUA rõ ràng (điển hình như trường hợp **TCB ngày 23/09, giá 33k, Target 42.9k, ID 37** lưu trong Supabase), tín hiệu chỉ hiển thị trên màn hình Web và lưu vào Supabase mà **hoàn toàn KHÔNG gửi tin nhắn cảnh báo vào Discord DM** của Client.
  3. **Ô nhiễm dữ liệu kiểm thử (Test Pollution vào Discord DM):** Khi chạy bộ unit test tự động của hệ thống, các hàm gửi alert chưa được cô lập (mock) triệt để, dẫn đến việc bot gửi các mã test lạ (`HOT1`, `HOT2`, `TRAP1`) và kịch bản giả lập (`FPT giá 80k lỗ -20%`) vào Discord DM thật của Client, gây hoang mang và hiểu nhầm về trạng thái danh mục thật.
  4. **Spam thanh lọc Watchlist:** Tính năng dọn dẹp cổ phiếu quá mua/bẫy giá bị kích hoạt nhiều lần hoặc gửi dồn dập trong phiên; Client yêu cầu: **Tính năng thanh lọc cổ phiếu khỏi Watchlist chỉ được thực hiện trước phiên ATO (08:45) và chỉ làm ĐÚNG 1 LẦN DUY NHẤT trong ngày**.
  5. **Ngưỡng/trọng số cứng chưa được kiểm chứng:** Ngưỡng 70 điểm conviction, trọng số 40/25/20/15, cooldown 5 ngày, tối đa 2 BUY/ngày, tối đa 8 vị thế cần được kiểm chứng thực nghiệm qua Backtest và Paper Trading.

- **Giải pháp mong muốn:**
  1. **Tích hợp Dashboard Giao diện UI Backtest & Paper Trading:** Thêm khu vực điều khiển và trực quan hóa trực tiếp trên Streamlit (tích hợp Tab 6 hoặc Tab riêng) hiển thị kết quả 4 cột (FULL, UPTREND, DOWNTREND, SIDEWAYS) và bảng theo dõi lệnh ảo Paper Trading.
  2. **Nối dây tự động Web $\rightarrow$ Discord DM:** Mỗi khi người dùng bấm phân tích mã trên Tab AI mà kết luận là **MUA**, hệ thống tự động phát tin nhắn Rich Embed tóm tắt vào Discord DM của Client.
  3. **Cách ly 100% môi trường kiểm thử (Zero Discord Leak in Tests):** Bắt buộc mock toàn bộ hàm gửi Discord trong test suite, tuyệt đối không để lọt bất kỳ dữ liệu test nào ra ngoài.
  4. **Cố định lịch thanh lọc Watchlist trước ATO:** Chỉ quét dọn Watchlist vào lúc 08:45 sáng (1 lần/ngày), nêu rõ tên mã cổ phiếu thật và lý do định lượng minh bạch.

---

## 2. CHÂN DUNG NGƯỜI DÙNG (USER PERSONAS)

- **Nhóm 1 (Nhà đầu tư cá nhân / Client):** 
  - Cần giao diện trực quan bấm 1 click là chạy được Backtest cho cổ phiếu quan tâm, xem được biểu đồ đường vốn so sánh với VN-Index.
  - Cần nhận được tin nhắn Discord DM ngay lập tức khi phân tích trên Web ra khuyến nghị MUA tốt (như TCB), không bị bỏ lỡ cơ hội.
  - Yêu cầu kênh Discord sạch sẽ: Không nhận tin nhắn rác từ bài test (`HOT1`, `HOT2`, giá ảo) và không bị spam thanh lọc liên tục trong phiên.
- **Nhóm 2 (Nhà quản lý danh mục / Quản trị rủi ro):** Cần đối soát độc lập giữa Backtest lý thuyết và Paper Trading thực tế, kiểm soát trượt giá (Implementation Shortfall), theo dõi nhánh Ablation (Quant Only vs Quant + LLM).

---

## 3. TÍNH NĂNG CỐT LÕI (CORE FEATURES - MUST HAVE)

### Feature 1: Giao diện Trực quan hóa Backtest & Paper Trading (UI Dashboard)
- Tích hợp giao diện người dùng trên Streamlit (`tabs/tab_alpha_tracker.py` hoặc tab chuyên biệt):
  - **Bộ điều khiển Backtest:** Cho phép chọn mã cổ phiếu, khoảng thời gian, phương pháp phân loại Regime (`MA200_SLOPE` hoặc `MOMENTUM_VOLATILITY`), mức vốn ban đầu (mặc định 100 triệu).
  - **Bảng số liệu 4 Cột:** Hiển thị trực quan kết quả bóc tách: `Toàn kỳ (Full)`, `Uptrend`, `Downtrend`, `Sideways` (CAGR, Max Drawdown, Sharpe, Sortino, Win Rate, Expectancy, Alpha/Beta).
  - **Biểu đồ Đường vốn (Equity Curve):** Trực quan hóa biến động NAV so sánh với VN-Index.
  - **Bảng theo dõi Paper Trading:** Hiển thị danh mục lệnh ảo, trạng thái khớp lệnh, tỷ lệ khớp, và mức trượt giá trung bình (bps).

### Feature 2: Nối dây Tín hiệu Mua từ Web sang Discord DM (Web-to-Discord Hook)
- Trong `ai_analyst.py` (hàm `analyze_stock_with_smart_committee`):
  - Khi phân tích hoàn tất và hành động định lượng là **`MUA`** (hoặc `VALUE BUY`, `ACCUMULATE`):
    - Tự động gọi `send_trade_signal_alert()` gửi thông báo Rich Embed trực tiếp vào **Discord DM** của Client.
    - Nội dung tin nhắn: Mã CP, Thị giá hiện tại, Giá Target, Ngưỡng Stop-loss, Điểm F-Score, Biên an toàn MoS (%), và tóm tắt lý do trọng tâm từ Hội đồng định lượng.
    - Đảm bảo các tín hiệu như TCB (ID 37) sẽ lập tức đến tay Client ngay khi bấm phân tích trên Web.

### Feature 3: Cách ly Triệt để Môi trường Kiểm thử (Strict Test Isolation)
- Rà soát và cập nhật 100% các file unit test trong `tests/` (`test_corporate_actions_and_ai.py`, `test_task_0001_watchlist_and_noon.py`, `test_discord_alerts_no_truncation.py`...):
  - Bắt buộc phải mock `send_trade_signal_alert`, `send_watchlist_pruned_alert`, và `send_discord_dm`.
  - Nghiêm cấm chạy test mà phát sinh network request thật đến Discord Webhook/Bot API.
  - Chấm dứt hoàn toàn tình trạng Client nhận tin nhắn `HOT1`, `HOT2`, `TRAP1` hoặc `FPT giá 80k lỗ -20%` khi dev chạy test.

### Feature 4: Chuẩn hóa Lịch Thanh lọc Watchlist (Trước ATO - Duy nhất 1 lần/ngày)
- Cơ chế dọn dẹp cổ phiếu quá mua / dính bẫy giá trong `trading_bot.py`:
  - **Thời điểm kích hoạt:** Duy nhất vào khung giờ chuẩn bị trước phiên ATO (**08:45 sáng**).
  - **Tần suất:** Đúng **1 lần duy nhất trong ngày giao dịch**, nghiêm cấm quét lặp lại gây spam trong phiên liên tục.
  - **Định dạng báo cáo:** Ghi rõ đích danh mã cổ phiếu niêm yết thật, phân biệt rõ mã thủ công vs mã auto, nêu rõ số liệu định lượng (RSI, MoS, bẫy giá) và khuyến nghị vùng giá chờ mua an toàn.

### Feature 5: Đảm bảo Triển khai Đồng bộ Local & PROD
- Sau khi hoàn thành kiểm thử cục bộ, thực hiện quy trình release chuẩn:
  - Commit mã nguồn an toàn kèm thông điệp rõ ràng.
  - Đẩy lên nhánh chính trên GitHub (`git push`) để hệ thống CI/CD và máy chủ PROD (Streamlit Cloud / Render) tự động cập nhật phiên bản mới nhất cho Client sử dụng trên điện thoại/trình duyệt.

---

## 4. ĐỊNH HƯỚNG VÀ RÀNG BUỘC KỸ THUẬT (TECHNICAL CONSTRAINTS)

- **Tech Stack:** Python 3.10+, Streamlit, Vnstock (>= 4.0.6), Supabase PostgreSQL, Apache ECharts.
- **Tích hợp Kênh Thông báo:** Discord Bot API (gửi DM bảo mật qua User ID), Discord Webhook (báo cáo công khai kênh chung).
- **Quy chuẩn chất lượng:** SonarCloud (Cognitive Complexity < 15, S8572 logging.exception, Ruff I001), Unit Test Coverage >= 80%.
- **An toàn Kiểm thử (Testing Guardrail):** 100% unit tests phải chạy ở chế độ offline mock, không kết nối Discord thật.

---

## 5. YÊU CẦU PHI CHỨC NĂNG (NON-FUNCTIONAL REQUIREMENTS)

- **Trải nghiệm Người dùng (UX):** Giao diện chạy mượt mà, phản hồi bấm nút Backtest dưới 3 giây đối với chuỗi dữ liệu 1-2 năm.
- **Độ tin cậy Thông báo:** Tín hiệu Mua phát ra từ Web phải đến Discord DM của Client trong vòng dưới 2 giây.
- **Tính Minh bạch:** Báo cáo Backtest và Paper Trading hiển thị rõ các giới hạn mô phỏng (không có tác động thị trường thực, giả định trượt giá).
- **Ngôn ngữ:** 100% Tiếng Việt chuẩn Unicode, không dùng chữ Hán/tiếng Trung.

---

## 6. LỊCH SỬ RỦI RO & BÀI HỌC XƯƠNG MÁU (KNOWN RISKS & LESSONS LEARNED)

*Bài học cũ (vẫn còn hiệu lực):*
1. **Sự cố dữ liệu BCTC đóng băng (Stale Data Incident):** Dữ liệu cũ quá 2 quý phải bị khóa khuyến nghị (`recommendation_allowed = False`).
2. **Bẫy thanh khoản cổ phiếu nhỏ (Penny Liquidity Trap):** ADV20 < 300k cấm khuyến nghị tỷ trọng lớn.
3. **Ảo giác AI & FOMO Đỉnh sóng:** Luôn có bộ lọc trọng tài PM Arbitration chặn lệnh khi RSI > 75.
4. **Bội chi Token LLM (Token Cost Runaway):** Lọc trước bằng code Python (0 token), chỉ gửi dữ liệu nén cho LLM.
5. **Look-ahead bias trong Backtest:** Chỉ dùng dữ liệu Point-in-time cho BCTC, không backtest phần LLM.
6. **Overfitting tham số:** Kiểm định độ nhạy (ngưỡng 60 vs 70 vs 80), walk-forward.

*Bài học MỚI từ vận hành thực tế v3.1:*
7. **Đứt gãy Liên kết Web $\rightarrow$ Discord (Web Alert Disconnect):**
   - *Bài học:* Người dùng kỳ vọng mọi quyết định MUA quan trọng (dù phát sinh từ Bot ngầm hay từ thao tác phân tích chủ động trên Web) đều phải gửi thông báo về túi (Discord DM). Không được để tình trạng tín hiệu đã lưu Supabase nhưng người dùng không hề hay biết.
8. **Rò rỉ Môi trường Test ra Kênh Thật (Test Alert Leakage):**
   - *Bài học:* Chạy test tự động không mock hàm thông báo dẫn đến việc gửi dữ liệu giả (`HOT1`, `TRAP1`, `FPT lỗ -20%`) vào Discord thật của Client. Điều này làm xói mòn niềm tin của người dùng vào hệ thống. Quy chuẩn: **100% test case bắt buộc phải mock toàn bộ I/O bên ngoài (Discord, Telegram, Email)**.
9. **Spam Thông báo Thanh lọc (Prune Alert Fatigue):**
   - *Bài học:* Gửi thông báo thanh lọc danh mục liên tục trong phiên gây phiền toái cho nhà đầu tư. Chỉ quét và thông báo đúng 1 lần vào đầu ngày trước giờ mở phiên (08:45).

