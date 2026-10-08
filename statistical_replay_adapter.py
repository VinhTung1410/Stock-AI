"""statistical_replay_adapter.py

Wiring adapter connecting replay data, matched-date peers, event clustering,
marginal ablation sets, and the statistical validation engine (TASK-0082).

Enforces:
  - Exact price return convention: R_tradable = Close(D+20) / Open(D+1) - 1
  - Matched-date peer baseline: stocks not triggering signal on date D (N_peers >= 10)
  - PIT trailing 60-day rolling beta adjustment (data <= D)
  - Non-overlapping cluster definition: default gap = 20 bars (matching T+20 horizon)
  - Marginal ablation sets evaluated as marginal differences; G < 5 -> "KHÔNG THỂ KIỂM ĐỊNH (G < 5)"
  - Direct integration with statistical_validation_engine.py
"""

from __future__ import annotations

import glob
import logging
import os
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from statistical_validation_engine import (
    DEFAULT_M_HOLM,
    DELTA_ECONOMIC_HURDLE,
    MAX_CLUSTER_LENGTH_BARS,
    MIN_MARGINAL_CLUSTERS,
    MIN_PEERS_COUNT,
    VERDICT_INCONCLUSIVE,
    apply_holm_bonferroni,
    calculate_cluster_means,
    calculate_cluster_t_stats,
    check_clustering_sensitivity,
    cluster_events_with_chaining_limit_diagnostics,
    generate_dynamic_verdict,
    wild_cluster_bootstrap,
)

logger = logging.getLogger("statistical_replay_adapter")

# Verdict and Status String Constants
STATUS_CANNOT_TEST_G_TOO_SMALL: str = "KHÔNG THỂ KIỂM ĐỊNH (G < 5)"
FLAG_BOOTSTRAP_DISAGREEMENT: str = "CỜ_BẤT_ĐỒNG_BOOTSTRAP"


@dataclass
class TradeEvent:
    symbol: str
    signal_date: pd.Timestamp
    entry_date: pd.Timestamp
    exit_date: pd.Timestamp
    entry_price: float
    exit_price: float
    ret_tradable: float
    peer_baseline_ret: float
    excess_alpha: float
    beta_adj_alpha: float
    cluster_id: int = -1


@dataclass
class VariantEvaluationResult:
    variant_name: str
    n_events: int
    g_clusters: int
    cluster_se: float
    theta_hat_alpha: float
    ci_lower: float
    ci_upper: float
    rejection_hurdle_nominal: float
    rejection_hurdle_holm: float
    mde_nominal: float
    mde_holm: float
    p_value_nominal: float
    p_value_holm: float
    p_value_tost_holm: float
    binding_count: int
    marginal_clusters: int
    verdict: str
    is_marginal_test: bool
    split_clusters_count: int = 0
    sensitivity_flag: bool = False


