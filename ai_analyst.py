import json
import logging
import os
import re

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass
from google import genai

from data_engine import evaluate_portfolio, fetch_macro_news, load_portfolio
from quant_engine import evaluate_holding_position, evaluate_market_regime
from quant_sanity_check import validate_holding_position, validate_trade_setup
from quant_valuation import calculate_fair_value_and_mos

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


def call_gemini(client, prompt: str, max_retries: int = 3, retry_delay: float = 2.0) -> str:
    """
    Gọi Gemini API với System Language Rule tích hợp sẵn ở cả đầu và cuối prompt,
    tích hợp cơ chế retry tự động chống timeout/rate-limit,
    sau đó tự động lọc qua sanitize_ai_text để đảm bảo đầu ra sạch 100%.
    """
    import time
    full_prompt = f"{SYSTEM_LANGUAGE_RULE}\n\n{prompt}\n\n{SYSTEM_LANGUAGE_RULE}"
    last_err = None
    for attempt in range(1, max_retries + 1):
        try:
            response = client.models.generate_content(
                model=MODEL_NAME,
                contents=full_prompt
            )
            return sanitize_ai_text(response.text)
        except Exception as e:
            last_err = e
            logging.warning("[Gemini API] Lần gọi %d/%d thất bại: %s", attempt, max_retries, e)
            if attempt < max_retries:
                time.sleep(retry_delay * attempt)
    logging.exception("[Gemini API] Toàn bộ %d lần gọi Gemini thất bại: %s", max_retries, last_err)
    raise RuntimeError(f"Gemini API generation failed after {max_retries} attempts: {last_err}") from last_err


async def async_call_gemini(client, prompt: str, max_retries: int = 3, retry_delay: float = 2.0) -> str:
    """
    Gọi Gemini API bất đồng bộ (asyncio) qua client.aio.models.generate_content.
    Tích hợp cơ chế retry tự động với exponential backoff không block event loop.
    """
    import asyncio
    full_prompt = f"{SYSTEM_LANGUAGE_RULE}\n\n{prompt}\n\n{SYSTEM_LANGUAGE_RULE}"
    last_err = None
    for attempt in range(1, max_retries + 1):
        try:
            response = await client.aio.models.generate_content(
                model=MODEL_NAME,
                contents=full_prompt
            )
            return sanitize_ai_text(response.text)
        except Exception as e:
            last_err = e
            logging.warning("[Gemini Async API] Lần gọi %d/%d thất bại: %s", attempt, max_retries, e)
            if attempt < max_retries:
                await asyncio.sleep(retry_delay * attempt)
    logging.exception("[Gemini Async API] Toàn bộ %d lần gọi Gemini thất bại: %s", max_retries, last_err)
    raise RuntimeError(f"Async Gemini API generation failed after {max_retries} attempts: {last_err}") from last_err


def get_ai_client():
    if not GEMINI_API_KEY:
        raise ValueError("Chưa cấu hình GEMINI_API_KEY trong file .env!")
    return genai.Client(api_key=GEMINI_API_KEY)


def _build_portfolio_quant_summary(portfolio_df) -> str:
    """Build pre-computed quantitative and sanity check summary lines for portfolio."""
    if portfolio_df is None or portfolio_df.empty:
        return "Chưa có mã nào trong danh mục."

    lines = []
    for _, row in portfolio_df.iterrows():
        sym = str(row.get("symbol", row.get("Mã CP", ""))).upper()
        entry_p = float(row.get("avg_price", row.get("Giá vốn (k)", 0.0)))
        curr_p = float(row.get("market_price", row.get("Thị giá (k)", entry_p)))
        pl_p = ((curr_p - entry_p) / entry_p * 100) if entry_p > 0 else 0.0

        mock_tech = {
            "current_price": curr_p,
            "atr": float(row.get("atr", 0.0)) if "atr" in row else (curr_p * 0.025),
            "ma20": float(row.get("ma20", curr_p)) if "ma20" in row else curr_p,
        }
        eval_res = evaluate_holding_position(row.to_dict(), mock_tech)
        _, _, eval_res = validate_holding_position(eval_res)

        if eval_res["is_profit"]:
            lines.append(
                f"• **{sym}** | Giá vốn: {entry_p:.2f}k | Thị giá ATC: {curr_p:.2f}k | Lãi: +{pl_p:.1f}% | "
                f"Hành động: {eval_res['action']} | 🛡️ MỐC TRAILING STOP BẢO VỆ LÃI: **{eval_res['trailing_stop']:.2f}k** | "
                f"Chi tiết: {eval_res['detail']}"
            )
        else:
            lines.append(
                f"• **{sym}** | Giá vốn: {entry_p:.2f}k | Thị giá ATC: {curr_p:.2f}k | Lỗ: {pl_p:.1f}% | "
                f"Hành động: {eval_res['action']} | 🛡️ MỐC STOP-LOSS KỸ THUẬT: **{eval_res['stop_loss']:.2f}k** | "
                f"Thesis Breaker: {eval_res['thesis_breaker']} | Chi tiết: {eval_res['detail']}"
            )
    return "\n".join(lines) if lines else "Chưa có mã nào trong danh mục."


def _format_news_summary(news_items, limit: int = 8) -> str:
    """Format news items into concise summary lines for LLM context."""
    if not news_items:
        return "Không có tin tức mới."
    lines = []
    for n in (news_items or [])[:limit]:
        tag = n.get("tag", n.get("keyword", "TIN TỨC")).upper()
        line = f"- [{tag}] {n['title']}"
        if n.get("summary"):
            line += f" | Tóm tắt: {n['summary'][:160]}..."
        if n.get("matched_symbols"):
            line += f" | 🔥 Trực tiếp tác động: {', '.join(n['matched_symbols'])}"
        lines.append(line)
    return "\n".join(lines) if lines else "Không có tin tức mới."


