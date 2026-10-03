# 📓 GLOBAL: DECISION LOG (NHẬT KÝ QUYẾT ĐỊNH HỆ THỐNG - ADR)

Tài liệu này lưu trữ các Quyết định Kiến trúc & Nghiệp vụ Trọng yếu (Architectural Decision Records - ADR) của dự án Stock-AI nhằm đảm bảo tính kế thừa, minh bạch lý do đằng sau các thay đổi và tránh lặp lại sai lầm trong quá khứ.

---

## Mẫu Nhật ký (ADR Template)

```markdown
### [ADR-xxx] Tiêu đề Quyết định
- **Ngày quyết định:** YYYY-MM-DD
- **Người đề xuất / Tham gia:** PO, Finance, Senior Dev, QA Lead, Reviewer, Client
- **Bối cảnh & Vấn đề (Context):** Tại sao cần đưa ra quyết định này? Vấn đề gì đang xảy ra?
- **Các phương án cân nhắc (Options):** Các lựa chọn được đưa ra thảo luận.
- **Quyết định lựa chọn (Decision):** Giải pháp được chọn và lý do.
- **Hệ quả & Đánh đổi (Consequences):** Lợi ích đạt được và các giới hạn/chi phí chấp nhận đánh đổi.
```

---

## Danh mục Quyết định đã Thông qua

### [ADR-001] Chốt chặn Dữ liệu Đóng băng (Stale Data Gate) & Triangle Cross-Check
- **Ngày quyết định:** 2026-09-23
- **Người tham gia:** Client, Finance Lead, Senior Dev
- **Bối cảnh & Vấn đề:** Báo cáo định giá tự động tính P/B của VCB/TCB vọt lên 4.06x do nguồn dữ liệu bị kẹt ở quý 4/2018 (30 quý cũ). Các kiểm tra trước đây chỉ kiểm tra khoảng giá trị (range check) mà không kiểm tra độ mới của dữ liệu (freshness).
- **Quyết định lựa chọn:**
  1. Triển khai kiểm tra bắt buộc thời gian cập nhật dữ liệu (`freshness check`) trong `data_gate.py`.
  2. Bổ sung phép kiểm tra chéo tam giác (Triangle cross-check: Market Cap vs Equity vs Outstanding Shares).
  3. Nếu dữ liệu stale quá 2 quý đối với cổ phiếu niêm yết, tự động kích hoạt cờ đỏ `recommendation_allowed = False`.
- **Hệ quả:** Hệ thống có thể từ chối xuất báo cáo cho một số mã ít cập nhật, nhưng loại bỏ hoàn toàn nguy cơ xuất số liệu ảo làm sai lệch quyết định đầu tư thực tế.

---

### [ADR-002] Cơ chế Trọng tài PM Quyết định luận (Deterministic PM Arbitration)
- **Ngày quyết định:** 2026-09-23
- **Người tham gia:** Finance Lead, Senior Dev, Reviewer
- **Bối cảnh & Vấn đề:** Hội đồng 5 chuyên gia LLM có thể bị ảo giác (hallucination) hoặc FOMO khi đọc tin tức tích cực, đưa ra khuyến nghị BUY ngay đỉnh hoặc khi cổ phiếu đang rơi tự do (Falling Knife).
- **Quyết định lựa chọn:** Thêm lớp trọng tài độc lập `arbitrate_pm_decision()` trong `ai_analyst.py` để ghi đè (override) quyết định của LLM bằng các quy tắc toán học cứng (Thesis Breaker, Falling Knife, FOMO Protection).
- **Hệ quả:** Quyết định của AI được kiểm soát bằng "dây cương" định lượng; mô hình toán luôn có quyền phủ quyết cao nhất.

---

### [ADR-003] Quản trị Vốn Định lượng với Half-Kelly & Lọc Thanh khoản ADV20
- **Ngày quyết định:** 2026-09-23
- **Người tham gia:** Client, Finance Lead, QA Lead
- **Bối cảnh & Vấn đề:** Cổ phiếu vốn hóa nhỏ (Penny/Micro-cap) có thanh khoản thấp, nếu khuyến nghị tỷ trọng danh mục lớn sẽ khiến nhà đầu tư bị kẹt hàng khi thị trường sụt giảm.
- **Quyết định lựa chọn:**
  1. Ứng dụng công thức Half-Kelly để tính toán tỷ trọng phân bổ vốn an toàn.
  2. Phân tầng 3 cấp độ thanh khoản dựa trên khối lượng khớp lệnh trung bình 20 phiên (ADV20 Tier 1: > 1M cp, Tier 2: 200k - 1M cp, Tier 3: < 200k cp).
  3. Giới hạn tỷ trọng tối đa cho từng nhóm ngành (Sector Concentration Cap) không quá 25% tổng danh mục.
- **Hệ quả:** Tối ưu hóa tỷ suất sinh lời điều chỉnh theo rủi ro (Risk-Adjusted Return), ngăn ngừa rủi ro thanh khoản.

---

### [ADR-004] Thiết lập Quy trình Đa vai trò Lấy Client làm Trung tâm (Client-Centric Multi-Agent Workflow)
- **Ngày quyết định:** 2026-09-23
- **Người tham gia:** Client, PO, Senior Dev
- **Bối cảnh & Vấn đề:** Nhu cầu chuẩn hóa quy trình tiếp nhận yêu cầu từ Client thành các User Stories, được thẩm định tài chính, hiện thực hóa kỹ thuật, kiểm thử độ phủ và audit độc lập trước khi đẩy lên Production.
- **Quyết định lựa chọn:** Thiết lập cấu trúc thư mục quy chuẩn: `GLOBAL/`, `ROLES/`, `TASK/`, đặt Client làm vai trò định hướng nghiệp vụ tối cao tại `Client.md`.
- **Hệ quả:** Tăng tính minh bạch, chuyên môn hóa vai trò, đảm bảo mọi dòng code đều phục vụ đúng mục tiêu kinh doanh của Client và đạt chuẩn SonarCloud.

---

### [ADR-005] Khám phá & Thanh lọc Watchlist Tự động và Khắc phục Báo cáo 5 Câu hỏi
- **Ngày quyết định:** 2026-09-24
- **Người tham gia:** Client (Tùng), PO, Finance Lead, Senior Dev, QA Lead, Reviewer
- **Bối cảnh & Vấn đề:** Báo cáo phiên trưa (11:30) bị nuốt mất Câu hỏi số 5 do lỗi dính dòng prompt. Người dùng phải nhập tay Watchlist thủ công và chưa có cơ chế tự động dọn dẹp các mã đang quá hot (RSI > 75) hoặc dính bẫy giá.
- **Quyết định lựa chọn:**
  1. Tách dòng prompt và hoàn thiện Fallback Sanity Check đa định dạng (`**II.`, `📌 II.`), bổ sung `session_label` cho phiên trưa.
  2. Xây dựng `sync_auto_watchlist()` tự động tìm kiếm cơ hội (F-Score cao, MoS >= 15%, không bị Data Gate chặn), bảo toàn 100% mã do người dùng tự thêm tay.
  3. Xây dựng `prune_unsuitable_watchlist()` tự động xóa các mã auto bị Quá Hot (RSI > 75 hoặc MoS < -25%) hoặc dính bẫy giá; gắn cờ cảnh báo an toàn đối với mã manual của người dùng.
- **Hệ quả:** Watchlist luôn được làm mới liên tục với các cơ hội an toàn nhất, người dùng mở app lên luôn có danh sách cổ phiếu đạt chuẩn định lượng, loại bỏ hoàn toàn tình trạng thiếu câu hỏi cốt tử trong báo cáo.

---

### [ADR-006] Cho Phép Tự Động Xóa Mã Thủ Công Quá Hot & Gửi Báo Cáo Lý Do Vào Discord DM
- **Ngày quyết định:** 2026-09-24
- **Người tham gia:** Client (Tùng), PO, Senior Dev, QA Lead
- **Bối cảnh & Vấn đề:** Trước đây hệ thống chỉ xóa mã tự động (`is_auto: True`) và giữ nguyên mã manual để tránh mất dữ liệu của người dùng. Tuy nhiên, Client yêu cầu: bot được phép tự động xóa cả các mã do Client nhập tay nếu chúng đã quá nóng (RSI > 75, MoS < -25%) hoặc dính bẫy giá, nhưng **bắt buộc phải gửi báo cáo nêu rõ lý do xóa vào Discord DM** của Client.
- **Quyết định lựa chọn:**
  1. Nâng cấp `prune_unsuitable_watchlist()` đặt `prune_manual: bool = True` làm mặc định.
  2. Bổ sung hàm `send_watchlist_pruned_alert(pruned_items)` trong `discord_alerts.py`, format Rich Embed gửi trực tiếp vào Discord DM của Client.
  3. Ghi rõ nguồn gốc mã trong báo cáo (`👤 Bạn đã thêm thủ công` vs `🤖 Bot phát hiện tự động`), kèm theo thị giá, chỉ số RSI, MoS và lý do chi tiết vi phạm.
- **Hệ quả:** Giúp danh mục Watchlist của Client luôn sạch, giải phóng slot cho các cổ phiếu tiềm năng khác, đồng thời Client luôn nắm được đầy đủ lý do lượng hóa vì sao một mã bị loại bỏ.

---

### [ADR-007] Kiến trúc Engine Backtest theo Regime & Framework Forward Testing Đo lường Implementation Shortfall
- **Ngày quyết định:** 2026-09-24
- **Người tham gia:** Client (Tùng), PO, Finance Lead, Senior Dev, QA Lead, Reviewer
- **Bối cảnh & Vấn đề:** Hệ thống thiếu số liệu định lượng về tỷ lệ sinh lời sau chi phí thực tế (Sharpe, MDD, Expectancy) và các tham số cứng (70 điểm, 40/25/20/15, 2 BUY/ngày) chưa được kiểm chứng độ nhạy. Ngoài ra, LLM trong quá khứ bị rò rỉ thông tin huấn luyện (look-ahead bias) và chưa có công cụ đo trượt giá (Implementation Shortfall).
- **Quyết định lựa chọn:**
  1. Tách bạch hoàn toàn: **Chỉ backtest phần lõi định lượng xác định** (`regime_classifier.py`, `backtest_engine.py`), tuyệt đối không backtest LLM.
  2. Mô phỏng trung thực quy chế HOSE: biên độ trần ±7% (kịch trần không khớp mua), thanh toán T+2.5 (chỉ bán từ chiều T+2), phí 2 chiều + thuế bán 0.1%, và trần hấp thụ thanh khoản theo 5% ADV20.
  3. Xây dựng `paper_trading.py` đo lường Implementation Shortfall (bps) trên snapshot bất biến và theo dõi 2 nhánh Ablation (Quant Only vs Quant + LLM).
- **Hệ quả:** Cung cấp bằng chứng thực nghiệm minh bạch, loại bỏ hoàn toàn look-ahead bias và cho phép đo lường chính xác giá trị thặng dư (Alpha) thực tế của AI.

---

### [ADR-008] Nối dây Tín hiệu Web AI sang Discord DM, Khung giờ Thanh lọc Watchlist ATO & Cách ly Kiểm thử Tuyệt đối
- **Ngày quyết định:** 2026-09-24
- **Người tham gia:** Client (Tùng), PO, Finance Lead, Senior Dev, QA Lead, Reviewer
- **Bối cảnh & Vấn đề:** 
  1. Khi phân tích cổ phiếu trên Web Tab 5 đạt điều kiện MUA (như case TCB ID 37), hệ thống chỉ ghi Supabase mà không thông báo đến Discord DM của Client.
  2. Việc chạy unit test tự động làm rò rỉ mã ảo (`HOT1`, `TRAP1`, synthetic `FPT -20%`) vào Discord DM thật của Client do thiếu mock các hàm `send_*_alert`.
  3. Tính năng thanh lọc Watchlist bị kích hoạt nhiều lần trong ngày, gây loãng thông tin.
- **Quyết định lựa chọn:**
  1. Bổ sung Web-to-Discord hook trong `ai_analyst.py`: Tự động gửi Rich Embed khi tín hiệu là `MUA` / `BUY` kèm đầy đủ thông số Target, Stop-loss, MoS và F-Score.
  2. Bổ sung chốt chặn `last_ato_pruned_date` trong `trading_bot.py`: Đảm bảo thanh lọc Watchlist chỉ diễn ra đúng 1 lần/ngày trước phiên ATO (08:45).
  3. Chuẩn hóa quy định kiểm thử: 100% unit tests phải mock toàn bộ kênh mạng gửi Discord (`send_trade_signal_alert`, `send_watchlist_pruned_alert`, `send_discord_dm`, `send_discord_webhook`).
- **Hệ quả:** Kênh Discord DM của Client nhận trọn vẹn mọi tín hiệu MUA tức thì từ Web, được bảo vệ tuyệt đối khỏi dữ liệu test rác, và không bị spam thông báo dọn dẹp danh mục trong phiên.

---

### [ADR-009] Chuẩn Hóa Thước Đo Alpha/Beta, Phân Loại Regime Theo VN-Index & Chiến Lược Lõi Quant Core
- **Ngày quyết định:** 2026-09-24
- **Người tham gia:** Client (Tùng), PO, Finance Lead, Senior Dev, QA Lead, Reviewer
- **Bối cảnh & Vấn đề:** 
  1. Kiểm tra thực tế mã VIC tăng +67% nhưng Backtest báo lỗ -30% do dùng duy nhất chiến lược MA20/MA50 crossover thô sơ dẫn đến bẫy whipsaw ở cổ phiếu High-Beta.
  2. Hệ thống chưa truyền chuỗi lợi suất VN-Index vào `run_backtest()`, dẫn đến Beta luôn bằng 1.0 và Alpha luôn bằng 0%, làm tê liệt thước đo rủi ro.
  3. Phân loại Regime dùng nến của chính cổ phiếu đang test (Regime Tautology) và thuật toán MA200 cần >= 200 nến làm bảng kết quả cột Uptrend/Downtrend bị rỗng.
  4. Thiếu đường vốn đối chiếu Buy & Hold và Paper Trading Subtab 3 chưa nối dây tín hiệu thực từ Supabase.
