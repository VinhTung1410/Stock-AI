"""
Mathematical Consistency & Sanity Check Engine — institutional-grade
validation layer before rendering UI or sending data to LLMs.

Enforces 6 invariant rules:
1. Long position: Current Price > Trailing Stop / Stop Loss.
2. New trade setup: Target > Entry > Stop Loss.
3. R:R consistency from the same weighted average entry.
4. MoS % = (Fair Value - Current Price) / Fair Value * 100%.
5. Profitable positions strictly prohibited from 'cut loss' labels.
6. Strong value + positive MoS never misclassified as 'AVOID'.
"""

import logging
from typing import Any

import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

COL_GIA_VON_K = "Giá vốn (k)"
COL_THI_GIA_K = "Thị giá (k)"


def validate_holding_position(pos: dict) -> tuple[bool, list[str], dict]:
    """Audit a holding position against mathematical and label consistency rules.

    Checks:
    - P/L % matches (current - entry) / entry
    - Profitable positions use trailing stop (not stop loss), clamped < current price
    - Losing positions have stop loss < current price

    Returns:
        tuple of (is_valid: bool, issues: list[str], sanitized_pos: dict)
    """
    issues = []
    sanitized = dict(pos)

    curr_p = float(sanitized.get("curr_price", sanitized.get("market_price", 0.0)))
    entry_p = float(sanitized.get("entry_price", sanitized.get("avg_price", 0.0)))
    pl_pct = float(sanitized.get("pl_pct", 0.0))
    action = str(sanitized.get("action", ""))
    trailing_stop = sanitized.get("trailing_stop")
    stop_loss = sanitized.get("stop_loss")

    # 1. Kiểm tra tính khớp của P/L %
    if entry_p > 0:
        expected_pl = round(((curr_p - entry_p) / entry_p) * 100, 2)
        if abs(pl_pct - expected_pl) > 0.5:
            issues.append(f"P/L% không khớp: ghi nhận {pl_pct}%, tính toán lại {expected_pl}%.")
            sanitized["pl_pct"] = expected_pl

    # 2. Quy tắc cốt tử: Vị thế LÃI cấm dùng từ Cắt lỗ
    if pl_pct > 0:
        if "CẮT LỖ" in action.upper():
            issues.append("Vi phạm logic: Vị thế đang LÃI nhưng lại gắn nhãn CẮT LỖ!")
            sanitized["action"] = "🟢 BẢO VỆ THÀNH QUẢ / NÂNG TRAILING STOP"

        # 3. Validation Trailing Stop: Bắt buộc Trailing Stop < Current Price
        if trailing_stop is not None:
            trailing_stop = float(trailing_stop)
            if trailing_stop >= curr_p:
                issues.append(f"Vi phạm logic: Trailing Stop ({trailing_stop}k) >= Thị giá hiện tại ({curr_p}k)!")
                # Auto-remediate clamp: Trailing stop tối đa = curr_p * 0.96
                sanitized["trailing_stop"] = round(curr_p * 0.96, 2)

    # 4. Vị thế LỖ: Stop Loss bắt buộc < Current Price
    elif pl_pct < 0:
        if stop_loss is not None:
            stop_loss = float(stop_loss)
            if stop_loss >= curr_p:
                issues.append(f"Vi phạm logic: Stop Loss ({stop_loss}k) >= Thị giá ({curr_p}k)!")
                sanitized["stop_loss"] = round(curr_p * 0.96, 2)

    is_valid = len(issues) == 0
    return is_valid, issues, sanitized


