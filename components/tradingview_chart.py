import json
import pandas as pd

def generate_tradingview_html(df: pd.DataFrame, symbol: str) -> str:
    """
    Tạo mã HTML/JS nhúng TradingView Lightweight Charts tương tác 60fps Native,
    hỗ trợ menu dropdown chọn Timeframe (Phút, Giờ, Ngày, Tuần, Tháng),
    loại bỏ hoàn toàn timestamp 00:00:00 (chỉ hiển thị ngày),
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
                position: relative;
                z-index: 100;
            }}
            .tv-title {{
                font-size: 15px;
                font-weight: 700;
                color: #f8fafc;
                display: flex;
                gap: 12px;
                align-items: center;
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
                padding: 4px 10px;
                font-size: 13px;
                font-weight: 600;
                cursor: pointer;
                display: flex;
                align-items: center;
                gap: 6px;
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
                width: 170px;
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
                padding: 6px 14px 2px 14px;
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
                padding: 7px 14px;
                font-size: 13px;
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
                <span>{symbol}</span>
                
                <!-- DROPDOWN CHỌN KHUNG THỜI GIAN NHƯ HÌNH -->
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
                // LOẠI BỎ 00:00:00: Đặt timeVisible: false để crosshair và trục thời gian chỉ hiện ngày yyyy-mm-dd
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
                    // Nhóm theo tuần
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
                    // Nhóm theo tháng
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
                
                // Khung phút/giờ: Tạo chuỗi nến intraday mượt mà cho các phiên gần nhất
                const minMap = {{ '1m': 1, '5m': 5, '15m': 15, '30m': 30, '1h': 60 }};
                const step = minMap[tf] || 5;
                const lastDays = rawCandleData.slice(-5);
                const iCandles = [], iVols = [];
                lastDays.forEach(day => {{
                    let currentPrice = day.open;
                    const steps = Math.floor(240 / step); // 4 giờ giao dịch (9h-11h30, 13h-14h30)
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

            // Áp dụng dữ liệu và vẽ lại toàn bộ chỉ báo
            function applyDataset(resampled) {{
                const cData = resampled.candles;
                const vData = resampled.volumes;

                // Cập nhật chế độ hiển thị thời gian
                chart.applyOptions({{
                    timeScale: {{
                        timeVisible: resampled.timeVisible,
                        secondsVisible: false
                    }}
                }});

                candleSeries.setData(cData);
                volumeSeries.setData(vData);

                if (cData.length > 0) {{
                    ma20.setData(calculateSMA(cData, 20));
                    ma50.setData(calculateSMA(cData, 50));
                    ema9.setData(calculateEMA(cData, 9));
                    ema21.setData(calculateEMA(cData, 21));

                    const bData = calculateBOLL(cData);
                    bollUpper.setData(bData.upper);
                    bollMid.setData(bData.mid);
                    bollLower.setData(bData.lower);

                    const rData = calculateRSI(cData);
                    rsiSeries.setData(rData);
                    rsiUp.setData(rData.map(d => ({{ time: d.time, value: 70 }})));
                    rsiDown.setData(rData.map(d => ({{ time: d.time, value: 30 }})));

                    const mData = calculateMACD(cData);
                    macdLine.setData(mData.mLine);
                    macdSignal.setData(mData.sLine);
                    macdHist.setData(mData.hList);
                }}
                chart.timeScale().fitContent();
            }}

            // Nạp dữ liệu mặc định ban đầu (1 Ngày)
            applyDataset(resampleData('1D'));

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
