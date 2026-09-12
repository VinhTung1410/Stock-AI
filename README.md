# 📈 AI Stock Copilot (Hệ thống Trợ lý Đầu tư & Cảnh báo Tự động)

Hệ sinh thái phân tích chứng khoán tự động kết hợp **vnstock**, **Gemini Pro (Google GenAI)**, **Discord Webhook** và **Streamlit Cloud Dashboard** với chi phí 0đ.

---

## 🌟 Tính Năng Cốt Lõi

1. **Dữ liệu Kỹ thuật Real-time (vnstock):**
   - Tự động kéo giá nến OHLCV, tính MA20, MA50, RSI(14), so sánh thanh khoản so với trung bình 20 phiên.
2. **Biểu đồ TradingView 60 FPS Native & Dropdown Timeframe:**
   - Hỗ trợ chọn khung thời gian: 1m, 5m, 15m, 30m, 1h, 1 ngày, 1 tuần, 1 tháng.
   - Bật/tắt tức thì các chỉ báo MA, EMA, MACD, RSI, BOLL ở thanh công cụ đáy.
   - Crosshair ngày sạch sẽ (loại bỏ hoàn toàn 00:00:00).
3. **Phân tích Bội số Định giá Thị trường (P/E & P/B ECharts):**
   - Biểu đồ định giá kép với thanh DataZoom tương tác và đường Trung bình lịch sử (Mean Valuation Line).
   - Bộ chọn bố cục thông minh: Toàn cảnh P/E, Toàn cảnh P/B, So sánh song song.
4. **Theo dõi Danh mục Cá nhân hóa:**
   - Quản lý các mã đang nắm giữ (BSR, MSB, SSI...), tự động tính toán lãi/lỗ (VND và %).
   - Chỉnh sửa danh mục trực tiếp trên web bằng bảng tương tác `st.data_editor`.
5. **Đầu não Phân tích AI (Gemini Flash):**
   - Đọc dữ liệu danh mục kết hợp tin tức vĩ mô crawl tự động qua RSS để đưa ra nhận định đa chiều.
   - Xuất kịch bản T+ (Ngắn hạn), Trung hạn (3-6 tháng) và quản trị rủi ro Stop Loss / Take Profit.
6. **Cảnh báo Tự động qua Discord (Kênh chung & DM cá nhân):**
   - Báo cáo phân tích định dạng Rich Embed đẹp mắt gửi vào Kênh Discord qua Webhook.
   - Bot Discord bắn thông báo riêng (DM) trực tiếp vào tài khoản Discord của bạn.

---

## 🏛️ Cấu Trúc Dự Án (Project Structure)

> 📘 **Xem tài liệu kiến trúc chi tiết tại:** [PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md)

Dự án được xây dựng theo mô hình module hóa cao (Modular Architecture):

```text
Stock - learning/
│
├── app.py                      # 🚀 Tầng điều phối Streamlit chính (~85 dòng)
├── components/                 # 📊 Các bộ sinh đồ thị tương tác
│   ├── tradingview_chart.py    # Biểu đồ nến TradingView 60 FPS
│   └── echarts_valuation.py    # Biểu đồ định giá P/E, P/B ECharts
├── tabs/                       # 📑 Từng Tab chức năng riêng biệt
│   ├── tab_overview.py         # Tab 1: Tổng quan danh mục & Cảnh báo Discord
│   ├── tab_market.py           # Tab 2: Thị trường VN-Index & Định giá P/E, P/B
│   ├── tab_charts.py           # Tab 3: Biểu đồ kỹ thuật từng cổ phiếu
│   ├── tab_portfolio.py        # Tab 4: Quản lý & chỉnh sửa danh mục
│   └── tab_ai.py               # Tab 5: Trợ lý phân tích chiến lược AI
├── data_engine.py              # ⚙️ Tầng dữ liệu chứng khoán & tính toán chỉ báo
├── ai_analyst.py               # 🧠 Tầng trí tuệ nhân tạo Gemini Flash
├── discord_alerts.py           # 🔔 Tầng cảnh báo Discord (Webhook + DM Bot)
├── portfolio.json              # 💾 Dữ liệu danh mục cổ phiếu
└── run_dashboard.bat           # ⚡ Kịch bản khởi chạy nhanh 1-click
```

---

## 🚀 Hướng Dẫn Cài Đặt & Chạy Cục Bộ (Local)

### 1. Kích hoạt môi trường ảo:
```powershell
& "$HOME\.venv\Scripts\Activate.ps1"
```

### 2. Cấu hình biến môi trường (`.env`):
Tạo file `.env` và điền key của bạn:
```env
GEMINI_API_KEY="your_gemini_api_key"
DISCORD_WEBHOOK_URL="https://discord.com/api/webhooks/..."
```

### 3. Chạy Dashboard Streamlit:
```bash
streamlit run app.py
```

### 4. Gửi báo cáo thử nghiệm đến Discord:
```bash
python discord_alerts.py
```

---

## ☁️ Hướng Dẫn Triển Khai Miễn Phí Lên Streamlit Cloud

1. Đẩy mã nguồn lên GitHub:
   ```bash
   git push -u origin main
   ```
2. Truy cập [share.streamlit.io](https://share.streamlit.io/) và đăng nhập bằng GitHub.
3. Nhấn **"New app"** -> Chọn Repository `VinhTung1410/Stock-AI` -> Main file: `app.py`.
4. Trong mục **Advanced Settings -> Secrets**, dán nội dung từ file `.env`:
   ```toml
   GEMINI_API_KEY = "your_key"
   DISCORD_WEBHOOK_URL = "your_webhook_url"
   ```
5. Nhấn **Deploy**! Bạn sẽ có ngay một Web Dashboard online 24/7 để cả nhóm cùng truy cập.
