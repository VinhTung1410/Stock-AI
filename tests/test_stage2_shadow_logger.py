# -*- coding: utf-8 -*-
"""Regression and unit tests for Stage 2 Shadow Logger (scripts/stage2_shadow_logger.py)."""

from __future__ import annotations

import json
import os
import sys

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from scripts.stage2_shadow_logger import (
    EXPECTED_UNIVERSE_SIZE,
    GROUP_REJECT,
    GROUP_SHADOW,
    GROUP_WATCH_FAILED,
    MANIFEST_FILENAME,
    MARKET_LOG_FILENAME,
    ROLE_EXPLORATORY,
    ROLE_PROSPECTIVE,
    SCHEMA_VERSION,
    STOCK_LOG_FILENAME,
    run_stage2_shadow_logger,
)
from scripts.update_forward_returns import UNIVERSE_METADATA


def _make_mock_history(dates: list[str], base_price: float = 30.0, volume: float = 2_000_000.0, drop_last: bool = False) -> pd.DataFrame:
    """Create deterministic upward/flat OHLCV history ending on dates[-1] (or dates[-2] if halted)."""
    used_dates = dates[:-1] if drop_last else dates
    n = len(used_dates)
    closes = [base_price * (1.0 + 0.002 * i) for i in range(n)]
    return pd.DataFrame({
        "date": used_dates,
        "open": closes,
        "high": [c * 1.01 for c in closes],
        "low": [c * 0.99 for c in closes],
        "close": closes,
        "volume": [volume] * n,
    })


def _make_55_decision_csv(tmp_dir: str, date_t0: str, symbols: list[str]) -> str:
    """Create synthetic 55-symbol EOD_CANONICAL decision_records CSV."""
    rows = []
    for idx, sym in enumerate(symbols):
        if idx == 0:
            dec, conv, mos, gates = "WATCH", 85.0, 35.0, "TECH_CONFIRMATION"
            reason = "Cơ bản tốt (MoS +35.0%), Conviction 85/100 nhưng chờ tín hiệu xác nhận dòng tiền."
        elif idx == 1:
            dec, conv, mos, gates = "WATCH", 55.0, 25.0, "TECH_CONFIRMATION"
            reason = "Cơ bản tốt (MoS +25.0%), Conviction 55/100 nhưng giá dưới MA100 (20.0), RSI yếu (38.0)."
        else:
            dec, conv, mos, gates = "REJECT", 40.0, 5.0, "GATE_MOS"
            reason = "Biên an toàn MoS thấp."
        rows.append({
            "symbol": sym,
            "session": "EOD_CANONICAL",
            "decision": dec,
            "conviction": conv,
            "mos_pct": mos,
            "gates_failed": gates,
            "primary_rejection_gate": "TECH_CONFIRMATION" if dec == "WATCH" else "RISK_TRAP",
            "rejection_reasons": reason,
            "informative": True,
            "is_canonical": True,
            "logic_version": "v15.0_frozen_20261013",
            "git_sha": "106e6c61af",
            "facts": json.dumps({"universe_hash": "hash55test"}),
        })
    d_code = date_t0.replace("-", "")
    fpath = os.path.join(tmp_dir, f"decision_records_{d_code}.csv")
    pd.DataFrame(rows).to_csv(fpath, index=False)
    return fpath


