"""Financial indicators and scoring models."""

import logging
from typing import Any

import numpy as np
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

def calculate_atr(df_history: pd.DataFrame, period: int = 14) -> float:
    """Calculate Average True Range reflecting actual price volatility.

    Args:
        df_history: OHLC DataFrame with 'high', 'low', 'close' columns.
        period: ATR lookback window (default: 14).

    Returns:
        ATR value rounded to 2 decimals, or 0.0 on insufficient data.
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


def _get_f_score_rating(score: int) -> str:
    """Return institutional qualitative rating based on Piotroski F-Score."""
    if score >= 8:
        return "XUẤT SẮC"
    if score >= 6:
        return "TỐT"
    if score >= 4:
        return "TRUNG BÌNH"
    return "YẾU / RỦI RO"


def calculate_piotroski_f_score(fin_dict: dict, sector: str = "") -> dict:
    """Score financial health using Piotroski F-Score model (0-9 scale).

    Evaluates three pillars:
    - Profitability (max 4 pts): ROA, cash flow, ROE, net margin
    - Leverage / Liquidity (max 3 pts): D/E, current ratio, financial leverage
    - Operating Efficiency (max 2 pts): gross margin, ROIC

    Args:
        fin_dict: Financial data with keys: roe, roa, debt_equity,
                  current_ratio, gross_margin, net_margin, p_cf, roic.

    Returns:
        Dict with 'score' (0-9), 'max_score', 'rating', and 'breakdown'.
    """
    if sector in ["Ngân hàng", "Bất động sản"]:
        return {
            "score": 6,
            "max_score": 9,
            "rating": "TRUNG BÌNH - (Ngoại lệ Ngành)",
            "breakdown": {}
        }

    # Support precomputed f_score if breakdown fields are absent
    if fin_dict and fin_dict.get("f_score") is not None and not any(k in fin_dict for k in ("roa", "current_ratio", "debt_equity")):
        raw_s = int(fin_dict["f_score"])
        return {
            "score": raw_s,
            "max_score": 9,
            "rating": _get_f_score_rating(raw_s),
            "breakdown": {"precomputed": raw_s}
        }

    fin_dict = fin_dict or {}
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

    return {
        "score": score,
        "max_score": 9,
        "rating": _get_f_score_rating(score),
        "breakdown": breakdown
    }


def calculate_altman_z_score(fin_dict: dict, sector: str = "") -> dict:
    """Estimate Altman Z''-Score for emerging markets (bankruptcy risk).

    Z'' = 6.56*X1 + 3.26*X2 + 6.72*X3 + 1.05*X4
    - Z >= 2.90: Safe Zone (green)
    - 1.23 <= Z < 2.90: Grey Zone (caution)
    - Z < 1.23: Distress Zone (red)

    Args:
        fin_dict: Financial data with keys: roa, debt_equity, current_ratio.

    Returns:
        Dict with 'z_score', 'zone' description, and 'icon' emoji.
    """
    if sector in ["Ngân hàng", "Bất động sản"]:
        return {"z_score": 3.0, "zone": "VÙNG XANH (Ngoại lệ ngành đặc thù)", "icon": "🟢"}

    if not fin_dict:
        return {"z_score": None, "zone": "Chưa đủ dữ liệu", "icon": "⚪"}

    # Support precomputed z_score if breakdown fields are absent
    if fin_dict.get("z_score") is not None and not any(k in fin_dict for k in ("roa", "debt_equity")):
        raw_z = float(fin_dict["z_score"])
        if raw_z >= 2.90:
            zone = "VÙNG XANH (An toàn tài chính cao)"
            color = "🟢"
        elif raw_z >= 1.80:
            zone = "VÙNG XÁM (Thận trọng / Đòn bẩy vừa)"
            color = "🟡"
        else:
            zone = "VÙNG ĐỎ (Cảnh báo rủi ro kiệt quệ)"
            color = "🔴"
        return {"z_score": raw_z, "zone": zone, "icon": color}
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


def evaluate_smart_money_flow(
    foreign_flow: dict | None = None,
    prop_flow: dict | None = None,
    heavy_sell_threshold_bil: float = -20.0,
    accumulation_threshold_bil: float = 15.0,
) -> dict:
    """Evaluate institutional smart money flow from Foreign and Proprietary trading.

    Returns:
        dict containing institutional status, flags, and recommendation guidance.
    """
    net_foreign = float(foreign_flow.get("net_val_bil", 0.0)) if foreign_flow else 0.0
    net_prop = float(prop_flow.get("net_val_bil", 0.0)) if prop_flow else 0.0
    total_net = net_foreign + net_prop

    heavy_selling = (net_foreign < heavy_sell_threshold_bil) or (total_net < heavy_sell_threshold_bil)
    strong_accumulation = (net_foreign > accumulation_threshold_bil) or (total_net > accumulation_threshold_bil)

    if heavy_selling:
        status = "INSTITUTIONAL_HEAVY_DISTRIBUTION"
        buy_allowed = False
        reason = "Khối ngoại / Tự doanh đang bán ròng quy mô lớn (> 20 tỷ VNĐ)."
    elif strong_accumulation:
        status = "INSTITUTIONAL_STRONG_ACCUMULATION"
        buy_allowed = True
        reason = "Dòng tiền tổ chức mua ròng mạnh mẽ, hỗ trợ đà tăng giá."
    else:
        status = "INSTITUTIONAL_NEUTRAL"
        buy_allowed = True
        reason = "Dòng tiền tổ chức ở mức cân bằng, không có áp lực bán đột biến."

    return {
        "status": status,
        "net_foreign_bil": round(net_foreign, 2),
        "net_prop_bil": round(net_prop, 2),
        "total_net_bil": round(total_net, 2),
        "heavy_selling": heavy_selling,
        "buy_allowed": buy_allowed,
        "reason": reason,
    }


def calculate_factor_exposures(
    asset_returns: pd.Series | list[float],
    market_returns: pd.Series | list[float],
    sector_returns: pd.Series | list[float] | None = None,
) -> dict[str, Any]:
    """Phân rã đa nhân tố lợi suất theo Market Beta và Sector Beta (Phase 5c)."""
    s_asset = pd.Series(asset_returns, dtype=float).dropna()
    s_market = pd.Series(market_returns, dtype=float).dropna()

    if len(s_asset) < 3 or len(s_market) < 3:
        return {
            "market_beta": 1.0,
            "market_r2": 0.0,
            "sector_beta": None,
            "idiosyncratic_alpha_pct": 0.0,
        }

    # Căn chỉnh độ dài chuỗi
    n_min = min(len(s_asset), len(s_market))
    r_a = s_asset.iloc[-n_min:].to_numpy()
    r_m = s_market.iloc[-n_min:].to_numpy()

    var_m = float(np.var(r_m, ddof=1))
    if var_m > 1e-12:
        cov_am = float(np.cov(r_a, r_m)[0, 1])
        market_beta = round(cov_am / var_m, 2)
        corr_m = float(np.corrcoef(r_a, r_m)[0, 1])
        market_r2 = round(corr_m ** 2, 3)
    else:
        market_beta = 1.0
        market_r2 = 0.0

    sector_beta = None
    if sector_returns is not None:
        s_sector = pd.Series(sector_returns, dtype=float).dropna()
        if len(s_sector) >= n_min:
            r_s = s_sector.iloc[-n_min:].to_numpy()
            var_s = float(np.var(r_s, ddof=1))
            if var_s > 1e-12:
                cov_as = float(np.cov(r_a, r_s)[0, 1])
                sector_beta = round(cov_as / var_s, 2)

    # Idiosyncratic Alpha (Lợi suất vượt trội riêng biệt hàng năm sau điều chỉnh beta)
    excess_annual = (np.mean(r_a) - (market_beta * np.mean(r_m))) * 252.0 * 100.0

    return {
        "market_beta": market_beta,
        "market_r2": market_r2,
        "sector_beta": sector_beta,
        "idiosyncratic_alpha_pct": round(float(excess_annual), 2),
    }


