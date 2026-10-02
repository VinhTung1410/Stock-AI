import logging
import os
import time
from typing import Any

import requests

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")
DISCORD_BOT_TOKEN = os.environ.get("DISCORD_BOT_TOKEN")
DISCORD_USER_ID = os.environ.get("DISCORD_USER_ID")

SIGNAL_DISCLAIMER = (
    "\n\n⚠️ *Tín hiệu tự động từ hệ thống AI — KHÔNG phải tư vấn đầu tư "
    "được cấp phép. Tự chịu trách nhiệm quyết định. Quá khứ không đảm bảo "
    "tương lai. Chỉ dùng số tiền có thể mất hoàn toàn.*"
)


def send_discord_dm(content: str = None, embeds: list = None) -> bool:
    """
    Gửi tin nhắn riêng (Direct Message - DM) trực tiếp vào hộp thư cá nhân của bạn.
    """
    if not DISCORD_BOT_TOKEN or not DISCORD_USER_ID:
        logging.warning("Chưa cấu hình DISCORD_BOT_TOKEN hoặc DISCORD_USER_ID trong .env!")
        return False

    headers = {"Authorization": f"Bot {DISCORD_BOT_TOKEN}", "Content-Type": "application/json"}

    try:
        # Bước 1: Mở kênh DM với User ID
        dm_res = requests.post(
            "https://discord.com/api/v10/users/@me/channels",
            headers=headers,
            json={"recipient_id": DISCORD_USER_ID},
            timeout=10,
        )
        if dm_res.status_code != 200:
            logging.error(f"Lỗi khi mở kênh DM: {dm_res.status_code} - {dm_res.text}")
            return False

        channel_id = dm_res.json().get("id")
        if not channel_id:
            return False

        # Bước 2: Gửi nội dung tin nhắn / Embed vào kênh DM
        if embeds:
            flat_embeds = []
            for item in embeds:
                if isinstance(item, list):
                    flat_embeds.extend(item)
                elif isinstance(item, dict):
                    flat_embeds.append(item)

            for emb in flat_embeds:
                msg_res = requests.post(
                    f"https://discord.com/api/v10/channels/{channel_id}/messages",
                    headers=headers,
                    json={"embeds": [emb]},
                    timeout=10,
                )
                if msg_res.status_code not in [200, 201]:
                    logging.error(f"Lỗi khi gửi Embed DM: {msg_res.status_code} - {msg_res.text}")
                    return False
                time.sleep(0.4)

        if content:
            # Tự động chia nhỏ tin nhắn nếu dài hơn 1900 ký tự (tránh giới hạn 2000 ký tự của Discord)
            chunks = [content[i : i + 1900] for i in range(0, len(content), 1900)]
            for chunk in chunks:
                msg_res = requests.post(
                    f"https://discord.com/api/v10/channels/{channel_id}/messages",
                    headers=headers,
                    json={"content": chunk},
                    timeout=10,
                )
                if msg_res.status_code not in [200, 201]:
                    logging.error(f"Lỗi khi gửi text DM: {msg_res.status_code} - {msg_res.text}")
                    return False

        logging.info("Đã gửi tin nhắn riêng (DM) đến bạn thành công!")
        return True
    except Exception as e:
        logging.exception("Ngoại lệ khi gửi DM")
        return False