def generate_portfolio_analysis(portfolio_df, news_items, watchlist_df=None, vnindex_tech=None, custom_question: str = None) -> str:
    """
    🎯 BÁO CÁO TỔNG KẾT PHIÊN ATC (15:00) - AI STOCK COPILOT V2.1:
    - Triết lý: Value-First + Technical Timing.
    - Bắt buộc trả lời 5 câu hỏi cốt tử.
    - Định lượng 100% bằng Python: Cổ phiếu LÃI kích hoạt TRAILING STOP cụ thể, TUYỆT ĐỐI KHÔNG DÙNG TỪ CẮT LỖ.
    - Chạy Sanity Check Engine kiểm toán tính nhất quán toán học trước khi render.
    """
    from quant_engine import evaluate_market_regime
    client = get_ai_client()

    quant_eval_str = _build_portfolio_quant_summary(portfolio_df)
    portfolio_str = portfolio_df.to_string(index=False) if portfolio_df is not None and not portfolio_df.empty else "Chưa có dữ liệu."
    watchlist_str = watchlist_df.to_string(index=False) if watchlist_df is not None and not watchlist_df.empty else ""
    news_str = _format_news_summary(news_items, limit=8)
    
    regime_data = evaluate_market_regime(vnindex_tech) if vnindex_tech else {"tag": "N/A", "stock_pct": "70%", "cash_pct": "30%", "max_stock_nav": 100, "bias": "Neutral"}

    prompt = f"""Bạn là Giám đốc Quản trị Rủi ro & Chiến lược Danh mục Đầu tư (Senior Portfolio Manager) theo trường phái Value-First + Technical Timing.
Bây giờ là 15:00 CHIỀU - phiên giao dịch chứng khoán vừa khép lại tại ATC.

=== 1. TÍNH TOÁN ĐỊNH LƯỢNG TẤT ĐỊNH CỦA HỆ THỐNG PYTHON CHO DANH MỤC ===
{quant_eval_str}
- TỶ TRỌNG PHÂN BỔ ĐỀ XUẤT (THEO RISK BUDGET): Cổ phiếu {regime_data['stock_pct']} | Tiền mặt {regime_data['cash_pct']} (Hạn mức tối đa: {regime_data['max_stock_nav']}% NAV)

=== 2. BẢNG TRẠNG THÁI GIAO DỊCH THỰC TẾ ===
{portfolio_str}
"""
    if watchlist_str:
        prompt += f"""
=== 3. DANH SÁCH THEO DÕI (WATCHLIST) ===
{watchlist_str}
"""

    prompt += f"""
=== 4. TIN TỨC VĨ MÔ & DOANH NGHIỆP TRONG PHIÊN (CAFEF) ===
{news_str}

QUY TẮC CỐT TỬ KHÔNG ĐƯỢC VI PHẠM (MATHEMATICAL SANITY RULES):
1. ĐỐI VỚI VỊ THẾ ĐANG CÓ LÃI (P/L > 0): TUYỆT ĐỐI KHÔNG DÙNG TỪ "CẮT LỖ". Bắt buộc gọi là "CHỐT LỜI TỪNG PHẦN / BẢO VỆ THÀNH QUẢ" và ghi rõ con số Mốc Trailing Stop do Python đã tính toán.
2. TRAILING STOP BẮT BUỘC PHẢI NHỎ HƠN THỊ GIÁ ATC (Stop < Current Price). Không bao giờ có chuyện giá 12.80 mà chặn lãi 12.84!
3. ĐỐI VỚI VỊ THẾ ĐẦU TƯ GIÁ TRỊ ĐANG LỖ: Đánh giá bằng "Thesis Breaker" (luận điểm doanh nghiệp có bị vỡ không), không đưa ra quyết định cắt lỗ hoảng loạn theo biến động kỹ thuật ngắn hạn.
4. BẮT BUỘC TRẢ LỜI ĐỦ 5 CÂU HỎI CỐT TỬ CỦA NHÀ ĐẦU TƯ TRONG PHẦN TỔNG KẾT:
   - Câu hỏi 1: Danh mục hôm nay tăng/giảm do đâu? (Bóc tách dòng tiền, nhóm ngành, tin tức).
   - Câu hỏi 2: Cổ phiếu nào còn rẻ, cổ phiếu nào chạm định giá? (Tham chiếu Fair Value và Margin of Safety).
   - Câu hỏi 3: Vị thế nào cần chốt lời từng phần và nâng Trailing Stop? (Nêu rõ mốc giá cụ thể do Python đã tính).
   - Câu hỏi 4: Vị thế nào bị suy giảm luận điểm (Thesis Breaker) cần dứt khoát cơ cấu?
   - Câu hỏi 5: Tỷ trọng tiền mặt hiện tại đã an toàn chưa? Đề xuất tỷ lệ Tiền/Cổ phiếu tối ưu dựa trên Risk Budgeting.

Yêu cầu trình bày báo cáo tổng kết phiên:
**I. TỔNG KẾT PHIÊN ATC & ĐÁNH GIÁ 5 CÂU HỎI CỐT TỬ**
BẮT BUỘC sử dụng đúng định dạng danh sách dưới đây, không được bỏ sót câu nào:
- **Câu hỏi 1 (Nguyên nhân biến động):** [Trả lời ngắn gọn]
- **Câu hỏi 2 (Định giá & MoS):** [Trả lời ngắn gọn]
- **Câu hỏi 3 (Chốt lời & Trailing Stop):** [Trả lời ngắn gọn]
- **Câu hỏi 4 (Thesis Breaker):** [Trả lời ngắn gọn]
- **Câu hỏi 5 (Tỷ trọng Tiền/Cổ phiếu):** [Trả lời ngắn gọn dựa trên tỷ lệ Tiền mặt đề xuất]**II. CHI TIẾT DANH MỤC & HÀNH ĐỘNG QUẢN TRỊ RỦI RO**
- Trình bày từng mã đang nắm giữ:
  • Cổ phiếu **[MÃ]** ([Ngành]) — [HUY HIỆU: 🟢 BẢO VỆ THÀNH QUẢ / NÂNG TRAILING STOP hoặc 🔴 THOÁT VỊ THẾ / THESIS BREAKER]:
    - **Giá vốn:** ...k | **Thị giá ATC:** ...k | **P/L:** ...%
    - **Hành động cụ thể:** [Chốt lời 30-50% hay tiếp tục nắm giữ]
    - **Mốc Trailing Stop bảo vệ lãi (hoặc Stop-loss):** [Ghi con số giá cụ thể do Python đã tính]
    - **Đánh giá Luận điểm cơ bản (Thesis):** [Tình trạng doanh nghiệp]

**III. TÁC ĐỘNG VĨ MÔ & DÒNG TIỀN TỰ DOANH / NGOẠI**
- Đánh giá động thái mua/bán ròng và tin tức CafeF hôm nay.

**IV. KẾ HOẠCH HÀNH ĐỘNG CHO PHIÊN KẾ TIẾP**
- Tỷ trọng phân bổ đề xuất: % Tiền mặt / % Cổ phiếu.
- Điều kiện thị trường để kích hoạt giải ngân mới.

Định dạng Discord/Web:
- KHÔNG dùng bảng markdown (|---|).
- KHÔNG dùng dấu `###`.
- BẮT BUỘC IN ĐẬM TẤT CẢ MÃ CỔ PHIẾU (**SSI**, **BSR**, **MSB**, **HPG**, **MWG**, **FPT**...).
- Dùng gạch đầu dòng phân cấp.
"""

    if custom_question:
        prompt += f"\n\n[CÂU HỎI BỔ SUNG CỦA NHÀ ĐẦU TƯ]: {custom_question}\nHãy trả lời chi tiết trọng tâm câu hỏi này."

    result = call_gemini(client, prompt)
    
    # Sanity Check Hậu kiểm
    if "Câu hỏi 5" not in result and "Câu 5" not in result:
        result = result.replace("📌 II.", f"- **Câu hỏi 5 (Tỷ trọng Tiền/Cổ phiếu):** Tỷ trọng phân bổ đề xuất hiện tại là Cổ phiếu {regime_data['stock_pct']} / Tiền mặt {regime_data['cash_pct']} để đảm bảo an toàn danh mục.\n\n📌 II.")
        
    return result


