"""
=============================================================================
🤖 TRADING BOT DAEMON - HỆ THỐNG CANH THỊ TRƯỜNG & CẢNH BÁO DISCORD 24/7
=============================================================================
- Chạy nền độc lập 24/7 (Local hoặc Cloud: Render / Koyeb / VPS).
- Múi giờ chuẩn: Asia/Ho_Chi_Minh (UTC+7) - Tối ưu hoàn hảo cho nhà đầu tư tại Pháp.
- Cảnh báo rủi ro tức thời trong phiên: < 0.5 giây (Stop Loss -5%/-7%, gãy MA20, RSI > 75).
- Báo cáo chiến lược định kỳ:
    + 08:45: Điểm tin vĩ mô đầu ngày trước ATO.
    + 11:30: Tổng kết phiên sáng.
    + 14:45: Báo cáo danh mục & nhận định chiến lược AI sau chốt phiên ATC.
=============================================================================
"""

import time
import logging
from datetime import datetime, time as dtime
from zoneinfo import ZoneInfo
from dotenv import load_dotenv

from data_engine import load_portfolio, evaluate_portfolio, fetch_macro_news
from ai_analyst import generate_portfolio_analysis
from discord_alerts import (
    send_discord_webhook,
    send_discord_dm,
    format_portfolio_embed,
    send_risk_alert
)

load_dotenv()
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] (TradingBot) %(message)s"
)

# Múi giờ thị trường chứng khoán Việt Nam (UTC+7)
VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")

# Lịch sử cảnh báo trong ngày để chống spam (Cooldown)
# Key: (ngày, mã, loại cảnh báo)
sent_alerts = set()
sent_scheduled_reports = set()


def get_vn_time() -> datetime:
    """Lấy thời gian thực tế chính xác theo giờ Việt Nam."""
    return datetime.now(VN_TZ)


def is_trading_day(dt: datetime) -> bool:
    """Thứ 2 (0) đến Thứ 6 (4) là ngày giao dịch."""
    return dt.weekday() < 5


def is_market_open(dt: datetime) -> bool:
    """
    Kiểm tra xem hiện tại có đang trong phiên giao dịch khớp lệnh hay không:
    - Phiên sáng: 09:00:00 - 11:30:00
    - Phiên chiều: 13:00:00 - 14:45:00 (Bao gồm ATC)
    """
    if not is_trading_day(dt):
        return False

    t = dt.time()
    morning = dtime(9, 0) <= t <= dtime(11, 30)
    afternoon = dtime(13, 0) <= t <= dtime(14, 45)
    return morning or afternoon


