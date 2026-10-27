# -*- coding: utf-8 -*-
"""Enrich canonical forward returns files with valuation events and point-in-time ADV20 as-of metadata."""

import glob
import json
import logging
import os
from typing import Any

import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

VAL_CSV = "data/valuation_events.csv"
TECH_PATH = "data/last_known_tech.json"
BASE_ASOF_DATE = "2026-10-13"

# Horizons for each cohort T0
TARGET_DATES_HORIZONS: dict[str, dict[int, str]] = {
    "20261014": {1: "2026-10-15", 3: "2026-10-19", 5: "2026-10-21"},
    "20261015": {1: "2026-10-16", 3: "2026-10-20", 5: "2026-10-22"},
    "20261016": {1: "2026-10-19", 3: "2026-10-21", 5: "2026-10-23"},
    "20261019": {1: "2026-10-20", 3: "2026-10-22", 5: "2026-10-26"},
    "20261020": {1: "2026-10-21", 3: "2026-10-23", 5: "2026-10-27"},
    "20261021": {1: "2026-10-22", 3: "2026-10-26", 5: "2026-10-28"},
    "20261022": {1: "2026-10-23", 3: "2026-10-27", 5: "2026-10-29"},
    "20261023": {1: "2026-10-26", 3: "2026-10-28", 5: "2026-10-30"},
    "20261026": {1: "2026-10-27", 3: "2026-10-29", 5: "2026-11-02"},
    "20261027": {1: "2026-10-28", 3: "2026-10-30", 5: "2026-11-03"},
}

# Maximum matured exit date as of 2026-10-26 close
TARGET_DATES_MAX_MATURED: dict[str, str | None] = {
    "20261014": "2026-10-21",  # T+5 matured 21/10
    "20261015": "2026-10-22",  # T+5 matured 22/10
    "20261016": "2026-10-23",  # T+5 matured 23/10
    "20261019": "2026-10-26",  # T+5 matured 26/10
    "20261020": "2026-10-23",  # T+3 matured 23/10
    "20261021": "2026-10-26",  # T+3 matured 26/10
    "20261022": "2026-10-23",  # T+1 matured 23/10
    "20261023": "2026-10-26",  # T+1 matured 26/10
    "20261026": None,          # 0 matured horizons as of 26/10 close
}


def load_valuation_events() -> dict[str, dict[str, Any]]:
    """Load valuation events map with published, detected, effective dates and event_timing_unknown flag."""
    events: dict[str, dict[str, Any]] = {}
    if not os.path.exists(VAL_CSV):
        return events

    try:
        val_df = pd.read_csv(VAL_CSV)
        for _, r in val_df.iterrows():
            s = str(r.get("symbol", "")).upper().strip()
            if not s:
                continue
            pub_raw = str(r.get("bctc_published_date", "")).strip()[:10]
            pub_d = pub_raw if pub_raw not in ("nan", "UNKNOWN", "") else None

            det_raw = str(r.get("bctc_detected_date", "")).strip()[:10]
            det_d = det_raw if det_raw not in ("nan", "UNKNOWN", "") else None

            effective_d = pub_d if pub_d else det_d
            timing_unk = bool(r.get("event_timing_unknown", True))

            events[s] = {
                "bctc_published_date": pub_d,
                "bctc_detected_date": det_d,
                "effective_date": effective_d,
                "event_timing_unknown": timing_unk,
            }
    except Exception:
        logging.exception("Failed to load valuation events from %s", VAL_CSV)

    return events


def load_base_adv20_map() -> dict[str, float]:
    """Load baseline ADV20 values from technical snapshot (as of 2026-10-13)."""
    adv_map: dict[str, float] = {}
    if not os.path.exists(TECH_PATH):
        return adv_map

    try:
        with open(TECH_PATH, "r", encoding="utf-8") as f:
            tdata = json.load(f)
            for sym, d in tdata.items():
                adv_map[sym.upper().strip()] = float(d.get("adv20_billion", 0.0))
    except Exception:
        logging.exception("Failed to load technical snapshot from %s", TECH_PATH)

    return adv_map


def load_all_snapshot_caches() -> dict[str, dict[str, tuple[float, str]]]:
    """Load all canonical raw snapshots to provide true point-in-time ADV20 values."""
    cache: dict[str, dict[str, tuple[float, str]]] = {}
    for f in sorted(glob.glob("data/raw_snapshots_*_canonical.json")):
        parts = os.path.basename(f).split("_")
        if len(parts) >= 3 and parts[2].isdigit():
            date_code = parts[2]
            try:
                with open(f, "r", encoding="utf-8") as fp:
                    items = json.load(fp)
                cache[date_code] = {}
                for item in items:
                    sym = str(item.get("symbol", "")).upper().strip()
                    rp = item.get("raw_price") or {}
                    adv = rp.get("adv20_billion")
                    asof = rp.get("price_asof")
                    if sym and adv is not None:
                        cache[date_code][sym] = (float(adv), str(asof)[:10])
            except Exception:
                logging.exception("Failed to load snapshot cache %s", f)
    return cache


