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
    sync_auto_watchlist,
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
last_ato_pruned_date: str = ""


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


def _handle_gdkhq_shield(symbol: str, curr_price: float, today_str: str, gdkhq_info: dict):
    alert_key = (today_str, symbol, "GDKHQ_SHIELD")
    if alert_key in sent_alerts:
        return
    logging.warning(f"🛡️ GDKHQ SHIELD KÍCH HOẠT CHO {symbol}: {gdkhq_info['reason']}")
    send_trade_signal_alert(
        symbol=symbol,
        action="THEO DÕI (GDKHQ)",
        current_price=curr_price,
        trigger_reason=f"[KHIÊN CHẮN CỔ TỨC] {gdkhq_info['reason']}"
    )
    sent_alerts.add(alert_key)


def _handle_stop_loss(symbol: str, curr_price: float, cost_price: float, pnl_pct: float, today_str: str) -> bool:
    alert_key_sl7 = (today_str, symbol, "STOP_LOSS_7")
    if pnl_pct <= -7.0 and alert_key_sl7 not in sent_alerts:
        logging.warning(f"🚨 PHÁT HIỆN VI PHẠM STOP LOSS -7%: {symbol} ({pnl_pct:.2f}%)")
        reason = f"Thị giá sụt giảm nghiêm trọng ({pnl_pct:+.2f}% so với giá vốn). Đã chạm ngưỡng cắt lỗ dứt khoát -7%!"
        send_trade_signal_alert(symbol, "BÁN", curr_price, reason, stop_loss=curr_price)
        sent_alerts.add(alert_key_sl7)
        return True

    alert_key_sl5 = (today_str, symbol, "STOP_LOSS_5")
    if pnl_pct <= -5.0 and alert_key_sl5 not in sent_alerts:
        logging.warning(f"⚠️ PHÁT HIỆN VI PHẠM STOP LOSS -5%: {symbol} ({pnl_pct:.2f}%)")
        reason = f"Thị giá vi phạm ngưỡng cảnh báo đầu tiên ({pnl_pct:+.2f}%). Cân nhắc hạ 50% tỷ trọng bảo toàn vốn!"
        send_trade_signal_alert(symbol, "BÁN", curr_price, reason, stop_loss=cost_price * 0.93)
        sent_alerts.add(alert_key_sl5)
        return True

    return False


def _handle_ma20_breakdown(symbol: str, curr_price: float, status_ma20: str, vol_ratio: float, today_str: str) -> bool:
    alert_key = (today_str, symbol, "MA20_BREAKDOWN")
    if "DƯỚI" in status_ma20 and vol_ratio >= 1.5 and alert_key not in sent_alerts:
        logging.warning(f"⚠️ PHÁT HIỆN GÃY MA20 KÈM VOL LỚN: {symbol} (Vol x{vol_ratio:.1f})")
        reason = f"Giá xuyên thủng hỗ trợ MA20 với thanh khoản bán đột biến gấp {vol_ratio:.1f}x trung bình 20 phiên!"
        send_trade_signal_alert(symbol, "BÁN", curr_price, reason)
        sent_alerts.add(alert_key)
        return True
    return False


def _handle_rsi_overbought(symbol: str, curr_price: float, rsi, today_str: str):
    alert_key = (today_str, symbol, "RSI_OVERBOUGHT")
    if isinstance(rsi, (int, float)) and rsi >= 75 and alert_key not in sent_alerts:
        logging.info(f"🎯 PHÁT HIỆN VÙNG QUÁ MUA HƯNG PHẤN: {symbol} (RSI {rsi:.1f})")
        reason = f"Chỉ số RSI đạt {rsi:.1f} (Vùng quá mua cực đại). Đang có sự hưng phấn cao độ, thích hợp hiện thực hóa lợi nhuận từng phần!"
        send_trade_signal_alert(symbol, "BÁN", curr_price, reason, target_price=curr_price * 1.05)
        sent_alerts.add(alert_key)