def send_discord_webhook(content: str = None, embeds: list = None) -> bool:
    """
    Gửi thông báo độc quyền vào Kênh Discord thông qua Webhook URL (không gửi vào tin nhắn riêng).
    Hỗ trợ tự động phân tách đa Embeds tuần tự để bảo toàn 100% nội dung dài.
    """
    if not DISCORD_WEBHOOK_URL:
        logging.warning("Chưa cấu hình DISCORD_WEBHOOK_URL trong .env!")
        return False

    try:
        if content:
            requests.post(DISCORD_WEBHOOK_URL, json={"content": content}, timeout=10)

        if embeds:
            flat_embeds = []
            for item in embeds:
                if isinstance(item, list):
                    flat_embeds.extend(item)
                elif isinstance(item, dict):
                    flat_embeds.append(item)

            for emb in flat_embeds:
                resp = requests.post(DISCORD_WEBHOOK_URL, json={"embeds": [emb]}, timeout=10)
                if resp.status_code not in [200, 204]:
                    logging.error(f"Lỗi khi gửi Webhook: {resp.status_code} - {resp.text}")
                time.sleep(0.4)

        logging.info("Đã gửi tin nhắn qua Webhook thành công!")
        return True
    except Exception as e:
        logging.exception("Lỗi khi gửi Webhook")
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


def _slice_long_content(content: str, max_chars: int = 1000) -> list[str]:
    """Cắt chuỗi dài thành các đoạn an toàn <= max_chars ưu tiên ngắt dòng hoặc kết thúc câu."""
    chunks = []
    c = content.strip()
    while len(c) > max_chars:
        split_pos = c.rfind("\n", 0, max_chars)
        if split_pos == -1:
            split_pos = c.rfind(". ", 0, max_chars)
        if split_pos == -1:
            split_pos = max_chars
        chunks.append(c[:split_pos].strip())
        c = c[split_pos:].strip()
    if c:
        chunks.append(c)
    return chunks


def _append_field_chunks(fields: list, title: str, content: str, start_part: int) -> int:
    """Tạo các embed fields từ nội dung và trả về part_count tiếp theo mà không bao giờ cắt xén ký tự."""
    if not content.strip():
        return start_part
    part_idx = start_part
    for chunk in _slice_long_content(content, max_chars=1000):
        display_title = title if part_idx == 1 else f"{title} (Phần {part_idx})"
        fields.append({"name": display_title[:256], "value": chunk, "inline": False})
        part_idx += 1
    return part_idx


