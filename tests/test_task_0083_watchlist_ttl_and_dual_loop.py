# -*- coding: utf-8 -*-
"""Unit tests for TASK-0083: Dual-Loop State Machine & Watchlist TTL (Phase 28 - v15.0)."""

from data_engine import (
    _build_auto_watchlist_candidate,
    check_watchlist_ttl_status,
    prune_unsuitable_watchlist,
)


def test_build_auto_watchlist_candidate_includes_ttl_fields():
    """AC-01: Candidate built for auto watchlist must include watch_entry_date and watch_ttl_days."""
    opp = {
        "symbol": "FPT",
        "status": "RECOMMEND_BUY",
        "conviction_score": 75.0,
        "mos_pct": 20.0,
        "mos_is_informative": True,
        "current_price": 100.0,
        "sector": "Công nghệ",
        "entry_date": "2026-10-01",
        "watch_ttl_days": 10,
    }

    res = _build_auto_watchlist_candidate(opp, manual_symbols=set())
    assert res is not None
    assert res["symbol"] == "FPT"
    assert res["watch_entry_date"] == "2026-10-01"
    assert res["watch_ttl_days"] == 10
    assert res["entry_target_price"] > 0
    assert res["is_auto"] is True


def test_check_watchlist_ttl_status_active_vs_expired():
    """AC-02: Check active vs expired items based on watch_entry_date and as_of_date."""
    # Active item (age 4 days < 10 days)
    active_item = {
        "symbol": "MWG",
        "watch_entry_date": "2026-10-05",
        "watch_ttl_days": 10,
    }
    is_exp, age, reason = check_watchlist_ttl_status(active_item, as_of_date="2026-10-09")
    assert is_exp is False
    assert age == 4
    assert reason == ""

    # Expired item (age 11 days >= 10 days)
    expired_item = {
        "symbol": "VNM",
        "watch_entry_date": "2026-09-28",
        "watch_ttl_days": 10,
    }
    is_exp, age, reason = check_watchlist_ttl_status(expired_item, as_of_date="2026-10-09")
    assert is_exp is True
    assert age == 11
    assert "TTL" in reason
    assert "11 ngày >= 10 ngày" in reason


def test_prune_unsuitable_watchlist_auto_prunes_expired_item(tmp_path):
    """AC-02: prune_unsuitable_watchlist must prune items that exceeded TTL."""
    test_file = tmp_path / "test_ttl_watchlist.json"
    watchlist = [
        {
            "symbol": "HPG",
            "target_buy": 25.0,
            "watch_entry_date": "2026-10-07",
            "watch_ttl_days": 10,
            "is_auto": True,
            "note": "Active candidate",
        },
        {
            "symbol": "SSI",
            "target_buy": 30.0,
            "watch_entry_date": "2026-09-20",  # Expired (19 days ago)
            "watch_ttl_days": 10,
            "is_auto": True,
            "note": "Expired candidate",
        },
    ]

    tech_map = {
        "HPG": {"current_price": 25.0, "rsi14": 45.0},
        "SSI": {"current_price": 30.0, "rsi14": 50.0},
    }

    from unittest import mock

    with mock.patch("data_engine._calculate_item_mos", return_value=15.0):
        retained, pruned = prune_unsuitable_watchlist(
            watchlist=watchlist,
            filepath=str(test_file),
            tech_map=tech_map,
            prune_manual=False,
            notify_discord=False,
            as_of_date="2026-10-09",
        )

    retained_symbols = [r["symbol"] for r in retained]
    pruned_symbols = [p["symbol"] for p in pruned]

    assert "HPG" in retained_symbols
    assert "SSI" in pruned_symbols
    assert any("TTL" in p["reason"] for p in pruned if p["symbol"] == "SSI")


def test_manual_protected_item_ttl_exemption(tmp_path):
    """AC-03: An item with is_manual_protected=True is NOT deleted when TTL expires,

    instead a warning tag is appended to note.
    """
    test_file = tmp_path / "test_protected_watchlist.json"
    watchlist = [
        {
            "symbol": "TCB",
            "target_buy": 35.0,
            "watch_entry_date": "2026-09-01",  # Over a month old
            "watch_ttl_days": 10,
            "is_auto": False,
            "is_manual_protected": True,
            "note": "VIP Portfolio Stock",
        }
    ]

    tech_map = {
        "TCB": {"current_price": 35.0, "rsi14": 50.0},
    }

    from unittest import mock

    with mock.patch("data_engine._calculate_item_mos", return_value=15.0):
        retained, pruned = prune_unsuitable_watchlist(
            watchlist=watchlist,
            filepath=str(test_file),
            tech_map=tech_map,
            prune_manual=False,
            notify_discord=False,
            as_of_date="2026-10-09",
        )

    assert len(retained) == 1
    assert len(pruned) == 0
    assert retained[0]["symbol"] == "TCB"
    assert "CẢNH BÁO" in retained[0]["note"]
