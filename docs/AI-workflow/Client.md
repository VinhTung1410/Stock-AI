# 🎯 YÊU CẦU DỰ ÁN (CLIENT BRIEF)

**Tên dự án:** Stock-AI / AI Trading Bot  
**Ngày tạo:** 2026-09-24 | **Cập nhật:** 2026-09-26  
**Người yêu cầu (Client):** Tùng  
**Phiên bản yêu cầu:** v5.1 — Tường lửa Bảo mật & Pháp lý (Phase 0) + Hạ tầng Bằng chứng Signal Lifecycle (Phase 1)  

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

- **Mục tiêu phiên bản 4.5** *(kế thừa từ v4.1, đã hoàn thành)*:
  1. **Chuẩn hóa thước đo định lượng:** Nạp chuỗi dữ liệu VN-Index làm Benchmark để tính toán chính xác Alpha, Beta thực của từng mã cổ phiếu và vẽ đường so sánh Buy & Hold trực quan.
  2. **Chuẩn hóa bộ phân loại Regime theo VN-Index:** Xác định trạng thái thị trường dựa trên VN-Index thay vì từng mã riêng lẻ.
  3. **Xây dựng chiến lược lõi "Quant Core Strategy":** F-Score $\ge 6$, MoS $\ge 15\%$, Z-Score $> 1.8$, RSI $< 70$, Hard Gates & ATR Stop-loss.
  4. **Kích hoạt Macro Circuit Breaker / Cash Mode:** Khóa 100% lệnh Mua khi VN-Index xác nhận Downtrend.
  5. **Smart Money Flow Engine:** EOD flow Khối ngoại & Tự doanh làm bộ lọc xác nhận.
  6. **Drawdown-Controlled Sizing:** Giảm 50% vị thế khi chuỗi thua $\ge 2$ hoặc drawdown $\ge 5\%$.
  7. **Paper Trading → Supabase:** Hiển thị lệnh ảo và đo Implementation Shortfall thực.
  8. **UX:** Định dạng số tiền nhập liệu (`100,000,000 VND`).

- **Mục tiêu phiên bản 5.1** *(hiện tại — ưu tiên cao nhất)*:
  - **Shift triết lý:** `AI Stock Bot → Investment Research Platform` — hệ thống không chỉ phát tín hiệu mà còn **tự ghi nhận, đo lường, kiểm định và phản biện chính các tín hiệu của nó**.
  - **Phase 0 — Tường lửa bảo mật & tuân thủ pháp lý** (xem Mục 3A).
  - **Phase 1 — Hạ tầng bằng chứng (Signal Lifecycle)** (xem Mục 3B).

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

## 3A. PHASE 0 — TƯỜNG LỬA BẢO MẬT & TUÂN THỦ (v5.1 — Làm Ngay)

> **Ưu tiên tuyệt đối.** Đây là các rủi ro đang active trong production trước khi bổ sung bất kỳ tính năng mới nào.

### Phase 0a: Disclaimer Bắt buộc trên Mọi Tín hiệu Discord

- **Vấn đề:** Hệ thống tự động phát tín hiệu MUA cụ thể (giá vào, target, stop-loss) qua Discord DM. Tại Việt Nam, hoạt động này có thể cấu thành "tư vấn đầu tư chứng khoán" cần giấy phép UBCKNN (Luật CK 2019, Điều 10 & 82). Không có tuyên bố miễn trừ trách nhiệm đi kèm.
- **Yêu cầu:** Thêm disclaimer cố định vào cuối **mọi** Discord DM — `discord_alerts.py`:
  ```python
  SIGNAL_DISCLAIMER = (
      "\n\n⚠️ *Tín hiệu tự động từ hệ thống AI — KHÔNG phải tư vấn đầu tư "
      "được cấp phép. Tự chịu trách nhiệm quyết định. Quá khứ không đảm bảo "
      "tương lai. Chỉ dùng số tiền có thể mất hoàn toàn.*"
  )
  ```
- **Định nghĩa Done:** 100% Discord DM phát tín hiệu có disclaimer, unit test xác nhận.

### Phase 0b: Content Filter RSS → LLM (Chống Prompt Injection)

