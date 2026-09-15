"""
Script kiểm thử độc lập 7 lỗi logic toán học & cấu trúc AI Stock Copilot V2:
1. R:R chuẩn xác theo Weighted Entry (không dùng Current Price).
2. Trailing Stop / Stop Loss validation: Luôn Stop < Current < Target đối với Long. Clamp Trailing Stop <= Current * 0.96. Không dùng từ "cắt lỗ" khi P/L > 0.
3. Tách biệt Value Signal vs Technical Signal: MoS >= 8% nhưng dưới MA20 (như MWG) phải là WATCH / WAIT FOR CONFIRMATION, cấm gán TRÁNH BẪY/AVOID.
4. Fair Value kèm Methodology & Confidence (SOTP/RNAV cho VIC).
5. Tách biệt Fair Value (Nội tại) vs Price Target (Kỳ vọng thời gian).
6. Market Regime kết hợp Risk Budgeting đa biến (Trend, Breadth, Liquidity, Drawdown, Margin).
7. Bộ kiểm toán Sanity Check Engine độc lập (quant_sanity_check.py).
"""

import sys
import os
import pandas as pd

# Cấu hình UTF-8 cho Windows console
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

# Thêm thư mục hiện tại vào sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from quant_sanity_check import (
    validate_holding_position,
    validate_trade_setup,
    validate_valuation_mos,
    validate_value_vs_technical,
    run_full_portfolio_sanity_check
)
from quant_engine import (
    calculate_weighted_entry_and_rr,
    evaluate_holding_position,
    evaluate_market_regime,
    evaluate_decision_hard_gates
)
from quant_valuation import calculate_fair_value_and_mos

def test_case_1_weighted_rr():
    print("\n--- TEST CASE 1: R:R THEO WEIGHTED ENTRY ---")
    entries = [72.0, 70.0, 68.0]
    weights = [0.30, 0.40, 0.30]
    target = 82.0
    stop = 65.0
    
    result = calculate_weighted_entry_and_rr(entries, weights, target, stop)
    print(f"Weighted Entry: {result['weighted_entry']} (Kỳ vọng: 70.0)")
    print(f"Reward: {result['reward']} (Kỳ vọng: 12.0)")
    print(f"Risk: {result['risk']} (Kỳ vọng: 5.0)")
    print(f"R:R: {result['rr_ratio']} (Kỳ vọng: 2.40)")
    
    assert abs(result['weighted_entry'] - 70.0) < 1e-4, "Lỗi: Weighted entry sai!"
    assert abs(result['reward'] - 12.0) < 1e-4, "Lỗi: Reward sai!"
    assert abs(result['risk'] - 5.0) < 1e-4, "Lỗi: Risk sai!"
    assert abs(result['rr_ratio'] - 2.40) < 1e-4, "Lỗi: R:R sai!"
    print(">>> PASS: Test Case 1 R:R Weighted Entry hoàn thành chuẩn xác.")

def test_case_2_trailing_stop_clamp_msb():
    print("\n--- TEST CASE 2: TRAILING STOP CLAMP CHO MSB ---")
    # Tình huống thực tế của MSB: Current = 12.80, Entry = 12.42, MA20 = 13.10
    row = {"symbol": "MSB", "avg_price": 12.42, "volume": 1000}
    tech_data = {"current_price": 12.80, "ma20": 13.10, "atr": 0.35}
    
    pos = evaluate_holding_position(row, tech_data)
    print(f"Mã MSB: Giá hiện tại = {pos['curr_price']}, Giá vốn = {pos['entry_price']}, Lãi/Lỗ = {pos['pl_pct']}%")
    print(f"Trailing Stop được sinh ra: {pos['trailing_stop']}")
    print(f"Hành động đề xuất: {pos['action']}")
    print(f"Ghi chú: {pos['detail']}")
    
    # Kiểm tra Trailing Stop bắt buộc < curr_price
    assert pos['trailing_stop'] < 12.80, f"LỖI: Trailing Stop ({pos['trailing_stop']}) >= Current (12.80)"
    assert pos['trailing_stop'] <= round(12.80 * 0.96, 2), "LỖI: Chưa clamp trailing stop <= 0.96 * current!"
    
    # Kiểm tra không được gọi là 'Cắt lỗ' khi P/L > 0
    assert "cắt lỗ" not in pos['detail'].lower(), "LỖI: Vị thế đang lãi nhưng ghi 'cắt lỗ'!"
    assert "cắt lỗ" not in pos['action'].lower(), "LỖI: Action ghi 'cắt lỗ' khi đang lãi!"
    print(">>> PASS: Test Case 2 Trailing Stop Clamp và bảo vệ lãi chuẩn xác.")