- **Quyết định lựa chọn:**
  1. Nạp chuỗi lịch sử `VNINDEX` qua `fetch_index_historical()` làm Benchmark chuẩn, truyền vào `run_backtest()` để tính Beta thực và Alpha Jensen.
  2. Phân loại Regime thị trường dựa trên nến chỉ số VN-Index; xử lý linh hoạt độ dài nến để hiển thị đầy đủ 4 cột Uptrend, Downtrend, Sideways, Full.
  3. Xây dựng Chiến lược kiểm thử lõi "Quant Core Strategy" kết hợp Piotroski F-Score >= 6, MoS >= 15%, Z-Score > 1.8, RSI < 70, Hard Gates và Stop-loss biến động ATR.
  4. Trực quan hóa đồng thời 3 đường vốn trên biểu đồ Equity Curve: Chiến Lược, Buy & Hold và VN-Index chuẩn hóa.
  5. Đấu nối Paper Trading với bảng `quant_signals` từ Supabase và format số tiền nhập liệu trực quan (`100,000,000 VND`).
- **Hệ quả:** Kết quả kiểm định phản ánh trung thực năng lực định lượng của hệ thống Stock-AI, loại bỏ hoàn toàn các sai số phương pháp luận và cung cấp thước đo rủi ro chuẩn mực cho nhà đầu tư chuyên nghiệp.

---

### [ADR-010] Kiến Trúc Regime-First, Chốt Chặn Vĩ Mô Né Sập (Cash Mode), Quản Trị Rủi Ro Drawdown & Smart Money Flow
- **Ngày quyết định:** 2026-09-24
- **Người tham gia:** Client (Tùng), PO, Finance Lead, Senior Dev, QA Lead, Reviewer
- **Bối cảnh & Vấn đề:** 
  1. Tư duy kiểm thử ban đầu bị định kiến vào con số PnL tĩnh thay vì năng lực nương theo pha thị trường (Regime Alignment). Bot phát tín hiệu breakout giả trong downtrend khốc liệt làm danh mục chịu tổn thất lớn.
  2. Báo cáo và tin tức mua mới của quỹ đầu tư có độ trễ lớn (T+30 đến T+45) và quỹ mở bị ràng buộc nắm giữ 80-95% cổ phiếu nên không giúp nhà đầu tư né sập.
  3. Thiếu cơ chế kiểm soát rủi ro tâm lý khi gặp chuỗi thua lỗ liên tiếp (Revenge Trading) và rủi ro trượt giá do vượt trần thanh khoản ADV20.
- **Quyết định lựa chọn:**
  1. Đảo ngược pipeline thực thi theo chuẩn Quản lý Quỹ: `Macro Regime Gate -> Smart Money Watchlist -> Quant Trigger -> Drawdown Sizing -> Execution`.
  2. Bổ sung `is_macro_circuit_breaker_active()` trong `regime_classifier.py` và cờ `enforce_regime_gate=True` trong `backtest_engine.py`: Tự động khóa toàn bộ lệnh Mua khi VN-Index Downtrend (*Cash Mode*), bảo vệ 100% tài sản qua các đợt sập lịch sử.
  3. Xây dựng hàm `evaluate_smart_money_flow()` trong `quant_engine.py`: Đánh giá dòng tiền mua/bán ròng EOD của Khối ngoại & Tự doanh, chặn mua khi bị tổ chức bán ròng quy mô lớn (> 20 tỷ VNĐ).
  4. Hiện thực hóa `calculate_drawdown_controlled_sizing()`: Tự động giảm 50% quy mô vị thế khi có chuỗi 2 lệnh thua liên tiếp hoặc drawdown >= 5%.
  5. Hiện thực hóa `check_adv20_liquidity_absorption()`: Giới hạn quy mô lệnh không vượt quá 10% ADV20 để chống trượt giá và bẫy thanh khoản.
  6. Tích hợp checkbox "🛡️ Kích hoạt Chốt chặn Vĩ mô Né sập" trực tiếp trên giao diện Backtest của Tab Alpha Tracker.
- **Hệ quả:** Hệ thống đạt chuẩn quản lý quỹ quốc tế (Institutional Grade), tự động kích hoạt chế độ phòng thủ bảo toàn vốn khi thị trường sụp đổ và phân bổ vốn kỷ luật, loại bỏ triệt để sai lầm cảm xúc của nhà đầu tư cá nhân.

---

### [ADR-011] Tường Lửa Bảo Mật & Pháp Lý (Phase 0) + Hạ Tầng Bằng Chứng Signal Lifecycle (Phase 1)
- **Ngày quyết định:** 2026-09-26
- **Người tham gia:** Client (Tùng), PO, Finance Lead, Senior Dev, QA Lead, Independent Reviewer
- **Bối cảnh & Vấn đề:**
  1. Thiếu disclaimer pháp lý trên các thông báo Discord DM, tiềm ẩn rủi ro theo Luật Chứng khoán 2019 Điều 10 & 82.
  2. RSS CafeF nạp raw text trực tiếp vào LLM prompt mở ra bề mặt tấn công Prompt Injection thao túng tín hiệu tiền thật.
  3. Thiếu liveness heartbeat định kỳ 08:30 trước ATO và cảnh báo nghẽn rate limit Gemini (15 RPM).
  4. Hệ thống có nhiều cơ chế nhưng thiếu bằng chứng (Evidence): chưa tách biệt `initial_stop_price` để đo R-Multiple chuẩn xác, chưa tính Expectancy và Effective Sample Size (ESS) xử lý tương quan chuỗi.
  5. Cần khóa cứng các tham số Quant Core (ADR-0001) trước khi backtest để chống Data Snooping và Overfitting.
- **Quyết định lựa chọn:**
  1. Ban hành `SIGNAL_DISCLAIMER` cố định trên 100% cảnh báo Discord (`discord_alerts.py`).
  2. Xây dựng bộ lọc `sanitize_news_for_llm()` với blocklist regex và length caps (title $\le 120$, summary $\le 400$) cô lập tin độc hại khỏi LLM prompt (`data_engine.py`).
  3. Tích hợp `send_system_heartbeat()` 08:30 hàng ngày và `send_gemini_rate_limit_alert()` bảo vệ hạn mức API (`trading_bot.py`, `discord_alerts.py`).
  4. Xây dựng schema `signal_lifecycle` bất biến (`migrations/0002_create_signal_lifecycle.sql`, `db_manager.py`) bảo toàn `initial_stop_price` độc lập với trailing stop.
  5. Xây dựng `calculate_signal_performance_metrics()` trong `quant_engine.py`: Đo Win Rate, Expectancy, Profit Factor, R-Multiple, Effective Sample Size (ESS), Hurdle Rate sàn 4.5%/năm và Sharpe $\ge 0.5$.
  6. Ban hành `ADR-0001` chính thức khóa cố định các ngưỡng Quant Core (F-Score $\ge 6$, MoS $\ge 15\%$, Z-Score $> 1.8$, RSI $< 70$, Conviction $\ge 55$, Sector $\le 25\%$).
- **Hệ quả:** Hệ thống chính thức bước sang giai đoạn *Investment Research Platform* vững chắc về an ninh pháp lý, chống tấn công dữ liệu đầu vào, và sở hữu hạ tầng bằng chứng kiểm định định lượng chuẩn mực quỹ.

---

### [ADR-012] Kiểm Soát Rủi Ro Tập Trung Ngành, Mô Hình Trượt Giá Động & Cầu Dao Rate Limit Gemini (Phase 2)
- **Ngày quyết định:** 2026-09-26
- **Người tham gia:** Client (Tùng), PO, Finance Lead, Senior Dev, QA Lead, Independent Reviewer
- **Bối cảnh & Vấn đề:**
  1. `SECTOR_MAP` không được kết nối với Risk Gate, tiềm ẩn rủi ro mở 8/8 vị thế cùng ngành, khiến hệ số tương quan tiệm cận 1.0 làm vô hiệu hóa Half-Kelly.
  2. Mức trượt giá cố định 15 bps (`DEFAULT_SLIPPAGE_BPS`) trong Backtest Engine là sự lạc quan cấu trúc trong thị trường gấu, không phản ánh đúng chi phí thoát hàng khi thị trường sập sàn (50–150 bps).
  3. Quét đa mã đồng thời có thể vượt trần 15 RPM của Gemini API Free tier gây lỗi HTTP 429 và bỏ lỡ cơ hội.
- **Quyết định lựa chọn:**
  1. Triển khai `check_sector_concentration()` trong `quant_engine.py`: Giới hạn tối đa 3 vị thế cùng ngành trong danh mục 8-10 mã (hoặc $\le 25\%$ tổng NAV danh mục). Chặn mua mới nếu vi phạm.
  2. Triển khai `calculate_dynamic_slippage_bps()` trong `backtest_engine.py`: Tăng trượt giá gấp 4.0x khi mua kịch trần (60 bps), gấp 5.0x khi bán tháo kịch sàn (75 bps), tăng khi thanh khoản cạn kiệt (`vol_ratio < 0.5`) và tăng theo quy mô lệnh chiếm tỷ trọng lớn trên ADV20. Trần tối đa 200 bps.
  3. Triển khai `check_and_track_gemini_call()` trong `ai_analyst.py`: Cơ chế Sliding Window 60s, đệm an toàn 12/15 RPM, tự động kích hoạt cooldown và bắn Discord alert danh sách các mã bị hoãn.
- **Hệ quả:** Hệ thống loại bỏ hoàn toàn các điểm mù rủi ro danh mục, mô phỏng chi phí trượt giá sát thực tế thị trường HOSE và bảo vệ hạ tầng gọi AI ổn định 24/7.

---

### [ADR-013] Khung Kiểm Định Walk-Forward, Ma Trận Stress Backtest & Bootstrap Sharpe CI (Phase 3)
- **Ngày quyết định:** 2026-09-26
- **Người tham gia:** Client (Tùng), PO, Finance Lead, Senior Dev, QA Lead, Independent Reviewer
- **Bối cảnh & Vấn đề:**
  1. Mô hình giao dịch thường backtest toàn bộ dữ liệu 2018–2024 trong một lần chạy, tiềm ẩn nguy cơ nghiêm trọng về Look-ahead Bias và Data Snooping.
  2. Thiếu quy trình kiểm tra áp lực (Crisis Stress Matrix) độc lập qua các đợt sập lịch sử lớn nhất của VN-Index: Chiến tranh Thương mại Q4/2018 (-30%), COVID-19 Q1/2020 (-35%), Khủng hoảng Trái phiếu/BĐS 2022 (-45%), và Sóng Bull 2021 (+150%).
  3. Giá trị Sharpe point-estimate với mẫu nhỏ ($N < 30$) không có ý nghĩa thống kê; không phân biệt được giữa may mắn ngẫu nhiên (luck) và lợi thế định lượng thực sự (true quant edge).
- **Quyết định lựa chọn:**
  1. Triển khai `run_walk_forward_backtest()` trong `backtest_engine.py`: Tách bạch 3 giai đoạn không gối đầu: Training (2018–2020), Validation (2020–2022), và Out-of-Sample OOS (2022–2024), khóa cứng tham số Quant Core bằng `ADR-0001` trước khi chạy OOS.
  2. Triển khai `run_crisis_stress_matrix()` và `scan_market_stress_events()` trong `backtest_engine.py`: Tự động cắt chuỗi dữ liệu qua 11 kịch bản lịch sử (Chiến tranh TM 2018, Trump Tariff 2019, COVID 2020, Lockdown Delta 2021, Bull 2021, Bắt bớ FLC/Tân Hoàng Minh 2022, Tăng lãi suất 2022, Vạn Thịnh Phát 2022, Hút tín phiếu Q3/2023, Áp lực DXY Q2/2024, Cạn thanh khoản Q3/2024) và bộ lọc quét Flash Crash 50 điểm/phiên, -4%/phiên, sụt giảm dốc >= 10%.
  3. Triển khai `bootstrap_sharpe_ci()` trong `quant_engine.py`: Tái mẫu $10,000$ lần bằng NumPy vectorization, ước lượng phân vị tin cậy 95% (`ci_lower`, `ci_upper`), tính $p$-value kiểm định Sharpe $\le 0$, hiệu chỉnh tự tương quan (Effective Sample Size), và cảnh báo minh bạch nếu `ci_lower \le 0`.
- **Hệ quả:** Hệ thống chính thức bước lên đẳng cấp **Investment Research Platform**, kiểm định khắt khe theo tiêu chuẩn kinh tế lượng và quản lý quỹ chuyên nghiệp, chống triệt để hiện tượng overfitting.

---

### [ADR-014] Thử Nghiệm Song Song A/B (Quant-Only vs Quant+AI) & Chuẩn Định AI Confidence (Phase 4)
- **Ngày quyết định:** 2026-09-26
- **Người tham gia:** Client (Tùng), PO, Finance Lead, Senior Dev, QA Lead, Independent Reviewer
- **Bối cảnh & Vấn đề:**
  1. Chưa có phương pháp định lượng chứng minh hội đồng AI Gemini tạo ra Alpha thực sự hay chỉ là một tầng phân tích làm đẹp báo cáo nhưng tốn chi phí gọi API.
  2. Nguy cơ từ hiện tượng AI tự tin thái quá (Overconfidence Hallucination): AI phát biểu độ tin cậy 75–85% nhưng tỷ lệ thắng thực tế thấp hơn nhiều. Nếu đưa trực tiếp độ tin cậy này vào Half-Kelly position sizing sẽ gây rủi ro cháy tài khoản.
- **Quyết định lựa chọn:**
  1. Triển khai cấu trúc 2 nhánh thử nghiệm `ARM_QUANT_ONLY` và `ARM_QUANT_AI` cùng hàm `compare_quant_vs_ai_arms()` trong `quant_engine.py`: Bóc tách đối chiếu trực diện Expectancy, Sharpe Ratio, Win Rate và Tần suất lệnh giữa 2 nhánh để đưa ra kết luận khoa học (`POSITIVE_AI_ALPHA`, `NEUTRAL_REPORTING_ONLY`, `NEGATIVE_AI_DRAG`).
  2. Triển khai `check_ai_calibration()` trong `quant_engine.py`: Phân nhóm 5 khoảng confidence (`50-60`, `60-70`, `70-80`, `80-90`, `90-100`), đo lường `calibration_gap` và Brier Score.
  3. Thiết lập Cầu dao An toàn (Safety Circuit Breaker): Nếu AI bị lệch chuẩn (`calibration_gap > 0.15` hoặc bucket cao có actual win rate < 60%), hệ thống tự động ngắt quyền đưa `ai_confidence` vào Half-Kelly position sizing và phát cảnh báo rủi ro.
