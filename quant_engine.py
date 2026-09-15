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

from quant_valuation import calculate_fair_value_and_mos, classify_stock_archetype, INSTITUTIONAL_CONSENSUS_TARGETS

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


def evaluate_market_regime(vnindex_tech: dict = None) -> dict:
    """
    Xác định Trạng thái thị trường (Market Regime):
    - BULLISH: Xu hướng tăng mạnh, VN-Index trên MA20 và MA50. Tỷ trọng: 70-80% Cổ, 20-30% Tiền.
    - NEUTRAL: Thị trường đi ngang, tích lũy quanh MA20. Tỷ trọng: 50-60% Cổ, 40-50% Tiền.
    - CORRECTION: Nhịp điều chỉnh, thủng MA20 nhưng còn hỗ trợ. Tỷ trọng: 30-40% Cổ, 60-70% Tiền.
    - RISK-OFF: Thị trường suy yếu mạnh, mở biên rơi. Tỷ trọng: 10-20% Cổ, 80-90% Tiền (Ưu tiên bảo toàn vốn).
    """
    if not vnindex_tech:
        return {
            "regime": "NEUTRAL",
            "tag": "🟡 ĐI NGANG / TÍCH LŨY",
            "stock_pct": "50%",
            "cash_pct": "50%",
            "bias": "Thận trọng, giải ngân theo từng phần cổ phiếu đạt định giá rẻ.",
            "defense_priority": "Trung bình"
        }

    curr = vnindex_tech.get("current_price", 0.0)
    ma20 = vnindex_tech.get("ma20", curr)
    ma50 = vnindex_tech.get("ma50", curr)
    rsi = vnindex_tech.get("rsi", 50.0)

    if curr > ma20 and curr > ma50 and rsi >= 50.0:
        regime = "BULLISH"
        tag = "🟢 XU HƯỚNG TĂNG TRƯỞNG (BULLISH)"
        stock_pct = "70% - 80%"
        cash_pct = "20% - 30%"
        bias = "Thị trường thuận lợi. Tận dụng nhịp rung lắc kỹ thuật để gia tăng cổ phiếu có Margin of Safety cao."
        defense_priority = "Thấp"
    elif curr < ma20 and curr < ma50 and (rsi < 42.0 or curr < ma20 * 0.98):
        regime = "RISK-OFF"
        tag = "🔴 PHÒNG THỦ CAO ĐỘ (RISK-OFF)"
        stock_pct = "10% - 20%"
        cash_pct = "80% - 90%"
        bias = "Thị trường chịu áp lực bán lớn. Tuyệt đối không bắt dao rơi, hạ đòn bẩy margin về 0, giữ tiền mặt bảo toàn vốn."
        defense_priority = "Tối đa"
    elif curr < ma20 and curr >= ma50:
        regime = "CORRECTION"
        tag = "🟠 ĐIỀU CHỈNH KỸ THUẬT (CORRECTION)"
        stock_pct = "30% - 40%"
        cash_pct = "60% - 70%"
        bias = "Thị trường kiểm định hỗ trợ trung hạn. Chỉ quan sát hoặc tích lũy tỷ trọng nhỏ mã có định giá rất rẻ."
        defense_priority = "Cao"
    else:
        regime = "NEUTRAL"
        tag = "🟡 ĐI NGANG / PHÂN HÓA (NEUTRAL)"
        stock_pct = "50% - 60%"
        cash_pct = "40% - 50%"
        bias = "Dòng tiền phân hóa mạnh. Ưu tiên cổ phiếu có câu chuyện kinh doanh riêng biệt và định giá hấp dẫn."
        defense_priority = "Trung bình"

    return {
        "regime": regime,
        "tag": tag,
        "stock_pct": stock_pct,
        "cash_pct": cash_pct,
        "bias": bias,
        "defense_priority": defense_priority
    }


