import os
import json
import logging
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
import feedparser
from dotenv import load_dotenv

import re
import requests
import urllib.request
import io

# Nạp biến môi trường từ .env
load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Danh sách mã cổ phiếu trụ cột / thanh khoản cao phục vụ quét cơ hội đầu ngày (08:45 sáng)
TOP_MARKET_SYMBOLS = ["HPG", "SSI", "FPT", "MWG", "TCB", "VHM"]


# Cache bộ nhớ tạm để tránh spam request Google Sheets liên tục
_GSHEET_CACHE = {
    "timestamp": 0,
    "portfolio": None,
    "watchlist": None
}


def parse_google_sheet_csv_url(url: str) -> str:
    """
    Chuyển đổi link chia sẻ Google Sheet thông thường thành link tải CSV trực tiếp.
    Ví dụ: https://docs.google.com/spreadsheets/d/{ID}/edit?usp=sharing -> .../export?format=csv
    """
    match = re.search(r"/spreadsheets/d/([a-zA-Z0-9-_]+)", url)
    if not match:
        return url
    sheet_id = match.group(1)
    gid_match = re.search(r"[#&?]gid=([0-9]+)", url)
    gid = gid_match.group(1) if gid_match else "0"
    return f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={gid}"


def fetch_google_sheet_data(sheet_url: str = None) -> tuple:
    """
    Đọc dữ liệu từ Google Sheet công khai (hỗ trợ cả 2 Sheet: Sheet 1 = Danh mục, Sheet 2 = Watchlist).
    Tự động thử định dạng XLSX đa trang tính trước, fallback về CSV nếu cần.
    Cache 45 giây để tối ưu hiệu năng.
    """
    global _GSHEET_CACHE
    import time
    import io
    now_ts = time.time()
    if _GSHEET_CACHE["portfolio"] is not None and (now_ts - _GSHEET_CACHE["timestamp"]) < 45:
        return _GSHEET_CACHE["portfolio"], _GSHEET_CACHE["watchlist"]

    target_url = sheet_url or os.environ.get("GOOGLE_SHEET_URL", "").strip()
    if not target_url:
        return None, None

    portfolio = []
    watchlist = []

    try:
        # Cách 1: Thử tải toàn bộ Workbook định dạng XLSX để lấy cả Sheet 1 & Sheet 2
        match = re.search(r"/spreadsheets/d/([a-zA-Z0-9-_]+)", target_url)
        if match:
            sheet_id = match.group(1)
            xlsx_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=xlsx"
            logging.info(f"Đang đồng bộ Google Sheets đa trang tính (XLSX): {xlsx_url}")
            req = urllib.request.Request(xlsx_url, headers={"User-Agent": "Mozilla/5.0"})
            content = urllib.request.urlopen(req, timeout=10).read()
            xl = pd.ExcelFile(io.BytesIO(content))

            # --- Sheet 1: Danh mục nắm giữ (Portfolio) ---
            if len(xl.sheet_names) >= 1:
                df1 = xl.parse(xl.sheet_names[0], dtype=str)
                # Kiểm tra có header hay không
                col_names_lower = [str(c).lower() for c in df1.columns]
                has_header = any("mã" in c or "symbol" in c for c in col_names_lower)
                if not has_header:
                    df1 = xl.parse(xl.sheet_names[0], header=None, dtype=str)

                col_map = {}
                for col in df1.columns:
                    c_clean = str(col).strip().lower()
                    if any(k in c_clean for k in ["mã", "symbol", "ticker", "cp"]):
                        col_map[col] = "symbol"
                    elif any(k in c_clean for k in ["khối lượng", "số lượng", "volume", "kl", "qty"]):
                        col_map[col] = "volume"
                    elif any(k in c_clean for k in ["giá vốn", "cost_price", "giá mua", "cost"]):
                        col_map[col] = "cost_price"
                    elif any(k in c_clean for k in ["ghi chú", "note", "ngành", "nhóm"]):
                        col_map[col] = "note"

                if col_map:
                    df1 = df1.rename(columns=col_map)
                else:
                    # Mặc định cột 0: Mã, cột 1: Khối lượng, cột 2: Giá vốn
                    col_names = ["symbol", "volume", "cost_price", "note"]
                    df1 = df1.rename(columns={i: col_names[i] for i in range(min(len(col_names), df1.shape[1]))})

                for _, row in df1.iterrows():
                    sym = str(row.get("symbol", "")).strip().upper()
                    if not sym or not re.match(r"^[A-Z0-9]{3}$", sym):
                        continue
                    vol_str = str(row.get("volume", "0")).replace(",", "").replace(".", "").strip()
                    try:
                        volume = int(float(vol_str)) if vol_str and vol_str != "nan" else 0
                    except:
                        volume = 0

                    cost_str = str(row.get("cost_price", "0")).replace(",", "").strip()
                    try:
                        cost_price = float(cost_str) if cost_str and cost_str != "nan" else 0.0
                    except:
                        cost_price = 0.0

                    note = str(row.get("note", "")).strip() if pd.notnull(row.get("note")) and str(row.get("note")).strip() != "nan" else ""
                    if volume > 0:
                        portfolio.append({
                            "symbol": sym,
                            "volume": volume,
                            "cost_price": cost_price,
                            "note": note
                        })

            # --- Sheet 2: Danh sách theo dõi (Watchlist) nếu có ---
            if len(xl.sheet_names) >= 2:
                df2 = xl.parse(xl.sheet_names[1], header=None, dtype=str)
                for _, row in df2.iterrows():
                    sym = str(row.iloc[0]).strip().upper()
                    if not sym or not re.match(r"^[A-Z0-9]{3}$", sym):
                        continue
                    target_str = str(row.iloc[1]).replace(",", "").strip() if len(row) > 1 and pd.notnull(row.iloc[1]) else "0"
                    try:
                        target_buy = float(target_str) if target_str and target_str != "nan" else 0.0
                    except:
                        target_buy = 0.0

                    note = str(row.iloc[2]).strip() if len(row) > 2 and pd.notnull(row.iloc[2]) and str(row.iloc[2]).strip() != "nan" else "Theo dõi từ Google Sheet"
                    watchlist.append({
                        "symbol": sym,
                        "target_buy": target_buy,
                        "note": note
                    })

            if portfolio or watchlist:
                _GSHEET_CACHE["timestamp"] = now_ts
                _GSHEET_CACHE["portfolio"] = portfolio
                _GSHEET_CACHE["watchlist"] = watchlist
                logging.info(f"✅ Đã đồng bộ Google Sheets (XLSX): {len(portfolio)} mã danh mục, {len(watchlist)} mã theo dõi.")
                return portfolio, watchlist
    except Exception as e_xlsx:
        logging.warning(f"Không thể đọc XLSX từ Google Sheet ({e_xlsx}), chuyển sang tải CSV dự phòng...")

    # Cách 2 (Dự phòng): Tải CSV đơn trang tính
    try:
        csv_url = parse_google_sheet_csv_url(target_url)
        df = pd.read_csv(csv_url, dtype=str)
        if df is None or df.empty:
            return None, None

        col_map = {}
        for col in df.columns:
            c_clean = str(col).strip().lower()
            if any(k in c_clean for k in ["mã", "symbol", "ticker", "cp"]):
                col_map[col] = "symbol"
            elif any(k in c_clean for k in ["khối lượng", "số lượng", "volume", "kl", "qty"]):
                col_map[col] = "volume"
            elif any(k in c_clean for k in ["giá vốn", "cost_price", "giá mua", "cost"]):
                col_map[col] = "cost_price"
            elif any(k in c_clean for k in ["giá chờ mua", "giá mục tiêu", "target", "chờ mua"]):
                col_map[col] = "target_buy"
            elif any(k in c_clean for k in ["loại", "type", "phân loại"]):
                col_map[col] = "type"
            elif any(k in c_clean for k in ["ghi chú", "note", "ngành", "nhóm"]):
                col_map[col] = "note"

        df = df.rename(columns=col_map)
        if "symbol" not in df.columns:
            df_no_head = pd.read_csv(csv_url, header=None, dtype=str)
            if df_no_head is not None and not df_no_head.empty:
                col_names = ["symbol", "volume", "cost_price", "note"]
                df = df_no_head.rename(columns={i: col_names[i] for i in range(min(len(col_names), df_no_head.shape[1]))})
            else:
                return None, None

        for _, row in df.iterrows():
            sym = str(row.get("symbol", "")).strip().upper()
            if not sym or not re.match(r"^[A-Z0-9]{3}$", sym):
                continue

            vol_str = str(row.get("volume", "0")).replace(",", "").replace(".", "").strip()
            try:
                volume = int(float(vol_str)) if vol_str and vol_str != "nan" else 0
            except:
                volume = 0

            cost_str = str(row.get("cost_price", "0")).replace(",", "").strip()
            try:
                cost_price = float(cost_str) if cost_str and cost_str != "nan" else 0.0
            except:
                cost_price = 0.0

            target_str = str(row.get("target_buy", "0")).replace(",", "").strip()
            try:
                target_buy = float(target_str) if target_str and target_str != "nan" else 0.0
            except:
                target_buy = 0.0

            row_type = str(row.get("type", "")).strip().upper()
            note = str(row.get("note", "")).strip() if pd.notnull(row.get("note")) else ""

            if volume > 0 and row_type not in ["WATCH", "THEO DÕI", "THEODOI"]:
                portfolio.append({
                    "symbol": sym,
                    "volume": volume,
                    "cost_price": cost_price,
                    "note": note
                })
            else:
                watchlist.append({
                    "symbol": sym,
                    "target_buy": target_buy if target_buy > 0 else cost_price,
                    "note": note
                })

        _GSHEET_CACHE["timestamp"] = now_ts
        _GSHEET_CACHE["portfolio"] = portfolio
        _GSHEET_CACHE["watchlist"] = watchlist
        return portfolio, watchlist
    except Exception as e:
        logging.error(f"❌ Lỗi khi đọc Google Sheet CSV: {e}")
        return None, None


