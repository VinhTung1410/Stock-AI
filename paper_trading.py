"""Module: paper_trading.py.

Manages forward testing / paper trading simulations, tracking immutable signal
snapshots, measuring Implementation Shortfall (basis points), and maintaining
ablation branches (Quant Only vs Quant + LLM).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Final

# Order Status Constants (S1192)
STATUS_PENDING: Final[str] = "PENDING"
STATUS_FILLED: Final[str] = "FILLED"
STATUS_UNFILLED_CEILING: Final[str] = "UNFILLED_CEILING"
STATUS_REJECTED_BUDGET: Final[str] = "REJECTED_BUDGET"
STATUS_REJECTED_COOLDOWN: Final[str] = "REJECTED_COOLDOWN"

# Ablation Branches
BRANCH_QUANT_ONLY: Final[str] = "QUANT_ONLY"
BRANCH_QUANT_PLUS_LLM: Final[str] = "QUANT_PLUS_LLM"

# Operational Limits
MAX_DAILY_BUYS: Final[int] = 2
MAX_PORTFOLIO_POSITIONS: Final[int] = 8
COOLDOWN_DAYS: Final[int] = 5


@dataclass
class PaperOrder:
    """Individual paper trading order with execution tracking."""

    symbol: str
    decision_time: datetime
    decision_price: float
    side: str  # "BUY" or "SELL"
    branch: str = BRANCH_QUANT_ONLY
    status: str = STATUS_PENDING
    fill_time: datetime | None = None
    fill_price: float | None = None
    shares: int = 0
    shortfall_bps: float = 0.0
    reason: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


def calculate_implementation_shortfall(
    decision_price: float,
    fill_price: float,
    is_buy: bool = True,
) -> float:
    """Calculate execution slippage / implementation shortfall in basis points (bps).

    Positive bps indicates adverse execution (bought higher or sold lower).
    """
    if decision_price <= 0:
        return 0.0

    if is_buy:
        # Slippage when buying: (fill - decision) / decision
        shortfall = ((fill_price - decision_price) / decision_price) * 10000.0
    else:
        # Slippage when selling: (decision - fill) / decision
        shortfall = ((decision_price - fill_price) / decision_price) * 10000.0

    return round(float(shortfall), 2)


class PaperTradingManager:
    """Orchestrates paper orders, enforces budget & guardrails, and records shortfall."""

    def __init__(
        self,
        max_daily_buys: int = MAX_DAILY_BUYS,
        max_positions: int = MAX_PORTFOLIO_POSITIONS,
        cooldown_days: int = COOLDOWN_DAYS,
    ) -> None:
        self.max_daily_buys = max_daily_buys
        self.max_positions = max_positions
        self.cooldown_days = cooldown_days
        self.orders: list[PaperOrder] = []
        self.active_positions: dict[str, int] = {}
        self.symbol_last_signal_date: dict[str, datetime] = {}

    def _count_daily_buys(self, target_date: datetime) -> int:
        """Count filled or pending BUY orders on a specific date."""
        return sum(
            1
            for o in self.orders
            if o.side == "BUY"
            and o.decision_time.date() == target_date.date()
            and o.status in (STATUS_PENDING, STATUS_FILLED)
        )

    def _is_in_cooldown(self, symbol: str, current_time: datetime) -> bool:
        """Check if symbol has received a signal within cooldown window."""
        last_date = self.symbol_last_signal_date.get(symbol)
        if last_date is None:
            return False
        delta_days = (current_time.date() - last_date.date()).days
        return delta_days < self.cooldown_days

    def submit_paper_order(
        self,
        symbol: str,
        side: str,
        decision_price: float,
        decision_time: datetime,
        branch: str = BRANCH_QUANT_ONLY,
        metadata: dict[str, Any] | None = None,
    ) -> PaperOrder:
        """Submit a new paper order checking daily budget and cooldown."""
        meta = metadata or {}

        # 1. Check Cooldown
        if side == "BUY" and self._is_in_cooldown(symbol, decision_time):
            order = PaperOrder(
                symbol=symbol,
                decision_time=decision_time,
                decision_price=decision_price,
                side=side,
                branch=branch,
                status=STATUS_REJECTED_COOLDOWN,
                reason="Cooldown 5 days active",
                metadata=meta,
            )
            self.orders.append(order)
            return order

        # 2. Check Daily Buy Budget
        if side == "BUY" and self._count_daily_buys(decision_time) >= self.max_daily_buys:
            order = PaperOrder(
                symbol=symbol,
                decision_time=decision_time,
                decision_price=decision_price,
                side=side,
                branch=branch,
                status=STATUS_REJECTED_BUDGET,
                reason="Daily signal budget exhausted",
                metadata=meta,
            )
            self.orders.append(order)
            return order

        # 3. Create Valid Order
        order = PaperOrder(
            symbol=symbol,
            decision_time=decision_time,
            decision_price=decision_price,
            side=side,
            branch=branch,
            status=STATUS_PENDING,
            metadata=meta,
        )
        self.orders.append(order)
        self.symbol_last_signal_date[symbol] = decision_time
        return order

    def execute_fill(
        self,
        order: PaperOrder,
        fill_price: float,
        fill_time: datetime,
        shares: int,
        is_ceiling_hit: bool = False,
    ) -> PaperOrder:
        """Execute simulated fill and calculate implementation shortfall."""
        if is_ceiling_hit and order.side == "BUY":
            order.status = STATUS_UNFILLED_CEILING
            order.reason = "HOSE Ceiling limit reached - unfilled"
            return order

        order.fill_price = fill_price
        order.fill_time = fill_time
        order.shares = shares
        order.status = STATUS_FILLED
        is_buy = order.side == "BUY"
        order.shortfall_bps = calculate_implementation_shortfall(
            order.decision_price, fill_price, is_buy=is_buy
        )

        if is_buy:
            self.active_positions[order.symbol] = self.active_positions.get(order.symbol, 0) + shares
        else:
            self.active_positions.pop(order.symbol, None)

        return order

    def compute_shortfall_summary(self, branch: str | None = None) -> dict[str, Any]:
        """Summarize execution quality: fill rate and average shortfall (bps)."""
        filtered = [o for o in self.orders if branch is None or o.branch == branch]
        total = len(filtered)
        if total == 0:
            return {
                "total_orders": 0,
                "filled_orders": 0,
                "fill_rate_pct": 0.0,
                "avg_shortfall_bps": 0.0,
            }

        filled = [o for o in filtered if o.status == STATUS_FILLED]
        shortfalls = [o.shortfall_bps for o in filled]
        avg_shortfall = float(sum(shortfalls) / len(shortfalls)) if shortfalls else 0.0

        return {
            "total_orders": total,
            "filled_orders": len(filled),
            "fill_rate_pct": round((len(filled) / total) * 100.0, 2),
            "avg_shortfall_bps": round(avg_shortfall, 2),
        }
