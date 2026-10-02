# =============================================================================
# TESTS FOR TASK-0033: Anti-Synthetic MoS, Target Buy Integrity & Flow Gate
# Phase 12 - v7.2
# =============================================================================


from data_engine import (
    _build_auto_watchlist_candidate,
    calculate_conviction_score,
    sync_auto_watchlist,
)
from quant_valuation import (
    INSTITUTIONAL_CONSENSUS_TARGETS,
    calculate_fair_value_and_mos,
    check_institutional_target_freshness,
)


def test_build_auto_watchlist_blocks_uninformative_synthetic_mos():
    """AC-33.1: Candidate with synthetic/uninformative MoS (e.g. 15.3% from 1.18x multiplier)

    must NOT be admitted into auto watchlist if conviction is medium (65).
    """
    manual_symbols = {"VIC", "VPB", "TCB"}
    opp_synthetic = {
        "symbol": "MWG",
        "current_price": 72.6,
        "target_price": None,
        "conviction_score": 65.0,
        "mos_pct": 15.3,
        "mos_is_informative": False,
        "status": "WATCH_CONFIRMATION",
        "sector": "💻 Công nghệ & Tiêu dùng Tăng trưởng",
    }
    candidate = _build_auto_watchlist_candidate(opp_synthetic, manual_symbols)
    assert candidate is None, "Synthetic uninformative MoS must not trigger auto-discovery!"


def test_build_auto_watchlist_admits_genuine_informative_mos():
    """AC-33.1: Candidate with genuine informative MoS >= 15% and conviction >= 60

    is properly admitted.
    """
    manual_symbols = {"VIC", "VPB"}
    opp_genuine = {
        "symbol": "FPT",
        "current_price": 130.0,
        "target_price": 160.0,
        "conviction_score": 70.0,
        "mos_pct": 18.5,
        "mos_is_informative": True,
        "status": "RECOMMEND_BUY",
        "sector": "💻 Công nghệ & Tiêu dùng Tăng trưởng",
    }
    candidate = _build_auto_watchlist_candidate(opp_genuine, manual_symbols)
    assert candidate is not None
    assert candidate["symbol"] == "FPT"
    assert candidate["target_buy"] == 123.5  # TASK-0056: Entry zone = 130 * 0.95
    assert candidate["target_buy"] < opp_genuine["current_price"]
    assert "MoS: 18.5%" in candidate["note"]
    assert candidate["is_auto"] is True


def test_build_auto_watchlist_sanitizes_target_buy_no_market_price_fallback():
    """AC-33.2 & AC-52.5: target_buy anchors to entry zone (5% discount) and NEVER fallbacks to current_price."""
    manual_symbols = set()
    opp_no_target = {
        "symbol": "VNM",
        "current_price": 68.0,
        "target_price": None,  # Không có giá mục tiêu chốt lời
        "conviction_score": 80.0,  # Conviction cao vượt ngưỡng
        "mos_pct": 16.0,
        "mos_is_informative": True,
        "status": "RECOMMEND_BUY",
        "sector": "💻 Công nghệ & Tiêu dùng Tăng trưởng",
    }
    candidate = _build_auto_watchlist_candidate(opp_no_target, manual_symbols)
    assert candidate is not None
    assert candidate["target_buy"] == 64.6  # TASK-0056: Entry zone = 68 * 0.95
    assert candidate["target_buy"] != 68.0, "target_buy must NEVER fallback to current_price!"
    assert candidate["target_buy"] < opp_no_target["current_price"]


def test_build_auto_watchlist_rejects_insufficient_data():
    """AC-33.1: INSUFFICIENT_DATA status is strictly rejected."""
    opp_insufficient = {
        "symbol": "TEST",
        "current_price": 20.0,
        "status": "INSUFFICIENT_DATA",
        "conviction_score": 80.0,
        "mos_pct": 20.0,
    }
    assert _build_auto_watchlist_candidate(opp_insufficient, set()) is None


def test_foreign_selling_penalty_in_conviction_score():
    """AC-33.3: Heavy foreign selling (>= 50 tỷ) penalizes conviction score by 10 pts."""
    # Base flow without heavy selling
    score_normal = calculate_conviction_score(
        mos_pct=20.0,
        curr_price=70.0,
        ma20=69.0,
        rsi=52.0,
        vol_ratio=1.1,
        foreign_flow={"status": "NEUTRAL", "foreign_net_val_bil": 0.0},
    )

    # Heavy foreign selling >= 50 tỷ
    score_heavy_selling = calculate_conviction_score(
        mos_pct=20.0,
        curr_price=70.0,
        ma20=69.0,
        rsi=52.0,
        vol_ratio=1.1,
        foreign_flow={"status": "SELLING", "badge": "TÂY BÁN RÒNG", "foreign_net_val_bil": 65.5},
    )

    diff = score_normal["score"] - score_heavy_selling["score"]
    # Flow points went from 3 to 0 (-3) + foreign penalty (-10) = diff of 13
    assert diff >= 10.0, f"Expected penalty diff >= 10, got {diff}"
    assert score_heavy_selling["breakdown"]["foreign_penalty"] == 10.0


def test_foreign_moderate_selling_penalty():
    """AC-33.3: Moderate foreign selling (20-49 tỷ) penalizes conviction score by 5 pts."""
    score_mod = calculate_conviction_score(
        mos_pct=20.0,
        curr_price=70.0,
        ma20=69.0,
        rsi=52.0,
        vol_ratio=1.1,
        foreign_flow={"status": "SELLING", "badge": "TÂY BÁN RÒNG", "foreign_net_val_bil": 25.0},
    )
    assert score_mod["breakdown"]["foreign_penalty"] == 5.0


def test_mwg_updated_consensus_target_and_freshness():
    """AC-33.5: MWG consensus target is updated to 83.5k with fresh last_updated date."""
    mwg_data = INSTITUTIONAL_CONSENSUS_TARGETS.get("MWG")
    assert mwg_data is not None
    assert mwg_data["consensus_target"] == 83.5
    assert mwg_data["last_updated"] == "2026-09-30"

    freshness = check_institutional_target_freshness("MWG", as_of_date="2026-10-02")
    assert freshness["is_stale"] is False, "Consensus target of MWG should be fresh within 180 days!"

    # Valuation check with fresh target
    val = calculate_fair_value_and_mos("MWG", current_price=72.6, sector="Bán lẻ")
    assert val["mos_is_informative"] is True, "Fresh consensus target makes MoS informative!"
    assert val["consensus_stale"] is False
    assert val["price_target"] == 83.5
    # MoS should be around 9.0%, NOT 15.3%
    assert 7.0 <= val["mos_pct"] <= 12.0
    assert val["mos_pct"] != 15.3


def test_sync_auto_watchlist_excludes_synthetic_mwg(tmp_path):
    """Full integration test: sync_auto_watchlist excludes candidate with synthetic MoS."""
    wl_file = tmp_path / "test_watchlist.json"
    opportunities = [
        {
            "symbol": "MWG",
            "current_price": 72.6,
            "target_price": None,
            "conviction_score": 65.0,
            "mos_pct": 15.3,
            "mos_is_informative": False,
            "status": "WATCH_CONFIRMATION",
            "sector": "💻 Công nghệ & Tiêu dùng Tăng trưởng",
        }
    ]
    res = sync_auto_watchlist(opportunities=opportunities, filepath=str(wl_file), max_auto=5)
    symbols = [x["symbol"] for x in res]
    assert "MWG" not in symbols, "MWG with synthetic MoS must not be added to watchlist!"
