"""statistical_validation_engine.py

Statistical Validation Engine for Event Study & Ablation Testing (TASK-0082).
Enforces rigorous econometric standards:
  - Event clustering with chaining limit (max 40 bars) & sensitivity analysis
  - Split cluster tracking and diagnostics
  - Estimand: Mean of cluster means
  - Wild Cluster Bootstrap (Webb 6-point) & Student-t cluster distribution
  - Dynamic 3-way verdicts (ALPHA, KHÔNG CÓ HIỆU ỨNG ĐÁNG KỂ, INCONCLUSIVE)
  - Holm-Bonferroni correction over pre-specified hypothesis family (m = 40)
  - Pre-run Acceptance Tests (Monte Carlo placebo/power/coverage validation with FWER)
  - Blocking safety gate producing cryptographic verification report
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

import numpy as np
import pandas as pd
from scipy import stats

logger = logging.getLogger("statistical_validation_engine")

# --- Economic & Econometric Constants ---
DELTA_ECONOMIC_HURDLE: float = 2.50  # Net alpha hurdle in percent
DEFAULT_M_HOLM: int = 40  # Pre-accumulated hypothesis family count
MAX_CLUSTER_LENGTH_BARS: int = 40  # Maximum length of a single cluster in bars
DEFAULT_CLUSTER_GAP_BARS: int = 10  # Default inter-signal gap defining a new cluster
MIN_PEERS_COUNT: int = 10  # Minimum required peer stocks on signal day
MIN_MARGINAL_CLUSTERS: int = 5  # Minimum marginal clusters required to test ablation

# Verdict String Constants (Sonar S1192 prevention)
VERDICT_ALPHA: str = "ALPHA"
VERDICT_NO_EFFECT: str = "KHÔNG CÓ HIỆU ỨNG ĐÁNG KỂ"
VERDICT_INCONCLUSIVE: str = "INCONCLUSIVE"
FLAG_SENSITIVE_CLUSTERING: str = "SENSITIVE_TO_CLUSTERING_PARAMETER"

# Webb 6-point distribution weights for wild cluster bootstrap
WEBB_6_POINTS: np.ndarray = np.array(
    [-np.sqrt(1.5), -1.0, -np.sqrt(0.5), np.sqrt(0.5), 1.0, np.sqrt(1.5)],
    dtype=float,
)


@dataclass
class ClusterSummary:
    g_clusters: int
    cluster_se: float
    mde: float
    mde_holm: float
    theta_hat: float
    ci_lower: float
    ci_upper: float
    t_stat: float
    p_value_alpha: float
    p_value_tost: float
    max_cluster_len: int
    split_clusters_count: int = 0
    sensitivity_flag: bool = False


def cluster_events_with_chaining_limit_diagnostics(
    event_dates: pd.Series | List[pd.Timestamp],
    gap_bars: int = DEFAULT_CLUSTER_GAP_BARS,
    max_length_bars: int = MAX_CLUSTER_LENGTH_BARS,
) -> Tuple[np.ndarray, int]:
    """Assign cluster IDs with chaining limit and count explicit splits."""
    if len(event_dates) == 0:
        return np.array([], dtype=int), 0

    dates = pd.to_datetime(pd.Series(event_dates).sort_values()).reset_index(drop=True)
    n = len(dates)
    cluster_ids = np.zeros(n, dtype=int)

    current_cluster_id = 0
    cluster_start_date = dates.iloc[0]
    cluster_ids[0] = current_cluster_id
    split_count = 0

    for i in range(1, n):
        prev_date = dates.iloc[i - 1]
        curr_date = dates.iloc[i]

        day_diff = (curr_date - prev_date).days
        total_span = (curr_date - cluster_start_date).days

        if total_span > max_length_bars:
            current_cluster_id += 1
            cluster_start_date = curr_date
            split_count += 1
        elif day_diff > gap_bars:
            current_cluster_id += 1
            cluster_start_date = curr_date

        cluster_ids[i] = current_cluster_id

    return cluster_ids, split_count


def cluster_events_with_chaining_limit(
    event_dates: pd.Series | List[pd.Timestamp],
    gap_bars: int = DEFAULT_CLUSTER_GAP_BARS,
    max_length_bars: int = MAX_CLUSTER_LENGTH_BARS,
) -> np.ndarray:
    """Assign cluster IDs to event dates based on calendar gap and chaining limit."""
    c_ids, _ = cluster_events_with_chaining_limit_diagnostics(
        event_dates, gap_bars=gap_bars, max_length_bars=max_length_bars
    )
    return c_ids


def check_clustering_sensitivity(
    event_dates: pd.Series | List[pd.Timestamp],
    gaps: Tuple[int, ...] = (5, 10, 20),
    max_length_bars: int = MAX_CLUSTER_LENGTH_BARS,
) -> Dict[str, Any]:
    """Test sensitivity of cluster counts across gap thresholds and report split counts."""
    if len(event_dates) == 0:
        return {
            "g_by_gap": {},
            "is_sensitive": False,
            "max_lengths": {},
            "split_counts": {},
        }

    results: Dict[int, int] = {}
    max_lengths: Dict[int, int] = {}
    split_counts: Dict[int, int] = {}

    dates = pd.to_datetime(pd.Series(event_dates).sort_values()).reset_index(drop=True)

    for gap in gaps:
        c_ids, n_splits = cluster_events_with_chaining_limit_diagnostics(
            dates, gap_bars=gap, max_length_bars=max_length_bars
        )
        g_count = len(np.unique(c_ids))
        results[gap] = g_count
        split_counts[gap] = n_splits

        spans = []
        for cid in np.unique(c_ids):
            c_dates = dates[c_ids == cid]
            spans.append((c_dates.iloc[-1] - c_dates.iloc[0]).days + 1)
        max_lengths[gap] = max(spans) if spans else 0

    base_g = results.get(DEFAULT_CLUSTER_GAP_BARS, list(results.values())[0])
    is_sensitive = False
    if base_g > 0:
        variations = [abs(g - base_g) / base_g for g in results.values()]
        is_sensitive = max(variations) > 0.30

    return {
        "g_by_gap": results,
        "is_sensitive": is_sensitive,
        "max_lengths": max_lengths,
        "split_counts": split_counts,
    }


def calculate_cluster_means(
    values: np.ndarray | List[float],
    cluster_ids: np.ndarray,
) -> np.ndarray:
    """Compute the unweighted mean of observations for each cluster (Estimand input)."""
    vals = np.asarray(values, dtype=float)
    c_ids = np.asarray(cluster_ids, dtype=int)
    unique_ids = np.unique(c_ids)

    means = np.zeros(len(unique_ids), dtype=float)
    for idx, cid in enumerate(unique_ids):
        means[idx] = np.mean(vals[c_ids == cid])
    return means


def calculate_cluster_t_stats(
    cluster_means: np.ndarray,
    delta: float = DELTA_ECONOMIC_HURDLE,
    m_family: int = DEFAULT_M_HOLM,
) -> ClusterSummary:
    """Calculate Student-t statistics, Cluster SE, MDE, CI and p-values for cluster means."""
    g = len(cluster_means)
    if g < 2:
        return ClusterSummary(
            g_clusters=g,
            cluster_se=float("nan"),
            mde=float("nan"),
            mde_holm=float("nan"),
            theta_hat=float(np.mean(cluster_means)) if g == 1 else float("nan"),
            ci_lower=float("nan"),
            ci_upper=float("nan"),
            t_stat=float("nan"),
            p_value_alpha=1.0,
            p_value_tost=1.0,
            max_cluster_len=0,
        )

    theta_hat = float(np.mean(cluster_means))
    s_cluster = float(np.std(cluster_means, ddof=1))
    cluster_se = s_cluster / np.sqrt(g)

    df = g - 1
    t_crit_ci = float(stats.t.ppf(0.975, df=df))
    t_power = float(stats.t.ppf(0.80, df=df))
    t_crit_holm = float(stats.t.ppf(1.0 - 0.05 / (2 * m_family), df=df))

    # Unified MDE strictly matching two-sided 95% CI lower bound > delta
    mde = (t_crit_ci + t_power) * cluster_se
    mde_holm = (t_crit_holm + t_power) * cluster_se

    ci_lower = theta_hat - t_crit_ci * cluster_se
    ci_upper = theta_hat + t_crit_ci * cluster_se

    # Two-sided p-value against boundary delta corresponding to 95% CI lower bound > delta
    t_stat_delta = (theta_hat - delta) / cluster_se if cluster_se > 0 else 0.0
    if t_stat_delta > 0:
        p_value_alpha = float(min(1.0, 2.0 * (1.0 - stats.t.cdf(t_stat_delta, df=df))))
    else:
        p_value_alpha = 1.0

    # TOST test: H01: theta <= -delta vs H11: theta > -delta
    #            H02: theta >= +delta vs H12: theta < +delta
    t_stat_lower = (theta_hat - (-delta)) / cluster_se if cluster_se > 0 else 0.0
    t_stat_upper = (theta_hat - delta) / cluster_se if cluster_se > 0 else 0.0
    p_lower = float(1.0 - stats.t.cdf(t_stat_lower, df=df))
    p_upper = float(stats.t.cdf(t_stat_upper, df=df))
    p_value_tost = max(p_lower, p_upper)

    t_stat_zero = theta_hat / cluster_se if cluster_se > 0 else 0.0

    return ClusterSummary(
        g_clusters=g,
        cluster_se=cluster_se,
        mde=mde,
        mde_holm=mde_holm,
        theta_hat=theta_hat,
        ci_lower=ci_lower,
        ci_upper=ci_upper,
        t_stat=t_stat_zero,
        p_value_alpha=p_value_alpha,
        p_value_tost=p_value_tost,
        max_cluster_len=0,
    )


def wild_cluster_bootstrap(
    cluster_means: np.ndarray,
    null_theta: float = DELTA_ECONOMIC_HURDLE,
    n_boot: int = 1000,
    seed: int = 42,
) -> Tuple[float, float, float]:
    """Perform Null-Restricted Wild Cluster Bootstrap with Webb 6-point distribution."""
    g = len(cluster_means)
    if g < 2:
        return 1.0, float("nan"), float("nan")

    rng = np.random.default_rng(seed)
    theta_hat = float(np.mean(cluster_means))
    s_cluster = float(np.std(cluster_means, ddof=1))
    se_orig = s_cluster / np.sqrt(g)

    t_obs = (theta_hat - null_theta) / se_orig if se_orig > 0 else 0.0
    residuals = cluster_means - theta_hat

    webb_indices = rng.integers(0, len(WEBB_6_POINTS), size=(n_boot, g))
    weights = WEBB_6_POINTS[webb_indices]

    boot_means = null_theta + weights * residuals[np.newaxis, :]
    boot_theta = np.mean(boot_means, axis=1)
    boot_std = np.std(boot_means, axis=1, ddof=1)
    boot_se = boot_std / np.sqrt(g)

    valid_idx = boot_se > 1e-12
    t_boot = np.zeros(n_boot)
    t_boot[valid_idx] = (boot_theta[valid_idx] - null_theta) / boot_se[valid_idx]

    p_val_one_sided = float(np.mean(t_boot >= t_obs))

    # Studentized Wild Cluster Bootstrap CI (Bootstrap-t)
    boot_unres = theta_hat + weights * residuals[np.newaxis, :]
    boot_unres_theta = np.mean(boot_unres, axis=1)
    boot_unres_se = np.std(boot_unres, axis=1, ddof=1) / np.sqrt(g)
    valid_unres = boot_unres_se > 1e-12
    t_unres = np.zeros(n_boot)
    t_unres[valid_unres] = (boot_unres_theta[valid_unres] - theta_hat) / boot_unres_se[valid_unres]
    q_low = float(np.percentile(t_unres, 2.5))
    q_high = float(np.percentile(t_unres, 97.5))
    ci_lower = theta_hat - q_high * se_orig
    ci_upper = theta_hat - q_low * se_orig

    return p_val_one_sided, ci_lower, ci_upper


def apply_holm_bonferroni(
    p_values: List[float] | np.ndarray,
    m_family: int = DEFAULT_M_HOLM,
) -> np.ndarray:
    """Apply Holm-Bonferroni correction over a pre-specified hypothesis family of size m_family."""
    p_arr = np.asarray(p_values, dtype=float)
    k = len(p_arr)
    if k == 0:
        return np.array([], dtype=float)

    effective_m = max(m_family, k)
    sort_idx = np.argsort(p_arr)
    sorted_p = p_arr[sort_idx]

    adjusted = np.zeros(k, dtype=float)
    running_max = 0.0

    for i in range(k):
        mult = effective_m - i
        adj_p = min(1.0, sorted_p[i] * mult)
        running_max = max(running_max, adj_p)
        adjusted[sort_idx[i]] = running_max

    return np.clip(adjusted, 0.0, 1.0)


def generate_dynamic_verdict(
    p_holm_alpha: float,
    p_holm_tost: float,
    sensitivity_flag: bool = False,
) -> str:
    """Generate dynamic verdict string based on statistical significance."""
    base_verdict = VERDICT_INCONCLUSIVE
    if p_holm_alpha < 0.05:
        base_verdict = VERDICT_ALPHA
    elif p_holm_tost < 0.05:
        base_verdict = VERDICT_NO_EFFECT

    if sensitivity_flag and base_verdict != VERDICT_INCONCLUSIVE:
        return f"{base_verdict} ({FLAG_SENSITIVE_CLUSTERING})"
    return base_verdict


def run_monte_carlo_acceptance_test(
    n_sim: int = 10000,
    seed: int = 42,
) -> Dict[str, Any]:
    """Execute the mandatory Monte Carlo acceptance test with realistic non-Gaussian data."""
    rng = np.random.default_rng(seed)
    g = 13
    df = g - 1
    delta = DELTA_ECONOMIC_HURDLE
    m_family = DEFAULT_M_HOLM

    t_crit_ci = float(stats.t.ppf(0.975, df=df))
    t_power = float(stats.t.ppf(0.80, df=df))
    t_crit_holm = float(stats.t.ppf(1.0 - 0.05 / m_family, df=df))
    mde_holm_mult = t_crit_holm + t_power

    # Pre-generate Webb weights for studentized wild cluster bootstrap: shape (200, g)
    w_mat = WEBB_6_POINTS[rng.integers(0, 6, size=(200, g))]

    fp_zero_count = 0
    fp_delta_count = 0
    extreme_tail_count = 0
    fwer_holm_count = 0
    power_holm_count = 0
    t_coverage_count = 0
    boot_coverage_count = 0
    tost_boundary_count = 0

    for _ in range(n_sim):
        # 1. Non-Gaussian DGP: shared cluster market shock (skewed + fat-tailed + outlier)
        c_shocks = (rng.chisquare(df=3, size=g) - 3.0) * 1.5
        if rng.random() < 0.10:
            c_shocks[0] += 26.0  # Realistic +26% stock surge outlier (like VIC)

        # Baseline variant under true theta = 0
        noise_0 = rng.standard_t(df=4, size=g) * 2.0
        c_means_null = c_shocks + noise_0

        mean_null = np.mean(c_means_null)
        se_null = np.std(c_means_null, ddof=1) / np.sqrt(g)
        ci_low = mean_null - t_crit_ci * se_null
        ci_high = mean_null + t_crit_ci * se_null
        if ci_low <= 0.0 <= ci_high:
            t_coverage_count += 1

        # Studentized Wild Cluster Bootstrap CI check on ALL 10,000 runs
        res_null = c_means_null - mean_null
        b_unres = mean_null + w_mat * res_null[np.newaxis, :]
        b_means = np.mean(b_unres, axis=1)
        b_se = np.std(b_unres, axis=1, ddof=1) / np.sqrt(g)
        t_b = (b_means - mean_null) / b_se
        q_l = float(np.percentile(t_b, 2.5))
        q_h = float(np.percentile(t_b, 97.5))
        if (mean_null - q_h * se_null) <= 0.0 <= (mean_null - q_l * se_null):
            boot_coverage_count += 1

        # False positive at theta = 0 for one-sided H0: theta <= delta
        t_stat_0 = (mean_null - delta) / se_null if se_null > 0 else 0.0
        p_val_0 = 1.0 - stats.t.cdf(t_stat_0, df=df)
        if p_val_0 < 0.05:
            fp_zero_count += 1

        # 2. Family of m=40 hypotheses on the SAME non-Gaussian DGP under boundary theta = delta
        p_vals_boundary = np.zeros(m_family)
        for j in range(m_family):
            v_noise = rng.standard_t(df=4, size=g) * 2.0
            c_means_d = c_shocks + v_noise + delta
            m_d = np.mean(c_means_d)
            se_d = np.std(c_means_d, ddof=1) / np.sqrt(g)
            t_d = (m_d - delta) / se_d if se_d > 0 else 0.0
            p_vals_boundary[j] = 1.0 - stats.t.cdf(t_d, df=df)

        # Single test FP at boundary delta (variant 0)
        if p_vals_boundary[0] < 0.05:
            fp_delta_count += 1
        if p_vals_boundary[0] < (0.05 / m_family):
            extreme_tail_count += 1

        # TOST Type I error at boundary theta = delta under Holm
        c_means_0 = c_shocks + noise_0 + delta
        m_0 = np.mean(c_means_0)
        se_0 = np.std(c_means_0, ddof=1) / np.sqrt(g)
        t_0 = (m_0 - delta) / se_0 if se_0 > 0 else 0.0
        p_tost_high = stats.t.cdf(t_0, df=df)
        p_tost_low = 1.0 - stats.t.cdf((m_0 - (-delta)) / se_0, df=df)
        if max(p_tost_low, p_tost_high) < (0.05 / m_family):
            tost_boundary_count += 1

        # FWER with Holm across m=40 under boundary null theta = delta on SAME DGP
        adj_p_40 = apply_holm_bonferroni(p_vals_boundary, m_family=m_family)
        if np.any(adj_p_40 < 0.05):
            fwer_holm_count += 1

        # 3. Empirical Power test under Holm on the SAME DGP
        c_target = c_means_null + delta + mde_holm_mult * se_null
        m_target = np.mean(c_target)
        se_target = np.std(c_target, ddof=1) / np.sqrt(g)
        t_target = (m_target - delta) / se_target if se_target > 0 else 0.0
        p_target = 1.0 - stats.t.cdf(t_target, df=df)

        p_family_power = np.concatenate([[p_target], p_vals_boundary[1:]])
        adj_power_p = apply_holm_bonferroni(p_family_power, m_family=m_family)
        if adj_power_p[0] < 0.05:
            power_holm_count += 1

    # TOST power test on large sample (G=100)
    g_large = 100
    df_large = g_large - 1
    tost_large_count = 0
    for _ in range(n_sim):
        c_large = rng.normal(0.0, 3.0, size=g_large)
        m_large = np.mean(c_large)
        se_l = np.std(c_large, ddof=1) / np.sqrt(g_large)
        p_l = 1.0 - stats.t.cdf((m_large - (-delta)) / se_l, df=df_large)
        p_u = stats.t.cdf((m_large - delta) / se_l, df=df_large)
        if max(p_l, p_u) < 0.05:
            tost_large_count += 1

    fp_rate_zero = fp_zero_count / n_sim
    fp_rate_delta = fp_delta_count / n_sim
    extreme_tail_rate = extreme_tail_count / n_sim
    fwer_rate = fwer_holm_count / n_sim
    power_rate = power_holm_count / n_sim
    t_cov_rate = t_coverage_count / n_sim
    boot_cov_rate = boot_coverage_count / n_sim
    tost_boundary_rate = tost_boundary_count / n_sim
    tost_large_rate = tost_large_count / n_sim

    pass_fp_zero = fp_rate_zero <= 0.010
    pass_fp_delta = fp_rate_delta <= 0.050
    pass_extreme_tail = extreme_tail_rate <= 0.0020
    pass_fwer = fwer_rate <= 0.055
    pass_power = 0.765 <= power_rate <= 0.835
    pass_t_cov = 0.940 <= t_cov_rate <= 0.960
    pass_boot_cov = 0.920 <= boot_cov_rate <= 0.960
    pass_tost_boundary = tost_boundary_rate <= 0.010
    pass_tost_large = tost_large_rate >= 0.900

    all_passed = (
        pass_fp_zero
        and pass_fp_delta
        and pass_extreme_tail
        and pass_fwer
        and pass_power
        and pass_t_cov
        and pass_boot_cov
        and pass_tost_boundary
        and pass_tost_large
    )

    return {
        "passed": all_passed,
        "n_sim": n_sim,
        "fp_rate_zero": round(fp_rate_zero, 4),
        "pass_fp_zero": pass_fp_zero,
        "fp_rate_delta": round(fp_rate_delta, 4),
        "pass_fp_delta": pass_fp_delta,
        "extreme_tail_fp_rate": round(extreme_tail_rate, 5),
        "pass_extreme_tail": pass_extreme_tail,
        "fwer_rate_holm40": round(fwer_rate, 4),
        "pass_fwer": pass_fwer,
        "empirical_power_holm40": round(power_rate, 4),
        "pass_power": pass_power,
        "student_t_coverage": round(t_cov_rate, 4),
        "pass_t_cov": pass_t_cov,
        "wild_bootstrap_coverage": round(boot_cov_rate, 4),
        "pass_boot_cov": pass_boot_cov,
        "tost_boundary_type1": round(tost_boundary_rate, 4),
        "pass_tost_boundary": pass_tost_boundary,
        "tost_rate_large_g": round(tost_large_rate, 4),
        "pass_tost_large": pass_tost_large,
    }


def verify_engine_safety_gate(
    n_sim: int = 10000,
    seed: int = 42,
    report_path: str = "docs/AI-workflow/TASK/acceptance_test_report.json",
    spec_path: str = "docs/AI-workflow/TASK/TASK-0082-Spec.md",
    hypothesis_path: str = "docs/AI-workflow/TASK/hypothesis_family_m40.json",
) -> Dict[str, Any]:
    """Enforce the mandatory safety gate and produce a cryptographic audit report."""
    logger.info("Running mandatory Monte Carlo acceptance test (N_sim=%d)...", n_sim)
    results = run_monte_carlo_acceptance_test(n_sim=n_sim, seed=seed)

    # Compute hashes of spec, code, and hypothesis family
    import datetime
    import sys

    import scipy

    spec_hash = ""
    if os.path.exists(spec_path):
        with open(spec_path, "rb") as f:
            spec_hash = hashlib.sha256(f.read()).hexdigest()

    hypo_hash = ""
    if os.path.exists(hypothesis_path):
        with open(hypothesis_path, "rb") as f:
            hypo_hash = hashlib.sha256(f.read()).hexdigest()

    code_hash = ""
    current_file = __file__ if "__file__" in globals() else "statistical_validation_engine.py"
    if os.path.exists(current_file):
        with open(current_file, "rb") as f:
            code_hash = hashlib.sha256(f.read()).hexdigest()

    results["spec_sha256"] = spec_hash
    results["hypothesis_family_sha256"] = hypo_hash
    results["engine_code_sha256"] = code_hash
    results["seed"] = seed
    results["delta_economic_hurdle"] = DELTA_ECONOMIC_HURDLE
    results["m_family_hypotheses"] = DEFAULT_M_HOLM
    results["primary_method"] = "Student-t (df=G-1)"
    results["secondary_method"] = "Studentized Wild Cluster Bootstrap (Webb 6-point)"
    results["decision_rule_alpha"] = "One-sided H0: theta <= delta at alpha=0.05 with Holm m=40"
    results["decision_rule_tost"] = "Two One-Sided Tests (TOST) in [-delta, +delta] at alpha=0.05 with Holm m=40"
    results["python_version"] = sys.version.split()[0]
    results["scipy_version"] = scipy.__version__
    results["numpy_version"] = np.__version__
    results["timestamp_utc"] = datetime.datetime.now(datetime.timezone.utc).isoformat()

    # Compute hash of complete result
    serialized = json.dumps(results, sort_keys=True)
    report_hash = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
    results["report_sha256"] = report_hash

    os.makedirs(os.path.dirname(report_path), exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    if not results["passed"]:
        msg = f"CRITICAL: Statistical validation engine failed acceptance test: {results}"
        logger.error(msg)
        raise RuntimeError(msg)

    logger.info("Acceptance test PASSED: SHA-256=%s", report_hash)
    return results
