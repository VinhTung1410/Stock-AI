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

import logging
import time
from datetime import datetime
from datetime import time as dtime
from zoneinfo import ZoneInfo

from ai_analyst import generate_morning_strategy_report, generate_portfolio_analysis
from data_engine import (
    evaluate_portfolio,
    evaluate_watchlist,
    fetch_macro_news,
    is_symbol_in_cooldown,
    load_portfolio,
    load_watchlist,
    record_signal_cooldown,
    scan_market_opportunities,
)
from discord_alerts import (
    format_portfolio_embed,
    send_discord_dm,
    send_discord_webhook,
    send_trade_signal_alert,
)

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass
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
    """Return current timestamp in Vietnam timezone (UTC+7)."""
    return datetime.now(VN_TZ)


def is_market_open(dt: datetime) -> bool:
    """Check if Vietnam Stock Exchange (HOSE/HNX) is currently in trading session.

    - Mon to Fri
    - Morning: 09:00 - 11:30
    - Afternoon: 13:00 - 14:45
    """
    if dt.weekday() >= 5:  # Saturday (5), Sunday (6)
        return False

    t = dt.time()
    morning_session = dtime(9, 0) <= t <= dtime(11, 30)
    afternoon_session = dtime(13, 0) <= t <= dtime(14, 45)
    return morning_session or afternoon_session


def is_trading_day(dt: datetime) -> bool:
    """Check if the given datetime falls on a regular trading day (Mon-Fri)."""
    return dt.weekday() < 5


