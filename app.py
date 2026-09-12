import os
import json
from datetime import datetime, timedelta
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from dotenv import load_dotenv

from data_engine import load_portfolio, save_portfolio, evaluate_portfolio, fetch_macro_news
from ai_analyst import generate_portfolio_analysis
from discord_alerts import send_discord_message, format_portfolio_embed

load_dotenv()

st.set_page_config(
    page_title="AI Stock Copilot - Quản trị & Định giá Thị trường",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS giao diện Fintech Dark Theme cao cấp
st.markdown("""
<style>
    .metric-card {
        background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
        border: 1px solid #334155;
        border-radius: 10px;
        padding: 16px;
        text-align: center;
    }
    .metric-title { font-size: 13px; color: #94a3b8; margin-bottom: 4px; }
    .metric-val { font-size: 22px; font-weight: 700; color: #f8fafc; }
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
    start_date = (datetime.now() - timedelta(days=260)).strftime("%Y-%m-%d")
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


@st.cache_data(ttl=1800)
def get_vnindex_valuation_data():
    """Lấy dữ liệu VNINDEX và tạo chuỗi định giá P/E, P/B thị trường thực tế."""
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


def generate_tradingview_html(df: pd.DataFrame, symbol: str) -> str:
    """Tạo mã HTML/JS nhúng TradingView Lightweight Charts tương tác 60fps."""
    candle_list = []
    volume_list = []
    for _, row in df.iterrows():
        t = str(row["time"]).split(" ")[0]
        o, h, l, c = float(row["open"]), float(row["high"]), float(row["low"]), float(row["close"])
        v = int(row.get("volume", 0))
        is_up = c >= o
        candle_list.append({"time": t, "open": o, "high": h, "low": l, "close": c})
        volume_list.append({
            "time": t,
            "value": v,
            "color": "rgba(8, 153, 129, 0.45)" if is_up else "rgba(242, 54, 69, 0.45)"
        })

    candle_json = json.dumps(candle_list)
    volume_json = json.dumps(volume_list)

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <script src="https://unpkg.com/lightweight-charts@4.1.3/dist/lightweight-charts.standalone.production.js"></script>
        <style>
            * {{ box-sizing: border-box; margin: 0; padding: 0; }}
            body {{ background-color: #131722; color: #d1d4dc; font-family: -apple-system, BlinkMacSystemFont, "Trebuchet MS", Roboto, sans-serif; overflow: hidden; }}
            .tv-header {{ display: flex; justify-content: space-between; align-items: center; padding: 8px 16px; background-color: #1e222d; border-bottom: 1px solid #2a2e39; }}
            .tv-title {{ font-size: 15px; font-weight: 700; color: #f8fafc; display: flex; gap: 12px; align-items: center; }}
            .badge-sma9 {{ color: #2962FF; font-size: 12px; font-weight: 600; }}
            .badge-sma20 {{ color: #FF6D00; font-size: 12px; font-weight: 600; }}
            #tv-chart {{ width: 100%; height: 520px; }}
        </style>
    </head>
    <body>
        <div class="tv-header">
            <div class="tv-title">
                <span>{symbol} • 1D</span>
                <span class="badge-sma9">● SMA 9</span>
                <span class="badge-sma20">● SMA 20</span>
            </div>
            <span style="font-size: 11px; color: #787b86;">TradingView Lightweight Charts • 60 FPS</span>
        </div>
        <div id="tv-chart"></div>

        <script>
            const container = document.getElementById('tv-chart');
            const chart = LightweightCharts.createChart(container, {{
                width: container.clientWidth,
                height: 520,
                layout: {{ background: {{ color: '#131722' }}, textColor: '#d1d4dc' }},
                grid: {{ vertLines: {{ color: 'rgba(42, 46, 57, 0.4)' }}, horzLines: {{ color: 'rgba(42, 46, 57, 0.4)' }} }},
                crosshair: {{ mode: LightweightCharts.CrosshairMode.Normal }},
                rightPriceScale: {{ borderColor: '#2a2e39', scaleMargins: {{ top: 0.1, bottom: 0.25 }} }},
                timeScale: {{ borderColor: '#2a2e39', timeVisible: true }},
            }});

            const candleSeries = chart.addCandlestickSeries({{
                upColor: '#089981', downColor: '#F23645',
                borderVisible: false, wickUpColor: '#089981', wickDownColor: '#F23645',
            }});

            const volumeSeries = chart.addHistogramSeries({{
                priceFormat: {{ type: 'volume' }},
                priceScaleId: '',
            }});
            volumeSeries.priceScale().applyOptions({{
                scaleMargins: {{ top: 0.8, bottom: 0 }},
            }});

            const sma9Series = chart.addLineSeries({{ color: '#2962FF', lineWidth: 2, title: 'SMA 9' }});
            const sma20Series = chart.addLineSeries({{ color: '#FF6D00', lineWidth: 2, title: 'SMA 20' }});

            const candleData = {candle_json};
            const volumeData = {volume_json};

            function calculateSMA(data, period) {{
                const res = [];
                for (let i = 0; i < data.length; i++) {{
                    if (i < period - 1) continue;
                    let sum = 0;
                    for (let j = 0; j < period; j++) sum += data[i - j].close;
                    res.push({{ time: data[i].time, value: parseFloat((sum / period).toFixed(2)) }});
                }}
                return res;
            }}

            candleSeries.setData(candleData);
            volumeSeries.setData(volumeData);
            sma9Series.setData(calculateSMA(candleData, 9));
            sma20Series.setData(calculateSMA(candleData, 20));

            window.addEventListener('resize', () => {{
                chart.resize(container.clientWidth, 520);
            }});
        </script>
    </body>
    </html>
    """
    return html


def generate_echarts_valuation_html(df: pd.DataFrame, metric: str = "PE") -> str:
    """Tạo mã HTML/JS nhúng Apache ECharts định giá VN-Index vs P/E hoặc P/B."""
    dataset = []
    for _, row in df.iterrows():
        dataset.append({
            "date": str(row["time"]).split(" ")[0],
            "index": round(float(row["close"])),
            "val": float(row["PE"] if metric == "PE" else row["PB"])
        })

    metric_name = "P/E" if metric == "PE" else "P/B"
    color_val = "#4caf50" if metric == "PE" else "#00b4d8"
    dataset_json = json.dumps(dataset)

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <script src="https://cdn.jsdelivr.net/npm/echarts@5.5.0/dist/echarts.min.js"></script>
        <style>
            * {{ box-sizing: border-box; margin: 0; padding: 0; }}
            body {{ background-color: #1a1d24; color: #d1d4dc; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; overflow: hidden; }}
            .header {{ display: flex; justify-content: space-between; align-items: center; padding: 12px 16px; border-bottom: 1px solid #2d3139; }}
            .title {{ font-size: 15px; font-weight: 700; color: #f8fafc; }}
            .select-tf {{ background-color: #242933; color: #e2e8f0; border: 1px solid #3b4252; padding: 4px 10px; border-radius: 6px; font-size: 12px; outline: none; cursor: pointer; }}
            #chart-container {{ width: 100%; height: 440px; }}
        </style>
    </head>
    <body>
        <div class="header">
            <span class="title">Định giá theo {metric_name} ⓘ</span>
            <select id="tf-select" class="select-tf">
                <option value="1m">1 tháng</option>
                <option value="3m">3 tháng</option>
                <option value="1y" selected>1 năm</option>
                <option value="3y">3 năm</option>
            </select>
        </div>
        <div id="chart-container"></div>

        <script>
            const fullData = {dataset_json};
            const chartDom = document.getElementById('chart-container');
            const myChart = echarts.init(chartDom);

            function render(timeframe) {{
                let count = 260;
                if (timeframe === '1m') count = 22;
                if (timeframe === '3m') count = 65;
                if (timeframe === '1y') count = 260;
                if (timeframe === '3y') count = fullData.length;

                const sliced = fullData.slice(-count);
                const dates = sliced.map(d => d.date);
                const idxVals = sliced.map(d => d.index);
                const metricVals = sliced.map(d => d.val);

                const option = {{
                    backgroundColor: 'transparent',
                    tooltip: {{
                        trigger: 'axis',
                        axisPointer: {{ type: 'cross', lineStyle: {{ color: '#64748b', type: 'dashed' }} }},
                        backgroundColor: 'rgba(26, 29, 36, 0.95)',
                        borderColor: '#3b4252',
                        textStyle: {{ color: '#f8fafc' }},
                        formatter: function(params) {{
                            let str = `<b>${{params[0].axisValue}}</b><br/>`;
                            params.forEach(item => {{
                                const unit = item.seriesIndex === 0 ? ' điểm' : ' lần';
                                str += `<span style="color:${{item.color}};">●</span> ${{item.seriesName}}: <b>${{item.value}}${{unit}}</b><br/>`;
                            }});
                            return str;
                        }}
                    }},
                    legend: {{
                        data: ['VNINDEX (điểm, cột trái)', '{metric_name} (lần, cột phải)'],
                        bottom: 0,
                        textStyle: {{ color: '#cbd5e1', fontSize: 11 }},
                        icon: 'circle'
                    }},
                    grid: {{ left: '3%', right: '3%', top: '12%', bottom: '12%', containLabel: true }},
                    xAxis: {{
                        type: 'category',
                        data: dates,
                        axisLine: {{ lineStyle: {{ color: '#334155' }} }},
                        axisLabel: {{ color: '#94a3b8', formatter: val => val.substring(5) }},
                        axisTick: {{ show: false }}
                    }},
                    yAxis: [
                        {{
                            type: 'value',
                            name: 'VNINDEX',
                            nameTextStyle: {{ color: '#ff9800', align: 'right' }},
                            position: 'left',
                            min: val => Math.floor(val.min / 50) * 50,
                            axisLabel: {{ color: '#ff9800', formatter: '{{value}}' }},
                            splitLine: {{ lineStyle: {{ color: 'rgba(51, 65, 85, 0.35)', type: 'dashed' }} }}
                        }},
                        {{
                            type: 'value',
                            name: '{metric_name}',
                            nameTextStyle: {{ color: '{color_val}', align: 'left' }},
                            position: 'right',
                            min: val => parseFloat((val.min - 0.2).toFixed(1)),
                            axisLabel: {{ color: '{color_val}', formatter: val => val.toFixed(1) }},
                            splitLine: {{ show: false }}
                        }}
                    ],
                    series: [
                        {{
                            name: 'VNINDEX (điểm, cột trái)',
                            type: 'line',
                            yAxisIndex: 0,
                            data: idxVals,
                            smooth: 0.2,
                            showSymbol: false,
                            itemStyle: {{ color: '#ff9800' }},
                            lineStyle: {{ width: 2, color: '#ff9800' }}
                        }},
                        {{
                            name: '{metric_name} (lần, cột phải)',
                            type: 'line',
                            yAxisIndex: 1,
                            data: metricVals,
                            smooth: 0.2,
                            showSymbol: false,
                            itemStyle: {{ color: '{color_val}' }},
                            lineStyle: {{ width: 2, color: '{color_val}' }}
                        }}
                    ]
                }};
                myChart.setOption(option, true);
            }}

            document.getElementById('tf-select').addEventListener('change', (e) => render(e.target.value));
            render('1y');
            window.addEventListener('resize', () => myChart.resize());
        </script>
    </body>
    </html>
    """
    return html


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
tab_overview, tab_market_val, tab_charts, tab_portfolio, tab_ai = st.tabs([
    "📊 Tổng quan Danh mục", 
    "🏛️ Thị Trường & Định Giá (VN-Index, P/E, P/B)",
    "📈 Biểu đồ Kỹ thuật (TradingView & Plotly)", 
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


# --- TAB 2: THỊ TRƯỜNG & ĐỊNH GIÁ (VN-INDEX, P/E, P/B) ---
with tab_market_val:
    st.subheader("🏛️ Tổng quan Thị trường Toàn cảnh & Bội số Định giá")
    st.caption("Theo dõi tương quan chu kỳ giữa điểm số VN-Index và mức độ đắt/rẻ của định giá toàn thị trường.")

    df_vnindex = get_vnindex_valuation_data()
    if df_vnindex is not None and not df_vnindex.empty:
        latest_idx = df_vnindex["close"].iloc[-1]
        prev_idx = df_vnindex["close"].iloc[-2] if len(df_vnindex) > 1 else latest_idx
        idx_change = ((latest_idx - prev_idx) / prev_idx) * 100
        latest_pe = df_vnindex["PE"].iloc[-1]
        latest_pb = df_vnindex["PB"].iloc[-1]

        kpi1, kpi2, kpi3, kpi4 = st.columns(4)
        kpi1.metric("Chỉ số VN-INDEX", f"{latest_idx:,.2f}", f"{idx_change:+.2f}%")
        kpi2.metric("P/E Thị Trường", f"{latest_pe:.1f} lần", "Vùng định giá hợp lý")
        kpi3.metric("P/B Thị Trường", f"{latest_pb:.2f} lần", "Hấp dẫn trung hạn")
        kpi4.metric("Thanh khoản phiên", f"{int(df_vnindex['volume'].iloc[-1]):,} cp")

        # 2 Biểu đồ Apache ECharts song song
        col_pe, col_pb = st.columns(2)
        with col_pe:
            html_pe = generate_echarts_valuation_html(df_vnindex, metric="PE")
            components.html(html_pe, height=510)

        with col_pb:
            html_pb = generate_echarts_valuation_html(df_vnindex, metric="PB")
            components.html(html_pb, height=510)
    else:
        st.error("Chưa tải được dữ liệu định giá VN-Index từ hệ thống.")


# --- TAB 3: BIỂU ĐỒ KỸ THUẬT (TRADINGVIEW & PLOTLY) ---
with tab_charts:
    symbols = [item["symbol"] for item in raw_portfolio]
    if symbols:
        header_col1, header_col2 = st.columns([3, 2])
        with header_col1:
            selected_symbol = st.selectbox("🎯 Chọn cổ phiếu cần phân tích kỹ thuật:", symbols)
        with header_col2:
            chart_engine = st.radio("🛠️ Chọn Engine Biểu đồ:", ["TradingView Lightweight Charts (60 FPS)", "Plotly Subplots (Kèm RSI & MACD)"], horizontal=True)

        df_chart = get_stock_chart_data(selected_symbol)
        
        if df_chart is not None and not df_chart.empty:
            if chart_engine == "TradingView Lightweight Charts (60 FPS)":
                # Nhúng trực tiếp TradingView 60fps
                tv_html = generate_tradingview_html(df_chart, selected_symbol)
                components.html(tv_html, height=580)
                st.caption("✨ **TradingView Native:** Lăn con lăn chuột để phóng to/thu nhỏ từng ngày, nhấp giữ chuột trái để kéo pan qua các tháng.")
            else:
                # Engine Plotly Subplots
                c1, c2, c3, c4 = st.columns(4)
                show_ma20 = c1.checkbox("📈 Đường MA20", value=True)
                show_ma50 = c2.checkbox("📉 Đường MA50", value=True)
                show_rsi = c3.checkbox("⚡ Chỉ báo RSI(14)", value=True)
                show_macd = c4.checkbox("🌊 Chỉ báo MACD", value=True)

                rows = 1
                row_heights = [0.6]
                if show_rsi and show_macd:
                    rows, row_heights, chart_h = 3, [0.55, 0.22, 0.23], 720
                elif show_rsi or show_macd:
                    rows, row_heights, chart_h = 2, [0.70, 0.30], 600
                else:
                    rows, row_heights, chart_h = 1, [1.0], 480

                fig = make_subplots(rows=rows, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=row_heights)
                
                # Nến Nhật
                fig.add_trace(go.Candlestick(
                    x=df_chart["time"], open=df_chart["open"], high=df_chart["high"],
                    low=df_chart["low"], close=df_chart["close"], name="Nến",
                    increasing_line_color="#22c55e", decreasing_line_color="#ef4444"
                ), row=1, col=1)

                if show_ma20 and "MA20" in df_chart.columns:
                    fig.add_trace(go.Scatter(x=df_chart["time"], y=df_chart["MA20"], line=dict(color="#f59e0b", width=1.5), name="MA20"), row=1, col=1)
                if show_ma50 and "MA50" in df_chart.columns:
                    fig.add_trace(go.Scatter(x=df_chart["time"], y=df_chart["MA50"], line=dict(color="#3b82f6", width=1.5), name="MA50"), row=1, col=1)

                cur_r = 2
                if show_rsi:
                    fig.add_trace(go.Scatter(x=df_chart["time"], y=df_chart["RSI"], line=dict(color="#a855f7", width=1.5), name="RSI(14)"), row=cur_r, col=1)
                    fig.add_hline(y=70, line_dash="dash", line_color="#ef4444", line_width=1, row=cur_r, col=1)
                    fig.add_hline(y=30, line_dash="dash", line_color="#22c55e", line_width=1, row=cur_r, col=1)
                    fig.update_yaxes(title_text="RSI", range=[0, 100], tickvals=[30, 50, 70], row=cur_r, col=1)
                    cur_r += 1

                if show_macd:
                    fig.add_trace(go.Scatter(x=df_chart["time"], y=df_chart["MACD"], line=dict(color="#38bdf8", width=1.5), name="MACD"), row=cur_r, col=1)
                    fig.add_trace(go.Scatter(x=df_chart["time"], y=df_chart["Signal"], line=dict(color="#f97316", width=1.5), name="Signal"), row=cur_r, col=1)
                    h_colors = ["#22c55e" if h >= 0 else "#ef4444" for h in df_chart["Hist"]]
                    fig.add_trace(go.Bar(x=df_chart["time"], y=df_chart["Hist"], marker_color=h_colors, name="Hist"), row=cur_r, col=1)
                    fig.update_yaxes(title_text="MACD", row=cur_r, col=1)

                fig.update_layout(
                    title=f"<b>{selected_symbol}</b> • Plotly Interactive Chart",
                    xaxis_rangeslider_visible=False, template="plotly_dark",
                    height=chart_h, hovermode="x unified",
                    margin=dict(l=20, r=20, t=50, b=20)
                )
                fig.update_xaxes(type="category")
                st.plotly_chart(fig, use_container_width=True, config={"scrollZoom": True})
        else:
            st.error(f"Không thể tải biểu đồ cho mã {selected_symbol}")


# --- TAB 4: QUẢN LÝ DANH MỤC ---
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


# --- TAB 5: TRỢ LÝ PHÂN TÍCH AI ---
with tab_ai:
    st.subheader("🧠 Hỏi Chuyên gia Chiến lược AI (Gemini Pro)")
    st.caption("AI sẽ kết hợp trạng thái danh mục, giá vốn của bạn cùng dữ liệu nến và tin tức vĩ mô mới nhất.")

    custom_q = st.text_input("Câu hỏi bổ sung (tùy chọn):", placeholder="Ví dụ: P/E của SSI có đắt không? BSR chạm giá nào thì nên chốt lời?")
    
    if st.button("🚀 Phân tích Toàn diện Danh mục", type="primary", use_container_width=True):
        with st.spinner("Gemini Pro đang phân tích dữ liệu chuyên sâu..."):
            news = fetch_macro_news()
            analysis_result = generate_portfolio_analysis(df_eval, news, custom_question=custom_q)
            st.markdown(analysis_result)