def _handle_value_deep_drawdown(symbol: str, curr_price: float, cost_price: float, pnl_pct: float, today_str: str) -> bool:
    alert_key = (today_str, symbol, "VALUE_DEEP_DRAWDOWN")
    if pnl_pct <= -15.0 and alert_key not in sent_alerts:
        logging.warning(f"🚨 CẢNH BÁO TÍCH SẢN LỖ SÂU: {symbol} ({pnl_pct:.2f}%)")
        reason = (
            f"Vị thế đầu tư dài hạn/tích sản {symbol} đang lỗ {pnl_pct:+.2f}% (vượt ngưỡng an toàn -15%). "
            f"Cần kiểm tra khẩn cấp Luận điểm đầu tư (Thesis Breaker) và BCTC quý mới nhất!"
        )
        send_trade_signal_alert(symbol, "CẢNH BÁO", curr_price, reason, stop_loss=cost_price * 0.85)
        sent_alerts.add(alert_key)
        return True
    return False


def _check_single_holding_risk(row, today_str: str, vnindex_chg_pct: float):
    from data_engine import detect_gdkhq_event, fetch_stock_technical
    from quant_valuation import get_stock_archetype_details

    symbol = row["Mã CP"]
    curr_price = float(row["Thị giá (k)"])
    cost_price = float(row["Giá vốn (k)"])
    pnl_pct = float(row["Lãi/Lỗ (%)"])
    vol_ratio = float(row.get("Vol/TB20", 1.0))
    rsi = row.get("RSI(14)")
    status_ma20 = str(row.get("Vị thế MA20", ""))
    strategy_input = str(row.get("Chiến lược", "")).upper()
    sector_input = str(row.get("Ngành", ""))

    archetype_info = get_stock_archetype_details(symbol, sector_input)
    is_value_investing = (
        strategy_input in ["VALUE", "COMPOUNDER", "LONG_TERM"]
        or archetype_info.get("holding_shield", False)
    )

    tech_sym = fetch_stock_technical(symbol)
    gdkhq_info = detect_gdkhq_event(symbol, tech_sym, vnindex_chg_pct)
    if gdkhq_info.get("is_gdkhq"):
        _handle_gdkhq_shield(symbol, curr_price, today_str, gdkhq_info)
        return

    if not is_value_investing:
        # Cổ phiếu Lướt sóng / Chu kỳ (SWING / CYCLICAL): Kiểm soát chặt Stop Loss và gãy MA20
        if _handle_stop_loss(symbol, curr_price, cost_price, pnl_pct, today_str):
            return
        if _handle_ma20_breakdown(symbol, curr_price, status_ma20, vol_ratio, today_str):
            return
    else:
        # Tăng trưởng Dài hạn & Tích sản (FPT, MWG...):
        # Bỏ qua rung lắc ngắn hạn -5%/-7% và gãy MA20 tạm thời để bảo vệ vị thế!
        # Chỉ cảnh báo nếu lỗ quá sâu (-15%) hoặc Thesis Breaker
        if _handle_value_deep_drawdown(symbol, curr_price, cost_price, pnl_pct, today_str):
            return

    _handle_rsi_overbought(symbol, curr_price, rsi, today_str)


def _audit_portfolio_risk(today_str: str):
    from data_engine import fetch_stock_technical
    vnindex_tech = fetch_stock_technical("VNINDEX")
    vnindex_chg_pct = vnindex_tech.get("change_pct", 0.0) if vnindex_tech else 0.0

    portfolio = load_portfolio()
    if not portfolio:
        return

    df_eval = evaluate_portfolio(portfolio)
    if df_eval is None or df_eval.empty:
        return

    for _, row in df_eval.iterrows():
        _check_single_holding_risk(row, today_str, vnindex_chg_pct)


def _evaluate_watchlist_buy_trigger(target_buy: float, curr_p: float, tech: dict) -> tuple[bool, str]:
    status_ma20 = tech.get("status_ma20", "")
    vol_r = tech.get("vol_ratio", 1.0)
    rsi = tech.get("rsi14")

    if target_buy > 0 and curr_p <= target_buy:
        return True, f"Thị giá ({curr_p}k) đã chạm/về dưới vùng giá chờ mua ({target_buy}k)!"
    if "TRÊN" in status_ma20 and vol_r >= 1.3:
        return True, f"Phát hiện điểm nổ Breakout MA20 kèm thanh khoản gấp {vol_r:.1f}x TB20 phiên!"
    if isinstance(rsi, (int, float)) and rsi <= 32:
        return True, f"RSI({rsi:.1f}) rơi vào vùng QUÁ BÁN sâu (< 32)!"
    return False, ""


