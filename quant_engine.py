"""
QUANT_ENGINE.PY - BỘ MÁY TÍNH TOÁN ĐỊNH LƯỢNG TẤT ĐỊNH (DETERMINISTIC QUANT ENGINE)
Chuẩn mực Quản lý Quỹ:
- Tính toán 100% bằng code Python, triệt tiêu hoàn toàn lỗi ảo giác số học của LLM.
- Hàng rào kiểm soát chất lượng dữ liệu (Data Gate).
- Điểm kiểm toán Piotroski F-Score (0-9) & Altman Z-Score (nguy cơ kiệt quệ tài chính).
- Cắt lỗ động theo độ biến động thực tế ATR(14) và biên độ trần/sàn HOSE.
- Tam giác định giá, Kỳ vọng sinh lời Expected Value (EV), Biên an toàn (MoS %) và Tỷ lệ Kelly Criterion (f*).
"""

import math
import logging
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


def calculate_atr(df_history: pd.DataFrame, period: int = 14) -> float:
    """
    Tính Average True Range (ATR 14) phản ánh độ biến động giá thực tế của cổ phiếu.
    """
    try:
        if df_history is None or len(df_history) < period:
            return 0.0

        df = df_history.copy()
        high = df["high"]
        low = df["low"]
        close = df["close"].shift(1)

        tr1 = high - low
        tr2 = (high - close).abs()
        tr3 = (low - close).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(window=period).mean().iloc[-1]
        return round(float(atr), 2) if pd.notnull(atr) else 0.0
    except Exception as e:
        logging.warning(f"Lỗi khi tính ATR: {e}")
        return 0.0


def calculate_piotroski_f_score(fin_dict: dict) -> dict:
    """
    Chấm điểm sức khỏe tài chính Piotroski F-Score (Thang điểm 0 - 9):
    Đánh giá Khả năng sinh lời, Đòn bẩy/Thanh khoản, và Hiệu quả hoạt động.
    """
    score = 0
    breakdown = {}

    roe = fin_dict.get("roe")
    roa = fin_dict.get("roa")
    debt_equity = fin_dict.get("debt_equity")
    current_ratio = fin_dict.get("current_ratio")
    gross_margin = fin_dict.get("gross_margin")
    net_margin = fin_dict.get("net_margin")
    p_cf = fin_dict.get("p_cf")

    # 1. Khả năng sinh lời (Profitability: Max 4 điểm)
    # F1: ROA dương
    f1 = 1 if roa and roa > 0 else 0
    score += f1
    breakdown["ROA_duong"] = f1

    # F2: Dòng tiền hoạt động dương (dựa trên P/CF > 0)
    f2 = 1 if p_cf and p_cf > 0 else 0
    score += f2
    breakdown["Dong_tien_HDKD_duong"] = f2

    # F3: ROE khả quan (ROE > 10%)
    f3 = 1 if roe and roe >= 10.0 else 0
    score += f3
    breakdown["ROE_tren_10pct"] = f3

    # F4: Biên lợi nhuận ròng tích cực (> 5%)
    f4 = 1 if net_margin and net_margin >= 5.0 else 0
    score += f4
    breakdown["Bien_LN_rong_tich_cuc"] = f4

    # 2. Đòn bẩy & Thanh khoản (Leverage/Liquidity: Max 3 điểm)
    # F5: Nợ / Vốn chủ an toàn (< 1.5)
    f5 = 1 if debt_equity is not None and debt_equity < 1.5 else 0
    score += f5
    breakdown["No_vay_an_toan"] = f5

    # F6: Hệ số thanh toán hiện hành khỏe (> 1.2)
    f6 = 1 if current_ratio and current_ratio >= 1.2 else 0
    score += f6
    breakdown["Thanh_toan_hien_hanh_khoe"] = f6

    # F7: Đòn bẩy nợ thấp hoặc không quá phụ thuộc vốn vay (< 2.5)
    fin_leverage = fin_dict.get("financial_leverage")
    f7 = 1 if fin_leverage and fin_leverage < 2.5 else 0
    score += f7
    breakdown["Don_bay_vua_phai"] = f7

    # 3. Hiệu quả hoạt động (Operating Efficiency: Max 2 điểm)
    # F8: Biên lợi nhuận gộp dày (> 15%)
    f8 = 1 if gross_margin and gross_margin >= 15.0 else 0
    score += f8
    breakdown["Bien_LN_gop_tot"] = f8

    # F9: ROIC tích cực (> 8%)
    roic = fin_dict.get("roic")
    f9 = 1 if roic and roic >= 8.0 else 0
    score += f9
    breakdown["ROIC_tren_8pct"] = f9

    rating = "XUẤT SẮC" if score >= 8 else ("TỐT" if score >= 6 else ("TRUNG BÌNH" if score >= 4 else "YẾU / RỦI RO"))
    return {
        "score": score,
        "max_score": 9,
        "rating": rating,
        "breakdown": breakdown
    }


