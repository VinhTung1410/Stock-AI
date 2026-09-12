import os
import logging
import requests
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")
DISCORD_BOT_TOKEN = os.environ.get("DISCORD_BOT_TOKEN")
DISCORD_USER_ID = os.environ.get("DISCORD_USER_ID")


def send_discord_dm(content: str = None, embeds: list = None) -> bool:
    """
    Gửi tin nhắn riêng (Direct Message - DM) trực tiếp vào hộp thư cá nhân của bạn.
    """
    if not DISCORD_BOT_TOKEN or not DISCORD_USER_ID:
        logging.warning("Chưa cấu hình DISCORD_BOT_TOKEN hoặc DISCORD_USER_ID trong .env!")
        return False

    headers = {
        "Authorization": f"Bot {DISCORD_BOT_TOKEN}",
        "Content-Type": "application/json"
    }

    try:
        # Bước 1: Mở kênh DM với User ID
        dm_res = requests.post(
            "https://discord.com/api/v10/users/@me/channels",
            headers=headers,
            json={"recipient_id": DISCORD_USER_ID},
            timeout=10
        )
        if dm_res.status_code != 200:
            logging.error(f"Lỗi khi mở kênh DM: {dm_res.status_code} - {dm_res.text}")
            return False

        channel_id = dm_res.json().get("id")
        if not channel_id:
            return False

        # Bước 2: Gửi nội dung tin nhắn / Embed vào kênh DM
        if embeds:
            msg_res = requests.post(
                f"https://discord.com/api/v10/channels/{channel_id}/messages",
                headers=headers,
                json={"embeds": embeds},
                timeout=10
            )
            if msg_res.status_code not in [200, 201]:
                logging.error(f"Lỗi khi gửi Embed DM: {msg_res.status_code} - {msg_res.text}")
                return False

        if content:
            # Tự động chia nhỏ tin nhắn nếu dài hơn 1900 ký tự (tránh giới hạn 2000 ký tự của Discord)
            chunks = [content[i:i+1900] for i in range(0, len(content), 1900)]
            for chunk in chunks:
                msg_res = requests.post(
                    f"https://discord.com/api/v10/channels/{channel_id}/messages",
                    headers=headers,
                    json={"content": chunk},
                    timeout=10
                )
                if msg_res.status_code not in [200, 201]:
                    logging.error(f"Lỗi khi gửi text DM: {msg_res.status_code} - {msg_res.text}")
                    return False

        logging.info("Đã gửi tin nhắn riêng (DM) đến bạn thành công!")
        return True
    except Exception as e:
        logging.error(f"Ngoại lệ khi gửi DM: {e}")
        return False


