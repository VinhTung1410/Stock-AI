# QUY TẮC PHÁT TRIỂN & CHUẨN HÓA HỆ THỐNG STOCK AI ASSISTANT

Tài liệu này định nghĩa các quy tắc cốt lõi (Core Rules) bắt buộc áp dụng cho toàn bộ mã nguồn, trợ lý AI (Gemini Flash), hệ thống thông báo Discord và giao diện Streamlit trong dự án.

---

## 1. QUY TẮC NGÔN NGỮ & MÃ HÓA (STRICT LANGUAGE STANDARD)

### 1.1. Tiêu chuẩn 100% Tiếng Việt Chuẩn Unicode
- Toàn bộ nội dung báo cáo phân tích, nhận định thị trường, khuyến nghị và thông báo cảnh báo phải được trình bày bằng **100% tiếng Việt phổ thông chuẩn Unicode**.
- **NGHIÊM CẤM** sự xuất hiện của bất kỳ ký tự tiếng Trung / Hán tự (CJK Ideographs `[\u4e00-\u9fff]`) trong văn bản xuất bản (ví dụ các token lỗi hay gặp như `证券公司`, `股票`, `银行`, `风险`, `变动`...).

### 1.2. Chuẩn hóa tên mã cổ phiếu và công ty chứng khoán
- Với mã **SSI**: Luôn hiển thị là **`SSI`**, **`Mã SSI`** hoặc **`Công ty Chứng khoán SSI`** (hoặc `CTCK SSI`).
- **TUYỆT ĐỐI KHÔNG ĐƯỢC PHÉP** xuất hiện định dạng chắp vá như `证券公司 SSI`.
- Các công ty chứng khoán khác: Viết rõ `VND (VNDirect)`, `VCI (Vietcap)`, `HCM (HSC)`, v.v.

---

## 2. KIẾN TRÚC PHÒNG THỦ 2 LỚP (TWO-TIER DEFENSE ARCHITECTURE)

Để triệt tiêu hoàn toàn hiện tượng AI sinh nhầm ký tự tiếng Trung, hệ thống bắt buộc triển khai mô hình phòng thủ 2 lớp độc lập:

```
                  ┌──────────────────────────────────────────────┐
                  │              Input Prompt / Query            │
                  └──────────────────────┬───────────────────────┘
                                         ▼
┌────────────────────────────────────────────────────────────────────────────────┐
│ LỚP 1: SYSTEM LANGUAGE RULE (CHẶN TỪ GỐC KHI GỌI MODEL)                        │
│ • Gắn chỉ thị bắt buộc vào đầu và cuối prompt gửi tới Gemini API.             │
│ • Ràng buộc rõ vai trò trợ lý tài chính chứng khoán độc quyền tại Việt Nam.   │
└────────────────────────────────────────┬───────────────────────────────────────┘
                                         ▼
                               [ Gemini 3.5 Flash ]
                                         ▼
┌────────────────────────────────────────────────────────────────────────────────┐
│ LỚP 2: DETERMINISTIC SANITIZER (LƯỚI AN TOÀN TẤT ĐỊNH Ở TẦNG CODE)            │
│ • Hàm `sanitize_ai_text()` xử lý chuỗi trước khi trả về.                       │
│ • Tự động dịch các thuật ngữ tài chính tiếng Trung sang tiếng Việt chuẩn.      │
│ • Regex loại bỏ triệt để mọi ký tự trong dải Unicode CJK `[\u4e00-\u9fff]`.   │
└────────────────────────────────────────┬───────────────────────────────────────┘
                                         ▼
              ┌──────────────────────────────────────────────────────┐
              │ Output 100% Tiếng Việt sạch cho Discord & Web UI     │
              └──────────────────────────────────────────────────────┘
```

### 2.1. Lớp 1: Ép quy tắc vào System Prompt (`ai_analyst.py`)
Mọi yêu cầu gửi tới Gemini đều tự động được bao bọc bởi `SYSTEM_LANGUAGE_RULE` thông qua hàm tập trung `call_gemini(client, prompt)`:
```python
SYSTEM_LANGUAGE_RULE = """
[BẮT BUỘC - QUY TẮC NGÔN NGỮ TUYỆT ĐỐI]:
- BẮT BUỘC dùng 100% TIẾNG VIỆT CHUẨN UNICODE.
- NGHIÊM CẤM dùng bất kỳ ký tự chữ Hán / tiếng Trung nào (ví dụ: 证券公司, 股票, 银行, 风险, 变动...).
- Đối với mã SSI hoặc các CTCK khác: viết rõ 'Công ty Chứng khoán SSI' hoặc 'Chứng khoán SSI' hoặc 'Mã SSI', TUYỆT ĐỐI KHÔNG VIẾT '证券公司 SSI'.
"""
```

