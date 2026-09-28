"""Script gửi thử nghiệm trọn bộ báo cáo và tín hiệu đầu tư lên Discord.

Kiểm tra:
1. Thẻ Tín hiệu Mua Chuẩn Quỹ (Institutional Trade Signal Card)
2. Cảnh báo Chốt lời từng phần (Partial Profit Lock - Target 1)
3. Cảnh báo Macro Circuit Breaker (Trạng thái thị trường)
"""

import os
import sys
import time

from dotenv import load_dotenv

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from discord_alerts import (
    send_partial_take_profit_alert,
    send_regime_circuit_breaker_alert,
    send_trade_signal_alert,
)

load_dotenv()


def main():
    print("=" * 60)
    print("🚀 BẮT ĐẦU GỬI THỬ NGHIỆM BÁO CÁO & TÍN HIỆU LÊN DISCORD")
    print("=" * 60)

    # 1. Thẻ Tín hiệu Mua Chuẩn Quỹ (Institutional Signal Card)
    print("\n[1/3] 🟢 Đang bắn Thẻ Tín Hiệu Mua Chuẩn Quỹ (mã FPT)...")
    success_buy = send_trade_signal_alert(
        symbol="FPT",
        action="MUA",
        current_price=135.0,
        trigger_reason="Breakout nền tích lũy 3 tuần kèm Vol bùng nổ gấp 2.2x TB20 phiên. RSI(14) xác nhận xu hướng tại 58.5!",
        target_price=150.0,
        stop_loss=127.0,
        entry_range=(134.0, 136.0),
        target_price_t2=165.0,
        risk_reward=2.50,
        position_size_nav="12% - 15% NAV",
        conviction_score=85.0,
        quant_metrics={
            "f_score": 8,
            "mos_pct": 22.5,
            "z_score": 3.42,
            "tech_status": "TRÊN MA20 (Uptrend)",
            "rsi": 58.5,
        },
        catalysts=[
            "Doanh thu ký mới mảng AI và Chuyển đổi số tăng trưởng +45% YoY",
            "Ký kết thành công hợp đồng cung cấp giải pháp bán dẫn lớn tại thị trường Nhật Bản",
            "Khối ngoại quay lại mua ròng phiên thứ 3 liên tiếp",
        ],
        thesis_breaker="Thủng ngưỡng hỗ trợ then chốt 127.0k hoặc tăng trưởng LNST quý tới dưới 15%.",
        strategy_style="⚡ LƯỚT SÓNG T+ / BREAKOUT",
    )
    print(f"       -> Kết quả: {'✅ THÀNH CÔNG' if success_buy else '❌ THẤT BÀI'}")

    time.sleep(1.0)

    # 2. Cảnh báo Chốt lời từng phần (Partial Profit Lock)
    print("\n[2/3] 🎯 Đang bắn Cảnh Báo Chốt Lời Từng Phần Target 1 (mã MWG)...")
    success_tp = send_partial_take_profit_alert(
        symbol="MWG",
        current_price=68.5,
        entry_price=60.0,
        gain_pct=14.17,
        new_stop_price=60.0,
        lock_fraction=0.5,
    )
    print(f"       -> Kết quả: {'✅ THÀNH CÔNG' if success_tp else '❌ THẤT BÀI'}")

    time.sleep(1.0)

    # 3. Cảnh báo Macro Circuit Breaker
    print("\n[3/3] 🛡️ Đang bắn Cảnh Báo Chốt Chặn Vĩ Mô (Macro Circuit Breaker)...")
    success_macro = send_regime_circuit_breaker_alert(
        regime="UPTREND",
        reason="VN-Index giữ vững trên MA200 ngày, thanh khoản tích cực. Hệ thống duy trì chế độ săn tìm cơ hội đầu tư.",
        vnindex_price=1288.6,
    )
    print(f"       -> Kết quả: {'✅ THÀNH CÔNG' if success_macro else '❌ THẤT BÀI'}")

    print("\n" + "=" * 60)
    print("🎉 ĐÃ HOÀN TẤT GỬI THỬ NGHIỆM! HÃY MỞ DISCORD KIỂM TRA NGAY.")
    print("=" * 60)


if __name__ == "__main__":
    main()