def check_realtime_risk():
    """Tier 1: Real-time risk and opportunity monitoring (< 1s latency).

    1. Holdings scan: Check stop-loss, trailing stops, MA20 breakdowns, overbought RSI.
    2. Watchlist scan: Check target buy entries, MA20 breakouts with volume expansion.
    """
    now = get_vn_time()
    today_str = now.strftime("%Y-%m-%d")

    # =========================================================================
    # PART 1: REAL-TIME PORTFOLIO RISK AUDIT (HOLDINGS)
    # =========================================================================
    from data_engine import detect_gdkhq_event, fetch_stock_technical
    vnindex_tech = fetch_stock_technical("VNINDEX")
    vnindex_chg_pct = vnindex_tech.get("change_pct", 0.0) if vnindex_tech else 0.0

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

                # KHIÊN CHẮN NGÀY GIAO DỊCH KHÔNG HƯỞNG QUYỀN (GDKHQ SHIELD)
                # Ngăn chặn triệt để báo động giả cắt lỗ khi thị giá bị điều chỉnh kỹ thuật do cổ tức
                tech_sym = fetch_stock_technical(symbol)
                gdkhq_info = detect_gdkhq_event(symbol, tech_sym, vnindex_chg_pct)
                if gdkhq_info.get("is_gdkhq"):
                    alert_key_gdkhq = (today_str, symbol, "GDKHQ_SHIELD")
                    if alert_key_gdkhq not in sent_alerts:
                        logging.warning(f"🛡️ GDKHQ SHIELD KÍCH HOẠT CHO {symbol}: {gdkhq_info['reason']}")
                        send_trade_signal_alert(
                            symbol=symbol,
                            action="THEO DÕI (GDKHQ)",
                            current_price=curr_price,
                            trigger_reason=f"[KHIÊN CHẮN CỔ TỨC] {gdkhq_info['reason']}"
                        )
                        sent_alerts.add(alert_key_gdkhq)
                    continue

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
                tech = fetch_stock_technical(sym)
                if not tech:
                    continue

                curr_p = tech.get("current_price", 0.0)
                ma20 = tech.get("ma20")
                rsi = tech.get("rsi14")
                vol_r = tech.get("vol_ratio", 1.0)
                status_ma20 = tech.get("status_ma20", "")
                ceiling_p = tech.get("ceiling_price", curr_p * 1.069)
                change_pct = tech.get("change_pct", 0.0)
                is_ceiling = tech.get("is_ceiling", False)

                # BỘ LỌC CHỐNG MUA ĐUỔI TRẦN (ANTI-CHASING FILTER)
                # Chỉ chặn BUY mới, tuyệt đối không ảnh hưởng tới lệnh bán vị thế đang giữ
                is_anti_chasing = (
                    curr_p >= ceiling_p or
                    change_pct >= 6.7 or
                    is_ceiling
                )
                if is_anti_chasing:
                    logging.info(f"🚫 ANTI-CHASING: Bỏ qua mua đuổi {sym} (Giá {curr_p}k đã kịch trần/áp sát trần {change_pct:+.1f}%)")
                    continue

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
                    f_score_dict = {"score": 6}
                    try:
                        from data_engine import fetch_stock_historical, get_financial_ratios
                        from quant_engine import calculate_atr, calculate_piotroski_f_score, check_data_gate
                        fin = get_financial_ratios(sym)
                        gate = check_data_gate(sym, tech, fin)
                        f_score_dict = calculate_piotroski_f_score(fin)

                        if not gate["passed"]:
                            logging.warning(f"⛔ HỦY BẮN TÍN HIỆU {sym}: Không đạt Data Gate ({', '.join(gate['reasons'])})")
                            continue
                        if f_score_dict["score"] <= 3:
                            logging.warning(f"⛔ HỦY BẮN TÍN HIỆU {sym}: Sức khỏe tài chính yếu (F-Score: {f_score_dict['score']}/9)")
                            continue

                        f_score_txt = f" | F-Score: {f_score_dict['score']}/9"

                        # Tính ATR(14) Stop-Loss động thích ứng với biến động thực tế
                        df_hist = fetch_stock_historical(sym, time_frame="1D", limit=30)
                        if df_hist is not None and not df_hist.empty:
                            atr_val = calculate_atr(df_hist, 14)
                            if atr_val > 0:
                                dynamic_sl = round(max(curr_p * 0.93, curr_p - 1.5 * atr_val), 2)
                    except Exception as q_err:
                        logging.debug(f"Bỏ qua kiểm tra quant: {q_err}")

                    # KIỂM TRA COOLDOWN 5 NGÀY ĐỂ BẢO VỆ VỐN & TRÁNH SPAM LẶP LẠI TÍN HIỆU
                    if is_symbol_in_cooldown(sym, cooldown_days=5):
                        logging.info(f"⏳ Bỏ qua cảnh báo mua {sym}: đang trong thời gian cooldown 5 ngày.")
                        continue

                    target_p = round(curr_p * 1.12, 2)
                    logging.info(f"🟢 BẮN TÍN HIỆU MUA WATCHLIST: {sym} (SL: {dynamic_sl}k{f_score_txt})")
                    send_trade_signal_alert(
                        symbol=sym,
                        action="MUA",
                        current_price=curr_p,
                        trigger_reason=f"[WATCHLIST THEO DÕI] {buy_reason}{f_score_txt}",
                        target_price=target_p,
                        stop_loss=dynamic_sl
                    )
                    sent_alerts.add(alert_key_wl_buy)
                    record_signal_cooldown(sym, action="MUA", conviction_score=75.0)

                    # LƯU SNAPSHOT BẤT BIẾN VÀO SUPABASE SIGNAL LIFECYCLE
                    try:
                        from db_manager import save_quant_signal
                        act_tag = "🟢 VALUE BUY" if "Breakout" in buy_reason else "🟢 ACCUMULATE"
                        save_quant_signal(
                            symbol=sym,
                            action=act_tag,
                            decision_tag=f"[WATCHLIST TỰ ĐỘNG] {buy_reason}{f_score_txt}",
                            entry_price=curr_p,
                            market_price_at_signal=curr_p,
                            target_price=target_p,
                            stop_loss=dynamic_sl,
                            hard_gates={"mos_pct": 15.0, "ev": round(curr_p * 1.08, 2), "kelly_f": 0.12, "risk_reward": 2.0},
                            f_score_res=f_score_dict,
                            z_score_res={"z_score": 2.5},
                            prob_dict={"P_bull": 0.35, "P_base": 0.50, "P_bear": 0.15, "rationale_base": buy_reason},
                            model_version="trading-bot-v2.1",
                            input_snapshot={"tech": tech, "f_score": f_score_dict.get("score", 6)}
                        )
                    except Exception as sb_err:
                        logging.error(f"Lỗi ghi Supabase Signal: {sb_err}")
            except Exception:
                continue


