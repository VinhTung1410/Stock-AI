"""tests/test_statistical_validation_engine.py

Unit tests for statistical_validation_engine.py (TASK-0082).
Verifies:
  - Event clustering with 40-bar chaining limit
  - Sensitivity analysis across 5, 10, 20 bar gaps
  - Estimand calculation (mean of cluster means)
  - Student-t cluster statistics, MDE, and CI
  - Wild Cluster Bootstrap with Webb 6-point distribution
  - Holm-Bonferroni correction with pre-specified family size (m=40)
  - Dynamic 3-way verdicts
  - Monte Carlo acceptance test safety gate
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from statistical_validation_engine import (
    DEFAULT_M_HOLM,
    DELTA_ECONOMIC_HURDLE,
    FLAG_SENSITIVE_CLUSTERING,
    VERDICT_ALPHA,
    VERDICT_INCONCLUSIVE,
    VERDICT_NO_EFFECT,
    apply_holm_bonferroni,
    calculate_cluster_means,
    calculate_cluster_t_stats,
    check_clustering_sensitivity,
    cluster_events_with_chaining_limit,
    generate_dynamic_verdict,
    run_monte_carlo_acceptance_test,
    verify_engine_safety_gate,
    wild_cluster_bootstrap,
)


def test_cluster_events_with_chaining_limit_empty():
    res = cluster_events_with_chaining_limit([])
    assert len(res) == 0


def test_cluster_events_with_chaining_limit_basic():
    # Events spanning days
    dates = pd.to_datetime(["2023-01-01", "2023-01-05", "2023-01-20", "2023-01-25"])
    # First two are gap=4 (<= 10), then gap=15 (>10), then gap=5 (<=10)
    c_ids = cluster_events_with_chaining_limit(dates, gap_bars=10, max_length_bars=40)
    assert c_ids[0] == 0
    assert c_ids[1] == 0
    assert c_ids[2] == 1
    assert c_ids[3] == 1


def test_cluster_events_with_chaining_limit_max_length_split():
    # Events occurring every 5 days continuously for 60 days
    dates = pd.date_range("2023-01-01", periods=13, freq="5D")
    c_ids = cluster_events_with_chaining_limit(dates, gap_bars=10, max_length_bars=40)
    # Total span is 60 days, so it must be split when exceeding 40 days
    assert len(np.unique(c_ids)) >= 2


def test_check_clustering_sensitivity():
    dates = pd.date_range("2023-01-01", periods=10, freq="7D")
    sens = check_clustering_sensitivity(dates, gaps=(5, 10, 20), max_length_bars=40)
    assert "g_by_gap" in sens
    assert "is_sensitive" in sens
    assert 5 in sens["g_by_gap"]
    assert 10 in sens["g_by_gap"]
    assert 20 in sens["g_by_gap"]


def test_check_clustering_sensitivity_empty():
    sens = check_clustering_sensitivity([])
    assert sens["is_sensitive"] is False
    assert len(sens["g_by_gap"]) == 0


def test_calculate_cluster_means():
    values = np.array([10.0, 20.0, 5.0, 15.0])
    c_ids = np.array([0, 0, 1, 1])
    means = calculate_cluster_means(values, c_ids)
    assert len(means) == 2
    assert means[0] == 15.0
    assert means[1] == 10.0


def test_calculate_cluster_t_stats_small_sample():
    stats_res = calculate_cluster_t_stats(np.array([5.0]))
    assert stats_res.g_clusters == 1
    assert np.isnan(stats_res.cluster_se)


def test_calculate_cluster_t_stats_standard():
    cluster_means = np.array([5.0, 6.0, 7.0, 8.0, 9.0, 10.0, 11.0, 12.0, 13.0, 14.0, 15.0, 16.0, 17.0])
    summary = calculate_cluster_t_stats(cluster_means, delta=DELTA_ECONOMIC_HURDLE)
    assert summary.g_clusters == 13
    assert summary.theta_hat == pytest.approx(11.0)
    assert summary.cluster_se > 0
    assert summary.mde > 0
    assert summary.ci_lower < summary.theta_hat < summary.ci_upper
    # Since theta_hat = 11.0 >> delta = 2.5, p_value_alpha should be very small
    assert summary.p_value_alpha < 0.01


def test_wild_cluster_bootstrap():
    cluster_means = np.array([6.0, 8.0, 7.0, 9.0, 10.0, 12.0, 11.0, 13.0, 14.0, 15.0, 16.0, 17.0, 18.0])
    p_val, ci_low, ci_high = wild_cluster_bootstrap(
        cluster_means,
        null_theta=DELTA_ECONOMIC_HURDLE,
        n_boot=200,
        seed=42,
    )
    assert 0.0 <= p_val <= 1.0
    assert np.isfinite(ci_low)
    assert np.isfinite(ci_high)
    assert ci_low < ci_high

    # Edge case: G < 2
    p_single, _, _ = wild_cluster_bootstrap(np.array([5.0]))
    assert p_single == 1.0


def test_apply_holm_bonferroni():
    p_vals = [0.001, 0.02, 0.04]
    adj = apply_holm_bonferroni(p_vals, m_family=10)
    assert len(adj) == 3
    # First p-value adjusted by 10
    assert adj[0] == pytest.approx(0.01)
    # Monotonicity preserved
    assert adj[0] <= adj[1] <= adj[2]
    assert np.all(adj <= 1.0)

    # Empty list
    assert len(apply_holm_bonferroni([])) == 0


def test_apply_holm_bonferroni_partial_family_multipliers():
    """Verify that when only n < m p-values are tested (Point D2),
    Holm-Bonferroni treats unmeasured hypotheses as p=1.0 and applies
    multipliers (m, m-1, ..., m-n+1).
    """
    m_family = 40
    # 5 test p-values sorted
    p_vals = [0.0005, 0.0010, 0.0020, 0.0050, 0.0100]
    adj = apply_holm_bonferroni(p_vals, m_family=m_family)
    assert len(adj) == 5

    # Multipliers must be 40, 39, 38, 37, 36
    expected_0 = min(1.0, 0.0005 * 40)  # 0.020
    expected_1 = min(1.0, 0.0010 * 39)  # 0.039
    expected_2 = min(1.0, 0.0020 * 38)  # 0.076
    expected_3 = min(1.0, 0.0050 * 37)  # 0.185
    expected_4 = min(1.0, 0.0100 * 36)  # 0.360

    assert adj[0] == pytest.approx(expected_0)
    assert adj[1] == pytest.approx(expected_1)
    assert adj[2] == pytest.approx(expected_2)
    assert adj[3] == pytest.approx(expected_3)
    assert adj[4] == pytest.approx(expected_4)


def test_alpha_detection_on_heavy_tailed_dgp_with_outlier():
    """Verify that on realistic heavy-tailed DGP with +26% outlier (Point D3),
    a genuine large alpha (+22%) yields the ALPHA verdict under Holm m=40.
    """
    rng = np.random.default_rng(42)
    g = 13
    # Non-Gaussian DGP with VIC +26% shock
    c_shocks = (rng.chisquare(df=3, size=g) - 3.0) * 1.5
    c_shocks[0] += 26.0 - 2.6
    noise = rng.standard_t(df=4, size=g) * 2.0

    # Strong true alpha = +22%
    true_alpha = 22.0
    cluster_means = c_shocks + noise + true_alpha

    summary = calculate_cluster_t_stats(cluster_means, delta=DELTA_ECONOMIC_HURDLE, m_family=DEFAULT_M_HOLM)
    assert summary.theta_hat > 20.0
    assert summary.cluster_se > 0.0

    adj_p_alpha = apply_holm_bonferroni([summary.p_value_alpha], m_family=DEFAULT_M_HOLM)[0]
    verdict = generate_dynamic_verdict(p_holm_alpha=adj_p_alpha, p_holm_tost=1.0)
    assert verdict == VERDICT_ALPHA


def test_generate_dynamic_verdict():
    # Alpha confirmed
    v_alpha = generate_dynamic_verdict(p_holm_alpha=0.01, p_holm_tost=0.50)
    assert v_alpha == VERDICT_ALPHA

    # No effect confirmed
    v_no_effect = generate_dynamic_verdict(p_holm_alpha=0.50, p_holm_tost=0.02)
    assert v_no_effect == VERDICT_NO_EFFECT

    # Inconclusive
    v_inconclusive = generate_dynamic_verdict(p_holm_alpha=0.20, p_holm_tost=0.20)
    assert v_inconclusive == VERDICT_INCONCLUSIVE

    # With sensitivity flag
    v_flagged = generate_dynamic_verdict(p_holm_alpha=0.01, p_holm_tost=0.50, sensitivity_flag=True)
    assert FLAG_SENSITIVE_CLUSTERING in v_flagged


def test_monte_carlo_acceptance_test_and_safety_gate(tmp_path):
    # Run a fast 500-sim check for unit test speed
    res = run_monte_carlo_acceptance_test(n_sim=500, seed=42)
    assert "passed" in res
    assert "student_t_coverage" in res
    assert "wild_bootstrap_coverage" in res
    assert "empirical_power_holm40" in res

    # Verify verify_engine_safety_gate raises RuntimeError on forced failure
    def mock_failure(n_sim: int = 2000, seed: int = 42):
        return {"passed": False}

    import statistical_validation_engine

    orig = statistical_validation_engine.run_monte_carlo_acceptance_test
    try:
        statistical_validation_engine.run_monte_carlo_acceptance_test = mock_failure
        mock_path = str(tmp_path / "mock_report.json")
        with pytest.raises(RuntimeError, match="CRITICAL"):
            verify_engine_safety_gate(n_sim=10, report_path=mock_path)
    finally:
        statistical_validation_engine.run_monte_carlo_acceptance_test = orig
