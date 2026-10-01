"""Financial module stub for vnstock."""

from __future__ import annotations

import pandas as pd


class Finance:
    """Mock Finance class for CI test environments."""

    def __init__(self, *args, **kwargs):
        pass

    def ratio(self, *args, **kwargs) -> pd.DataFrame:
        return pd.DataFrame()


__all__ = ["Finance"]
