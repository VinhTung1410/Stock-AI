import os
import sys
import logging
from datetime import datetime

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data_engine import load_portfolio, save_portfolio, fetch_corporate_dividends
from db_manager import get_supabase_client

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

def sync_corporate_actions():
    portfolio = load_portfolio()
    if not portfolio:
        logging.info("Danh mục trống. Bỏ qua.")
        return

    today_str = datetime.now().strftime("%Y-%m-%d")
    updated = False

    for idx, item in enumerate(portfolio):
        symbol = item["symbol"]
        cost_price = item["cost_price"]
        
        try:
            div_df = fetch_corporate_dividends(symbol)
            if div_df is None or div_df.empty:
                continue
                
            # Tuỳ thuộc vào format của Vnstock (ex_right_date, ngay_gdkhq, ...)
            # Tìm ngày GDKHQ trùng với ngày hôm nay
            gdkhq_col = None
            for col in ['ex_right_date', 'ngay_gdkhq', 'exercise_date', 'exDate']:
                if col in div_df.columns:
                    gdkhq_col = col
                    break
            
            if gdkhq_col:
                today_events = div_df[div_df[gdkhq_col].astype(str).str.startswith(today_str)]
                if not today_events.empty:
                    logging.info(f"🚨 Phát hiện sự kiện GDKHQ hôm nay cho mã {symbol}!")
                    # Giả lập tính toán giá điều chỉnh mới.
                    # PO Review: Sẽ điều chỉnh trực tiếp JSON/DB.
                    logging.info(f"Cần điều chỉnh giá vốn cho {symbol}. Giá vốn cũ: {cost_price}")
                    
                    # portfolio[idx]["cost_price"] = new_cost_price
                    # updated = True
                    
                    client = get_supabase_client()
                    if client:
                        pass
                        # res = client.table("signals").update({"entry_price": new_cost_price, "is_adjusted": True}).eq("symbol", symbol).execute()
        except Exception:
            logging.exception(f"Lỗi đồng bộ cổ tức cho {symbol}")

    if updated:
        save_portfolio(portfolio)
        logging.info("Đã lưu lại portfolio.json")

if __name__ == "__main__":
    sync_corporate_actions()
