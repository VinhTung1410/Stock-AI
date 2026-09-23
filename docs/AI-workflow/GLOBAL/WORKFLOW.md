# 🔄 GLOBAL: MULTI-AGENT WORKFLOW (QUY TRÌNH PHỐI HỢP)

Quy trình phát triển phần mềm và tối ưu hóa hệ thống định lượng Stock-AI vận hành theo chu trình khép kín gồm 7 bước (Phase), đảm bảo mọi yêu cầu từ **Client** được phân tích, thẩm định tài chính, hiện thực hóa kỹ thuật, và kiểm toán chất lượng trước khi triển khai.

---

## 1. Sơ đồ Chu trình Làm việc Chuẩn (Happy Path Workflow)

```text
[Phase 1: Client]
    │   Viết yêu cầu vào Client.md (Pain points, Must-haves, Constraints, Budget)
    ▼
[Phase 2: Product Owner]
    │   Phân tích yêu cầu, làm rõ nghiệp vụ, tạo TASK-xxxx.md (User Stories + AC)
    ▼
[Phase 3: Finance Lead]
    │   Thẩm định tính khả thi tài chính, định giá, rủi ro danh mục, chi phí token & hạ tầng
    ▼
[Phase 4: Senior Dev]
    │   Thiết kế giải pháp, lập trình tối giản (Lazy Dev), tuân thủ SonarCloud
    ▼
[Phase 5: QA Lead]
    │   Viết unit tests, kiểm thử biên (Edge Cases), đảm bảo độ phủ Coverage >= 80%
    ▼
[Phase 6: Independent Reviewer]
    │   Audit mã nguồn, kiểm tra linting (Ruff), quét lỗ hổng bảo mật & duplication <= 3%
    ▼
[Phase 7: Client Review & Release]
        Bàn giao báo cáo nghiệm thu (Walkthrough) -> Client bấm duyệt -> Commit & Push
```

---

## 2. Cơ chế Phản hồi & Vòng lặp Xử lý Từ chối (Rejection & Feedback Loops)

Nếu ở bất kỳ giai đoạn nào tiêu chuẩn không đạt, task sẽ kích hoạt cơ chế phản hồi ngược (Feedback Loop) để khắc phục triệt để trước khi được đi tiếp:

```text
       ┌─────────── [Phase 3: Finance Lead] ──────────┐
       │ (Từ chối định giá/rủi ro)                    │ (Đạt chuẩn tài chính)
       ▼                                              ▼
[Phase 2: PO làm rõ/điều chỉnh AC]           [Phase 4: Senior Dev]
                                                      ▲
                                                      │ (Sửa lỗi code/test)
                                                      ├────────────────────────┐
                                                      │                        │
                                             [Phase 5: QA Lead]       [Phase 6: Reviewer]
                                            (Failed test / Cov < 80%) (Lint / Sonar / Duplication)
```

1. **Finance Lead REJECT (Không đạt chuẩn an toàn tài chính):**
   - **Lý do:** Mô hình định giá sai Archetype, dữ liệu stale không có chốt chặn, rủi ro danh mục vượt trần, hoặc chi phí token vượt ngân sách.
   - **Xử lý:** Task chuyển về `PO_REVIEW`. PO cùng Client điều chỉnh lại phạm vi (Scope) hoặc bổ sung ràng buộc dữ liệu.
2. **QA Lead REJECT (Kiểm thử thất bại hoặc thiếu Coverage):**
   - **Lý do:** Có test case bị fail, phát sinh lỗi hồi quy (regression), hoặc Coverage mã mới $< 80\%$.
   - **Xử lý:** Task chuyển về `DEV_IN_PROGRESS`. Senior Dev phải bổ sung xử lý ngoại lệ hoặc sửa lỗi thuật toán.
3. **Reviewer REJECT (Vi phạm SonarCloud / Code Quality):**
   - **Lý do:** `ruff check` có warning/error, Cognitive Complexity $\ge 15$, `logging.error` trong `except`, hoặc code duplication mới $> 3.0\%$.
   - **Xử lý:** Task chuyển về `DEV_IN_PROGRESS` để Senior Dev refactor vi phẫu.
4. **Client REJECT (Chưa đạt kỳ vọng nghiệp vụ):**
   - **Lý do:** Giao diện chưa trực quan, ngôn ngữ chưa chuẩn Unicode/CFA, hoặc thiếu tính năng Must-have.
   - **Xử lý:** Task chuyển về `PO_REVIEW` để tái lập trình kế hoạch cải tiến.

---

## 3. Chi tiết Từng Giai đoạn & Tiêu chí Chuyển tiếp (Hand-off Criteria)

### Giai đoạn 1: Khởi tạo Yêu cầu (Client Brief)
- **Actor:** Client (Người dùng).
- **Đầu vào:** Biểu mẫu `docs/AI-workflow/Client.md`.
- **Hành động:** Điền đầy đủ: Vấn đề gặp phải (Pain points), tính năng mong muốn, ràng buộc kỹ thuật và ngân sách/thời hạn.
- **Cổng chuyển tiếp:** File `Client.md` được lưu với trạng thái sẵn sàng để PO tiếp nhận.

