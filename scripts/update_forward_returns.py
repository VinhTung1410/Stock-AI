"""Script to compute and update forward returns (T+1, T+3, T+5, T+10, T+20) for all decision records.

Adheres to Institutional Evidence Framework:
- Dual-mode return reporting: Signal Return (Close_T to Close_T+h) & Executable Return (Open_T+1 to Close_T+h).
- Strictly aligned VN-Index return matching exact entry and exit conventions.
- HOSE tick size aware Ceiling/Floor flags (ENTRY_CEILING_LOCKED, EXIT_FLOOR_LOCKED).
- Explicit deduplication and canonical record filtering (is_canonical >= 2026-10-14).
- Rich self-auditable metadata: raw prices (close_t0, open_t1, close_t1), sector, exchange, maturity booleans, and large gap flags.
"""

from __future__ import annotations

import argparse
import logging
import math
import os
import sys
from datetime import datetime, timedelta
from typing import Any

import numpy as np
import pandas as pd

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Add project root to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data_engine import _fetch_history_with_fallback
from db_manager import (
    get_supabase_client,
    update_decision_forward_returns,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

HORIZONS = (1, 3, 5, 10, 20)
CANONICAL_CUTOFF_DATE = "2026-10-14"
CALC_VERSION = "v2.0_institutional"
DEFAULT_LOGIC_VERSION = "v15.0_frozen_20261013"
EST_TRANSACTION_FEE_PCT = 0.40
LARGE_GAP_THRESHOLD_PP = 2.0
SYM_VNINDEX = "VNINDEX"
EXCHANGE_HOSE = "HOSE"
EXCHANGE_HNX = "HNX"
EXCHANGE_UPCOM = "UPCOM"
DECISION_WATCH = "WATCH"
DECISION_REJECT = "REJECT"

# Sector Classification for Universe 58
UNIVERSE_METADATA: dict[str, dict[str, str]] = {
    # Ngân hàng (14)
    "ACB": {"exchange": EXCHANGE_HOSE, "sector": "Ngân hàng"},
    "BID": {"exchange": EXCHANGE_HOSE, "sector": "Ngân hàng"},
    "CTG": {"exchange": EXCHANGE_HOSE, "sector": "Ngân hàng"},
    "HDB": {"exchange": EXCHANGE_HOSE, "sector": "Ngân hàng"},
    "MBB": {"exchange": EXCHANGE_HOSE, "sector": "Ngân hàng"},
    "MSB": {"exchange": EXCHANGE_HOSE, "sector": "Ngân hàng"},
    "SHB": {"exchange": EXCHANGE_HOSE, "sector": "Ngân hàng"},
    "SSB": {"exchange": EXCHANGE_HOSE, "sector": "Ngân hàng"},
    "STB": {"exchange": EXCHANGE_HOSE, "sector": "Ngân hàng"},
    "TCB": {"exchange": EXCHANGE_HOSE, "sector": "Ngân hàng"},
    "TPB": {"exchange": EXCHANGE_HOSE, "sector": "Ngân hàng"},
    "VCB": {"exchange": EXCHANGE_HOSE, "sector": "Ngân hàng"},
    "VIB": {"exchange": EXCHANGE_HOSE, "sector": "Ngân hàng"},
    "VPB": {"exchange": EXCHANGE_HOSE, "sector": "Ngân hàng"},
    # Chứng khoán (2)
    "SSI": {"exchange": EXCHANGE_HOSE, "sector": "Chứng khoán"},
    "VND": {"exchange": EXCHANGE_HOSE, "sector": "Chứng khoán"},
    # Thép & Vật liệu xây dựng (3)
    "HPG": {"exchange": EXCHANGE_HOSE, "sector": "Thép & Vật liệu"},
    "HSG": {"exchange": EXCHANGE_HOSE, "sector": "Thép & Vật liệu"},
    "NKG": {"exchange": EXCHANGE_HOSE, "sector": "Thép & Vật liệu"},
    # Bất động sản dân dụng (9)
    "DIG": {"exchange": EXCHANGE_HOSE, "sector": "Bất động sản dân dụng"},
    "DXG": {"exchange": EXCHANGE_HOSE, "sector": "Bất động sản dân dụng"},
    "KDH": {"exchange": EXCHANGE_HOSE, "sector": "Bất động sản dân dụng"},
    "NLG": {"exchange": EXCHANGE_HOSE, "sector": "Bất động sản dân dụng"},
    "NVL": {"exchange": EXCHANGE_HOSE, "sector": "Bất động sản dân dụng"},
    "PDR": {"exchange": EXCHANGE_HOSE, "sector": "Bất động sản dân dụng"},
    "VHM": {"exchange": EXCHANGE_HOSE, "sector": "Bất động sản dân dụng"},
    "VIC": {"exchange": EXCHANGE_HOSE, "sector": "Bất động sản dân dụng"},
    "VRE": {"exchange": EXCHANGE_HOSE, "sector": "Bất động sản dân dụng"},
    # Bất động sản KCN & Cao su (5)
    "GVR": {"exchange": EXCHANGE_HOSE, "sector": "BĐS KCN & Cao su"},
    "IDC": {"exchange": EXCHANGE_HNX, "sector": "BĐS KCN & Cao su"},
    "KBC": {"exchange": EXCHANGE_HOSE, "sector": "BĐS KCN & Cao su"},
    "SZC": {"exchange": EXCHANGE_HOSE, "sector": "BĐS KCN & Cao su"},
    "VGC": {"exchange": EXCHANGE_HOSE, "sector": "BĐS KCN & Cao su"},
    # Bán lẻ tiêu dùng (2)
    "MWG": {"exchange": EXCHANGE_HOSE, "sector": "Bán lẻ tiêu dùng"},
    "MSN": {"exchange": EXCHANGE_HOSE, "sector": "Bán lẻ tiêu dùng"},
    # Công nghệ (1)
    "FPT": {"exchange": EXCHANGE_HOSE, "sector": "Công nghệ / AI"},
    # Hóa chất & Phân bón (4)
    "CSV": {"exchange": EXCHANGE_HOSE, "sector": "Hóa chất & Phân bón"},
    "DCM": {"exchange": EXCHANGE_HOSE, "sector": "Hóa chất & Phân bón"},
    "DGC": {"exchange": EXCHANGE_HOSE, "sector": "Hóa chất & Phân bón"},
    "DPM": {"exchange": EXCHANGE_HOSE, "sector": "Hóa chất & Phân bón"},
    # Dầu khí & Năng lượng (6)
    "BSR": {"exchange": EXCHANGE_UPCOM, "sector": "Dầu khí & Năng lượng"},
    "GAS": {"exchange": EXCHANGE_HOSE, "sector": "Dầu khí & Năng lượng"},
    "PLX": {"exchange": EXCHANGE_HOSE, "sector": "Dầu khí & Năng lượng"},
    "POW": {"exchange": EXCHANGE_HOSE, "sector": "Dầu khí & Năng lượng"},
    "PVD": {"exchange": EXCHANGE_HOSE, "sector": "Dầu khí & Năng lượng"},
    "PVT": {"exchange": EXCHANGE_HOSE, "sector": "Dầu khí & Năng lượng"},
    # Cảng biển & Logistics (3)
    "GMD": {"exchange": EXCHANGE_HOSE, "sector": "Cảng biển & Logistics"},
    "HAH": {"exchange": EXCHANGE_HOSE, "sector": "Cảng biển & Logistics"},
    "VTP": {"exchange": EXCHANGE_HOSE, "sector": "Cảng biển & Logistics"},
    # Thủy sản (3)
    "ANV": {"exchange": EXCHANGE_HOSE, "sector": "Thủy sản"},
    "FMC": {"exchange": EXCHANGE_HOSE, "sector": "Thủy sản"},
    "VHC": {"exchange": EXCHANGE_HOSE, "sector": "Thủy sản"},
    # Dệt may (4)
    "GIL": {"exchange": EXCHANGE_HOSE, "sector": "Dệt may"},
    "MSH": {"exchange": EXCHANGE_HOSE, "sector": "Dệt may"},
    "STK": {"exchange": EXCHANGE_HOSE, "sector": "Dệt may"},
    "TNG": {"exchange": EXCHANGE_HNX, "sector": "Dệt may"},
    # Thực phẩm & Đồ uống (2)
    "SAB": {"exchange": EXCHANGE_HOSE, "sector": "Thực phẩm & Đồ uống"},
    "VNM": {"exchange": EXCHANGE_HOSE, "sector": "Thực phẩm & Đồ uống"},
}


def get_hose_tick_size(price: float) -> float:
    """Return HOSE tick size based on price level (in thousands VND)."""
    if price < 10.0:
        return 0.01
    if price < 50.0:
        return 0.05
    return 0.10


def calc_hose_ceiling_floor(ref_price: float) -> tuple[float, float]:
    """Calculate HOSE ceiling (+7%) and floor (-7%) prices rounded to tick size."""
    tick = get_hose_tick_size(ref_price)
    raw_ceil = ref_price * 1.07
    raw_floor = ref_price * 0.93
    ceil_p = round(math.floor(raw_ceil / tick + 1e-7) * tick, 2)
    floor_p = round(math.ceil(raw_floor / tick - 1e-7) * tick, 2)
    return ceil_p, max(floor_p, tick)


def calc_exchange_ceiling_floor(ref_price: float, exchange: str = EXCHANGE_HOSE) -> tuple[float, float]:
    """Calculate ceiling and floor prices rounded to exchange tick size:
    - HOSE: +/- 7%, tick based on price (<10k: 0.01, <50k: 0.05, >=50k: 0.10)
    - HNX: +/- 10%, tick 0.10
    - UPCOM: +/- 15%, tick 0.10
    """
    ex = (exchange or "").upper().strip()
    if ex == EXCHANGE_HNX:
        tick = 0.10
        raw_ceil = ref_price * 1.10
        raw_floor = ref_price * 0.90
    elif ex == EXCHANGE_UPCOM:
        tick = 0.10
        raw_ceil = ref_price * 1.15
        raw_floor = ref_price * 0.85
    else:
        return calc_hose_ceiling_floor(ref_price)

    ceil_p = round(math.floor(raw_ceil / tick + 1e-7) * tick, 2)
    floor_p = round(math.ceil(raw_floor / tick - 1e-7) * tick, 2)
    return ceil_p, max(floor_p, tick)


def _is_valid_ticker(sym: str) -> bool:
    """Validate 3-letter uppercase stock ticker or VNINDEX."""
    s = sym.upper().strip()
    return (len(s) == 3 and s.isalpha()) or s == SYM_VNINDEX


def get_symbol_profile(sym: str) -> tuple[str, str]:
    """Return exchange and sector for a symbol."""
    info = UNIVERSE_METADATA.get(sym.upper().strip())
    if info:
        return info.get("exchange", EXCHANGE_HOSE), info.get("sector", "Khác")
    return EXCHANGE_HOSE, "Khác"


def filter_canonical_and_deduplicate(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Deduplicate decision records according to institutional audit rules:
    - >= 2026-10-14: take records where is_canonical is True (or session is EOD_CANONICAL).
    - < 2026-10-14: take the latest record per (symbol, date) based on created_at.
    """
    selected: dict[tuple[str, str], dict[str, Any]] = {}

    for rec in records:
        sym = str(rec.get("symbol", "")).upper().strip()
        if not sym or not _is_valid_ticker(sym):
            continue

        raw_dt = str(rec.get("created_at") or rec.get("decision_time") or "")
        date_str = raw_dt[:10]
        if not date_str:
            continue

        is_canon = bool(
            rec.get("is_canonical")
            or (rec.get("facts") or {}).get("is_canonical")
            or rec.get("session") == "EOD_CANONICAL"
        )
        key = (sym, date_str)

        if date_str >= CANONICAL_CUTOFF_DATE:
            if is_canon:
                selected[key] = rec
        else:
            prev = selected.get(key)
            if prev is None:
                selected[key] = rec
            else:
                prev_dt = str(prev.get("created_at") or prev.get("decision_time") or "")
                if raw_dt > prev_dt:
                    selected[key] = rec

    return sorted(list(selected.values()), key=lambda r: str(r.get("created_at") or ""))


def _build_price_series(symbols: set[str], start_date: str, end_date: str) -> dict[str, dict[str, Any]]:
    """Fetch daily price series with full OHLC for valid symbols and VNINDEX."""
    series_map = {}
    valid_syms = sorted([s for s in symbols if _is_valid_ticker(s)])
    if SYM_VNINDEX not in valid_syms:
        valid_syms.append(SYM_VNINDEX)

    total = len(valid_syms)
    logging.info("Starting price history fetch for %d valid tickers...", total)

    for idx, sym in enumerate(valid_syms):
        try:
            df = _fetch_history_with_fallback(sym, start_date=start_date, end_date=end_date)
            if df is not None and not df.empty and "time" in df.columns and "close" in df.columns:
                df["date_str"] = df["time"].astype(str).str[:10]
                sorted_df = df.sort_values("date_str").drop_duplicates(subset=["date_str"])
                dates = list(sorted_df["date_str"])
                prices = {d: float(c) for d, c in zip(dates, sorted_df["close"])}

                # Store full OHLC dictionary
                ohlc = {}
                for _, row in sorted_df.iterrows():
                    d = str(row["date_str"])
                    ohlc[d] = {
                        "open": float(row.get("open", row.get("close", 0.0))),
                        "high": float(row.get("high", row.get("close", 0.0))),
                        "low": float(row.get("low", row.get("close", 0.0))),
                        "close": float(row.get("close", 0.0)),
                    }

                series_map[sym] = {"dates": dates, "prices": prices, "ohlc": ohlc}
                logging.info("[%d/%d] Fetched %s: %d trading sessions", idx + 1, total, sym, len(dates))
            else:
                series_map[sym] = {"dates": [], "prices": {}, "ohlc": {}}
                logging.warning("[%d/%d] Empty history for %s", idx + 1, total, sym)
        except Exception:
            logging.exception("Error fetching price history for %s", sym)
            series_map[sym] = {"dates": [], "prices": {}, "ohlc": {}}

    return series_map


def _find_matching_index(dates: list[str], raw_date: str) -> int | None:
    """Find the earliest trading day on or after raw_date."""
    for i, d in enumerate(dates):
        if d >= raw_date:
            return i
    return None


def _extract_price_point(sym_series: dict[str, Any], date_str: str) -> dict[str, float]:
    """Extract OHLC or fallback prices for a given date."""
    ohlc_map = sym_series.get("ohlc", {})
    if date_str in ohlc_map:
        return ohlc_map[date_str]
    close_p = float(sym_series.get("prices", {}).get(date_str, 0.0))
    return {"open": close_p, "high": close_p, "low": close_p, "close": close_p}


def _compute_signal_horizon(
    dates: list[str],
    sym_series: dict[str, Any],
    vn_series: dict[str, Any],
    matching_idx: int,
    h: int,
    p_close_t0: float,
    vn_close_t0: float,
) -> tuple[float | None, float | None, str | None, float | None, float | None]:
    """Compute signal return, matching VN-Index return, exit date, and exit prices for horizon h."""
    target_idx = matching_idx + h
    if target_idx >= len(dates) or p_close_t0 <= 0.0:
        return None, None, None, None, None

    exit_date = dates[target_idx]
    exit_p = _extract_price_point(sym_series, exit_date)["close"]
    signal_ret = round(((exit_p - p_close_t0) / p_close_t0) * 100.0, 3)

    vn_ret = None
    vn_exit_p = None
    if vn_close_t0 > 0.0:
        vn_exit_p = _extract_price_point(vn_series, exit_date)["close"]
        if vn_exit_p > 0.0:
            vn_ret = round(((vn_exit_p - vn_close_t0) / vn_close_t0) * 100.0, 3)

    return signal_ret, vn_ret, exit_date, exit_p, vn_exit_p


def _compute_executable_horizon(
    dates: list[str],
    sym_series: dict[str, Any],
    vn_series: dict[str, Any],
    matching_idx: int,
    h: int,
    p_open_t1: float,
    vn_open_t1: float,
    exchange: str = EXCHANGE_HOSE,
) -> tuple[float | None, float | None, bool, float | None, float | None]:
    """Compute executable return (entry at Open_T+1, exit Close_T+h), ceiling/floor, and floor check."""
    target_idx = matching_idx + h
    if target_idx >= len(dates) or p_open_t1 <= 0.0:
        return None, None, False, None, None

    exit_date = dates[target_idx]
    exit_p = _extract_price_point(sym_series, exit_date)["close"]
    prev_exit_p = _extract_price_point(sym_series, dates[target_idx - 1])["close"]

    # Exit ceiling and floor check (exchange-specific rule)
    ceil_exit, floor_exit = calc_exchange_ceiling_floor(prev_exit_p, exchange)
    exit_floor_locked = exit_p <= (floor_exit + 1e-4)

    exec_ret = round(((exit_p - p_open_t1) / p_open_t1) * 100.0, 3)

    vn_ret = None
    if vn_open_t1 > 0.0:
        vn_exit_p = _extract_price_point(vn_series, exit_date)["close"]
        if vn_exit_p > 0.0:
            vn_ret = round(((vn_exit_p - vn_open_t1) / vn_open_t1) * 100.0, 3)

    return exec_ret, vn_ret, exit_floor_locked, ceil_exit, floor_exit


def _calculate_record_payload(
    rec: dict[str, Any],
    series_map: dict[str, dict[str, Any]],
) -> dict[str, Any] | None:
    """Compute institutional forward returns payload with dual signal & executable modes."""
    dec_id = rec.get("decision_id")
    sym = rec.get("symbol", "").upper().strip()
    if not dec_id or not sym or sym not in series_map:
        return None

    sym_series = series_map[sym]
    dates = sym_series["dates"]
    if not dates:
        return None

    raw_date = str(rec.get("created_at") or rec.get("decision_time") or "")[:10]
    matching_idx = _find_matching_index(dates, raw_date)
    if matching_idx is None:
        return None

    # Baseline price anchors
    date_t0 = dates[matching_idx]
    p_t0 = _extract_price_point(sym_series, date_t0)
    p_close_t0 = p_t0["close"]
    if p_close_t0 <= 0.0:
        facts = rec.get("facts", {}) or {}
        p_close_t0 = float(facts.get("snapshot_price") or facts.get("price") or 0.0)
    if p_close_t0 <= 0.0:
        return None

    vn_series = series_map.get(SYM_VNINDEX, {})
    vn_close_t0 = _extract_price_point(vn_series, date_t0)["close"] if vn_series else 0.0

    # T+1 anchors for executable returns
    has_t1 = (matching_idx + 1) < len(dates)
    date_t1 = dates[matching_idx + 1] if has_t1 else None
    p_open_t1 = _extract_price_point(sym_series, date_t1)["open"] if date_t1 else 0.0
    p_close_t1 = _extract_price_point(sym_series, date_t1)["close"] if date_t1 else 0.0
    vn_open_t1 = _extract_price_point(vn_series, date_t1)["open"] if date_t1 and vn_series else 0.0

    exchange, _ = get_symbol_profile(sym)

    # Entry Ceiling and Floor Check on T+1 (based on close_t0)
    ceil_t1, floor_t1 = calc_exchange_ceiling_floor(p_close_t0, exchange)
    entry_ceiling_locked = (p_open_t1 >= ceil_t1 - 1e-4) if p_open_t1 > 0 else False

    ceilings: dict[int, float | None] = {1: ceil_t1}
    floors: dict[int, float | None] = {1: floor_t1}

    signal_returns: dict[int, float | None] = {}
    executable_returns: dict[int, float | None] = {}
    vn_signal_returns: dict[int, float | None] = {}
    vn_exec_returns: dict[int, float | None] = {}
    exit_dates: dict[int, str | None] = {}
    exit_prices: dict[int, float | None] = {}
    vn_exit_prices: dict[int, float | None] = {}
    exit_floor_locks: dict[int, bool] = {}
    matured_horizons = []

    for h in HORIZONS:
        s_ret, vn_s_ret, ex_date, ex_p, vn_ex_p = _compute_signal_horizon(
            dates, sym_series, vn_series, matching_idx, h, p_close_t0, vn_close_t0
        )
        signal_returns[h] = s_ret
        vn_signal_returns[h] = vn_s_ret
        exit_dates[h] = ex_date
        exit_prices[h] = ex_p
        vn_exit_prices[h] = vn_ex_p

        e_ret, vn_e_ret, e_floor_locked, ceil_h, floor_h = _compute_executable_horizon(
            dates, sym_series, vn_series, matching_idx, h, p_open_t1, vn_open_t1, exchange=exchange
        )
        executable_returns[h] = e_ret
        vn_exec_returns[h] = vn_e_ret
        exit_floor_locks[h] = e_floor_locked
        if ceil_h is not None:
            ceilings[h] = ceil_h
            floors[h] = floor_h

        if s_ret is not None or e_ret is not None:
            matured_horizons.append(h)

    # Legacy snapshot fallback if ohlc is not present
    snap_price = float((rec.get("facts") or {}).get("snapshot_price") or p_close_t0)
    has_real_ohlc = bool(sym_series.get("ohlc"))

    # In database decision_forward_returns table, populate executable returns when real OHLC exists
    # Fallback to signal returns if execution entry or OHLC is not available
    def _pick_ret(h: int) -> float | None:
        if has_real_ohlc and executable_returns.get(h) is not None:
            return executable_returns.get(h)
        return signal_returns.get(h)

    def _pick_vn(h: int) -> float | None:
        if has_real_ohlc and vn_exec_returns.get(h) is not None:
            return vn_exec_returns.get(h)
        return vn_signal_returns.get(h)

    return {
        "decision_id": dec_id,
        "symbol": sym,
        "snapshot_price": snap_price,
        "entry_date_signal": date_t0,
        "entry_date_exec": date_t1,
        "close_t0": p_close_t0,
        "open_t1": p_open_t1 if date_t1 else None,
        "close_t1": p_close_t1 if date_t1 else None,
        "vn_close_t0": vn_close_t0 if vn_series and vn_close_t0 > 0 else None,
        "vn_open_t1": vn_open_t1 if date_t1 and vn_series and vn_open_t1 > 0 else None,
        "vn_close_t1": (
            _extract_price_point(vn_series, date_t1)["close"]
            if date_t1 and vn_series
            else None
        ),
        "entry_ceiling_locked": entry_ceiling_locked,
        "exit_floor_locks": exit_floor_locks,
        "ceilings": ceilings,
        "floors": floors,
        "matured_horizons": matured_horizons,
        "signal_returns": signal_returns,
        "executable_returns": executable_returns,
        "vnindex_signal": vn_signal_returns,
        "vnindex_executable": vn_exec_returns,
        "exit_dates": exit_dates,
        "exit_prices": exit_prices,
        "vn_exit_prices": vn_exit_prices,
        "t1_return_pct": _pick_ret(1),
        "t3_return_pct": _pick_ret(3),
        "t5_return_pct": _pick_ret(5),
        "t10_return_pct": _pick_ret(10),
        "t20_return_pct": _pick_ret(20),
        "vnindex_t5_pct": _pick_vn(5),
        "vnindex_t20_pct": _pick_vn(20),
    }


def _load_valuation_events_map() -> dict[str, dict[str, Any]]:
    """Load valuation events and return a mapping by uppercase symbol."""
    candidates = [
        os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "valuation_events.csv"),
        "data/valuation_events.csv",
    ]
    path = next((p for p in candidates if os.path.exists(p)), None)
    if not path:
        return {}
    try:
        vdf = pd.read_csv(path)
        evt_map = {}
        for _, vrow in vdf.iterrows():
            s = str(vrow.get("symbol", "")).upper().strip()
            if s:
                evt_map[s] = {
                    "event_id": vrow.get("event_id"),
                    "bctc_published_date": str(vrow.get("bctc_published_date", "")).strip()[:10],
                    "event_date": str(vrow.get("event_date", "")).strip()[:10],
                    "event_type": vrow.get("event_type"),
                    "corporate_action": vrow.get("corporate_action"),
                }
        return evt_map
    except Exception:
        return {}


def _assemble_evaluation_row(rec: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    """Assemble a single fully-auditable evaluation row."""
    sym = payload["symbol"]
    exchange, sector = get_symbol_profile(sym)
    facts = rec.get("facts") or {}
    logic_ver = rec.get("logic_version") or facts.get("logic_version", DEFAULT_LOGIC_VERSION)

    matured_set = set(payload.get("matured_horizons", []))
    sig_t1 = payload["signal_returns"].get(1)
    vn_sig_t1 = payload["vnindex_signal"].get(1)
    exec_t1 = payload["executable_returns"].get(1)
    vn_exec_t1 = payload["vnindex_executable"].get(1)

    excess_sig_t1 = round(sig_t1 - vn_sig_t1, 3) if sig_t1 is not None and vn_sig_t1 is not None else None
    excess_exec_t1 = round(exec_t1 - vn_exec_t1, 3) if exec_t1 is not None and vn_exec_t1 is not None else None
    gap_pp = round(exec_t1 - sig_t1, 3) if exec_t1 is not None and sig_t1 is not None else None
    large_gap = abs(gap_pp) >= LARGE_GAP_THRESHOLD_PP if gap_pp is not None else False

    sig_t3 = payload["signal_returns"].get(3)
    vn_sig_t3 = payload["vnindex_signal"].get(3)
    exec_t3 = payload["executable_returns"].get(3)
    vn_exec_t3 = payload["vnindex_executable"].get(3)
    excess_sig_t3 = round(sig_t3 - vn_sig_t3, 3) if sig_t3 is not None and vn_sig_t3 is not None else None
    excess_exec_t3 = round(exec_t3 - vn_exec_t3, 3) if exec_t3 is not None and vn_exec_t3 is not None else None
    gap_t3_pp = round(exec_t3 - sig_t3, 3) if exec_t3 is not None and sig_t3 is not None else None

    sig_t5 = payload["signal_returns"].get(5)
    vn_sig_t5 = payload["vnindex_signal"].get(5)
    exec_t5 = payload["executable_returns"].get(5)
    vn_exec_t5 = payload["vnindex_executable"].get(5)
    excess_sig_t5 = round(sig_t5 - vn_sig_t5, 3) if sig_t5 is not None and vn_sig_t5 is not None else None
    excess_exec_t5 = round(exec_t5 - vn_exec_t5, 3) if exec_t5 is not None and vn_exec_t5 is not None else None
    gap_t5_pp = round(exec_t5 - sig_t5, 3) if exec_t5 is not None and sig_t5 is not None else None

    exit_prices = payload.get("exit_prices", {})
    vn_exit_prices = payload.get("vn_exit_prices", {})
    exit_floor_locks = payload.get("exit_floor_locks", {})
    ceilings = payload.get("ceilings", {})
    floors = payload.get("floors", {})

    ceil_t1 = ceilings.get(1)
    floor_t1 = floors.get(1)
    ceil_t3 = ceilings.get(3) if 3 in matured_set else None
    floor_t3 = floors.get(3) if 3 in matured_set else None
    ceil_t5 = ceilings.get(5) if 5 in matured_set else None
    floor_t5 = floors.get(5) if 5 in matured_set else None

    val_map = _load_valuation_events_map()
    sym_evt = val_map.get(sym.upper().strip())
    bctc_pub_date = sym_evt.get("bctc_published_date") if sym_evt else None

    t0_date = str(payload.get("entry_date_signal") or "")[:10]
    matured_dates = [payload["exit_dates"][h] for h in matured_set if h in payload.get("exit_dates", {})]
    max_matured_date = max(matured_dates) if matured_dates else None

    crosses_val_evt = False
    if bctc_pub_date and max_matured_date and t0_date:
        crosses_val_evt = bool(t0_date < bctc_pub_date <= max_matured_date)

    return {
        "decision_id": payload["decision_id"],
        "symbol": sym,
        "decision": rec.get("decision"),
        "exchange": exchange,
        "sector": sector,
        "logic_version": logic_ver,
        "calc_version": CALC_VERSION,
        "price_adjusted": True,
        "entry_date_t0": payload["entry_date_signal"],
        "close_t0": payload["close_t0"],
        "entry_date_t1": payload["entry_date_exec"],
        "open_t1": payload["open_t1"],
        "close_t1": payload["close_t1"],
        "close_t3": exit_prices.get(3),
        "close_t5": exit_prices.get(5),
        "vn_close_t0": payload.get("vn_close_t0"),
        "vn_open_t1": payload.get("vn_open_t1"),
        "vn_close_t1": payload.get("vn_close_t1"),
        "vn_close_t3": vn_exit_prices.get(3),
        "vn_close_t5": vn_exit_prices.get(5),
        "ceiling_price": ceil_t1,
        "floor_price": floor_t1,
        "ceiling_price_t1": ceil_t1,
        "floor_price_t1": floor_t1,
        "ceiling_price_t3": ceil_t3,
        "floor_price_t3": floor_t3,
        "ceiling_price_t5": ceil_t5,
        "floor_price_t5": floor_t5,
        "matured_t1": 1 in matured_set,
        "matured_t3": 3 in matured_set,
        "matured_t5": 5 in matured_set,
        "matured_t10": 10 in matured_set,
        "matured_t20": 20 in matured_set,
        "entry_ceiling_locked_t1": payload["entry_ceiling_locked"],
        "exit_floor_locked_t1": exit_floor_locks.get(1, False),
        "exit_floor_locked_t3": exit_floor_locks.get(3, False),
        "exit_floor_locked_t5": exit_floor_locks.get(5, False),
        "signal_t1_pct": sig_t1,
        "vn_signal_t1_pct": vn_sig_t1,
        "excess_signal_t1_pct": excess_sig_t1,
        "exec_t1_pct": exec_t1,
        "vn_exec_t1_pct": vn_exec_t1,
        "excess_exec_t1_pct": excess_exec_t1,
        "gap_exec_vs_signal_pp": gap_pp,
        "signal_t3_pct": sig_t3,
        "vn_signal_t3_pct": vn_sig_t3,
        "excess_signal_t3_pct": excess_sig_t3,
        "exec_t3_pct": exec_t3,
        "vn_exec_t3_pct": vn_exec_t3,
        "excess_exec_t3_pct": excess_exec_t3,
        "gap_exec_vs_signal_t3_pp": gap_t3_pp,
        "signal_t5_pct": sig_t5,
        "vn_signal_t5_pct": vn_sig_t5,
        "excess_signal_t5_pct": excess_sig_t5,
        "exec_t5_pct": exec_t5,
        "vn_exec_t5_pct": vn_exec_t5,
        "excess_exec_t5_pct": excess_exec_t5,
        "gap_exec_vs_signal_t5_pp": gap_t5_pp,
        "large_overnight_gap": large_gap,
        "est_fee_tax_pct": EST_TRANSACTION_FEE_PCT,
        "crosses_valuation_event": crosses_val_evt,
        "bctc_published_date": bctc_pub_date,
    }


def _calculate_benchmarks_and_excess(df: pd.DataFrame) -> pd.DataFrame:
    """Calculate universe EW and sector leave-one-out benchmarks for matured horizons."""
    if df.empty:
        return df

    for h in (1, 3, 5):
        m_col = f"matured_t{h}"
        e_col = f"exec_t{h}_pct"
        u_bench_col = f"universe_exec_t{h}_pct"
        u_excess_col = f"excess_vs_universe_t{h}_pct"
        s_bench_col = f"sector_exec_t{h}_pct"
        s_excess_col = f"excess_vs_sector_t{h}_pct"

        df[u_bench_col] = None
        df[u_excess_col] = None
        df[s_bench_col] = None
        df[s_excess_col] = None

        if m_col not in df.columns or e_col not in df.columns:
            continue

        mask = df[m_col].fillna(False).astype(bool) & df[e_col].notna()
        if not mask.any():
            continue

        # Universe benchmark: equal-weighted mean across all matured universe stocks
        u_mean = round(float(df.loc[mask, e_col].mean()), 3)
        df.loc[mask, u_bench_col] = u_mean
        df.loc[mask, u_excess_col] = (df.loc[mask, e_col] - u_mean).round(3)

        # Sector leave-one-out (LOO) benchmark:
        # Peer average excluding self; recorded as None/NaN when sector count < 3.
        sub = df.loc[mask, ["sector", e_col]].copy()
        sec_counts = sub.groupby("sector")[e_col].transform("count")
        sec_sums = sub.groupby("sector")[e_col].transform("sum")

        eligible = sec_counts >= 3
        if eligible.any():
            peer_counts = sec_counts[eligible] - 1
            peer_means = ((sec_sums[eligible] - sub.loc[eligible, e_col]) / peer_counts).round(3)
            peer_excess = (sub.loc[eligible, e_col] - peer_means).round(3)

            df.loc[peer_means.index, s_bench_col] = peer_means
            df.loc[peer_excess.index, s_excess_col] = peer_excess

    # Latest horizon aliases with explicit _latest suffix and latest_horizon indicator
    latest_h = None
    for h in (5, 3, 1):
        m_col = f"matured_t{h}"
        if m_col in df.columns and df[m_col].fillna(False).astype(bool).any():
            latest_h = h
            break

    if latest_h is not None:
        df["latest_horizon"] = f"T+{latest_h}"
        df["excess_vs_universe_latest"] = df[f"excess_vs_universe_t{latest_h}_pct"]
        df["excess_vs_sector_latest"] = df[f"excess_vs_sector_t{latest_h}_pct"]
    else:
        df["latest_horizon"] = None
        df["excess_vs_universe_latest"] = None
        df["excess_vs_sector_latest"] = None

    return df


def simulate_sector_stratified_baseline(
    df: pd.DataFrame,
    horizon: int = 1,
    n_simulations: int = 5000,
    seed: int | None = 42,
) -> dict[str, Any] | None:
    """Evaluate whether WATCH outperformance exceeds chance given sector composition.

    Draws random portfolios with the exact same sector composition as the WATCH group
    to isolate true within-sector selection alpha from sector allocation / luck.
    """
    m_col = f"matured_t{horizon}"
    e_col = f"exec_t{horizon}_pct"
    if m_col not in df.columns or e_col not in df.columns:
        return None

    mask = df[m_col].fillna(False).astype(bool) & df[e_col].notna()
    sub_df = df.loc[mask]
    if sub_df.empty or "decision" not in sub_df.columns or "sector" not in sub_df.columns:
        return None

    w_mask = sub_df["decision"] == DECISION_WATCH
    r_mask = sub_df["decision"] == DECISION_REJECT
    if not w_mask.any() or not r_mask.any():
        return None

    w_ret = float(sub_df.loc[w_mask, e_col].mean())
    r_ret = float(sub_df.loc[r_mask, e_col].mean())
    obs_spread = w_ret - r_ret
    u_mean = float(sub_df[e_col].mean())

    sector_w_counts = sub_df.loc[w_mask, "sector"].value_counts().to_dict()
    sectors_data = {
        s: sub_df.loc[sub_df["sector"] == s, e_col].to_numpy(dtype=float)
        for s in sub_df["sector"].unique()
    }

    if seed is not None:
        np.random.seed(seed)

    strat_w_list = []
    strat_spread_list = []
    for _ in range(n_simulations):
        sim_w = []
        sim_r = []
        for s, vals in sectors_data.items():
            k = sector_w_counts.get(s, 0)
            if k > 0:
                perm = np.random.permutation(vals)
                sim_w.extend(perm[:k])
                sim_r.extend(perm[k:])
            else:
                sim_r.extend(vals)
        mean_sw = float(np.mean(sim_w))
        mean_sr = float(np.mean(sim_r))
        strat_w_list.append(mean_sw)
        strat_spread_list.append(mean_sw - mean_sr)

    strat_w = np.array(strat_w_list)
    strat_spread = np.array(strat_spread_list)

    p_w = float(np.mean(strat_w >= w_ret))
    p_spread = float(np.mean(strat_spread >= obs_spread))
    strat_w_mean = float(np.mean(strat_w))

    return {
        "horizon": f"T+{horizon}",
        "n_watch": int(w_mask.sum()),
        "n_reject": int(r_mask.sum()),
        "universe_mean": round(u_mean, 3),
        "watch_mean": round(w_ret, 3),
        "reject_mean": round(r_ret, 3),
        "observed_spread": round(obs_spread, 3),
        "strat_watch_median": round(float(np.median(strat_w)), 3),
        "strat_watch_iqr": (
            round(float(np.percentile(strat_w, 25)), 3),
            round(float(np.percentile(strat_w, 75)), 3),
        ),
        "selection_alpha_vs_sector_baseline": round(w_ret - strat_w_mean, 3),
        "p_value_watch_return": round(p_w, 4),
        "strat_spread_median": round(float(np.median(strat_spread)), 3),
        "strat_spread_iqr": (
            round(float(np.percentile(strat_spread, 25)), 3),
            round(float(np.percentile(strat_spread, 75)), 3),
        ),
        "p_value_spread": round(p_spread, 4),
    }


def evaluate_date_batch(
    target_date: str = "2026-10-14",
    series_map: dict[str, dict[str, Any]] | None = None,
) -> pd.DataFrame:
    """Evaluate canonical decisions for a specific target day and export rich comparison table."""
    client = get_supabase_client()
    canonical_recs: list[dict[str, Any]] = []

    if client:
        res = (
            client.table("decision_records")
            .select("*")
            .gte("created_at", f"{target_date}T00:00:00")
            .lte("created_at", f"{target_date}T23:59:59")
            .execute()
        )
        raw_records = res.data or []
        canonical_recs = filter_canonical_and_deduplicate(raw_records)

    # Fallback to local snapshot if client returned no data
    if not canonical_recs:
        local_csv = f"decision_records_{target_date.replace('-', '')}.csv"
        if os.path.exists(local_csv):
            import json

            logging.info("Reading canonical records from local file %s", local_csv)
            raw_df = pd.read_csv(local_csv)
            raw_records = []
            for _, r in raw_df.iterrows():
                r_dict = r.to_dict()
                if isinstance(r_dict.get("facts"), str):
                    try:
                        r_dict["facts"] = json.loads(r_dict["facts"])
                    except Exception:
                        pass
                raw_records.append(r_dict)
            canonical_recs = filter_canonical_and_deduplicate(raw_records)

    logging.info("Found %d canonical records for target date %s", len(canonical_recs), target_date)
    if not canonical_recs:
        return pd.DataFrame()

    if series_map is None:
        symbols = {r["symbol"] for r in canonical_recs if r.get("symbol")}
        start_date = (datetime.strptime(target_date, "%Y-%m-%d") - timedelta(days=10)).strftime("%Y-%m-%d")
        end_date = datetime.now().strftime("%Y-%m-%d")
        series_map = _build_price_series(symbols, start_date=start_date, end_date=end_date)

    rows = []
    for r in canonical_recs:
        p = _calculate_record_payload(r, series_map)
        if not p:
            continue
        rows.append(_assemble_evaluation_row(r, p))

    df = pd.DataFrame(rows)
    df = _calculate_benchmarks_and_excess(df)

    csv_path = f"canonical_forward_returns_{target_date.replace('-', '')}.csv"
    df.to_csv(csv_path, index=False)
    logging.info("Saved %d evaluation rows to %s", len(df), csv_path)
    return df


def update_all_decision_forward_returns(limit: int = 2000) -> int:
    """Fetch deduplicated decision records, calculate institutional forward returns, and update DB."""
    client = get_supabase_client()
    if not client:
        logging.error("Supabase client is not available.")
        return 0

    res = client.table("decision_records").select("*").order("created_at", desc=False).limit(limit).execute()
    raw_records = res.data or []
    if not raw_records:
        logging.info("No decision records found.")
        return 0

    records = filter_canonical_and_deduplicate(raw_records)
    logging.info("Fetched %d raw records -> %d deduplicated canonical records.", len(raw_records), len(records))

    symbols = {r["symbol"].upper().strip() for r in records if r.get("symbol")}
    start_date = (datetime.now() - timedelta(days=90)).strftime("%Y-%m-%d")
    end_date = datetime.now().strftime("%Y-%m-%d")

    logging.info("Fetching price series from %s to %s for %d symbols...", start_date, end_date, len(symbols))
    series_map = _build_price_series(symbols, start_date=start_date, end_date=end_date)

    fwd_res = client.table("decision_forward_returns").select("decision_id").limit(5000).execute()
    existing_fwd_ids = {f["decision_id"] for f in (fwd_res.data or []) if f.get("decision_id")}

    inserts = []
    updates = 0

    for rec in records:
        payload = _calculate_record_payload(rec, series_map)
        if not payload:
            continue

        dec_id = payload["decision_id"]
        # Prepare DB compatible row
        row = {
            "decision_id": dec_id,
            "symbol": payload["symbol"],
            "snapshot_price": payload["snapshot_price"],
            "t1_return_pct": payload["t1_return_pct"],
            "t3_return_pct": payload["t3_return_pct"],
            "t5_return_pct": payload["t5_return_pct"],
            "t10_return_pct": payload["t10_return_pct"],
            "t20_return_pct": payload["t20_return_pct"],
            "vnindex_t5_pct": payload["vnindex_t5_pct"],
            "vnindex_t20_pct": payload["vnindex_t20_pct"],
        }

        if dec_id in existing_fwd_ids:
            if update_decision_forward_returns(dec_id, row):
                updates += 1
        else:
            inserts.append(row)

    new_inserts_count = 0
    batch_size = 100
    for i in range(0, len(inserts), batch_size):
        chunk = inserts[i : i + batch_size]
        try:
            ins_res = client.table("decision_forward_returns").insert(chunk).execute()
            if ins_res.data:
                new_inserts_count += len(ins_res.data)
        except Exception:
            logging.exception("Failed to insert chunk %d..%d into decision_forward_returns", i, i + len(chunk))

    total_processed = new_inserts_count + updates
    logging.info(
        "Forward returns processing complete: %d inserted, %d updated (Total: %d).",
        new_inserts_count,
        updates,
        total_processed,
    )
    return total_processed


def print_date_summary(target_date: str, df: pd.DataFrame) -> None:
    """Print readable summary of forward returns for a specific date."""
    if df.empty:
        return
    print(f"\n{'=' * 75}")
    print(f"=== TONG HOP FORWARD RETURNS CHO NGAY {target_date} ({len(df)} ma Universe) ===")
    print(f"{'=' * 75}")

    matured = []
    for h in HORIZONS:
        col = f"matured_t{h}"
        if col in df.columns and bool(df[col].iloc[0]):
            matured.append(f"T+{h}")
    print(f"[*] Cac moc da truong thanh (Matured): {', '.join(matured) if matured else 'Chua co moc nao'}")

    for h in (1, 3, 5):
        m_col = f"matured_t{h}"
        if m_col in df.columns and bool(df[m_col].iloc[0]):
            vn_sig = df[f"vn_signal_t{h}_pct"].iloc[0] if f"vn_signal_t{h}_pct" in df.columns else 0.0
            vn_exec = df[f"vn_exec_t{h}_pct"].iloc[0] if f"vn_exec_t{h}_pct" in df.columns else 0.0
            u_exec = df[f"universe_exec_t{h}_pct"].iloc[0] if f"universe_exec_t{h}_pct" in df.columns else 0.0
            print(f"[*] Moc T+{h}: VN-Index Exec = {vn_exec:+.2f}% (Signal {vn_sig:+.2f}%) | Universe 55 Equal-Weight Exec = {u_exec:+.2f}%")

    print("\n--- Hieu suat theo Quyet dinh (WATCH vs REJECT) ---")
    cols_to_show = [
        c
        for c in [
            "exec_t1_pct",
            "excess_vs_universe_t1_pct",
            "excess_exec_t1_pct",
            "exec_t3_pct",
            "excess_vs_universe_t3_pct",
            "excess_exec_t3_pct",
            "exec_t5_pct",
            "excess_vs_universe_t5_pct",
            "excess_exec_t5_pct",
        ]
        if c in df.columns and df[c].notna().any()
    ]
    if cols_to_show:
        summary_tbl = df.groupby("decision")[cols_to_show].mean().round(3)
        print(summary_tbl.to_string())

        # Print spread WATCH minus REJECT
        if DECISION_WATCH in summary_tbl.index and DECISION_REJECT in summary_tbl.index:
            for h in (1, 3, 5):
                e_col = f"exec_t{h}_pct"
                if e_col in summary_tbl.columns:
                    w_val = summary_tbl.loc[DECISION_WATCH, e_col]
                    r_val = summary_tbl.loc[DECISION_REJECT, e_col]
                    spread = round(w_val - r_val, 3)
                    print(f"[*] Spread WATCH - REJECT (T+{h} Exec): {w_val:+.2f}% - ({r_val:+.2f}%) = {spread:+.2f} pp")

    _print_sector_stratified_summary(df)


def _print_sector_stratified_summary(df: pd.DataFrame) -> None:
    """Print statistical significance results vs sector-stratified baseline."""
    print("\n--- Kiem Dinh Thong Ke May Rui: Nhom Ngau Nhien Cung Co Cau Nganh (Sector-Stratified Baseline) ---")
    for h in (1, 3, 5):
        sim = simulate_sector_stratified_baseline(df, horizon=h, n_simulations=5000)
        if not sim:
            continue
        p_val = sim["p_value_watch_return"]
        signif_label = "Co y nghia thong ke (p < 0.05)" if p_val < 0.05 else "Chua vuot nguong thong ke (p >= 0.05)"
        iqr_lo, iqr_hi = sim["strat_watch_iqr"]
        print(
            f"[*] Moc T+{h} ({sim['n_watch']} WATCH vs {sim['n_reject']} REJECT):\n"
            f"    - Spread Quan Sat (WATCH - REJECT): {sim['observed_spread']:+.2f} pp\n"
            f"    - Ngau Nhien Cung Co Cau Nganh: Median = {sim['strat_watch_median']:+.2f}% "
            f"(IQR [{iqr_lo:+.2f}%, {iqr_hi:+.2f}%])\n"
            f"    - Selection Alpha Noi Nganh: {sim['selection_alpha_vs_sector_baseline']:+.2f} pp "
            f"(p-value = {p_val:.4f} -> {signif_label})"
        )


def run_pipeline(target_dates: list[str] | None = None, sync_db: bool = True) -> None:
    """Run full forward returns pipeline, export canonical CSVs, and update DB."""
    client = get_supabase_client()
    if not client:
        logging.error("Supabase client is not available.")
        return

    # Determine dates to process
    if not target_dates:
        res = (
            client.table("decision_records")
            .select("created_at")
            .gte("created_at", f"{CANONICAL_CUTOFF_DATE}T00:00:00")
            .order("created_at", desc=False)
            .limit(5000)
            .execute()
        )
        dates_raw = {str(r["created_at"])[:10] for r in (res.data or []) if r.get("created_at")}
        target_dates = sorted(list(dates_raw))

    if not target_dates:
        target_dates = ["2026-10-14", "2026-10-15"]

    logging.info("Processing forward returns for dates: %s", target_dates)

    symbols = set(UNIVERSE_METADATA.keys())
    start_date = (datetime.strptime(min(target_dates), "%Y-%m-%d") - timedelta(days=15)).strftime("%Y-%m-%d")
    end_date = datetime.now().strftime("%Y-%m-%d")
    series_map = _build_price_series(symbols, start_date=start_date, end_date=end_date)

    for d in target_dates:
        df_d = evaluate_date_batch(d, series_map=series_map)
        print_date_summary(d, df_d)

    if sync_db:
        update_all_decision_forward_returns()


def _normalize_date(date_str: str) -> str:
    """Normalize date string to YYYY-MM-DD format (supports YYYYMMDD and YYYY-MM-DD)."""
    s = date_str.strip()
    if len(s) == 8 and s.isdigit():
        return f"{s[:4]}-{s[4:6]}-{s[6:]}"
    try:
        dt = datetime.strptime(s, "%Y-%m-%d")
        return dt.strftime("%Y-%m-%d")
    except ValueError:
        logging.warning("Invalid date format: '%s'. Expected YYYY-MM-DD or YYYYMMDD.", date_str)
        return s


def main() -> None:
    """CLI entrypoint with argument parsing."""
    parser = argparse.ArgumentParser(description="Institutional forward returns calculator & CSV exporter.")
    parser.add_argument(
        "dates",
        nargs="*",
        help="Optional date(s) to evaluate (e.g. 2026-10-14 2026-10-15 or 20261014 20261015). If omitted, evaluates all canonical dates.",
    )
    parser.add_argument("--date", type=str, default=None, help="Specific date to evaluate (YYYY-MM-DD or YYYYMMDD)")
    parser.add_argument("--skip-db", action="store_true", help="Skip updating Supabase DB table")
    args = parser.parse_args()

    target_dates = []
    if args.date:
        target_dates.append(_normalize_date(args.date))
    if args.dates:
        target_dates.extend([_normalize_date(d) for d in args.dates if not d.startswith("-")])

    run_pipeline(target_dates=target_dates if target_dates else None, sync_db=not args.skip_db)


if __name__ == "__main__":
    main()
