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


def generate_portfolio_analysis(portfolio_df, news_items, custom_question: str = None) -> str:
    """
    Tạo báo cáo phân tích toàn diện kết hợp Danh mục, Chỉ báo Kỹ thuật và Tin tức Vĩ mô.
    """
    client = get_ai_client()

    portfolio_str = portfolio_df.to_string(index=False)
    news_str = "\n".join([f"- [{n['keyword'].upper()}] {n['title']}" for n in news_items[:6]])

    prompt = f"""Bạn là Chuyên gia Trưởng Ban Chiến lược Đầu tư Chứng khoán với hơn 15 năm kinh nghiệm thực chiến tại thị trường Việt Nam (HSX, HNX).
Dưới đây là dữ liệu giao dịch và trạng thái danh mục thực tế của Nhà đầu tư:

=== BẢNG TRẠNG THÁI DANH MỤC HIỆN TẠI ===
{portfolio_str}

=== TIN TỨC VĨ MÔ & NGÀNH NỔI BẬT TRONG 24H QUA ===
{news_str}

Nhiệm vụ của bạn:
1. **Đánh giá sức khỏe danh mục:** Nhận xét từng mã (BSR, MSB, SSI). Phân loại mã nào đang giữ nhịp tốt, mã nào rủi ro gãy nền cần lưu ý giá vốn.
2. **Tác động Tin vĩ mô & Ngành:** Tin tức về giá dầu, lãi suất, tỷ giá đang hỗ trợ hay tạo áp lực lên từng mã trong danh mục?
3. **Kịch bản hành động cụ thể (Rõ ràng từng mốc):**
   - **T+ (Ngắn hạn):** Điểm chốt lời ngắn hạn (Take Profit) và điểm quản trị rủi ro/cắt lỗ (Stop Loss) cụ thể theo giá thị trường.
   - **Trung hạn (3 - 6 tháng):** Chiến lược cơ cấu, gia tăng tỷ trọng hay hạ bớt.
4. **Ngành/Cổ phiếu tiềm năng:** Gợi ý ngắn gọn 1 nhóm ngành đang có dòng tiền hoặc hưởng lợi vĩ mô để chuẩn bị đón sóng.

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

    prompt = f"""Hãy đóng vai trò là một chuyên gia phân tích đầu tư chuyên nghiệp (CFA Charterholder / Senior Equity Research Analyst) với kinh nghiệm về phân tích cơ bản, phân tích kỹ thuật, định giá doanh nghiệp và quản trị rủi ro tại thị trường chứng khoán Việt Nam.

Dưới đây là toàn bộ dữ liệu tài chính, kỹ thuật và tin tức đã được thu thập cho cổ phiếu **{symbol}**:

=== DỮ LIỆU KỸ THUẬT & GIAO DỊCH ===
{tech_summary}

=== BÁO CÁO CHỈ SỐ TÀI CHÍNH & ĐỊNH GIÁ ===
{fin_summary}

=== TIN TỨC VĨ MÔ & LIÊN QUAN ===
{news_str}

Nhiệm vụ của bạn là đọc toàn bộ dữ liệu trên, kiểm tra tính đầy đủ, làm sạch dữ liệu nếu cần, sau đó thực hiện một phân tích toàn diện theo đúng 8 phần chuẩn mực sau:

**1. KIỂM TRA VÀ HIỂU DỮ LIỆU**
- Xác nhận các loại dữ liệu có trong bộ hồ sơ (báo cáo tài chính, chỉ số định giá, dữ liệu giao dịch kỹ thuật, tin tức).
- Nêu rõ các biến quan trọng còn thiếu (nếu có) và giả định hợp lý được sử dụng để phân tích.
- Đánh giá chất lượng và độ tin cậy của dữ liệu.

**2. PHÂN TÍCH CƠ BẢN VÀ KHẢ NĂNG SINH LỜI**
- Đánh giá tăng trưởng doanh thu và lợi nhuận qua các quý gần nhất.
- Phân tích biên lợi nhuận (biên gộp, biên ròng) và xu hướng thay đổi.
- Đánh giá hiệu quả sinh lời: ROE, ROA, ROIC thực tế.
- So sánh các chỉ số trên với trung bình ngành tại Việt Nam (benchmark ngành).
- Phân tích sức khỏe tài chính: cơ cấu nợ/vốn chủ sở hữu, đòn bẩy tài chính, khả năng thanh toán ngắn hạn (hệ số thanh toán hiện hành, thanh toán nhanh).

**3. PHÂN TÍCH ĐỊNH GIÁ**
- Đánh giá mức độ đắt/rẻ của cổ phiếu {symbol} dựa trên:
  + P/E hiện tại so với lịch sử và trung bình ngành.
  + P/B hiện tại so với lịch sử và trung bình ngành.
  + EV/EBITDA, P/S hoặc Giá/Dòng tiền.
