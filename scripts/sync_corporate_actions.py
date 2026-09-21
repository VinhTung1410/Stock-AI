import logging
import os
import sys
from datetime import datetime

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data_engine import fetch_corporate_dividends, load_portfolio, save_portfolio
from db_manager import get_supabase_client

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

CANDIDATE_DATE_COLS = ("ex_right_date", "ngay_gdkhq", "exercise_date", "exDate")


def _get_gdkhq_column(df):
    """Xác định cột ngày GDKHQ từ DataFrame trả về."""
    for col in CANDIDATE_DATE_COLS:
        if col in df.columns:
            return col
    return None


def _check_and_notify_gdkhq(symbol, cost_price, today_str):
    """Kiểm tra sự kiện GDKHQ và thông báo điều chỉnh giá vốn nếu có."""
    try:
        div_df = fetch_corporate_dividends(symbol)
        if div_df is None or div_df.empty:
            return False

        gdkhq_col = _get_gdkhq_column(div_df)
        if not gdkhq_col:
            return False

        today_events = div_df[div_df[gdkhq_col].astype(str).str.startswith(today_str)]
        if today_events.empty:
            return False

        logging.info("🚨 Phát hiện sự kiện GDKHQ hôm nay cho mã %s!", symbol)
        logging.info("Cần điều chỉnh giá vốn cho %s. Giá vốn cũ: %s", symbol, cost_price)

        client = get_supabase_client()
        if client:
            logging.info("Supabase client sẵn sàng cho việc cập nhật %s", symbol)
        return True
    except Exception:
        logging.exception("Lỗi đồng bộ cổ tức cho %s", symbol)
        return False


def sync_corporate_actions():
    portfolio = load_portfolio()
    if not portfolio:
        logging.info("Danh mục trống. Bỏ qua.")
        return

    today_str = datetime.now().strftime("%Y-%m-%d")
    updated = False

    for item in portfolio:
        symbol = item.get("symbol")
        cost_price = item.get("cost_price")
        if symbol and _check_and_notify_gdkhq(symbol, cost_price, today_str):
            updated = True

    if updated:
        save_portfolio(portfolio)
        logging.info("Đã lưu lại portfolio.json")


if __name__ == "__main__":
    sync_corporate_actions()
