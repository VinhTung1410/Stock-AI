"""
=============================================================================
🧪 SCRIPT KIỂM THỬ HỆ THỐNG CẢNH BÁO BOT MUA / BÁN DISCORD
=============================================================================
Script này giúp bạn kiểm thử ngay lập tức xem bot cảnh báo có hoạt động
tốt và nổ chuông Discord hay không mà không cần chờ đến giờ giao dịch thị trường!
=============================================================================
"""

import os
import sys

from dotenv import load_dotenv

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Đảm bảo import được các module từ thư mục gốc
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from ai_analyst import generate_portfolio_analysis
from data_engine import (
    evaluate_portfolio,
    evaluate_watchlist,
    fetch_macro_news,
    load_portfolio,
    load_watchlist,
)
from discord_alerts import format_portfolio_embed, send_discord_dm, send_discord_message, send_trade_signal_alert
from trading_bot import check_realtime_risk

load_dotenv()


def test_buy_signal():
    """Bắn thử nghiệm 1 Tín hiệu MUA cổ phiếu vào DM riêng (Màu xanh lá)."""
    print("\n🟢 Đang gửi thử nghiệm [TÍN HIỆU MUA] vào Tin nhắn riêng (DM) Discord...")
    success = send_trade_signal_alert(
        symbol="SSI",
        action="MUA",
        current_price=21.50,
        trigger_reason="Giá bứt phá vượt MA20 kèm Volume đột biến gấp 1.8x TB20 phiên. RSI(14) bật tăng từ vùng tích lũy 52.0!",
        target_price=25.00,
        stop_loss=20.20
    )
    if success:
        print("✅ Thành công! Hãy mở mục TIN NHẮN RIÊNG (DM) với Bot trên Discord để kiểm tra (màu XANH LÁ).")
    else:
        print("❌ Thất bại! Vui lòng kiểm tra lại DISCORD_BOT_TOKEN và DISCORD_USER_ID trong file .env.")


def test_sell_signal():
    """Bắn thử nghiệm 1 Tín hiệu BÁN / Cắt lỗ vào DM riêng (Màu đỏ)."""
    print("\n🔴 Đang gửi thử nghiệm [TÍN HIỆU BÁN / CẮT LỖ] vào Tin nhắn riêng (DM) Discord...")
    success = send_trade_signal_alert(
        symbol="BSR",
        action="BÁN",
        current_price=25.20,
        trigger_reason="Thị giá giảm quá -7.2% so với giá vốn (27.16). Đã kích hoạt ngưỡng CẮT LỖ dứt khoát bảo toàn vốn!",
        target_price=None,
        stop_loss=25.20
    )
    if success:
        print("✅ Thành công! Hãy mở mục TIN NHẮN RIÊNG (DM) với Bot trên Discord để kiểm tra (màu ĐỎ).")
    else:
        print("❌ Thất bại! Vui lòng kiểm tra lại DISCORD_BOT_TOKEN và DISCORD_USER_ID trong file .env.")


def test_live_portfolio_scan():
    """Quét dữ liệu thực tế của danh mục hiện tại và kiểm tra điều kiện Mua/Bán."""
    print("\n🔍 Đang quét dữ liệu thực tế của danh mục hiện tại...")
    portfolio = load_portfolio()
    df_eval = evaluate_portfolio(portfolio)

    if df_eval is None or df_eval.empty:
        print("⚠️ Không lấy được dữ liệu danh mục!")
        return

    print(f"📊 Đã đánh giá xong {len(df_eval)} mã trong danh mục:")
    for _, row in df_eval.iterrows():
        sym = row["Mã CP"]
        price = row["Thị giá (k)"]
        pnl = row["Lãi/Lỗ (%)"]
        ma20 = row.get("Vị thế MA20", "N/A")
        rsi = row.get("RSI(14)", "N/A")
        vol = row.get("Vol/TB20", "N/A")
        print(f"  ➜ {sym}: Thị giá {price} | Lãi/Lỗ {pnl:+.2f}% | Vị thế MA20: {ma20} | RSI: {rsi} | Vol/TB20: {vol}x")

    print("\n⚡ Đang chạy bộ lọc cảnh báo Bot (bỏ qua rào cản giờ hành chính)...")
    check_realtime_risk()
    print("✅ Đã hoàn tất kiểm tra quét tín hiệu thực tế. (Nếu có vi phạm sẽ nổ chuông trong DM!)")


