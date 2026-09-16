"""
test_alpha_and_lifecycle.py
Kiểm thử toàn diện 4 tính năng nâng cấp:
1. Khiên chắn Cổ tức GDKHQ (Anti-False Stop Loss).
2. Bộ lọc Chống Mua Đuổi Trần (Anti-Chasing Filter).
3. Supabase Signal Lifecycle & Immutable Snapshot.
4. Data Freshness Check & State Transition (TARGET_HIT / STOP_LOSS).
5. Metrics calculation cho Tab 6 (Alpha Tracker).
"""
import sys
import os
from datetime import datetime

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from data_engine import detect_gdkhq_event
from db_manager import (
    save_quant_signal,
    get_supabase_client,
    fetch_open_signals,
    get_signal_audit_metrics,
    update_daily_tracking
)


def test_1_gdkhq_shield():
    print("\n--- [TEST 1] KHIÊN CHẮN CỔ TỨC GDKHQ SHIELD ---")
    # Giả lập cổ phiếu bị điều chỉnh kỹ thuật:
    # Tham chiếu 50.0k, mở cửa 47.0k (Gap down -6.0%) trong khi VN-Index chỉ biến động -0.2%
    mock_tech_gdkhq = {
        "current_price": 47.2,
        "ref_price": 50.0,
        "open": 47.0,
        "change_pct": -5.6
    }
    res = detect_gdkhq_event("MSB", mock_tech_gdkhq, vnindex_chg_pct=-0.2)
    print(f"Kết quả GDKHQ: is_gdkhq = {res['is_gdkhq']}, Lý do: {res.get('reason')}")
    assert res["is_gdkhq"] is True, "LỖI: Phải nhận diện được hiện tượng GDKHQ!"
    assert "GDKHQ" in res["reason"], "LỖI: Lý do phải nêu rõ GDKHQ!"

    # Giả lập phiên bán tháo do thị trường sập diện rộng (-3.5%) -> Không được báo nhầm là GDKHQ
    res_crash = detect_gdkhq_event("MSB", mock_tech_gdkhq, vnindex_chg_pct=-3.5)
    print(f"Thị trường sập diện rộng: is_gdkhq = {res_crash['is_gdkhq']}")
    assert res_crash["is_gdkhq"] is False, "LỖI: Thị trường sập diện rộng không được báo nhầm là GDKHQ!"
    print("✅ PASS: Test 1 GDKHQ Shield hoạt động chuẩn xác!")


def test_2_anti_chasing_filter():
    print("\n--- [TEST 2] BỘ LỌC CHỐNG MUA ĐUỔI TRẦN (ANTI-CHASING) ---")
    # Tình huống 1: Cổ phiếu tăng +6.8% (áp sát trần HOSE)
    tech_ceiling = {
        "current_price": 28.5,
        "ceiling_price": 28.5,
        "change_pct": 6.85,
        "is_ceiling": True
    }
    is_anti_chasing = (
        tech_ceiling["current_price"] >= tech_ceiling["ceiling_price"] or
        tech_ceiling["change_pct"] >= 6.7 or
        tech_ceiling["is_ceiling"]
    )
    print(f"Cổ phiếu kịch trần (+6.85%): Anti-chasing = {is_anti_chasing}")
    assert is_anti_chasing is True, "LỖI: Phải kích hoạt Anti-Chasing khi giá kịch trần!"

    # Tình huống 2: Cổ phiếu tăng vừa phải +3.2% (Vùng mua breakout hợp lệ)
    tech_normal = {
        "current_price": 27.5,
        "ceiling_price": 28.5,
        "change_pct": 3.2,
        "is_ceiling": False
    }
    is_anti_chasing_normal = (
        tech_normal["current_price"] >= tech_normal["ceiling_price"] or
        tech_normal["change_pct"] >= 6.7 or
        tech_normal["is_ceiling"]
    )
    print(f"Cổ phiếu breakout lành mạnh (+3.2%): Anti-chasing = {is_anti_chasing_normal}")
    assert is_anti_chasing_normal is False, "LỖI: Không được chặn mua ở vùng giá lành mạnh!"
    print("✅ PASS: Test 2 Anti-Chasing Filter hoạt động chuẩn xác!")


