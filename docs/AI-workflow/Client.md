# 🎯 YÊU CẦU DỰ ÁN (CLIENT BRIEF)

**Tên dự án:** Stock-AI / AI Trading Bot  
**Ngày tạo:** 2026-09-24 | **Cập nhật:** 2026-09-26  
**Người yêu cầu (Client):** Tùng  
**Phiên bản yêu cầu:** v5.5 — Tối Ưu Hóa Danh Mục, Mô Phỏng Rủi Ro Monte Carlo & Phân Rã Nhân Tố (Phase 5 — Advanced Quantitative Portfolio Engine)  

---

## 1. TỔNG QUAN DỰ ÁN (EXECUTIVE SUMMARY)

- **Kế thừa thành quả các phiên bản trước:**
  - Hạ tầng cứng Backtest đã mô phỏng chuẩn xác cơ chế HOSE (trần/sàn ±7%, quy chế T+2.5, thuế phí 0.25%, trượt giá động sát thực tế, trần hấp thụ thanh khoản 5% ADV20, Audit Trail Supabase).
  - Tích hợp thành công giao diện Tab 6 (Backtest Dashboard, Bảng số liệu Regime, Paper Trading).
  - Hoàn thiện luồng Web-to-Discord hook cho khuyến nghị MUA và cô lập 100% mock Discord trong bộ kiểm thử tự động (Zero Test Leakage).
  - Hoàn tất **Phase 0** (Tường lửa Disclaimer, Content Filter RSS, Heartbeat 08:30), **Phase 1** (Hạ tầng Bằng chứng Signal Lifecycle, ADR-0001 Lock Thresholds), **Phase 2** (Chốt chặn Ngành $\le 25\%$, Trượt giá động 60–75 bps, Cầu dao Gemini 12 RPM), **Phase 3** (Walk-Forward 3 chặng, Ma trận Stress 11 sự kiện khủng hoảng, Bộ quét Flash Crash, Bootstrap Sharpe CI $10,000$ lần), và **Phase 4** (Thử nghiệm song song A/B Quant-Only vs Quant+AI, Chuẩn định Confidence Calibration & Brier Score).

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

- **Mục tiêu phiên bản 5.2 – 5.4** *(đã hoàn thành)*:
  - **Phase 0 — Tường lửa bảo mật & tuân thủ pháp lý** (xem Mục 3A, đã hoàn thành).
  - **Phase 1 — Hạ tầng bằng chứng (Signal Lifecycle)** (xem Mục 3B, đã hoàn thành).
  - **Phase 2 — Kiểm soát rủi ro & Bảo vệ danh mục (Risk Fixes)** (xem Mục 3C, đã hoàn thành).
  - **Phase 3 — Nghiên cứu & Thẩm định Chuyên sâu (Walk-Forward, Stress Matrix, Bootstrap Sharpe CI)** (xem Mục 3D, đã hoàn thành).
  - **Phase 4 — Thử nghiệm Song song A/B & Chuẩn định AI Confidence** (xem Mục 3E, đã hoàn thành).

- **Mục tiêu phiên bản 5.5** *(hiện tại — Tối ưu hóa Danh mục & Mô phỏng Rủi ro Nâng cao - Phase 5)*:
  - **Phase 5a — Mô phỏng Rủi ro Đuôi Monte Carlo (Monte Carlo Tail Risk Simulation):** Tráo thứ tự chuỗi giao dịch qua 2,000 đường mô phỏng để tính 95th/99th Percentile Drawdown và xác suất sụt giảm vốn quá 15%.
  - **Phase 5b — Tối ưu hóa Tỷ trọng Đóng góp Rủi ro Ngang bằng (Risk Parity / Inverse Volatility Sizing):** Phân bổ tỷ trọng theo nghịch đảo độ biến động ATR/Vol thay vì tỷ trọng đều, khống chế trần tối đa 25%/mã.
  - **Phase 5c — Phân rã Đa Nhân tố Rủi ro (Multi-Factor Beta Decomposition):** Bóc tách Market Beta và Sector Beta độc lập.
  - **Phase 5d — Chiến lược Chốt lời Từng phần & Kéo Break-even (Partial Profit Taking & Breakeven Stop):** Chốt 50% tại Target 1 (+12%), tự động dời stop lên giá vốn để tạo vị thế "Risk-Free Trade".



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

## 3C. PHASE 2 — KIỂM SOÁT RỦI RO & BẢO VỆ DANH MỤC (v5.1 — RISK FIXES)