def test_full_ai_report():
    """Bắn báo cáo phân tích chiến lược AI toàn diện của Gemini vào Discord."""
    print("\n🧠 Đang gọi Gemini phân tích toàn diện danh mục & tin tức CafeF...")
    portfolio = load_portfolio()
    df_eval = evaluate_portfolio(portfolio)
    watchlist = load_watchlist()
    df_wl = evaluate_watchlist(watchlist) if watchlist else None
    news = fetch_macro_news(limit=8)

    ai_text = generate_portfolio_analysis(df_eval, news, watchlist_df=df_wl)
    embed = format_portfolio_embed(df_eval, ai_text, report_type="BÁO CÁO CHIẾN LƯỢC TOÀN DIỆN")

    print("📤 Đang gửi Rich Embed vào Discord...")
    success = send_discord_message(embeds=[embed])
    if success:
        print("✅ Báo cáo AI đã được bắn thành công vào Discord!")
    else:
        print("❌ Gửi báo cáo AI thất bại.")


def test_morning_recommendation_report():
    """Bắn bản tin Khuyến nghị Cổ phiếu đầu ngày 08:45 Sáng (Top Picks phong cách SSI/TCBS)."""
    print("\n🌅 Đang khởi tạo Bản tin Khuyến nghị Đầu Ngày 08:45 Sáng (trước ATO)...")
    from ai_analyst import generate_morning_strategy_report
    from data_engine import evaluate_watchlist, load_watchlist, scan_market_opportunities

    portfolio = load_portfolio()
    df_eval = evaluate_portfolio(portfolio)
    watchlist = load_watchlist()
    df_wl = evaluate_watchlist(watchlist) if watchlist else None

    print("🔍 Đang quét rổ cổ phiếu dẫn dắt thị trường + Watchlist...")
    tracked = [p["symbol"] for p in portfolio]
    if watchlist:
        tracked += [w["symbol"] for w in watchlist]
    opportunities = scan_market_opportunities(extra_symbols=tracked)
    for o in opportunities:
        print(f"  ➜ {o['symbol']}: {o['setup_type']} | Giá: {o['current_price']}k | Target: {o['target_price']}k | Cutloss: {o['stop_loss']}k")

    print("📰 Đang thu thập tin tức tài chính CafeF nóng nhất sáng nay...")
    news = fetch_macro_news(limit=8, tracked_symbols=tracked)

    print("🧠 Đang gọi Gemini đóng vai Trưởng ban Chiến lược SSI/TCBS tạo khuyến nghị...")
    ai_text = generate_morning_strategy_report(df_eval, df_wl, opportunities, news)
    embed = format_portfolio_embed(df_eval, ai_text, report_type="KHUYẾN NGHỊ ĐẦU NGÀY 08:45 (ATO)")

    print("📤 Đang gửi bản tin khuyến nghị vào Discord DM riêng...")
    success = send_discord_dm(embeds=[embed])
    if not success:
        send_discord_message(embeds=[embed])
    if success:
        print("✅ Thành công! Hãy mở Discord DM kiểm tra bản tin Khuyến nghị Mua đầu ngày.")
    else:
        print("❌ Gửi bản tin thất bại.")


def main():
    print("=" * 60)
    print("🤖 MENU KIỂM THỬ HỆ THỐNG CẢNH BÁO BOT (DISCORD ALERTS)")
    print("=" * 60)
    print("1. [TEST TÍN HIỆU MUA]        ➜ Bắn cảnh báo MUA màu XANH LÁ (vào DM riêng)")
    print("2. [TEST TÍN HIỆU BÁN]        ➜ Bắn cảnh báo BÁN/CẮT LỖ màu ĐỎ (vào DM riêng)")
    print("3. [QUÉT DANH MỤC & WATCHLIST]➜ Quét giá thực tế & tín hiệu Mua/Bán")
    print("4. [BÁO CÁO TOÀN DIỆN AI]     ➜ Phân tích danh mục + tin CafeF chuyên sâu")
    print("5. [🌅 KHUYẾN NGHỊ 08:45 SÁNG]➜ Gợi ý Top Cổ phiếu Tiềm năng chuẩn CTCK")
    print("0. Thoát")
    print("=" * 60)

    choice = input("👉 Nhập lựa chọn của bạn (1-5, hoặc 0 để thoát): ").strip()

    if choice == "1":
        test_buy_signal()
    elif choice == "2":
        test_sell_signal()
    elif choice == "3":
        test_live_portfolio_scan()
    elif choice == "4":
        test_full_ai_report()
    elif choice == "5":
        test_morning_recommendation_report()
    else:
        print("Tạm biệt!")


if __name__ == "__main__":
    main()