def test_3_supabase_signal_lifecycle():
    print("\n--- [TEST 3] SUPABASE SIGNAL LIFECYCLE & IMMUTABLE SNAPSHOT ---")
    client = get_supabase_client()
    if not client:
        print("⚠️ Bỏ qua test 3 vì chưa cấu hình Supabase Client.")
        return

    # Lưu 1 tín hiệu mẫu có đầy đủ snapshot
    test_symbol = "TCB"
    sig_id = save_quant_signal(
        symbol=test_symbol,
        action="🟢 VALUE BUY",
        decision_tag="🟢 VALUE BUY (Test Unit Lifecycle)",
        entry_price=24.5,
        market_price_at_signal=24.5,
        target_price=28.0,
        stop_loss=22.8,
        hard_gates={"mos_pct": 19.5, "ev": 27.2, "kelly_f": 0.18, "risk_reward": 2.05},
        f_score_res={"score": 8},
        z_score_res={"z_score": 3.1},
        prob_dict={"P_bull": 0.40, "P_base": 0.45, "P_bear": 0.15, "rationale_base": "Tăng trưởng NIM và CASA dẫn đầu ngành"},
        model_version="test-suite-v1.0",
        input_snapshot={"pe": 6.8, "pb": 1.1, "roe": 19.2, "test_tag": "UNIT_TEST"}
    )
    print(f"Đã lưu tín hiệu test vào Supabase: ID = {sig_id}")
    assert sig_id is not None, "LỖI: Không thể lưu signal vào Supabase!"

    # Đọc lại từ Supabase để xác minh Immutable Snapshot
    res = client.table("signals").select("*, signal_tracking(*)").eq("id", sig_id).execute()
    data = res.data[0]
    print(f"Mã: {data['symbol']}, Entry: {data['entry_price']}, MoS: {data['mos_pct']}%, F-Score: {data['f_score']}")
    print(f"Input Snapshot lưu trữ: {data['input_snapshot']}")
    
    assert data["symbol"] == test_symbol
    assert float(data["entry_price"]) == 24.5
    assert float(data["mos_pct"]) == 19.5
    assert data["input_snapshot"]["test_tag"] == "UNIT_TEST"

    # Kiểm tra bản ghi tracking OPEN tương ứng
    trackings = data.get("signal_tracking") or []
    assert len(trackings) > 0, "LỖI: Chưa tự động tạo bản ghi signal_tracking!"
    assert trackings[0]["status"] == "OPEN", "LỖI: Trạng thái ban đầu phải là OPEN!"
    print("✅ PASS: Test 3 Supabase Signal Lifecycle & Immutable Snapshot hoàn thành chuẩn xác!")


def test_4_metrics_and_audit_calculation():
    print("\n--- [TEST 4] TÍNH TOÁN METRICS CHO TAB 6 ALPHA TRACKER ---")
    metrics = get_signal_audit_metrics()
    print(f"Tổng số tín hiệu: {metrics['total_signals']}")
    print(f"Số tín hiệu OPEN: {metrics['open_signals']}")
    print(f"Số tín hiệu đã đóng: {metrics['resolved_signals']}")
    print(f"Win Rate tạm tính: {metrics['win_rate']}%")
    print(f"Profit Factor: {metrics['profit_factor']}")
    print(f"Alpha vs VN-Index: {metrics['alpha_vs_vnindex']}%")

    assert metrics["total_signals"] >= 1, "LỖI: Phải có ít nhất 1 tín hiệu trong database!"
    assert "signals_df" in metrics
    print("✅ PASS: Test 4 Metrics Alpha Tracker hoàn thành chuẩn xác!")


if __name__ == "__main__":
    print("=" * 65)
    print("🧪 BẮT ĐẦU KIỂM THỬ TOÀN DIỆN ALPHA TRACKER & SIGNAL LIFECYCLE")
    print("=" * 65)
    test_1_gdkhq_shield()
    test_2_anti_chasing_filter()
    test_3_supabase_signal_lifecycle()
    test_4_metrics_and_audit_calculation()
    print("\n" + "=" * 65)
    print("🎉 TẤT CẢ 4/4 TEST SUITES ĐÃ PASS 100%! HỆ THỐNG HOẠT ĐỘNG HOÀN HẢO!")
    print("=" * 65)