> **Mục tiêu:** Vá triệt để các lỗ hổng rủi ro danh mục và hoàn thiện cơ chế mô phỏng thực tế trước khi bước vào giai đoạn nghiên cứu phân tích chuyên sâu (Phase 3).

### Phase 2a: Chốt chặn Tập trung Ngành (Sector Concentration Gate)

- **Vấn đề thực tế:** 
  - Tại `data_engine.py:1269`, từ điển `SECTOR_MAP` đã được định nghĩa nhưng chưa từng được nối vào Risk Engine hay Data Gate.
  - Hậu quả: Hệ thống có thể mở đồng thời 8/8 vị thế vào cùng một nhóm ngành (ví dụ: toàn Bất động sản hoặc Ngân hàng). Khi khủng hoảng ngành xảy ra (như sự kiện Trái phiếu Doanh nghiệp 2022), hệ số tương quan giữa các cổ phiếu tiến tới 1.0, khiến mô hình Half-Kelly và đa dạng hóa danh mục hoàn toàn bị vô hiệu hóa.
- **Yêu cầu kỹ thuật:**
  - Tích hợp hàm kiểm tra tập trung ngành:
    ```python
    MAX_POSITIONS_PER_SECTOR = 3  # Tối đa 3 vị thế cùng một ngành trong danh mục 8-10 mã (<= 35% portfolio)
    MAX_SECTOR_WEIGHT_PCT = 25.0  # Hoặc tối đa 25% tổng giá trị danh mục
    ```
  - Triển khai hàm `check_sector_concentration(new_symbol: str, current_portfolio: list, sector_map: dict = None) -> tuple[bool, str]`.
  - Nếu số lượng mã cùng ngành trong danh mục đã chạm trần hoặc tỷ trọng vượt quá $25\%$:
    - Hard Block: Không cho phép kích hoạt tín hiệu Mua mới (`allowed = False`).
    - Ghi log và trả về lý do từ chối cụ thể: *"Sector Gate Blocked: Ngành '{sector}' đã đạt giới hạn tập trung vị thế"*.
- **Định nghĩa Done:** Unit test mô phỏng danh mục đã có 3 mã BĐS/Ngân hàng và xác nhận mã thứ 4 bị từ chối 100%.

---

### Phase 2b: Mô hình Trượt giá Động (Dynamic Slippage Engine)

- **Vấn đề thực tế:** 
  - `backtest_engine.py:23` đang áp dụng `DEFAULT_SLIPPAGE_BPS = 15.0` cố định cho mọi điều kiện thị trường.
  - Hậu quả: Đây là sự **lạc quan cấu trúc (Structural Optimism)** nghiêm trọng trong thị trường gấu. Trong các phiên bán tháo hoặc giảm sàn liên tiếp, thanh khoản biến mất (trắng bên mua), mức trượt giá thực tế lên tới 50–150 bps. Dùng 15 bps cố định làm cho con số Sharpe, Max Drawdown và Alpha trong backtest bị thổi phồng một cách phi thực tế ở chính pha Downtrend mà hệ thống cần kiểm chứng.
- **Yêu cầu kỹ thuật:**
  - Thay thế 15 bps cố định bằng hàm tính trượt giá động `calculate_dynamic_slippage_bps()`:
    ```python
    def calculate_dynamic_slippage_bps(
        is_buy: bool,
        vol_ratio: float,
        is_floor: bool = False,
        is_ceiling: bool = False,
        adv20_billion: float = 10.0,
        order_size_billion: float = 0.1,
    ) -> float:
        base_bps = 15.0
        # Kịch bản kịch trần (khó mua)
        if is_ceiling and is_buy:
            base_bps *= 4.0
        # Kịch bản kịch sàn (rất khó thoát hàng, kẹt thanh khoản)
        elif is_floor and not is_buy:
            base_bps *= 5.0
        # Thanh khoản suy kiệt so với bình quân
        if vol_ratio < 0.5:
            base_bps *= 2.0
        elif vol_ratio > 3.0:
            base_bps *= 1.5
        # Quy mô lệnh chiếm tỷ trọng đáng kể trên ADV20
        order_pct_adv = order_size_billion / adv20_billion if adv20_billion > 0 else 0
        if order_pct_adv > 0.05:
            base_bps *= (1 + order_pct_adv * 3)
        return min(base_bps, 200.0)
    ```
  - Tích hợp trượt giá động vào vòng lặp khớp lệnh ảo của Backtest Engine và Paper Trading.