def send_discord_webhook(content: str = None, embeds: list = None) -> bool:
    """
    Gửi thông báo độc quyền vào Kênh Discord thông qua Webhook URL (không gửi vào tin nhắn riêng).
    """
    if not DISCORD_WEBHOOK_URL:
        logging.warning("Chưa cấu hình DISCORD_WEBHOOK_URL trong .env!")
        return False

    payload = {}
    if content:
        payload["content"] = content
    if embeds:
        payload["embeds"] = embeds

    try:
        response = requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=10)
        if response.status_code in [200, 204]:
            logging.info("Đã gửi tin nhắn qua Webhook thành công!")
            return True
        else:
            logging.error(f"Lỗi khi gửi Webhook: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        logging.error(f"Lỗi khi gửi Webhook: {e}")
        return False


def send_discord_message(content: str = None, embeds: list = None) -> bool:
    """
    Gửi thông báo tự động: Ưu tiên gửi qua Webhook vào Kênh chung nếu có, 
    nếu không có Webhook thì fallback gửi vào tin nhắn riêng (DM), không bao giờ gửi trùng 2 lần.
    """
    if DISCORD_WEBHOOK_URL:
        return send_discord_webhook(content=content, embeds=embeds)
    elif DISCORD_BOT_TOKEN and DISCORD_USER_ID:
        return send_discord_dm(content=content, embeds=embeds)
    else:
        logging.warning("Chưa cấu hình cả Webhook lẫn Bot Token trong .env!")
        return False



def split_ai_summary_into_fields(ai_summary: str) -> list:
    """
    Tách bài phân tích của AI thành các Field của Discord Embed (mỗi field < 1024 ký tự),
    loại bỏ các dấu ### và tự động dọn sạch định dạng để hiển thị hoàn hảo trên Discord.
    """
    clean_text = ai_summary.replace("### ", "").replace("## ", "").strip()
    
    # Định nghĩa các mốc tiêu đề phổ biến
    sections = [
        "I. ĐÁNH GIÁ SỨC KHỎE DANH MỤC",
        "II. TÁC ĐỘNG VĨ MÔ & DÒNG TIỀN",
        "III. KỊCH BẢN & CHIẾN LƯỢC HÀNH ĐỘNG",
        "IV. CỔ PHIẾU / NGÀNH ĐÓN SÓNG TIỀM NĂNG",
        "I. NHẬN ĐỊNH ĐẦU PHIÊN ATO",
        "II. HÀNH ĐỘNG VỚI DANH MỤC HIỆN TẠI",
        "III. 🎯 TOP CỔ PHIẾU KHUYẾN NGHỊ HÔM NAY",
        "III. TOP CỔ PHIẾU KHUYẾN NGHỊ HÔM NAY"
    ]
    
    fields = []
    paragraphs = clean_text.split("\n\n")
    current_title = "🧠 Nhận định & Khuyến nghị Chiến lược"
    current_chunk = ""

    for p in paragraphs:
        # Kiểm tra xem đoạn p có chứa tiêu đề mục lớn không
        matched_section = None
        for s in sections:
            if s in p:
                matched_section = s
                break
        
        if matched_section:
            if current_chunk.strip():
                fields.append({
                    "name": current_title,
                    "value": current_chunk.strip()[:1024],
                    "inline": False
                })
                current_chunk = ""
            
            # Tách tiêu đề và nội dung
            parts = p.split(matched_section, 1)
            current_title = f"📌 {matched_section}"
            remainder = parts[1].lstrip("*\n :")
            if remainder:
                current_chunk = remainder + "\n\n"
        else:
            if len(current_chunk) + len(p) + 2 > 1000:
                fields.append({
                    "name": current_title,
                    "value": current_chunk.strip()[:1024],
                    "inline": False
                })
                current_title = f"{current_title} (tiếp theo)"
                current_chunk = p.strip() + "\n\n"
            else:
                current_chunk += p.strip() + "\n\n"

    if current_chunk.strip():
        fields.append({
            "name": current_title,
            "value": current_chunk.strip()[:1024],
            "inline": False
        })

    return fields if fields else [{"name": "🧠 Phân tích AI", "value": clean_text[:1024], "inline": False}]


def format_portfolio_embed(portfolio_df, ai_summary: str, report_type: str = "BÁO CÁO PHIÊN") -> dict:
    """
    Format báo cáo danh mục thành Discord Rich Embed sang trọng, trực quan, không bị cắt chữ.
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

    ai_fields = split_ai_summary_into_fields(ai_summary)

    embed = {
        "title": f"📊 AI STOCK COPILOT - {report_type.upper()}",
        "description": f"{summary_pnl}\n\n**Chi tiết từng mã:**\n{portfolio_desc}",
        "color": color,
        "fields": ai_fields,
        "footer": {
            "text": "Stock AI Assistant • Dữ liệu vnstock • Phân tích bởi Gemini",
        },
    }
    return embed


def send_trade_signal_alert(symbol: str, action: str, current_price: float, trigger_reason: str, target_price: float = None, stop_loss: float = None) -> bool:
    """
    Gửi cảnh báo tín hiệu MUA hoặc BÁN bảo mật trực tiếp vào Tin nhắn riêng (DM) của bạn.
    Không gửi vào group/kênh chung để bảo mật danh mục và chiến lược giao dịch cá nhân.
    """
    is_buy = "MUA" in action.upper()
    color = 0x2ECC71 if is_buy else 0xE74C3C
    icon = "🟢" if is_buy else "🔴"
    action_str = "MUA / TÍCH LŨY" if is_buy else "BÁN / HẠ TỶ TRỌNG"

    fields = [
        {"name": "💵 Thị giá hiện tại", "value": f"`{current_price:,.2f} k VND`", "inline": True},
        {"name": "🎯 Lý do kích hoạt", "value": f"`{trigger_reason}`", "inline": False},
    ]
    if target_price:
        fields.append({"name": "🚀 Giá mục tiêu (Target)", "value": f"`{target_price:,.2f} k VND`", "inline": True})
    if stop_loss:
        fields.append({"name": "🛡️ Ngưỡng cắt lỗ (Stop Loss)", "value": f"`{stop_loss:,.2f} k VND`", "inline": True})

    embed = {
        "title": f"{icon} [DM RIÊNG] TÍN HIỆU {action_str}: {symbol.upper()}",
        "description": f"Hệ thống Trading Bot vừa phát hiện tín hiệu kỹ thuật cho mã **{symbol.upper()}** (Gửi bảo mật vào DM riêng)!",
        "color": color,
        "fields": fields,
        "footer": {
            "text": "Trading Signal Bot • Tín hiệu riêng tư 24/7",
        },
    }
    
    # Ưu tiên gửi thẳng vào DM riêng của User
    if DISCORD_BOT_TOKEN and DISCORD_USER_ID:
        return send_discord_dm(embeds=[embed])
    else:
        logging.warning("Chưa cấu hình DISCORD_BOT_TOKEN hoặc DISCORD_USER_ID để gửi DM! Tạm thời fallback sang Webhook...")
        return send_discord_webhook(embeds=[embed])


def send_risk_alert(symbol: str, current_price: float, cost_price: float, trigger_reason: str):
    """
    Gửi cảnh báo rủi ro khẩn cấp vào Tin nhắn riêng (DM).
    """
    pnl_pct = ((current_price - cost_price) / cost_price) * 100
    embed = {
        "title": f"🚨 [DM RIÊNG] CẢNH BÁO RỦI RO: {symbol}",
        "description": (
            f"Mã **{symbol}** vừa kích hoạt tín hiệu quản trị rủi ro!\n\n"
            f"- **Lý do:** `{trigger_reason}`\n"
            f"- **Thị giá hiện tại:** `{current_price}` (Giá vốn: `{cost_price}`)\n"
            f"- **Tỷ lệ vi phạm:** `{pnl_pct:+.2f}%`\n\n"
            f"⚠️ **Khuyến nghị:** Cân nhắc hạ tỷ trọng bảo toàn vốn!"
        ),
        "color": 0xE74C3C,  # Đỏ khẩn cấp
        "footer": {
            "text": "Risk Management Bot • Cảnh báo riêng tư",
        },
    }
    if DISCORD_BOT_TOKEN and DISCORD_USER_ID:
        return send_discord_dm(embeds=[embed])
    else:
        return send_discord_webhook(embeds=[embed])


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
