# 📈 AI Stock Copilot (Trợ Lý Đầu Tư & Cảnh Báo Chứng Khoán Tự Động)

Hệ sinh thái phân tích chứng khoán tự động chuyên nghiệp kết hợp **vnstock (VCI)**, **Gemini 2.5 Pro (Google GenAI)**, **TradingView Lightweight Charts (60 FPS Native)**, **Apache ECharts Bội số Định giá**, **Discord Webhook / Bot DM**, và kiến trúc vận hành 24/7 trên **Render.com / Streamlit Cloud**.

---

## 🌟 Tính Năng Cốt Lõi

1. **Biểu đồ TradingView 60 FPS Native & Dropdown Khung Thời Gian:**
   * Đa khung thời gian: `1m`, `5m`, `15m`, `30m`, `1h`, `1 ngày (1D)`, `1 tuần (1W)`, `1 tháng (1M)`.
   * Tách riêng 3 subpanel phân tích: **Khối lượng (Volume)**, **MACD**, và **RSI**.
   * Hỗ trợ **kéo thả chuột trực tiếp để chỉnh độ cao** từng subpanel (`pane-resizer`).
   * **Đường dóng dọc liền mạch tuyệt đối** từ đỉnh nến chính xuyên suốt qua tất cả các subpanel.
   * Định dạng mốc thời gian chuẩn Tiếng Việt: `29 Tháng Năm '26` trên nhãn chuột, và `Tháng Mười hai`, `Tháng Hai`... trên trục thời gian.
   * Bật/tắt linh hoạt các chỉ báo kỹ thuật: `MA20`, `MA50`, `EMA9`, `EMA21`, `Bollinger Bands`.

2. **Phân tích Bội số Định giá Thị trường (P/E & P/B ECharts):**
   * Biểu đồ kép tương tác trực quan: Điểm số VN-INDEX (cột trái) đối chiếu với P/E hoặc P/B (cột phải).
   * Đường định giá trung bình lịch sử (`TB: ...x`).
   * Thanh trượt **DataZoom** tương tác mượt mà, chống đè chữ và che nhãn ngày tháng.
   * Tùy chọn 3 bố cục: *Toàn cảnh P/E*, *Toàn cảnh P/B*, và *So sánh song song (2 cột)*.

3. **Header Thị Trường & Thanh Khoản Chuẩn Ngữ Nghĩa Tài Chính:**
   * Card giao diện Responsive Card: Sử dụng dynamic font `clamp()` và `min-width: max-content`, **chặn đứng hoàn toàn lỗi cắt xén số liệu thành dấu ba chấm (`...`)**.
   * Màu sắc đơn vị chuẩn tài chính: `CP` và `Tỷ` mang màu xám trung tính, không bị xung đột ngữ nghĩa với mã màu vàng tham chiếu.
   * Độ rộng thị trường chi tiết: Số mã tăng (trần tím), giảm (sàn xanh lơ), tham chiếu vàng và trạng thái phiên khớp lệnh.

4. **Trợ Lý Phân Tích AI Chiến Lược (Gemini 2.5 Pro):**
   * **Phân tích chuyên sâu 8 trụ cột**: Đánh giá toàn diện mô hình kinh doanh, sức khỏe tài chính, lợi thế cạnh tranh, định giá P/B Justified & Graham, kỹ thuật và rủi ro.
   * **Báo cáo tóm tắt 3 màu cảnh báo trực quan**: Huy hiệu `🟢 Tốt`, `🟡 Trung bình`, `🔴 Rủi ro` giúp nhà đầu tư nắm bắt cơ hội trong 30 giây.
   * **Mô phỏng 3-4 kịch bản rủi ro thị trường**: Lạc quan (Bull), Cơ sở (Base), Bi quan (Bear) kèm xác suất, điều kiện kích hoạt và nhóm ngành hưởng lợi.

5. **Theo dõi Danh mục Cá nhân hóa:**
   * Quản lý các mã cổ phiếu đang nắm giữ, tự động tính toán lãi/lỗ (VND và %).
   * Chỉnh sửa trực tiếp trên giao diện web với bảng `st.data_editor` và lưu trữ bền vững vào `portfolio.json`.