- **Định nghĩa Done:** Unit test chứng minh slippage khi chạm giá sàn tăng lên tối thiểu 75 bps và trần tối đa không vượt quá 200 bps.

---

### Phase 2c: Cầu dao Hạn mức API Gemini (Rate Limit Circuit Breaker 15 RPM)

- **Vấn đề thực tế:**
  - Hạn mức Google Gemini API (Free tier) bị giới hạn trần 15 RPM (Requests Per Minute). Khi bot chạy quét đa mã đồng thời hoặc gặp phiên thị trường biến động mạnh, việc gọi LLM liên tục sẽ kích hoạt lỗi `HTTP 429 Too Many Requests`.
  - Hậu quả: Bot bị crash hoặc tự động bỏ qua tín hiệu mà không có thông báo cho người dùng, dẫn đến mất dấu cơ hội hoặc không kịp cảnh báo rủi ro.
- **Yêu cầu kỹ thuật:**
  - Triển khai cơ chế Sliding Window 60 giây theo dõi tần suất gọi `_GEMINI_RATE_TRACKER`:
    - Đếm số lượt gọi trong 60 giây gần nhất.
    - Ngưỡng cảnh báo đệm: Chạm $\ge 12$ calls/phút (buffer 3 calls).
  - Khi chạm ngưỡng $\ge 12$ calls/phút:
    - Kích hoạt trạng thái Cooldown an toàn (tạm dừng gọi LLM cho các mã ít ưu tiên).
    - Tự động bắn Discord Alert thông báo: *"⚠️ Gemini Rate Limit Buffer Reached (12/15 RPM)"* kèm danh sách các mã bị hoãn để người dùng chủ động theo dõi thủ công.
- **Định nghĩa Done:** Mock test xác nhận khi gọi đến request thứ 12 trong vòng 60s, hàm trả về False và phát cảnh báo Discord.

---

## 3D. PHASE 3 — NGHIÊN CỨU & THẨM ĐỊNH CHUYÊN SÂU (v5.3 — RESEARCH & STRESS TESTING)

> **Mục tiêu:** Kiểm chứng tính vững chắc (Robustness) của chiến lược bằng phương pháp luận quản lý quỹ khắt khe: Walk-Forward OOS, Stress Test 4 đợt sập lịch sử, và Bootstrap Sharpe Confidence Interval.

### Phase 3a: Khung Kiểm định Walk-Forward (Walk-Forward Optimization Framework)

- **Vấn đề thực tế:**
  - Sai lầm lớn nhất của các mô hình giao dịch là "Backtest toàn bộ chuỗi dữ liệu cùng lúc". Việc nắn tham số trên toàn bộ lịch sử 2018–2024 khiến kết quả kiểm định bị nhiễm Look-ahead Bias và Data Snooping.
- **Yêu cầu kỹ thuật:**
  - Thiết lập phân chia timeline cố định 3 giai đoạn không gối đầu:
    1. **Training Period (2018–2020):** Khớp các tham số nền tảng (Lookback window, baseline multiples).
    2. **Validation Period (2020–2022):** Tinh chỉnh ngưỡng chốt chặn (Hard Gates, Stop loss, ATR) — TUYỆT ĐỐI KHÔNG nhìn trước dữ liệu giai đoạn sau.
    3. **Out-of-Sample (OOS) Test (2022–2024):** Chạy kiểm định 1 lần duy nhất trên dữ liệu hoàn toàn chưa từng biết đến.
  - **Quy tắc sắt Quản lý Quỹ:**
    - Khóa cứng tham số Quant Core bằng `ADR-0001` trước khi chạy OOS.
    - Nếu OOS thất bại (Sharpe < 0.5 hoặc CAGR < 4.5%): Bắt buộc quay lại bước Training để cấu trúc lại luận điểm, nghiêm cấm "nhìn trộm" OOS để sửa tham số lần 2.
- **Định nghĩa Done:** Báo cáo bóc tách hiệu năng theo 3 giai đoạn độc lập: Training vs. Validation vs. OOS.

---

### Phase 3b: Ma trận Kiểm tra Áp lực Khủng hoảng & Bộ Quét Định lượng (Crisis Stress Matrix & Quantitative Event Scanners)

- **Vấn đề thực tế:**
  - Một chiến lược định lượng chỉ thực sự có giá trị nếu nó sống sót và bảo toàn được vốn qua các giai đoạn thị trường sụp đổ thảm khốc nhất của VN-Index và né được các cú sốc thanh khoản vĩ mô.
