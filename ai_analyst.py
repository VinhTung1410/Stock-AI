import os
import json
import re
import logging
from dotenv import load_dotenv
from google import genai
from data_engine import load_portfolio, evaluate_portfolio, fetch_macro_news

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
MODEL_NAME = "gemini-3.5-flash-lite"  # Model tối ưu tốc độ, token và ổn định quota cao của Gemini

# ==============================================================================
# BỘ QUY TẮC & BỘ LỌC TẤT ĐỊNH TRIỆT TIÊU 100% CHỮ HÁN / TIẾNG TRUNG
# ==============================================================================
CHINESE_FINANCE_DICTIONARY = {
    "证券公司": "Công ty Chứng khoán",
    "证券": "Chứng khoán",
    "股票": "Cổ phiếu",
    "银行": "Ngân hàng",
    "变动": "Biến động",
    "风险": "Rủi ro",
    "投资": "Đầu tư",
    "市场": "Thị trường",
    "基金": "Quỹ",
    "交易": "Giao dịch",
    "买入": "Mua",
    "卖出": "Bán",
    "持有": "Nắm giữ",
    "止损": "Cắt lỗ",
    "目标价": "Giá mục tiêu",
}

SYSTEM_LANGUAGE_RULE = """
[BẮT BUỘC - QUY TẮC TRÌNH BÀY, ĐỊNH DẠNG & NGÔN NGỮ]:
1. 100% TIẾNG VIỆT CHUẨN UNICODE: Cấm chữ Hán/tiếng Trung. Với SSI viết rõ 'Công ty Chứng khoán SSI' hoặc 'Mã **SSI**'.
2. BẮT BUỘC IN ĐẬM TẤT CẢ MÃ CỔ PHIẾU: Mọi mã chứng khoán (như **SSI**, **BSR**, **MSB**, **HPG**, **MWG**, **FPT**, **VHM**...) PHẢI ĐƯỢC IN ĐẬM để đập vào mắt người đọc khi đọc lướt.
3. PHÂN TÁCH BẠCH 2 PHONG CÁCH GIAO DỊCH (LƯỚT SÓNG VS GOM HÀNG):
   - ⚡ **[LƯỚT SÓNG T+ / BREAKOUT]**: Điểm vào lệnh cực hẹp (tối đa ±0.3% - 0.5%, khoảng 2-3 bước giá). Mua dứt khoát 1 lần. Vượt quá dải này: CẤM MUA ĐUỔI. Tỷ lệ R:R tính theo giá vào trần.
   - 💎 **[GOM HÀNG VỊ THẾ / TRUNG HẠN]**: Áp dụng cho cổ phiếu cơ bản, vốn hóa lớn (FPT, HPG, MWG...). Vùng gom mở rộng (1.5% - 2.5%), nhưng BẮT BUỘC có lộ trình giải ngân chia 3 bước (30% - 40% - 30%) và nêu rõ "Giá vốn bình quân mục tiêu". Tỷ lệ R:R tính theo giá vốn bình quân này.
4. GẮN HUY HIỆU HÀNH ĐỘNG RÕ RÀNG:
   - ⚡ **[LƯỚT SÓNG T+]** hoặc 🚀 **[BREAKOUT MUA MỚI]**
   - 💎 **[GOM HÀNG VỊ THẾ]** hoặc 🟢 **[MUA GOM TÍCH LŨY]**
   - 🔵 **[NẮM GIỮ GỒNG LÃI]**
   - 🟡 **[THEO DÕI CHỜ MUA]**
   - 🟠 **[CHỐT LỜI TỪNG PHẦN]** hoặc 🟠 **[HẠ TỶ TRỌNG]**
   - 🔴 **[CẮT LỖ / BÁN DỨT KHOÁT]**
   - ⛔ **[ĐỨNG NGOÀI / TRÁNH BẪY]**
5. TUYỆT ĐỐI KHÔNG ĐÁNH SỐ THỨ TỰ LIÊN TỤC (1., 2., 3., 4., 5., 6., 7., 8...) CHO TỪNG DÒNG CHI TIẾT.
   - Tên mã là gạch đầu dòng cấp 1: `• Cổ phiếu **MÃ** (Ngành) — [HUY HIỆU]`
   - Các thuộc tính là gạch đầu dòng cấp 2 thụt lề `- **Thuộc tính:**`.
"""


def sanitize_ai_text(text: str) -> str:
    """
    Bộ lọc tất định (Deterministic Sanitizer):
    1. Triệt tiêu 100% mọi ký tự tiếng Trung / Hán tự.
    2. Tự động in đậm mọi mã cổ phiếu (3 ký tự in hoa đứng sau Cổ phiếu / Mã / CP).
    3. Xóa bỏ đánh số thứ tự liên tục (1., 2., 3., 4...) ở các dòng thuộc tính, chuyển thành gạch đầu dòng phân cấp.
    """
    if not text:
        return text

    # Bước 1: Thay thế các cụm từ tài chính tiếng Trung phổ biến sang tiếng Việt chuẩn
    for cn, vn in CHINESE_FINANCE_DICTIONARY.items():
        text = text.replace(cn, vn)

    # Bước 2: Quét dọn sạch mọi ký tự CJK (chữ Hán Unicode \u4e00-\u9fff) còn sót lại
    text = re.sub(r'[\u4e00-\u9fff]+', '', text)

    # Bước 3: Chuẩn hóa các dòng thuộc tính bị AI đánh số liên tục (ví dụ: 4. Câu chuyện xúc tác, 5. Vùng giá gom...)
    attr_pattern = r'^\s*\d+\.\s*(Câu chuyện xúc tác|Luận điểm cơ bản|Vùng giá gom|Giá mục tiêu|Ngưỡng dừng lỗ|Trạng thái kỹ thuật|Xúc tác|Mục tiêu|Cắt lỗ|Kỹ thuật)[^:]*:\s*'
    text = re.sub(attr_pattern, r'  - **\1:** ', text, flags=re.MULTILINE)

    # Bước 4: Chuẩn hóa dòng tiêu đề mã bị đánh số (ví dụ: 1. Cổ phiếu BSR, 3. Cổ phiếu SSI) thành bullet point cấp 1
    code_pattern = r'^\s*\d+\.\s*(Cổ phiếu|Mã)\s+'
    text = re.sub(code_pattern, r'• \1 ', text, flags=re.MULTILINE)

    # Bước 5: Đảm bảo in đậm các mã cổ phiếu đứng sau Cổ phiếu / Mã / CP nếu AI quên in đậm
    text = re.sub(r'\b(Cổ phiếu|cổ phiếu|Mã|mã|CP|cp)\s+([A-Z0-9]{3})\b', r'\1 **\2**', text)
    # Loại bỏ double asterisks nếu có (ví dụ ****SSI**** -> **SSI**)
    text = text.replace('****', '**')

    # Bước 6: Chuẩn hóa khoảng trắng
    text = re.sub(r'[ \t]+', ' ', text)
    return text.strip()


def call_gemini(client, prompt: str) -> str:
    """
    Gọi Gemini API với System Language Rule tích hợp sẵn ở cả đầu và cuối prompt,
    sau đó tự động lọc qua sanitize_ai_text để đảm bảo đầu ra sạch 100%.
    """
    full_prompt = f"{SYSTEM_LANGUAGE_RULE}\n\n{prompt}\n\n{SYSTEM_LANGUAGE_RULE}"
    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=full_prompt
    )
    return sanitize_ai_text(response.text)


def get_ai_client():
    if not GEMINI_API_KEY:
        raise ValueError("Chưa cấu hình GEMINI_API_KEY trong file .env!")
    return genai.Client(api_key=GEMINI_API_KEY)


