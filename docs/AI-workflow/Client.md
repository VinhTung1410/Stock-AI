# 🎯 YÊU CẦU DỰ ÁN (CLIENT BRIEF) - VERSION 6.3

**Tên dự án:** Stock-AI / AI Investment Decision & Research Platform  
**Phiên bản:** v6.3 — Phase 8: Daily Analyst Report Pipeline & Context Engine Integration  
**Trọng tâm:** *"Tích hợp báo cáo phân tích kỹ thuật thị trường hàng ngày từ TCBS vào hệ thống dưới dạng nguồn INFERENCE bậc cao (Context Engine) có kiểm soát, tuân thủ nguyên tắc Zero-Democracy Quant Gate và tuyệt đối không sáng tác/bịa đặt số liệu."*

---

## 1. MỤC TIÊU PHIÊN BẢN v6.3 (PHASE 8: CONTEXT ENGINE)

1. **Chuẩn hóa Cấu trúc Thư mục Tài liệu Tham chiếu (`docs/Reference/`):**
   - Phân loại rõ ràng các nhóm tài liệu tham khảo theo nghiệp vụ:
     + `PTKT_Daily/`: Báo cáo phân tích kỹ thuật thị trường chung hàng ngày từ CTCK (TCBS).
     + `Stock_Analysis/`: Báo cáo phân tích chuyên sâu từng mã cổ phiếu cụ thể (BSR, VIC...).
     + `Insider_Trading/`: Báo cáo theo dõi giao dịch nội bộ lãnh đạo và cá mập theo ngành.
     + `Macro/`: Báo cáo vĩ mô, lãi suất, tỷ giá định kỳ.
     + `Archive/`: Lưu trữ các báo cáo cũ theo tháng (`YYYY-MM`).
   - Duy trì file theo dõi trạng thái `manifest.json` ghi nhận lịch sử xử lý, ngày báo cáo, và đường dẫn file context.

2. **Xây dựng Pipeline Trích xuất Dữ liệu Báo cáo Hàng ngày (`scripts/parse_daily_reports.py`):**
   - Đọc tự động file PDF mới nhất chưa xử lý từ `docs/Reference/PTKT_Daily/` bằng `PyMuPDF`.
   - Trích xuất thông tin khách quan chuẩn hóa: Ngày báo cáo, Nguồn, Xu hướng thị trường (Analyst Regime), Vùng hỗ trợ/kháng cự VN-Index, Nhóm ngành tâm điểm, Danh mục cổ phiếu có tín hiệu Mua/Bán, Giao dịch khối ngoại & cá mập, Từ khóa rủi ro và Tóm tắt diễn biến.
   - **Nguyên tắc Sắt - Zero Hallucination & Zero Fabrication:** Tuyệt đối không suy diễn hoặc bịa đặt số liệu. Trường thông tin nào không xuất hiện rõ ràng trong văn bản PDF phải gán giá trị mặc định (`[]` hoặc `"UNKNOWN"`).
   - Xuất dữ liệu sạch ra `data/market_context.json` và đánh dấu `processed: true` trong `manifest.json`.

3. **Hiện thực hóa Context Engine (`context_engine.py`):**
   - Định nghĩa dataclass `MarketContext` chứa đầy đủ cấu trúc ngữ cảnh thị trường.
   - Hàm `load_market_context()` nạp dữ liệu an toàn, kiểm tra tính hợp lệ và độ tươi mới (so sánh `date` với ngày phiên giao dịch).
   - Hàm `build_context_prompt_snippet()` đóng gói thông tin xúc tích để inject vào System Prompt của Hội đồng Chuyên gia AI trong `ai_analyst.py`.
   - **Fail-Safe Thiết yếu:** Nếu file `market_context.json` không tồn tại, bị lỗi định dạng hoặc ngày báo cáo bị lệch (stale data), Context Engine tự động chuyển về chế độ graceful fallback (`is_valid = False`), hệ thống tiếp tục vận hành bình thường không bị gián đoạn (Non-blocking).