def validate_trade_setup(setup: dict) -> tuple[bool, list[str], dict]:
    """Audit new buy / accumulation trade setup for order and R:R consistency.

    Enforces:
    - Long order: Target > Entry > Stop Loss
    - R:R = (Target - Entry) / (Entry - Stop Loss)

    Returns:
        tuple of (is_valid: bool, issues: list[str], sanitized_setup: dict)
    """
    issues = []
    sanitized = dict(setup)

    entry = float(
        sanitized.get("weighted_entry")
        or sanitized.get("avg_cost")
        or sanitized.get("entry_price")
        or sanitized.get("current_price", 0.0)
    )
    target = float(sanitized.get("target_price", 0.0))
    stop = float(sanitized.get("stop_loss", 0.0))
    reported_rr = float(sanitized.get("risk_reward", 1.0))

    if target > 0 and entry > 0 and stop > 0:
        # Kiểm tra thứ tự giá đối với lệnh Long
        if not (target > entry > stop):
            issues.append(f"Vi phạm trật tự giá Long: Target ({target}k) > Entry ({entry}k) > Stop ({stop}k) bị sai!")
            # Tự động điều chỉnh
            if target <= entry:
                target = round(entry * 1.15, 2)
                sanitized["target_price"] = target
            if stop >= entry:
                stop = round(entry * 0.93, 2)
                sanitized["stop_loss"] = stop

        # Kiểm tra tính khớp của R:R
        reward = target - entry
        risk = entry - stop
        calculated_rr = round(reward / risk, 2) if risk > 0 else 1.0

        if abs(reported_rr - calculated_rr) > 0.15:
            issues.append(f"R:R không khớp công thức: ghi nhận {reported_rr}x, tính lại {calculated_rr}x.")
            sanitized["risk_reward"] = calculated_rr

    is_valid = len(issues) == 0
    return is_valid, issues, sanitized


def validate_valuation_mos(val_dict: dict) -> tuple[bool, list[str], dict]:
    """Audit Margin of Safety (MoS) % and valuation model availability.

    Enforces:
    - MoS % = (Fair Value - Current Price) / Fair Value * 100%
    - Valuation methodology and confidence presence

    Returns:
        tuple of (is_valid: bool, issues: list[str], sanitized_val: dict)
    """
    issues = []
    sanitized = dict(val_dict)

    fv = float(sanitized.get("fair_value", sanitized.get("fair_value_base", 0.0)))
    curr_p = float(sanitized.get("current_price", 0.0))
    reported_mos = float(sanitized.get("mos_pct", 0.0))

    if fv > 0 and curr_p > 0:
        calculated_mos = round(((fv - curr_p) / fv) * 100, 2)
        if abs(reported_mos - calculated_mos) > 0.5:
            issues.append(f"MoS% không khớp: ghi nhận {reported_mos}%, tính lại {calculated_mos}%.")
            sanitized["mos_pct"] = calculated_mos

    if not sanitized.get("valuation_method") or sanitized.get("valuation_method") == "N/A":
        issues.append("Thiếu thông tin mô hình định giá (Valuation Method)!")
        sanitized["valuation_method"] = "Normalized Valuation Multiple"

    if sanitized.get("confidence") not in ["HIGH", "MEDIUM", "LOW"]:
        sanitized["confidence"] = "MEDIUM"

    is_valid = len(issues) == 0
    return is_valid, issues, sanitized


def validate_value_vs_technical(
    symbol: str, mos_pct: float, action_state: str, decision_tag: str
) -> tuple[bool, str, str]:
    """Guard against misclassifying high-value stocks with weak technicals as 'AVOID'.

    If fundamental MoS >= 8% but technical is currently lagging (e.g. below MA20),
    auto-remediates action to 'WATCH / WAIT FOR BASE' instead of 'AVOID'.

    Returns:
        tuple of (is_valid: bool, new_action: str, new_tag: str)
    """
    is_valid = True
    new_action = action_state
    new_tag = decision_tag

    is_avoid = any(w in decision_tag.upper() or w in action_state.upper() for w in ["TRÁNH BẪY", "AVOID", "BẪY TIN"])

    if mos_pct >= 8.0 and is_avoid:
        is_valid = False
        new_action = "🟡 THEO DÕI"
        new_tag = f"🟡 THEO DÕI / CHỜ NỀN CÂN BẰNG (Mã {symbol} có MoS {mos_pct:.1f}% đạt chuẩn giá trị, Kỹ thuật đang tích lũy dưới MA20 - Chờ nến xác nhận)"
        logging.warning(f"Sanity Check: Đã auto-remediate mã {symbol} từ AVOID sang WATCH / WAIT FOR CONFIRMATION!")

    return is_valid, new_action, new_tag


