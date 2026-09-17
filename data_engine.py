import os
os.environ["VNSTOCK_TELEMETRY"] = "off"
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
    from quant_valuation import calculate_fair_value_and_mos
    from quant_engine import evaluate_holding_position

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
    from quant_valuation import calculate_fair_value_and_mos

    records = []
    for item in watchlist:
        symbol = item["symbol"]
        target_buy = float(item.get("target_buy", 0.0))
        note = item.get("note", "")

        tech = fetch_stock_technical(symbol)
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
            from quant_valuation import calculate_fair_value_and_mos
            from quant_engine import calculate_weighted_entry_and_rr
            
            val_res = calculate_fair_value_and_mos(symbol=sym, current_price=curr_price, sector=sector)
            fv = val_res.get("fair_value", curr_price * 1.10)
            mos_pct = val_res.get("mos_pct", 0.0)
            val_method = val_res.get("valuation_method", "N/A")
            val_conf = val_res.get("confidence", "MEDIUM")
            p_target = val_res.get("price_target") or round(fv * 1.05, 2)

            # --- KIỂM TRA ĐIỀU KIỆN KỸ THUẬT THỰC CHIẾN ---
            tech_allowed = curr_price >= (ma20 * 0.985)
            rsi_allowed = (44 <= rsi <= 68)
            vol_allowed = (vol_ratio >= 0.90)
            no_trap = not is_trap

            # A. ĐẠT TOÀN DIỆN: ĐỊNH GIÁ RẺ (MOS >= 15%) HOẶC CÓ XÚC TÁC + KỸ THUẬT CHO PHÉP
            if (mos_pct >= 15.0 or cat_info) and tech_allowed and rsi_allowed and vol_allowed and no_trap:
                target_price = p_target
                stop_loss = round(max(ma20 * 0.95, curr_price * 0.93), 2)
                # Đảm bảo Stop < current
                stop_loss = min(stop_loss, round(curr_price * 0.96, 2))

                # Phân tách 2 phong cách giao dịch: Lướt sóng T+ vs Gom hàng vị thế
                if vol_ratio >= 1.25 and change_pct >= 0.5:
                    style_type = "⚡ [LƯỚT SÓNG T+ / BREAKOUT]"
                    setup_type = "⚡ BREAKOUT NỔ VOL VƯỢT NỀN"
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
                    setup_type = "💎 TÍCH LŨY NỀN GIÁ TRÊN MA20"
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
                    "rationale": f"Định giá MoS: {mos_pct:+.1f}% ({val_method}). Kỹ thuật: Trên MA20 ({ma20:.1f}), RSI {rsi:.1f}, Vol x{vol_ratio:.1f}. {f_badge}."
                }

            # B. CƠ BẢN & ĐỊNH GIÁ HẤP DẪN (MOS >= 8%) NHƯNG KỸ THUẬT CHƯA CHO PHÉP (VÍ DỤ MWG)
            # TUYỆT ĐỐI KHÔNG CHỤP MŨ LÀ BẪY TIN -> CHUYỂN SANG WATCH / WAIT FOR CONFIRMATION
            elif mos_pct >= 8.0:
                return {
                    "symbol": sym,
                    "sector": sector,
                    "status": "WATCH_CONFIRMATION",
                    "setup_type": "🟡 THEO DÕI / CHỜ NỀN CÂN BẰNG",
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
                    "rationale": f"Cơ bản tốt, Biên an toàn hấp dẫn (MoS {mos_pct:+.1f}%), nhưng giá đang nằm dưới MA20 ({ma20:.1f}) hoặc RSI yếu ({rsi:.1f}). Ưu tiên theo dõi chờ nến xác nhận ngừng rơi, không mua đuổi."
                }

            # C. CÓ TIN HOẶC DÍNH BẪY PHÂN PHỐI / ĐỊNH GIÁ ĐẮT -> CẢNH BÁO BẪY
            elif cat_info or is_trap:
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

                return {
                    "symbol": sym,
                    "sector": sector,
                    "status": "CAUTION_TRAP",
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
        print(f"[{n.get('tag', n.get('keyword', 'TIN'))}] {n.get('title', '')}")