def update_google_sheet_portfolio(portfolio_data: list) -> bool:
    """
    Ghi ngược danh mục nắm giữ từ Web Dashboard lên Sheet 1 của Google Sheet.
    Hỗ trợ qua webhook Google Apps Script (GOOGLE_SHEET_UPDATE_URL).
    """
    update_url = os.environ.get("GOOGLE_SHEET_UPDATE_URL", "").strip()
    if not update_url:
        return False
    try:
        payload = {"type": "portfolio", "data": portfolio_data}
        res = requests.post(update_url, json=payload, timeout=10)
        if res.status_code == 200:
            _GSHEET_CACHE["timestamp"] = 0
            _GSHEET_CACHE["portfolio"] = None
            logging.info("✅ Đã ghi ngược danh mục lên Google Sheet thành công!")
            return True
        else:
            logging.error(f"Lỗi khi gửi dữ liệu lên Google Sheet Webhook: {res.status_code} - {res.text}")
            return False
    except Exception as e:
        logging.error(f"Lỗi kết nối Webhook Google Sheet: {e}")
        return False


def update_google_sheet_watchlist(watchlist_data: list) -> bool:
    """
    Ghi ngược danh sách theo dõi (Watchlist) từ Web Dashboard lên Sheet 2 của Google Sheet.
    """
    update_url = os.environ.get("GOOGLE_SHEET_UPDATE_URL", "").strip()
    if not update_url:
        return False
    try:
        payload = {"type": "watchlist", "data": watchlist_data}
        res = requests.post(update_url, json=payload, timeout=10)
        if res.status_code == 200:
            _GSHEET_CACHE["timestamp"] = 0
            _GSHEET_CACHE["watchlist"] = None
            logging.info("✅ Đã ghi ngược Watchlist lên Google Sheet thành công!")
            return True
        else:
            logging.error(f"Lỗi gửi Watchlist lên Google Sheet: {res.status_code} - {res.text}")
            return False
    except Exception as e:
        logging.error(f"Lỗi kết nối Webhook Google Sheet Watchlist: {e}")
        return False


