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
    if not text:
        return text
    for cn, vn in CHINESE_FINANCE_DICTIONARY.items():
        text = text.replace(cn, vn)
    text = re.sub(r"[\u4e00-\u9fff]+", "", text)
    attr_pattern = r"^\s*\d+\.\s*(Câu chuyện xúc tác|Luận điểm cơ bản|Vùng giá gom|Giá mục tiêu|Ngưỡng dừng lỗ|Trạng thái kỹ thuật|Xúc tác|Mục tiêu|Cắt lỗ|Kỹ thuật)[^:]*:\s*"
    text = re.sub(attr_pattern, r"  - **\1:** ", text, flags=re.MULTILINE)
    code_pattern = r"^\s*\d+\.\s*(Cổ phiếu|Mã)\s+"
    text = re.sub(code_pattern, r"• \1 ", text, flags=re.MULTILINE)
    text = re.sub(r"\b(Cổ phiếu|cổ phiếu|Mã|mã|CP|cp)\s+([A-Z0-9]{3})\b", r"\1 **\2**", text)
    text = text.replace("****", "**")
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


def call_gemini(client, prompt: str, max_retries: int = 3, retry_delay: float = 2.0) -> str:
    import time

    full_prompt = f"{SYSTEM_LANGUAGE_RULE}\n\n{prompt}\n\n{SYSTEM_LANGUAGE_RULE}"
    last_err = None
    for attempt in range(1, max_retries + 1):
        try:
            response = client.models.generate_content(model=MODEL_NAME, contents=full_prompt)
            return sanitize_ai_text(response.text)
        except Exception as e:
            last_err = e
            logging.warning("[Gemini API] Lần gọi %d/%d thất bại: %s", attempt, max_retries, e)
            if attempt < max_retries:
                time.sleep(retry_delay * attempt)
    logging.exception("[Gemini API] Toàn bộ %d lần gọi Gemini thất bại: %s", max_retries, last_err)
    raise RuntimeError(f"Gemini API generation failed after {max_retries} attempts: {last_err}") from last_err


async def async_call_gemini(client, prompt: str, max_retries: int = 3, retry_delay: float = 2.0) -> str:
    import asyncio

    full_prompt = f"{SYSTEM_LANGUAGE_RULE}\n\n{prompt}\n\n{SYSTEM_LANGUAGE_RULE}"
    last_err = None
    for attempt in range(1, max_retries + 1):
        try:
            response = await client.aio.models.generate_content(model=MODEL_NAME, contents=full_prompt)
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


def _build_gate_rejection_message(symbol: str, extra_info: str, reasons: str, gate_name: str) -> str:
    """Helper function to centralize duplicated gate rejection messages."""
    return (
        f"======================================================\n"
        f"⛔ **TỪ CHỐI KHUYẾN NGHỊ: DỮ LIỆU KHÔNG ĐẠT CHUẨN AN TOÀN QUỸ**\n"
        f"======================================================\n\n"
        f"• **Mã cổ phiếu:** **{symbol}**\n"
        f"{extra_info}\n"
        f"• **Lý do từ chối:** {reasons}\n\n"
        f"⚠️ **Khuyến cáo:** Hệ thống {gate_name} từ chối phân tích cổ phiếu có dữ liệu bị sai lệch, giá âm hoặc thiếu minh bạch để bảo vệ vốn nhà đầu tư!"
    )


