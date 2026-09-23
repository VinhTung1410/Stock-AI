# 📌 TASK TEMPLATE: TASK-[MÃ_SỐ] - [TÊN TÍNH NĂNG]

**Mã Task:** `TASK-[MÃ_SỐ]` (Ví dụ: `TASK-0001`)  
**Ngày tạo:** [YYYY-MM-DD]  
**Người khởi xướng:** Client (Yêu cầu từ `Client.md`)  
**Product Owner:** [Tên PO]  
**Trạng thái:** `[ DRAFT | PO_REVIEW | FINANCE_AUDIT | DEV_IN_PROGRESS | QA_TESTING | CODE_REVIEW | CLIENT_ACCEPTANCE | REJECTED_BY_FINANCE | REJECTED_BY_QA | REJECTED_BY_REVIEWER | DONE ]`  
**Mức độ ưu tiên:** `[ P0 - Blocker | P1 - Critical | P2 - Normal | P3 - Low ]`

---

## 1. Bối cảnh & Mục tiêu Nghiệp vụ (Business Context)
- **Vấn đề cần giải quyết (Từ Client.md):** [Mô tả ngắn gọn vấn đề/pain point mà người dùng đang gặp phải]
- **Mục tiêu đạt được:** [Kết quả cụ thể sau khi hoàn thành tính năng]

---

## 2. Câu chuyện Người dùng (User Stories)
- **US-1:** Là một [Nhà đầu tư cá nhân], tôi muốn [Xem cảnh báo khi cổ phiếu bị đóng băng dữ liệu tài chính], để [Không bị lừa bởi mức định giá P/B ảo].
- **US-2:** Là một [Nhà quản lý danh mục], tôi muốn [Hệ thống tự động áp dụng Half-Kelly và giới hạn ngành 25%], để [Bảo vệ tổng tài sản không bị sụt giảm quá mức khi thị trường biến động].

---

## 3. Tiêu chí Chấp thuận (Acceptance Criteria - AC)
- **AC-1:** *Given* dữ liệu tài chính của cổ phiếu có báo cáo tài chính mới nhất cũ hơn 2 quý, *When* hệ thống thực hiện phân tích, *Then* cờ `recommendation_allowed` phải bằng `False` và xuất thông báo lỗi rõ ràng.
- **AC-2:** *Given* tỷ lệ thắng và tỷ lệ lời/lỗ ước lượng của một mã, *When* tính toán tỷ trọng phân bổ, *Then* hàm `calculate_half_kelly_allocation()` phải trả về giá trị không vượt quá 20% và tuân thủ trần thanh khoản ADV20.
- **AC-3:** *Given* hội đồng AI đưa ra khuyến nghị BUY nhưng RSI(14) > 75 (FOMO), *When* đi qua `arbitrate_pm_decision()`, *Then* khuyến nghị phải bị hạ xuống HOLD hoặc NEUTRAL.

---

## 4. Thẩm định & Ký duyệt Tài chính (Finance Lead Sign-off)

*Chuyên viên Tài chính & Quản trị Rủi ro (Finance Lead) kiểm định theo `ROLES/finance.md`:*

- [ ] **Mô hình định giá:** Đã khớp với Archetype ngành (Ngân hàng: P/B, BĐS: RNAV/Tồn kho, Chu kỳ: P/E chu kỳ/Gross Margin).
- [ ] **Độ tươi & Tính toàn vẹn (Freshness & Integrity):** Có SLA kiểm tra BCTC $\le 2$ quý và kiểm tra chéo tam giác (Triangle cross-check).
- [ ] **Bộ lọc Rủi ro Định lượng:** Tích hợp F-Score $\ge 5$, Z-Score $> 1.81$, Cash Flow $\text{CFO} / \text{NI} \ge 0.8$.
- [ ] **Phân bổ vốn & Thanh khoản:** Half-Kelly $\le 20\%$, Ngành $\le 25\%$, ADV20 Liquidity Tiering.
- [ ] **Trọng tài PM (Arbitration):** Kích hoạt Thesis Breaker, Falling Knife và FOMO Protection.
- [ ] **Kiểm soát Ngân sách Token:** Đã có tầng lọc bằng code Python trước khi gọi LLM (giảm $75\%$ token).

**Kết luận Thẩm định:** `[ APPROVED | REJECTED ]`  
*Ghi chú của Finance Lead:* [Nhập nhận xét / yêu cầu điều chỉnh nếu có]  
*Ký tên:* [Tên Finance Lead] — Ngày: [YYYY-MM-DD]

---

## 5. Phương án Kỹ thuật & Phạm vi Files (Senior Dev Design)
- **Giải pháp thực hiện:** [Mô tả vắn tắt cách tiếp cận kỹ thuật theo triết lý Lazy Senior Dev]
- **Danh sách Files tác động:**
  - `[MODIFY]` [file_1.py](file:///path/to/file_1.py): [Mô tả nội dung sửa]
  - `[NEW]` [file_2.py](file:///path/to/file_2.py): [Mô tả nội dung tạo mới]
- **Tự kiểm tra SonarCloud:** Cognitive Complexity < 15, S8572 `logging.exception`, Ruff I001 format, New Duplicated Lines <= 3.0%.

---

## 6. Kế hoạch Kiểm thử & Độ phủ (QA Lead Verification)
- **File Test:** `tests/test_xxxx.py`
- **Kịch bản Happy Path:** [Mô tả luồng chuẩn]
- **Kịch bản Edge Cases:** [Dữ liệu rỗng, chia cho 0, mất mạng, BCTC cũ > 2 quý, thanh khoản sụt giảm]
- **Kết quả Coverage:** [Ví dụ: 92.5% (>= 80% đạt yêu cầu)]
- **Ký duyệt:** `[ PASSED | REJECTED ]` — Trưởng nhóm QA: [Tên QA Lead] — Ngày: [YYYY-MM-DD]

---

## 7. Kiểm duyệt Mã nguồn (Reviewer Audit)
- **Linter Output:** `ruff check .` -> Exit code 0 `[ PASS / FAIL ]`
- **SonarCloud Audit:** S8572 [OK], S3776 [OK], S1192 [OK], F401 [OK] `[ PASS / FAIL ]`
- **Mật độ Trùng lặp:** New Duplicated Lines <= 3.0% `[ PASS / FAIL ]`
- **Bảo mật & Bí mật:** Không rò rỉ secret key vào git `[ CONFIRMED ]`
- **Đóng dấu duyệt:** `[ LGTM - Looks Good To Me | REJECTED ]` — Reviewer: [Tên Reviewer] — Ngày: [YYYY-MM-DD]

---

## 8. Bàn giao & Nghiệm thu từ Client (Client Acceptance)
- **Walkthrough Artifact:** [Link tới artifact walkthrough.md]
- **Đánh giá từ Client:** `[ ACCEPTED | NEED_REVISION ]`
- **Git Commit Hash:** `[hash_commit]`
- **Trạng thái cuối cùng:** `[ DONE ]`