def run_full_portfolio_sanity_check(df_portfolio: pd.DataFrame) -> tuple[bool, list[str], pd.DataFrame]:
    """Audit the entire portfolio DataFrame before UI rendering or LLM dispatch.

    Returns:
        tuple of (all_passed: bool, log_issues: list[str], clean_df: pd.DataFrame)
    """
    if df_portfolio is None or df_portfolio.empty:
        return True, [], df_portfolio

    all_passed = True
    log_issues = []
    df_clean = df_portfolio.copy()

    for idx, row in df_clean.iterrows():
        sym = str(row.get("Mã CP", row.get("symbol", "")))
        entry_p = float(row.get(COL_GIA_VON_K, row.get("avg_price", row.get("cost_price", 0.0))))
        curr_p = float(row.get(COL_THI_GIA_K, row.get("market_price", row.get("current_price", entry_p))))

        # Operational Gate: Chống lệch scale giá (VND vs k VND, lỗi nhân 100x hoặc 1000x)
        if entry_p >= 10000.0:
            entry_p /= 1000.0
            if COL_GIA_VON_K in df_clean.columns:
                df_clean.at[idx, COL_GIA_VON_K] = round(entry_p, 2)
        elif 1000.0 <= entry_p < 10000.0:
            entry_p /= 100.0
            if COL_GIA_VON_K in df_clean.columns:
                df_clean.at[idx, COL_GIA_VON_K] = round(entry_p, 2)

        if curr_p >= 10000.0:
            curr_p /= 1000.0
            if COL_THI_GIA_K in df_clean.columns:
                df_clean.at[idx, COL_THI_GIA_K] = round(curr_p, 2)
        elif 1000.0 <= curr_p < 10000.0:
            curr_p /= 100.0
            if COL_THI_GIA_K in df_clean.columns:
                df_clean.at[idx, COL_THI_GIA_K] = round(curr_p, 2)

        pnl_pct = float(row.get("Lãi/Lỗ (%)", row.get("pl_pct", 0.0)))
        def_target = row.get("Chặn lãi/Cắt lỗ (k)", row.get("trailing_stop", row.get("stop_loss")))

        vol = float(row.get("Khối lượng", 0))
        if "Lãi/Lỗ (VND)" in df_clean.columns and vol > 0:
            df_clean.at[idx, "Lãi/Lỗ (VND)"] = int(vol * (curr_p - entry_p) * 1000)

        pos_dict = {
            "symbol": sym,
            "entry_price": entry_p,
            "curr_price": curr_p,
            "pl_pct": pnl_pct,
            "action": str(row.get("Hành động V2", row.get("action", ""))),
            "trailing_stop": def_target if pnl_pct > 0 else None,
            "stop_loss": def_target if pnl_pct <= 0 else None,
        }

        v_ok, issues, san_pos = validate_holding_position(pos_dict)
        if not v_ok:
            all_passed = False
            for iss in issues:
                log_issues.append(f"[{sym}] {iss}")

            # Cập nhật lại giá trị đã được auto-remediate vào DataFrame
            if pnl_pct > 0 and "Chặn lãi/Cắt lỗ (k)" in df_clean.columns:
                df_clean.at[idx, "Chặn lãi/Cắt lỗ (k)"] = san_pos["trailing_stop"]
            elif pnl_pct <= 0 and "Chặn lãi/Cắt lỗ (k)" in df_clean.columns:
                df_clean.at[idx, "Chặn lãi/Cắt lỗ (k)"] = san_pos["stop_loss"]

            if "Hành động V2" in df_clean.columns:
                df_clean.at[idx, "Hành động V2"] = san_pos["action"]

    return all_passed, log_issues, df_clean