def generate_morning_strategy_report(portfolio_df, watchlist_df, opportunities: list, news_items: list, vnindex_tech: dict = None) -> str:
    """
    🎯 BÁO CÁO CHIẾN LƯỢC ĐẦU NGÀY 08:45 (VALUE-FIRST + TECHNICAL TIMING) - CHUẨN V2.1:
    - Nhận diện Market Regime & Risk Budgeting đa biến (Trend + Breadth + Liquidity + Drawdown + Margin).
    - 4 Trạng thái chuẩn: 🟢 MUA, 🟢 TÍCH LŨY, 🟡 THEO DÕI, 🔴 GIẢM / THOÁT.
    - Phân tách rõ ràng Fair Value (Nội tại) vs Price Target (Kỳ vọng thời gian).
    - Đi kèm Mô hình định giá (Methodology) & Độ tin cậy (Confidence).
    - R:R tính chuẩn xác từ cùng một Weighted Average Entry.
    - Cổ phiếu có MoS >= 8% nhưng Kỹ thuật yếu (như MWG) chuyển thành WATCH / WAIT FOR CONFIRMATION, tuyệt đối cấm gán TRÁNH BẪY!
    """
    client = get_ai_client()

    # Kéo số liệu VN-Index thực tế nếu chưa được truyền vào
    if not vnindex_tech:
        try:
            from data_engine import fetch_stock_technical
            vnindex_tech = fetch_stock_technical("VNINDEX")
        except Exception:
            vnindex_tech = {}

    idx_price = vnindex_tech.get("current_price", 0.0)
    idx_chg = vnindex_tech.get("change_pct", 0.0)
    idx_ma20 = vnindex_tech.get("ma20", 0.0)
    idx_ma50 = vnindex_tech.get("ma50", 0.0)
    idx_rsi = vnindex_tech.get("rsi14", 0.0)
    idx_status = vnindex_tech.get("status_ma20", "")

    # Đánh giá Market Regime & Ngân sách Rủi ro Đa biến (Risk Budgeting)
    regime_data = evaluate_market_regime(vnindex_tech)

    p_str = portfolio_df.to_string(index=False) if portfolio_df is not None and not portfolio_df.empty else "Chưa có mã nắm giữ."
    w_str = watchlist_df.to_string(index=False) if watchlist_df is not None and not watchlist_df.empty else "Chưa có mã trong Watchlist."

    idx_context = f"""=== 0. DỮ LIỆU THỊ TRƯỜNG & RISK BUDGETING (CẬP NHẬT TỨC THỜI) ===
- Điểm số đóng cửa phiên gần nhất: {idx_price:.2f} điểm (Thay đổi: {idx_chg:+.2f}%)
- Đường MA20 ngày: {idx_ma20:.2f} điểm (Trạng thái: {idx_status})
- Đường MA50 ngày: {idx_ma50:.2f} điểm | RSI(14): {idx_rsi}
- TRẠNG THÁI THỊ TRƯỜNG (MARKET REGIME): {regime_data['tag']}
- TỶ TRỌNG PHÂN BỔ ĐỀ XUẤT (THEO RISK BUDGET): Cổ phiếu {regime_data['stock_pct']} | Tiền mặt {regime_data['cash_pct']} (Hạn mức tối đa: {regime_data['max_stock_nav']}% NAV)
- ĐỊNH HƯỚNG QUẢN TRỊ RỦI RO: {regime_data['bias']} (Ưu tiên phòng thủ: {regime_data['defense_priority']})
"""

    # Defensive Deduplication Gate: Guarantee every candidate ticker is processed at most once
    seen_opp_symbols = set()
    deduped_opportunities = []
    for o in opportunities:
        sym_check = (o.get("symbol") or "").strip().upper()
        if sym_check and sym_check not in seen_opp_symbols:
            seen_opp_symbols.add(sym_check)
            deduped_opportunities.append(o)
    opportunities = deduped_opportunities

    buy_lines = []
    watch_lines = []
    caution_lines = []

    for o in opportunities:
        sym = o.get("symbol", "")
        # Lấy định giá Fair Value, Methodology, Confidence và Price Target
        val_res = calculate_fair_value_and_mos(symbol=sym, current_price=o.get("current_price", 0.0), sector=o.get("sector", ""))
        fv = val_res.get("fair_value", o.get("fair_value", 0.0))
        mos = val_res.get("mos_pct", o.get("mos_pct", 0.0))
        val_method = val_res.get("valuation_method", o.get("valuation_method", "N/A"))
        val_conf = val_res.get("confidence", o.get("confidence", "MEDIUM"))
        p_target = val_res.get("price_target") or o.get("target_price") or round(fv * 1.05, 2)

        status = o.get("status", "")
        avg_entry = o.get("avg_cost", o.get("current_price", 0.0))
        stop = o.get("stop_loss", round(avg_entry * 0.93, 2))

        # SANITY CHECK CHO R:R THEO WEIGHTED ENTRY
        setup_dict = {
            "weighted_entry": avg_entry,
            "target_price": p_target,
            "stop_loss": stop,
            "risk_reward": o.get("risk_reward", 1.5)
        }
        _, _, clean_setup = validate_trade_setup(setup_dict)
        rr = clean_setup["risk_reward"]

        if status == "RECOMMEND_BUY":
            act = "🟢 VALUE BUY" if mos >= 15.0 and o.get("current_price", 0) >= o.get("ma20", 0) else "🟢 ACCUMULATE"
            dq_badge = o.get("data_badge") or (f"📊 Data Quality: {o.get('data_quality', 'HIGH')}" if o.get("data_quality") else "")
            dq_line = f"  - **Độ tin cậy dữ liệu:** {dq_badge}\n" if dq_badge else ""
            buy_lines.append(
                f"• Mã: **{sym}** ({o.get('sector', 'Niêm yết')}) — {act}\n"
                f"{dq_line}"
                f"  - **Giá trị hợp lý (Fair Value):** {fv:.2f}k | **Mô hình định giá:** {val_method} (Độ tin cậy: {val_conf})\n"
                f"  - **Biên an toàn (MoS):** {mos:+.1f}% | **Mục tiêu giá (Target 6-12T):** {p_target:.2f}k\n"
                f"  - **Vùng gom:** {o.get('entry_zone', o.get('current_price'))}k | **Giá vốn BQ dự kiến (Weighted Entry):** {avg_entry:.2f}k\n"
                f"  - **Ngưỡng dừng lỗ:** {stop:.2f}k | **Tỷ lệ R:R chuẩn:** {rr:.1f}x (tính trên Giá vốn BQ {avg_entry:.2f}k)\n"
                f"  - **Kế hoạch giải ngân:** {o.get('execution_plan', 'Chia 2-3 phần')}\n"
                f"  - **Luận điểm & Xúc tác:** [{o.get('story_tag')}] {o.get('story')}"
            )
        elif status == "CAUTION_TRAP":
            caution_lines.append(
                f"• Mã: **{sym}** ({o.get('sector', 'Niêm yết')}) — ⛔ **[ĐỨNG NGOÀI / TRÁNH BẪY]**\n"
                f"  - **Thị giá:** {o['current_price']}k | **Cảnh báo rủi ro:** {o.get('rationale')}"
            )
        else:
            # WATCH_CONFIRMATION hoặc mã cơ bản tốt nhưng kỹ thuật yếu -> WATCH / WAIT FOR CONFIRMATION
            watch_lines.append(
                f"• Mã: **{sym}** ({o.get('sector', 'Niêm yết')}) — 🟡 **[THEO DÕI / CHỜ NỀN CÂN BẰNG]**\n"
                f"  - **Giá trị hợp lý (Fair Value):** {fv:.2f}k | **Mô hình:** {val_method} ({val_conf})\n"
                f"  - **Biên an toàn (MoS):** {mos:+.1f}% | **Mục tiêu giá:** {p_target:.2f}k | **Thị giá hiện tại:** {o.get('current_price')}k\n"
                f"  - **Lý do theo dõi:** {o.get('setup_type', 'Chờ xác nhận')} — {o.get('rationale', 'Định giá và cơ bản đạt chuẩn nhưng giá cần tích lũy thêm trên MA20. Tuyệt đối không mua vội, chờ tín hiệu dòng tiền.')}"
            )

    buy_str = "\n".join(buy_lines) if buy_lines else "Thị trường chưa có mã nào đạt đồng thời Biên an toàn (MoS >= 15%) và tín hiệu kỹ thuật ổn định."
    watch_str = "\n".join(watch_lines) if watch_lines else "Không có mã nào trong diện chờ xác nhận nền."
    caution_str = "\n".join(caution_lines) if caution_lines else "Không có mã nào rơi vào diện cảnh báo bẫy tin."

    news_lines = []
    for n in news_items[:6]:
        news_lines.append(f"- [{n.get('tag', 'TIN').upper()}] {n['title']}")
    news_str = "\n".join(news_lines)

    prompt = f"""Bạn là Giám đốc Chiến lược Đầu tư Định chế (Institutional Investment Strategist).
Bây giờ là 08:45 SÁNG - chuẩn bị bước vào phiên giao dịch ATO của thị trường chứng khoán Việt Nam.
Hãy xuất bản bản tin "CHIẾN LƯỢC PHIÊN HÔM NAY & KHUYẾN NGHỊ ĐẦU NGÀY (VALUE-FIRST + TECHNICAL TIMING)":

{idx_context}

=== 1. DANH MỤC HIỆN TẠI CỦA NHÀ ĐẦU TƯ ===
{p_str}

=== 2. DANH SÁCH THEO DÕI (WATCHLIST) ===
{w_str}

=== 3. CƠ HỘI ĐẠT CHUẨN ĐỊNH LƯỢNG (BIÊN AN TOÀN + KỸ THUẬT CHO PHÉP - TỐI ĐA 1-2 MÃ MUA) ===
{buy_str}

=== 4. CỔ PHIẾU CƠ BẢN TỐT CẦN THEO DÕI CHỜ NỀN (WATCH / WAIT FOR CONFIRMATION - CHỈ QUAN SÁT) ===
{watch_str}

=== 5. CẢNH BÁO BẪY PHÂN PHỐI & RỦI RO CAO (CAUTION - TRÁNH BẮT ĐÁY) ===
{caution_str}

=== 6. ĐIỂM TIN VĨ MÔ SÁNG NAY (CAFEF) ===
{news_str}

QUY TẮC CỐT TỬ KHÔNG ĐƯỢC VI PHẠM (MATHEMATICAL CONSISTENCY & UX CLARITY):
1. R:R PHẢI DÙNG ĐÚNG GIÁ VỐN BQ DỰ KIẾN (WEIGHTED AVERAGE ENTRY) ĐÃ CÔNG BỐ. Tuyệt đối không tính R:R từ Current Price nếu kế hoạch vào lệnh chia 3 bước!
2. FAIR VALUE VÀ PRICE TARGET PHẢI TÁCH BIỆT NHAU: Fair Value là giá trị hợp lý nội tại (kèm Mô hình định giá và Độ tin cậy), Target là mục tiêu giá theo khung thời gian đầu tư 6-12T.
3. PHÂN TÁCH BẠCH RÕ RÀNG 3 NHÓM (TRÁNH GÂY NHẦM LẪN CHO NHÀ ĐẦU TƯ):
   - Nhóm Mua chỉ tối đa 1-2 mã thực sự xuất sắc đạt chuẩn.
   - Nhóm Theo Dõi (Watchlist) TUYỆT ĐỐI KHÔNG khuyến nghị Mua vội, phải ghi rõ 'Chờ nền cân bằng'.
   - Nhóm Cảnh Báo ghi rõ 'Đứng ngoài / Tránh bẫy'.
4. TỶ TRỌNG CỔ PHIẾU PHẢI DỰA TRÊN RISK BUDGETING ĐA BIẾN (không tự động ép 70-80% khi Bullish).

Yêu cầu xuất bản & Cấu trúc 4 phần chuẩn mực:
**I. BỐI CẢNH VĨ MÔ & TRẠNG THÁI THỊ TRƯỜNG (MARKET REGIME & RISK BUDGET)**
- Nêu rõ Trạng thái: {regime_data['tag']}.
- Phân bổ đề xuất: {regime_data['stock_pct']} Cổ phiếu / {regime_data['cash_pct']} Tiền mặt (Hạn mức tối đa {regime_data['max_stock_nav']}% NAV).
- Phân tích điểm số VN-Index ({idx_price:.2f}), mốc hỗ trợ MA20 ({idx_ma20:.2f})/MA50 ({idx_ma50:.2f}).

**II. CƠ HỘI ĐẦU TƯ & RADAR THEO DÕI (PHÂN TÁCH 3 NHÓM RÕ RÀNG)**
Trình bày rõ ràng thành 3 tiểu mục riêng biệt để người đọc không bao giờ nhầm lẫn giữa Mua và Theo dõi:

**A. 🟢 KHUYẾN NGHỊ MUA MỚI / TÍCH LŨY (TỐI ĐA 1-2 MÃ ĐẠT CHUẨN)**
(Chỉ lấy mã từ Mục 3 phía trên, nếu không có mã nào thì ghi rõ: "Phiên nay không khuyến nghị mở mua mới để bảo toàn sức mua")
(Với mỗi mã khuyến nghị Mua, áp dụng quy trình Hội đồng Đầu tư 5 vai trò & Tự phản biện Red Team):
• Cổ phiếu **[MÃ]** ([Ngành]) — [🟢 VALUE BUY hoặc 🟢 ACCUMULATE]
  - **Độ tin cậy dữ liệu:** [Trích xuất Data Quality từ hệ thống]
  - **Giá trị hợp lý (Fair Value):** ...k (Mô hình: ... | Độ tin cậy: ...) | **Mục tiêu giá:** ...k
  - **Biên an toàn (MoS):** ...% | **Vùng gom:** ...k
  - **Giá vốn BQ dự kiến (Weighted Entry):** ...k | **Kế hoạch giải ngân:** ...
  - **Dừng lỗ:** ...k | **Tỷ lệ R:R:** ...x (tính trên Giá vốn BQ)
  - **Góc nhìn FA & TA:** [Đánh giá chất lượng cơ bản + Động lượng kỹ thuật]
  - **Phản biện Red Team (3 câu cốt lõi):** Điểm yếu nhất? Nếu bỏ catalyst còn vững? Kịch bản downside & xác suất?
  - **Phán quyết PM:** [STRONG_OPPORTUNITY hoặc ATTRACTIVE] — Lý do hành động ngay (Why Now).

**B. 🟡 RADAR THEO DÕI CHỜ NỀN (CHƯA PHẢI ĐIỂM MUA - QUAN SÁT TÍCH LŨY)**
(Lấy từ Mục 4 phía trên. Nhắc nhở nhà đầu tư kiên nhẫn, không mua bắt dao rơi)

**C. ⛔ CẢNH BÁO PHÒNG THỦ & TRÁNH BẪY (CAUTION)**
(Lấy từ Mục 5 phía trên. Tuyệt đối đứng ngoài các mã phân phối/bẫy tin)

**III. KỊCH BẢN HÀNH ĐỘNG TRONG PHIÊN (BULL / BASE / BEAR)**
- Kịch bản Bull (Hưng phấn ATO): Hành động gì? (Cấm FOMO mua đuổi).
- Kịch bản Base (Giằng co tích lũy): Giải ngân từng phần theo đúng lộ trình.
- Kịch bản Bear (Áp lực bán tháo/Rung lắc mạnh): Kỷ luật quản trị rủi ro.

**IV. KỶ LUẬT QUẢN TRỊ RỦI RO & BẢO TOÀN VỐN**
- Cảnh báo bẫy giá rơi (Falling Knife): Rẻ vẫn phải đợi nền cân bằng.
- Không dùng margin trong vùng thị trường nhạy cảm.

Định dạng Discord/Web:
- KHÔNG dùng bảng markdown (|---|).
- KHÔNG dùng dấu `###`.
- BẮT BUỘC IN ĐẬM TẤT CẢ MÃ CỔ PHIẾU (**SSI**, **BSR**, **MSB**, **HPG**, **MWG**, **FPT**, **VIC**...).
- Dùng gạch đầu dòng phân cấp.
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
    from data_engine import fetch_macro_news, fetch_stock_technical, get_financial_ratios
    from quant_engine import (
        calculate_altman_z_score,
        calculate_piotroski_f_score,
        calculate_valuation_triangle,
        check_data_gate,
        evaluate_decision_hard_gates,
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

    # TỰ ĐỘNG LƯU SNAPSHOT BẤT BIẾN VÀO SUPABASE (SIGNAL LIFECYCLE)
    try:
        from db_manager import save_quant_signal
        save_quant_signal(
            symbol=symbol,
            action=hard_gates.get("action_state", "🟡 THEO DÕI"),
            decision_tag=hard_gates.get("decision_tag", ""),
            entry_price=curr_price,
            market_price_at_signal=curr_price,
            target_price=hard_gates.get("price_target"),
            stop_loss=hard_gates.get("stop_loss"),
            hard_gates=hard_gates,
            f_score_res=f_score_res,
            z_score_res=z_score_res,
            prob_dict=prob_dict,
            model_version=f"{MODEL_NAME}-v2.1",
            input_snapshot={
                "pe": pe,
                "pb": pb,
                "roe": fin_data.get("roe"),
                "debt_equity": fin_data.get("debt_equity"),
                "adv20_billion": tech_data.get("adv20_billion"),
                "rsi14": tech_data.get("rsi14"),
                "status_ma20": tech_data.get("status_ma20")
            }
        )
    except Exception as db_err:
        logging.warning(f"Không thể lưu snapshot tín hiệu vào Supabase: {db_err}")

    return {
        "status": "SUCCESS",
        "report_text": final_report,
        "hard_gates": hard_gates,
        "f_score": f_score_res,
        "z_score": z_score_res,
        "data_gate": gate
    }


VALID_PM_STATES = (
    "STRONG_OPPORTUNITY", "ATTRACTIVE", "WATCHLIST", "WAIT_BETTER_ENTRY",
    "HOLD_MAINTAIN", "RISK_ELEVATED", "AVOID", "INSUFFICIENT_DATA"
)


def _resolve_input_data(symbol: str, tech_data: dict = None, fin_data: dict = None, news_items: list = None):
    """Resolve default technical, financial, and news data if not supplied."""
    sym = (symbol or "").strip().upper()
    resolved_tech = tech_data
    if resolved_tech is None:
        try:
            from data_engine import fetch_stock_technical
            resolved_tech = fetch_stock_technical(sym)
        except Exception:
            resolved_tech = {}

    resolved_fin = fin_data
    if resolved_fin is None:
        try:
            from data_engine import get_financial_ratios
            resolved_fin = get_financial_ratios(sym)
        except Exception:
            resolved_fin = {}

    resolved_news = news_items
    if resolved_news is None:
        try:
            from data_engine import fetch_macro_news
            resolved_news = fetch_macro_news(limit=6, tracked_symbols=[sym])
        except Exception:
            resolved_news = []

    return sym, resolved_tech, resolved_fin, resolved_news


def _format_z_score(z_raw, zone: str):
    """Safely format Altman Z-score value."""
    if z_raw is None:
        return "N/A", "N/A (Chưa đủ BCTC)"
    try:
        val_str = f"{float(z_raw):.2f}"
    except (ValueError, TypeError):
        val_str = str(z_raw)
    return val_str, f"{val_str} ({zone})"


def _format_committee_prompt_context(
    sym: str,
    tech_data: dict,
    gate_res: dict,
    val_res: dict,
    f_score_res: dict,
    z_score_res: dict,
    news_items: list
) -> str:
    """Format prompt string for smart compressed investment committee analysis."""
    from data_gate import format_data_quality_badge

    curr_price = float(tech_data.get("current_price", 0.0))
    ma20_val = tech_data.get("ma20")
    ma50_val = tech_data.get("ma50")
    rsi_val = tech_data.get("rsi14")
    vol_val = tech_data.get("vol_ratio")

    ma20_str = f"{ma20_val}k" if ma20_val is not None else "N/A"
    ma50_str = f"{ma50_val}k" if ma50_val is not None else "N/A"
    rsi_str = f"{rsi_val}" if rsi_val is not None else "N/A"
    vol_str = f"{vol_val}x" if vol_val is not None else "N/A"

    fv = val_res.get("fair_value", curr_price * 1.10)
    mos = val_res.get("mos_pct", 0.0)
    val_method = val_res.get("valuation_method", "P/B")
    val_conf = val_res.get("confidence", "MEDIUM")

    p_target = val_res.get("price_target") or round(fv * 1.05, 2)
    stop_loss = round(curr_price * 0.93, 2) if curr_price > 0 else 0.0
    upside = max(0.0, p_target - curr_price)
    downside = max(0.1, curr_price - stop_loss)
    rr = round(upside / downside, 2) if downside > 0 else 1.5

    data_badge_str = format_data_quality_badge(gate_res)

    news_text = "Không có tin đột biến."
    if news_items:
        news_text = "; ".join([n.get("title", "") for n in news_items[:3] if n.get("title")])

    f_raw = f_score_res.get("score")
    if f_raw is not None:
        f_val_str = f"{f_raw}/9 ({f_score_res.get('rating', 'Khỏe')})"
        f_eval = f"{f_raw}"
    else:
        f_val_str = "N/A (Chưa đủ BCTC)"
        f_eval = "N/A"

    z_raw = z_score_res.get("z_score")
    z_eval, z_val_str = _format_z_score(z_raw, z_score_res.get("zone", "Vùng an toàn"))

    return f"""Bạn là Investment Committee (Hội đồng Đầu tư Định chế) gồm 5 vai trò chuyên môn:
