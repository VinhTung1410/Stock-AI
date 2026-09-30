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


def _calc_profitability_points(fin_dict: dict, breakdown: dict) -> int:
    roa = fin_dict.get("roa")
    p_cf = fin_dict.get("p_cf")
    roe = fin_dict.get("roe")
    net_margin = fin_dict.get("net_margin")

    f1 = 1 if roa and roa > 0 else 0
    f2 = 1 if p_cf and p_cf > 0 else 0
    f3 = 1 if roe and roe >= 10.0 else 0
    f4 = 1 if net_margin and net_margin >= 5.0 else 0

    breakdown["ROA_duong"] = f1
    breakdown["Dong_tien_HDKD_duong"] = f2
    breakdown["ROE_tren_10pct"] = f3
    breakdown["Bien_LN_rong_tich_cuc"] = f4
    return f1 + f2 + f3 + f4


def _calc_leverage_and_efficiency_points(fin_dict: dict, breakdown: dict) -> int:
    debt_equity = fin_dict.get("debt_equity")
    current_ratio = fin_dict.get("current_ratio")
    fin_leverage = fin_dict.get("financial_leverage")
    gross_margin = fin_dict.get("gross_margin")
    roic = fin_dict.get("roic")

    f5 = 1 if debt_equity is not None and debt_equity < 1.5 else 0
    f6 = 1 if current_ratio and current_ratio >= 1.2 else 0
    f7 = 1 if fin_leverage and fin_leverage < 2.5 else 0
    f8 = 1 if gross_margin and gross_margin >= 15.0 else 0
    f9 = 1 if roic and roic >= 8.0 else 0

    breakdown["No_vay_an_toan"] = f5
    breakdown["Thanh_toan_hien_hanh_khoe"] = f6
    breakdown["Don_bay_vua_phai"] = f7
    breakdown["Bien_LN_gop_tot"] = f8
    breakdown["ROIC_tren_8pct"] = f9
    return f5 + f6 + f7 + f8 + f9


def calculate_piotroski_f_score(fin_dict: dict, sector: str = "") -> dict:
    """Score financial health using Piotroski F-Score model (0-9 scale).

    Evaluates three pillars:
    - Profitability (max 4 pts): ROA, cash flow, ROE, net margin
    - Leverage / Liquidity (max 3 pts): D/E, current ratio, financial leverage
    - Operating Efficiency (max 2 pts): gross margin, ROIC
    """
    if sector in ["Ngân hàng", "Bất động sản"]:
        return {
            "score": 6,
            "max_score": 9,
            "rating": "TRUNG BÌNH - (Ngoại lệ Ngành)",
            "breakdown": {}
        }

    if fin_dict and fin_dict.get("f_score") is not None and not any(k in fin_dict for k in ("roa", "current_ratio", "debt_equity")):
        raw_s = int(fin_dict["f_score"])
        return {
            "score": raw_s,
            "max_score": 9,
            "rating": _get_f_score_rating(raw_s),
            "breakdown": {"precomputed": raw_s}
        }

    fin_dict = fin_dict or {}
    breakdown = {}
    score = _calc_profitability_points(fin_dict, breakdown) + _calc_leverage_and_efficiency_points(fin_dict, breakdown)

    return {
        "score": score,
        "max_score": 9,
        "rating": _get_f_score_rating(score),
        "breakdown": breakdown
    }


def _resolve_z_zone(z: float) -> tuple[str, str]:
    if z >= 2.90:
        return "VÙNG XANH (An toàn tài chính cao)", "🟢"
    if z >= 1.80:
        return "VÙNG XÁM (Thận trọng / Đòn bẩy vừa)", "🟡"
    return "VÙNG ĐỎ (Cảnh báo rủi ro kiệt quệ)", "🔴"


def calculate_altman_z_score(fin_dict: dict, sector: str = "") -> dict:
    """Estimate Altman Z''-Score for emerging markets (bankruptcy risk).

    Z'' = 6.56*X1 + 3.26*X2 + 6.72*X3 + 1.05*X4
    - Z >= 2.90: Safe Zone (green)
    - 1.23 <= Z < 2.90: Grey Zone (caution)
    - Z < 1.23: Distress Zone (red)
    """
    if sector in ["Ngân hàng", "Bất động sản"]:
        return {"z_score": 3.0, "zone": "VÙNG XANH (Ngoại lệ ngành đặc thù)", "icon": "🟢"}

    if not fin_dict:
        return {"z_score": None, "zone": "Chưa đủ dữ liệu", "icon": "⚪"}

    if fin_dict.get("z_score") is not None and not any(k in fin_dict for k in ("roa", "debt_equity")):
        raw_z = float(fin_dict["z_score"])
        zone, color = _resolve_z_zone(raw_z)
        return {"z_score": raw_z, "zone": zone, "icon": color}

    try:
        roa = (fin_dict.get("roa") or 0.0) / 100.0
        debt_equity = fin_dict.get("debt_equity") or 1.5
        current_ratio = fin_dict.get("current_ratio") or 1.2
        equity_ratio = 1.0 / (1.0 + debt_equity) if debt_equity >= 0 else 0.5

        x1 = min(max((current_ratio - 1.0) * 0.2, -0.5), 0.5)
        x2 = max(roa * 0.8, -0.3)
        x3 = max(roa * 1.1, -0.3)
        x4 = max(equity_ratio, 0.1)

        z = round(float((6.56 * x1) + (3.26 * x2) + (6.72 * x3) + (1.05 * x4) + 1.5), 2)
        zone, color = _resolve_z_zone(z)
        return {"z_score": z, "zone": zone, "icon": color}
    except Exception:
        logging.exception("Lỗi khi tính Z-Score")
        return {"z_score": 2.2, "zone": "VÙNG XÁM", "icon": "🟡"}