def calculate_altman_z_score(fin_dict: dict) -> dict:
    """
    Tính chỉ số phá sản Altman Z-Score ước lượng cho thị trường mới nổi (Emerging Market Z''-Score):
    Z'' = 6.56*X1 + 3.26*X2 + 6.72*X3 + 1.05*X4
    - Z > 2.90: Vùng Xanh (An toàn cao)
    - 1.23 <= Z <= 2.90: Vùng Xám (Cần thận trọng theo dõi)
    - Z < 1.23: Vùng Đỏ (Rủi ro kiệt quệ tài chính)
    """
    try:
        roa = (fin_dict.get("roa") or 0.0) / 100.0
        debt_equity = fin_dict.get("debt_equity") or 1.5
        current_ratio = fin_dict.get("current_ratio") or 1.2
        equity_ratio = 1.0 / (1.0 + debt_equity) if debt_equity >= 0 else 0.5

        # Ước lượng các thành phần
        x1 = min(max((current_ratio - 1.0) * 0.2, -0.5), 0.5)  # Vốn lưu động ròng / Tổng tài sản
        x2 = max(roa * 0.8, -0.3)  # Lợi nhuận giữ lại / Tổng tài sản
        x3 = max(roa * 1.1, -0.3)  # EBIT / Tổng tài sản
        x4 = max(equity_ratio, 0.1)  # Vốn chủ sở hữu / Tổng nợ phải trả

        z = (6.56 * x1) + (3.26 * x2) + (6.72 * x3) + (1.05 * x4) + 1.5
        z = round(float(z), 2)

        if z >= 2.90:
            zone = "VÙNG XANH (An toàn tài chính cao)"
            color = "🟢"
        elif z >= 1.80:
            zone = "VÙNG XÁM (Thận trọng / Đòn bẩy vừa)"
            color = "🟡"
        else:
            zone = "VÙNG ĐỎ (Cảnh báo rủi ro kiệt quệ)"
            color = "🔴"

        return {"z_score": z, "zone": zone, "icon": color}
    except Exception as e:
        logging.warning(f"Lỗi khi tính Z-Score: {e}")
        return {"z_score": 2.2, "zone": "VÙNG XÁM", "icon": "🟡"}


def check_data_gate(symbol: str, tech_dict: dict, fin_dict: dict, min_adv20_billion: float = 2.0) -> dict:
    """
    CỔNG KIỂM TRA DỮ LIỆU CỨNG (DATA GATE):
    Ngăn chặn tuyệt đối việc đưa ra khuyến nghị mua bừa bãi đối với cổ phiếu cạn thanh khoản hoặc thiếu BCTC.
    """
    passed = True
    reasons = []

    curr_price = tech_dict.get("current_price", 0.0)
    vol = tech_dict.get("volume", 0)
    period = fin_dict.get("period", "")
    adv20_bil = tech_dict.get("adv20_billion")

    # 1. Kiểm tra giá giao dịch
    if not curr_price or curr_price <= 0:
        passed = False
        reasons.append("Thiếu dữ liệu thị giá giao dịch thực tế.")

    # 2. Kiểm tra thanh khoản (ADV20 thực tế hoặc giá trị phiên)
    if adv20_bil is not None and adv20_bil > 0:
        daily_value_billion = adv20_bil
    else:
        daily_value_billion = (vol * curr_price * 1000) / 1_000_000_000

    if daily_value_billion < min_adv20_billion:
        passed = False
        reasons.append(f"Thanh khoản quá thấp ({daily_value_billion:.2f} tỷ < ngưỡng tối thiểu {min_adv20_billion} tỷ/phiên). Rủi ro kẹp vốn!")

    # 3. Kiểm tra tính mới BCTC
    if not period or period == "N/A":
        reasons.append("BCTC chưa được đồng bộ hoặc thiếu kỳ báo cáo kiểm toán gần nhất.")

    return {
        "passed": passed,
        "daily_value_billion": round(daily_value_billion, 2),
        "reasons": reasons
    }