1. Chuyên gia Phân tích Cơ bản (FA Analyst)
2. Chuyên gia Kỹ thuật & Định thời điểm (TA & Timing Specialist)
3. Chuyên gia Vĩ mô & Động lực Ngành (Macro & Catalyst Strategist)
4. Đội Phản biện Đối kháng (Red Team Contrarian Auditor)
5. Giám đốc Quản lý Danh mục (Portfolio Manager - PM)

Hãy thực hiện phân tích TUẦN TỰ cho cổ phiếu **{sym}**:

=== DỮ LIỆU ĐÃ KIỂM CHỨNG BỞI PYTHON DETERMINISTIC (PHASE 0 - 2) ===
- Mã cổ phiếu: **{sym}**
- {data_badge_str}
- Thị giá: {curr_price}k VND | MA20: {ma20_str} | MA50: {ma50_str} | RSI(14): {rsi_str} | Vol/SMA20: {vol_str}
- Định giá Fair Value: {fv:.2f}k VND (Mô hình: {val_method}, Độ tin cậy: {val_conf}) | Biên an toàn (MoS): {mos:+.1f}%
- Mục tiêu giá (Target): {p_target:.2f}k VND | Ngưỡng dừng lỗ: {stop_loss:.2f}k VND | Tỷ lệ R:R: {rr:.1f}x
- Điểm tài chính Piotroski F-Score: {f_val_str}
- Sức khỏe tài chính Altman Z-Score: {z_val_str}
- Tin tức & Xúc tác: {news_text}