- **Yêu cầu kỹ thuật:**

  #### 1. Danh mục 10 Sự kiện Khủng hoảng & Biến động Lịch sử Trọng yếu (2018–2024):

  | Mã sự kiện | Giai đoạn | Sự kiện Thị trường & Bối cảnh | Mức tác động VN-Index | Trọng tâm Thẩm định Sống còn |
  |---|---|---|---|---|
  | `trade_war_2018` | 03/2018 – 12/2018 | **Chiến tranh thương mại Mỹ - Trung (2018):** Mỹ áp thuế nhôm/thép và 50 tỷ USD hàng TQ. VN-Index từ đỉnh lịch sử 1.204 (09/04/2018) lao dốc về quanh 900 điểm vào tháng 7 và giằng co giảm tới hết năm. | Sụt giảm $-25\%$ đến $-30\%$ | Cash Mode có kích hoạt kịp thời để cắt lỗ và đứng ngoài hay không? |
  | `trump_tariff_2019` | 05/05/2019 – 31/05/2019 | **Trump Tariff – 20 ngày đỏ lửa Thiên nga đen:** Tweet ngày 05/05/2019 của TT Trump tuyên bố tăng thuế từ 10% lên 25% đối với 200 tỷ USD hàng TQ khiến thị trường chìm trong sắc đỏ suốt tháng 5. | Sụt giảm dốc ngắn hạn $-5\%$ | Hệ thống có phát tín hiệu phòng thủ né bẫy bắt đáy sớm? |
  | `covid_crash_2020` | 23/01/2020 – 31/03/2020 | **Bùng phát đại dịch Covid-19 (2020):** Bán tháo toàn cầu khi WHO công bố đại dịch, VN-Index chạm đáy chu kỳ 659 điểm (24/03/2020) trước Chỉ thị 16. | Sụt giảm $-35\%$ | Max Drawdown thực tế của hệ thống là bao nhiêu so với mức sập $-35\%$ của Index? |
  | `covid_lockdown_2021` | 09/07/2021 – 30/09/2021 | **Giãn cách xã hội nghiêm ngặt (Biến chủng Delta):** Phong tỏa cứng TP.HCM và 19 tỉnh phía Nam theo Chỉ thị 16. VN-Index giảm nhanh từ 1.420 về 1.225 điểm (-14%) trong tháng 7 trước khi dòng tiền F0 hấp thụ. | Giảm sốc $-14\%$ rồi hồi phục | Quản trị rủi ro nhịp chỉnh sâu trong sóng uptrend lớn. |
  | `bull_market_2021` | 01/01/2021 – 31/12/2021 | **Sóng Bull Market Siêu thanh khoản:** Lãi suất rẻ, bùng nổ nhà đầu tư cá nhân F0 đưa VN-Index vượt 1.500 điểm (cổ phiếu x3–x5). | Tăng trưởng $+35\%$ (nhiều mã $+150\%$) | Hệ thống có kiên nhẫn để lãi chạy (ride the trend) hay chốt non quá sớm? |
  | `bond_crackdown_2022` | 29/03/2022 – 31/05/2022 | **Sai phạm TTCK & Trái phiếu doanh nghiệp:** Khởi tố Chủ tịch FLC Trịnh Văn Quyết và Tân Hoàng Minh Đỗ Anh Dũng; bán tháo diện rộng nhóm đầu cơ, đóng băng kênh trái phiếu. | Sụt giảm $-23\%$ | Chốt chặn Sector Gate và FA Gate có né hoàn toàn các mã đầu cơ? |
  | `rate_hike_2022` | 23/09/2022 – 31/12/2022 | **NHNN thắt chặt tiền tệ, tăng lãi suất điều hành:** Hai đợt tăng lãi suất liên tiếp (mỗi lần +100 bps vào 23/09 và 25/10/2022) nhằm ghìm tỷ giá và lạm phát. | Sụt giảm $-20\%$ | Hệ thống có duy trì tỷ trọng tiền mặt tối đa khi lãi suất đảo chiều tăng? |
  | `van_thinh_phat_2022` | 06/10/2022 – 16/11/2022 | **Sự kiện Vạn Thịnh Phát & SCB:** Khởi tố bà Trương Mỹ Lan, rút tiền tại SCB, giải chấp chéo đưa VN-Index về đáy sâu nhất 873 điểm (16/11/2022). | Sụt giảm $-25\%$ (Đáy 873 điểm) | Cơ chế cắt lỗ kỷ luật và trượt giá sàn có giúp bảo toàn vốn? |
  | `fx_bill_tightening_2023` | 01/07/2023 – 30/09/2023 | **Khối ngoại bán ròng kỷ lục & Hút tín phiếu SBV:** Chênh lệch lãi suất USD-VND nới rộng, NHNN mở lại kênh hút tín phiếu giữa tháng 9/2023 khiến Index sập từ 1.250 về 1.020. | Sụt giảm $-18\%$ | Nhận diện đảo chiều dòng tiền ngoại và tín hiệu co hẹp vị thế. |
  | `fx_dxy_pressure_2024` | 01/04/2024 – 30/06/2024 | **Đồng USD tăng vọt & Tỷ giá chạm kỷ lục:** DXY vượt 105-106, USD/VND vượt 25.400, SBV bán can thiệp ngoại tệ và phát hành tín phiếu. | Điều chỉnh dốc ngắn $-10\%$ | Đánh giá phản ứng co cụm tỷ trọng trước áp lực vĩ mô. |
  | `liquidity_dry_2024` | 01/07/2024 – 30/09/2024 | **Sụt giảm thanh khoản & Khối ngoại bán ròng:** Giá trị giao dịch teo tóp về 12.000–15.000 tỷ/phiên trước thềm Fed hạ lãi suất và khối ngoại duy trì rút ròng. | Đi ngang / Phân hóa hẹp | Tránh bẫy Whipsaw khi thị trường cạn kiệt thanh khoản. |

  #### 2. Bộ Lọc Quy Tắc Quét Định Lượng (Quantitative Stress Scanners / Dynamic Event Filters):
  - **Flash Crash $\ge 50$ điểm/phiên:** Quét tự động các phiên hoảng loạn lịch sử: 24/08/2015, 05/02/2018, 09/03/2020, 19/01/2021, 28/01/2021 (-73 điểm), 25/04/2022 (-68 điểm), 12/05/2022 (-62 điểm), 18/08/2023 (-55 điểm), và 15/04/2024 (-60 điểm).
  - **Phiên sụt giảm $\ge 4\%$/phiên của VN-Index:** Lọc các phiên giảm $\ge 4\%$ trong chu kỳ 10 năm qua (tháng 03/2020, tháng 01/2021, tháng 04-05/2022).
  - **Gãy sóng dốc liên tiếp $\sim 10\%$ trong thời gian $< 1$ tháng (2022–2024):** Nhắm vào 4 đợt sập dốc: 04/2022, 10/2022, 09-10/2023 và 04/2024.
  - **DXY bứt phá dốc đứng (2022–2024):** Quét các giai đoạn DXY vượt 114 (08–10/2022) và vượt 106 (03–05/2024).
  - **Phản ứng Ngày Công bố Lãi suất FED (FOMC):** Các đợt tăng sốc 75 bps (tháng 6, 7, 9, 11 năm 2022) và đợt hạ lãi suất 50 bps (18/09/2024).

  - **Bảng tổng kết Stress Test bắt buộc so sánh:** Max Drawdown, Net Return, Tỷ lệ Lệnh cắt lỗ đúng kỷ luật, Tốc độ hồi phục vốn (Recovery Factor), và Tỷ trọng Tiền mặt (Cash Mode) duy trì trong kỳ.