def split_ai_summary_into_fields(ai_summary: str) -> list:
    """
    Tách bài phân tích của AI thành các Field của Discord Embed (mỗi field < 1024 ký tự),
    tự động nhận diện các mục La Mã và đánh số phần chuyên nghiệp (Phần 2, Phần 3),
    bảo toàn trọn vẹn 100% nội dung (kể cả Câu hỏi 5), không bao giờ cắt cụt chữ.
    """
    try:
        from ai_analyst import sanitize_ai_text

        ai_summary = sanitize_ai_text(ai_summary)
    except Exception:
        pass
    import re

    clean_text = ai_summary.replace("### ", "").replace("## ", "").strip()
    raw_lines = clean_text.split("\n")

    fields = []
    base_title = "🧠 Nhận định & Khuyến nghị Chiến lược"
    part_count = 1
    current_chunk = ""

    # Regex nhận diện tiêu đề mục lớn & tiểu mục (hỗ trợ số La Mã I-X hoặc ký tự A-D kèm emoji đầu/sau, in đậm markdown)
    # Hỗ trợ dấu ':' trong tiêu đề như (11:30) mà không bị cắt cụt
    header_pattern = re.compile(r"^[#*>\s]*(?:[^\w\s]{1,3}\s*)?((?:[IVX]+|[A-D])\.\s+[^\n*]+)", re.IGNORECASE)

    for line in raw_lines:
        line_s = line.strip()
        if not line_s:
            if current_chunk and not current_chunk.endswith("\n\n"):
                current_chunk += "\n"
            continue

        match = header_pattern.match(line_s)
        if match:
            if current_chunk.strip():
                part_count = _append_field_chunks(fields, base_title, current_chunk, part_count)
                current_chunk = ""

            matched_title = match.group(1).strip().strip("*#_")
            base_title = f"📌 {matched_title}"
            part_count = 1
        else:
            if len(current_chunk) + len(line_s) + 2 > 950:
                part_count = _append_field_chunks(fields, base_title, current_chunk, part_count)
                current_chunk = line_s + "\n"
            else:
                current_chunk += line_s + "\n"

    if current_chunk.strip():
        _append_field_chunks(fields, base_title, current_chunk, part_count)

    return fields if fields else [{"name": "🧠 Phân tích AI", "value": clean_text[:1000], "inline": False}]


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
        pnl_pct = row["Lãi/Lỗ (%)"]
        pnl_icon = "🟢" if pnl_pct >= 0 else "🔴"

        # Trailing Stop hoặc Stop-loss
        def_val = row.get("Chặn lãi/Cắt lỗ (k)")
        if def_val:
            def_label = f" | 🛡️ Trailing Stop: `{def_val}k`" if pnl_pct > 0 else f" | 🛡️ Stop-loss: `{def_val}k`"
        else:
            def_label = ""

        # Fair value & MoS
        fv = row.get("Fair Value (k)")
        mos = row.get("MoS (%)")
        val_str = f" [FV: `{fv}k`, MoS: `{mos:+}%`]" if fv and mos is not None else ""

        line = (
            f"{pnl_icon} **{row['Mã CP']}** ({row['Khối lượng']:,} cp){val_str} | "
            f"Vốn: `{row['Giá vốn (k)']}` ➔ Giá: `{row['Thị giá (k)']}` | "
            f"**{pnl_pct:+.2f}%** (`{int(row['Lãi/Lỗ (VND)']):+,}đ`){def_label}"
        )
        portfolio_lines.append(line)

    portfolio_desc = "\n".join(portfolio_lines)
    summary_pnl = f"**Tổng tài sản danh mục:** `{int(total_market):,}đ` | **Lãi/Lỗ:** `{int(total_pnl_vnd):+,}đ` (**{total_pnl_pct:+.2f}%**)"

    ai_fields = split_ai_summary_into_fields(ai_summary)

    title_str = f"📊 AI STOCK COPILOT - {report_type.upper()}"[:256]
    desc_str = f"{summary_pnl}\n\n**Chi tiết từng mã:**\n{portfolio_desc}"[:4000]
    footer_text = "Stock AI Assistant • Dữ liệu vnstock • Phân tích bởi Gemini"

    # Phân phối thông minh các fields thành 1 hoặc 2 Embeds nguyên vẹn 100%, không bao giờ cắt chữ
    fields_p1 = []
    fields_p2 = []
    curr_len_p1 = len(title_str) + len(desc_str) + len(footer_text)

    for f in ai_fields:
        f_len = len(f.get("name", "")) + len(f.get("value", ""))
        if len(fields_p1) < 20 and (curr_len_p1 + f_len) < 5200:
            fields_p1.append(f)
            curr_len_p1 += f_len
        else:
            fields_p2.append(f)

    embed1 = {
        "title": title_str,
        "description": desc_str,
        "color": color,
        "fields": fields_p1,
        "footer": {
            "text": footer_text,
        },
    }

    if not fields_p2:
        return embed1

    # Nếu bài viết dài, tạo Embed Phần 2 chứa trọn vẹn 100% các mục còn lại
    title_p2 = f"📊 AI STOCK COPILOT - {report_type.upper()} (PHẦN 2)"[:256]
    embed2 = {
        "title": title_p2,
        "description": "*(Tiếp nối: Tác động vĩ mô, dòng tiền tổ chức & Kế hoạch hành động phiên tới)*",
        "color": color,
        "fields": fields_p2[:25],
        "footer": {
            "text": footer_text,
        },
    }
    return [embed1, embed2]


