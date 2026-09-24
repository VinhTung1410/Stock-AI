"""Unit tests for regime_classifier.py."""

from __future__ import annotations

import numpy as np
import pandas as pd

from regime_classifier import (
    METHOD_MA200_SLOPE,
    METHOD_MOMENTUM_VOLATILITY,
    REGIME_DOWNTREND,
    REGIME_SIDEWAYS,
    REGIME_UPTREND,
    classify_market_regime,
    classify_regime_ma200_slope,
    classify_regime_momentum_volatility,
)


def _generate_synthetic_index(days: int = 300, trend: str = "UP") -> pd.DataFrame:
    """Generate synthetic index price series for testing."""
    dates = pd.date_range("2023-01-01", periods=days, freq="B")
    if trend == "UP":
        prices = np.linspace(1000, 1500, days)
    elif trend == "DOWN":
        prices = np.linspace(1500, 900, days)
    else:
        prices = 1200 + np.sin(np.linspace(0, 10, days)) * 50

    return pd.DataFrame({"close": prices}, index=dates)


def test_classify_regime_empty_dataframe():
    """Empty dataframe should safely return empty series."""
    df_empty = pd.DataFrame()
    res = classify_market_regime(df_empty)
    assert res.empty


def test_classify_regime_insufficient_data():
    """Dataframe with fewer than MA window should return SIDEWAYS."""
    df_short = pd.DataFrame({"close": [100.0, 105.0, 102.0]})
    res = classify_market_regime(df_short)
    assert len(res) == 3
    assert (res == REGIME_SIDEWAYS).all()


def test_classify_regime_ma200_slope_uptrend():
    """Verify consistent UPTREND detection on upward sloping data."""
    df = _generate_synthetic_index(days=250, trend="UP")
    regimes = classify_regime_ma200_slope(df, ma_window=50, slope_window=10)
    # Towards the end of the series, should be UPTREND
    assert regimes.iloc[-1] == REGIME_UPTREND


def test_classify_regime_ma200_slope_downtrend():
    """Verify consistent DOWNTREND detection on downward sloping data."""
    df = _generate_synthetic_index(days=250, trend="DOWN")
    regimes = classify_regime_ma200_slope(df, ma_window=50, slope_window=10)
    # Towards the end of the series, should be DOWNTREND
    assert regimes.iloc[-1] == REGIME_DOWNTREND


def test_classify_regime_momentum_volatility():
    """Verify momentum volatility classifier."""
    df_up = _generate_synthetic_index(days=100, trend="UP")
    regimes = classify_regime_momentum_volatility(df_up, return_window=20, up_threshold=2.0)
    assert regimes.iloc[-1] == REGIME_UPTREND

    df_down = _generate_synthetic_index(days=100, trend="DOWN")
    regimes_down = classify_regime_momentum_volatility(df_down, return_window=20, down_threshold=-2.0)
    assert regimes_down.iloc[-1] == REGIME_DOWNTREND


def test_classify_market_regime_router():
    """Test router function with different methods and fallback."""
    df = _generate_synthetic_index(days=150, trend="UP")
    res_ma = classify_market_regime(df, method=METHOD_MA200_SLOPE)
    assert len(res_ma) == 150

    res_mom = classify_market_regime(df, method=METHOD_MOMENTUM_VOLATILITY)
    assert len(res_mom) == 150

    res_unknown = classify_market_regime(df, method="UNKNOWN_METHOD")
    assert len(res_unknown) == 150
