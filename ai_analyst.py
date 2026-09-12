import os
import json
import logging
from dotenv import load_dotenv
from google import genai
from data_engine import load_portfolio, evaluate_portfolio, fetch_macro_news

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
MODEL_NAME = "gemini-3.6-flash"  # Model tối ưu tốc độ, context và free tier của Gemini


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
1. **Đánh giá sức khỏe danh mục:** Nhận xét chi tiết từng mã đang nắm giữ. Phân loại mã nào đang giữ nhịp tốt (trên MA20, RSI tích cực), mã nào rủi ro gãy nền cần quản trị giá vốn.
2. **Tác động Tin vĩ mô & Doanh nghiệp:** Tin tức CafeF vừa cập nhật (cổ tức, KQKD, giao dịch nội bộ, chính sách) đang tạo động lực hay áp lực lên danh mục?
3. **Kịch bản hành động cụ thể (Rõ ràng từng mốc):**
   - **T+ (Ngắn hạn):** Điểm chốt lời ngắn hạn (Take Profit) và điểm quản trị rủi ro/cắt lỗ (Stop Loss) cụ thể theo giá thị trường.
   - **Trung hạn (3 - 6 tháng):** Chiến lược cơ cấu, gia tăng tỷ trọng hay hạ bớt.
4. **Cổ phiếu / Ngành tiềm năng:** Nhận định về các mã trong Watchlist (nếu có) hoặc gợi ý 1 nhóm ngành đang có dòng tiền vào mạnh đón sóng.

Yêu cầu định dạng đặc biệt cho Discord & Web:
- TUYỆT ĐỐI KHÔNG DÙNG BẢNG MARKDOWN (| Cột | Cột |) vì Discord không hỗ trợ hiển thị bảng và sẽ bị vỡ nát trên điện thoại.
- TUYỆT ĐỐI KHÔNG DÙNG DẤU `###`. Thay bằng tiêu đề in đậm rõ ràng (Ví dụ: `**I. ĐÁNH GIÁ SỨC KHỎE DANH MỤC**`).
- Dùng bullet point dạng `• ` hoặc `> ` kèm emoji để tạo giao diện trực quan, sang trọng.
- Chia rõ ràng 4 mục lớn:
  **I. ĐÁNH GIÁ SỨC KHỎE DANH MỤC**
  **II. TÁC ĐỘNG VĨ MÔ & DÒNG TIỀN**
  **III. KỊCH BẢN & CHIẾN LƯỢC HÀNH ĐỘNG**
  **IV. CỔ PHIẾU / NGÀNH ĐÓN SÓNG TIỀM NĂNG**
"""

    if custom_question:
        prompt += f"\n\n[CÂU HỎI BỔ SUNG CỦA NHÀ ĐẦU TƯ]: {custom_question}\nHãy trả lời chi tiết trọng tâm câu hỏi này."

    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=prompt
    )
    return response.text


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
                f"• Mã: {o['symbol']} ({o.get('sector', 'Niêm yết')}) | Thị giá: {o['current_price']}k | Setup: {o.get('setup_type')} | "
                f"Vùng mua: {o.get('entry_zone', 'Quanh giá hiện tại')}k | Target: {o.get('target_price')}k | Cutloss: {o.get('stop_loss')}k | R:R: {o.get('risk_reward')} | "
                f"Xúc tác/Câu chuyện: [{o.get('story_tag')}] {o.get('story')} | Chi tiết: {o.get('rationale')}"
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

Yêu cầu xuất bản:
1. **Định hướng thị trường phiên hôm nay:** Nhận định nhanh tâm lý mở phiên ATO, dựa sát vào điểm số VN-Index ({idx_price:.2f}) và các mốc hỗ trợ MA20 ({idx_ma20:.2f})/kháng cự thực tế.
2. **Kế hoạch cho danh mục hiện tại:** Mã nào cần kê lệnh chốt lời, mã nào cần giữ kỷ luật nếu thị trường rung lắc.
3. **🎯 TOP CỔ PHIẾU KHUYẾN NGHỊ MUA (CÂU CHUYỆN + KỸ THUẬT ĐẠT CHUẨN):**
   Từ danh sách mục 3, nêu rõ từng mã được chọn:
   - **Mã cổ phiếu & Nhóm ngành**
   - **Câu chuyện xúc tác / Luận điểm cơ bản**
   - **Vùng giá gom an toàn (Buy Range)**
   - **Giá mục tiêu kỳ vọng (Target Price)**
   - **Ngưỡng dừng lỗ (Stop Loss)**
   - **Trạng thái kỹ thuật & Dòng tiền xác nhận**
4. **⚠️ CẢNH BÁO BẪY TIN TỨC & QUẢN TRỊ RỦI RO:**
   Từ danh sách mục 4, nhắc nhở nhà đầu tư KHÔNG Fomo/bắt đáy các mã có tin tốt nhưng giá đang dưới MA20 hoặc bị bán xả.

Định dạng Discord/Web:
- KHÔNG dùng bảng markdown (|---|).
- KHÔNG dùng dấu `###`.
- Tiêu đề in đậm: `**I. NHẬN ĐỊNH ĐẦU PHIÊN ATO**`, `**II. HÀNH ĐỘNG VỚI DANH MỤC HIỆN TẠI**`, `**III. 🎯 TOP CỔ PHIẾU KHUYẾN NGHỊ MUA**`, `**IV. ⚠️ CẢNH BÁO TRÁNH BẪY TIN TỨC**`.
"""
    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=prompt
    )
    return response.text


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

    news_str = "\n".join([f"- [{n['keyword'].upper()}] {n['title']}" for n in news_items[:8]])

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

    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=prompt
    )
    return response.text