- Ước lượng giá trị hợp lý (Fair Value) bằng ít nhất một phương pháp định giá rõ ràng (ví dụ: P/E mục tiêu hoặc P/B mục tiêu kết hợp DCF đơn giản hóa với giả định tăng trưởng cụ thể).
- Xác định biên an toàn (Margin of Safety) so với thị giá hiện tại.

**4. PHÂN TÍCH KỸ THUẬT VÀ XU HƯỚNG GIÁ**
- Xác định xu hướng giá hiện tại (ngắn hạn, trung hạn, dài hạn).
- Phân tích các đường trung bình động chính (MA20, MA50, MA100/200).
- Đánh giá chỉ báo động lượng: RSI(14) (quá mua, quá bán hay phân kỳ).
- Đánh giá biến động và vị thế giá quanh dải Bollinger Bands.
- Xác định các vùng hỗ trợ và kháng cự then chốt (k VND).
- Nhận diện các mẫu hình giá đáng chú ý (nếu có).

**5. PHÂN TÍCH HÀNH VI DÒNG TIỀN VÀ KHỐI LƯỢNG**
- Phân tích mối quan hệ giữa giá và khối lượng giao dịch (tỷ lệ Vol / SMA20).
- Nhận diện các dấu hiệu gom hàng (accumulation) hoặc phân phối (distribution) của tay to (Smart Money).
- Đánh giá tính thanh khoản của cổ phiếu.

**6. PHÂN TÍCH RỦI RO**
- Rủi ro ngành và vĩ mô (lãi suất, lạm phát, tỷ giá, chu kỳ kinh tế...).
- Rủi ro nội tại doanh nghiệp (áp lực nợ vay, suy giảm biên lợi nhuận, vấn đề quản trị...).
- Rủi ro thị trường chung và thanh khoản.
- Kịch bản rủi ro xấu nhất (Worst-case scenario) và mức độ sụt giảm tiềm năng (% drawdown).

**7. CÁC KỊCH BẢN ĐẦU TƯ (6 - 12 THÁNG TỚI)**
Xây dựng 3 kịch bản cụ thể cho cổ phiếu {symbol}:
- **Kịch bản tích cực (Bull case):** Điều kiện kích hoạt, giá mục tiêu (Target Price), tỷ suất sinh lời kỳ vọng (%).
- **Kịch bản cơ sở (Base case):** Điều kiện kích hoạt, giá mục tiêu, tỷ suất sinh lời kỳ vọng (%).
- **Kịch bản tiêu cực (Bear case):** Điều kiện kích hoạt, mức giá có thể giảm về, mức lỗ tiềm năng (%).

**8. KẾT LUẬN VÀ CHẤM ĐIỂM ĐẦU TƯ (THANG ĐIỂM 100)**
- Đưa ra khuyến nghị rõ ràng: **MUA MẠNH**, **MUA**, **THEO DÕI/NẮM GIỮ**, hoặc **BÁN**.
- Vùng giá mua khuyến nghị, giá mục tiêu (Target) và mức giá cắt lỗ (Stop-loss) cụ thể bằng con số (k VND).
- Khung thời gian đầu tư phù hợp (Lướt sóng ngắn hạn T+, Đầu tư trung hạn 3-6 tháng, hay Nắm giữ dài hạn 1 năm).
- Tỷ trọng phân bổ danh mục đề xuất (% tổng tài sản).
- **BẢNG CHẤM ĐIỂM CỔ PHIẾU TRÊN THANG ĐIỂM 100:**
  + Chất lượng cơ bản: .../25 điểm
  + Tiềm năng tăng trưởng: .../20 điểm
  + Định giá hấp dẫn: .../20 điểm
  + Tín hiệu kỹ thuật & Dòng tiền: .../20 điểm
  + Mức độ an toàn rủi ro (điểm càng cao rủi ro càng thấp): .../15 điểm
  -> **TỔNG ĐIỂM ĐÁNH GIÁ: .../100 ĐIỂM**

---
**TÓM TẮT NHANH (EXECUTIVE SUMMARY - ĐÚNG 5 DÒNG):**
1. Khuyến nghị: [MUA MẠNH / MUA / THEO DÕI / BÁN]
2. Vùng giá mua gom: [...] k VND
3. Giá mục tiêu: [...] k VND (Tiềm năng: +...%)
4. Ngưỡng cắt lỗ: [...] k VND (Rủi ro: -...%)
5. Điểm số tổng hợp: .../100 Điểm

Yêu cầu trình bày:
- Cấu trúc chuyên nghiệp, lập luận chặt chẽ như báo cáo phân tích định chế quỹ đầu tư.
- Mọi nhận định định lượng cần có số liệu đi kèm, không đưa ra kết luận chung chung.
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

