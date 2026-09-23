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