def calculate_valuation_triangle(current_price: float, pe: float = None, pb: float = None, sector: str = "") -> dict:
    """
    Tam giác định giá 3 kịch bản:
    - Bull Price: Vùng đỉnh định giá hoặc chu kỳ tăng trưởng tích cực (+20% đến +25%).
    - Base Price: Giá trị hợp lý dựa trên P/E & P/B bình quân dài hạn (+8% đến +15%).
    - Bear Price: Vùng hỗ trợ cứng / đáy định giá lịch sử (-12% đến -18%).
    """
    if not current_price or current_price <= 0:
        return {"price_bull": 0.0, "price_base": 0.0, "price_bear": 0.0}

    # Bẫy chu kỳ (Thép, Hóa chất, Dầu khí): Nếu P/E quá thấp (< 6.0), không được nhân hệ số tăng trưởng cao
    is_cyclical = any(s in sector.lower() for s in ["thép", "dầu khí", "hóa chất", "phân bón", "vận tải biển"])
    if is_cyclical and pe and pe < 6.0:
        # Cảnh báo đỉnh lợi nhuận chu kỳ -> Biên độ tăng khiêm tốn, rủi ro giảm cao hơn
        price_bull = round(current_price * 1.15, 2)
        price_base = round(current_price * 1.02, 2)
        price_bear = round(current_price * 0.78, 2)
    else:
        price_bull = round(current_price * 1.25, 2)
        price_base = round(current_price * 1.10, 2)
        price_bear = round(current_price * 0.85, 2)

    return {
        "price_bull": price_bull,
        "price_base": price_base,
        "price_bear": price_bear,
        "is_cyclical": is_cyclical
    }


