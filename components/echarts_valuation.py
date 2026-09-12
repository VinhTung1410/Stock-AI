import json
import pandas as pd

def generate_echarts_valuation_html(df: pd.DataFrame, metric: str = "PE") -> str:
    """
    Tạo mã HTML/JS nhúng Apache ECharts định giá VN-Index vs P/E hoặc P/B.
    Khắc phục triệt để lỗi cụt chữ /NINDEX, căn chỉnh lề (margins),
    bổ sung đường Trung Bình (Mean Valuation) và thanh DataZoom tương tác 60fps.
    """
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

                // Tính giá trị trung bình để làm đường chuẩn định giá
                const avgVal = parseFloat((metricVals.reduce((a, b) => a + b, 0) / metricVals.length).toFixed(2));

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
                                if (item.seriesName.indexOf('TB') === -1) {{
                                    const unit = item.seriesIndex === 0 ? ' điểm' : ' lần';
                                    str += `<span style="color:${{item.color}};">●</span> ${{item.seriesName}}: <b>${{item.value}}${{unit}}</b><br/>`;
                                }}
                            }});
                            return str;
                        }}
                    }},
                    legend: {{
                        data: ['VNINDEX (điểm, cột trái)', '{metric_name} (lần, cột phải)', 'Trung bình {metric_name}'],
                        bottom: 0,
                        textStyle: {{ color: '#cbd5e1', fontSize: 11 }},
                        icon: 'circle'
                    }},
                    // ĐẶT LỀ CỐ ĐỊNH 58px TRÁNH BỊ CẮT CHỮ VÀ DÍNH LỀ
                    grid: {{ left: 58, right: 58, top: 28, bottom: 48, containLabel: false }},
                    dataZoom: [
                        {{ type: 'inside', start: 0, end: 100 }},
                        {{
                            type: 'slider',
                            show: true,
                            height: 12,
                            bottom: 24,
                            borderColor: '#2d3139',
                            backgroundColor: '#131722',
                            fillerColor: 'rgba(41, 98, 255, 0.25)',
                            showDetail: false,
                            handleSize: '100%'
                        }}
                    ],
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
                            position: 'left',
                            min: val => Math.floor(val.min / 50) * 50,
                            axisLabel: {{ color: '#ff9800', formatter: '{{value}}' }},
                            splitLine: {{ lineStyle: {{ color: 'rgba(51, 65, 85, 0.35)', type: 'dashed' }} }}
                        }},
                        {{
                            type: 'value',
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
                            lineStyle: {{ width: 2, color: '{color_val}' }},
                            markLine: {{
                                silent: true,
                                symbol: ['none', 'none'],
                                data: [
                                    {{
                                        yAxis: avgVal,
                                        lineStyle: {{ color: '#f59e0b', type: 'dashed', width: 1.5 }},
                                        label: {{
                                            show: true,
                                            position: 'insideEndTop',
                                            formatter: `TB: ${{avgVal}}x`,
                                            color: '#f59e0b',
                                            fontSize: 10,
                                            backgroundColor: 'rgba(26, 29, 36, 0.85)',
                                            padding: [2, 4],
                                            borderRadius: 3
                                        }}
                                    }}
                                ]
                            }}
                        }}
                    ]
                }};
                myChart.setOption(option);
            }}

            render('1y');
            document.getElementById('tf-select').addEventListener('change', function(e) {{
                render(e.target.value);
            }});
            window.addEventListener('resize', () => myChart.resize());
        </script>
    </body>
    </html>
    """
    return html
