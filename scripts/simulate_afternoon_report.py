import sys
import os
import json
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
    fetch_macro_news
)
from ai_analyst import generate_portfolio_analysis
from discord_alerts import (
    send_discord_webhook,
    send_discord_dm,
    format_portfolio_embed
)

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


def run_afternoon_simulation():
    print("=" * 70, flush=True)
    print("📊 [GIẢ LẬP 2] BÁO CÁO TỔNG KẾT PHIÊN GIAO DỊCH (15:00 - 11/09)", flush=True)
    print("=" * 70, flush=True)

    portfolio = load_portfolio()
    df_eval = evaluate_portfolio(portfolio)
    watchlist = load_watchlist()
    df_wl = evaluate_watchlist(watchlist) if watchlist else None

    tracked_symbols = [p["symbol"] for p in portfolio]
    if watchlist:
        tracked_symbols += [w["symbol"] for w in watchlist]

    print("📰 1. Thu thập tin tức CafeF & dữ liệu đóng cửa kết phiên...", flush=True)
    news = fetch_macro_news(limit=10, tracked_symbols=tracked_symbols)

    print("🧠 2. AI Gemini Flash tổng kết phiên & đánh giá sức khỏe danh mục...", flush=True)
    afternoon_ai_text = generate_portfolio_analysis(df_eval, news, watchlist_df=df_wl)

    afternoon_embed = format_portfolio_embed(
        df_eval,
        afternoon_ai_text,
        report_type="📊 BÁO CÁO TỔNG KẾT PHIÊN (15:00 - 11/09)"
    )

    print("📤 3. Bắn báo cáo 15:00 vào Discord (Kênh chung & DM cá nhân)...", flush=True)
    wh_res = send_discord_webhook(embeds=[afternoon_embed])
    dm_res = send_discord_dm(embeds=[afternoon_embed])
    print(f"  ➜ Kênh chung (Webhook): {'✅ Thành công' if wh_res else '❌ Thất bại'}", flush=True)
    print(f"  ➜ Hộp thư riêng (DM Bot): {'✅ Thành công' if dm_res else '❌ Thất bại'}", flush=True)

    with open("report_afternoon_1500.md", "w", encoding="utf-8") as f:
        f.write("# BÁO CÁO TỔNG KẾT KẾT PHIÊN GIAO DỊCH (15:00 - 11/09)\n\n")
        f.write(afternoon_ai_text)

    print("\n" + "#" * 70, flush=True)
    print("--- NỘI DUNG BÁO CÁO 15:00 KẾT PHIÊN ---", flush=True)
    print(afternoon_ai_text, flush=True)
    print("#" * 70, flush=True)


if __name__ == "__main__":
    run_afternoon_simulation()