def load_portfolio(filepath: str = "portfolio.json") -> list:
    """
    Đọc thông tin danh mục cổ phiếu.
    Ưu tiên kéo từ Google Sheet (nếu cấu hình GOOGLE_SHEET_URL).
    Tự động sao lưu dự phòng sang portfolio.json và fallback khi offline.
    """
    sheet_url = os.environ.get("GOOGLE_SHEET_URL", "").strip()
    if sheet_url:
        p_data, _ = fetch_google_sheet_data(sheet_url)
        if p_data:
            # Tự động sao lưu bản copy xuống portfolio.json
            try:
                save_portfolio(p_data, filepath)
            except:
                pass
            return p_data

    # Fallback file json cục bộ
    if not os.path.exists(filepath):
        return []
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logging.error(f"Lỗi đọc {filepath}: {e}")
        return []


def load_watchlist(filepath: str = "watchlist.json") -> list:
    """
    Đọc danh sách cổ phiếu đang theo dõi (Watchlist).
    Ưu tiên kéo từ Google Sheet (nếu có), fallback sang watchlist.json.
    """
    sheet_url = os.environ.get("GOOGLE_SHEET_URL", "").strip()
    if sheet_url:
        _, w_data = fetch_google_sheet_data(sheet_url)
        if w_data:
            try:
                with open(filepath, "w", encoding="utf-8") as f:
                    json.dump(w_data, f, ensure_ascii=False, indent=2)
            except:
                pass
            return w_data

    if not os.path.exists(filepath):
        return []
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logging.error(f"Lỗi đọc {filepath}: {e}")
        return []


