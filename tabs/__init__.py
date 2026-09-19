# Package tabs: Chứa các giao diện và logic phân tách theo từng Tab
from .tab_ai import render_tab_ai
from .tab_alpha_tracker import render_tab_alpha_tracker
from .tab_charts import render_tab_charts, render_tab_market_and_charts
from .tab_market import render_tab_market
from .tab_overview import render_tab_overview
from .tab_portfolio import render_tab_portfolio

__all__ = [
    "render_tab_overview",
    "render_tab_market",
    "render_tab_charts",
    "render_tab_market_and_charts",
    "render_tab_portfolio",
    "render_tab_ai",
    "render_tab_alpha_tracker",
]
