"""
Test suite covering all 58 universe stocks under synthetic and edge-case market conditions.
Verifies that no ticker crashes with an unhandled exception ('>=', float(None), or formatting).
Asserts that EXCEPTION gate count is strictly 0.
"""

from unittest.mock import patch

import pytest

from data_engine import scan_market_opportunities

UNIVERSE_58 = [
    "ACB", "ANV", "BID", "BSR", "CSV", "CTG", "DCM", "DGC", "DIG", "DPM",
    "DXG", "FMC", "FPT", "GAS", "GIL", "GMD", "GVR", "HAH", "HDB", "HPG",
    "HSG", "IDC", "KBC", "KDH", "MBB", "MSB", "MSH", "MSN", "MWG", "NKG",
    "NLG", "NVL", "PDR", "PLX", "POW", "PVD", "PVT", "SAB", "SHB", "SSB",
    "SSI", "STB", "STK", "SZC", "TCB", "TNG", "TPB", "VCB", "VGC", "VHC",
    "VHM", "VIB", "VIC", "VND", "VNM", "VPB", "VRE", "VTP",
]


@pytest.fixture
def mock_market_environment():
    """Mock technical data, financial ratios, and network calls for the 58 universe stocks."""
    def _mock_fetch_technical(symbol, count_back=60, fetch_foreign=True):
        sym = symbol.upper().strip()
        # Edge case test: FPT has RSI 0.0 (extreme oversold waterfall drop)
        rsi_val = 0.0 if sym == "FPT" else (32.0 if sym in ("STB", "HSG") else 48.0)
        return {
            "symbol": sym,
            "current_price": 25.0,
            "ref_price": 25.5,
            "change_pct": -2.0,
            "open": 25.5,
            "high": 25.8,
            "low": 24.8,
            "ma20": 27.0,
            "ma50": 28.5,
            "ma100": 30.0,
            "ma200": 31.0,
            "rsi14": rsi_val,
            "rsi": rsi_val,
            "volume": 1_500_000,
            "vol_ratio": 1.1,
            "adv20_billion": 35.0,
            "atr14": 1.2,
            "upper_wick_ratio": 0.1,
            "foreign_flow": {"status": "NEUTRAL", "net_val_bil": 0.0},
            "trap_info": {"is_trap": False, "trap_type": "NONE"},
            "price_source": "MOCK_TEST",
            "price_asof": "2026-10-12 15:00:00",
        }

    def _mock_financial_ratios(symbol):
        sym = symbol.upper().strip()
        # Edge case: 20 stocks with uninformative or None valuation
        if sym in ("ANV", "CSV", "FMC", "GAS", "GIL", "GMD", "HAH", "MSH", "MSN",
                    "PLX", "POW", "PVT", "SAB", "SSI", "STK", "SZC", "TNG", "VGC", "VHC", "VND"):
            return {
                "period": "2026-Q2",
                "roe": 0.08,
                "pb": 1.2,
                "pe": None,
                "eps": None,
                "f_score": 5,
                "z_score": 1.8,
                "cfo_to_net_income": 0.9,
                "npl": 0.0,
            }
        # Bank stocks
        if sym in ("ACB", "BID", "CTG", "HDB", "MBB", "MSB", "SHB", "SSB", "STB", "TCB", "TPB", "VCB", "VIB", "VPB"):
            return {
                "period": "2026-Q2",
                "roe": 0.20 if sym != "STB" else 0.05,
                "pb": 1.1,
                "bvps": 22.0,
                "pe": 8.0,
                "eps": 2.5,
                "f_score": 7,
                "z_score": 2.2,
                "npl": 0.015,
            }
        # Regular stocks
        return {
            "period": "2026-Q2",
            "roe": 0.16,
            "pb": 1.5,
            "pe": 10.0,
            "eps": 2.5,
            "f_score": 7,
            "z_score": 2.8,
            "cfo_to_net_income": 1.2,
        }

    with patch("data_engine.fetch_stock_technical", side_effect=_mock_fetch_technical), \
         patch("data_engine.get_financial_ratios", side_effect=_mock_financial_ratios), \
         patch("db_manager.save_decision_record", return_value="DEC_MOCK_001"), \
         patch("db_manager.save_lifecycle_event", return_value="EVT_MOCK_001"), \
         patch("db_manager.update_decision_forward_returns", return_value=True):
        yield


def test_universe_58_zero_exceptions(mock_market_environment):
    """Test that all 58 universe stocks complete execution with ZERO unhandled exceptions."""
    assert len(UNIVERSE_58) == 58

    results = scan_market_opportunities(
        extra_symbols=UNIVERSE_58,
        session_override="EOD_REPLAY_TEST",
        model_version_override="v15.0_post_fix",
        is_shadow_override=True,
    )

    assert len(results) == 58, f"Expected 58 results, got {len(results)}"

    exceptions = []
    for r in results:
        sym = r.get("symbol")
        status = r.get("status")
        gate = r.get("primary_rejection_gate")
        setup = r.get("setup_type", "")

        # Strict assertion: NO stock may end with EXCEPTION
        if gate == "EXCEPTION" or status == "EXCEPTION" or "Lỗi exception" in setup:
            exceptions.append((sym, gate, setup))

    assert len(exceptions) == 0, f"Found {len(exceptions)} stocks with EXCEPTION: {exceptions}"


def test_no_data_error_in_normal_flow(mock_market_environment):
    """Confirm that with complete mock data, all 58 stocks evaluate without DATA_ERROR."""
    results = scan_market_opportunities(
        extra_symbols=UNIVERSE_58,
        session_override="EOD_REPLAY_TEST",
        model_version_override="v15.0_post_fix",
    )

    data_errors = [r for r in results if r.get("primary_rejection_gate") == "DATA_ERROR"]
    assert len(data_errors) == 0, f"Unexpected DATA_ERROR in universe: {data_errors}"


def test_simulated_exception_produces_data_error():
    """Verify that if an unhandled crash occurs, it is categorized as DATA_ERROR, NOT REJECT + EXCEPTION."""
    saved_records = []

    def _mock_save_decision(payload):
        saved_records.append(payload)
        return "DEC_CRASH_TEST"

    with patch("data_engine.fetch_stock_technical", side_effect=RuntimeError("Simulated hardware error")), \
         patch("db_manager.save_decision_record", side_effect=_mock_save_decision):
        results = scan_market_opportunities(
            extra_symbols=["HPG"],
            session_override="EOD_REPLAY_TEST",
            model_version_override="v15.0_post_fix",
        )

    assert len(results) == 1
    res = results[0]
    assert res.get("status") == "DATA_ERROR"
    assert res.get("primary_rejection_gate") == "DATA_ERROR"
    assert len(saved_records) == 1
    saved = saved_records[0]
    assert saved.get("decision") == "DATA_ERROR"
    assert saved.get("primary_rejection_gate") == "DATA_ERROR"
    assert saved.get("decision") != "REJECT"

