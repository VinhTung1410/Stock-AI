"""Module: test_task_0006_regime_first.py.

Unit tests for TASK-0006:
- Macro Circuit Breaker / Cash Mode detection (regime_classifier.py)
- Drawdown-Controlled Position Sizing & Liquidity Absorption (quant_engine.py)
- Smart Money Flow Evaluation (quant_engine.py)
- Regime Gate enforcement in Backtest Engine (backtest_engine.py)
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from backtest_engine import (
    REGIME_DOWNTREND,
    RegimeBacktestEngine,
    _generate_quant_core_signals,
)
from quant_engine import (
    calculate_drawdown_controlled_sizing,
    check_adv20_liquidity_absorption,
    evaluate_smart_money_flow,
)
from regime_classifier import (
    is_macro_circuit_breaker_active,
)


class TestMacroCircuitBreaker:
    """Test suite for Macro Circuit Breaker (Cash Mode detection)."""

    def test_empty_or_invalid_index_data(self):
        """Should safely handle empty or malformed index data."""
        active, reason = is_macro_circuit_breaker_active(pd.DataFrame())
        assert not active
        assert reason == "INDEX_DATA_UNAVAILABLE"

        df_no_close = pd.DataFrame({"volume": [100, 200]})
        active2, reason2 = is_macro_circuit_breaker_active(df_no_close)
        assert not active2
        assert reason2 == "INDEX_DATA_UNAVAILABLE"

    def test_downtrend_triggers_circuit_breaker(self):
        """Downtrend index series should trigger circuit breaker."""
        # Simulated continuous downward index (1500 down to 900)
        dates = pd.date_range("2022-01-01", periods=100)
        close_prices = np.linspace(1500, 900, 100)
        df_index = pd.DataFrame({"close": close_prices}, index=dates)

        active, reason = is_macro_circuit_breaker_active(df_index)
        assert active is True
        assert reason == "VN-INDEX_DOWNTREND_CIRCUIT_BREAKER"

    def test_uptrend_keeps_circuit_breaker_inactive(self):
        """Uptrend index series should keep circuit breaker inactive."""
        dates = pd.date_range("2023-01-01", periods=100)
        close_prices = np.linspace(1000, 1300, 100)
        df_index = pd.DataFrame({"close": close_prices}, index=dates)

        active, reason = is_macro_circuit_breaker_active(df_index)
        assert active is False
        assert reason == "MARKET_HEALTHY_OR_SIDEWAYS"


class TestQuantEngineRiskControls:
    """Test suite for Drawdown Sizing, Liquidity Absorption, and Smart Money Flow."""

    def test_drawdown_controlled_sizing_standard(self):
        """Normal conditions should keep standard Half-Kelly size up to max cap."""
        size, reason = calculate_drawdown_controlled_sizing(
            half_kelly_f=0.12, consecutive_losses=0, current_drawdown_pct=2.0
        )
        assert size == 0.12
        assert reason == "STANDARD_HALF_KELLY"

    def test_drawdown_controlled_sizing_cap(self):
        """Should cap position size at max_cap_pct (e.g. 20%)."""
        size, _ = calculate_drawdown_controlled_sizing(half_kelly_f=0.35, max_cap_pct=0.20)
        assert size == 0.20

    def test_drawdown_controlled_sizing_losing_streak_defense(self):
        """2 or more consecutive losses should trigger 50% defense cut."""
        size, reason = calculate_drawdown_controlled_sizing(
            half_kelly_f=0.15, consecutive_losses=2, current_drawdown_pct=1.0
        )
        assert size == pytest.approx(0.075, rel=1e-3)
        assert reason == "DRAWDOWN_DEFENSE_HALF_SIZE"

    def test_drawdown_controlled_sizing_high_drawdown_defense(self):
        """Drawdown >= 5% should trigger 50% defense cut."""
        size, reason = calculate_drawdown_controlled_sizing(
            half_kelly_f=0.10, consecutive_losses=0, current_drawdown_pct=5.5
        )
        assert size == pytest.approx(0.05, rel=1e-3)
        assert reason == "DRAWDOWN_DEFENSE_HALF_SIZE"

    def test_drawdown_controlled_sizing_negative_kelly(self):
        """Zero or negative Kelly should allocate 0.0."""
        size, reason = calculate_drawdown_controlled_sizing(half_kelly_f=-0.05)
        assert size == 0.0
        assert reason == "KELLY_NON_POSITIVE"

    def test_adv20_liquidity_absorption_pass(self):
        """Order under 10% ADV20 should pass."""
        passed, allowed, reason = check_adv20_liquidity_absorption(
            order_val_vnd=500_000_000.0, adv20_vnd=10_000_000_000.0
        )
        assert passed is True
        assert allowed == 500_000_000.0
        assert reason == "LIQUIDITY_ABSORPTION_OK"

    def test_adv20_liquidity_absorption_exceeded(self):
        """Order over 10% ADV20 should fail and return max allowed."""
        passed, allowed, reason = check_adv20_liquidity_absorption(
            order_val_vnd=2_000_000_000.0, adv20_vnd=10_000_000_000.0
        )
        assert passed is False
        assert allowed == 1_000_000_000.0  # 10% of 10B
        assert reason == "EXCEEDS_MAX_ADV20_ABSORPTION"

    def test_adv20_liquidity_absorption_invalid_adv(self):
        """Zero or negative ADV20 should be rejected."""
        passed, allowed, reason = check_adv20_liquidity_absorption(
            order_val_vnd=100_000_000.0, adv20_vnd=0.0
        )
        assert passed is False
        assert allowed == 0.0
        assert reason == "ADV20_ZERO_OR_NEGATIVE"

    def test_smart_money_flow_heavy_sell(self):
        """Heavy institutional selling should flag heavy_selling and disallow buy."""
        res = evaluate_smart_money_flow(
            foreign_flow={"net_val_bil": -25.0},
            prop_flow={"net_val_bil": -5.0},
        )
        assert res["heavy_selling"] is True
        assert res["buy_allowed"] is False
        assert res["status"] == "INSTITUTIONAL_HEAVY_DISTRIBUTION"

    def test_smart_money_flow_strong_accumulation(self):
        """Strong accumulation should be approved."""
        res = evaluate_smart_money_flow(
            foreign_flow={"net_val_bil": 20.0},
            prop_flow={"net_val_bil": 10.0},
        )
        assert res["heavy_selling"] is False
        assert res["buy_allowed"] is True
        assert res["status"] == "INSTITUTIONAL_STRONG_ACCUMULATION"

    def test_smart_money_flow_neutral(self):
        """Moderate flows should remain neutral and allow buy."""
        res = evaluate_smart_money_flow(
            foreign_flow={"net_val_bil": 5.0},
            prop_flow={"net_val_bil": -2.0},
        )
        assert res["heavy_selling"] is False
        assert res["buy_allowed"] is True
        assert res["status"] == "INSTITUTIONAL_NEUTRAL"


class TestBacktestRegimeGateEnforcement:
    """Test suite for Regime Gate enforcement in Backtest Engine."""

    def test_quant_core_signals_suppressed_in_downtrend(self):
        """Buy signals should be blocked when enforce_regime_gate=True during Downtrend."""
        dates = pd.date_range("2023-01-01", periods=60)
        # Upward price to generate potential buy signal
        close_prices = np.linspace(20, 30, 60)
        df_price = pd.DataFrame({"close": close_prices}, index=dates)

        # Force Downtrend regime for all dates
        regimes = pd.Series(REGIME_DOWNTREND, index=dates)

        # Without regime gate -> Can generate buy signals
        signals_open = _generate_quant_core_signals(
            df_price, f_score=7, mos_pct=20.0, z_score=2.5, regimes=regimes, enforce_regime_gate=False
        )
        # With regime gate -> All buy signals suppressed
        signals_gated = _generate_quant_core_signals(
            df_price, f_score=7, mos_pct=20.0, z_score=2.5, regimes=regimes, enforce_regime_gate=True
        )

        assert (signals_gated == 1).sum() == 0
        assert signals_open.sum() >= (signals_gated.sum())

    def test_run_backtest_with_regime_gate_cash_mode(self):
        """Backtest should not enter trades during Downtrend when enforce_regime_gate=True."""
        dates = pd.date_range("2023-01-01", periods=50)
        close_prices = np.linspace(50, 40, 50)
        df_price = pd.DataFrame({"close": close_prices, "open": close_prices}, index=dates)

        # Artificial buy signals during downtrend
        signals = pd.Series(0, index=dates)
        signals.iloc[10] = 1
        signals.iloc[20] = 1

        regimes = pd.Series(REGIME_DOWNTREND, index=dates)

        engine = RegimeBacktestEngine(initial_capital=100_000_000.0)
        res_gated = engine.run_backtest(
            df_price=df_price,
            signals=signals,
            regimes=regimes,
            enforce_regime_gate=True,
        )

        # Zero trades should be executed because Cash Mode is strictly enforced
        assert len(res_gated.trades) == 0
        assert res_gated.equity_curve.iloc[-1] == 100_000_000.0