def test_case_3_value_vs_technical_mwg():
    print("\n--- TEST CASE 3: TÁCH VALUE VS TECHNICAL CHO MWG ---")
    # MWG: Giá 57.0, Fair Value 65.0 -> MoS tốt
    # Nhưng Price < MA20 (59.0) (Kỹ thuật yếu)
    curr_price = 57.0
    gate_decision = evaluate_decision_hard_gates(
        current_price=curr_price,
        p_bull=0.25,
        p_base=0.55,
        p_bear=0.20,
        price_bull=75.0,
        price_base=65.0,
        price_bear=52.0,
        atr=1.5,
        symbol="MWG",
        sector="Bán lẻ",
        tech_data={"current_price": 57.0, "ma20": 59.0, "ma50": 60.0, "rsi": 42.0}
    )
    print(f"Mã MWG - MoS: {gate_decision['mos_pct']}%, Kỹ thuật: tech_signal={gate_decision['tech_signal']}")
    print(f"Quyết định Hard Gate: {gate_decision['decision_tag']}")
    print(f"Trạng thái: {gate_decision['action_state']}")
    
    # Kiểm tra không được là AVOID hoặc CẢNH BÁO BẪY
    assert "TRÁNH BẪY" not in gate_decision['decision_tag'], "LỖI: Bị gán TRÁNH BẪY!"
    assert "BẪY" not in gate_decision['decision_tag'], "LỖI: MoS tốt bị chụp mũ BẪY!"
    assert "THEO DÕI" in gate_decision['action_state'], "Kỳ vọng: Phải là THEO DÕI / CHỜ NỀN CÂN BẰNG!"
    print(">>> PASS: Test Case 3 Tách biệt Value vs Technical hoàn thành chuẩn xác.")

def test_case_4_vic_sotp_and_methodology():
    print("\n--- TEST CASE 4: ĐỊNH GIÁ VIC VÀ METHODOLOGY / CONFIDENCE ---")
    val_vic = calculate_fair_value_and_mos("VIC", current_price=42.0)
    print(f"VIC Valuation Method: {val_vic.get('valuation_method')}")
    print(f"VIC Confidence: {val_vic.get('confidence')}")
    print(f"VIC Fair Value: {val_vic.get('fair_value')}k")
    print(f"VIC Price Target 1Y: {val_vic.get('price_target')}k")
    
    assert "SOTP" in val_vic.get('valuation_method', ''), "LỖI: VIC phải dùng mô hình SOTP / RNAV!"
    assert val_vic.get('confidence') in ['HIGH', 'MEDIUM', 'LOW'], "LỖI: Confidence không hợp lệ!"
    assert val_vic.get('price_target') is not None, "LỖI: Thiếu price_target tách biệt!"
    print(">>> PASS: Test Case 4 SOTP cho VIC & Methodology hoàn thành chuẩn xác.")

def test_case_5_market_regime_risk_budgeting():
    print("\n--- TEST CASE 5: MARKET REGIME KẾT HỢP RISK BUDGETING ĐA BIẾN ---")
    vnindex_tech = {
        "current_price": 1285.0,
        "ma20": 1280.0,
        "ma50": 1260.0,
        "rsi": 58.0,
        "vol_ratio": 1.15
    }
    regime = evaluate_market_regime(
        vnindex_tech=vnindex_tech,
        market_breadth_pct=62.0,
        portfolio_drawdown_pct=-1.5,
        margin_exposure_pct=10.0
    )
    print(f"Regime: {regime['regime']}")
    print(f"Tag: {regime['tag']}")
    print(f"Tỷ trọng khuyến nghị: Cổ phiếu {regime['stock_pct']} / Tiền {regime['cash_pct']}")
    print(f"Risk Budget Score: {regime['risk_budget_score']}/100")
    print(f"Bias: {regime['bias']}")
    
    assert regime['regime'] in ["BULLISH", "NEUTRAL", "CORRECTION", "RISK-OFF"], "LỖI: Regime không hợp lệ!"
    assert regime['risk_budget_score'] > 0, "LỖI: Risk budget score phải > 0!"
    print(">>> PASS: Test Case 5 Risk Budgeting đa biến hoàn thành chuẩn xác.")

def test_case_6_quant_sanity_check_engine():
    print("\n--- TEST CASE 6: RUN FULL SANITY CHECK ENGINE ---")
    # Test portfolio DF
    df_portfolio = pd.DataFrame([
        {
            'symbol': 'MSB',
            'market_price': 12.80,
            'avg_cost': 12.42,
            'pnl_pct': 3.06,
            'trailing_stop': 12.28,
            'action': 'NẮM GIỮ',
            'note': 'Bảo toàn lợi nhuận, nâng trailing stop lên 12.28k.'
        },
        {
            'symbol': 'FPT',
            'market_price': 135.0,
            'avg_cost': 130.0,
            'pnl_pct': 3.85,
            'trailing_stop': 129.5,
            'action': 'NẮM GIỮ',
            'note': 'Xu hướng tăng duy trì tốt.'
        }
    ])
    
    all_passed, log_issues, verified_df = run_full_portfolio_sanity_check(df_portfolio)
    print(f"Sanity Check All Passed: {all_passed}")
    print(f"Log issues (nếu có): {log_issues}")
    assert all_passed is True, f"LỖI: Sanity check portfolio phát hiện lỗi: {log_issues}"
    print(">>> PASS: Test Case 6 Sanity Check Engine hoàn thành chuẩn xác.")

if __name__ == "__main__":
    print("================================================================")
    print("BẮT ĐẦU KIỂM THỬ TOÀN DIỆN 7 LỖI LOGIC AI STOCK COPILOT V2")
    print("================================================================")
    test_case_1_weighted_rr()
    test_case_2_trailing_stop_clamp_msb()
    test_case_3_value_vs_technical_mwg()
    test_case_4_vic_sotp_and_methodology()
    test_case_5_market_regime_risk_budgeting()
    test_case_6_quant_sanity_check_engine()
    print("\n================================================================")
    print("🎉 TẤT CẢ 6/6 TEST SUITES ĐÃ PASS 100%! TOÁN HỌC & LOGIC CHUẨN XÁC!")
    print("================================================================")