- **Định nghĩa Done:** Module tự động chạy stress test trên 10 kịch bản lịch sử, tích hợp hàm quét quy tắc định lượng flash crash, và xuất báo cáo đối soát chi tiết.

---

### Phase 3c: Khoảng Tin cậy Sharpe bằng Phương pháp Bootstrap (Bootstrap Sharpe CI)

- **Vấn đề thực tế:**
  - Khi số lượng giao dịch còn ít ($N < 30$ hoặc Effective $N < 20$), con số Sharpe point-estimate (ví dụ: Sharpe = 1.4) không có ý nghĩa thống kê đáng tin cậy. Nếu khoảng tin cậy 95% rơi vào `[-0.3, 2.8]`, điều đó có nghĩa là hiệu năng dương chỉ là ngẫu nhiên may mắn.
- **Yêu cầu kỹ thuật:**
  - Triển khai hàm `bootstrap_sharpe_ci(returns, n_bootstrap=10_000, risk_free_annual=0.045, ci=0.95) -> dict`:
    ```python
    def bootstrap_sharpe_ci(
        returns: list[float],
        n_bootstrap: int = 10_000,
        risk_free_annual: float = 0.045,
        ci: float = 0.95,
    ) -> dict:
        """Tính toán Khoảng tin cậy (Confidence Interval) của Sharpe qua 10,000 lần Resampling."""
        # Ước lượng ci_lower, ci_upper tại phân vị 2.5% và 97.5%
        # Tính toán Effective Sample Size (ESS) xử lý tự tương quan
        # Xác định rõ cờ is_statistically_significant: ci_lower > 0
    ```
  - Nếu `ci_lower < 0`: Đưa ra cảnh báo minh bạch trên Dashboard: *"Số lượng quan sát chưa đủ để khẳng định chiến lược có Edge thống kê. Cần tiếp tục tích lũy quan sát từ Signal Lifecycle."*