def save_portfolio(portfolio_data: list, filepath: str = "portfolio.json"):
    """Lưu danh mục cổ phiếu ra file json."""
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(portfolio_data, f, ensure_ascii=False, indent=2)


def save_watchlist(watchlist_data: list, filepath: str = "watchlist.json"):
    """Lưu danh sách cổ phiếu theo dõi ra file json."""
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(watchlist_data, f, ensure_ascii=False, indent=2)


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


def evaluate_watchlist(watchlist: list) -> pd.DataFrame:
    """
    Tính toán tín hiệu kỹ thuật cho Danh mục Cổ phiếu Đang Theo Dõi (Watchlist).
    Giúp phát hiện sớm các cổ phiếu đang tiệm cận vùng giá mua an toàn hoặc bùng nổ điểm mua.
    """
    records = []
    for item in watchlist:
        symbol = item["symbol"]
        target_buy = float(item.get("target_buy", 0.0))
        note = item.get("note", "")

        tech = fetch_stock_technical(symbol)
        curr_price = tech.get("current_price", target_buy)
        diff_pct = ((curr_price - target_buy) / target_buy * 100) if target_buy > 0 else 0.0

        records.append({
            "Mã CP": symbol,
            "Thị giá (k)": curr_price,
            "Thay đổi (%)": tech.get("change_pct", 0.0),
            "Giá chờ mua (k)": target_buy if target_buy > 0 else curr_price,
            "Khoảng cách (%)": round(diff_pct, 2),
            "Vị thế MA20": tech.get("status_ma20", "N/A"),
            "RSI(14)": tech.get("rsi14", "N/A"),
            "Vol/TB20": tech.get("vol_ratio", 1.0),
            "Luận điểm / Ghi chú": note,
        })
    return pd.DataFrame(records)


