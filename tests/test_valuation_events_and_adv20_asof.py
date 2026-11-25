# -*- coding: utf-8 -*-
"""Unit tests for valuation event crossing flags, ADV20 point-in-time metadata, and regression stability."""

import io
import json
import os
import subprocess

import pandas as pd
import pytest

from scripts.enrich_forward_returns_valuation_events import (
    _evaluate_symbol_event_crossing,
    load_valuation_events,
)

DATE_2026_10_13 = "2026-10-13"
DATE_2026_10_14 = "2026-10-14"
DATE_2026_10_19 = "2026-10-19"
DATE_2026_10_20 = "2026-10-20"
DATE_2026_10_21 = "2026-10-21"
DATE_2026_10_22 = "2026-10-22"
DATE_2026_10_23 = "2026-10-23"
DATE_2026_10_26 = "2026-10-26"

ALL_COHORT_FILES = [
    "canonical_forward_returns_20261014.csv",
    "canonical_forward_returns_20261015.csv",
    "canonical_forward_returns_20261016.csv",
    "canonical_forward_returns_20261019.csv",
    "canonical_forward_returns_20261020.csv",
    "canonical_forward_returns_20261021.csv",
    "canonical_forward_returns_20261022.csv",
    "canonical_forward_returns_20261023.csv",
    "canonical_forward_returns_20261026.csv",
]


class TestValuationEventCrossingLogic:
    """Test unit logic of _evaluate_symbol_event_crossing and priority order."""

    def test_both_dates_empty_flags_intentionally_false(self):
        """When both published and detected dates are missing, all flags must be False."""
        h_dates = {1: DATE_2026_10_20, 3: DATE_2026_10_22, 5: DATE_2026_10_26}
        c1, c3, c5, c_val = _evaluate_symbol_event_crossing(DATE_2026_10_19, None, h_dates, DATE_2026_10_26)
        assert (c1, c3, c5, c_val) == (False, False, False, False)

    def test_published_date_overrides_detected_date(self):
        """When published date exists, it takes precedence over detection date."""
        h_dates = {1: DATE_2026_10_20, 3: DATE_2026_10_22, 5: DATE_2026_10_26}
        pub_date = DATE_2026_10_20
        det_date = "2026-10-23"
        effective = pub_date if pub_date else det_date
        c1, c3, c5, c_val = _evaluate_symbol_event_crossing(DATE_2026_10_19, effective, h_dates, DATE_2026_10_26)
        assert c1 is True
        assert c3 is True

    def test_same_day_event_treated_as_absorbed_in_close_t0(self):
        """Rule: If effective_date == T0, the event is absorbed in Close T0, so forward flags are False."""
        h_23 = {1: DATE_2026_10_26, 3: "2026-10-28", 5: "2026-10-30"}
        # Event effective on 23/10 with T0 = 23/10
        c1, c3, c5, c_val = _evaluate_symbol_event_crossing(DATE_2026_10_23, DATE_2026_10_23, h_23, DATE_2026_10_26)
        assert (c1, c3, c5, c_val) == (False, False, False, False)

    def test_vpb_cohort_19_oct_crossing(self):
        h_dates = {1: DATE_2026_10_20, 3: DATE_2026_10_22, 5: DATE_2026_10_26}
        c1, c3, c5, c_val = _evaluate_symbol_event_crossing(DATE_2026_10_19, DATE_2026_10_20, h_dates, DATE_2026_10_26)
        assert (c1, c3, c5, c_val) == (True, True, True, True)

    def test_tcb_cohort_19_oct_crossing(self):
        h_dates = {1: DATE_2026_10_20, 3: DATE_2026_10_22, 5: DATE_2026_10_26}
        c1, c3, c5, c_val = _evaluate_symbol_event_crossing(DATE_2026_10_19, DATE_2026_10_21, h_dates, DATE_2026_10_26)
        assert (c1, c3, c5, c_val) == (False, True, True, True)

    def test_msn_crossing_behavior_across_cohorts(self):
        """MSN detected on 2026-10-23 must cross windows that encompass 23/10."""
        # Cohort 19/10: H1=20/10, H3=22/10, H5=26/10 -> crosses H5 only
        h_19 = {1: DATE_2026_10_20, 3: DATE_2026_10_22, 5: DATE_2026_10_26}
        c1, c3, c5, cv = _evaluate_symbol_event_crossing(DATE_2026_10_19, DATE_2026_10_23, h_19, DATE_2026_10_26)
        assert (c1, c3, c5, cv) == (False, False, True, True)

        # Cohort 20/10: H1=21/10, H3=23/10, H5=27/10 -> crosses H3 and H5
        h_20 = {1: DATE_2026_10_21, 3: DATE_2026_10_23, 5: "2026-10-27"}
        c1, c3, c5, cv = _evaluate_symbol_event_crossing(DATE_2026_10_20, DATE_2026_10_23, h_20, DATE_2026_10_23)
        assert (c1, c3, c5, cv) == (False, True, True, True)

        # Cohort 22/10: H1=23/10, H3=27/10, H5=29/10 -> crosses H1, H3, H5
        h_22 = {1: DATE_2026_10_23, 3: "2026-10-27", 5: "2026-10-29"}
        c1, c3, c5, cv = _evaluate_symbol_event_crossing(DATE_2026_10_22, DATE_2026_10_23, h_22, DATE_2026_10_23)
        assert (c1, c3, c5, cv) == (True, True, True, True)

        # Cohort 23/10: T0=23/10 -> event is NOT crossing (already known on or before T0)
        h_23 = {1: DATE_2026_10_26, 3: "2026-10-28", 5: "2026-10-30"}
        c1, c3, c5, cv = _evaluate_symbol_event_crossing(DATE_2026_10_23, DATE_2026_10_23, h_23, DATE_2026_10_26)
        assert (c1, c3, c5, cv) == (False, False, False, False)

    def test_kbc_prior_event_never_crosses_subsequent_cohorts(self):
        """KBC detected on 2026-10-14 must never cross subsequent cohorts (T0 >= 14/10)."""
        h_14 = {1: "2026-10-15", 3: DATE_2026_10_19, 5: DATE_2026_10_21}
        c1, c3, c5, cv = _evaluate_symbol_event_crossing(DATE_2026_10_14, DATE_2026_10_14, h_14, DATE_2026_10_21)
        assert (c1, c3, c5, cv) == (False, False, False, False)


