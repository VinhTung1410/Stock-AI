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
import math
from datetime import datetime, timedelta
from typing import Any, Final, Optional

import numpy as np
import pandas as pd

from quant_valuation import calculate_fair_value_and_mos

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Re-exported from sub-modules for backwards compatibility
from indicators import (  # noqa: F401
    _get_fq_score_rating,
    calculate_100_point_score,
    calculate_altman_z_score,
    calculate_atr,
    calculate_factor_exposures,
    calculate_valuation_triangle,
    calculate_vibe_quality_score,
    evaluate_smart_money_flow,
)
from portfolio_guard import (  # noqa: F401
    MAX_POSITIONS_PER_SECTOR,
    _cap_and_redistribute_weights,
    _redistribute_uncapped_weights,
    calculate_drawdown_controlled_sizing,
    check_adv20_liquidity_absorption,
    check_portfolio_concentration,
    check_sector_concentration,
    evaluate_holding_position,
    evaluate_partial_profit_lock,
    optimize_portfolio_risk_parity,
)

ACTION_ACCUMULATE = "🟢 TÍCH LŨY"


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
        reasons.append(
            f"Thanh khoản quá thấp ({daily_value_billion:.2f} tỷ < ngưỡng tối thiểu {min_adv20_billion} tỷ/phiên). Rủi ro kẹp vốn!"
        )

    # 3. Kiểm tra tính mới BCTC
    if not period or period == "N/A":
        reasons.append("BCTC chưa được đồng bộ hoặc thiếu kỳ báo cáo kiểm toán gần nhất.")

    return {"passed": passed, "daily_value_billion": round(daily_value_billion, 2), "reasons": reasons}


def evaluate_market_regime(
    vnindex_tech: dict = None,
    market_breadth_pct: float = None,
    portfolio_drawdown_pct: float = 0.0,
    margin_exposure_pct: float = 0.0,
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
            "defense_priority": "Trung bình",
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
        "defense_priority": defense_priority,
    }


def calculate_weighted_entry_and_rr(
    entry_prices: list[float], weights: list[float] | None = None, target_price: float = 0.0, stop_loss: float = 0.0
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
            "error": "Thiếu danh sách giá vào lệnh (entry_prices)",
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
        "is_valid": is_valid,
    }


def calculate_structural_stop_loss(
    current_price: float,
    tech_data: dict | None = None,
    atr: float | None = None,
) -> tuple[float, float, str]:
    """Calculate structural stop-loss based on swing low, MA50, and ATR buffer (Phase 13 / TASK-0039).

    Avoids the mechanical -7% HOSE limit-down floor trap.

    Returns:
        tuple of (stop_loss: float, risk_pct: float, method_desc: str)
    """
    if current_price <= 0:
        return 0.0, 0.0, "INVALID_PRICE"

    tech = tech_data or {}
    atr_val = float(atr) if (atr and atr > 0) else float(tech.get("atr") or (current_price * 0.03))
    atr_buffer = round(0.5 * atr_val, 2)

    # 1. Structural anchors in priority: swing_low -> support_level -> ma50 -> ma20
    swing_low = float(tech.get("swing_low") or 0.0)
    support_lvl = float(tech.get("support_level") or tech.get("base_support") or 0.0)
    ma50 = float(tech.get("ma50") or 0.0)
    ma20 = float(tech.get("ma20") or 0.0)

    anchor = 0.0
    method = ""
    if 0 < swing_low < current_price:
        anchor = swing_low
        method = "SWING_LOW"
    elif 0 < support_lvl < current_price:
        anchor = support_lvl
        method = "BASE_SUPPORT"
    elif 0 < ma50 < current_price:
        anchor = ma50
        method = "MA50_SUPPORT"
    elif 0 < ma20 <= current_price:
        anchor = ma20
        method = "MA20_SUPPORT"

    if anchor > 0:
        candidate_stop = round(anchor - atr_buffer, 2)
        # Bounded between 5% and 12% below current_price
        min_stop = round(current_price * 0.88, 2)  # max 12% loss
        max_stop = round(current_price * 0.95, 2)  # at least 5% room
        stop_loss = max(min(candidate_stop, max_stop), min_stop)
        desc = f"STRUCTURAL_{method} (Anchor: {anchor:.2f}, Buffer: -{atr_buffer:.2f})"
    else:
        # Dynamic ATR fallback (avoiding hardcoded -7% HOSE floor trap)
        stop_loss = round(current_price - (2.5 * atr_val), 2)
        stop_loss = max(min(stop_loss, round(current_price * 0.95, 2)), round(current_price * 0.90, 2))
        desc = f"DYNAMIC_ATR_FALLBACK (2.5x ATR: {2.5 * atr_val:.2f})"

    risk_pct = round(((current_price - stop_loss) / current_price) * 100, 2)
    return stop_loss, risk_pct, desc


