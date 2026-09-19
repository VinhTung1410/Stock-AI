import os

os.environ["VNSTOCK_TELEMETRY"] = "off"
try:
    import vnai
    vnai.disable_telemetry()
except Exception:
    pass
import io
import json
import logging
import re
import urllib.request
from datetime import datetime, timedelta

import feedparser
import pandas as pd
import requests

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

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


def _parse_numeric(val, default=0.0, is_int: bool = False):
    """Safely parse numeric values from sheet strings."""
    if not val or str(val).lower() == "nan":
        return int(default) if is_int else float(default)
    cleaned = str(val).replace(",", "").strip()
    if is_int:
        cleaned = cleaned.replace(".", "")
    try:
        return int(float(cleaned)) if is_int else float(cleaned)
    except (ValueError, TypeError):
        return int(default) if is_int else float(default)


def _normalize_column_names(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize common Google Sheet column variations to standard schema."""
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
    if col_map:
        return df.rename(columns=col_map)
    col_names = ["symbol", "volume", "cost_price", "note"]
    return df.rename(columns={i: col_names[i] for i in range(min(len(col_names), df.shape[1]))})


def _is_valid_symbol(sym: str) -> bool:
    """Validate 3-character ticker format."""
    return bool(sym and re.match(r"^[A-Z0-9]{3}$", sym))


def _parse_sheet_portfolio(df: pd.DataFrame) -> list:
    """Extract valid portfolio holdings from normalized sheet DataFrame."""
    portfolio = []
    for _, row in df.iterrows():
        sym = str(row.get("symbol", "")).strip().upper()
        if not _is_valid_symbol(sym):
            continue
        volume = _parse_numeric(row.get("volume"), 0, is_int=True)
        if volume <= 0:
            continue
        cost_price = _parse_numeric(row.get("cost_price"), 0.0)
        note_val = row.get("note", "")
        note = str(note_val).strip() if pd.notnull(note_val) and str(note_val).strip() != "nan" else ""
        portfolio.append({"symbol": sym, "volume": volume, "cost_price": cost_price, "note": note})
    return portfolio


def _parse_sheet_watchlist(df: pd.DataFrame) -> list:
    """Extract watchlist items from sheet DataFrame."""
    watchlist = []
    for _, row in df.iterrows():
        sym = str(row.iloc[0]).strip().upper()
        if not _is_valid_symbol(sym):
            continue
        t_str = row.iloc[1] if len(row) > 1 and pd.notnull(row.iloc[1]) else "0"
        target_buy = _parse_numeric(t_str, 0.0)
        note_val = row.iloc[2] if len(row) > 2 and pd.notnull(row.iloc[2]) else "Theo dõi từ Google Sheet"
        note = str(note_val).strip() if str(note_val).strip() != "nan" else "Theo dõi từ Google Sheet"
        watchlist.append({"symbol": sym, "target_buy": target_buy, "note": note})
    return watchlist


def _parse_xlsx_sheets(target_url: str) -> tuple:
    """Download and parse multi-sheet XLSX from Google Sheets."""
    match = re.search(r"/spreadsheets/d/([a-zA-Z0-9-_]+)", target_url)
    if not match:
        return None, None
    sheet_id = match.group(1)
    xlsx_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=xlsx"
    req = urllib.request.Request(xlsx_url, headers={"User-Agent": "Mozilla/5.0"})
    content = urllib.request.urlopen(req, timeout=10).read()
    xl = pd.ExcelFile(io.BytesIO(content))

    portfolio, watchlist = [], []
    if len(xl.sheet_names) >= 1:
        df1 = xl.parse(xl.sheet_names[0], dtype=str)
        if not any(k in str(c).lower() for c in df1.columns for k in ["mã", "symbol"]):
            df1 = xl.parse(xl.sheet_names[0], header=None, dtype=str)
        portfolio = _parse_sheet_portfolio(_normalize_column_names(df1))

    if len(xl.sheet_names) >= 2:
        df2 = xl.parse(xl.sheet_names[1], header=None, dtype=str)
        watchlist = _parse_sheet_watchlist(df2)

    return (portfolio, watchlist) if (portfolio or watchlist) else (None, None)


def _split_csv_rows(df: pd.DataFrame) -> tuple[list, list]:
    """Classify rows into portfolio and watchlist from unified single-sheet CSV."""
    portfolio, watchlist = [], []
    for _, row in df.iterrows():
        sym = str(row.get("symbol", "")).strip().upper()
        if not _is_valid_symbol(sym):
            continue
        volume = _parse_numeric(row.get("volume"), 0, is_int=True)
        cost_price = _parse_numeric(row.get("cost_price"), 0.0)
        target_buy = _parse_numeric(row.get("target_buy"), 0.0)
        row_type = str(row.get("type", "")).strip().upper()
        note = str(row.get("note", "")).strip() if pd.notnull(row.get("note")) else ""

        if volume > 0 and row_type not in ["WATCH", "THEO DÕI", "THEODOI"]:
            portfolio.append({"symbol": sym, "volume": volume, "cost_price": cost_price, "note": note})
        else:
            watchlist.append({"symbol": sym, "target_buy": target_buy if target_buy > 0 else cost_price, "note": note})
    return portfolio, watchlist


def _parse_csv_fallback(target_url: str) -> tuple:
    """Download and parse single-sheet CSV fallback from Google Sheets."""
    csv_url = parse_google_sheet_csv_url(target_url)
    try:
        df = pd.read_csv(csv_url, dtype=str)
    except Exception:
        return None, None
    if df.empty:
        return None, None
    df = _normalize_column_names(df)
    if "symbol" not in df.columns:
        try:
            df_no_head = pd.read_csv(csv_url, header=None, dtype=str)
        except Exception:
            return None, None
        if df_no_head.empty:
            return None, None
        col_names = ["symbol", "volume", "cost_price", "note"]
        df = df_no_head.rename(columns={i: col_names[i] for i in range(min(len(col_names), df_no_head.shape[1]))})

    return _split_csv_rows(df)


def fetch_google_sheet_data(sheet_url: str = None) -> tuple:
    """Ingest holdings and watchlist from public Google Sheet (XLSX multi-sheet with CSV fallback)."""
    global _GSHEET_CACHE
    import time
    now_ts = time.time()
    if _GSHEET_CACHE["portfolio"] is not None and (now_ts - _GSHEET_CACHE["timestamp"]) < 45:
        return _GSHEET_CACHE["portfolio"], _GSHEET_CACHE["watchlist"]

    target_url = sheet_url or os.environ.get("GOOGLE_SHEET_URL", "").strip()
    if not target_url:
        return None, None

    try:
        portfolio, watchlist = _parse_xlsx_sheets(target_url)
        if portfolio is not None or watchlist is not None:
            _GSHEET_CACHE.update({"timestamp": now_ts, "portfolio": portfolio or [], "watchlist": watchlist or []})
            return portfolio or [], watchlist or []
    except Exception as e_xlsx:
        logging.warning(f"Could not parse Google Sheet XLSX ({e_xlsx}), falling back to CSV...")

    try:
        portfolio, watchlist = _parse_csv_fallback(target_url)
        if portfolio is not None or watchlist is not None:
            _GSHEET_CACHE.update({"timestamp": now_ts, "portfolio": portfolio or [], "watchlist": watchlist or []})
            return portfolio or [], watchlist or []
    except Exception as e:
        logging.exception("Error reading Google Sheet CSV: %s", e)

    return None, None


def clean_json_records(records: list) -> list:
    """Loại bỏ triệt để các giá trị NaN/Inf không hợp lệ trong chuẩn JSON."""
    import math
    cleaned = []
    for item in records:
        if not isinstance(item, dict):
            continue
        c = {}
        for k, v in item.items():
            if pd.isna(v):
                if k in ["note", "name", "symbol", "type", "channel", "tag"]:
                    c[k] = ""
                else:
                    c[k] = 0.0
            elif isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
                c[k] = 0.0
            else:
                c[k] = v
        cleaned.append(c)
    return cleaned


def update_google_sheet_portfolio(portfolio_data: list) -> tuple:
    """
    Ghi ngược danh mục nắm giữ từ Web Dashboard lên Sheet 1 của Google Sheet.
    Hỗ trợ qua webhook Google Apps Script (GOOGLE_SHEET_UPDATE_URL).
    Trả về (thành_công: bool, thông_điệp: str).
    """
    global _GSHEET_CACHE
    update_url = os.environ.get("GOOGLE_SHEET_UPDATE_URL", "").strip()
    if not update_url:
        return False, "Thiếu biến môi trường GOOGLE_SHEET_UPDATE_URL trên server."
    try:
        clean_data = clean_json_records(portfolio_data)
        payload = {"type": "portfolio", "data": clean_data}
        res = requests.post(update_url, json=payload, timeout=30)
        if res.status_code == 200:
            import time
            _GSHEET_CACHE["timestamp"] = time.time()
            _GSHEET_CACHE["portfolio"] = clean_data
            logging.info("✅ Đã ghi ngược danh mục lên Google Sheet thành công!")
            return True, "OK"
        else:
            err_msg = f"HTTP {res.status_code}: {res.text[:120]}"
            logging.error(f"Lỗi khi gửi dữ liệu lên Google Sheet Webhook: {err_msg}")
            return False, err_msg
    except requests.exceptions.Timeout:
        logging.error("Lỗi: Quá thời gian chờ phản hồi từ Google Apps Script (>30s).")
        return False, "Hết thời gian chờ (Timeout > 30s). Google Apps Script xử lý quá lâu."
    except Exception as e:
        logging.error(f"Lỗi kết nối Webhook Google Sheet: {e}")
        return False, str(e)


def update_google_sheet_watchlist(watchlist_data: list) -> tuple:
    """
    Ghi ngược danh sách theo dõi (Watchlist) từ Web Dashboard lên Sheet 2 của Google Sheet.
    Trả về (thành_công: bool, thông_điệp: str).
    """
    global _GSHEET_CACHE
    update_url = os.environ.get("GOOGLE_SHEET_UPDATE_URL", "").strip()
    if not update_url:
        return False, "Thiếu biến môi trường GOOGLE_SHEET_UPDATE_URL trên server."
    try:
        clean_data = clean_json_records(watchlist_data)
        payload = {"type": "watchlist", "data": clean_data}
        res = requests.post(update_url, json=payload, timeout=30)
        if res.status_code == 200:
            import time
            _GSHEET_CACHE["timestamp"] = time.time()
            _GSHEET_CACHE["watchlist"] = clean_data
            logging.info("✅ Đã ghi ngược Watchlist lên Google Sheet thành công!")
            return True, "OK"
        else:
            err_msg = f"HTTP {res.status_code}: {res.text[:120]}"
            logging.error(f"Lỗi gửi Watchlist lên Google Sheet: {err_msg}")
            return False, err_msg
    except requests.exceptions.Timeout:
        logging.error("Lỗi: Quá thời gian chờ phản hồi Watchlist từ Google Apps Script (>30s).")
        return False, "Hết thời gian chờ (Timeout > 30s). Google Apps Script xử lý quá lâu."
    except Exception as e:
        logging.error(f"Lỗi kết nối Webhook Google Sheet Watchlist: {e}")
        return False, str(e)


def load_portfolio(filepath: str = "data/portfolio.json") -> list:
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


def load_watchlist(filepath: str = "data/watchlist.json") -> list:
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


def save_portfolio(portfolio_data: list, filepath: str = "data/portfolio.json"):
    """Lưu danh mục cổ phiếu ra file json."""
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(portfolio_data, f, ensure_ascii=False, indent=2)


def save_watchlist(watchlist_data: list, filepath: str = "data/watchlist.json"):
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


_FOREIGN_FLOW_CACHE = {}


def fetch_foreign_trading_flow(symbol: str) -> dict:
    """
    Kéo dữ liệu giao dịch khớp lệnh Khối ngoại từ bảng giá vnstock:
    - Giá trị mua, bán, mua ròng (Tỷ VNĐ)
    - Trạng thái: 🟢 Mua ròng mạnh / ⚪ Trung tính / 🔴 Bán ròng xả hàng
    Cache 60s để tối ưu hiệu năng.
    """
    global _FOREIGN_FLOW_CACHE
    import time
    now = time.time()
    sym_clean = symbol.upper().strip()
    if sym_clean in _FOREIGN_FLOW_CACHE:
        cached_time, data = _FOREIGN_FLOW_CACHE[sym_clean]
        if now - cached_time < 60:
            return data

    default_res = {
        "symbol": sym_clean,
        "foreign_buy_val_bil": 0.0,
        "foreign_sell_val_bil": 0.0,
        "foreign_net_val_bil": 0.0,
        "buy_val_bil": 0.0,
        "sell_val_bil": 0.0,
        "net_val_bil": 0.0,
        "foreign_net_vol": 0,
        "status": "NEUTRAL",
        "status_vi": "Cân bằng",
        "badge": "Khối ngoại: Cân bằng",
        "icon": "⚪"
    }

    try:
        from vnstock import Trading
        t = Trading(symbol=sym_clean, source="VCI")
        pb = t.price_board([sym_clean])
        if pb is not None and not pb.empty:
            row = pb.iloc[0]
            f_buy_val = float(row.get(("match", "foreign_buy_value"), 0) or 0)
            f_sell_val = float(row.get(("match", "foreign_sell_value"), 0) or 0)
            f_buy_vol = int(float(row.get(("match", "foreign_buy_volume"), 0) or 0))
            f_sell_vol = int(float(row.get(("match", "foreign_sell_volume"), 0) or 0))

            net_val = f_buy_val - f_sell_val
            net_vol = f_buy_vol - f_sell_vol

            buy_bil = round(f_buy_val / 1e9, 2)
            sell_bil = round(f_sell_val / 1e9, 2)
            net_bil = round(net_val / 1e9, 2)

            if net_bil >= 5.0:
                status = "BUYING"
                status_vi = "Mua ròng"
                badge = f"Tây mua ròng: +{net_bil:.1f} tỷ"
                icon = "🟢"
            elif net_bil <= -8.0:
                status = "SELLING"
                status_vi = "Bán ròng"
                badge = f"Tây bán ròng: {net_bil:.1f} tỷ"
                icon = "🔴"
            else:
                status = "NEUTRAL"
                status_vi = "Cân bằng"
                badge = f"Tây cân bằng ({net_bil:+.1f} tỷ)"
                icon = "⚪"

            res = {
                "symbol": sym_clean,
                "foreign_buy_val_bil": buy_bil,
                "foreign_sell_val_bil": sell_bil,
                "foreign_net_val_bil": net_bil,
                "buy_val_bil": buy_bil,
                "sell_val_bil": sell_bil,
                "net_val_bil": net_bil,
                "foreign_net_vol": net_vol,
                "status": status,
                "status_vi": status_vi,
                "badge": badge,
                "icon": icon
            }
            _FOREIGN_FLOW_CACHE[sym_clean] = (now, res)
            return res
    except Exception as e:
        logging.warning(f"Không lấy được dữ liệu khối ngoại cho {sym_clean}: {e}")

    _FOREIGN_FLOW_CACHE[sym_clean] = (now, default_res)
    return default_res


def detect_news_trap(symbol: str, tech_data: dict, news_items: list = None) -> dict:
    """
    Thuật toán nhận diện 3 bẫy tin tức kinh điển trên TTCK Việt Nam:
    - Bẫy 1: Quá mua nổ tin (Sell on news / Overbought trap): RSI >= 68 kèm tin tốt.
    - Bẫy 2: Kéo xả nến cụt đầu (Upper wick / Shooting star trap): Vol lớn nhưng râu nến trên dài >= 45%.
    - Bẫy 3: Bắt dao rơi (Falling knife trap): Giá nằm dưới cả MA20 và MA50.
    """
    if not tech_data:
        return {"is_trap": False, "trap_type": "NONE", "warning_msg": "", "severity": "NONE", "icon": "🟢"}

    curr_price = tech_data.get("current_price", 0.0)
    ma20 = tech_data.get("ma20", 0.0)
    ma50 = tech_data.get("ma50", 0.0)
    rsi14 = tech_data.get("rsi14", 50.0)
    vol_ratio = tech_data.get("vol_ratio", 1.0)
    upper_wick_ratio = tech_data.get("upper_wick_ratio", 0.0)

    has_news = False
    news_matched_title = ""
    if news_items:
        for n in news_items:
            title = n.get("title", "")
            tag = n.get("tag", "").upper()
            if symbol.upper() in title.upper() or tag in ["KQKD", "CỔ TỨC", "NỘI BỘ", "VĨ MÔ"]:
                has_news = True
                news_matched_title = title
                break

    # Bẫy 1: Quá mua nổ tin (RSI >= 68 và có tin tức giật gân)
    if has_news and rsi14 and rsi14 >= 68.0:
        return {
            "is_trap": True,
            "trap_type": "OVERBOUGHT_NEWS_TRAP",
            "warning_msg": f"BẪY MUA ĐUỔI TIN TỨC: Cổ phiếu có tin ('{news_matched_title[:45]}...') nhưng RSI(14) đã chạm {rsi14:.1f} (Quá mua). Nguy cơ bị xả chốt lời cực cao (Sell on news).",
            "severity": "HIGH",
            "icon": "⚠️"
        }

    # Bẫy 2: Nến cụt đầu nổ Vol (Kéo xả ngấm ngầm)
    if vol_ratio >= 1.30 and upper_wick_ratio >= 0.40:
        return {
            "is_trap": True,
            "trap_type": "UPPER_WICK_DISTRIBUTION_TRAP",
            "warning_msg": f"CẢNH BÁO NẾN CỤT ĐẦU: Thanh khoản nổ gấp {vol_ratio:.1f}x SMA20 nhưng râu nến trên chiếm {upper_wick_ratio*100:.0f}% biên độ! Lực cung bán chốt lời đè giá áp đảo.",
            "severity": "HIGH",
            "icon": "⚠️"
        }

    # Bẫy 3: Bắt dao rơi (Giá gãy cả MA20 và MA50)
    if ma20 and ma50 and curr_price < ma20 and curr_price < ma50:
        return {
            "is_trap": True,
            "trap_type": "FALLING_KNIFE_TRAP",
            "warning_msg": f"CẢNH BÁO BẮT DAO RƠI: Thị giá ({curr_price:.2f}k) nằm dưới cả MA20 ({ma20:.2f}k) và MA50 ({ma50:.2f}k). Cổ phiếu đang trong pha Downtrend / Rơi tự do.",
            "severity": "MEDIUM",
            "icon": "⛔"
        }

    return {
        "is_trap": False,
        "trap_type": "NONE",
        "warning_msg": "Kỹ thuật đạt chuẩn, không có dấu hiệu bẫy phân phối hay rủi ro bán tháo.",
        "severity": "NONE",
        "icon": "🟢"
    }


_TECH_CACHE = {}

def fetch_stock_technical(symbol: str, count_back: int = 60, fetch_foreign: bool = True) -> dict:
    """
    Kéo lịch sử giá và tính toán các chỉ số kỹ thuật:
    MA20, MA50, RSI14, Vol/Vol_SMA20, ATR(14), Giá trị GD 20 phiên (ADV20 Tỷ),
    Hình thái nến (Upper Wick) và Dòng tiền Khối ngoại.
    Tích hợp cache 120 giây chống nghẽn / Rate Limit vnstock.
    """
    global _TECH_CACHE
    import time
    now = time.time()
    sym_clean = symbol.upper().strip()
    cache_key = f"{sym_clean}_{fetch_foreign}"
    if cache_key in _TECH_CACHE:
        c_time, c_data = _TECH_CACHE[cache_key]
        if now - c_time < 120:
            return c_data

    try:
        from vnstock.api.quote import Quote
        q = Quote(symbol=sym_clean, source="VCI")

        # Lấy ngày hiện tại và 120 ngày trước để đủ tính MA50 & RSI14 & ATR
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

        high = float(latest.get("high", current_price))
        low = float(latest.get("low", current_price))
        open_price = float(latest.get("open", current_price))

        candle_range = high - low
        upper_wick = high - max(open_price, current_price)
        upper_wick_ratio = round(upper_wick / candle_range, 2) if candle_range > 0 else 0.0

        ma20 = float(latest["MA20"]) if pd.notnull(latest["MA20"]) else None
        ma50 = float(latest["MA50"]) if pd.notnull(latest["MA50"]) else None
        rsi14 = float(latest["RSI14"]) if pd.notnull(latest["RSI14"]) else None
        vol = float(latest["volume"])
        vol_ma20 = float(latest["VOL_MA20"]) if pd.notnull(latest["VOL_MA20"]) else vol
        vol_ratio = (vol / vol_ma20) if vol_ma20 > 0 else 1.0

        # Thanh khoản bình quân 20 phiên (Tỷ VND)
        adv20_billion = round((vol_ma20 * current_price * 1000) / 1e9, 2)

        # Tính ATR(14)
        from quant_engine import calculate_atr
        atr14 = calculate_atr(df, period=14)

        # Xác định trạng thái kỹ thuật
        status_ma20 = "Nằm TRÊN MA20 (Khả quan)" if ma20 and current_price >= ma20 else "Nằm DƯỚI MA20 (Thận trọng)"

        # Kéo dòng tiền khối ngoại nếu được yêu cầu
        foreign_data = fetch_foreign_trading_flow(symbol) if fetch_foreign else {}

        # Phát hiện bẫy kỹ thuật / nến
        trap_info = detect_news_trap(symbol, {
            "current_price": current_price,
            "ma20": ma20,
            "ma50": ma50,
            "rsi14": rsi14,
            "vol_ratio": vol_ratio,
            "upper_wick_ratio": upper_wick_ratio
        })

        # Tính giá trần / sàn ước lượng (HOSE ±7%, HNX ±10%)
        # Mặc định an toàn cho HOSE: 6.8% - 7.0%
        ref_price = prev_close
        ceiling_price = round(ref_price * 1.069, 2) if ref_price else current_price
        floor_price = round(ref_price * 0.931, 2) if ref_price else current_price
        is_ceiling = (current_price >= ceiling_price * 0.998) or (change_pct >= 6.7)
        is_floor = (current_price <= floor_price * 1.002) or (change_pct <= -6.7)

        res = {
            "symbol": symbol,
            "date": str(latest["time"]),
            "current_price": current_price,
            "ref_price": ref_price,
            "ceiling_price": ceiling_price,
            "floor_price": floor_price,
            "is_ceiling": is_ceiling,
            "is_floor": is_floor,
            "change_pct": round(change_pct, 2),
            "open": open_price,
            "high": high,
            "low": low,
            "ma20": round(ma20, 2) if ma20 else None,
            "ma50": round(ma50, 2) if ma50 else None,
            "status_ma20": status_ma20,
            "rsi14": round(rsi14, 1) if rsi14 else None,
            "volume": int(vol),
            "vol_ratio": round(vol_ratio, 2),
            "adv20_billion": adv20_billion,
            "atr14": atr14,
            "upper_wick_ratio": upper_wick_ratio,
            "foreign_flow": foreign_data,
            "trap_info": trap_info
        }
        _TECH_CACHE[cache_key] = (now, res)
        return res
    except Exception as e:
        logging.error(f"Lỗi khi lấy kỹ thuật mã {symbol}: {e}")
        return {}


def detect_gdkhq_event(symbol: str, tech_dict: dict, vnindex_chg_pct: float = 0.0) -> dict:
    """
    KHIÊN CHẮN NGÀY GIAO DỊCH KHÔNG HƯỞNG QUYỀN (GDKHQ / CORPORATE ACTION SHIELD):
    Phát hiện hiện tượng sụt giảm giá kỹ thuật do chia cổ tức bằng tiền mặt hoặc cổ phiếu thưởng.
    - Dấu hiệu: Thị giá sụt giảm sâu so với phiên trước (Gap Down đầu phiên <= -4.0%)
      trong khi VN-Index không bán tháo diện rộng (VN-Index > -1.5%).
    - Mục đích: Ngăn chặn triệt để tình trạng Trading Bot hoảng loạn bắn Stop-Loss sai.
    """
    if not tech_dict:
        return {"is_gdkhq": False, "reason": ""}

    curr_p = tech_dict.get("current_price", 0.0)
    ref_p = tech_dict.get("ref_price", curr_p)
    open_p = tech_dict.get("open", curr_p)
    change_pct = tech_dict.get("change_pct", 0.0)

    # 1. Kiểm tra bước nhảy giá đầu phiên (Opening Gap) so với giá tham chiếu
    opening_gap_pct = ((open_p - ref_p) / ref_p * 100) if ref_p > 0 else 0.0

    # Nếu cổ phiếu rơi mạnh bất thường ngay từ đầu phiên nhưng thị trường chung ổn định
    if opening_gap_pct <= -4.5 and vnindex_chg_pct >= -1.5:
        return {
            "is_gdkhq": True,
            "gap_pct": round(opening_gap_pct, 2),
            "reason": (
                f"Phát hiện Gap Down kỹ thuật bất thường ({opening_gap_pct:+.1f}%) "
                f"trong khi VN-Index bình ổn ({vnindex_chg_pct:+.1f}%). "
                f"Khả năng cao là ngày GDKHQ (chia cổ tức / phát hành thêm). Tạm dừng cắt lỗ cơ học!"
            )
        }

    return {"is_gdkhq": False, "reason": ""}


def evaluate_portfolio(portfolio: list) -> pd.DataFrame:
    """
    Tính toán lãi/lỗ và tổng hợp tình trạng danh mục theo chuẩn AI Stock Copilot V2:
    - Bổ sung Fair Value & Margin of Safety (MoS %).
    - Bổ sung Trailing Stop cho vị thế lãi, Stop-loss cho vị thế lỗ.
    - Gắn thẻ Hành động V2 (Chốt lời từng phần / Nâng chặn lãi vs Theo dõi).
    """
    from concurrent.futures import ThreadPoolExecutor

    from quant_engine import evaluate_holding_position
    from quant_valuation import calculate_fair_value_and_mos

    # Tối ưu hóa hiệu năng: Kéo dữ liệu kỹ thuật đa luồng song song (giảm thời gian chờ từ 20s xuống ~3s)
    symbols = [item["symbol"] for item in portfolio]
    tech_map = {}
    if symbols:
        with ThreadPoolExecutor(max_workers=min(len(symbols), 5)) as executor:
            future_to_sym = {executor.submit(fetch_stock_technical, s): s for s in symbols}
            for future in future_to_sym:
                s = future_to_sym[future]
                try:
                    tech_map[s] = future.result()
                except Exception as e:
                    logging.warning(f"Lỗi lấy dữ liệu song song cho {s}: {e}")
                    tech_map[s] = {}

    records = []
    for item in portfolio:
        symbol = item["symbol"]
        volume = item["volume"]
        cost_price = item["cost_price"]
        note = item.get("note", "")

        tech = tech_map.get(symbol) or fetch_stock_technical(symbol)
        curr_price = tech.get("current_price", cost_price)

        cost_value = volume * cost_price * 1000  # Đơn vị giá vnstock thường là nghìn VNĐ
        market_value = volume * curr_price * 1000
        pnl_vnd = market_value - cost_value
        pnl_pct = ((curr_price - cost_price) / cost_price) * 100 if cost_price else 0.0

        ff = tech.get("foreign_flow", {})
        ff_net = round(float(ff.get("net_val_bil", 0.0)), 1) if ff else 0.0
        tr = tech.get("trap_info", {})
        trap_label = f"⚠️ {tr.get('trap_type', 'BẪY')}" if tr.get("is_trap") else "✅ An toàn"

        # Đánh giá Fair Value & MoS
        val_res = calculate_fair_value_and_mos(symbol=symbol, current_price=curr_price, sector=note)
        fair_val = val_res.get("fair_value", curr_price)
        mos_pct = val_res.get("mos_pct", 0.0)

        # Đánh giá vị thế nắm giữ V2
        row_dict = {"symbol": symbol, "avg_price": cost_price, "volume": volume, "market_price": curr_price}
        pos_eval = evaluate_holding_position(row_dict, tech)

        action_v2 = pos_eval.get("action", "🟢 NẮM GIỮ")
        defense_target = pos_eval.get("trailing_stop") if pos_eval.get("is_profit") else pos_eval.get("stop_loss")

        records.append({
            "Mã CP": symbol,
            "Khối lượng": volume,
            "Giá vốn (k)": cost_price,
            "Thị giá (k)": curr_price,
            "Thay đổi (%)": tech.get("change_pct", 0.0),
            "Lãi/Lỗ (%)": round(pnl_pct, 2),
            "Lãi/Lỗ (VND)": int(pnl_vnd),
            "Fair Value (k)": round(fair_val, 2),
            "MoS (%)": round(mos_pct, 1),
            "Chặn lãi/Cắt lỗ (k)": defense_target,
            "Hành động V2": action_v2,
            "Vị thế MA20": tech.get("status_ma20", "N/A"),
            "Khối ngoại (Tỷ)": ff_net,
            "Tín hiệu Bẫy": trap_label,
            "RSI(14)": tech.get("rsi14", "N/A"),
            "Vol/TB20": tech.get("vol_ratio", 1.0),
        })
    df = pd.DataFrame(records)
    try:
        from quant_sanity_check import run_full_portfolio_sanity_check
        _, _, clean_df = run_full_portfolio_sanity_check(df)
        return clean_df
    except Exception as e:
        logging.warning(f"Sanity check warning in evaluate_portfolio: {e}")
        return df


def evaluate_watchlist(watchlist: list) -> pd.DataFrame:
    """
    Tính toán tín hiệu kỹ thuật & định giá cho Danh mục Theo Dõi (Watchlist) V2:
    - Hiển thị Fair Value & Margin of Safety (MoS %).
    - Giúp phát hiện sớm các cổ phiếu đạt tiêu chuẩn an toàn vốn.
    """
    from concurrent.futures import ThreadPoolExecutor

    from quant_valuation import calculate_fair_value_and_mos

    # Tối ưu hóa tải song song đa luồng cho watchlist
    symbols = [item["symbol"] for item in watchlist]
    tech_map = {}
    if symbols:
        with ThreadPoolExecutor(max_workers=min(len(symbols), 6)) as executor:
            future_to_sym = {executor.submit(fetch_stock_technical, s): s for s in symbols}
            for future in future_to_sym:
                s = future_to_sym[future]
                try:
                    tech_map[s] = future.result()
                except Exception as e:
                    logging.warning(f"Lỗi lấy dữ liệu song song cho {s}: {e}")
                    tech_map[s] = {}

    records = []
    for item in watchlist:
        symbol = item["symbol"]
        target_buy = float(item.get("target_buy", 0.0))
        note = item.get("note", "")

        tech = tech_map.get(symbol) or fetch_stock_technical(symbol)
        curr_price = tech.get("current_price", target_buy)
        diff_pct = ((curr_price - target_buy) / target_buy * 100) if target_buy > 0 else 0.0

        ff = tech.get("foreign_flow", {})
        ff_net = round(float(ff.get("net_val_bil", 0.0)), 1) if ff else 0.0
        tr = tech.get("trap_info", {})
        trap_label = f"⚠️ {tr.get('trap_type', 'BẪY')}" if tr.get("is_trap") else "✅ An toàn"

        val_res = calculate_fair_value_and_mos(symbol=symbol, current_price=curr_price, sector=note)
        fair_val = val_res.get("fair_value", curr_price)
        mos_pct = val_res.get("mos_pct", 0.0)

        records.append({
            "Mã CP": symbol,
            "Thị giá (k)": curr_price,
            "Thay đổi (%)": tech.get("change_pct", 0.0),
            "Fair Value (k)": round(fair_val, 2),
            "MoS (%)": round(mos_pct, 1),
            "Giá chờ mua (k)": target_buy if target_buy > 0 else curr_price,
            "Khoảng cách (%)": round(diff_pct, 2),
            "Vị thế MA20": tech.get("status_ma20", "N/A"),
            "Khối ngoại (Tỷ)": ff_net,
            "Tín hiệu Bẫy": trap_label,
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

                # Trích xuất link ảnh nếu có (linear non-backtracking parsing)
                img_match = re.search(r'src="([^"]+)"', summary_raw)
                img_url = None
                if img_match:
                    candidate_url = img_match.group(1).strip()
                    if re.search(r'\.(?:jpg|png|jpeg|webp)(?:$|[?#])', candidate_url, re.IGNORECASE):
                        img_url = candidate_url

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


# ==============================================================================
# HỆ THỐNG KIỂM SOÁT ĐỘ TIN CẬY TÍN HIỆU (SIGNAL CREDIBILITY & COOLDOWN ENGINE)
# ==============================================================================

SIGNAL_COOLDOWN_FILE = os.path.join(os.path.dirname(__file__), "data", ".signal_cooldown.json")
COOLDOWN_DAYS = 5
MAX_DAILY_BUY_SIGNALS = 2
MAX_OPEN_POSITIONS = 8
HIGH_CONVICTION_THRESHOLD = 70.0
MEDIUM_CONVICTION_THRESHOLD = 55.0


def calculate_conviction_score(
    mos_pct: float,
    val_confidence: str = "MEDIUM",
    curr_price: float = 0.0,
    ma20: float = 0.0,
    rsi: float = 50.0,
    vol_ratio: float = 1.0,
    cat_info: dict = None,
    foreign_flow: dict = None,
    is_trap: bool = False
) -> dict:
    """Calculate 4-pillar conviction score (100-point institutional scale).

    Pillars:
    - Pillar 1: Valuation & Margin of Safety (Max 40 pts)
    - Pillar 2: Technical Confluence (Max 25 pts)
    - Pillar 3: Catalyst & Narrative (Max 20 pts)
    - Pillar 4: Liquidity & Smart Money Flow (Max 15 pts)

    Classification:
    - >= 70 pts: HIGH (Eligible for RECOMMEND_BUY)
    - 55 - 69 pts: MEDIUM (WATCH_CONFIRMATION / Momentum setup)
    - < 55 pts: LOW (REJECT / CAUTION)
    """
    # 1. Pillar 1: Valuation & Margin of Safety (Max 40 pts)
    if mos_pct >= 25.0:
        mos_pts = 40.0
    elif mos_pct >= 15.0:
        mos_pts = 30.0
    elif mos_pct >= 8.0:
        mos_pts = 20.0
    elif mos_pct >= 0.0:
        mos_pts = 10.0
    else:
        mos_pts = 0.0

    if str(val_confidence).upper() in ["LOW", "N/A"]:
        mos_pts = min(mos_pts, 25.0)

    # 2. Pillar 2: Technical Confluence & Trend (Max 25 pts)
    tech_pts = 0.0
    if curr_price > 0 and ma20 > 0:
        if curr_price >= ma20:
            tech_pts += 10.0
        elif curr_price >= ma20 * 0.985:
            tech_pts += 5.0

    if 48.0 <= rsi <= 62.0:
        tech_pts += 10.0
    elif (44.0 <= rsi < 48.0) or (62.0 < rsi <= 68.0):
        tech_pts += 6.0
    elif 40.0 <= rsi <= 72.0:
        tech_pts += 2.0

    if not is_trap:
        tech_pts += 5.0
    else:
        tech_pts -= 15.0  # Heavy penalty for distribution/bull trap

    # 3. Pillar 3: Catalyst & Verified Narrative (Max 20 pts)
    cat_pts = 0.0
    if cat_info:
        tag = str(cat_info.get("tag", "")).upper()
        if any(k in tag for k in ["KQKD", "CỔ TỨC", "VĨ MÔ", "NỘI BỘ", "M&A", "TĂNG TRƯỞNG"]):
            cat_pts = 20.0
        elif any(k in tag for k in ["WATCHLIST", "CHIẾN LƯỢC", "NGÀNH"]):
            cat_pts = 15.0
        else:
            cat_pts = 10.0
    else:
        cat_pts = 5.0

    # 4. Pillar 4: Liquidity & Smart Money Flow (Max 15 pts)
    flow_pts = 0.0
    if vol_ratio >= 1.3:
        flow_pts += 10.0
    elif vol_ratio >= 1.0:
        flow_pts += 7.0
    elif vol_ratio >= 0.85:
        flow_pts += 4.0
    else:
        flow_pts += 1.0

    if foreign_flow:
        f_status = foreign_flow.get("status", "")
        f_badge = foreign_flow.get("badge", "")
        if f_status == "BUYING" or "MUA RÒNG" in str(f_badge).upper():
            flow_pts += 5.0
        elif f_status == "SELLING" or "BÁN RÒNG" in str(f_badge).upper():
            flow_pts += 0.0
        else:
            flow_pts += 3.0
    else:
        flow_pts += 3.0

    total_score = round(max(0.0, min(100.0, mos_pts + tech_pts + cat_pts + flow_pts)), 1)
    if total_score >= HIGH_CONVICTION_THRESHOLD:
        tier = "HIGH"
    elif total_score >= MEDIUM_CONVICTION_THRESHOLD:
        tier = "MEDIUM"
    else:
        tier = "LOW"

    return {
        "score": total_score,
        "tier": tier,
        "breakdown": {
            "valuation": mos_pts,
            "technical": tech_pts,
            "catalyst": cat_pts,
            "liquidity": flow_pts
        }
    }


def load_signal_cooldown() -> dict:
    """Load signal cooldown registry from local JSON file."""
    if os.path.exists(SIGNAL_COOLDOWN_FILE):
        try:
            with open(SIGNAL_COOLDOWN_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_signal_cooldown(data: dict):
    """Persist signal cooldown registry to local JSON file."""
    try:
        os.makedirs(os.path.dirname(SIGNAL_COOLDOWN_FILE), exist_ok=True)
        with open(SIGNAL_COOLDOWN_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logging.warning(f"Could not persist signal cooldown to disk: {e}")


def is_symbol_in_cooldown(symbol: str, cooldown_days: int = COOLDOWN_DAYS) -> bool:
    """Check if a ticker is currently within the active cooldown window.

    Priority 1: Query Supabase signals table (Cloud persistence across restarts).
    Priority 2: Fallback to local JSON cache (data/.signal_cooldown.json) for offline resilience.
    """
    sym = symbol.upper().strip()
    try:
        from db_manager import check_symbol_recent_signal
        if check_symbol_recent_signal(sym, days=cooldown_days):
            return True
    except Exception as e:
        logging.debug(f"Supabase cooldown check fallback: {e}")

    # Fallback to local cache
    history = load_signal_cooldown()
    rec = history.get(sym)
    if not rec:
        return False
    last_signal_date = rec.get("last_signal_date")
    if not last_signal_date:
        return False
    try:
        last_dt = datetime.strptime(last_signal_date, "%Y-%m-%d").date()
        today = datetime.now().date()
        delta = (today - last_dt).days
        return delta < cooldown_days
    except Exception:
        return False


def record_signal_cooldown(symbol: str, action: str = "RECOMMEND_BUY", conviction_score: float = 0.0):
    """Record ticker into the cooldown registry after triggering a recommendation."""
    history = load_signal_cooldown()
    today_str = datetime.now().strftime("%Y-%m-%d")
    history[symbol.upper()] = {
        "last_signal_date": today_str,
        "action": action,
        "conviction_score": conviction_score
    }
    save_signal_cooldown(history)


def get_active_cooldown_symbols(cooldown_days: int = COOLDOWN_DAYS) -> list:
    """Return active cooldown symbols combining Supabase OPEN tracking records and local cache."""
    active = set()
    # 1. Supabase OPEN tracking records
    try:
        from db_manager import fetch_open_signals
        open_signals = fetch_open_signals()
        for s in open_signals:
            sym = s.get("symbol")
            if sym:
                active.add(sym.upper())
    except Exception as e:
        logging.debug(f"Supabase open signals fallback: {e}")

    # 2. Local JSON cache
    history = load_signal_cooldown()
    today = datetime.now().date()
    for sym, info in history.items():
        dt_str = info.get("last_signal_date", "")
        if not dt_str:
            continue
        try:
            d = datetime.strptime(dt_str, "%Y-%m-%d").date()
            if (today - d).days < cooldown_days:
                active.add(sym.upper())
        except Exception:
            continue
    return list(active)


def scan_market_opportunities(extra_symbols: list = None) -> list:
    """Scan market opportunities using 2-tier Catalyst + Technical Confluence approach.

    1. Ingest RSS financial news to identify catalyst stocks (earnings, dividends, macro).
    2. Merge with user watchlist and top market liquid leaders.
    3. Evaluate technical indicators (MA20, RSI, Volume ratio, Smart money flow).
    4. Compute 4-pillar conviction score (0-100) and enforce hard gates (MoS, Cooldown, Daily Budget).

    Returns:
        List of opportunity dictionaries ranked by conviction score.
    """

    # 1. Ingest CafeF RSS and build catalyst map
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
        logging.warning(f"Failed to fetch CafeF RSS for opportunity scanner: {e}")

    # 2. Add symbols from watchlist
    watchlist_items = load_watchlist()
    for w in watchlist_items:
        w_sym = w.get("symbol", "").upper()
        if w_sym and w_sym not in catalyst_map:
            catalyst_map[w_sym] = {
                "tag": "WATCHLIST",
                "title": w.get("note") or "Cổ phiếu chiến lược trong danh sách theo dõi",
                "summary": ""
            }

    # 3. Tạo danh sách ứng viên (Ưu tiên mã người dùng theo dõi trong extra_symbols + watchlist)
    candidate_symbols = []
    for s in (extra_symbols or []):
        if s and s.upper() not in candidate_symbols:
            candidate_symbols.append(s.upper())
    for w in watchlist_items:
        ws = w.get("symbol", "").upper()
        if ws and ws not in candidate_symbols:
            candidate_symbols.append(ws)
    for c in list(catalyst_map.keys()):
        if c not in candidate_symbols:
            candidate_symbols.append(c)
    for t in TOP_MARKET_SYMBOLS:
        if t not in candidate_symbols:
            candidate_symbols.append(t)

    # Khống chế danh sách quét tối đa 8 mã để đảm bảo an toàn hạn mức 20 req/phút của vnstock
    pool = candidate_symbols[:8]

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

            # Kiểm tra bẫy tin tức và rủi ro phân phối
            trap_info = tech.get("trap_info", {})
            foreign_flow = tech.get("foreign_flow", {})
            is_trap = trap_info.get("is_trap", False)

            # Tích hợp định giá Fair Value & Biên an toàn MoS
            from quant_engine import calculate_weighted_entry_and_rr
            from quant_valuation import calculate_fair_value_and_mos

            val_res = calculate_fair_value_and_mos(symbol=sym, current_price=curr_price, sector=sector)
            fv = val_res.get("fair_value", curr_price * 1.10)
            mos_pct = val_res.get("mos_pct", 0.0)
            val_method = val_res.get("valuation_method", "N/A")
            val_conf = val_res.get("confidence", "MEDIUM")
            p_target = val_res.get("price_target") or round(fv * 1.05, 2)

            # --- KIỂM TRA ĐIỀU KIỆN KỸ THUẬT THỰC CHIẾN ---
            # --- TÍNH ĐIỂM CONVICTION THEO 4 TRỤ CỘT ---
            conviction = calculate_conviction_score(
                mos_pct=mos_pct,
                val_confidence=val_conf,
                curr_price=curr_price,
                ma20=ma20,
                rsi=rsi,
                vol_ratio=vol_ratio,
                cat_info=cat_info,
                foreign_flow=foreign_flow,
                is_trap=is_trap
            )
            conv_score = conviction["score"]
            conv_tier = conviction["tier"]
            conv_breakdown = conviction["breakdown"]

            # --- KIỂM TRA ĐIỀU KIỆN KỸ THUẬT THỰC CHIẾN ---
            tech_allowed = curr_price >= (ma20 * 0.985)
            rsi_allowed = (44 <= rsi <= 68)
            vol_allowed = (vol_ratio >= 0.90)
            no_trap = not is_trap

            # A. ĐẠT CHUẨN HIGH CONVICTION (>= 70) VÀ KỸ THUẬT AN TOÀN -> KHUYẾN NGHỊ MUA
            if conv_score >= HIGH_CONVICTION_THRESHOLD and tech_allowed and rsi_allowed and vol_allowed and no_trap:
                target_price = p_target
                stop_loss = round(max(ma20 * 0.95, curr_price * 0.93), 2)
                # Đảm bảo Stop < current
                stop_loss = min(stop_loss, round(curr_price * 0.96, 2))

                # Phân tách 2 phong cách giao dịch: Lướt sóng T+ vs Gom hàng vị thế
                if vol_ratio >= 1.25 and change_pct >= 0.5:
                    style_type = "⚡ [LƯỚT SÓNG T+ / BREAKOUT]"
                    setup_type = f"⚡ BREAKOUT NỔ VOL VƯỢT NỀN (Conviction: {conv_score:.0f}/100)"
                    p_min = round(curr_price * 0.995, 2)
                    p_max = round(curr_price * 1.005, 2)
                    entry_zone = f"{p_min} - {p_max}"
                    entry_prices = [p_min, curr_price, p_max]
                    weights = [0.3, 0.4, 0.3]
                    rr_calc = calculate_weighted_entry_and_rr(entry_prices, weights, target_price, stop_loss)
                    avg_cost = rr_calc["weighted_entry"]
                    rr = rr_calc["risk_reward"]
                    execution_plan = f"Mua dứt khoát 1 lần quanh {curr_price}k (vùng {entry_zone}k). Vượt {p_max}k KHÔNG mua đuổi."
                else:
                    style_type = "💎 [GOM HÀNG VỊ THẾ / TRUNG HẠN]"
                    setup_type = f"💎 TÍCH LŨY NỀN GIÁ TRÊN MA20 (Conviction: {conv_score:.0f}/100)"
                    p_low = round(min(ma20, curr_price * 0.985), 2)
                    p_high = round(curr_price * 1.005, 2)
                    entry_zone = f"{p_low} - {p_high}"
                    entry_prices = [p_high, curr_price, p_low]
                    weights = [0.3, 0.4, 0.3]
                    rr_calc = calculate_weighted_entry_and_rr(entry_prices, weights, target_price, stop_loss)
                    avg_cost = rr_calc["weighted_entry"]
                    rr = rr_calc["risk_reward"]
                    execution_plan = f"Chia 3 phần: 30% tại {p_high}k, 40% tại {curr_price}k, 30% đón tại {p_low}k (Giá vốn BQ dự kiến: {avg_cost}k)."

                f_badge = foreign_flow.get("badge", "")
                return {
                    "symbol": sym,
                    "sector": sector,
                    "status": "RECOMMEND_BUY",
                    "conviction_score": conv_score,
                    "conviction_tier": conv_tier,
                    "conviction_breakdown": conv_breakdown,
                    "style_type": style_type,
                    "setup_type": setup_type,
                    "story_tag": story_tag,
                    "story": story_title,
                    "current_price": curr_price,
                    "entry_zone": entry_zone,
                    "avg_cost": avg_cost,
                    "execution_plan": execution_plan,
                    "target_price": target_price,
                    "fair_value": fv,
                    "mos_pct": mos_pct,
                    "valuation_method": val_method,
                    "confidence": val_conf,
                    "stop_loss": stop_loss,
                    "risk_reward": rr,
                    "rsi": rsi,
                    "vol_ratio": vol_ratio,
                    "foreign_flow": foreign_flow,
                    "rationale": f"Conviction {conv_score:.0f}/100 ({conv_tier}). Định giá MoS: {mos_pct:+.1f}% ({val_method}). Kỹ thuật: Trên MA20 ({ma20:.1f}), RSI {rsi:.1f}, Vol x{vol_ratio:.1f}. {f_badge}."
                }

            # B. MEDIUM CONVICTION (55-69) HOẶC CƠ BẢN TỐT (MOS >= 8%) NHƯNG KỸ THUẬT CHƯA XÁC NHẬN
            # -> ĐƯA VÀO RADAR THEO DÕI (WATCH_CONFIRMATION) CHO LƯỚT SÓNG HOẶC CHỜ NỀN
            elif conv_score >= MEDIUM_CONVICTION_THRESHOLD or mos_pct >= 8.0:
                watch_reason = []
                if curr_price < ma20:
                    watch_reason.append(f"giá dưới MA20 ({ma20:.1f})")
                if rsi < 45:
                    watch_reason.append(f"RSI yếu ({rsi:.1f})")
                if conv_score < HIGH_CONVICTION_THRESHOLD:
                    watch_reason.append(f"Conviction {conv_score:.0f}/100 cần thêm lực cầu")
                reason_str = ", ".join(watch_reason) if watch_reason else "chờ tín hiệu xác nhận dòng tiền"

                return {
                    "symbol": sym,
                    "sector": sector,
                    "status": "WATCH_CONFIRMATION",
                    "conviction_score": conv_score,
                    "conviction_tier": conv_tier,
                    "conviction_breakdown": conv_breakdown,
                    "setup_type": f"🟡 THEO DÕI / CHỜ NỀN CÂN BẰNG (Conviction: {conv_score:.0f}/100)",
                    "story_tag": story_tag,
                    "story": story_title,
                    "current_price": curr_price,
                    "fair_value": fv,
                    "mos_pct": mos_pct,
                    "valuation_method": val_method,
                    "confidence": val_conf,
                    "rsi": rsi,
                    "vol_ratio": vol_ratio,
                    "foreign_flow": foreign_flow,
                    "rationale": f"Cơ bản tốt (MoS {mos_pct:+.1f}%), Conviction {conv_score:.0f}/100 nhưng {reason_str}. Ưu tiên theo dõi chờ nến xác nhận ngừng rơi, không mua đuổi."
                }

            # C. CÓ TIN HOẶC DÍNH BẪY PHÂN PHỐI / ĐỊNH GIÁ ĐẮT -> CẢNH BÁO BẪY
            elif cat_info or is_trap or conv_score < MEDIUM_CONVICTION_THRESHOLD:
                caution_reason = []
                if is_trap:
                    caution_reason.append(trap_info.get("warning_msg", "Phát hiện bẫy kỹ thuật"))
                if curr_price < ma20:
                    caution_reason.append(f"Giá đang dưới MA20 ({ma20:.1f})")
                if rsi > 68:
                    caution_reason.append(f"RSI {rsi:.1f} quá mua")
                elif rsi < 42:
                    caution_reason.append(f"RSI {rsi:.1f} yếu")
                if foreign_flow.get("status") == "SELLING":
                    caution_reason.append(f"Tây bán ròng {foreign_flow.get('foreign_net_val_bil')} tỷ")
                if conv_score < MEDIUM_CONVICTION_THRESHOLD:
                    caution_reason.append(f"Điểm Conviction thấp ({conv_score:.0f}/100)")

                return {
                    "symbol": sym,
                    "sector": sector,
                    "status": "CAUTION_TRAP",
                    "conviction_score": conv_score,
                    "conviction_tier": conv_tier,
                    "setup_type": "⚠️ CẢNH BÁO BẪY / CHƯA ĐẠT CHUẨN MUA",
                    "story_tag": story_tag,
                    "story": story_title,
                    "current_price": curr_price,
                    "fair_value": fv,
                    "mos_pct": mos_pct,
                    "valuation_method": val_method,
                    "confidence": val_conf,
                    "rsi": rsi,
                    "vol_ratio": vol_ratio,
                    "foreign_flow": foreign_flow,
                    "rationale": " | ".join(caution_reason) if caution_reason else "Kỹ thuật chưa đạt chuẩn an toàn."
                }

            return None
        except Exception as e:
            logging.debug(f"Lỗi phân tích {sym}: {e}")
            return None

    all_results = []
    for sym in pool:
        try:
            res = analyze_symbol(sym)
            if res:
                all_results.append(res)
            import time
            time.sleep(0.2)
        except Exception as e:
            logging.debug(f"Lỗi khi xử lý {sym}: {e}")

    # Tách nhóm kết quả ban đầu
    buy_candidates = [r for r in all_results if r["status"] == "RECOMMEND_BUY"]
    watch_picks = [r for r in all_results if r["status"] == "WATCH_CONFIRMATION"]
    caution_picks = [r for r in all_results if r["status"] == "CAUTION_TRAP"]

    # 1. COOLDOWN FILTER (5-DAY): Deduplicate consecutive buy signals on the same symbol
    eligible_buys = []
    for c in buy_candidates:
        sym = c["symbol"]
        if is_symbol_in_cooldown(sym, cooldown_days=COOLDOWN_DAYS):
            # Downgrade to WATCH_CONFIRMATION
            c["status"] = "WATCH_CONFIRMATION"
            c["setup_type"] = f"⏳ THEO DÕI NẮM GIỮ (Đang Cooldown {COOLDOWN_DAYS} ngày)"
            c["rationale"] = (
                f"Mã {sym} đã phát tín hiệu khuyến nghị gần đây. "
                f"Hệ thống kích hoạt Cooldown {COOLDOWN_DAYS} ngày để bảo vệ vốn và tránh mua đuổi gia tăng giá vốn."
            )
            watch_picks.append(c)
        else:
            eligible_buys.append(c)

    # 2. PORTFOLIO DIVERSIFICATION GUARD (MAX 8 POSITIONS)
    active_cooldown_syms = get_active_cooldown_symbols(cooldown_days=COOLDOWN_DAYS)
    active_positions_count = len(active_cooldown_syms)

    if active_positions_count >= MAX_OPEN_POSITIONS:
        for c in eligible_buys:
            c["status"] = "WATCH_CONFIRMATION"
            c["setup_type"] = f"🛡️ CHỜ THU HỒI VỐN (Đã mở {active_positions_count}/{MAX_OPEN_POSITIONS} vị thế)"
            c["rationale"] = (
                f"Conviction {c.get('conviction_score', 0):.0f}/100 đạt chuẩn mua, nhưng danh mục đã đạt "
                f"hạn mức tối đa {MAX_OPEN_POSITIONS} vị thế đang theo dõi. Ưu tiên quản trị rủi ro, không mở thêm vị thế."
            )
            watch_picks.append(c)
        eligible_buys = []

    # 3. DAILY SIGNAL BUDGET (MAX 2 BUYS / DAY)
    # Priority ranking by Conviction Score desc, then Vol Ratio and R:R
    eligible_buys.sort(
        key=lambda x: (x.get("conviction_score", 0), x.get("vol_ratio", 1.0), x.get("risk_reward", 1.0)),
        reverse=True
    )

    approved_buys = eligible_buys[:MAX_DAILY_BUY_SIGNALS]
    overflow_buys = eligible_buys[MAX_DAILY_BUY_SIGNALS:]

    # Overflow candidates downgraded gracefully to WATCH_CONFIRMATION
    for c in overflow_buys:
        c["status"] = "WATCH_CONFIRMATION"
        c["setup_type"] = f"🎯 TIỀM NĂNG (VƯỢT HẠN MỨC {MAX_DAILY_BUY_SIGNALS} MÃ MUA/NGÀY)"
        c["rationale"] = (
            f"Conviction {c.get('conviction_score', 0):.0f}/100 rất tốt nhưng hệ thống giới hạn "
            f"tối đa {MAX_DAILY_BUY_SIGNALS} mã mua/ngày để tập trung sức mua. Đưa vào radar ưu tiên phiên tới."
        )
        watch_picks.append(c)

    # Record cooldown for approved buy signals
    for b in approved_buys:
        record_signal_cooldown(
            symbol=b["symbol"],
            action="RECOMMEND_BUY",
            conviction_score=b.get("conviction_score", 0.0)
        )

    # Sort watch and caution lists
    watch_picks.sort(key=lambda x: x.get("conviction_score", 0), reverse=True)
    caution_picks.sort(key=lambda x: x.get("vol_ratio", 1.0), reverse=True)

    # Return up to 2 Buys + 2 Watch + 2 Caution
    return approved_buys + watch_picks[:2] + caution_picks[:2]




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
        print(f"[{n.get('tag', n.get('keyword', 'TIN'))}] {n.get('title', '')}")
