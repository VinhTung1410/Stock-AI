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
    meta_verified = {"conviction_ex_watchlist": 75.0, "conviction_score": 75.0}

    # 1. First BUY order -> Approved
    o1 = manager.submit_paper_order("HPG", "BUY", 28.0, t0, metadata=meta_verified)
    assert o1.status != STATUS_REJECTED_BUDGET
    assert o1.status != "BUY_UNVERIFIED"

    # 2. Same symbol same day -> Cooldown active
    o_repeat = manager.submit_paper_order("HPG", "BUY", 28.5, t0 + timedelta(hours=1), metadata=meta_verified)
    assert o_repeat.status == STATUS_REJECTED_COOLDOWN

    # 3. Second BUY order for another symbol -> Approved
    o2 = manager.submit_paper_order("FPT", "BUY", 110.0, t0 + timedelta(hours=2), metadata=meta_verified)
    assert o2.status != STATUS_REJECTED_BUDGET
    assert o2.status != "BUY_UNVERIFIED"

    # 4. Third BUY order on the same day -> Blocked by daily budget
    o3 = manager.submit_paper_order("MWG", "BUY", 45.0, t0 + timedelta(hours=3), metadata=meta_verified)
    assert o3.status == STATUS_REJECTED_BUDGET



def test_paper_trading_execution_and_ablation_summary():
    """Verify order fill, ceiling unfill, and shortfall summary by branch."""
    manager = PaperTradingManager()
    t0 = datetime(2024, 3, 1, 10, 0)

    # Submit 2 orders: 1 Quant Only, 1 Quant + LLM
    meta_ok = {"conviction_ex_watchlist": 75.0, "conviction_score": 75.0}
    o_quant = manager.submit_paper_order("SSI", "BUY", 30.0, t0, branch=BRANCH_QUANT_ONLY, metadata=meta_ok)
    o_llm = manager.submit_paper_order("VHM", "BUY", 40.0, t0, branch=BRANCH_QUANT_PLUS_LLM, metadata=meta_ok)

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


def test_paper_trading_suppresses_buy_when_conviction_ex_watchlist_below_70():
    """Verify that BUY orders with conviction_ex_watchlist < 70 are suppressed under Option 1 execution gate."""
    from paper_trading import STATUS_SUPPRESSED_WATCHLIST

    manager = PaperTradingManager()
    t0 = datetime(2026, 10, 24, 10, 0)

    # 1. MBB-style: conviction 76.0 with bonus, but conviction_ex_watchlist = 66.0 (< 70)
    order_suppressed = manager.submit_paper_order(
        symbol="MBB",
        side="BUY",
        decision_price=20.0,
        decision_time=t0,
        metadata={"conviction_score": 76.0, "conviction_ex_watchlist": 66.0, "watchlist_bonus": 10.0},
    )
    assert order_suppressed.status == STATUS_SUPPRESSED_WATCHLIST
    assert "conviction_ex_watchlist (66.0) < 70.0" in order_suppressed.reason

    # 2. Genuine high conviction: conviction_ex_watchlist = 72.0 (>= 70)
    order_approved = manager.submit_paper_order(
        symbol="FPT",
        side="BUY",
        decision_price=60.0,
        decision_time=t0,
        metadata={"conviction_score": 82.0, "conviction_ex_watchlist": 72.0, "watchlist_bonus": 10.0},
    )
    assert order_approved.status != STATUS_SUPPRESSED_WATCHLIST


def test_paper_trading_fail_closed_when_conviction_ex_watchlist_missing():
    """Verify fail-closed gate: BUY order missing conviction_ex_watchlist is BLOCKED as BUY_UNVERIFIED."""
    from paper_trading import STATUS_UNVERIFIED_BUY

    manager = PaperTradingManager()
    t0 = datetime(2026, 10, 24, 10, 0)

    # Legacy production record without conviction_ex_watchlist field
    legacy_order = manager.submit_paper_order(
        symbol="TCB",
        side="BUY",
        decision_price=33.0,
        decision_time=t0,
        metadata={"conviction_score": 75.0},  # No conviction_ex_watchlist!
    )
    assert legacy_order.status == STATUS_UNVERIFIED_BUY
    assert "conviction_ex_watchlist invalid/missing" in legacy_order.reason

    # Explicit None in metadata
    none_order = manager.submit_paper_order(
        symbol="VPB",
        side="BUY",
        decision_price=24.0,
        decision_time=t0,
        metadata={"conviction_score": 80.0, "conviction_ex_watchlist": None},
    )
    assert none_order.status == STATUS_UNVERIFIED_BUY
    assert "conviction_ex_watchlist invalid/missing" in none_order.reason

    # Non-numeric string, NaN, Inf, and out-of-range values ([0, 100])
    invalid_inputs = [
        "N/A", "invalid", "", {}, [],
        float("nan"), "nan", "NaN",
        float("inf"), float("-inf"), "inf", "-inf",
        -5.0, "-1.0", -0.1,
        100.1, 105.0, "150.0",
    ]
    for bad_val in invalid_inputs:
        bad_order = manager.submit_paper_order(
            symbol="HPG",
            side="BUY",
            decision_price=28.0,
            decision_time=t0,
            metadata={"conviction_score": 80.0, "conviction_ex_watchlist": bad_val},
        )
        assert bad_order.status == STATUS_UNVERIFIED_BUY, f"Expected BUY_UNVERIFIED for {bad_val!r}"
        assert "fail-closed verification gate" in bad_order.reason