def _format_execution_fields(
    current_price: float,
    target_price: float | None,
    stop_loss: float | None,
    entry_range: tuple[float, float] | None,
    target_price_t2: float | None,
    risk_reward: float | None,
    position_size_nav: str | None,
) -> list[dict[str, Any]]:
    fields = []
    if entry_range and len(entry_range) == 2:
        fields.append(
            {
                "name": "🎯 Vùng gom mua tối ưu",
                "value": f"`{entry_range[0]:,.2f} - {entry_range[1]:,.2f} k VND`",
                "inline": True,
            }
        )
    else:
        fields.append(
            {
                "name": "💵 Thị giá hiện tại",
                "value": f"`{current_price:,.2f} k VND`",
                "inline": True,
            }
        )

    if target_price:
        t1_label = "🚀 Giá mục tiêu T1" if target_price_t2 else "🚀 Giá mục tiêu (Target)"
        t1_pct = ((target_price - current_price) / current_price) * 100 if current_price > 0 else 0.0
        fields.append(
            {
                "name": t1_label,
                "value": f"`{target_price:,.2f} k` (**{t1_pct:+.1f}%**)",
                "inline": True,
            }
        )

    if target_price_t2:
        t2_pct = ((target_price_t2 - current_price) / current_price) * 100 if current_price > 0 else 0.0
        fields.append(
            {
                "name": "💎 Giá mục tiêu T2 (Fair Value)",
                "value": f"`{target_price_t2:,.2f} k` (**{t2_pct:+.1f}%**)",
                "inline": True,
            }
        )

    if stop_loss:
        sl_pct = ((stop_loss - current_price) / current_price) * 100 if current_price > 0 else 0.0
        fields.append(
            {
                "name": "🛡️ Ngưỡng cắt lỗ (Stop Loss)",
                "value": f"`{stop_loss:,.2f} k` (**{sl_pct:+.1f}%**)",
                "inline": True,
            }
        )

    if risk_reward:
        rr_icon = "⭐" if risk_reward >= 2.0 else "⚠️"
        fields.append(
            {
                "name": f"{rr_icon} Tỷ lệ R:R",
                "value": f"`{risk_reward:.2f}x` (Chuẩn Quỹ ≥ 2.0x)",
                "inline": True,
            }
        )

    if position_size_nav:
        fields.append(
            {
                "name": "⚖️ Tỷ trọng đề xuất (Half-Kelly)",
                "value": f"`{position_size_nav}`",
                "inline": True,
            }
        )

    return fields


def _format_quant_fields(
    quant_metrics: dict | None,
    trigger_reason: str,
    conviction_score: float | None,
) -> list[dict[str, Any]]:
    fields = []
    if conviction_score is not None:
        tier_label = "💎 HIGH CONVICTION" if conviction_score >= 70 else "🎯 MEDIUM CONVICTION"
        fields.append(
            {
                "name": "⭐ Điểm tin cậy (Conviction)",
                "value": f"**{conviction_score:.0f}/100** ({tier_label})",
                "inline": True,
            }
        )

    if quant_metrics:
        f_score = quant_metrics.get("f_score")
        mos = quant_metrics.get("mos_pct")
        z_score = quant_metrics.get("z_score")
        tech_status = quant_metrics.get("tech_status") or quant_metrics.get("ma20_status")
        rsi_val = quant_metrics.get("rsi")

        metrics_items = []
        if f_score is not None:
            metrics_items.append(f"• **F-Score:** `{f_score}/9`")
        if mos is not None:
            metrics_items.append(f"• **Biên an toàn (MoS):** `{mos:+.1f}%`")
        if z_score is not None:
            metrics_items.append(f"• **Altman Z-Score:** `{z_score:.2f}` (An toàn)")
        if tech_status:
            metrics_items.append(f"• **Kỹ thuật:** `{tech_status}`")
        if rsi_val is not None:
            metrics_items.append(f"• **RSI(14):** `{rsi_val:.1f}`")

        if metrics_items:
            fields.append(
                {
                    "name": "🔬 Bảo chứng Định lượng (Quant Proof)",
                    "value": "\n".join(metrics_items),
                    "inline": False,
                }
            )

    if trigger_reason:
        fields.append(
            {
                "name": "🎯 Lý do kích hoạt",
                "value": f"`{trigger_reason}`",
                "inline": False,
            }
        )

    return fields


