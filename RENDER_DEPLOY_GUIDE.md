# 🚀 HƯỚNG DẪN TRIỂN KHAI BOT LÊN RENDER.COM (100% MIỄN PHÍ - KHÔNG CẦN THẺ)

Tài liệu này hướng dẫn bạn cách đưa toàn bộ hệ thống **AI Stock Copilot & Trading Bot** lên nền tảng đám mây **Render.com** kết hợp với **UptimeRobot** để:
* Bot chạy liên tục **24/7/365 không bao giờ ngủ đông**.
* Canh chuẩn từng giây theo **múi giờ Việt Nam (UTC+7)** dù bạn đang ở Pháp.
* **Bảo mật 100%:** Tuyệt đối không cần nhập bất kỳ thông tin thẻ ngân hàng hay thẻ tín dụng nào.

---

## BƯỚC 1: Đẩy Mã Nguồn Lên GitHub Cá Nhân (Private)

1. Truy cập [github.com](https://github.com) và đăng nhập.
2. Tạo một kho lưu trữ mới (**New Repository**):
   * Tên Repository: `stock-copilot` (hoặc tên tùy thích).
   * **Chọn chế độ: `Private`** (để giữ bí mật danh mục và mã nguồn của bạn).
3. Tại thư mục dự án trên máy tính, đẩy toàn bộ code lên GitHub:
   ```bash
   git add .
   git commit -m "feat: Ready for 24/7 Cloud deployment"
   git branch -M main
   git remote add origin https://github.com/<tai-khoan-cua-ban>/stock-copilot.git
   git push -u origin main
   ```

---

## BƯỚC 2: Đăng Ký & Tạo Web Service Trên Render.com

1. Truy cập [render.com](https://render.com) và chọn **GET STARTED FOR FREE**.
2. Chọn **Sign in with GitHub** (Đăng nhập bằng tài khoản GitHub, **KHÔNG BỊ HỎI THẺ TÍN DỤNG**).
3. Tại trang tổng quan (Dashboard), nhấn nút **New +** ở góc trên bên phải ➔ Chọn **Web Service**.
4. Chọn repository `stock-copilot` bạn vừa tạo ở Bước 1 và nhấn **Connect**.
5. Điền thông tin cấu hình dịch vụ:
   * **Name:** `stock-copilot` (hoặc tên tùy bạn thích).
   * **Region:** Chọn `Frankfurt (EU Central)` (Gần Pháp nhất, độ trễ thấp nhất).
   * **Branch:** `main`
   * **Runtime:** `Python 3`
   * **Build Command:** `pip install -r requirements.txt`
   * **Start Command:** `python run_cloud.py`
   * **Instance Type:** Chọn gói **Free** ($0/month - 512MB RAM).

6. **Cấu hình biến bí mật (Environment Variables):**
   Kéo xuống mục **Environment Variables**, bấm **Add Environment Variable** và điền các giá trị từ file `.env` của bạn:
   * `GEMINI_API_KEY`: *(Dán mã API Key Gemini của bạn)*
   * `DISCORD_WEBHOOK_URL`: *(Dán link Webhook Discord của bạn)*
   * `DISCORD_BOT_TOKEN`: *(Dán Token Bot Discord của bạn)*
   * `DISCORD_USER_ID`: *(Dán User ID Discord của bạn)*
   * `VNSTOCK_API_KEY`: *(Dán API Key Vnstock nếu có)*
   * `PYTHONUTF8`: `1`

7. Nhấn nút **Create Web Service** ở dưới cùng.
   * Render sẽ tự động kéo code, cài đặt thư viện và khởi chạy cả Web Dashboard lẫn Bot Daemon.
   * Khi hoàn tất, bạn sẽ thấy dòng chữ xanh **Live** kèm đường link web có dạng:
     `https://stock-copilot-xxxx.onrender.com`

---

## BƯỚC 3: Cài Đặt UptimeRobot Để Bot Thức 24/7 (Không Bao Giờ Ngủ)

Gói Free của Render bình thường sẽ tạm ngủ nếu không có ai truy cập sau 15 phút. Chúng ta dùng UptimeRobot để "đánh thức" liên tục:

1. Truy cập [uptimerobot.com](https://uptimerobot.com) ➔ Chọn **Register for FREE** (Đăng ký miễn phí, **không cần thẻ**).
2. Sau khi vào Dashboard, nhấn nút **+ Add New Monitor**:
   * **Monitor Type:** Chọn `HTTP(s)`
   * **Friendly Name:** `Stock Copilot Keepalive`
   * **URL (or IP):** Dán link web Render của bạn (Ví dụ: `https://stock-copilot-xxxx.onrender.com`)
   * **Monitoring Interval:** Chọn `Every 5 minutes` (Mỗi 5 phút một lần).
3. Nhấn **Create Monitor**.

🎉 **CHÚC MỪNG BẠN!**
* Cứ mỗi 5 phút, UptimeRobot sẽ gửi 1 tín hiệu nhẹ đến web của bạn.
* Render sẽ luôn ở trạng thái **Thức 24/7/365**.
* Tiến trình `trading_bot.py` chạy ngầm bên trong sẽ liên tục canh thị trường Việt Nam từ `08:45` đến `15:00` hàng ngày và bắn cảnh báo về Discord cho bạn ở Pháp, ngay cả khi bạn tắt máy tính hay đang ngủ sâu!

---

## BƯỚC 4: Kiểm Tra Hoạt Động Của Bot

* **Xem Web Dashboard từ xa:** Mở link `https://stock-copilot-xxxx.onrender.com` trên điện thoại hoặc trình duyệt tại Pháp.
* **Xem Log hoạt động của Bot:** Trên trang Render, vào tab **Logs**, bạn sẽ thấy các dòng log:
  ```text
  🌟 TRADING BOT DAEMON ĐÃ KHỞI CHẠY THÀNH CÔNG!
  🕒 Múi giờ hệ thống: Asia/Ho_Chi_Minh (UTC+7)
  ⏱️ Tần suất quét rủi ro trong phiên: Mỗi 30 giây
  📅 Khung giờ báo cáo tự động: 08:45 (ATO) | 11:30 (Trưa) | 14:45 (ATC)
  ```
