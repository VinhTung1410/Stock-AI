import os
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
from dotenv import load_dotenv

from data_engine import load_portfolio, save_portfolio, evaluate_portfolio, fetch_macro_news
from ai_analyst import generate_portfolio_analysis
from discord_alerts import send_discord_message, format_portfolio_embed

load_dotenv()

st.set_page_config(
    page_title="AI Stock Copilot - Quản trị Danh mục",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS cho phong cách chuyên nghiệp, Dark Mode hiện đại
st.markdown("""
<style>
    .metric-card {
        background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
        border: 1px solid #334155;
        border-radius: 10px;
        padding: 16px;
        text-align: center;
    }
    .metric-title { font-size: 14px; color: #94a3b8; margin-bottom: 4px; }
    .metric-val { font-size: 24px; font-weight: 700; color: #f8fafc; }
    .stDataFrame { border-radius: 8px; overflow: hidden; }
</style>
""", unsafe_allow_html=True)


@st.cache_data(ttl=300)
def get_cached_portfolio_eval():
    portfolio = load_portfolio()
    return evaluate_portfolio(portfolio), portfolio


@st.cache_data(ttl=600)
def get_stock_chart_data(symbol: str):
    from vnstock.api.quote import Quote
    q = Quote(symbol=symbol, source="VCI")
    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=200)).strftime("%Y-%m-%d")
    df = q.history(start=start_date, end=end_date)
    if df is not None and not df.empty:
        df = df.sort_values("time").reset_index(drop=True)
        # Các đường trung bình động
        df["MA20"] = df["close"].rolling(20).mean()
        df["MA50"] = df["close"].rolling(50).mean()
        
        # Chỉ báo RSI(14)
        delta = df["close"].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df["RSI"] = 100 - (100 / (1 + rs))

        # Chỉ báo MACD (12, 26, 9)
        exp12 = df["close"].ewm(span=12, adjust=False).mean()
        exp26 = df["close"].ewm(span=26, adjust=False).mean()
        df["MACD"] = exp12 - exp26
        df["Signal"] = df["MACD"].ewm(span=9, adjust=False).mean()
        df["Hist"] = df["MACD"] - df["Signal"]

        # Màu khối lượng giao dịch
        df["Vol_Color"] = ["#22c55e" if c >= o else "#ef4444" for c, o in zip(df["close"], df["open"])]
    return df


