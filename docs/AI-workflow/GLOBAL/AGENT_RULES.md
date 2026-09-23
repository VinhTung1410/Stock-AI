# 📜 GLOBAL: AGENT RULES (QUY TẮC BẮT BUỘC DÀNH CHO CÁC ROLE)

Tài liệu này quy định các nguyên tắc làm việc cốt lõi, đạo đức nghề nghiệp, và kỷ luật kỹ thuật mà TẤT CẢ các vai trò (PO, Finance, Senior Dev, QA Lead, Reviewer) phải tuân thủ tuyệt đối trong toàn bộ quy trình.

---

## 1. Triết lý Kỹ sư Thực dụng (Lazy Senior Developer Philosophy)

Tất cả các thành viên kỹ thuật phải suy nghĩ trước khi gõ code. Code tốt nhất là dòng code không cần phải viết:
1. **YAGNI (You Aren't Gonna Need It):** Không tự vẽ thêm tính năng phức tạp nếu Client và PO không yêu cầu trong `Client.md` hoặc `TASK-xxxx.md`.
2. **Tận dụng tài nguyên sẵn có:** Luôn kiểm tra xem hàm helper, thuật toán định lượng, hoặc thư viện đã có trong codebase chưa (`quant_engine.py`, `data_engine.py`, `data_gate.py`).
3. **Ưu tiên Standard Library & Native Engine:** Sử dụng thư viện chuẩn của Python hoặc các hàm native của `vnstock`/`pandas`/`numpy`.
4. **Sửa đổi tối thiểu (Surgical Edits):** Tránh viết lại toàn bộ file hoặc refactor tràn lan gây hồi quy (regression) và tăng duplicated lines density.

---

## 2. Tiêu chuẩn Chất lượng Mã nguồn (SonarCloud Quality Gates)

Trước khi chuyển giao task sang giai đoạn Review hoặc Commit, code phải đáp ứng:

- **Độ phức tạp nhận thức (Cognitive Complexity - S3776):** Mọi hàm phải có độ phức tạp **< 15**. Sử dụng kỹ thuật Early Return (`if not condition: return`) và tách hàm con độc lập.
- **Xử lý Ngoại lệ & Logging (S8572):** Trong các khối `except Exception as e:`, BẮT BUỘC sử dụng `logging.exception("...")` thay vì `logging.error(f"... {e}")` để bảo tồn stack trace.
- **Trùng lặp Chuỗi ký tự (String Duplication - S1192):** Nếu một chuỗi ký tự (ví dụ: nhãn ngành, trạng thái giao dịch, category) xuất hiện từ 3 lần trở lên trong một file, phải trích xuất thành CONSTANT ở đầu file.
- **Định dạng & Thứ tự Import (Ruff I001):** Bắt buộc chạy `ruff check --fix` để tự động sắp xếp imports (thư viện chuẩn -> bên thứ ba -> module nội bộ) và chuẩn hóa khoảng trống.
- **Loại bỏ mã chết (Dead Code & F401):** Không để lại biến thừa (S1481), tham số không dùng (S1172), hoặc import thừa (F401).

---

## 3. Kỷ luật Kiểm thử & Độ phủ (> 80% Coverage)

- **Test-Driven Delivery:** Mọi tính năng mới, module định lượng, hoặc công thức rủi ro đều phải đi kèm unit test trong thư mục `tests/`.
- **Target Coverage:** Độ phủ kiểm thử trên mã mới phải đạt tối thiểu **80%** (khuyến khích 85-95%+).
- **Edge Cases Bắt buộc:**
  - Dữ liệu rỗng, `None`, hoặc chia cho 0 (`ZeroDivisionError`).
  - Dữ liệu bị đóng băng (stale data cũ nhiều quý/năm).
  - Tín hiệu nhiễu cực đoan (P/E âm, P/B lệch chuẩn, thanh khoản tắt thanh khoản sàn).

---

## 4. Bảo mật & Bảo vệ Dữ liệu (Zero Disk Persistence)

- **Tuyệt đối không lưu khóa bí mật:** API Keys (`VNSTOCK_API_KEY`, Supabase Key, Discord Webhook, Google AI API Key) chỉ được đọc qua biến môi trường (`.env` hoặc `os.environ`), tuyệt đối không hardcode trong mã nguồn hoặc commit lên Git.
- **Không rò rỉ dữ liệu nhạy cảm vào log:** Không in raw API responses chứa thông tin định danh người dùng hoặc tài khoản.

---

## 5. Chuẩn mực Giao tiếp & Ngôn ngữ

- **Ngôn ngữ báo cáo & Giao diện:** Sử dụng 100% Tiếng Việt chuẩn chính tả và bảng mã Unicode.
- **Thuật ngữ chuyên ngành:** Giữ nguyên các thuật ngữ quốc tế chuẩn CFA (ví dụ: *P/E, P/B, ROE, Margin of Safety, Half-Kelly, Drawdown, ADV20, Trailing Stop, Hit Rate*), đi kèm diễn giải ngắn gọn nếu phục vụ người dùng cuối.
- **Nghiêm cấm:** Tuyệt đối không dùng chữ Hán / tiếng Trung hoặc tiếng bồi làm giảm tính chuyên nghiệp của hệ thống tài chính.
