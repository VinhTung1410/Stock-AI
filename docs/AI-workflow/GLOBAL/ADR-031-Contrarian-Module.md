# ADR-031: Contrarian Module (Panic Buy Engine v10.0)

*(Tài liệu này hợp nhất các quyết định kiến trúc từ ADR-0008, ADR-0009 và ADR-031 cũ)*

## 1. Trạng thái và Bối cảnh (Context)
- **Trạng thái:** Tương lai / Đã triển khai (v10.0)
- **Ngày:** 2026-10-02
- **Tác giả:** PO/Client & AI Architect
- **Bối cảnh:** Triết lý hiện tại của Bot là **"Chất lượng + Xác nhận xu hướng"** (chỉ mua khi giá trên MA20/MA50). Tuy nhiên, trong các đợt flash crash hoặc Bear Market, các blue-chips chất lượng rơi về vùng định giá cực rẻ (MoS > 20%) sẽ bị chặn tự động ở Tầng Kỹ thuật. Hệ quả là bot "im lặng" đúng vào thời điểm cần "Tham lam khi người khác sợ hãi".
- Hơn nữa, việc chỉ sử dụng "Oversold Detector" thô sơ (RSI <= 30) làm chốt chặn ban đầu sẽ gây ra 2 rủi ro:
  1. **Bẫy Giá Rẻ (Value Trap):** Bắt đáy các mã bị bán tháo do vỡ nợ hoặc kiểm toán ngoại trừ (ví dụ: NVL, DGC).
  2. **Mất Mát Ngữ Nghĩa (Semantic Loss):** Đánh đồng cổ phiếu rác với cổ phiếu siêu tốt đang giảm về sát ngưỡng hoảng loạn (ví dụ FPT ở mức RSI ~ 32). Hệ thống v9.0 trước đó chặn (Block) cả 2 mã này như nhau vì RSI chưa thủng 30.

## 2. Quyết định Kiến trúc (Decision)
Thay vì nới lỏng hệ thống Uptrend, chúng ta xây dựng **Contrarian Module (Panic Buy Engine)** hoàn toàn độc lập, áp dụng cơ chế **4-State Machine** (Máy 4 trạng thái) và **Continuous Panic Score**.

### 2.1. Đảo ngược trình tự đánh giá (Holistic Pipeline)
Hệ thống KHÔNG return `False` ngay khi RSI > 30. Trình tự đánh giá tuân thủ nguyên tắc "Chất lượng/Sinh tồn trước - Kỹ thuật sau":
1. **Gate 1: Governance & Event Risk:** Chặn (VETO) ngay lập tức nếu dính rủi ro pháp lý, thanh tra, kiểm toán ngoại trừ.
2. **Gate 2: Fundamental & Quality (Sinh tồn):** Đánh giá sức khỏe tài chính. Chặn nếu F-Score < 7, Z-Score <= 2.0, Debt/Equity > 1.0 (Trừ Bank), hoặc LNST đang lao dốc (Fundamental Damage).
3. **Gate 3: Valuation (Intrinsic MoS):** Yêu cầu MoS >= 20.0% (trong Uptrend/Sideways) hoặc >= 30.0% (trong Downtrend). KHÔNG dùng fallback valuation.
4. **Gate 4: Panic Assessment:** Tính điểm cường độ hoảng loạn (0-100) dựa trên RSI và độ lệch MA20.
5. **Gate 5: Price Confirmation:** Kiểm tra nến rút chân, phân kỳ dương (Chỉ cấp quyền mua khi thỏa mãn).

### 2.2. Ma trận 4 trạng thái (4-State Machine)
Mọi cổ phiếu lọt qua Gate 1, 2, 3 (TỐT và RẺ) sẽ được phân loại dựa trên Gate 4 & 5:
- 🟢 **NORMAL (Bỏ qua):** Cổ phiếu tốt, nhưng chưa có chiết khấu hoảng loạn (RSI > 35).
- 🟡 **NEAR_PANIC_WATCH (Radar săn mồi):** Cổ phiếu tốt, định giá cực rẻ, hoảng loạn mấp mé (30 < RSI <= 35). Đưa vào Watchlist đặc biệt.
- 🟠 **EXTREME_FEAR_WATCH (Chờ bắt đáy):** Hoảng loạn tột độ (RSI <= 30) nhưng chưa có xác nhận đáy (Dao đang rơi).
- 🚨 **PANIC_BUY (Kích hoạt lệnh):** Hoảng loạn tột độ (RSI <= 30) + Có xác nhận đảo chiều (Price Confirmation).

### 2.3. Cường độ hoảng loạn (Continuous Panic Score)
Tính liên tục từ 0-100 để đo lường độ dốc của pha rơi:
- **RSI Contribution (70%):** Giảm dần từ RSI 40 (0 điểm) -> 35 (25 điểm) -> 30 (75 điểm) -> <= 25 (100 điểm).
- **Price Deviation (30%):** Khoảng cách giá rớt sâu so với MA20.

### 2.4. Quản trị Rủi ro & Quy mô Vị thế (Sizing)
- **Rải đinh (Tranching):** Bắt đáy không bao giờ All-in. Giải ngân tối đa giới hạn ở **5% NAV**.
- **Kelly Penalty:** Giá trị tính toán từ Half-Kelly sẽ bị phạt chia đôi (`/ 2`) để giảm thiểu biến động danh mục nếu giá tiếp tục rơi.
- **Dynamic Stop-loss:** Stop-loss dựa vào Hỗ trợ tĩnh / MA200 hoặc Hard Stop-loss cố định (-8%), thay vì MA20.

## 3. Hệ quả (Consequences)
**Tích cực:**
- Triệt tiêu tối đa rủi ro rơi vào "bẫy giá rẻ" (Value Trap) và "bắt dao rơi".
- Tận dụng được các cơ hội chiết khấu hiếm có của siêu cổ phiếu (Vào Watchlist sớm thay vì bị âm thầm chặn).
- Giữ nguyên được sự trong sáng của hệ thống Trend-Following.

**Tiêu cực / Đánh đổi:**
- Bỏ lỡ đáy chữ V nếu thị trường giật ngược mà không tạo nến xác nhận.
- Đòi hỏi cập nhật `market_context.json` liên tục để nhận diện rủi ro sự kiện (Event Risk).

## 4. Tham chiếu (References)
- TASK-0070 (Phase 20 - v10.0 Roadmap)
- Phản hồi từ Client về Single Point of Failure của Layer 2 (v9.0).