def generate_portfolio_analysis(portfolio_df, news_items, watchlist_df=None, custom_question: str = None) -> str:
    """
    Tạo báo cáo phân tích toàn diện kết hợp Danh mục, Chỉ báo Kỹ thuật và Tin tức Vĩ mô chuyên sâu CafeF.
    """
    client = get_ai_client()

    portfolio_str = portfolio_df.to_string(index=False) if portfolio_df is not None and not portfolio_df.empty else "Chưa có mã nào trong danh mục."
    watchlist_str = watchlist_df.to_string(index=False) if watchlist_df is not None and not watchlist_df.empty else ""

    news_lines = []
    for n in news_items[:8]:
        tag = n.get("tag", n.get("keyword", "TIN TỨC")).upper()
        line = f"- [{tag}] {n['title']}"
        if n.get("summary"):
            line += f" | Tóm tắt: {n['summary'][:160]}..."
        if n.get("matched_symbols"):
            line += f" | 🔥 Trực tiếp tác động: {', '.join(n['matched_symbols'])}"
        news_lines.append(line)
    news_str = "\n".join(news_lines) if news_lines else "Không có tin tức mới."

    prompt = f"""Bạn là Chuyên gia Trưởng Ban Chiến lược Đầu tư Chứng khoán với hơn 15 năm kinh nghiệm thực chiến tại thị trường Việt Nam (HSX, HNX).
Dưới đây là dữ liệu giao dịch và trạng thái danh mục thực tế của Nhà đầu tư:

=== BẢNG TRẠNG THÁI DANH MỤC HIỆN TẠI (HOLDINGS) ===
{portfolio_str}
"""
    if watchlist_str:
        prompt += f"""
=== DANH SÁCH CỔ PHIẾU ĐANG THEO DÕI (WATCHLIST) ===
{watchlist_str}
"""

    prompt += f"""
=== TIN TỨC TÀI CHÍNH & DOANH NGHIỆP MỚI NHẤT (NGUỒN CAFEF CHUYÊN SÂU) ===
{news_str}

Nhiệm vụ của bạn:
1. **Đánh giá sức khỏe danh mục:** 
   - Với mỗi mã đang nắm giữ, BẮT BUỘC in đậm mã và gắn huy hiệu hành động nổi bật ngay đầu dòng:
     • Cổ phiếu **BSR** (Dầu khí) — 🔵 **[NẮM GIỮ GỒNG LÃI]**: ...
     • Cổ phiếu **MSB** (Ngân hàng) — 🟠 **[CHỐT LỜI TỪNG PHẦN]**: ...
     • Cổ phiếu **SSI** (Chứng khoán) — 🟡 **[THEO DÕI QUẢN TRỊ RỦI RO]**: ...
2. **Tác động Tin vĩ mô & Doanh nghiệp:** Tin tức CafeF vừa cập nhật (cổ tức, KQKD, giao dịch nội bộ, chính sách) đang tạo động lực hay áp lực lên danh mục? In đậm tất cả mã cổ phiếu được nhắc đến (**FPT**, **HPG**, **SSI**...).
3. **Kịch bản hành động cụ thể (Rõ ràng từng mốc):**
   - Trình bày theo từng mã với huy hiệu hành động:
     • Đối với mã **[MÃ]** — [HUY HIỆU HÀNH ĐỘNG]:
       > **Ngắn hạn (T+):** Điểm chốt lời / Điểm quản trị rủi ro...
       > **Trung hạn (3-6 tháng):** Chiến lược tích lũy / hạ bớt...
4. **Cổ phiếu / Ngành đón sóng tiềm năng (Phân tách rõ 2 phong cách):**
   - Nhận định về các mã trong Watchlist (**FPT**, **HPG**, **MWG**...) hoặc cơ hội mới:
     + Nếu là Lướt sóng T+: Gắn huy hiệu ⚡ **[LƯỚT SÓNG T+]**, cho điểm vào lệnh hẹp (±0.3k - 0.5k), cấm mua đuổi, tính R:R theo điểm vào cao nhất.
     + Nếu là Gom hàng vị thế (FPT, HPG, MWG...): Gắn huy hiệu 💎 **[GOM HÀNG VỊ THẾ]**, dải gom 1.5% - 2.5%, BẮT BUỘC nêu kế hoạch giải ngân chia 3 bước (30% - 40% - 30%), xác định Giá vốn BQ dự kiến và tính R:R theo giá vốn này.
     + Nếu chưa đạt chuẩn kỹ thuật: Gắn huy hiệu 🟡 **[THEO DÕI CHỜ MUA]** hoặc ⛔ **[ĐỨNG NGOÀI / TRÁNH BẪY]**.

Yêu cầu định dạng đặc biệt cho Discord & Web:
- TUYỆT ĐỐI KHÔNG DÙNG BẢNG MARKDOWN (| Cột | Cột |).
- TUYỆT ĐỐI KHÔNG DÙNG DẤU `###`.
- BẮT BUỘC IN ĐẬM TẤT CẢ MÃ CỔ PHIẾU (**SSI**, **BSR**, **MSB**, **HPG**, **MWG**, **FPT**...).
- TUYỆT ĐỐI KHÔNG ĐÁNH SỐ THỨ TỰ LIÊN TỤC (1., 2., 3., 4., 5...). Dùng bullet point dạng `• ` hoặc `> ` kèm emoji.
- Chia rõ ràng 4 mục lớn:
  **I. ĐÁNH GIÁ SỨC KHỎE DANH MỤC**
  **II. TÁC ĐỘNG VĨ MÔ & DÒNG TIỀN**
  **III. KỊCH BẢN & CHIẾN LƯỢC HÀNH ĐỘNG**
  **IV. CỔ PHIẾU / NGÀNH ĐÓN SÓNG TIỀM NĂNG**
"""

    if custom_question:
        prompt += f"\n\n[CÂU HỎI BỔ SUNG CỦA NHÀ ĐẦU TƯ]: {custom_question}\nHãy trả lời chi tiết trọng tâm câu hỏi này."

    return call_gemini(client, prompt)


