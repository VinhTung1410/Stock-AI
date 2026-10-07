"""
Contrarian Module / Panic Buy Engine (Phase 20 - v10.0 / ADR-0009).

Kiến trúc 4-State Contrarian Framework:
Lớp 1: Market Regime Layer - Điều chỉnh MoS dựa trên vĩ mô.
Lớp 2: Governance & Event Risk Layer - Chặn rủi ro sự kiện (kiểm toán, pháp lý).
Lớp 3: Fundamental Integrity & Valuation Layer - Chốt chặn sinh tồn & định giá sâu, bóc tách Value Trap.
Lớp 4: Panic Assessment Layer - Chấm điểm hoảng loạn liên tục (0-100). Phân loại Normal / Near-Panic / Extreme-Fear.
Lớp 5: Price Confirmation Layer - Yêu cầu xác nhận đảo chiều (chống dao rơi).
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from indicators import calculate_altman_z_score, calculate_vibe_quality_score
from quant_valuation import calculate_fair_value_and_mos

# Constants - Numerical Thresholds
CONTRARIAN_MIN_FSCORE = 7
CONTRARIAN_MIN_ZSCORE = 2.0
CONTRARIAN_MAX_DEBT_EQUITY = 1.0
CONTRARIAN_MIN_MOS_PCT = 15.0  # Tương đương ~17.6% Upside
CONTRARIAN_DEEP_MOS_PCT = 20.0  # Require deeper MoS in DOWNTREND (Tương đương 25% Upside)
CONTRARIAN_MAX_RSI_WATCH = 35.0   # <= 35 is NEAR-PANIC WATCH
CONTRARIAN_MAX_RSI_EXTREME = 30.0 # <= 30 is EXTREME FEAR / PANIC BUY
CONTRARIAN_MIN_ADV20_BILLION = 2.0
CONTRARIAN_MAX_POSITION_SIZE_PCT = 5.0
CONTRARIAN_MAX_PANIC_SIZE_PCT = 3.0 # Giảm size bắt đáy dao rơi xuống 3% tối đa
CONTRARIAN_STOP_LOSS_PCT = 0.08
SHADOW_MODE_ACTIVE = True  # Mặc định kích hoạt chế độ shadow 60 phiên (TASK-0074)

# Gate Names
GATE_REGIME = "MARKET_REGIME"
GATE_EVENT_RISK = "GOVERNANCE_EVENT_RISK"
GATE_SURVIVAL = "SURVIVAL_QUALITY"
GATE_VALUATION = "VALUATION_MOS"
GATE_PANIC_SCORE = "PANIC_SCORE"
GATE_PRICE_CONFIRM = "PRICE_CONFIRMATION"
GATE_LIQUIDITY = "ADV20_LIQUIDITY"
GATE_DATA = "DATA_GATE"

# States (ADR-0009 Standardized)
STATE_NORMAL = "NORMAL"
STATE_NEAR_PANIC_WATCH = "NEAR_PANIC_WATCH"
STATE_EXTREME_FEAR_WATCH = "EXTREME_FEAR_WATCH"
STATE_VALUATION_WATCH = "VALUATION_WATCH"
STATE_PANIC_BUY = "PANIC_BUY"
STATE_BLOCKED = "BLOCKED"

# Actions
ACTION_NO_SETUP = "KHÔNG CÓ SETUP (NORMAL)"
ACTION_WATCH_NEAR_PANIC = "👀 THEO DÕI (NEAR PANIC WATCH)"
ACTION_WATCH_EXTREME = "👀 CHỜ ĐÁY (EXTREME FEAR WATCH)"
ACTION_PANIC_BUY_STR = "🚨 BẮT ĐÁY PANIC BUY"
ACTION_BLOCKED = "❌ BỊ CHẶN (BLOCKED)"

STYLE_CONTRARIAN_PANIC_BUY = "🚨 [BẮT ĐÁY PANIC BUY]"
STYLE_WATCH_ZONE = "👀 [WATCH/ACCUMULATION ZONE]"

SECTOR_BANKING = "Ngân hàng"
SECTOR_BANK_NAMES = (SECTOR_BANKING, "Bank", "Banking")
RISK_KEYWORDS_VETO = ["kiểm toán ngoại trừ", "khởi tố", "bắt bớ", "thanh tra", "hủy niêm yết", "bán tháo lãnh đạo"]


@dataclass
class ContrarianResult:
    symbol: str
    can_buy: bool
    status: str = STATE_NORMAL
    setup_type: str = ""
    style_type: str = ""
    action_state: str = ACTION_NO_SETUP
    is_contrarian: bool = True
    blocked_by: Optional[str] = None
    blocking_reasons: List[str] = field(default_factory=list)
    passed_gates: List[str] = field(default_factory=list)
    position_size_pct: float = 0.0
    position_size_nav: str = "0.0% NAV"
    target_price: float = 0.0
    stop_loss: float = 0.0
    fair_value: float = 0.0
    mos_pct: float = 0.0
    upside_pct: float = 0.0
    risk_reward: float = 0.0
    metrics: Dict[str, Any] = field(default_factory=dict)


def _check_market_regime(macro_regime: Optional[str], result: ContrarianResult) -> float:
    required_mos = CONTRARIAN_MIN_MOS_PCT
    if macro_regime == "DOWNTREND":
        required_mos = CONTRARIAN_DEEP_MOS_PCT
        result.metrics["regime_penalty"] = True
    result.passed_gates.append(GATE_REGIME)
    return required_mos


def _check_governance_and_event_risk(tech_data: Dict[str, Any], result: ContrarianResult) -> bool:
    risk_keywords = tech_data.get("risk_keywords", "")
    if isinstance(risk_keywords, list):
        risk_keywords = " ".join(risk_keywords)
    risk_keywords = risk_keywords.lower()

    for kw in RISK_KEYWORDS_VETO:
        if kw in risk_keywords:
            result.can_buy = False
            result.status = STATE_BLOCKED
            result.action_state = ACTION_BLOCKED
            result.blocked_by = GATE_EVENT_RISK
            result.blocking_reasons.append(f"Rủi ro sự kiện/quản trị: Phát hiện từ khóa '{kw}'. VETO!")
            return False

    result.passed_gates.append(GATE_EVENT_RISK)
    return True


def _extract_f_score(fin: Dict[str, Any]) -> int:
    f_score = fin.get("f_score")
    if f_score is None:
        f_res = calculate_vibe_quality_score(fin)
        return int(f_res.get("score", 0))
    return int(f_score)


def _extract_z_score(fin: Dict[str, Any], sector: str) -> Optional[float]:
    z_score = fin.get("z_score")
    if z_score is None:
        z_res = calculate_altman_z_score(fin, sector=sector)
        z_val = z_res.get("z_score")
        return float(z_val) if z_val is not None else None
    return float(z_score)


def _get_stress_haircut(symbol: str, sector: str, fin_dict: Dict[str, Any], tech_data: Dict[str, Any], result: ContrarianResult) -> float:
    from quant_valuation import classify_stock_archetype
    archetype = classify_stock_archetype(symbol, sector)
    
    if archetype == "REAL_ESTATE":
        haircut = 0.25
    elif archetype == "CYCLICAL":
        haircut = 0.35 if result.metrics.get("cyclical_damage", False) else 0.25
    elif archetype == "BANK":
        haircut = 0.20
        npl = float(fin_dict.get("Tỷ lệ nợ xấu") or fin_dict.get("npl") or 0.0)
        if npl > 2.0:
            haircut += 0.10
    else:  # GROWTH_COMPOUNDER
        haircut = 0.15
        
    risk_kw = tech_data.get("risk_keywords", "")
    if isinstance(risk_kw, list):
        risk_kw = " ".join(risk_kw)
    if "phạt" in risk_kw.lower() or "cảnh báo" in risk_kw.lower() or "kiểm soát" in risk_kw.lower():
        haircut += 0.15
        
    core_ratio = fin_dict.get("core_earnings_ratio")
    if core_ratio is not None and float(core_ratio) < 0.5:
        haircut += 0.10
        
    return min(haircut, 0.60)

def _check_archetype_specific_gates(
    sector: str,
    fin_dict: Dict[str, Any],
    result: ContrarianResult,
) -> bool:
    """Kiểm tra các chốt chặn sinh tồn đặc thù theo Archetype (Nhánh B)."""
    is_bank = sector in SECTOR_BANK_NAMES
    is_re = sector in ("Bất động sản", "Real Estate", "Bất động sản Khu công nghiệp")
    is_sec = sector in ("Chứng khoán", "Financial Services")

    if is_bank:
        npl = fin_dict.get("Tỷ lệ nợ xấu") or fin_dict.get("npl")
        if npl is not None:
            npl_val = float(npl)
            result.metrics["npl"] = npl_val
            if npl_val > 3.0:
                result.can_buy = False
                result.status = STATE_BLOCKED
                result.action_state = ACTION_BLOCKED
                result.blocked_by = GATE_SURVIVAL
                result.blocking_reasons.append(f"L2 Archetype: Ngân hàng có nợ xấu cao (NPL={npl_val}% > 3%). Rủi ro vỡ nợ!")
                return False
    elif is_sec:
        margin_ratio = fin_dict.get("financial_leverage") or fin_dict.get("Đòn bẩy tài chính")
        if margin_ratio is not None:
            lev_val = float(margin_ratio) / 100.0
            result.metrics["financial_leverage"] = lev_val
            if lev_val > 3.0:
                result.can_buy = False
                result.status = STATE_BLOCKED
                result.action_state = ACTION_BLOCKED
                result.blocked_by = GATE_SURVIVAL
                result.blocking_reasons.append(f"L2 Archetype: Công ty CK dùng đòn bẩy quá rủi ro (Leverage={lev_val}x > 3.0x).")
                return False
    elif is_re:
        debt_equity = fin_dict.get("debt_equity") or fin_dict.get("debt_on_equity") or fin_dict.get("debt_to_equity")
        if debt_equity is not None:
            de_val = float(debt_equity) / 100.0
            result.metrics["debt_equity"] = de_val
            if de_val > 1.5:
                result.can_buy = False
                result.status = STATE_BLOCKED
                result.action_state = ACTION_BLOCKED
                result.blocked_by = GATE_SURVIVAL
                result.blocking_reasons.append(f"L2 Archetype: BĐS rủi ro thanh khoản (D/E={de_val}x > 1.5x).")
                return False
    else:
        z_score = _extract_z_score(fin_dict, sector)
        result.metrics["z_score"] = z_score
        debt_equity = fin_dict.get("debt_equity") or fin_dict.get("debt_on_equity") or fin_dict.get("debt_to_equity")
        if debt_equity is not None:
            result.metrics["debt_equity"] = float(debt_equity) / 100.0

        if z_score is not None and z_score <= CONTRARIAN_MIN_ZSCORE:
            result.can_buy = False
            result.status = STATE_BLOCKED
            result.action_state = ACTION_BLOCKED
            result.blocked_by = GATE_SURVIVAL
            result.blocking_reasons.append(f"L2 Archetype: Phi Tài chính có nguy cơ phá sản (Z-Score={z_score:.2f} <= {CONTRARIAN_MIN_ZSCORE}).")
            return False
        de_val = result.metrics.get("debt_equity")
        if de_val is not None and de_val > CONTRARIAN_MAX_DEBT_EQUITY:
            result.can_buy = False
            result.status = STATE_BLOCKED
            result.action_state = ACTION_BLOCKED
            result.blocked_by = GATE_SURVIVAL
            result.blocking_reasons.append(f"L2 Archetype: Đòn bẩy cao (D/E={de_val:.2f}x > {CONTRARIAN_MAX_DEBT_EQUITY:.1f}x).")
            return False

    return True


def _check_fundamental_integrity(
    symbol: str,
    current_price: float,
    fin_dict: Optional[Dict[str, Any]],
    tech_data: Dict[str, Any],
    sector: str,
    required_mos: float,
    result: ContrarianResult,
) -> bool:
    if not fin_dict:
        result.can_buy = False
        result.status = STATE_BLOCKED
        result.action_state = ACTION_BLOCKED
        result.blocked_by = GATE_SURVIVAL
        result.blocking_reasons.append("Thiếu báo cáo tài chính.")
        return False
    from indicators import calculate_vibe_quality_score
    f_res = calculate_vibe_quality_score(fin_dict or {}, sector)
    f_score = f_res.get("score", 0)
    data_comp = f_res.get("data_completeness", 1.0)
    
    result.metrics["f_score"] = f_score
    result.metrics["f_score_details"] = f_res

    # 0. Hard Veto Risk Overlays (Nhánh B - Archetype Overlays)
    if not _check_archetype_specific_gates(sector, fin_dict, result):
        return False

    is_bank = sector in SECTOR_BANK_NAMES

    # 1. 3-Tier FQ-Score Gating (Task-23.1)
    if f_score < 4:
        # TIER 1: BLOCK UNCONDITIONALLY (Value Trap)
        if data_comp < 0.7 and not is_bank:
            result.can_buy = False
            result.status = STATE_BLOCKED
            result.action_state = "DATA / FUNDAMENTAL REVIEW REQUIRED"
            result.blocked_by = GATE_SURVIVAL
            result.blocking_reasons.append(f"FQ-Score={f_score}/9 nhưng thiếu dữ liệu (Completeness={data_comp*100:.0f}%). Yêu cầu Audit Data.")
            return False
        else:
            result.can_buy = False
            result.status = STATE_BLOCKED
            result.action_state = ACTION_BLOCKED
            result.blocked_by = GATE_SURVIVAL
            result.blocking_reasons.append(f"FQ-Score={f_score}/9 < 4 (Dữ liệu xác nhận). VALUE TRAP RÕ RÀNG!")
            return False

    elif f_score < CONTRARIAN_MIN_FSCORE:
        # TIER 2: CONDITIONAL PASS (Requires Overlays, which are already checked globally above)
        if data_comp < 0.7 and not is_bank:
            result.can_buy = False
            result.status = STATE_BLOCKED
            result.action_state = "DATA / FUNDAMENTAL REVIEW REQUIRED"
            result.blocked_by = GATE_SURVIVAL
            result.blocking_reasons.append(f"FQ-Score={f_score}/9 (Tier 2) nhưng thiếu dữ liệu (Completeness={data_comp*100:.0f}%). Không đủ cơ sở đánh giá.")
            return False
    else:
        # TIER 3: FULL PASS (f_score >= 7)
        pass

    # 2. Earnings Revision (Value Trap Check)
    margin_trend = fin_dict.get("margin_trend", "")
    is_earnings_declining = margin_trend == "down_2_quarters" or fin_dict.get("earnings_declining")
    
    if is_earnings_declining:
        from quant_valuation import classify_stock_archetype
        archetype = classify_stock_archetype(symbol, sector)
        
        cfo_indicator = fin_dict.get("cfo") or fin_dict.get("operating_cash_flow") or fin_dict.get("p_cf")
        is_cfo_negative = False
        if cfo_indicator is not None:
            is_cfo_negative = float(cfo_indicator) <= 0.0

        if archetype == "CYCLICAL" and not is_cfo_negative:
            result.metrics["cyclical_damage"] = True
            # Không block, nhưng sẽ ghi nhận để tăng haircut ở L4 và giảm size ở L6
            result.blocking_reasons.append("Lợi nhuận giảm (Đáy chu kỳ) nhưng CFO dương/an toàn. Sẽ áp dụng chiết khấu sâu & giảm vốn.")
        else:
            result.can_buy = False
            result.status = STATE_BLOCKED
            result.action_state = ACTION_BLOCKED
            result.blocked_by = GATE_SURVIVAL
            if archetype == "CYCLICAL" and is_cfo_negative:
                result.blocking_reasons.append("Cổ phiếu chu kỳ nhưng CFO âm (Dòng tiền cạn kiệt). VALUE TRAP!")
            else:
                result.blocking_reasons.append("Lợi nhuận/Biên gộp lao dốc (Structural Damage). VALUE TRAP!")
            return False

    # 3. Valuation & L4 Stress-MoS
    if "mos_pct" in fin_dict and "mos_is_informative" in fin_dict:
        mos_val = float(fin_dict["mos_pct"])
        calc_fv = current_price / (1.0 - mos_val / 100.0) if mos_val < 100.0 else current_price * 10.0
        val_res = {
            "mos_pct": mos_val,
            "mos_is_informative": bool(fin_dict["mos_is_informative"]),
            "fair_value": float(fin_dict.get("fair_value", calc_fv)),
        }
    else:
        val_res = calculate_fair_value_and_mos(
            symbol=symbol, current_price=current_price, fin_dict=fin_dict, sector=sector
        )

    base_mos_pct = float(val_res.get("mos_pct", 0.0))
    mos_is_informative = bool(val_res.get("mos_is_informative", False))
    fair_value = float(val_res.get("fair_value", 0.0))

    # L4: Dynamic Stress-MoS (Haircut Valuation)
    stress_haircut = _get_stress_haircut(symbol, sector, fin_dict, tech_data, result)
    result.metrics["stress_haircut_applied"] = stress_haircut
    
    stress_fair_value = fair_value * (1.0 - stress_haircut)
    stress_upside_pct = ((stress_fair_value - current_price) / current_price) * 100.0 if current_price > 0 else 0.0
    stress_mos_pct = ((stress_fair_value - current_price) / stress_fair_value) * 100.0 if stress_fair_value > 0 else 0.0

    result.mos_pct = stress_mos_pct # Gán MoS đã stress vào kết quả để UI hiện
    result.upside_pct = stress_upside_pct
    result.fair_value = stress_fair_value
    result.metrics["base_mos_pct"] = base_mos_pct
    result.metrics["mos_pct"] = stress_mos_pct
    result.metrics["upside_pct"] = stress_upside_pct
    result.metrics["base_fair_value"] = fair_value
    result.metrics["fair_value"] = stress_fair_value
    result.metrics["mos_is_informative"] = mos_is_informative

    if not mos_is_informative:
        result.can_buy = False
        result.status = STATE_BLOCKED
        result.action_state = ACTION_BLOCKED
        result.blocked_by = GATE_VALUATION
        result.blocking_reasons.append("Thiếu dữ liệu định giá tin cậy (mos_is_informative=False).")
        return False

    if stress_mos_pct < required_mos:
        result.can_buy = False
        result.status = STATE_BLOCKED
        result.action_state = ACTION_BLOCKED
        result.blocked_by = GATE_VALUATION
        result.blocking_reasons.append(f"L4 Stress-MoS={stress_mos_pct:+.1f}% < Yêu cầu {required_mos:.1f}%.")
        return False

    result.passed_gates.append(GATE_SURVIVAL)
    result.passed_gates.append(GATE_VALUATION)
    return True


def _calculate_panic_score(current_price: float, tech_data: Dict[str, Any]) -> float:
    rsi = float(tech_data.get("rsi14") or tech_data.get("rsi") or 50.0)
    ma20 = float(tech_data.get("ma20") or 0.0)
    
    score = 0.0
    
    # 1. RSI Score (Max 30)
    if rsi <= 25.0:
        score += 30.0
    elif rsi <= 35.0:
        score += 30.0 - (rsi - 25.0) * 3.0
        
    # 2. Drawdown / Deviation from MA20 (Max 20)
    if ma20 > 0:
        pct_below = (1.0 - (current_price / ma20)) * 100.0
        if pct_below >= 15.0:
            score += 20.0
        elif pct_below > 5.0:
            score += (pct_below - 5.0) * 2.0
            
    # 3. Volume Shock (Max 20)
    vol_ratio = float(tech_data.get("volume_ratio_20d") or 1.0)
    if vol_ratio >= 3.0:
        score += 20.0
    elif vol_ratio > 1.5:
        score += (vol_ratio - 1.5) * 13.33
        
    # 4. ATR Expansion / Volatility (Max 15)
    atr_ratio = float(tech_data.get("atr_ratio_14d") or 1.0)
    if atr_ratio >= 2.0:
        score += 15.0
    elif atr_ratio > 1.2:
        score += (atr_ratio - 1.2) * 18.75
        
    # 5. Gap Shock / Velocity (Max 15)
    if tech_data.get("has_gap_down", False):
        score += 15.0
        
    return round(min(100.0, score), 1)


def _evaluate_panic_state(current_price: float, tech_data: Dict[str, Any], result: ContrarianResult) -> bool:
    panic_score = _calculate_panic_score(current_price, tech_data)
    result.metrics["panic_score"] = panic_score
    
    if panic_score < 40.0:
        result.can_buy = False
        result.status = STATE_VALUATION_WATCH
        result.action_state = "👀 ĐỊNH GIÁ RẺ (VALUATION WATCH)"
        result.style_type = STYLE_WATCH_ZONE
        result.setup_type = f"👀 ĐỊNH GIÁ RẺ (Score={panic_score:.0f}, MoS: {result.mos_pct:+.1f}%)"
        result.blocked_by = GATE_PANIC_SCORE
        result.blocking_reasons.append(f"Chưa kích hoạt trạng thái hoảng loạn (Score={panic_score} < 40), chuyển sang theo dõi định giá.")
        return False
        
    result.passed_gates.append(GATE_PANIC_SCORE)
    
    trigger_txt = f"Score={panic_score:.0f}/100"
    result.metrics["extreme_fear_trigger"] = trigger_txt
    
    if panic_score >= 70.0:
        result.status = STATE_EXTREME_FEAR_WATCH
        result.action_state = ACTION_WATCH_EXTREME
        result.style_type = STYLE_WATCH_ZONE
        result.setup_type = f"👀 CHỜ BẮT ĐÁY ({trigger_txt}, MoS: {result.mos_pct:+.1f}%)"
    else:
        result.status = STATE_NEAR_PANIC_WATCH
        result.action_state = ACTION_WATCH_NEAR_PANIC
        result.style_type = STYLE_WATCH_ZONE
        result.setup_type = f"👀 THEO DÕI ({trigger_txt}, MoS: {result.mos_pct:+.1f}%)"
        
    return True


def _check_price_confirmation(current_price: float, tech_data: Dict[str, Any], result: ContrarianResult) -> bool:
    has_reversal = tech_data.get("has_reversal_pattern", False)
    bullish_div = tech_data.get("bullish_divergence", False)
    price_confirmation = tech_data.get("price_confirmation", False)
    volume_contraction = tech_data.get("volume_contraction", False)
    higher_low = tech_data.get("higher_low", False)
    ma20 = float(tech_data.get("ma20") or 0.0)

    conf_score = 0
    if higher_low:
        conf_score += 25
    if bullish_div:
        conf_score += 20
    if price_confirmation:
        conf_score += 20
    if current_price > ma20 and ma20 > 0:
        conf_score += 20
    if has_reversal:
        conf_score += 15
    if volume_contraction:
        conf_score += 10
    
    result.metrics["price_confirmation_score"] = conf_score
    is_structurally_confirmed = conf_score >= 60

    if "is_late_session" in tech_data:
        is_late_session = bool(tech_data["is_late_session"])
    else:
        from datetime import datetime
        from zoneinfo import ZoneInfo
        now = datetime.now(ZoneInfo("Asia/Ho_Chi_Minh"))
        is_late_session = now.hour > 14 or (now.hour == 14 and now.minute >= 15)
    is_backtest = tech_data.get("is_backtest", False)

    if not is_structurally_confirmed:
        result.can_buy = False
        result.blocked_by = GATE_PRICE_CONFIRM
        result.blocking_reasons.append(f"L5 Structure: Score={conf_score} < 60. Chưa có cấu trúc xác nhận đáy mạnh. Dao đang rơi!")
        return False

    if not is_late_session and not is_backtest:
        result.can_buy = False
        result.blocked_by = GATE_PRICE_CONFIRM
        result.blocking_reasons.append("L5 Structure: Chưa qua 14:15. Bắt đáy phiên sáng rất dễ dính Bull-trap (Fake reversal).")
        return False

    result.passed_gates.append(GATE_PRICE_CONFIRM)
    return True


def _check_liquidity_and_size(
    current_price: float,
    tech_data: Optional[Dict[str, Any]],
    half_kelly_f: float,
    kill_switch_active: bool,
    result: ContrarianResult,
) -> bool:
    adv20 = float(tech_data.get("adv20_billion", 0.0)) if tech_data else 0.0
    result.metrics["adv20_billion"] = adv20
    if adv20 < CONTRARIAN_MIN_ADV20_BILLION:
        result.can_buy = False
        result.blocked_by = GATE_LIQUIDITY
        result.position_size_pct = 0.0
        result.position_size_nav = "0.0% NAV"
        result.blocking_reasons.append(f"ADV20={adv20:.2f} tỷ < {CONTRARIAN_MIN_ADV20_BILLION:.1f} tỷ VND.")
        return False

    penalized_kelly = (max(0.01, half_kelly_f) / 2.0) * 100.0
    
    # Bắt đáy Panic Buy cần position size nhỏ hơn bình thường để thăm dò
    max_size = CONTRARIAN_MAX_PANIC_SIZE_PCT
    if result.metrics.get("cyclical_damage", False):
        max_size = min(max_size, 2.0) # Dao rơi ngành chu kỳ tối đa 2%
        
    base_size = min(max_size, max(1.0, penalized_kelly))

    if kill_switch_active:
        base_size = round(base_size * 0.5, 2)
        result.metrics["kill_switch_penalty"] = True

    result.position_size_pct = round(base_size, 2)
    result.position_size_nav = f"{result.position_size_pct:.1f}% NAV"

    result.stop_loss = round(current_price * (1.0 - CONTRARIAN_STOP_LOSS_PCT), 2)
    result.target_price = round(result.fair_value, 2)

    risk_per_share = max(0.01, current_price - result.stop_loss)
    reward_per_share = max(0.01, result.target_price - current_price)
    result.risk_reward = round(reward_per_share / risk_per_share, 2)

    result.passed_gates.append(GATE_LIQUIDITY)
    return True


def evaluate_contrarian_gates(
    symbol: str,
    current_price: float,
    tech_data: Optional[Dict[str, Any]] = None,
    fin_dict: Optional[Dict[str, Any]] = None,
    sector: str = "",
    macro_regime: Optional[str] = None,
    portfolio: Optional[List[Dict[str, Any]]] = None,
    kill_switch_active: bool = False,
    half_kelly_f: float = 0.12,
    shadow_mode: bool = SHADOW_MODE_ACTIVE,
) -> ContrarianResult:
    res = ContrarianResult(symbol=symbol.upper(), can_buy=False)
    _ = portfolio  # Reserved for cross-portfolio allocation gates

    if not symbol or current_price <= 0:
        res.status = STATE_BLOCKED
        res.action_state = ACTION_BLOCKED
        res.blocked_by = GATE_DATA
        res.blocking_reasons.append("Mã cổ phiếu hoặc thị giá không hợp lệ.")
        return res

    required_mos = _check_market_regime(macro_regime, res)

    if not _check_governance_and_event_risk(tech_data or {}, res):
        return res

    if not _check_fundamental_integrity(symbol, current_price, fin_dict, tech_data or {}, sector, required_mos, res):
        return res

    if not _evaluate_panic_state(current_price, tech_data or {}, res):
        return res
        
    if res.status == STATE_EXTREME_FEAR_WATCH:
        if _check_price_confirmation(current_price, tech_data or {}, res):
            if _check_liquidity_and_size(current_price, tech_data, half_kelly_f, kill_switch_active, res):
                res.status = STATE_PANIC_BUY
                is_backtest = bool(tech_data and tech_data.get("is_backtest", False))
                if shadow_mode and not is_backtest:
                    res.can_buy = False
                    res.action_state = "🔭 SHADOW BUY (60-phiên trial)"
                    res.metrics["shadow_mode"] = True
                else:
                    res.can_buy = True
                    res.action_state = ACTION_PANIC_BUY_STR
                res.style_type = STYLE_CONTRARIAN_PANIC_BUY
                trigger_txt = res.metrics.get("extreme_fear_trigger", "")
                res.setup_type = f"🚨 BẮT ĐÁY HOẢNG LOẠN ({trigger_txt}, MoS: {res.mos_pct:+.1f}%)"
                return res

    return res
