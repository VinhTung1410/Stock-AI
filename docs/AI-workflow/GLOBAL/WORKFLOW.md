# 🔄 GLOBAL: MULTI-AGENT WORKFLOW (QUY TRÌNH PHỐI HỢP ĐA VAI TRÒ)

> **Phiên bản chuẩn hóa:** v5.1 — Đồng bộ cùng Paradigm Shift: *Investment Research Platform*  
> **Cơ chế cốt lõi:** Chu trình 7 bước (Phase 1–7) khép kín với Tường lửa Bảo mật & Pháp lý (Phase 0) và Hạ tầng Bằng chứng Kiểm định (Phase 1 Signal Lifecycle).

Quy trình phát triển phần mềm và tối ưu hóa hệ thống định lượng Stock-AI vận hành theo chu trình khép kín gồm 7 bước (Phase), đảm bảo mọi yêu cầu từ **Client** được phân tích, thẩm định tài chính, hiện thực hóa kỹ thuật, kiểm toán chất lượng và cô lập tài nguyên bảo mật trước khi bàn giao.

---

## 1. Sơ đồ Chu trình Làm việc Chuẩn (Happy Path Workflow)

```text
[Phase 1: Client]
    │   Cập nhật Client.md (Pain points, Must-haves, Constraints, v5.1 Security & Evidence)
    ▼
[Phase 2: Product Owner]
    │   Phân tích yêu cầu, bóc tách User Stories, thiết lập AC & DoD, tạo TASK-xxxx.md
    ▼
[Phase 3: Finance Lead]
    │   Thẩm định tính khả thi tài chính: Regime-First, ADR Thresholds Lock, Risk Constraints,
    │   Benchmark kép (VN-Index & VN30 + Hurdle Rate 4.5%), Sizing, Chi phí LLM & Hạ tầng
    ▼
[Phase 4: Senior Dev]
    │   Thiết kế giải pháp, lập trình tối giản (Lazy Dev), Tường lửa Phase 0, Signal Lifecycle Phase 1,
    │   Tuân thủ SonarCloud (S3776 < 15, S8572 logging.exception, S1192 constants)
    ▼
[Phase 5: QA Lead]
    │   Viết unit tests tự động, kiểm thử biên (Edge Cases), RSS Injection payloads,
    │   Cô lập Mock I/O (Zero Test Leakage), đảm bảo Coverage >= 80%
    ▼
[Phase 6: Independent Reviewer]
    │   Audit mã nguồn, kiểm tra linting (Ruff exit 0), quét lỗ hổng bảo mật, Duplication <= 3%,
    │   Audit Disclaimer pháp lý trên 100% cảnh báo, kiểm toán Git Staging (No Local Files)
    ▼
[Phase 7: Client Review, Release & Local Workspace Hygiene]
        Bàn giao báo cáo nghiệm thu (Walkthrough) -> Client duyệt ->
        Cập nhật DECISION_LOG.md -> Kiểm tra .gitignore -> Commit & Push an toàn
```

---

## 2. Cơ chế Phản hồi & Vòng lặp Xử lý Từ chối (Rejection & Feedback Loops)

Nếu ở bất kỳ giai đoạn nào tiêu chuẩn không đạt, task sẽ kích hoạt cơ chế phản hồi ngược (Feedback Loop) để khắc phục triệt để trước khi được đi tiếp:

```text
       ┌─────────── [Phase 3: Finance Lead] ──────────┐
       │ (Từ chối định giá/rủi ro/ADR snooping)      │ (Đạt chuẩn tài chính)
       ▼                                              ▼
[Phase 2: PO làm rõ/điều chỉnh AC]           [Phase 4: Senior Dev]
                                                      ▲
                                                      │ (Sửa lỗi code/test/security)
                                                      ├────────────────────────┐
                                                      │                        │
                                             [Phase 5: QA Lead]       [Phase 6: Reviewer]
                                            (Failed test/Cov < 80%)  (Lint/Sonar/Duplication/
                                            (Leakage/Injection bypass) Disclaimer/Git Leak)
```

1. **Finance Lead REJECT (Không đạt chuẩn an toàn tài chính & phương pháp luận):**
   - **Lý do:** 
     - Tự ý thay đổi tham số Quant Core mà không có ADR chốt trước (Data Snooping).
     - Dùng AI Confidence chưa qua chuẩn định (uncalibrated) đưa thẳng vào Half-Kelly sizing formula.
     - Vi phạm giới hạn tập trung ngành (`SECTOR_MAP` không được enforce, sector > 25%).
     - Dữ liệu stale không có chốt chặn hoặc thiếu chuỗi Benchmark thực (VN-Index, VN30).
     - Giả định slippage cố định (fixed 15 bps) gây lạc quan thái quá trong thị trường downtrend/sàn.
   - **Xử lý:** Task chuyển về `PO_REVIEW`. PO cùng Client điều chỉnh phạm vi (Scope) hoặc bổ sung ràng buộc định lượng.
