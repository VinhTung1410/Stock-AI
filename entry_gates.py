"""
Unified Entry Gate Engine (Phase 15 - v7.5).

Hệ thống Kiểm soát Cổng vào Lệnh 7 Tầng Thống nhất (Single Gatekeeper Architecture).
Áp dụng bình đẳng cho mọi luồng ra quyết định:
- WATCHLIST (Tín hiệu theo dõi danh mục)
- SCAN (Bộ quét cơ hội thị trường chủ động)
- TWO_PASS (Báo cáo Phân tích Lượng hóa 2-Pass)
- COMMITTEE (Hội đồng Đầu tư AI 5 Chuyên gia)

Nguyên tắc: Quant Rules Over LLM — Tuyệt đối không mở cổng MUA khi vi phạm định lượng.
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from data_gate import reconcile_data
from indicators import calculate_altman_z_score, calculate_piotroski_f_score
from quant_valuation import calculate_fair_value_and_mos, classify_stock_archetype

# Gate Names Constants (SonarCloud S1192)
GATE_MACRO_REGIME = "MACRO_REGIME"
GATE_DATA_GATE = "DATA_GATE"
GATE_FINANCIAL_HEALTH = "FINANCIAL_HEALTH"
GATE_VALUATION_MOS = "VALUATION_MOS"
GATE_TECHNICAL_MOMENTUM = "TECHNICAL_MOMENTUM"
GATE_QUANT_CONVICTION = "QUANT_CONVICTION"
GATE_PM_VETO = "PM_VETO"

# Action State Constants
ACTION_BUY = "🟢 MUA"
ACTION_ACCUMULATE = "🟢 ACCUMULATE"
ACTION_WATCH = "🟡 THEO DÕI"
ACTION_REDUCE = "🔴 GIẢM / THOÁT"

# Bullish Technical Signals Set
BULLISH_SET = {
    "BULLISH_CONFIRMED",
    "CONSOLIDATION_BASE",
    "BULLISH",
    "STRONG_BULLISH",
    "ACCUMULATION",
}

# Archetype MoS Minimum Thresholds (%)
ARCHETYPE_MOS_THRESHOLDS: Dict[str, float] = {
    "BANK": 10.0,
    "GROWTH_COMPOUNDER": 15.0,
    "GROWTH": 15.0,
    "CYCLICAL": 15.0,
    "REAL_ESTATE": 15.0,
    "DEFAULT": 15.0,
}


@dataclass
class EntryGateResult:
    """Kết quả kiểm định Cổng vào lệnh 7 tầng."""

    can_buy: bool
    blocked_by: Optional[str] = None
    blocking_reasons: List[str] = field(default_factory=list)
    passed_gates: List[str] = field(default_factory=list)
    metrics: Dict[str, Any] = field(default_factory=dict)
    position_size_multiplier: float = 1.0
    action_state: str = ACTION_WATCH


def _check_macro_regime_layer(macro_regime: Optional[str], result: EntryGateResult) -> bool:
    """Tầng 0: Kiểm tra Macro Regime (MA200 Hysteresis).

    Block nếu DOWNTREND. Kích hoạt Fail-safe nếu thiếu dữ liệu vĩ mô (giảm 50% size).
    """
    if not macro_regime or macro_regime.upper() in ("UNKNOWN", "ERROR", "N/A", "NONE"):
        result.blocking_reasons.append(
            "[MACRO_FAILSAFE] Dữ liệu VN-Index không khả dụng hoặc thiếu. Kích hoạt chế độ phòng thủ: giảm 50% quy mô vị thế."
        )
        result.position_size_multiplier = 0.5
        result.passed_gates.append(GATE_MACRO_REGIME)
        return True

    reg_up = macro_regime.upper().strip()
    if "DOWNTREND" in reg_up:
        result.can_buy = False
        result.blocked_by = GATE_MACRO_REGIME
        result.position_size_multiplier = 0.0
        result.blocking_reasons.append(
            f"Thị trường chung VN-Index đang trong xu hướng DOWNTREND ({macro_regime}). Cấm mở vị thế Mua mới."
        )
        return False

    result.passed_gates.append(GATE_MACRO_REGIME)
    return True


def _check_data_gate_layer(
    symbol: str, tech_data: Optional[Dict[str, Any]], fin_dict: Optional[Dict[str, Any]], result: EntryGateResult
) -> bool:
    """Tầng 1: Kiểm định tính toàn vẹn và độ tươi dữ liệu (Data Gate)."""
    try:
        recon = reconcile_data(symbol=symbol, tech_data=tech_data, fin_data=fin_dict)
    except Exception:
        logging.exception("Lỗi khi chạy reconcile_data cho %s", symbol)
        recon = {"gate_passed": False, "recommendation_allowed": False, "quality_score": 0.0}

    q_score = recon.get("quality_score", 0.0)
    rec_allowed = recon.get("recommendation_allowed", False)
    gate_passed = recon.get("gate_passed", False)
    is_stale = recon.get("is_stale", False)

    result.metrics["data_quality_score"] = q_score
    result.metrics["data_quality_tier"] = recon.get("data_quality", "UNKNOWN")

    if not gate_passed or not rec_allowed or q_score < 65.0 or is_stale:
        result.can_buy = False
        result.blocked_by = GATE_DATA_GATE
        result.position_size_multiplier = 0.0
        issues = recon.get("conflicting_data", []) + recon.get("stale_data", [])
        issue_msg = "; ".join(issues) if issues else f"Chất lượng dữ liệu không đạt (Score={q_score:.1f}/100)"
        result.blocking_reasons.append(f"Data Gate từ chối: {issue_msg}")
        return False

    result.passed_gates.append(GATE_DATA_GATE)
    return True


def _check_financial_health_layer(
    fin_dict: Optional[Dict[str, Any]], sector: str, result: EntryGateResult
) -> bool:
    """Tầng 2: Sức khỏe tài chính Piotroski F-Score và Altman Z-Score."""
    fin = fin_dict or {}

    # Ưu tiên lấy f_score có sẵn trong fin_dict nếu hợp lệ
    f_score = fin.get("f_score")
    if f_score is None:
        f_res = calculate_piotroski_f_score(fin, sector=sector)
        f_score = f_res.get("score", 6)
    else:
        f_score = int(f_score)
    result.metrics["f_score"] = f_score

    if f_score <= 3:
        result.can_buy = False
        result.blocked_by = GATE_FINANCIAL_HEALTH
        result.position_size_multiplier = 0.0
        result.blocking_reasons.append(f"Sức khỏe tài chính yếu: Piotroski F-Score={f_score}/9 <= 3.")
        return False

    z_score = fin.get("z_score")
    if z_score is None:
        z_res = calculate_altman_z_score(fin, sector=sector)
        z_score = z_res.get("z_score")
    else:
        z_score = float(z_score)
    result.metrics["z_score"] = z_score

    if sector not in ("Ngân hàng", "Bất động sản") and z_score is not None and z_score < 1.23:
        result.can_buy = False
        result.blocked_by = GATE_FINANCIAL_HEALTH
        result.position_size_multiplier = 0.0
        result.blocking_reasons.append(f"Rủi ro kiệt quệ tài chính cao: Altman Z-Score={z_score:.2f} < 1.23 (Vùng đỏ).")
        return False

    result.passed_gates.append(GATE_FINANCIAL_HEALTH)
    return True


def _check_valuation_mos_layer(
    symbol: str,
    current_price: float,
    fin_dict: Optional[Dict[str, Any]],
    sector: str,
    archetype: str,
    caller: str,
    result: EntryGateResult,
) -> bool:
    """Tầng 3: Định giá nội tại và Biên an toàn MoS."""
    arch = archetype
    if not arch or arch == "UNKNOWN":
        arch = classify_stock_archetype(symbol, sector)
        # TASK-0049: 2-Pass caller không cho phép fallback GROWTH khi sector rỗng/unknown
        if (
            caller == "TWO_PASS"
            and arch == "GROWTH_COMPOUNDER"
            and not sector
            and symbol not in ("FPT", "MWG", "PNJ", "VNM")
        ):
            arch = "UNKNOWN"

    if arch == "UNKNOWN":
        result.can_buy = False
        result.blocked_by = GATE_VALUATION_MOS
        result.position_size_multiplier = 0.0
        result.blocking_reasons.append("Không xác định được ngành nghề / Archetype định giá hợp lệ. Chặn mở vị thế.")
        return False

    if fin_dict and "mos_pct" in fin_dict and "mos_is_informative" in fin_dict:
        val_res = {
            "mos_pct": float(fin_dict["mos_pct"]),
            "mos_is_informative": bool(fin_dict["mos_is_informative"]),
            "fair_value": float(fin_dict.get("fair_value", current_price * (1.0 + float(fin_dict["mos_pct"]) / 100.0))),
            "valuation_method": str(fin_dict.get("valuation_method", "PROVIDED")),
        }
    else:
        val_res = calculate_fair_value_and_mos(
            symbol=symbol, current_price=current_price, fin_dict=fin_dict, sector=sector
        )
    mos_pct = float(val_res.get("mos_pct", 0.0))
    mos_is_informative = bool(val_res.get("mos_is_informative", False))
    fair_value = float(val_res.get("fair_value", 0.0))

    result.metrics["mos_pct"] = mos_pct
    result.metrics["fair_value"] = fair_value
    result.metrics["mos_is_informative"] = mos_is_informative
    result.metrics["valuation_method"] = val_res.get("valuation_method", "N/A")

    min_mos = ARCHETYPE_MOS_THRESHOLDS.get(arch, ARCHETYPE_MOS_THRESHOLDS["DEFAULT"])

    if not mos_is_informative:
        result.can_buy = False
        result.blocked_by = GATE_VALUATION_MOS
        result.position_size_multiplier = 0.0
        result.blocking_reasons.append(
            f"Định giá không thực chất (mos_is_informative=False) hoặc thiếu BCTC cho archetype {arch}."
        )
        return False

    if mos_pct < min_mos:
        result.can_buy = False
        result.blocked_by = GATE_VALUATION_MOS
        result.position_size_multiplier = 0.0
        result.blocking_reasons.append(
            f"Biên an toàn MoS={mos_pct:+.1f}% không đạt ngưỡng tối thiểu {min_mos:.1f}% của archetype {arch}."
        )
        return False

    result.passed_gates.append(GATE_VALUATION_MOS)
    return True


def _check_technical_momentum_layer(
    tech_data: Optional[Dict[str, Any]], current_price: float, result: EntryGateResult
) -> bool:
    """Tầng 4: Xu hướng Kỹ thuật và Động lượng (chặn bắt dao rơi)."""
    tech = tech_data or {}
    tech_sig = tech.get("tech_signal")

    if not tech_sig:
        ma20 = tech.get("ma20", current_price)
        ma50 = tech.get("ma50", current_price)
        rsi = tech.get("rsi", tech.get("rsi14", 50.0))
        if current_price < ma20 * 0.95 and rsi < 36.0:
            tech_sig = "FALLING_KNIFE"
        elif current_price < ma20 * 0.97 or current_price < ma50 * 0.98:
            tech_sig = "WEAK_BELOW_MA20"
        elif current_price >= ma20 and rsi >= 48.0:
            tech_sig = "BULLISH_CONFIRMED"
        else:
            tech_sig = "CONSOLIDATION_BASE"

    result.metrics["tech_signal"] = tech_sig

    if tech_sig not in BULLISH_SET:
        result.can_buy = False
        result.blocked_by = GATE_TECHNICAL_MOMENTUM
        result.position_size_multiplier = 0.0
        result.blocking_reasons.append(
            f"Tín hiệu kỹ thuật {tech_sig} không thuộc BULLISH_SET. Chặn mở vị thế khi cổ phiếu yếu/dưới MA20/MA50."
        )
        return False

    result.passed_gates.append(GATE_TECHNICAL_MOMENTUM)
    return True


def _check_quant_conviction_layer(conviction_score: Optional[float], result: EntryGateResult) -> bool:
    """Tầng 5: Điểm Conviction tổng hợp (>= 60)."""
    if conviction_score is not None:
        result.metrics["conviction_score"] = conviction_score
        if conviction_score < 60.0:
            result.can_buy = False
            result.blocked_by = GATE_QUANT_CONVICTION
            result.position_size_multiplier = 0.0
            result.blocking_reasons.append(
                f"Điểm Conviction {conviction_score:.1f}/100 < 60.0 (Dưới ngưỡng an toàn định lượng)."
            )
            return False

    result.passed_gates.append(GATE_QUANT_CONVICTION)
    return True


def _check_pm_veto_layer(pm_veto: bool, pm_output: Optional[str], result: EntryGateResult) -> bool:
    """Tầng 6: PM Veto / Portfolio Risk Arbitrator."""
    has_veto = pm_veto
    if not has_veto and pm_output:
        has_veto = any(v in pm_output.upper() for v in ("VETO", "PHỦ QUYẾT", "REJECT_BUY", "VETO_OVERRIDE"))

    if has_veto:
        result.can_buy = False
        result.blocked_by = GATE_PM_VETO
        result.position_size_multiplier = 0.0
        result.blocking_reasons.append("PM Veto kích hoạt: Phát hiện rủi ro phi định lượng hoặc xung đột danh mục.")
        return False

    result.passed_gates.append(GATE_PM_VETO)
    return True


def evaluate_entry_gates(
    symbol: str,
    current_price: float,
    fin_dict: Optional[Dict[str, Any]] = None,
    tech_data: Optional[Dict[str, Any]] = None,
    sector: str = "",
    archetype: str = "",
    macro_regime: Optional[str] = None,
    caller: str = "UNKNOWN",
    conviction_score: Optional[float] = None,
    pm_veto: bool = False,
    pm_output: Optional[str] = None,
    **kwargs,
) -> EntryGateResult:
    """Thực thi kiểm định Cổng vào lệnh 7 tầng (Unified Entry Gate).

    Tuần tự:
    - Tầng 0: Macro Regime (MA200 Hysteresis)
    - Tầng 1: Data Gate (Freshness + BCTC + Survival Gate)
    - Tầng 2: Sức khỏe tài chính (F-Score + Z-Score)
    - Tầng 3: Định giá nội tại & MoS
    - Tầng 4: Xu hướng Kỹ thuật & Momentum
    - Tầng 5: Quant Conviction
    - Tầng 6: PM Veto / Governance
    """
    sym = (symbol or "").strip().upper()
    result = EntryGateResult(
        can_buy=True,
        metrics={
            "symbol": sym,
            "current_price": current_price,
            "caller": caller,
            "sector": sector,
        },
    )

    if current_price <= 0.0:
        result.can_buy = False
        result.blocked_by = GATE_DATA_GATE
        result.position_size_multiplier = 0.0
        result.blocking_reasons.append(f"Thị giá không hợp lệ ({current_price}k <= 0).")
        return result

    # 0. Tầng Macro
    if not _check_macro_regime_layer(macro_regime, result):
        return result

    # 1. Tầng Data Gate
    if not _check_data_gate_layer(sym, tech_data, fin_dict, result):
        return result

    # 2. Tầng Sức khỏe tài chính
    if not _check_financial_health_layer(fin_dict, sector, result):
        return result

    # 3. Tầng MoS & Định giá
    if not _check_valuation_mos_layer(sym, current_price, fin_dict, sector, archetype, caller, result):
        return result

    # 4. Tầng Kỹ thuật
    if not _check_technical_momentum_layer(tech_data, current_price, result):
        return result

    # 5. Tầng Conviction
    if not _check_quant_conviction_layer(conviction_score, result):
        return result

    # 6. Tầng PM Veto
    if not _check_pm_veto_layer(pm_veto, pm_output, result):
        return result

    # Đạt chuẩn toàn bộ 7 tầng
    tech_sig = result.metrics.get("tech_signal", "")
    result.action_state = ACTION_ACCUMULATE if tech_sig == "CONSOLIDATION_BASE" else ACTION_BUY
    return result