def compute_fundamental_input_hash(
    eps: Any = None,
    bvps: Any = None,
    roe: Any = None,
    pe: Any = None,
    consensus_price: Any = None,
    bctc_period: Any = None,
) -> str:
    """Hash core fundamental metrics (EPS, BVPS, ROE, P/E, consensus target) to detect provider revisions
    even when period or as_of labels remain unchanged (e.g. KBS BVPS revision incident)."""
    import hashlib
    raw = f"eps={eps}|bvps={bvps}|roe={roe}|pe={pe}|cons={consensus_price}|period={bctc_period}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def calculate_implicit_fair_value(price: float | None, mos_pct: float | None) -> float | None:
    """Calculate implicit fair value using the invariant: FV = Price / (1 - MoS/100)."""
    if price is None or price <= 0 or mos_pct is None:
        return None
    # Support both percentage (e.g. 20.0 for 20%) and ratio (0.20)
    mos_ratio = (mos_pct / 100.0) if abs(mos_pct) > 1.0 else mos_pct
    denom = 1.0 - mos_ratio
    if abs(denom) < 1e-6:
        return None
    return round(price / denom, 2)


def detect_unintended_valuation_drift(
    prev_record: dict,
    curr_record: dict,
    tolerance_pct: float = 0.5,
) -> tuple[bool, str]:
    """Audit invariant: Implicit Fair Value = Price / (1 - MoS) must NOT drift
    between sessions if fundamental inputs (EPS, BVPS, consensus, period) are unchanged.

    Returns:
        (is_drift_detected: bool, message: str)
    """
    sym = curr_record.get("symbol") or prev_record.get("symbol", "UNKNOWN")
    f_prev = prev_record.get("facts") if isinstance(prev_record.get("facts"), dict) else prev_record
    f_curr = curr_record.get("facts") if isinstance(curr_record.get("facts"), dict) else curr_record

    # 1. Compare fundamental data hash (fin_hash) if present
    fin_hash_prev = f_prev.get("fin_hash")
    fin_hash_curr = f_curr.get("fin_hash")
    if fin_hash_prev and fin_hash_curr and fin_hash_prev != fin_hash_curr:
        return False, f"[{sym}] Fundamental numbers legitimately changed (fin_hash: {fin_hash_prev}->{fin_hash_curr})"

    # 2. Check declared period and consensus dates
    period_prev = f_prev.get("bctc_period")
    period_curr = f_curr.get("bctc_period")
    cons_asof_prev = f_prev.get("consensus_asof")
    cons_asof_curr = f_curr.get("consensus_asof")

    # If period or consensus date changed, input legitimately changed
    if (period_prev and period_curr and period_prev != period_curr) or (
        cons_asof_prev and cons_asof_curr and cons_asof_prev != cons_asof_curr
    ):
        return False, (
            f"[{sym}] Inputs updated legitimately: BCTC {period_prev}->{period_curr}, "
            f"Consensus {cons_asof_prev}->{cons_asof_curr}"
        )

    p_prev = float(f_prev.get("price") or 0.0)
    p_curr = float(f_curr.get("price") or 0.0)
    mos_prev = f_prev.get("mos_pct")
    mos_curr = f_curr.get("mos_pct")

    if mos_prev is None or mos_curr is None or p_prev <= 0 or p_curr <= 0:
        return False, f"[{sym}] MoS or Price absent in one or both records; invariant check skipped."

    fv_prev = calculate_implicit_fair_value(p_prev, float(mos_prev))
    fv_curr = calculate_implicit_fair_value(p_curr, float(mos_curr))

    if fv_prev is None or fv_curr is None or fv_prev <= 0:
        return False, f"[{sym}] Indeterminate implicit fair value."

    drift_pct = abs(fv_curr - fv_prev) / fv_prev * 100.0
    if drift_pct > tolerance_pct:
        msg = (
            f"[{sym}] UNINTENDED VALUATION DRIFT DETECTED: Implicit FV mutated from {fv_prev:.2f}k to {fv_curr:.2f}k "
            f"({drift_pct:.2f}% > {tolerance_pct}%) while fundamental inputs were unchanged "
            f"(BCTC: {period_curr}, Consensus: {cons_asof_curr})."
        )
        logging.warning(msg)
        return True, msg

    return False, f"[{sym}] Invariant preserved: FV drift {drift_pct:.2f}% <= {tolerance_pct}%"