- **Vấn đề xác nhận tại `data_engine.py:1201`:**
  ```python
  feed = feedparser.parse(resp.content)
  title = html.unescape(str(entry.title).strip())
  # → title + summary đẩy thẳng vào LLM prompt, không qua filter
  ```
  Luồng tấn công: `CafeF RSS (bên ngoài) → LLM prompt bị thao túng → Tín hiệu BUY sai → Discord DM → Lệnh tiền thật`.
  Hệ thống hiện chỉ sanitize HTML tags, **không có lớp bảo vệ nội dung** (content-level).
- **Yêu cầu:** Implement `sanitize_news_for_llm(title, summary) -> dict | None` với:
  - Regex blocklist: `ignore previous instructions`, `system:`, `disregard all`...
  - Hard cap độ dài: title ≤ 120 ký tự, summary ≤ 400 ký tự.
  - Return `None` nếu phát hiện injection → bỏ qua tin đó, log warning.
  - Tin tức chỉ được đưa vào LLM dưới dạng **sentiment score / category** (gián tiếp), không phải raw text trực tiếp vào decision prompt.
- **Định nghĩa Done:** Unit test với payload injection thực tế xác nhận bị chặn.

### Phase 0c: Heartbeat & System Status Alert

- **Vấn đề:** Không có cơ chế báo hiệu khi bot crash. Người dùng có thể đặt lệnh dựa trên tín hiệu cũ từ hôm trước mà không hay biết.
- **Yêu cầu:**
  - Bot tự gửi Discord DM `"✅ SYSTEM ONLINE 08:30 — [data_engine ✅] [gemini ✅] [supabase ✅]"` mỗi sáng trước ATO.
  - Nếu bất kỳ check nào fail: `"🚨 SYSTEM DEGRADED — Lỗi: [danh sách subsystems fail]"` kèm tên mã cần kiểm tra thủ công.
  - Rate limit Gemini (15 RPM): khi chạm ngưỡng 12 calls/phút, bắn Discord alert kèm danh sách symbols bị bỏ qua.
- **Định nghĩa Done:** Mock test xác nhận heartbeat gửi đúng giờ; fail-case gửi đúng format alert.

---

## 3B. PHASE 1 — HẠ TẦNG BẰNG CHỨNG: SIGNAL LIFECYCLE (v5.1)

> **Mục tiêu:** Biến mỗi trade thành một research observation. Không có Signal Lifecycle Database, mọi con số hiệu suất đều không có giá trị kiểm chứng.

### Phase 1a: Bảng `signal_lifecycle` trên Supabase

- **Schema bắt buộc** (mọi trường đều immutable tại thời điểm phát tín hiệu, trừ các trường exit và path metrics):

  ```sql
  CREATE TABLE signal_lifecycle (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    signal_id        TEXT UNIQUE NOT NULL,  -- "FPT_20260926_143022"
    symbol           TEXT NOT NULL,
    created_at       TIMESTAMPTZ DEFAULT NOW(),

    -- Quant inputs (đóng băng khi phát tín hiệu)
    entry_price      NUMERIC(10,2),
    entry_regime     TEXT,                  -- UPTREND/SIDEWAYS/DOWNTREND
    entry_sector     TEXT,
    f_score          INT,
    z_score          NUMERIC(6,3),
    mos_pct          NUMERIC(6,2),
    kelly_f          NUMERIC(6,4),
    rsi14            NUMERIC(5,1),
    conviction_score NUMERIC(5,1),
    adv20_billion    NUMERIC(8,2),

    -- AI metadata (đóng băng khi phát tín hiệu)
    ai_confidence      NUMERIC(5,1),
    ai_recommendation  TEXT,
    prompt_version     TEXT,               -- "quant_2pass_v3.2"
    model_version      TEXT,               -- "gemini-2.5-flash"

    -- Position
    initial_stop_price NUMERIC(10,2),      -- KHÔNG thay đổi → tính R-multiple
    stop_loss_price    NUMERIC(10,2),      -- có thể điều chỉnh (trailing)
    target_price       NUMERIC(10,2),

    -- Exit
    exit_timestamp  TIMESTAMPTZ,
    exit_price      NUMERIC(10,2),
    exit_reason     TEXT,                  -- STOP/TARGET/TRAILING/MANUAL/REGIME
    pnl_pct         NUMERIC(7,3),
    r_multiple      NUMERIC(6,3),          -- pnl / initial_risk

    -- Path metrics (cron T+1, T+5, T+20)
    mfe_pct  NUMERIC(7,3),
    mae_pct  NUMERIC(7,3),
    t1_pct   NUMERIC(7,3),
    t5_pct   NUMERIC(7,3),
    t20_pct  NUMERIC(7,3),

    -- Benchmark
    vnindex_pct_same_period NUMERIC(7,3),
    vn30_pct_same_period    NUMERIC(7,3),

    -- Experiment arm (Phase 4 — AI Validation)
    arm    TEXT DEFAULT 'QUANT_AI',        -- QUANT_ONLY / QUANT_AI
    status TEXT DEFAULT 'OPEN'
  );
  ```