def generate_portfolio_analysis(portfolio_df, news_items, watchlist_df=None, custom_question: str = None) -> str:
    client = get_ai_client()
    quant_eval_str = _build_portfolio_quant_summary(portfolio_df)
    portfolio_str = (
        portfolio_df.to_string(index=False)
        if portfolio_df is not None and not portfolio_df.empty
        else "Chưa có dữ liệu."
    )
    watchlist_str = watchlist_df.to_string(index=False) if watchlist_df is not None and not watchlist_df.empty else ""
    news_str = _format_news_summary(news_items, limit=8)

    prompt = f"""Bạn là Giám đốc Quản trị Rủi ro & Chiến lược Danh mục Đầu tư (Senior Portfolio Manager) theo trường phái Value-First + Technical Timing.
Bây giờ là 15:00 CHIỀU - phiên giao dịch chứng khoán vừa khép lại tại ATC.

=== 1. TÍNH TOÁN ĐỊNH LƯỢNG TẤT ĐỊNH CỦA HỆ THỐNG PYTHON CHO DANH MỤC ===
{quant_eval_str}

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
   - Câu hỏi 1: Danh mục hôm nay tăng/giảm do đâu?
   - Câu hỏi 2: Cổ phiếu nào còn rẻ, cổ phiếu nào chạm định giá?
   - Câu hỏi 3: Vị thế nào cần chốt lời từng phần và nâng Trailing Stop?
   - Câu hỏi 4: Vị thế nào bị suy giảm luận điểm (Thesis Breaker) cần dứt khoát cơ cấu?
   - Câu hỏi 5: Tỷ trọng tiền mặt hiện tại đã an toàn chưa? Đề xuất tỷ lệ Tiền/Cổ phiếu tối ưu dựa trên Risk Budgeting.

Yêu cầu trình bày báo cáo tổng kết phiên:
**I. TỔNG KẾT PHIÊN ATC & ĐÁNH GIÁ 5 CÂU HỎI CỐT TỬ**
(Trả lời lần lượt, ngắn gọn, đi thẳng vào bản chất 5 câu hỏi trên)

**II. CHI TIẾT DANH MỤC & HÀNH ĐỘNG QUẢN TRỊ RỦI RO**
- Trình bày từng mã đang nắm giữ:
  • Cổ phiếu **[MÃ]** ([Ngành]) — [HUY HIỆU]:
    - **Giá vốn:** ...k | **Thị giá ATC:** ...k | **P/L:** ...%
    - **Hành động cụ thể:** ...
    - **Mốc Trailing Stop bảo vệ lãi (hoặc Stop-loss):** ...
    - **Đánh giá Luận điểm cơ bản (Thesis):** ...

**III. TÁC ĐỘNG VĨ MÔ & DÒNG TIỀN TỰ DOANH / NGOẠI**
- Đánh giá động thái mua/bán ròng và tin tức CafeF hôm nay.

**IV. KẾ HOẠCH HÀNH ĐỘNG CHO PHIÊN KẾ TIẾP**
- Tỷ trọng phân bổ đề xuất: % Tiền mặt / % Cổ phiếu.
- Điều kiện thị trường để kích hoạt giải ngân mới.

Định dạng Discord/Web:
- KHÔNG dùng bảng markdown (|---|).
- KHÔNG dùng dấu `###`.
- BẮT BUỘC IN ĐẬM TẤT CẢ MÃ CỔ PHIẾU.
- Dùng gạch đầu dòng phân cấp.
"""

    if custom_question:
        prompt += (
            f"\n\n[CÂU HỎI BỔ SUNG CỦA NHÀ ĐẦU TƯ]: {custom_question}\nHãy trả lời chi tiết trọng tâm câu hỏi này."
        )

    return call_gemini(client, prompt)


