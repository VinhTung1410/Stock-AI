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


def _get_fq_score_rating(score: int) -> str:
    """Return institutional qualitative rating based on Fundamental Quality Score."""
    if score >= 8:
        return "XUẤT SẮC"
    if score >= 6:
        return "TỐT"
    if score >= 4:
        return "TRUNG BÌNH"
    return "YẾU / RỦI RO"


def _evaluate_fscore_metric(name: str, value: Any, condition_fn, passed_list, failed_list, unknown_list) -> int:
    if value is None:
        unknown_list.append(name)
        return 0
    
    try:
        if condition_fn(value):
            passed_list.append(name)
            return 1
        else:
            failed_list.append(name)
            return 0
    except Exception:
        unknown_list.append(name)
        return 0

def _calc_profitability_points(fin_dict: dict, passed: list, failed: list, unknown: list) -> int:
    f1 = _evaluate_fscore_metric("ROA", fin_dict.get("roa"), lambda x: x > 0, passed, failed, unknown)
    # cfo_to_assets = CFO / Total Assets from KBS. If > 0, operating cash flow is positive.
    # Falls back to p_cf (Price/Cash Flow from VCI) if cfo_to_assets is unavailable.
    # KBS returns 0.0 as sentinel for missing quarterly cash flow data (real values
    # only appear in Q4 annual periods), so treat 0.0 as None (unknown, not failed).
    cfo_val = fin_dict.get("cfo_to_assets")
    if cfo_val is None or abs(float(cfo_val)) < 1e-6:
        cfo_val = fin_dict.get("p_cf") or None
    f2 = _evaluate_fscore_metric("CFO", cfo_val, lambda x: x > 0, passed, failed, unknown)
    f3 = _evaluate_fscore_metric("ROE", fin_dict.get("roe"), lambda x: x >= 10.0, passed, failed, unknown)
    f4 = _evaluate_fscore_metric("Net Margin", fin_dict.get("net_margin"), lambda x: x >= 5.0, passed, failed, unknown)
    return f1 + f2 + f3 + f4


def _calc_leverage_and_efficiency_points(fin_dict: dict, passed: list, failed: list, unknown: list) -> int:
    # debt_equity and financial_leverage from vnstock are in % (e.g. 90.28 = 90.28% = 0.9028x)
    f5 = _evaluate_fscore_metric("Debt/Equity", fin_dict.get("debt_equity") or fin_dict.get("debt_on_equity") or fin_dict.get("debt_to_equity"), lambda x: (x / 100.0) < 1.5, passed, failed, unknown)
    f6 = _evaluate_fscore_metric("Current Ratio", fin_dict.get("current_ratio"), lambda x: x >= 1.2, passed, failed, unknown)
    f7 = _evaluate_fscore_metric("Financial Leverage", fin_dict.get("financial_leverage"), lambda x: (x / 100.0) < 2.5, passed, failed, unknown)
    f8 = _evaluate_fscore_metric("Gross Margin", fin_dict.get("gross_margin"), lambda x: x >= 15.0, passed, failed, unknown)
    f9 = _evaluate_fscore_metric("ROIC", fin_dict.get("roic"), lambda x: x >= 8.0, passed, failed, unknown)
    return f5 + f6 + f7 + f8 + f9


def calculate_vibe_quality_score(fin_dict: dict, sector: str = "") -> dict:
    """Score financial health using Vibe Fundamental Quality (FQ) Score (0-9 scale).

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
            "passed": [],
            "failed": [],
            "unknown": ["ALL (sector-exempt)"],
            "data_completeness": 0.0,
            "confidence": "LOW CONFIDENCE (SECTOR EXEMPT)",
            "breakdown": {},
        }

    if (
        fin_dict
        and fin_dict.get("f_score") is not None
        and not any(k in fin_dict for k in ("roa", "current_ratio", "roic"))
    ):
        raw_s = int(fin_dict["f_score"])
        return {
            "score": raw_s,
            "max_score": 9,
            "rating": _get_fq_score_rating(raw_s),
            "passed": ["Precomputed"],
            "failed": [],
            "unknown": [],
            "data_completeness": 1.0,
            "confidence": "HIGH CONFIDENCE (PRECOMPUTED)",
            "breakdown": {"precomputed": raw_s},
        }

    fin_dict = fin_dict or {}
    passed = []
    failed = []
    unknown = []
    score = _calc_profitability_points(fin_dict, passed, failed, unknown) + _calc_leverage_and_efficiency_points(fin_dict, passed, failed, unknown)

    total_criteria = 9
    available = total_criteria - len(unknown)
    data_completeness = round(available / total_criteria, 2)
    
    if available == 9:
        confidence = "HIGH CONFIDENCE"
    elif available >= 7:
        confidence = "MEDIUM CONFIDENCE"
    else:
        confidence = "INVALID FOR GATING (<7/9 criteria)"

    return {
        "score": score, 
        "max_score": 9, 
        "rating": _get_fq_score_rating(score),
        "passed": passed,
        "failed": failed,
        "unknown": unknown,
        "data_completeness": data_completeness,
        "confidence": confidence,
        "breakdown": {}
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

    return {"price_bull": price_bull, "price_base": price_base, "price_bear": price_bear, "is_cyclical": is_cyclical}


def _score_fundamental_pillar(fin_dict: dict) -> float:
    f_res = calculate_vibe_quality_score(fin_dict)
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
        },
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
        market_r2 = round(corr_m**2, 3)
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