4. **Kiểm soát Xung đột Xu hướng Thị trường (Regime Conflict Arbitration):**
   - Hàm `check_regime_conflict(code_regime, analyst_regime)` so sánh xu hướng khách quan từ Python MA200 (`regime_classifier.py` - FACT) với nhận định chuyên gia CTCK (INFERENCE).
   - **Quy tắc Ưu tiên Định lượng:** Code tính toán MA200 luôn luôn thắng.
   - Nếu Code báo UPTREND nhưng Chuyên gia cảnh báo DOWNTREND: Bật cờ `regime_conflict = True` và tự động giảm 50% quy mô vị thế đề xuất để phòng thủ thận trọng.
   - Nếu Code báo DOWNTREND nhưng Chuyên gia nhận định UPTREND: Bật cờ `regime_conflict = True`, giữ nguyên chế độ Cash Mode (100% tiền mặt), cấm tuyệt đối việc LLM hoặc nhận định bên ngoài mở quyền mua (`can_buy`).

5. **Lưu vết Ngữ cảnh Kiểm toán (Audit Trail & DB Migration):**
   - Bổ sung migration `migrations/0004_analyst_context.sql` thêm 4 trường vào bảng `decision_records`:
     `analyst_context_used`, `regime_conflict`, `context_source_file`, `context_date`.
   - Cập nhật `SignalEvent` trong `ai_analyst.py` để ghi nhận đầy đủ các cờ ngữ cảnh này vào nhật ký quyết định vĩnh viễn.

---

## 2. KẾ THỪA CÁC MỤC TIÊU PHIÊN BẢN TRƯỚC (v6.1 - v6.2)

1. **Bản vá Báo cáo ATC & Single Source of Truth VN-Index (TASK-0017 - Hotfix v6.1.1):**
   - Khắc phục VN-Index 0.00 điểm bằng auto-fetch fallback và persistent cache `_LAST_KNOWN_TECH_CACHE["VNINDEX"]`.
   - Bổ sung `diff_points`, `diff_ma20`, `diff_ma50` vào `fetch_stock_technical()`.
   - Hợp nhất 100% tỷ lệ Tiền/Cổ phiếu từ `quant_engine.evaluate_market_regime()`, xóa bỏ dict hardcode 70/30.
2. **Hạ tầng Bằng chứng Quyết định Bất biến (TASK-0013 & TASK-0014):**
   - Replay audit idempotent, cờ `t_plus_2_locked`, `mos_is_informative`, lưu vết 4 tầng FACT, INFERENCE, OPINION, COUNTERFACTUAL trong `decision_records`.
   - Evidence-Based Kill Switch giảm 50% size khi Expectancy 20 lệnh gần nhất < 0.
3. **Thắt chặt AI Governance (TASK-0015):**
   - Veto Only: LLM chỉ có quyền Veto hoặc giảm vị thế; không được tự cấp quyền mua.
   - Wrapper tập trung 15 RPM, khóa `temperature = 0.0`, SHA-256 audit hash, Fail-Safe Parser Pass 1.
4. **Exit Hypothesis Lab & Conviction Weights IC (TASK-0016):**
   - Exit Replay 4 chiến lược với Paired Bootstrap (Report-Only).
   - Kiểm định Spearman IC & Benjamini–Hochberg FDR ($\alpha = 0.05$).

---

## 3. NGUYÊN TẮC QUẢN TRỊ RỦI RO & BẢO TOÀN KIẾN TRÚC

- **Zero-Democracy Risk Gate:** Báo cáo bên ngoài chỉ là nguồn tham khảo (INFERENCE), không bao giờ có quyền ghi đè luật toán học của Quant Gate.
- **Tuyệt Đối Không Sáng Tác Dữ Liệu (Zero-Fabrication):** Mọi trường dữ liệu trích xuất từ báo cáo phải trung thực 100% với nội dung văn bản.
- **Fail-Safe & Graceful Degradation:** Mất kết nối, thiếu file, file hỏng hoặc stale data KHÔNG ĐƯỢC PHÉP làm sập luồng phân tích chính.
- **Single Source of Truth (SSOT):** Tham số phân bổ vốn và regime gốc luôn phát xuất từ `quant_engine.py` và `regime_classifier.py`.

---

## 4. TIÊU CHUẨN KỸ THUẬT (QUALITY GATE)

- **SonarCloud:** Cognitive Complexity < 15 (S3776), `logging.exception()` trong except (S8572), không trùng lặp chuỗi >= 3 lần (S1192).
- **Ruff:** Tự động sắp xếp import và định dạng code với `ruff check --fix .`, bảo đảm exit code 0.
- **Test Coverage:** >= 80% cho toàn bộ logic mới trong `context_engine.py` và parser; 100% I/O ngoài (PDF, File, Gemini) được mock chặt chẽ khi kiểm thử.\n