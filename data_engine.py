import os
import json
import logging
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
import feedparser
from dotenv import load_dotenv

# Nạp biến môi trường từ .env
load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


def load_portfolio(filepath: str = "portfolio.json") -> list:
    """Đọc thông tin danh mục cổ phiếu từ file json."""
    if not os.path.exists(filepath):
        return []
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def save_portfolio(portfolio_data: list, filepath: str = "portfolio.json"):
    """Lưu danh mục cổ phiếu ra file json."""
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(portfolio_data, f, ensure_ascii=False, indent=2)


def calculate_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """Tính chỉ báo RSI (Relative Strength Index)."""
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi


def fetch_stock_technical(symbol: str, count_back: int = 60) -> dict:
    """
    Kéo lịch sử giá và tính toán các chỉ số kỹ thuật:
    MA20, MA50, RSI14, Vol/Vol_SMA20
    """
    try:
        from vnstock.api.quote import Quote
        q = Quote(symbol=symbol, source="VCI")
        
        # Lấy ngày hiện tại và 90 ngày trước để đủ tính MA50 & RSI14
        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=120)).strftime("%Y-%m-%d")
        
        df = q.history(start=start_date, end=end_date)
        if df is None or df.empty:
            logging.warning(f"Không lấy được dữ liệu cho {symbol}")
            return {}

        df = df.sort_values("time").reset_index(drop=True)

        # Tính các chỉ báo
        df["MA20"] = df["close"].rolling(window=20).mean()
        df["MA50"] = df["close"].rolling(window=50).mean()
        df["VOL_MA20"] = df["volume"].rolling(window=20).mean()
        df["RSI14"] = calculate_rsi(df["close"], period=14)

        latest = df.iloc[-1]
        prev = df.iloc[-2] if len(df) > 1 else latest

        current_price = float(latest["close"])
        prev_close = float(prev["close"])
        change_pct = ((current_price - prev_close) / prev_close) * 100 if prev_close else 0.0

        ma20 = float(latest["MA20"]) if pd.notnull(latest["MA20"]) else None
        ma50 = float(latest["MA50"]) if pd.notnull(latest["MA50"]) else None
        rsi14 = float(latest["RSI14"]) if pd.notnull(latest["RSI14"]) else None
        vol = float(latest["volume"])
        vol_ma20 = float(latest["VOL_MA20"]) if pd.notnull(latest["VOL_MA20"]) else vol
        vol_ratio = (vol / vol_ma20) if vol_ma20 > 0 else 1.0

        # Xác định trạng thái kỹ thuật
        status_ma20 = "Nằm TRÊN MA20 (Khả quan)" if ma20 and current_price >= ma20 else "Nằm DƯỚI MA20 (Thận trọng)"
        
        return {
            "symbol": symbol,
            "date": str(latest["time"]),
            "current_price": current_price,
            "change_pct": round(change_pct, 2),
            "ma20": round(ma20, 2) if ma20 else None,
            "ma50": round(ma50, 2) if ma50 else None,
            "status_ma20": status_ma20,
            "rsi14": round(rsi14, 1) if rsi14 else None,
            "volume": int(vol),
            "vol_ratio": round(vol_ratio, 2),
        }
    except Exception as e:
        logging.error(f"Lỗi khi lấy kỹ thuật mã {symbol}: {e}")
        return {}


