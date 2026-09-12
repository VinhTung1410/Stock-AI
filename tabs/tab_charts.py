import streamlit as st
import streamlit.components.v1 as components
from data_engine import get_stock_chart_data
from components.tradingview_chart import generate_tradingview_html

def render_tab_charts(raw_portfolio: list):
    """Render Tab 3: Biểu đồ kỹ thuật tương tác (TradingView 60 FPS Native)."""
    symbols = [item["symbol"] for item in raw_portfolio]
    if symbols:
        selected_symbol = st.selectbox("🎯 Chọn cổ phiếu cần phân tích kỹ thuật:", symbols)
        df_chart = get_stock_chart_data(selected_symbol)
        
        if df_chart is not None and not df_chart.empty:
            tv_html = generate_tradingview_html(df_chart, selected_symbol)
            components.html(tv_html, height=530)
            st.caption("✨ **Biểu đồ Kỹ thuật:** Chọn khung thời gian (Phút, Giờ, Ngày, Tuần, Tháng) ở header. Bật/tắt chỉ báo **MA, EMA, MACD, RSI, BOLL** bên dưới đáy. Rê chuột trên nến để xem chi tiết từng chỉ báo. Lăn chuột để phóng to/thu nhỏ.")
        else:
            st.error(f"Không thể tải biểu đồ cho mã {selected_symbol}")
    else:
        st.info("Chưa có mã cổ phiếu nào trong danh mục để xem biểu đồ.")
