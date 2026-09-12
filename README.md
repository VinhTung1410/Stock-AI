# 📈 AI Stock Copilot (Hệ thống Trợ lý Đầu tư & Cảnh báo Tự động)

Hệ sinh thái phân tích chứng khoán tự động kết hợp **vnstock**, **Gemini Pro (Google GenAI)**, **Discord Webhook** và **Streamlit Cloud Dashboard** với chi phí 0đ.

---

## 🌟 Tính Năng Cốt Lõi

1. **Dữ liệu Kỹ thuật Real-time (vnstock):**
   - Tự động kéo giá nến OHLCV, tính MA20, MA50, RSI(14), so sánh thanh khoản so với trung bình 20 phiên.
2. **Theo dõi Danh mục Cá nhân hóa:**
   - Quản lý các mã đang nắm giữ (BSR, MSB, SSI...), tự động tính toán lãi/lỗ (VND và %).
   - Chỉnh sửa danh mục trực tiếp trên web bằng bảng tương tác `st.data_editor`.
3. **Đầu não Phân tích AI (Gemini Pro):**
   - Đọc dữ liệu danh mục kết hợp tin tức vĩ mô crawl tự động qua RSS để đưa ra nhận định đa chiều.
   - Xuất kịch bản T+ (Ngắn hạn), Trung hạn (3-6 tháng) và quản trị rủi ro Stop Loss / Take Profit.
4. **Cảnh báo Tự động qua Discord Webhook:**
   - Báo cáo phân tích định dạng Rich Embed đẹp mắt, màu sắc trực quan (Xanh lời / Đỏ lỗ / Cảnh báo khẩn cấp).

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