def generate_morning_strategy_report(portfolio_df, watchlist_df, opportunities: list, news_items: list, vnindex_tech: dict = None) -> str:
    """
    🎯 BÁO CÁO CHIẾN LƯỢC ĐẦU NGÀY 08:45 (PHONG CÁCH CTCK CHUYÊN NGHIỆP SSI / TCBS):
    Tập hợp số liệu VN-Index thực tế + Điểm tin CafeF đêm qua + Chiến lược danh mục + Top cơ hội tiềm năng.
    """
    client = get_ai_client()

    # Kéo số liệu VN-Index thực tế nếu chưa được truyền vào
    if not vnindex_tech:
        try:
            from data_engine import fetch_stock_technical
            vnindex_tech = fetch_stock_technical("VNINDEX")
        except:
            vnindex_tech = {}

    idx_price = vnindex_tech.get("current_price", 0.0)
    idx_chg = vnindex_tech.get("change_pct", 0.0)
    idx_ma20 = vnindex_tech.get("ma20", 0.0)
    idx_ma50 = vnindex_tech.get("ma50", 0.0)
    idx_rsi = vnindex_tech.get("rsi14", 0.0)
    idx_status = vnindex_tech.get("status_ma20", "")

    p_str = portfolio_df.to_string(index=False) if portfolio_df is not None and not portfolio_df.empty else "Chưa có mã nắm giữ."
    w_str = watchlist_df.to_string(index=False) if watchlist_df is not None and not watchlist_df.empty else "Chưa có mã trong Watchlist."

    idx_context = f"""=== 0. DỮ LIỆU THỰC TẾ CHỈ SỐ VN-INDEX (CẬP NHẬT TỨC THỜI) ===
- Điểm số đóng cửa phiên gần nhất: {idx_price:.2f} điểm (Thay đổi: {idx_chg:+.2f}%)
- Đường MA20 ngày: {idx_ma20:.2f} điểm (Trạng thái: {idx_status})
- Đường MA50 ngày: {idx_ma50:.2f} điểm
- Chỉ số sức mạnh tương đối RSI(14): {idx_rsi}
(QUAN TRỌNG: Bạn PHẢI dùng các mốc số liệu thực tế này ({idx_price:.2f}, MA20={idx_ma20:.2f}, MA50={idx_ma50:.2f}) để phân tích vùng hỗ trợ / kháng cự phiên hôm nay. TUYỆT ĐỐI KHÔNG BỊA RA HOẶC DÙNG MỐC 1.250 - 1.280 CỦA CÁC NĂM CŨ!)
"""

    buy_lines = []
    caution_lines = []
    for o in opportunities:
        if o.get("status") == "RECOMMEND_BUY":
            buy_lines.append(
                f"• Mã: {o['symbol']} ({o.get('sector', 'Niêm yết')}) | Phong cách: {o.get('style_type')} | Setup: {o.get('setup_type')} | "
                f"Thị giá: {o['current_price']}k | Vùng vào lệnh: {o.get('entry_zone')}k | Giá vốn BQ dự kiến: {o.get('avg_cost')}k | Target: {o.get('target_price')}k | Cutloss: {o.get('stop_loss')}k | R:R: {o.get('risk_reward')} | "
                f"Kế hoạch giải ngân: {o.get('execution_plan')} | Xúc tác: [{o.get('story_tag')}] {o.get('story')}"
            )
        elif o.get("status") == "CAUTION_TRAP":
            caution_lines.append(
                f"• Mã: {o['symbol']} ({o.get('sector', 'Niêm yết')}) | Thị giá: {o['current_price']}k | "
                f"Xúc tác: [{o.get('story_tag')}] {o.get('story')} | Cảnh báo: {o.get('rationale')}"
            )

    buy_str = "\n".join(buy_lines) if buy_lines else "Chưa có mã nào thỏa mãn đồng thời cả 2 điều kiện Xúc tác + Kỹ thuật."
    caution_str = "\n".join(caution_lines) if caution_lines else "Không có cổ phiếu nào rơi vào diện cảnh báo bẫy tin."

    news_lines = []
    for n in news_items[:6]:
        news_lines.append(f"- [{n.get('tag', 'TIN').upper()}] {n['title']}")
    news_str = "\n".join(news_lines)

    prompt = f"""Bạn là Giám đốc Chiến lược Đầu tư tại Công ty Chứng khoán hàng đầu (chuẩn mực như SSI Research, TCBS).
Bây giờ là 08:45 SÁNG - chuẩn bị bước vào phiên giao dịch ATO của thị trường chứng khoán Việt Nam.
Hãy xuất bản bản tin "CHIẾN LƯỢC PHIÊN HÔM NAY & KHUYẾN NGHỊ ĐẦU NGÀY":

{idx_context}

=== 1. DANH MỤC HIỆN TẠI CỦA KHÁCH HÀNG ===
{p_str}

=== 2. DANH SÁCH THEO DÕI (WATCHLIST) ===
{w_str}

=== 3. CỔ PHIẾU ĐỦ ĐIỀU KIỆN 'CÂU CHUYỆN XÚC TÁC + KỸ THUẬT CHO PHÉP' ===
{buy_str}

=== 4. CẢNH BÁO BẪY TIN TỨC (CÓ TIN/THEO DÕI NHƯNG KỸ THUẬT CHƯA CHO PHÉP) ===
{caution_str}

=== 5. ĐIỂM TIN NÓNG CAFEF SÁNG NAY ===
{news_str}

Yêu cầu xuất bản & Trình bày:
1. **Định hướng thị trường phiên hôm nay:** Nhận định nhanh tâm lý mở phiên ATO, dựa sát vào điểm số VN-Index ({idx_price:.2f}) và các mốc hỗ trợ MA20 ({idx_ma20:.2f})/kháng cự thực tế.
2. **Kế hoạch cho danh mục hiện tại:** 
   - Với mỗi mã, BẮT BUỘC in đậm mã và gắn huy hiệu hành động nổi bật ngay đầu dòng (ví dụ: `• Cổ phiếu **BSR** (Lọc hóa dầu) — 🔵 **[NẮM GIỮ GỒNG LÃI]**: ...`, `• Cổ phiếu **MSB** (Ngân hàng) — 🟠 **[CHỐT LỜI TỪNG PHẦN]**: ...`, `• Cổ phiếu **SSI** (Chứng khoán) — 🟡 **[THEO DÕI QUẢN TRỊ RỦI RO]**: ...`).
3. **🎯 TOP CỔ PHIẾU KHUYẾN NGHỊ MUA (PHÂN TÁCH RÕ 2 PHONG CÁCH):**
   - TUYỆT ĐỐI KHÔNG ĐÁNH SỐ THỨ TỰ (1., 2., 3., 4., 5., 6...) CHO CÁC DÒNG THUỘC TÍNH.
   - Nhận diện đúng phong cách từ dữ liệu mục 3 để trình bày:
     
     *Nếu là LƯỚT SÓNG T+ (Breakout / Sóng ngắn):*
     • Cổ phiếu **[MÃ]** ([Ngành]) — ⚡ **[LƯỚT SÓNG T+]**
       - **Xúc tác:** [...]
       - **Điểm vào lệnh (Sniper):** [...] k (Vùng [...] k - Mua dứt khoát quanh giá này, vượt giá trần dải KHÔNG mua đuổi)
       - **Giá mục tiêu:** [...] k | **Dừng lỗ:** [...] k | **R:R:** [...] (tính theo giá vào trần)
       - **Kỹ thuật & Dòng tiền:** [...]
     
     *Nếu là GOM HÀNG VỊ THẾ (Tích lũy nền / Cổ phiếu cơ bản lớn như FPT, HPG, MWG):*
     • Cổ phiếu **[MÃ]** ([Ngành]) — 💎 **[GOM HÀNG VỊ THẾ]**
       - **Xúc tác & Luận điểm:** [...]
       - **Dải gom giá:** [...] k | **Giá vốn BQ dự kiến:** [...] k
       - **Kế hoạch giải ngân 3 bước:** [...] (30% thăm dò, 40% rung lắc, 30% hỗ trợ)
       - **Giá mục tiêu:** [...] k | **Dừng lỗ:** [...] k | **R:R chuẩn:** [...] (tính theo giá vốn BQ)
       - **Kỹ thuật & Dòng tiền:** [...]
4. **⚠️ CẢNH BÁO BẪY TIN TỨC & QUẢN TRỊ RỦI RO:**
   - Trình bày dạng:
     • Cổ phiếu **[MÃ]** ([Ngành]) — ⛔ **[ĐỨNG NGOÀI / TRÁNH BẪY]**: [Lý do kỹ thuật chưa đạt...]

Định dạng Discord/Web:
- KHÔNG dùng bảng markdown (|---|).
- KHÔNG dùng dấu `###`.
- BẮT BUỘC IN ĐẬM TẤT CẢ MÃ CỔ PHIẾU (**SSI**, **BSR**, **MSB**, **HPG**, **MWG**...).
- Tiêu đề in đậm: `**I. NHẬN ĐỊNH ĐẦU PHIÊN ATO**`, `**II. HÀNH ĐỘNG VỚI DANH MỤC HIỆN TẠI**`, `**III. 🎯 TOP CỔ PHIẾU KHUYẾN NGHỊ MUA**`, `**IV. ⚠️ CẢNH BÁO TRÁNH BẪY TIN TỨC**`.
"""
    return call_gemini(client, prompt)