class MatchedDatePeerEngine:
    """Computes point-in-time peer baselines and rolling betas for signals."""

    def __init__(self, price_cache: Dict[str, pd.DataFrame], bench_symbol: str = "VNINDEX"):
        self.price_cache = price_cache
        self.bench_symbol = bench_symbol
        self.bench_df = price_cache.get(bench_symbol)

    def calculate_tradable_return(
        self, df: pd.DataFrame, entry_idx: int, holding_bars: int = 20
    ) -> Optional[Tuple[float, float, float, pd.Timestamp, pd.Timestamp]]:
        """Calculate R_tradable = Close(D+holding_bars) / Open(entry_idx)."""
        exit_idx = entry_idx + holding_bars - 1
        if entry_idx >= len(df) or exit_idx >= len(df):
            return None

        open_p = float(df["open"].iloc[entry_idx])
        close_p = float(df["close"].iloc[exit_idx])
        if open_p <= 0 or close_p <= 0 or not np.isfinite(open_p) or not np.isfinite(close_p):
            return None

        ret = (close_p / open_p - 1.0) * 100.0
        d_entry = pd.to_datetime(df["time"].iloc[entry_idx])
        d_exit = pd.to_datetime(df["time"].iloc[exit_idx])
        return ret, open_p, close_p, d_entry, d_exit

    def compute_peer_baseline(
        self,
        signal_date: pd.Timestamp,
        active_symbols: List[str],
        holding_bars: int = 20,
    ) -> Tuple[float, int]:
        """Compute the unweighted average tradable return of non-triggering peer stocks."""
        peer_rets: List[float] = []

        for sym, df in self.price_cache.items():
            if sym == self.bench_symbol or sym in active_symbols or df.empty:
                continue

            # Find row matching signal_date
            matches = df.index[df["time"] == signal_date].tolist()
            if not matches:
                continue

            sig_idx = matches[0]
            entry_idx = sig_idx + 1
            res = self.calculate_tradable_return(df, entry_idx, holding_bars=holding_bars)
            if res is not None:
                peer_rets.append(res[0])

        if len(peer_rets) < MIN_PEERS_COUNT:
            # Fallback to benchmark return if peers count < 10
            bench_ret = self.compute_benchmark_return(signal_date, holding_bars=holding_bars)
            return (bench_ret if bench_ret is not None else 0.0), len(peer_rets)

        return float(np.mean(peer_rets)), len(peer_rets)

    def compute_benchmark_return(
        self, signal_date: pd.Timestamp, holding_bars: int = 20
    ) -> Optional[float]:
        if self.bench_df is None or self.bench_df.empty:
            return None
        matches = self.bench_df.index[self.bench_df["time"] == signal_date].tolist()
        if not matches:
            return None
        res = self.calculate_tradable_return(self.bench_df, matches[0] + 1, holding_bars=holding_bars)
        return res[0] if res is not None else None

    def compute_rolling_beta(
        self, symbol: str, signal_date: pd.Timestamp, window: int = 60
    ) -> float:
        """Compute PIT rolling beta against benchmark strictly using data <= signal_date."""
        df_sym = self.price_cache.get(symbol)
        if df_sym is None or self.bench_df is None:
            return 1.0

        sub_sym = df_sym[df_sym["time"] <= signal_date].tail(window + 1)
        sub_bch = self.bench_df[self.bench_df["time"] <= signal_date].tail(window + 1)
        if len(sub_sym) < window or len(sub_bch) < window:
            return 1.0

        r_sym = sub_sym["close"].pct_change().dropna()
        r_bch = sub_bch["close"].pct_change().dropna()
        common_len = min(len(r_sym), len(r_bch))
        if common_len < 20:
            return 1.0

        cov_mat = np.cov(r_sym.iloc[-common_len:], r_bch.iloc[-common_len:])
        var_bch = cov_mat[1, 1]
        return float(cov_mat[0, 1] / var_bch) if var_bch > 1e-8 else 1.0


def load_price_cache_from_directory(cache_dir: str = "data/replay_cache") -> Dict[str, pd.DataFrame]:
    """Load all cached stock price files into memory."""
    cache: Dict[str, pd.DataFrame] = {}
    pattern = os.path.join(cache_dir, "*_*.csv")
    files = glob.glob(pattern)

    for f in files:
        sym = os.path.basename(f).split("_")[0]
        try:
            df = pd.read_csv(f, parse_dates=["time"])
            df = df.sort_values("time").drop_duplicates("time").reset_index(drop=True)
            if len(df) >= 30:
                cache[sym] = df
        except Exception:
            logger.exception("Failed loading CSV for %s", sym)
    return cache