- **Hệ quả:** Hệ thống đạt chuẩn mực phân tích khoa học tài chính định lượng, minh bạch hóa hoàn toàn giá trị thực của AI và triệt tiêu nguy cơ phá sản do ảo giác của mô hình ngôn ngữ lớn.

---

### [ADR-015] Tối Ưu Hóa Danh Mục, Phân Rã Beta Đa Nhân Tố & Chốt Lời Từng Phần (Phase 5)
- **Ngày quyết định:** 2026-09-26
- **Người tham gia:** Client (Tùng), PO, Finance Lead, Senior Dev, QA Lead, Independent Reviewer
- **Bối cảnh & Vấn đề:**
  1. Thiếu mô hình lượng hóa rủi ro đuôi (Tail Risk) và Drawdown tiềm tàng trong tương lai; các chỉ số quá khứ không lường trước được xác suất chuỗi thua lỗ liên tiếp vượt ngưỡng chịu đựng NAV.
  2. Phân bổ tỷ trọng bằng nhau (Equal-Weight) hoặc ngẫu hứng tạo ra gánh nặng rủi ro bất bình đẳng (các cổ phiếu biến động mạnh như BĐS, Chứng khoán chiếm 70-80% rủi ro danh mục).
  3. Không phân rã được lợi nhuận của vị thế đến từ đâu: do may mắn đu theo sóng thị trường chung (Market Beta), sóng dòng tiền ngành (Sector Beta) hay do lợi thế lựa chọn cổ phiếu vượt trội (Idiosyncratic Alpha).
  4. Cơ chế chốt lời "all-in/all-out" khiến nhà đầu tư dễ bị non gan chốt sớm khi vừa có lãi nhẹ hoặc để mất toàn bộ lợi nhuận khi cổ phiếu đảo chiều từ mức đỉnh cao.
- **Quyết định lựa chọn:**
  1. Triển khai `simulate_monte_carlo_drawdown()` trong `quant_engine.py`: Tái mẫu Bootstrap Monte Carlo $2,000$ đường cong NAV với 63 phiên dự phóng (1 quý giao dịch). Lượng hóa chính xác Max Drawdown trung vị, đuôi xấu nhất P95, P99 và xác suất $P(\text{Drawdown} > 15\%)$.
  2. Triển khai `optimize_portfolio_risk_parity()` trong `quant_engine.py`: Phân bổ tỷ trọng theo nghịch đảo biến động (Inverse Volatility / Equal Risk Contribution), áp trần cứng $25\%$ cho mỗi mã và tái phân bổ phần vốn dư thừa cho các mã còn lại theo đúng tỷ lệ nghịch đảo rủi ro.
  3. Triển khai `calculate_factor_exposures()` trong `quant_engine.py`: Phân rã OLS đa nhân tố gồm $\beta_{\text{market}}$ (so với VN-Index), $\beta_{\text{sector}}$ (so với chỉ số ngành VN30/VNMID) và $\alpha_{\text{idiosyncratic}}$ (Annualized Alpha). Giúp xác định chính xác cổ phiếu có "Alpha thực sự" ($\alpha > 0$ và $R^2 < 0.7$).
  4. Triển khai `evaluate_partial_profit_lock()` trong `quant_engine.py`: Cơ chế chốt lời 2 nấc: Khóa lợi nhuận $50\%$ vị thế tại ngưỡng mục tiêu $+12\%$, đồng thời tự động dời Stop Loss của $50\%$ vị thế còn lại lên điểm hòa vốn (Break-even Stop) cộng phí giao dịch ($+0.3\%$). Khi giá tiếp tục tăng vượt $+15\%$, chuyển sang trailing stop $5\%$.
- **Hệ quả:** Hoàn thiện cỗ máy quản trị danh mục định lượng chuẩn mực quỹ đầu tư (Fund-grade Quantitative Portfolio Engine), bảo vệ tài khoản trước rủi ro sụt giảm cực đoan và tối ưu hóa điểm số Risk-Adjusted Return.

---

### [ADR-016] Tái Cấu Trúc Stress Test, Stationary Block Bootstrap & Quản Trị Rủi Ro Dữ Liệu (Phase 6)
- **Ngày quyết định:** 2026-09-27
- **Người tham gia:** Client (Tùng), PO, Finance Lead, Senior Dev, QA Lead, Independent Reviewer
- **Bối cảnh & Vấn đề (Từ Thẩm Định Due Diligence):**
  1. Mô phỏng rủi ro đuôi Monte Carlo sử dụng giả định độc lập $I.I.D.$ (xáo trộn từng lệnh đơn lẻ) làm phân tán cụm thua lỗ liên tiếp thường thấy trong các cú sốc vĩ mô (loss clustering), khiến chỉ số P95/P99 Drawdown bị đánh giá thấp nghiêm trọng.
  2. Giao diện Stress Test bị "rối" do thiếu phân tầng nhận thức: bảng số liệu thô 8 cột không sort, danh sách ngày sập rời rạc, bắt copy-paste PnL thủ công, thiếu kết luận tóm lược cho nhà đầu tư ở đầu trang.
  3. Mọi điểm ước tính (Sharpe, CAGR, Win Rate) hiển thị đơn lẻ không có khoảng tin cậy 95% và không cảnh báo khi cỡ mẫu nhỏ ($N < 30$).
  4. Sector Gate chưa định lượng được "chi phí bảo hiểm" (Upside hy sinh vs MDD tránh được) để trả lời câu hỏi đánh đổi của nhà đầu tư.
  5. Mỏ neo giá mục tiêu đồng thuận (`INSTITUTIONAL_CONSENSUS_TARGETS`) bị hardcode cố định không có timestamp `last_updated`, tiềm ẩn rủi ro dùng định giá quá hạn làm sai lệch Margin of Safety.
- **Quyết định lựa chọn:**
  1. Triển khai **Stationary Block Bootstrap** trong `simulate_monte_carlo_drawdown()` (`quant_engine.py`): Tái lấy mẫu theo các khối lệnh liên tiếp có kích thước tự thích ứng $L = \max(3, \lfloor n^{1/3} \rfloor)$, bảo toàn các cụm lệnh lỗ liên tiếp trong khủng hoảng.
  2. Tái cấu trúc toàn diện Subtab 4 Stress Test (`tabs/tab_alpha_tracker.py`):
     - Bổ sung *Risk Executive Summary* (4 thẻ KPI đầu trang: MDD tệ nhất, P99 Monte Carlo, Trạng thái Cash Mode, Cảnh báo cỡ mẫu).
     - Thay thế bảng thô 8 cột bằng *Biểu đồ Cột Ngang Đôi (Paired Horizontal Bar Chart)* bằng Plotly, sắp xếp giảm dần theo mức độ sụt giảm VN-Index và tô màu trực quan; thu gọn bảng chi tiết vào expander.
     - Tự động liên kết (Auto-wire) chuỗi PnL từ kết quả backtest sang Monte Carlo mà không bắt người dùng paste tay.
  3. Minh bạch hóa thống kê: Thêm ghi chú cảnh báo cỡ mẫu nhỏ ($N < 30$) dưới bảng KPI phân tích theo Regime.
  4. Triển khai `calculate_sector_gate_insurance_roi()` trong `quant_engine.py` và tích hợp widget định lượng chi phí bảo hiểm minh bạch trên UI.
  5. Bổ sung `last_updated: "2024-10-01"` vào 100% mục trong `INSTITUTIONAL_CONSENSUS_TARGETS` và triển khai `check_institutional_target_freshness()` trong `quant_valuation.py` tự động cảnh báo dữ liệu cũ quá 180 ngày.
- **Hệ quả:** Hệ thống đạt chuẩn mực thẩm định của quỹ đầu tư định lượng tổ chức (Institutional Quant Due Diligence Standard), loại bỏ thiên lệch lạc quan của mô phỏng I.I.D., phân tầng trực quan hóa rõ ràng và minh bạch hóa chi phí bảo vệ vốn.

---

### [ADR-017] Vá Tính Toàn Vẹn Bằng Chứng, Holding-Period Alpha, Replay Idempotent & Đối Soát Tham Số ADR-0002 (TASK-0013)
- **Ngày quyết định:** 2026-09-28
- **Người tham gia:** Client (Tùng), PO, Finance Lead, Senior Dev, QA Lead, Independent Reviewer
- **Bối cảnh & Vấn đề (The Broken Scale Trap):**
  1. Alpha đo lệch chu kỳ: Lấy biến động 1 phiên của VN-Index trừ cho PnL toàn bộ chu kỳ nắm giữ của vị thế.
  2. Audit không idempotent: Chỉ lấy giá ngày chạy; chạm cả Target và Stop cùng ngày thì ưu tiên Target (quá lạc quan); bỏ qua quy chế T+2.5.
  3. Mỏ neo consensus quá hạn (> 180 ngày) vẫn bị trộn 40% vào Fair Value.
  4. Cổ phiếu Growth bị tính giá trị nội tại bằng cách nhân 1.18x làm MoS luôn pass giả tạo (~15.25%).
  5. Data Gate nhận tham số mặc định giả (P/E 12, P/B 1.5, F-Score 7, Z-Score 3.0) trong opportunity scanner.
  6. Lệch pha giữa ADR-0001 (ghi Conviction >= 55) và code live thực thi (yêu cầu >= 70 cho lệnh BUY).
- **Quyết định lựa chọn:**
  1. Triển khai `calculate_holding_period_benchmark_return()`: Tính chuẩn Alpha $T_{\text{in}} \rightarrow T_{\text{out}}$ đối chiếu cả VN-Index và VN30.
  2. Xây dựng hàm `replay_signal_path()`: Bảo đảm tính idempotent 100%, quy tắc bảo thủ (STOP_LOSS trước TARGET_HIT khi cùng ngày chạm cả hai), và gắn cờ `t_plus_2_locked`.
  3. Tích hợp `check_institutional_target_freshness()` vào `calculate_fair_value_and_mos()`: Consensus quá hạn > 180 ngày bị de-weight về 0, hạ confidence xuống LOW, bật cờ `consensus_stale = True`.
  4. Bổ sung cờ `mos_is_informative: bool`: Gán False cho các mã tính FV từ hệ số nhân cố định.
  5. Đấu nối số liệu BCTC thật từ `get_financial_ratios()` vào `scan_market_opportunities()`, trả về `INSUFFICIENT_DATA` khi thiếu.
  6. Ban hành `ADR-0002`: Đóng băng hằng số `LOCKED_QUANT_THRESHOLDS` (Buy Conviction >= 70, Watch >= 55, trọng số 40/25/20/15, AI Veto Only) và thiết lập unit test đối chiếu tự động.
- **Hệ quả:** Thước đo định lượng được sửa chuẩn xác tuyệt đối, loại bỏ toàn bộ dữ liệu giả tạo và ảo tưởng hiệu suất.

---

### [ADR-018] Nhật Ký Quyết Định Universe Panel, Migration 0003, Phân Tách Dispatcher & Evidence Kill Switch (TASK-0014)
- **Ngày quyết định:** 2026-09-28
- **Người tham gia:** Client (Tùng), PO, Finance Lead, Senior Dev, QA Lead, Independent Reviewer
- **Bối cảnh & Vấn đề:**
  1. Thiếu lưu vết lý do TẠI SAO từ chối: Hệ thống chỉ lưu các lệnh BUY phát đi, không lưu các mã bị loại bỏ (REJECT) hoặc đưa vào theo dõi (WATCH), làm mất khả năng đo lường Counterfactual ROI của từng cổng rủi ro.
  2. Bện chặt phân tích với hiển thị: `ai_analyst.py` vừa suy luận vừa gọi trực tiếp Discord alert, gây khó khăn cho việc kiểm thử tự động offline.
  3. Thiếu nhật ký quyết định trên giao diện người dùng.
- **Quyết định lựa chọn:**
  1. Chuẩn hóa schema `DecisionRecord` phân định 4 tầng: FACTS (giá, BCTC), INFERENCES (MoS, F-Score, RSI), OPINIONS (nhận định LLM), COUNTERFACTUAL (cổng từ chối chính, lý do từ chối).
  2. Ban hành Migration `0003_decision_records.sql`: Bổ sung cột cho `signal_lifecycle`, tạo bảng `decision_records`, bảng `decision_forward_returns` với trigger PostgreSQL bất biến `forbid_decision_mutation()`.
  3. Tách kiến trúc: Tạo module `dispatcher.py` độc lập chuyên trách gửi Discord. `ai_analyst.py` tạo và trả về `dataclass SignalEvent` độc lập, test được offline 100% không cần token Discord.
  4. Xây dựng Subtab 5 "Nhật Ký Quyết Định" trên Dashboard (`tabs/tab_alpha_tracker.py`) tra cứu toàn bộ lịch sử BUY/WATCH/REJECT và cổng từ chối.
  5. Tích hợp `check_evidence_kill_switch()`: Tự động cắt giảm 50% quy mô vị thế mở mới khi Expectancy theo R của 20 lệnh gần nhất < 0.
- **Hệ quả:** Hệ thống đạt chuẩn closed-loop learning hoàn chỉnh, kiểm toán toàn diện lý do ra quyết định trên toàn bộ Universe và tự động bảo vệ vốn khi kỳ vọng toán học suy giảm.

---