def calculate_gap_risk_position_sizing(
    kelly_f: float,
    stop_loss_pct: float,
    max_nav_risk: float = 0.015,
    floor_gap_risk: float = 0.14,
    max_position_cap: float = 0.25,
) -> tuple[float, str]:
    """Calculate position size incorporating gap floor risk (Phase 13 / TASK-0039).

    Stress tests 2 consecutive floor limit-down sessions (-14% on HOSE) to protect portfolio NAV budget.

    Returns:
        tuple of (position_size_nav: float, note: str)
    """
    if kelly_f <= 0 or stop_loss_pct <= 0:
        return 0.0, "NO_ALLOCATION (Kelly <= 0 or invalid SL)"

    half_kelly = kelly_f * 0.5
    nominal_risk = stop_loss_pct / 100.0
    effective_risk = max(nominal_risk, floor_gap_risk)

    budget_size = max_nav_risk / effective_risk
    final_size = min(half_kelly, budget_size, max_position_cap)
    final_size = round(final_size, 4)

    note = (
        f"GAP_STRESS_SIZING: Half-Kelly={half_kelly*100:.1f}%, "
        f"BudgetCap={budget_size*100:.1f}% (Stress -14%), Cap={max_position_cap*100:.1f}%"
    )
    return final_size, note


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
    tech_data: dict | None = None,
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
    if symbol:
        try:
            val_model = calculate_fair_value_and_mos(
                symbol=symbol, current_price=current_price, fin_dict=fin_dict or {}, sector=sector
            )
        except TypeError:
            try:
                val_model = calculate_fair_value_and_mos(
                    symbol=symbol, current_price=current_price, sector=sector
                )
            except TypeError:
                val_model = calculate_fair_value_and_mos(symbol, current_price, sector)
        mos_is_informative = val_model.get("mos_is_informative", True)
        fair_value = val_model.get("fair_value", price_base)
        if not mos_is_informative or fair_value <= 0:
            mos_pct = 0.0
            fallback_mos = 0.0
            val_confidence = "LOW"
        else:
            fallback_mos = round(((price_base - current_price) / price_base) * 100, 2) if price_base > 0 else 0.0
            mos_pct = val_model.get("mos_pct", fallback_mos)
            val_confidence = val_model.get("confidence", "MEDIUM")
        val_method = val_model.get("valuation_method", "N/A")
        price_target = val_model.get("price_target") or round(fair_value * 1.08, 2)
    else:
        val_model = {}
        fair_value = price_base
        mos_pct = round(((price_base - current_price) / price_base) * 100, 2) if price_base > 0 else 0.0
        val_method = "SCENARIO_INPUT"
        val_confidence = "HIGH"
        price_target = price_bull
        mos_is_informative = True

    # 1. Expected Value
    ev = (p_bull * price_bull) + (p_base * price_base) + (p_bear * price_bear)
    ev = round(float(ev), 2)

    # 2. Structural Stop-loss & Gap Risk Sizing (Phase 13 / TASK-0039)
    stop_loss, sl_risk_pct, sl_method = calculate_structural_stop_loss(
        current_price=current_price, tech_data=tech_data, atr=atr
    )

    downside_val = max(current_price - stop_loss, 0.01)
    upside_val = max(price_target - current_price, 0.01)

    # 3. Tỷ lệ Risk / Reward R (theo Current nếu chưa có weighted entry)
    rr = round(upside_val / downside_val, 2) if downside_val > 0 else 1.0

    # 4. Kelly Criterion f* & Half-Kelly
    p_win = p_bull + (0.5 * p_base)
    p_loss = 1.0 - p_win
    kelly_f = round(p_win - (p_loss / rr), 2) if rr > 0 else -1.0
    half_kelly_f = round(kelly_f * 0.5, 2) if kelly_f > 0 else 0.0

    gap_sized_nav, gap_sizing_note = calculate_gap_risk_position_sizing(
        kelly_f=kelly_f, stop_loss_pct=sl_risk_pct
    )

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
    # Khóa cứng MoS uninformative hoặc không có định giá thực chất (TASK-0038)
    gate_mos_passed = (mos_pct >= 12.0) and mos_is_informative and (fair_value > 0)
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
        if mos_pct >= 15.0 and mos_is_informative:
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

    elif mos_is_informative and mos_pct >= 15.0 and gate_rr_passed and gate_kelly_passed:
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

    elif mos_is_informative and mos_pct >= 8.0:
        can_buy = False
        action_state = "🟡 THEO DÕI"
        decision_tag = "🟡 THEO DÕI (Biên an toàn còn mỏng 8-15%, chờ giá chiết khấu thêm)"
        position_size_nav = "0% NAV"

    elif not mos_is_informative:
        can_buy = False
        action_state = "🟡 THEO DÕI"
        decision_tag = "🟡 THEO DÕI (Thiếu dữ liệu BCTC tin cậy để xác định Biên an toàn MoS)"
        position_size_nav = "0% NAV"

    else:
        can_buy = False
        action_state = "🟡 THEO DÕI"
        decision_tag = "🟡 THEO DÕI (Hàng rào định lượng chưa đủ điều kiện kích hoạt Mua)"
        position_size_nav = "0% NAV"

    # =========================================================================
    # KIỂM TRA KILL SWITCH TỪ EVIDENCE DATABASE (PHASE 4)
    # =========================================================================
    try:
        if can_buy:
            from db_manager import check_evidence_kill_switch

            ks_res = check_evidence_kill_switch(lookback_trades=20)
            if ks_res.get("is_triggered"):
                decision_tag = f"{decision_tag} ⚠️ [KILL SWITCH KÍCH HOẠT: Expectancy R {ks_res.get('expectancy_r')}]"
                position_size_nav = f"{position_size_nav} (Yêu cầu giảm 50% quy mô do chuỗi lệnh thua)"
    except Exception:
        import logging

        logging.exception("Lỗi khi kiểm tra Kill Switch")

    return {
        "ev": ev,
        "fair_value": fair_value,
        "price_target": price_target,
        "mos_pct": mos_pct,
        "mos_is_informative": mos_is_informative,
        "valuation_model": val_model,
        "valuation_method": val_method,
        "confidence": val_confidence,
        "stop_loss": stop_loss,
        "downside_pct": round(((current_price - stop_loss) / current_price) * 100, 1) if current_price > 0 else 0.0,
        "structural_stop_loss_method": sl_method,
        "gap_risk_nav_cap": gap_sized_nav,
        "gap_risk_note": gap_sizing_note,
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
        "position_size_nav": position_size_nav,
    }