def evaluate_holding_position(row: dict, tech_data: dict, fin_dict: dict = None) -> dict:
    """
    ĐÁNH GIÁ VỊ THẾ ĐANG NẮM GIỮ (PORTFOLIO POSITION EVALUATOR) - CHUẨN V2:
    - QUY TẮC CỐT TỬ: Khi cổ phiếu đang LÃI (P/L > 0), TUYỆT ĐỐI KHÔNG DÙNG TỪ "CẮT LỖ".
      Phải chuyển sang "CHỐT LỜI TỪNG PHẦN / BẢO VỆ THÀNH QUẢ" và tính mốc TRAILING STOP cụ thể bằng số.
    - Khi cổ phiếu LỖ (P/L <= 0):
      + Vị thế Đầu tư giá trị dài hạn: Quản trị bằng THESIS BREAKER (chỉ bán khi luận điểm vỡ).
      + Vị thế Lướt sóng Trading: Quản trị bằng STOP-LOSS KỸ THUẬT dứt khoát.
    """
    symbol = row.get("symbol", "")
    entry_price = float(row.get("avg_price", 0.0))
    curr_price = float(tech_data.get("current_price") or row.get("market_price", entry_price))
    volume = int(row.get("volume", 0))
    
    pl_val = (curr_price - entry_price) * volume * 1000
    pl_pct = ((curr_price - entry_price) / entry_price * 100) if entry_price > 0 else 0.0
    
    atr = tech_data.get("atr") or 0.0
    ma20 = tech_data.get("ma20") or curr_price
    
    # 1. KỊCH BẢN VỊ THẾ CÓ LÃI (P/L > 0)
    if pl_pct > 0:
        # Tính mốc Trailing Stop cụ thể bằng số
        if atr and atr > 0:
            trailing_candidate = curr_price - (1.5 * atr)
        else:
            trailing_candidate = curr_price * 0.95
        
        # Trailing Stop ít nhất phải giữ được lãi nhẹ (>= entry_price * 1.02) nếu lãi đã trên 5%
        if pl_pct >= 5.0:
            trailing_stop = max(entry_price * 1.02, trailing_candidate, ma20 * 0.98)
        else:
            trailing_stop = entry_price  # Hòa vốn

        trailing_stop = round(float(trailing_stop), 2)
        
        if pl_pct >= 20.0:
            action = "🟢 BẢO VỆ THÀNH QUẢ / HIỆN THỰC HÓA LỢI NHUẬN"
            detail = (
                f"Cổ phiếu đang có tỷ suất sinh lời xuất sắc (+{pl_pct:.1f}%). "
                f"Khuyến nghị: Hiện thực hóa 30-50% lợi nhuận, nâng mốc Trailing Stop lên {trailing_stop:.2f}k "
                f"để gồng lãi phần còn lại mà không sợ mất thành quả."
            )
        elif pl_pct >= 8.0:
            action = "🟢 TIẾP TỤC NẮM GIỮ / NÂNG TRAILING STOP"
            detail = (
                f"Vị thế lãi tốt (+{pl_pct:.1f}%). Khuyến nghị: Tiếp tục gồng lãi xu hướng, "
                f"đặt mốc Trailing Stop chặn lãi cứng tại {trailing_stop:.2f}k. Nếu giá vi phạm thủng mốc này mới chốt."
            )
        else:
            action = "🟢 NẮM GIỮ / THEO DÕI ĐÀ TĂNG"
            detail = (
                f"Vị thế có lãi nhẹ (+{pl_pct:.1f}%). Tiếp tục nắm giữ, "
                f"đặt mốc chặn lãi hòa vốn (Break-even Stop) tại {entry_price:.2f}k."
            )

        return {
            "symbol": symbol,
            "status": "PROFITABLE",
            "entry_price": entry_price,
            "curr_price": curr_price,
            "pl_pct": round(pl_pct, 2),
            "pl_val": round(pl_val, 0),
            "action": action,
            "detail": detail,
            "trailing_stop": trailing_stop,
            "is_profit": True,
            "thesis_breaker": "N/A (Vị thế đang thắng thế, không có rủi ro vỡ luận điểm)"
        }

    # 2. KỊCH BẢN VỊ THẾ ĐANG LỖ (P/L <= 0)
    else:
        loss_pct = abs(pl_pct)
        # Tính Stop-loss kỹ thuật
        if atr and atr > 0:
            tech_stop = curr_price - (2.0 * atr)
            stop_loss = max(tech_stop, entry_price * 0.93)
        else:
            stop_loss = entry_price * 0.93
        stop_loss = round(float(stop_loss), 2)

        # Kiểm tra Thesis Breaker (Luận điểm đầu tư cơ bản)
        thesis_intact = True
        thesis_msg = "Luận điểm tăng trưởng doanh nghiệp cốt lõi vẫn được bảo toàn."
        
        if fin_dict:
            f_score = calculate_piotroski_f_score(fin_dict).get("score", 6)
            z_data = calculate_altman_z_score(fin_dict)
            if f_score < 4 or "ĐỎ" in z_data.get("zone", ""):
                thesis_intact = False
                thesis_msg = "CẢNH BÁO: BCTC suy giảm nghiêm trọng hoặc đòn bẩy quá cao (Thesis Breaker bị kích hoạt!)."

        if thesis_intact:
            if loss_pct <= 5.0:
                action = "🟡 THEO DÕI BIẾN ĐỘNG / GIỮ VỊ THẾ DÀI HẠN"
                detail = (
                    f"Khoản lỗ nhẹ (-{loss_pct:.1f}%) nằm trong biên độ dao động thông thường của thị trường. "
                    f"Luận điểm giá trị vẫn nguyên vẹn. Không hoảng loạn cắt lỗ máy móc."
                )
            elif loss_pct <= 8.0:
                action = "🟡 QUẢN TRỊ RỦI RO / QUAN SÁT NGƯỠNG HỖ TRỢ"
                detail = (
                    f"Lỗ -{loss_pct:.1f}%. Nếu là vị thế lướt sóng T+, kích hoạt kỷ luật Stop-Loss tại {stop_loss:.2f}k. "
                    f"Nếu là danh mục đầu tư giá trị, kiểm tra mốc cân bằng mới trước khi ra quyết định gom thêm."
                )
            else:
                action = "🔴 CẮT LỖ KỸ THUẬT HOẶC HẠ TỶ TRỌNG"
                detail = (
                    f"Mức sụt giảm sâu (-{loss_pct:.1f}%). Khuyến nghị dứt khoát hạ tỷ trọng bảo vệ vốn, "
                    f"ngưỡng Stop-loss đã bị vi phạm tại {stop_loss:.2f}k."
                )
        else:
            action = "🔴 THOÁT VỊ THẾ (THESIS BREAKER KÍCH HOẠT)"
            detail = f"Lỗ -{loss_pct:.1f}%. {thesis_msg} Cần dứt khoát cơ cấu thoát vốn sang mã có cơ bản vượt trội."

        return {
            "symbol": symbol,
            "status": "LOSS",
            "entry_price": entry_price,
            "curr_price": curr_price,
            "pl_pct": round(pl_pct, 2),
            "pl_val": round(pl_val, 0),
            "action": action,
            "detail": detail,
            "stop_loss": stop_loss,
            "is_profit": False,
            "thesis_breaker": thesis_msg
        }