def generate_morning_strategy_report(
    portfolio_df, watchlist_df, opportunities: list, news_items: list, vnindex_tech: dict = None
) -> str:
    client = get_ai_client()
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

    regime_data = evaluate_market_regime(vnindex_tech)
    p_str = (
        portfolio_df.to_string(index=False)
        if portfolio_df is not None and not portfolio_df.empty
        else "Chưa có mã nắm giữ."
    )
    w_str = (
        watchlist_df.to_string(index=False)
        if watchlist_df is not None and not watchlist_df.empty
        else "Chưa có mã trong Watchlist."
    )

    idx_context = f"""=== 0. DỮ LIỆU THỊ TRƯỜNG & RISK BUDGETING (CẬP NHẬT TỨC THỜI) ===
- Điểm số đóng cửa phiên gần nhất: {idx_price:.2f} điểm (Thay đổi: {idx_chg:+.2f}%)
- Đường MA20 ngày: {idx_ma20:.2f} điểm (Trạng thái: {idx_status})
- Đường MA50 ngày: {idx_ma50:.2f} điểm | RSI(14): {idx_rsi}
- TRẠNG THÁI THỊ TRƯỜNG (MARKET REGIME): {regime_data["tag"]}
- TỶ TRỌNG PHÂN BỔ ĐỀ XUẤT (THEO RISK BUDGET): Cổ phiếu {regime_data["stock_pct"]} | Tiền mặt {regime_data["cash_pct"]} (Hạn mức tối đa: {regime_data["max_stock_nav"]}% NAV)
- ĐỊNH HƯỚNG QUẢN TRỊ RỦI RO: {regime_data["bias"]} (Ưu tiên phòng thủ: {regime_data["defense_priority"]})
"""

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
        val_res = calculate_fair_value_and_mos(
            symbol=sym, current_price=o.get("current_price", 0.0), sector=o.get("sector", "")
        )
        fv = val_res.get("fair_value", o.get("fair_value", 0.0))
        mos = val_res.get("mos_pct", o.get("mos_pct", 0.0))
        val_method = val_res.get("valuation_method", o.get("valuation_method", "N/A"))
        val_conf = val_res.get("confidence", o.get("confidence", "MEDIUM"))
        p_target = val_res.get("price_target") or o.get("target_price") or round(fv * 1.05, 2)

        status = o.get("status", "")
        avg_entry = o.get("avg_cost", o.get("current_price", 0.0))
        stop = o.get("stop_loss", round(avg_entry * 0.93, 2))

        setup_dict = {
            "weighted_entry": avg_entry,
            "target_price": p_target,
            "stop_loss": stop,
            "risk_reward": o.get("risk_reward", 1.5),
        }
        _, _, clean_setup = validate_trade_setup(setup_dict)
        rr = clean_setup["risk_reward"]

        if status == "RECOMMEND_BUY":
            act = "🟢 VALUE BUY" if mos >= 15.0 and o.get("current_price", 0) >= o.get("ma20", 0) else "🟢 ACCUMULATE"
            dq_badge = o.get("data_badge") or (
                f"📊 Data Quality: {o.get('data_quality', 'HIGH')}" if o.get("data_quality") else ""
            )
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
            watch_lines.append(
                f"• Mã: **{sym}** ({o.get('sector', 'Niêm yết')}) — 🟡 **[THEO DÕI / CHỜ NỀN CÂN BẰNG]**\n"
                f"  - **Giá trị hợp lý (Fair Value):** {fv:.2f}k | **Mô hình:** {val_method} ({val_conf})\n"
                f"  - **Biên an toàn (MoS):** {mos:+.1f}% | **Mục tiêu giá:** {p_target:.2f}k | **Thị giá hiện tại:** {o.get('current_price')}k\n"
                f"  - **Lý do theo dõi:** {o.get('setup_type', 'Chờ xác nhận')} — {o.get('rationale', 'Định giá và cơ bản đạt chuẩn nhưng giá cần tích lũy thêm trên MA20.')}"
            )

    buy_str = "\n".join(buy_lines) if buy_lines else "Thị trường chưa có mã nào đạt đồng thời Biên an toàn và kỹ thuật."
    watch_str = "\n".join(watch_lines) if watch_lines else "Không có mã nào trong diện chờ xác nhận nền."
    caution_str = "\n".join(caution_lines) if caution_lines else "Không có mã nào rơi vào diện cảnh báo bẫy tin."

    news_lines = [f"- [{n.get('tag', 'TIN').upper()}] {n['title']}" for n in news_items[:6]]
    news_str = "\n".join(news_lines)

    prompt = f"""Bạn là Giám đốc Chiến lược Đầu tư Định chế.
Bây giờ là 08:45 SÁNG - chuẩn bị bước vào phiên giao dịch ATO.
Hãy xuất bản bản tin "CHIẾN LƯỢC PHIÊN HÔM NAY & KHUYẾN NGHỊ ĐẦU NGÀY":

{idx_context}

=== 1. DANH MỤC HIỆN TẠI CỦA NHÀ ĐẦU TƯ ===
{p_str}

=== 2. DANH SÁCH THEO DÕI (WATCHLIST) ===
{w_str}

=== 3. CƠ HỘI ĐẠT CHUẨN ĐỊNH LƯỢNG (TỐI ĐA 1-2 MÃ MUA) ===
{buy_str}

=== 4. CỔ PHIẾU CƠ BẢN TỐT CẦN THEO DÕI CHỜ NỀN ===
{watch_str}

=== 5. CẢNH BÁO BẪY PHÂN PHỐI & RỦI RO CAO ===
{caution_str}

=== 6. ĐIỂM TIN VĨ MÔ SÁNG NAY ===
{news_str}

Yêu cầu xuất bản & Cấu trúc:
**I. BỐI CẢNH VĨ MÔ & TRẠNG THÁI THỊ TRƯỜNG**
**II. CƠ HỘI ĐẦU TƯ & RADAR THEO DÕI**
  A. 🟢 KHUYẾN NGHỊ MUA MỚI / TÍCH LŨY
  B. 🟡 RADAR THEO DÕI CHỜ NỀN
  C. ⛔ CẢNH BÁO PHÒNG THỦ & TRÁNH BẪY
**III. KỊCH BẢN HÀNH ĐỘNG TRONG PHIÊN (BULL / BASE / BEAR)**
**IV. KỶ LUẬT QUẢN TRỊ RỦI RO & BẢO TOÀN VỐN**
"""
    return call_gemini(client, prompt)