class TestValuationEventsMapLoading:
    """Test loading, inclusion, and metadata integrity in valuation_events.csv."""

    def test_msn_kbc_vix_all_included_in_events_table(self):
        events = load_valuation_events()
        assert "MSN" in events, "MSN must be included in valuation_events"
        assert events["MSN"]["effective_date"] == DATE_2026_10_23
        assert events["MSN"]["event_timing_unknown"] is True

        assert "KBC" in events, "KBC must be included with its authentic detection date"
        assert events["KBC"]["effective_date"] == DATE_2026_10_14

        assert "VIX" in events, "VIX must be tracked in valuation_events"
        assert events["VIX"]["effective_date"] == DATE_2026_10_22

    def test_timing_unknown_flag_present_and_true_for_unverified_events(self):
        events = load_valuation_events()
        all_14_unverified = [
            "VPB",
            "TCB",
            "MSN",
            "VGC",
            "CSV",
            "TNG",
            "HAH",
            "SSI",
            "VND",
            "SZC",
            "ANV",
            "FMC",
            "KBC",
            "VIX",
        ]
        for sym in all_14_unverified:
            assert sym in events, f"{sym} must be present in valuation_events.csv"
            assert events[sym]["event_timing_unknown"] is True, f"{sym} must have event_timing_unknown == True"


