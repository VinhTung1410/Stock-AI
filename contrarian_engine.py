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

from indicators import calculate_altman_z_score, calculate_piotroski_f_score
from quant_valuation import calculate_fair_value_and_mos

# Constants - Numerical Thresholds
CONTRARIAN_MIN_FSCORE = 7
CONTRARIAN_MIN_ZSCORE = 2.0
CONTRARIAN_MAX_DEBT_EQUITY = 1.0
CONTRARIAN_MIN_MOS_PCT = 20.0
CONTRARIAN_DEEP_MOS_PCT = 30.0  # Require deeper MoS in DOWNTREND
CONTRARIAN_MAX_RSI_NORMAL = 35.0  # > 35 is NORMAL
CONTRARIAN_MAX_RSI_WATCH = 35.0   # <= 35 is NEAR-PANIC WATCH
CONTRARIAN_MAX_RSI_EXTREME = 30.0 # <= 30 is EXTREME FEAR
CONTRARIAN_MIN_ADV20_BILLION = 2.0
CONTRARIAN_MAX_POSITION_SIZE_PCT = 5.0
CONTRARIAN_STOP_LOSS_PCT = 0.08

# Gate Names
GATE_REGIME = "MARKET_REGIME"
GATE_EVENT_RISK = "GOVERNANCE_EVENT_RISK"
GATE_SURVIVAL = "SURVIVAL_QUALITY"
GATE_VALUATION = "VALUATION_MOS"
GATE_PANIC_SCORE = "PANIC_SCORE"
GATE_PRICE_CONFIRM = "PRICE_CONFIRMATION"
GATE_LIQUIDITY = "ADV20_LIQUIDITY"
GATE_DATA = "DATA_GATE"

# States
STATE_NORMAL = "NORMAL"
STATE_NEAR_PANIC_WATCH = "NEAR_PANIC_WATCH"
STATE_EXTREME_FEAR_WATCH = "EXTREME_FEAR_WATCH"
STATE_PANIC_BUY = "PANIC_BUY"
STATE_BLOCKED = "BLOCKED"

# Actions
ACTION_NO_SETUP = "KHÔNG CÓ SETUP (NORMAL)"
ACTION_WATCH_NEAR_PANIC = "👀 THEO DÕI (NEAR PANIC)"
ACTION_WATCH_EXTREME = "👀 CHỜ ĐÁY (EXTREME FEAR)"
ACTION_PANIC_BUY_STR = "🚨 BẮT ĐÁY PANIC BUY"
ACTION_BLOCKED = "❌ BỊ CHẶN (BLOCKED)"

STYLE_CONTRARIAN_PANIC_BUY = "🚨 [BẮT ĐÁY PANIC BUY]"
STYLE_WATCH_ZONE = "👀 [WATCH/ACCUMULATION ZONE]"

SECTOR_BANKING = "Ngân hàng"
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
        f_res = calculate_piotroski_f_score(fin)
        return int(f_res.get("f_score", 0))
    return int(f_score)


def _extract_z_score(fin: Dict[str, Any], sector: str) -> Optional[float]:
    z_score = fin.get("z_score")
    if z_score is None:
        z_res = calculate_altman_z_score(fin, sector=sector)
        z_val = z_res.get("z_score")
        return float(z_val) if z_val is not None else None
    return float(z_score)