- **Lý do `initial_stop_price` riêng biệt với `stop_loss_price`:** Trailing stop làm thay đổi `stop_loss_price` theo thời gian — nhưng R-multiple phải tính dựa trên **rủi ro ban đầu tại thời điểm vào lệnh**, không phải stop đã dời. Đây là sai lầm phổ biến khiến R-multiple bị đo lường không chính xác.

### Phase 1b: Metrics Bắt buộc trong Performance Dashboard

**Trade-level:**

| Metric | Công thức | Ghi chú |
|---|---|---|
| Win Rate | Lệnh thắng / Tổng lệnh | Không kết luận với < 30 lệnh |
| Expectancy | WinRate × AvgWin − LossRate × \|AvgLoss\| | Quan trọng hơn Win Rate |
| Profit Factor | Tổng lãi / \|Tổng lỗ\| | > 1.5 = chấp nhận được |
| R-Multiple | pnl / initial_risk | Dùng `initial_stop_price` |
| Effective N | Bootstrap ESS, không phải raw count | 100 trades tương quan ≠ 100 obs độc lập |

**Portfolio-level:** CAGR, Max Drawdown, Sharpe, Sortino, Calmar, Alpha vs VN-Index, Alpha vs VN30.

### Phase 1c: Benchmark Nâng cấp

- **Thêm VN30** làm secondary benchmark (phù hợp hơn VN-Index đơn thuần cho chiến lược mid-cap/growth).
- **Floor tối thiểu:** CAGR sau phí phải > 4.5%/năm (lãi suất tiền gửi risk-free). Nếu không → không có lý do dùng hệ thống thay vì gửi ngân hàng.
- **Rule:** Sharpe < 0.5 → không đủ risk-adjusted return → điều tra trước khi mở rộng vốn.

### Phase 1d: Lock Quant Core Thresholds (ADR)

- **Yêu cầu:** Ghi ADR với **ngày chốt** và lý do chọn từng ngưỡng Quant Core **trước khi** chạy thêm bất kỳ backtest nào.
- **Mục đích:** Ngăn data snooping — nếu ngưỡng được tune sau khi nhìn kết quả backtest, toàn bộ con số Sharpe/Win Rate đều bị thổi phồng và không có giá trị dự báo.
- **ADR template tối thiểu:**

  | Parameter | Value | Nguồn gốc chọn |
  |---|---|---|
  | F-Score min | ≥ 6 | Piotroski (2000): >5 = quality firm |
  | MoS min | ≥ 15% | Conservative value investing floor |
  | Z-Score min | > 1.8 | Altman "safe zone" boundary |
  | RSI max (entry) | < 70 | Below FOMO/overbought territory |
  | Conviction min | ≥ 55 | Medium pillar threshold |

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

*Bài học MỚI từ v3.1 — v4.5 & Đối thoại cùng Quản lý Quỹ:*
9. **Lỗi "Đồng hồ đo sai" (Dead Metrics Trap — Beta luôn bằng 1.0):**
   - Không truyền dữ liệu Benchmark làm tê liệt Alpha, Beta. Mọi kiểm định định lượng bắt buộc phải có chuỗi Benchmark VN-Index thật đi kèm.
10. **Nghịch lý "Xe đua F1 gắn bánh xe đạp" (Strategy Mismatch in Backtest):**
    - Đánh giá hệ thống phức hợp bằng chiến lược MA thô sơ dẫn đến kết quả sai lệch hoàn toàn. Engine Backtest phải phản ánh đúng chiến lược Quant Core.
