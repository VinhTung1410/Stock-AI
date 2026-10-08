"""contrarian_features.py

Tính các trường mà contrarian_engine.py đọc nhưng fetch_stock_technical chưa cung cấp:
    volume_ratio_20d, atr_ratio_14d, has_gap_down,
    higher_low, bullish_divergence, price_confirmation,
    volume_contraction, has_reversal_pattern

Nguyên tắc: POINT-IN-TIME. Chỉ dùng dữ liệu đến nến cuối cùng của df truyền vào,
nên dùng được cho cả live (df đầy đủ) lẫn replay (df.iloc[: i + 1]).
df cần các cột: open, high, low, close, volume, sắp xếp tăng dần theo thời gian.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

MIN_BARS = 40
GAP_DOWN_PCT = -0.03  # gap mở cửa <= -3% so với đóng cửa hôm trước (biên HOSE là ±7%)

DEFAULT_FEATURES: dict[str, Any] = {
    "volume_ratio_20d": 1.0,
    "atr_ratio_14d": 1.0,
    "has_gap_down": False,
    "higher_low": False,
    "bullish_divergence": False,
    "price_confirmation": False,
    "volume_contraction": False,
    "has_reversal_pattern": False,
}


def _rsi(close: pd.Series, period: int = 14) -> pd.Series:
    """RSI cùng công thức rolling-mean với data_engine.calculate_rsi."""
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def _volume_ratio(v: np.ndarray) -> float:
    base = v[-21:-1].mean()
    return float(v[-1] / base) if base > 0 else 1.0


def _atr_ratio(h: np.ndarray, low: np.ndarray, c: np.ndarray) -> float:
    prev_c = c[:-1]
    tr = np.maximum(h[1:] - low[1:], np.maximum(np.abs(h[1:] - prev_c), np.abs(low[1:] - prev_c)))
    atr = pd.Series(tr).rolling(14).mean()
    now = atr.iloc[-1]
    base = atr.iloc[-61:-1].median()
    if pd.isna(now) or pd.isna(base) or base <= 0:
        return 1.0
    return float(now / base)


def _has_gap_down(o: np.ndarray, c: np.ndarray) -> bool:
    for k in (1, 2, 3):
        if len(c) > k + 1 and c[-k - 1] > 0 and (o[-k] / c[-k - 1] - 1.0) <= GAP_DOWN_PCT:
            return True
    return False


def _higher_low(low: np.ndarray) -> bool:
    """Đáy 5 phiên gần nhất cao hơn đáy của 20 phiên trước đó."""
    return bool(low[-5:].min() > low[-25:-5].min())


def _bullish_divergence(low: np.ndarray, rsi: pd.Series) -> bool:
    """Giá tạo đáy thấp hơn nhưng RSI tại đáy cao hơn (phân kỳ dương)."""
    rec_low, pri_low = low[-10:], low[-25:-10]
    if len(pri_low) == 0 or rec_low.min() >= pri_low.min():
        return False
    r_rec = rsi.iloc[len(rsi) - 10 + int(rec_low.argmin())]
    r_pri = rsi.iloc[len(rsi) - 25 + int(pri_low.argmin())]
    if pd.isna(r_rec) or pd.isna(r_pri):
        return False
    return bool(r_rec > r_pri + 2.0 and r_pri < 40.0)


def _reversal_pattern(o: np.ndarray, h: np.ndarray, low: np.ndarray, c: np.ndarray) -> bool:
    """Hammer hoặc Bullish Engulfing trong 2 nến gần nhất."""
    for k in (1, 2):
        rng = h[-k] - low[-k]
        if rng <= 0:
            continue
        lower = min(o[-k], c[-k]) - low[-k]
        upper = h[-k] - max(o[-k], c[-k])
        if lower >= 0.6 * rng and upper <= 0.15 * rng:
            return True
    if len(c) >= 2 and c[-2] < o[-2] and c[-1] > o[-1] and o[-1] <= c[-2] and c[-1] >= o[-2]:
        return True
    return False


def compute_contrarian_features(df: pd.DataFrame | None, lookback: int = 120) -> dict[str, Any]:
    """Trả về dict feature contrarian tính từ nến cuối của df (point-in-time)."""
    if df is None or len(df) < MIN_BARS:
        return dict(DEFAULT_FEATURES)

    d = df.tail(lookback).reset_index(drop=True)
    o = d["open"].to_numpy(dtype=float)
    h = d["high"].to_numpy(dtype=float)
    low = d["low"].to_numpy(dtype=float)
    c = d["close"].to_numpy(dtype=float)
    v = d["volume"].to_numpy(dtype=float)
    rsi = _rsi(d["close"].astype(float))

    base_vol = v[-23:-3].mean()
    return {
        "volume_ratio_20d": round(_volume_ratio(v), 2),
        "atr_ratio_14d": round(_atr_ratio(h, low, c), 2),
        "has_gap_down": _has_gap_down(o, c),
        "higher_low": _higher_low(low),
        "bullish_divergence": _bullish_divergence(low, rsi),
        "price_confirmation": bool(c[-1] > h[-2] and c[-1] > o[-1]),
        "volume_contraction": bool(base_vol > 0 and v[-3:].mean() < 0.7 * base_vol),
        "has_reversal_pattern": _reversal_pattern(o, h, low, c),
    }