def get_pit_adv20_for_symbol(
    sym: str,
    date_code: str,
    base_map: dict[str, float],
    snapshot_caches: dict[str, dict[str, tuple[float, str]]],
) -> tuple[float, str, bool]:
    """Get point-in-time ADV20, its as-of date, and fallback flag ensuring as_of <= T0."""
    t0_date = f"{date_code[:4]}-{date_code[4:6]}-{date_code[6:8]}"

    # 1. Check exact date snapshot
    if date_code in snapshot_caches and sym in snapshot_caches[date_code]:
        adv, asof = snapshot_caches[date_code][sym]
        if asof <= t0_date:
            is_fb = bool(asof != t0_date)
            return round(adv, 3), asof, is_fb

    # 2. Check latest available snapshot <= T0
    avail_dates = sorted([d for d in snapshot_caches if d <= date_code], reverse=True)
    for d in avail_dates:
        if sym in snapshot_caches[d]:
            adv, asof = snapshot_caches[d][sym]
            if asof <= t0_date:
                is_fb = bool(asof != t0_date)
                return round(adv, 3), asof, is_fb

    # 3. Fallback to baseline technical snapshot as of 2026-10-13
    base_adv = base_map.get(sym, 0.0)
    return round(base_adv, 3), BASE_ASOF_DATE, True


def _evaluate_symbol_event_crossing(
    t0_date: str,
    effective_d: str | None,
    h_dates: dict[int, str],
    max_mat_date: str | None,
) -> tuple[bool, bool, bool, bool]:
    """Compute crosses_t1, crosses_t3, crosses_t5, crosses_valuation_event."""
    if not effective_d:
        return False, False, False, False

    c1 = bool(1 in h_dates and t0_date < effective_d <= h_dates[1])
    c3 = bool(3 in h_dates and t0_date < effective_d <= h_dates[3])
    c5 = bool(5 in h_dates and t0_date < effective_d <= h_dates[5])
    c_val = bool(max_mat_date and t0_date < effective_d <= max_mat_date)
    return c1, c3, c5, c_val


def count_trading_session_lag(asof_date: str, t0_date: str) -> int:
    """Calculate the number of trading sessions lag between asof_date and t0_date."""
    if asof_date == t0_date:
        return 0
    trading_dates = [
        "2026-10-13",
        "2026-10-14",
        "2026-10-15",
        "2026-10-16",
        "2026-10-19",
        "2026-10-20",
        "2026-10-21",
        "2026-10-22",
        "2026-10-23",
        "2026-10-26",
        "2026-10-27",
    ]
    if asof_date in trading_dates and t0_date in trading_dates:
        return max(0, trading_dates.index(t0_date) - trading_dates.index(asof_date))
    try:
        rng = pd.bdate_range(start=asof_date, end=t0_date)
        return max(0, len(rng) - 1)
    except Exception:
        return 0


def count_event_offset_sessions(t0_date: str, effective_d: str | None) -> int | None:
    """Calculate the number of trading sessions between T0 and effective event date (positive = future, 0 = same day, negative = past)."""
    if not effective_d:
        return None
    trading_dates = [
        "2026-10-13",
        "2026-10-14",
        "2026-10-15",
        "2026-10-16",
        "2026-10-19",
        "2026-10-20",
        "2026-10-21",
        "2026-10-22",
        "2026-10-23",
        "2026-10-26",
        "2026-10-27",
        "2026-10-28",
        "2026-10-29",
        "2026-10-30",
        "2026-11-02",
    ]
    if t0_date in trading_dates and effective_d in trading_dates:
        return trading_dates.index(effective_d) - trading_dates.index(t0_date)
    try:
        b_range = pd.bdate_range(start=min(t0_date, effective_d), end=max(t0_date, effective_d))
        diff = len(b_range) - 1
        return diff if effective_d >= t0_date else -diff
    except Exception:
        return None