### 2.2. Lớp 2: Bộ lọc tất định ở tầng mã nguồn (`sanitize_ai_text`)
Kể cả khi mô hình AI có độ ngẫu nhiên xác suất, bộ lọc `sanitize_ai_text()` sẽ chặn lại ở tầng mã nguồn (Python):
1. **Từ điển thay thế tài chính:**
   - `证券公司` ➔ `Công ty Chứng khoán`
   - `证券` ➔ `Chứng khoán`
   - `股票` ➔ `Cổ phiếu`
   - `银行` ➔ `Ngân hàng`
   - `变动` ➔ `Biến động`
   - `风险` ➔ `Rủi ro`
   - `投资` ➔ `Đầu tư`
   - `买入` ➔ `Mua`
   - `卖出` ➔ `Bán`
2. **Quét Regex CJK triệt để:** `re.sub(r'[\u4e00-\u9fff]+', '', text)` đảm bảo không còn sót lại bất kỳ ký tự chữ Hán nào.

---

## 3. KIẾN TRÚC LƯỢNG HÓA HAI LƯỢT (QUANTAMENTAL 2-PASS PIPELINE)

Để giải quyết triệt để 2 vấn đề lớn nhất của AI tài chính: **Ảo giác số học** và **Bẫy đỉnh chu kỳ lợi nhuận**, hệ thống bắt buộc áp dụng nguyên lý:
> **"Python làm 100% việc tính toán số học tất định — LLM làm nhiệm vụ ngữ nghĩa, chất xúc tác và gán xác suất kịch bản".**

```
                       Yêu cầu phân tích cổ phiếu {symbol}
                                      │
                                      ▼
             ┌──────────────────────────────────────────────────┐
             │ BƯỚC 1: CỔNG KIỂM TRA DỮ LIỆU (DATA GATE)         │
             │ • ADV20 thanh khoản (≥ 3 - 5 tỷ VND / phiên)     │
             │ • Tính mới BCTC (trong vòng 2 quý gần nhất)       │
             └────────────────────────┬─────────────────────────┘
                   [ĐẠT]              │          [KHÔNG ĐẠT]
                                      │               │
                                      │               ▼
                                      │   "TỪ CHỐI KHUYẾN NGHỊ:
                                      │    DỮ LIỆU KHÔNG ĐẠT CHUẨN"
                                      ▼
             ┌──────────────────────────────────────────────────┐
             │ BƯỚC 2: PYTHON QUANT ENGINE                      │
             │ • Tính Piotroski F-Score (0-9)                   │
             │ • Tính Altman Z-Score (Vùng an toàn/xám/nguy cơ) │
             │ • Tính ATR(14) Stop-Loss & Giá trần/sàn HOSE     │
             │ • Tam giác định giá (P/E chu kỳ, P/B chuẩn hóa)  │
             └────────────────────────┬─────────────────────────┘
                                      │ (Nạp dữ liệu vào Prompt Lần 1)
                                      ▼
             ┌──────────────────────────────────────────────────┐
             │ BƯỚC 3: LƯỢT 1 (LLM GÁN XÁC SUẤT KỊCH BẢN)       │
             │ • LLM đọc dữ liệu định tính + chất xúc tác       │
             │ • Trả JSON: {P_bull, P_base, P_bear, rationale}  │
             └────────────────────────┬─────────────────────────┘
                                      │ (Trả JSON về Python)
                                      ▼
             ┌──────────────────────────────────────────────────┐
             │ BƯỚC 4: PYTHON HÀNG RÀO QUYẾT ĐỊNH (HARD GATES)  │
             │ • EV = P_bull*Price_bull + P_base*Price_base...  │
             │ • Margin of Safety (MoS %) = (EV - Price)/Price  │
             │ • Tỷ lệ Lãi/Lỗ R = Upside / Downside             │
             │ • Kelly Criterion f* = p - (1-p)/R               │
             │ • Áp hàng rào: MoS ≥ 15%, R ≥ 1.5, Kelly > 0     │
             └────────────────────────┬─────────────────────────┘
                                      │ (Nạp kết quả thép vào Prompt Lần 2)
                                      ▼
             ┌──────────────────────────────────────────────────┐
             │ BƯỚC 5: LƯỢT 2 (LLM VIẾT BÁO CÁO ĐỊNH CHẾ)       │
             │ • Báo cáo chuyên sâu 8 trụ cột chuẩn CFA         │
             │ • Giữ nguyên 100% con số Python đã tính          │
             │ • Xuất bản giao diện Web & Discord               │
             └──────────────────────────────────────────────────┘
```

