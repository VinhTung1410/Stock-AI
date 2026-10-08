"""tests/test_ablation_study.py

Unit tests for ablation_study.py (Phase 27 - P2 Ablation Testing).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from ablation_study import (
    VAR_FULL_BASELINE,
    VAR_NO_PRICE_CONFIRM,
    AblationConfig,
    StockAblationContext,
    aggregate_ablation_summary,
    evaluate_gate_compliance,
    get_ablation_configs,
    simulate_trade_record,
)


@pytest.fixture
def mock_ablation_context():
    dates = pd.date_range("2023-01-01", periods=100, freq="B")
    base_price = 50.0
    np.random.seed(42)
    daily_returns = np.random.normal(0.001, 0.02, size=100)
    prices = base_price * np.exp(np.cumsum(daily_returns))

    df = pd.DataFrame(
        {
            "time": dates,
            "open": prices * 0.99,
            "high": prices * 1.02,
            "low": prices * 0.98,
            "close": prices,
            "volume": np.random.uniform(50_000_000, 100_000_000, size=100),
        }
    )
    b_prices = 1000.0 * np.exp(np.cumsum(np.random.normal(0.0005, 0.01, size=len(dates))))
    b_open = pd.Series(b_prices * 0.995, index=pd.DatetimeIndex(dates))
    b_close = pd.Series(b_prices, index=pd.DatetimeIndex(dates))

    return StockAblationContext("TEST", df, b_open, b_close)


def test_get_ablation_configs():
    configs = get_ablation_configs()
    assert VAR_FULL_BASELINE in configs
    assert VAR_NO_PRICE_CONFIRM in configs
    assert configs[VAR_FULL_BASELINE].require_price_confirm is True
    assert configs[VAR_NO_PRICE_CONFIRM].require_price_confirm is False


def test_evaluate_gate_compliance(mock_ablation_context):
    ctx = mock_ablation_context
    cfg_base = AblationConfig(name="test", min_panic_score=0.0, require_price_confirm=False)
    # With min_panic_score = 0 and no confirm required, should pass
    passed = evaluate_gate_compliance(ctx, i=50, cfg=cfg_base, bench_downtrend=False)
    assert passed is True

    # With impossible panic score
    cfg_strict = AblationConfig(name="test", min_panic_score=999.0)
    assert evaluate_gate_compliance(ctx, i=50, cfg=cfg_strict, bench_downtrend=False) is False


def test_simulate_trade_record(mock_ablation_context):
    ctx = mock_ablation_context
    rec = simulate_trade_record(ctx, i=50, variant_name=VAR_FULL_BASELINE)
    assert rec is not None
    assert rec["variant"] == VAR_FULL_BASELINE
    assert rec["symbol"] == "TEST"
    assert "ret_t20" in rec
    assert "alpha_t20" in rec
    assert "mae_pct" in rec


def test_aggregate_ablation_summary():
    mock_df = pd.DataFrame(
        [
            {
                "variant": VAR_FULL_BASELINE,
                "ret_t20": 5.0,
                "alpha_t20": 2.0,
                "mae_pct": -4.0,
                "mfe_pct": 10.0,
            },
            {
                "variant": VAR_FULL_BASELINE,
                "ret_t20": 10.0,
                "alpha_t20": 4.0,
                "mae_pct": -2.0,
                "mfe_pct": 15.0,
            },
            {
                "variant": VAR_NO_PRICE_CONFIRM,
                "ret_t20": 2.0,
                "alpha_t20": -1.0,
                "mae_pct": -12.0,
                "mfe_pct": 8.0,
            },
        ]
    )
    configs = {
        VAR_FULL_BASELINE: AblationConfig(name=VAR_FULL_BASELINE),
        VAR_NO_PRICE_CONFIRM: AblationConfig(name=VAR_NO_PRICE_CONFIRM),
    }

    summary = aggregate_ablation_summary(mock_df, configs)
    assert not summary.empty
    assert "Variant" in summary.columns
    assert "Verdict" in summary.columns
    base_row = summary[summary["Variant"] == VAR_FULL_BASELINE].iloc[0]
    assert base_row["N"] == 2
    assert base_row["Verdict"] == "BASELINE"


def test_each_gate_rejects_synthetic_case(mock_ablation_context):
    ctx = mock_ablation_context
    cfg_base = AblationConfig(name="base")
    
    # Mocking technical scores for an index i=50
    ctx.get_panic_max_window = lambda i, window=10: 80.0
    ctx.get_conf_score = lambda i: 50.0
    ctx.adv20_val[50] = 5.0
    ctx.base_f_score = 7
    ctx.base_mos_pct = 20.0
    
    # 1. Base should pass
    assert evaluate_gate_compliance(ctx, 50, cfg_base, bench_downtrend=False) is True
    
    # 2. Reject by Panic
    ctx.get_panic_max_window = lambda i, window=10: 60.0
    assert evaluate_gate_compliance(ctx, 50, cfg_base, bench_downtrend=False) is False
    ctx.get_panic_max_window = lambda i, window=10: 80.0 # reset
    
    # 3. Reject by Confirm
    ctx.get_conf_score = lambda i: 30.0
    assert evaluate_gate_compliance(ctx, 50, cfg_base, bench_downtrend=False) is False
    ctx.get_conf_score = lambda i: 50.0 # reset
    
    # 4. Reject by F-Score
    ctx.base_f_score = 4
    assert evaluate_gate_compliance(ctx, 50, cfg_base, bench_downtrend=False) is False
    ctx.base_f_score = 7 # reset
    
    # 5. Reject by Liquidity
    ctx.adv20_val[50] = 1.0
    assert evaluate_gate_compliance(ctx, 50, cfg_base, bench_downtrend=False) is False
    ctx.adv20_val[50] = 5.0 # reset
    
    # 6. Reject by MoS
    ctx.base_mos_pct = 10.0
    assert evaluate_gate_compliance(ctx, 50, cfg_base, bench_downtrend=False) is False
    ctx.base_mos_pct = 20.0 # reset
    
    # 7. Reject by Downtrend penalty (req 15 + 5 = 20. If base is 18, it fails in downtrend)
    ctx.base_mos_pct = 18.0
    assert evaluate_gate_compliance(ctx, 50, cfg_base, bench_downtrend=True) is False
    assert evaluate_gate_compliance(ctx, 50, cfg_base, bench_downtrend=False) is True