BẮT BUỘC PHÂN TÍCH TUẦN TỰ THEO 5 BƯỚC:

=== BƯỚC 1: ĐÁNH GIÁ CƠ BẢN (FA VIEW) ===
Dựa trên F-Score={f_eval}, Z-Score={z_eval}, MoS={mos:+.1f}%:
- Chất lượng lợi nhuận và mô hình kinh doanh có bền vững không? (Nếu N/A, không tự suy diễn số liệu tích cực).
- Đánh giá FA VIEW: BULLISH / NEUTRAL / BEARISH
- Định giá: UNDERVALUED / FAIR / OVERVALUED

=== BƯỚC 2: ĐÁNH GIÁ KỸ THUẬT (TA VIEW) ===
Dựa trên MA20={ma20_str}, RSI={rsi_str}, Vol={vol_str}:
- Động lượng dòng tiền, kiểm tra bẫy mua đuổi (Anti-chasing), vị thế nền giá.
- Đánh giá TA VIEW: BULLISH / NEUTRAL / BEARISH

=== BƯỚC 3: ĐÁNH GIÁ VĨ MÔ & XÚC TÁC ===
- Chất xúc tác có đủ mạnh không và đã phản ánh vào thị giá chưa (Already Priced-in)?
- Đánh giá MACRO VIEW: SUPPORTIVE / NEUTRAL / NEGATIVE

