"""Module: regime_classifier.py.

Provides deterministic and objective market regime classification
(UPTREND, DOWNTREND, SIDEWAYS) based on index price series.
"""

from __future__ import annotations

import logging
from typing import Final

import numpy as np
import pandas as pd

# Regime Constants (S1192: String Duplication Prevention)
REGIME_UPTREND: Final[str] = "UPTREND"
REGIME_DOWNTREND: Final[str] = "DOWNTREND"
REGIME_SIDEWAYS: Final[str] = "SIDEWAYS"

# Methodology Constants
METHOD_MA200_SLOPE: Final[str] = "MA200_SLOPE"
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

        if method == METHOD_MA200_SLOPE:
            return classify_regime_ma200_slope(df_index)
        if method == METHOD_MOMENTUM_VOLATILITY:
            return classify_regime_momentum_volatility(df_index)

        # Fallback to default
        return classify_regime_ma200_slope(df_index)

    except Exception:
        logging.exception("Failed to classify market regime for given index data.")
        return pd.Series(REGIME_SIDEWAYS, index=df_index.index)