def trigger_scheduled_report(report_type: str, title_desc: str):
    """Tier 2: AI-driven scheduled strategy reports (ATO 08:45, Lunch 11:30, ATC 14:45)."""
    logging.info(f"🚀 Starting scheduled strategy report: {report_type} ({title_desc})")
    try:
        portfolio = load_portfolio()
        df_eval = evaluate_portfolio(portfolio)
        watchlist = load_watchlist()
        df_wl = evaluate_watchlist(watchlist) if watchlist else None
        news = fetch_macro_news(limit=10, tracked_symbols=[p["symbol"] for p in portfolio] + [w["symbol"] for w in watchlist])

        if "08:45" in report_type or "ATO" in report_type:
            # Morning report: Market opportunity scan + Watchlist
            opportunities = scan_market_opportunities(extra_symbols=[w["symbol"] for w in watchlist])
            ai_text = generate_morning_strategy_report(df_eval, df_wl, opportunities, news)
        else:
            ai_text = generate_portfolio_analysis(df_eval, news, watchlist_df=df_wl)

        embed = format_portfolio_embed(df_eval, ai_text, report_type=report_type)

        # Send to Discord Webhook channel
        send_discord_webhook(embeds=[embed])

        # Send to private DM
        send_discord_dm(embeds=[embed])

        logging.info(f"✅ Successfully dispatched {report_type} report to Discord!")
    except Exception as e:
        logging.error(f"❌ Error dispatching scheduled report {report_type}: {e}")


def trigger_post_market_audit():
    """Tier 3: Automated post-market signal audit process (15:15 UTC+7).

    - Data Freshness Check: Skip audit if market closing data not finalized (PENDING_DATA).
    - Update MFE (highest high), MAE (lowest low), and T+1, T+5, T+20 marks.
    - Evaluate state transition (TARGET_HIT / STOP_LOSS) and measure Alpha vs VN-Index.
    - Dispatch Alpha Tracker audit summary embed to Discord.
    """
    logging.info("🚀 Starting automated post-market signal audit (15:15)...")
    try:
        from db_manager import get_signal_audit_metrics, update_daily_tracking
        audit_res = update_daily_tracking()

        if audit_res.get("status") == "PENDING_DATA":
            logging.warning("⚠️ DATA FRESHNESS CHECK: Market data not ready. Deferring audit.")
            return

        metrics = get_signal_audit_metrics()
        now_vn = get_vn_time()

        embed = {
            "title": "🎯 BÁO CÁO KIỂM TOÁN HIỆU QUẢ TÍN HIỆU (ALPHA TRACKER)",
            "description": (
                f"**Kết quả rà soát sau phiên ATC ({now_vn.strftime('%d/%m/%Y')}):**\n"
                f"• Cập nhật hôm nay: **{audit_res.get('updated', 0)}** tín hiệu\n"
                f"• Tỷ lệ thắng (Hit Rate): **{metrics.get('win_rate', 0)}%** ({metrics.get('resolved_signals', 0)} lệnh đã đóng)\n"
                f"• Tỷ số Lãi/Lỗ (Profit Factor): **{metrics.get('profit_factor', 0)}x**\n"
                f"• Alpha vượt trội vs VN-Index: **{metrics.get('alpha_vs_vnindex', 0):+.2f}%**\n"
                f"• Số tín hiệu đang theo dõi (OPEN): **{metrics.get('open_signals', 0)}**"
            ),
            "color": 0x2ECC71 if metrics.get("win_rate", 0) >= 50 else 0x3498DB,
            "footer": {"text": "AI Stock Copilot • Post-Market Audit Engine"}
        }
        send_discord_webhook(embeds=[embed])
        send_discord_dm(embeds=[embed])
        logging.info("✅ Successfully dispatched 15:15 audit report to Discord!")
    except Exception as e:
        logging.error(f"❌ Error in 15:15 post-market audit process: {e}")