LOCKED_QUANT_THRESHOLDS = {
    "f_score_min": 6,
    "mos_min_pct": 15.0,
    "z_score_min": 1.80,
    "rsi_max_entry": 70.0,
    "conviction_min": 55.0,  # Legacy key preserved for backward compatibility
    "watch_conviction_min": 55.0,
    "buy_conviction_min": 70.0,
    "adv20_absorption_max_pct": 0.10,
    "sector_exposure_max_pct": 0.25,
    "pillar_weights": {"fa": 0.40, "ta": 0.25, "flow": 0.20, "macro_news": 0.15},
    "adr_version": "ADR-0002",
}

RISK_FREE_HURDLE_RATE_PCT = 4.5  # Sàn lãi suất tiền gửi rủi ro thấp theo năm


def _extract_pnl_and_r_multiples(trades: list[dict]) -> tuple[list[float], list[float]]:
    pnl_list = []
    r_multiples = []
    for t in trades:
        pnl = float(t.get("pnl_pct", 0.0))
        pnl_list.append(pnl)

        entry_p = float(t.get("entry_price", 0.0))
        init_stop = float(t.get("initial_stop_price", 0.0))

        if entry_p > init_stop > 0:
            initial_risk_pct = ((entry_p - init_stop) / entry_p) * 100.0
            r_m = pnl / initial_risk_pct if initial_risk_pct > 0 else 0.0
        else:
            r_m = float(t.get("r_multiple", 0.0))
        r_multiples.append(r_m)
    return pnl_list, r_multiples


def _compute_effective_sample_size(pnl_list: list[float]) -> float:
    n_trades = len(pnl_list)
    if n_trades < 4:
        return float(n_trades)
    s_pnl = pd.Series(pnl_list)
    rho_1 = s_pnl.autocorr(lag=1)
    if pd.notnull(rho_1) and -0.99 <= rho_1 <= 0.99:
        ess_calc = n_trades * ((1.0 - rho_1) / (1.0 + rho_1))
        return round(max(1.0, min(float(n_trades), ess_calc)), 1)
    return float(n_trades)


def _compute_profit_factor(sum_wins: float, sum_losses: float) -> float:
    if sum_losses > 0:
        return round(sum_wins / sum_losses, 2)
    return 99.0 if sum_wins > 0 else 0.0


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

    pnl_list, r_multiples = _extract_pnl_and_r_multiples(trades)
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
    profit_factor = _compute_profit_factor(sum(wins), abs(sum(losses)))
    avg_r = round(float(pd.Series(r_multiples).mean()), 2) if r_multiples else 0.0
    effective_n = _compute_effective_sample_size(pnl_list)

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


MAX_SECTOR_WEIGHT_PCT: float = 25.0


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
    if n >= 4 and ret_std > 1e-12:
        s_ret = pd.Series(arr)
        rho_1 = s_ret.autocorr(lag=1)
        if pd.notnull(rho_1) and -0.99 <= rho_1 <= 0.99:
            ess = n * ((1.0 - rho_1) / (1.0 + rho_1))
            effective_n = round(max(1.0, min(float(n), ess)), 1)

    is_significant = bool(ci_lower > 0.0)
    warning_msg = ""
    if not is_significant:
        warning_msg = (
            f"Khoảng tin cậy {int(ci * 100)}% [{ci_lower}, {ci_upper}] chứa giá trị <= 0. "
            "Chưa đủ bằng chứng thống kê để khẳng định chiến lược có Edge thực sự."
        )
    elif effective_n < 30.0:
        warning_msg = f"Effective Sample Size ({effective_n}) < 30. Cần tích lũy thêm dữ liệu để kết luận chắc chắn."

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

