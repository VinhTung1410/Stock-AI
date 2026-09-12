import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
from components.tradingview_chart import generate_tradingview_html
from components.echarts_valuation import generate_echarts_valuation_html

def render_tab_market(df_vnindex: pd.DataFrame):
    """Render Tab 2: Thị trường VN-Index & Bội số Định giá P/E, P/B."""
    if df_vnindex is not None and not df_vnindex.empty:
        latest_idx = df_vnindex["close"].iloc[-1]
        prev_idx = df_vnindex["close"].iloc[-2] if len(df_vnindex) > 1 else latest_idx
        idx_change = ((latest_idx - prev_idx) / prev_idx) * 100
        latest_pe = df_vnindex["PE"].iloc[-1]
        latest_pb = df_vnindex["PB"].iloc[-1]

        kpi1, kpi2, kpi3, kpi4 = st.columns(4)
        kpi1.metric("Chỉ số VN-INDEX", f"{latest_idx:,.2f}", f"{idx_change:+.2f}%")
        kpi2.metric("P/E Thị Trường", f"{latest_pe:.1f} lần", "Vùng hợp lý")
        kpi3.metric("P/B Thị Trường", f"{latest_pb:.2f} lần", "Hấp dẫn trung hạn")
        kpi4.metric("Thanh khoản phiên", f"{int(df_vnindex['volume'].iloc[-1]):,} cp")

        # 1. BIỂU ĐỒ NẾN NHẬT VN-INDEX
        st.subheader("📉 Biểu đồ Kỹ thuật Chỉ số VN-INDEX")
        tv_vnindex_html = generate_tradingview_html(df_vnindex, "VNINDEX")
        components.html(tv_vnindex_html, height=530)

        st.divider()

        # 2. HAI BIỂU ĐỒ ĐỊNH GIÁ P/E VÀ P/B CỦA VN-INDEX
        st.subheader("📊 Tương quan Bội số Định giá Thị trường")
        valuation_view = st.radio(
            "📐 Bố cục hiển thị biểu đồ định giá:",
            ["🖥️ Toàn cảnh P/E (Khuyên dùng)", "📈 Toàn cảnh P/B", "↔️ So sánh song song (2 Cột)"],
            horizontal=True
        )

        if valuation_view == "🖥️ Toàn cảnh P/E (Khuyên dùng)":
            st.caption("💡 **Chế độ Toàn cảnh:** Không gian mở rộng tối đa giúp quan sát trọn vẹn xu hướng định giá P/E so với đỉnh/đáy lịch sử VN-INDEX và đường Trung bình (TB).")
            html_pe = generate_echarts_valuation_html(df_vnindex, metric="PE")
            components.html(html_pe, height=480)
        elif valuation_view == "📈 Toàn cảnh P/B":
            st.caption("💡 **Chế độ Toàn cảnh:** Phân tích giá trị sổ sách P/B của toàn thị trường mở rộng 100% chiều ngang.")
            html_pb = generate_echarts_valuation_html(df_vnindex, metric="PB")
            components.html(html_pb, height=480)
        else:
            col_pe, col_pb = st.columns(2)
            with col_pe:
                html_pe = generate_echarts_valuation_html(df_vnindex, metric="PE")
                components.html(html_pe, height=480)

            with col_pb:
                html_pb = generate_echarts_valuation_html(df_vnindex, metric="PB")
                components.html(html_pb, height=480)
    else:
        st.error("Chưa tải được dữ liệu định giá VN-Index từ hệ thống.")