### 3.1. Hàng rào quyết định định lượng cứng (Hard Gates)
Hệ thống **CẤM KHUYẾN NGHỊ MUA** nếu vi phạm bất kỳ tiêu chí nào sau đây:
1. **Biên an toàn (Margin of Safety - MoS):** Phải đạt $\ge 8\%$ (Bluechip) hoặc $\ge 15\%$ (Midcap). Nếu MoS âm $\to$ Bắt buộc chọn `🔴 BÁN / HẠ TỶ TRỌNG`.
2. **Tỷ lệ Lãi / Lỗ $R$ (Risk / Reward):** Phải đạt $R \ge 1.5$ (Lướt sóng T+) hoặc $R \ge 2.0$ (Trung hạn).
3. **Tiêu chuẩn Kelly Criterion ($f^*$):** Nếu $f^* \le 0$, tỷ lệ phân bổ vốn tối ưu là 0% $\to$ Không được mở vị thế mua mới.

---

## 4. TÍCH HỢP ĐỊNH LƯỢNG VÀO TRADING BOT

Đối với bot giám sát giao dịch thời gian thực (`trading_bot.py`):
1. **Stop-Loss động theo ATR(14):**
   - Thay vì chỉ dựa vào mốc cố định $-5\%$ hoặc $-7\%$, bot tính toán mức biến động ATR thực tế:
     $StopLoss_{ATR} = \max(\text{Giá vốn} \times 0.93, \text{Thị giá} - 2 \times ATR(14))$.
   - Đảm bảo cổ phiếu biến động mạnh không bị "rũ hàng" non, nhưng vẫn có chốt chặn an toàn $-7\%$ trần/sàn HOSE.
2. **Bộ lọc an toàn trước khi bắn tín hiệu Mua:**
   - Kiểm tra `Data Gate` và điểm `F-Score`: Nếu doanh nghiệp có dấu hiệu gian lận BCTC hoặc thanh khoản quá thấp, bot sẽ hủy bỏ cảnh báo mua để bảo vệ tài khoản.

---

## 5. QUY CHUẨN HIỂN THỊ ĐỊNH DẠNG (DISCORD & WEB UI)

### 5.1. Bắt buộc In đậm Mã Cổ phiếu (Stock Symbol Bolding)
- Mọi mã cổ phiếu (ví dụ: **SSI**, **BSR**, **MSB**, **HPG**, **MWG**, **FPT**, **VHM**...) **BẮT BUỘC PHẢI ĐƯỢC IN ĐẬM** (`**MÃ**`) trong toàn bộ các câu văn, tiêu đề và gạch đầu dòng.
- Giúp người đọc lướt qua tin nhắn Discord trên điện thoại có thể nhận diện ngay lập tức cổ phiếu nào đang được phân tích.

### 5.2. Hệ thống Huy hiệu Hành động Trực quan (Action Badges)
Mỗi khi đưa ra nhận định hoặc khuyến nghị với một mã cổ phiếu, bắt buộc gắn kèm nhãn huy hiệu chuẩn:
- 🟢 **`[MUA MỚI]`** hoặc 🟢 **`[MUA GOM]`**: Đạt cả 2 tiêu chí Xúc tác dòng tiền + Kỹ thuật vượt cản.
- 🔵 **`[NẮM GIỮ]`** hoặc 🔵 **`[GỒNG LÃI]`**: Giá nằm trên MA20, xu hướng dòng tiền khỏe.
- 🟡 **`[THEO DÕI]`** hoặc 🟡 **`[CHỜ ĐIỀU CHỈNH]`**: Đang tích lũy, chưa đủ điểm mua hoặc cần quan sát cung cầu.
- 🟠 **`[CHỐT LỜI]`** hoặc 🟠 **`[HẠ TỶ TRỌNG]`**: Chạm kháng cự, RSI quá mua, hiện thực hóa lợi nhuận từng phần.
- 🔴 **`[CẮT LỖ]`** hoặc 🔴 **`[BÁN DỨT KHOÁT]`**: Vi phạm ngưỡng dừng lỗ (-5%, -7%, gãy MA20 vol lớn).
- ⛔ **`[ĐỨNG NGOÀI / TRÁNH BẪY]`**: Có tin tức tốt nhưng kỹ thuật gãy nền, cấm bắt đáy.