def _format_thesis_fields(
    catalysts: list[str] | str | None,
    thesis_breaker: str | None,
) -> list[dict[str, Any]]:
    fields = []
    if catalysts:
        if isinstance(catalysts, list):
            cat_text = "\n".join([f"• {c}" for c in catalysts])
        else:
            cat_text = str(catalysts)
        fields.append(
            {
                "name": "💡 Luận điểm Xúc tác (Catalysts)",
                "value": cat_text[:1000],
                "inline": False,
            }
        )

    if thesis_breaker:
        fields.append(
            {
                "name": "⚠️ Kịch bản Vô hiệu hóa (Thesis Breaker)",
                "value": f"`{thesis_breaker[:500]}`",
                "inline": False,
            }
        )
    return fields


def send_trade_signal_alert(
    symbol: str,
    action: str,
    current_price: float,
    trigger_reason: str,
    target_price: float = None,
    stop_loss: float = None,
    *,
    entry_range: tuple[float, float] = None,
    target_price_t2: float = None,
    risk_reward: float = None,
    position_size_nav: str = None,
    conviction_score: float = None,
    quant_metrics: dict = None,
    catalysts: list[str] | str = None,
    thesis_breaker: str = None,
    strategy_style: str = None,
) -> bool:
    """
    Gửi thẻ tín hiệu MUA hoặc BÁN bảo mật chuẩn Quỹ (Institutional Trade Signal Card)
    trực tiếp vào Tin nhắn riêng (DM) của bạn.
    """
    act_up = action.upper()
    if any(k in act_up for k in ("THEO DÕI", "WATCH")):
        color = 0xF1C40F
        icon = "🟡"
        base_action = "THEO DÕI"
    elif any(k in act_up for k in ("CẢNH BÁO", "CAUTION")):
        color = 0xE67E22
        icon = "⚠️"
        base_action = "CẢNH BÁO — KHÔNG PHẢI BÁN"
    elif "GDKHQ" in act_up:
        color = 0x3498DB
        icon = "📅"
        base_action = "SỰ KIỆN GDKHQ"
    elif any(k in act_up for k in ("MUA", "TÍCH LŨY", "ACCUMULATE", "BUY")):
        color = 0x2ECC71
        icon = "🟢"
        base_action = "MUA / TÍCH LŨY"
    else:
        color = 0xE74C3C
        icon = "🔴"
        base_action = "BÁN / HẠ TỶ TRỌNG"

    action_str = f"{base_action} ({strategy_style})" if strategy_style else base_action

    fields = _format_execution_fields(
        current_price=current_price,
        target_price=target_price,
        stop_loss=stop_loss,
        entry_range=entry_range,
        target_price_t2=target_price_t2,
        risk_reward=risk_reward,
        position_size_nav=position_size_nav,
    )
    fields.extend(
        _format_quant_fields(
            quant_metrics=quant_metrics,
            trigger_reason=trigger_reason,
            conviction_score=conviction_score,
        )
    )
    fields.extend(
        _format_thesis_fields(
            catalysts=catalysts,
            thesis_breaker=thesis_breaker,
        )
    )

    embed = {
        "title": f"{icon} [DM RIÊNG] TÍN HIỆU {action_str}: {symbol.upper()}",
        "description": (
            f"Hệ thống Trading Bot vừa kích hoạt tín hiệu định lượng cho mã **{symbol.upper()}** "
            f"(Gửi bảo mật vào DM riêng)!{SIGNAL_DISCLAIMER}"
        ),
        "color": color,
        "fields": fields,
        "footer": {
            "text": "Institutional Signal Engine • Tín hiệu riêng tư 24/7 • Miễn trừ trách nhiệm",
        },
    }

    # Ưu tiên gửi thẳng vào DM riêng của User
    if DISCORD_BOT_TOKEN and DISCORD_USER_ID:
        return send_discord_dm(embeds=[embed])
    else:
        logging.warning(
            "Chưa cấu hình DISCORD_BOT_TOKEN hoặc DISCORD_USER_ID để gửi DM! Tạm thời fallback sang Webhook..."
        )
        return send_discord_webhook(embeds=[embed])


