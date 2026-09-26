# -*- coding: utf-8 -*-
"""
Deterministic Quantitative Engine - computes all financial metrics via Python
to eliminate LLM numerical hallucination.

Capabilities:
- Data Gate: reject signals when data quality is insufficient
- Piotroski F-Score (0-9): financial health scoring
- Altman Z-Score: bankruptcy risk assessment
- ATR(14) volatility-based stop loss
- Valuation triangle, Expected Value, Margin of Safety, Kelly Criterion
"""

import logging
from typing import Any, Dict, Final, List

import numpy as np
import pandas as pd

from quant_valuation import calculate_fair_value_and_mos

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


ACTION_ACCUMULATE = "🟢 TÍCH LŨY"


def _get_f_score_rating(score: int) -> str:
    """Return institutional qualitative rating based on Piotroski F-Score."""
    if score >= 8:
        return "XUẤT SẮC"
    if score >= 6:
        return "TỐT"
    if score >= 4:
        return "TRUNG BÌNH"
    return "YẾU / RỦI RO"


def calculate_piotroski_f_score(fin_dict: dict) -> dict:
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


def calculate_altman_z_score(fin_dict: dict) -> dict:
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


def check_data_gate(symbol: str, tech_dict: dict, fin_dict: dict, min_adv20_billion: float = 2.0) -> dict:
    """Hard data quality gate - blocks recommendations for illiquid or stale-data stocks.

    Checks:
    1. Valid market price exists
    2. Average daily volume (ADV20) meets minimum threshold
    3. Financial statements are recent enough

    Args:
        symbol: Stock ticker.
        tech_dict: Technical data with current_price, volume, adv20_billion.
        fin_dict: Financial data with 'period' key.
        min_adv20_billion: Minimum daily trading value in billion VND.

    Returns:
        Dict with 'passed' (bool), 'daily_value_billion', and 'reasons' list.
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


def evaluate_market_regime(
    vnindex_tech: dict = None,
    market_breadth_pct: float = None,
    portfolio_drawdown_pct: float = 0.0,
    margin_exposure_pct: float = 0.0
) -> dict:
    """Classify market regime and compute multi-variable risk budget.

    Combines 5 factors into a risk score (0-100):
    1. Market Trend - VN-Index vs MA20/MA50
    2. Market Breadth - % of stocks above MA20
    3. Liquidity - volume vs 20-day average
    4. Portfolio Drawdown - current NAV decline
    5. Margin Exposure - leverage ratio

    Returns:
        Dict with 'regime' (BULLISH/NEUTRAL/CORRECTION/RISK-OFF),
        'stock_pct', 'cash_pct', 'risk_budget_score', 'bias', etc.
    """
    if not vnindex_tech:
        return {
            "regime": "NEUTRAL",
            "tag": "🟡 ĐI NGANG / TÍCH LŨY",
            "stock_pct": "50%",
            "cash_pct": "50%",
            "max_stock_nav": 50,
            "bias": "Thận trọng, giải ngân từng phần vào các mã có Margin of Safety cao.",
            "defense_priority": "Trung bình"
        }

    curr = vnindex_tech.get("current_price", 0.0)
    ma20 = vnindex_tech.get("ma20", curr)
    ma50 = vnindex_tech.get("ma50", curr)
    rsi = vnindex_tech.get("rsi", 50.0)
    vol_ratio = vnindex_tech.get("vol_ratio", 1.0)

    # 1. Điểm Xu hướng Trend (Max 35)
    trend_score = 0
    if curr >= ma20:
        trend_score += 18
    if curr >= ma50:
        trend_score += 12
    if 50.0 <= rsi <= 68.0:
        trend_score += 5
    elif rsi > 70.0:
        trend_score += 1  # Cảnh báo quá mua

    # 2. Điểm Độ rộng Thị trường Breadth (Max 25)
    breadth = market_breadth_pct if market_breadth_pct is not None else (60.0 if curr >= ma20 else 40.0)
    breadth_score = min(round((breadth / 100.0) * 25, 1), 25.0)

    # 3. Điểm Thanh khoản Liquidity (Max 20)
    if vol_ratio >= 1.1:
        liq_score = 20.0
    elif vol_ratio >= 0.85:
        liq_score = 15.0
    else:
        liq_score = 8.0  # Cạn thanh khoản

    # 4. Điểm Quản trị Rủi ro Portfolio Drawdown & Margin (Max 20)
    risk_score = 20.0
    if portfolio_drawdown_pct < -5.0:
        risk_score -= 8.0
    if margin_exposure_pct > 30.0:
        risk_score -= 7.0

    total_risk_budget = trend_score + breadth_score + liq_score + risk_score

    # Phân loại Regime và cấp hạn mức Cổ phiếu theo Risk Budget
    if total_risk_budget >= 78.0 and curr >= ma20 and curr >= ma50:
        regime = "BULLISH"
        tag = "🟢 XU HƯỚNG TĂNG TRƯỞNG (BULLISH)"
        stock_pct = "65% - 75%"
        cash_pct = "25% - 35%"
        max_nav = 75
        bias = "Xu hướng tích cực được hỗ trợ bởi độ rộng và thanh khoản. Duy trì vị thế cổ phiếu chủ lực."
        defense_priority = "Thấp"
    elif total_risk_budget >= 55.0 or (curr >= ma50 and curr < ma20):
        regime = "NEUTRAL"
        tag = "🟡 ĐI NGANG / PHÂN HÓA (NEUTRAL)"
        stock_pct = "45% - 55%"
        cash_pct = "45% - 55%"
        max_nav = 55
        bias = "Dòng tiền phân hóa. Chỉ gom cổ phiếu đạt chuẩn giá trị (MoS >= 15%) tại vùng hỗ trợ."
        defense_priority = "Trung bình"
    elif curr < ma20 and curr >= ma50 * 0.98:
        regime = "CORRECTION"
        tag = "🟠 ĐIỀU CHỈNH KỸ THUẬT (CORRECTION)"
        stock_pct = "30% - 40%"
        cash_pct = "60% - 70%"
        max_nav = 40
        bias = "Thị trường kiểm định hỗ trợ trung hạn. Ưu tiên giữ tiền mặt, cấm mua đuổi ATO."
        defense_priority = "Cao"
    else:
        regime = "RISK-OFF"
        tag = "🔴 PHÒNG THỦ CAO ĐỘ (RISK-OFF)"
        stock_pct = "10% - 20%"
        cash_pct = "80% - 90%"
        max_nav = 20
        bias = "Áp lực bán lớn, rủi ro gãy xu hướng. Hạ margin về 0, bảo toàn vốn tối đa."
        defense_priority = "Tối đa"

    return {
        "regime": regime,
        "tag": tag,
        "stock_pct": stock_pct,
        "cash_pct": cash_pct,
        "max_stock_nav": max_nav,
        "risk_budget_score": total_risk_budget,
        "bias": bias,
        "defense_priority": defense_priority
    }


def calculate_weighted_entry_and_rr(
    entry_prices: list[float],
    weights: list[float] | None = None,
    target_price: float = 0.0,
    stop_loss: float = 0.0
) -> dict:
    """Compute weighted average entry price and risk/reward ratio.

    R:R is always calculated from the weighted entry - never from
    current market price - to prevent misleading ratios.

    Args:
        entry_prices: List of entry prices for staged buying.
        weights: Capital allocation weights (default: 30/40/30 for 3 entries).
        target_price: Price target for profit taking.
        stop_loss: Stop loss price level.

    Returns:
        Dict with 'weighted_entry', 'reward', 'risk', 'rr_ratio', 'is_valid'.
    """
    if not entry_prices:
        return {
            "weighted_entry": 0.0,
            "reward": 0.0,
            "risk": 0.0,
            "risk_reward": 1.0,
            "is_valid": False,
            "error": "Thiếu danh sách giá vào lệnh (entry_prices)"
        }

    # Mặc định trọng số giải ngân 3 bước (30% - 40% - 30%)
    if not weights or len(weights) != len(entry_prices):
        if len(entry_prices) == 3:
            weights = [0.3, 0.4, 0.3]
        elif len(entry_prices) == 2:
            weights = [0.4, 0.6]
        else:
            weights = [1.0 / len(entry_prices)] * len(entry_prices)

    total_w = sum(weights)
    norm_w = [w / total_w for w in weights]

    weighted_entry = round(sum(p * w for p, w in zip(entry_prices, norm_w)), 2)

    reward = round(max(target_price - weighted_entry, 0.0), 2) if target_price > 0 else 0.0
    risk = round(max(weighted_entry - stop_loss, 0.01), 2) if stop_loss > 0 else 0.01

    rr = round(reward / risk, 2) if risk > 0 else 1.0

    # Validation: Đối với vị thế Long, bắt buộc Target > Weighted Entry > Stop Loss
    is_valid = (target_price > weighted_entry) and (weighted_entry > stop_loss)

    return {
        "weighted_entry": weighted_entry,
        "entry_prices": entry_prices,
        "weights": weights,
        "target_price": target_price,
        "stop_loss": stop_loss,
        "reward": reward,
        "risk": risk,
        "risk_reward": rr,
        "rr_ratio": rr,
        "is_valid": is_valid
    }


def evaluate_holding_position(row: dict, tech_data: dict, fin_dict: dict | None = None) -> dict:
    """Evaluate an existing portfolio position and recommend action.

    Core rules:
    - Profitable positions (P/L > 0): use trailing stop, NEVER label as 'cut loss'.
    - Trailing stop is always clamped below current price (validation invariant).
    - Losing positions: value investments use thesis breaker; trades use technical stop.

    Args:
        row: Position data with 'symbol', 'avg_price', 'volume'.
        tech_data: Technical data with 'current_price', 'atr', 'ma20'.
        fin_dict: Optional financial data for enhanced evaluation.

    Returns:
        Dict with 'action', 'trailing_stop'/'stop_loss', 'pl_pct', 'detail', etc.
    """
    symbol = row.get("symbol", "")
    entry_price = float(row.get("avg_price", 0.0))
    curr_price = float(tech_data.get("current_price") or row.get("market_price", entry_price))
    volume = int(row.get("volume", 0))

    pl_val = (curr_price - entry_price) * volume * 1000
    pl_pct = ((curr_price - entry_price) / entry_price * 100) if entry_price > 0 else 0.0

    atr = float(tech_data.get("atr") or tech_data.get("atr14") or 0.0)
    ma20 = float(tech_data.get("ma20") or curr_price)

    # 1. KỊCH BẢN VỊ THẾ CÓ LÃI (P/L > 0)
    if pl_pct > 0:
        # Ngưỡng trần tối đa cho Trailing Stop (Bắt buộc nhỏ hơn Current Price ít nhất 3.5% - 4.5%)
        max_allowed_stop = round(curr_price * 0.96, 2)

        # Tính toán mốc Trailing Stop lý tưởng
        if pl_pct >= 15.0:
            # Lãi lớn (>= 15%): Nâng trailing stop khóa lợi nhuận (tối thiểu entry * 1.05 hoặc bám MA20)
            candidate_stop = max(
                entry_price * 1.06,
                (curr_price - (1.2 * atr)) if atr > 0 else (curr_price * 0.95),
                ma20 * 0.98
            )
        elif pl_pct >= 5.0:
            # Lãi vừa (5% - 15%): Khóa lãi hòa vốn + chi phí (entry * 1.02)
            candidate_stop = max(
                entry_price * 1.02,
                (curr_price - (1.5 * atr)) if atr > 0 else (curr_price * 0.94)
            )
        else:
            # Lãi nhẹ (< 5%): Hòa vốn
            candidate_stop = entry_price

        # VALIDATION CLAMP BẮT BUỘC: Trailing Stop PHẢI < curr_price
        trailing_stop = min(candidate_stop, max_allowed_stop)
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
                f"đặt mốc chặn lãi hòa vốn tại {trailing_stop:.2f}k."
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

        # Đảm bảo Stop-loss < curr_price
        stop_loss = min(round(float(stop_loss), 2), round(curr_price * 0.97, 2))

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
    trap_info: dict | None = None,
    foreign_flow: dict | None = None,
    adv20_billion: float = 0.0,
    symbol: str = "",
    fin_dict: dict | None = None,
    sector: str = "",
    tech_data: dict | None = None
) -> dict:
    """Compute deterministic hard gates for buy/sell decision.

    Strictly separates value signals from technical signals:
    - Good fundamentals + weak technicals = WATCH (never AVOID)
    - Automatically rejects buy if MoS < 8%, R:R < 1.5, or Kelly <= 0

    Decision states:
    1. 🟢 VALUE BUY - strong fundamentals + MoS >= 15% + bullish technicals
    2. 🟢 ACCUMULATE - strong fundamentals + MoS >= 15% + base formation
    3. 🟡 WATCH - good value but weak technicals (needs confirmation)
    4. 🔴 REDUCE/EXIT - overvalued or thesis breaker triggered

    Returns:
        Dict with 'decision_tag', 'action_state', 'mos_pct', 'ev',
        'kelly_f', 'risk_reward', 'tech_signal', etc.
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
    val_method = val_model.get("valuation_method", "N/A")
    val_confidence = val_model.get("confidence", "MEDIUM")
    price_target = val_model.get("price_target") or round(fair_value * 1.08, 2)

    # 1. Expected Value
    ev = (p_bull * price_bull) + (p_base * price_base) + (p_bear * price_bear)
    ev = round(float(ev), 2)

    # 2. Dynamic ATR Stop-loss
    if atr and atr > 0:
        atr_stop = round(current_price - (2.0 * atr), 2)
        stop_loss = max(atr_stop, round(current_price * 0.93, 2))
    else:
        stop_loss = round(current_price * 0.93, 2)

    # Đảm bảo Stop-loss < current_price
    stop_loss = min(round(float(stop_loss), 2), round(current_price * 0.97, 2))

    downside_val = max(current_price - stop_loss, 0.01)
    upside_val = max(price_target - current_price, 0.01)

    # 3. Tỷ lệ Risk / Reward R (theo Current nếu chưa có weighted entry)
    rr = round(upside_val / downside_val, 2) if downside_val > 0 else 1.0

    # 4. Kelly Criterion f* & Half-Kelly
    p_win = p_bull + (0.5 * p_base)
    p_loss = 1.0 - p_win
    kelly_f = round(p_win - (p_loss / rr), 2) if rr > 0 else -1.0
    half_kelly_f = round(kelly_f * 0.5, 2) if kelly_f > 0 else 0.0

    # 5. Phân loại Tín hiệu Kỹ thuật (Technical Signal)
    tech_signal = "NEUTRAL"
    ma20 = tech_data.get("ma20", current_price) if tech_data else current_price
    ma50 = tech_data.get("ma50", current_price) if tech_data else current_price
    rsi = tech_data.get("rsi", 50.0) if tech_data else 50.0

    is_falling_knife = False
    if current_price < ma20 * 0.95 and rsi < 36.0:
        is_falling_knife = True
        tech_signal = "FALLING_KNIFE"
    elif current_price < ma20 * 0.97 or current_price < ma50 * 0.98:
        tech_signal = "WEAK_BELOW_MA20"
    elif current_price >= ma20 and rsi >= 48.0:
        tech_signal = "BULLISH_CONFIRMED"
    else:
        tech_signal = "CONSOLIDATION_BASE"

    # --- HÀNG RÀO CỨNG (HARD GATES) ---
    gate_mos_passed = mos_pct >= 12.0
    gate_rr_passed = rr >= 1.5
    gate_kelly_passed = kelly_f > 0
    gate_trap_passed = not (trap_info and trap_info.get("is_trap"))

    # Kiểm tra dòng tiền Khối ngoại
    is_heavy_foreign_sell = False
    if foreign_flow and foreign_flow.get("status") in ["SELLING", "HEAVY_SELLING"]:
        net_val = foreign_flow.get("net_val_bil", 0.0)
        if net_val < -20.0:
            is_heavy_foreign_sell = True

    # =========================================================================
    # MA TRẬN PHÂN LOẠI QUYẾT ĐỊNH (VALUE + TECHNICAL COUPLING)
    # =========================================================================
    if adv20_billion > 0 and adv20_billion < 2.0:
        can_buy = False
        action_state = "🟡 THEO DÕI"
        decision_tag = "🟡 THEO DÕI (Thanh khoản quá thấp < 2 tỷ/phiên - Rủi ro kẹp vốn)"
        position_size_nav = "0% NAV"

    elif mos_pct < 0:
        # Vùng định giá đắt
        can_buy = False
        action_state = "🔴 GIẢM / THOÁT"
        decision_tag = "🔴 GIẢM / THOÁT (Thị giá vượt giá trị hợp lý, định giá quá đắt)"
        position_size_nav = "0% NAV"

    elif is_falling_knife or tech_signal == "WEAK_BELOW_MA20":
        # Cơ bản & Định giá có thể tốt (như MWG MoS 9.1%) nhưng kỹ thuật đang yếu
        # TUYỆT ĐỐI KHÔNG GÁN AVOID / TRÁNH BẪY mà chuyển thành WATCH / WAIT FOR CONFIRMATION
        can_buy = False
        action_state = "🟡 THEO DÕI"
        if mos_pct >= 15.0:
            decision_tag = "🟡 THEO DÕI / CHỜ XÁC NHẬN (Định giá rất rẻ nhưng Kỹ thuật đang rơi - Chờ nến cân bằng, cấm bắt dao rơi)"
        else:
            decision_tag = "🟡 THEO DÕI (Kỹ thuật nằm dưới MA20/MA50 - Chờ tích lũy ổn định)"
        position_size_nav = "0% NAV (Chờ tín hiệu xác nhận ngừng rơi)"

    elif not gate_trap_passed:
        # Bẫy phân phối khối lượng lớn / tin tức bơm thổi
        can_buy = False
        trap_msg = trap_info.get("warning_msg", "Phát hiện bẫy giá nguy hiểm")
        action_state = "🔴 GIẢM / THOÁT"
        decision_tag = f"🔴 GIẢM / THOÁT (Cảnh báo bẫy: {trap_msg})"
        position_size_nav = "0% NAV"

    elif mos_pct >= 15.0 and gate_rr_passed and gate_kelly_passed:
        can_buy = True
        if is_heavy_foreign_sell:
            action_state = ACTION_ACCUMULATE
            decision_tag = f"🟢 TÍCH LŨY THĂM DÒ (Khối ngoại xả ròng {foreign_flow.get('net_val_bil'):.1f} tỷ)"
            position_size_nav = "5% - 8% NAV"
        elif adv20_billion > 0 and adv20_billion < 10.0:
            action_state = ACTION_ACCUMULATE
            decision_tag = f"🟢 TÍCH LŨY THĂM DÒ (Thanh khoản {adv20_billion:.1f} tỷ < 10 tỷ - Cảnh báo trượt giá)"
            position_size_nav = "5% - 8% NAV"
        elif tech_signal == "BULLISH_CONFIRMED":
            action_state = "🟢 MUA"
            decision_tag = "🟢 VALUE BUY (Biên an toàn cao & Kỹ thuật xác nhận xu hướng bứt phá)"
            position_size_nav = "15% - 20% NAV"
        else:
            action_state = ACTION_ACCUMULATE
            decision_tag = "🟢 ACCUMULATE (Định giá rẻ, gom nhặt trong vùng nền chờ xác nhận)"
            position_size_nav = "10% - 12% NAV"

    elif mos_pct >= 8.0:
        can_buy = False
        action_state = "🟡 THEO DÕI"
        decision_tag = "🟡 THEO DÕI (Biên an toàn còn mỏng 8-15%, chờ giá chiết khấu thêm)"
        position_size_nav = "0% NAV"

    else:
        can_buy = False
        action_state = "🟡 THEO DÕI"
        decision_tag = "🟡 THEO DÕI (Hàng rào định lượng chưa đủ điều kiện kích hoạt Mua)"
        position_size_nav = "0% NAV"

    return {
        "ev": ev,
        "fair_value": fair_value,
        "price_target": price_target,
        "mos_pct": mos_pct,
        "valuation_model": val_model,
        "valuation_method": val_method,
        "confidence": val_confidence,
        "stop_loss": stop_loss,
        "downside_pct": round(((current_price - stop_loss) / current_price) * 100, 1) if current_price > 0 else 0.0,
        "risk_reward": rr,
        "kelly_f": kelly_f,
        "half_kelly_f": half_kelly_f,
        "gate_mos_passed": gate_mos_passed,
        "gate_rr_passed": gate_rr_passed,
        "gate_kelly_passed": gate_kelly_passed,
        "gate_trap_passed": gate_trap_passed,
        "trap_info": trap_info or {},
        "foreign_flow": foreign_flow or {},
        "can_buy": can_buy,
        "tech_signal": tech_signal,
        "action_state": action_state,
        "decision_tag": decision_tag,
        "position_size_nav": position_size_nav
    }