2. **QA Lead REJECT (Kiểm thử thất bại, hở bảo mật hoặc thiếu Coverage):**
   - **Lý do:**
     - Có unit test bị fail hoặc phát sinh lỗi hồi quy (regression).
     - Payload Prompt Injection qua RSS vượt qua bộ lọc vào LLM prompt.
     - Test case phát sinh network request thực ra Discord/Telegram (vi phạm Zero Test Leakage).
     - Code Coverage trên mã mới $< 80\%$.
   - **Xử lý:** Task chuyển về `DEV_IN_PROGRESS`. Senior Dev khắc phục triệt để lỗ hổng và thuật toán.
3. **Reviewer REJECT (Vi phạm SonarCloud, Pháp lý hoặc Vệ sinh Git):**
   - **Lý do:**
     - `ruff check` có warning/error, Cognitive Complexity $\ge 15$, `logging.error` trong `except`, hoặc duplication $> 3.0\%$.
     - Thiếu `SIGNAL_DISCLAIMER` bắt buộc trên các bản tin/webhook cảnh báo tín hiệu.
     - Phát hiện các file nghiên cứu cá nhân/local (`danh_gia_he_thong_quy_fund.md`, `stock_ai_roadmap.md`, `idea.md`...) bị stage vào Git index.
   - **Xử lý:** Task chuyển về `DEV_IN_PROGRESS` để Senior Dev refactor vi phẫu, bổ sung disclaimer và loại bỏ file local khỏi Git cache.
4. **Client REJECT (Chưa đạt kỳ vọng nghiệp vụ hoặc trải nghiệm):**
   - **Lý do:** Giao diện chưa trực quan, ngôn ngữ chưa chuẩn Unicode/CFA, hoặc thiếu tính năng Must-have theo hợp đồng nghiệp vụ.
   - **Xử lý:** Task chuyển về `PO_REVIEW` để tái lập trình kế hoạch cải tiến.

---

## 3. Chi tiết Từng Giai đoạn & Tiêu chí Chuyển tiếp (Hand-off Criteria)

### Giai đoạn 1: Khởi tạo Yêu cầu (Client Brief)
- **Actor:** Client (Người dùng).
- **Đầu vào:** Biểu mẫu `docs/AI-workflow/Client.md`.
- **Hành động:** Điền đầy đủ: Vấn đề gặp phải (Pain points), tính năng mong muốn, ràng buộc kỹ thuật, ngân sách, mục tiêu phiên bản (v5.1 Phase 0 & Phase 1).
- **Cổng chuyển tiếp:** File `Client.md` được lưu với trạng thái sẵn sàng để PO tiếp nhận.

### Giai đoạn 2: Phân tích & Phân rã Task (PO Analysis)
- **Actor:** Product Owner (PO).
- **Hành động:** 
  1. Đọc kỹ `Client.md`. Phản biện các điểm mù nghiệp vụ hoặc rủi ro pháp lý/bảo mật.
  2. Tạo file task tương ứng: `docs/AI-workflow/TASK/TASK-xxxx.md`.
  3. Định nghĩa cụ thể: User Stories, Điều kiện Chấp thuận (Acceptance Criteria - AC) theo cấu trúc *Given - When - Then*, Tiêu chuẩn Hoàn thành (Definition of Done - DoD).
  4. Xác lập rõ phạm vi Phase 0 (Bảo mật/Pháp lý) và Phase 1 (Bằng chứng Signal Lifecycle).
- **Cổng chuyển tiếp:** File task chuyển trạng thái `FINANCE_AUDIT`.

