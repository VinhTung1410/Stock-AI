"""Integration Tests for Shadow Mode Pipeline (TASK-0075 / Phase 25).

Tests the full data flow:
  contrarian_engine.evaluate_contrarian_gates()
    → decision record (SHADOW_BUY)
    → update_shadow_returns.update_shadow_records_forward_returns()
    → evaluate_shadow_graduation.evaluate_shadow_graduation()

Verifies:
  1. Contrarian engine generates correct SHADOW_BUY state with shadow_mode=True
  2. Decision record structure matches what update_shadow_returns expects
  3. Forward returns flow correctly into graduation evaluator
  4. End-to-end pipeline produces consistent graduation verdicts
  5. Idempotency: re-processing does not create duplicates or mutate snapshot
  6. Edge cases: missing horizons, None vs 0.0, stale data
"""

from __future__ import annotations

from unittest.mock import patch

from contrarian_engine import (
    STATE_PANIC_BUY,
    ContrarianResult,
    evaluate_contrarian_gates,
)
from scripts.evaluate_shadow_graduation import (
    deduplicate_signal_episodes,
    estimate_effective_sample_size,
    evaluate_shadow_graduation,
)
from scripts.update_shadow_returns import update_shadow_records_forward_returns

# ---------------------------------------------------------------------------
# Fixtures: Reusable test data
# ---------------------------------------------------------------------------

def _make_shadow_buy_inputs():
    """Create inputs that trigger SHADOW_BUY through all gates."""
    fin_dict = {
        "f_score": 8,
        "f_score_details": {
            "score": 8,
            "data_completeness": 1.0,
            "passed": ["positive_net_income", "positive_cfo"],
            "failed": ["decreasing_leverage"],
        },
        "z_score": 3.5,
        "debt_equity": 50.0,
        "cfo": 500.0,
        "mos_pct": 35.0,
        "mos_is_informative": True,
        "fair_value": 50.0,
    }
    tech_data = {
        "rsi14": 18.0,
        "ma20": 50.0,
        "volume_ratio_20d": 3.5,
        "atr_ratio_14d": 2.5,
        "has_gap_down": True,
        "has_reversal_pattern": True,
        "bullish_divergence": True,
        "price_confirmation": True,
        "volume_contraction": True,
        "higher_low": True,
        "adv20_billion": 10.0,
        "is_late_session": True,
    }
    return fin_dict, tech_data


def _make_decision_record_from_result(result: ContrarianResult, decision_id: str, session: str) -> dict:
    """Transform ContrarianResult into a decision record structure matching db_manager output."""
    return {
        "decision_id": decision_id,
        "symbol": result.symbol,
        "decision": "SHADOW_BUY" if result.metrics.get("shadow_mode") else "RECOMMEND_BUY",
        "session": session,
        "created_at": f"{session} 14:30:00",
        "price": 30.0,
        "facts": {
            "snapshot_price": 30.0,
            "panic_score": result.metrics.get("panic_score", 0.0),
            "mos_pct": result.mos_pct,
            "fair_value": result.fair_value,
        },
    }


def _make_pipeline_records(n_wins: int, n_losses: int, win_ret: float = 5.0, loss_ret: float = -3.0):
    """Generate synthetic decision records with forward returns for graduation testing."""
    records = []
    total = n_wins + n_losses
    for i in range(total):
        ret = win_ret if i < n_wins else loss_ret
        records.append({
            "decision_id": f"integ_dec_{i}",
            "symbol": f"INTEG_{i}",
            "session": f"2026-03-{i % 28 + 1:02d}",
            "created_at": f"2026-03-{i % 28 + 1:02d} 14:30:00",
            "price": 30.0,
            "facts": {"snapshot_price": 30.0},
            "t10_return_pct": ret,
        })
    return records


# ---------------------------------------------------------------------------
# Test 1: Contrarian Engine → SHADOW_BUY Decision
# ---------------------------------------------------------------------------