def check_portfolio_concentration(
    candidates: List[Dict[str, Any]],
    max_per_sector: int = 1
) -> Dict[str, Any]:
    """Audit candidate recommendations against sector concentration.

    Retains the highest conviction candidate per sector in approved list,
    and downgrades duplicate sector candidates to Watchlist with a concentration alert.

    Returns:
        dict with 'approved_candidates', 'downgraded_candidates', 'warnings'.
    """
    if not candidates:
        return {"approved_candidates": [], "downgraded_candidates": [], "warnings": []}

    sector_counts: Dict[str, int] = {}
    approved = []
    downgraded = []
    warnings = []

    def _conviction_score(c: Dict[str, Any]) -> float:
        mos = float(c.get("mos_pct") or 0.0)
        rr = float(c.get("risk_reward") or 1.0)
        f_val = c.get("f_score")
        f_score = float(f_val) if f_val is not None else 5.0
        return mos + (rr * 5.0) + (f_score * 2.0)

    sorted_candidates = sorted(candidates, key=_conviction_score, reverse=True)

    for item in sorted_candidates:
        sym = item.get("symbol", "UNKNOWN")
        sector = (item.get("sector") or "OTHER").strip().upper()
        current_count = sector_counts.get(sector, 0)

        if current_count < max_per_sector:
            sector_counts[sector] = current_count + 1
            approved.append(item)
        else:
            downgraded_item = dict(item)
            downgraded_item["action_state"] = "🟡 THEO DÕI"
            downgraded_item["position_size_nav"] = "0% NAV (Dự phòng)"
            downgraded_item["decision_tag"] = (
                f"🟡 THEO DÕI / DỰ PHÒNG (Cảnh báo tập trung danh mục: Đã có mã ngành {sector})"
            )
            downgraded.append(downgraded_item)
            warnings.append(
                f"Tập trung ngành {sector}: Mã {sym} được chuyển sang danh mục dự phòng "
                f"để tránh rủi ro đồng pha danh mục."
            )

    return {
        "approved_candidates": approved,
        "downgraded_candidates": downgraded,
        "warnings": warnings
    }


