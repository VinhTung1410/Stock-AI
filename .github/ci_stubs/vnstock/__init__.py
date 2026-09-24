"""CI Stub for vnstock when public PyPI package is temporarily unavailable."""
from __future__ import annotations

__version__ = "4.0.8"


class Vnstock:
    """Mock Vnstock class for CI test environments."""

    def __init__(self, *args, **kwargs):
        pass

    def stock(self, *args, **kwargs):
        return self


class Trading:
    """Mock Trading class for CI test environments."""

    def __init__(self, *args, **kwargs):
        pass

    def price_board(self, *args, **kwargs):
        import pandas as pd
        return pd.DataFrame()


class Quote:
    """Mock Quote class for CI test environments."""

    def __init__(self, *args, **kwargs):
        pass

    def history(self, *args, **kwargs):
        import pandas as pd
        return pd.DataFrame()