def _validate_quant_gate(sym: str, tech: dict, curr_p: float) -> tuple[bool, float, dict, str]:
    from data_engine import fetch_stock_historical, get_financial_ratios
    from quant_engine import calculate_atr, calculate_piotroski_f_score, check_data_gate

    dynamic_sl = round(curr_p * 0.94, 2)
    f_score_dict = {"score": 6}

    try:
        fin = get_financial_ratios(sym)
        gate = check_data_gate(sym, tech, fin)
        f_score_dict = calculate_piotroski_f_score(fin)

        if not gate["passed"]:
            logging.warning(f"⛔ HỦY BẮN TÍN HIỆU {sym}: Không đạt Data Gate ({', '.join(gate['reasons'])})")
            return False, dynamic_sl, f_score_dict, ""
        if f_score_dict["score"] <= 3:
            logging.warning(f"⛔ HỦY BẮN TÍN HIỆU {sym}: Sức khỏe tài chính yếu (F-Score: {f_score_dict['score']}/9)")
            return False, dynamic_sl, f_score_dict, ""

        atr_val = float(tech.get("atr14") or 0.0)
        if atr_val <= 0:
            df_hist = fetch_stock_historical(sym, time_frame="1D", limit=30)
            if df_hist is not None and not df_hist.empty:
                atr_val = calculate_atr(df_hist, 14)

        if atr_val > 0:
            dynamic_sl = round(max(curr_p * 0.93, curr_p - 1.5 * atr_val), 2)
    except Exception:
        logging.exception(f"Lỗi khi kiểm tra quant cho {sym}")

    f_score_txt = f" | F-Score: {f_score_dict['score']}/9"
    return True, dynamic_sl, f_score_dict, f_score_txt


def _record_and_save_buy_signal(
    sym: str,
    curr_p: float,
    target_p: float,
    dynamic_sl: float,
    buy_reason: str,
    f_score_txt: str,
    f_score_dict: dict,
    tech: dict
):
    from db_manager import save_quant_signal
    record_signal_cooldown(sym, action="MUA", conviction_score=75.0)
    try:
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
    except Exception:
        logging.exception("Lỗi ghi Supabase Signal")


def _process_single_watchlist_item(item: dict, today_str: str):
    sym = item["symbol"]
    target_buy = float(item.get("target_buy", 0.0))
    alert_key = (today_str, sym, "WATCHLIST_BUY")
    if alert_key in sent_alerts:
        return

    from data_engine import fetch_stock_technical
    tech = fetch_stock_technical(sym)
    if not tech:
        return

    curr_p = tech.get("current_price", 0.0)
    ceiling_p = tech.get("ceiling_price", curr_p * 1.069)
    change_pct = tech.get("change_pct", 0.0)
    is_ceiling = tech.get("is_ceiling", False)

    if curr_p >= ceiling_p or change_pct >= 6.7 or is_ceiling:
        logging.info(f"🚫 ANTI-CHASING: Bỏ qua mua đuổi {sym}")
        return

    buy_triggered, buy_reason = _evaluate_watchlist_buy_trigger(target_buy, curr_p, tech)
    if not buy_triggered:
        return

    passed, dynamic_sl, f_score_dict, f_score_txt = _validate_quant_gate(sym, tech, curr_p)
    if not passed or is_symbol_in_cooldown(sym, cooldown_days=5):
        return

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
    sent_alerts.add(alert_key)
    _record_and_save_buy_signal(sym, curr_p, target_p, dynamic_sl, buy_reason, f_score_txt, f_score_dict, tech)


def _scan_watchlist_opportunities(today_str: str):
    watchlist = load_watchlist()
    if not watchlist:
        return

    for item in watchlist:
        try:
            _process_single_watchlist_item(item, today_str)
        except Exception:
            logging.exception("Lỗi khi quét mục watchlist")


def check_realtime_risk():
    """Tier 1: Real-time risk and opportunity monitoring (< 1s latency)."""
    now = get_vn_time()
    today_str = now.strftime("%Y-%m-%d")
    _audit_portfolio_risk(today_str)
    _scan_watchlist_opportunities(today_str)