# --- SIDEBAR ---
with st.sidebar:
    st.title("🤖 AI Stock Copilot")
    st.caption("Trợ lý Chứng khoán Thông minh cho Nhóm Đầu tư")
    st.divider()

    st.subheader("⚡ Tác vụ Nhanh")
    if st.button("🔄 Làm mới dữ liệu", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    if st.button("📢 Bắn Báo cáo sang Discord", use_container_width=True):
        with st.spinner("Đang gửi báo cáo đến Discord..."):
            df_eval, _ = get_cached_portfolio_eval()
            news = fetch_macro_news()
            ai_text = generate_portfolio_analysis(df_eval, news)
            embed = format_portfolio_embed(df_eval, ai_text, report_type="BÁO CÁO THỦ CÔNG TỪ DASHBOARD")
            if send_discord_message(embeds=[embed]):
                st.success("✅ Đã gửi báo cáo thành công vào Discord!")
            else:
                st.error("❌ Gửi thất bại, kiểm tra lại Webhook!")

    st.divider()
    st.info("💡 **Gợi ý:** Bạn có thể chỉnh sửa trực tiếp danh mục bên tab 'Quản lý Danh mục'.")


# --- MAIN TABS ---
tab_overview, tab_charts, tab_portfolio, tab_ai = st.tabs([
    "📊 Tổng quan Danh mục", 
    "📈 Biểu đồ Kỹ thuật", 
    "⚙️ Quản lý Danh mục", 
    "🧠 Trợ lý Phân tích AI"
])

df_eval, raw_portfolio = get_cached_portfolio_eval()

# --- TAB 1: TỔNG QUAN ---
with tab_overview:
    if not df_eval.empty:
        total_cost = (df_eval["Khối lượng"] * df_eval["Giá vốn (k)"] * 1000).sum()
        total_market = (df_eval["Khối lượng"] * df_eval["Thị giá (k)"] * 1000).sum()
        total_pnl_vnd = total_market - total_cost
        total_pnl_pct = (total_pnl_vnd / total_cost * 100) if total_cost > 0 else 0.0

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Tổng vốn đầu tư", f"{total_cost:,.0f} đ")
        col2.metric("Tổng giá trị thị trường", f"{total_market:,.0f} đ")
        col3.metric("Lãi / Lỗ danh mục", f"{total_pnl_vnd:+,.0f} đ", f"{total_pnl_pct:+.2f}%")
        col4.metric("Số mã theo dõi", f"{len(df_eval)} mã")

        st.subheader("📋 Bảng trạng thái cổ phiếu")
        st.dataframe(
            df_eval.style.format({
                "Giá vốn (k)": "{:.2f}",
                "Thị giá (k)": "{:.2f}",
                "Thay đổi (%)": "{:+.2f}%",
                "Lãi/Lỗ (%)": "{:+.2f}%",
                "Lãi/Lỗ (VND)": "{:+,.0f}",
                "Vol/TB20": "{:.2f}",
            }),
            use_container_width=True,
            hide_index=True
        )

        st.subheader("📰 Tin tức Vĩ mô & Ngành nóng")
        news = fetch_macro_news()
        cols = st.columns(3)
        for i, item in enumerate(news[:6]):
            with cols[i % 3]:
                st.markdown(f"**[{item['keyword'].upper()}]** [{item['title']}]({item['link']})")
    else:
        st.warning("Danh mục hiện đang trống! Hãy thêm mã ở tab 'Quản lý Danh mục'.")


# --- TAB 2: BIỂU ĐỒ KỸ THUẬT ---
with tab_charts:
    symbols = [item["symbol"] for item in raw_portfolio]
    if symbols:
        col_select, col_days = st.columns([3, 2])
        with col_select:
            selected_symbol = st.selectbox("🎯 Chọn cổ phiếu cần phân tích:", symbols)
        with col_days:
            time_range = st.selectbox("⏱️ Khung thời gian quan sát:", ["1 tháng (Ngắn hạn)", "3 tháng (Chuẩn)", "6 tháng (Trung hạn)", "Toàn bộ"], index=1)

        # Thanh điều khiển bật tắt chỉ báo theo nhu cầu
        st.markdown("**🛠️ Tùy chỉnh Chỉ báo Kỹ thuật & Công cụ Phân tích:**")
        c1, c2, c3, c4, c5 = st.columns(5)
        show_ma20 = c1.checkbox("📈 Đường MA20 (Cam)", value=True)
        show_ma50 = c2.checkbox("📉 Đường MA50 (Xanh)", value=True)
        show_volume = c3.checkbox("📊 Khối lượng (Vol)", value=True)
        show_rsi = c4.checkbox("⚡ Chỉ báo RSI(14)", value=True)
        show_macd = c5.checkbox("🌊 Chỉ báo MACD", value=True)

        df_chart = get_stock_chart_data(selected_symbol)
        
        if df_chart is not None and not df_chart.empty:
            # Lọc số phiên theo khung thời gian đã chọn
            if time_range == "1 tháng (Ngắn hạn)":
                df_view = df_chart.iloc[-25:].copy()
            elif time_range == "3 tháng (Chuẩn)":
                df_view = df_chart.iloc[-65:].copy()
            elif time_range == "6 tháng (Trung hạn)":
                df_view = df_chart.iloc[-130:].copy()
            else:
                df_view = df_chart.copy()

            # Định hình cấu trúc Subplots động
            has_rsi = show_rsi
            has_macd = show_macd

            if has_rsi and has_macd:
                rows = 3
                row_heights = [0.55, 0.22, 0.23]
                chart_height = 750
            elif has_rsi or has_macd:
                rows = 2
                row_heights = [0.70, 0.30]
                chart_height = 620
            else:
                rows = 1
                row_heights = [1.0]
                chart_height = 500

            fig = make_subplots(
                rows=rows,
                cols=1,
                shared_xaxes=True,
                vertical_spacing=0.03,
                row_heights=row_heights
            )

            # 1. Nến Nhật (Row 1)
            fig.add_trace(go.Candlestick(
                x=df_view["time"],
                open=df_view["open"],
                high=df_view["high"],
                low=df_view["low"],
                close=df_view["close"],
                name="Nến Nhật",
                increasing_line_color="#22c55e",
                decreasing_line_color="#ef4444"
            ), row=1, col=1)

            # Các đường MA
            if show_ma20 and "MA20" in df_view.columns:
                fig.add_trace(go.Scatter(
                    x=df_view["time"], y=df_view["MA20"],
                    line=dict(color="#f59e0b", width=1.5),
                    name="MA20"
                ), row=1, col=1)

            if show_ma50 and "MA50" in df_view.columns:
                fig.add_trace(go.Scatter(
                    x=df_view["time"], y=df_view["MA50"],
                    line=dict(color="#3b82f6", width=1.5),
                    name="MA50"
                ), row=1, col=1)

            # Khối lượng giao dịch (Overlay mờ ở panel nến chính)
            if show_volume and "volume" in df_view.columns:
                fig.add_trace(go.Bar(
                    x=df_view["time"],
                    y=df_view["volume"],
                    marker_color=df_view["Vol_Color"],
                    opacity=0.35,
                    name="Khối lượng (Vol)"
                ), row=1, col=1)

            current_row = 2

            # 2. Subplot RSI (nếu bật)
            if has_rsi:
                fig.add_trace(go.Scatter(
                    x=df_view["time"], y=df_view["RSI"],
                    line=dict(color="#a855f7", width=1.5),
                    name="RSI(14)"
                ), row=current_row, col=1)
                
                # Dải quá mua / quá bán (70 / 30)
                fig.add_hline(y=70, line_dash="dash", line_color="#ef4444", line_width=1, row=current_row, col=1)
                fig.add_hline(y=30, line_dash="dash", line_color="#22c55e", line_width=1, row=current_row, col=1)
                fig.update_yaxes(title_text="RSI(14)", range=[0, 100], tickvals=[30, 50, 70], row=current_row, col=1)
                current_row += 1

            # 3. Subplot MACD (nếu bật)
            if has_macd:
                fig.add_trace(go.Scatter(
                    x=df_view["time"], y=df_view["MACD"],
                    line=dict(color="#38bdf8", width=1.5),
                    name="MACD"
                ), row=current_row, col=1)
                fig.add_trace(go.Scatter(
                    x=df_view["time"], y=df_view["Signal"],
                    line=dict(color="#f97316", width=1.5),
                    name="Signal"
                ), row=current_row, col=1)
                
                # Cột Histogram
                hist_colors = ["#22c55e" if h >= 0 else "#ef4444" for h in df_view["Hist"]]
                fig.add_trace(go.Bar(
                    x=df_view["time"], y=df_view["Hist"],
                    marker_color=hist_colors,
                    name="Histogram"
                ), row=current_row, col=1)
                fig.add_hline(y=0, line_dash="solid", line_color="#64748b", line_width=1, row=current_row, col=1)
                fig.update_yaxes(title_text="MACD", row=current_row, col=1)

            # Cấu hình Layout TradingView-grade
            fig.update_layout(
                title=f"<b>{selected_symbol}</b> • Biểu đồ Kỹ thuật Chuyên sâu (Lăn chuột để Phóng to / Thu nhỏ từng ngày)",
                yaxis_title="Giá (nghìn đồng)",
                xaxis_rangeslider_visible=False,
                template="plotly_dark",
                height=chart_height,
                hovermode="x unified",
                margin=dict(l=20, r=20, t=50, b=20),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
            )

            # Xóa khoảng cách ngày nghỉ (Thứ 7, CN) để nến liền mạch
            fig.update_xaxes(type="category")

            # Hiển thị biểu đồ với Scroll Zoom & Pan mượt mà
            st.plotly_chart(
                fig,
                use_container_width=True,
                config={
                    "scrollZoom": True,
                    "displayModeBar": True,
                    "modeBarButtonsToAdd": ["drawline", "drawopenpath", "eraseshape"],
                    "displaylogo": False
                }
            )
            st.caption("🔍 **Mẹo tương tác:** Đặt con trỏ chuột vào đồ thị và **lăn chuột giữa (scroll wheel)** để phóng to từng cây nến. Nhấp giữ chuột trái để kéo (pan) qua lại giữa các phiên.")
        else:
            st.error(f"Không thể tải biểu đồ cho mã {selected_symbol}")


# --- TAB 3: QUẢN LÝ DANH MỤC ---
with tab_portfolio:
    st.subheader("✏️ Chỉnh sửa Danh mục Trực tiếp")
    st.caption("Bạn có thể thêm dòng mới, sửa mã, khối lượng hoặc giá vốn trực tiếp trên bảng bên dưới rồi nhấn Lưu.")
    
    df_raw = pd.DataFrame(raw_portfolio)
    edited_df = st.data_editor(
        df_raw,
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "symbol": st.column_config.TextColumn("Mã CP", required=True),
            "volume": st.column_config.NumberColumn("Số lượng", min_value=1, step=10, required=True),
            "cost_price": st.column_config.NumberColumn("Giá vốn (k)", min_value=0.1, step=0.05, format="%.2f", required=True),
            "note": st.column_config.TextColumn("Ghi chú / Nhóm ngành"),
        }
    )

    if st.button("💾 Lưu thay đổi Danh mục", type="primary"):
        new_portfolio = edited_df.to_dict(orient="records")
        save_portfolio(new_portfolio)
        st.cache_data.clear()
        st.success("✅ Đã cập nhật danh mục thành công!")
        st.rerun()


# --- TAB 4: TRỢ LÝ PHÂN TÍCH AI ---
with tab_ai:
    st.subheader("🧠 Hỏi Chuyên gia Chiến lược AI (Gemini Pro)")
    st.caption("AI sẽ kết hợp trạng thái danh mục, giá vốn của bạn cùng dữ liệu nến và tin tức vĩ mô mới nhất.")

    custom_q = st.text_input("Câu hỏi bổ sung (tùy chọn):", placeholder="Ví dụ: P/E của SSI có đắt không? BSR chạm giá nào thì nên chốt lời?")
    
    if st.button("🚀 Phân tích Toàn diện Danh mục", type="primary", use_container_width=True):
        with st.spinner("Gemini Pro đang phân tích dữ liệu chuyên sâu..."):
            news = fetch_macro_news()
            analysis_result = generate_portfolio_analysis(df_eval, news, custom_question=custom_q)
            st.markdown(analysis_result)