def reorder_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Reorder columns to position adv20_asof, adv20_age_sessions, adv20_is_fallback, event_timing_unknown, event_offset_sessions, and crosses_* audit flags cleanly."""
    drop_cols = {
        "adv20_value",
        "adv20_asof",
        "adv20_age_sessions",
        "adv20_is_fallback",
        "executable_size_ok",
        "crosses_t1",
        "crosses_t3",
        "crosses_t5",
        "crosses_valuation_event",
        "event_timing_unknown",
        "event_offset_sessions",
        "bctc_published_date",
        "bctc_detected_date",
    }
    cols = [c for c in df.columns if c not in drop_cols]
    if "large_overnight_gap" in cols:
        pos_gap = cols.index("large_overnight_gap") + 1
        cols = (
            cols[:pos_gap]
            + [
                "adv20_value",
                "adv20_asof",
                "adv20_age_sessions",
                "adv20_is_fallback",
                "executable_size_ok",
            ]
            + cols[pos_gap:]
        )
    if "est_fee_tax_pct" in cols:
        pos_fee = cols.index("est_fee_tax_pct") + 1
        cols = (
            cols[:pos_fee]
            + [
                "crosses_t1",
                "crosses_t3",
                "crosses_t5",
                "crosses_valuation_event",
                "event_timing_unknown",
                "event_offset_sessions",
                "bctc_published_date",
                "bctc_detected_date",
            ]
            + cols[pos_fee:]
        )
    return df[cols]


def enrich_forward_returns_file(
    date_code: str,
    h_dates: dict[int, str],
    max_mat_date: str | None,
    events_map: dict[str, dict[str, Any]],
    base_adv20_map: dict[str, float],
    snapshot_caches: dict[str, dict[str, tuple[float, str]]],
) -> None:
    """Enrich a single canonical forward returns CSV file."""
    csv_file = f"canonical_forward_returns_{date_code}.csv"
    if not os.path.exists(csv_file):
        logging.warning("Cohort file %s does not exist, skipping.", csv_file)
        return

    df = pd.read_csv(csv_file)
    t0_date = f"{date_code[:4]}-{date_code[4:6]}-{date_code[6:8]}"

    c1_list: list[bool] = []
    c3_list: list[bool] = []
    c5_list: list[bool] = []
    c_val_list: list[bool] = []
    timing_unk_list: list[bool] = []
    offset_list: list[int | None] = []
    pub_list: list[str | None] = []
    det_list: list[str | None] = []
    adv_list: list[float] = []
    asof_list: list[str] = []
    age_list: list[int] = []
    fb_list: list[bool] = []
    exec_ok_list: list[bool | None] = []

    for _, row in df.iterrows():
        sym = str(row.get("symbol", "")).upper().strip()
        evt = events_map.get(sym, {})
        pub_d = evt.get("bctc_published_date")
        det_d = evt.get("bctc_detected_date")
        effective_d = evt.get("effective_date")
        timing_unk = bool(evt.get("event_timing_unknown", False)) if effective_d else False

        adv, asof, is_fb = get_pit_adv20_for_symbol(sym, date_code, base_adv20_map, snapshot_caches)
        age = count_trading_session_lag(asof, t0_date)

        adv_list.append(adv)
        asof_list.append(asof)
        age_list.append(age)
        fb_list.append(is_fb)

        # For stale fallback >= 5 sessions (VTP, NVL, VIC), liquidity is UNKNOWN / None
        exec_ok = None if age >= 5 else bool(adv >= 2.0)
        exec_ok_list.append(exec_ok)

        offset_sessions = count_event_offset_sessions(t0_date, effective_d)
        offset_list.append(offset_sessions)

        pub_list.append(pub_d)
        det_list.append(det_d)
        timing_unk_list.append(timing_unk)

        c1, c3, c5, c_val = _evaluate_symbol_event_crossing(t0_date, effective_d, h_dates, max_mat_date)
        c1_list.append(c1)
        c3_list.append(c3)
        c5_list.append(c5)
        c_val_list.append(c_val)

    df["adv20_value"] = adv_list
    df["adv20_asof"] = asof_list
    df["adv20_age_sessions"] = age_list
    df["adv20_is_fallback"] = fb_list
    df["executable_size_ok"] = exec_ok_list
    df["crosses_t1"] = c1_list
    df["crosses_t3"] = c3_list
    df["crosses_t5"] = c5_list
    df["crosses_valuation_event"] = c_val_list
    df["event_timing_unknown"] = timing_unk_list
    df["event_offset_sessions"] = offset_list
    df["bctc_published_date"] = pub_list
    df["bctc_detected_date"] = det_list

    df = reorder_columns(df)
    df.to_csv(csv_file, index=False)

    t1_syms = [df.at[i, "symbol"] for i, val in enumerate(c1_list) if val]
    t3_syms = [df.at[i, "symbol"] for i, val in enumerate(c3_list) if val]
    t5_syms = [df.at[i, "symbol"] for i, val in enumerate(c5_list) if val]
    logging.info(
        "Enriched %s (%d rows): crosses_t1=%s, crosses_t3=%s, crosses_t5=%s",
        csv_file,
        len(df),
        t1_syms,
        t3_syms,
        t5_syms,
    )


def run_enrichment() -> None:
    """Enrich all canonical forward returns cohort files."""
    events_map = load_valuation_events()
    base_adv20_map = load_base_adv20_map()
    snapshot_caches = load_all_snapshot_caches()

    for date_code, h_dates in TARGET_DATES_HORIZONS.items():
        max_mat_date = TARGET_DATES_MAX_MATURED.get(date_code)
        enrich_forward_returns_file(date_code, h_dates, max_mat_date, events_map, base_adv20_map, snapshot_caches)


if __name__ == "__main__":
    run_enrichment()