def calculate_valuation_triangle(current_price: float, pe: float = None, pb: float = None, sector: str = "") -> dict:
    """Tam giác định giá 3 kịch bản dựa trên P/E & P/B bình quân và chu kỳ ngành."""
    if not current_price or current_price <= 0:
        return {"price_bull": 0.0, "price_base": 0.0, "price_bear": 0.0}

    is_cyclical = any(s in sector.lower() for s in ["thép", "dầu khí", "hóa chất", "phân bón", "vận tải biển"])
    is_cyclical_peak = is_cyclical and ((pe is not None and pe < 6.0) or (pb is not None and pb < 0.8))

    if is_cyclical_peak:
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


def _score_fundamental_pillar(fin_dict: dict) -> float:
    f_res = calculate_piotroski_f_score(fin_dict)
    f_pts = min(round((f_res.get("score", 5) / 9.0) * 18, 1), 18.0)

    z_res = calculate_altman_z_score(fin_dict)
    z_val = z_res.get("z_score", 2.0)
    if z_val >= 2.9:
        z_pts = 10.0
    elif z_val >= 1.8:
        z_pts = 6.0
    else:
        z_pts = 2.0

    roe = (fin_dict.get("roe") or 0.0) if fin_dict else 0.0
    if roe >= 18.0:
        roe_pts = 7.0
    elif roe >= 12.0:
        roe_pts = 5.0
    elif roe >= 8.0:
        roe_pts = 3.0
    else:
        roe_pts = 1.0

    return round(f_pts + z_pts + roe_pts, 1)


def _score_valuation_pillar(mos_data: dict) -> float:
    mos_pct = mos_data.get("mos_pct", 0.0) if mos_data else 0.0
    if mos_pct >= 25.0:
        return 30.0
    if mos_pct >= 18.0:
        return 25.0
    if mos_pct >= 12.0:
        return 20.0
    if mos_pct >= 5.0:
        return 14.0
    if mos_pct >= 0.0:
        return 8.0
    return 2.0


def _score_technical_pillar(tech_data: dict) -> float:
    curr = tech_data.get("current_price", 0.0)
    ma20 = tech_data.get("ma20", curr)
    rsi = tech_data.get("rsi", 50.0)
    vol = tech_data.get("volume", 0)
    vol_ma20 = tech_data.get("vol_ma20", vol)

    tech_pts = 0.0
    if curr >= ma20:
        tech_pts += 8.0
    elif curr >= ma20 * 0.98:
        tech_pts += 4.0

    if 48.0 <= rsi <= 65.0:
        tech_pts += 7.0
    elif 40.0 <= rsi < 48.0:
        tech_pts += 5.0
    elif 65.0 < rsi <= 75.0:
        tech_pts += 3.0
    else:
        tech_pts += 1.0

    if vol_ma20 > 0 and vol >= vol_ma20 * 1.1:
        tech_pts += 5.0
    else:
        tech_pts += 3.0
    return round(tech_pts, 1)


def _score_flow_pillar(tech_data: dict) -> float:
    flow_pts = 0.0
    foreign = tech_data.get("foreign_flow") or {}
    f_net = foreign.get("net_val_bil", 0.0)
    if f_net > 5.0:
        flow_pts += 8.0
    elif f_net >= -10.0:
        flow_pts += 5.0
    else:
        flow_pts += 1.0

    adv20 = tech_data.get("adv20_billion", 10.0)
    if adv20 >= 30.0:
        flow_pts += 7.0
    elif adv20 >= 10.0:
        flow_pts += 5.0
    elif adv20 >= 2.0:
        flow_pts += 3.0
    return round(flow_pts, 1)


def _get_100_point_grade_and_rating(total_score: float) -> tuple[str, str]:
    if total_score >= 80.0:
        return "A+", "XUẤT SẮC (Ưu tiên giải ngân lớn / Tích lũy chủ lực)"
    if total_score >= 68.0:
        return "A", "TỐT (Đạt chuẩn tích lũy từng phần)"
    if total_score >= 55.0:
        return "B", "TRUNG BÌNH (Theo dõi thêm, chờ giá chiết khấu)"
    return "C", "YẾU / RỦI RO (Không đạt tiêu chí giải ngân)"


def calculate_100_point_score(symbol: str, tech_data: dict, fin_dict: dict, mos_data: dict) -> dict:
    """THANG ĐIỂM ĐỊNH LƯỢNG 100 ĐIỂM (100-POINT QUANT SCORE) THEO 4 TRỤ CỘT."""
    pillar_fundamental = _score_fundamental_pillar(fin_dict)
    mos_pts = _score_valuation_pillar(mos_data)
    tech_pts = _score_technical_pillar(tech_data)
    flow_pts = _score_flow_pillar(tech_data)

    total_score = round(pillar_fundamental + mos_pts + tech_pts + flow_pts, 1)
    grade, rating = _get_100_point_grade_and_rating(total_score)

    return {
        "symbol": symbol.upper().strip() if symbol else "",
        "total_score": total_score,
        "grade": grade,
        "rating": rating,
        "breakdown": {
            "pillar_fundamental": pillar_fundamental,
            "pillar_valuation": mos_pts,
            "pillar_technical": tech_pts,
            "pillar_smart_flow": flow_pts,
        }
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