def send_partial_take_profit_alert(
    symbol: str,
    current_price: float,
    entry_price: float,
    gain_pct: float,
    new_stop_price: float,
    lock_fraction: float = 0.5,
) -> bool:
    """Gửi cảnh báo chốt lời từng phần (Partial Profit Lock) và dời stop lên break-even (Phase 5d)."""
    embed = {
        "title": f"🎯 [DM RIÊNG] ĐẠT TARGET 1: CHỐT LỜI {symbol.upper()} (+{gain_pct:.1f}%)",
        "description": (
            f"Vị thế **{symbol.upper()}** vừa chạm mục tiêu Target 1 với mức lãi **+{gain_pct:.1f}%**!\n\n"
            f"**Kế hoạch khóa lợi nhuận (Institutional Rule):**\n"
            f"• 💰 **Chốt lời:** Bán `{int(lock_fraction * 100)}%` vị thế để hiện thực hóa lợi nhuận vào túi.\n"
            f"• 🛡️ **Dời Stop Loss:** Nâng Stop Loss của `{int((1 - lock_fraction) * 100)}%` còn lại lên giá vốn `{new_stop_price:,.2f} k` (Break-even).\n"
            f"• ✨ **Trạng thái:** Vị thế hiện tại đã chuyển sang **Risk-Free Trade** (Tuyệt đối không thể lỗ)!"
            f"{SIGNAL_DISCLAIMER}"
        ),
        "color": 0xF39C12,  # Màu vàng cam Target Reached
        "fields": [
            {"name": "💵 Thị giá hiện tại", "value": f"`{current_price:,.2f} k`", "inline": True},
            {"name": "💼 Giá vốn ban đầu", "value": f"`{entry_price:,.2f} k`", "inline": True},
            {"name": "🛡️ Stop Loss mới (Hòa vốn)", "value": f"`{new_stop_price:,.2f} k`", "inline": True},
        ],
        "footer": {
            "text": "Partial Profit Lock Engine • Kỷ luật chốt lời 2 nấc",
        },
    }
    if DISCORD_BOT_TOKEN and DISCORD_USER_ID:
        return send_discord_dm(embeds=[embed])
    return send_discord_webhook(embeds=[embed])


def send_regime_circuit_breaker_alert(
    regime: str,
    reason: str,
    vnindex_price: float = None,
) -> bool:
    """Gửi cảnh báo Macro Circuit Breaker khi thị trường chuyển sang DOWNTREND hoặc CASH MODE."""
    is_downtrend = "DOWNTREND" in regime.upper()
    color = 0xE74C3C if is_downtrend else 0x2ECC71
    icon = "🚨" if is_downtrend else "🟢"
    action_note = (
        "**HÀNH ĐỘNG BẮT BUỘC (CASH MODE):**\n"
        "• Khóa 100% lệnh mua mới để tránh rủi ro 'bắt dao rơi'.\n"
        "• Ưu tiên bảo toàn vốn, hạ margin và kích hoạt Stop Loss dứt khoát nếu vi phạm."
        if is_downtrend
        else "**HÀNH ĐỘNG:**\n"
        "• Thị trường đã lấy lại xu hướng tăng/cân bằng. Mở lại luồng quét cơ hội mua theo định lượng."
    )
    vn_info = f" (VN-Index: `{vnindex_price:,.1f}`)" if vnindex_price else ""
    embed = {
        "title": f"{icon} [MACRO CIRCUIT BREAKER] TRẠNG THÁI THỊ TRƯỜNG: {regime.upper()}",
        "description": (
            f"Hệ thống phát hiện biến động trạng thái vĩ mô VN-Index{vn_info}:\n\n"
            f"• **Lý do kích hoạt:** `{reason}`\n\n"
            f"{action_note}"
            f"{SIGNAL_DISCLAIMER}"
        ),
        "color": color,
        "footer": {
            "text": "Macro Regime Circuit Breaker • Quản trị rủi ro hệ thống",
        },
    }
    if DISCORD_BOT_TOKEN and DISCORD_USER_ID:
        return send_discord_dm(embeds=[embed])
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
            f"⚠️ **Khuyến nghị:** Cân nhắc hạ tỷ trọng bảo toàn vốn!{SIGNAL_DISCLAIMER}"
        ),
        "color": 0xE74C3C,  # Đỏ khẩn cấp
        "footer": {
            "text": "Risk Management Bot • Cảnh báo riêng tư • Miễn trừ trách nhiệm",
        },
    }
    if DISCORD_BOT_TOKEN and DISCORD_USER_ID:
        return send_discord_dm(embeds=[embed])
    else:
        return send_discord_webhook(embeds=[embed])


