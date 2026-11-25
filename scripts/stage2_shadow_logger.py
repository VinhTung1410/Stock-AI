# -*- coding: utf-8 -*-
"""Stage 2 Prospective Raw Score & Shadow Regime Logger (v2.0.0).

Implements the locked Stage 2 v2.1 logging specification (pre-reg-v2.1-locked-20261125):
- Append-only, completely isolated from canonical_forward_returns_*.csv.
- Logs ALL 55 universe symbols daily (Table 1) plus daily market/Arm A-B-C state (Table 2).
- Strictly zero forward-return columns (no look-ahead); timestamps logged_at before T+1 open.
- Enforces rows == 55 invariant, trading-day validation, idempotent re-runs, and SHA256 manifest.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import subprocess
import sys
from datetime import datetime, timezone
from typing import Any

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data_engine import _fetch_history_with_fallback
from regime_classifier import REGIME_UPTREND, classify_regime_ma200_hysteresis
from scripts.update_forward_returns import UNIVERSE_METADATA

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
LOGGER = logging.getLogger("stage2_shadow_logger")

# SonarCloud S1192 Constants
SCHEMA_VERSION = "2.0.0"
EXPECTED_UNIVERSE_SIZE = 55
PROSPECTIVE_START_DATE = "2026-11-26"
ROLE_PROSPECTIVE = "STAGE2_PROSPECTIVE"
ROLE_EXPLORATORY = "EXPLORATORY_IN_SAMPLE"
DEC_WATCH = "WATCH"
DEC_REJECT = "REJECT"
GROUP_SHADOW = "SHADOW"
GROUP_WATCH_FAILED = "WATCH_FAILED_INTERNAL"
GROUP_REJECT = "REJECT"
SESSION_EOD = "EOD_CANONICAL"
SYM_VNINDEX = "VNINDEX"
DEFAULT_OUTPUT_DIR = os.path.join("data", "stage2_shadow")
STOCK_LOG_FILENAME = "stage2_stock_scores.csv"
MARKET_LOG_FILENAME = "stage2_market_regime.csv"
MANIFEST_FILENAME = "stage2_manifest_sha256.json"
DEFAULT_LOGIC_VERSION = "v15.0_frozen_20261013"

# Locked Gate Thresholds (Stage 2 Pre-Reg Section 2)
MIN_MOS_PCT = 15.0
MIN_CONVICTION = 70.0
MIN_RSI = 45.0
MIN_VOL_RATIO = 1.0
ARM_A_MA200_FLOOR = -2.0
ARM_C_MA200_FLOOR = -3.0
ARM_C_BREADTH_MIN = 40.0
MIN_CONFIRM_STREAK = 2


def _compute_file_sha256(fpath: str) -> str:
    """Compute SHA256 hex digest of a file."""
    h = hashlib.sha256()
    with open(fpath, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _get_current_git_sha() -> str:
    """Return short HEAD commit hash safely."""
    try:
        return subprocess.check_output(["git", "rev-parse", "--short=10", "HEAD"], text=True).strip()
    except Exception:
        LOGGER.exception("Không lấy được git SHA hiện tại")
        return "unknown"


def _compute_wilder_rsi(closes: pd.Series, period: int = 14) -> float | None:
    """Compute latest RSI value from chronological close series without look-ahead."""
    clean = closes.dropna().astype(float)
    if len(clean) <= period:
        return None
    delta = clean.diff().dropna()
    gain = delta.clip(lower=0.0)
    loss = (-delta).clip(lower=0.0)
    avg_gain = float(gain.iloc[:period].mean())
    avg_loss = float(loss.iloc[:period].mean())
    for g, l_val in zip(gain.iloc[period:], loss.iloc[period:]):
        avg_gain = (avg_gain * (period - 1) + float(g)) / period
        avg_loss = (avg_loss * (period - 1) + float(l_val)) / period
    if avg_loss == 0.0:
        return 100.0 if avg_gain > 0.0 else 50.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


def _extract_t0_technicals(hist_df: pd.DataFrame | None, date_t0: str) -> dict[str, Any]:
    """Extract strict T0 technical indicators from history truncated at <= date_t0."""
    empty_res: dict[str, Any] = {
        "close": None,
        "ma20": None,
        "ma100": None,
        "volume": None,
        "ma20_volume": None,
        "rsi_14": None,
        "pct_vs_ma20": None,
        "pct_vs_ma100": None,
        "vol_vs_ma20": None,
        "has_t0_bar": False,
    }
    if hist_df is None or hist_df.empty or "date" not in hist_df.columns:
        return empty_res

    df = hist_df.copy()
    df["date_str"] = df["date"].astype(str).str[:10]
    df = df[df["date_str"] <= date_t0].sort_values("date_str")
    if df.empty or df["date_str"].iloc[-1] != date_t0:
        return empty_res

    closes = df["close"].astype(float)
    vols = df["volume"].astype(float) if "volume" in df.columns else pd.Series(0.0, index=df.index)
    last_close = float(closes.iloc[-1])
    last_vol = float(vols.iloc[-1])
    ma20 = float(closes.rolling(20).mean().iloc[-1]) if len(closes) >= 20 else None
    ma100 = float(closes.rolling(100).mean().iloc[-1]) if len(closes) >= 100 else None
    ma20_vol = float(vols.rolling(20).mean().iloc[-1]) if len(vols) >= 20 else None
    rsi_14 = _compute_wilder_rsi(closes, period=14)

    pct_ma20 = ((last_close - ma20) / ma20 * 100.0) if (ma20 and ma20 > 0) else None
    pct_ma100 = ((last_close - ma100) / ma100 * 100.0) if (ma100 and ma100 > 0) else None
    vol_ratio = (last_vol / ma20_vol) if (ma20_vol and ma20_vol > 0) else None

    return {
        "close": round(last_close, 4),
        "ma20": round(ma20, 4) if ma20 is not None else None,
        "ma100": round(ma100, 4) if ma100 is not None else None,
        "volume": round(last_vol, 2),
        "ma20_volume": round(ma20_vol, 2) if ma20_vol is not None else None,
        "rsi_14": round(rsi_14, 2) if rsi_14 is not None else None,
        "pct_vs_ma20": round(pct_ma20, 2) if pct_ma20 is not None else None,
        "pct_vs_ma100": round(pct_ma100, 2) if pct_ma100 is not None else None,
        "vol_vs_ma20": round(vol_ratio, 3) if vol_ratio is not None else None,
        "has_t0_bar": True,
    }


def _evaluate_gates(rec: dict[str, Any], tech: dict[str, Any]) -> dict[str, Any]:
    """Evaluate Gates 1..6, trap flags, and control group cleanly."""
    decision = str(rec.get("decision") or DEC_REJECT).upper()
    reason_raw = str(rec.get("rejection_reasons") or "")
    gates_raw = str(rec.get("gates_failed") or "")
    conv = float(rec["conviction"]) if pd.notna(rec.get("conviction")) else None
    mos = float(rec["mos_pct"]) if pd.notna(rec.get("mos_pct")) else None

    has_bar = bool(tech.get("has_t0_bar"))
    close = tech.get("close")
    ma20 = tech.get("ma20")
    ma100 = tech.get("ma100")
    rsi = tech.get("rsi_14")
    vol_r = tech.get("vol_vs_ma20")

    gate_data = has_bar and ("DATA_RECONCILE" not in gates_raw) and bool(rec.get("informative", True))
    gate_fin = ("FINANCIAL_HEALTH" not in gates_raw) and ("ALTMAN" not in gates_raw.upper())
    gate_mos = (mos is not None and mos >= MIN_MOS_PCT) and ("GATE_MOS" not in gates_raw) and ("VALUATION_MOS" not in gates_raw)

    tech_ok = (
        has_bar
        and close is not None
        and ma20 is not None
        and ma100 is not None
        and rsi is not None
        and close >= ma20
        and close >= ma100
        and rsi >= MIN_RSI
        and (vol_r is None or vol_r >= MIN_VOL_RATIO)
    )
    reason_tech_fail = any(
        txt in reason_raw for txt in ("giá dưới MA20", "giá dưới MA100", "RSI yếu", "cần thêm lực cầu")
    )
    gate_tech = tech_ok and not reason_tech_fail
    gate_conv = conv is not None and conv >= MIN_CONVICTION

    flag_falling_knife = bool(has_bar and close is not None and ma20 is not None and rsi is not None and close < ma20 * 0.95 and rsi < 36.0)
    flag_bull_trap = "BULL_TRAP" in reason_raw.upper() or "BULL_TRAP" in gates_raw.upper()
    flag_veto = "PM_VETO" in gates_raw.upper()
    gate_pm = not (flag_falling_knife or flag_bull_trap or flag_veto)

    pass_6 = bool(
        decision == DEC_WATCH
        and gate_data
        and gate_fin
        and gate_mos
        and gate_tech
        and gate_conv
        and gate_pm
    )
    if pass_6:
        group = GROUP_SHADOW
    elif decision == DEC_WATCH:
        group = GROUP_WATCH_FAILED
    else:
        group = GROUP_REJECT

    return {
        "gate_data_health": gate_data,
        "gate_financial_health": gate_fin,
        "gate_mos": gate_mos,
        "gate_tech_momentum": gate_tech,
        "gate_conviction": gate_conv,
        "gate_pm_veto": gate_pm,
        "flag_bull_trap": flag_bull_trap,
        "flag_falling_knife": flag_falling_knife,
        "flag_veto": flag_veto,
        "pass_6_internal_gates": pass_6,
        "group": group,
    }


def _load_eod_canonical_records(decision_csv: str) -> pd.DataFrame:
    """Load strictly EOD_CANONICAL rows from decision_records CSV."""
    if not os.path.exists(decision_csv):
        raise FileNotFoundError(f"Không tìm thấy tệp decision records cho ngày giao dịch: {decision_csv}")
    df = pd.read_csv(decision_csv)
    if "session" in df.columns:
        eod = df[df["session"] == SESSION_EOD].copy()
        if not eod.empty:
            return eod.drop_duplicates(subset=["symbol"], keep="last")
    if "is_canonical" in df.columns:
        can = df[df["is_canonical"] == True].copy()  # noqa: E712
        if not can.empty:
            return can.drop_duplicates(subset=["symbol"], keep="last")
    raise ValueError(f"Không có bản ghi EOD_CANONICAL hợp lệ trong {decision_csv} (có thể là ngày nghỉ lễ).")


def _validate_trading_day(date_t0: str, vn_hist: pd.DataFrame | None, decision_csv: str) -> pd.DataFrame:
    """Validate that date_t0 is a genuine trading day (reject weekends/holidays)."""
    dt_obj = datetime.strptime(date_t0, "%Y-%m-%d")
    if dt_obj.weekday() >= 5:
        raise ValueError(f"Từ chối chạy vào ngày cuối tuần: {date_t0}")

    if vn_hist is not None and not vn_hist.empty and "date" in vn_hist.columns:
        vn_dates = set(vn_hist["date"].astype(str).str[:10])
        if date_t0 not in vn_dates:
            raise ValueError(f"Ngày {date_t0} không có dữ liệu giao dịch VN-Index (ngày nghỉ lễ/chưa khớp lệnh).")

    return _load_eod_canonical_records(decision_csv)


def _compute_vnindex_row(
    date_t0: str,
    vn_hist: pd.DataFrame,
    breadth_pct: float,
    prev_market_row: dict[str, Any] | None,
    universe_hash: str,
    logged_at: str,
) -> dict[str, Any]:
    """Compute Table 2 daily market regime and Arm A/B/C tracking row."""
    df = vn_hist.copy()
    df["date_str"] = df["date"].astype(str).str[:10]
    df = df[df["date_str"] <= date_t0].sort_values("date_str")
    closes = df["close"].astype(float)

    vn_close = float(closes.iloc[-1])
    ma20_s = closes.rolling(20).mean()
    ma200_s = closes.rolling(200, min_periods=50).mean()
    vn_ma20 = float(ma20_s.iloc[-1]) if pd.notna(ma20_s.iloc[-1]) else vn_close
    vn_ma200 = float(ma200_s.iloc[-1]) if pd.notna(ma200_s.iloc[-1]) else vn_close

    slope_ma20 = float(((ma20_s.iloc[-1] - ma20_s.iloc[-6]) / ma20_s.iloc[-6]) * 100.0) if len(ma20_s.dropna()) >= 6 else 0.0
    slope_ma200 = float(((ma200_s.iloc[-1] - ma200_s.iloc[-21]) / ma200_s.iloc[-21]) * 100.0) if len(ma200_s.dropna()) >= 21 else 0.0
    vs_ma200 = ((vn_close - vn_ma200) / vn_ma200 * 100.0) if vn_ma200 > 0 else 0.0

    raw_a = (vs_ma200 >= ARM_A_MA200_FLOOR) and (vn_close > vn_ma20) and (slope_ma20 > 0.0)
    hyst_series = classify_regime_ma200_hysteresis(df, reentry_pct=1.0, confirmation_sessions=2, vol_surge_mult=1.3)
    raw_b = str(hyst_series.iloc[-1]) == REGIME_UPTREND
    raw_c = (vs_ma200 >= ARM_C_MA200_FLOOR) and (breadth_pct >= ARM_C_BREADTH_MIN)

    prev = prev_market_row or {}
    streak_a = (int(prev.get("arm_a_streak", 0)) + 1) if raw_a else 0
    streak_b = (int(prev.get("arm_b_streak", 0)) + 1) if raw_b else 0
    streak_c = (int(prev.get("arm_c_streak", 0)) + 1) if raw_c else 0

    return {
        "schema_version": SCHEMA_VERSION,
        "date_t0": date_t0,
        "vn_close": round(vn_close, 2),
        "vn_ma20": round(vn_ma20, 2),
        "vn_ma200": round(vn_ma200, 2),
        "vn_vs_ma200_pct": round(vs_ma200, 2),
        "slope_ma20": round(slope_ma20, 3),
        "slope_ma200": round(slope_ma200, 3),
        "breadth_pct_above_ma20": round(breadth_pct, 2),
        "arm_a_open": streak_a >= MIN_CONFIRM_STREAK,
        "arm_b_open": streak_b >= MIN_CONFIRM_STREAK,
        "arm_c_open": streak_c >= MIN_CONFIRM_STREAK,
        "arm_a_streak": streak_a,
        "arm_b_streak": streak_b,
        "arm_c_streak": streak_c,
        "is_trading_day": True,
        "universe_hash": universe_hash,
        "logged_at": logged_at,
    }


def _append_idempotent(csv_path: str, new_df: pd.DataFrame, date_t0: str) -> bool:
    """Append new_df strictly once per date_t0 (idempotent on re-run)."""
    if os.path.exists(csv_path):
        existing = pd.read_csv(csv_path)
        if not existing.empty and date_t0 in set(existing["date_t0"].astype(str)):
            LOGGER.info("Ngày %s đã tồn tại trong %s — bỏ qua ghi trùng (idempotent).", date_t0, csv_path)
            return False
        combined = pd.concat([existing, new_df], ignore_index=True)
        combined.to_csv(csv_path, index=False, encoding="utf-8")
    else:
        new_df.to_csv(csv_path, index=False, encoding="utf-8")
    return True


def _update_sha256_manifest(output_dir: str, stock_path: str, market_path: str, date_t0: str, logged_at: str) -> str:
    """Write or update append-only SHA256 verification manifest."""
    manifest_path = os.path.join(output_dir, MANIFEST_FILENAME)
    manifest: dict[str, Any] = {"schema_version": SCHEMA_VERSION, "entries": []}
    if os.path.exists(manifest_path):
        try:
            with open(manifest_path, encoding="utf-8") as fh:
                manifest = json.load(fh)
        except Exception:
            LOGGER.exception("Lỗi đọc manifest %s; khởi tạo lại danh sách.", manifest_path)

    existing_dates = {e.get("date_t0") for e in manifest.get("entries", [])}
    if date_t0 not in existing_dates:
        manifest.setdefault("entries", []).append({
            "date_t0": date_t0,
            "logged_at": logged_at,
            "stock_csv_sha256": _compute_file_sha256(stock_path),
            "market_csv_sha256": _compute_file_sha256(market_path),
        })
        with open(manifest_path, "w", encoding="utf-8") as fh:
            json.dump(manifest, fh, ensure_ascii=False, indent=2)
    return manifest_path


def run_stage2_shadow_logger(
    date_t0: str,
    entry_date_t1: str = "",
    data_dir: str = ".",
    output_dir: str = DEFAULT_OUTPUT_DIR,
    history_fetcher: Any = _fetch_history_with_fallback,
    logged_at_override: str | None = None,
) -> dict[str, Any]:
    """Execute Stage 2 v2.1 prospective raw-score & market-regime logging for a trading day."""
    d_code = date_t0.replace("-", "")
    decision_csv = os.path.join(data_dir, f"decision_records_{d_code}.csv")

    vn_hist = history_fetcher(SYM_VNINDEX, days=320)
    eod_df = _validate_trading_day(date_t0, vn_hist, decision_csv)

    universe_symbols = sorted(eod_df["symbol"].astype(str).unique().tolist())
    if len(universe_symbols) != EXPECTED_UNIVERSE_SIZE:
        raise ValueError(
            f"Vi phạm bất biến rows == {EXPECTED_UNIVERSE_SIZE}: tìm thấy {len(universe_symbols)} mã trong {decision_csv}."
        )

    logged_at = logged_at_override or datetime.now(timezone.utc).isoformat()
    sample_role = ROLE_PROSPECTIVE if date_t0 >= PROSPECTIVE_START_DATE else ROLE_EXPLORATORY
    git_sha = _get_current_git_sha()
    rec_map = {str(r["symbol"]): r.to_dict() for _, r in eod_df.iterrows()}

    stock_rows: list[dict[str, Any]] = []
    above_ma20_count = 0
    valid_ma20_count = 0
    universe_hash = ""

    for sym in universe_symbols:
        rec = rec_map.get(sym)
        missing_reasons: list[str] = []
        if rec is None:
            rec = {"symbol": sym, "decision": DEC_REJECT}
            missing_reasons.append("MISSING_EOD_DECISION")
        elif not universe_hash and isinstance(rec.get("facts"), str):
            try:
                universe_hash = str(json.loads(rec["facts"]).get("universe_hash") or "")
            except Exception:
                LOGGER.exception("Lỗi đọc facts JSON cho %s", sym)

        sym_hist = history_fetcher(sym, days=180)
        tech = _extract_t0_technicals(sym_hist, date_t0)
        if not tech["has_t0_bar"]:
            missing_reasons.append("HALTED_OR_NO_OHLCV")

        if tech["close"] is not None and tech["ma20"] is not None:
            valid_ma20_count += 1
            if tech["close"] > tech["ma20"]:
                above_ma20_count += 1

        gate_res = _evaluate_gates(rec, tech)
        sector = UNIVERSE_METADATA.get(sym, {}).get("sector", "Khác")
        stock_rows.append({
            "schema_version": SCHEMA_VERSION,
            "date_t0": date_t0,
            "entry_date_t1": entry_date_t1,
            "symbol": sym,
            "sector": sector,
            "logic_version": str(rec.get("logic_version") or DEFAULT_LOGIC_VERSION),
            "commit": str(rec.get("git_sha") or git_sha)[:10],
            "logged_at": logged_at,
            "price_adjusted": True,
            "sample_role": sample_role,
            "decision": str(rec.get("decision") or DEC_REJECT),
            "watch_reason": str(rec.get("rejection_reasons") or ""),
            "rejection_gate": str(rec.get("primary_rejection_gate") or ""),
            "conviction": rec.get("conviction"),
            "mos_pct": rec.get("mos_pct"),
            "rsi_14": tech["rsi_14"],
            "close": tech["close"],
            "ma20": tech["ma20"],
            "ma100": tech["ma100"],
            "volume": tech["volume"],
            "ma20_volume": tech["ma20_volume"],
            "pct_vs_ma20": tech["pct_vs_ma20"],
            "pct_vs_ma100": tech["pct_vs_ma100"],
            "vol_vs_ma20": tech["vol_vs_ma20"],
            **gate_res,
            "missing_reason": ";".join(missing_reasons),
        })

    if len(stock_rows) != EXPECTED_UNIVERSE_SIZE:
        raise AssertionError(f"Từ chối ghi Bảng 1: len(stock_rows)={len(stock_rows)} != {EXPECTED_UNIVERSE_SIZE}.")

    os.makedirs(output_dir, exist_ok=True)
    stock_path = os.path.join(output_dir, STOCK_LOG_FILENAME)
    market_path = os.path.join(output_dir, MARKET_LOG_FILENAME)

    prev_market_row: dict[str, Any] | None = None
    if os.path.exists(market_path):
        prev_df = pd.read_csv(market_path)
        prev_lt = prev_df[prev_df["date_t0"].astype(str) < date_t0].sort_values("date_t0")
        if not prev_lt.empty:
            prev_market_row = prev_lt.iloc[-1].to_dict()

    breadth_pct = (above_ma20_count / valid_ma20_count * 100.0) if valid_ma20_count > 0 else 0.0
    if not universe_hash:
        universe_hash = hashlib.sha256(",".join(universe_symbols).encode("utf-8")).hexdigest()[:16]

    market_row = _compute_vnindex_row(date_t0, vn_hist, breadth_pct, prev_market_row, universe_hash, logged_at)

    wrote_stock = _append_idempotent(stock_path, pd.DataFrame(stock_rows), date_t0)
    wrote_market = _append_idempotent(market_path, pd.DataFrame([market_row]), date_t0)
    manifest_path = _update_sha256_manifest(output_dir, stock_path, market_path, date_t0, logged_at)

    return {
        "date_t0": date_t0,
        "rows_logged": len(stock_rows),
        "wrote_new": wrote_stock and wrote_market,
        "shadow_count": sum(1 for r in stock_rows if r["pass_6_internal_gates"]),
        "stock_path": stock_path,
        "market_path": market_path,
        "manifest_path": manifest_path,
    }


def main() -> None:
    """CLI entrypoint for Stage 2 shadow logger."""
    parser = argparse.ArgumentParser(description="Stage 2 v2.1 Raw Score & Shadow Logger")
    parser.add_argument("date", help="Trading date YYYY-MM-DD")
    parser.add_argument("--entry-t1", default="", help="Expected next trading day YYYY-MM-DD")
    parser.add_argument("--data-dir", default=".", help="Directory containing decision_records_*.csv")
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR, help="Isolated Stage 2 output directory")
    args = parser.parse_args()

    res = run_stage2_shadow_logger(
        date_t0=args.date,
        entry_date_t1=args.entry_t1,
        data_dir=args.data_dir,
        output_dir=args.output_dir,
    )
    LOGGER.info("Stage 2 logger hoàn tất: %s", res)


if __name__ == "__main__":
    main()
