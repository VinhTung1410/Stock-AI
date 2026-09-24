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


