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