def generate_market_risk_scenarios(vnindex_df, news_items) -> str:
    client = get_ai_client()
    idx_summary = "Không có dữ liệu VNINDEX"
    if vnindex_df is not None and not vnindex_df.empty:
        latest = vnindex_df.iloc[-1]
        prev = vnindex_df.iloc[-2] if len(vnindex_df) > 1 else latest
        c = float(latest["close"])
        p_c = float(prev["close"])
        chg = ((c - p_c) / p_c) * 100
        idx_summary = (
            f"VN-Index hiện tại: {c:.2f} điểm (Thay đổi: {chg:+.2f}%)\n"
            f"Khối lượng: {int(latest.get('volume', 0)):,} CP\n"
            f"P/E thị trường: {latest.get('PE', 'N/A')} | P/B: {latest.get('PB', 'N/A')}"
        )

    news_str = (
        "\n".join([f"- [{n.get('tag', 'TIN').upper()}] {n.get('title', '')}" for n in news_items[:8]])
        if news_items
        else "Không có tin tức vĩ mô mới."
    )

    prompt = f"""Hãy đóng vai trò là Giám đốc Quản trị Rủi ro & Chiến lược Vĩ mô cấp cao.

=== DỮ LIỆU CHỈ SỐ VN-INDEX ===
{idx_summary}

=== BỐI CẢNH VĨ MÔ & DÒNG TIỀN ===
{news_str}

Nhiệm vụ: Xây dựng Ma trận Kịch bản Rủi ro Thị trường toàn diện:
**I. ĐỊNH VỊ CHU KỲ SÓNG & TÂM LÝ THỊ TRƯỜNG** (Wyckoff & Elliott)
**II. 3 - 4 KỊCH BẢN THỊ TRƯỜNG TOÀN DIỆN** (Lạc quan, Cơ sở, Bi quan, Cực đoan)
**III. HƯỚNG DẪN THỰC THI & NGUYÊN TẮC KỶ LUẬT VỐN**
"""
    return call_gemini(client, prompt)