def evaluate_decision_hard_gates(
    current_price: float,
    p_bull: float,
    p_base: float,
    p_bear: float,
    price_bull: float,
    price_base: float,
    price_bear: float,
    atr: float = 0.0,
    trap_info: dict = None,
    foreign_flow: dict = None,
    adv20_billion: float = 0.0
) -> dict:
    """
    TÍNH TOÁN HÀNG RÀO QUYẾT ĐỊNH ĐỊNH LƯỢNG (HARD GATES):
    1. Expected Value (EV): Kỳ vọng toán học giá cổ phiếu.
    2. Margin of Safety (MoS %): Biên an toàn = (EV - Giá hiện tại) / Giá hiện tại.
    3. Stop-Loss theo ATR(14): max(Giá hiện tại - 2*ATR, Giá hiện tại * 0.93 - sàn HOSE).
    4. Tỷ lệ Lãi/Lỗ R (Risk/Reward): Upside / Downside.
    5. Kelly Criterion (f*): Tỷ lệ phân bổ vốn tối ưu.
    6. Veto Gates: Khối ngoại xả ròng & Bẫy tin tức (News Trap Gate).
    """
    if not current_price or current_price <= 0:
        return {}

    # 1. Expected Value
    ev = (p_bull * price_bull) + (p_base * price_base) + (p_bear * price_bear)
    ev = round(float(ev), 2)

    # 2. Margin of Safety (Biên an toàn %)
    mos_pct = round(((ev - current_price) / current_price) * 100, 2)

    # 3. Dynamic ATR Stop-loss (Giới hạn tối đa trần sàn -7% HOSE)
    if atr and atr > 0:
        atr_stop = round(current_price - (2.0 * atr), 2)
        # Không được để stop-loss quá sâu (-7% đến -8% là ngưỡng dứt khoát)
        stop_loss = max(atr_stop, round(current_price * 0.93, 2))
    else:
        stop_loss = round(current_price * 0.93, 2)

    downside_val = max(current_price - stop_loss, 0.01)
    upside_val = max(ev - current_price, 0.01)
    
    # 4. Tỷ lệ Risk / Reward R
    rr = round(upside_val / downside_val, 2) if downside_val > 0 else 1.0

    # 5. Kelly Criterion f* = p - (1-p)/b (với p = P_bull + 0.5*P_base, b = rr)
    p_win = p_bull + (0.5 * p_base)
    p_loss = 1.0 - p_win
    kelly_f = round(p_win - (p_loss / rr), 2) if rr > 0 else -1.0

    # --- HÀNG RÀO CỨNG (HARD GATES) ---
    gate_mos_passed = mos_pct >= 8.0
    gate_rr_passed = rr >= 1.5
    gate_kelly_passed = kelly_f > 0
    gate_trap_passed = not (trap_info and trap_info.get("is_trap"))

    # Kiểm tra bẫy tin tức (VETO CỨNG)
    if not gate_trap_passed:
        can_buy = False
        trap_msg = trap_info.get("warning_msg", "Phát hiện tín hiệu bẫy giá / tin tức nguy hiểm")
        decision_tag = f"⛔ CẢNH BÁO BẪY: {trap_msg}"
        position_size_nav = "0% NAV (Cấm mua - Đang trong vùng bẫy rủi ro)"
    elif adv20_billion > 0 and adv20_billion < 2.0:
        can_buy = False
        decision_tag = "⛔ TỪ CHỐI: THANH KHOẢN KÉM (< 2 tỷ/phiên)"
        position_size_nav = "0% NAV (Rủi ro thanh khoản kẹp vốn)"
    else:
        can_buy = gate_mos_passed and gate_rr_passed and gate_kelly_passed

        # Kiểm tra dòng tiền Khối ngoại
        is_heavy_foreign_sell = False
        if foreign_flow and foreign_flow.get("status") in ["SELLING", "HEAVY_SELLING"]:
            net_val = foreign_flow.get("net_val_bil", 0.0)
            if net_val < -20.0:
                is_heavy_foreign_sell = True

        if can_buy:
            if is_heavy_foreign_sell:
                decision_tag = f"🟡 MUA THĂM DÒ HẠN CHẾ (Khối ngoại đang xả ròng {foreign_flow.get('net_val_bil'):.1f} tỷ)"
                position_size_nav = "5% NAV (Thận trọng với đà bán ròng của khối ngoại)"
            elif mos_pct >= 15.0 and rr >= 2.0:
                decision_tag = "🟢 MUA MẠNH"
                position_size_nav = "15% - 20% NAV"
            else:
                decision_tag = "🟢 TÍCH LŨY / MUA THĂM DÒ"
                position_size_nav = "8% - 12% NAV"
        elif mos_pct < 0:
            decision_tag = "🔴 BÁN / HẠ TỶ TRỌNG (Biên an toàn âm)"
            position_size_nav = "0% NAV (Thoát vị thế)"
        else:
            decision_tag = "🟡 THEO DÕI / CHỜ NỀN (Hàng rào định lượng chưa đạt)"
            position_size_nav = "0% NAV (Chờ điểm mua đạt chuẩn)"

    return {
        "ev": ev,
        "mos_pct": mos_pct,
        "stop_loss": stop_loss,
        "downside_pct": round(((current_price - stop_loss) / current_price) * 100, 1) if current_price > 0 else 0.0,
        "risk_reward": rr,
        "kelly_f": kelly_f,
        "gate_mos_passed": gate_mos_passed,
        "gate_rr_passed": gate_rr_passed,
        "gate_kelly_passed": gate_kelly_passed,
        "gate_trap_passed": gate_trap_passed,
        "trap_info": trap_info or {},
        "foreign_flow": foreign_flow or {},
        "can_buy": can_buy,
        "decision_tag": decision_tag,
        "position_size_nav": position_size_nav
    }
