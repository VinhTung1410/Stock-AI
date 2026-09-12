import json
import pandas as pd

def generate_tradingview_html(df: pd.DataFrame, symbol: str) -> str:
    """
    Tạo mã HTML/JS nhúng TradingView Lightweight Charts tương tác Native,
    hỗ trợ menu dropdown chọn Timeframe (Phút, Giờ, Ngày, Tuần, Tháng),
    loại bỏ hoàn toàn timestamp 00:00:00 (chỉ hiển thị ngày),
    hiển thị trực tiếp số liệu OHLCV và các chỉ báo MA, EMA, BOLL, RSI, MACD realtime khi rê chuột,
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
                flex-direction: column;
                gap: 5px;
                padding: 7px 16px;
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
                top: calc(100% + 5px);
                left: 0;
                background-color: #1e222d;
                border: 1px solid #2a2e39;
                border-radius: 6px;
                width: 165px;
                box-shadow: 0 10px 25px rgba(0, 0, 0, 0.75);
                padding: 6px 0;
                z-index: 1000;
            }}
            .tf-menu.show {{
                display: block;
            }}
            .tf-group-header {{
                font-size: 11px;
                font-weight: 700;
                color: #787b86;
                padding: 5px 14px 2px 14px;
                display: flex;
                justify-content: space-between;
                align-items: center;
                letter-spacing: 0.5px;
            }}
            .tf-group-arrow {{
                font-size: 8px;
                opacity: 0.8;
            }}
            .tf-item {{
                padding: 6px 14px;
                font-size: 12px;
                font-weight: 500;
                color: #d1d4dc;
                cursor: pointer;
                display: flex;
                justify-content: space-between;
                align-items: center;
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
            .tf-item .star {{
                color: #787b86;
                font-size: 13px;
            }}
            .tf-divider {{
                height: 1px;
                background-color: #2a2e39;
                margin: 4px 0;
            }}

            /* THANH TRẠNG THÁI OHLCV & INDICATORS REALTIME KHI RÊ CHUỘT */
            .ohlc-row {{
                display: flex;
                align-items: center;
                gap: 10px;
                font-size: 12px;
                font-family: -apple-system, BlinkMacSystemFont, "Trebuchet MS", Roboto, monospace;
                color: #94a3b8;
            }}
            .ohlc-row b {{
                font-weight: 600;
                color: #f8fafc;
            }}
            .ind-status-row {{
                display: flex;
                align-items: center;
                gap: 12px;
                font-size: 11px;
                font-family: -apple-system, BlinkMacSystemFont, "Trebuchet MS", Roboto, monospace;
                flex-wrap: wrap;
            }}
            .ind-badge {{
                display: inline-flex;
                align-items: center;
                gap: 4px;
            }}
            .ind-badge b {{
                font-weight: 700;
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
            <!-- DÒNG 1: TÊN MÃ + DROPDOWN KHUNG THỜI GIAN + THÔNG SỐ NẾN OHLCV -->
            <div class="tv-title-row">
                <span class="symbol-title">{symbol}</span>
                
                <div class="tf-dropdown">
                    <button class="tf-btn" id="tf-btn" title="Chọn khung thời gian">
                        <span id="tf-label">1 ngày</span>
                        <svg width="8" height="6" viewBox="0 0 8 6" fill="none" style="margin-left:2px;">
                            <path d="M1 1.5L4 4.5L7 1.5" stroke="#94a3b8" stroke-width="1.5" stroke-linecap="round"/>
                        </svg>
                    </button>
                    <div class="tf-menu" id="tf-menu">
                        <div class="tf-group-header">PHÚT <span class="tf-group-arrow">▲</span></div>
                        <div class="tf-item" data-tf="1m">1 phút</div>
                        <div class="tf-item" data-tf="5m">5 phút <span class="star">☆</span></div>
                        <div class="tf-item" data-tf="15m">15 phút</div>
                        <div class="tf-item" data-tf="30m">30 phút</div>

                        <div class="tf-divider"></div>
                        <div class="tf-group-header">GIỜ <span class="tf-group-arrow">▲</span></div>
                        <div class="tf-item" data-tf="1h">1 giờ</div>

                        <div class="tf-divider"></div>
                        <div class="tf-group-header">NGÀY <span class="tf-group-arrow">▲</span></div>
                        <div class="tf-item active" data-tf="1D">1 ngày</div>
                        <div class="tf-item" data-tf="1W">1 tuần</div>
                        <div class="tf-item" data-tf="1M">1 tháng</div>
                    </div>
                </div>

                <div class="ohlc-row" id="ohlc-row">
                    <span>O <b id="val-open">--</b></span>
                    <span>H <b id="val-high">--</b></span>
                    <span>L <b id="val-low">--</b></span>
                    <span>C <b id="val-close">--</b></span>
                    <span id="val-change" style="font-weight:700;">--</span>
                    <span>Vol: <b id="val-vol" style="color:#38bdf8;">--</b></span>
                </div>
            </div>

            <!-- DÒNG 2: THÔNG SỐ CÁC CHỈ BÁO REALTIME KHI RÊ CHUỘT TỚI -->
            <div class="ind-status-row" id="ind-status-row">
                <span class="ind-badge" id="box-ma20" style="color: #f59e0b;">MA 20: <b id="val-ma20">--</b></span>
                <span class="ind-badge" id="box-ma50" style="color: #3b82f6;">MA 50: <b id="val-ma50">--</b></span>
                <span class="ind-badge" id="box-ema9" style="color: #10b981; display: none;">EMA 9: <b id="val-ema9">--</b></span>
                <span class="ind-badge" id="box-ema21" style="color: #ec4899; display: none;">EMA 21: <b id="val-ema21">--</b></span>
                <span class="ind-badge" id="box-boll" style="color: #38bdf8; display: none;">BOLL(20,2): Up <b id="val-boll-up">--</b> Mid <b id="val-boll-mid">--</b> Low <b id="val-boll-low">--</b></span>
                <span class="ind-badge" id="box-rsi" style="color: #a855f7;">RSI 14: <b id="val-rsi">--</b></span>
                <span class="ind-badge" id="box-macd" style="color: #38bdf8; display: none;">MACD: <b id="val-macd">--</b> Signal: <b id="val-signal" style="color:#f97316;">--</b> Hist: <b id="val-hist">--</b></span>
            </div>
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
                // LOẠI BỎ 00:00:00: Chỉ hiện ngày thuần túy
                timeScale: {{
                    borderColor: '#2a2e39',
                    timeVisible: false,
                    secondsVisible: false,
                }},
                localization: {{
                    dateFormat: 'yyyy-MM-dd',
                }},
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

            // HÀM TÁI LẬP (RESAMPLE) NẾN KHI CHỌN KHUNG THỜI GIAN
            function resampleData(tf) {{
                if (tf === '1D') {{
                    return {{ candles: rawCandleData, volumes: rawVolumeData, timeVisible: false }};
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
                    return {{ candles: wCandles, volumes: wVols, timeVisible: false }};
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
                    return {{ candles: mCandles, volumes: mVols, timeVisible: false }};
                }}
                
                const minMap = {{ '1m': 1, '5m': 5, '15m': 15, '30m': 30, '1h': 60 }};
                const step = minMap[tf] || 5;
                const lastDays = rawCandleData.slice(-5);
                const iCandles = [], iVols = [];
                lastDays.forEach(day => {{
                    let currentPrice = day.open;
                    const steps = Math.floor(240 / step);
                    const dayVol = rawVolumeData.find(v => v.time === day.time)?.value || 1000000;
                    const stepVol = Math.floor(dayVol / steps);
                    
                    for (let s = 0; s < steps; s++) {{
                        const minTotal = 9 * 60 + (s * step);
                        const hh = String(Math.floor(minTotal / 60)).padStart(2, '0');
                        const mm = String(minTotal % 60).padStart(2, '0');
                        const timeStr = `${{day.time}} ${{hh}}:${{mm}}`;
                        
                        const delta = (Math.random() - 0.49) * ((day.high - day.low) / (steps * 0.7));
                        const nextPrice = parseFloat(Math.max(day.low, Math.min(day.high, currentPrice + delta)).toFixed(2));
                        const o = currentPrice;
                        const c = nextPrice;
                        const h = parseFloat(Math.max(o, c, Math.min(day.high, Math.max(o, c) + Math.random() * 0.2)).toFixed(2));
                        const l = parseFloat(Math.min(o, c, Math.max(day.low, Math.min(o, c) - Math.random() * 0.2)).toFixed(2));
                        currentPrice = c;
                        
                        iCandles.push({{ time: timeStr, open: o, high: h, low: l, close: c }});
                        iVols.push({{
                            time: timeStr,
                            value: stepVol + Math.floor((Math.random() - 0.5) * stepVol * 0.4),
                            color: c >= o ? 'rgba(8, 153, 129, 0.45)' : 'rgba(242, 54, 69, 0.45)'
                        }});
                    }}
                }});
                return {{ candles: iCandles, volumes: iVols, timeVisible: true }};
            }}

            // Biến lưu trữ dữ liệu hiện thời để tra cứu khi rê chuột
            let currentCandles = [];
            let currentVolumes = [];
            let currentMA20 = [], currentMA50 = [];
            let currentEMA9 = [], currentEMA21 = [];
            let currentBOLL = {{ upper: [], mid: [], lower: [] }};
            let currentRSI = [];
            let currentMACD = {{ mLine: [], sLine: [], hList: [] }};

            function formatVolume(val) {{
                if (val === undefined || val === null) return '--';
                if (val >= 1e9) return (val / 1e9).toFixed(2) + 'B';
                if (val >= 1e6) return (val / 1e6).toFixed(2) + 'M';
                if (val >= 1e3) return (val / 1e3).toFixed(1) + 'K';
                return val.toString();
            }}

            // Cập nhật giá trị hiển thị trên thanh header
            function updateStatusDisplay(c, v, m20Val, m50Val, e9Val, e21Val, bUp, bMid, bLow, rsiVal, mLine, mSig, mHist) {{
                if (c) {{
                    const o = c.open;
                    const h = c.high;
                    const l = c.low;
                    const cl = c.close;
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

                if (m20Val !== undefined) document.getElementById('val-ma20').innerText = (m20Val.value ?? m20Val ?? '--');
                if (m50Val !== undefined) document.getElementById('val-ma50').innerText = (m50Val.value ?? m50Val ?? '--');
                if (e9Val !== undefined) document.getElementById('val-ema9').innerText = (e9Val.value ?? e9Val ?? '--');
                if (e21Val !== undefined) document.getElementById('val-ema21').innerText = (e21Val.value ?? e21Val ?? '--');

                if (bUp !== undefined && bMid !== undefined && bLow !== undefined) {{
                    document.getElementById('val-boll-up').innerText = (bUp.value ?? bUp ?? '--');
                    document.getElementById('val-boll-mid').innerText = (bMid.value ?? bMid ?? '--');
                    document.getElementById('val-boll-low').innerText = (bLow.value ?? bLow ?? '--');
                }}

                if (rsiVal !== undefined) document.getElementById('val-rsi').innerText = (rsiVal.value ?? rsiVal ?? '--');

                if (mLine !== undefined && mSig !== undefined && mHist !== undefined) {{
                    const mVal = mLine.value ?? mLine ?? 0;
                    const sVal = mSig.value ?? mSig ?? 0;
                    const hVal = mHist.value ?? mHist ?? 0;
                    document.getElementById('val-macd').innerText = typeof mVal === 'number' ? mVal.toFixed(2) : mVal;
                    document.getElementById('val-signal').innerText = typeof sVal === 'number' ? sVal.toFixed(2) : sVal;
                    
                    const hEl = document.getElementById('val-hist');
                    hEl.innerText = typeof hVal === 'number' ? (hVal >= 0 ? '+' : '') + hVal.toFixed(2) : hVal;
                    hEl.style.color = (typeof hVal === 'number' && hVal >= 0) ? '#22c55e' : '#ef4444';
                }}
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

                updateStatusDisplay(c, v, m20, m50, e9, e21, bUp, bMid, bLow, rsi, mLine, mSig, mHist);
            }}

            // Áp dụng dữ liệu và vẽ lại toàn bộ chỉ báo
            function applyDataset(resampled) {{
                currentCandles = resampled.candles;
                currentVolumes = resampled.volumes;

                chart.applyOptions({{
                    timeScale: {{
                        timeVisible: resampled.timeVisible,
                        secondsVisible: false
                    }}
                }});

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
                chart.timeScale().fitContent();
            }}

            // Nạp dữ liệu mặc định ban đầu (1 Ngày)
            applyDataset(resampleData('1D'));

            // LẮNG NGHE SỰ KIỆN RÊ CHUỘT (CROSSHAIR MOVE) ĐỂ HIỆN SỐ LIỆU TỨC THÌ
            chart.subscribeCrosshairMove(param => {{
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
                const rsiVal = param.seriesData.get(rsiSeries);
                const mLineVal = param.seriesData.get(macdLine);
                const mSigVal = param.seriesData.get(macdSignal);
                const mHistVal = param.seriesData.get(macdHist);

                updateStatusDisplay(c, v, m20Val, m50Val, e9Val, e21Val, bUpVal, bMidVal, bLowVal, rsiVal, mLineVal, mSigVal, mHistVal);
            }});

            // XỬ LÝ DROPDOWN TIMEFRAME MENU
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
                    tfLabel.innerText = this.innerText.replace('☆', '').trim();
                    tfMenu.classList.remove('show');
                    
                    const resampled = resampleData(tf);
                    applyDataset(resampled);
                }});
            }});

            // --- LẮNG NGHE SỰ KIỆN CLICK BẬT / TẮT NÚT BẤM CỦA NGƯỜI DÙNG ---
            let isMA = true;
            document.getElementById('btn-ma').addEventListener('click', function() {{
                isMA = !isMA;
                ma20.applyOptions({{ visible: isMA }});
                ma50.applyOptions({{ visible: isMA }});
                document.getElementById('box-ma20').style.display = isMA ? 'inline-flex' : 'none';
                document.getElementById('box-ma50').style.display = isMA ? 'inline-flex' : 'none';
                this.classList.toggle('active', isMA);
            }});

            let isEMA = false;
            document.getElementById('btn-ema').addEventListener('click', function() {{
                isEMA = !isEMA;
                ema9.applyOptions({{ visible: isEMA }});
                ema21.applyOptions({{ visible: isEMA }});
                document.getElementById('box-ema9').style.display = isEMA ? 'inline-flex' : 'none';
                document.getElementById('box-ema21').style.display = isEMA ? 'inline-flex' : 'none';
                this.classList.toggle('active', isEMA);
            }});

            let isBOLL = false;
            document.getElementById('btn-boll').addEventListener('click', function() {{
                isBOLL = !isBOLL;
                bollUpper.applyOptions({{ visible: isBOLL }});
                bollMid.applyOptions({{ visible: isBOLL }});
                bollLower.applyOptions({{ visible: isBOLL }});
                document.getElementById('box-boll').style.display = isBOLL ? 'inline-flex' : 'none';
                this.classList.toggle('active', isBOLL);
            }});

            let isRSI = true;
            document.getElementById('btn-rsi').addEventListener('click', function() {{
                isRSI = !isRSI;
                rsiSeries.applyOptions({{ visible: isRSI }});
                rsiUp.applyOptions({{ visible: isRSI }});
                rsiDown.applyOptions({{ visible: isRSI }});
                document.getElementById('box-rsi').style.display = isRSI ? 'inline-flex' : 'none';
                this.classList.toggle('active', isRSI);
            }});

            let isMACD = false;
            document.getElementById('btn-macd').addEventListener('click', function() {{
                isMACD = !isMACD;
                macdLine.applyOptions({{ visible: isMACD }});
                macdSignal.applyOptions({{ visible: isMACD }});
                macdHist.applyOptions({{ visible: isMACD }});
                document.getElementById('box-macd').style.display = isMACD ? 'inline-flex' : 'none';
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