### [ADR-019] AI Governance & Tối Ưu Hóa Kiến Trúc 3 Tầng: Veto-Only, Wrapper Tập Trung, Fail-Safe Parser & 60-Session Calibration Horizon (TASK-0015)
- **Ngày quyết định:** 2026-09-28
- **Người tham gia:** Client (Tùng), PO, Finance Lead, Senior Dev, QA Lead, Independent Reviewer
- **Bối cảnh & Vấn đề (AI Vulnerability & Pseudo-Probabilities):**
  1. Pass 1 trong `generate_quantamental_2pass_report` gọi trực tiếp `client.models.generate_content`, bỏ qua wrapper tập trung, retry logic, bộ đệm rate-limit (15 RPM) và bộ lọc prompt injection.
  2. Nguy cơ Fallback xác suất giả: Khi LLM trả về JSON lỗi hoặc rác, hàm `_parse_pass1_probabilities` âm thầm fallback về gán `0.25, 0.50, 0.25` kèm lý lẽ bịa đặt, khiến hệ thống tiếp tục tính toán EV và có thể mở vị thế mua trên dữ liệu rác.
  3. Thiếu kiểm soát Veto-Only cứng: LLM không bao giờ được phép tự ý lật ngược trạng thái `can_buy = False` của Quant Core thành `BUY` hoặc tự nâng size Half-Kelly.
  4. Thiếu tính tái lập (Reproducibility & Provenance): Các cuộc gọi LLM chưa khóa cứng `temperature = 0.0`, chưa lưu hash kiểm toán `prompt_hash` (SHA-256) và `input_hash` (SHA-256).
  5. Chu kỳ hiệu chuẩn AI (Calibration Horizon): Đánh giá độ lệch chuẩn (Calibration Gap) của AI cần neo theo đúng chu kỳ 60 phiên giao dịch (khớp vòng đời EXPIRED).
- **Quyết định lựa chọn:**
  1. Gom 100% lệnh gọi Gemini về wrapper tập trung `call_gemini` / `async_call_gemini` với `temperature = 0.0` qua `types.GenerateContentConfig`, rate limit buffer 15 RPM.
  2. Bổ sung `sanitize_prompt_input()` lọc toàn bộ đầu vào tin tức, ghi chú người dùng khỏi các mẫu tấn công Prompt Injection phổ biến.
  3. Tái cấu trúc `_parse_pass1_probabilities` thành Fail-Safe Parser: lỗi JSON lập tức bật cờ `pass1_parse_failed = True`, kích hoạt trạng thái từ chối (`can_buy = False`, `position_size_nav = "0% NAV"`, `action_state = "TỪ CHỐI (LỖI PARSE PASS 1)"`), cấm tuyệt đối fallback xác suất giả 25/50/25.
  4. Đính kèm siêu dữ liệu kiểm toán định chế: `prompt_hash`, `input_hash`, `model_id`, `temperature = 0.0` vào kết quả phân tích và Decision Record.
  5. Thiết lập `check_ai_calibration(horizon_days=60)` và `calibrate_scenario_probabilities(horizon_days=60)`: Lọc dữ liệu giao dịch và phân phối xác suất kịch bản theo chu kỳ 60 phiên giao dịch, tính toán Brier Score và Calibration Gap cho từng kịch bản Bull/Base/Bear.
  6. Triển khai trọn bộ 13 unit tests chuyên biệt trong `tests/test_task_0015_ai_governance.py` bảo đảm 100% pass và SonarCloud clean.
- **Hệ quả:** Hệ thống đóng băng hoàn toàn rủi ro ảo giác từ AI, bảo đảm tính tất định và khả năng tái lập kiểm toán toán học, bảo vệ vốn tuyệt đối trước mọi sự cố sập cấu trúc của LLM.

---

### [ADR-020] Exit Hypothesis Lab, Paired Bootstrap & Kiểm Định Thống Kê Conviction Weights với Spearman IC & Benjamini–Hochberg FDR (TASK-0016)
- **Ngày quyết định:** 2026-09-28
- **Người tham gia:** Client (Tùng), PO, Finance Lead, Senior Dev, QA Lead, Independent Reviewer
- **Bối cảnh & Vấn đề (Exit Replay Rigor & Data Snooping Prevention):**
  1. Chiến lược thoát lệnh hiện tại (Policy A: Lãi $\ge +12\%$ chốt 50%, dời SL về BE) chưa từng được đối chiếu khách quan với các phương án định chế chuẩn (Policy B: R-Multiple $+2R$, Policy C: ATR Trailing $2.5\times$, Policy D: All-or-Nothing).
  2. Nguy cơ Rule Snooping / Overfitting: Nếu tùy tiện đổi luật bán theo cảm tính sau mỗi nhịp thị trường, chiến lược sẽ rơi vào bẫy đường cong hồi quy giả tạo. Cần một phòng thí nghiệm Replay offline độc lập hoạt động nghiêm ngặt ở chế độ "Chỉ Báo Cáo" (Report-Only).
  3. Kiểm định trọng số 4 trụ cột Conviction (MoS 40%, F-Score 25%, TA 20%, Flow 15%): Cần đo lường hệ số tương quan hạng Spearman (Spearman IC) đối với Alpha thực tế $T+20$, đồng thời bắt buộc loại trừ các bản ghi có `mos_is_informative = False` (do suy từ hệ số nhân cố định 1.18x).
  4. Vấn đề Đa so sánh (Multiple Testing & False Discovery): Khi kiểm định đồng thời nhiều yếu tố, xác suất ngẫu nhiên bắt gặp một biến "có vẻ hiệu quả" tăng vọt. Cần cơ chế kiểm soát False Discovery Rate (FDR).
  5. Nguyên tắc "Thu thập trước, Hồi quy sau": Tuyệt đối cấm cập nhật trọng số khi cỡ mẫu quan sát $N < 100$.
- **Quyết định lựa chọn:**
  1. Xây dựng module `Exit Hypothesis Lab` trong `backtest_engine.py`:
     - Hiện thực hóa 4 hàm mô phỏng thoát lệnh độc lập: `_simulate_policy_a`, `_simulate_policy_b`, `_simulate_policy_c`, `_simulate_policy_d` và `simulate_exit_policy`.
     - Áp dụng phương pháp **Paired Bootstrap** (1,000 resamples trên cùng tập lệnh) trong `run_exit_hypothesis_lab()`, đối chiếu Expectancy theo R ($\text{PnL}/R$), Win Rate, Max Drawdown và tính khoảng tin cậy 95% chênh lệch $\Delta \text{Expectancy}$ kèm $p$-value so sánh với Baseline A.
     - Khóa cứng cờ `report_only = True` và phát thông điệp `EXIT_LAB_REPORT_DISCLAIMER` cấm tự động cập nhật hệ thống live khi chưa có ADR mới.
  2. Xây dựng pipeline kiểm định trọng số trong `quant_engine.py`:
     - Viết `calculate_pillar_spearman_ic()`: Tính Spearman IC thuần qua Standard Library + Pandas rank (không phụ thuộc Scipy), lọc sạch các bản ghi có `mos_is_informative = False`.
     - Viết `apply_benjamini_hochberg_fdr()`: Thực hiện kiểm định step-up Benjamini–Hochberg kiểm soát FDR ở mức $\alpha = 0.05$.
     - Bật cảnh báo `INSUFFICIENT_SAMPLE` khi quy mô mẫu $N < 100$, ngăn ngừa việc tối ưu hóa vội vàng khi thiếu dữ liệu.
  3. Tạo bộ unit tests chuyên biệt `tests/test_task_0016_exit_lab_and_ic.py` (12 tests) đạt 100% pass, đưa toàn bộ suite lên 289 tests xanh.
- **Hệ quả:** Hoàn tất trọn vẹn Phase 7 trong lộ trình `stock_ai_roadmap.md`, thiết lập nền tảng khoa học dữ liệu và thống kê định chế vững chắc cho toàn bộ hệ thống Stock-AI.

---

### DECISION-0017: Bản vá Khắc phục Lỗ hổng Hệ thống Báo cáo Phiên ATC & Chuẩn hóa Single Source of Truth VN-Index (TASK-0017 - Hotfix v6.1.1)
- **Ngày:** 2026-09-29
- **Trạng thái:** `APPROVED / IMPLEMENTED`
- **Người tham gia:** Client, PO, Finance Lead, Senior Dev, QA Lead, Independent Reviewer
- **Bối cảnh & Vấn đề (ATC Report Data Integrity & Allocation Conflict):**
  1. VN-Index trả về `0.00 điểm`: Hàm `generate_portfolio_analysis()` trong `ai_analyst.py` nhận `vnindex_tech=None` nhưng không có cơ chế auto-fetch fallback như báo cáo ATO, khiến prompt Gemini nhận điểm số 0.00.
  2. Thiếu Delta điểm số: `fetch_stock_technical()` chỉ tính `change_pct` (%), thiếu số điểm tăng/giảm tuyệt đối ($\Delta \text{Điểm}$) và khoảng cách MA20/MA50, khiến phân tích kỹ thuật thiếu chiều sâu định lượng.
  3. Xung đột tỷ lệ Tiền/Cổ phiếu: Sáng (ATO) báo 50/50 từ `quant_engine`, Chiều (ATC) lại hardcode `stock_pct: 70% / cash_pct: 30%` tại dòng 341 `ai_analyst.py`, vi phạm nguyên tắc Single Source of Truth (SSOT).
- **Quyết định lựa chọn:**
  1. **Chuẩn hóa tính toán Delta trong `data_engine.py`:**
     - Bổ sung `diff_points` ($P_{\text{close}} - P_{\text{ref}}$), `diff_ma20`, `diff_ma50` vào `fetch_stock_technical()`.
     - Tích hợp nạp và đồng bộ hóa bộ nhớ đệm `_LAST_KNOWN_TECH_CACHE` xuống disk (`data/last_known_tech.json`) phòng thủ chống rớt mạng / lỗi API.
  2. **Tái cấu trúc `generate_portfolio_analysis()` trong `ai_analyst.py`:**
     - Tự động gọi `fetch_stock_technical("VNINDEX")` khi `vnindex_tech` bị thiếu hoặc rỗng.
     - Xóa bỏ hoàn toàn dict hardcode 70/30, hợp nhất 100% với `quant_engine.evaluate_market_regime()` (SSOT).
     - Đưa thông số kỹ thuật VN-Index (Điểm số, $\Delta$ Điểm, % thay đổi, MA20, MA50, RSI) vào Section 0 và Section I của prompt.
  3. **Tối ưu hóa `trading_bot.py` & Scripts:**
     - Pre-fetch `vnindex_tech` một lần trong `trigger_scheduled_report` và truyền vào các hàm phân tích AI.
  4. **Kiểm thử & Chất lượng:**
     - Tạo bộ test chuyên biệt `tests/test_task_0017_atc_report_fixes.py` (5 tests PASSED 100%), toàn bộ suite đạt 299 tests PASSED.
     - `ruff check . --output-format=github` đạt exit code 0.
- **Hệ quả:** Báo cáo ATC và ATO đồng bộ 100% về tỷ trọng danh mục và điểm số chỉ số vĩ mô; loại bỏ hoàn toàn hiện tượng 0.00 điểm và xung đột khuyến nghị.

---

### [ADR-021] Tích Hợp Daily Analyst Report Pipeline & Context Engine (TCBS) với Regime Arbitration & Zero-Fabrication (TASK-0018 / v6.3)
- **Ngày quyết định:** 2026-09-30
- **Trạng thái:** `APPROVED / IMPLEMENTED`
- **Người tham gia:** Client, PO, Finance Lead, Senior Dev, QA Lead, Independent Reviewer
- **Bối cảnh & Vấn đề (Market Context Integration & Zero-Fabrication Rigor):**
  1. Thiếu tầng bối cảnh thị trường chuyên gia (Macro & Sentiment Context): AI Analyst và Portfolio Manager phân tích chỉ dựa trên số liệu thuần Python, bỏ lỡ các nhận định vĩ mô, ngành tâm điểm và dòng tiền cá mập từ báo cáo phân tích kỹ thuật (BC PTKT) hàng ngày của TCBS.
  2. Cấu trúc tài liệu tham chiếu chưa được phân loại và quản lý trạng thái: Trộn lẫn báo cáo doanh nghiệp, vĩ mô và giao dịch nội bộ; thiếu cơ chế theo dõi file nào đã nạp context.
  3. Nguy cơ ảo giác và sáng tác dữ liệu (Hallucination/Fabrication): Báo cáo CTCK là nguồn INFERENCE bậc cao. Tuyệt đối không được sáng tác hay suy diễn số liệu ngoài văn bản PDF.
  4. Xung đột xu hướng (Regime Conflict): Chuyên gia CTCK có thể nhận định chủ quan khác với xu hướng tính từ MA200 định lượng (`regime_classifier.py`). Cần trọng tài phân xử tất định.
- **Quyết định lựa chọn:**
  1. **Tái cấu trúc và Quản lý Manifest (`docs/Reference/`):**
     - Phân loại 5 nhóm: `PTKT_Daily/`, `Stock_Analysis/`, `Insider_Trading/`, `Macro/`, `Archive/`.
     - Tự động duy trì `manifest.json` theo dõi trạng thái `processed`, ngày báo cáo, và đường dẫn file context.
  2. **Pipeline Trích xuất Dữ liệu Sạch (`scripts/parse_daily_reports.py`):**
     - Ứng dụng `PyMuPDF` trích xuất văn bản từ PDF báo cáo hàng ngày mới nhất.
     - Trích xuất chuẩn hóa: Ngày, Nguồn TCBS, Xu hướng, Điểm số/Delta VN-Index, Ngành tâm điểm, Từ khóa rủi ro, Tín hiệu Mua/Bán CTCK, và Đoạn tóm tắt diễn biến.
     - Tuân thủ nguyên tắc Zero-Fabrication: Trường không có trong văn bản mặc định là `[]` hoặc `"UNKNOWN"`, tuyệt đối không bịa đặt số liệu.
     - Xuất dữ liệu ra `data/market_context.json`.
  3. **Module Context Engine (`context_engine.py`):**
     - Định nghĩa dataclass `MarketContext` và hàm `load_market_context()`.
     - Chốt chặn Fail-Safe: File thiếu, file hỏng hoặc stale date tự động chuyển về `is_valid = False` (Non-blocking, không bao giờ làm sập hệ thống).
     - Trọng tài Xung đột Regime (`check_regime_conflict()`): Code MA200 (FACT) luôn luôn thắng nhận định CTCK (INFERENCE). Nếu Code báo UPTREND nhưng Chuyên gia báo DOWNTREND -> Bật cờ xung đột và giảm 50% quy mô vị thế đề xuất để phòng thủ; nếu Code báo DOWNTREND nhưng Chuyên gia báo UPTREND -> Giữ nguyên Cash Mode, cấm mở mua.
     - Hàm `build_context_prompt_snippet()` đóng gói thông tin xúc tích kèm cảnh báo quản trị để inject vào prompt LLM.
  4. **Tích hợp Kiến trúc & Lưu vết Kiểm toán:**
     - Tạo migration `migrations/0004_analyst_context.sql` bổ sung 4 trường vào `decision_records`: `analyst_context_used`, `regime_conflict`, `context_source_file`, `context_date`.
     - Mở rộng `SignalEvent` trong `dispatcher.py` và luồng phân tích trong `ai_analyst.py`.
  5. **Kiểm thử & Tiêu chuẩn Chất lượng:**
     - Xây dựng 24 unit tests chuyên biệt trong `tests/test_task_0018_context_engine.py` (23 passed, 1 env-skip).
     - `ruff check . --output-format=github` đạt exit code 0.