def generate_institutional_stock_report(symbol: str, financial_info: dict, tech_dict: dict, news_items: list) -> str:
    client = get_ai_client()
    current_price = tech_dict.get("current_price") or 0.0
    change_pct = tech_dict.get("change_pct", 0.0)
    ma20 = tech_dict.get("ma20")

    if ma20 and current_price >= ma20:
        stop_loss_ref = round(min(ma20 * 0.97, current_price * 0.94), 2)
    else:
        stop_loss_ref = round(current_price * 0.93, 2) if current_price > 0 else 0.0

    downside_pct = round(((current_price - stop_loss_ref) / current_price) * 100, 1) if current_price > 0 else 7.0
    foreign_flow = tech_dict.get("foreign_flow", {})
    foreign_summary = (
        f"- Khối ngoại: Mua {foreign_flow.get('buy_val_bil', 0):.1f} tỷ | Bán {foreign_flow.get('sell_val_bil', 0):.1f} tỷ"
        if foreign_flow
        else "- Khối ngoại: Chưa có dữ liệu."
    )

    trap_info = tech_dict.get("trap_info", {})
    trap_summary = (
        f"- Cảnh báo: ⚠️ {trap_info.get('warning_msg')}"
        if trap_info.get("is_trap")
        else "- Cảnh báo: ✅ Không phát hiện bẫy."
    )

    tech_summary = (
        f"Mã CP: {symbol}\n- Thị giá: {current_price} k VND ({change_pct:+.2f}%)\n"
        f"- MA20: {ma20} k VND ({tech_dict.get('status_ma20', 'N/A')})\n"
        f"- RSI(14): {tech_dict.get('rsi14', 'N/A')} | Vol/SMA20: {tech_dict.get('vol_ratio', 1.0)}x\n"
        f"{foreign_summary}\n{trap_summary}\n- Cắt lỗ tham chiếu: {stop_loss_ref} k VND (-{downside_pct}%)\n"
    )

    fin_summary = f"Kỳ báo cáo: {financial_info.get('period', 'N/A')}\n"
    for k in ["pe", "pb", "roe", "debt_equity"]:
        fin_summary += f"- {k.upper()}: {financial_info.get(k, 'N/A')}\n"

    news_str = (
        "\n".join([f"- [{n.get('tag', 'TIN').upper()}] {n.get('title', '')}" for n in (news_items or [])[:6]])
        or "Không có tin tức đột biến."
    )

    prompt = f"""<ROLE> Giám đốc Phân tích Đầu tư cấp cao (CFA). Tranh biện Đối kháng (Bò vs Gấu). </ROLE>
<CONTEXT>
Cổ phiếu mục tiêu: **{symbol}**
--- 1. TÍN HIỆU KỸ THUẬT & DÒNG TIỀN ---
{tech_summary}
--- 2. TÀI CHÍNH & ĐỊNH GIÁ ---
{fin_summary}
--- 3. TIN TỨC VĨ MÔ ---
{news_str}
</CONTEXT>
<OUTPUT_FORMAT>
Hãy lập Báo cáo Phân tích Toàn diện gồm: I. TÓM TẮT ĐIỀU HÀNH | II. BẢNG TỔNG KẾT TÍN HIỆU 8 TRỤ CỘT | III. TRANH BIỆN BÒ VS GẤU | IV. ĐỊNH GIÁ & BIÊN AN TOÀN | V. PHÂN TÍCH KỸ THUẬT | VI. 3 KỊCH BẢN ĐẦU TƯ | VII. KẾT LUẬN CHẤM ĐIỂM
</OUTPUT_FORMAT>"""
    return call_gemini(client, prompt)


