"""Module: regime_classifier.py.

Provides deterministic and objective market regime classification
(UPTREND, DOWNTREND, SIDEWAYS) based on index price series.
"""

from __future__ import annotations

import logging
from enum import Enum
from typing import Final

import numpy as np
import pandas as pd

# Regime Constants (S1192: String Duplication Prevention)
REGIME_UPTREND: Final[str] = "UPTREND"
REGIME_DOWNTREND: Final[str] = "DOWNTREND"
REGIME_SIDEWAYS: Final[str] = "SIDEWAYS"
REGIME_UNKNOWN: Final[str] = "UNKNOWN"


class RegimeState(str, Enum):
    """Canonical Market Regime State (Phase 17 / TASK-0058)."""

    UPTREND = "UPTREND"
    SIDEWAYS = "SIDEWAYS"
    DOWNTREND = "DOWNTREND"
    UNKNOWN = "UNKNOWN"


# Methodology Constants
METHOD_MA200_SLOPE: Final[str] = "MA200_SLOPE"
METHOD_MA200_HYSTERESIS: Final[str] = "MA200_HYSTERESIS"
METHOD_MOMENTUM_VOLATILITY: Final[str] = "MOMENTUM_VOLATILITY"


def _calculate_slope(series: pd.Series, window: int = 20) -> pd.Series:
    """Calculate normalized percentage slope of a moving average over a window."""
    if len(series) < window:
        return pd.Series(0.0, index=series.index)
    shifted = series.shift(window)
    return ((series - shifted) / shifted.replace(0, np.nan)) * 100.0