def check_realtime_risk():
    """
    TẦNG 1: CẢNH BÁO RỦI RO SIÊU TỐC (< 1 GIÂY)
    Quét danh mục mỗi 30s, tính toán toán học thuần túy (không qua AI)
    để nổ chuông Discord ngay lập tức khi cổ phiếu chạm ngưỡng nguy hiểm.
    """
    now = get_vn_time()
    today_str = now.strftime("%Y-%m-%d")

    portfolio = load_portfolio()
    if not portfolio:
        return

    df_eval = evaluate_portfolio(portfolio)
    if df_eval is None or df_eval.empty:
        return

    for _, row in df_eval.iterrows():
        symbol = row["Mã CP"]
        curr_price = float(row["Thị giá (k)"])
        cost_price = float(row["Giá vốn (k)"])
        pnl_pct = float(row["Lãi/Lỗ (%)"])
        vol_ratio = float(row.get("Vol/TB20", 1.0))
        rsi = row.get("RSI(14)")
        status_ma20 = str(row.get("Vị thế MA20", ""))

        # 1. CẢNH BÁO STOP LOSS CẤP ĐỘ 2: ÂM QUÁ -7% (Cắt lỗ dứt khoát)
        alert_key_sl7 = (today_str, symbol, "STOP_LOSS_7")
        if pnl_pct <= -7.0 and alert_key_sl7 not in sent_alerts:
            logging.warning(f"🚨 PHÁT HIỆN VI PHẠM STOP LOSS -7%: {symbol} ({pnl_pct:.2f}%)")
            reason = f"Thị giá sụt giảm nghiêm trọng ({pnl_pct:+.2f}% so với giá vốn). Đã chạm ngưỡng cắt lỗ dứt khoát -7%!"
            send_risk_alert(symbol, curr_price, cost_price, reason)
            sent_alerts.add(alert_key_sl7)
            continue

        # 2. CẢNH BÁO STOP LOSS CẤP ĐỘ 1: ÂM QUÁ -5% (Chạm ngưỡng hạ tỷ trọng)
        alert_key_sl5 = (today_str, symbol, "STOP_LOSS_5")
        if pnl_pct <= -5.0 and alert_key_sl5 not in sent_alerts:
            logging.warning(f"⚠️ PHÁT HIỆN VI PHẠM STOP LOSS -5%: {symbol} ({pnl_pct:.2f}%)")
            reason = f"Thị giá vi phạm ngưỡng cảnh báo đầu tiên ({pnl_pct:+.2f}%). Cân nhắc hạ 50% tỷ trọng bảo toàn vốn!"
            send_risk_alert(symbol, curr_price, cost_price, reason)
            sent_alerts.add(alert_key_sl5)
            continue

        # 3. CẢNH BÁO GÃY HỖ TRỢ MA20 KÈM VOL ĐỘT BIẾN (Áp lực bán tháo)
        alert_key_ma20 = (today_str, symbol, "MA20_BREAKDOWN")
        if "DƯỚI" in status_ma20 and vol_ratio >= 1.5 and alert_key_ma20 not in sent_alerts:
            logging.warning(f"⚠️ PHÁT HIỆN GÃY MA20 KÈM VOL LỚN: {symbol} (Vol x{vol_ratio:.1f})")
            reason = f"Giá xuyên thủng hỗ trợ MA20 với thanh khoản bán đột biến gấp {vol_ratio:.1f}x trung bình 20 phiên!"
            send_risk_alert(symbol, curr_price, cost_price, reason)
            sent_alerts.add(alert_key_ma20)
            continue

        # 4. CẢNH BÁO VÙNG QUÁ MUA HƯNG PHẤN (RSI > 75 - Khuyến nghị chốt lời)
        alert_key_rsi = (today_str, symbol, "RSI_OVERBOUGHT")
        if isinstance(rsi, (int, float)) and rsi >= 75 and alert_key_rsi not in sent_alerts:
            logging.info(f"🎯 PHÁT HIỆN VÙNG QUÁ MUA HƯNG PHẤN: {symbol} (RSI {rsi:.1f})")
            reason = f"Chỉ số RSI đạt {rsi:.1f} (Vùng quá mua cực đại). Đang có sự hưng phấn cao độ, thích hợp hiện thực hóa lợi nhuận từng phần!"
            send_risk_alert(symbol, curr_price, cost_price, reason)
            sent_alerts.add(alert_key_rsi)


def trigger_scheduled_report(report_type: str, title_desc: str):
    """
    TẦNG 2: BÁO CÁO CHIẾN LƯỢC TOÀN DIỆN CỦA AI (HẸN GIỜ CHUẨN XÁC)
    Gọi Gemini phân tích sâu và bắn Rich Embed vào cả Webhook lẫn DM Discord.
    """
    logging.info(f"🚀 BẮT ĐẦU TẠO BÁO CÁO CHIẾN LƯỢC: {report_type} ({title_desc})")
    try:
        portfolio = load_portfolio()
        df_eval = evaluate_portfolio(portfolio)
        news = fetch_macro_news()

        ai_text = generate_portfolio_analysis(df_eval, news)
        embed = format_portfolio_embed(df_eval, ai_text, report_type=report_type)

        # Gửi vào Kênh Webhook chung
        send_discord_webhook(embeds=[embed])

        # Gửi vào Hộp thư cá nhân (DM Bot) của bạn
        send_discord_dm(embeds=[embed])

        logging.info(f"✅ ĐÃ BẮN THÀNH CÔNG BÁO CÁO {report_type} ĐẾN DISCORD!")
    except Exception as e:
        logging.error(f"❌ Lỗi khi gửi báo cáo chiến lược {report_type}: {e}")


