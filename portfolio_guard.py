"""Portfolio risk constraints, sizing, and concentration guards."""

import logging
from typing import Any, Dict, List

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
from indicators import calculate_altman_z_score, calculate_piotroski_f_score

MAX_POSITIONS_PER_SECTOR: int = 3


def _evaluate_profitable_holding(
    symbol: str,
    entry_price: float,
    curr_price: float,
    volume: int,
    pl_pct: float,
    pl_val: float,
    atr: float,
    ma20: float,
) -> dict:
    max_allowed_stop = round(curr_price * 0.96, 2)
    if pl_pct >= 15.0:
        candidate_stop = max(
            entry_price * 1.06, (curr_price - (1.2 * atr)) if atr > 0 else (curr_price * 0.95), ma20 * 0.98
        )
    elif pl_pct >= 5.0:
        candidate_stop = max(entry_price * 1.02, (curr_price - (1.5 * atr)) if atr > 0 else (curr_price * 0.94))
    else:
        candidate_stop = entry_price

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
            f"Vị thế có lãi nhẹ (+{pl_pct:.1f}%). Tiếp tục nắm giữ, đặt mốc chặn lãi hòa vốn tại {trailing_stop:.2f}k."
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
        "thesis_breaker": "N/A (Vị thế đang thắng thế, không có rủi ro vỡ luận điểm)",
    }


def _evaluate_losing_holding(
    symbol: str,
    entry_price: float,
    curr_price: float,
    volume: int,
    pl_pct: float,
    pl_val: float,
    atr: float,
    fin_dict: dict | None,
    sector: str,
) -> dict:
    loss_pct = abs(pl_pct)
    if atr and atr > 0:
        tech_stop = curr_price - (2.0 * atr)
        stop_loss = max(tech_stop, entry_price * 0.93)
    else:
        stop_loss = entry_price * 0.93

    stop_loss = min(round(float(stop_loss), 2), round(curr_price * 0.97, 2))

    thesis_intact = True
    thesis_msg = "Luận điểm tăng trưởng doanh nghiệp cốt lõi vẫn được bảo toàn."

    if fin_dict:
        f_score = calculate_piotroski_f_score(fin_dict, sector).get("score", 6)
        z_data = calculate_altman_z_score(fin_dict, sector)
        if f_score < 4 or "ĐỎ" in z_data.get("zone", ""):
            thesis_intact = False
            thesis_msg = "CẢNH BÁO: BCTC suy giảm nghiêm trọng hoặc đòn bẩy quá cao (Thesis Breaker bị kích hoạt!)."

    if not thesis_intact:
        action = "🔴 THOÁT VỊ THẾ (THESIS BREAKER KÍCH HOẠT)"
        detail = f"Lỗ -{loss_pct:.1f}%. {thesis_msg} Cần dứt khoát cơ cấu thoát vốn sang mã có cơ bản vượt trội."
    elif loss_pct <= 5.0:
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
        "thesis_breaker": thesis_msg,
    }


def evaluate_holding_position(row: dict, tech_data: dict, fin_dict: dict | None = None, sector: str = "") -> dict:
    """Evaluate an existing portfolio position and recommend action."""
    symbol = str(row.get("symbol") or row.get("Mã CP", "")).strip().upper()
    entry_price = float(
        row.get("avg_price")
        or row.get("Giá TB (k)")
        or row.get("Giá vốn (k)")
        or 0.0
    )
    curr_price = float(
        tech_data.get("current_price")
        or row.get("market_price")
        or row.get("Giá hiện tại (k)")
        or row.get("Thị giá (k)")
        or entry_price
    )
    volume = int(row.get("volume") or row.get("Khối lượng") or 0)

    pl_val = (curr_price - entry_price) * volume * 1000
    pl_pct = ((curr_price - entry_price) / entry_price * 100) if entry_price > 0 else 0.0

    atr = float(tech_data.get("atr") or tech_data.get("atr14") or 0.0)
    ma20 = float(tech_data.get("ma20") or curr_price)

    if pl_pct > 0:
        return _evaluate_profitable_holding(symbol, entry_price, curr_price, volume, pl_pct, pl_val, atr, ma20)
    return _evaluate_losing_holding(symbol, entry_price, curr_price, volume, pl_pct, pl_val, atr, fin_dict, sector)


def check_portfolio_concentration(candidates: List[Dict[str, Any]], max_per_sector: int = 1) -> Dict[str, Any]:
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

    return {"approved_candidates": approved, "downgraded_candidates": downgraded, "warnings": warnings}