CALIBRATION_BUCKET_NAMES: Final[list[str]] = ["50-60", "60-70", "70-80", "80-90", "90-100"]


def _extract_trade_confidence(row: dict[str, Any]) -> tuple[float, int] | None:
    if not isinstance(row, dict):
        return None
    raw_conf = row.get("ai_confidence", row.get("confidence"))
    if raw_conf is None:
        return None
    try:
        conf = float(raw_conf)
        if 0.0 <= conf <= 1.0:
            conf *= 100.0
    except (ValueError, TypeError):
        return None
    pnl = float(row.get("pnl_pct", row.get("pnl", 0.0)))
    win = 1 if pnl > 0 else 0
    return conf, win


def _assign_confidence_bucket(conf: float) -> str | None:
    """Assign confidence value (50.0 to 100.0) to corresponding bucket."""
    if conf < 50.0 or conf > 100.0:
        return None
    if conf >= 90.0:
        return "90-100"
    if conf >= 80.0:
        return "80-90"
    if conf >= 70.0:
        return "70-80"
    if conf >= 60.0:
        return "60-70"
    return "50-60"


def _evaluate_calibration_bucket(
    b_name: str, wins: list[int], min_obs: int, max_gap: float
) -> tuple[dict[str, Any], bool, bool]:
    lo_val = float(b_name.split("-")[0])
    midpoint = (lo_val + 5.0) / 100.0
    n = len(wins)
    actual_wr = round(sum(wins) / n, 3)
    gap = round(abs(actual_wr - midpoint), 3)

    is_bucket_calibrated = True
    evaluated = n >= min_obs
    if evaluated and (gap > max_gap or (midpoint >= 0.75 and actual_wr < 0.60)):
        is_bucket_calibrated = False

    res = {
        "n": n,
        "claimed_midpoint": midpoint,
        "actual_win_rate": actual_wr,
        "calibration_gap": gap,
        "evaluated": evaluated,
        "is_calibrated": is_bucket_calibrated,
    }
    return res, evaluated, (evaluated and not is_bucket_calibrated)


def _build_calibration_warning(
    evaluated_buckets: int, uncalibrated_buckets: int, min_obs: int
) -> tuple[bool, bool, str]:
    if evaluated_buckets == 0:
        return False, False, f"Chưa có bucket nào đủ tối thiểu {min_obs} lệnh để kết luận độ chuẩn định."
    if uncalibrated_buckets > 0:
        return (
            False,
            False,
            "⚠️ AI Confidence bị lệch chuẩn (Uncalibrated): Tỷ lệ thắng thực tế sai lệch đáng kể "
            "so với độ tin cậy AI phát biểu. CẤM đưa ai_confidence vào công thức Half-Kelly position sizing.",
        )
    return True, True, ""


def _filter_trades_by_horizon(
    trades: list[dict[str, Any]],
    horizon_days: Optional[int],
    as_of_date: Optional[Any] = None,
) -> list[dict[str, Any]]:
    """Filter trades within horizon window (in calendar/trading days)."""
    if not horizon_days or horizon_days <= 0 or not trades:
        return trades

    ref_date = datetime.now().date()
    if as_of_date:
        if isinstance(as_of_date, str):
            try:
                ref_date = datetime.strptime(as_of_date[:10], "%Y-%m-%d").date()
            except ValueError:
                pass
        elif isinstance(as_of_date, datetime):
            ref_date = as_of_date.date()

    cutoff_date = ref_date - timedelta(days=int(horizon_days * 1.5))
    filtered = []
    for t in trades:
        if not isinstance(t, dict):
            continue
        days_ago = t.get("days_ago") or t.get("days_elapsed")
        if days_ago is not None:
            try:
                if float(days_ago) <= horizon_days:
                    filtered.append(t)
                continue
            except (ValueError, TypeError):
                pass

        d_str = t.get("exit_date") or t.get("trading_date") or t.get("date") or t.get("entry_date")
        if d_str:
            try:
                t_date = datetime.strptime(str(d_str)[:10], "%Y-%m-%d").date()
                if t_date >= cutoff_date:
                    filtered.append(t)
                continue
            except ValueError:
                pass
        filtered.append(t)
    return filtered


