import json
import pandas as pd

def generate_tradingview_html(df: pd.DataFrame, symbol: str) -> str:
    """
    Tạo mã HTML/JS nhúng TradingView Lightweight Charts tương tác chuẩn TradingView Pro:
    - Bố cục Multi-Pane tự co giãn chiếm 100% chiều cao, không bị tràn màn hình:
      + Header trên đỉnh: Tên mã, Khung thời gian (1D/1W/1M), Nút bật/tắt MA, EMA, BOLL, Vol, MACD, RSI, OHLCV realtime.
      + Pane 1: Đồ thị nến Candlestick + MA + EMA + BOLL.
      + Pane 2: Đồ thị Khối lượng Volume tách riêng + SMA 20.
      + Pane 3: Sub-panel MACD (Line, Signal, Histogram).
      + Pane 4: Sub-panel RSI (14) + 70/30.
    - Đường gióng Crosshair thẳng đứng (dấu ----) cắt xuyên suốt 100% từ đỉnh Pane Nến xuống tận đáy cùng của tất cả các Subpanel kèm Nhãn Ngày Tháng nổi bật ở chân trục thời gian.
    - Hàm recalcLayout(): Tự động co giãn nến chiếm toàn bộ không gian khi tắt các subpanel, không để khoảng trống đen.
    - Đồng bộ Crosshair & Header: Trỏ chuột vào bất kỳ ngày nào, toàn bộ 4 pane đều nhảy đúng số liệu ngày đó.
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
            "color": "rgba(8, 153, 129, 0.65)" if is_up else "rgba(242, 54, 69, 0.65)"
        })

    candle_json = json.dumps(candle_list)
    volume_json = json.dumps(volume_list)

    html = f"""
    <!DOCTYPE html>
    <html lang="vi">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <script src="https://unpkg.com/lightweight-charts@4.1.3/dist/lightweight-charts.standalone.production.js"></script>
        <style>
            * {{ box-sizing: border-box; margin: 0; padding: 0; }}
            html, body {{
                width: 100%;
                height: 100%;
                overflow: hidden;
                background-color: #131722;
                color: #d1d4dc;
                font-family: -apple-system, BlinkMacSystemFont, "Trebuchet MS", Roboto, sans-serif;
                display: flex;
                flex-direction: column;
            }}

            /* 1. THANH HEADER CHÍNH TRÊN ĐỈNH */
            .main-header {{
                display: flex;
                align-items: center;
                justify-content: space-between;
                padding: 6px 14px;
                background-color: #1e222d;
                border-bottom: 1px solid #2a2e39;
                flex-shrink: 0;
                gap: 10px;
                flex-wrap: wrap;
                z-index: 100;
            }}
            .header-left {{
                display: flex;
                align-items: center;
                gap: 8px;
                flex-wrap: wrap;
            }}
            .symbol-title {{
                font-size: 15px;
                font-weight: 800;
                color: #f8fafc;
                letter-spacing: 0.5px;
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
                padding: 3px 8px;
                font-size: 11px;
                font-weight: 600;
                cursor: pointer;
                display: flex;
                align-items: center;
                gap: 4px;
                transition: all 0.15s ease;
            }}
            .tf-btn:hover {{
                background-color: #363a45;
            }}
            .tf-menu {{
                display: none;
                position: absolute;
                top: calc(100% + 4px);
                left: 0;
                background-color: #1e222d;
                border: 1px solid #2a2e39;
                border-radius: 6px;
                width: 110px;
                box-shadow: 0 10px 25px rgba(0, 0, 0, 0.75);
                padding: 4px 0;
                z-index: 1000;
            }}
            .tf-menu.show {{ display: block; }}
            .tf-item {{
                padding: 5px 12px;
                font-size: 11px;
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
                font-weight: 700;
            }}

            .v-sep {{
                width: 1px;
                height: 18px;
                background-color: #363a45;
                margin: 0 2px;
            }}

            /* NHÓM NÚT BẬT TẮT CHỈ BÁO TRÊN HEADER */
            .btn-group {{
                display: flex;
                align-items: center;
                gap: 4px;
            }}
            .btn-tag {{
                background-color: #262b38;
                color: #848e9c;
                border: 1px solid #363a45;
                border-radius: 4px;
                padding: 2px 8px;
                font-size: 11px;
                font-weight: 700;
                cursor: pointer;
                transition: all 0.15s ease;
                outline: none;
            }}
            .btn-tag:hover {{
                background-color: #363a45;
                color: #f8fafc;
            }}
            .btn-tag.active {{
                background-color: #2962FF;
                color: #ffffff;
                border-color: #2962FF;
                box-shadow: 0 0 8px rgba(41, 98, 255, 0.4);
            }}

            /* DÒNG THÔNG SỐ NẾN OHLCV */
            .header-right {{
                display: flex;
                align-items: center;
                gap: 8px;
                font-size: 11px;
                font-family: -apple-system, BlinkMacSystemFont, "Trebuchet MS", Roboto, monospace;
                color: #94a3b8;
                flex-wrap: wrap;
            }}
            .header-right span b {{
                color: #f8fafc;
                font-weight: 600;
            }}

            /* 2. CÁC PANE ĐỒ THỊ RIÊNG BIỆT (MULTI-PANE CONTAINER) */
            .panes-wrapper {{
                flex: 1;
                display: flex;
                flex-direction: column;
                width: 100%;
                height: 100%;
                background-color: #131722;
                overflow: hidden;
                position: relative;
            }}
            .pane-box {{
                width: 100%;
                position: relative;
                display: flex;
                flex-direction: column;
                background-color: #131722;
                border-bottom: 1px solid #2a2e39;
            }}
            .pane-header-bar {{
                height: 22px;
                padding: 0 12px;
                background-color: #161a25;
                display: flex;
                align-items: center;
                gap: 10px;
                font-size: 11px;
                font-family: -apple-system, BlinkMacSystemFont, "Trebuchet MS", Roboto, monospace;
                color: #94a3b8;
                flex-shrink: 0;
                z-index: 10;
                user-select: none;
            }}
            .pane-header-bar b {{
                font-weight: 700;
            }}
            .pane-chart-container {{
                width: 100%;
                flex: 1;
                position: relative;
            }}

            /* 3. ĐƯỜNG GIÓNG CROSSHAIR CẮT XUYÊN SUỐT TẤT CẢ CÁC PANE */
            #v-crosshair-line {{
                position: absolute;
                top: 0;
                bottom: 0;
                width: 1px;
                border-left: 1px dashed rgba(209, 212, 220, 0.6);
                pointer-events: none;
                display: none;
                z-index: 90;
            }}
            #v-crosshair-badge {{
                position: absolute;
                bottom: 3px;
                background-color: #2962FF;
                color: #ffffff;
                font-size: 11px;
                font-weight: 700;
                padding: 2px 8px;
                border-radius: 4px;
                transform: translateX(-50%);
                pointer-events: none;
                display: none;
                z-index: 100;
                box-shadow: 0 2px 8px rgba(0,0,0,0.75);
                font-family: -apple-system, BlinkMacSystemFont, "Trebuchet MS", Roboto, monospace;
                white-space: nowrap;
            }}
        </style>
    </head>
    <body>
        <!-- 1. THANH HEADER CHÍNH TRÊN ĐỈNH -->
        <div class="main-header" id="main-header">
            <div class="header-left">
                <span class="symbol-title">{symbol}</span>
                
                <!-- DROPDOWN CHỌN KHUNG THỜI GIAN -->
                <div class="tf-dropdown">
                    <button class="tf-btn" id="tf-btn">
                        <span id="tf-label">1 ngày</span>
                        <svg width="7" height="5" viewBox="0 0 8 6" fill="none">
                            <path d="M1 1.5L4 4.5L7 1.5" stroke="#94a3b8" stroke-width="1.5" stroke-linecap="round"/>
                        </svg>
                    </button>
                    <div class="tf-menu" id="tf-menu">
                        <div class="tf-item active" data-tf="1D">1 ngày</div>
                        <div class="tf-item" data-tf="1W">1 tuần</div>
                        <div class="tf-item" data-tf="1M">1 tháng</div>
                    </div>
                </div>

                <div class="v-sep"></div>

                <!-- CÁC NÚT CHỈ BÁO TRÊN ĐỒ THỊ CHÍNH -->
                <div class="btn-group">
                    <button class="btn-tag active" id="btn-ma" title="Đường trung bình MA (20, 50)">MA</button>
                    <button class="btn-tag" id="btn-ema" title="Đường trung bình hàm mũ EMA (9, 21)">EMA</button>
                    <button class="btn-tag" id="btn-boll" title="Dải băng Bollinger Bands (20, 2)">BOLL</button>
                </div>

                <div class="v-sep"></div>

                <!-- CÁC NÚT BẬT TẮT SUBPANEL ĐỒ THỊ PHỤ -->
                <div class="btn-group">
                    <button class="btn-tag active" id="btn-vol" title="Đồ thị Khối lượng tách riêng">Khối lượng</button>
                    <button class="btn-tag" id="btn-macd" title="Đồ thị MACD tách riêng">MACD</button>
                    <button class="btn-tag active" id="btn-rsi" title="Đồ thị RSI (14) tách riêng">RSI</button>
                </div>
            </div>

            <!-- CHỈ SỐ OHLCV REALTIME CỦA NGÀY TRỎ CHUỘT -->
            <div class="header-right" id="header-ohlc">
                <span>O <b id="val-open">--</b></span>
                <span>H <b id="val-high">--</b></span>
                <span>L <b id="val-low">--</b></span>
                <span>C <b id="val-close">--</b></span>
                <span id="val-change" style="font-weight:700;">--</span>
            </div>
        </div>

        <!-- 2. BỐ CỤC CÁC PANE ĐỒ THỊ -->
        <div class="panes-wrapper" id="panes-wrapper">
            <!-- ĐƯỜNG GIÓNG CROSSHAIR CẮT XUYÊN SUỐT TOÀN BỘ CÁC PANE -->
            <div id="v-crosshair-line"></div>
            <div id="v-crosshair-badge"></div>

            <!-- PANE 1: BIỂU ĐỒ NẾN CHÍNH -->
            <div class="pane-box" id="pane-main">
                <div class="pane-header-bar" id="hdr-main">
                    <span id="badge-ma20" style="color: #f59e0b;">MA 20: <b>--</b></span>
                    <span id="badge-ma50" style="color: #3b82f6;">MA 50: <b>--</b></span>
                    <span id="badge-ema9" style="color: #10b981; display: none;">EMA 9: <b>--</b></span>
                    <span id="badge-ema21" style="color: #ec4899; display: none;">EMA 21: <b>--</b></span>
                    <span id="badge-boll" style="color: #38bdf8; display: none;">BOLL(20,2): Up <b>--</b> Mid <b>--</b> Low <b>--</b></span>
                </div>
                <div class="pane-chart-container" id="container-main"></div>
            </div>

            <!-- PANE 2: ĐỒ THỊ KHỐI LƯỢNG TÁCH RIÊNG Ở DƯỚI -->
            <div class="pane-box" id="pane-vol">
                <div class="pane-header-bar">
                    <span style="color:#f8fafc; font-weight:700;">Khối lượng</span>
                    <span style="color:#787b86;">20 SMA 20</span>
                    <span style="color: #38bdf8;" id="hdr-vol-val">Vol: <b>--</b></span>
                    <span style="color: #f59e0b;" id="hdr-vol-sma">SMA 20: <b>--</b></span>
                </div>
                <div class="pane-chart-container" id="container-vol"></div>
            </div>

            <!-- PANE 3: ĐỒ THỊ MACD TÁCH RIÊNG (Ẩn mặc định) -->
            <div class="pane-box" id="pane-macd" style="display: none;">
                <div class="pane-header-bar">
                    <span style="color:#f8fafc; font-weight:700;">MACD</span>
                    <span style="color:#787b86;">12 26 close 9</span>
                    <span style="color: #38bdf8;" id="hdr-macd-line">MACD: <b>--</b></span>
                    <span style="color: #f97316;" id="hdr-macd-sig">Signal: <b>--</b></span>
                    <span id="hdr-macd-hist">Hist: <b>--</b></span>
                </div>
                <div class="pane-chart-container" id="container-macd"></div>
            </div>

            <!-- PANE 4: ĐỒ THỊ RSI TÁCH RIÊNG (Bật mặc định) -->
            <div class="pane-box" id="pane-rsi">
                <div class="pane-header-bar">
                    <span style="color:#f8fafc; font-weight:700;">RSI</span>
                    <span style="color:#787b86;">14</span>
                    <span style="color: #a855f7;" id="hdr-rsi-val">RSI: <b>--</b></span>
                </div>
                <div class="pane-chart-container" id="container-rsi"></div>
            </div>
        </div>

        <script>
            const cMain = document.getElementById('container-main');
            const cVol = document.getElementById('container-vol');
            const cMacd = document.getElementById('container-macd');
            const cRsi = document.getElementById('container-rsi');

            const pMain = document.getElementById('pane-main');
            const pVol = document.getElementById('pane-vol');
            const pMacd = document.getElementById('pane-macd');
            const pRsi = document.getElementById('pane-rsi');

            const vLine = document.getElementById('v-crosshair-line');
            const vBadge = document.getElementById('v-crosshair-badge');

            // CẤU HÌNH TIME SCALE: Chống co cụm nến
            const makeTimeScale = (showTimeAxis) => ({{
                borderColor: '#2a2e39',
                timeVisible: false,
                secondsVisible: false,
                visible: showTimeAxis,
                fixLeftEdge: true,
                fixRightEdge: true,
                minBarSpacing: 1,
                rightOffset: 2,
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

            // 4. Chart RSI Tách Riêng
            const chartRsi = LightweightCharts.createChart(cRsi, makeOptions(true));
            const rsiSeries = chartRsi.addLineSeries({{ color: '#a855f7', lineWidth: 1.8 }});
            const rsiUp = chartRsi.addLineSeries({{ color: '#ef4444', lineWidth: 1, lineStyle: 2 }});
            const rsiDown = chartRsi.addLineSeries({{ color: '#22c55e', lineWidth: 1, lineStyle: 2 }});

            const allCharts = [
                {{ chart: chartMain, series: candleSeries, key: 'main' }},
                {{ chart: chartVol, series: volumeSeries, key: 'vol' }},
                {{ chart: chartMacd, series: macdLine, key: 'macd' }},
                {{ chart: chartRsi, series: rsiSeries, key: 'rsi' }}
            ];

            // TRẠNG THÁI HIỂN THỊ CÁC CHỈ BÁO & SUBPANEL
            let isMA = true, isEMA = false, isBOLL = false;
            let isVol = true, isMacd = false, isRsi = true;
            let isSyncing = false;

            // ĐỒNG BỘ CUỘN VÀ ZOOM GIỮA CÁC PANE
            allCharts.forEach((sourceItem, sIdx) => {{
                sourceItem.chart.timeScale().subscribeVisibleLogicalRangeChange(range => {{
                    if (isSyncing || !range) return;
                    isSyncing = true;
                    allCharts.forEach((targetItem, tIdx) => {{
                        if (sIdx !== tIdx) {{
                            targetItem.chart.timeScale().setVisibleLogicalRange(range);
                        }}
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
                    const diff = data[i].close - data[i - 1].close;
                    if (diff >= 0) gains += diff; else losses -= diff;
                }}
                let avgGain = gains / period;
                let avgLoss = losses / period;
                let rs = avgLoss === 0 ? 100 : avgGain / avgLoss;
                res.push({{ time: data[period].time, value: parseFloat((100 - (100 / (1 + rs))).toFixed(2)) }});

                for (let i = period + 1; i < data.length; i++) {{
                    const diff = data[i].close - data[i - 1].close;
                    const g = diff >= 0 ? diff : 0;
                    const l = diff < 0 ? -diff : 0;
                    avgGain = (avgGain * (period - 1) + g) / period;
                    avgLoss = (avgLoss * (period - 1) + l) / period;
                    rs = avgLoss === 0 ? 100 : avgGain / avgLoss;
                    res.push({{ time: data[i].time, value: parseFloat((100 - (100 / (1 + rs))).toFixed(2)) }});
                }}
                return res;
            }}

            function calculateMACD(data) {{
                const ema12 = calculateEMA(data, 12);
                const ema26 = calculateEMA(data, 26);
                const map26 = {{}};
                ema26.forEach(d => map26[d.time] = d.value);

                const macdRaw = [];
                ema12.forEach(d => {{
                    if (map26[d.time] !== undefined) {{
                        macdRaw.push({{ time: d.time, close: parseFloat((d.value - map26[d.time]).toFixed(2)) }});
                    }}
                }});

                const signalRaw = calculateEMA(macdRaw, 9);
                const mapSig = {{}};
                signalRaw.forEach(d => mapSig[d.time] = d.value);

                const mLine = [], sLine = [], hList = [];
                macdRaw.forEach(d => {{
                    const sVal = mapSig[d.time];
                    mLine.push({{ time: d.time, value: d.close }});
                    if (sVal !== undefined) {{
                        sLine.push({{ time: d.time, value: sVal }});
                        const diff = parseFloat((d.close - sVal).toFixed(2));
                        hList.push({{
                            time: d.time,
                            value: diff,
                            color: diff >= 0 ? '#26a69a' : '#ef5350'
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
                        wVols.push({{ time: mon, value: vol, color: isUp ? 'rgba(8, 153, 129, 0.65)' : 'rgba(242, 54, 69, 0.65)' }});
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
                        mVols.push({{ time: mKey, value: vol, color: isUp ? 'rgba(8, 153, 129, 0.65)' : 'rgba(242, 54, 69, 0.65)' }});
                    }});
                    return {{ candles: mCandles, volumes: mVols }};
                }}
                return {{ candles: rawCandleData, volumes: rawVolumeData }};
            }}

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

            function formatDateBadge(tStr) {{
                if (!tStr) return '';
                const parts = tStr.split('-');
                if (parts.length === 3) {{
                    return `${{parts[2]}} Thg ${{parseInt(parts[1])}} '${{parts[0].slice(2)}}`;
                }}
                return tStr;
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

                // 1. Header chính: OHLCV
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

                // Pane Nến: MA, EMA, BOLL
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
                    document.querySelector('#hdr-macd-hist').innerHTML = `Hist: <b style="color:${{histVal >= 0 ? '#26a69a' : '#ef5350'}};">${{histVal >= 0 ? '+' : ''}}${{histVal.toFixed(2)}}</b>`;
                }}

                // 4. Pane RSI
                if (r !== undefined) {{
                    document.querySelector('#hdr-rsi-val b').innerText = r.toFixed(2);
                }}
            }}

            // HÀM TỰ TÍNH TOÁN BỐ CỤC KHÔNG ĐỂ KHOẢNG TRỐNG VÀ KHÔNG BỊ TRÀN KHUNG
            function recalcLayout() {{
                const wrapper = document.getElementById('panes-wrapper');
                const totalW = wrapper.clientWidth || window.innerWidth;
                const totalH = wrapper.clientHeight || (window.innerHeight - 48);

                if (!totalW || totalW <= 50 || !totalH || totalH <= 100) return;

                const volH = isVol ? 80 : 0;
                const macdH = isMacd ? 95 : 0;
                const rsiH = isRsi ? 80 : 0;

                const mainH = Math.max(160, totalH - (volH + macdH + rsiH));

                pMain.style.height = mainH + 'px';
                cMain.style.height = (mainH - 22) + 'px';

                if (isVol) {{
                    pVol.style.display = 'flex';
                    pVol.style.height = volH + 'px';
                    cVol.style.height = (volH - 22) + 'px';
                }} else {{
                    pVol.style.display = 'none';
                }}

                if (isMacd) {{
                    pMacd.style.display = 'flex';
                    pMacd.style.height = macdH + 'px';
                    cMacd.style.height = (macdH - 22) + 'px';
                }} else {{
                    pMacd.style.display = 'none';
                }}

                if (isRsi) {{
                    pRsi.style.display = 'flex';
                    pRsi.style.height = rsiH + 'px';
                    cRsi.style.height = (rsiH - 22) + 'px';
                }} else {{
                    pRsi.style.display = 'none';
                }}

                const activeList = [
                    {{ chart: chartMain, active: true }},
                    {{ chart: chartVol, active: isVol }},
                    {{ chart: chartMacd, active: isMacd }},
                    {{ chart: chartRsi, active: isRsi }}
                ].filter(item => item.active);

                activeList.forEach((item, idx) => {{
                    const isLast = (idx === activeList.length - 1);
                    item.chart.applyOptions({{ timeScale: {{ visible: isLast }} }});
                }});

                chartMain.resize(totalW, mainH - 22);
                if (isVol) chartVol.resize(totalW, volH - 22);
                if (isMacd) chartMacd.resize(totalW, macdH - 22);
                if (isRsi) chartRsi.resize(totalW, rsiH - 22);

                isSyncing = true;
                chartMain.timeScale().fitContent();
                const vRange = chartMain.timeScale().getVisibleLogicalRange();
                if (vRange) {{
                    if (isVol) chartVol.timeScale().setVisibleLogicalRange(vRange);
                    if (isMacd) chartMacd.timeScale().setVisibleLogicalRange(vRange);
                    if (isRsi) chartRsi.timeScale().setVisibleLogicalRange(vRange);
                }}
                isSyncing = false;
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

                recalcLayout();
            }}

            // ĐỒNG BỘ RÊ CHUỘT: ĐƯỜNG GIÓNG THẲNG ĐỨNG CẮT XUYÊN SUỐT TOÀN BỘ CÁC PANE
            allCharts.forEach(sourceItem => {{
                sourceItem.chart.subscribeCrosshairMove(param => {{
                    if (!param || !param.time || param.point === undefined || param.point.x < 0) {{
                        vLine.style.display = 'none';
                        vBadge.style.display = 'none';
                        allCharts.forEach(item => {{
                            try {{ item.chart.clearCrosshairPosition(); }} catch(e) {{}}
                        }});
                        updateAllPanes(latestTime);
                        return;
                    }}

                    const t = param.time;

                    // 1. Cập nhật đường gióng nét đứt (----) cắt xuyên suốt tất cả các pane
                    vLine.style.display = 'block';
                    vLine.style.left = param.point.x + 'px';

                    // 2. Cập nhật nhãn ngày nổi bật ở chân trục thời gian
                    vBadge.style.display = 'block';
                    vBadge.style.left = param.point.x + 'px';
                    vBadge.innerText = formatDateBadge(t);

                    // 3. Gọi setCrosshairPosition đồng bộ sang các chart phụ
                    const cData = dataMaps.candle[t];
                    const vData = dataMaps.volume[t];
                    const rData = dataMaps.rsi[t];
                    const mData = dataMaps.macdLine[t];

                    if (cData && sourceItem.key !== 'main') {{
                        try {{ chartMain.setCrosshairPosition(cData.close, t, candleSeries); }} catch(e) {{}}
                    }}
                    if (isVol && vData !== undefined && sourceItem.key !== 'vol') {{
                        try {{ chartVol.setCrosshairPosition(vData, t, volumeSeries); }} catch(e) {{}}
                    }}
                    if (isMacd && mData !== undefined && sourceItem.key !== 'macd') {{
                        try {{ chartMacd.setCrosshairPosition(mData, t, macdLine); }} catch(e) {{}}
                    }}
                    if (isRsi && rData !== undefined && sourceItem.key !== 'rsi') {{
                        try {{ chartRsi.setCrosshairPosition(rData, t, rsiSeries); }} catch(e) {{}}
                    }}

                    // 4. Nhảy số liệu tức thì trên tất cả các Header
                    updateAllPanes(t);
                }});
            }});

            // Ẩn đường gióng khi chuột rời khỏi vùng đồ thị
            document.getElementById('panes-wrapper').addEventListener('mouseleave', () => {{
                vLine.style.display = 'none';
                vBadge.style.display = 'none';
                allCharts.forEach(item => {{
                    try {{ item.chart.clearCrosshairPosition(); }} catch(e) {{}}
                }});
                updateAllPanes(latestTime);
            }});

            // NẠP DỮ LIỆU BAN ĐẦU
            loadDataset(rawCandleData, rawVolumeData);

            // BẬT / TẮT CHỈ BÁO NẾN TRÊN HEADER
            document.getElementById('btn-ma').addEventListener('click', function() {{
                isMA = !isMA;
                ma20.applyOptions({{ visible: isMA }});
                ma50.applyOptions({{ visible: isMA }});
                document.getElementById('badge-ma20').style.display = isMA ? 'inline-block' : 'none';
                document.getElementById('badge-ma50').style.display = isMA ? 'inline-block' : 'none';
                this.classList.toggle('active', isMA);
            }});

            document.getElementById('btn-ema').addEventListener('click', function() {{
                isEMA = !isEMA;
                ema9.applyOptions({{ visible: isEMA }});
                ema21.applyOptions({{ visible: isEMA }});
                document.getElementById('badge-ema9').style.display = isEMA ? 'inline-block' : 'none';
                document.getElementById('badge-ema21').style.display = isEMA ? 'inline-block' : 'none';
                this.classList.toggle('active', isEMA);
            }});

            document.getElementById('btn-boll').addEventListener('click', function() {{
                isBOLL = !isBOLL;
                bollUpper.applyOptions({{ visible: isBOLL }});
                bollMid.applyOptions({{ visible: isBOLL }});
                bollLower.applyOptions({{ visible: isBOLL }});
                document.getElementById('badge-boll').style.display = isBOLL ? 'inline-block' : 'none';
                this.classList.toggle('active', isBOLL);
            }});

            // BẬT / TẮT SUBPANEL ĐỒ THỊ PHỤ - NẾN CHÍNH TỰ ĐỘNG MỞ RỘNG/THU HẸP
            document.getElementById('btn-vol').addEventListener('click', function() {{
                isVol = !isVol;
                this.classList.toggle('active', isVol);
                recalcLayout();
            }});

            document.getElementById('btn-macd').addEventListener('click', function() {{
                isMacd = !isMacd;
                this.classList.toggle('active', isMacd);
                recalcLayout();
            }});

            document.getElementById('btn-rsi').addEventListener('click', function() {{
                isRsi = !isRsi;
                this.classList.toggle('active', isRsi);
                recalcLayout();
            }});

            // DROPDOWN CHỌN KHUNG THỜI GIAN (1D, 1W, 1M)
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

            // TỰ ĐỘNG BÁM SÁT KÍCH THƯỚC IFRAME STREAMLIT VÀ KHI CHUYỂN TAB
            window.addEventListener('resize', recalcLayout);
            window.addEventListener('load', recalcLayout);
            setTimeout(recalcLayout, 50);
            setTimeout(recalcLayout, 150);
            setTimeout(recalcLayout, 400);

            if (window.ResizeObserver) {{
                const ro = new ResizeObserver(() => {{
                    recalcLayout();
                }});
                ro.observe(document.getElementById('panes-wrapper'));
            }}
        </script>
    </body>
    </html>
    """
    return html