def run_trading_bot_loop(check_interval_sec: int = 30):
    """
    VÒNG LẶP CHÍNH CỦA TRADING BOT:
    - Canh đúng từng giây các mốc: 08:45, 11:30, 14:45.
    - Trong giờ giao dịch: Quét giá mỗi 30 giây để bắn cảnh báo khẩn cấp.
    """
    logging.info("=" * 65)
    logging.info("🌟 TRADING BOT DAEMON ĐÃ KHỞI CHẠY THÀNH CÔNG!")
    logging.info(f"🕒 Múi giờ hệ thống: {VN_TZ} (Asia/Ho_Chi_Minh)")
    logging.info(f"⏱️ Tần suất quét rủi ro trong phiên: Mỗi {check_interval_sec} giây")
    logging.info("📅 Khung giờ báo cáo tự động: 08:45 (ATO) | 11:30 (Trưa) | 14:45 (ATC)")
    logging.info("=" * 65)

    last_heartbeat_hour = -1

    while True:
        try:
            now = get_vn_time()
            today_str = now.strftime("%Y-%m-%d")
            cur_time_str = now.strftime("%H:%M")

            # 1. ĐẶT LỊCH: 08:45 SÁNG - BÁO CÁO VĨ MÔ ĐẦU NGÀY TRƯỚC ATO
            key_0845 = (today_str, "08:45")
            if is_trading_day(now) and cur_time_str == "08:45" and key_0845 not in sent_scheduled_reports:
                sent_scheduled_reports.add(key_0845)
                trigger_scheduled_report("BÁO CÁO ĐẦU NGÀY (TRƯỚC PHIÊN ATO)", "Điểm tin vĩ mô thế giới & Sẵn sàng mở phiên")

            # 2. ĐẶT LỊCH: 11:30 TRƯA - TỔNG KẾT PHIÊN SÁNG
            key_1130 = (today_str, "11:30")
            if is_trading_day(now) and cur_time_str == "11:30" and key_1130 not in sent_scheduled_reports:
                sent_scheduled_reports.add(key_1130)
                trigger_scheduled_report("TỔNG KẾT PHIÊN SÁNG (NGHỈ TRƯA)", "Đánh giá biến động nửa ngày & Dòng tiền nổi bật")

            # 3. ĐẶT LỊCH: 14:45 CHIỀU - BÁO CÁO TỔNG KẾT NGÀY SAU ATC
            key_1445 = (today_str, "14:45")
            if is_trading_day(now) and cur_time_str == "14:45" and key_1445 not in sent_scheduled_reports:
                sent_scheduled_reports.add(key_1445)
                trigger_scheduled_report("BÁO CÁO TỔNG KẾT PHIÊN ATC (TOÀN DIỆN)", "Phân tích sức khỏe danh mục & Khuyến nghị phiên tới")

            # 4. TRONG PHIÊN GIAO DỊCH: QUÉT CẢNH BÁO RỦI RO TỨC THÌ (<1s)
            if is_market_open(now):
                check_realtime_risk()
            else:
                # Ngoài giờ hoặc cuối tuần: Ghi log nhịp đập (Heartbeat) mỗi giờ 1 lần
                if now.hour != last_heartbeat_hour:
                    logging.info(f"💤 Ngoài phiên giao dịch VN [{now.strftime('%H:%M:%S %d/%m/%Y')}]. Bot đang ở chế độ chờ tiết kiệm tài nguyên...")
                    last_heartbeat_hour = now.hour

        except Exception as e:
            logging.error(f"Ngoại lệ trong vòng lặp Trading Bot: {e}")

        # Tạm nghỉ trước lần quét kế tiếp
        time.sleep(check_interval_sec)


if __name__ == "__main__":
    run_trading_bot_loop(check_interval_sec=30)
