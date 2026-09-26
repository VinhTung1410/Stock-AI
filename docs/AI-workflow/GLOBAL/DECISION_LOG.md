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