def _check_fundamental_integrity(
    symbol: str,
    current_price: float,
    fin_dict: Optional[Dict[str, Any]],
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

    # 1. Sinh tồn
    f_score = _extract_f_score(fin_dict)
    result.metrics["f_score"] = f_score
    if f_score < CONTRARIAN_MIN_FSCORE:
        result.can_buy = False
        result.status = STATE_BLOCKED
        result.action_state = ACTION_BLOCKED
        result.blocked_by = GATE_SURVIVAL
        result.blocking_reasons.append(f"F-Score={f_score}/9 < {CONTRARIAN_MIN_FSCORE}.")
        return False

    is_bank = sector in (SECTOR_BANKING, "Bank", "Banking")
    if not is_bank:
        z_score = _extract_z_score(fin_dict, sector)
        result.metrics["z_score"] = z_score
        if z_score is not None and z_score <= CONTRARIAN_MIN_ZSCORE:
            result.can_buy = False
            result.status = STATE_BLOCKED
            result.action_state = ACTION_BLOCKED
            result.blocked_by = GATE_SURVIVAL
            result.blocking_reasons.append(f"Z-Score={z_score:.2f} <= {CONTRARIAN_MIN_ZSCORE}.")
            return False

        debt_equity = fin_dict.get("debt_equity") or fin_dict.get("debt_to_equity")
        if debt_equity is not None:
            de_val = float(debt_equity)
            result.metrics["debt_equity"] = de_val
            if de_val > CONTRARIAN_MAX_DEBT_EQUITY:
                result.can_buy = False
                result.status = STATE_BLOCKED
                result.action_state = ACTION_BLOCKED
                result.blocked_by = GATE_SURVIVAL
                result.blocking_reasons.append(f"D/E={de_val:.2f}x > {CONTRARIAN_MAX_DEBT_EQUITY:.1f}x.")
                return False

    # 2. Earnings Revision (Value Trap Check)
    margin_trend = fin_dict.get("margin_trend", "")
    if margin_trend == "down_2_quarters" or fin_dict.get("earnings_declining"):
        result.can_buy = False
        result.status = STATE_BLOCKED
        result.action_state = ACTION_BLOCKED
        result.blocked_by = GATE_SURVIVAL
        result.blocking_reasons.append("Lợi nhuận/Biên gộp đang lao dốc (Fundamental Damage). VALUE TRAP!")
        return False

    # 3. Valuation
    if "mos_pct" in fin_dict and "mos_is_informative" in fin_dict:
        val_res = {
            "mos_pct": float(fin_dict["mos_pct"]),
            "mos_is_informative": bool(fin_dict["mos_is_informative"]),
            "fair_value": float(fin_dict.get("fair_value", current_price * (1.0 + float(fin_dict["mos_pct"]) / 100.0))),
        }
    else:
        val_res = calculate_fair_value_and_mos(
            symbol=symbol, current_price=current_price, fin_dict=fin_dict, sector=sector
        )

    mos_pct = float(val_res.get("mos_pct", 0.0))
    mos_is_informative = bool(val_res.get("mos_is_informative", False))
    fair_value = float(val_res.get("fair_value", 0.0))

    result.mos_pct = mos_pct
    result.fair_value = fair_value
    result.metrics["mos_pct"] = mos_pct
    result.metrics["fair_value"] = fair_value
    result.metrics["mos_is_informative"] = mos_is_informative

    if not mos_is_informative:
        result.can_buy = False
        result.status = STATE_BLOCKED
        result.action_state = ACTION_BLOCKED
        result.blocked_by = GATE_VALUATION
        result.blocking_reasons.append("Thiếu dữ liệu định giá tin cậy (mos_is_informative=False).")
        return False

    if mos_pct < required_mos:
        result.can_buy = False
        result.status = STATE_BLOCKED
        result.action_state = ACTION_BLOCKED
        result.blocked_by = GATE_VALUATION
        result.blocking_reasons.append(f"MoS={mos_pct:+.1f}% < Yêu cầu {required_mos:.1f}%.")
        return False

    result.passed_gates.append(GATE_SURVIVAL)
    result.passed_gates.append(GATE_VALUATION)
    return True


def _calculate_panic_score(current_price: float, tech_data: Dict[str, Any]) -> float:
    rsi = float(tech_data.get("rsi14") or tech_data.get("rsi") or 50.0)
    ma20 = float(tech_data.get("ma20") or 0.0)
    
    rsi_score = 0.0
    if rsi <= 25.0:
        rsi_score = 70.0
    elif rsi <= 30.0:
        rsi_score = 50.0 + (30.0 - rsi) / 5.0 * 20.0
    elif rsi <= 35.0:
        rsi_score = 25.0 + (35.0 - rsi) / 5.0 * 25.0
    elif rsi <= 40.0:
        rsi_score = (40.0 - rsi) / 5.0 * 25.0
        
    dev_score = 0.0
    if ma20 > 0:
        pct_below = (1.0 - (current_price / ma20)) * 100.0
        if pct_below >= 20.0:
            dev_score = 30.0
        elif pct_below > 5.0:
            dev_score = (pct_below - 5.0) / 15.0 * 30.0
            
    return round(min(100.0, rsi_score + dev_score), 1)


def _evaluate_panic_state(current_price: float, tech_data: Dict[str, Any], result: ContrarianResult) -> bool:
    panic_score = _calculate_panic_score(current_price, tech_data)
    result.metrics["panic_score"] = panic_score
    rsi = float(tech_data.get("rsi14") or tech_data.get("rsi") or 50.0)
    
    if rsi > CONTRARIAN_MAX_RSI_WATCH:
        result.can_buy = False
        result.status = STATE_NORMAL
        result.action_state = ACTION_NO_SETUP
        result.blocked_by = GATE_PANIC_SCORE
        result.blocking_reasons.append("Chưa kích hoạt trạng thái hoảng loạn cực đoan.")
        return False
        
    result.passed_gates.append(GATE_PANIC_SCORE)
    
    trigger_txt = f"RSI={rsi:.1f} & Score={panic_score}/100"
    result.metrics["extreme_fear_trigger"] = trigger_txt
    
    if rsi <= CONTRARIAN_MAX_RSI_EXTREME:
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


def _check_price_confirmation(tech_data: Dict[str, Any], result: ContrarianResult) -> bool:
    has_reversal = tech_data.get("has_reversal_pattern", False)
    bullish_div = tech_data.get("bullish_divergence", False)
    price_confirmation = tech_data.get("price_confirmation", False)

    if not (has_reversal or bullish_div or price_confirmation):
        result.can_buy = False
        result.blocked_by = GATE_PRICE_CONFIRM
        result.blocking_reasons.append("Động lượng suy yếu cực độ nhưng chưa có xác nhận đảo chiều (Dao đang rơi).")
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
    base_size = min(CONTRARIAN_MAX_POSITION_SIZE_PCT, max(1.0, penalized_kelly))

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
) -> ContrarianResult:
    res = ContrarianResult(symbol=symbol.upper(), can_buy=False)

    if not symbol or current_price <= 0:
        res.status = STATE_BLOCKED
        res.action_state = ACTION_BLOCKED
        res.blocked_by = GATE_DATA
        res.blocking_reasons.append("Mã cổ phiếu hoặc thị giá không hợp lệ.")
        return res

    required_mos = _check_market_regime(macro_regime, res)

    if not _check_governance_and_event_risk(tech_data or {}, res):
        return res

    if not _check_fundamental_integrity(symbol, current_price, fin_dict, sector, required_mos, res):
        return res

    if not _evaluate_panic_state(current_price, tech_data or {}, res):
        return res
        
    if res.status == STATE_EXTREME_FEAR_WATCH:
        if _check_price_confirmation(tech_data or {}, res):
            if _check_liquidity_and_size(current_price, tech_data, half_kelly_f, kill_switch_active, res):
                res.status = STATE_PANIC_BUY
                res.can_buy = True
                res.action_state = ACTION_PANIC_BUY_STR
                res.style_type = STYLE_CONTRARIAN_PANIC_BUY
                trigger_txt = res.metrics.get("extreme_fear_trigger", "")
                res.setup_type = f"🚨 BẮT ĐÁY HOẢNG LOẠN ({trigger_txt}, MoS: {res.mos_pct:+.1f}%)"
                return res

    return res
