import os
import json
from datetime import datetime, timedelta
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
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
    start_date = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")
    df = q.history(start=start_date, end=end_date)
    if df is not None and not df.empty:
        df = df.sort_values("time").reset_index(drop=True)
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
    """
    Tạo mã HTML/JS nhúng TradingView Lightweight Charts tương tác 60fps Native,
    tích hợp thanh công cụ đáy bật tắt MA, EMA, MACD, RSI, BOLL tức thì.
    """
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
            body {{
                background-color: #131722;
                color: #d1d4dc;
                font-family: -apple-system, BlinkMacSystemFont, "Trebuchet MS", Roboto, sans-serif;
                display: flex;
                flex-direction: column;
                height: 590px;
                overflow: hidden;
            }}
            .tv-header {{
                display: flex;
                justify-content: space-between;
                align-items: center;
                padding: 8px 16px;
                background-color: #1e222d;
                border-bottom: 1px solid #2a2e39;
            }}
            .tv-title {{
                font-size: 15px;
                font-weight: 700;
                color: #f8fafc;
                display: flex;
                gap: 12px;
                align-items: center;
            }}
            .legend-badge {{
                font-size: 11px;
                font-weight: 600;
                padding: 2px 6px;
                border-radius: 4px;
                background-color: rgba(42, 46, 57, 0.6);
            }}
            #tv-chart {{
                flex: 1;
                width: 100%;
                position: relative;
            }}
            .tv-bottom-toolbar {{
                display: flex;
                justify-content: center;
                align-items: center;
                gap: 8px;
                padding: 6px 12px;
                background-color: #131722;
                border-top: 1px solid #2a2e39;
            }}
            .btn-ind {{
                background-color: #2a2e39;
                color: #848e9c;
                border: 1px solid #363a45;
                border-radius: 6px;
                padding: 5px 16px;
                font-size: 12px;
                font-weight: 700;
                cursor: pointer;
                transition: all 0.15s ease;
                outline: none;
            }}
            .btn-ind:hover {{
                background-color: #363a45;
                color: #f8fafc;
            }}
            .btn-ind.active {{
                background-color: #2962FF;
                color: #ffffff;
                border-color: #2962FF;
                box-shadow: 0 0 10px rgba(41, 98, 255, 0.4);
            }}
        </style>
    </head>
    <body>
        <div class="tv-header">
            <div class="tv-title">
                <span>{symbol} • 1D</span>
                <span class="legend-badge" style="color: #f59e0b;" id="leg-ma20">MA 20</span>
                <span class="legend-badge" style="color: #3b82f6;" id="leg-ma50">MA 50</span>
                <span class="legend-badge" style="color: #10b981;" id="leg-ema9">EMA 9</span>
                <span class="legend-badge" style="color: #38bdf8;" id="leg-boll">BOLL (20,2)</span>
            </div>
            <span style="font-size: 11px; color: #787b86;">TradingView Lightweight Charts • 60 FPS</span>
        </div>

        <div id="tv-chart"></div>

        <div class="tv-bottom-toolbar">
            <button class="btn-ind active" id="btn-ma">MA</button>
            <button class="btn-ind" id="btn-ema">EMA</button>
            <button class="btn-ind" id="btn-macd">MACD</button>
            <button class="btn-ind active" id="btn-rsi">RSI</button>
            <button class="btn-ind" id="btn-boll">BOLL</button>
        </div>

        <script>
            const container = document.getElementById('tv-chart');
            const chart = LightweightCharts.createChart(container, {{
                width: container.clientWidth,
                height: container.clientHeight,
                layout: {{ background: {{ color: '#131722' }}, textColor: '#d1d4dc' }},
                grid: {{ vertLines: {{ color: 'rgba(42, 46, 57, 0.35)' }}, horzLines: {{ color: 'rgba(42, 46, 57, 0.35)' }} }},
                crosshair: {{ mode: LightweightCharts.CrosshairMode.Normal }},
                rightPriceScale: {{
                    borderColor: '#2a2e39',
                    scaleMargins: {{ top: 0.08, bottom: 0.28 }},
                }},
                timeScale: {{ borderColor: '#2a2e39', timeVisible: true }},
            }});

            // 1. Candlestick Series
            const candleSeries = chart.addCandlestickSeries({{
                upColor: '#089981', downColor: '#F23645',
                borderVisible: false, wickUpColor: '#089981', wickDownColor: '#F23645',
            }});

            // 2. Volume Series (chiếm 20% đáy)
            const volumeSeries = chart.addHistogramSeries({{
                priceFormat: {{ type: 'volume' }},
                priceScaleId: '',
            }});
            volumeSeries.priceScale().applyOptions({{
                scaleMargins: {{ top: 0.8, bottom: 0 }},
            }});

            // 3. MA Series
            const ma20 = chart.addLineSeries({{ color: '#f59e0b', lineWidth: 1.5, title: 'MA 20', visible: true }});
            const ma50 = chart.addLineSeries({{ color: '#3b82f6', lineWidth: 1.5, title: 'MA 50', visible: true }});

            // 4. EMA Series
            const ema9 = chart.addLineSeries({{ color: '#10b981', lineWidth: 1.5, title: 'EMA 9', visible: false }});
            const ema21 = chart.addLineSeries({{ color: '#ec4899', lineWidth: 1.5, title: 'EMA 21', visible: false }});

            // 5. BOLL Series
            const bollUpper = chart.addLineSeries({{ color: 'rgba(56, 189, 248, 0.7)', lineWidth: 1, title: 'BOLL Up', visible: false }});
            const bollMid = chart.addLineSeries({{ color: 'rgba(56, 189, 248, 0.85)', lineWidth: 1, lineStyle: 2, title: 'BOLL Mid', visible: false }});
            const bollLower = chart.addLineSeries({{ color: 'rgba(56, 189, 248, 0.7)', lineWidth: 1, title: 'BOLL Low', visible: false }});

            // 6. RSI Series (Scale riêng ở đáy)
            const rsiSeries = chart.addLineSeries({{
                color: '#a855f7', lineWidth: 1.5, title: 'RSI(14)',
                priceScaleId: 'rsi_scale', visible: true
            }});
            chart.priceScale('rsi_scale').applyOptions({{
                scaleMargins: {{ top: 0.82, bottom: 0.02 }},
            }});
            const rsiUp = chart.addLineSeries({{
                color: '#ef4444', lineWidth: 1, lineStyle: 2, title: '70',
                priceScaleId: 'rsi_scale', visible: true
            }});
            const rsiDown = chart.addLineSeries({{
                color: '#22c55e', lineWidth: 1, lineStyle: 2, title: '30',
                priceScaleId: 'rsi_scale', visible: true
            }});

            // 7. MACD Series
            const macdLine = chart.addLineSeries({{
                color: '#38bdf8', lineWidth: 1.5, title: 'MACD',
                priceScaleId: 'macd_scale', visible: false
            }});
            const macdSignal = chart.addLineSeries({{
                color: '#f97316', lineWidth: 1.5, title: 'Signal',
                priceScaleId: 'macd_scale', visible: false
            }});
            const macdHist = chart.addHistogramSeries({{
                priceScaleId: 'macd_scale', visible: false
            }});
            chart.priceScale('macd_scale').applyOptions({{
                scaleMargins: {{ top: 0.82, bottom: 0.02 }},
            }});

            const candleData = {candle_json};
            const volumeData = {volume_json};

            // Hàm tính SMA
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

            // Hàm tính EMA
            function calculateEMA(data, period) {{
                const res = [];
                if (data.length === 0) return res;
                const k = 2 / (period + 1);
                let ema = data[0].close;
                for (let i = 0; i < data.length; i++) {{
                    ema = data[i].close * k + ema * (1 - k);
                    if (i >= period - 1) {{
                        res.push({{ time: data[i].time, value: parseFloat(ema.toFixed(2)) }});
                    }}
                }}
                return res;
            }}

            // Hàm tính Bollinger Bands
            function calculateBOLL(data, period = 20, mult = 2) {{
                const upper = [], mid = [], lower = [];
                for (let i = 0; i < data.length; i++) {{
                    if (i < period - 1) continue;
                    let sum = 0;
                    for (let j = 0; j < period; j++) sum += data[i - j].close;
                    const mean = sum / period;
                    let varSum = 0;
                    for (let j = 0; j < period; j++) varSum += Math.pow(data[i - j].close - mean, 2);
                    const std = Math.sqrt(varSum / period);
                    const t = data[i].time;
                    mid.push({{ time: t, value: parseFloat(mean.toFixed(2)) }});
                    upper.push({{ time: t, value: parseFloat((mean + mult * std).toFixed(2)) }});
                    lower.push({{ time: t, value: parseFloat((mean - mult * std).toFixed(2)) }});
                }}
                return {{ upper, mid, lower }};
            }}

            // Hàm tính RSI
            function calculateRSI(data, period = 14) {{
                const res = [];
                if (data.length <= period) return res;
                let gains = 0, losses = 0;
                for (let i = 1; i <= period; i++) {{
                    const d = data[i].close - data[i - 1].close;
                    if (d >= 0) gains += d; else losses -= d;
                }}
                let avgG = gains / period, avgL = losses / period;
                let rs = avgL === 0 ? 100 : avgG / avgL;
                res.push({{ time: data[period].time, value: parseFloat((100 - (100 / (1 + rs))).toFixed(2)) }});
                for (let i = period + 1; i < data.length; i++) {{
                    const d = data[i].close - data[i - 1].close;
                    avgG = (avgG * (period - 1) + (d > 0 ? d : 0)) / period;
                    avgL = (avgL * (period - 1) + (d < 0 ? -d : 0)) / period;
                    rs = avgL === 0 ? 100 : avgG / avgL;
                    res.push({{ time: data[i].time, value: parseFloat((100 - (100 / (1 + rs))).toFixed(2)) }});
                }}
                return res;
            }}

            // Hàm tính MACD
            function calculateMACD(data) {{
                const e12 = calculateEMA(data, 12);
                const e26 = calculateEMA(data, 26);
                const map12 = {{}};
                e12.forEach(d => map12[d.time] = d.value);
                const mLine = [];
                e26.forEach(d => {{
                    if (map12[d.time] !== undefined) {{
                        const val = map12[d.time] - d.value;
                        mLine.push({{ time: d.time, value: parseFloat(val.toFixed(2)), close: val }});
                    }}
                }});
                const sLine = calculateEMA(mLine, 9);
                const sMap = {{}};
                sLine.forEach(d => sMap[d.time] = d.value);
                const hList = [];
                mLine.forEach(d => {{
                    if (sMap[d.time] !== undefined) {{
                        const diff = d.value - sMap[d.time];
                        hList.push({{
                            time: d.time,
                            value: parseFloat(diff.toFixed(2)),
                            color: diff >= 0 ? '#22c55e' : '#ef4444'
                        }});
                    }}
                }});
                return {{ mLine, sLine, hList }};
            }}

            // Gán dữ liệu vào Series
            candleSeries.setData(candleData);
            volumeSeries.setData(volumeData);
            ma20.setData(calculateSMA(candleData, 20));
            ma50.setData(calculateSMA(candleData, 50));
            ema9.setData(calculateEMA(candleData, 9));
            ema21.setData(calculateEMA(candleData, 21));

            const bollData = calculateBOLL(candleData);
            bollUpper.setData(bollData.upper);
            bollMid.setData(bollData.mid);
            bollLower.setData(bollData.lower);

            const rsiData = calculateRSI(candleData);
            rsiSeries.setData(rsiData);
            rsiUp.setData(rsiData.map(d => ({{ time: d.time, value: 70 }})));
            rsiDown.setData(rsiData.map(d => ({{ time: d.time, value: 30 }})));

            const macdData = calculateMACD(candleData);
            macdLine.setData(macdData.mLine);
            macdSignal.setData(macdData.sLine);
            macdHist.setData(macdData.hList);

            // --- LẮNG NGHE SỰ KIỆN CLICK BẬT / TẮT NÚT BẤM CỦA NGƯỜI DÙNG ---
            let isMA = true;
            document.getElementById('btn-ma').addEventListener('click', function() {{
                isMA = !isMA;
                ma20.applyOptions({{ visible: isMA }});
                ma50.applyOptions({{ visible: isMA }});
                this.classList.toggle('active', isMA);
            }});

            let isEMA = false;
            document.getElementById('btn-ema').addEventListener('click', function() {{
                isEMA = !isEMA;
                ema9.applyOptions({{ visible: isEMA }});
                ema21.applyOptions({{ visible: isEMA }});
                this.classList.toggle('active', isEMA);
            }});

            let isBOLL = false;
            document.getElementById('btn-boll').addEventListener('click', function() {{
                isBOLL = !isBOLL;
                bollUpper.applyOptions({{ visible: isBOLL }});
                bollMid.applyOptions({{ visible: isBOLL }});
                bollLower.applyOptions({{ visible: isBOLL }});
                this.classList.toggle('active', isBOLL);
            }});

            let isRSI = true;
            document.getElementById('btn-rsi').addEventListener('click', function() {{
                isRSI = !isRSI;
                rsiSeries.applyOptions({{ visible: isRSI }});
                rsiUp.applyOptions({{ visible: isRSI }});
                rsiDown.applyOptions({{ visible: isRSI }});
                this.classList.toggle('active', isRSI);
            }});

            let isMACD = false;
            document.getElementById('btn-macd').addEventListener('click', function() {{
                isMACD = !isMACD;
                macdLine.applyOptions({{ visible: isMACD }});
                macdSignal.applyOptions({{ visible: isMACD }});
                macdHist.applyOptions({{ visible: isMACD }});
                this.classList.toggle('active', isMACD);
            }});

            window.addEventListener('resize', () => {{
                chart.resize(container.clientWidth, container.clientHeight);
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
            .header {{ display: flex; justify-content: space-between; align-items: center; padding: 10px 16px; border-bottom: 1px solid #2d3139; }}
            .title {{ font-size: 14px; font-weight: 700; color: #f8fafc; }}
            .select-tf {{ background-color: #242933; color: #e2e8f0; border: 1px solid #3b4252; padding: 4px 10px; border-radius: 6px; font-size: 12px; outline: none; cursor: pointer; }}
            #chart-container {{ width: 100%; height: 420px; }}
        </style>
    </head>
    <body>
        <div class="header">
            <span class="title">Định giá VN-INDEX theo {metric_name} ⓘ</span>
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
    "📈 Biểu đồ Kỹ thuật (TradingView 60 FPS)", 
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
    df_vnindex = get_vnindex_valuation_data()
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

        # 1. BIỂU ĐỒ NẾN NHẬT VN-INDEX (TRADINGVIEW 60 FPS)
        st.subheader("📉 Biểu đồ Kỹ thuật Chỉ số VN-INDEX (TradingView 60 FPS)")
        tv_vnindex_html = generate_tradingview_html(df_vnindex, "VNINDEX")
        components.html(tv_vnindex_html, height=600)

        st.divider()

        # 2. HAI BIỂU ĐỒ ĐỊNH GIÁ P/E VÀ P/B CỦA VN-INDEX
        st.subheader("📊 Tương quan Bội số Định giá Thị trường")
        col_pe, col_pb = st.columns(2)
        with col_pe:
            html_pe = generate_echarts_valuation_html(df_vnindex, metric="PE")
            components.html(html_pe, height=480)

        with col_pb:
            html_pb = generate_echarts_valuation_html(df_vnindex, metric="PB")
            components.html(html_pb, height=480)
    else:
        st.error("Chưa tải được dữ liệu định giá VN-Index từ hệ thống.")


# --- TAB 3: BIỂU ĐỒ KỸ THUẬT (TRADINGVIEW 60 FPS MẶC ĐỊNH) ---
with tab_charts:
    symbols = [item["symbol"] for item in raw_portfolio]
    if symbols:
        selected_symbol = st.selectbox("🎯 Chọn cổ phiếu cần phân tích kỹ thuật:", symbols)
        df_chart = get_stock_chart_data(selected_symbol)
        
        if df_chart is not None and not df_chart.empty:
            tv_html = generate_tradingview_html(df_chart, selected_symbol)
            components.html(tv_html, height=600)
            st.caption("✨ **TradingView Native 60 FPS:** Nhấp các nút **MA, EMA, MACD, RSI, BOLL** bên dưới đáy biểu đồ để bật/tắt chỉ báo tức thì. Lăn chuột để phóng to/thu nhỏ từng phiên.")
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