### Giai đoạn 3: Thẩm định Tài chính & Rủi ro (Finance Audit)
- **Actor:** Finance Lead (Kiểm soát Tài chính & Quản trị Rủi ro Quỹ).
- **Hành động:**
  1. **Khóa ngưỡng Quant Core (ADR Lock):** Xác nhận các ngưỡng F-Score $\ge 6$, MoS $\ge 15\%$, Z-Score $> 1.8$, RSI $< 70$, Conviction $\ge 55$ đã được đóng băng bằng ADR trước khi chạy kiểm định.
  2. **Thẩm định Regime-First & Benchmark:** Đảm bảo hệ thống sử dụng VN-Index làm chốt chặn Macro Circuit Breaker (Cash Mode khi downtrend) và so sánh song song với VN-Index, VN30, cùng rào cản tối thiểu (Hurdle Rate) 4.5%/năm.
  3. **Kiểm soát Mô hình Quản trị Vốn:** 
     - Enforce Half-Kelly kết hợp bộ lọc thanh khoản ADV20 ($ADV20 \ge 10 \times OrderSize$).
     - Enforce `SECTOR_MAP` với trần tỷ trọng tối đa $25\%$ cho một ngành.
     - Yêu cầu đo lường Effective Sample Size (ESS) thay vì raw count trades.
     - Nghiêm cấm đưa trực tiếp AI Confidence chưa calibrated vào công thức Kelly.
  4. **Đánh giá Hạ tầng & Chi phí:** Thẩm định ngân sách token Gemini LLM (15 RPM rate limit, nén prompt, 0 token cho bộ lọc định lượng bước 1).
- **Cổng chuyển tiếp:** Ký xác nhận "Financial Sanity Approved" trong `TASK-xxxx.md`, chuyển trạng thái `DEV_IN_PROGRESS`.

### Giai đoạn 4: Kiến trúc & Hiện thực hóa (Senior Dev Implementation)
- **Actor:** Senior Developer.
- **Hành động:**
  1. **Triết lý Lazy Senior Dev:** Tái sử dụng helper và pattern có sẵn trong `quant_engine.py`, `data_engine.py`, `data_gate.py`.
  2. **Hiện thực hóa Tường lửa Phase 0:**
     - Tích hợp `SIGNAL_DISCLAIMER` cố định vào cuối 100% tin nhắn Discord trong `discord_alerts.py`.
     - Xây dựng `sanitize_news_for_llm()` trong `data_engine.py` chặn triệt để Prompt Injection từ RSS (blocklist, độ dài tối đa title $\le 120$, summary $\le 400$).
     - Tích hợp Heartbeat hàng ngày lúc 08:30 trước ATO và cảnh báo suy thoái hệ thống.
  3. **Hiện thực hóa Hạ tầng Bằng chứng Phase 1:**
     - Thiết lập schema `signal_lifecycle` với dữ liệu bất biến (immutable) tại thời điểm phát tín hiệu.
     - Tách biệt rõ ràng `initial_stop_price` (bất biến để tính chuẩn R-Multiple) và `stop_loss_price` (biến đổi theo trailing stop).
     - Thay thế slippage cố định bằng mô hình slippage động phản ánh biến động giá sàn và thanh khoản.
  4. **Kỷ luật SonarCloud:** Cognitive Complexity $< 15$, `logging.exception` trong except block, trích xuất chuỗi lặp lại $\ge 3$ lần thành constant, không trùng lặp code giữa luồng Async và Sync.
- **Cổng chuyển tiếp:** Code chạy thông suốt, smoke test nội bộ đạt, chuyển trạng thái `QA_TESTING`.

### Giai đoạn 5: Kiểm thử Chất lượng Toàn diện (QA Verification)
- **Actor:** QA Lead.
- **Hành động:**
  1. Viết bộ unit tests tự động trong `tests/` bám sát Acceptance Criteria.
  2. Đo lường độ phủ Code Coverage đạt **$\ge 80\%$** (mục tiêu $85 - 95\%+$ trên module quant/rủi ro).
  3. **Kiểm thử An ninh & Biên (Edge Cases):**
     - Bơm các payload Prompt Injection thực tế vào RSS parser để xác nhận bộ lọc chặn thành công.
     - Mock toàn diện Discord webhook và Supabase I/O (nghiêm cấm rò rỉ network ra kênh thật).
     - Test kịch bản dữ liệu đóng băng (stale data), mất mạng, chia cho 0, cổ phiếu mất thanh khoản.
  4. Tuân thủ nguyên tắc "No Excuses": Luôn hoàn thành file test dù môi trường local có trở ngại.
- **Cổng chuyển tiếp:** 100% tests pass, chuyển trạng thái `CODE_REVIEW`.

### Giai đoạn 6: Kiểm duyệt Độc lập & Kiểm toán (Independent Review)
- **Actor:** Independent Reviewer.
- **Hành động:**
  1. **Audit Code Quality:** Chạy `ruff check . --output-format=github` bắt buộc đạt **exit code 0**. Quét các mã SonarCloud (S8572, S3776, S1192, F401). Mật độ trùng lặp mã mới $\le 3.0\%$.
  2. **Audit Tuân thủ Pháp lý:** Rà soát 100% mẫu cảnh báo/tín hiệu đảm bảo có disclaimer miễn trừ trách nhiệm đầu tư theo Luật Chứng khoán 2019.
  3. **Audit An toàn Bí mật (Secrets & Privacy):** Không hardcode API key. Toàn bộ prompt payload và cấu hình động tuân thủ cơ chế Zero Disk Persistence.
  4. **Audit Vệ sinh Git (Git Workspace Hygiene):** Kiểm tra `git status` đảm bảo **KHÔNG CÓ** file nháp cá nhân hoặc tài liệu nghiên cứu nội bộ nào của Client bị stage vào Git index.