6. **Hệ Thống Cảnh Báo Đa Kênh Tự Động (Discord):**
   * Gửi Rich Embed thông tin danh mục, tín hiệu Stop Loss và khuyến nghị mua/bán vào Kênh Discord qua Webhook.
   * Gửi tin nhắn riêng tư (DM) trực tiếp vào tài khoản Discord cá nhân.
   * Bot ngầm giám sát 24/7 theo lịch trình ATO (08:45), Nghỉ trưa (11:30) và ATC (14:45).

---

## 🏛️ Cấu Trúc Dự Án (Project Structure)

> 📘 **Xem tài liệu kiến trúc kỹ thuật chi tiết tại:** [PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md)

```text
Stock - learning/
│
├── app.py                      # 🚀 Tầng điều phối Streamlit Web chính
├── components/                 # 📊 Tầng biểu đồ TradingView & ECharts
├── tabs/                       # 📑 5 Tab chức năng nghiệp vụ riêng biệt
├── data_engine.py              # ⚙️ Tầng dữ liệu & tính toán chỉ báo kỹ thuật
├── ai_analyst.py               # 🧠 Tầng trí tuệ nhân tạo Gemini 2.5 Pro
├── discord_alerts.py           # 🔔 Tầng cảnh báo Discord (Webhook & DM)
├── trading_bot.py              # 🤖 Tầng tự động hóa giám sát thị trường 24/7
├── run_cloud.py                # ☁️ Tiến trình khởi chạy kép trên Cloud (Render/Linux)
├── scripts/                    # 🛠️ Bộ công cụ & kịch bản khởi chạy Windows
│   ├── run_dashboard.bat       # Khởi chạy Web Dashboard trên Local
│   ├── run_bot.bat             # Khởi chạy Trading Bot ngầm
│   └── clean_cache.bat         # 1-click dọn sạch thư mục cache bytecode
├── portfolio.json              # 💾 Cơ sở dữ liệu danh mục đầu tư mẫu
├── requirements.txt            # Danh mục thư viện Python phụ thuộc
├── Procfile                    # Chỉ thị tiến trình triển khai Web trên Cloud
└── RENDER_DEPLOY_GUIDE.md      # Cẩm nang hướng dẫn chi tiết Deploy 24/7
```

---

## 🚀 Hướng Dẫn Cài Đặt & Chạy Local

### 1. Kích hoạt môi trường ảo Python:
```powershell
& "$HOME\.venv\Scripts\Activate.ps1"
```

### 2. Cài đặt thư viện:
```bash
pip install -r requirements.txt
```

### 3. Cấu hình biến môi trường (`.env`):
Tạo file `.env` ở thư mục gốc và điền các khóa API của bạn:
```env
GEMINI_API_KEY="your_gemini_api_key_here"
DISCORD_WEBHOOK_URL="https://discord.com/api/webhooks/..."
DISCORD_BOT_TOKEN="your_discord_bot_token"
DISCORD_USER_ID="your_discord_user_id"
VNSTOCK_API_KEY="your_vnstock_key_if_sponsor"
```

### 4. Khởi chạy ứng dụng:
* **Cách 1**: Nhấp đúp vào file [run_dashboard.bat](run_dashboard.bat) ở thư mục gốc hoặc trong thư mục `scripts/`.
* **Cách 2**: Chạy qua dòng lệnh Terminal:
  ```bash
  streamlit run app.py
  ```
* Ứng dụng sẽ mở tự động tại: `http://localhost:8501`.

---

## ☁️ Hướng Dẫn Triển Khai Production 24/7 (Render.com)

> 📘 **Xem hướng dẫn chi tiết từng bước tại:** [RENDER_DEPLOY_GUIDE.md](RENDER_DEPLOY_GUIDE.md)

1. Đẩy mã nguồn lên kho lưu trữ GitHub của bạn:
   ```bash
   git add .
   git commit -m "feat: complete professional stock dashboard with gemini ai"
   git push origin main
   ```
2. Đăng nhập [Render.com](https://dashboard.render.com/) và tạo một **Web Service** mới liên kết với repository của bạn.
3. Thiết lập thông số:
   * **Runtime**: `Python 3`
   * **Build Command**: `pip install -r requirements.txt`
   * **Start Command**: `python run_cloud.py` (Khởi chạy đồng thời cả Web Streamlit và Bot 24/7).
4. Thêm các biến môi trường tương ứng trong tab **Environment** của Render.
5. Cài đặt [UptimeRobot](https://uptimerobot.com) ping kiểm tra HTTP 5 phút/lần vào địa chỉ web Render để giữ cho dịch vụ thức liên tục 24/7/365 hoàn toàn miễn phí!