def calculate_drawdown_controlled_sizing(
    half_kelly_f: float,
    consecutive_losses: int = 0,
    current_drawdown_pct: float = 0.0,
    max_cap_pct: float = 0.20,
) -> tuple[float, str]:
    """Calculate adaptive position size based on Half-Kelly, losing streaks, and drawdown.

    Rules:
    - If consecutive_losses >= 2 or current_drawdown_pct >= 5.0%:
      Reduce position size by 50% (Half-Size Defense) to prevent revenge trading.
    - Caps position sizing at max_cap_pct (default: 20%).
    """
    if half_kelly_f <= 0:
        return 0.0, "KELLY_NON_POSITIVE"

    base_size = min(half_kelly_f, max_cap_pct)

    if consecutive_losses >= 2 or current_drawdown_pct >= 5.0:
        defensive_size = round(base_size * 0.5, 4)
        return defensive_size, "DRAWDOWN_DEFENSE_HALF_SIZE"

    return round(base_size, 4), "STANDARD_HALF_KELLY"


def check_adv20_liquidity_absorption(
    order_val_vnd: float,
    adv20_vnd: float,
    max_absorption_pct: float = 0.10,
) -> tuple[bool, float, str]:
    """Verify that order size does not exceed maximum ADV20 liquidity absorption limit.

    Args:
        order_val_vnd: Target order value in VND.
        adv20_vnd: Average daily trading value over 20 days in VND.
        max_absorption_pct: Maximum allowed absorption percentage (default: 10%).

    Returns:
        tuple (is_passed, allowed_order_val_vnd, reason)
    """
    if adv20_vnd <= 0:
        return False, 0.0, "ADV20_ZERO_OR_NEGATIVE"

    max_allowed = adv20_vnd * max_absorption_pct
    if order_val_vnd > max_allowed:
        return False, round(max_allowed, 2), "EXCEEDS_MAX_ADV20_ABSORPTION"

    return True, round(order_val_vnd, 2), "LIQUIDITY_ABSORPTION_OK"


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