- **Cổng chuyển tiếp:** Đóng dấu `[ LGTM - Looks Good To Me ]` vào `TASK-xxxx.md`, chuyển trạng thái `CLIENT_ACCEPTANCE`.

### Giai đoạn 7: Nghiệm thu & Quản lý Tài nguyên Cục bộ (Client Acceptance & Release)
- **Actor:** Client + Hệ thống.
- **Hành động:**
  1. Trình diễn báo cáo nghiệm thu tóm tắt (Walkthrough) cho Client.
  2. Client bấm duyệt nghiệm thu.
  3. Ghi lại các quyết định kỹ thuật/nghiệp vụ quan trọng vào `docs/AI-workflow/GLOBAL/DECISION_LOG.md`.
  4. **Bảo vệ Tài liệu Nội bộ Local (Local Workspace Hygiene Rule):**
     - Các file nghiên cứu cá nhân, chiến lược phác thảo, tài liệu đánh giá của Client (ví dụ: `danh_gia_he_thong_quy_fund.md`, `stock_ai_roadmap.md`, `idea.md`...) được định danh là **TÀI NGUYÊN NỘI BỘ (LOCAL ONLY)**.
     - Bắt buộc khai báo các file này trong `.gitignore`.
     - Tuyệt đối không đưa vào `git add`, không tạo commit chứa các file này, và không push lên remote repository.
  5. Thực hiện `git commit` và `git push` mã nguồn chính thức lên GitHub an toàn.
- **Cổng chuyển tiếp:** Chuyển trạng thái task sang `DONE`.

---

## 4. Nguyên tắc Phân định Tài nguyên: Local Workspace vs. Git Repository

Để bảo vệ bí mật chiến lược cá nhân và duy trì sự tinh gọn cho repository dự án, toàn bộ thành viên và AI Agent phải tuân thủ bảng phân định:

| Loại Tài liệu | Đường dẫn / Tên file tiêu biểu | Trạng thái Git | Mục đích sử dụng |
|---|---|---|---|
| **Local Private Docs** | `danh_gia_he_thong_quy_fund.md`<br>`stock_ai_roadmap.md`<br>`idea.md` | **`.gitignore` (CẤM PUSH)** | Tài liệu phác thảo ý tưởng, ghi chép nghiên cứu, chiến lược riêng của Client. |
| **Workflow Tài liệu** | `docs/AI-workflow/Client.md`<br>`docs/AI-workflow/GLOBAL/*`<br>`docs/AI-workflow/TASK/*` | **Tracked / Committed** | Tài liệu quy chuẩn kỹ thuật, yêu cầu chính thức và lịch sử quyết định chung. |
| **Mã nguồn & Cấu hình** | `*.py`, `prompts/*`, `components/*`, `tests/*`, `requirements.txt` | **Tracked / Committed** | Mã nguồn vận hành hệ thống, đáp ứng đầy đủ SonarCloud & Unit Tests. |
| **Bí mật & Khóa API** | `.env`, `.env.local`, `.streamlit/secrets.toml` | **`.gitignore` (CẤM PUSH)** | Thông tin đăng nhập, API key, webhook URL. |

---

## 5. Quy tắc Giải quyết Bất đồng (Conflict Resolution)

1. **Nếu Kỹ thuật mâu thuẫn với Nghiệp vụ Tài chính:** Ý kiến của Finance Lead và Data Gate có quyền ưu tiên cao hơn để bảo toàn an toàn vốn cho nhà đầu tư.
2. **Nếu Tiến độ mâu thuẫn với Tiêu chuẩn An toàn (Phase 0 & SonarCloud):** Tuyệt đối không tắt tường lửa disclaimer, không bỏ qua kiểm tra Prompt Injection, và không hạ thấp chuẩn SonarCloud/Coverage. Nếu cần gấp, PO phải cắt giảm Scope tính năng thay vì cắt giảm chốt chặn an toàn.
3. **Nếu có nguy cơ rò rỉ file Local:** Mọi hành động `git push` phải bị dừng ngay lập tức cho đến khi toàn bộ file thuộc danh mục Local Private Docs được gỡ hoàn toàn khỏi Git staging và đưa vào `.gitignore`.