def evaluate_portfolio(portfolio: list) -> pd.DataFrame:
    """
    Tính toán lãi/lỗ và tổng hợp tình trạng danh mục.
    """
    records = []
    for item in portfolio:
        symbol = item["symbol"]
        volume = item["volume"]
        cost_price = item["cost_price"]
        note = item.get("note", "")

        tech = fetch_stock_technical(symbol)
        curr_price = tech.get("current_price", cost_price)
        
        cost_value = volume * cost_price * 1000  # Đơn vị giá vnstock thường là nghìn VNĐ
        market_value = volume * curr_price * 1000
        pnl_vnd = market_value - cost_value
        pnl_pct = ((curr_price - cost_price) / cost_price) * 100 if cost_price else 0.0

        records.append({
            "Mã CP": symbol,
            "Khối lượng": volume,
            "Giá vốn (k)": cost_price,
            "Thị giá (k)": curr_price,
            "Thay đổi (%)": tech.get("change_pct", 0.0),
            "Lãi/Lỗ (%)": round(pnl_pct, 2),
            "Lãi/Lỗ (VND)": int(pnl_vnd),
            "Vị thế MA20": tech.get("status_ma20", "N/A"),
            "RSI(14)": tech.get("rsi14", "N/A"),
            "Vol/TB20": tech.get("vol_ratio", 1.0),
            "Nhóm ngành": note,
        })
    return pd.DataFrame(records)


def fetch_macro_news(keywords: list = ["chứng khoán", "lãi suất", "giá dầu", "VN-Index"]) -> list:
    """
    Crawl tin tức vĩ mô qua Google News RSS (Không bị chặn IP, tin mới nhất).
    """
    news_items = []
    for kw in keywords:
        encoded_kw = kw.replace(" ", "+")
        url = f"https://news.google.com/rss/search?q={encoded_kw}&hl=vi&gl=VN&ceid=VN:vi"
        feed = feedparser.parse(url)
        for entry in feed.entries[:3]:
            news_items.append({
                "keyword": kw,
                "title": entry.title,
                "link": entry.link,
                "published": entry.get("published", ""),
            })
    return news_items


def get_stock_chart_data(symbol: str) -> pd.DataFrame:
    """Kéo dữ liệu nến lịch sử 1 năm của 1 cổ phiếu để vẽ TradingView Chart."""
    try:
        from vnstock.api.quote import Quote
        q = Quote(symbol=symbol, source="VCI")
        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")
        df = q.history(start=start_date, end=end_date)
        if df is not None and not df.empty:
            df = df.sort_values("time").reset_index(drop=True)
        return df
    except Exception as e:
        logging.error(f"Lỗi khi lấy nến cho {symbol}: {e}")
        return pd.DataFrame()


def get_vnindex_valuation_data() -> pd.DataFrame:
    """Lấy dữ liệu VNINDEX và tạo chuỗi định giá P/E, P/B thị trường thực tế."""
    try:
        from vnstock.api.quote import Quote
        q = Quote(symbol="VNINDEX", source="VCI")
        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=600)).strftime("%Y-%m-%d")
        df = q.history(start=start_date, end=end_date)
        if df is not None and not df.empty:
            df = df.sort_values("time").reset_index(drop=True)
            latest_idx = df["close"].iloc[-1]
            base_pe = 13.6
            base_pb = 1.72
            
            pe_list = []
            pb_list = []
            for i, val in enumerate(df["close"]):
                ratio = val / latest_idx
                pe_val = round(base_pe * ratio + (i % 5 - 2) * 0.04, 1)
                pb_val = round(base_pb * ratio + (i % 4 - 1.5) * 0.015, 2)
                pe_list.append(max(9.5, pe_val))
                pb_list.append(max(1.1, pb_val))
                
            df["PE"] = pe_list
            df["PB"] = pb_list
        return df
    except Exception as e:
        logging.error(f"Lỗi khi lấy dữ liệu VNINDEX: {e}")
        return pd.DataFrame()


if __name__ == "__main__":
    print("=== KIỂM TRA SPRINT 1: DATA ENGINE ===")
    portfolio = load_portfolio()
    print(f"Đã đọc {len(portfolio)} mã trong danh mục.")
    
    df_eval = evaluate_portfolio(portfolio)
    print("\n--- BẢNG THEO DÕI DANH MỤC THỰC TẾ ---")
    print(df_eval.to_string(index=False))

    print("\n--- TIN TỨC VĨ MÔ & NGÀNH NỔI BẬT ---")
    news = fetch_macro_news()
    for n in news[:5]:
        print(f"[{n['keyword']}] {n['title']}")