class TestContrarianToShadowDecision:
    """Verify contrarian engine produces correct SHADOW_BUY output."""

    def test_shadow_mode_blocks_real_buy_and_flags_shadow(self):
        """shadow_mode=True → can_buy=False, status=PANIC_BUY, metrics['shadow_mode']=True."""
        fin_dict, tech_data = _make_shadow_buy_inputs()
        result = evaluate_contrarian_gates(
            symbol="TEST",
            current_price=30.0,
            tech_data=tech_data,
            fin_dict=fin_dict,
            sector="Công nghệ",
            shadow_mode=True,
        )
        assert result.can_buy is False, "Shadow mode must block real buy"
        assert result.status == STATE_PANIC_BUY
        assert result.metrics.get("shadow_mode") is True
        assert "SHADOW BUY" in result.action_state

    def test_non_shadow_mode_allows_real_buy(self):
        """shadow_mode=False → can_buy=True (same inputs should pass all gates)."""
        fin_dict, tech_data = _make_shadow_buy_inputs()
        result = evaluate_contrarian_gates(
            symbol="TEST",
            current_price=30.0,
            tech_data=tech_data,
            fin_dict=fin_dict,
            sector="Công nghệ",
            shadow_mode=False,
        )
        assert result.can_buy is True
        assert result.status == STATE_PANIC_BUY
        assert result.metrics.get("shadow_mode") is not True

    def test_shadow_result_contains_required_metrics_for_downstream(self):
        """SHADOW_BUY result must contain panic_score, mos_pct, fair_value for decision record."""
        fin_dict, tech_data = _make_shadow_buy_inputs()
        result = evaluate_contrarian_gates(
            symbol="TEST",
            current_price=30.0,
            tech_data=tech_data,
            fin_dict=fin_dict,
            sector="Công nghệ",
            shadow_mode=True,
        )
        assert "panic_score" in result.metrics
        assert result.mos_pct != 0.0
        assert result.fair_value > 0.0
        assert result.position_size_pct > 0.0


# ---------------------------------------------------------------------------
# Test 2: Decision Record → update_shadow_returns (Data Handoff)
# ---------------------------------------------------------------------------

class TestDecisionToForwardReturns:
    """Verify data handoff from decision records to forward returns updater."""

    def test_valid_decision_record_is_processed(self):
        """Record with valid decision_id and snapshot_price is passed to upsert."""
        fin_dict, tech_data = _make_shadow_buy_inputs()
        result = evaluate_contrarian_gates(
            symbol="FPT",
            current_price=30.0,
            tech_data=tech_data,
            fin_dict=fin_dict,
            sector="Công nghệ",
            shadow_mode=True,
        )
        record = _make_decision_record_from_result(result, "dec_fpt_001", "2026-10-01")
        record["t1_return_pct"] = 2.0
        record["t5_return_pct"] = 4.5
        record["t10_return_pct"] = 6.0
        record["t20_return_pct"] = 8.0

        with patch("scripts.update_shadow_returns.update_decision_forward_returns", return_value=True) as mock_upsert:
            updated = update_shadow_records_forward_returns([record])
            assert updated == 1
            call_args = mock_upsert.call_args
            payload = call_args[0][1]
            assert payload["snapshot_price"] == 30.0
            assert payload["t10_return_pct"] == 6.0

    def test_record_without_decision_id_is_skipped(self):
        """Records missing decision_id must be silently skipped."""
        record = {
            "symbol": "VNM",
            "price": 50.0,
            "facts": {"snapshot_price": 50.0},
            "t10_return_pct": 3.0,
        }
        with patch("scripts.update_shadow_returns.update_decision_forward_returns") as mock_upsert:
            updated = update_shadow_records_forward_returns([record])
            assert updated == 0
            mock_upsert.assert_not_called()

    def test_record_with_zero_price_is_skipped(self):
        """Records with snapshot_price <= 0 must be skipped to prevent division errors."""
        record = {
            "decision_id": "dec_bad_price",
            "symbol": "BAD",
            "price": 0.0,
            "facts": {"snapshot_price": 0.0},
        }
        with patch("scripts.update_shadow_returns.update_decision_forward_returns") as mock_upsert:
            updated = update_shadow_records_forward_returns([record])
            assert updated == 0
            mock_upsert.assert_not_called()

    def test_snapshot_price_immutability(self):
        """snapshot_price must come from facts['snapshot_price'], not from current volatile price."""
        record = {
            "decision_id": "dec_immut",
            "symbol": "HPG",
            "price": 999.0,  # volatile current price (should NOT be used if facts has snapshot)
            "facts": {"snapshot_price": 25.0},
            "t10_return_pct": 3.0,
        }
        with patch("scripts.update_shadow_returns.update_decision_forward_returns", return_value=True) as mock_upsert:
            update_shadow_records_forward_returns([record])
            payload = mock_upsert.call_args[0][1]
            assert payload["snapshot_price"] == 25.0, "Must use facts['snapshot_price'], not volatile 'price'"

    def test_idempotent_reprocessing(self):
        """Running update twice on same records should call upsert same number of times (idempotent)."""
        records = [
            {
                "decision_id": "dec_idem_1",
                "symbol": "FPT",
                "facts": {"snapshot_price": 100.0},
                "t10_return_pct": 5.0,
            },
        ]
        with patch("scripts.update_shadow_returns.update_decision_forward_returns", return_value=True) as mock_upsert:
            count1 = update_shadow_records_forward_returns(records)
            count2 = update_shadow_records_forward_returns(records)
            assert count1 == count2 == 1
            assert mock_upsert.call_count == 2  # Called once per run, total 2 runs


