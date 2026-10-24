"""Portfolio risk constraints, sizing, and concentration guards."""

import logging
from typing import Any, Dict, List

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
from indicators import calculate_altman_z_score, calculate_vibe_quality_score
from policy_constants import (
    ACTION_EXIT_OVERVALUED,
    ACTION_EXIT_THESIS,
    ACTION_PARTIAL_PROFIT,
    ACTION_STOP_LOSS,
    ATR_STOP_MULTIPLIER,
    DRAWDOWN_BREAKER_PCT,
    DRAWDOWN_HALF_SIZE_PCT,
    FIXED_RISK_NAV_PCT,
    HARD_STOP_LOSS_PCT,
    MAX_FIXED_RISK_NAV_PCT,
    MAX_POSITION_SIZE_NAV_PCT,
    MAX_POSITIONS_PER_SECTOR,
    MIN_TRADES_FOR_KELLY_CALIBRATION,
    OVERVALUED_MOS_THRESHOLD,
    PARTIAL_TAKE_PROFIT_PCT,
    PROFIT_TRAIL_THRESHOLD_PCT,
    STRUCTURAL_STOP_LOSS_PCT,
    WARNING_LOSS_PCT,
)


def evaluate_sell_thesis(
    symbol: str,
    entry_price: float,
    curr_price: float,
    volume: int,
    pl_pct: float,
    pl_val: float,
    atr: float,
    ma20: float,
    fin_dict: dict | None,
    sector: str,
) -> dict:
    """Đánh giá vị thế (SELL/HOLD) theo thứ tự: Thesis -> Valuation -> Trend.
    Lợi nhuận (P/L) chỉ là tham số phụ.
    """
    is_profit = pl_pct > 0
    thesis_intact = True
    thesis_msg = "Luận điểm đầu tư vẫn nguyên vẹn."
    
    # 1. THESIS CHECK (Z-Score & F-Score)
    if fin_dict:
        f_score = calculate_vibe_quality_score(fin_dict, sector).get("score", 6)
        z_data = calculate_altman_z_score(fin_dict, sector)
        if f_score < 4 or "ĐỎ" in z_data.get("zone", ""):
            thesis_intact = False
            thesis_msg = "THESIS BREAKER KÍCH HOẠT: BCTC suy thoái nặng hoặc Đòn bẩy rủi ro cao (Z-Score Đỏ / F-Score < 4)."
    
    if not thesis_intact:
        return {
            "symbol": symbol,
            "status": "PROFITABLE" if is_profit else "LOSS",
            "sell_status": "THESIS_BROKEN",
            "entry_price": entry_price,
            "curr_price": curr_price,
            "pl_pct": round(pl_pct, 2),
            "pl_val": round(pl_val, 0),
            "action": ACTION_EXIT_THESIS,
            "detail": f"Bất chấp đang lãi hay lỗ ({pl_pct:.1f}%), luận điểm tài chính đã vỡ. {thesis_msg} Yêu cầu Exit.",
            "trailing_stop": curr_price,
            "stop_loss": curr_price,
            "is_profit": is_profit,
            "thesis_breaker": thesis_msg,
        }

    # 2. VALUATION CHECK (MoS)
    mos = 0.0
    if fin_dict and "fair_value" in fin_dict:
        fv = fin_dict["fair_value"]
        if fv > 0:
            mos = ((fv - curr_price) / fv) * 100.0
            if mos < OVERVALUED_MOS_THRESHOLD:
                return {
                    "symbol": symbol,
                    "status": "PROFITABLE" if is_profit else "LOSS",
                    "sell_status": "OVERVALUED",
                    "entry_price": entry_price,
                    "curr_price": curr_price,
                    "pl_pct": round(pl_pct, 2),
                    "pl_val": round(pl_val, 0),
                    "action": ACTION_EXIT_OVERVALUED,
                    "detail": f"Thị giá ({curr_price}) đã vượt Giá trị thực ({fv}). Định giá bong bóng. Bán thu tiền về.",
                    "trailing_stop": curr_price,
                    "stop_loss": curr_price,
                    "is_profit": is_profit,
                    "thesis_breaker": "Định giá quá đắt (MoS âm).",
                }

    # 3. TREND & RISK MANAGEMENT CHECK (Technical)
    # Lỗ kỹ thuật
    tech_stop = entry_price * (1.0 - (STRUCTURAL_STOP_LOSS_PCT / 100.0))  # Mặc định Stop-loss 7% cấu trúc
    if atr and atr > 0:
        tech_stop = max(tech_stop, curr_price - (ATR_STOP_MULTIPLIER * atr))
        
    tech_stop = round(float(tech_stop), 2)
    
    # Calculate progressive trailing stop for profitable positions
    profit_trailing_stop = entry_price
    if is_profit:
        max_allowed_stop = round(curr_price * 0.96, 2)
        if pl_pct >= 15.0:
            candidate_stop = max(entry_price * 1.06, (curr_price - (1.2 * atr)) if atr > 0 else (curr_price * 0.95), ma20 * 0.98)
        elif pl_pct >= WARNING_LOSS_PCT:
            candidate_stop = max(entry_price * 1.02, (curr_price - (1.5 * atr)) if atr > 0 else (curr_price * 0.94))
        else:
            candidate_stop = entry_price
        
        profit_trailing_stop = min(candidate_stop, max_allowed_stop)
        profit_trailing_stop = round(float(profit_trailing_stop), 2)

    
    if not is_profit:
        if pl_pct <= -HARD_STOP_LOSS_PCT or curr_price <= tech_stop:
            return {
                "symbol": symbol,
                "status": "LOSS",
                "sell_status": "STOP_LOSS",
                "entry_price": entry_price,
                "curr_price": curr_price,
                "pl_pct": round(pl_pct, 2),
                "pl_val": round(pl_val, 0),
                "action": ACTION_STOP_LOSS,
                "detail": f"Lỗ sâu ({pl_pct:.1f}%). Thủng ngưỡng phòng thủ ({tech_stop}). Phải hạ tỷ trọng/Cắt lỗ.",
                "trailing_stop": tech_stop,
                "stop_loss": tech_stop,
                "is_profit": False,
                "thesis_breaker": "N/A",
            }
        elif pl_pct <= -WARNING_LOSS_PCT:
            return {
                "symbol": symbol,
                "status": "LOSS",
                "sell_status": "RISK_MANAGEMENT",
                "entry_price": entry_price,
                "curr_price": curr_price,
                "pl_pct": round(pl_pct, 2),
                "pl_val": round(pl_val, 0),
                "action": "🟠 QUẢN TRỊ RỦI RO (CẢNH BÁO LỖ VỪA)",
                "detail": f"Lỗ vừa ({pl_pct:.1f}%). Cần theo dõi sát ngưỡng hỗ trợ.",
                "trailing_stop": tech_stop,
                "stop_loss": tech_stop,
                "is_profit": False,
                "thesis_breaker": "N/A",
            }
        else:
            return {
                "symbol": symbol,
                "status": "LOSS",
                "sell_status": "HOLD",
                "entry_price": entry_price,
                "curr_price": curr_price,
                "pl_pct": round(pl_pct, 2),
                "pl_val": round(pl_val, 0),
                "action": "🟡 THEO DÕI BIẾN ĐỘNG (THESIS INTACT)",
                "detail": f"Biến động nhẹ ({pl_pct:.1f}%). Luận điểm tài chính nguyên vẹn, tiếp tục theo dõi.",
                "trailing_stop": tech_stop,
                "stop_loss": tech_stop,
                "is_profit": False,
                "thesis_breaker": "N/A",
            }
        
    # Lãi kỹ thuật (Bảo vệ thành quả)
    if is_profit and pl_pct >= PARTIAL_TAKE_PROFIT_PCT:
        return {
            "symbol": symbol,
            "status": "PROFITABLE",
            "sell_status": "TAKE_PROFIT_PARTIAL",
            "entry_price": entry_price,
            "curr_price": curr_price,
            "pl_pct": round(pl_pct, 2),
            "pl_val": round(pl_val, 0),
            "action": ACTION_PARTIAL_PROFIT,
            "detail": f"Đang lãi lớn (+{pl_pct:.1f}%). Trend khỏe, Định giá (MoS {mos:.1f}%) & Luận điểm nguyên vẹn. Khuyến nghị chốt 30-50% bảo vệ thành quả.",
            "trailing_stop": profit_trailing_stop,
            "stop_loss": profit_trailing_stop,
            "is_profit": True,
            "thesis_breaker": "N/A",
        }

    if is_profit and pl_pct < PROFIT_TRAIL_THRESHOLD_PCT:
        return {
            "symbol": symbol,
            "status": "PROFITABLE",
            "sell_status": "HOLD",
            "entry_price": entry_price,
            "curr_price": curr_price,
            "pl_pct": round(pl_pct, 2),
            "pl_val": round(pl_val, 0),
            "action": "🟡 THEO DÕI ĐÀ TĂNG (THESIS INTACT)",
            "detail": f"Lãi nhẹ (+{pl_pct:.1f}%). Xu hướng đang hình thành, tiếp tục nắm giữ.",
            "trailing_stop": profit_trailing_stop,
            "stop_loss": profit_trailing_stop,
            "is_profit": True,
            "thesis_breaker": "N/A",
        }

    # HOLD
    return {
        "symbol": symbol,
        "status": "PROFITABLE" if is_profit else "LOSS",
        "sell_status": "HOLD",
        "entry_price": entry_price,
        "curr_price": curr_price,
        "pl_pct": round(pl_pct, 2),
        "pl_val": round(pl_val, 0),
        "action": "🟡 TIẾP TỤC NẮM GIỮ (THESIS INTACT)",
        "detail": f"P/L ({pl_pct:.1f}%). Luận điểm tài chính và Xu hướng vẫn nguyên vẹn. Tiếp tục nắm giữ.",
        "trailing_stop": tech_stop if not is_profit else profit_trailing_stop,
        "stop_loss": tech_stop if not is_profit else profit_trailing_stop,
        "is_profit": is_profit,
        "thesis_breaker": "N/A",
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

    return evaluate_sell_thesis(
        symbol=symbol,
        entry_price=entry_price,
        curr_price=curr_price,
        volume=volume,
        pl_pct=pl_pct,
        pl_val=pl_val,
        atr=atr,
        ma20=ma20,
        fin_dict=fin_dict,
        sector=sector,
    )


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


def calculate_fixed_risk_position_size(
    entry_price: float,
    stop_loss_price: float,
    nav_risk_pct: float = FIXED_RISK_NAV_PCT,
    max_cap_pct: float = MAX_POSITION_SIZE_NAV_PCT,
) -> float:
    """Fixed Risk Sizing (TASK-0077):
    Calculate position size as a fraction of NAV bounded by [0, max_cap_pct].
    Formula: min(nav_risk_pct / risk_on_trade, max_cap_pct)
    where risk_on_trade = (entry_price - stop_loss_price) / entry_price.
    """
    if entry_price <= 0.0:
        return 0.0

    if stop_loss_price <= 0.0 or stop_loss_price >= entry_price:
        risk_pct = STRUCTURAL_STOP_LOSS_PCT / 100.0
    else:
        risk_pct = (entry_price - stop_loss_price) / entry_price

    if risk_pct <= 0.0:
        return 0.0

    bounded_nav_risk = min(max(nav_risk_pct, 0.005), MAX_FIXED_RISK_NAV_PCT)
    raw_size = bounded_nav_risk / risk_pct
    return round(min(raw_size, max_cap_pct), 4)


def calculate_drawdown_controlled_sizing(
    half_kelly_f: float,
    consecutive_losses: int = 0,
    current_drawdown_pct: float = 0.0,
    max_cap_pct: float = MAX_POSITION_SIZE_NAV_PCT,
    regime_hysteresis_penalty: bool = False,
    total_calibrated_trades: int = 0,
    is_calibrated: bool = False,
    entry_price: float = 0.0,
    stop_loss_price: float = 0.0,
) -> tuple[float, str]:
    """Calculate adaptive position size based on Fixed Risk Sizing or calibrated Half-Kelly.

    Rules:
    - If current_drawdown_pct >= DRAWDOWN_BREAKER_PCT (10.0%):
      Hard Drawdown Breaker! Return 0 (Cash Mode) to protect portfolio.
    - If total_calibrated_trades > 0 and (total_calibrated_trades <= MIN_TRADES_FOR_KELLY_CALIBRATION or not is_calibrated):
      Chuyển sang Fixed Risk Sizing (1.0% - 1.5% NAV tại Stop-loss cấu trúc).
    - If regime_hysteresis_penalty is True (Regime Conflict >= 2 days):
      Reduce position size by 50% (Hysteresis Defense).
    - If consecutive_losses >= 2 or current_drawdown_pct >= DRAWDOWN_HALF_SIZE_PCT (5.0%):
      Reduce position size by 50% (Half-Size Defense) to prevent revenge trading.
    - Caps position sizing at max_cap_pct (default: 15%).
    """
    if current_drawdown_pct >= DRAWDOWN_BREAKER_PCT:
        return 0.0, "DRAWDOWN_BREAKER_TRIGGERED"

    use_fixed_risk = total_calibrated_trades > 0 and (
        total_calibrated_trades <= MIN_TRADES_FOR_KELLY_CALIBRATION or not is_calibrated
    )

    if use_fixed_risk:
        base_size = calculate_fixed_risk_position_size(
            entry_price=entry_price,
            stop_loss_price=stop_loss_price,
            max_cap_pct=max_cap_pct,
        )
        base_label = "FIXED_RISK_SIZING_UNCALIBRATED"
    else:
        if half_kelly_f <= 0:
            return 0.0, "KELLY_NON_POSITIVE"
        base_size = min(half_kelly_f, max_cap_pct)
        base_label = "STANDARD_HALF_KELLY"

    if regime_hysteresis_penalty:
        base_size = round(base_size * 0.5, 4)

    if consecutive_losses >= 2 or current_drawdown_pct >= DRAWDOWN_HALF_SIZE_PCT:
        defensive_size = round(base_size * 0.5, 4)
        return defensive_size, "DRAWDOWN_DEFENSE_HALF_SIZE"

    if regime_hysteresis_penalty:
        return base_size, "REGIME_CONFLICT_HALF_SIZE"

    return round(base_size, 4), base_label


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