- **Hệ quả:** Bổ sung trọn vẹn tầng ngữ cảnh thị trường hàng ngày từ TCBS cho AI Analyst mà vẫn giữ vững 100% tính toàn vẹn và kỷ luật thép của Quant Gate; hoàn tất thành công Phase 8 (v6.3).

---

### [ADR-022] Cải Tổ Toàn Diện Mô Hình Định Giá BĐS & Tập Đoàn Đa Ngành Bằng BCTC Thực (TASK-0024 -> 0028 / v7.0)
- **Ngày quyết định:** 2026-10-01
- **Trạng thái:** `APPROVED / IMPLEMENTED`
- **Người tham gia:** Client, PO, Finance Lead, Senior Dev, QA Lead, Independent Reviewer
- **Bối cảnh & Vấn đề (Real Estate Valuation Blind Spots & Naive Multiple Elimination):**
  1. Mô hình định giá BĐS trước đây trong `quant_valuation.py` sử dụng công thức giả định `current_price * 1.10 * leverage_penalty` và VIC `current_price * 1.15`, hoàn toàn không dựa vào BCTC thực, khiến Fair Value chạy theo thị giá và làm méo mó ý nghĩa của Margin of Safety (MoS).
  2. Bỏ qua chiết khấu tập đoàn (Holding Discount): VIC có tới 63.8% vốn hóa trả cho mảng chưa niêm yết (VinFast, Vinpearl...). Nếu mảng niêm yết chiếm quá ít mà mảng chưa niêm yết đốt tiền, hệ thống vẫn khuyến nghị MUA là rủi ro nghiêm trọng.
  3. Mù mờ chất lượng lợi nhuận: LNTT của VIC có tới 86% từ bán tài sản một lần, chỉ 14% từ kinh doanh cốt lõi. Bot đọc EPS thô và định giá rẻ mà không biết đây là "bán đồ trong nhà".
  4. Bẫy nợ vay & EBITDA chưa chuẩn hóa: Nợ ròng / EBITDA thực tế lên tới 7-8x trong khi EBITDA công bố phồng to do lãi tài chính một lần.
  5. Thiếu P/B Guardrail cho BĐS: P/B của VIC lên tới 10.5x (> Mean + 3σ) nhưng hệ thống vẫn có thể xếp loại "HẤP DẪN".
- **Quyết định lựa chọn:**
  1. **Thay thế định giá naive bằng BCTC thực (`quant_valuation.py`):**
     - Sử dụng Book Value Per Share (BVPS thực tế) và Target P/B chuẩn hóa dựa trên ROE (1.05x - 1.45x).
     - Chiết khấu cấu trúc nợ, chiết khấu holding, chiết khấu chất lượng lợi nhuận và chiết khấu P/B guardrail (tối đa trần 50%).
  2. **SOTP Sanity Check (`check_sotp_holding_sanity()` - TASK-0024):**
     - Tính tỷ lệ $\text{SOTP Ratio} = \sum (\text{Vốn hóa CTC niêm yết} \times \% \text{ sở hữu}) / \text{Vốn hóa mẹ}$.
     - Nếu $< 50\% \rightarrow$ Cắm cờ `SOTP_ANOMALY`, hạ confidence = LOW.
     - Nếu $< 30\% \rightarrow$ Bật cờ `SOTP_DISCOUNT_CRITICAL`, khóa khuyến nghị MUA, chiết khấu 20% Fair Value.
  3. **Quality of Earnings Gate (`calculate_core_earnings_ratio()` - TASK-0025):**
     - Core Ratio $= (\text{Gross Profit} - \text{SG&A}) / \text{PBT}$.
     - Nếu $< 40\% \rightarrow$ Cắm cờ `EARNINGS_QUALITY_LOW`, chiết khấu Fair Value 15%, hạ confidence = LOW.
     - Nếu PBT $\le 0 \rightarrow$ Cắm cờ `EARNINGS_QUALITY_NEGATIVE_PBT`, chiết khấu 20%.
  4. **Survival Gate (`reconcile_real_estate_survival_gate()` - TASK-0026):**
     - Chuẩn hóa EBITDA: $\text{Normalized EBITDA} = \text{EBITDA} - \text{Thu nhập tài chính bất thường} - \text{Lãi bán tài sản}$.
     - Gate 1: Net Debt / Normalized EBITDA $> 5.0x \rightarrow$ Khóa MUA + cờ `DEBT_OVERLOAD`.
     - Gate 2: Nợ ngắn hạn / Tổng nợ $> 40\% \rightarrow$ Chiết khấu Fair Value 10% + cờ `REFINANCING_RISK`.
     - Gate 3: Normalized EBITDA / Lãi vay $< 1.5x \rightarrow$ Khóa MUA + cờ `INTEREST_COVERAGE_CRITICAL`.
  5. **Mở rộng P/B Mean Reversion Guardrail cho REAL_ESTATE (TASK-0028):**
     - Nếu P/B $> \text{Mean} + 3\sigma \rightarrow$ Khóa trần rating tối đa là "ĐỊNH GIÁ ĐỦ" (cấm xếp HẤP DẪN / RẤT RẺ), cắm cờ `PB_EXTREME_PREMIUM`, hạ confidence = LOW, chiết khấu 15%.
     - Nếu P/B $> \text{Mean} + 2\sigma \rightarrow$ Cắm cờ `PB_ELEVATED_PREMIUM`, chiết khấu 10%.
  6. **Mở rộng Prompt AI Analyst (TASK-0027):**
     - Yêu cầu phân tích 3 chiều: Cash Cow vs Cash Burner, Runway tự nuôi, và Cross-Subsidy Risk khi phân tích holding company.
  7. **Kiểm thử & Đảm bảo Chất lượng:**
     - Bộ 21 unit tests tại `tests/test_task_0024_real_estate_valuation.py` đạt 100% pass.
     - `ruff check . --output-format=github` đạt exit code 0.
- **Hệ quả:** Loại bỏ hoàn toàn 5 điểm mù trong định giá BĐS & holding company; hệ thống có chốt chặn định lượng vững chắc chống bẫy giá trị và bẫy nợ; hoàn tất xuất sắc Phase 10 (v7.0).

---

### [ADR-023] Cải Tổ Toàn Diện Mô Hình Định Giá Cổ Phiếu Chu Kỳ (Cyclical Valuation Overhaul - Dầu Khí, Thép, Hóa Chất) (TASK-0029 -> 0032 / v7.1)
- **Ngày quyết định:** 2026-10-01
- **Trạng thái:** `APPROVED / IMPLEMENTED`
- **Người tham gia:** Client, PO, Finance Lead, Senior Dev, QA Lead, Independent Reviewer
- **Bối cảnh & Vấn đề (Bẫy P/E Đỉnh Chu Kỳ & Bài Học Nghiệp Vụ từ Case Study BSR):**
  1. **Bẫy P/E thấp tại đỉnh chu kỳ (Peak Earnings Trap):** Cổ phiếu chu kỳ hàng hóa (Dầu khí, Thép, Hóa chất) thường hiển thị P/E rất hấp dẫn ($4x - 8x$) ngay tại đỉnh lợi nhuận khi crack spread hoặc giá hàng hóa đạt đỉnh do sự kiện bất khả kháng (như BSR hưởng lợi từ xung đột Hormuz). Hệ thống nhìn thấy P/E thấp sẽ lầm tưởng là cổ phiếu "rẻ", trong khi biên lợi nhuận gộp đã bắt đầu rơi dốc (ví dụ BSR lùi từ 20.7% xuống 14.7%).
  2. **Biến dạng EPS do lợi nhuận đột biến một lần:** EPS trailing 12 tháng bị phồng to bởi khoản lợi nhuận đột biến một lần không thể lặp lại (+15.700 tỷ 6T đầu năm). Lợi nhuận bền vững thực chất chỉ từ 5.000–8.000 tỷ/năm (EPS chuẩn hóa 1.000–1.600đ so với trailing 3.974đ). Dùng EPS trailing tính Fair Value làm lệch hẳn giá trị nội tại.
  3. **Mù mờ tương quan định giá quốc tế (Peer Comparison):** BSR giao dịch ở P/B = 2.0x — đắt gấp đôi trung vị các nhà máy lọc dầu châu Á (Asian Refineries median P/B ~ 1.0x, P/E ~ 4.1x). Bot không có dữ liệu peer nên không cảnh báo được mức định giá đắt đỏ này.
  4. **Thiếu cảnh báo rủi ro đặc thù ngành (Sector Risk Flags):** Các rủi ro chí mạng của ngành lọc dầu (DSI tồn kho > 45 ngày gặp giá dầu giảm, biên gộp giảm liên tiếp, rủi ro hết hạn ưu đãi thuế 30/09/2026, rủi ro 1 cụm nhà máy duy nhất) và ngành thép (HRC Trung Quốc bán phá giá, tồn kho dồn ứ) chưa được lượng hóa vào Data Gate.
  5. **Mô hình CYCLICAL cũ mang tính tượng trưng (Naive):** Sử dụng các hệ số nhân thô `current_price * 1.02` và `current_price * 1.20`.
- **Quyết định lựa chọn:**
  1. **Peak Earnings Trap Detector (`check_peak_earnings_trap()` - TASK-0029):**
     - Nếu P/E < 6.5x VÀ Biên gộp giảm liên tiếp $\ge 2$ quý (hoặc xu hướng DOWN):
       - `is_peak_trap = True`, khóa khuyến nghị MUA (`recommendation_allowed = False`).
       - Bắt buộc gán nhãn `VAL_RATING_EXPENSIVE` ("🔴 ĐỊNH GIÁ QUÁ ĐẮT").
       - Áp dụng chiết khấu Fair Value 20%, hạ `confidence = "LOW"`.
  2. **Normalized Mid-Cycle EPS & Trimmed Mean 5Y (`calculate_trimmed_normalized_eps()` - TASK-0030):**
     - Thu thập chuỗi EPS 5 năm, loại bỏ năm cao nhất (đỉnh bất thường) và năm thấp nhất (đáy sự cố) để tính Normalized EPS trung hòa chu kỳ.
     - Tính `normalized_pe = current_price / normalized_eps`.
     - Áp dụng hệ số Mid-Cycle multiple 8.5x trên Normalized EPS để xác định Fair Value nền tảng.
  3. **Regional Peer Comparison Benchmark (`check_cyclical_peer_benchmark()` - TASK-0031):**
     - Xây dựng mỏ neo `CYCLICAL_PEER_BENCHMARKS` cho 3 phân ngành: Lọc dầu (`OIL_REFINING`), Thép (`STEEL`), và Hóa chất / Phân bón (`CHEMICAL_FERTILIZER`).
     - Nếu P/B $> \text{Median} \times 2.0 \rightarrow$ Bật cờ `PEER_PREMIUM_EXTREME`, khóa xếp hạng HẤP DẪN / RẤT RẺ (chuyển về tối đa ĐỊNH GIÁ ĐỦ), chiết khấu Fair Value 15%.
     - Nếu P/B $> \text{Median} \times 1.5 \rightarrow$ Bật cờ `PEER_PREMIUM_WARNING`, chiết khấu Fair Value 10%.
  4. **Sector-Specific Risk Flags (`check_sector_risk_flags()` - TASK-0032):**
     - Dầu khí: Cảnh báo `INVENTORY_RISK` (DSI > 45 ngày), `MARGIN_TREND_DOWN`, `POLICY_EXPIRING` (hết hạn thuế 30/09/2026), `SINGLE_PLANT_RISK`.
     - Thép: Cảnh báo `CHINA_DUMPING_RISK` và `INVENTORY_BUILDUP` (tồn kho tăng > 20% QoQ).
     - Tích hợp tự động vào quy trình kiểm định `reconcile_data()` của `data_gate.py`.
  5. **Cải tổ toàn diện nhánh CYCLICAL trong `quant_valuation.py`:**
     - Tích hợp đồng bộ 4 cấu phần trên trong `evaluate_cyclical_valuation()` và liên kết vào `calculate_fair_value_and_mos()`.
  6. **Kiểm thử & Đảm bảo Chất lượng:**
     - Bộ 14 unit tests tại `tests/test_task_0029_cyclical_valuation.py` đạt 100% pass.
     - Toàn bộ test suite 383 unit tests chạy mượt mà không lỗi.
     - `ruff check . --output-format=github` đạt exit code 0.
     - Tuân thủ nghiêm ngặt SonarCloud S3776 (Cognitive Complexity < 15), S8572 (`logging.exception`), S1192 (hằng số cờ rủi ro).
- **Hệ quả:** Hệ thống chính thức làm chủ nghiệp vụ định giá chu kỳ hàng hóa theo chuẩn mực quỹ đầu tư chuyên nghiệp (CFA Institute standard); xóa bỏ triệt để bẫy P/E giá rẻ ảo tại đỉnh lợi nhuận; hoàn tất xuất sắc Phase 11 (v7.1).

---