def test_post_holiday_halted_ticker_and_idempotent_reruns(tmp_path: object) -> None:
    """Mandatory regression test covering post-holiday execution, halted ticker missing_reason, and idempotent re-run."""
    tmp_dir = str(tmp_path)
    out_dir = os.path.join(tmp_dir, "stage2_shadow")
    symbols = sorted(list(UNIVERSE_METADATA.keys()))[:EXPECTED_UNIVERSE_SIZE]

    # Build calendar skipping holiday 2026-11-24 -> post-holiday 2026-11-25, plus 2026-11-26
    bdays = [d.strftime("%Y-%m-%d") for d in pd.bdate_range("2026-06-01", "2026-11-26")]
    trading_days = [d for d in bdays if d != "2026-11-24"]

    # Create EOD CSV for 2026-11-26 (First Stage-2 prospective session)
    _make_55_decision_csv(tmp_dir, "2026-11-26", symbols)

    halted_sym = symbols[2]  # Simulate halted ticker on 2026-11-26

    def mock_fetcher(symbol: str, days: int = 180) -> pd.DataFrame:
        if symbol == "VNINDEX":
            # Downtrend below MA200
            n = len(trading_days)
            closes = np.linspace(1800.0, 1690.0, n)
            return pd.DataFrame({"date": trading_days, "close": closes, "volume": [500_000_000.0] * n})
        return _make_mock_history(trading_days, drop_last=(symbol == halted_sym))

    # 1. Run on genuine trading day 2026-11-26
    res1 = run_stage2_shadow_logger(
        date_t0="2026-11-26",
        entry_date_t1="2026-11-27",
        data_dir=tmp_dir,
        output_dir=out_dir,
        history_fetcher=mock_fetcher,
        logged_at_override="2026-11-26T16:00:00+07:00",
    )
    assert res1["rows_logged"] == EXPECTED_UNIVERSE_SIZE
    assert res1["wrote_new"] is True
    assert res1["shadow_count"] == 1

    stock_df = pd.read_csv(os.path.join(out_dir, STOCK_LOG_FILENAME), keep_default_na=False)
    assert len(stock_df) == EXPECTED_UNIVERSE_SIZE
    assert (stock_df["schema_version"] == SCHEMA_VERSION).all()
    assert (stock_df["sample_role"] == ROLE_PROSPECTIVE).all()

    # Check groups & halted symbol missing_reason
    row0 = stock_df[stock_df["symbol"] == symbols[0]].iloc[0]
    row1 = stock_df[stock_df["symbol"] == symbols[1]].iloc[0]
    row_halted = stock_df[stock_df["symbol"] == halted_sym].iloc[0]
    assert row0["group"] == GROUP_SHADOW and bool(row0["pass_6_internal_gates"]) is True
    assert row1["group"] == GROUP_WATCH_FAILED and bool(row1["pass_6_internal_gates"]) is False
    assert row_halted["group"] == GROUP_REJECT
    assert "HALTED_OR_NO_OHLCV" in row_halted["missing_reason"]
    assert row_halted["close"] == ""

    # Verify NO forward return columns exist (anti look-ahead)
    assert not any(c.startswith("exec_t") for c in stock_df.columns)

    # Verify Table 2 & Manifest
    mkt_df = pd.read_csv(os.path.join(out_dir, MARKET_LOG_FILENAME))
    assert len(mkt_df) == 1
    assert bool(mkt_df.iloc[0]["arm_a_open"]) is False
    with open(os.path.join(out_dir, MANIFEST_FILENAME), encoding="utf-8") as fh:
        manifest = json.load(fh)
    assert len(manifest["entries"]) == 1 and len(manifest["entries"][0]["stock_csv_sha256"]) == 64

    # 2. Idempotent re-run on same day must NOT duplicate rows
    res2 = run_stage2_shadow_logger(
        date_t0="2026-11-26",
        entry_date_t1="2026-11-27",
        data_dir=tmp_dir,
        output_dir=out_dir,
        history_fetcher=mock_fetcher,
    )
    assert res2["wrote_new"] is False
    stock_df_after = pd.read_csv(os.path.join(out_dir, STOCK_LOG_FILENAME))
    mkt_df_after = pd.read_csv(os.path.join(out_dir, MARKET_LOG_FILENAME))
    assert len(stock_df_after) == EXPECTED_UNIVERSE_SIZE
    assert len(mkt_df_after) == 1

    # 3. Post-holiday run (2026-11-25) gets EXPLORATORY_IN_SAMPLE label
    _make_55_decision_csv(tmp_dir, "2026-11-25", symbols)
    res_pre = run_stage2_shadow_logger(
        date_t0="2026-11-25",
        entry_date_t1="2026-11-26",
        data_dir=tmp_dir,
        output_dir=out_dir,
        history_fetcher=mock_fetcher,
    )
    assert res_pre["wrote_new"] is True
    all_stocks = pd.read_csv(os.path.join(out_dir, STOCK_LOG_FILENAME))
    assert len(all_stocks) == EXPECTED_UNIVERSE_SIZE * 2
    assert (all_stocks[all_stocks["date_t0"] == "2026-11-25"]["sample_role"] == ROLE_EXPLORATORY).all()


def test_reject_holiday_weekend_and_invalid_row_count(tmp_path: object) -> None:
    """Verify logger fails loudly on holidays, weekends, missing decision CSVs, or rows != 55."""
    tmp_dir = str(tmp_path)
    out_dir = os.path.join(tmp_dir, "stage2_shadow")
    symbols = sorted(list(UNIVERSE_METADATA.keys()))[:EXPECTED_UNIVERSE_SIZE]
    bdays = [d.strftime("%Y-%m-%d") for d in pd.bdate_range("2026-06-01", "2026-11-26")]
    trading_days = [d for d in bdays if d != "2026-11-24"]

    def mock_fetcher(symbol: str, days: int = 180) -> pd.DataFrame:
        return _make_mock_history(trading_days)

    # 1. Weekend rejected
    with pytest.raises(ValueError, match="cuối tuần"):
        run_stage2_shadow_logger("2026-11-22", data_dir=tmp_dir, output_dir=out_dir, history_fetcher=mock_fetcher)

    # 2. Holiday (2026-11-24) rejected because VNINDEX has no bar on 2026-11-24
    with pytest.raises(ValueError, match="nghỉ lễ"):
        run_stage2_shadow_logger("2026-11-24", data_dir=tmp_dir, output_dir=out_dir, history_fetcher=mock_fetcher)

    # 3. Rows != 55 rejected without partial writes
    _make_55_decision_csv(tmp_dir, "2026-11-26", symbols[:54])
    with pytest.raises(ValueError, match="rows == 55"):
        run_stage2_shadow_logger("2026-11-26", data_dir=tmp_dir, output_dir=out_dir, history_fetcher=mock_fetcher)
    assert not os.path.exists(os.path.join(out_dir, STOCK_LOG_FILENAME))