def generate_quantamental_2pass_report(symbol: str) -> dict:
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

    gate = check_data_gate(symbol, tech_data, fin_data, min_adv20_billion=2.0)
    if not gate["passed"]:
        reasons = " | ".join(gate["reasons"])
        extra = f"• **Giá trị giao dịch trung bình phiên:** {gate.get('daily_value_billion', 0)} tỷ VND"
        return {
            "status": "DATA_GATE_REJECTED",
            "report_text": _build_gate_rejection_message(symbol, extra, reasons, "Lượng hóa Định chế"),
            "hard_gates": {},
            "f_score": {},
            "z_score": {},
        }

    curr_price = tech_data.get("current_price", 0.0)
    pe = fin_data.get("pe")
    pb = fin_data.get("pb")
    f_score_res = calculate_piotroski_f_score(fin_data)
    z_score_res = calculate_altman_z_score(fin_data)
    val_triangle = calculate_valuation_triangle(curr_price, pe=pe, pb=pb)

    pass1_prompt = f"""Bạn là Quản lý Quỹ Lượng hóa. Hãy đọc dữ liệu của mã **{symbol}** và gán xác suất (P_bull, P_base, P_bear) theo JSON:
- Thị giá: {curr_price}k | Vị thế MA20: {tech_data.get("status_ma20")}
- P/E: {pe} | P/B: {pb}
BẮT BUỘC TRẢ VỀ JSON HỢP LỆ."""

    try:
        pass1_resp = client.models.generate_content(model=MODEL_NAME, contents=pass1_prompt)
        raw_text = pass1_resp.text.strip()
        json_match = re.search(r"\{.*\}", raw_text, re.DOTALL)
        prob_dict = json.loads(json_match.group(0)) if json_match else json.loads(raw_text)

        p_bull, p_base, p_bear = (
            float(prob_dict.get("P_bull", 0.25)),
            float(prob_dict.get("P_base", 0.50)),
            float(prob_dict.get("P_bear", 0.25)),
        )
        total_p = p_bull + p_base + p_bear
        if total_p > 0:
            p_bull /= total_p
            p_base /= total_p
            p_bear /= total_p
    except Exception:
        p_bull, p_base, p_bear = 0.25, 0.50, 0.25
        prob_dict = {
            "rationale_bull": "Tăng trưởng tốt.",
            "rationale_base": "Duy trì ổn định.",
            "rationale_bear": "Áp lực điều chỉnh.",
        }

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
        adv20_billion=tech_data.get("adv20_billion", 0.0),
    )

    pass2_prompt = f"""<ROLE>Giám đốc Phân tích Đầu tư Lượng hóa (CFA).</ROLE>
Viết báo cáo Lượng hóa dựa trên Quyết định: {hard_gates.get("decision_tag")} và MoS {hard_gates.get("mos_pct")}%. Cổ phiếu **{symbol}**."""
    final_report = call_gemini(client, pass2_prompt)

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
            input_snapshot={"pe": pe, "pb": pb, "roe": fin_data.get("roe")},
        )
    except Exception as db_err:
        logging.warning(f"Không thể lưu snapshot: {db_err}")

    return {
        "status": "SUCCESS",
        "report_text": final_report,
        "hard_gates": hard_gates,
        "f_score": f_score_res,
        "z_score": z_score_res,
        "data_gate": gate,
    }


VALID_PM_STATES = (
    "STRONG_OPPORTUNITY",
    "ATTRACTIVE",
    "WATCHLIST",
    "WAIT_BETTER_ENTRY",
    "HOLD_MAINTAIN",
    "RISK_ELEVATED",
    "AVOID",
    "INSUFFICIENT_DATA",
)


def _resolve_input_data(symbol: str, tech_data: dict = None, fin_data: dict = None, news_items: list = None):
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
    if z_raw is None:
        return "N/A", "N/A (Chưa đủ BCTC)"
    try:
        val_str = f"{float(z_raw):.2f}"
    except (ValueError, TypeError):
        val_str = str(z_raw)
    return val_str, f"{val_str} ({zone})"