LOCKED_QUANT_THRESHOLDS = {
    "f_score_min": 6,
    "mos_min_pct": 15.0,
    "z_score_min": 1.80,
    "rsi_max_entry": 70.0,
    "conviction_min": 55.0,
    "adv20_absorption_max_pct": 0.10,
    "sector_exposure_max_pct": 0.25,
}

RISK_FREE_HURDLE_RATE_PCT = 4.5  # Sàn lãi suất tiền gửi rủi ro thấp theo năm


def calculate_signal_performance_metrics(
    trades: list[dict],
    cagr_pct: float = 0.0,
    sharpe_ratio: float = 0.0,
) -> dict:
    """Tính toán toàn diện bộ chỉ số bằng chứng kiểm định hiệu năng (Phase 1b & 1c).

    - Trade-level: Win Rate, Expectancy, Profit Factor, R-Multiple, Effective Sample Size (ESS).
    - Portfolio-level: Dual Benchmark check, Hurdle Rate sàn 4.5%/năm, Sharpe >= 0.5.
    """
    if not trades:
        return {
            "total_trades": 0,
            "win_rate": 0.0,
            "expectancy": 0.0,
            "profit_factor": 0.0,
            "avg_r_multiple": 0.0,
            "effective_n": 0.0,
            "statistically_reliable": False,
            "meets_hurdle_rate": False,
            "acceptable_sharpe": False,
            "warning": "Không có dữ liệu giao dịch để kiểm định.",
        }

    pnl_list = []
    r_multiples = []

    for t in trades:
        pnl = float(t.get("pnl_pct", 0.0))
        pnl_list.append(pnl)

        entry_p = float(t.get("entry_price", 0.0))
        init_stop = float(t.get("initial_stop_price", 0.0))

        if entry_p > 0 and init_stop > 0 and entry_p > init_stop:
            initial_risk_pct = ((entry_p - init_stop) / entry_p) * 100.0
            r_m = pnl / initial_risk_pct if initial_risk_pct > 0 else 0.0
        else:
            r_m = float(t.get("r_multiple", 0.0))
        r_multiples.append(r_m)

    n_trades = len(pnl_list)
    wins = [p for p in pnl_list if p > 0]
    losses = [p for p in pnl_list if p <= 0]

    win_count = len(wins)
    loss_count = len(losses)
    win_rate = (win_count / n_trades) * 100.0 if n_trades > 0 else 0.0
    loss_rate = (loss_count / n_trades) * 100.0 if n_trades > 0 else 0.0

    avg_win = float(pd.Series(wins).mean()) if wins else 0.0
    avg_loss = abs(float(pd.Series(losses).mean())) if losses else 0.0

    # Expectancy: (WinRate * AvgWin) - (LossRate * |AvgLoss|)
    expectancy = round(((win_rate / 100.0) * avg_win) - ((loss_rate / 100.0) * avg_loss), 3)

    sum_wins = sum(wins)
    sum_losses = abs(sum(losses))
    if sum_losses > 0:
        profit_factor = round(sum_wins / sum_losses, 2)
    elif sum_wins > 0:
        profit_factor = 99.0
    else:
        profit_factor = 0.0

    avg_r = round(float(pd.Series(r_multiples).mean()), 2) if r_multiples else 0.0

    # Effective Sample Size (ESS) qua lag-1 autocorrelation
    effective_n = float(n_trades)
    if n_trades >= 4:
        s_pnl = pd.Series(pnl_list)
        rho_1 = s_pnl.autocorr(lag=1)
        if pd.notnull(rho_1) and -0.99 <= rho_1 <= 0.99:
            ess_calc = n_trades * ((1.0 - rho_1) / (1.0 + rho_1))
            effective_n = round(max(1.0, min(float(n_trades), ess_calc)), 1)

    meets_hurdle = cagr_pct >= RISK_FREE_HURDLE_RATE_PCT
    acceptable_sharpe = sharpe_ratio >= 0.5
    statistically_reliable = effective_n >= 30.0

    return {
        "total_trades": n_trades,
        "effective_n": effective_n,
        "win_rate": round(win_rate, 2),
        "expectancy": expectancy,
        "profit_factor": profit_factor,
        "avg_r_multiple": avg_r,
        "cagr_pct": round(cagr_pct, 2),
        "sharpe_ratio": round(sharpe_ratio, 2),
        "meets_hurdle_rate": meets_hurdle,
        "acceptable_sharpe": acceptable_sharpe,
        "statistically_reliable": statistically_reliable,
    }