# ---------------------------------------------------------------------------
# Test 3: Forward Returns → Graduation Evaluator (End-to-End)
# ---------------------------------------------------------------------------

class TestForwardReturnsToGraduation:
    """Verify forward returns data flows correctly into graduation evaluation."""

    def test_positive_expectancy_pipeline_graduates(self):
        """Pipeline with strong returns → graduation passes all multi-factor criteria."""
        records = _make_pipeline_records(n_wins=25, n_losses=10, win_ret=6.0, loss_ret=-2.0)
        # Pad to 65+ distinct sessions
        for s in range(40):
            records.append({
                "decision_id": f"pad_{s}",
                "symbol": f"PAD_{s}",
                "session": f"2026-04-{s % 28 + 1:02d}_{s}",
                "created_at": f"2026-04-{s % 28 + 1:02d} 10:00:00",
                "t10_return_pct": None,
            })

        report = evaluate_shadow_graduation(records=records, cost_pct=0.35)
        assert report["can_graduate"] is True
        assert report["hit_rate_t10"] > 0.55
        assert report["expectancy_t10"] > 0.0
        assert report["profit_factor_t10"] >= 1.2

    def test_negative_expectancy_pipeline_blocks_graduation(self):
        """Pipeline with weak returns → graduation blocked despite decent hit rate."""
        records = _make_pipeline_records(n_wins=20, n_losses=15, win_ret=1.0, loss_ret=-3.0)
        for s in range(65):
            records.append({
                "decision_id": f"pad_{s}",
                "symbol": f"PAD_{s}",
                "session": f"2026-04-{s % 28 + 1:02d}_{s}",
                "created_at": f"2026-04-{s % 28 + 1:02d} 10:00:00",
                "t10_return_pct": None,
            })

        report = evaluate_shadow_graduation(records=records, cost_pct=0.35)
        assert report["can_graduate"] is False
        assert report["expectancy_t10"] < 0.0

    def test_insufficient_sessions_blocks_graduation(self):
        """Pipeline with fewer than 60 distinct sessions → graduation blocked."""
        records = _make_pipeline_records(n_wins=25, n_losses=5, win_ret=8.0, loss_ret=-1.0)
        # Only ~28 distinct sessions
        report = evaluate_shadow_graduation(records=records, cost_pct=0.35)
        assert report["can_graduate"] is False
        reasons_str = " ".join(report["reasons"])
        assert "60 phiên" in reasons_str

    def test_none_returns_treated_as_unmatured_not_zero(self):
        """Records with t10_return_pct=None must be excluded from hit rate, not counted as 0%."""
        records = [
            {"decision_id": f"mat_{i}", "symbol": f"MAT_{i}", "session": f"2026-05-{i+1:02d}",
             "created_at": f"2026-05-{i+1:02d} 10:00", "t10_return_pct": 5.0}
            for i in range(5)
        ]
        # Add 30 records with None (unmatured)
        for i in range(30):
            records.append({
                "decision_id": f"unmat_{i}", "symbol": f"UNMAT_{i}",
                "session": f"2026-06-{i % 28 + 1:02d}",
                "created_at": f"2026-06-{i % 28 + 1:02d} 10:00",
                "t10_return_pct": None,
            })
        # Add session padding
        for s in range(65):
            records.append({
                "decision_id": f"pad_{s}", "symbol": f"PAD_{s}",
                "session": f"2026-07-{s % 28 + 1:02d}_{s}",
                "created_at": f"2026-07-{s % 28 + 1:02d} 10:00",
                "t10_return_pct": None,
            })

        report = evaluate_shadow_graduation(records=records, cost_pct=0.35)
        # Only 5 matured records, hit rate should be 100% (all positive)
        assert report["t10_sample_count"] == 5
        assert report["hit_rate_t10"] == 1.0
        # But should still block due to insufficient effective samples
        assert report["can_graduate"] is False


