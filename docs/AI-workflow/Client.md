# 🎯 YÊU CẦU DỰ ÁN (CLIENT BRIEF)

**Tên dự án:** Stock-AI / AI Trading Bot  
**Ngày tạo:** [YYYY-MM-DD]  
**Người yêu cầu (Client):** [Tên của bạn]  
**Phiên bản yêu cầu:** v1.0  

---

## 1. TỔNG QUAN DỰ ÁN (EXECUTIVE SUMMARY)
- **Vấn đề hiện tại (Pain points):** [Mô tả ngắn gọn vấn đề bạn đang gặp phải. Ví dụ: Dữ liệu phân tích báo cáo tài chính của một số mã bị cũ dẫn đến định giá P/B bị lệch; Hoặc: Chưa có hệ thống tự động cảnh báo real-time khi cổ phiếu chạm điểm cắt lỗ ATR(14).]
- **Giải pháp mong muốn:** [Mô tả hệ thống hoặc tính năng bạn muốn xây dựng. Ví dụ: Một tính năng tự động lọc cổ phiếu đạt tiêu chuẩn F-Score >= 7 kết hợp bộ lọc thanh khoản ADV20 và gửi tin nhắn cảnh báo qua Discord kèm khuyến nghị phân bổ vốn Half-Kelly.]

---

## 2. CHÂN DUNG NGƯỜI DÙNG (USER PERSONAS)
Hệ thống phục vụ những nhóm người dùng nào?
- **Nhóm 1 (Nhà đầu tư cá nhân / Client):** Cần giao diện trực quan, khuyến nghị rõ ràng (BUY/HOLD/SELL), có giải thích lý do ngắn gọn bằng tiếng Việt chuẩn CFA, không bị biệt ngữ khó hiểu.
- **Nhóm 2 (Nhà quản lý danh mục / Admin):** Cần theo dõi tỷ trọng các ngành, kiểm soát rủi ro tập trung không quá 25%, và theo dõi lịch sử hiệu suất (Alpha Tracker, Hit Rate).

---

## 3. TÍNH NĂNG CỐT LÕI (CORE FEATURES - MUST HAVE)
*Định dạng thô các tính năng cần có để PO phân rã thành User Stories:*
- [Feature 1]: [Ví dụ: Tự động phát hiện và loại bỏ cổ phiếu có dữ liệu báo cáo tài chính bị đóng băng quá 2 quý].
- [Feature 2]: [Ví dụ: Tính toán kích thước vị thế an toàn dựa trên Half-Kelly Criteria và khối lượng giao dịch bình quân 20 phiên].
- [Feature 3]: [Ví dụ: Thêm tab giao diện theo dõi diễn biến định giá P/E, P/B bands theo thời gian thực].
- [Feature 4]: ...

---

## 4. ĐỊNH HƯỚNG VÀ RÀNG BUỘC KỸ THUẬT (TECHNICAL CONSTRAINTS)
*Client đưa ra các yêu cầu bắt buộc để Finance và Senior Dev đánh giá tính khả thi và chi phí:*
- **Tech Stack ưu tiên:** Python 3.10+, Streamlit, thư viện Vnstock, Supabase PostgreSQL, Apache ECharts.
- **Tích hợp hệ thống (Integration):** Tích hợp cảnh báo Discord Webhook, Google AI Gemini API.
- **Quy chuẩn chất lượng:** Tuân thủ SonarCloud (Cognitive Complexity < 15, S8572 logging.exception, Ruff I001) và Unit Test Coverage >= 80%.
- **Ngân sách hạ tầng tối đa:** [Ví dụ: Ưu tiên dùng các tier miễn phí của Streamlit Community Cloud / Supabase Free Tier, chi phí API Gemini tối đa 10$/tháng].

---

## 5. YÊU CẦU PHI CHỨC NĂNG (NON-FUNCTIONAL REQUIREMENTS)
- **Hiệu năng:** Thời gian phản hồi phân tích 1 mã cổ phiếu dưới 5 giây; hỗ trợ quét dữ liệu batch không làm treo giao diện.
- **Độ tin cậy:** 100% dữ liệu phải qua Data Gate; nếu dữ liệu bất thường phải từ chối khuyến nghị, tuyệt đối không đưa ra số liệu ảo.
- **Ngôn ngữ:** 100% Tiếng Việt chuẩn Unicode, không dùng chữ Hán/tiếng Trung.
- **Thời hạn kỳ vọng (Deadline):** [Hoàn thành trong sprint hiện tại].

---

## 6. LỊCH SỬ RỦI RO & BÀI HỌC XƯƠNG MÁU (KNOWN RISKS & LESSONS LEARNED)
*Client và đội ngũ ghi nhận các bài học thực tế từ vận hành để các role luôn ghi nhớ:*
1. **Sự cố dữ liệu BCTC đóng băng (Stale Data Incident):**
   - *Bài học:* Dữ liệu của một số mã lớn (ví dụ VCB) từng bị kẹt ở BCTC nhiều năm trước, dẫn đến tính P/B ảo (4.06x). Client yêu cầu: Bất kỳ mã nào có BCTC cũ quá 2 quý PHẢI bị khóa khuyến nghị (`recommendation_allowed = False`). Thà không có số liệu còn hơn số liệu sai.
2. **Bẫy thanh khoản cổ phiếu nhỏ (Penny Liquidity Trap):**
   - *Bài học:* Các mã thanh khoản dưới 300k cp/phiên (ADV20 < 300k) khi thị trường giảm rất dễ "trắng bên mua". Client yêu cầu hệ thống cấm khuyến nghị mua lướt sóng hoặc tỷ trọng lớn với nhóm này.
3. **Ảo giác AI & FOMO Đỉnh sóng:**
   - *Bài học:* AI LLM đọc tin tức tích cực có xu hướng hưng phấn quá đà khi cổ phiếu đã tăng nóng (RSI > 75). Phải luôn có bộ lọc trọng tài định lượng (PM Arbitration) để chặn lệnh FOMO.
4. **Bội chi Token LLM (Token Cost Runaway):**
   - *Bài học:* Gửi toàn bộ dữ liệu thô hàng nghìn dòng vào prompt làm tăng vọt chi phí API. Phải lọc trước bằng code Python (0 token) và chỉ gửi dữ liệu tóm tắt tinh gọn cho LLM.