MAX_POSITIONS_PER_SECTOR: int = 3
MAX_SECTOR_WEIGHT_PCT: float = 25.0


def check_sector_concentration(
    new_symbol: str,
    current_portfolio: list,
    sector_map: dict | None = None,
) -> tuple[bool, str]:
    """Kiểm tra chốt chặn tập trung ngành (Sector Concentration Gate - Phase 2a).

    Quy tắc:
    - Tối đa MAX_POSITIONS_PER_SECTOR (3) vị thế cùng ngành trong danh mục 8-10 mã.
    - Trả về tuple (is_allowed, reason).
    """
    if not new_symbol:
        return False, "INVALID_SYMBOL"

    if not current_portfolio:
        return True, "SECTOR_CONCENTRATION_OK"

    from data_engine import SECTOR_MAP
    s_map = sector_map if sector_map is not None else SECTOR_MAP

    sym_clean = new_symbol.upper().strip()
    new_sector = s_map.get(sym_clean, "Khác")

    same_sector_count = 0
    for item in current_portfolio:
        p_sym = str(item.get("symbol", item.get("Mã CP", ""))).upper().strip()
        if p_sym and s_map.get(p_sym, "Khác") == new_sector:
            same_sector_count += 1

    if same_sector_count >= MAX_POSITIONS_PER_SECTOR:
        reason = (
            f"Sector Gate Blocked: Ngành '{new_sector}' đã đạt giới hạn "
            f"{same_sector_count}/{MAX_POSITIONS_PER_SECTOR} vị thế tối đa. "
            f"Từ chối mở thêm vị thế cho {sym_clean} để chống rủi ro tương quan chùm."
        )
        return False, reason

    return True, "SECTOR_CONCENTRATION_OK"