# ---------------------------------------------------------------------------
# Test 4: Deduplication & N_eff Integration
# ---------------------------------------------------------------------------

class TestDeduplicationIntegration:
    """Verify deduplication correctly feeds into graduation evaluator."""

    def test_clustered_signals_reduce_effective_samples(self):
        """Same-symbol signals within 5 days should collapse, reducing sample count."""
        records = []
        # 5 signals for same symbol on consecutive days (= 1 episode)
        for d in range(5):
            records.append({
                "decision_id": f"cluster_{d}",
                "symbol": "HPG",
                "session": f"2026-08-{d+1:02d}",
                "created_at": f"2026-08-{d+1:02d} 14:30:00",
                "t10_return_pct": 3.0,
            })
        # 1 independent signal for different symbol
        records.append({
            "decision_id": "indep_1",
            "symbol": "FPT",
            "session": "2026-08-03",
            "created_at": "2026-08-03 14:30:00",
            "t10_return_pct": 4.0,
        })

        episodes = deduplicate_signal_episodes(records, window_days=5)
        # HPG: 5 consecutive days → 1 episode. FPT: 1 episode. Total: 2
        assert len(episodes) == 2

        # N_eff should reflect clustering
        n_eff = estimate_effective_sample_size(episodes, intra_cluster_corr=0.5)
        assert n_eff <= len(episodes)

    def test_deduplication_preserves_cross_symbol_independence(self):
        """Different symbols on same date should NOT be collapsed."""
        records = [
            {"decision_id": "a", "symbol": "HPG", "session": "2026-08-01",
             "created_at": "2026-08-01 14:30:00", "t10_return_pct": 2.0},
            {"decision_id": "b", "symbol": "FPT", "session": "2026-08-01",
             "created_at": "2026-08-01 14:30:00", "t10_return_pct": 3.0},
            {"decision_id": "c", "symbol": "VNM", "session": "2026-08-01",
             "created_at": "2026-08-01 14:30:00", "t10_return_pct": 4.0},
        ]
        episodes = deduplicate_signal_episodes(records, window_days=5)
        assert len(episodes) == 3  # All different symbols


# ---------------------------------------------------------------------------
# Test 5: Forward Returns with fwd_records parameter (bypass DB)
# ---------------------------------------------------------------------------

class TestForwardRecordsInjection:
    """Test that fwd_records parameter correctly injects forward returns without DB access."""

    def test_fwd_records_override_database_lookup(self):
        """When fwd_records is provided, graduation uses them instead of querying DB."""
        records = []
        fwd_records = []
        for i in range(35):
            dec_id = f"fwd_test_{i}"
            ret = 5.0 if i < 25 else -2.0
            records.append({
                "decision_id": dec_id,
                "symbol": f"FWD_{i}",
                "session": f"2026-09-{i % 28 + 1:02d}",
                "created_at": f"2026-09-{i % 28 + 1:02d} 10:00:00",
            })
            fwd_records.append({
                "decision_id": dec_id,
                "t10_return_pct": ret,
            })

        # Pad sessions
        for s in range(40):
            records.append({
                "decision_id": f"fwd_pad_{s}",
                "symbol": f"FPAD_{s}",
                "session": f"2026-10-{s % 28 + 1:02d}_{s}",
                "created_at": f"2026-10-{s % 28 + 1:02d} 10:00:00",
            })

        # No DB mock needed because fwd_records is provided
        report = evaluate_shadow_graduation(records=records, fwd_records=fwd_records, cost_pct=0.35)
        assert report["t10_sample_count"] == 35
        assert report["hit_rate_t10"] > 0.55


# ---------------------------------------------------------------------------
# Test 6: Full Pipeline Simulation (Engine → Record → Returns → Graduation)
# ---------------------------------------------------------------------------