def generate_market_risk_scenarios(vnindex_df, news_items) -> str:
    """
    Vẽ 3-4 kịch bản rủi ro thị trường (Lạc quan, Trung lập, Bi quan, Thiên nga đen),
    chiến lược thực hiện phân bổ vốn, và dự đoán chu kỳ sóng Elliott / Wyckoff.
    """
    client = get_ai_client()

    idx_summary = "Không có dữ liệu VNINDEX"
    if vnindex_df is not None and not vnindex_df.empty:
        latest = vnindex_df.iloc[-1]
        prev = vnindex_df.iloc[-2] if len(vnindex_df) > 1 else latest
        c = float(latest["close"])
        p_c = float(prev["close"])
        chg = ((c - p_c) / p_c) * 100
        vol = int(latest.get("volume", 0))
        pe = latest.get("PE", "N/A")
        pb = latest.get("PB", "N/A")
        idx_summary = (
            f"VN-Index hiện tại: {c:.2f} điểm (Thay đổi: {chg:+.2f}%)\n"
            f"Khối lượng phiên gần nhất: {vol:,} CP\n"
            f"P/E thị trường: {pe} | P/B thị trường: {pb}\n"
            f"Thời điểm: {latest.get('time', '')}"
        )

    if news_items:
        news_str = "\n".join([
            f"- [{n.get('tag', n.get('keyword', 'TIN TỨC')).upper()}] {n.get('title', '')}" 
            for n in news_items[:8]
        ])
    else:
        news_str = "Không có tin tức vĩ mô mới trong 24h qua."

    prompt = f"""Hãy đóng vai trò là Giám đốc Quản trị Rủi ro & Chiến lược Vĩ mô cấp cao (Chief Risk Officer & Macro Strategist) tại một định chế tài chính lớn tại Việt Nam.

Dưới đây là bức tranh dữ liệu thị trường và tin tức mới nhất:

=== DỮ LIỆU CHỈ SỐ VN-INDEX ===
{idx_summary}

=== BỐI CẢNH VĨ MÔ & DÒNG TIỀN (24H QUA) ===
{news_str}

Nhiệm vụ của bạn là xây dựng Ma trận Kịch bản Rủi ro Thị trường toàn diện gồm các nội dung cốt lõi:

**I. ĐỊNH VỊ CHU KỲ SÓNG & TÂM LÝ THỊ TRƯỜNG**
- **Chu kỳ Wyckoff:** Thị trường đang nằm ở pha nào? (Tích lũy - Accumulation, Đẩy giá - Markup, Phân phối - Distribution, hay Đè giá - Markdown)? Dấu hiệu dòng tiền Smart Money (Big Boys).
- **Dự báo cấu trúc sóng Elliott:** VN-Index đang vận động ở nhịp sóng nào (Sóng đẩy 1, 3, 5 hay sóng điều chỉnh A-B-C)? Khung thời gian ngắn và trung hạn.

**II. 3 - 4 KỊCH BẢN THỊ TRƯỜNG TOÀN DIỆN**
Vẽ chi tiết 4 kịch bản từ tích cực đến cực đoan:
1. **Kịch bản 1: Lạc quan / Bứt phá (Bullish Breakout)**
   - Xác suất xảy ra (%):
   - Điều kiện kích hoạt (Vùng điểm bứt phá, Thanh khoản tối thiểu, Động thái khối ngoại):
   - Vùng mục tiêu (Target Index):
   - Tỷ lệ phân bổ khuyến nghị (% Cổ phiếu / % Tiền mặt / Margin):
   - Kế hoạch hành động cụ thể:

2. **Kịch bản 2: Cơ sở / Tích lũy giằng co (Base Case - Sideway Accumulation)**
   - Xác suất xảy ra (%):
   - Điều kiện kích hoạt (Biên độ dao động Box sideway, Thanh khoản trung bình):
   - Vùng chặn trên và chặn dưới:
   - Tỷ lệ phân bổ khuyến nghị (% Cổ phiếu / % Tiền mặt):
   - Chiến lược giao dịch ngắn hạn phù hợp (Trading range):

3. **Kịch bản 3: Bi quan / Điều chỉnh sâu (Bearish Correction)**
   - Xác suất xảy ra (%):
   - Điều kiện kích hoạt (Thủng hỗ trợ then chốt nào, Áp lực vĩ mô):
   - Vùng hỗ trợ cứng đón dòng tiền bắt đáy:
   - Ngưỡng quản trị rủi ro / Hạ tỷ trọng bắt buộc:
   - Tỷ lệ phân bổ vốn phòng thủ:

4. **Kịch bản 4: Cực đoan / Rủi ro Thiên nga đen (Black Swan Stress-Test)**
   - Xác suất xảy ra (%):
   - Yếu tố rủi ro tiềm ẩn (Cú sốc tỷ giá, địa chính trị, thanh khoản liên ngân hàng...):
   - Mức giảm tối đa dự phóng (Max Drawdown):
   - Hành động kích hoạt chế độ sinh tồn (Capital Preservation Mode):

**III. HƯỚNG DẪN THỰC THI & NGUYÊN TẮC KỶ LUẬT VỐN**
- Tỷ lệ tiền mặt / cổ phiếu tối ưu ngay lúc này.
- Bộ 3 nguyên tắc kỷ luật lệnh để bảo vệ tài khoản trước các biến số bất ngờ.

Yêu cầu định dạng:
- Trình bày mạch lạc, số liệu cụ thể, không nói chung chung.
- Dùng bullet point dạng `• ` hoặc `> ` kèm emoji.
- Không dùng bảng Markdown (| Cột |) để tương thích Discord và giao diện web mobile."""

    return call_gemini(client, prompt)