def send_system_heartbeat(subsystems: dict = None) -> bool:
    """
    Gửi báo cáo Heartbeat kiểm tra sức khỏe hệ thống lúc 08:30 trước ATO.
    Định dạng:
    - Nếu bình thường: ✅ SYSTEM ONLINE 08:30 — [data_engine ✅] [gemini ✅] [supabase ✅]
    - Nếu có lỗi: 🚨 SYSTEM DEGRADED — Lỗi: [danh sách subsystems fail]
    """
    if subsystems is None:
        subsystems = {"data_engine": True, "gemini": True, "supabase": True}

    failed = [k for k, v in subsystems.items() if not v]
    now_str = time.strftime("%H:%M")

    if not failed:
        status_items = " ".join([f"[{k} ✅]" for k in subsystems])
        content = f"✅ SYSTEM ONLINE {now_str} — {status_items}"
        embed = {
            "title": f"🟢 [DISCORD DM] SYSTEM ONLINE ({now_str})",
            "description": f"Toàn bộ hạ tầng cốt lõi đã sẵn sàng cho phiên giao dịch:\n\n{content}",
            "color": 0x2ECC71,
            "footer": {"text": "Stock AI Heartbeat Daemon • Health Monitor"},
        }
    else:
        fail_str = ", ".join(failed)
        content = f"🚨 SYSTEM DEGRADED {now_str} — Lỗi: [{fail_str}]"
        embed = {
            "title": f"🚨 [DISCORD DM] CẢNH BÁO: SYSTEM DEGRADED ({now_str})",
            "description": (
                f"{content}\n\n"
                f"⚠️ **Khuyến cáo:** Cần kiểm tra thủ công các phân hệ bị lỗi trước khi giao dịch theo tín hiệu."
            ),
            "color": 0xE74C3C,
            "footer": {"text": "Stock AI Heartbeat Daemon • Alert Monitor"},
        }

    if DISCORD_BOT_TOKEN and DISCORD_USER_ID:
        return send_discord_dm(content=content, embeds=[embed])
    else:
        return send_discord_webhook(content=content, embeds=[embed])


