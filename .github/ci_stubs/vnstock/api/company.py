"""Company module stub for vnstock."""

from __future__ import annotations

import pandas as pd


class Company:
    """Mock Company class for CI test environments."""

    def __init__(self, *args, **kwargs):
        pass

    def overview(self, *args, **kwargs) -> pd.DataFrame:
        return pd.DataFrame()

    def events(self, *args, **kwargs) -> pd.DataFrame:
        return pd.DataFrame()


__all__ = ["Company"]