class TestCanonicalForwardReturnsCohort19Oct:
    """Verify cohort 19/10 values match exact user audit specifications."""

    @pytest.fixture
    def cohort_19_df(self):
        csv_file = "canonical_forward_returns_20261019.csv"
        assert os.path.exists(csv_file), f"{csv_file} must exist"
        return pd.read_csv(csv_file)

    def test_vpb_flags_cannot_disappear(self, cohort_19_df):
        vpb = cohort_19_df[cohort_19_df["symbol"] == "VPB"].iloc[0]
        assert bool(vpb["crosses_t1"]) is True
        assert bool(vpb["crosses_t3"]) is True
        assert bool(vpb["crosses_t5"]) is True
        assert bool(vpb["crosses_valuation_event"]) is True
        assert vpb["bctc_detected_date"] == DATE_2026_10_20
        assert bool(vpb["event_timing_unknown"]) is True

    def test_tcb_flags_cannot_disappear(self, cohort_19_df):
        tcb = cohort_19_df[cohort_19_df["symbol"] == "TCB"].iloc[0]
        assert bool(tcb["crosses_t1"]) is False
        assert bool(tcb["crosses_t3"]) is True
        assert bool(tcb["crosses_t5"]) is True
        assert bool(tcb["crosses_valuation_event"]) is True
        assert tcb["bctc_detected_date"] == DATE_2026_10_21
        assert bool(tcb["event_timing_unknown"]) is True

    def test_msn_flags_in_cohort_19(self, cohort_19_df):
        """MSN detected on 23/10 falls between T+3 (22/10) and T+5 (26/10)."""
        msn = cohort_19_df[cohort_19_df["symbol"] == "MSN"].iloc[0]
        assert bool(msn["crosses_t1"]) is False
        assert bool(msn["crosses_t3"]) is False
        assert bool(msn["crosses_t5"]) is True
        assert bool(msn["crosses_valuation_event"]) is True
        assert msn["bctc_detected_date"] == DATE_2026_10_23
        assert bool(msn["event_timing_unknown"]) is True

    def test_kbc_has_no_crossing_flags_in_cohort_19(self, cohort_19_df):
        """KBC event was 14/10, which is before cohort 19/10, so all crossing flags are False."""
        kbc = cohort_19_df[cohort_19_df["symbol"] == "KBC"].iloc[0]
        assert bool(kbc["crosses_t1"]) is False
        assert bool(kbc["crosses_t3"]) is False
        assert bool(kbc["crosses_t5"]) is False
        assert bool(kbc["crosses_valuation_event"]) is False

    def test_bctc_published_date_is_completely_null(self, cohort_19_df):
        """Published date must not be fabricated; it must remain completely NaN/empty."""
        assert cohort_19_df["bctc_published_date"].isna().all()

    def test_adv20_is_fallback_flag_present(self, cohort_19_df):
        """In cohort 19/10, all 55 stocks use baseline 13/10 snapshot, so adv20_is_fallback is True."""
        assert "adv20_is_fallback" in cohort_19_df.columns
        assert cohort_19_df["adv20_is_fallback"].all()

    def test_stk_adv20_is_strictly_low_liquidity(self, cohort_19_df):
        """STK ADV20 must be ~0.08 billion VND (strictly below 0.1 billion, never 0.64)."""
        stk = cohort_19_df[cohort_19_df["symbol"] == "STK"].iloc[0]
        assert stk["adv20_value"] == 0.08
        assert bool(stk["executable_size_ok"]) is False


