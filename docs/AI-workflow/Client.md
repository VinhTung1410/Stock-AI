# 🎯 YÊU CẦU DỰ ÁN (CLIENT BRIEF) - VERSION 7.1

**Tên dự án:** Stock-AI / AI Investment Decision & Research Platform  
**Phiên bản:** v7.1 — Phase 11: Cyclical Valuation Overhaul (Cải tổ Toàn diện Định giá Cổ phiếu Chu kỳ — Dầu khí, Thép, Hóa chất)  
**Trọng tâm:** *"Chấm dứt triệt để bẫy P/E thấp tại đỉnh chu kỳ lợi nhuận (Peak Earnings Trap) cho nhóm CYCLICAL (BSR, HPG, HSG, DGC...); áp dụng mô hình Normalized EPS (chuẩn hóa 5 năm), so sánh tương quan định giá với Peer quốc tế trong khu vực (P/B, EV/EBITDA), và thiết lập hệ thống cảnh báo rủi ro đặc thù ngành (Sector-Specific Risk Flags: Tồn kho, Xu hướng biên gộp, Rủi ro chính sách/hết hạn ưu đãi thuế) nhằm bảo vệ vốn tuyệt đối trước các pha đảo chiều chu kỳ hàng hóa."*

---

## 1. MỤC TIÊU PHIÊN BẢN v7.1 (PHASE 11: CYCLICAL VALUATION OVERHAUL)

1. **TASK-0029: Peak Earnings Trap Detector (Mục 11.0):**
   - Khắc phục bẫy P/E thấp đánh lừa hệ thống khi doanh nghiệp chu kỳ đạt đỉnh lợi nhuận ngắn hạn (như BSR hưởng lợi từ xung đột Hormuz/crack spread đột biến):
     - Khi $P/E < 6.5x$ VÀ biên lợi nhuận gộp giảm liên tiếp $\ge 2$ quý:
       - **Khóa khuyến nghị MUA** (`recommendation_allowed = False`).
       - Xếp hạng định giá tối đa: `"🔴 ĐỊNH GIÁ QUÁ ĐẮT (MOS Âm > 8%)"` (Peak Earnings Trap).
       - Bật cờ cảnh báo: `PEAK_EARNINGS_TRAP`, hạ `confidence = "LOW"`.
     - Nếu $P/E < 6.5x$ nhưng biên gộp vẫn mở rộng hoặc ổn định: Duy trì upside thận trọng.

2. **TASK-0030: Normalized EPS & Mid-Cycle Valuation (Mục 11.1):**
   - Thay thế EPS trailing 12 tháng bằng **Normalized EPS** (trung bình 5 năm có trimmed loại bỏ năm cao nhất và thấp nhất) cho toàn bộ archetype `CYCLICAL`:
     $$\text{Normalized\_EPS} = \text{TrimmedMean}_{5Y}(\text{EPS})$$
     $$\text{Normalized\_PE} = \frac{\text{Current Price}}{\text{Normalized\_EPS}}$$
   - Sử dụng $\text{Normalized\_PE}$ thay thế cho trailing P/E để xếp loại định giá thực chất và tính Fair Value cơ sở.
   - Bóc tách 3 lớp giá trị (Core Operations vs Event Windfall vs Future Capex).

3. **TASK-0031: Peer Comparison Benchmark — So Sánh Quốc Tế (Mục 11.2):**
   - Thiết lập bảng mỏ neo định giá so sánh theo ngành (Regional Peer Benchmark) cho nhóm Lọc hóa dầu (Asian Refineries: Trung vị P/B ~1.0x, P/E ~4.1x), Thép và Hóa chất:
     - Nếu $P/B_{\text{mã}} > \text{Peer\_Median} \times 2.0$:
       - **Khóa xếp hạng "HẤP DẪN" / "RẤT RẺ"**, cắm cờ `PEER_PREMIUM_EXTREME`.
     - Nếu $P/B_{\text{mã}} > \text{Peer\_Median} + 1\sigma$ (hoặc $> \text{Peer\_Median} \times 1.5$):
       - Bật cảnh báo `PEER_PREMIUM_WARNING`, chiết khấu Fair Value thêm $10\%$.