def generate_institutional_stock_report(symbol: str, financial_info: dict, tech_dict: dict, news_items: list) -> str:
    """
    Báo cáo phân tích chuyên sâu định chế 8 trụ cột và chấm điểm 100 theo đúng chuẩn Institutional Equity Research.
    """
    client = get_ai_client()

    tech_summary = (
        f"Mã CP: {symbol}\n"
        f"Thị giá: {tech_dict.get('current_price', 'N/A')} (k VND)\n"
        f"Biến động phiên: {tech_dict.get('change_pct', 0)}%\n"
        f"Vị thế MA20: {tech_dict.get('ma20', 'N/A')} ({tech_dict.get('status_ma20', 'N/A')})\n"
        f"Đường MA50: {tech_dict.get('ma50', 'N/A')}\n"
        f"RSI (14): {tech_dict.get('rsi14', 'N/A')}\n"
        f"Khối lượng giao dịch: {tech_dict.get('volume', 0):,} CP\n"
        f"Tỷ lệ Vol / SMA20: {tech_dict.get('vol_ratio', 1.0)}x\n"
    )

    fin_summary = f"Kỳ báo cáo gần nhất: {financial_info.get('period', 'N/A')}\n"
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

    news_str = "\n".join([f"- [{n['keyword'].upper()}] {n['title']}" for n in news_items[:6]])

    prompt = f"""Hãy đóng vai trò là một Giám đốc Phân tích Đầu tư cấp cao (Senior Equity Research Director / CFA Charterholder) tại một công ty quản lý quỹ hàng đầu Việt Nam.

Dưới đây là toàn bộ dữ liệu tài chính, kỹ thuật và tin tức đã được thu thập cho cổ phiếu **{symbol}**:

=== DỮ LIỆU KỸ THUẬT & GIAO DỊCH ===
{tech_summary}

=== BÁO CÁO CHỈ SỐ TÀI CHÍNH & ĐỊNH GIÁ ===
{fin_summary}

=== TIN TỨC VĨ MÔ & LIÊN QUAN ===
{news_str}

Nhiệm vụ của bạn là lập Báo cáo Phân tích Định chế Toàn diện cho cổ phiếu **{symbol}**. 
Hãy trình bày theo cấu trúc trực quan, khoa học sau:

======================================================
🎯 **I. TÓM TẮT ĐIỀU HÀNH (EXECUTIVE SUMMARY - ĐẶT NGAY TRÊN ĐẦU)**
======================================================
1. **Khuyến nghị hành động:** 🟢 [MUA MẠNH] / 🟢 [MUA] / 🟡 [THEO DÕI / NẮM GIỮ] / 🔴 [BÁN]
2. **Vùng giá mua gom tối ưu:** [...] k VND
3. **Giá mục tiêu (Target Price):** [...] k VND (Kỳ vọng sinh lời: +...%)
4. **Ngưỡng cắt lỗ (Stop-Loss):** [...] k VND (Mức rủi ro tối đa: -...%)
5. **Tổng điểm xếp hạng:** .../100 Điểm (Xếp loại: [🟢 Xuất sắc / 🟢 Tích cực / 🟡 Trung bình / 🔴 Rủi ro])

======================================================
📊 **II. BẢNG TỔNG KẾT TÍN HIỆU 8 TRỤ CỘT (CẢNH BÁO MÀU SẮC)**
======================================================
(QUY TẮC MÀU SẮC BẮT BUỘC:
 Dùng 🟢 cho trạng thái TỐT/MUA/HẤP DẪN/RỦI RO THẤP
 Dùng 🟡 cho trạng thái TRUNG BÌNH/THEO DÕI/NẮM GIỮ/RỦI RO VỪA
 Dùng 🔴 cho trạng thái XẤU/BÁN/RỦI RO CAO/ĐẮT)

• **Trụ cột 1 (Kiểm tra Dữ liệu):** 🟢 [ĐẦY ĐỦ / ĐỘ TIN CẬY CAO] (hoặc 🟡 [THIẾU DỮ LIỆU])
• **Trụ cột 2 (Cơ bản & Sinh lời):** 🟢 [MUA - TĂNG TRƯỞNG TỐT] / 🟡 [TRUNG BÌNH] / 🔴 [SUY GIẢM]
• **Trụ cột 3 (Định giá & Biên an toàn):** 🟢 [MUA - ĐỊNH GIÁ HẤP DẪN] / 🟡 [HỢP LÝ] / 🔴 [ĐỊNH GIÁ QUÁ CAO]
• **Trụ cột 4 (Kỹ thuật & Xu hướng):** 🟢 [MUA - XU HƯỚNG TĂNG] / 🟡 [NẮM GIỮ / CHỜ NỀN] / 🔴 [BÁN - GÃY MA]
• **Trụ cột 5 (Hành vi Dòng tiền):** 🟢 [GOM HÀNG TÍCH LŨY] / 🟡 [DÒNG TIỀN YẾU] / 🔴 [PHÂN PHỐI XẢ HÀNG]
• **Trụ cột 6 (Mức độ Rủi ro):** 🟢 [RỦI RO THẤP] / 🟡 [RỦI RO TRUNG BÌNH] / 🔴 [RỦI RO CAO]
• **Trụ cột 7 (Kịch bản 6-12 tháng):** 🟢 [XÁC SUẤT TĂNG CAO] / 🟡 [GIẰNG CO] / 🔴 [XÁC SUẤT GIẢM CAO]
• **Trụ cột 8 (Phân bổ Danh mục):** [ĐỀ XUẤT TỶ TRỌNG ...% TÀI SẢN]

======================================================
🔬 **III. PHÂN TÍCH CHI TIẾT 8 TRỤ CỘT (NGẮN GỌN, TRỰC QUAN, ĐÚNG TRỌNG TÂM)**
======================================================

**1. KIỂM TRA VÀ HIỂU DỮ LIỆU**
- Xác nhận các nguồn dữ liệu có sẵn, tính đầy đủ và giả định sử dụng.

**2. PHÂN TÍCH CƠ BẢN VÀ KHẢ NĂNG SINH LỜI**
- Tăng trưởng doanh thu và lợi nhuận các quý gần nhất.
- Hiệu quả sinh lời: ROE, ROA, ROIC so với trung bình ngành.
- Sức khỏe tài chính: Nợ/Vốn chủ, đòn bẩy tài chính và khả năng thanh toán.

**3. PHÂN TÍCH ĐỊNH GIÁ & GIÁ TRỊ HỢP LÝ (FAIR VALUE)**
*(Yêu cầu: TUYỆT ĐỐI KHÔNG dùng công thức toán học lý thuyết rườm rà như Ke, g, Justified P/B phức tạp. Hãy trình bày gãy gọn, dễ hiểu):*
- So sánh P/E, P/B hiện tại so với lịch sử và ngành.
- **Định giá P/E mục tiêu:** Giá ... k VND (P/E ...x) ➔ Tiềm năng: +...%
- **Định giá P/B mục tiêu:** Giá ... k VND (P/B ...x) ➔ Tiềm năng: +...%
- 🎯 **GIÁ TRỊ HỢP LÝ (FAIR VALUE BÌNH QUÂN):** ... k VND
- 🛡️ **BIÊN AN TOÀN (MARGIN OF SAFETY):** +...% so với thị giá hiện tại.

**4. PHÂN TÍCH KỸ THUẬT VÀ XU HƯỚNG GIÁ**
- Xu hướng ngắn - trung hạn: Vị thế nến so với MA20, MA50, MA200.
- Động lượng RSI(14) và dải biến động Bollinger Bands.
- Vùng hỗ trợ cứng và vùng cản kháng cự then chốt (k VND).

**5. PHÂN TÍCH HÀNH VI DÒNG TIỀN VÀ KHỐI LƯỢNG**
- Mối quan hệ Giá - Khối lượng (tỷ lệ Vol / SMA20).
- Dấu hiệu tích lũy gom hàng hay phân phối của dòng tiền tổ chức (Smart Money).

**6. PHÂN TÍCH RỦI RO**
- Rủi ro vĩ mô, lãi suất, tỷ giá hoặc đặc thù ngành.
- Rủi ro nội tại doanh nghiệp.
- Kịch bản rủi ro xấu nhất (Worst-case) và mức sụt giảm tiềm năng (% Drawdown).

**7. 3 KỊCH BẢN ĐẦU TƯ (6 - 12 THÁNG TỚI)**
- **Kịch bản Tích cực (Bull case):** Điều kiện kích hoạt, Giá mục tiêu (... k VND), Lợi nhuận kỳ vọng (+...%).
- **Kịch bản Cơ sở (Base case):** Điều kiện kích hoạt, Giá mục tiêu (... k VND), Lợi nhuận kỳ vọng (+...%).
- **Kịch bản Tiêu cực (Bear case):** Điều kiện kích hoạt, Mức giá giảm về (... k VND), Mức lỗ tiềm năng (-...%).

**8. KẾT LUẬN & BẢNG CHẤM ĐIỂM (THANG ĐIỂM 100)**
- Khung thời gian đầu tư phù hợp (Lướt sóng T+, Trung hạn 3-6 tháng, hay Nắm giữ 1 năm).
- Tỷ trọng khuyến nghị trong danh mục tổng thể.
- **BẢNG ĐIỂM CHI TIẾT:**
  + Chất lượng cơ bản: .../25 điểm
  + Tiềm năng tăng trưởng: .../20 điểm
  + Định giá hấp dẫn: .../20 điểm
  + Tín hiệu kỹ thuật & Dòng tiền: .../20 điểm
  + An toàn rủi ro (điểm càng cao rủi ro càng thấp): .../15 điểm
  ➔ **TỔNG ĐIỂM ĐÁNH GIÁ: .../100 ĐIỂM**

Quy chuẩn trình bày:
- TUYỆT ĐỐI CHỈ DÙNG 100% TIẾNG VIỆT CHUẨN UNICODE, KHÔNG LẪN BẤT KỲ KÝ TỰ TIẾNG TRUNG HOẶC TOKEN LỖI (ví dụ: viết 'biến động', tuyệt đối không viết 'biến动').
- Trình bày ngắn gọn, gãy gọn, số liệu định lượng rõ ràng, không nói chung chung.
- Sử dụng gạch đầu dòng rõ ràng, không dùng bảng markdown (|) để tránh vỡ giao diện."""

    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=prompt
    )
    return response.text


if __name__ == "__main__":
    print("=== KIỂM TRA PHÂN TÍCH VỚI GEMINI ===")
    portfolio = load_portfolio()
    df_eval = evaluate_portfolio(portfolio)
    news = fetch_macro_news()
    
    print("Đang gửi dữ liệu đến Gemini...")
    analysis = generate_portfolio_analysis(df_eval, news)
    print("\n--- BÁO CÁO PHÂN TÍCH TỪ GEMINI ---")
    print(analysis)

