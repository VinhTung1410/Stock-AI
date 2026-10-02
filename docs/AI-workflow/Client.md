# 🎯 YÊU CẦU DỰ ÁN (CLIENT BRIEF) - VERSION 7.4

**Tên dự án:** Stock-AI / AI Investment Decision & Research Platform  
**Phiên bản:** v7.4 — Phase 14: Data & Valuation Plumbing (Hệ thống Dẫn truyền Dữ liệu BCTC & Chuẩn hóa Định giá Thực chất)  
**Trọng tâm:** *"Khắc phục triệt để lỗ hổng đứt gãy dẫn truyền dữ liệu (`fin_dict`) vào toàn bộ các tầng định giá và hard gate; bãi bỏ tình trạng định giá fallback tạo ra MoS hằng số vô nghĩa (GROWTH=15.25%, BANK=10.71%, CYCLICAL=−17.6%); chuẩn hóa việc truyền `symbol`, `sector`, `tech_data` vào `evaluate_decision_hard_gates`; sửa lỗi ánh xạ khóa cột tiếng Việt trong `_build_portfolio_quant_summary` và `portfolio_guard.py` khiến P&L luôn bằng 0 và vị thế lãi bị đánh đồng thành vị thế lỗ; khóa cứng `mos_is_informative=False` cho CYCLICAL/REAL_ESTATE khi thiếu BCTC; và bổ sung kiểm tra độ tươi ngày tháng (`current_date`) trong `load_market_context()` để triệt tiêu việc nạp báo cáo chuyên gia cũ như thông tin trong ngày."*

---

## 1. MỤC TIÊU PHIÊN BẢN v7.4 (PHASE 14: DATA & VALUATION PLUMBING)

1. **TASK-0042: Fix fin_dict Pipeline & Gate Parameter Wiring (Root Cause - Mục 14.0):**
   - **Vấn đề cốt tử:** Audit hệ thống ngày 02/10/2026 phát hiện `fin_dict` không bao giờ được truyền vào `calculate_fair_value_and_mos` tại các luồng thực thi chính (`data_engine.py`, `ai_analyst.py`, `trading_bot.py`). Toàn bộ hệ thống đang chạy trên nhánh fallback, khiến MoS trở thành hằng số giả tạo.
   - **Giải pháp:**
     - Đấu nối `fin_dict` (từ `get_financial_ratios`) trước khi gọi `calculate_fair_value_and_mos` trong `scan_market_opportunities()`, `_process_single_watchlist_item()`, `evaluate_watchlist()`, `evaluate_portfolio()`, và `_prepare_smart_committee_context()`.
     - Truyền đầy đủ `symbol`, `sector`, `fin_dict`, `tech_data` vào mọi lời gọi `evaluate_decision_hard_gates()` (trong `generate_quantamental_2pass_report()`, `scan_market_opportunities()`, và Smart Committee).

2. **TASK-0043: Fix Portfolio P&L Key Mapping (Mục 14.1):**
   - **Vấn đề cốt tử:** Hàm `_build_portfolio_quant_summary` và `evaluate_holding_position` đọc key tiếng Anh (`avg_price`, `market_price`), trong khi DataFrame danh mục thực tế tại Việt Nam trả về các cột tiếng Việt: `"Giá vốn (k)"`, `"Giá TB (k)"`, `"Thị giá (k)"`, `"Giá hiện tại (k)"`, `"Giá cao (k)"`. Hệ quả: `entry_price` luôn = 0, `pl_pct` luôn = 0%, mọi vị thế lãi đều bị chuyển sang nhánh "LỖ" và cơ chế Trailing Stop bảo vệ lợi nhuận bị vô hiệu hóa hoàn toàn.
   - **Giải pháp:**
     - Chuẩn hóa ánh xạ cột đa ngữ (Column Mapping): `"Giá TB (k)"` / `"Giá vốn (k)"` $\rightarrow$ `avg_price`, `"Giá hiện tại (k)"` / `"Thị giá (k)"` $\rightarrow$ `market_price`, `"Giá cao (k)"` $\rightarrow$ `high_price`, `"Mã CP"` $\rightarrow$ `symbol`, `"Khối lượng"` $\rightarrow$ `volume`.
     - Đảm bảo `entry_price > 0`, `pl_pct` tính toán chính xác và các vị thế có lãi kích hoạt đúng Trailing Stop.

