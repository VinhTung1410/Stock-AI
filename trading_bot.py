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

from data_engine import (
    load_portfolio, 
    evaluate_portfolio, 
    load_watchlist, 
    evaluate_watchlist, 
    scan_market_opportunities, 
    fetch_macro_news
)
from ai_analyst import generate_portfolio_analysis, generate_morning_strategy_report
from discord_alerts import (
    send_discord_webhook,
    send_discord_dm,
    format_portfolio_embed,
    send_risk_alert,
    send_trade_signal_alert
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
    """Lấy thời gian hiện tại chuẩn múi giờ Việt Nam."""
    return datetime.now(VN_TZ)


def is_market_open(dt: datetime) -> bool:
    """
    Kiểm tra thị trường chứng khoán Việt Nam có đang trong phiên giao dịch không:
    - Thứ 2 đến Thứ 6.
    - Sáng: 09:00 - 11:30.
    - Chiều: 13:00 - 14:45.
    """
    if dt.weekday() >= 5:  # Thứ 7 (5), Chủ Nhật (6)
        return False

    t = dt.time()
    morning_session = dtime(9, 0) <= t <= dtime(11, 30)
    afternoon_session = dtime(13, 0) <= t <= dtime(14, 45)
    return morning_session or afternoon_session


def is_trading_day(dt: datetime) -> bool:
    """Kiểm tra có phải ngày giao dịch (Thứ 2 đến Thứ 6) không."""
    return dt.weekday() < 5


def check_realtime_risk():
    """
    TẦNG 1: CẢNH BÁO TỨC THÌ (< 1 GIÂY) VÀO DM DISCORD RIÊNG
    1. Quét Danh mục Nắm giữ (Holdings): Bắn cảnh báo BÁN/Cắt lỗ (-5%, -7%, gãy MA20, RSI > 75).
    2. Quét Danh mục Theo dõi (Watchlist): Bắn cảnh báo MUA (chạm giá chờ mua, bứt phá MA20 + vol).
    """
    now = get_vn_time()
    today_str = now.strftime("%Y-%m-%d")

    # =========================================================================
    # PHẦN 1: QUÉT QUẢN TRỊ RỦI RO DANH MỤC NẮM GIỮ (PORTFOLIO)
    # =========================================================================
    portfolio = load_portfolio()
    if portfolio:
        df_eval = evaluate_portfolio(portfolio)
        if df_eval is not None and not df_eval.empty:
            for _, row in df_eval.iterrows():
                symbol = row["Mã CP"]
                curr_price = float(row["Thị giá (k)"])
                cost_price = float(row["Giá vốn (k)"])
                pnl_pct = float(row["Lãi/Lỗ (%)"])
                vol_ratio = float(row.get("Vol/TB20", 1.0))
                rsi = row.get("RSI(14)")
                status_ma20 = str(row.get("Vị thế MA20", ""))

                # 1. CẢNH BÁO BÁN: STOP LOSS CẤP ĐỘ 2 (ÂM QUÁ -7% - Cắt lỗ dứt khoát)
                alert_key_sl7 = (today_str, symbol, "STOP_LOSS_7")
                if pnl_pct <= -7.0 and alert_key_sl7 not in sent_alerts:
                    logging.warning(f"🚨 PHÁT HIỆN VI PHẠM STOP LOSS -7%: {symbol} ({pnl_pct:.2f}%)")
                    reason = f"Thị giá sụt giảm nghiêm trọng ({pnl_pct:+.2f}% so với giá vốn). Đã chạm ngưỡng cắt lỗ dứt khoát -7%!"
                    send_trade_signal_alert(symbol, "BÁN", curr_price, reason, stop_loss=curr_price)
                    sent_alerts.add(alert_key_sl7)
                    continue

                # 2. CẢNH BÁO BÁN: STOP LOSS CẤP ĐỘ 1 (ÂM QUÁ -5% - Hạ 50% tỷ trọng)
                alert_key_sl5 = (today_str, symbol, "STOP_LOSS_5")
                if pnl_pct <= -5.0 and alert_key_sl5 not in sent_alerts:
                    logging.warning(f"⚠️ PHÁT HIỆN VI PHẠM STOP LOSS -5%: {symbol} ({pnl_pct:.2f}%)")
                    reason = f"Thị giá vi phạm ngưỡng cảnh báo đầu tiên ({pnl_pct:+.2f}%). Cân nhắc hạ 50% tỷ trọng bảo toàn vốn!"
                    send_trade_signal_alert(symbol, "BÁN", curr_price, reason, stop_loss=cost_price * 0.93)
                    sent_alerts.add(alert_key_sl5)
                    continue

                # 3. CẢNH BÁO BÁN: GÃY HỖ TRỢ MA20 KÈM VOL ĐỘT BIẾN (Áp lực bán tháo)
                alert_key_ma20_break = (today_str, symbol, "MA20_BREAKDOWN")
                if "DƯỚI" in status_ma20 and vol_ratio >= 1.5 and alert_key_ma20_break not in sent_alerts:
                    logging.warning(f"⚠️ PHÁT HIỆN GÃY MA20 KÈM VOL LỚN: {symbol} (Vol x{vol_ratio:.1f})")
                    reason = f"Giá xuyên thủng hỗ trợ MA20 với thanh khoản bán đột biến gấp {vol_ratio:.1f}x trung bình 20 phiên!"
                    send_trade_signal_alert(symbol, "BÁN", curr_price, reason)
                    sent_alerts.add(alert_key_ma20_break)
                    continue

                # 4. CẢNH BÁO BÁN: VÙNG QUÁ MUA HƯNG PHẤN (RSI >= 75 - Khuyến nghị chốt lời)
                alert_key_rsi_sell = (today_str, symbol, "RSI_OVERBOUGHT")
                if isinstance(rsi, (int, float)) and rsi >= 75 and alert_key_rsi_sell not in sent_alerts:
                    logging.info(f"🎯 PHÁT HIỆN VÙNG QUÁ MUA HƯNG PHẤN: {symbol} (RSI {rsi:.1f})")
                    reason = f"Chỉ số RSI đạt {rsi:.1f} (Vùng quá mua cực đại). Đang có sự hưng phấn cao độ, thích hợp hiện thực hóa lợi nhuận từng phần!"
                    send_trade_signal_alert(symbol, "BÁN", curr_price, reason, target_price=curr_price * 1.05)
                    sent_alerts.add(alert_key_rsi_sell)
                    continue

    # =========================================================================
    # PHẦN 2: QUÉT ĐIỂM MUA CHO DANH MỤC THEO DÕI (WATCHLIST)
    # =========================================================================
    watchlist = load_watchlist()
    if watchlist:
        for item in watchlist:
            sym = item["symbol"]
            target_buy = float(item.get("target_buy", 0.0))
            alert_key_wl_buy = (today_str, sym, "WATCHLIST_BUY")
            if alert_key_wl_buy in sent_alerts:
                continue

            try:
                from data_engine import fetch_stock_technical
                tech = fetch_stock_technical(sym)
                if not tech:
                    continue

                curr_p = tech.get("current_price", 0.0)
                ma20 = tech.get("ma20")
                rsi = tech.get("rsi14")
                vol_r = tech.get("vol_ratio", 1.0)
                status_ma20 = tech.get("status_ma20", "")

                buy_triggered = False
                buy_reason = ""

                # Điều kiện 1: Chạm vùng giá chờ mua thiết lập sẵn
                if target_buy > 0 and curr_p <= target_buy:
                    buy_triggered = True
                    buy_reason = f"Thị giá ({curr_p}k) đã chạm/về dưới vùng giá chờ mua ({target_buy}k) anh đã đặt trước!"
                # Điều kiện 2: Breakout MA20 kèm Vol bùng nổ
                elif "TRÊN" in status_ma20 and vol_r >= 1.3:
                    buy_triggered = True
                    buy_reason = f"Phát hiện điểm nổ Breakout MA20 kèm thanh khoản gấp {vol_r:.1f}x TB20 phiên!"
                # Điều kiện 3: RSI chạm vùng quá bán bắt đáy (RSI <= 32)
                elif isinstance(rsi, (int, float)) and rsi <= 32:
                    buy_triggered = True
                    buy_reason = f"RSI({rsi:.1f}) rơi vào vùng QUÁ BÁN sâu (< 32), cơ hội gom vị thế giá rẻ!"

                if buy_triggered:
                    # HÀNG RÀO KIỂM DUYỆT ĐỊNH LƯỢNG (QUANTAMENTAL SAFETY FILTER)
                    dynamic_sl = round(curr_p * 0.94, 2)
                    f_score_txt = ""
                    try:
                        from data_engine import get_financial_ratios, fetch_stock_historical
                        from quant_engine import check_data_gate, calculate_piotroski_f_score, calculate_atr
                        fin = get_financial_ratios(sym)
                        gate = check_data_gate(sym, tech, fin)
                        f_score = calculate_piotroski_f_score(fin)
                        
                        if not gate["passed"]:
                            logging.warning(f"⛔ HỦY BẮN TÍN HIỆU {sym}: Không đạt Data Gate ({', '.join(gate['reasons'])})")
                            continue
                        if f_score["score"] <= 3:
                            logging.warning(f"⛔ HỦY BẮN TÍN HIỆU {sym}: Sức khỏe tài chính yếu (F-Score: {f_score['score']}/9)")
                            continue

                        f_score_txt = f" | F-Score: {f_score['score']}/9"
                        
                        # Tính ATR(14) Stop-Loss động thích ứng với biến động thực tế
                        df_hist = fetch_stock_historical(sym, time_frame="1D", limit=30)
                        if df_hist is not None and not df_hist.empty:
                            atr_val = calculate_atr(df_hist, 14)
                            if atr_val > 0:
                                # Stop Loss động: Giữ khoảng cách 1.5x ATR nhưng không lùi quá sàn HOSE (-7%)
                                dynamic_sl = round(max(curr_p * 0.93, curr_p - 1.5 * atr_val), 2)
                    except Exception as q_err:
                        logging.debug(f"Bỏ qua kiểm tra quant: {q_err}")

                    logging.info(f"🟢 BẮN TÍN HIỆU MUA WATCHLIST: {sym} (SL: {dynamic_sl}k{f_score_txt})")
                    send_trade_signal_alert(
                        symbol=sym,
                        action="MUA",
                        current_price=curr_p,
                        trigger_reason=f"[WATCHLIST THEO DÕI] {buy_reason}{f_score_txt}",
                        target_price=round(curr_p * 1.12, 2),
                        stop_loss=dynamic_sl
                    )
                    sent_alerts.add(alert_key_wl_buy)
            except Exception as e:
                continue


def trigger_scheduled_report(report_type: str, title_desc: str):
    """
    TẦNG 2: BÁO CÁO CHIẾN LƯỢC TOÀN DIỆN CỦA AI (HẸN GIỜ CHUẨN XÁC)
    - 08:45 Sáng: Báo cáo khuyến nghị đầu ngày (Gợi ý cổ phiếu tiềm năng chuẩn CTCK).
    - 11:30 & 14:45: Báo cáo đánh giá danh mục & chiến lược phiên.
    """
    logging.info(f"🚀 BẮT ĐẦU TẠO BÁO CÁO CHIẾN LƯỢC: {report_type} ({title_desc})")
    try:
        portfolio = load_portfolio()
        df_eval = evaluate_portfolio(portfolio)
        watchlist = load_watchlist()
        df_wl = evaluate_watchlist(watchlist) if watchlist else None
        news = fetch_macro_news(limit=10, tracked_symbols=[p["symbol"] for p in portfolio] + [w["symbol"] for w in watchlist])

        if "08:45" in report_type or "ATO" in report_type:
            # Báo cáo đầu ngày: Quét cơ hội thị trường + Watchlist
            opportunities = scan_market_opportunities(extra_symbols=[w["symbol"] for w in watchlist])
            ai_text = generate_morning_strategy_report(df_eval, df_wl, opportunities, news)
        else:
            ai_text = generate_portfolio_analysis(df_eval, news, watchlist_df=df_wl)

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