=== BƯỚC 4: RED TEAM — TỰ PHẢN BIỆN (3 CÂU BẮT BUỘC) ===
1. Điểm YẾU NHẤT trong luận điểm đầu tư này là gì?
2. Nếu loại bỏ chất xúc tác tốt nhất, luận điểm có còn đứng vững không?
3. Kịch bản rủi ro sụt giảm (downside scenario) là gì và xác suất xảy ra bao nhiêu %?

=== BƯỚC 5: QUYẾT ĐỊNH CUỐI CÙNG (PM DECISION) ===
BẮT BUỘC chọn chính xác 1 trong 8 trạng thái định chế chuẩn:
[STRONG_OPPORTUNITY | ATTRACTIVE | WATCHLIST | WAIT_BETTER_ENTRY | HOLD_MAINTAIN | RISK_ELEVATED | AVOID | INSUFFICIENT_DATA]
BẮT BUỘC mở đầu dòng phán quyết bằng cú pháp chuẩn:
PM DECISION: <TRẠNG_THÁI> — <Lý do hành động súc tích>
- Kèm: WHY NOW / WHY WAIT (Tại sao mua ngay hoặc tại sao phải chờ)?
- TOP 3 LÝ DO HÀNH ĐỘNG
- TOP 3 RỦI RO TRỌNG YẾU

