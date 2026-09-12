import os
import logging
import requests
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")


def send_discord_message(content: str = None, embeds: list = None) -> bool:
    """Gửi tin nhắn hoặc Embed qua Discord Webhook."""
    if not DISCORD_WEBHOOK_URL:
        logging.error("Chưa cấu hình DISCORD_WEBHOOK_URL trong file .env!")
        return False

    payload = {}
    if content:
        payload["content"] = content
    if embeds:
        payload["embeds"] = embeds

    try:
        response = requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=10)
        if response.status_code in [200, 204]:
            logging.info("Đã gửi tin nhắn đến Discord thành công!")
            return True
        else:
            logging.error(f"Lỗi khi gửi Discord: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        logging.error(f"Ngoại lệ khi gửi Discord: {e}")
        return False


def format_portfolio_embed(portfolio_df, ai_summary: str, report_type: str = "BÁO CÁO PHIÊN") -> dict:
    """
    Format báo cáo danh mục thành Discord Rich Embed sang trọng, trực quan.
    """
    # Tính tổng lãi lỗ danh mục
    total_cost = (portfolio_df["Khối lượng"] * portfolio_df["Giá vốn (k)"] * 1000).sum()
    total_market = (portfolio_df["Khối lượng"] * portfolio_df["Thị giá (k)"] * 1000).sum()
    total_pnl_vnd = total_market - total_cost
    total_pnl_pct = (total_pnl_vnd / total_cost * 100) if total_cost > 0 else 0.0

    color = 0x2ECC71 if total_pnl_vnd >= 0 else 0xE74C3C  # Xanh lá nếu lời, Đỏ nếu lỗ

    # Tóm tắt danh mục thành chuỗi ngắn gọn
    portfolio_lines = []
    for _, row in portfolio_df.iterrows():
        pnl_icon = "🟢" if row["Lãi/Lỗ (%)"] >= 0 else "🔴"
        line = (
            f"{pnl_icon} **{row['Mã CP']}** ({row['Khối lượng']:,} cp) | "
            f"Vốn: `{row['Giá vốn (k)']}` ➔ Giá: `{row['Thị giá (k)']}` | "
            f"**{row['Lãi/Lỗ (%)']:+.2f}%** (`{int(row['Lãi/Lỗ (VND)']):+,}đ`)"
        )
        portfolio_lines.append(line)

    portfolio_desc = "\n".join(portfolio_lines)
    summary_pnl = f"**Tổng tài sản danh mục:** `{int(total_market):,}đ` | **Lãi/Lỗ:** `{int(total_pnl_vnd):+,}đ` (**{total_pnl_pct:+.2f}%**)"

    # Cắt ngắn bài phân tích AI nếu quá dài (giới hạn Discord field là 1024 ký tự)
    ai_display = ai_summary[:1000] + "..." if len(ai_summary) > 1000 else ai_summary

    embed = {
        "title": f"📊 AI STOCK COPILOT - {report_type.upper()}",
        "description": f"{summary_pnl}\n\n**Chi tiết từng mã:**\n{portfolio_desc}",
        "color": color,
        "fields": [
            {
                "name": "🧠 Nhận định & Khuyến nghị Chiến lược (Gemini Pro)",
                "value": ai_display,
                "inline": False,
            }
        ],
        "footer": {
            "text": "Stock AI Assistant • Dữ liệu vnstock • Phân tích bởi Gemini",
        },
    }
    return embed


def send_risk_alert(symbol: str, current_price: float, cost_price: float, trigger_reason: str):
    """
    Gửi cảnh báo rủi ro khẩn cấp khi gãy nền hoặc chạm ngưỡng Stop Loss.
    """
    pnl_pct = ((current_price - cost_price) / cost_price) * 100
    embed = {
        "title": f"🚨 CẢNH BÁO RỦI RO DANH MỤC: {symbol}",
        "description": (
            f"Mã **{symbol}** vừa kích hoạt tín hiệu quản trị rủi ro!\n\n"
            f"- **Lý do:** `{trigger_reason}`\n"
            f"- **Thị giá hiện tại:** `{current_price}` (Giá vốn: `{cost_price}`)\n"
            f"- **Tỷ lệ vi phạm:** `{pnl_pct:+.2f}%`\n\n"
            f"⚠️ **Khuyến nghị:** Cân nhắc hạ tỷ trọng bảo toàn vốn!"
        ),
        "color": 0xE74C3C,  # Đỏ khẩn cấp
        "footer": {
            "text": "Risk Management Bot • Cảnh báo tức thời",
        },
    }
    return send_discord_message(embeds=[embed])


if __name__ == "__main__":
    from data_engine import load_portfolio, evaluate_portfolio, fetch_macro_news
    from ai_analyst import generate_portfolio_analysis

    print("=== KIỂM TRA GỬI BÁO CÁO TOÀN DIỆN ĐẾN DISCORD ===")
    portfolio = load_portfolio()
    df_eval = evaluate_portfolio(portfolio)
    news = fetch_macro_news()

    print("Đang gọi AI phân tích...")
    ai_text = generate_portfolio_analysis(df_eval, news)

    print("Đang định dạng Embed và gửi Discord...")
    embed = format_portfolio_embed(df_eval, ai_text, report_type="BÁO CÁO THỰC THI SPRINT 1 & 2")
    success = send_discord_message(embeds=[embed])
    print("Kết quả gửi:", "Thành công!" if success else "Thất bại.")