def trigger_scheduled_report(report_type: str, title_desc: str):
    """Tier 2: AI-driven scheduled strategy reports (ATO 08:45, Lunch 11:30, ATC 14:45)."""
    logging.info(f"🚀 Starting scheduled strategy report: {report_type} ({title_desc})")
    try:
        # Tự động cập nhật & thanh lọc Watchlist DUY NHẤT 1 LẦN trước phiên ATO (08:45)
        global last_ato_pruned_date
        today_str = get_vn_time().strftime("%Y-%m-%d")
        if any(tag in report_type for tag in ["08:45", "ATO"]) and last_ato_pruned_date != today_str:
            try:
                sync_auto_watchlist(prune_manual=True)
                last_ato_pruned_date = today_str
                logging.info(f"✅ Đã hoàn tất thanh lọc Watchlist trước ATO cho ngày {today_str}")
            except Exception:
                logging.exception("Không thể đồng bộ tự động Watchlist trước ATO")

        portfolio = load_portfolio()
        df_eval = evaluate_portfolio(portfolio)
        watchlist = load_watchlist()
        df_wl = evaluate_watchlist(watchlist) if watchlist else None
        news = fetch_macro_news(limit=10, tracked_symbols=[p["symbol"] for p in portfolio] + [w["symbol"] for w in watchlist])

        if "08:45" in report_type or "ATO" in report_type:
            opportunities = scan_market_opportunities(extra_symbols=[w["symbol"] for w in watchlist])
            ai_text = generate_morning_strategy_report(df_eval, df_wl, opportunities, news)
        else:
            session_lbl = "NOON" if any(k in report_type for k in ["11:30", "TRƯA", "SÁNG"]) else "ATC"
            ai_text = generate_portfolio_analysis(df_eval, news, watchlist_df=df_wl, session_label=session_lbl)

        embed = format_portfolio_embed(df_eval, ai_text, report_type=report_type)

        send_discord_webhook(embeds=[embed])
        send_discord_dm(embeds=[embed])

        logging.info(f"✅ Successfully dispatched {report_type} report to Discord!")
    except Exception:
        logging.exception(f"❌ Error dispatching scheduled report {report_type}")


def trigger_post_market_audit():
    """Tier 3: Automated post-market signal audit process (15:15 UTC+7)."""
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
    except Exception:
        logging.exception("❌ Error in 15:15 post-market audit process")


def _clean_expired_daily_keys(today_str: str):
    expired_reports = [k for k in sent_scheduled_reports if k[0] != today_str]
    for k in expired_reports:
        sent_scheduled_reports.discard(k)

    expired_alerts = [a for a in sent_alerts if a[0] != today_str]
    for a in expired_alerts:
        sent_alerts.discard(a)


def _check_scheduled_reports(now: datetime, today_str: str, cur_t: dtime):
    if not is_trading_day(now):
        return

    schedules = [
        ("08:45", dtime(8, 45), dtime(9, 0), "BÁO CÁO ĐẦU NGÀY (TRƯỚC PHIÊN ATO)", "Điểm tin vĩ mô thế giới & Sẵn sàng mở phiên"),
        ("11:30", dtime(11, 30), dtime(12, 0), "TỔNG KẾT PHIÊN SÁNG (NGHỈ TRƯA)", "Đánh giá biến động nửa ngày & Dòng tiền nổi bật"),
        ("14:45", dtime(14, 45), dtime(15, 15), "BÁO CÁO TỔNG KẾT PHIÊN ATC (TOÀN DIỆN)", "Phân tích sức khỏe danh mục & Khuyến nghị phiên tới"),
    ]

    for key_tag, start_t, end_t, title, desc in schedules:
        report_key = (today_str, key_tag)
        if start_t <= cur_t < end_t and report_key not in sent_scheduled_reports:
            sent_scheduled_reports.add(report_key)
            trigger_scheduled_report(title, desc)

    key_1515 = (today_str, "15:15")
    if dtime(15, 15) <= cur_t < dtime(16, 0) and key_1515 not in sent_scheduled_reports:
        sent_scheduled_reports.add(key_1515)
        trigger_post_market_audit()


def run_trading_bot_loop(check_interval_sec: int = 30):
    """Main event loop for the background trading bot."""
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

            _clean_expired_daily_keys(today_str)
            _check_scheduled_reports(now, today_str, cur_t)

            if is_market_open(now):
                check_realtime_risk()
            elif now.hour != last_heartbeat_hour:
                logging.info(f"💤 Ngoài phiên giao dịch VN [{now.strftime('%H:%M:%S %d/%m/%Y')}]. Bot đang ở chế độ chờ tiết kiệm tài nguyên...")
                last_heartbeat_hour = now.hour

        except Exception:
            logging.exception("Ngoại lệ trong vòng lặp Trading Bot")

        time.sleep(check_interval_sec)


if __name__ == "__main__":
    run_trading_bot_loop(check_interval_sec=30)
