import json
import pandas as pd

def generate_tradingview_html(df: pd.DataFrame, symbol: str) -> str:
    """
    Tạo mã HTML/JS nhúng TradingView Lightweight Charts tương tác chuẩn TradingView Pro:
    - Bố cục Multi-Pane riêng biệt xếp chồng với chiều cao pixel cố định:
      + Pane 1: Nến Candlestick + MA (20, 50) + EMA (9, 21) + BOLL (20, 2)
      + Pane 2: Đồ thị Khối lượng Volume tách riêng ở dưới + SMA 20 của Khối lượng
      + Pane 3 (Sub-panel): MACD (Line, Signal, Histogram)
      + Pane 4 (Sub-panel): RSI (14) + đường mốc 70/30
    - Mỗi pane có header riêng hiển thị chính xác số liệu realtime khi trỏ chuột vào bất kỳ ngày nào.
    - Nến tự động căng đều toàn màn hình (barSpacing 9, fixLeft/RightEdge), triệt tiêu lỗi co cụm góc phải.
    - Lọc khung thời gian: 1 ngày, 1 tuần, 1 tháng.
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
            "color": "rgba(8, 153, 129, 0.55)" if is_up else "rgba(242, 54, 69, 0.55)"
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
                min-height: 100vh;
                overflow-x: hidden;
            }}

            /* 1. THANH HEADER CHÍNH */
            .main-header {{
                display: flex;
                flex-direction: column;
                gap: 4px;
                padding: 8px 16px;
                background-color: #1e222d;
                border-bottom: 1px solid #2a2e39;
                flex-shrink: 0;
            }}
            .main-title-row {{
                display: flex;
                align-items: center;
                gap: 12px;
                flex-wrap: wrap;
            }}
            .symbol-title {{
                font-size: 16px;
                font-weight: 700;
                color: #f8fafc;
            }}

            /* DROPDOWN CHỌN KHUNG THỜI GIAN */
            .tf-dropdown {{
                position: relative;
                display: inline-block;
            }}
            .tf-btn {{
                background-color: #2a2e39;
                color: #f8fafc;
                border: 1px solid #363a45;
                border-radius: 4px;
                padding: 3px 10px;
                font-size: 12px;
                font-weight: 600;
                cursor: pointer;
                display: flex;
                align-items: center;
                gap: 5px;
                transition: all 0.15s ease;
            }}
            .tf-btn:hover {{
                background-color: #363a45;
                border-color: #4a5060;
            }}
            .tf-menu {{
                display: none;
                position: absolute;
                top: calc(100% + 4px);
                left: 0;
                background-color: #1e222d;
                border: 1px solid #2a2e39;
                border-radius: 6px;
                width: 120px;
                box-shadow: 0 10px 25px rgba(0, 0, 0, 0.75);
                padding: 4px 0;
                z-index: 1000;
            }}
            .tf-menu.show {{
                display: block;
            }}
            .tf-item {{
                padding: 6px 14px;
                font-size: 12px;
                font-weight: 500;
                color: #d1d4dc;
                cursor: pointer;
            }}
            .tf-item:hover {{
                background-color: #2a2e39;
                color: #ffffff;
            }}
            .tf-item.active {{
                background-color: #2962FF !important;
                color: #ffffff !important;
                font-weight: 600;
            }}

            /* DÒNG THÔNG SỐ NẾN OHLCV */
            .ohlc-text {{
                display: flex;
                align-items: center;
                gap: 8px;
                font-size: 12px;
                font-family: -apple-system, BlinkMacSystemFont, "Trebuchet MS", Roboto, monospace;
                color: #94a3b8;
            }}
            .ohlc-text b {{
                font-weight: 600;
                color: #f8fafc;
            }}
            .ind-main-text {{
                display: flex;
                align-items: center;
                gap: 12px;
                font-size: 11px;
                font-family: -apple-system, BlinkMacSystemFont, "Trebuchet MS", Roboto, monospace;
            }}
            .badge-val {{
                display: inline-flex;
                align-items: center;
                gap: 4px;
            }}
            .badge-val b {{
                font-weight: 700;
            }}

            /* 2. CÁC PANE ĐỒ THỊ RIÊNG BIỆT (MULTI-PANE LAYOUT) */
            .panes-wrapper {{
                flex: 1;
                display: flex;
                flex-direction: column;
                width: 100%;
                background-color: #131722;
            }}
            .pane-box {{
                width: 100%;
                position: relative;
                display: flex;
                flex-direction: column;
                background-color: #131722;
            }}
            .pane-header-bar {{
                height: 24px;
                padding: 2px 14px;
                background-color: #171b26;
                display: flex;
                align-items: center;
                gap: 12px;
                font-size: 11px;
                font-family: -apple-system, BlinkMacSystemFont, "Trebuchet MS", Roboto, monospace;
                border-bottom: 1px solid rgba(42, 46, 57, 0.4);
                color: #cbd5e1;
                flex-shrink: 0;
                z-index: 10;
            }}
            .pane-header-bar b {{
                font-weight: 700;
            }}
            .pane-chart-container {{
                width: 100%;
                position: relative;
            }}
            .pane-divider {{
                height: 2px;
                background-color: #2a2e39;
                flex-shrink: 0;
            }}

            /* 3. TOOLBAR ĐÁY BẬT TẮT CHỈ BÁO */
            .tv-bottom-toolbar {{
                display: flex;
                justify-content: center;
                align-items: center;
                gap: 8px;
                padding: 8px 12px;
                background-color: #131722;
                border-top: 1px solid #2a2e39;
                flex-shrink: 0;
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
        <!-- 1. MAIN HEADER -->
        <div class="main-header">
            <div class="main-title-row">
                <span class="symbol-title">{symbol}</span>
                
                <div class="tf-dropdown">
                    <button class="tf-btn" id="tf-btn">
                        <span id="tf-label">1 ngày</span>
                        <svg width="8" height="6" viewBox="0 0 8 6" fill="none">
                            <path d="M1 1.5L4 4.5L7 1.5" stroke="#94a3b8" stroke-width="1.5" stroke-linecap="round"/>
                        </svg>
                    </button>
                    <div class="tf-menu" id="tf-menu">
                        <div class="tf-item active" data-tf="1D">1 ngày</div>
                        <div class="tf-item" data-tf="1W">1 tuần</div>
                        <div class="tf-item" data-tf="1M">1 tháng</div>
                    </div>
                </div>

                <div class="ohlc-text" id="ohlc-text">
                    <span>O <b id="val-open">--</b></span>
                    <span>H <b id="val-high">--</b></span>
                    <span>L <b id="val-low">--</b></span>
                    <span>C <b id="val-close">--</b></span>
                    <span id="val-change" style="font-weight:700;">--</span>
                </div>
            </div>

            <div class="ind-main-text" id="ind-main-text">
                <span class="badge-val" id="badge-ma20" style="color: #f59e0b;">MA 20: <b>--</b></span>
                <span class="badge-val" id="badge-ma50" style="color: #3b82f6;">MA 50: <b>--</b></span>
                <span class="badge-val" id="badge-ema9" style="color: #10b981; display: none;">EMA 9: <b>--</b></span>
                <span class="badge-val" id="badge-ema21" style="color: #ec4899; display: none;">EMA 21: <b>--</b></span>
                <span class="badge-val" id="badge-boll" style="color: #38bdf8; display: none;">BOLL(20,2): Up <b>--</b> Mid <b>--</b> Low <b>--</b></span>
            </div>
        </div>

        <!-- 2. MULTI-PANE CHARTS WRAPPER -->
        <div class="panes-wrapper" id="panes-wrapper">
            <!-- PANE 1: BIỂU ĐỒ NẾN CHÍNH (Chiếm 330px) -->
            <div class="pane-box" id="pane-main">
                <div class="pane-chart-container" id="container-main" style="height: 330px;"></div>
            </div>

            <div class="pane-divider"></div>

            <!-- PANE 2: ĐỒ THỊ KHỐI LƯỢNG VOLUME TÁCH RIÊNG Ở DƯỚI (Chiếm 115px) -->
            <div class="pane-box" id="pane-vol">
                <div class="pane-header-bar">
                    <span>Khối lượng <span style="color:#787b86;">20</span> SMA <span style="color:#787b86;">20</span></span>
                    <span style="color: #38bdf8;" id="hdr-vol-val">Vol: <b>--</b></span>
                    <span style="color: #f59e0b;" id="hdr-vol-sma">SMA 20: <b>--</b></span>
                </div>
                <div class="pane-chart-container" id="container-vol" style="height: 90px;"></div>
            </div>

            <!-- PANE 3: ĐỒ THỊ MACD TÁCH RIÊNG (Chiếm 130px - Khi bật MACD) -->
            <div class="pane-divider" id="sep-macd" style="display: none;"></div>
            <div class="pane-box" id="pane-macd" style="display: none;">
                <div class="pane-header-bar">
                    <span style="color:#f8fafc; font-weight:700;">MACD</span>
                    <span style="color:#787b86;">12 26 close 9</span>
                    <span style="color: #38bdf8;" id="hdr-macd-line">MACD: <b>--</b></span>
                    <span style="color: #f97316;" id="hdr-macd-sig">Signal: <b>--</b></span>
                    <span id="hdr-macd-hist">Hist: <b>--</b></span>
                </div>
                <div class="pane-chart-container" id="container-macd" style="height: 105px;"></div>
            </div>

            <!-- PANE 4: ĐỒ THỊ RSI TÁCH RIÊNG (Chiếm 120px - Khi bật RSI) -->
            <div class="pane-divider" id="sep-rsi"></div>
            <div class="pane-box" id="pane-rsi">
                <div class="pane-header-bar">
                    <span style="color:#f8fafc; font-weight:700;">RSI</span>
                    <span style="color:#787b86;">14</span>
                    <span style="color: #a855f7;" id="hdr-rsi-val">RSI: <b>--</b></span>
                </div>
                <div class="pane-chart-container" id="container-rsi" style="height: 95px;"></div>
            </div>
        </div>

        <!-- 3. TOOLBAR ĐÁY BẬT TẮT CHỈ BÁO -->
        <div class="tv-bottom-toolbar">
            <button class="btn-ind active" id="btn-ma">MA</button>
            <button class="btn-ind" id="btn-ema">EMA</button>
            <button class="btn-ind" id="btn-macd">MACD</button>
            <button class="btn-ind active" id="btn-rsi">RSI</button>
            <button class="btn-ind" id="btn-boll">BOLL</button>
        </div>

        <script>
            const cMain = document.getElementById('container-main');
            const cVol = document.getElementById('container-vol');
            const cMacd = document.getElementById('container-macd');
            const cRsi = document.getElementById('container-rsi');

            const paneMacd = document.getElementById('pane-macd');
            const sepMacd = document.getElementById('sep-macd');
            const paneRsi = document.getElementById('pane-rsi');
            const sepRsi = document.getElementById('sep-rsi');

            // CẤU HÌNH TIME SCALE: Chống co cụm nến (fixRightEdge + barSpacing 9) và loại bỏ 00:00:00
            const makeTimeScale = (showTimeAxis) => ({{
                borderColor: '#2a2e39',
                timeVisible: false,
                secondsVisible: false,
                visible: showTimeAxis,
                fixLeftEdge: true,
                fixRightEdge: true,
                minBarSpacing: 4,
                barSpacing: 9,
                rightOffset: 6,
            }});

            const makeOptions = (showTimeAxis) => ({{
                layout: {{ background: {{ color: '#131722' }}, textColor: '#d1d4dc' }},
                grid: {{ vertLines: {{ color: 'rgba(42, 46, 57, 0.25)' }}, horzLines: {{ color: 'rgba(42, 46, 57, 0.25)' }} }},
                crosshair: {{ mode: LightweightCharts.CrosshairMode.Normal }},
                rightPriceScale: {{
                    borderColor: '#2a2e39',
                    scaleMargins: {{ top: 0.08, bottom: 0.08 }},
                }},
                timeScale: makeTimeScale(showTimeAxis),
                localization: {{ dateFormat: 'yyyy-MM-dd' }},
            }});

            // 1. Chart Nến Chính
            const chartMain = LightweightCharts.createChart(cMain, makeOptions(false));
            const candleSeries = chartMain.addCandlestickSeries({{
                upColor: '#089981', downColor: '#F23645',
                borderVisible: false, wickUpColor: '#089981', wickDownColor: '#F23645',
            }});
            const ma20 = chartMain.addLineSeries({{ color: '#f59e0b', lineWidth: 1.5, title: 'MA 20', visible: true }});
            const ma50 = chartMain.addLineSeries({{ color: '#3b82f6', lineWidth: 1.5, title: 'MA 50', visible: true }});
            const ema9 = chartMain.addLineSeries({{ color: '#10b981', lineWidth: 1.5, title: 'EMA 9', visible: false }});
            const ema21 = chartMain.addLineSeries({{ color: '#ec4899', lineWidth: 1.5, title: 'EMA 21', visible: false }});
            const bollUpper = chartMain.addLineSeries({{ color: 'rgba(56, 189, 248, 0.7)', lineWidth: 1, title: 'BOLL Up', visible: false }});
            const bollMid = chartMain.addLineSeries({{ color: 'rgba(56, 189, 248, 0.85)', lineWidth: 1, lineStyle: 2, title: 'BOLL Mid', visible: false }});
            const bollLower = chartMain.addLineSeries({{ color: 'rgba(56, 189, 248, 0.7)', lineWidth: 1, title: 'BOLL Low', visible: false }});

            // 2. Chart Khối Lượng Tách Riêng Ở Dưới
            const chartVol = LightweightCharts.createChart(cVol, makeOptions(false));
            const volumeSeries = chartVol.addHistogramSeries({{ priceFormat: {{ type: 'volume' }} }});
            const volSmaSeries = chartVol.addLineSeries({{ color: '#f59e0b', lineWidth: 1.5, title: 'SMA 20' }});

            // 3. Chart MACD Tách Riêng
            const chartMacd = LightweightCharts.createChart(cMacd, makeOptions(false));
            const macdLine = chartMacd.addLineSeries({{ color: '#38bdf8', lineWidth: 1.5 }});
            const macdSignal = chartMacd.addLineSeries({{ color: '#f97316', lineWidth: 1.5 }});
            const macdHist = chartMacd.addHistogramSeries();

            // 4. Chart RSI Tách Riêng (Hiện trục thời gian ở đáy cùng)
            const chartRsi = LightweightCharts.createChart(cRsi, makeOptions(true));
            const rsiSeries = chartRsi.addLineSeries({{ color: '#a855f7', lineWidth: 1.8 }});
            const rsiUp = chartRsi.addLineSeries({{ color: '#ef4444', lineWidth: 1, lineStyle: 2 }});
            const rsiDown = chartRsi.addLineSeries({{ color: '#22c55e', lineWidth: 1, lineStyle: 2 }});

            const allCharts = [chartMain, chartVol, chartMacd, chartRsi];

            // ĐỒNG BỘ CUỘN VÀ ZOOM GIỮA TẤT CẢ CÁC PANE
            let isSyncing = false;
            allCharts.forEach((source, sIdx) => {{
                source.timeScale().subscribeVisibleLogicalRangeChange(range => {{
                    if (isSyncing || !range) return;
                    isSyncing = true;
                    allCharts.forEach((target, tIdx) => {{
                        if (sIdx !== tIdx) target.timeScale().setVisibleLogicalRange(range);
                    }});
                    isSyncing = false;
                }});
            }});

            const rawCandleData = {candle_json};
            const rawVolumeData = {volume_json};

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

            function calculateVolSMA(vols, period = 20) {{
                const res = [];
                for (let i = 0; i < vols.length; i++) {{
                    if (i < period - 1) continue;
                    let sum = 0;
                    for (let j = 0; j < period; j++) sum += vols[i - j].value;
                    res.push({{ time: vols[i].time, value: parseFloat((sum / period).toFixed(0)) }});
                }}
                return res;
            }}

            // HÀM RESAMPLE: 1D, 1W, 1M
            function resampleData(tf) {{
                if (tf === '1D') return {{ candles: rawCandleData, volumes: rawVolumeData }};
                if (tf === '1W') {{
                    const groups = {{}};
                    rawCandleData.forEach((c, idx) => {{
                        const d = new Date(c.time);
                        const day = d.getDay();
                        const diff = d.getDate() - day + (day === 0 ? -6 : 1);
                        const mon = new Date(d.setDate(diff)).toISOString().split('T')[0];
                        if (!groups[mon]) groups[mon] = [];
                        groups[mon].push({{ candle: c, volume: rawVolumeData[idx] }});
                    }});
                    const wCandles = [], wVols = [];
                    Object.keys(groups).sort().forEach(mon => {{
                        const items = groups[mon];
                        const open = items[0].candle.open;
                        const close = items[items.length - 1].candle.close;
                        const high = Math.max(...items.map(i => i.candle.high));
                        const low = Math.min(...items.map(i => i.candle.low));
                        const vol = items.reduce((sum, i) => sum + i.volume.value, 0);
                        const isUp = close >= open;
                        wCandles.push({{ time: mon, open, high, low, close }});
                        wVols.push({{ time: mon, value: vol, color: isUp ? 'rgba(8, 153, 129, 0.55)' : 'rgba(242, 54, 69, 0.55)' }});
                    }});
                    return {{ candles: wCandles, volumes: wVols }};
                }}
                if (tf === '1M') {{
                    const groups = {{}};
                    rawCandleData.forEach((c, idx) => {{
                        const mKey = c.time.substring(0, 7) + '-01';
                        if (!groups[mKey]) groups[mKey] = [];
                        groups[mKey].push({{ candle: c, volume: rawVolumeData[idx] }});
                    }});
                    const mCandles = [], mVols = [];
                    Object.keys(groups).sort().forEach(mKey => {{
                        const items = groups[mKey];
                        const open = items[0].candle.open;
                        const close = items[items.length - 1].candle.close;
                        const high = Math.max(...items.map(i => i.candle.high));
                        const low = Math.min(...items.map(i => i.candle.low));
                        const vol = items.reduce((sum, i) => sum + i.volume.value, 0);
                        const isUp = close >= open;
                        mCandles.push({{ time: mKey, open, high, low, close }});
                        mVols.push({{ time: mKey, value: vol, color: isUp ? 'rgba(8, 153, 129, 0.55)' : 'rgba(242, 54, 69, 0.55)' }});
                    }});
                    return {{ candles: mCandles, volumes: mVols }};
                }}
                return {{ candles: rawCandleData, volumes: rawVolumeData }};
            }}

            // BẢNG MAP O(1) CHO PHÉP NHẢY SỐ TỨC THÌ TỪNG NGÀY KHI RÊ CHUỘT
            let dataMaps = {{
                candle: {{}}, volume: {{}}, volSma: {{}},
                ma20: {{}}, ma50: {{}}, ema9: {{}}, ema21: {{}},
                bollUp: {{}}, bollMid: {{}}, bollLow: {{}},
                rsi: {{}}, macdLine: {{}}, macdSig: {{}}, macdHist: {{}}
            }};
            let latestTime = null;

            function formatVolume(val) {{
                if (val === undefined || val === null) return '--';
                if (val >= 1e9) return (val / 1e9).toFixed(3) + 'B';
                if (val >= 1e6) return (val / 1e6).toFixed(3) + 'M';
                if (val >= 1e3) return (val / 1e3).toFixed(1) + 'K';
                return val.toString();
            }}

            function updateAllPanes(t) {{
                if (!t) return;
                const c = dataMaps.candle[t];
                const v = dataMaps.volume[t];
                const vs = dataMaps.volSma[t];
                const m20 = dataMaps.ma20[t];
                const m50 = dataMaps.ma50[t];
                const e9 = dataMaps.ema9[t];
                const e21 = dataMaps.ema21[t];
                const bU = dataMaps.bollUp[t];
                const bM = dataMaps.bollMid[t];
                const bL = dataMaps.bollLow[t];
                const r = dataMaps.rsi[t];
                const mL = dataMaps.macdLine[t];
                const mS = dataMaps.macdSig[t];
                const mH = dataMaps.macdHist[t];

                // 1. Pane Nến Chính
                if (c) {{
                    const diff = c.close - c.open;
                    const pct = (diff / c.open) * 100;
                    const isUp = c.close >= c.open;
                    const col = isUp ? '#089981' : '#F23645';

                    document.getElementById('val-open').innerText = c.open.toFixed(2);
                    document.getElementById('val-high').innerText = c.high.toFixed(2);
                    document.getElementById('val-low').innerText = c.low.toFixed(2);
                    
                    const closeEl = document.getElementById('val-close');
                    closeEl.innerText = c.close.toFixed(2);
                    closeEl.style.color = col;

                    const chgEl = document.getElementById('val-change');
                    chgEl.innerText = `${{diff >= 0 ? '+' : ''}}${{diff.toFixed(2)}} (${{diff >= 0 ? '+' : ''}}${{pct.toFixed(2)}}%)`;
                    chgEl.style.color = col;
                }}
                document.querySelector('#badge-ma20 b').innerText = m20 !== undefined ? m20.toFixed(2) : '--';
                document.querySelector('#badge-ma50 b').innerText = m50 !== undefined ? m50.toFixed(2) : '--';
                document.querySelector('#badge-ema9 b').innerText = e9 !== undefined ? e9.toFixed(2) : '--';
                document.querySelector('#badge-ema21 b').innerText = e21 !== undefined ? e21.toFixed(2) : '--';
                if (bU !== undefined) {{
                    document.getElementById('badge-boll').innerHTML = `BOLL(20,2): Up <b>${{bU.toFixed(2)}}</b> Mid <b>${{bM.toFixed(2)}}</b> Low <b>${{bL.toFixed(2)}}</b>`;
                }}

                // 2. Pane Khối Lượng (Volume)
                if (v !== undefined) {{
                    document.querySelector('#hdr-vol-val b').innerText = formatVolume(v);
                }}
                if (vs !== undefined) {{
                    document.querySelector('#hdr-vol-sma b').innerText = formatVolume(vs);
                }}

                // 3. Pane MACD
                if (mL !== undefined) {{
                    document.querySelector('#hdr-macd-line b').innerText = mL.toFixed(2);
                    document.querySelector('#hdr-macd-sig b').innerText = mS !== undefined ? mS.toFixed(2) : '--';
                    const histVal = mH !== undefined ? mH : 0;
                    document.querySelector('#hdr-macd-hist').innerHTML = `Hist: <b style="color:${{histVal >= 0 ? '#22c55e' : '#ef4444'}};">${{histVal >= 0 ? '+' : ''}}${{histVal.toFixed(2)}}</b>`;
                }}

                // 4. Pane RSI
                if (r !== undefined) {{
                    document.querySelector('#hdr-rsi-val b').innerText = r.toFixed(2);
                }}
            }}

            // TỰ ĐỘNG CĂNG TRÀN ĐỒ THỊ 100% CHIỀU NGANG KHI LOAD
            function fitAll() {{
                const w = document.getElementById('panes-wrapper').clientWidth || window.innerWidth;
                if (!w || w === 0) return;

                chartMain.resize(w, cMain.clientHeight);
                chartVol.resize(w, cVol.clientHeight);
                chartMacd.resize(w, cMacd.clientHeight);
                chartRsi.resize(w, cRsi.clientHeight);

                setTimeout(() => {{
                    allCharts.forEach(chart => {{
                        chart.timeScale().fitContent();
                    }});
                }}, 50);
            }}

            function loadDataset(candles, volumes) {{
                dataMaps = {{
                    candle: {{}}, volume: {{}}, volSma: {{}},
                    ma20: {{}}, ma50: {{}}, ema9: {{}}, ema21: {{}},
                    bollUp: {{}}, bollMid: {{}}, bollLow: {{}},
                    rsi: {{}}, macdLine: {{}}, macdSig: {{}}, macdHist: {{}}
                }};

                candles.forEach(c => dataMaps.candle[c.time] = c);
                volumes.forEach(v => dataMaps.volume[v.time] = v.value);

                candleSeries.setData(candles);
                volumeSeries.setData(volumes);

                if (candles.length > 0) {{
                    latestTime = candles[candles.length - 1].time;

                    const ma20Data = calculateSMA(candles, 20);
                    ma20.setData(ma20Data);
                    ma20Data.forEach(d => dataMaps.ma20[d.time] = d.value);

                    const ma50Data = calculateSMA(candles, 50);
                    ma50.setData(ma50Data);
                    ma50Data.forEach(d => dataMaps.ma50[d.time] = d.value);

                    const ema9Data = calculateEMA(candles, 9);
                    ema9.setData(ema9Data);
                    ema9Data.forEach(d => dataMaps.ema9[d.time] = d.value);

                    const ema21Data = calculateEMA(candles, 21);
                    ema21.setData(ema21Data);
                    ema21Data.forEach(d => dataMaps.ema21[d.time] = d.value);

                    const bollData = calculateBOLL(candles);
                    bollUpper.setData(bollData.upper);
                    bollMid.setData(bollData.mid);
                    bollLower.setData(bollData.lower);
                    bollData.upper.forEach((d, i) => {{
                        dataMaps.bollUp[d.time] = d.value;
                        dataMaps.bollMid[d.time] = bollData.mid[i].value;
                        dataMaps.bollLow[d.time] = bollData.lower[i].value;
                    }});

                    const volSmaData = calculateVolSMA(volumes, 20);
                    volSmaSeries.setData(volSmaData);
                    volSmaData.forEach(d => dataMaps.volSma[d.time] = d.value);

                    const macdData = calculateMACD(candles);
                    macdLine.setData(macdData.mLine);
                    macdSignal.setData(macdData.sLine);
                    macdHist.setData(macdData.hList);
                    macdData.mLine.forEach(d => dataMaps.macdLine[d.time] = d.value);
                    macdData.sLine.forEach(d => dataMaps.macdSig[d.time] = d.value);
                    macdData.hList.forEach(d => dataMaps.macdHist[d.time] = d.value);

                    const rsiData = calculateRSI(candles);
                    rsiSeries.setData(rsiData);
                    rsiUp.setData(rsiData.map(d => ({{ time: d.time, value: 70 }})));
                    rsiDown.setData(rsiData.map(d => ({{ time: d.time, value: 30 }})));
                    rsiData.forEach(d => dataMaps.rsi[d.time] = d.value);

                    updateAllPanes(latestTime);
                }}

                fitAll();
            }}

            // ĐỒNG BỘ RÊ CHUỘT CROSSHAIR MOVE
            allCharts.forEach(chart => {{
                chart.subscribeCrosshairMove(param => {{
                    if (!param || !param.time || param.point === undefined) {{
                        updateAllPanes(latestTime);
                        return;
                    }}
                    updateAllPanes(param.time);
                }});
            }});

            loadDataset(rawCandleData, rawVolumeData);

            window.addEventListener('load', fitAll);
            window.addEventListener('resize', fitAll);
            setTimeout(fitAll, 100);
            setTimeout(fitAll, 300);

            // BẬT / TẮT CHỈ BÁO
            let isMA = true, isEMA = false, isBOLL = false, isMACD = false, isRSI = true;

            document.getElementById('btn-ma').addEventListener('click', function() {{
                isMA = !isMA;
                ma20.applyOptions({{ visible: isMA }});
                ma50.applyOptions({{ visible: isMA }});
                document.getElementById('badge-ma20').style.display = isMA ? 'inline-flex' : 'none';
                document.getElementById('badge-ma50').style.display = isMA ? 'inline-flex' : 'none';
                this.classList.toggle('active', isMA);
            }});

            document.getElementById('btn-ema').addEventListener('click', function() {{
                isEMA = !isEMA;
                ema9.applyOptions({{ visible: isEMA }});
                ema21.applyOptions({{ visible: isEMA }});
                document.getElementById('badge-ema9').style.display = isEMA ? 'inline-flex' : 'none';
                document.getElementById('badge-ema21').style.display = isEMA ? 'inline-flex' : 'none';
                this.classList.toggle('active', isEMA);
            }});

            document.getElementById('btn-boll').addEventListener('click', function() {{
                isBOLL = !isBOLL;
                bollUpper.applyOptions({{ visible: isBOLL }});
                bollMid.applyOptions({{ visible: isBOLL }});
                bollLower.applyOptions({{ visible: isBOLL }});
                document.getElementById('badge-boll').style.display = isBOLL ? 'inline-flex' : 'none';
                this.classList.toggle('active', isBOLL);
            }});

            document.getElementById('btn-macd').addEventListener('click', function() {{
                isMACD = !isMACD;
                this.classList.toggle('active', isMACD);
                paneMacd.style.display = isMACD ? 'flex' : 'none';
                sepMacd.style.display = isMACD ? 'block' : 'none';
                fitAll();
            }});

            document.getElementById('btn-rsi').addEventListener('click', function() {{
                isRSI = !isRSI;
                this.classList.toggle('active', isRSI);
                paneRsi.style.display = isRSI ? 'flex' : 'none';
                sepRsi.style.display = isRSI ? 'block' : 'none';
                chartMacd.applyOptions({{ timeScale: {{ visible: !isRSI && isMACD }} }});
                chartVol.applyOptions({{ timeScale: {{ visible: !isRSI && !isMACD }} }});
                fitAll();
            }});

            // DROPDOWN TIMEFRAME
            const tfBtn = document.getElementById('tf-btn');
            const tfMenu = document.getElementById('tf-menu');
            const tfLabel = document.getElementById('tf-label');
            tfBtn.addEventListener('click', (e) => {{
                e.stopPropagation();
                tfMenu.classList.toggle('show');
            }});
            document.addEventListener('click', () => tfMenu.classList.remove('show'));
            document.querySelectorAll('.tf-item').forEach(item => {{
                item.addEventListener('click', function(e) {{
                    e.stopPropagation();
                    document.querySelectorAll('.tf-item').forEach(el => el.classList.remove('active'));
                    this.classList.add('active');
                    const tf = this.getAttribute('data-tf');
                    tfLabel.innerText = this.innerText.trim();
                    tfMenu.classList.remove('show');
                    const resampled = resampleData(tf);
                    loadDataset(resampled.candles, resampled.volumes);
                }});
            }});
        </script>
    </body>
    </html>
    """
    return html