def generate_institutional_stock_report(symbol: str, financial_info: dict, tech_dict: dict, news_items: list) -> str:
    """
    Báo cáo phân tích chuyên sâu định chế 8 trụ cột chuẩn CFA kết hợp Quản trị rủi ro cấp Quỹ:
    - Ứng dụng cấu trúc thẻ XML chuẩn hóa (<ROLE>, <DATA_DICTIONARY>, <CONTEXT>, <CONSTRAINTS>, <DECISION_GUARDRAILS>, <OUTPUT_FORMAT>).
    - Tính toán trước các chỉ số kỹ thuật & rủi ro tham chiếu ở tầng Python (Deterministic Math).
    - Tích hợp khái niệm Thesis Breaker, Cảnh báo bẫy đỉnh chu kỳ, và Quyền ưu tiên '⛔ KHÔNG HÀNH ĐỘNG'.
    """
    client = get_ai_client()

    current_price = tech_dict.get("current_price") or 0.0
    change_pct = tech_dict.get("change_pct", 0.0)
    ma20 = tech_dict.get("ma20")
    ma50 = tech_dict.get("ma50")
    rsi14 = tech_dict.get("rsi14", "N/A")
    vol = tech_dict.get("volume", 0)
    vol_ratio = tech_dict.get("vol_ratio", 1.0)
    status_ma20 = tech_dict.get("status_ma20", "N/A")

    # --- TÍNH TOÁN THAM CHIẾU PYTHON (PRE-COMPUTED BENCHMARKS) ---
    # Ước tính ngưỡng cắt lỗ kỹ thuật an toàn (dưới MA20 hoặc -5% đến -7% thị giá)
    if ma20 and current_price >= ma20:
        stop_loss_ref = round(min(ma20 * 0.97, current_price * 0.94), 2)
    else:
        stop_loss_ref = round(current_price * 0.93, 2) if current_price > 0 else 0.0

    downside_pct = round(((current_price - stop_loss_ref) / current_price) * 100, 1) if current_price > 0 else 7.0

    # Trích xuất dữ liệu Khối ngoại, Bẫy tin tức và Thanh khoản ADV20
    foreign_flow = tech_dict.get("foreign_flow", {})
    if foreign_flow:
        foreign_summary = f"- Giao dịch Khối ngoại: Mua {foreign_flow.get('buy_val_bil', 0):.1f} tỷ | Bán {foreign_flow.get('sell_val_bil', 0):.1f} tỷ | Ròng {foreign_flow.get('net_val_bil', 0):+.1f} tỷ ({foreign_flow.get('status_vi', 'N/A')})"
    else:
        foreign_summary = "- Giao dịch Khối ngoại: Chưa có dữ liệu phiên hôm nay."

    trap_info = tech_dict.get("trap_info", {})
    if trap_info.get("is_trap"):
        trap_summary = f"- Cảnh báo bẫy giá / tin tức: ⚠️ {trap_info.get('warning_msg')}"
    else:
        trap_summary = "- Cảnh báo bẫy giá / tin tức: ✅ Không phát hiện tín hiệu bẫy nguy hiểm."

    adv20_bil = tech_dict.get("adv20_billion", 0.0)
    adv_summary = f"- Giá trị GD trung bình 20 phiên (ADV20): {adv20_bil:.2f} tỷ VND/phiên" if adv20_bil > 0 else ""

    tech_summary = (
        f"Mã CP: {symbol}\n"
        f"- Thị giá: {current_price} k VND (Phiên gần nhất: {change_pct:+.2f}%)\n"
        f"- MA20 ngày: {ma20} k VND (Vị thế: {status_ma20})\n"
        f"- MA50 ngày: {ma50} k VND\n"
        f"- RSI (14): {rsi14}\n"
        f"- Khối lượng giao dịch: {vol:,} CP | Vol / SMA20: {vol_ratio}x\n"
        f"{adv_summary}\n"
        f"{foreign_summary}\n"
        f"{trap_summary}\n"
        f"- Ngưỡng cắt lỗ tham chiếu kỹ thuật: {stop_loss_ref} k VND (Mức rủi ro downside: -{downside_pct}%)\n"
    )

    fin_summary = f"Kỳ báo cáo tài chính gần nhất: {financial_info.get('period', 'N/A')}\n"
    for k, label in [
        ("pe", "P/E"), ("pb", "P/B"), ("ps", "P/S"), ("ev_ebitda", "EV/EBITDA"),
        ("p_cf", "Giá / Dòng tiền"), ("roe", "ROE (%)"), ("roa", "ROA (%)"),
        ("roic", "ROIC (%)"), ("debt_equity", "Nợ / Vốn chủ sở hữu"),
        ("financial_leverage", "Đòn bẩy tài chính"), ("gross_margin", "Biên LN gộp (%)"),
        ("net_margin", "Biên LN ròng (%)"), ("current_ratio", "Thanh toán hiện hành"),
        ("quick_ratio", "Thanh toán nhanh"), ("market_cap_bil", "Vốn hóa (Tỷ VND)"),
        ("dividend_yield", "Tỷ suất cổ tức (%)")
    ]:
        v = financial_info.get(k)
        fin_summary += f"- {label}: {v if v is not None else 'N/A'}\n"

    news_lines = [f"- [{n.get('tag', n.get('keyword', 'TIN')).upper()}] {n.get('title', '')}" for n in (news_items or [])[:6]]
    news_str = "\n".join(news_lines) if news_lines else "Không có tin tức đột biến trong 7-14 ngày qua."

    prompt = f"""<ROLE>
Bạn là Giám đốc Phân tích Đầu tư cấp cao (Senior Equity Research Director / CFA Charterholder) kiêm Portfolio Manager tại một quỹ đầu tư hàng đầu tại Việt Nam. Khẩu vị của bạn là khách quan, sắc bén, dựa trên dữ liệu thật (data-driven), tuyệt đối không cảm tính.
Bạn sẽ điều phối một màn Tranh biện Đối kháng (Adversarial Debate) quyết liệt giữa Phe Bò (Bull Thesis) và Phe Gấu (Bear CRO Audit) trước khi đưa ra phán quyết kỷ luật.
</ROLE>

<DATA_DICTIONARY>
- Thị giá (k VND): 1k = 1.000 VND.
- Vol / SMA20: > 1.3x là dòng tiền nổ Vol; < 0.8x là thanh khoản cạn kiệt.
- Vị thế MA20: Nằm trên là Uptrend ngắn hạn; Nằm dưới là điều chỉnh/cần thận trọng.
- Khối ngoại: Mua/Bán ròng phản ánh sự ủng hộ hoặc xả hàng của dòng tiền tổ chức quốc tế.
- Bẫy tin tức: Tình huống ra tin tốt nhưng giá quá mua (RSI > 70) hoặc nến cụt đầu phân phối kéo xả.
- P/E & P/B: Chỉ số định giá bội số. CẢNH BÁO BẪY CHU KỲ: Với cổ phiếu chu kỳ (Thép, Hóa chất, Dầu khí...), P/E thấp nhất thường xuất hiện ở ĐỈNH chu kỳ lợi nhuận chứ không phải cổ phiếu rẻ.
- F-Score (Piotroski): Thang 9 điểm. 7-9 là Doanh nghiệp siêu khỏe; 0-3 là Rủi ro gian lận/suy kiệt tài chính.
- Z-Score (Altman): Đo lường nguy cơ phá sản. > 2.99 là Vùng an toàn; < 1.81 là Vùng báo động đỏ.
</DATA_DICTIONARY>

<CONTEXT>
Cổ phiếu mục tiêu: **{symbol}**

--- 1. TÍN HIỆU KỸ THUẬT, THANH KHOẢN & DÒNG TIỀN (THỰC TẾ) ---
{tech_summary}

--- 2. NỀN TẢNG TÀI CHÍNH & ĐỊNH GIÁ (BCTC) ---
{fin_summary}

--- 3. TIN TỨC VĨ MÔ & DOANH NGHIỆP LIÊN QUAN ---
{news_str}
</CONTEXT>

<CONSTRAINTS>
1. TUYỆT ĐỐI DÙNG 100% TIẾNG VIỆT CHUẨN UNICODE. Cấm chữ tiếng Trung. Với SSI viết rõ 'Công ty Chứng khoán SSI' hoặc 'Mã SSI'.
2. TUYỆT ĐỐI KHÔNG DÙNG BẢNG MARKDOWN (|). Hãy dùng danh sách gạch đầu dòng Markdown chuẩn (- ) và in đậm rõ ràng.
3. Không bịa đặt chỉ số tài chính. Dữ liệu nào ghi N/A hoặc thiếu thì đánh giá khách quan là 'Dữ liệu chưa công bố'.
4. Trình bày tách bạch từng mục, dùng tiêu đề H3 (###) chuẩn.
</CONSTRAINTS>

<DECISION_GUARDRAILS>
- KHÔNG BẮT BUỘC PHẢI MUA: Nếu tỷ lệ Risk/Reward < 1.5 hoặc thị trường đang rủi ro, BẮT BUỘC chọn khuyến nghị ⛔ [KHÔNG HÀNH ĐỘNG / TRÁNH BẪY] hoặc 🟡 [NẮM GIỮ / THEO DÕI].
- Nếu phát hiện bẫy tin tức hoặc khối ngoại xả ròng mạnh, TUYỆT ĐỐI KHÔNG khuyến nghị Mua mạnh.
- Phân biệt rõ 'Doanh nghiệp tốt' khác với 'Cổ phiếu tốt để mua'. Doanh nghiệp tốt nhưng giá quá đắt hoặc ở đỉnh chu kỳ thì không được khuyến nghị Mua mạnh.
</DECISION_GUARDRAILS>

<OUTPUT_FORMAT>
Hãy lập Báo cáo Phân tích Toàn diện cho cổ phiếu **{symbol}** theo chính xác cấu trúc sau:

---
### 🎯 I. TÓM TẮT ĐIỀU HÀNH (EXECUTIVE DECISION - ĐẶT NGAY TRÊN ĐẦU)
- **Khuyến nghị hành động:** 🟢 [MUA MẠNH] / 🟢 [MUA] / 🟢 [TÍCH LŨY] / 🟡 [NẮM GIỮ / THEO DÕI] / 🔴 [BÁN / CẮT LỖ] / ⛔ [KHÔNG HÀNH ĐỘNG / TRÁNH BẪY]
- **Vùng giá mua gom tối ưu:** [...] k VND
- **Giá mục tiêu (Target Price):** [...] k VND (Kỳ vọng sinh lời Upside: +...%)
- **Ngưỡng cắt lỗ (Stop-Loss):** [...] k VND (Mức rủi ro Downside tối đa: -...%)
- **Tỷ lệ Risk / Reward (R:R):** [...] x (Yêu cầu: ≥ 1.5 mới xét Mua)
- **Tổng điểm xếp hạng:** .../100 Điểm (Xếp loại: [🟢 Xuất sắc / 🟢 Tích cực / 🟡 Trung bình / 🔴 Rủi ro])
- **Thesis Breaker quan trọng nhất:** [Nêu 1 lý do then chốt nếu xảy ra sẽ lập tức hủy bỏ vị thế và bán cắt lỗ]
- **Lý do hành động trong 1 câu:** [...]

---
### 📊 II. BẢNG TỔNG KẾT TÍN HIỆU 8 TRỤ CỘT
(Quy tắc màu: 🟢 Tốt/Mua | 🟡 Trung bình/Theo dõi | 🔴 Xấu/Rủi ro cao)

- **Trụ cột 1 (Độ tin cậy dữ liệu):** 🟢 [ĐẦY ĐỦ / ĐỘ TIN CẬY CAO] (hoặc 🟡 [THIẾU DỮ LIỆU])
- **Trụ cột 2 (Cơ bản & Sinh lời):** 🟢 [MUA - TĂNG TRƯỞNG TỐT] / 🟡 [TRUNG BÌNH] / 🔴 [SUY GIẢM]
- **Trụ cột 3 (Định giá & Biên an toàn):** 🟢 [HẤP DẪN] / 🟡 [HỢP LÝ] / 🔴 [QUÁ ĐẮT / BẪY CHU KỲ]
- **Trụ cột 4 (Kỹ thuật & Xu hướng):** 🟢 [UPTREND] / 🟡 [CHỜ NỀN TÍCH LŨY] / 🔴 [DOWNTREND - GÃY MA]
- **Trụ cột 5 (Hành vi Dòng tiền & Khối ngoại):** [🟢 TỔ CHỨC GOM MUA / 🟡 THANH KHOẢN YẾU / 🔴 PHÂN PHỐI XẢ HÀNG]
- **Trụ cột 6 (Mức độ Rủi ro & Bẫy tin):** [🟢 RỦI RO THẤP / 🟡 CẢNH BÁO BẪY / 🔴 RỦI RO CAO]
- **Trụ cột 7 (Triển vọng 6-12 tháng):** 🟢 [KHẢ QUAN] / 🟡 [GIẰNG CO] / 🔴 [KÉM KHẢ QUAN]
- **Trụ cột 8 (Phân bổ Danh mục đề xuất):** [ĐỀ XUẤT TỶ TRỌNG ...% TÀI SẢN]

---
### 🐂 III. TRANH BIỆN ĐỐI KHÁNG: PHE BÒ (BULL THESIS) VS PHE GẤU (BEAR AUDIT)
#### 🟢 1. Phe Bò (Bull Thesis - Tăng Trưởng & Động Lực Mua):
- **Luận điểm 1 (Chất xúc tác & Doanh nghiệp):** [...]
- **Luận điểm 2 (Kỹ thuật & Dòng tiền):** [...]
- **Luận điểm 3 (Định giá & Biên an toàn):** [...]

#### 🔴 2. Phe Gấu (Bear CRO Audit - Vạch Lá Tìm Sâu & Bẫy Rủi Ro):
- **Phản biện 1 (Bẫy giá & Dòng tiền khối ngoại):** [Chỉ rõ áp lực bán ngoại, bẫy tin tức quá mua, nến cụt đầu nếu có...]
- **Phản biện 2 (Sức khỏe BCTC & Chu kỳ):** [Bóc tách điểm yếu nợ vay, biên lợi nhuận hoặc nguy cơ đỉnh chu kỳ...]
- **Phản biện 3 (Kỹ thuật & Rủi ro thủng nền):** [...]

#### 🛡️ 3. Bộ 3 Thesis Breakers (Ngưỡng Vi Phạm Bắt Buộc Thoát Vị Thế):
- **Thesis Breaker 1 (Kỹ thuật/Cắt lỗ):** Thủng mốc Stop-Loss [...] k VND kèm thanh khoản lớn -> Thoát 100% vị thế.
- **Thesis Breaker 2 (Dòng tiền / Khối ngoại):** [...]
- **Thesis Breaker 3 (Cơ bản / Hoạt động kinh doanh):** [...]

---
### 💰 IV. ĐỊNH GIÁ & BIÊN AN TOÀN (FAIR VALUE & MARGIN OF SAFETY)
- **Định giá P/E mục tiêu:** Giá ... k VND (P/E ...x) ➔ Tiềm năng: +...%
- **Định giá P/B mục tiêu:** Giá ... k VND (P/B ...x) ➔ Tiềm năng: +...%
- 🎯 **GIÁ TRỊ HỢP LÝ (FAIR VALUE BÌNH QUÂN):** ... k VND
- 🛡️ **BIÊN AN TOÀN (MARGIN OF SAFETY):** ...% so với thị giá hiện tại.
*(Lưu ý: Nếu cổ phiếu thuộc nhóm chu kỳ, hãy nêu rõ cảnh báo bẫy định giá đỉnh chu kỳ nếu có)*

---
### 📈 V. PHÂN TÍCH KỸ THUẬT & HÀNH VI DÒNG TIỀN (SMART MONEY)
- Vị thế xu hướng (MA20, MA50, MA200) và động lượng RSI(14).
- Giao dịch Khối ngoại và tín hiệu dòng tiền lớn.
- Vùng Hỗ trợ cứng: ... k VND | Vùng Kháng cự then chốt: ... k VND.

---
### 🎯 VI. 3 KỊCH BẢN ĐẦU TƯ (6 - 12 THÁNG TỚI)
- **Kịch bản Tích cực (Bull case):** Xác suất: ...% | Điều kiện kích hoạt: [...] | Giá mục tiêu: ... k VND (+...%)
- **Kịch bản Cơ sở (Base case):** Xác suất: ...% | Điều kiện kích hoạt: [...] | Giá mục tiêu: ... k VND (+...%)
- **Kịch bản Tiêu cực (Bear case):** Xác suất: ...% | Điều kiện kích hoạt: [...] | Giá giảm về: ... k VND (-...%)
*(Lưu ý: Tổng xác suất của 3 kịch bản phải đúng 100%)*

---
### 🏁 VII. KẾT LUẬN & BẢNG CHẤM ĐIỂM (THANG ĐIỂM 100)
- Khung thời gian nắm giữ tối ưu: (Lướt sóng T+, Trung hạn 3-6 tháng, hay Đầu tư giá trị > 1 năm).
- **BẢNG ĐIỂM CHI TIẾT:**
  - Chất lượng cơ bản & Tăng trưởng: .../25 điểm
  - Động lực & Chất xúc tác (Catalyst): .../20 điểm
  - Biên an toàn Định giá: .../20 điểm
  - Tín hiệu Kỹ thuật & Dòng tiền: .../20 điểm
  - Quản trị Rủi ro (Điểm càng cao rủi ro càng thấp): .../15 điểm
  ➔ **TỔNG ĐIỂM XẾP HẠNG: .../100 ĐIỂM**
</OUTPUT_FORMAT>"""

    return call_gemini(client, prompt)