def check_ai_calibration(
    trades: list[dict[str, Any]],
    min_observations_per_bucket: int = 3,
    max_acceptable_gap: float = 0.15,
    horizon_days: Optional[int] = 60,
    as_of_date: Optional[Any] = None,
) -> dict[str, Any]:
    """Kiểm tra độ chuẩn định (Calibration) của AI Confidence (Phase 4b / 7c).

    Bóc tách tỷ lệ thắng thực tế so với độ tin cậy được AI công bố.
    Neo theo chu kỳ horizon_days (mặc định 60 phiên giao dịch).
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

    effective_trades = _filter_trades_by_horizon(trades, horizon_days, as_of_date)
    if not effective_trades:
        return {
            "buckets": {},
            "is_calibrated": False,
            "allow_kelly_sizing": False,
            "brier_score": None,
            "total_evaluated_trades": 0,
            "warning": f"Không có dữ liệu giao dịch nào trong chu kỳ {horizon_days} phiên.",
        }

    buckets: dict[str, list[int]] = {b: [] for b in CALIBRATION_BUCKET_NAMES}
    conf_vals: list[float] = []
    win_vals: list[int] = []

    for row in effective_trades:
        extracted = _extract_trade_confidence(row)
        if extracted is None:
            continue
        conf, win = extracted
        b_name = _assign_confidence_bucket(conf)
        if b_name:
            buckets[b_name].append(win)
            conf_vals.append(conf / 100.0)
            win_vals.append(win)

    bucket_results: dict[str, Any] = {}
    evaluated_buckets = 0
    uncalibrated_buckets = 0

    for b_name, wins in buckets.items():
        if not wins:
            continue
        res, is_eval, is_uncal = _evaluate_calibration_bucket(
            b_name, wins, min_observations_per_bucket, max_acceptable_gap
        )
        bucket_results[b_name] = res
        if is_eval:
            evaluated_buckets += 1
        if is_uncal:
            uncalibrated_buckets += 1

    brier_score = None
    if conf_vals and win_vals:
        brier_score = round(float(np.mean([(c - w) ** 2 for c, w in zip(conf_vals, win_vals)])), 4)

    is_calibrated, allow_kelly, warn = _build_calibration_warning(
        evaluated_buckets, uncalibrated_buckets, min_observations_per_bucket
    )

    return {
        "buckets": bucket_results,
        "is_calibrated": is_calibrated,
        "allow_kelly_sizing": allow_kelly,
        "brier_score": brier_score,
        "total_evaluated_trades": len(win_vals),
        "warning": warn,
        "horizon_days": horizon_days,
    }


def calibrate_scenario_probabilities(
    scenarios: list[dict[str, Any]],
    horizon_days: int = 60,
    min_observations: int = 5,
    max_acceptable_gap: float = 0.15,
) -> dict[str, Any]:
    """Hiệu chuẩn phân phối xác suất kịch bản Pass 1 (P_bull, P_base, P_bear) theo chu kỳ 60 phiên (Phase 7c).

    So sánh xác suất gán trước với kết quả kịch bản thực tế ('BULL', 'BASE', 'BEAR').
    Tính Brier Score kịch bản và độ lệch (gap) từng nhánh kịch bản.
    """
    if not scenarios:
        return {
            "is_calibrated": False,
            "brier_score": None,
            "total_evaluated": 0,
            "horizon_days": horizon_days,
            "gaps": {},
            "warning": "Không có dữ liệu kịch bản để hiệu chuẩn.",
        }

    valid_items = []
    for sc in scenarios:
        if not isinstance(sc, dict):
            continue
        outcome = str(sc.get("actual_outcome") or sc.get("outcome") or "").upper().strip()
        if outcome in ("BULL", "BASE", "BEAR"):
            valid_items.append(sc)

    if len(valid_items) < min_observations:
        return {
            "is_calibrated": False,
            "brier_score": None,
            "total_evaluated": len(valid_items),
            "horizon_days": horizon_days,
            "gaps": {},
            "warning": f"Chưa đủ dữ liệu quan sát trong chu kỳ {horizon_days} phiên (có {len(valid_items)}/{min_observations} mẫu).",
        }

    brier_scores = []
    p_bulls, p_bases, p_bears = [], [], []
    y_bulls, y_bases, y_bears = [], [], []

    for item in valid_items:
        pb = float(item.get("P_bull", item.get("p_bull", 0.33)))
        pbase = float(item.get("P_base", item.get("p_base", 0.34)))
        pbear = float(item.get("P_bear", item.get("p_bear", 0.33)))
        tot = pb + pbase + pbear
        if tot > 0:
            pb, pbase, pbear = pb / tot, pbase / tot, pbear / tot

        outcome = str(item.get("actual_outcome") or item.get("outcome") or "").upper().strip()
        yb = 1.0 if outcome == "BULL" else 0.0
        ybase = 1.0 if outcome == "BASE" else 0.0
        ybear = 1.0 if outcome == "BEAR" else 0.0

        p_bulls.append(pb)
        p_bases.append(pbase)
        p_bears.append(pbear)
        y_bulls.append(yb)
        y_bases.append(ybase)
        y_bears.append(ybear)

        b_i = (pb - yb) ** 2 + (pbase - ybase) ** 2 + (pbear - ybear) ** 2
        brier_scores.append(b_i)

    mean_brier = round(float(np.mean(brier_scores)), 4)
    n = float(len(valid_items))
    gap_bull = round(abs(float(np.mean(p_bulls)) - (sum(y_bulls) / n)), 4)
    gap_base = round(abs(float(np.mean(p_bases)) - (sum(y_bases) / n)), 4)
    gap_bear = round(abs(float(np.mean(p_bears)) - (sum(y_bears) / n)), 4)
    max_gap = max(gap_bull, gap_base, gap_bear)

    is_calibrated = (max_gap <= max_acceptable_gap) and (mean_brier <= 0.40)
    warning = ""
    if not is_calibrated:
        warning = (
            f"Phân phối xác suất kịch bản AI bị lệch chuẩn chu kỳ {horizon_days} phiên "
            f"(Max gap: {max_gap:.1%}, Brier: {mean_brier:.4f}). Cảnh báo rủi ro mô hình."
        )

    return {
        "is_calibrated": is_calibrated,
        "brier_score": mean_brier,
        "total_evaluated": len(valid_items),
        "horizon_days": horizon_days,
        "gaps": {
            "bull_gap": gap_bull,
            "base_gap": gap_base,
            "bear_gap": gap_bear,
            "max_gap": max_gap,
        },
        "warning": warning,
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


def _generate_bootstrap_indices(
    n: int,
    n_simulations: int,
    block_size: int,
    rng: np.random.Generator,
) -> np.ndarray:
    """Sinh ma trận chỉ số lấy mẫu theo khối tròn (Circular Block Bootstrap)."""
    if block_size <= 1 or n <= 1:
        return rng.integers(0, n, size=(n_simulations, n))

    effective_block = min(block_size, n)
    k_blocks = int(np.ceil(n / effective_block))
    start_indices = rng.integers(0, n, size=(n_simulations, k_blocks))
    offsets = np.arange(effective_block)
    stacked = (start_indices[:, :, None] + offsets[None, None, :]) % n
    return stacked.reshape(n_simulations, k_blocks * effective_block)[:, :n]


# Phase 5 & 6: Advanced Portfolio Optimization, Monte Carlo & Risk Governance
def simulate_monte_carlo_drawdown(
    trade_pnl_pcts: list[float],
    n_simulations: int = 2_000,
    initial_capital: float = 100_000_000.0,
    block_size: int | None = None,
    random_state: int | None = 42,
) -> dict[str, Any]:
    """Mô phỏng 2,000 kịch bản ngẫu nhiên tráo đổi chuỗi lệnh (Trade order shuffling) (Phase 5a & 6a).

    Hỗ trợ Stationary Block Bootstrap để bảo toàn các cụm lệnh lỗ liên tiếp trong khủng hoảng.
    Đo lường phân vị Max Drawdown tồi tệ nhất (P95, P99) và xác suất sụt giảm quá 15% vốn.
    """
    fallback_res: dict[str, Any] = {
        "median_drawdown_pct": 0.0,
        "p95_drawdown_pct": 0.0,
        "p99_drawdown_pct": 0.0,
        "prob_drawdown_over_15pct": 0.0,
        "max_consecutive_losses": 0,
        "n_simulations": 0,
        "n_trades": 0,
        "block_size": 1,
    }

    if not trade_pnl_pcts:
        return fallback_res

    try:
        arr = np.asarray(trade_pnl_pcts, dtype=float)
        arr = arr[~np.isnan(arr)]
    except Exception:
        return fallback_res

    n = len(arr)
    if n == 0:
        return fallback_res

    if block_size is None:
        effective_block = 1 if n < 3 else max(3, int(round(n ** (1.0 / 3.0))))
        effective_block = min(effective_block, n)
    else:
        effective_block = max(1, min(int(block_size), n))

    rng = np.random.default_rng(random_state)
    indices = _generate_bootstrap_indices(n, n_simulations, effective_block, rng)
    sim_pnl = arr[indices]

    # Vectorized equity curve computation
    mults = 1.0 + (sim_pnl / 100.0)
    cum_equity = np.cumprod(mults, axis=1) * initial_capital
    initial_col = np.full((n_simulations, 1), initial_capital)
    full_equity = np.hstack([initial_col, cum_equity])

    running_max = np.maximum.accumulate(full_equity, axis=1)
    drawdowns = (full_equity - running_max) / running_max
    max_dd_per_sim = np.min(drawdowns, axis=1) * 100.0

    # Phân vị Max Drawdown đại số âm (5% và 1% xấu nhất)
    median_dd = round(float(np.median(max_dd_per_sim)), 2)
    p95_dd = round(float(np.percentile(max_dd_per_sim, 5.0)), 2)
    p99_dd = round(float(np.percentile(max_dd_per_sim, 1.0)), 2)
    prob_over_15 = round(float(np.mean(max_dd_per_sim <= -15.0)), 4)

    cur_loss, max_loss = 0, 0
    for p in arr:
        if p <= 0:
            cur_loss += 1
            max_loss = max(max_loss, cur_loss)
        else:
            cur_loss = 0

    return {
        "median_drawdown_pct": median_dd,
        "p95_drawdown_pct": p95_dd,
        "p99_drawdown_pct": p99_dd,
        "prob_drawdown_over_15pct": prob_over_15,
        "max_consecutive_losses": max_loss,
        "n_simulations": n_simulations,
        "n_trades": n,
        "block_size": effective_block,
    }


VERDICT_HIGH_EFFICIENCY: Final[str] = "HIGH_EFFICIENCY_INSURANCE"
VERDICT_FAIR_TRADE: Final[str] = "FAIR_RISK_TRADE"
VERDICT_COSTLY_PROTECTION: Final[str] = "COSTLY_PROTECTION"
VERDICT_FREE_PROTECTION: Final[str] = "FREE_PROTECTION"


def calculate_sector_gate_insurance_roi(
    cagr_without_gate: float,
    cagr_with_gate: float,
    mdd_without_gate: float,
    mdd_with_gate: float,
) -> dict[str, Any]:
    """Đo lường chi phí bảo hiểm và tỷ lệ hiệu quả (ROI) của Sector Gate (Phase 6d).

    - Upside Cost: Mức CAGR bị giảm do chốt chặn giới hạn ngành trong pha thị trường tăng.
    - Protection Benefit: Mức giảm thiểu Max Drawdown tránh được khi xảy ra sụp đổ ngành/thị trường.
    - Insurance ROI = Protection Benefit / Upside Cost.
    """
    upside_cost = max(0.0, round(float(cagr_without_gate - cagr_with_gate), 2))
    abs_mdd_no_gate = abs(float(mdd_without_gate))
    abs_mdd_with_gate = abs(float(mdd_with_gate))
    protection_benefit = max(0.0, round(abs_mdd_no_gate - abs_mdd_with_gate, 2))

    if upside_cost <= 0.0:
        roi = 999.0 if protection_benefit > 0.0 else 1.0
        verdict = VERDICT_FREE_PROTECTION
    else:
        roi = round(protection_benefit / upside_cost, 2)
        if roi >= 2.0:
            verdict = VERDICT_HIGH_EFFICIENCY
        elif roi >= 1.0:
            verdict = VERDICT_FAIR_TRADE
        else:
            verdict = VERDICT_COSTLY_PROTECTION

    return {
        "cagr_without_gate": round(float(cagr_without_gate), 2),
        "cagr_with_gate": round(float(cagr_with_gate), 2),
        "upside_cost_pct": upside_cost,
        "mdd_without_gate": round(abs_mdd_no_gate, 2),
        "mdd_with_gate": round(abs_mdd_with_gate, 2),
        "protection_benefit_pct": protection_benefit,
        "insurance_roi": roi,
        "verdict": verdict,
    }


# =============================================================================
# PHASE 7e: CONVICTION WEIGHTS STATISTICAL VALIDATION (SPEARMAN IC & FDR)
# =============================================================================

MIN_CONVICTION_OPTIMIZATION_SAMPLE: Final[int] = 100


def _calculate_spearman_rank_correlation(x: list[float], y: list[float]) -> tuple[float, float, float]:
    """Calculate Spearman rank correlation, t-statistic, and two-tailed p-value without scipy."""
    n = len(x)
    if n < 3:
        return 0.0, 0.0, 1.0

    sx = pd.Series(x, dtype=float).rank()
    sy = pd.Series(y, dtype=float).rank()

    rho = sx.corr(sy)
    if pd.isna(rho):
        return 0.0, 0.0, 1.0

    rho = float(np.clip(rho, -0.999999, 0.999999))
    t_stat = float(rho * np.sqrt((n - 2) / (1.0 - rho**2)))

    # Two-tailed p-value using normal/asymptotic erf approximation
    p_val = float(math.erfc(abs(t_stat) / math.sqrt(2.0)))
    return round(rho, 4), round(t_stat, 4), round(p_val, 4)


def calculate_pillar_spearman_ic(
    records: list[dict[str, Any]],
    return_col: str = "alpha_t20",
    min_observations: int = 30,
) -> dict[str, Any]:
    """Tính toán Hệ số tương quan hạng Spearman (Spearman IC) cho 4 trụ cột Conviction (Phase 7e).

    Loại trừ các bản ghi có mos_is_informative = False khi tính IC cho trụ cột MoS.
    """
    if not records:
        return {
            "status": "EMPTY_RECORDS",
            "pillars": {},
            "total_records": 0,
            "informative_mos_ratio": 0.0,
        }

    pillar_keys = ["s_mos", "s_fscore", "s_ta", "s_flow"]
    extracted: dict[str, tuple[list[float], list[float]]] = {k: ([], []) for k in pillar_keys}

    total_mos_records = 0
    informative_mos_count = 0

    for rec in records:
        if not isinstance(rec, dict):
            continue

        ret = rec.get(return_col)
        if ret is None:
            ret = rec.get("alpha") or rec.get("return_t20") or rec.get("ret_t20")
        if ret is None or pd.isna(ret):
            continue
        ret_val = float(ret)

        # 1. MoS: Bắt buộc lọc theo cờ mos_is_informative
        mos_val = rec.get("s_mos") if rec.get("s_mos") is not None else rec.get("mos_pct")
        if mos_val is not None and not pd.isna(mos_val):
            total_mos_records += 1
            is_info = rec.get("mos_is_informative", True)
            if is_info:
                informative_mos_count += 1
                extracted["s_mos"][0].append(float(mos_val))
                extracted["s_mos"][1].append(ret_val)

        # 2. F-Score
        f_val = rec.get("s_fscore") if rec.get("s_fscore") is not None else rec.get("f_score")
        if f_val is not None and not pd.isna(f_val):
            extracted["s_fscore"][0].append(float(f_val))
            extracted["s_fscore"][1].append(ret_val)

        # 3. Technical (TA)
        ta_val = rec.get("s_ta") if rec.get("s_ta") is not None else rec.get("rsi14")
        if ta_val is not None and not pd.isna(ta_val):
            extracted["s_ta"][0].append(float(ta_val))
            extracted["s_ta"][1].append(ret_val)

        # 4. Flow
        flow_val = rec.get("s_flow") if rec.get("s_flow") is not None else rec.get("foreign_flow")
        if flow_val is not None and not pd.isna(flow_val):
            try:
                extracted["s_flow"][0].append(float(flow_val))
                extracted["s_flow"][1].append(ret_val)
            except (ValueError, TypeError):
                pass

    results: dict[str, Any] = {}
    for p_key in pillar_keys:
        xs, ys = extracted[p_key]
        n_obs = len(xs)
        if n_obs < min_observations:
            results[p_key] = {
                "ic": 0.0,
                "t_stat": 0.0,
                "p_value": 1.0,
                "n_obs": n_obs,
                "is_significant": False,
                "status": "INSUFFICIENT_OBSERVATIONS",
            }
            continue

        ic, t_stat, p_val = _calculate_spearman_rank_correlation(xs, ys)
        results[p_key] = {
            "ic": ic,
            "t_stat": t_stat,
            "p_value": p_val,
            "n_obs": n_obs,
            "is_significant": bool(p_val < 0.05),
            "status": "EVALUATED",
        }

    info_ratio = round(informative_mos_count / total_mos_records, 2) if total_mos_records > 0 else 1.0

    return {
        "status": "SUCCESS",
        "pillars": results,
        "total_records": len(records),
        "informative_mos_ratio": info_ratio,
    }


def apply_benjamini_hochberg_fdr(
    p_values: dict[str, float],
    alpha: float = 0.05,
    total_sample_size: Optional[int] = None,
) -> dict[str, Any]:
    """Kiểm định hiệu chỉnh đa biến Benjamini–Hochberg kiểm soát False Discovery Rate (FDR - Phase 7e).

    Nếu tổng số quan sát < 100, phát cảnh báo INSUFFICIENT_SAMPLE theo nguyên tắc
    'Thu thập trước, Hồi quy sau' (cấm tự động cập nhật trọng số Conviction).
    """
    if not p_values:
        return {
            "alpha": alpha,
            "total_hypotheses": 0,
            "significant_count": 0,
            "warning": "",
            "results": {},
        }

    warning_msg = ""
    if total_sample_size is not None and total_sample_size < MIN_CONVICTION_OPTIMIZATION_SAMPLE:
        warning_msg = (
            f"INSUFFICIENT_SAMPLE: Quy mô mẫu N={total_sample_size} < 100 quan sát. "
            "Tuân thủ nguyên tắc 'Thu thập trước, Hồi quy sau' — Không đủ điều kiện để tối ưu trọng số Conviction."
        )

    # Sort p-values ascending
    sorted_items = sorted(p_values.items(), key=lambda item: float(item[1]))
    m = len(sorted_items)

    # Calculate BH adjusted p-values and significance
    q_thresholds = [(i + 1) / m * alpha for i in range(m)]

    # Largest k such that P_(k) <= (k/m) * alpha
    max_k = -1
    for i in range(m):
        if float(sorted_items[i][1]) <= q_thresholds[i]:
            max_k = i

    # Step-up adjusted p-values: p_adj_i = min(1.0, (m / (i+1)) * p_i)
    raw_p_floats = [float(val) for _, val in sorted_items]
    adj_p_vals = [min(1.0, (m / (i + 1)) * raw_p_floats[i]) for i in range(m)]

    # Monotonic adjustment from right to left
    for i in range(m - 2, -1, -1):
        adj_p_vals[i] = min(adj_p_vals[i], adj_p_vals[i + 1])

    results: dict[str, Any] = {}
    sig_count = 0
    for idx, (name, _) in enumerate(sorted_items):
        is_sig = idx <= max_k
        if is_sig:
            sig_count += 1
        results[name] = {
            "rank": idx + 1,
            "raw_p_value": round(raw_p_floats[idx], 4),
            "adjusted_p_value": round(adj_p_vals[idx], 4),
            "critical_threshold": round(q_thresholds[idx], 4),
            "is_significant": is_sig,
        }

    return {
        "alpha": alpha,
        "total_hypotheses": m,
        "significant_count": sig_count,
        "warning": warning_msg,
        "results": results,
    }