- **Định nghĩa Done:** Unit test xác nhận `bootstrap_sharpe_ci()` tạo ra khoảng tin cậy chuẩn xác qua $10,000$ lần tái mẫu với NumPy/Pandas.

---

## 3E. PHASE 4 — KIỂM CHỨNG GIÁ TRỊ AI & THỬ NGHIỆM SONG SONG A/B (v5.4 — AI VALIDATION & CALIBRATION)

> **Mục tiêu:** Trả lời dứt khoát câu hỏi cốt tử của nhà đầu tư và ban quản trị quỹ: *"AI đóng góp bao nhiêu vào Sharpe Ratio và Expectancy? Hay AI chỉ là một tầng phân tích tốn kém, tạo ảo giác tự tin?"*

### Phase 4a: Khung Thử nghiệm Song song 2 Nhánh (A/B Testing Framework: Quant-Only vs Quant+AI)

- **Vấn đề thực tế:**
  - Nhiều hệ thống AI trading gán mác "AI" nhưng không chứng minh được AI tạo ra thặng dư lợi suất (Incremental Alpha) so với một bộ lọc định lượng thuần túy (Quant-Only). Nếu bộ lọc định lượng đạt Sharpe 1.2 mà khi có AI vào Sharpe chỉ còn 1.1 (do AI quá thận trọng bỏ lỡ cơ hội hoặc bị ảo giác bắt đáy sai), thì việc tốn token LLM là hoàn toàn vô nghĩa.
- **Yêu cầu kỹ thuật:**
  - Thiết lập 2 nhánh thử nghiệm độc lập (Experiment Arms) chạy song song:
    - **Arm A (QUANT_ONLY):** 
      - Điều kiện: Piotroski F-Score $\ge 6$, MoS $\ge 15\%$, Conviction $\ge 55$, Vượt qua Hard Gates.
      - Hành động: Phát tín hiệu MUA ngay lập tức nếu pass định lượng mà không cần AI phê duyệt.
    - **Arm B (QUANT_AI):**
      - Điều kiện: Thỏa mãn toàn bộ điều kiện Arm A + Hội đồng AI Gemini phân tích và ra quyết định đồng thuận MUA.
      - Hành động: Chỉ phát tín hiệu MUA khi AI phê duyệt.
  - Lưu trường `arm: "QUANT_ONLY" | "QUANT_AI"` trong bảng `signal_lifecycle`.
  - Triển khai hàm `compare_quant_vs_ai_arms(trades_arm_a: list[dict], trades_arm_b: list[dict]) -> dict`:
    - Bóc tách so sánh trực diện:
      - **Expectancy:** Lợi nhuận kỳ vọng trên mỗi lệnh.
      - **Sharpe Ratio:** Tỷ suất sinh lời điều chỉnh theo rủi ro.
      - **Win Rate & Profit Factor:** Độ chính xác và tỷ lệ Lãi/Lỗ.
      - **Tần suất tín hiệu (Signal Frequency):** Đánh giá AI có quá dè dặt (overly conservative) làm bỏ lỡ sóng lớn không.
    - Đưa ra kết luận định lượng:
      - Nếu `Sharpe(Arm B) > Sharpe(Arm A)`: AI tạo ra giá trị gia tăng (Positive AI Alpha) -> Khuyến nghị giữ AI.
      - Nếu `Sharpe(Arm B) <= Sharpe(Arm A)`: AI không tạo Alpha hoặc làm giảm hiệu năng -> Điều tra lại prompt hoặc chuyển AI về tầng báo cáo thuần túy (Reporting Layer).