def generate_quantamental_2pass_report(symbol: str) -> dict:
    """
    QUY TRÌNH PHÂN TÍCH LƯỢNG HÓA HAI LƯỢT (QUANTAMENTAL 2-PASS PIPELINE):
    - Cổng Data Gate: Kiểm tra tính toàn vẹn và thanh khoản (ADV20).
    - Python Quant Engine: Tính toán Piotroski F-Score, Altman Z-Score, ATR, Tam giác định giá.
    - Lượt 1 (LLM): Đọc tin tức và bối cảnh ngành ➔ gán xác suất Bull/Base/Bear dạng JSON.
    - Python Bridge: Tính toán Expected Value (EV), Margin of Safety (MoS), Risk/Reward và Kelly Criterion f*.
    - Lượt 2 (LLM): Nhận các số liệu do Python tính toán và viết Báo cáo Định chế chuẩn CFA, tuyệt đối không bịa số.
    """
    client = get_ai_client()
    from data_engine import fetch_stock_technical, get_financial_ratios, fetch_macro_news
    from quant_engine import (
        check_data_gate,
        calculate_piotroski_f_score,
        calculate_altman_z_score,
        calculate_valuation_triangle,
        evaluate_decision_hard_gates
    )

    symbol = symbol.strip().upper()
    tech_data = fetch_stock_technical(symbol)
    fin_data = get_financial_ratios(symbol)
    news_items = fetch_macro_news(limit=10, tracked_symbols=[symbol])

    # -------------------------------------------------------------
    # BƯỚC 1: CỔNG KIỂM TRA DỮ LIỆU CỨNG (DATA GATE)
    # -------------------------------------------------------------
    gate = check_data_gate(symbol, tech_data, fin_data, min_adv20_billion=2.0)
    if not gate["passed"]:
        reason_str = " | ".join(gate["reasons"])
        refusal_report = (
            f"======================================================\n"
            f"⛔ **TỪ CHỐI KHUYẾN NGHỊ: DỮ LIỆU KHÔNG ĐẠT CHUẨN AN TOÀN QUỸ**\n"
            f"======================================================\n\n"
            f"• **Mã cổ phiếu:** {symbol}\n"
            f"• **Giá trị giao dịch trung bình phiên:** {gate.get('daily_value_billion', 0)} tỷ VND\n"
            f"• **Lý do từ chối:** {reason_str}\n\n"
            f"⚠️ **Khuyến cáo:** Hệ thống Lượng hóa Định chế từ chối đưa ra khuyến nghị đối với cổ phiếu cạn thanh khoản hoặc thiếu BCTC kiểm toán để bảo vệ vốn nhà đầu tư!"
        )
        return {
            "status": "DATA_GATE_REJECTED",
            "report_text": refusal_report,
            "hard_gates": {},
            "f_score": {},
            "z_score": {}
        }

    # -------------------------------------------------------------
    # BƯỚC 2: PYTHON QUANT ENGINE TÍNH TOÁN TRƯỚC
    # -------------------------------------------------------------
    curr_price = tech_data.get("current_price", 0.0)
    pe = fin_data.get("pe")
    pb = fin_data.get("pb")
    f_score_res = calculate_piotroski_f_score(fin_data)
    z_score_res = calculate_altman_z_score(fin_data)
    val_triangle = calculate_valuation_triangle(curr_price, pe=pe, pb=pb)

    ff = tech_data.get("foreign_flow", {})
    ff_str = f"Mua {ff.get('buy_val_bil', 0):.1f} tỷ, Bán {ff.get('sell_val_bil', 0):.1f} tỷ, Ròng {ff.get('net_val_bil', 0):+.1f} tỷ ({ff.get('status_vi', 'N/A')})" if ff else "Chưa có số liệu giao dịch."
    
    tr = tech_data.get("trap_info", {})
    tr_str = f"⚠️ CẢNH BÁO BẪY: {tr.get('warning_msg')}" if tr.get("is_trap") else "✅ Không phát hiện bẫy nguy hiểm."
    adv_str = f"{tech_data.get('adv20_billion', 0):.2f} tỷ/phiên" if tech_data.get('adv20_billion') else "N/A"

    news_brief = "\n".join([f"- [{n.get('tag', n.get('keyword', 'TIN')).upper()}] {n.get('title', '')}" for n in (news_items or [])[:5]]) if news_items else "Không có tin tức đột biến."

    # -------------------------------------------------------------
    # BƯỚC 3: LƯỢT 1 (LLM GÁN XÁC SUẤT KỊCH BẢN DẠNG JSON)
    # -------------------------------------------------------------
    pass1_prompt = f"""Bạn là Quản lý Quỹ Lượng hóa (Quantamental Portfolio Manager).
Hãy đọc các dữ liệu thị trường và tin tức sau của mã **{symbol}**:
- Thị giá: {curr_price}k | Vị thế MA20: {tech_data.get('status_ma20')} | RSI(14): {tech_data.get('rsi14')} | Vol/SMA20: {tech_data.get('vol_ratio')}x
- Thanh khoản ADV20: {adv_str} | Dòng tiền Khối ngoại: {ff_str}
- Tín hiệu Bẫy tin tức: {tr_str}
- P/E: {pe} | P/B: {pb} | ROE: {fin_data.get('roe')}% | Nợ/Vốn chủ: {fin_data.get('debt_equity')}
- Điểm kiểm toán F-Score: {f_score_res['score']}/9 ({f_score_res['rating']}) | Z-Score: {z_score_res['z_score']} ({z_score_res['zone']})
- Tin tức vĩ mô / doanh nghiệp:
{news_brief}

Mục tiêu của bạn trong Lượt 1:
Dựa trên bối cảnh ngành, áp lực mua/bán ròng của Khối ngoại và tín hiệu Bẫy tin tức (nếu có), hãy gán xác suất cho 3 kịch bản trong 6-12 tháng tới:
- P_bull: Xác suất kịch bản Lạc quan
- P_base: Xác suất kịch bản Cơ sở
- P_bear: Xác suất kịch bản Tiêu cực (Nếu có cảnh báo bẫy hoặc khối ngoại xả ròng mạnh, P_bear phải tăng lên tương xứng)
(Yêu cầu: P_bull + P_base + P_bear = 1.0)

BẮT BUỘC TRẢ VỀ DUY NHẤT 1 ĐOẠN JSON HỢP LỆ (KHÔNG GIẢI THÍCH THÊM NGOÀI JSON) theo cấu trúc:
```json
{{
  "P_bull": 0.25,
  "P_base": 0.50,
  "P_bear": 0.25,
  "rationale_bull": "Điều kiện kích hoạt kịch bản tốt...",
  "rationale_base": "Điều kiện kịch bản cơ sở...",
  "rationale_bear": "Rủi ro kịch bản xấu..."
}}
```"""

    try:
        pass1_resp = client.models.generate_content(model=MODEL_NAME, contents=pass1_prompt)
        raw_text = pass1_resp.text.strip()
        # Trích xuất JSON từ markdown block nếu có
        json_match = re.search(r'\{.*\}', raw_text, re.DOTALL)
        if json_match:
            prob_dict = json.loads(json_match.group(0))
        else:
            prob_dict = json.loads(raw_text)
        
        p_bull = float(prob_dict.get("P_bull", 0.25))
        p_base = float(prob_dict.get("P_base", 0.50))
        p_bear = float(prob_dict.get("P_bear", 0.25))
        # Chuẩn hóa tổng xác suất = 1.0
        total_p = p_bull + p_base + p_bear
        if total_p > 0:
            p_bull /= total_p
            p_base /= total_p
            p_bear /= total_p
    except Exception as e:
        logging.warning(f"Fallback xác suất Lượt 1 do lỗi parse JSON: {e}")
        p_bull, p_base, p_bear = 0.25, 0.50, 0.25
        prob_dict = {
            "rationale_bull": "Tăng trưởng doanh thu và mở rộng thị phần tích cực.",
            "rationale_base": "Duy trì nhịp vận động kinh doanh và định giá ổn định.",
            "rationale_bear": "Áp lực điều chỉnh theo thị trường chung hoặc chi phí vốn tăng."
        }

    # -------------------------------------------------------------
    # BƯỚC 4: PYTHON TÍNH TOÁN HÀNG RÀO QUYẾT ĐỊNH ĐỊNH LƯỢNG
    # -------------------------------------------------------------
    hard_gates = evaluate_decision_hard_gates(
        current_price=curr_price,
        p_bull=p_bull,
        p_base=p_base,
        p_bear=p_bear,
        price_bull=val_triangle["price_bull"],
        price_base=val_triangle["price_base"],
        price_bear=val_triangle["price_bear"],
        atr=tech_data.get("atr14", 0.0),
        trap_info=tech_data.get("trap_info"),
        foreign_flow=tech_data.get("foreign_flow"),
        adv20_billion=tech_data.get("adv20_billion", 0.0)
    )

    # -------------------------------------------------------------
    # BƯỚC 5: LƯỢT 2 (LLM VIẾT BÁO CÁO TRANH BIỆN ĐỊNH CHẾ HOÀN CHỈNH)
    # -------------------------------------------------------------
    pass2_prompt = f"""<ROLE>
Bạn là Giám đốc Phân tích Đầu tư Lượng hóa (Senior Quantamental Research Director / CFA).
Toàn bộ số liệu định lượng dưới đây ĐÃ ĐƯỢC HỆ THỐNG PYTHON TÍNH TOÁN XÁC THỰC. Bạn TUYỆT ĐỐI KHÔNG ĐƯỢC THAY ĐỔI BẤT KỲ CON SỐ NÀO.
Bạn sẽ tổ chức một màn TRANH BIỆN ĐỐI KHÁNG (Adversarial Debate) quyết liệt giữa Phe Bò (Bull Thesis - Trưởng nhóm Phân tích) và Phe Gấu (Bear CRO Audit - Giám đốc Quản trị Rủi ro), sau đó áp đặt Phán quyết Định lượng Cuối cùng do Python quyết định.
</ROLE>

<CONTEXT>
[CÁC KẾT QUẢ ĐỊNH LƯỢNG DO PYTHON TÍNH TOÁN]:
- Cổ phiếu: {symbol} | Thị giá hiện tại: {curr_price} k VND (Biến động phiên: {tech_data.get('change_pct')}%)
- Vị thế kỹ thuật: {tech_data.get('status_ma20')} (MA20: {tech_data.get('ma20')}k, MA50: {tech_data.get('ma50')}k, RSI: {tech_data.get('rsi14')}, Vol/SMA20: {tech_data.get('vol_ratio')}x)
- Thanh khoản ADV20: {adv_str}
- Giao dịch Khối ngoại: {ff_str}
- Cảnh báo bẫy tin tức: {tr_str}
- Điểm kiểm toán Piotroski F-Score: {f_score_res['score']}/9 (Xếp loại: {f_score_res['rating']})
- Điểm kiệt quệ tài chính Altman Z-Score: {z_score_res['z_score']} ({z_score_res['zone']})
- Giá mục tiêu 3 kịch bản: Bull = {val_triangle['price_bull']}k | Base = {val_triangle['price_base']}k | Bear = {val_triangle['price_bear']}k
- Xác suất kịch bản đã gán: Bull = {p_bull*100:.1f}% | Base = {p_base*100:.1f}% | Bear = {p_bear*100:.1f}%
- Giá trị kỳ vọng toán học (Expected Value - EV): {hard_gates.get('ev')} k VND
- Biên an toàn định lượng (Margin of Safety - MoS): {hard_gates.get('mos_pct'):+.2f}%
- Ngưỡng cắt lỗ Stop-Loss: {hard_gates.get('stop_loss')} k VND (Mức rủi ro Downside: -{hard_gates.get('downside_pct')}%)
- Tỷ lệ Lãi / Lỗ R (Risk/Reward): {hard_gates.get('risk_reward')}x
- Tiêu chuẩn phân bổ Kelly Criterion (f*): {hard_gates.get('kelly_f')}
- QUYẾT ĐỊNH HÀNG RÀO CỨNG: {hard_gates.get('decision_tag')}
- TỶ TRỌNG NAV ĐỀ XUẤT: {hard_gates.get('position_size_nav')}
- Luận điểm kịch bản:
  + Bull: {prob_dict.get('rationale_bull')}
  + Base: {prob_dict.get('rationale_base')}
  + Bear: {prob_dict.get('rationale_bear')}
- Bối cảnh tin tức mới nhất:
{news_brief}
</CONTEXT>

<CONSTRAINTS>
1. TUYỆT ĐỐI DÙNG 100% TIẾNG VIỆT CHUẨN UNICODE. Cấm chữ tiếng Trung. Với SSI viết rõ 'Công ty Chứng khoán SSI' hoặc 'Mã SSI'.
2. TUYỆT ĐỐI KHÔNG DÙNG BẢNG MARKDOWN (|). Hãy dùng bullet point và in đậm.
3. Giữ nguyên 100% các con số định lượng do Python đã tính toán. Nếu Python đưa ra '⛔ CẢNH BÁO BẪY' hoặc '0% NAV', cấm AI tự ý khuyên Mua!
</CONSTRAINTS>

<OUTPUT_FORMAT>
Hãy trình bày báo cáo chính xác theo cấu trúc sau:

---
### 🎯 I. TÓM TẮT ĐIỀU HÀNH (EXECUTIVE DECISION - THEO HÀNG RÀO PYTHON)
- **Khuyến nghị chính thức:** {hard_gates.get('decision_tag')}
- **Giá trị kỳ vọng (Expected Value - EV):** {hard_gates.get('ev')} k VND
- **Biên an toàn định lượng (Margin of Safety):** {hard_gates.get('mos_pct'):+.2f}%
- **Vùng giá mua gom tối ưu:** [Đề xuất vùng giá hợp lý dựa trên mốc Base và MA20] k VND
- **Ngưỡng cắt lỗ dứt khoát (Stop-Loss):** {hard_gates.get('stop_loss')} k VND (Mức rủi ro Downside: -{hard_gates.get('downside_pct')}%)
- **Tỷ lệ Risk / Reward (R:R):** {hard_gates.get('risk_reward')}x
- **Tỷ trọng đề xuất trong danh mục:** {hard_gates.get('position_size_nav')}
- **Kelly Criterion f*:** {hard_gates.get('kelly_f')} (Ý nghĩa: {'Cấm mở vị thế mua do Kelly không dương' if hard_gates.get('kelly_f', 0) <= 0 else 'Đạt chuẩn giải ngân vốn'})
- **Thesis Breaker quan trọng nhất:** [Nêu 1 lý do then chốt nếu vi phạm sẽ thoát vị thế ngay]

---
### 📊 II. BẢNG TỔNG KẾT 8 TRỤ CỘT & ĐIỂM SỨC KHỎE TÀI CHÍNH
- **Piotroski F-Score:** {f_score_res['score']}/9 Điểm (Xếp loại: {f_score_res['rating']})
- **Altman Z-Score:** {z_score_res['z_score']} ({z_score_res['icon']} {z_score_res['zone']})
- **Trụ cột 1 (Dữ liệu):** 🟢 ĐẦY ĐỦ / ĐẠT CHUẨN DATA GATE (Thanh khoản {gate.get('daily_value_billion')} tỷ/phiên)
- **Trụ cột 2 (Cơ bản & Sinh lời):** [🟢 Tốt / 🟡 Trung bình / 🔴 Suy giảm] (ROE {fin_data.get('roe')}%, Nợ/Vốn {fin_data.get('debt_equity')})
- **Trụ cột 3 (Định giá & Biên an toàn):** [🟢 Hấp dẫn / 🟡 Hợp lý / 🔴 Bẫy chu kỳ/Đắt] (MoS {hard_gates.get('mos_pct'):+.2f}%)
- **Trụ cột 4 (Kỹ thuật & Xu hướng):** [🟢 Uptrend / 🟡 Chờ tích lũy / 🔴 Gãy MA20] ({tech_data.get('status_ma20')})
- **Trụ cột 5 (Hành vi Dòng tiền & Khối ngoại):** [🟢 Gom hàng / 🟡 Cạn kiệt / 🔴 Phân phối / Xả ròng] ({ff_str})
- **Trụ cột 6 (Mức độ Rủi ro & Bẫy tin):** [🟢 Thấp / 🟡 Cảnh báo bẫy / 🔴 Cao] ({tr_str})
- **Trụ cột 7 (Triển vọng Kịch bản):** [🟢 Khả quan / 🟡 Giằng co / 🔴 Tiêu cực]
- **Trụ cột 8 (Phân bổ Danh mục):** {hard_gates.get('position_size_nav')}

---
### 🐂 III. TRANH BIỆN ĐỐI KHÁNG: PHE BÒ (BULL THESIS) VS PHE GẤU (BEAR CRO AUDIT)
#### 🟢 1. Phe Bò (Bull Thesis - Luận Điểm Tăng Trưởng & Upside):
- **Động lực tăng trưởng:** {prob_dict.get('rationale_bull')}
- **Kỹ thuật & Dòng tiền:** [Nêu ưu điểm kỹ thuật và bệ đỡ giá]
- **Mục tiêu Kịch bản Lạc quan:** {val_triangle['price_bull']} k VND

#### 🔴 2. Phe Gấu (Bear CRO Audit - Vạch Lá Tìm Sâu & Bẫy Rủi Ro):
- **Cảnh báo Bẫy & Dòng tiền ngoại:** [Đánh giá tín hiệu '{tr_str}' và dòng tiền '{ff_str}']
- **Bóc tách rủi ro BCTC & Chu kỳ:** Điểm F-Score ({f_score_res['score']}/9), Z-Score ({z_score_res['z_score']}), rủi ro {prob_dict.get('rationale_bear')}
- **Rủi ro Kịch bản Xấu nhất:** Giảm về vùng Bear {val_triangle['price_bear']} k VND.

#### 🛡️ 3. Bộ 3 Thesis Breakers (Ngưỡng Vi Phạm Bắt Buộc Thoát Vị Thế):
- **Thesis Breaker 1 (Ngưỡng Cắt Lỗ Cứng):** Giá đóng cửa gãy mốc Stop-loss {hard_gates.get('stop_loss')} k VND (Rủi ro -{hard_gates.get('downside_pct')}%) -> Kích hoạt lệnh bán dứt khoát 100%.
- **Thesis Breaker 2 (Dòng tiền / Veto Bẫy):** [Điều kiện vi phạm dòng tiền hoặc bẫy tin tức kéo xả]
- **Thesis Breaker 3 (Cơ bản / BCTC):** [Điều kiện vi phạm hoạt động kinh doanh cốt lõi]

---
### 🎯 IV. 3 KỊCH BẢN 6-12 THÁNG (ĐỊNH LƯỢNG)
- **🟢 Kịch bản Lạc quan (Bull Case):** Giá {val_triangle['price_bull']}k | Xác suất: {p_bull*100:.1f}% | Điều kiện: {prob_dict.get('rationale_bull')}
- **🟡 Kịch bản Cơ sở (Base Case):** Giá {val_triangle['price_base']}k | Xác suất: {p_base*100:.1f}% | Điều kiện: {prob_dict.get('rationale_base')}
- **🔴 Kịch bản Tiêu cực (Bear Case):** Giá {val_triangle['price_bear']}k | Xác suất: {p_bear*100:.1f}% | Điều kiện: {prob_dict.get('rationale_bear')}
➔ **Giá trị kỳ vọng toán học (EV):** {hard_gates.get('ev')} k VND | **Biên an toàn (MoS):** {hard_gates.get('mos_pct'):+.2f}%

---
### 🔍 V. KIỂM TRA CHÉO & PHÁN QUYẾT HỘI ĐỒNG LƯỢNG HÓA
- **Quyết định định lượng tối hậu:** {hard_gates.get('decision_tag')}
- **Hành động phân bổ vốn:** {hard_gates.get('position_size_nav')}
- **Tín hiệu theo dõi trọng yếu:** [...]
</OUTPUT_FORMAT>"""

    final_report = call_gemini(client, pass2_prompt)
    return {
        "status": "SUCCESS",
        "report_text": final_report,
        "hard_gates": hard_gates,
        "f_score": f_score_res,
        "z_score": z_score_res,
        "data_gate": gate
    }


if __name__ == "__main__":
    print("=== KIỂM TRA PHÂN TÍCH VỚI GEMINI ===")
    portfolio = load_portfolio()
    df_eval = evaluate_portfolio(portfolio)
    news = fetch_macro_news()
    
    print("Đang gửi dữ liệu đến Gemini...")
    analysis = generate_portfolio_analysis(df_eval, news)
    print("\n--- BÁO CÁO PHÂN TÍCH TỪ GEMINI ---")
    print(analysis)