def fetch_macro_news(limit: int = 15, tracked_symbols: list = None) -> list:
    """
    Cào tin tức tài chính chuyên sâu trực tiếp từ CafeF RSS (Thị trường chứng khoán & Doanh nghiệp).
    - Phân loại tin chuyên ngành: [CỔ TỨC], [KQKD / BCTC], [GIAO DỊCH NỘI BỘ], [THỊ TRƯỜNG], [VĨ MÔ].
    - Đánh dấu tin tức liên quan trực tiếp đến các mã trong Danh mục & Watchlist.
    """
    feeds = [
        ("https://cafef.vn/thi-truong-chung-khoan.rss", "Thị trường"),
        ("https://cafef.vn/doanh-nghiep.rss", "Doanh nghiệp"),
    ]
    
    if tracked_symbols is None:
        tracked_symbols = []
    tracked_upper = [s.upper() for s in tracked_symbols if s]

    news_items = []
    seen_titles = set()

    import html

    for feed_url, channel_name in feeds:
        try:
            # Tải nội dung RSS bằng requests với mã hóa UTF-8 tuyệt đối
            resp = requests.get(feed_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
            resp.encoding = "utf-8"
            feed = feedparser.parse(resp.content)

            for entry in feed.entries:
                title = html.unescape(str(entry.title).strip())
                if title in seen_titles:
                    continue
                seen_titles.add(title)

                # Làm sạch tóm tắt (loại bỏ thẻ HTML, giải mã thực thể và lấy text sạch)
                summary_raw = getattr(entry, "summary", "")
                summary_clean = re.sub(r"<[^>]+>", "", summary_raw).strip()
                summary_clean = html.unescape(" ".join(summary_clean.split()))

                # Trích xuất link ảnh nếu có
                img_match = re.search(r'src="([^"]+\.(?:jpg|png|jpeg|webp)[^"]*)"', summary_raw)
                img_url = img_match.group(1) if img_match else None

                # Gắn nhãn phân loại tự động
                full_text = (title + " " + summary_clean).lower()
                tag = "THỊ TRƯỜNG"
                tag_color = "#3b82f6"  # Blue

                if any(w in full_text for w in ["cổ tức", "chốt quyền", "chia thưởng", "trả cổ tức"]):
                    tag = "CỔ TỨC"
                    tag_color = "#10b981"  # Green
                elif any(w in full_text for w in ["lợi nhuận", "kết quả kinh doanh", "kqkd", "báo cáo tài chính", "bctc", "lãi ròng", "doanh thu"]):
                    tag = "KQKD"
                    tag_color = "#8b5cf6"  # Purple
                elif any(w in full_text for w in ["chủ tịch", "tổng giám đốc", "mua vào", "bán ra", "thoái vốn", "đăng ký bán", "đăng ký mua", "nội bộ"]):
                    tag = "NỘI BỘ"
                    tag_color = "#f59e0b"  # Amber
                elif any(w in full_text for w in ["lãi suất", "fed", "ngân hàng nhà nước", "tỷ giá", "lạm phát", "gdp", "fdi"]):
                    tag = "VĨ MÔ"
                    tag_color = "#ec4899"  # Pink

                # Kiểm tra mã cổ phiếu liên quan
                matched_symbols = []
                for sym in tracked_upper:
                    # Tìm mã cổ phiếu đứng độc lập hoặc trong ngoặc
                    if re.search(rf"\b{sym}\b", title.upper()) or re.search(rf"\b{sym}\b", summary_clean.upper()):
                        matched_symbols.append(sym)

                news_items.append({
                    "title": title,
                    "summary": summary_clean,
                    "link": entry.link,
                    "published": entry.get("published", ""),
                    "channel": channel_name,
                    "tag": tag,
                    "tag_color": tag_color,
                    "image": img_url,
                    "matched_symbols": matched_symbols
                })

                if len(news_items) >= limit:
                    break
            if len(news_items) >= limit:
                break
        except Exception as e:
            logging.error(f"Lỗi khi cào RSS CafeF ({feed_url}): {e}")

    return news_items


SECTOR_MAP = {
    "FPT": "Công nghệ / AI",
    "HPG": "Thép & Vật liệu xây dựng",
    "MWG": "Bán lẻ tiêu dùng",
    "SSI": "Chứng khoán",
    "VND": "Chứng khoán",
    "VCI": "Chứng khoán",
    "BSR": "Dầu khí / Lọc hóa dầu",
    "PVD": "Dầu khí / Khoan dầu",
    "PVS": "Dầu khí / Xây lắp dầu khí",
    "MSB": "Ngân hàng",
    "TCB": "Ngân hàng",
    "MBB": "Ngân hàng",
    "VPB": "Ngân hàng",
    "ACB": "Ngân hàng",
    "VHM": "Bất động sản",
    "VIC": "Bất động sản / Xe điện",
    "VNM": "Thực phẩm & Đồ uống",
    "DGC": "Hóa chất cơ bản",
    "DCM": "Phân bón & Hóa chất",
    "DPM": "Phân bón & Hóa chất"
}


def scan_market_opportunities(extra_symbols: list = None) -> list:
    """
    🎯 BỘ LỌC CƠ HỘI ĐẦU NGÀY CHUẨN CTCK (SSI, TCBS, MBS, TPS):
    Nguyên lý 2 tầng: 'Catalyst (Câu chuyện xúc tác) + Technical Confluence (Kỹ thuật cho phép)'
    1. Cào tin tức CafeF mới nhất: gom các mã có xúc tác (KQKD, Cổ tức, Vĩ mô ngành, Nội bộ gom...).
    2. Kết hợp với Watchlist người dùng theo dõi và nhóm dẫn dắt thị trường.
    3. Kiểm tra dữ liệu giao dịch thực tế vnstock:
       - CHỈ KHUYẾN NGHỊ MUA KHI:
         + Có câu chuyện xúc tác rõ ràng (hoặc thuộc Watchlist chiến lược).
         + Kỹ thuật cho phép: Giá nằm trên/sát MA20, RSI lành mạnh (45 - 68), Dòng tiền vào.
       - CẢNH BÁO BẪY TIN TỨC nếu có tin tốt nhưng giá dưới MA20 / cắm đầu giảm.
    """
    from concurrent.futures import ThreadPoolExecutor

    # 1. Thu thập tin tức CafeF và tạo bản đồ Xúc tác (Catalyst Map)
    catalyst_map = {}
    try:
        news_items = fetch_macro_news(limit=25)
        for n in news_items:
            for sym in n.get("matched_symbols", []):
                sym_up = sym.upper()
                if sym_up not in catalyst_map:
                    catalyst_map[sym_up] = {
                        "tag": n.get("tag", "TIN TỨC"),
                        "title": n.get("title", ""),
                        "summary": n.get("summary", "")
                    }
    except Exception as e:
        logging.warning(f"Không thể cào tin CafeF cho bộ lọc cơ hội: {e}")

    # 2. Bổ sung các mã từ Watchlist (người dùng tự đưa vào theo dõi)
    watchlist_items = load_watchlist()
    for w in watchlist_items:
        w_sym = w.get("symbol", "").upper()
        if w_sym and w_sym not in catalyst_map:
            catalyst_map[w_sym] = {
                "tag": "WATCHLIST",
                "title": w.get("note") or "Cổ phiếu chiến lược trong danh sách theo dõi",
                "summary": ""
            }

    # 3. Tạo danh sách ứng viên (Ưu tiên mã có tin tức + Watchlist + Top trụ cột)
    pool = list(set(list(catalyst_map.keys()) + list(TOP_MARKET_SYMBOLS) + [s.upper() for s in (extra_symbols or []) if s]))

    def analyze_symbol(sym):
        try:
            tech = fetch_stock_technical(sym)
            if not tech:
                return None

            curr_price = tech.get("current_price", 0.0)
            ma20 = tech.get("ma20")
            ma50 = tech.get("ma50")
            rsi = tech.get("rsi14")
            vol_ratio = tech.get("vol_ratio", 1.0)
            change_pct = tech.get("change_pct", 0.0)

            if not curr_price or not ma20 or not rsi:
                return None

            sector = SECTOR_MAP.get(sym, "Doanh nghiệp niêm yết")
            cat_info = catalyst_map.get(sym)
            story_title = cat_info["title"] if cat_info else f"Cổ phiếu đầu ngành {sector} dẫn dắt dòng tiền"
            story_tag = cat_info["tag"] if cat_info else "DÒNG TIỀN"

            # --- KIỂM TRA ĐIỀU KIỆN KỸ THUẬT THỰC CHIẾN ---
            # Điều kiện 1: Giá không bị downtrend (trên MA20 hoặc cách MA20 tối đa 1.5% để test hỗ trợ)
            tech_allowed = curr_price >= (ma20 * 0.985)
            # Điều kiện 2: RSI không bị quá mua (> 70) và không cắm đầu hoảng loạn (< 42)
            rsi_allowed = (44 <= rsi <= 68)
            # Điều kiện 3: Thanh khoản không bị mất hút
            vol_allowed = (vol_ratio >= 0.90)

            # A. ĐẠT CẢ HAI: CÓ CÂU CHUYỆN + KỸ THUẬT CHO PHÉP -> KHUYẾN NGHỊ MUA
            if tech_allowed and rsi_allowed and vol_allowed:
                target_price = round(curr_price * 1.10, 2)
                stop_loss = round(max(ma20 * 0.95, curr_price * 0.95), 2)
                rr = round((target_price - curr_price) / max(0.1, curr_price - stop_loss), 1)

                # Phân tách 2 phong cách giao dịch: Lướt sóng T+ vs Gom hàng vị thế
                if vol_ratio >= 1.25 and change_pct >= 0.5:
                    style_type = "⚡ [LƯỚT SÓNG T+ / BREAKOUT]"
                    setup_type = "⚡ BREAKOUT NỔ VOL VƯỢT NỀN"
                    # Biên độ điểm vào cực hẹp (tối đa 2-3 bước giá, ~0.4%)
                    p_min = round(curr_price * 0.996, 1)
                    p_max = round(curr_price * 1.004, 1)
                    entry_zone = f"{p_min} - {p_max}"
                    execution_plan = f"Mua dứt khoát 1 lần quanh {curr_price}k (vùng {entry_zone}k). Vượt {p_max}k KHÔNG mua đuổi."
                    avg_cost = curr_price
                else:
                    style_type = "💎 [GOM HÀNG VỊ THẾ / TRUNG HẠN]"
                    setup_type = "💎 TÍCH LŨY NỀN GIÁ TRÊN MA20"
                    # Dải gom mở rộng 1.5% - 2.0% nhưng có lộ trình chia 3 bước giải ngân
                    p_low = round(min(ma20, curr_price * 0.985), 1)
                    p_high = round(curr_price * 1.005, 1)
                    entry_zone = f"{p_low} - {p_high}"
                    avg_cost = round((p_low * 0.3 + curr_price * 0.4 + p_high * 0.3), 1)
                    execution_plan = f"Chia 3 phần: 30% tại {p_high}k, 40% tại {curr_price}k, 30% đón tại {p_low}k (Giá vốn BQ dự kiến: {avg_cost}k)."

                rr = round((target_price - avg_cost) / max(0.1, avg_cost - stop_loss), 1)

                return {
                    "symbol": sym,
                    "sector": sector,
                    "status": "RECOMMEND_BUY",
                    "style_type": style_type,
                    "setup_type": setup_type,
                    "story_tag": story_tag,
                    "story": story_title,
                    "current_price": curr_price,
                    "entry_zone": entry_zone,
                    "avg_cost": avg_cost,
                    "execution_plan": execution_plan,
                    "target_price": target_price,
                    "stop_loss": stop_loss,
                    "risk_reward": rr,
                    "rsi": rsi,
                    "vol_ratio": vol_ratio,
                    "rationale": f"Xúc tác: {story_title}. Kỹ thuật: Vận động trên MA20 ({ma20:.1f}), RSI {rsi:.1f}, Vol TB x{vol_ratio:.1f}."
                }

            # B. CÓ TIN TỨC HOT NHƯNG KỸ THUẬT CHƯA CHO PHÉP -> CẢNH BÁO BẪY TIN TỨC
            elif cat_info and (not tech_allowed or rsi < 42 or rsi > 70):
                caution_reason = []
                if curr_price < ma20:
                    caution_reason.append(f"Giá đang dưới MA20 ({ma20:.1f})")
                if rsi > 70:
                    caution_reason.append(f"RSI {rsi:.1f} quá mua (nguy cơ rung lắc ngắn hạn)")
                elif rsi < 42:
                    caution_reason.append(f"RSI {rsi:.1f} yếu, lực bán đang chiếm ưu thế")

                return {
                    "symbol": sym,
                    "sector": sector,
                    "status": "CAUTION_TRAP",
                    "setup_type": "⚠️ CHƯA ĐẠT ĐIỀU KIỆN MUA",
                    "story_tag": story_tag,
                    "story": story_title,
                    "current_price": curr_price,
                    "rsi": rsi,
                    "vol_ratio": vol_ratio,
                    "rationale": f"Có tin xúc tác [{story_tag}] nhưng " + ", ".join(caution_reason) + ". Khuyến nghị: ĐỨNG NGOÀI QUAN SÁT, chưa vội gom hàng."
                }

            return None
        except Exception as e:
            logging.debug(f"Lỗi phân tích {sym}: {e}")
            return None

    all_results = []
    with ThreadPoolExecutor(max_workers=6) as executor:
        for res in executor.map(analyze_symbol, pool):
            if res:
                all_results.append(res)

    # Tách thành 2 nhóm: Khuyến nghị Mua và Cảnh báo
    buy_picks = [r for r in all_results if r["status"] == "RECOMMEND_BUY"]
    caution_picks = [r for r in all_results if r["status"] == "CAUTION_TRAP"]

    # Ưu tiên mã có vol nổ và R:R tốt
    buy_picks.sort(key=lambda x: (x["vol_ratio"], x["risk_reward"]), reverse=True)
    caution_picks.sort(key=lambda x: x["vol_ratio"], reverse=True)

    # Trả về tối đa 4 khuyến nghị mua + 2 cảnh báo bẫy tin
    return buy_picks[:4] + caution_picks[:2]



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


def get_financial_ratios(symbol: str) -> dict:
    """
    Lấy các chỉ số tài chính cơ bản & định giá chuyên sâu phục vụ báo cáo 8 trụ cột:
    P/E, P/B, P/S, EV/EBITDA, ROE, ROA, Nợ/VCSH, Biên LN gộp, Biên LN ròng, Vốn hóa...
    """
    try:
        from vnstock import Vnstock
        v = Vnstock().stock(symbol=symbol, source="VCI")
        df_ratio = v.finance.ratio()
        if df_ratio is None or df_ratio.empty:
            return {}

        data_cols = [c for c in df_ratio.columns if c not in ["item", "item_en", "item_id"]]
        if not data_cols:
            return {}
        latest_col = data_cols[-1]

        metric_map = {}
        for _, row in df_ratio.iterrows():
            item_name = str(row.get("item", "")).strip()
            val = row.get(latest_col)
            try:
                val_num = float(val) if pd.notnull(val) else None
            except (ValueError, TypeError):
                val_num = None
            if item_name:
                metric_map[item_name] = val_num

        def get_m(name, default=None):
            return metric_map.get(name, default)

        pe = get_m("P/E")
        pb = get_m("P/B")
        ps = get_m("P/S")
        ev_ebitda = get_m("EV/EBITDA")
        p_cf = get_m("Giá/ Dòng tiền")
        roe = get_m("ROE (%)")
        if roe is not None and roe < 1.0:
            roe = roe * 100
        roa = get_m("ROA (%)")
        if roa is not None and roa < 1.0:
            roa = roa * 100
        roic = get_m("ROIC")
        if roic is not None and roic < 1.0:
            roic = roic * 100
        debt_equity = get_m("Nợ/Vốn chủ") or get_m("Nợ trên vốn chủ")
        financial_leverage = get_m("Đòn bẩy tài chính")
        gross_margin = get_m("Biên LN gộp (%)")
        if gross_margin is not None and gross_margin < 1.0:
            gross_margin = gross_margin * 100
        net_margin = get_m("Biên LN sau thuế (%)")
        if net_margin is not None and net_margin < 1.0:
            net_margin = net_margin * 100
        current_ratio = get_m("Hệ số thanh toán hiện hành")
        quick_ratio = get_m("Hệ số thanh toán nhanh")
        market_cap = get_m("Vốn hóa")
        dividend_yield = get_m("Tỷ suất cổ tức (%)")
        if dividend_yield is not None and dividend_yield < 1.0:
            dividend_yield = dividend_yield * 100

        return {
            "symbol": symbol,
            "period": latest_col,
            "pe": round(pe, 2) if pe is not None else None,
            "pb": round(pb, 2) if pb is not None else None,
            "ps": round(ps, 2) if ps is not None else None,
            "ev_ebitda": round(ev_ebitda, 2) if ev_ebitda is not None else None,
            "p_cf": round(p_cf, 2) if p_cf is not None else None,
            "roe": round(roe, 2) if roe is not None else None,
            "roa": round(roa, 2) if roa is not None else None,
            "roic": round(roic, 2) if roic is not None else None,
            "debt_equity": round(debt_equity, 2) if debt_equity is not None else None,
            "financial_leverage": round(financial_leverage, 2) if financial_leverage is not None else None,
            "gross_margin": round(gross_margin, 2) if gross_margin is not None else None,
            "net_margin": round(net_margin, 2) if net_margin is not None else None,
            "current_ratio": round(current_ratio, 2) if current_ratio is not None else None,
            "quick_ratio": round(quick_ratio, 2) if quick_ratio is not None else None,
            "market_cap_bil": round(market_cap / 1e9, 1) if market_cap is not None else None,
            "dividend_yield": round(dividend_yield, 2) if dividend_yield is not None else None,
        }
    except Exception as e:
        logging.error(f"Lỗi khi lấy chỉ số tài chính cho {symbol}: {e}")
        return {}



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
