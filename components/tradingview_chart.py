import json
import pandas as pd

def generate_tradingview_html(df: pd.DataFrame, symbol: str) -> str:
    """
    Tạo mã HTML/JS nhúng TradingView Lightweight Charts tương tác Native:
    - Dropdown timeframe chuẩn dữ liệu thực tế (1 ngày, 1 tuần, 1 tháng), loại bỏ các khung ngắn hơn 1 ngày.
    - Loại bỏ hoàn toàn 00:00:00 (chỉ hiển thị ngày tháng năm).
    - Biểu đồ nến chính hiển thị MA (20, 50), EMA (9, 21), BOLL (20, 2) và Khối lượng Volume.
    - Tạo một bảng riêng biệt (Sub-panel) ở dưới cho RSI và MACD với header hiển thị số liệu realtime khi trỏ chuột vào một ngày.
    - Thanh công cụ đáy bật/tắt linh hoạt các chỉ báo.
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
            
            /* HEADER CHÍNH: TÊN MÃ, TIMEFRAME, VÀ THÔNG SỐ NẾN OHLCV */
            .tv-header {{
                display: flex;
                flex-direction: column;
                gap: 4px;
                padding: 6px 14px;
                background-color: #1e222d;
                border-bottom: 1px solid #2a2e39;
                position: relative;
                z-index: 100;
            }}
            .tv-title-row {{
                display: flex;
                align-items: center;
                gap: 12px;
                flex-wrap: wrap;
            }}
            .symbol-title {{
                font-size: 15px;
                font-weight: 700;
                color: #f8fafc;
            }}
            
            /* DROPDOWN CHỌN KHUNG THỜI GIAN (CHỈ 1 NGÀY, 1 TUẦN, 1 THÁNG) */
            .tf-dropdown {{
                position: relative;
                display: inline-block;
            }}
            .tf-btn {{
                background-color: #2a2e39;
                color: #f8fafc;
                border: 1px solid #363a45;
                border-radius: 4px;
                padding: 3px 9px;
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
                width: 130px;
                box-shadow: 0 10px 25px rgba(0, 0, 0, 0.75);
                padding: 5px 0;
                z-index: 1000;
            }}
            .tf-menu.show {{
                display: block;
            }}
            .tf-group-header {{
                font-size: 10px;
                font-weight: 700;
                color: #787b86;
                padding: 4px 12px 2px 12px;
                letter-spacing: 0.5px;
            }}
            .tf-item {{
                padding: 6px 12px;
                font-size: 12px;
                font-weight: 500;
                color: #d1d4dc;
                cursor: pointer;
                transition: background 0.1s ease;
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

            /* THANH TRẠNG THÁI OHLCV */
            .ohlc-row {{
                display: flex;
                align-items: center;
                gap: 8px;
                font-size: 12px;
                font-family: -apple-system, BlinkMacSystemFont, "Trebuchet MS", Roboto, monospace;
                color: #94a3b8;
            }}
            .ohlc-row b {{
                font-weight: 600;
                color: #f8fafc;
            }}
            .ind-main-row {{
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

            /* KHU VỰC ĐỒ THỊ CHÍNH & PHỤ */
            .charts-wrapper {{
                flex: 1;
                display: flex;
                flex-direction: column;
                width: 100%;
                position: relative;
                overflow: hidden;
            }}
            #tv-chart-main {{
                flex: 1;
                width: 100%;
                position: relative;
            }}

            /* BẢNG PHỤ (SUB-PANEL CHO RSI HOẶC MACD) */
            .tv-sub-panel {{
                height: 145px;
                width: 100%;
                display: flex;
                flex-direction: column;
                border-top: 1px solid #2a2e39;
                background-color: #131722;
                position: relative;
            }}
            .sub-header {{
                height: 24px;
                padding: 3px 14px;
                background-color: #171b26;
                display: flex;
                align-items: center;
                gap: 10px;
                font-size: 11px;
                font-family: -apple-system, BlinkMacSystemFont, "Trebuchet MS", Roboto, monospace;
                border-bottom: 1px solid rgba(42, 46, 57, 0.4);
                color: #cbd5e1;
            }}
            .sub-header b {{
                font-weight: 700;
            }}
            #tv-chart-sub {{
                flex: 1;
                width: 100%;
                position: relative;
            }}

            /* TOOLBAR ĐÁY BẬT TẮT CHỈ BÁO */
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
        <!-- HEADER TRÊN CÙNG -->
        <div class="tv-header">
            <div class="tv-title-row">
                <span class="symbol-title">{symbol}</span>
                
                <!-- DROPDOWN KHUNG THỜI GIAN: CHỈ GIỮ 1 NGÀY, 1 TUẦN, 1 THÁNG -->
                <div class="tf-dropdown">
                    <button class="tf-btn" id="tf-btn" title="Chọn khung thời gian">
                        <span id="tf-label">1 ngày</span>
                        <svg width="8" height="6" viewBox="0 0 8 6" fill="none" style="margin-left:2px;">
                            <path d="M1 1.5L4 4.5L7 1.5" stroke="#94a3b8" stroke-width="1.5" stroke-linecap="round"/>
                        </svg>
                    </button>
                    <div class="tf-menu" id="tf-menu">
                        <div class="tf-group-header">KHUNG THỜI GIAN</div>
                        <div class="tf-item active" data-tf="1D">1 ngày</div>
                        <div class="tf-item" data-tf="1W">1 tuần</div>
                        <div class="tf-item" data-tf="1M">1 tháng</div>
                    </div>
                </div>

                <!-- THÔNG SỐ NẾN OHLCV -->
                <div class="ohlc-row" id="ohlc-row">
                    <span>O <b id="val-open">--</b></span>
                    <span>H <b id="val-high">--</b></span>
                    <span>L <b id="val-low">--</b></span>
                    <span>C <b id="val-close">--</b></span>
                    <span id="val-change" style="font-weight:700;">--</span>
                    <span>Vol: <b id="val-vol" style="color:#38bdf8;">--</b></span>
                </div>
            </div>

            <!-- CHỈ BÁO NẰM TRÊN CHART CHÍNH: MA, EMA, BOLL -->
            <div class="ind-main-row" id="ind-main-row">
                <span class="badge-val" id="stat-ma20" style="color: #f59e0b;">MA 20: <b>--</b></span>
                <span class="badge-val" id="stat-ma50" style="color: #3b82f6;">MA 50: <b>--</b></span>
                <span class="badge-val" id="stat-ema9" style="color: #10b981; display: none;">EMA 9: <b>--</b></span>
                <span class="badge-val" id="stat-ema21" style="color: #ec4899; display: none;">EMA 21: <b>--</b></span>
                <span class="badge-val" id="stat-boll" style="color: #38bdf8; display: none;">BOLL(20,2): Up <b>--</b> Mid <b>--</b> Low <b>--</b></span>
            </div>
        </div>

        <!-- KHU VỰC CHỨA 2 KHUNG ĐỒ THỊ -->
        <div class="charts-wrapper">
            <!-- 1. BIỂU ĐỒ NẾN CHÍNH -->
            <div id="tv-chart-main"></div>

            <!-- 2. BẢNG PHỤ CHO CHỈ BÁO RSI VÀ MACD (SUB-PANEL RIÊNG BIỆT) -->
            <div class="tv-sub-panel" id="tv-sub-panel">
                <div class="sub-header" id="sub-header-content">
                    <!-- TIÊU ĐỀ SỐ LIỆU ĐỘNG SẼ ĐƯỢC CHÈN BẰNG JS -->
                </div>
                <div id="tv-chart-sub"></div>
            </div>
        </div>

        <!-- THANH CÔNG CỤ ĐÁY BẬT TẮT -->
        <div class="tv-bottom-toolbar">
            <button class="btn-ind active" id="btn-ma">MA</button>
            <button class="btn-ind" id="btn-ema">EMA</button>
            <button class="btn-ind" id="btn-macd">MACD</button>
            <button class="btn-ind active" id="btn-rsi">RSI</button>
            <button class="btn-ind" id="btn-boll">BOLL</button>
        </div>

        <script>
            const mainContainer = document.getElementById('tv-chart-main');
            const subContainer = document.getElementById('tv-chart-sub');
            const subPanel = document.getElementById('tv-sub-panel');
            const subHeader = document.getElementById('sub-header-content');

            // --- 1. KHỞI TẠO BIỂU ĐỒ CHÍNH (MAIN CHART) ---
            const chartMain = LightweightCharts.createChart(mainContainer, {{
                width: mainContainer.clientWidth,
                height: mainContainer.clientHeight,
                layout: {{ background: {{ color: '#131722' }}, textColor: '#d1d4dc' }},
                grid: {{ vertLines: {{ color: 'rgba(42, 46, 57, 0.35)' }}, horzLines: {{ color: 'rgba(42, 46, 57, 0.35)' }} }},
                crosshair: {{ mode: LightweightCharts.CrosshairMode.Normal }},
                rightPriceScale: {{
                    borderColor: '#2a2e39',
                    scaleMargins: {{ top: 0.08, bottom: 0.22 }},
                }},
                timeScale: {{
                    borderColor: '#2a2e39',
                    timeVisible: false,
                    secondsVisible: false,
                }},
                localization: {{ dateFormat: 'yyyy-MM-dd' }},
            }});

            const candleSeries = chartMain.addCandlestickSeries({{
                upColor: '#089981', downColor: '#F23645',
                borderVisible: false, wickUpColor: '#089981', wickDownColor: '#F23645',
            }});

            const volumeSeries = chartMain.addHistogramSeries({{
                priceFormat: {{ type: 'volume' }},
                priceScaleId: '',
            }});
            volumeSeries.priceScale().applyOptions({{
                scaleMargins: {{ top: 0.8, bottom: 0 }},
            }});

            // Chỉ báo đường trên biểu đồ chính
            const ma20 = chartMain.addLineSeries({{ color: '#f59e0b', lineWidth: 1.5, title: 'MA 20', visible: true }});
            const ma50 = chartMain.addLineSeries({{ color: '#3b82f6', lineWidth: 1.5, title: 'MA 50', visible: true }});
            const ema9 = chartMain.addLineSeries({{ color: '#10b981', lineWidth: 1.5, title: 'EMA 9', visible: false }});
            const ema21 = chartMain.addLineSeries({{ color: '#ec4899', lineWidth: 1.5, title: 'EMA 21', visible: false }});

            const bollUpper = chartMain.addLineSeries({{ color: 'rgba(56, 189, 248, 0.7)', lineWidth: 1, title: 'BOLL Up', visible: false }});
            const bollMid = chartMain.addLineSeries({{ color: 'rgba(56, 189, 248, 0.85)', lineWidth: 1, lineStyle: 2, title: 'BOLL Mid', visible: false }});
            const bollLower = chartMain.addLineSeries({{ color: 'rgba(56, 189, 248, 0.7)', lineWidth: 1, title: 'BOLL Low', visible: false }});

            // --- 2. KHỞI TẠO BIỂU ĐỒ PHỤ (SUB-PANEL CHART DÀNH CHO RSI & MACD) ---
            const chartSub = LightweightCharts.createChart(subContainer, {{
                width: subContainer.clientWidth,
                height: subContainer.clientHeight,
                layout: {{ background: {{ color: '#131722' }}, textColor: '#d1d4dc' }},
                grid: {{ vertLines: {{ color: 'rgba(42, 46, 57, 0.25)' }}, horzLines: {{ color: 'rgba(42, 46, 57, 0.25)' }} }},
                crosshair: {{ mode: LightweightCharts.CrosshairMode.Normal }},
                rightPriceScale: {{
                    borderColor: '#2a2e39',
                    scaleMargins: {{ top: 0.1, bottom: 0.1 }},
                }},
                timeScale: {{
                    borderColor: '#2a2e39',
                    timeVisible: false,
                    secondsVisible: false,
                }},
                localization: {{ dateFormat: 'yyyy-MM-dd' }},
            }});

            // Series của RSI trong Sub-Chart
            const rsiSeries = chartSub.addLineSeries({{ color: '#a855f7', lineWidth: 1.8, title: 'RSI(14)', visible: true }});
            const rsiUp = chartSub.addLineSeries({{ color: '#ef4444', lineWidth: 1, lineStyle: 2, title: '70', visible: true }});
            const rsiDown = chartSub.addLineSeries({{ color: '#22c55e', lineWidth: 1, lineStyle: 2, title: '30', visible: true }});

            // Series của MACD trong Sub-Chart
            const macdLine = chartSub.addLineSeries({{ color: '#38bdf8', lineWidth: 1.5, title: 'MACD', visible: false }});
            const macdSignal = chartSub.addLineSeries({{ color: '#f97316', lineWidth: 1.5, title: 'Signal', visible: false }});
            const macdHist = chartSub.addHistogramSeries({{ title: 'Hist', visible: false }});

            // ĐỒNG BỘ TRỤC THỜI GIAN GIỮA CHART CHÍNH VÀ CHART PHỤ (SYNC TIME AXIS)
            let isSyncingRange = false;
            chartMain.timeScale().subscribeVisibleLogicalRangeChange(range => {{
                if (isSyncingRange || !range || !subPanel.style.display || subPanel.style.display === 'none') return;
                isSyncingRange = true;
                chartSub.timeScale().setVisibleLogicalRange(range);
                isSyncingRange = false;
            }});

            chartSub.timeScale().subscribeVisibleLogicalRangeChange(range => {{
                if (isSyncingRange || !range) return;
                isSyncingRange = true;
                chartMain.timeScale().setVisibleLogicalRange(range);
                isSyncingRange = false;
            }});

            const rawCandleData = {candle_json};
            const rawVolumeData = {volume_json};

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

            // HÀM RESAMPLE CHỈ CHO CÁC KHUNG THỜI GIAN THẬT: 1D, 1W, 1M
            function resampleData(tf) {{
                if (tf === '1D') {{
                    return {{ candles: rawCandleData, volumes: rawVolumeData }};
                }}
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
                        wVols.push({{
                            time: mon,
                            value: vol,
                            color: isUp ? 'rgba(8, 153, 129, 0.45)' : 'rgba(242, 54, 69, 0.45)'
                        }});
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
                        mVols.push({{
                            time: mKey,
                            value: vol,
                            color: isUp ? 'rgba(8, 153, 129, 0.45)' : 'rgba(242, 54, 69, 0.45)'
                        }});
                    }});
                    return {{ candles: mCandles, volumes: mVols }};
                }}
                return {{ candles: rawCandleData, volumes: rawVolumeData }};
            }}

            let currentCandles = [];
            let currentVolumes = [];
            let currentMA20 = [], currentMA50 = [];
            let currentEMA9 = [], currentEMA21 = [];
            let currentBOLL = {{ upper: [], mid: [], lower: [] }};
            let currentRSI = [];
            let currentMACD = {{ mLine: [], sLine: [], hList: [] }};

            let isMA = true;
            let isEMA = false;
            let isBOLL = false;
            let isRSI = true;
            let isMACD = false;

            function formatVolume(val) {{
                if (val === undefined || val === null) return '--';
                if (val >= 1e9) return (val / 1e9).toFixed(2) + 'B';
                if (val >= 1e6) return (val / 1e6).toFixed(2) + 'M';
                if (val >= 1e3) return (val / 1e3).toFixed(1) + 'K';
                return val.toString();
            }}

            // Cập nhật thông số nến trên Main Header
            function updateMainHeader(c, v, m20Val, m50Val, e9Val, e21Val, bUp, bMid, bLow) {{
                if (c) {{
                    const o = c.open, h = c.high, l = c.low, cl = c.close;
                    const diff = cl - o;
                    const pct = (diff / o) * 100;
                    const isUp = cl >= o;
                    const col = isUp ? '#089981' : '#F23645';

                    document.getElementById('val-open').innerText = o.toFixed(2);
                    document.getElementById('val-high').innerText = h.toFixed(2);
                    document.getElementById('val-low').innerText = l.toFixed(2);
                    
                    const closeEl = document.getElementById('val-close');
                    closeEl.innerText = cl.toFixed(2);
                    closeEl.style.color = col;

                    const chgEl = document.getElementById('val-change');
                    chgEl.innerText = `${{diff >= 0 ? '+' : ''}}${{diff.toFixed(2)}} (${{diff >= 0 ? '+' : ''}}${{pct.toFixed(2)}}%)`;
                    chgEl.style.color = col;
                }}
                if (v !== undefined && v !== null) {{
                    const volVal = typeof v === 'object' ? v.value : v;
                    document.getElementById('val-vol').innerText = formatVolume(volVal);
                }}

                if (m20Val !== undefined) document.querySelector('#stat-ma20 b').innerText = (m20Val.value ?? m20Val ?? '--');
                if (m50Val !== undefined) document.querySelector('#stat-ma50 b').innerText = (m50Val.value ?? m50Val ?? '--');
                if (e9Val !== undefined) document.querySelector('#stat-ema9 b').innerText = (e9Val.value ?? e9Val ?? '--');
                if (e21Val !== undefined) document.querySelector('#stat-ema21 b').innerText = (e21Val.value ?? e21Val ?? '--');

                if (bUp !== undefined && bMid !== undefined && bLow !== undefined) {{
                    const bUpV = bUp.value ?? bUp ?? '--';
                    const bMidV = bMid.value ?? bMid ?? '--';
                    const bLowV = bLow.value ?? bLow ?? '--';
                    document.getElementById('stat-boll').innerHTML = `BOLL(20,2): Up <b>${{bUpV}}</b> Mid <b>${{bMidV}}</b> Low <b>${{bLowV}}</b>`;
                }}
            }}

            // Cập nhật thông số bảng phụ (Sub-header) cho RSI và MACD
            function updateSubHeader(rsiVal, mLine, mSig, mHist) {{
                let html = '';
                if (isRSI) {{
                    const rVal = rsiVal !== undefined ? (rsiVal.value ?? rsiVal ?? '--') : '--';
                    html += `<span><span style="color:#f8fafc; font-weight:700;">RSI</span> <span style="color:#94a3b8;">14</span> <b style="color:#a855f7;">${{rVal}}</b></span>`;
                }}
                if (isMACD) {{
                    const mVal = mLine !== undefined ? (mLine.value ?? mLine ?? 0) : 0;
                    const sVal = mSig !== undefined ? (mSig.value ?? mSig ?? 0) : 0;
                    const hVal = mHist !== undefined ? (mHist.value ?? mHist ?? 0) : 0;
                    const hColor = (typeof hVal === 'number' && hVal >= 0) ? '#22c55e' : '#ef4444';
                    html += `<span><span style="color:#f8fafc; font-weight:700;">MACD</span> <span style="color:#94a3b8;">12 26 9</span> MACD: <b style="color:#38bdf8;">${{typeof mVal === 'number' ? mVal.toFixed(2) : mVal}}</b> Signal: <b style="color:#f97316;">${{typeof sVal === 'number' ? sVal.toFixed(2) : sVal}}</b> Hist: <b style="color:${{hColor}};">${{typeof hVal === 'number' ? (hVal >= 0 ? '+' : '') + hVal.toFixed(2) : hVal}}</b></span>`;
                }}
                subHeader.innerHTML = html;
            }}

            function setLatestValues() {{
                if (currentCandles.length === 0) return;
                const lastIdx = currentCandles.length - 1;
                const c = currentCandles[lastIdx];
                const v = currentVolumes[lastIdx];
                const m20 = currentMA20[currentMA20.length - 1];
                const m50 = currentMA50[currentMA50.length - 1];
                const e9 = currentEMA9[currentEMA9.length - 1];
                const e21 = currentEMA21[currentEMA21.length - 1];
                const bUp = currentBOLL.upper[currentBOLL.upper.length - 1];
                const bMid = currentBOLL.mid[currentBOLL.mid.length - 1];
                const bLow = currentBOLL.lower[currentBOLL.lower.length - 1];
                const rsi = currentRSI[currentRSI.length - 1];
                const mLine = currentMACD.mLine[currentMACD.mLine.length - 1];
                const mSig = currentMACD.sLine[currentMACD.sLine.length - 1];
                const mHist = currentMACD.hList[currentMACD.hList.length - 1];

                updateMainHeader(c, v, m20, m50, e9, e21, bUp, bMid, bLow);
                updateSubHeader(rsi, mLine, mSig, mHist);
            }}

            function syncSubPanelVisibility() {{
                const showSub = isRSI || isMACD;
                subPanel.style.display = showSub ? 'flex' : 'none';

                rsiSeries.applyOptions({{ visible: isRSI }});
                rsiUp.applyOptions({{ visible: isRSI }});
                rsiDown.applyOptions({{ visible: isRSI }});

                macdLine.applyOptions({{ visible: isMACD }});
                macdSignal.applyOptions({{ visible: isMACD }});
                macdHist.applyOptions({{ visible: isMACD }});

                // Cập nhật lại kích thước canvas của 2 biểu đồ
                setTimeout(() => {{
                    chartMain.resize(mainContainer.clientWidth, mainContainer.clientHeight);
                    if (showSub) {{
                        chartSub.resize(subContainer.clientWidth, subContainer.clientHeight);
                        chartSub.timeScale().setVisibleLogicalRange(chartMain.timeScale().getVisibleLogicalRange());
                    }}
                }}, 30);
                setLatestValues();
            }}

            function applyDataset(resampled) {{
                currentCandles = resampled.candles;
                currentVolumes = resampled.volumes;

                candleSeries.setData(currentCandles);
                volumeSeries.setData(currentVolumes);

                if (currentCandles.length > 0) {{
                    currentMA20 = calculateSMA(currentCandles, 20);
                    currentMA50 = calculateSMA(currentCandles, 50);
                    ma20.setData(currentMA20);
                    ma50.setData(currentMA50);

                    currentEMA9 = calculateEMA(currentCandles, 9);
                    currentEMA21 = calculateEMA(currentCandles, 21);
                    ema9.setData(currentEMA9);
                    ema21.setData(currentEMA21);

                    currentBOLL = calculateBOLL(currentCandles);
                    bollUpper.setData(currentBOLL.upper);
                    bollMid.setData(currentBOLL.mid);
                    bollLower.setData(currentBOLL.lower);

                    // RSI & MACD trên Sub-Chart
                    currentRSI = calculateRSI(currentCandles);
                    rsiSeries.setData(currentRSI);
                    rsiUp.setData(currentRSI.map(d => ({{ time: d.time, value: 70 }})));
                    rsiDown.setData(currentRSI.map(d => ({{ time: d.time, value: 30 }})));

                    currentMACD = calculateMACD(currentCandles);
                    macdLine.setData(currentMACD.mLine);
                    macdSignal.setData(currentMACD.sLine);
                    macdHist.setData(currentMACD.hList);

                    setLatestValues();
                }}
                chartMain.timeScale().fitContent();
                chartSub.timeScale().fitContent();
            }}

            applyDataset(resampleData('1D'));
            syncSubPanelVisibility();

            // --- LẮNG NGHE SỰ KIỆN RÊ CHUỘT TRÊN BIỂU ĐỒ CHÍNH ---
            chartMain.subscribeCrosshairMove(param => {{
                if (!param || !param.time || param.point === undefined || !param.seriesData) {{
                    setLatestValues();
                    return;
                }}
                const c = param.seriesData.get(candleSeries);
                const v = param.seriesData.get(volumeSeries);
                const m20Val = param.seriesData.get(ma20);
                const m50Val = param.seriesData.get(ma50);
                const e9Val = param.seriesData.get(ema9);
                const e21Val = param.seriesData.get(ema21);
                const bUpVal = param.seriesData.get(bollUpper);
                const bMidVal = param.seriesData.get(bollMid);
                const bLowVal = param.seriesData.get(bollLower);

                // Lấy số liệu RSI/MACD tại thời điểm ngày đó
                const t = param.time;
                const rsiItem = currentRSI.find(item => item.time === t);
                const mLineItem = currentMACD.mLine.find(item => item.time === t);
                const mSigItem = currentMACD.sLine.find(item => item.time === t);
                const mHistItem = currentMACD.hList.find(item => item.time === t);

                updateMainHeader(c, v, m20Val, m50Val, e9Val, e21Val, bUpVal, bMidVal, bLowVal);
                updateSubHeader(rsiItem, mLineItem, mSigItem, mHistItem);
            }});

            // --- LẮNG NGHE SỰ KIỆN RÊ CHUỘT TRÊN BIỂU ĐỒ PHỤ ---
            chartSub.subscribeCrosshairMove(param => {{
                if (!param || !param.time || param.point === undefined || !param.seriesData) {{
                    setLatestValues();
                    return;
                }}
                const t = param.time;
                const cItem = currentCandles.find(item => item.time === t);
                const vItem = currentVolumes.find(item => item.time === t);
                const m20Item = currentMA20.find(item => item.time === t);
                const m50Item = currentMA50.find(item => item.time === t);
                const e9Item = currentEMA9.find(item => item.time === t);
                const e21Item = currentEMA21.find(item => item.time === t);

                const rsiVal = param.seriesData.get(rsiSeries);
                const mLineVal = param.seriesData.get(macdLine);
                const mSigVal = param.seriesData.get(macdSignal);
                const mHistVal = param.seriesData.get(macdHist);

                updateMainHeader(cItem, vItem, m20Item, m50Item, e9Item, e21Item);
                updateSubHeader(rsiVal, mLineVal, mSigVal, mHistVal);
            }});

            // DROPDOWN CHỌN KHUNG THỜI GIAN
            const tfBtn = document.getElementById('tf-btn');
            const tfMenu = document.getElementById('tf-menu');
            const tfLabel = document.getElementById('tf-label');

            tfBtn.addEventListener('click', (e) => {{
                e.stopPropagation();
                tfMenu.classList.toggle('show');
            }});

            document.addEventListener('click', () => {{
                tfMenu.classList.remove('show');
            }});

            document.querySelectorAll('.tf-item').forEach(item => {{
                item.addEventListener('click', function(e) {{
                    e.stopPropagation();
                    document.querySelectorAll('.tf-item').forEach(el => el.classList.remove('active'));
                    this.classList.add('active');
                    
                    const tf = this.getAttribute('data-tf');
                    tfLabel.innerText = this.innerText.trim();
                    tfMenu.classList.remove('show');
                    
                    const resampled = resampleData(tf);
                    applyDataset(resampled);
                }});
            }});

            // TOOLBAR BẬT TẮT CHỈ BÁO
            document.getElementById('btn-ma').addEventListener('click', function() {{
                isMA = !isMA;
                ma20.applyOptions({{ visible: isMA }});
                ma50.applyOptions({{ visible: isMA }});
                document.getElementById('stat-ma20').style.display = isMA ? 'inline-flex' : 'none';
                document.getElementById('stat-ma50').style.display = isMA ? 'inline-flex' : 'none';
                this.classList.toggle('active', isMA);
            }});

            document.getElementById('btn-ema').addEventListener('click', function() {{
                isEMA = !isEMA;
                ema9.applyOptions({{ visible: isEMA }});
                ema21.applyOptions({{ visible: isEMA }});
                document.getElementById('stat-ema9').style.display = isEMA ? 'inline-flex' : 'none';
                document.getElementById('stat-ema21').style.display = isEMA ? 'inline-flex' : 'none';
                this.classList.toggle('active', isEMA);
            }});

            document.getElementById('btn-boll').addEventListener('click', function() {{
                isBOLL = !isBOLL;
                bollUpper.applyOptions({{ visible: isBOLL }});
                bollMid.applyOptions({{ visible: isBOLL }});
                bollLower.applyOptions({{ visible: isBOLL }});
                document.getElementById('stat-boll').style.display = isBOLL ? 'inline-flex' : 'none';
                this.classList.toggle('active', isBOLL);
            }});

            document.getElementById('btn-rsi').addEventListener('click', function() {{
                isRSI = !isRSI;
                this.classList.toggle('active', isRSI);
                syncSubPanelVisibility();
            }});

            document.getElementById('btn-macd').addEventListener('click', function() {{
                isMACD = !isMACD;
                this.classList.toggle('active', isMACD);
                syncSubPanelVisibility();
            }});

            window.addEventListener('resize', () => {{
                chartMain.resize(mainContainer.clientWidth, mainContainer.clientHeight);
                if (isRSI || isMACD) {{
                    chartSub.resize(subContainer.clientWidth, subContainer.clientHeight);
                }}
            }});
        </script>
    </body>
    </html>
    """
    return html