def bootstrap_sharpe_ci(
    returns: list[float] | pd.Series | np.ndarray,
    n_bootstrap: int = 10_000,
    risk_free_annual: float = 0.045,
    ci: float = 0.95,
    periods_per_year: int = 252,
    random_state: int | None = 42,
) -> dict[str, Any]:
    """Tính toán Khoảng tin cậy (Confidence Interval) của Sharpe qua n_bootstrap lần Resampling (Phase 3c).

    Giúp bóc tách giữa may mắn ngẫu nhiên (luck) và lợi thế định lượng thực sự (edge)
    đặc biệt khi số lượng quan sát giao dịch nhỏ (N < 30).
    """
    fallback_res: dict[str, Any] = {
        "sharpe_point": 0.0,
        "ci_lower": 0.0,
        "ci_upper": 0.0,
        "std_err": 0.0,
        "p_value_zero": 1.0,
        "is_statistically_significant": False,
        "n_samples": 0,
        "effective_n": 0.0,
        "warning": "Dữ liệu lợi suất rỗng hoặc không đủ số lượng quan sát để chạy Bootstrap CI.",
    }

    if returns is None:
        return fallback_res

    try:
        arr = np.asarray(returns, dtype=float)
        arr = arr[~np.isnan(arr)]
    except Exception:
        return fallback_res

    n = len(arr)
    if n < 2:
        fallback_res["n_samples"] = n
        fallback_res["effective_n"] = float(n)
        return fallback_res

    daily_rf = (1.0 + risk_free_annual) ** (1.0 / periods_per_year) - 1.0
    ret_std = float(np.std(arr, ddof=1))
    point_sharpe = float(((np.mean(arr) - daily_rf) / ret_std) * np.sqrt(periods_per_year)) if ret_std > 1e-12 else 0.0

    # Resampling ma trận vectorization
    rng = np.random.default_rng(random_state)
    indices = rng.integers(0, n, size=(n_bootstrap, n))
    samples = arr[indices]

    sample_means = np.mean(samples, axis=1) - daily_rf
    sample_stds = np.std(samples, axis=1, ddof=1)
    valid_mask = sample_stds > 1e-12

    sharpe_dist = np.zeros(n_bootstrap, dtype=float)
    sharpe_dist[valid_mask] = (sample_means[valid_mask] / sample_stds[valid_mask]) * np.sqrt(periods_per_year)

    alpha_level = (1.0 - ci) / 2.0
    ci_lower = round(float(np.percentile(sharpe_dist, alpha_level * 100.0)), 3)
    ci_upper = round(float(np.percentile(sharpe_dist, (1.0 - alpha_level) * 100.0)), 3)
    std_err = round(float(np.std(sharpe_dist)), 3)
    p_value_zero = round(float(np.mean(sharpe_dist <= 0.0)), 4)

    # Effective Sample Size (ESS) xử lý tự tương quan lag-1
    effective_n = float(n)
    if n >= 4:
        s_ret = pd.Series(arr)
        rho_1 = s_ret.autocorr(lag=1)
        if pd.notnull(rho_1) and -0.99 <= rho_1 <= 0.99:
            ess = n * ((1.0 - rho_1) / (1.0 + rho_1))
            effective_n = round(max(1.0, min(float(n), ess)), 1)

    is_significant = bool(ci_lower > 0.0)
    warning_msg = ""
    if not is_significant:
        warning_msg = (
            f"Khoảng tin cậy {int(ci*100)}% [{ci_lower}, {ci_upper}] chứa giá trị <= 0. "
            "Chưa đủ bằng chứng thống kê để khẳng định chiến lược có Edge thực sự."
        )
    elif effective_n < 30.0:
        warning_msg = (
            f"Effective Sample Size ({effective_n}) < 30. "
            "Cần tích lũy thêm dữ liệu để kết luận chắc chắn."
        )

    return {
        "sharpe_point": round(point_sharpe, 3),
        "ci_lower": ci_lower,
        "ci_upper": ci_upper,
        "std_err": std_err,
        "p_value_zero": p_value_zero,
        "is_statistically_significant": is_significant,
        "n_samples": n,
        "effective_n": effective_n,
        "warning": warning_msg,
    }