3. **TASK-0044: Fix mos_is_informative Correctness & Fallback Hard Block (Mục 14.2):**
   - **Vấn đề:** Khi `fin_dict={}`, archetype `CYCLICAL` và `REAL_ESTATE` tự tính Fair Value theo hệ số nhân thị giá nhưng cờ `mos_is_informative` vẫn trả về `True`.
   - **Giải pháp:**
     - `mos_is_informative` CHỈ ĐƯỢC PHÉP bằng `True` khi Fair Value được tính từ số liệu BCTC thực chất (với `CYCLICAL` bắt buộc có `eps_history` hoặc `pe`; với `REAL_ESTATE` bắt buộc có `bvps` hoặc `pb`).
     - Khi `fin_dict` rỗng hoặc thiếu BCTC, `mos_is_informative = False` và Decision Hard Gates tự động khóa cứng (Block) khuyến nghị MUA.

4. **TASK-0045: Fix Market Context Staleness Check (Mục 14.3):**
   - **Vấn đề:** `load_market_context()` không kiểm tra ngày hiện tại nếu caller không truyền `current_date`, dẫn đến việc file `data/market_context.json` từ ngày hôm trước (hoặc tuần trước) vẫn được nạp vào system prompt như nhận định của phiên hôm nay.
   - **Giải pháp:**
     - `load_market_context()` mặc định lấy ngày hiện tại (múi giờ UTC+7 / `date.today()`) khi `current_date=None` và `allow_stale=False`.
     - Nếu ngày của báo cáo khác ngày hiện tại, trả về `MarketContext(is_valid=False)` để caller tự động xử lý kịch bản không có context (Fail-safe).

---

## 2. KẾ THỪA CÁC CHỐT CHẶN PHIÊN BẢN TRƯỚC (v6.1 - v7.3)

1. **Phase 13 (v7.3):** Core Valuation Re-Architecture, Structural Risk Protection & Macro Hysteresis (Forward EPS $\times$ Median P/E, SOTP MWG, Structural Stop-loss, Macro Hysteresis $\pm 1.5\%$, `FLAG_DATA_STALE_FREEZE`).
2. **Phase 12 (v7.2):** Compounder & Retail Flow Gatekeeper (Anti-Synthetic MoS, Chuẩn hóa `target_buy`, Bộ lọc xu hướng trung hạn MA100/MA200, Phạt xả ròng khối ngoại).
3. **Phase 11 (v7.1):** Cyclical Valuation Overhaul (Peak Earnings Trap, Normalized EPS 5 năm, Regional Peer Benchmark, Sector Risk Flags).
4. **Phase 10 (v7.0):** Real Estate & Holding Valuation Overhaul (SOTP Sanity Check, Core Earnings Ratio, Survival Gate, P/B Mean Reversion Guardrail).
5. **Phase 8 (v6.3):** Context Engine & PTKT Hàng ngày (Báo cáo TCBS vào `market_context.json`, Code MA200 luôn thắng nhận định chuyên gia).
6. **Phase 1-7 (v5.1 - v6.2):** Evidence Integrity, Signal Lifecycle bất biến, Data Gate nhị phân cứng, 4 tầng Fact/Inference/Hypothesis.

---

## 3. NGUYÊN TẮC QUẢN TRỊ RỦI RO & BẢO TOÀN KIẾN TRÚC

- **Zero-Unwired Data Principle:** Mọi mô hình định giá định lượng phải được cấp dữ liệu tài chính BCTC thực (`fin_dict`). Nghiêm cấm chạy âm thầm trên nhánh fallback mà không có cảnh báo.
- **Strict Informative MoS Enforcement:** Cờ `mos_is_informative` là chốt an toàn tối thượng. Mọi tín hiệu fallback đều phải bị đánh dấu `mos_is_informative=False` và bị cấm mở vị thế Mua giá trị.
- **Fail-Safe Graceful Degradation:** Mất dữ liệu bối cảnh hoặc BCTC stale $\rightarrow$ vô hiệu hóa context an toàn, không làm gián đoạn luồng vận hành nền của bot.
- **Data Model Idempotence:** Ánh xạ dữ liệu DataFrame danh mục phải tương thích ngược cả tiếng Việt và tiếng Anh, không gây ngoại lệ KeyError.

---

## 4. TIÊU CHUẨN KỸ THUẬT (QUALITY GATE)

- **SonarCloud:** Cognitive Complexity < 15 (S3776), `logging.exception()` trong except (S8572), không trùng lặp chuỗi $\ge 3$ lần (S1192), duplicate lines density $\le 3.0\%$.
- **Ruff:** `ruff check --fix .` đảm bảo exit code 0 và imports chuẩn `isort`.
- **Test Coverage:** $\ge 80\%$ (mục tiêu $85 - 95\%+$) cho toàn bộ logic mới; 100% test case kiểm thử biên, e2e entry gates, và kịch bản fallback.
- **TDD (Test-Driven Development):** Viết integration test `tests/test_e2e_entry_gates.py` reproduce lỗi và fail trước khi sửa code, sau đó pass 100%.