- **Định nghĩa Done:** Unit test so sánh 2 tập trade records và xác định chính xác đóng góp thặng dư của AI.

---

### Phase 4b: Kiểm định Chuẩn định Độ tin cậy AI (AI Confidence Calibration)

- **Vấn đề thực tế:**
  - Các mô hình LLM thường mắc hội chứng **Tự tin thái quá (Overconfidence Hallucination)**: Gemini có thể đưa ra mức tự tin $75\% - 85\%$, nhưng trong thực tế các deal đó chỉ có tỷ lệ thắng $50\%$. Nếu lấy con số $75\%$ chưa qua chuẩn định (uncalibrated) đưa thẳng vào công thức Half-Kelly sizing, hệ thống sẽ đi lệnh quá lớn và dẫn đến sụt giảm vốn nghiêm trọng.
- **Yêu cầu kỹ thuật:**
  - Triển khai hàm `check_ai_calibration(trades: list[dict], min_observations_per_bucket: int = 3) -> dict`:
    - Phân nhóm các giao dịch đã hoàn tất theo 5 khoảng Confidence:
      - `50-60` (Midpoint 55%)
      - `60-70` (Midpoint 65%)
      - `70-80` (Midpoint 75%)
      - `80-90` (Midpoint 85%)
      - `90-100` (Midpoint 95%)
    - Đối chiếu `claimed_midpoint` và `actual_win_rate` (Số lệnh thắng / Tổng lệnh trong bucket).
    - Tính toán `calibration_gap = abs(actual_win_rate - claimed_midpoint)` và `brier_score`.
    - **Chốt chặn An toàn Quỹ (Safety Circuit Breaker):**
      - Nếu `is_calibrated == False` (ví dụ: `calibration_gap > 0.15` hoặc `actual_win_rate < 0.60` ở bucket $\ge 70\%$):
        - **HARD BLOCK:** CẤM tuyệt đối đưa `ai_confidence` vào công thức định cỡ vị thế Half-Kelly.
        - Hệ thống tự động chuyển sang chế độ `FIXED_DEFAULT_SIZING` hoặc `PURE_QUANT_SIZING` để bảo vệ vốn.
- **Định nghĩa Done:** Unit test chứng minh khi AI overconfident (claimed 80% nhưng thực tế 50%), hàm trả về `is_calibrated = False` và kích hoạt cờ cảnh báo rủi ro Kelly.

---

## 3F. PHASE 5 — TỐI ƯU HÓA DANH MỤC & MÔ PHỎNG RỦI RO NÂNG CAO (v5.5 — ADVANCED QUANT PORTFOLIO ENGINE)

> **Mục tiêu:** Nâng tầm hệ thống lên chuẩn mực quỹ phòng hộ (Hedge Fund Standard): Mô phỏng rủi ro đuôi Monte Carlo, Phân bổ tỷ trọng Risk Parity (nghịch đảo biến động), Phân rã đa nhân tố (Factor Beta), và Chốt lời từng phần (Partial Profit Lock).

### Phase 5a: Mô phỏng Rủi ro Đuôi Monte Carlo (Monte Carlo Drawdown & Tail Risk Engine)

- **Vấn đề thực tế:**
  - Một đường vốn backtest lịch sử duy nhất không phản ánh rủi ro đuôi (Tail Risk). Nếu thứ tự các lệnh bị đảo lộn (ví dụ gặp một chuỗi 4 lệnh thua liên tiếp rơi đúng vào lúc khởi đầu phân bổ vốn), tài khoản có thể bị Drawdown nặng nề hơn nhiều so với con số Max Drawdown quá khứ.
- **Yêu cầu kỹ thuật:**
  - Triển khai hàm `simulate_monte_carlo_drawdown(trade_pnl_pcts: list[float], n_simulations: int = 2_000, initial_capital: float = 100_000_000.0, random_state: int | None = 42) -> dict[str, Any]`:
    - Chạy $2,000$ đường mô phỏng ngẫu nhiên tráo đổi chuỗi lệnh (Trade order shuffling with replacement).
    - Tính toán:
      - `median_drawdown_pct`: Trung vị Max Drawdown qua các kịch bản.
      - `p95_drawdown_pct`: Phân vị 95% Max Drawdown (95% kịch bản drawdown không vượt quá con số này).
      - `p99_drawdown_pct`: Phân vị 99% Max Drawdown (Kịch bản rủi ro đuôi cực đoan / Tail Risk VaR).
      - `prob_drawdown_over_15pct`: Xác suất xảy ra sụt giảm vốn quá $15\%$.
      - `max_consecutive_losses`: Số lệnh thua liên tiếp tồi tệ nhất qua các mô phỏng.