11. **Lỗi logic tự quy chiếu trong phân loại Regime (Regime Tautology):**
    - Phải xác định trạng thái thị trường từ **chỉ số toàn thị trường (VN-Index)**, không lấy nến từng mã riêng lẻ.
12. **Bẫy Overfitting & Tâm lý "Làm đẹp số liệu":**
    - Đo lường khả năng thích ứng thị trường và bảo toàn vốn có giá trị cao gấp nhiều lần một đường vốn tăng trưởng dốc đứng do "nắn nót" tham số.
13. **Cạm bẫy "Bắt chước Quỹ" (Fund Copycat Trap) & Độ trễ Báo cáo:**
    - Tin tức và báo cáo tháng của quỹ có độ trễ lớn (T+30 đến T+45). Mua theo tin tức quỹ dễ biến nhà đầu tư thành thanh khoản chốt lời (Exit Liquidity). Quỹ không giúp né sập thị trường vì họ bị ràng buộc luật giữ 80-95% cổ phiếu.
14. **Tư duy Regime Alignment — "Bảo toàn vốn trước khi tìm kiếm lợi nhuận":**
    - Thước đo bot tốt không phải là PnL tĩnh, mà là sự nhịp nhàng với thị trường: Vào sóng mạnh trong Uptrend, và tuyệt đối kích hoạt **Cash Mode** đứng ngoài khi Downtrend để né trọn các đợt sập lịch sử.
15. **Hành vi "Trả thù thị trường" (Revenge Trading Trap):**
    - Phải áp dụng cơ chế tự động hạ $50\%$ quy mô vốn sau chuỗi thua liên tiếp (Drawdown-Controlled Sizing) để cứu nhà đầu tư khỏi sự phá vỡ kỷ luật giao dịch.

*Bài học MỚI từ v4.5 → v5.1 — Đánh giá Quỹ & Quant Researcher:*
16. **Bề mặt tấn công Prompt Injection qua RSS (RSS Injection Surface):**
    - `data_engine.py` scrape CafeF RSS rồi đẩy raw title/summary thẳng vào LLM decision prompt mà không qua content filter. Sanitize HTML tags là chưa đủ — phải có lớp kiểm tra nội dung (content-level blocklist) để ngăn tín hiệu bị thao túng từ nội dung bên ngoài.
17. **Slippage Cố định 15 bps — Lạc quan Cấu trúc trong Thị trường Gấu (`Fixed Slippage Optimism`):**
    - `backtest_engine.py` dùng `DEFAULT_SLIPPAGE_BPS = 15.0` cho mọi điều kiện thị trường. Trong kịch bản giảm sàn liên tiếp, slippage thực tế 50–150 bps. Con số Sharpe/Alpha trong backtest do đó bị thổi phồng cấu trúc ở giai đoạn thị trường gấu — đúng lúc Cash Mode được thiết kế để bảo vệ. Cần slippage động theo `is_floor`, `vol_ratio`, `adv20`.
18. **SECTOR_MAP tồn tại nhưng không được dùng (Dead Code Risk Gate):**
    - `SECTOR_MAP` đã định nghĩa tại `data_engine.py:1269` nhưng không có risk gate nào enforce giới hạn sector. 8/8 vị thế cùng BĐS hoặc Ngân hàng vẫn "hợp lệ" — trong khủng hoảng ngành, correlation tiến về 1.0, Half-Kelly không bảo vệ được gì.
19. **AI Confidence Chưa Calibrated — Không được Dùng trực tiếp vào Kelly (`Uncalibrated AI Input`):**
    - Gemini trả về `confidence=78%` nhưng actual win rate có thể chỉ 52%. Dùng confidence chưa calibrate làm `p_win` trong Kelly dẫn đến position sizing bị thổi phồng — đây là model risk nhân lên, không phải lỗi nhỏ. Phải đo calibration curve từ `signal_lifecycle` trước khi dùng AI confidence vào bất kỳ sizing formula nào.
20. **100 Trades ≠ 100 Independent Observations (Effective Sample Size):**
    - Nếu nhiều tín hiệu xuất hiện trong cùng một regime hoặc cùng sector, các observations bị correlated — raw count N không phản ánh đúng sức mạnh thống kê. Phải dùng Effective Sample Size (ESS = N × (1 − |autocorrelation|)) khi kết luận về edge của hệ thống.