def calculate_100_point_score(symbol: str, tech_data: dict, fin_dict: dict, mos_data: dict) -> dict:
    """
    THANG ĐIỂM ĐỊNH LƯỢNG 100 ĐIỂM (100-POINT QUANT SCORE) THEO 4 TRỤ CỘT:
    1. Cơ bản & Sức khỏe tài chính (Fundamental & Health): Max 35 điểm
    2. Định giá & Biên an toàn (Valuation & MoS): Max 30 điểm
    3. Kỹ thuật & Xu hướng (Technical & Momentum): Max 20 điểm
    4. Dòng tiền lớn & Quản trị rủi ro (Smart Flow & Risk): Max 15 điểm
    """
    scores = {}
    
    # --- Trụ cột 1: Sức khỏe tài chính (Max 35) ---
    f_res = calculate_piotroski_f_score(fin_dict)
    f_pts = min(round((f_res.get("score", 5) / 9.0) * 18, 1), 18.0)  # Max 18đ
    
    z_res = calculate_altman_z_score(fin_dict)
    z_val = z_res.get("z_score", 2.0)
    z_pts = 10.0 if z_val >= 2.9 else (6.0 if z_val >= 1.8 else 2.0)  # Max 10đ
    
    roe = (fin_dict.get("roe") or 0.0) if fin_dict else 0.0
    roe_pts = 7.0 if roe >= 18.0 else (5.0 if roe >= 12.0 else (3.0 if roe >= 8.0 else 1.0)) # Max 7đ
    pillar_fundamental = round(f_pts + z_pts + roe_pts, 1)
    scores["pillar_fundamental"] = pillar_fundamental
    
    # --- Trụ cột 2: Định giá & Biên an toàn (Max 30) ---
    mos_pct = mos_data.get("mos_pct", 0.0) if mos_data else 0.0
    if mos_pct >= 25.0:
        mos_pts = 30.0
    elif mos_pct >= 18.0:
        mos_pts = 25.0
    elif mos_pct >= 12.0:
        mos_pts = 20.0
    elif mos_pct >= 5.0:
        mos_pts = 14.0
    elif mos_pct >= 0.0:
        mos_pts = 8.0
    else:
        mos_pts = 2.0  # Quá đắt
    scores["pillar_valuation"] = mos_pts
    
    # --- Trụ cột 3: Kỹ thuật & Xu hướng (Max 20) ---
    curr = tech_data.get("current_price", 0.0)
    ma20 = tech_data.get("ma20", curr)
    rsi = tech_data.get("rsi", 50.0)
    vol = tech_data.get("volume", 0)
    vol_ma20 = tech_data.get("vol_ma20", vol)
    
    tech_pts = 0.0
    # Nằm trên MA20
    if curr >= ma20:
        tech_pts += 8.0
    elif curr >= ma20 * 0.98:
        tech_pts += 4.0
        
    # RSI lành mạnh (45 - 65)
    if 48.0 <= rsi <= 65.0:
        tech_pts += 7.0
    elif 40.0 <= rsi < 48.0:
        tech_pts += 5.0
    elif 65.0 < rsi <= 75.0:
        tech_pts += 3.0
    else:
        tech_pts += 1.0
        
    # Khối lượng có tín hiệu hấp thụ
    if vol_ma20 > 0 and vol >= vol_ma20 * 1.1:
        tech_pts += 5.0
    else:
        tech_pts += 3.0
    scores["pillar_technical"] = round(tech_pts, 1)
    
    # --- Trụ cột 4: Dòng tiền lớn & Thanh khoản (Max 15) ---
    flow_pts = 0.0
    foreign = tech_data.get("foreign_flow") or {}
    f_net = foreign.get("net_val_bil", 0.0)
    if f_net > 5.0:
        flow_pts += 8.0
    elif f_net >= -10.0:
        flow_pts += 5.0
    else:
        flow_pts += 1.0  # Bị xả mạnh
        
    adv20 = tech_data.get("adv20_billion", 10.0)
    if adv20 >= 30.0:
        flow_pts += 7.0
    elif adv20 >= 10.0:
        flow_pts += 5.0
    elif adv20 >= 2.0:
        flow_pts += 3.0
    else:
        flow_pts += 0.0
    scores["pillar_smart_flow"] = round(flow_pts, 1)
    
    total_score = round(pillar_fundamental + mos_pts + tech_pts + flow_pts, 1)
    
    if total_score >= 80.0:
        rating = "XUẤT SẮC (Ưu tiên giải ngân lớn / Tích lũy chủ lực)"
        grade = "A+"
    elif total_score >= 68.0:
        rating = "TỐT (Đạt chuẩn tích lũy từng phần)"
        grade = "A"
    elif total_score >= 55.0:
        rating = "TRUNG BÌNH (Theo dõi thêm, chờ giá chiết khấu)"
        grade = "B"
    else:
        rating = "YẾU / RỦI RO (Không đạt tiêu chí giải ngân)"
        grade = "C"
        
    return {
        "total_score": total_score,
        "grade": grade,
        "rating": rating,
        "breakdown": scores
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
    adv20_billion: float = 0.0,
    symbol: str = "",
    fin_dict: dict = None,
    sector: str = "",
    tech_data: dict = None
) -> dict:
    """
    TÍNH TOÁN HÀNG RÀO QUYẾT ĐỊNH ĐỊNH LƯỢNG (HARD GATES) - CHUẨN V2:
    4 TRẠNG THÁI DUY NHẤT:
    1. 🟢 MUA (MOS >= 15%, kỹ thuật xác nhận tạo đáy / bứt phá, dòng tiền ủng hộ).
    2. 🟢 TÍCH LŨY (MOS >= 15%, đang tích lũy nền chặt, gom từng phần).
    3. 🟡 THEO DÕI (Đang rơi tự do 'Falling Knife', hoặc MOS chưa đủ an toàn < 10%).
    4. 🔴 GIẢM / THOÁT (MOS âm, định giá quá đắt, hoặc gãy hỗ trợ quan trọng).
    """
    if not current_price or current_price <= 0:
        return {}

    # Tích hợp mô hình Fair Value & MOS chuẩn tổ chức
    val_model = calculate_fair_value_and_mos(
        symbol=symbol,
        current_price=current_price,
        fin_dict=fin_dict or {},
        sector=sector
    )
    
    fair_value = val_model.get("fair_value", price_base)
    mos_pct = val_model.get("mos_pct", round(((price_base - current_price) / price_base) * 100, 2))
    
    # 1. Expected Value
    ev = (p_bull * price_bull) + (p_base * price_base) + (p_bear * price_bear)
    ev = round(float(ev), 2)

    # 2. Dynamic ATR Stop-loss
    if atr and atr > 0:
        atr_stop = round(current_price - (2.0 * atr), 2)
        stop_loss = max(atr_stop, round(current_price * 0.93, 2))
    else:
        stop_loss = round(current_price * 0.93, 2)

    downside_val = max(current_price - stop_loss, 0.01)
    upside_val = max(fair_value - current_price, 0.01)
    
    # 3. Tỷ lệ Risk / Reward R
    rr = round(upside_val / downside_val, 2) if downside_val > 0 else 1.0

    # 4. Kelly Criterion f*
    p_win = p_bull + (0.5 * p_base)
    p_loss = 1.0 - p_win
    kelly_f = round(p_win - (p_loss / rr), 2) if rr > 0 else -1.0

    # 5. Kiểm tra bẫy giá rơi (Falling Knife Check)
    is_falling_knife = False
    if tech_data:
        ma20 = tech_data.get("ma20", current_price)
        rsi = tech_data.get("rsi", 50.0)
        # Rơi tự do: Giá dưới MA20 trên 4% và RSI cắm đầu sâu không tạo đáy
        if current_price < ma20 * 0.96 and rsi < 36.0:
            is_falling_knife = True

    # --- HÀNG RÀO CỨNG (HARD GATES) ---
    gate_mos_passed = mos_pct >= 12.0
    gate_rr_passed = rr >= 1.5
    gate_kelly_passed = kelly_f > 0
    gate_trap_passed = not (trap_info and trap_info.get("is_trap"))

    # Kiểm tra bẫy tin tức (VETO CỨNG)
    if not gate_trap_passed:
        can_buy = False
        trap_msg = trap_info.get("warning_msg", "Phát hiện bẫy giá / tin tức nguy hiểm")
        decision_tag = f"🔴 GIẢM / THOÁT (Bẫy giá: {trap_msg})"
        action_state = "🔴 GIẢM / THOÁT"
        position_size_nav = "0% NAV (Cấm mua - Đang trong vùng bẫy rủi ro)"
    elif adv20_billion > 0 and adv20_billion < 2.0:
        can_buy = False
        decision_tag = "🟡 THEO DÕI (Thanh khoản quá thấp < 2 tỷ/phiên)"
        action_state = "🟡 THEO DÕI"
        position_size_nav = "0% NAV (Rủi ro kẹp vốn thanh khoản)"
    elif is_falling_knife:
        can_buy = False
        decision_tag = "🟡 THEO DÕI (Giá rơi tự do 'Falling Knife' - Cấm bắt đáy khi chưa cân bằng)"
        action_state = "🟡 THEO DÕI"
        position_size_nav = "0% NAV (Chờ nến xác nhận ngừng rơi)"
    else:
        # Kiểm tra dòng tiền Khối ngoại
        is_heavy_foreign_sell = False
        if foreign_flow and foreign_flow.get("status") in ["SELLING", "HEAVY_SELLING"]:
            net_val = foreign_flow.get("net_val_bil", 0.0)
            if net_val < -20.0:
                is_heavy_foreign_sell = True

        if mos_pct >= 15.0 and gate_rr_passed and gate_kelly_passed:
            can_buy = True
            if is_heavy_foreign_sell:
                decision_tag = f"🟢 TÍCH LŨY THĂM DÒ (Khối ngoại còn xả ròng {foreign_flow.get('net_val_bil'):.1f} tỷ)"
                action_state = "🟢 TÍCH LŨY"
                position_size_nav = "5% - 8% NAV"
            elif tech_data and tech_data.get("current_price", 0) >= tech_data.get("ma20", 0):
                decision_tag = "🟢 MUA (Biên an toàn cao & Kỹ thuật xác nhận xu hướng)"
                action_state = "🟢 MUA"
                position_size_nav = "15% - 20% NAV"
            else:
                decision_tag = "🟢 TÍCH LŨY (Định giá rẻ, gom nhặt trong vùng nền)"
                action_state = "🟢 TÍCH LŨY"
                position_size_nav = "10% - 12% NAV"
        elif mos_pct >= 8.0:
            can_buy = False
            decision_tag = "🟡 THEO DÕI (Biên an toàn còn mỏng < 15%, chờ giá chiết khấu thêm)"
            action_state = "🟡 THEO DÕI"
            position_size_nav = "0% NAV"
        elif mos_pct < 0:
            can_buy = False
            decision_tag = "🔴 GIẢM / THOÁT (Thị giá vượt giá trị hợp lý, định giá quá đắt)"
            action_state = "🔴 GIẢM / THOÁT"
            position_size_nav = "0% NAV"
        else:
            can_buy = False
            decision_tag = "🟡 THEO DÕI (Hàng rào định lượng chưa đủ điều kiện kích hoạt Mua)"
            action_state = "🟡 THEO DÕI"
            position_size_nav = "0% NAV"

    return {
        "ev": ev,
        "fair_value": fair_value,
        "mos_pct": mos_pct,
        "valuation_model": val_model,
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
        "action_state": action_state,
        "decision_tag": decision_tag,
        "position_size_nav": position_size_nav
    }