QUY TẮC BẮT BUỘC:
- 100% tiếng Việt chuẩn Unicode, TUYỆT ĐỐI KHÔNG dùng chữ Hán / tiếng Trung.
- BẮT BUỘC IN ĐẬM mã cổ phiếu **{sym}**.
- KHÔNG dùng bảng markdown (|---|). Dùng danh sách gạch đầu dòng phân cấp.
"""


def _extract_pm_decision(report_text: str) -> str:
    """Extract PM Decision from AI report using priority matching."""
    # Priority 1: Match explicit PM DECISION statement
    pattern = re.compile(
        r'(?:PM[_\s]*DECISION|PHÁN QUYẾT PM|QUYẾT ĐỊNH PM)[:\s—\-]+([A-Z_]+)',
        re.IGNORECASE
    )
    for m in reversed(pattern.findall(report_text)):
        candidate = m.strip().upper()
        if candidate in VALID_PM_STATES:
            return candidate

    # Priority 2: Search exclusively in Bước 5 / Decision section
    b5_pos = report_text.rfind("BƯỚC 5")
    scope = report_text[b5_pos:] if b5_pos != -1 else report_text
    for line in scope.splitlines():
        for state in VALID_PM_STATES:
            if re.search(r'\b' + re.escape(state) + r'\b', line):
                return state

    # Priority 3: Fallback default
    return "WATCHLIST"


def _prepare_smart_committee_context(
    symbol: str,
    tech_data: dict = None,
    fin_data: dict = None,
    news_items: list = None
) -> tuple[dict | None, str | None, dict | None]:
    """
    Chuẩn bị dữ liệu và prompt cho Hội đồng Đầu tư Định chế V2.
    Trả về:
      - (rejection_result, None, None) nếu vi phạm Phase 0 Data Reconciliation Gate.
      - (None, prompt, context_meta) nếu vượt qua Data Gate và sẵn sàng gọi LLM.
    """
    sym, tech_data, fin_data, news_items = _resolve_input_data(symbol, tech_data, fin_data, news_items)

    # 1. PHASE 0: DATA RECONCILIATION GATE (100% DETERMINISTIC PYTHON)
    from data_gate import reconcile_data
    gate_res = reconcile_data(
        symbol=sym,
        tech_data=tech_data,
        fin_data=fin_data,
        news=news_items
    )

    # Hard Gate check: Reject if price conflict, statutory band breach, or critical quality
    if not gate_res.get("gate_passed") or gate_res.get("price_status") == "CONFLICT":
        conflicts = "; ".join(gate_res.get("conflicting_data", ["Xung đột dữ liệu giá hoặc vi phạm quy chế sàn"]))
        refusal_report = (
            "======================================================\n"
            "⛔ **TỪ CHỐI KHUYẾN NGHỊ: DỮ LIỆU KHÔNG ĐẠT CHUẨN AN TOÀN QUỸ**\n"
            "======================================================\n\n"
            f"• **Mã cổ phiếu:** **{sym}**\n"
            f"• **Chất lượng dữ liệu:** `{gate_res.get('data_quality', 'CRITICAL')}` ({gate_res.get('quality_score', 0):.0f}/100)\n"
            f"• **Lý do từ chối:** {conflicts}\n\n"
            "⚠️ **Khuyến cáo:** Hệ thống Data Reconciliation Gate (Phase 0) từ chối phân tích cổ phiếu có dữ liệu bị sai lệch, giá âm hoặc vi phạm biên độ quy chế để bảo vệ vốn nhà đầu tư!"
        )
        rejection_res = {
            "status": "DATA_GATE_REJECTED",
            "symbol": sym,
            "data_quality": gate_res.get("data_quality", "CRITICAL"),
            "quality_score": gate_res.get("quality_score", 0.0),
            "gate_res": gate_res,
            "report_text": refusal_report,
            "pm_decision": "INSUFFICIENT_DATA"
        }
        return rejection_res, None, None

    # 2. PYTHON DETERMINISTIC QUANT ENGINE
    from quant_engine import calculate_altman_z_score, calculate_piotroski_f_score
    from quant_valuation import calculate_fair_value_and_mos

    val_res = calculate_fair_value_and_mos(symbol=sym, current_price=tech_data.get("current_price", 0.0))
    f_score_res = calculate_piotroski_f_score(fin_data)
    z_score_res = calculate_altman_z_score(fin_data)

    prompt = _format_committee_prompt_context(
        sym=sym,
        tech_data=tech_data,
        gate_res=gate_res,
        val_res=val_res,
        f_score_res=f_score_res,
        z_score_res=z_score_res,
        news_items=news_items
    )

    context_meta = {
        "symbol": sym,
        "gate_res": gate_res,
        "val_res": val_res,
        "f_score": f_score_res,
        "z_score": z_score_res
    }
    return None, prompt, context_meta


def _build_committee_response(context_meta: dict, report_text: str = None, error: Exception = None) -> dict:
    """Xây dựng response payload chuẩn hóa cho Smart Committee (SUCCESS hoặc AI_GENERATION_FAILED)."""
    gate_res = context_meta["gate_res"]
    val_res = context_meta["val_res"]
    sym = context_meta["symbol"]

    if error is not None:
        return {
            "status": "AI_GENERATION_FAILED",
            "symbol": sym,
            "pm_decision": "INSUFFICIENT_DATA",
            "data_quality": gate_res.get("data_quality", "HIGH"),
            "quality_score": gate_res.get("quality_score", 100.0),
            "gate_res": gate_res,
            "val_res": val_res,
            "f_score": context_meta["f_score"],
            "z_score": context_meta["z_score"],
            "report_text": f"⚠️ Lỗi kết nối AI khi phân tích cổ phiếu **{sym}**: {error}",
            "error": str(error)
        }

    return {
        "status": "SUCCESS",
        "symbol": sym,
        "pm_decision": _extract_pm_decision(report_text),
        "data_quality": gate_res.get("data_quality", "HIGH"),
        "quality_score": gate_res.get("quality_score", 100.0),
        "gate_res": gate_res,
        "val_res": val_res,
        "f_score": context_meta["f_score"],
        "z_score": context_meta["z_score"],
        "report_text": report_text
    }


def analyze_stock_with_smart_committee(
    symbol: str,
    tech_data: dict = None,
    fin_data: dict = None,
    news_items: list = None
) -> dict:
    """
    BÁO CÁO PHÂN TÍCH ĐỊNH CHẾ TOÀN DIỆN V2 (SMART COMPRESSED INVESTMENT COMMITTEE):
    1 API call duy nhất — Đạt 80% giá trị của V2 Master Prompt với token tăng tối thiểu (+30%).

    Quy trình tích hợp:
    - Phase 0: Data Reconciliation Gate (data_gate.py) — 100% Python deterministic.
    - Quant Engine: Fair Value, MoS, Piotroski F-Score, Altman Z-Score, ATR Stop, R:R.
    - 5-Expert Sequential Reasoning (FA View -> TA View -> Macro & Catalyst View -> Red Team 3 câu -> PM Decision 8 trạng thái).
    - 2-Tier Language Sanitizer (100% Vietnamese, zero CJK, bold tickers).
    """
    client = get_ai_client()
    rejection_res, prompt, context_meta = _prepare_smart_committee_context(symbol, tech_data, fin_data, news_items)
    if rejection_res is not None:
        return rejection_res

    try:
        report_text = call_gemini(client, prompt)
    except Exception as api_err:
        logging.exception("Lỗi AI Generation cho mã %s: %s", context_meta["symbol"], api_err)
        return _build_committee_response(context_meta, error=api_err)

    return _build_committee_response(context_meta, report_text=report_text)


async def async_analyze_stock_with_smart_committee(
    symbol: str,
    tech_data: dict = None,
    fin_data: dict = None,
    news_items: list = None,
    client = None
) -> dict:
    """
    Phân tích định chế toàn diện V2 bất đồng bộ (Async Smart Compressed Committee).
    Không chặn luồng chính, cho phép phân tích song song nhiều mã cổ phiếu cùng lúc.
    """
    ai_client = client or get_ai_client()
    rejection_res, prompt, context_meta = _prepare_smart_committee_context(symbol, tech_data, fin_data, news_items)
    if rejection_res is not None:
        return rejection_res

    try:
        report_text = await async_call_gemini(ai_client, prompt)
    except Exception as api_err:
        logging.exception("Lỗi Async AI Generation cho mã %s: %s", context_meta["symbol"], api_err)
        return _build_committee_response(context_meta, error=api_err)

    return _build_committee_response(context_meta, report_text=report_text)


async def async_analyze_stocks_batch(
    symbols_or_candidates: list,
    max_concurrency: int = 5,
    client = None
) -> list:
    """
    Phân tích đồng thời hàng loạt cổ phiếu bằng asyncio.gather kết hợp Semaphore.
    Giúp quét 10-20 mã trong < 15s mà không bị tràn quota API Gemini.
    """
    import asyncio
    sem = asyncio.Semaphore(max_concurrency)
    ai_client = client or get_ai_client()

    async def _bound_worker(item):
        async with sem:
            if isinstance(item, str):
                return await async_analyze_stock_with_smart_committee(symbol=item, client=ai_client)
            if isinstance(item, dict):
                return await async_analyze_stock_with_smart_committee(
                    symbol=item.get("symbol", ""),
                    tech_data=item.get("tech_data"),
                    fin_data=item.get("fin_data"),
                    news_items=item.get("news_items"),
                    client=ai_client
                )
            return {
                "status": "INVALID_INPUT",
                "symbol": "UNKNOWN",
                "pm_decision": "INSUFFICIENT_DATA",
                "report_text": "Dữ liệu đầu vào không hợp lệ"
            }

    tasks = [_bound_worker(c) for c in (symbols_or_candidates or [])]
    if not tasks:
        return []
    return list(await asyncio.gather(*tasks, return_exceptions=False))



if __name__ == "__main__":
    print("=== KIỂM TRA PHÂN TÍCH VỚI GEMINI ===")
    portfolio = load_portfolio()
    df_eval = evaluate_portfolio(portfolio)
    news = fetch_macro_news()

    print("Đang gửi dữ liệu đến Gemini...")
    analysis = generate_portfolio_analysis(df_eval, news)
    print("\n--- BÁO CÁO PHÂN TÍCH TỪ GEMINI ---")
    print(analysis)