def calculate_drawdown_controlled_sizing(
    half_kelly_f: float,
    consecutive_losses: int = 0,
    current_drawdown_pct: float = 0.0,
    max_cap_pct: float = 0.15,
    regime_hysteresis_penalty: bool = False,
) -> tuple[float, str]:
    """Calculate adaptive position size based on Half-Kelly, losing streaks, and drawdown.

    Rules:
    - If current_drawdown_pct >= 10.0%:
      Hard Drawdown Breaker! Return 0 (Cash Mode) to protect portfolio.
    - If regime_hysteresis_penalty is True (Regime Conflict >= 2 days):
      Reduce position size by 50% (Hysteresis Defense).
    - If consecutive_losses >= 2 or current_drawdown_pct >= 5.0%:
      Reduce position size by 50% (Half-Size Defense) to prevent revenge trading.
    - Caps position sizing at max_cap_pct (default: 15%).
    """
    if half_kelly_f <= 0:
        return 0.0, "KELLY_NON_POSITIVE"

    if current_drawdown_pct >= 10.0:
        return 0.0, "DRAWDOWN_BREAKER_TRIGGERED"

    base_size = min(half_kelly_f, max_cap_pct)

    if regime_hysteresis_penalty:
        base_size = round(base_size * 0.5, 4)

    if consecutive_losses >= 2 or current_drawdown_pct >= 5.0:
        defensive_size = round(base_size * 0.5, 4)
        return defensive_size, "DRAWDOWN_DEFENSE_HALF_SIZE"

    if regime_hysteresis_penalty:
        return base_size, "REGIME_CONFLICT_HALF_SIZE"

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


def _redistribute_uncapped_weights(
    remaining_keys: set[str],
    fixed_weights: dict[str, float],
    inv_vols: dict[str, float],
    weights: dict[str, float],
) -> None:
    rem_weight_budget = 1.0 - sum(fixed_weights.values())
    rem_inv_sum = sum(inv_vols[k] for k in remaining_keys)
    if rem_inv_sum > 0:
        for k in remaining_keys:
            weights[k] = rem_weight_budget * (inv_vols[k] / rem_inv_sum)
    else:
        eq_share = rem_weight_budget / len(remaining_keys)
        for k in remaining_keys:
            weights[k] = eq_share


def _cap_and_redistribute_weights(
    clean_vols: dict[str, float],
    inv_vols: dict[str, float],
    weights: dict[str, float],
    effective_cap: float,
) -> dict[str, float]:
    fixed_weights: dict[str, float] = {}
    remaining_keys = set(clean_vols.keys())

    for _ in range(len(clean_vols)):
        exceeded = [k for k in remaining_keys if weights[k] > effective_cap + 1e-6]
        if not exceeded:
            break
        for k in exceeded:
            fixed_weights[k] = effective_cap
            remaining_keys.remove(k)

        if not remaining_keys:
            break

        _redistribute_uncapped_weights(remaining_keys, fixed_weights, inv_vols, weights)

    for k, fw in fixed_weights.items():
        weights[k] = fw
    return weights


def optimize_portfolio_risk_parity(
    volatilities: dict[str, float],
    max_weight: float = 0.25,
) -> dict[str, float]:
    """Phân bổ tỷ trọng đóng góp rủi ro ngang bằng theo nghịch đảo biến động (Phase 5b).

    Bảo đảm cổ phiếu rủi ro cao không chi phối toàn bộ danh mục, áp dụng trần max_weight.
    """
    if not volatilities:
        return {}

    clean_vols = {k: max(float(v), 0.001) for k, v in volatilities.items() if float(v) >= 0}
    if not clean_vols:
        return {}

    effective_cap = max(max_weight, 1.0 / len(clean_vols))
    inv_vols = {k: 1.0 / v for k, v in clean_vols.items()}
    sum_inv = sum(inv_vols.values())
    weights = {k: v / sum_inv for k, v in inv_vols.items()}

    weights = _cap_and_redistribute_weights(clean_vols, inv_vols, weights, effective_cap)

    # Final normalization & hard cap verification
    tot = sum(weights.values())
    if tot > 0:
        weights = {k: min(w / tot, effective_cap) for k, w in weights.items()}

    tot2 = sum(weights.values())
    return {k: round(w / tot2, 4) for k, w in weights.items()}


def evaluate_partial_profit_lock(
    entry_price: float,
    current_high: float,
    current_price: float,
    target_profit_pct: float = 12.0,
) -> dict[str, Any]:
    """Đánh giá chiến lược Chốt lời từng phần và dời stop lên break-even (Phase 5d)."""
    if entry_price <= 0:
        return {
            "partial_take_profit": False,
            "lock_fraction": 0.0,
            "new_stop_price": None,
            "status": "INVALID_ENTRY_PRICE",
        }

    max_gain_pct = ((current_high - entry_price) / entry_price) * 100.0
    current_pnl_pct = ((current_price - entry_price) / entry_price) * 100.0

    if max_gain_pct >= target_profit_pct:
        return {
            "partial_take_profit": True,
            "lock_fraction": 0.50,
            "new_stop_price": round(entry_price, 2),
            "max_gain_pct": round(max_gain_pct, 2),
            "current_pnl_pct": round(current_pnl_pct, 2),
            "status": "TARGET_1_REACHED_BREAKEVEN_LOCKED",
        }

    return {
        "partial_take_profit": False,
        "lock_fraction": 0.0,
        "new_stop_price": None,
        "max_gain_pct": round(max_gain_pct, 2),
        "current_pnl_pct": round(current_pnl_pct, 2),
        "status": "TRAIL_IN_PROGRESS",
    }