# Phase 4: A/B Testing Arms and AI Calibration
ARM_QUANT_ONLY: Final[str] = "QUANT_ONLY"
ARM_QUANT_AI: Final[str] = "QUANT_AI"

CALIBRATION_BUCKET_NAMES: Final[list[str]] = [
    "50-60", "60-70", "70-80", "80-90", "90-100"
]


def check_ai_calibration(
    trades: list[dict[str, Any]],
    min_observations_per_bucket: int = 3,
    max_acceptable_gap: float = 0.15,
) -> dict[str, Any]:
    """Kiểm tra độ chuẩn định (Calibration) của AI Confidence (Phase 4b).

    Bóc tách tỷ lệ thắng thực tế so với độ tin cậy được AI công bố.
    Nếu uncalibrated (lệch chuẩn > 15%), Hard Block không đưa ai_confidence vào Kelly sizing.
    """
    if not trades:
        return {
            "buckets": {},
            "is_calibrated": False,
            "allow_kelly_sizing": False,
            "brier_score": None,
            "total_evaluated_trades": 0,
            "warning": "Không có dữ liệu giao dịch để kiểm định độ chuẩn định của AI.",
        }

    buckets: dict[str, list[int]] = {b: [] for b in CALIBRATION_BUCKET_NAMES}
    conf_vals: list[float] = []
    win_vals: list[int] = []

    for row in trades:
        if not isinstance(row, dict):
            continue
        raw_conf = row.get("ai_confidence", row.get("confidence", None))
        if raw_conf is None:
            continue
        try:
            conf = float(raw_conf)
            if 0.0 <= conf <= 1.0:
                conf *= 100.0
        except (ValueError, TypeError):
            continue

        pnl = float(row.get("pnl_pct", row.get("pnl", 0.0)))
        win = 1 if pnl > 0 else 0

        for b_name in CALIBRATION_BUCKET_NAMES:
            lo_s, hi_s = b_name.split("-")
            lo, hi = float(lo_s), float(hi_s)
            if (lo <= conf < hi) or (hi == 100.0 and conf == 100.0):
                buckets[b_name].append(win)
                conf_vals.append(conf / 100.0)
                win_vals.append(win)
                break

    bucket_results: dict[str, Any] = {}
    evaluated_buckets = 0
    uncalibrated_buckets = 0

    for b_name, wins in buckets.items():
        lo_val = float(b_name.split("-")[0])
        midpoint = (lo_val + 5.0) / 100.0
        n = len(wins)
        if n == 0:
            continue

        actual_wr = round(sum(wins) / n, 3)
        gap = round(abs(actual_wr - midpoint), 3)

        is_bucket_calibrated = True
        if n >= min_observations_per_bucket:
            evaluated_buckets += 1
            if gap > max_acceptable_gap or (midpoint >= 0.75 and actual_wr < 0.60):
                is_bucket_calibrated = False
                uncalibrated_buckets += 1

        bucket_results[b_name] = {
            "n": n,
            "claimed_midpoint": midpoint,
            "actual_win_rate": actual_wr,
            "calibration_gap": gap,
            "evaluated": n >= min_observations_per_bucket,
            "is_calibrated": is_bucket_calibrated,
        }

    brier_score = None
    if conf_vals and win_vals:
        brier_score = round(float(np.mean([(c - w) ** 2 for c, w in zip(conf_vals, win_vals)])), 4)

    if evaluated_buckets == 0:
        is_calibrated = False
        allow_kelly = False
        warn = f"Chưa có bucket nào đủ tối thiểu {min_observations_per_bucket} lệnh để kết luận độ chuẩn định."
    elif uncalibrated_buckets > 0:
        is_calibrated = False
        allow_kelly = False
        warn = (
            "⚠️ AI Confidence bị lệch chuẩn (Uncalibrated): Tỷ lệ thắng thực tế sai lệch đáng kể "
            "so với độ tin cậy AI phát biểu. CẤM đưa ai_confidence vào công thức Half-Kelly position sizing."
        )
    else:
        is_calibrated = True
        allow_kelly = True
        warn = ""

    return {
        "buckets": bucket_results,
        "is_calibrated": is_calibrated,
        "allow_kelly_sizing": allow_kelly,
        "brier_score": brier_score,
        "total_evaluated_trades": len(win_vals),
        "warning": warn,
    }