class TestFullPipelineSimulation:
    """Simulate the complete pipeline without any database dependency."""

    def test_end_to_end_shadow_pipeline(self):
        """Full pipeline: engine → decision_record → update_returns → graduation evaluation."""
        fin_dict, tech_data = _make_shadow_buy_inputs()

        # Step 1: Contrarian engine generates SHADOW_BUY
        result = evaluate_contrarian_gates(
            symbol="PIPELINE_TEST",
            current_price=30.0,
            tech_data=tech_data,
            fin_dict=fin_dict,
            sector="Công nghệ",
            shadow_mode=True,
        )
        assert result.metrics.get("shadow_mode") is True

        # Step 2: Create decision record from result
        record = _make_decision_record_from_result(result, "pipe_001", "2026-10-01")

        # Step 3: Simulate forward returns update (mock DB layer)
        record["t1_return_pct"] = 1.5
        record["t5_return_pct"] = 3.2
        record["t10_return_pct"] = 5.8
        record["t20_return_pct"] = 7.1

        with patch("scripts.update_shadow_returns.update_decision_forward_returns", return_value=True) as mock_upsert:
            updated = update_shadow_records_forward_returns([record])
            assert updated == 1

        # Step 4: Generate synthetic cohort for graduation evaluation
        cohort = [record]
        for i in range(34):
            cohort.append({
                "decision_id": f"pipe_{i+2:03d}",
                "symbol": f"PIPE_{i}",
                "session": f"2026-09-{i % 28 + 1:02d}",
                "created_at": f"2026-09-{i % 28 + 1:02d} 14:30:00",
                "t10_return_pct": 4.0 if i < 24 else -2.0,
            })
        # Pad sessions to reach 60+
        for s in range(40):
            cohort.append({
                "decision_id": f"pipe_pad_{s}",
                "symbol": f"PPAD_{s}",
                "session": f"2026-08-{s % 28 + 1:02d}_{s}",
                "created_at": f"2026-08-{s % 28 + 1:02d} 10:00:00",
                "t10_return_pct": None,
            })

        # Step 5: Evaluate graduation
        report = evaluate_shadow_graduation(records=cohort, cost_pct=0.35)
        assert report["can_graduate"] is True
        assert report["expectancy_t10"] > 0.0

    def test_pipeline_with_all_losses_blocks_graduation(self):
        """Pipeline where all trades lose → graduation must be blocked."""
        records = _make_pipeline_records(n_wins=0, n_losses=35, win_ret=0.0, loss_ret=-5.0)
        for s in range(65):
            records.append({
                "decision_id": f"loss_pad_{s}",
                "symbol": f"LPAD_{s}",
                "session": f"2026-04-{s % 28 + 1:02d}_{s}",
                "created_at": f"2026-04-{s % 28 + 1:02d} 10:00",
                "t10_return_pct": None,
            })

        report = evaluate_shadow_graduation(records=records, cost_pct=0.35)
        assert report["can_graduate"] is False
        assert report["hit_rate_t10"] == 0.0
        assert report["expectancy_t10"] < 0.0
        assert report["profit_factor_t10"] == 0.0


# ---------------------------------------------------------------------------
# Test 7: Stage Gate Notice Always Present
# ---------------------------------------------------------------------------

class TestStageGateNotice:
    """Verify that graduation report always contains the stage gate notice."""

    def test_stage_gate_notice_present_on_pass(self):
        """Stage gate notice must be present even when graduation passes."""
        records = _make_pipeline_records(n_wins=25, n_losses=10, win_ret=6.0, loss_ret=-2.0)
        for s in range(40):
            records.append({
                "decision_id": f"notice_pad_{s}",
                "symbol": f"NPAD_{s}",
                "session": f"2026-04-{s % 28 + 1:02d}_{s}",
                "created_at": f"2026-04-{s % 28 + 1:02d} 10:00",
                "t10_return_pct": None,
            })
        report = evaluate_shadow_graduation(records=records, cost_pct=0.35)
        assert "stage_gate_notice" in report
        assert "Research Review" in report["stage_gate_notice"]

    def test_stage_gate_notice_present_on_fail(self):
        """Stage gate notice must be present when graduation fails."""
        report = evaluate_shadow_graduation(records=[])
        assert "stage_gate_notice" in report
        assert "Research Review" in report["stage_gate_notice"]

    def test_stage_gate_notice_present_no_t10_samples(self):
        """Stage gate notice present even with records but no T+10 data."""
        records = [
            {"decision_id": f"no_t10_{i}", "symbol": f"NT_{i}",
             "session": f"2026-06-{i+1:02d}", "created_at": f"2026-06-{i+1:02d} 10:00"}
            for i in range(10)
        ]
        report = evaluate_shadow_graduation(records=records)
        assert "stage_gate_notice" in report