4. **TASK-0032: Sector-Specific Risk Flags cho Dầu khí & Thép (Mục 11.3):**
   - Bổ sung bộ kiểm tra rủi ro đặc thù ngành trong `data_gate.py`:
     - **Nhóm Dầu khí / Lọc dầu (BSR, PVD, PVS):**
       - `INVENTORY_RISK`: Số ngày tồn kho (DSI) $> 45$ ngày $\rightarrow$ Rủi ro trích lập giảm giá tồn kho khi giá dầu Brent giảm.
       - `MARGIN_TREND_DOWN`: Biên gộp giảm liên tiếp $\ge 2$ quý $\rightarrow$ Crack spread bị thu hẹp.
       - `POLICY_EXPIRING`: Ưu đãi thuế thu nhập hoặc thuế nhập khẩu sắp hết hạn.
       - `SINGLE_PLANT_RISK`: Phụ thuộc vào một cụm nhà máy duy nhất, bảo dưỡng/sự cố = mất doanh thu.
     - **Nhóm Thép (HPG, HSG, NKG):**
       - `CHINA_DUMPING_RISK`: Chênh lệch giá HRC nội địa vs Trung Quốc bị ép giảm.
       - `INVENTORY_BUILDUP`: Tồn kho thành phẩm tăng $> 20\%$ QoQ.

---

## 2. KẾ THỪA CÁC CHỐT CHẶN PHIÊN BẢN TRƯỚC (v6.1 - v7.0)

1. **Real Estate & Holding Valuation Overhaul (v7.0 - Phase 10):**
   - SOTP Sanity Check cho Holding Company (VIC, MSN, REE, GEX), Quality of Earnings Gate (Core Earnings Ratio), Survival Gate (Normalized EBITDA, Refinancing Risk, Interest Coverage) và P/B Mean Reversion Guardrail cho BĐS.
2. **System Rigor & De-risking (v6.4 - Phase 9):**
   - Kelly Hard-Cap $15\%$ NAV, Hysteresis $\ge 2$ phiên cho Regime Conflict, Drawdown Breaker cấp danh mục $10\%$.
3. **Context Engine & PTKT Hàng ngày (v6.3 - Phase 8):**
   - Trích xuất bối cảnh chuyên gia từ PDF TCBS vào `market_context.json`, Code MA200 luôn thắng nhận định chuyên gia.
4. **Hạ tầng Bằng chứng & Audit Idempotent (v6.1 - v6.2):**
   - Lưu vết 4 tầng FACT, INFERENCE, OPINION, COUNTERFACTUAL trong `decision_records`, Veto Only cho AI Committee.

---

## 3. NGUYÊN TẮC QUẢN TRỊ RỦI RO & BẢO TOÀN KIẾN TRÚC

- **Zero-Democracy Risk Gate:** Chu kỳ lợi nhuận hàng hóa biến động khôn lường; cấm dựa vào P/E trailing giá rẻ tại đỉnh chu kỳ để khuyến nghị tích sản.
- **Fail-Safe & Graceful Degradation:** Thiếu dữ liệu peer quốc tế hoặc lịch sử EPS 5 năm thì tự động fallback về logic định giá chu kỳ cơ bản, cắm cờ `DATA_PARTIAL_FALLBACK`, tuyệt đối không gây crash.
- **Single Source of Truth (SSOT):** Toàn bộ tham số định giá chu kỳ phát xuất từ `quant_valuation.py` và `data_gate.py`.

---

## 4. TIÊU CHUẨN KỸ THUẬT (QUALITY GATE)

- **SonarCloud:** Cognitive Complexity < 15 (S3776), `logging.exception()` trong except (S8572), không trùng lặp chuỗi $\ge 3$ lần (S1192), duplicate lines density $\le 3.0\%$.
- **Ruff:** `ruff check --fix .` đảm bảo exit code 0.
- **Test Coverage:** $\ge 80\%$ (mục tiêu $85 - 95\%+$) cho toàn bộ logic mới; 100% test case kiểm thử biên và fail-safe branch.