def _format_committee_prompt_context(
    sym: str, tech_data: dict, gate_res: dict, val_res: dict, f_score_res: dict, z_score_res: dict, news_items: list
) -> str:
    from data_gate import format_data_quality_badge

    curr_price = float(tech_data.get("current_price", 0.0))
    fv = val_res.get("fair_value", curr_price * 1.10)
    mos = val_res.get("mos_pct", 0.0)
    p_target = val_res.get("price_target") or round(fv * 1.05, 2)
    stop_loss = round(curr_price * 0.93, 2) if curr_price > 0 else 0.0
    rr = round(max(0.0, p_target - curr_price) / max(0.1, curr_price - stop_loss), 2)

    data_badge_str = format_data_quality_badge(gate_res)
    news_text = (
        "; ".join([n.get("title", "") for n in news_items[:3] if n.get("title")])
        if news_items
        else "Không có tin đột biến."
    )
    f_val_str = (
        f"{f_score_res.get('score')}/9 ({f_score_res.get('rating', 'Khỏe')})"
        if f_score_res.get("score") is not None
        else "N/A"
    )
    _, z_val_str = _format_z_score(z_score_res.get("z_score"), z_score_res.get("zone", "Vùng an toàn"))

    return f"""Bạn là Investment Committee (Hội đồng Đầu tư Định chế) gồm 5 vai trò.
- Mã cổ phiếu: **{sym}**
- {data_badge_str}
- Thị giá: {curr_price}k VND
- Định giá Fair Value: {fv:.2f}k VND | Biên an toàn (MoS): {mos:+.1f}%
- Mục tiêu giá: {p_target:.2f}k VND | Dừng lỗ: {stop_loss:.2f}k VND | R:R: {rr:.1f}x
- Piotroski F-Score: {f_val_str} | Altman Z-Score: {z_val_str}
- Tin tức: {news_text}
BẮT BUỘC PHÂN TÍCH TUẦN TỰ THEO 5 BƯỚC: FA View, TA View, Macro, Red Team, và PM DECISION."""


def _extract_pm_decision(report_text: str) -> str:
    pattern = re.compile(r"(?:PM[_\s]*DECISION|PHÁN QUYẾT PM|QUYẾT ĐỊNH PM)[:\s—\-]+([A-Z_]+)", re.IGNORECASE)
    for m in reversed(pattern.findall(report_text)):
        if (c := m.strip().upper()) in VALID_PM_STATES:
            return c
    return "WATCHLIST"


def _prepare_smart_committee_payload(symbol: str, tech_data: dict, fin_data: dict, news_items: list):
    """Refactored logic gom chung cho cả Sync và Async để giảm trùng lặp."""
    sym, tech_data, fin_data, news_items = _resolve_input_data(symbol, tech_data, fin_data, news_items)
    from data_gate import reconcile_data

    gate_res = reconcile_data(symbol=sym, tech_data=tech_data, fin_data=fin_data, news=news_items)

    if not gate_res.get("gate_passed") or gate_res.get("price_status") == "CONFLICT":
        conflicts = "; ".join(gate_res.get("conflicting_data", ["Xung đột dữ liệu giá hoặc vi phạm quy chế sàn"]))
        extra = f"• **Chất lượng dữ liệu:** `{gate_res.get('data_quality', 'CRITICAL')}` ({gate_res.get('quality_score', 0):.0f}/100)"
        return {
            "status": "DATA_GATE_REJECTED",
            "symbol": sym,
            "data_quality": gate_res.get("data_quality", "CRITICAL"),
            "quality_score": gate_res.get("quality_score", 0.0),
            "gate_res": gate_res,
            "report_text": _build_gate_rejection_message(sym, extra, conflicts, "Data Reconciliation Gate (Phase 0)"),
            "pm_decision": "INSUFFICIENT_DATA",
        }

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
        news_items=news_items,
    )
    meta = {"symbol": sym, "gate_res": gate_res, "val_res": val_res, "f_score": f_score_res, "z_score": z_score_res}
    return prompt, meta


