"""
=============================================================================
🚀 RUN CLOUD: KỊCH BẢN KHỞI CHẠY ĐỒNG THỜI STREAMLIT & TRADING BOT TRÊN CLOUD
=============================================================================
- Phù hợp triển khai trên: Render.com, Koyeb, VPS Linux.
- Luồng 1 (Background Thread): Chạy Trading Bot 24/7 canh thị trường & gửi Discord.
- Luồng 2 (Main Process): Chạy Web Dashboard Streamlit trên cổng $PORT.
- Khi UptimeRobot ping vào link web -> Giữ toàn bộ tiến trình thức 24/7/365!
=============================================================================
"""

import os
os.environ["VNSTOCK_TELEMETRY"] = "off"
try:
    import vnai
    vnai.disable_telemetry()
except Exception:
    pass
import sys
import threading
import subprocess
import logging
from trading_bot import run_trading_bot_loop

logging.basicConfig(level=logging.INFO, format="%(asctime)s [RUNNER] %(message)s")


def start_bot_thread():
    """Khởi chạy vòng lặp Trading Bot trong một luồng nền độc lập."""
    logging.info("Đang khởi động tiến trình Trading Bot chạy ngầm...")
    bot_thread = threading.Thread(
        target=run_trading_bot_loop,
        kwargs={"check_interval_sec": 60},
        daemon=True,
        name="TradingBotDaemon"
    )
    bot_thread.start()
    logging.info("✅ Tiến trình Trading Bot đã chạy ngầm thành công!")


def main():
    # 1. Khởi động Bot chạy ngầm canh thị trường
    start_bot_thread()

    # 2. Lấy cổng từ biến môi trường (Render tự cấp cổng qua biến $PORT)
    port = os.environ.get("PORT", "8501")
    logging.info(f"Đang khởi động Streamlit Web Dashboard trên cổng {port}...")

    # 3. Chạy giao diện Web Streamlit (-u unbuffered để đẩy log ngay lập tức)
    cmd = [
        sys.executable, "-u", "-m", "streamlit", "run", "app.py",
        "--server.port", str(port),
        "--server.address", "0.0.0.0",
        "--server.headless", "true",
        "--browser.gatherUsageStats", "false"
    ]

    subprocess.run(cmd)


if __name__ == "__main__":
    main()