- **Định nghĩa Done:** Unit test chứng minh mô phỏng 2,000 lần tính toán chuẩn xác các phân vị P95, P99 và xác suất rủi ro đuôi.

---

### Phase 5b: Phân bổ Tỷ trọng Đóng góp Rủi ro Ngang bằng (Risk Parity / Equal Risk Contribution)

- **Vấn đề thực tế:**
  - Phân bổ tỷ trọng đều bằng nhau (Equal Weight: ví dụ chia đều 20% cho mỗi mã) là một sai lầm chết người trong quản lý quỹ. Một cổ phiếu High-Beta biến động $5\%$/ngày (như nhóm Thép/BĐS) sẽ chi phối $80\%$ rủi ro của toàn danh mục, khiến một mã giảm sàn có thể kéo sập NAV.
- **Yêu cầu kỹ thuật:**
  - Triển khai hàm `optimize_portfolio_risk_parity(volatilities: dict[str, float], max_weight: float = 0.25) -> dict[str, float]`:
    - Phân bổ tỷ trọng nghịch đảo với độ biến động (Inverse Volatility / Equal Risk Contribution):
      $$w_i \propto \frac{1}{\sigma_i}$$
    - Chuẩn hóa tổng trọng số danh mục bằng $1.0$ ($100\%$).
    - Áp dụng trần tỷ trọng tối đa `max_weight = 0.25` ($25\%$/mã) theo quy định an toàn danh mục của Quỹ. Tái phân bổ phần thặng dư cho các mã còn lại.
- **Định nghĩa Done:** Unit test chứng minh mã biến động thấp (VCB, FPT) được cấp tỷ trọng lớn hơn mã biến động cao (NVL, DIG), và không mã nào vượt quá trần $25\%$.

---

### Phase 5c: Phân rã Đa Nhân tố Rủi ro (Multi-Factor Beta Decomposition)

- **Vấn đề thực tế:**
  - Đánh giá chỉ bằng Market Beta (so với VN-Index) là chưa đủ. Một cổ phiếu có thể tăng không phải nhờ thị trường chung mà nhờ sóng riêng của ngành (Sector Momentum), hoặc ngược lại sụt giảm theo sóng tháo chạy của nhóm ngành.
- **Yêu cầu kỹ thuật:**
  - Triển khai hàm `calculate_factor_exposures(asset_returns: pd.Series, market_returns: pd.Series, sector_returns: pd.Series | None = None) -> dict[str, Any]`:
    - Tính toán Market Beta ($\beta_M$) và $R^2$ giải thích của thị trường chung.
    - Nếu có dữ liệu ngành, hồi quy đa biến tính toán Sector Beta ($\beta_S$) và Alpha thặng dư thuần túy (Idiosyncratic Alpha).
- **Định nghĩa Done:** Unit test xác nhận phân rã thành công hệ số Beta thị trường và Beta ngành.

---

### Phase 5d: Chiến lược Chốt lời Từng phần & Kéo Break-even (Partial Profit Taking & Breakeven Stop)

- **Vấn đề thực tế:**
  - Khi cổ phiếu đã lãi $+12\%$ đến $+15\%$, nếu để nguyên vị thế và gặp nhịp đảo chiều bất ngờ, khoản lãi có thể biến thành khoản lỗ, gây tổn thương tâm lý nhà đầu tư.
- **Yêu cầu kỹ thuật:**
  - Thiết kế quy tắc `evaluate_partial_profit_lock(entry_price: float, current_high: float, current_price: float, target_profit_pct: float = 12.0) -> dict[str, Any]`:
    - **Nấc 1:** Khi giá chạm hoặc vượt `target_profit_pct` (+12%):
      - Kích hoạt lệnh BÁN $50\%$ vị thế (Hiện thực hóa lợi nhuận).
      - Tự động kéo Stop-Loss của $50\%$ còn lại lên **Giá vốn (Break-even Stop)**.
    - **Nấc 2:** Phần vị thế $50\%$ còn lại trở thành một "Risk-Free Trade", được thả cho Trailing Stop tiếp tục gồng lãi tối đa theo sóng tăng.
- **Định nghĩa Done:** Unit test xác nhận khi giá đạt +12%, hàm phát tín hiệu chốt 50% và dời stop lên break-even.

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

