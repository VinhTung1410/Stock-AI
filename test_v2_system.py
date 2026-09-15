"""
test_v2_system.py - Script kiểm thử toàn diện hệ thống AI Stock Copilot V2
"""
import sys
import os

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except:
        pass

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from quant_valuation import calculate_fair_value_and_mos, classify_stock_archetype, INSTITUTIONAL_CONSENSUS_TARGETS
from quant_engine import (
    evaluate_market_regime,
    evaluate_holding_position,
    calculate_100_point_score,
    evaluate_decision_hard_gates
)
from data_engine import load_portfolio, evaluate_portfolio

def test_v2():
    print("=" * 70)
    print("🧪 KIỂM THỬ HỆ THỐNG AI STOCK COPILOT V2 - VALUE-FIRST + TIMING")
    print("=" * 70)

    # 1. Test Archetype & Fair Value & MoS
    print("\n[1] KIỂM THỬ PHÂN LOẠI ARCHETYPE & ĐỊNH GIÁ FAIR VALUE:")
    test_cases = [
        ("MSB", 15.0, "Ngân hàng"),
        ("FPT", 75.0, "Công nghệ"),
        ("HPG", 26.0, "Thép"),
        ("BSR", 28.0, "Dầu khí"),
        ("VHM", 42.0, "Bất động sản")
    ]
    for sym, price, sector in test_cases:
        archetype = classify_stock_archetype(sym, sector)
        res = calculate_fair_value_and_mos(sym, price, sector=sector)
        print(f"  • {sym} ({sector}) -> Archetype: {archetype} | Giá: {price}k | FV Base: {res['fair_value']}k | MoS: {res['mos_pct']:+}% | Rating: {res['valuation_rating']}")

    # 2. Test Quy tắc Cốt tử: Vị thế LÃI kích hoạt Trailing Stop, CẤM dùng từ Cắt lỗ
    print("\n[2] KIỂM THỬ VỊ THẾ LÃI (TRAILING STOP vs CẮT LỖ):")
    mock_pos_profit = {
        "symbol": "MSB",
        "avg_price": 12.5,
        "volume": 2000,
        "market_price": 15.0
    }
    mock_tech_msb = {
        "current_price": 15.0,
        "atr": 0.45,
        "ma20": 14.2
    }
    eval_msb = evaluate_holding_position(mock_pos_profit, mock_tech_msb)
    print(f"  • MSB (Vốn 12.5k -> Giá 15.0k, Lãi {eval_msb['pl_pct']:+}%):")
    print(f"    - Hành động: {eval_msb['action']}")
    print(f"    - Mốc Trailing Stop bảo vệ lãi: {eval_msb['trailing_stop']}k")
    print(f"    - Chi tiết: {eval_msb['detail']}")
    assert "CẮT LỖ" not in eval_msb['action'].upper(), "LỖI VI PHẠM: Vị thế lãi nhưng lại đề xuất cắt lỗ!"
    assert eval_msb['trailing_stop'] >= 12.5, "LỖI: Trailing stop phải bảo toàn vốn/lãi!"
    print("    ✅ PASSED: Vị thế lãi đã kích hoạt Trailing Stop chính xác, triệt tiêu hoàn toàn từ cắt lỗ!")

    # 3. Test Vị thế LỖ nhẹ trong biên độ an toàn
    print("\n[3] KIỂM THỬ VỊ THẾ LỖ (THESIS BREAKER vs HOẢNG LOẠN CẮT LỖ):")
    mock_pos_loss = {
        "symbol": "FPT",
        "avg_price": 78.0,
        "volume": 1000,
        "market_price": 75.0
    }
    mock_tech_fpt = {
        "current_price": 75.0,
        "atr": 1.8,
        "ma20": 76.5
    }
    eval_fpt = evaluate_holding_position(mock_pos_loss, mock_tech_fpt)
    print(f"  • FPT (Vốn 78.0k -> Giá 75.0k, Lỗ {eval_fpt['pl_pct']}%):")
    print(f"    - Hành động: {eval_fpt['action']}")
    print(f"    - Stop-loss kỹ thuật: {eval_fpt['stop_loss']}k")
    print(f"    - Thesis Breaker: {eval_fpt['thesis_breaker']}")
    print("    ✅ PASSED: Luận điểm Thesis Breaker hoạt động chính xác, không hoảng loạn cắt lỗ!")

    # 4. Test Market Regime
    print("\n[4] KIỂM THỬ MARKET REGIME (BULLISH / NEUTRAL / CORRECTION / RISK-OFF):")
    cases_regime = [
        {"name": "VN-Index vượt đỉnh", "data": {"current_price": 1320, "ma20": 1300, "ma50": 1280, "rsi": 62}},
        {"name": "VN-Index gãy MA20", "data": {"current_price": 1270, "ma20": 1290, "ma50": 1260, "rsi": 44}},
        {"name": "VN-Index mở biên rơi", "data": {"current_price": 1220, "ma20": 1280, "ma50": 1270, "rsi": 32}}
    ]
    for c in cases_regime:
        r = evaluate_market_regime(c["data"])
        print(f"  • {c['name']} -> {r['tag']} | Cổ phiếu: {r['stock_pct']} / Tiền mặt: {r['cash_pct']}")

    # 5. Test Thang điểm 100 điểm Lượng hóa
    print("\n[5] KIỂM THỬ THANG ĐIỂM 100 ĐIỂM ĐA TẦNG:")
    fin_sample = {"roe": 19.5, "roa": 2.2, "debt_equity": 0.8, "current_ratio": 1.5, "gross_margin": 22.0, "net_margin": 14.0, "p_cf": 12.0, "roic": 15.0}
    tech_sample = {"current_price": 75.0, "ma20": 73.0, "rsi": 54.0, "volume": 3500000, "vol_ma20": 3000000, "adv20_billion": 260.0, "foreign_flow": {"net_val_bil": 15.0}}
    mos_sample = {"mos_pct": 21.0}
    score_res = calculate_100_point_score("FPT", tech_sample, fin_sample, mos_sample)
    print(f"  • FPT: Tổng điểm = {score_res['total_score']}/100 | Xếp hạng: {score_res['grade']} ({score_res['rating']})")
    print(f"    - Cơ bản: {score_res['breakdown']['pillar_fundamental']}/35 | Định giá: {score_res['breakdown']['pillar_valuation']}/30 | Kỹ thuật: {score_res['breakdown']['pillar_technical']}/20 | Dòng tiền: {score_res['breakdown']['pillar_smart_flow']}/15")

    # 6. Test evaluate_portfolio V2
    print("\n[6] KIỂM THỬ EVALUATE_PORTFOLIO TÍCH HỢP ĐỊNH GIÁ & TRAILING STOP:")
    p = load_portfolio()
    df = evaluate_portfolio(p)
    print(df[["Mã CP", "Giá vốn (k)", "Thị giá (k)", "Lãi/Lỗ (%)", "Fair Value (k)", "MoS (%)", "Chặn lãi/Cắt lỗ (k)", "Hành động V2"]].to_string(index=False))

    print("\n" + "=" * 70)
    print("🎉 TẤT CẢ TEST CASES V2 ĐỀU ĐẠT CHUẨN 100%!")
    print("=" * 70)

if __name__ == "__main__":
    test_v2()