### Giai đoạn 2: Phân tích & Phân rã Task (PO Analysis)
- **Actor:** Product Owner (PO).
- **Hành động:** 
  1. Đọc kỹ `Client.md`. Đặt câu hỏi phản biện nếu thông tin bị thiếu hoặc mập mờ.
  2. Tạo file `docs/AI-workflow/TASK/TASK-xxxx.md`.
  3. Định nghĩa cụ thể: User Stories, Điều kiện Chấp thuận (Acceptance Criteria - AC) theo cấu trúc *Given - When - Then*, Tiêu chuẩn Hoàn thành (Definition of Done - DoD).
- **Cổng chuyển tiếp:** File task chuyển trạng thái `FINANCE_AUDIT`.

### Giai đoạn 3: Thẩm định Tài chính & Rủi ro (Finance Audit)
- **Actor:** Finance Lead (Kiểm soát Tài chính & Quản trị Rủi ro).
- **Hành động:**
  1. Thẩm định mô hình định giá theo đúng Archetype ngành (Ngân hàng, Bất động sản, Sản xuất chu kỳ, Tăng trưởng).
  2. Đảm bảo có chốt chặn chống dữ liệu đóng băng (Freshness check $\le 2$ quý) và Triangle cross-check.
  3. Kiểm tra các ràng buộc định lượng: Half-Kelly, ADV20, Sector concentration $\le 25\%$, F-Score, Z-Score.
  4. Đánh giá chi phí hạ tầng (Chi phí token Gemini LLM, tài nguyên Supabase/Render).
- **Cổng chuyển tiếp:** Ký xác nhận "Financial Sanity Approved" trong `TASK-xxxx.md`, chuyển trạng thái `DEV_IN_PROGRESS`.

### Giai đoạn 4: Kiến trúc & Hiện thực hóa (Senior Dev Implementation)
- **Actor:** Senior Developer.
- **Hành động:**
  1. Lên phương án kỹ thuật theo triết lý "Lazy Senior Developer" (tái sử dụng code có sẵn, không over-engineering).
  2. Viết mã nguồn tập trung, chỉnh sửa vi phẫu, tuân thủ `GLOBAL/AGENT_RULES.md`.
  3. Đảm bảo Cognitive Complexity $< 15$, không trùng lặp code giữa luồng Async và Sync.
  4. Đảm bảo 100% tiếng Việt chuẩn Unicode, không dùng chữ Hán/tiếng Trung.
- **Cổng chuyển tiếp:** Code chạy thông suốt, tự smoke test nhanh, chuyển trạng thái `QA_TESTING`.

### Giai đoạn 5: Kiểm thử Chất lượng Toàn diện (QA Verification)
- **Actor:** QA Lead.
- **Hành động:**
  1. Viết bộ unit tests tự động trong `tests/` bám sát Acceptance Criteria.
  2. Đo lường độ phủ Code Coverage đạt **$\ge 80\%$** (mục tiêu $85 - 95\%+$ trên module quant/rủi ro).
  3. Chạy test các kịch bản bất thường (dữ liệu stale, mất mạng, chia 0, cổ phiếu mất thanh khoản).
  4. Tuân thủ nguyên tắc "No Excuses": Luôn hoàn thành file test dù môi trường local có trở ngại.
- **Cổng chuyển tiếp:** 100% tests pass, chuyển trạng thái `CODE_REVIEW`.

### Giai đoạn 6: Kiểm duyệt Độc lập (Independent Review)
- **Actor:** Reviewer.
- **Hành động:**
  1. Chạy `ruff check . --output-format=github` bắt buộc đạt **exit code 0**.
  2. Quét các quy tắc SonarCloud (S8572 `logging.exception`, S3776 complexity $< 15$, S1192 string duplication, F401).
  3. Đo lường mật độ trùng lặp mã mới (Duplicated Lines Density $\le 3.0\%$).
  4. Quét rà soát an ninh (Security & Secrets Audit): Tuyệt đối không rò rỉ API key, token hay mật khẩu.
- **Cổng chuyển tiếp:** Reviewer đóng dấu `[ LGTM - Looks Good To Me ]` vào `TASK-xxxx.md`, chuyển trạng thái `CLIENT_ACCEPTANCE`.

### Giai đoạn 7: Nghiệm thu & Triển khai (Client Acceptance & Deploy)
- **Actor:** Client + Hệ thống.
- **Hành động:**
  1. Trình diễn báo cáo nghiệm thu tóm tắt (Walkthrough) cho Client.
  2. Client bấm xác nhận nghiệm thu.
  3. Ghi lại các quyết định kỹ thuật/nghiệp vụ quan trọng vào `docs/AI-workflow/GLOBAL/DECISION_LOG.md`.
  4. Thực hiện `git commit` và `git push` lên GitHub an toàn.
- **Cổng chuyển tiếp:** Chuyển trạng thái task sang `DONE`.

---

## 4. Quy tắc Giải quyết Bất đồng (Conflict Resolution)

1. **Nếu Kỹ thuật mâu thuẫn với Nghiệp vụ Tài chính:** Ý kiến của Finance Lead và Data Gate có quyền ưu tiên cao hơn để bảo toàn an toàn vốn cho nhà đầu tư.
2. **Nếu Tiến độ mâu thuẫn với Chất lượng Code:** Không bao giờ hạ thấp Quality Gate (SonarCloud & Coverage $\ge 80\%$). Nếu cần gấp, PO phải cắt giảm Scope (chức năng Must-have trước, Nice-to-have sau) thay vì cắt giảm kiểm thử.