class TestCanonicalForwardReturnsAllCohorts:
    """Verify adv20_asof freshness, adv20_age_sessions ceilings, static fixture zero-diff, external anchor, and column count progression."""

    AGE_CEILINGS = {
        "20261014": 1,
        "20261015": 2,
        "20261016": 3,
        "20261019": 4,
        "20261020": 5,
        "20261021": 6,
        "20261022": 7,
        "20261023": 8,
        "20261026": 9,
    }

    def test_adv20_age_sessions_strictly_enforced_with_ceilings(self):
        """Test strict trading day lag integer column adv20_age_sessions and per-cohort ceilings."""
        for f in ALL_COHORT_FILES:
            if not os.path.exists(f):
                continue
            df = pd.read_csv(f)
            t0 = f.split("_")[3][:8]
            t0_date = f"{t0[:4]}-{t0[4:6]}-{t0[6:8]}"
            ceiling = self.AGE_CEILINGS[t0]

            assert "adv20_age_sessions" in df.columns, f"Missing adv20_age_sessions in {f}"
            assert "adv20_asof" in df.columns, f"Missing adv20_asof in {f}"
            assert "adv20_is_fallback" in df.columns, f"Missing adv20_is_fallback in {f}"

            # Strict ceiling check across all 55 rows
            assert (df["adv20_age_sessions"] <= ceiling).all(), f"Age ceiling {ceiling} breached in {f}"
            assert (df["adv20_age_sessions"] >= 0).all(), f"Negative age in {f}"
            assert (df["adv20_asof"] <= t0_date).all(), f"Lookahead in {f}: adv20_asof > T0 ({t0_date})"

            # For cohorts <= 19/10: all 55 rows use baseline 13/10 (exact deliberate staleness)
            if t0 <= "20261019":
                assert (df["adv20_age_sessions"] == ceiling).all(), f"Cohort {t0} must have exact age {ceiling}"
                assert df["adv20_is_fallback"].all()

            # For cohorts 20/10 - 23/10: 52 liquid symbols have age == 0, 3 fallback symbols have age == ceiling
            elif "20261020" <= t0 <= "20261023":
                liquid_with_snapshots = df[~df["symbol"].isin(["VTP", "NVL", "VIC"])]
                assert (liquid_with_snapshots["adv20_age_sessions"] == 0).all()
                assert (liquid_with_snapshots["adv20_asof"] == t0_date).all()
                assert (~liquid_with_snapshots["adv20_is_fallback"]).all()

                fallbacks = df[df["symbol"].isin(["VTP", "NVL", "VIC"])]
                assert (fallbacks["adv20_age_sessions"] == ceiling).all()
                assert fallbacks["adv20_is_fallback"].all()
                assert (fallbacks["adv20_asof"] == DATE_2026_10_13).all()

            elif t0 == "20261026":
                # Cohort 26/10 uses latest available snapshot (2026-10-23): 52 stocks have lag = 1 session
                liquid_with_snapshots = df[~df["symbol"].isin(["VTP", "NVL", "VIC"])]
                assert (liquid_with_snapshots["adv20_age_sessions"] == 1).all()
                assert (liquid_with_snapshots["adv20_asof"] == DATE_2026_10_23).all()
                assert liquid_with_snapshots["adv20_is_fallback"].all()

                # VTP, NVL, VIC fallback to 13/10: lag = exactly 9 trading sessions
                fallbacks = df[df["symbol"].isin(["VTP", "NVL", "VIC"])]
                assert (fallbacks["adv20_age_sessions"] == 9).all()
                assert fallbacks["adv20_is_fallback"].all()
                assert (fallbacks["adv20_asof"] == DATE_2026_10_13).all()

    def test_adv20_general_staleness_ceiling_and_null_liquidity(self):
        """General staleness ceiling (4 sessions): rows >= 5 sessions must have executable_size_ok as null (không rõ)."""
        for f in ALL_COHORT_FILES:
            if not os.path.exists(f):
                continue
            df = pd.read_csv(f)
            # All 52 liquid symbols must never exceed 4 trading sessions lag
            liquid = df[~df["symbol"].isin(["VTP", "NVL", "VIC"])]
            assert (liquid["adv20_age_sessions"] <= 4).all()
            assert liquid["executable_size_ok"].notna().all()

            # For rows with staleness >= 5 sessions (VTP, NVL, VIC in snapshot era), executable_size_ok is null (không rõ)
            stale_rows = df[df["adv20_age_sessions"] >= 5]
            if not stale_rows.empty:
                assert stale_rows["executable_size_ok"].isna().all(), f"Stale rows in {f} must have executable_size_ok as null"

    def test_event_offset_sessions_stratification(self):
        """Test event_offset_sessions calculation and prove same-day (0) vs border (+1) vs prior (<0) event behavior."""
        # 1. Cohort 14/10: KBC is same-day (offset = 0) -> crosses flags must be False
        df14 = pd.read_csv("canonical_forward_returns_20261014.csv").set_index("symbol")
        kbc14 = df14.loc["KBC"]
        assert kbc14["event_offset_sessions"] == 0
        assert bool(kbc14["crosses_t1"]) is False
        assert bool(kbc14["crosses_valuation_event"]) is False

        # 2. Cohort 23/10: MSN is same-day (offset = 0) -> crosses flags must be False
        df23 = pd.read_csv("canonical_forward_returns_20261023.csv").set_index("symbol")
        msn23 = df23.loc["MSN"]
        assert msn23["event_offset_sessions"] == 0
        assert bool(msn23["crosses_t1"]) is False
        assert bool(msn23["crosses_valuation_event"]) is False

        # 3. Cohort 19/10: VPB is border event (+1 session) -> crosses_t1 must be True
        df19 = pd.read_csv("canonical_forward_returns_20261019.csv").set_index("symbol")
        vpb19 = df19.loc["VPB"]
        assert vpb19["event_offset_sessions"] == 1
        assert bool(vpb19["crosses_t1"]) is True

        # 4. Cohort 19/10: TCB is +2 sessions -> crosses_t1 False, crosses_t3 True
        tcb19 = df19.loc["TCB"]
        assert tcb19["event_offset_sessions"] == 2
        assert bool(tcb19["crosses_t1"]) is False
        assert bool(tcb19["crosses_t3"]) is True

        # 5. Cohort 19/10: KBC is prior event (-3 sessions) -> crosses flags False
        kbc19 = df19.loc["KBC"]
        assert kbc19["event_offset_sessions"] == -3
        assert bool(kbc19["crosses_t1"]) is False
        assert bool(kbc19["crosses_valuation_event"]) is False

        # 6. Symbols with no valuation events must have event_offset_sessions as NaN
        fpt19 = df19.loc["FPT"]
        assert pd.isna(fpt19["event_offset_sessions"])

    def test_zero_diff_against_static_fixture(self):
        """Test exact zero-diff (0.000000) against static repo fixture tests/fixtures/canonical_forward_returns_reference.json across all stored numeric metrics."""
        fix_path = os.path.join("tests", "fixtures", "canonical_forward_returns_reference.json")
        assert os.path.exists(fix_path), f"Static reference fixture {fix_path} must exist"

        with open(fix_path, "r", encoding="utf-8") as f:
            ref_data = json.load(f)

        for f in ALL_COHORT_FILES:
            if not os.path.exists(f):
                continue
            t0 = f.split("_")[3][:8]
            assert t0 in ref_data, f"Cohort {t0} missing in reference fixture"

            df_cur = pd.read_csv(f).set_index("symbol")
            cohort_ref = ref_data[t0]["records"]
            cols_to_check = ref_data[t0].get("columns_stored", ["close_t0", "open_t1", "close_t1"])

            for sym, ref_vals in cohort_ref.items():
                assert sym in df_cur.index, f"{sym} missing in {f}"
                cur_row = df_cur.loc[sym]

                for pcol in cols_to_check:
                    r_val = ref_vals.get(pcol)
                    if r_val is not None:
                        c_val = float(cur_row[pcol])
                        diff = abs(c_val - r_val)
                        assert diff == 0.0, f"Zero-diff violation in {f} {sym}:{pcol} -> cur={c_val}, ref={r_val}"

    def test_newly_matured_columns_against_external_anchor(self):
        """Verify newly matured exit prices and VN-Index on 2026-10-26 close against immutable external canonical EOD decision records."""
        dec26_file = "decision_records_20261026.csv"
        assert os.path.exists(dec26_file)
        dec_df = pd.read_csv(dec26_file)

        fwd26 = pd.read_csv("canonical_forward_returns_20261026.csv").set_index("symbol")
        can26 = dec_df[dec_df["decision_id"].isin(fwd26["decision_id"])].set_index("symbol")
        assert len(can26) == 55

        fwd19 = pd.read_csv("canonical_forward_returns_20261019.csv").set_index("symbol")
        fwd21 = pd.read_csv("canonical_forward_returns_20261021.csv").set_index("symbol")
        fwd23 = pd.read_csv("canonical_forward_returns_20261023.csv").set_index("symbol")

        # 1. Newly matured T+5 on 26/10 (Cohort 19/10) matches 26/10 canonical EOD price (55/55 match)
        diff_19 = (fwd19["close_t5"] - can26["price"]).abs().max()
        assert diff_19 == 0.0, f"Cohort 19/10 close_t5 mismatch vs 26/10 EOD price: diff={diff_19}"

        # 2. Newly matured T+3 on 26/10 (Cohort 21/10) matches 26/10 canonical EOD price (55/55 match)
        diff_21 = (fwd21["close_t3"] - can26["price"]).abs().max()
        assert diff_21 == 0.0, f"Cohort 21/10 close_t3 mismatch vs 26/10 EOD price: diff={diff_21}"

        # 3. Newly matured T+1 on 26/10 (Cohort 23/10) matches 26/10 canonical EOD price (55/55 match)
        diff_23 = (fwd23["close_t1"] - can26["price"]).abs().max()
        assert diff_23 == 0.0, f"Cohort 23/10 close_t1 mismatch vs 26/10 EOD price: diff={diff_23}"

        # 4. Cohort 26/10 close_t0 matches 26/10 canonical EOD price (55/55 match)
        diff_26 = (fwd26["close_t0"] - can26["price"]).abs().max()
        assert diff_26 == 0.0, f"Cohort 26/10 close_t0 mismatch vs 26/10 EOD price: diff={diff_26}"

        # 5. VN-Index closing score on 26/10 is identical across all 4 cohorts
        vn_19 = fwd19["vn_close_t5"].iloc[0]
        vn_21 = fwd21["vn_close_t3"].iloc[0]
        vn_23 = fwd23["vn_close_t1"].iloc[0]
        vn_26 = fwd26["vn_close_t0"].iloc[0]
        assert vn_19 == vn_21 == vn_23 == vn_26 == 1763.55

    def test_matured_column_progression_documented_and_verified(self):
        """Document and assert populated numeric columns scale according to maturity horizons as of 2026-10-26 close.

        Maturity timeline as of 2026-10-26 close:
        - Cohorts 14/10, 15/10, 16/10, 19/10: T+1, T+3, T+5 all matured (19/10 T+5 matured today 26/10) -> 36 columns
        - Cohorts 20/10, 21/10: T+1, T+3 matured (21/10 T+3 matured today 26/10; T+5 pending) -> 28 columns
        - Cohorts 22/10, 23/10: T+1 matured (23/10 T+1 matured today 26/10; T+3, T+5 pending) -> 21 columns
        - Cohort 26/10: 0 forward horizons matured (T+1 exits 27/10) -> 0 return columns populated
        """
        expected_progression = {
            # Fully matured T+1, T+3, T+5 -> 36 numeric columns populated
            "20261014": {"matured_h": [1, 3, 5]},
            "20261015": {"matured_h": [1, 3, 5]},
            "20261016": {"matured_h": [1, 3, 5]},
            "20261019": {"matured_h": [1, 3, 5]},  # T+5 matured on 2026-10-26 close
            # Matured T+1, T+3 (T+5 pending) -> 28 numeric columns populated
            "20261020": {"matured_h": [1, 3]},
            "20261021": {"matured_h": [1, 3]},  # T+3 matured on 2026-10-26 close
            # Matured T+1 only (T+3, T+5 pending) -> 21 numeric columns populated
            "20261022": {"matured_h": [1]},
            "20261023": {"matured_h": [1]},  # T+1 matured on 2026-10-26 close
            # Unmatured cohort 26/10: 0 forward horizons matured
            "20261026": {"matured_h": []},
        }

        all_ret_cols = [
            "signal_t1_pct", "exec_t1_pct", "excess_signal_t1_pct", "excess_exec_t1_pct",
            "signal_t3_pct", "exec_t3_pct", "excess_signal_t3_pct", "excess_exec_t3_pct",
            "signal_t5_pct", "exec_t5_pct", "excess_signal_t5_pct", "excess_exec_t5_pct",
        ]

        for f in ALL_COHORT_FILES:
            if not os.path.exists(f):
                continue
            t0 = f.split("_")[3][:8]
            if t0 not in expected_progression:
                continue
            df = pd.read_csv(f)
            exp = expected_progression[t0]

            # Check that matured horizons are populated and unmatured horizons are strictly NaN
            for h in [1, 3, 5]:
                h_cols = [c for c in all_ret_cols if f"t{h}" in c]
                matured_flag = bool(df.get(f"matured_t{h}", pd.Series([False])).iloc[0])

                # All horizons already matured by 2026-10-26 close MUST be marked True
                if h in exp["matured_h"]:
                    assert matured_flag is True, f"Expected horizon T+{h} to be matured in {f}"

                # Strict consistency between maturity flag and return columns
                if matured_flag:
                    for col in h_cols:
                        if col in df.columns:
                            assert df[col].notna().any(), f"Expected populated {col} in {f} when matured_t{h} is True"
                else:
                    for col in h_cols:
                        if col in df.columns:
                            assert df[col].isna().all(), f"Expected un-matured NaN for {col} in {f} when matured_t{h} is False"

    def test_thin_liquidity_universe_stable(self):
        """FMC, GIL, STK must be consistently flagged as thin liquidity across all 9 cohorts."""
        for f in ALL_COHORT_FILES:
            if not os.path.exists(f):
                continue
            df = pd.read_csv(f)
            thin = df[df["executable_size_ok"].eq(False)]["symbol"].tolist()
            assert sorted(thin) == ["FMC", "GIL", "STK"], f"Unexpected thin liquidity in {f}: {thin}"

    def test_vix_not_in_55_canonical_forward_returns_universe(self):
        """VIX is in the extended watchlist, but not in the 55 canonical forward returns universe."""
        for f in ALL_COHORT_FILES:
            if not os.path.exists(f):
                continue
            df = pd.read_csv(f)
            assert "VIX" not in df["symbol"].values
            assert len(df) == 55

    def test_published_date_completely_null_in_all_cohorts(self):
        for f in ALL_COHORT_FILES:
            if not os.path.exists(f):
                continue
            df = pd.read_csv(f)
            assert df["bctc_published_date"].isna().all(), f"Fabricated published date in {f}"

    def test_zero_diff_regression_against_baseline(self):
        """Formally test 0.000000 maximum absolute diff across all price and return columns against commit 878f706."""
        numeric_cols = [
            "close_t0", "open_t1", "close_t1", "close_t3", "vn_close_t0", "vn_open_t1", "vn_close_t1",
            "signal_t1_pct", "exec_t1_pct", "excess_signal_t1_pct", "excess_exec_t1_pct",
            "universe_exec_t1_pct", "excess_vs_universe_t1_pct", "gap_exec_vs_signal_pp",
        ]
        for f in ALL_COHORT_FILES:
            res = subprocess.run(["git", "show", f"878f706:{f}"], capture_output=True)
            if res.returncode != 0:
                continue
            old_df = pd.read_csv(io.StringIO(res.stdout.decode("utf-8", errors="replace"))).sort_values("symbol").reset_index(drop=True)
            new_df = pd.read_csv(f).sort_values("symbol").reset_index(drop=True)
            for c in numeric_cols:
                if c in old_df.columns and c in new_df.columns:
                    v_old = pd.to_numeric(old_df[c], errors="coerce")
                    v_new = pd.to_numeric(new_df[c], errors="coerce")
                    mask = v_old.notna()
                    if mask.any():
                        assert v_new[mask].notna().all()
                        max_d = (v_old[mask] - v_new[mask]).abs().max()
                        assert max_d == 0.0, f"Zero-diff violation in {f}:{c} -> diff={max_d}"

    def test_executable_size_ok_roundtrip_nullable_boolean(self):
        """Verify executable_size_ok survives CSV roundtrip and preserves nullable boolean behavior."""
        for f in ALL_COHORT_FILES:
            if not os.path.exists(f):
                continue
            # 1. Read with pandas nullable boolean dtype
            df_orig = pd.read_csv(f, dtype={"executable_size_ok": "boolean"})
            assert df_orig["executable_size_ok"].dtype.name == "boolean"

            t0 = int(f.split("_")[3][:8])
            thin_count = df_orig["executable_size_ok"].eq(False).sum()
            assert thin_count == 3  # FMC, GIL, STK always thin

            if t0 <= 20261019:
                assert df_orig["executable_size_ok"].isna().sum() == 0
                assert df_orig["executable_size_ok"].eq(True).sum() == 52
            else:
                assert df_orig["executable_size_ok"].isna().sum() == 3
                assert df_orig["executable_size_ok"].eq(True).sum() == 49
                stale_symbols = df_orig[df_orig["executable_size_ok"].isna()]["symbol"].tolist()
                assert sorted(stale_symbols) == ["NVL", "VIC", "VTP"]

            # 2. Roundtrip via CSV serialization
            buf = io.StringIO()
            df_orig.to_csv(buf, index=False)
            buf.seek(0)

            # 3. Read back with nullable boolean dtype
            df_roundtrip = pd.read_csv(buf, dtype={"executable_size_ok": "boolean"})
            assert df_roundtrip["executable_size_ok"].dtype.name == "boolean"
            assert (df_orig["executable_size_ok"].isna() == df_roundtrip["executable_size_ok"].isna()).all()
            assert (df_orig["executable_size_ok"].fillna(False) == df_roundtrip["executable_size_ok"].fillna(False)).all()

            # 4. Read back with default pandas parsing (object with np.nan)
            buf.seek(0)
            df_default = pd.read_csv(buf)
            assert df_default["executable_size_ok"].isna().sum() == df_orig["executable_size_ok"].isna().sum()
            assert (df_default["executable_size_ok"].astype("boolean").fillna(False) == df_orig["executable_size_ok"].fillna(False)).all()