def classify_regime_ma200_slope(
    df_index: pd.DataFrame,
    ma_window: int = 200,
    slope_window: int = 20,
    slope_threshold: float = 1.0,
) -> pd.Series:
    """Classify regime using Index relative to MA200 and MA200 slope.

    Rules:
    - UPTREND: Price >= MA and Slope(MA) > -0.5%
    - DOWNTREND: Price < MA and Slope(MA) < 0.5%
    - SIDEWAYS: Disagreements between price position and slope
    """
    if "close" not in df_index.columns or len(df_index) < slope_window:
        return pd.Series(REGIME_SIDEWAYS, index=df_index.index)

    close = df_index["close"].astype(float)
    # Adaptive window if data length is less than ma_window
    effective_window = ma_window if len(df_index) >= ma_window else max(20, len(df_index) // 2)
    min_p = max(10, effective_window // 4)
    ma_series = close.rolling(window=effective_window, min_periods=min_p).mean()
    slope = _calculate_slope(ma_series, window=slope_window)

    above_ma = close >= ma_series
    slope_pos = slope >= -0.5
    below_ma = close < ma_series
    slope_neg = slope <= slope_threshold

    regimes = pd.Series(REGIME_SIDEWAYS, index=df_index.index)
    regimes[above_ma & slope_pos] = REGIME_UPTREND
    regimes[below_ma & slope_neg] = REGIME_DOWNTREND

    return regimes


def classify_regime_ma200_hysteresis(
    df_index: pd.DataFrame,
    ma_window: int = 200,
    hysteresis_pct: float = 1.5,
    reentry_pct: float = 1.0,
    confirmation_sessions: int = 2,
    vol_surge_mult: float = 1.3,
) -> pd.Series:
    """Classify regime with hysteresis buffer to eliminate whipsaws around MA200 (Phase 13 / TASK-0040).

    Rules:
    - Downtrend Trigger: Close < MA200 * (1 - hysteresis_pct/100) for >= confirmation_sessions consecutive sessions,
      OR breakdown below MA200 with heavy volume (> vol_surge_mult * ADV20).
    - Uptrend / Re-entry Trigger: Close > MA200 * (1 + reentry_pct/100).
    - Buffer / Neutral: Keeps prior regime state to avoid oscillating false signals.
    """
    if "close" not in df_index.columns or len(df_index) < 20:
        return pd.Series(REGIME_SIDEWAYS, index=df_index.index)

    close = df_index["close"].astype(float)
    effective_window = ma_window if len(df_index) >= ma_window else max(20, len(df_index) // 2)
    min_p = max(10, effective_window // 4)
    ma_series = close.rolling(window=effective_window, min_periods=min_p).mean()

    volume = df_index["volume"].astype(float) if "volume" in df_index.columns else pd.Series(0.0, index=df_index.index)
    vol_ma = volume.rolling(window=20, min_periods=5).mean()

    lower_band = ma_series * (1.0 - hysteresis_pct / 100.0)
    upper_band = ma_series * (1.0 + reentry_pct / 100.0)

    is_below_lower = (close < lower_band).astype(int)
    rolling_below_count = is_below_lower.rolling(window=confirmation_sessions, min_periods=confirmation_sessions).sum()
    confirmed_downtrend = rolling_below_count >= confirmation_sessions

    vol_surge_break = (close < ma_series) & (volume > (vol_ma * vol_surge_mult))
    confirmed_uptrend = close >= upper_band

    regimes = pd.Series(REGIME_SIDEWAYS, index=df_index.index)
    current_state = REGIME_SIDEWAYS
    for i in range(len(df_index)):
        if confirmed_uptrend.iloc[i]:
            current_state = REGIME_UPTREND
        elif confirmed_downtrend.iloc[i] or vol_surge_break.iloc[i]:
            current_state = REGIME_DOWNTREND
        elif close.iloc[i] >= ma_series.iloc[i] and current_state == REGIME_DOWNTREND:
            current_state = REGIME_SIDEWAYS
        elif close.iloc[i] < ma_series.iloc[i] and current_state == REGIME_UPTREND:
            current_state = REGIME_SIDEWAYS
        regimes.iloc[i] = current_state

    return regimes


def classify_regime_momentum_volatility(
    df_index: pd.DataFrame,
    return_window: int = 60,
    vol_window: int = 20,
    up_threshold: float = 5.0,
    down_threshold: float = -5.0,
) -> pd.Series:
    """Classify regime using rolling cumulative return and volatility.

    Rules:
    - UPTREND: Rolling return > +5.0%
    - DOWNTREND: Rolling return < -5.0%
    - SIDEWAYS: Between -5.0% and +5.0%
    """
    if "close" not in df_index.columns or len(df_index) < vol_window:
        return pd.Series(REGIME_SIDEWAYS, index=df_index.index)

    eff_ret_window = return_window if len(df_index) >= return_window else max(10, len(df_index) // 2)
    close = df_index["close"].astype(float)
    shifted = close.shift(eff_ret_window)
    rolling_ret = ((close - shifted) / shifted.replace(0, np.nan)) * 100.0

    regimes = pd.Series(REGIME_SIDEWAYS, index=df_index.index)
    regimes[rolling_ret > up_threshold] = REGIME_UPTREND
    regimes[rolling_ret < down_threshold] = REGIME_DOWNTREND

    return regimes


def classify_market_regime(
    df_index: pd.DataFrame,
    method: str = METHOD_MA200_SLOPE,
) -> pd.Series:
    """Entry point for market regime classification.

    Cognitive Complexity < 15, deterministic, zero-lookahead.
    """
    try:
        if df_index.empty:
            return pd.Series(dtype=str)

        if method == METHOD_MA200_HYSTERESIS:
            return classify_regime_ma200_hysteresis(df_index)
        if method == METHOD_MA200_SLOPE:
            return classify_regime_ma200_slope(df_index)
        if method == METHOD_MOMENTUM_VOLATILITY:
            return classify_regime_momentum_volatility(df_index)

        # Fallback to default
        return classify_regime_ma200_slope(df_index)

    except Exception:
        logging.exception("Failed to classify market regime for given index data.")
        return pd.Series(REGIME_SIDEWAYS, index=df_index.index)


def is_macro_circuit_breaker_active(
    df_index: pd.DataFrame,
    method: str = METHOD_MA200_SLOPE,
) -> tuple[bool, str]:
    """Check if Macro Circuit Breaker is active to enforce Cash Mode.

    Returns:
        tuple (is_active, reason):
        - (True, "VN-INDEX_DOWNTREND_CIRCUIT_BREAKER") if market is in DOWNTREND.
        - (False, "MARKET_HEALTHY_OR_SIDEWAYS") otherwise.
    """
    if df_index.empty or "close" not in df_index.columns:
        return False, "INDEX_DATA_UNAVAILABLE"

    regimes = classify_market_regime(df_index, method=method)
    if regimes.empty:
        return False, "REGIME_SERIES_EMPTY"

    latest_regime = regimes.iloc[-1]
    if latest_regime == REGIME_DOWNTREND:
        return True, "VN-INDEX_DOWNTREND_CIRCUIT_BREAKER"

    return False, "MARKET_HEALTHY_OR_SIDEWAYS"


def get_canonical_regime(
    symbol_data: dict | pd.DataFrame | None = None,
    vn_index_data: dict | pd.DataFrame | None = None,
) -> RegimeState:
    """MA200 hysteresis -> Single source of truth cho toàn bộ hệ thống (TASK-0058).

    Supports dictionary (e.g. {'current_price': ..., 'ma200': ...}) or DataFrame.
    """
    data = vn_index_data if vn_index_data is not None else symbol_data
    if data is None:
        return RegimeState.UNKNOWN

    if isinstance(data, dict):
        if not data:
            return RegimeState.UNKNOWN
        curr_p = float(data.get("current_price") or data.get("close") or 0.0)
        ma200 = float(data.get("ma200") or 0.0)
        if curr_p <= 0 or ma200 <= 0:
            return RegimeState.UNKNOWN
        # MA200 Hysteresis buffer +/- 1.5%
        if curr_p > ma200 * 1.015:
            return RegimeState.UPTREND
        if curr_p < ma200 * 0.985:
            return RegimeState.DOWNTREND
        return RegimeState.SIDEWAYS

    if isinstance(data, pd.DataFrame):
        if data.empty or "close" not in data.columns:
            return RegimeState.UNKNOWN
        regimes = classify_regime_ma200_hysteresis(data)
        if regimes.empty:
            return RegimeState.UNKNOWN
        val = str(regimes.iloc[-1]).upper()
        if "UP" in val:
            return RegimeState.UPTREND
        if "DOWN" in val:
            return RegimeState.DOWNTREND
        return RegimeState.SIDEWAYS

    return RegimeState.UNKNOWN