### [ADR-024] Xây dựng Broad Market Pool & Rotating Cursor cho Active Screener
- **Ngày quyết định:** 2026-10-01
- **Người tham gia:** Client, AI
- **Bối cảnh & Vấn đề:**
  - Active Market Screener (`scan_market_opportunities` trong `data_engine.py`) trước đó bị hard-code giới hạn chỉ ưu tiên quét 6 mã trụ cột lớn nhất (`TOP_MARKET_SYMBOLS`) và Watchlist cá nhân.
  - Hạn mức Rate limit 20 req/min của thư viện vnstock buộc danh sách mỗi lần quét phải khống chế ở 8 mã.
  - Hậu quả: Các cổ phiếu vào pha đáy chu kỳ (Deep Value) như PVD bị lọt lưới nếu không có tin tức vĩ mô nổi bật hoặc không được nạp tay vào Watchlist.
- **Quyết định lựa chọn:**
  - Thay thế `TOP_MARKET_SYMBOLS` bằng `BROAD_MARKET_POOL` gồm 56 mã đại diện (VN30 + Midcap tiêu biểu).
  - Triển khai biến `_market_scanner_cursor` chạy theo cơ chế Round-Robin.
  - Trong mỗi nhịp chạy, các slot còn trống (để max 8 mã) sẽ được tự động lấp đầy bằng mã lấy từ `BROAD_MARKET_POOL` dựa trên cursor.
- **Hệ quả:** Radar hoạt động xoay vòng 360 độ, quét 100% các mã bluechip và midcap chất lượng sau mỗi 2-3 giờ, đảm bảo không bỏ sót bất kỳ cơ hội Deep Value nào mà không vi phạm Rate Limit.

---

### [ADR-025] Triệt Tiêu Ảo Ảnh Biên An Toàn MoS Tự Sinh (Anti-Synthetic MoS) & Chuẩn Hóa Target Buy (Phase 12 - v7.2)
- **Ngày quyết định:** 2026-10-02
- **Người tham gia:** Client, PO, Finance Lead, Senior Dev, QA Lead
- **Bối cảnh & Vấn đề:**
  - Qua trường hợp MWG, phát hiện khi mỏ neo consensus bị stale quá hạn 180 ngày, nhánh `GROWTH_COMPOUNDER` tự fallback sang công thức nhân cứng $FV = Current\_Price \times 1.18$.
  - Khi đó, $MoS = \frac{1.18 \times P - P}{1.18 \times P} = 15.25\% \approx 15.3\%$ là một hằng số cơ học tự sinh, xuất hiện tại mọi mức giá và đánh lừa bộ quét tự động `sync_auto_watchlist()`.
  - Bộ quét nạp nhầm `target_buy` thành `current_price = 72.6k` do fallback khi không có target_price.
  - Hệ thống thiếu bộ lọc xu hướng trung hạn MA100/MA200 và điểm trừ bán ròng ngoại kỷ lục.
- **Quyết định lựa chọn:**
  1. Triển khai chốt chặn `effective_mos = mos_is_informative and mos_pct >= 15.0` trong `_build_auto_watchlist_candidate()`. Cấm tuyệt đối nạp vào Watchlist dưới cờ MoS nếu `mos_is_informative is False`.
  2. Chuẩn hóa `target_buy`: Tuyệt đối không fallback về `current_price`. Nếu không có giá mục tiêu chốt lời định lượng, `target_buy` phải để `0.0`.
  3. Bổ sung tính toán `MA100` và `MA200` vào `fetch_stock_technical()`. Khóa khuyến nghị `RECOMMEND_BUY` nếu giá nằm dưới `MA100 * 0.98`.
  4. Bổ sung điểm phạt xả ròng khối ngoại (Foreign Net Flow Penalty: -5đ đến -10đ) trong `calculate_conviction_score()`.
  5. Cập nhật mỏ neo đồng thuận MWG (`83.5k`, `last_updated: "2026-09-30"`).
  6. Làm sạch `data/watchlist.json` loại bỏ bản ghi MWG sai lệch.
- **Hệ quả:** Loại bỏ hoàn toàn các khuyến nghị dựa trên MoS ảo; đảm bảo tính toàn vẹn, trung thực và minh bạch 100% của danh mục Watchlist tự động. Hoàn tất Phase 12 (v7.2).

---

### [ADR-026] Tái Cấu Trúc Cốt Lõi Định Giá Thực Chất (Intrinsic Valuation), Quản Trị Rủi Ro Cấu Trúc & Vùng Đệm Trễ Vĩ Mô (Phase 13 - v7.3)
- **Ngày quyết định:** 2026-10-02
- **Người tham gia:** Client, PO, Finance Lead, Senior Dev, QA Lead, Independent Reviewer
- **Bối cảnh & Vấn đề:**
  - Qua thẩm định sâu mã nguồn `quant_valuation.py`, phát hiện công thức `fv_base = current_price * 1.18` trong nhánh `GROWTH_COMPOUNDER` tạo ra hàm số phụ thuộc thị giá ($FV = 0.708 \times P + 28.39$), biến Biên an toàn (MoS) thành một định đề toán học luôn dương giả tạo ($15.3\%$) khi thiếu consensus.
  - Nhánh `BANK` cũng fallback `current_price * 1.12` khi thiếu P/B.
  - Ngưỡng dừng lỗ cơ học `price * 0.93` (-7%) trùng khớp biên độ sàn 1 phiên của HOSE, gây bẫy thanh khoản và rủi ro mất khả năng thoát hàng khi cổ phiếu giảm sàn trắng bên mua.
  - Cổng vĩ mô ngắt nhị phân khi VN-Index chạm MA200 tạo ra hiện tượng whipsaw (mua đỉnh bán đáy trong vùng thị trường đi ngang).
  - Data Gate thiếu chốt chặn xử phạt dữ liệu đóng băng theo từng trường (`as_of_date`).
- **Quyết định lựa chọn:**
  1. **Xóa bỏ vĩnh viễn $P \times 1.18$ & $P \times 1.12$:**
     - Xây dựng hàm `evaluate_compounder_valuation()` định giá nội tại thực chất dựa trên $Forward\_EPS \times Historical\_Median\_PE$ và mô hình SOTP đa mảng (MWG: ICT Core 40k + BHX 38k + Khác 7k = 85k).
     - Áp dụng nguyên tắc Fail-Safe: Nếu thiếu dữ liệu cơ bản, trả về `fair_value = 0.0`, `mos_is_informative = False`, và `INSUFFICIENT_DATA`. Tuyệt đối cấm dẫn xuất FV từ thị giá.
  2. **Khóa cứng MoS Uninformative (Hard Gate):**
     - Tại `quant_engine.py`: Nếu `mos_is_informative is False` hoặc `fair_value <= 0`, khóa cứng `gate_mos_passed = False`, cấm dùng MoS để kích hoạt lệnh Mua giá trị.
  3. **Quản lý Vòng đời Consensus Target $\le 90$ ngày:**
     - Rút ngắn thời hạn tối đa `max_age_days = 90` (thay vì 180 ngày). Quá 90 ngày tự động de-weight về 0 và gắn cảnh báo `is_stale = True`.
  4. **Dừng lỗ Cấu trúc & Định cỡ Vị thế Phòng vệ Gap Sàn:**
     - Triển khai `calculate_structural_stop_loss()` neo theo Swing Low, Base Support, MA50 trừ đệm $0.5 \times ATR$.
     - Triển khai `calculate_gap_risk_position_sizing()` stress-test kịch bản 2 cây sàn liên tiếp ($-14\%$) để đảm bảo tổn thất tối đa $\le 1.5\%$ NAV.
  5. **Cổng Vĩ mô có Vùng Đệm Trễ (Macro Hysteresis):**
     - Triển khai `classify_regime_ma200_hysteresis()` với vùng trễ $\pm 1.5\% - 2.0\%$ và điều kiện xác nhận 2 phiên liên tiếp (hoặc volume bán tháo đột biến $> 1.3 \times ADV20$) nhằm triệt tiêu whipsaw.
  6. **Data Gate Field-level Freshness:**
     - Gắn cờ `FLAG_DATA_STALE_FREEZE`, tự động khóa khuyến nghị đầu tư khi dữ liệu BCTC chậm nộp quá 180 ngày.
- **Hệ quả:** Hệ thống đạt chuẩn CFA về tính độc lập của mô hình định giá với thị giá; triệt tiêu hoàn toàn rủi ro bẫy sàn HOSE và whipsaw MA200; 100% test suites (58/58 tests) đạt kết quả Green. Hoàn tất Phase 13 (v7.3).

---

### [ADR-027] Khắc Phục Đứt Gãy Dẫn Truyền Dữ Liệu BCTC (fin_dict Plumbing), Ánh Xạ P&L Danh Mục & Kiểm Soát Độ Tươi Bối Cảnh (Phase 14 - v7.4)
- **Ngày quyết định:** 2026-10-02
- **Người tham gia:** Client, PO, Finance Lead, Senior Dev, QA Lead, Independent Reviewer
- **Bối cảnh & Vấn đề:**
  - Qua cuộc kiểm toán toàn diện hệ thống ngày 02/10/2026, phát hiện lỗ hổng nghiêm trọng: `fin_dict` không bao giờ được truyền vào `calculate_fair_value_and_mos()` tại các luồng thực thi nền (`scan_market_opportunities()`, `_process_single_watchlist_item()`, `evaluate_portfolio()`, `evaluate_watchlist()`, và `_prepare_smart_committee_context()`).
  - Toàn bộ hệ thống chạy trên nhánh fallback, khiến Biên an toàn (MoS) của mọi archetype biến thành các hằng số vô nghĩa (GROWTH=15.25%, BANK=10.71%, CYCLICAL=−17.65%), làm mất đi tính khách quan của các mô hình định giá nội tại.
  - Các tham số `symbol`, `fin_dict`, `sector`, `tech_data` bị bỏ quên khi gọi `evaluate_decision_hard_gates()` trong `generate_quantamental_2pass_report()`.
  - Hàm `_build_portfolio_quant_summary()` và `evaluate_holding_position()` đọc key tiếng Anh trong khi DataFrame danh mục trả về các cột tiếng Việt (`"Giá TB (k)"`, `"Giá vốn (k)"`, `"Thị giá (k)"`, `"Giá hiện tại (k)"`), dẫn đến `entry_price = 0.0`, `pl_pct = 0.0%`, khiến mọi vị thế có lãi đều bị phân loại nhầm thành "LỖ" và vô hiệu hóa Trailing Stop.
  - Cờ `mos_is_informative` trả về `True` cho CYCLICAL và REAL_ESTATE ngay cả khi `fin_dict={}` chạy trên fallback.
  - `load_market_context()` không kiểm tra ngày hiện tại khi caller không truyền `current_date`, nạp nhầm báo cáo chuyên gia cũ vào system prompt.
- **Quyết định lựa chọn:**
  1. **Đấu nối toàn diện `fin_dict`:**
     - Gọi `get_financial_ratios()` trước khi tính định giá; truyền đầy đủ `fin_dict` và `sector` vào `calculate_fair_value_and_mos()` trên toàn bộ các luồng: `scan_market_opportunities()`, `evaluate_portfolio()`, `evaluate_watchlist()`, `_calculate_item_mos()`, `_validate_quant_gate()`, và `_prepare_smart_committee_context()`.
     - Truyền đủ `symbol`, `fin_dict`, `sector`, `tech_data` vào `evaluate_decision_hard_gates()` trong quy trình 2-Pass và Screener.
  2. **Chuẩn hóa ánh xạ cột tiếng Việt cho P&L danh mục:**
     - Cập nhật `evaluate_holding_position()` trong `portfolio_guard.py` và `_build_portfolio_quant_summary()` trong `ai_analyst.py` để tự động nhận diện cả tên cột tiếng Việt (`"Giá TB (k)"`, `"Giá vốn (k)"`, `"Giá hiện tại (k)"`, `"Thị giá (k)"`, `"Giá cao (k)"`, `"Mã CP"`, `"Khối lượng"`).
     - Đảm bảo `entry_price > 0`, `pl_pct` phản ánh đúng thực tế, vị thế có lãi kích hoạt chính xác mốc `trailing_stop`.
  3. **Khóa cứng cờ `mos_is_informative` cho CYCLICAL & REAL_ESTATE:**
     - Nếu `fin_dict` thiếu số liệu BCTC cốt lõi (`eps_history`/`pe` cho CYCLICAL; `bvps`/`pb` cho REAL_ESTATE), gắn cờ `mos_is_informative = False`, khóa cứng khuyến nghị MUA tại Decision Hard Gates.
  4. **Kiểm tra độ tươi ngày tháng trong `load_market_context()`:**
     - Mặc định so khớp `report_date` với `date.today()` khi caller không truyền `current_date` và `allow_stale=False`; nếu lệch ngày trả về `is_valid = False`.
  5. **Bổ sung mã ngân hàng vào `SECTOR_MAP`:**
     - Thêm `BID`, `VCB`, `CTG`, `STB` vào `SECTOR_MAP` để định tuyến chính xác archetype Ngân hàng.
- **Hệ quả:**
  - Xóa bỏ triệt để tình trạng MoS hằng số; toàn bộ pipeline định giá chạy trên số liệu tài chính thực chất.
  - Phục hồi hoàn hảo cơ chế Trailing Stop bảo vệ lợi nhuận cho danh mục đầu tư.
  - 100% test suites (102/102 unit/integration tests) đạt kết quả Green.
  - `ruff check . --output-format=github` đạt exit code 0. Hoàn tất Phase 14 (v7.4).

---