def evaluate_variant_statistics(
    variant_name: str,
    events: List[TradeEvent],
    baseline_events: Optional[List[TradeEvent]] = None,
    delta: float = DELTA_ECONOMIC_HURDLE,
    m_family: int = DEFAULT_M_HOLM,
    gap_bars: int = 20,  # Default gap 20 bars matching T+20 horizon
    max_length_bars: int = MAX_CLUSTER_LENGTH_BARS,
    binding_count: int = 0,
) -> VariantEvaluationResult:
    """Evaluate cluster statistics and hypothesis testing for a variant or its marginal set."""
    is_marginal = baseline_events is not None
    target_events = events

    # For ablation testing: isolate the marginal events (events rejected by baseline)
    if is_marginal:
        base_sigs = {(e.symbol, e.signal_date) for e in baseline_events}
        target_events = [e for e in events if (e.symbol, e.signal_date) not in base_sigs]

    n_events = len(target_events)
    if n_events == 0:
        return VariantEvaluationResult(
            variant_name=variant_name,
            n_events=0,
            g_clusters=0,
            cluster_se=float("nan"),
            theta_hat_alpha=float("nan"),
            ci_lower=float("nan"),
            ci_upper=float("nan"),
            rejection_hurdle_nominal=float("nan"),
            rejection_hurdle_holm=float("nan"),
            mde_nominal=float("nan"),
            mde_holm=float("nan"),
            p_value_nominal=1.0,
            p_value_holm=1.0,
            p_value_tost_holm=1.0,
            binding_count=binding_count,
            marginal_clusters=0,
            verdict=STATUS_CANNOT_TEST_G_TOO_SMALL,
            is_marginal_test=is_marginal,
        )

    # 1. Clustering
    event_dates = [e.signal_date for e in target_events]
    c_ids, split_count = cluster_events_with_chaining_limit_diagnostics(
        event_dates, gap_bars=gap_bars, max_length_bars=max_length_bars
    )
    for idx, e in enumerate(target_events):
        e.cluster_id = c_ids[idx]

    g_clusters = len(np.unique(c_ids))

    # Check sensitivity
    sens_res = check_clustering_sensitivity(
        event_dates, gaps=(5, 10, 20), max_length_bars=max_length_bars
    )
    sensitivity_flag = sens_res.get("is_sensitive", False)

    # Hard guard for insufficient clusters
    if g_clusters < MIN_MARGINAL_CLUSTERS:
        return VariantEvaluationResult(
            variant_name=variant_name,
            n_events=n_events,
            g_clusters=g_clusters,
            cluster_se=float("nan"),
            theta_hat_alpha=float("nan"),
            ci_lower=float("nan"),
            ci_upper=float("nan"),
            rejection_hurdle_nominal=float("nan"),
            rejection_hurdle_holm=float("nan"),
            mde_nominal=float("nan"),
            mde_holm=float("nan"),
            p_value_nominal=1.0,
            p_value_holm=1.0,
            p_value_tost_holm=1.0,
            binding_count=binding_count,
            marginal_clusters=g_clusters,
            verdict=STATUS_CANNOT_TEST_G_TOO_SMALL,
            is_marginal_test=is_marginal,
            split_clusters_count=split_count,
            sensitivity_flag=sensitivity_flag,
        )

    # 2. Estimand: Mean of cluster means
    alphas = np.array([e.excess_alpha for e in target_events], dtype=float)
    cluster_means = calculate_cluster_means(alphas, c_ids)

    # 3. Student-t cluster statistics (Primary method)
    summary = calculate_cluster_t_stats(cluster_means, delta=delta, m_family=m_family)

    # Holm correction
    adj_alpha_p = apply_holm_bonferroni([summary.p_value_alpha], m_family=m_family)[0]
    adj_tost_p = apply_holm_bonferroni([summary.p_value_tost], m_family=m_family)[0]

    # Dynamic verdict
    verdict = generate_dynamic_verdict(
        p_holm_alpha=adj_alpha_p,
        p_holm_tost=adj_tost_p,
        sensitivity_flag=sensitivity_flag,
    )

    # 4. Secondary check: Wild Cluster Bootstrap (Bootstrap-t)
    p_boot, ci_b_low, _ = wild_cluster_bootstrap(
        cluster_means, null_theta=delta, n_boot=1000, seed=42
    )
    # Flag disagreement if bootstrap would make a different decision
    boot_alpha_decision = (summary.theta_hat > delta) and (p_boot < 0.05 / m_family)
    t_alpha_decision = adj_alpha_p < 0.05
    if boot_alpha_decision != t_alpha_decision and verdict != VERDICT_INCONCLUSIVE:
        verdict = f"{verdict} ({FLAG_BOOTSTRAP_DISAGREEMENT})"

    # 5. Distinctly compute Rejection Hurdle vs MDE for power 80%
    df = g_clusters - 1
    from scipy import stats

    t_crit_single = float(stats.t.ppf(0.95, df=df))
    t_crit_holm = float(stats.t.ppf(1.0 - 0.05 / m_family, df=df))
    t_power = float(stats.t.ppf(0.80, df=df))

    rejection_hurdle_nominal = delta + t_crit_single * summary.cluster_se
    rejection_hurdle_holm = delta + t_crit_holm * summary.cluster_se

    mde_nominal = (t_crit_single + t_power) * summary.cluster_se
    mde_holm = (t_crit_holm + t_power) * summary.cluster_se

    return VariantEvaluationResult(
        variant_name=variant_name,
        n_events=n_events,
        g_clusters=g_clusters,
        cluster_se=round(summary.cluster_se, 2),
        theta_hat_alpha=round(summary.theta_hat, 2),
        ci_lower=round(summary.ci_lower, 2),
        ci_upper=round(summary.ci_upper, 2),
        rejection_hurdle_nominal=round(rejection_hurdle_nominal, 2),
        rejection_hurdle_holm=round(rejection_hurdle_holm, 2),
        mde_nominal=round(mde_nominal, 2),
        mde_holm=round(mde_holm, 2),
        p_value_nominal=round(summary.p_value_alpha, 4),
        p_value_holm=round(adj_alpha_p, 4),
        p_value_tost_holm=round(adj_tost_p, 4),
        binding_count=binding_count,
        marginal_clusters=g_clusters if is_marginal else 0,
        verdict=verdict,
        is_marginal_test=is_marginal,
        split_clusters_count=split_count,
        sensitivity_flag=sensitivity_flag,
    )