def _build_committee_failure_response(meta: dict, api_err: Exception) -> dict:
    return {
        "status": "AI_GENERATION_FAILED",
        "symbol": meta["symbol"],
        "pm_decision": "INSUFFICIENT_DATA",
        "data_quality": meta["gate_res"].get("data_quality", "HIGH"),
        "quality_score": meta["gate_res"].get("quality_score", 100.0),
        "gate_res": meta["gate_res"],
        "val_res": meta["val_res"],
        "f_score": meta["f_score"],
        "z_score": meta["z_score"],
        "report_text": f"⚠️ Lỗi kết nối AI khi phân tích cổ phiếu **{meta['symbol']}**: {api_err}",
        "error": str(api_err),
    }


def _build_committee_success_response(meta: dict, report_text: str) -> dict:
    return {
        "status": "SUCCESS",
        "symbol": meta["symbol"],
        "pm_decision": _extract_pm_decision(report_text),
        "data_quality": meta["gate_res"].get("data_quality", "HIGH"),
        "quality_score": meta["gate_res"].get("quality_score", 100.0),
        "gate_res": meta["gate_res"],
        "val_res": meta["val_res"],
        "f_score": meta["f_score"],
        "z_score": meta["z_score"],
        "report_text": report_text,
    }


def analyze_stock_with_smart_committee(
    symbol: str, tech_data: dict = None, fin_data: dict = None, news_items: list = None
) -> dict:
    client = get_ai_client()
    payload = _prepare_smart_committee_payload(symbol, tech_data, fin_data, news_items)
    if isinstance(payload, dict):
        return payload
    prompt, meta = payload
    try:
        report_text = call_gemini(client, prompt)
    except Exception as api_err:
        logging.exception("Lỗi AI Generation cho mã %s: %s", meta["symbol"], api_err)
        return _build_committee_failure_response(meta, api_err)
    return _build_committee_success_response(meta, report_text)


async def async_analyze_stock_with_smart_committee(
    symbol: str, tech_data: dict = None, fin_data: dict = None, news_items: list = None, client=None
) -> dict:
    ai_client = client or get_ai_client()
    payload = _prepare_smart_committee_payload(symbol, tech_data, fin_data, news_items)
    if isinstance(payload, dict):
        return payload
    prompt, meta = payload
    try:
        report_text = await async_call_gemini(ai_client, prompt)
    except Exception as api_err:
        logging.exception("Lỗi Async AI Generation cho mã %s: %s", meta["symbol"], api_err)
        return _build_committee_failure_response(meta, api_err)
    return _build_committee_success_response(meta, report_text)


async def async_analyze_stocks_batch(symbols_or_candidates: list, max_concurrency: int = 5, client=None) -> list:
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
                    client=ai_client,
                )
            return {
                "status": "INVALID_INPUT",
                "symbol": "UNKNOWN",
                "pm_decision": "INSUFFICIENT_DATA",
                "report_text": "Dữ liệu đầu vào không hợp lệ",
            }

    tasks = [_bound_worker(c) for c in (symbols_or_candidates or [])]
    return list(await asyncio.gather(*tasks, return_exceptions=False)) if tasks else []


if __name__ == "__main__":
    print("=== KIỂM TRA PHÂN TÍCH VỚI GEMINI ===")
    portfolio = load_portfolio()
    df_eval = evaluate_portfolio(portfolio)
    news = fetch_macro_news()

    print("Đang gửi dữ liệu đến Gemini...")
    analysis = generate_portfolio_analysis(df_eval, news)
    print("\n--- BÁO CÁO PHÂN TÍCH TỪ GEMINI ---")
    print(analysis)