### [ADR-028] Xây Dựng Cổng Kiểm Soát Vào Lệnh Thống Nhất 7 Tầng (Unified Entry Gate Engine), Đồng Bộ Cooldown & Trọng Tài Định Lượng (Phase 15 - v7.5)
- **Ngày quyết định:** 2026-10-02
- **Người tham gia:** Client, PO, Finance Lead, Senior Dev, QA Lead, Independent Reviewer
- **Bối cảnh & Vấn đề:**
  - 4 luồng ra quyết định vào lệnh (`Watchlist Alert`, `scan_market_opportunities`, `2-Pass Web Report`, `Smart Investment Committee`) trước đó áp dụng các bộ quy tắc không đồng nhất, tạo ra các lỗ hổng rò rỉ rủi ro nghiêm trọng:
    1. Market Scanner hoàn toàn bỏ qua Macro Gate (khi VN-Index Downtrend vẫn phát khuyến nghị BUY).
    2. Ghi nhận `record_signal_cooldown` trước khi gửi Discord hoặc chạy độc lập, khiến mã bị khóa cooldown dù Discord alert thất bại (network timeout, rate limit).
    3. 2-Pass Web report tự động fallback về `GROWTH` nếu không rõ sector.
    4. Smart Committee cho phép LLM quyết định `STRONG_OPPORTUNITY` (BUY) ngay cả khi MoS âm hoặc vi phạm Data Gate, để ảo giác LLM ghi đè quy tắc định lượng.
    5. Active Screener lọc trạng thái không khớp (`status != "HIGH_CONVICTION"` trong khi scanner trả về `"RECOMMEND_BUY"`).
- **Quyết định lựa chọn:**
  1. **Tạo module trung tâm `entry_gates.py`:**
     - Hiện thực hóa hàm `evaluate_entry_gates()` và dataclass `EntryGateResult` thực thi tuần tự 7 tầng cổng kiểm định:
       - Tầng 0 (Macro Regime): Chặn 100% lệnh MUA khi VN-Index Downtrend; kích hoạt Fail-safe (cảnh báo + giảm 50% size) khi mất kết nối dữ liệu vĩ mô.
       - Tầng 1 (Data Gate): Chặn khi `quality_score < 65` hoặc dữ liệu BCTC/giá bị stale/đóng băng.
       - Tầng 2 (Financial Health): Chặn khi F-Score $\le 3$ hoặc Z-Score $< 1.23$ (vùng kiệt quệ tài chính).
       - Tầng 3 (Valuation & MoS): Yêu cầu `mos_is_informative = True` và $MoS \ge threshold[archetype]$.
       - Tầng 4 (Technical Momentum): Yêu cầu tín hiệu kỹ thuật thuộc `BULLISH_SET`, cấm bắt dao rơi dưới MA20/MA50.
       - Tầng 5 (Quant Conviction): Yêu cầu điểm Conviction $\ge 60$.
       - Tầng 6 (PM Veto): Chặn nếu phát hiện cờ Veto rủi ro danh mục.
  2. **Bật Macro Gate cho Scanner & Smart Committee:**
     - Đấu nối `evaluate_entry_gates` vào `scan_market_opportunities()`, bảo đảm khi VN-Index Downtrend thì trả về 0 BUY alerts.
  3. **Đồng bộ hóa thời điểm kích hoạt Cooldown:**
     - Xóa bỏ việc ghi cooldown sớm bên trong `scan_market_opportunities()`.
     - Trong `trading_bot.py`, `record_signal_cooldown` chỉ được gọi sau khi `send_trade_signal_alert()` trả về `True` (xác nhận Discord dispatch thành công).
  4. **Chuẩn hóa 2-Pass Archetype Wiring:**
     - Tra cứu sector thực từ `SECTOR_MAP`; nếu archetype là `UNKNOWN` và không xác định được ngành nghề $\rightarrow$ tự động Block BUY, tuyệt đối không default `GROWTH`.
  5. **Smart Committee Quant Hard Gate Arbitrator:**
     - Đấu nối `evaluate_entry_gates()` sau khi LLM Committee phản hồi. Nếu vi phạm cổng định lượng, tự động ghi đè khuyến nghị thành `THEO DÕI` (WATCHLIST) và ghi rõ lý do chặn trong `override_reason`.
  6. **Đồng bộ ánh xạ trạng thái Active Screener:**
     - Cập nhật bộ lọc Screener chấp nhận cả `HIGH_CONVICTION` và `RECOMMEND_BUY`.
- **Hệ quả:**
  - Thiết lập thành công cơ chế "Single Gatekeeper Architecture" chuẩn mực quỹ đầu tư, loại bỏ hoàn toàn tình trạng bypass cổng an toàn vốn.
  - Toàn bộ 118 unit & integration tests trong regression suite đạt 100% Green.
  - `ruff check . --output-format=github` đạt exit code 0. Hoàn tất Phase 15 (v7.5).

---

### [ADR-029] Chốt Chặn Toàn Vẹn Tín Hiệu Khuyến Nghị (Signal Integrity Filter), Ánh Xạ Vòng Đời Tín Hiệu & Bảo Vệ Danh Mục Thủ Công (Phase 16 - v7.6)
- **Ngày quyết định:** 2026-10-02
- **Người tham gia:** Client, PO, Finance Lead, Senior Dev, QA Lead, Independent Reviewer
- **Bối cảnh & Vấn đề:**
  1. `save_quant_signal()` ghi nhận tất cả hành động kể cả `THEO DÕI`, `GIẢM TỶ TRỌNG`, `TỪ CHỐI` vào bảng `signals`. Bảng này dùng để theo dõi hiệu suất danh mục khuyến nghị MUA, dẫn đến việc theo dõi hiệu suất bị rác và làm sai lệch thống kê PnL/Winrate.
  2. `check_symbol_recent_signal()` chỉ so khớp cứng chuỗi `action.ilike("%MUA%")`, bỏ sót các biến thể tiếng Anh hoặc hành động gom hàng như `🟢 TÍCH LŨY`, `🟢 ACCUMULATE`, `🟢 VALUE BUY`, `RECOMMEND_BUY`, dẫn đến nguy cơ bypass bộ lọc Cooldown 5 ngày.
  3. `save_signal_lifecycle()` adapter thiếu hỗ trợ ánh xạ khi caller truyền `initial_target_price` thay vì `target_price`, hoặc `initial_stop_price` thay vì `stop_loss_price`, làm thiếu hụt 5 trường hiệu chuẩn mô hình (`entry_price`, `target_price`, `initial_target_price`, `stop_loss_price`, `initial_stop_price`) cùng `f_score`, `mos_pct`.
  4. Lệch pha thời gian khớp lệnh (Time-Aware Audit Fill): Khi tín hiệu phát ra sau 11:30 sáng phiên T=0, audit tracking lấy giá High/Low của toàn bộ phiên (bao gồm cả biến động buổi sáng trước khi tín hiệu xuất hiện), gây sai lệch kết quả khớp lệnh ảo. Thời gian nắm giữ `days_elapsed` tính theo ngày lịch thay vì số phiên giao dịch (`count_trading_days()`).
  5. `target_buy` của cổ phiếu thêm tự động vào Watchlist bị gán nhầm bằng `target_price` (mục tiêu chốt lời trên đỉnh) thay vì vùng mua hỗ trợ / chiết khấu (entry zone), khiến cổ phiếu bị kích hoạt mua ngay lập tức thay vì chờ nhịp điều chỉnh.
  6. `prune_unsuitable_watchlist()` tự động xóa các cổ phiếu do người dùng tự tay thêm vào (`added_by == "user"` hoặc `is_manual_protected == True`) khi cổ phiếu vào vùng quá mua hoặc xuất hiện bẫy rủi ro, vi phạm quyền kiểm soát của nhà đầu tư trừ phi có `force_override=True`.
- **Quyết định lựa chọn:**
  1. **Lọc chặt chẽ hành động trong `save_quant_signal()`:**
     - Định nghĩa tập hợp hành động mua hợp lệ `BUY_ACTIONS = {"🟢 MUA", "🟢 TÍCH LŨY", "🟢 ACCUMULATE", "🟢 VALUE BUY", "RECOMMEND_BUY", "MUA", "BUY"}`.
     - Chỉ lưu vào cơ sở dữ liệu `signals` khi hành động thuộc `BUY_ACTIONS`; các hành động khác (`THEO DÕI`, `GIẢM TỶ TRỌNG`, `TỪ CHỐI`) bị từ chối lưu và trả về `None`.
     - Cung cấp hàm bảo trì `mark_non_buy_signals_invalid()` để dọn dẹp các bản ghi không phải mua cũ trong database.
  2. **Chuẩn hóa bộ lọc Cooldown đa từ khóa:**
     - Trong `check_symbol_recent_signal()`, truy vấn OR trên cơ sở dữ liệu và lọc in-memory với các từ khóa `%MUA%`, `%TÍCH LŨY%`, `%ACCUMULATE%`, `%BUY%`.
  3. **Hoàn thiện Adapter `save_signal_lifecycle()`:**
     - Tự động map fallback `target_price = kwargs.get("target_price") or kwargs.get("initial_target_price", 0.0)` và `stop_loss_price = kwargs.get("stop_loss_price") or kwargs.get("initial_stop_price", 0.0)`.
     - Bảo đảm đồng thời lưu cả 5 trường hiệu chuẩn mô hình và `f_score`, `mos_pct`.
  4. **Kiểm soát Khớp lệnh Theo Phiên & Tính Số Ngày Giao Dịch Thực:**
     - Xây dựng hàm `count_trading_days(start_date, end_date, holidays)` đếm chính xác số ngày làm việc (bỏ qua Thứ Bảy, Chủ Nhật và ngày lễ Việt Nam).
     - Trong `update_daily_tracking()` và `calculate_signal_performance_metrics()`: Đối với tín hiệu phát sau 11:30 ngày T=0, sử dụng giá đóng cửa `curr_p` thay cho `high_p` và `low_p` toàn phiên, loại trừ hoàn toàn fill ảo từ phiên sáng.
  5. **Định vị Vùng Mua Chiết Khấu (Entry Zone Target Buy):**
     - Trong `_build_auto_watchlist_candidate()`, gán `target_buy = support_level or current_price * 0.95`. Cổ phiếu cần điều chỉnh về vùng hỗ trợ mới kích hoạt khuyến nghị giải ngân.
  6. **Cơ chế Bảo vệ Danh mục Theo dõi Thủ công (Manual Watchlist Protection):**
     - Trong `_evaluate_watchlist_item_suitability()` và `prune_unsuitable_watchlist()`: Bổ sung cờ `is_manual_protected=True` (hoặc `added_by == "user"`).
     - Mặc định giữ lại cổ phiếu bảo vệ trong danh mục và chỉ bổ sung tiền tố cảnh báo `[⚠️ CẢNH BÁO: ...]`, không xóa khỏi danh sách trừ khi có chỉ định tường minh `force_override=True`.
- **Hệ quả:**
  - Bảng tín hiệu và audit hoàn toàn sạch sẽ, chỉ theo dõi các khuyến nghị MUA thực thụ.
  - Loại bỏ hoàn toàn lỗi khớp lệnh ảo buổi sáng trên các tín hiệu phát sinh phiên chiều.
  - Bảo toàn tuyệt đối danh mục theo dõi chủ động của người dùng.
  - 100% test suites (437/437 unit & integration tests) đạt kết quả Green.
  - `ruff check . --output-format=github` đạt exit code 0. Hoàn tất Phase 16 (v7.6).

---

### [ADR-030] Hoàn Thiện Tầng Quản Trị Rủi Ro & Sizing Số Thực, Canonical RegimeState và Chuẩn Hóa Cảnh Báo Discord (Phase 17 - v8.0)
- **Ngày quyết định:** 2026-10-02
- **Người tham gia:** Client, PO, Finance Lead, Senior Dev, QA Lead, Independent Reviewer
- **Bối cảnh & Vấn đề:**
  1. Tầng 7 Quản trị Rủi ro bị tách rời: Các hàm `check_adv20_liquidity_absorption()`, `check_sector_concentration()`, `calculate_drawdown_controlled_sizing()` đã viết nhưng không được gọi trong `evaluate_entry_gates()`. Trường `position_size_nav` trả về chuỗi hard-code `"15-20% NAV"`, không phản ánh thanh khoản và sụt giảm vốn thực tế.
  2. Phân mảnh định nghĩa Regime: Tồn tại 2 định nghĩa regime song song (ngắn hạn MA20/MA50 vs trung hạn MA200) và kiểm tra bằng chuỗi tự do, gây nguy cơ xung đột logic khi gọi `check_regime_conflict`.
  3. Ánh xạ nhãn cảnh báo Discord sai lệch: Trong `send_trade_signal_alert`, mọi non-MUA action đều bị map thành "BÁN / HẠ TỶ TRỌNG" màu đỏ `0xE74C3C`. Tín hiệu "THEO DÕI" hoặc "CẢNH BÁO" bị hiển thị như tín hiệu bán tháo/cắt lỗ gây hoang mang cho nhà đầu tư.
  4. Suy đoán ngày GDKHQ thiếu bằng chứng: `detect_gdkhq_event` chỉ nhìn bước nhảy giá đầu phiên $\le -4.5\%$ để kết luận chia cổ tức. Nếu cổ phiếu gap-down do tin xấu bất ngờ, hệ thống bỏ qua Stop-Loss vì ngộ nhận là chia cổ tức.
  5. Kill Switch chỉ nối chuỗi văn bản: Khi kích hoạt Kill Switch phòng thủ, hệ thống chỉ ghi chú vào text mà không thực sự cắt giảm `position_size_pct` dạng số học.
  6. Trigger Watchlist Value Buy bắt đáy dao rơi: Điều kiện kích hoạt cũ `RSI <= 32` là hành vi bắt đáy dao rơi rủi ro, mâu thuẫn với chiến lược Value Buy đầu tư giá trị trung dài hạn.