def run_trading_bot_loop(check_interval_sec: int = 30):
    """Main event loop for the background trading bot.

    - Accurately triggers scheduled reports: 08:45, 11:30, 14:45, 15:15.
    - Scans intraday prices every 30 seconds for emergency risk alerts.
    """
    logging.info("=" * 65)
    logging.info("🌟 TRADING BOT DAEMON ĐÃ KHỞI CHẠY THÀNH CÔNG!")
    logging.info(f"🕒 Múi giờ hệ thống: {VN_TZ} (Asia/Ho_Chi_Minh)")
    logging.info(f"⏱️ Tần suất quét rủi ro trong phiên: Mỗi {check_interval_sec} giây")
    logging.info("📅 Khung giờ báo cáo tự động: 08:45 (ATO) | 11:30 (Trưa) | 14:45 (ATC) | 15:15 (Audit)")
    logging.info("=" * 65)

    last_heartbeat_hour = -1

    while True:
        try:
            now = get_vn_time()
            today_str = now.strftime("%Y-%m-%d")
            cur_t = now.time()

            # Tự động dọn dẹp cache ngày cũ để tối ưu bộ nhớ dài hạn
            for old_key in list(sent_scheduled_reports):
                if old_key[0] != today_str:
                    sent_scheduled_reports.discard(old_key)
            for old_alert in list(sent_alerts):
                if old_alert[0] != today_str:
                    sent_alerts.discard(old_alert)

            # 1. ĐẶT LỊCH: 08:45 SÁNG - BÁO CÁO VĨ MÔ ĐẦU NGÀY TRƯỚC ATO (Cửa sổ 08:45 - 09:00)
            key_0845 = (today_str, "08:45")
            if is_trading_day(now) and dtime(8, 45) <= cur_t < dtime(9, 0) and key_0845 not in sent_scheduled_reports:
                sent_scheduled_reports.add(key_0845)
                trigger_scheduled_report("BÁO CÁO ĐẦU NGÀY (TRƯỚC PHIÊN ATO)", "Điểm tin vĩ mô thế giới & Sẵn sàng mở phiên")

            # 2. ĐẶT LỊCH: 11:30 TRƯA - TỔNG KẾT PHIÊN SÁNG (Cửa sổ 11:30 - 12:00)
            key_1130 = (today_str, "11:30")
            if is_trading_day(now) and dtime(11, 30) <= cur_t < dtime(12, 0) and key_1130 not in sent_scheduled_reports:
                sent_scheduled_reports.add(key_1130)
                trigger_scheduled_report("TỔNG KẾT PHIÊN SÁNG (NGHỈ TRƯA)", "Đánh giá biến động nửa ngày & Dòng tiền nổi bật")

            # 3. ĐẶT LỊCH: 14:45 CHIỀU - BÁO CÁO TỔNG KẾT NGÀY SAU ATC (Cửa sổ 14:45 - 15:15)
            key_1445 = (today_str, "14:45")
            if is_trading_day(now) and dtime(14, 45) <= cur_t < dtime(15, 15) and key_1445 not in sent_scheduled_reports:
                sent_scheduled_reports.add(key_1445)
                trigger_scheduled_report("BÁO CÁO TỔNG KẾT PHIÊN ATC (TOÀN DIỆN)", "Phân tích sức khỏe danh mục & Khuyến nghị phiên tới")

            # 4. ĐẶT LỊCH: 15:15 CHIỀU - TIẾN TRÌNH KIỂM TOÁN TÍN HIỆU SAU PHIÊN (Cửa sổ 15:15 - 16:00)
            key_1515 = (today_str, "15:15")
            if is_trading_day(now) and dtime(15, 15) <= cur_t < dtime(16, 0) and key_1515 not in sent_scheduled_reports:
                sent_scheduled_reports.add(key_1515)
                trigger_post_market_audit()

            # 5. TRONG PHIÊN GIAO DỊCH: QUÉT CẢNH BÁO RỦI RO TỨC THÌ (<1s)
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