### 5.3. Cấm Đánh số Thứ tự Liên tục cho Thuộc tính Cổ phiếu (No Continuous Numbering)
- **TUYỆT ĐỐI KHÔNG ĐÁNH SỐ** kiểu `1. Cổ phiếu A`, `2. Xúc tác`, `3. Vùng gom`, `4. Target`, `5. Dừng lỗ`, `6. Kỹ thuật`... gây rối mắt và làm hỏng phân cấp văn bản.
- **Bắt buộc phân cấp rõ ràng:**
  - Cấp 1 (Tên mã): Gạch đầu dòng tròn `• ` kèm tên mã in đậm và huy hiệu:
    `• Cổ phiếu **SSI** (Chứng khoán) — 🟢 **[MUA GOM]**`
  - Cấp 2 (Thuộc tính): Thụt lề 2 khoảng trắng với dấu gạch ngang `- `:
    `  - **Xúc tác:** Thu hút dòng tiền đón sóng thanh khoản.`
    `  - **Vùng gom:** 20.1 - 20.5k (Hiện tại: **20.3k**)`
    `  - **Mục tiêu:** 22.33k | **Dừng lỗ:** 19.55k | **R:R:** 2.7`
    `  - **Kỹ thuật:** Vận động tích lũy trên MA20, RSI đạt 60.2.`

### 5.4. Phân Tách Bạch 2 Phong Cách Giao Dịch (Lướt Sóng T+ vs Gom Hàng Vị Thế)
Để triệt tiêu hoàn toàn sự mập mờ trong khuyến nghị và sự sai lệch toán học của tỷ lệ Risk/Reward ($R:R$), hệ thống bắt buộc phân loại rõ ràng 2 phong cách:

1. ⚡ **Phong cách 1: LƯỚT SÓNG T+ / BREAKOUT SNIPER**
   - **Đặc điểm**: Đánh theo dòng tiền đầu cơ, nổ Vol bứt phá nền ngắn hạn.
   - **Huy hiệu**: ⚡ **`[LƯỚT SÓNG T+]`** hoặc 🚀 **`[BREAKOUT MUA MỚI]`**.
   - **Quy tắc Điểm vào (Entry Price)**: Biên độ cực hẹp $\le 3$ bước giá (tối đa $\pm 0.3\% - 0.5\%$). Mua dứt khoát 1 lần (Single Entry). Nếu giá vượt quá dải trên $\to$ **CẤM MUA ĐUỔI**.
   - **Quy tắc tính R:R**: Bắt buộc tính theo mức giá trần của điểm vào để phản ánh mức rủi ro khắt khe nhất.

2. 💎 **Phong cách 2: GOM HÀNG VỊ THẾ / TÍCH LŨY TRUNG HẠN**
   - **Đặc điểm**: Áp dụng cho cổ phiếu cơ bản nền tảng, vốn hóa lớn (**FPT**, **HPG**, **MWG**, **VHM**...).
   - **Huy hiệu**: 💎 **`[GOM HÀNG VỊ THẾ]`** hoặc 🟢 **`[MUA GOM TÍCH LŨY]`**.
   - **Dải gom giá (Accumulation Zone)**: Được phép mở rộng từ $1.5\% - 2.5\%$.
   - **Bắt buộc Lộ trình giải ngân 3 bước (Roadmap)**:
     - Bước 1 (Thăm dò 30%): Mua tại cạnh trên của dải gom.
     - Bước 2 (Gia tăng 40%): Mua khi giá nhúng rung lắc kiểm định MA20.
     - Bước 3 (Hoàn tất 30%): Mua tại hỗ trợ cứng đáy dải gom.
   - **Giá vốn bình quân mục tiêu (Expected Avg Cost)**: Bắt buộc tính toán rõ ràng mốc này.
   - **Quy tắc tính R:R**: Tỷ lệ $R:R$ bắt buộc tính dựa trên **Giá vốn bình quân mục tiêu**, triệt tiêu việc lấy bừa mốc đáy dải gom để làm đẹp số liệu.

### 5.5. Khắc phục giới hạn Discord Embed & Giao diện Web
1. **Khắc phục giới hạn Discord:**
   - TUYỆT ĐỐI KHÔNG dùng bảng Markdown (`|---|`) trong nội dung do AI sinh ra vì Discord không hỗ trợ hiển thị bảng và bị tràn ngang trên màn hình điện thoại.
   - Tách báo cáo thành từng Field có độ dài dưới 1024 ký tự (`split_ai_summary_into_fields()`).
   - Các phần cắt nhỏ của một mục dài phải được đặt tên là `(Phần 2)`, `(Phần 3)` thay vì nối chuỗi lặp `(tiếp theo)`.

2. **Giao diện Web Streamlit:**
   - Hiển thị theo thiết kế thẻ (Card Metric), huy hiệu màu sắc tương ứng với trạng thái khuyến nghị (Xanh: Mua, Vàng: Nắm giữ/Theo dõi, Đỏ: Bán/Cắt lỗ).