- **Quyết định lựa chọn:**
  1. **Canonical `RegimeState` Enum & Source of Truth:**
     - Thiết lập enum `RegimeState(str, Enum)`: `UPTREND`, `SIDEWAYS`, `DOWNTREND`, `UNKNOWN` trong `regime_classifier.py`.
     - Cung cấp hàm `get_canonical_regime()` làm nguồn chân lý duy nhất từ MA200 Hysteresis $\pm 1.5\%$.
     - `check_regime_conflict()` trong `context_engine.py` hỗ trợ trực tiếp cả `RegimeState` enum và chuỗi chuẩn hóa.
  2. **Đấu Nối Tầng 7 (Risk Governance & Position Sizing Float):**
     - Đấu nối `_calculate_position_size_layer()` vào cuối `evaluate_entry_gates()`.
     - Chặn tuyệt đối (`can_buy = False`, `blocked_by = "ADV20_LIQUIDITY"`, `position_size_pct = 0.0`) khi thanh khoản ADV20 < 2.0 tỷ VND.
     - Tính toán `position_size_pct` dạng số thực `float` dựa trên Half-Kelly, Drawdown Breaker và Liquidity Absorption.
  3. **Chuẩn Hóa Ánh Xạ Nhãn & Màu Sắc Discord Alert:**
     - Cập nhật `send_trade_signal_alert` phân định rõ 5 nhóm trạng thái:
       - `MUA` / `TÍCH LŨY` / `BUY` $\rightarrow$ `🟢 MUA / TÍCH LŨY` (Xanh lá `0x2ECC71`).
       - `THEO DÕI` / `WATCH` $\rightarrow$ `🟡 THEO DÕI` (Vàng `0xF1C40F`).
       - `GIẢM` / `THOÁT` $\rightarrow$ `🔴 GIẢM / THOÁT` (Đỏ `0xE74C3C`).
       - `CẢNH BÁO` $\rightarrow$ `⚠️ CẢNH BÁO — KHÔNG PHẢI BÁN` (Cam `0xE67E22`).
       - `GDKHQ` $\rightarrow$ `📅 SỰ KIỆN GDKHQ` (Xanh dương `0x3498DB`).
  4. **Đối Soát Lịch Sự Kiện Doanh Nghiệp Thật (Corporate Actions Shield):**
     - `detect_gdkhq_event()` đối soát ngày GDKHQ thực tế thông qua `fetch_corporate_dividends()`.
     - Nếu có sự kiện GDKHQ hôm nay $\rightarrow$ xác nhận `"GDKHQ_CONFIRMED"`, tạm dừng cắt lỗ.
     - Nếu không có sự kiện GDKHQ $\rightarrow$ gắn cờ `"GAP_DOWN_NEWS"`, `is_gdkhq = False` và kích hoạt ngay kiểm tra Stop-Loss.
  5. **Kill Switch Cắt Giảm Vị Thế Bằng Số Thực:**
     - Khi Kill Switch hoặc Hysteresis Defense hoạt động, nhân giảm $50\%$ giá trị `position_size_pct` thật (`actual_size = base_size * 0.5`).
  6. **Chuẩn Hóa Vùng Kích Hoạt Watchlist Value Buy:**
     - Trong `_evaluate_watchlist_buy_trigger()`: Giá trị Value Buy kích hoạt khi $RSI \in [30, 50]$, loại bỏ hoàn toàn bẫy bắt đáy dao rơi $RSI < 30$.
- **Hệ quả:**
  - Quy mô giải ngân vốn hoàn toàn định lượng, số thực hóa, phản ánh thanh khoản và rủi ro danh mục thực tế.
  - Xóa bỏ triệt để hiện tượng cảnh báo Discord sai màu gây hoang mang cho nhà đầu tư.
  - Hệ thống khiên chắn cổ tức đối soát bằng dữ liệu VSDC thực chất, bảo toàn kỷ luật cắt lỗ.
  - 100% test suites (449/449 unit & integration tests) đạt kết quả Green.
  - `ruff check . --output-format=github` đạt exit code 0. Hoàn tất Phase 17 (v8.0).
### [ADR-031] Contrarian Module (Panic Buy Engine) v10.0 & Cấu trúc 4-State Machine (Phase 20)
- **Ngày quyết định:** 2026-10-02
- **Người tham gia:** Client, PO, Finance Lead, Senior Dev, QA Lead, Independent Reviewer
- **Bối cảnh & Vấn đề:** Hệ thống Trend Following thông thường sẽ khóa 100% cơ hội khi thị trường hoảng loạn. Contrarian Module cũ (v8.1 - v9.0) giải quyết bài toán này bằng cách chỉ kích hoạt khi $RSI \le 30$. Tuy nhiên, việc đặt chốt chặn Kỹ thuật (RSI) TRƯỚC chốt chặn Cơ bản (Quality/MoS) đã dẫn đến "Single Point of Failure": Hệ thống đánh đồng cổ phiếu siêu tốt đang giảm về sát ngưỡng hoảng loạn (ví dụ FPT) với cổ phiếu rớt giá do kiểm toán/vỡ cơ bản (Value Trap như DGC, NVL). 
- **Quyết định lựa chọn (Hợp nhất từ ADR-0008, 0009):**
  1. Đảo ngược trình tự đánh giá: Hệ thống bắt buộc phải qua 3 cửa ải khắt khe (Governance Event Risk $\rightarrow$ Survival Quality $\rightarrow$ Deep MoS) TRƯỚC KHI đánh giá tín hiệu Kỹ thuật.
  2. Bất cứ mã nào vi phạm rủi ro sự kiện (kiểm toán, pháp lý) hoặc tài chính suy kiệt (LNST lao dốc, F-Score thấp) đều bị BLOCK vĩnh viễn với cờ VALUE TRAP.
  3. Cơ chế 4-State Machine (Máy 4 trạng thái): Các mã TỐT & RẺ sẽ được phân loại thành `NORMAL`, `NEAR_PANIC_WATCH` ($30 < RSI \le 35$), `EXTREME_FEAR_WATCH` ($RSI \le 30$ nhưng chưa có xác nhận) và `PANIC_BUY` ($RSI \le 30$ kèm nến đảo chiều).
  4. Continuous Panic Score: Đánh giá cường độ rơi từ 0-100 thay vì chỉ trả về nhị phân.
  5. Quản trị vị thế thận trọng: Vị thế trần tối đa $5.0\%$ NAV, phạt chia đôi $\text{Half-Kelly} / 2$, Hard Stop-loss cố định $-8.0\%$.
- **Hệ quả & Đánh đổi:**
  - Bắt đáy an toàn, triệt tiêu hoàn toàn "bẫy giá rẻ" bằng cách loại ngay rác từ vòng gửi xe. Không bỏ sót cổ phiếu chất lượng nhờ cơ chế radar "Near Panic Watch".
  - Giữ nguyên sự trong sáng của hệ thống Trend Following cốt lõi.
  - Hồi quy toàn bộ hệ thống test đạt 100% green. Hoàn tất Phase 20 (v10.0). Tham chiếu chi tiết tại `ADR-031-Contrarian-Module.md`.

---

### [ADR-032] L0-L7 Contrarian 5-Layer Framework & 4-State Machine (Phase 20 / v10.0)
- **Ng�y quy?t d?nh:** 2026-10-03
- **Tr?ng th�i:** APPROVED / IMPLEMENTED
- **Ngu?i tham gia:** Client, PO, Senior Dev
- **B?i c?nh & V?n d? (The Panic Trap):** H? th?ng Contrarian v8.1 b?t d�y d?a tr�n m?t di?m ch?m nh? ph�n qu� th� (RSI <= 30). H?u qu? l� c�c c? phi?u r�c d�nh b?y (Value Trap) do r?i ro n?i t?i l?i du?c duy?t mua ch? v� gi� gi?m m?nh, trong khi c�c c? phi?u c� n?n t?ng xu?t s?c (v� d? FPT) v?a roi v? v�ng gi� tr? h?p d?n (RSI 31-35) th� l?i b? th?ng tay lo?i b? v� kh�ng d�p ?ng Hard Gate c?ng ng?c.
- **Quy?t d?nh l?a ch?n:**
  1. Thay th? Hard Gate b?ng 4 tr?ng th�i: NORMAL, NEAR_PANIC_WATCH, EXTREME_FEAR_WATCH, PANIC_BUY.
  2. B? sung L1 Governance & Event Veto: Ch?n c�c r?i ro tin t?c ti�u c?c (h?y ni�m y?t, b?t b?).
  3. B? sung L2 Survival Archetype: N?i l?ng D/E <= 1.0 th� r�p, thay b?ng N? x?u Bank < 3%, D/E B�S < 1.5, ��n b?y CK < 3.
  4. B? sung L4 Stress-MoS: Ph?t Fair Value 20% m� ph?ng EPS s?p, y�u c?u bi�n an to�n th?c ch?t.
  5. B? sung L5 Structural Confirmation: Ch? x�c nh?n mua khi c� volume c?n ki?t, c?u tr�c d�y sau cao hon v� sau 14:15.
- **H? qu?:** Ho�n to�n lo?i b? r?i ro Value Trap, gi? l?i c�c m� t?t ? tr?ng th�i WATCH thay v� REJECT, ch?ng l?i h?i ch?ng Falling Knife.


---

### [ADR-033] Phase 22 - Contrarian Engine v11.1 (MoS Semantics, Valuation Watch, Dynamic Size/Haircut)
- **Ngày quyết định:** 2026-10-03
- **Người tham gia:** Client, PO, Senior Dev
- **Bối cảnh & Vấn đề:**
  1. Sai lệch hệ quy chiếu MoS: Thuật ngữ Margin of Safety bị tính nhầm thành Upside = `(FV - Price) / Price` trong tầng contrarian.
  2. Bẫy giờ server: Lỗi lệch múi giờ trên production (`now.hour >= 14 and now.minute >= 15`) do máy chủ chạy UTC dẫn đến bot đánh giá sai giờ ATC.
  3. Tư duy "Trắng - Đen" trong kiến trúc: Cổ phiếu rơi khỏi Panic Gate (RSI > 35) bị trả về `STATE_NORMAL` cào bằng, lãng phí cơ hội quan sát định giá rẻ.
  4. Trừng phạt cứng nhắc Value Trap: Cổ phiếu chu kỳ (Cyclical) ở đáy lợi nhuận bị block cứng.
- **Quyết định lựa chọn:**
  1. **Chuẩn hóa công thức MoS:** Sử dụng `mos_pct = (FV - Price) / FV`, song song tính `upside_pct`.
  2. **ZoneInfo & Timezone Check:** Force `Asia/Ho_Chi_Minh` và sửa logic giờ.
  3. **Kiến trúc phân lớp trạng thái:** Sinh ra trạng thái `VALUATION_WATCH` cho các mã RSI ổn định nhưng định giá siêu hấp dẫn.
  4. **Cyclical Exemption:** Không block cứng Value Trap nếu `archetype == "CYCLICAL"`.
  5. **Dynamic Haircut & Sizing:** Tùy biến stress haircut (15% - 60%) dựa trên sector và rủi ro. Giảm max position size bắt đáy về 3.0%.
  6. **Định lượng đa biến (Multi-factor):** Panic Score 100 điểm với 5 tham số. Price Confirmation Score 100 điểm (pass >= 60).
- **Hệ quả:**
  - Hoàn thiện module bắt đáy với sự thận trọng tuyệt đối. Codebase pass 100% test suites.

---

---

### [ADR-034] Phase 23.1 - Advanced F-Score 3-Tier Architecture & Macro Overlays
- **Ngày quyết định:** 2026-10-03
- **Người tham gia:** Client, PO, Senior Dev
- **Bối cảnh & Vấn đề:**
  1. Hệ thống cũ sử dụng ngưỡng F-Score tĩnh (Hard Gate < 7 là chặn). Điều này dẫn đến việc bỏ lỡ các cổ phiếu tốt đang ở vùng đáy lợi nhuận (Cyclical) hoặc có dấu hiệu phục hồi nhưng F-Score chỉ đạt 4-6.
  2. Phụ thuộc quá nhiều vào F-Score mà thiếu các màng lọc (Risk Overlays) rủi ro vĩ mô như thanh khoản (ADV20) hay khả năng phá sản (Z-Score) và nợ vay (D/E).
  3. Đánh đồng các mã thiếu dữ liệu F-Score với các mã có sức khỏe tài chính yếu kém thực sự.
- **Quyết định lựa chọn:**
  1. **Kiến trúc F-Score 3-Tier:** Chuyển đổi sang hệ thống 3 tầng: Tier 1 (F < 4: Hard Block), Tier 2 (F từ 4-6: Cần qua Risk Overlays), Tier 3 (F >= 7: Bỏ qua Risk Overlays).
  2. **Risk Overlays độc lập:** Bổ sung các chốt chặn Z-Score, Debt/Equity theo từng Archetype (Bất động sản, Ngân hàng, v.v.).
  3. **Phân biệt Value Trap và Cyclical:** Các mã chu kỳ (Cyclical) có F-Score thấp không bị chặn tức thời mà bị áp dụng Haircut (giảm giá trị thực) mạnh ở bước Valuation MoS, ngăn rủi ro Value Trap một cách hợp lý.
- **Hệ quả:**
  - Hệ thống Contrarian đã phản ứng linh hoạt hơn với nhóm cổ phiếu có F-Score 4-6, kết hợp chặt chẽ với các chỉ số rủi ro (Z-Score, D/E).
  - Vượt qua toàn bộ 19/19 test cases, đảm bảo hệ thống chặn chính xác Value Trap mà không bị chặn lầm mã tốt.

---

### [ADR-035] Phase 23.2 - Fundamental Quality Conditional Gate (CFO Validation)
- **Ngày quyết định:** 2026-10-03
- **Người tham gia:** Client, PO, Senior Dev
- **Bối cảnh & Vấn đề:** Đối với các cổ phiếu chu kỳ (Cyclical), lợi nhuận và biên gộp có thể chạm đáy (Earnings Revision Down), nhưng nếu dòng tiền hoạt động kinh doanh (CFO) vẫn dương, đó là tổn thất mang tính chu kỳ (temporary). Ngược lại, nếu CFO âm, rủi ro vỡ nợ hiện hữu và đó là một Value Trap thực sự.
- **Quyết định lựa chọn:** Thêm điều kiện kiểm tra CFO (`cfo` hoặc `p_cf`) vào Gate Survival. Nếu doanh nghiệp thuộc nhóm Cyclical và có xu hướng giảm lợi nhuận, bắt buộc CFO phải > 0 để được tiếp tục pass (với án phạt Haircut L4). Nếu CFO <= 0, chặn ngay lập tức với lý do: "Cổ phiếu chu kỳ nhưng CFO âm (Dòng tiền cạn kiệt). VALUE TRAP!".
- **Hệ quả:** Hoàn thiện Conditional Gate cho nhóm cổ phiếu F-Score 4-6, đảm bảo bộ lọc bắt đáy phân biệt được sự hoảng loạn ngắn hạn và sự suy thoái dòng tiền cấu trúc, bảo vệ an toàn vốn tuyệt đối.
