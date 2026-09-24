"""Unit tests for paper_trading.py."""

from __future__ import annotations

from datetime import datetime, timedelta

from paper_trading import (
    BRANCH_QUANT_ONLY,
    BRANCH_QUANT_PLUS_LLM,
    STATUS_FILLED,
    STATUS_REJECTED_BUDGET,
    STATUS_REJECTED_COOLDOWN,
    STATUS_UNFILLED_CEILING,
    PaperTradingManager,
    calculate_implementation_shortfall,
)


def test_calculate_implementation_shortfall_buy():
    """Adverse slippage when buying: fill higher than decision."""
    # Decision at 50.0, filled at 50.5 (+1% = +100 bps)
    bps = calculate_implementation_shortfall(50.0, 50.5, is_buy=True)
    assert bps == 100.0

    # Favorable fill: filled lower at 49.5 (-100 bps)
    bps_fav = calculate_implementation_shortfall(50.0, 49.5, is_buy=True)
    assert bps_fav == -100.0


def test_calculate_implementation_shortfall_sell():
    """Adverse slippage when selling: fill lower than decision."""
    # Decision at 50.0, filled at 49.5 (-1% = +100 bps shortfall)
    bps = calculate_implementation_shortfall(50.0, 49.5, is_buy=False)
    assert bps == 100.0


def test_paper_trading_daily_buy_budget_and_cooldown():
    """Verify Daily 2 BUY budget and 5-day Cooldown enforcement."""
    manager = PaperTradingManager(max_daily_buys=2, cooldown_days=5)
    t0 = datetime(2024, 3, 1, 9, 30)

    # 1. First BUY order -> Approved
    o1 = manager.submit_paper_order("HPG", "BUY", 28.0, t0)
    assert o1.status != STATUS_REJECTED_BUDGET

    # 2. Same symbol same day -> Cooldown active
    o_repeat = manager.submit_paper_order("HPG", "BUY", 28.5, t0 + timedelta(hours=1))
    assert o_repeat.status == STATUS_REJECTED_COOLDOWN

    # 3. Second BUY order for another symbol -> Approved
    o2 = manager.submit_paper_order("FPT", "BUY", 110.0, t0 + timedelta(hours=2))
    assert o2.status != STATUS_REJECTED_BUDGET

    # 4. Third BUY order on the same day -> Blocked by daily budget
    o3 = manager.submit_paper_order("MWG", "BUY", 45.0, t0 + timedelta(hours=3))
    assert o3.status == STATUS_REJECTED_BUDGET


def test_paper_trading_execution_and_ablation_summary():
    """Verify order fill, ceiling unfill, and shortfall summary by branch."""
    manager = PaperTradingManager()
    t0 = datetime(2024, 3, 1, 10, 0)

    # Submit 2 orders: 1 Quant Only, 1 Quant + LLM
    o_quant = manager.submit_paper_order("SSI", "BUY", 30.0, t0, branch=BRANCH_QUANT_ONLY)
    o_llm = manager.submit_paper_order("VHM", "BUY", 40.0, t0, branch=BRANCH_QUANT_PLUS_LLM)

    # Fill Quant order at 30.15 (+50 bps)
    manager.execute_fill(o_quant, fill_price=30.15, fill_time=t0 + timedelta(minutes=5), shares=1000)
    assert o_quant.status == STATUS_FILLED
    assert o_quant.shortfall_bps == 50.0

    # Fill LLM order hit ceiling -> Unfilled
    manager.execute_fill(o_llm, fill_price=42.8, fill_time=t0 + timedelta(minutes=5), shares=0, is_ceiling_hit=True)
    assert o_llm.status == STATUS_UNFILLED_CEILING

    # Check metrics
    summary_all = manager.compute_shortfall_summary()
    assert summary_all["total_orders"] == 2
    assert summary_all["filled_orders"] == 1
    assert summary_all["fill_rate_pct"] == 50.0
    assert summary_all["avg_shortfall_bps"] == 50.0

    summary_quant = manager.compute_shortfall_summary(branch=BRANCH_QUANT_ONLY)
    assert summary_quant["fill_rate_pct"] == 100.0