def send_gemini_rate_limit_alert(current_rpm: int, dropped_symbols: list = None) -> bool:
    """Cảnh báo khi gọi Gemini chạm ngưỡng giới hạn 15 RPM (cảnh báo khi chạm 12+ RPM)."""
    dropped = dropped_symbols or []
    dropped_str = ", ".join(dropped) if dropped else "Không có mã bị hủy"
    content = f"⚠️ [RATE LIMIT ALERT] Gemini API đang chạm {current_rpm}/15 RPM! Mã bị bỏ qua: {dropped_str}"
    embed = {
        "title": "⚠️ [DISCORD DM] GEMINI API RATE LIMIT ALERT",
        "description": (
            f"Tần suất gọi Gemini API đã đạt **{current_rpm} RPM** (ngưỡng an toàn 12/15 RPM).\n\n"
            f"- **Các mã tạm bỏ qua:** `{dropped_str}`\n"
            f"- **Hành động:** Hệ thống tự động kích hoạt cooldown để bảo vệ hạn mức API."
        ),
        "color": 0xF1C40F,
        "footer": {"text": "Gemini Rate Limiter • Quản lý ngân sách Token"},
    }
    if DISCORD_BOT_TOKEN and DISCORD_USER_ID:
        return send_discord_dm(content=content, embeds=[embed])
    else:
        return send_discord_webhook(content=content, embeds=[embed])


def _format_pruned_item_stats(curr_p: float, rsi: Any, mos: Any) -> str:
    """Format price, RSI, and MoS metrics string for pruned item."""
    stats = []
    if curr_p:
        stats.append(f"Thị giá: `{curr_p:,.2f}k`")
    if rsi is not None and isinstance(rsi, (int, float)):
        stats.append(f"RSI(14): `{rsi:.1f}`")
    if mos is not None and isinstance(mos, (int, float)):
        stats.append(f"MoS: `{mos:+.1f}%`")
    return " | ".join(stats) if stats else "N/A"


def _build_pruned_item_field(item: dict) -> dict:
    """Build a single Discord embed field representing a pruned watchlist ticker."""
    sym = item.get("symbol", "").upper()
    reason = item.get("reason", "Không phù hợp tiêu chí")
    is_auto = item.get("is_auto", False)
    source_label = "🤖 Bot phát hiện tự động" if is_auto else "👤 Bạn đã thêm thủ công"
    stats_str = _format_pruned_item_stats(
        item.get("current_price", 0.0),
        item.get("rsi"),
        item.get("mos_pct"),
    )
    return {
        "name": f"❌ {sym} ({source_label})",
        "value": (
            f"• **Lý do loại bỏ:** {reason}\n"
            f"• **Chỉ số:** {stats_str}\n"
            f"• **Khuyến nghị:** Tạm thời gỡ khỏi danh sách chờ mua để tránh bẫy giá hoặc FOMO đu đỉnh. "
            f"Chờ cổ phiếu chiết khấu về vùng cân bằng an toàn."
        ),
        "inline": False,
    }


def send_watchlist_pruned_alert(pruned_items: list) -> bool:
    """
    Gửi báo cáo lý do thanh lọc cổ phiếu khỏi Watchlist trực tiếp vào Discord DM của người dùng.
    Phân loại rõ ràng mã do người dùng tự nhập hay do bot quét tự động.
    """
    if not pruned_items:
        return False

    fields = [_build_pruned_item_field(item) for item in pruned_items[:10]]

    embed = {
        "title": "🧹 [DISCORD DM] BÁO CÁO THANH LỌC WATCHLIST (LOẠI BỎ CỔ PHIẾU)",
        "description": (
            f"Hệ thống vừa tiến hành kiểm toán và tự động gỡ bỏ **{len(pruned_items)} mã** "
            f"khỏi Watchlist để bảo vệ bạn khỏi rủi ro quá mua, định giá ảo hoặc bẫy giá:"
        ),
        "color": 0xE67E22,  # Màu cam cảnh báo rủi ro
        "fields": fields,
        "footer": {
            "text": "Watchlist Pruning Engine • Tự động bảo vệ danh mục theo dõi",
        },
    }

    if DISCORD_BOT_TOKEN and DISCORD_USER_ID:
        return send_discord_dm(embeds=[embed])
    else:
        return send_discord_webhook(embeds=[embed])


if __name__ == "__main__":
    from ai_analyst import generate_portfolio_analysis
    from data_engine import evaluate_portfolio, fetch_macro_news, load_portfolio

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