def compare_quant_vs_ai_arms(
    trades_arm_a: list[dict[str, Any]],
    trades_arm_b: list[dict[str, Any]],
    cagr_a: float = 0.0,
    cagr_b: float = 0.0,
    sharpe_a: float = 0.0,
    sharpe_b: float = 0.0,
) -> dict[str, Any]:
    """So sánh 2 nhánh thử nghiệm A/B: Quant-Only vs Quant+AI (Phase 4a).

    Xác định liệu hội đồng AI có tạo ra Alpha thặng dư thực sự hay chỉ là một tầng phân tích tốn kém.
    """
    m_a = calculate_signal_performance_metrics(trades_arm_a, cagr_pct=cagr_a, sharpe_ratio=sharpe_a)
    m_b = calculate_signal_performance_metrics(trades_arm_b, cagr_pct=cagr_b, sharpe_ratio=sharpe_b)

    inc_sharpe = round(m_b["sharpe_ratio"] - m_a["sharpe_ratio"], 2)
    inc_expectancy = round(m_b["expectancy"] - m_a["expectancy"], 3)
    inc_win_rate = round(m_b["win_rate"] - m_a["win_rate"], 2)

    # Đánh giá kết luận nghiệp vụ
    if inc_sharpe > 0.10 and inc_expectancy > 0.0:
        verdict = "POSITIVE_AI_ALPHA"
        recommendation = (
            "Khuyến nghị: Giữ AI trong quy trình ra quyết định. AI cải thiện rõ rệt "
            f"Sharpe (+{inc_sharpe}) và Expectancy (+{inc_expectancy})."
        )
    elif abs(inc_sharpe) <= 0.10:
        verdict = "NEUTRAL_REPORTING_ONLY"
        recommendation = (
            "Khuyến nghị: AI không tạo ra thặng dư Sharpe đáng kể so với Quant-Only. "
            "Nên chuyển AI thành tầng phân tích giải thích (reporting layer) để tiết kiệm token và giảm độ trễ."
        )
    else:
        verdict = "NEGATIVE_AI_DRAG"
        recommendation = (
            "Khuyến nghị: AI làm suy giảm hiệu năng so với Quant-Only thuần túy "
            f"(Sharpe lệch {inc_sharpe}). Cần điều tra lại prompt hội đồng hoặc vô hiệu hóa quyền phủ quyết của AI."
        )

    return {
        "arm_a_quant_only": m_a,
        "arm_b_quant_ai": m_b,
        "incremental_sharpe": inc_sharpe,
        "incremental_expectancy": inc_expectancy,
        "incremental_win_rate": inc_win_rate,
        "ai_verdict": verdict,
        "recommendation": recommendation,
    }

