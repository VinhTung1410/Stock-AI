import sys
import os
import logging
from dotenv import load_dotenv

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except:
        pass

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from data_engine import (
    load_portfolio,
    evaluate_portfolio,
    load_watchlist,
    evaluate_watchlist,
    scan_market_opportunities,
    fetch_macro_news
)
from ai_analyst import generate_morning_strategy_report
from discord_alerts import (
    send_discord_webhook,
    send_discord_dm,
    format_portfolio_embed
)

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


def run_morning_report():
    print("=" * 70, flush=True)
    print("🌅 BÁO CÁO CHIẾN LƯỢC & KHUYẾN NGHỊ ĐẦU PHIÊN ATO (08:45)", flush=True)
    print("=" * 70, flush=True)

    portfolio = load_portfolio()
    df_eval = evaluate_portfolio(portfolio)
    watchlist = load_watchlist()
    df_wl = evaluate_watchlist(watchlist) if watchlist else None

    tracked_symbols = [p["symbol"] for p in portfolio]
    if watchlist:
        tracked_symbols += [w["symbol"] for w in watchlist]

    print("🔍 1. Quét cơ hội thị trường & lọc tiêu chuẩn Kỹ thuật + Câu chuyện riêng...", flush=True)
    opportunities = scan_market_opportunities(extra_symbols=tracked_symbols)
    for o in opportunities:
        status_tag = "✅ MUA" if o["status"] == "RECOMMEND_BUY" else "⚠️ THẬN TRỌNG"
        print(f"  {status_tag} {o['symbol']} ({o.get('sector')}): {o.get('setup_type')} | Thị giá: {o['current_price']}k | Xúc tác: [{o.get('story_tag')}]", flush=True)

    print("\n📰 2. Thu thập tin tức vĩ mô & doanh nghiệp CafeF...", flush=True)
    news = fetch_macro_news(limit=10, tracked_symbols=tracked_symbols)

    print("\n🧠 3. AI Gemini đóng vai Giám đốc Chiến lược CTCK lập báo cáo ATO 08:45...", flush=True)
    morning_ai_text = generate_morning_strategy_report(df_eval, df_wl, opportunities, news)
    
    morning_embed = format_portfolio_embed(
        df_eval, 
        morning_ai_text, 
        report_type="🌅 CHIẾN LƯỢC ATO ĐẦU NGÀY (08:45)"
    )

    print("\n📤 4. Bắn báo cáo ATO vào Discord (Kênh chung & DM cá nhân)...", flush=True)
    wh_res = send_discord_webhook(embeds=[morning_embed])
    dm_res = send_discord_dm(embeds=[morning_embed])
    print(f"  ➜ Kênh chung (Webhook): {'✅ Thành công' if wh_res else '❌ Thất bại'}", flush=True)
    print(f"  ➜ Hộp thư riêng (DM Bot): {'✅ Thành công' if dm_res else '❌ Thất bại'}", flush=True)

    with open("report_morning_0845.md", "w", encoding="utf-8") as f:
        f.write("# BÁO CÁO CHIẾN LƯỢC & KHUYẾN NGHỊ ĐẦU PHIÊN ATO (08:45)\n\n")
        f.write(morning_ai_text)

    print("\n" + "#" * 70, flush=True)
    print("--- NỘI DUNG BÁO CÁO 08:45 ATO ĐẦU NGÀY ---", flush=True)
    print(morning_ai_text, flush=True)
    print("#" * 70, flush=True)


if __name__ == "__main__":
    run_morning_report()
