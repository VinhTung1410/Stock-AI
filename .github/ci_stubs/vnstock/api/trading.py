"""Trading module stub for vnstock."""

from __future__ import annotations

import pandas as pd


class Trading:
    """Mock Trading class for CI test environments."""

    def __init__(self, *args, **kwargs):
        pass

    def price_board(self, *args, **kwargs) -> pd.DataFrame:
        return pd.DataFrame()


__all__ = ["Trading"]
