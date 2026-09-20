"""
Tests for Signal Credibility Engine:
- Conviction scoring (4 pillars)
- 5-day cooldown deduplication
- Daily Signal Budget (max 2 BUY recommendations)
- Portfolio Diversification Guard (max 8 open positions)
"""
import json
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest

from data_engine import (
    HIGH_CONVICTION_THRESHOLD,
    MAX_DAILY_BUY_SIGNALS,
    MEDIUM_CONVICTION_THRESHOLD,
    calculate_conviction_score,
    get_active_cooldown_symbols,
    is_symbol_in_cooldown,
    record_signal_cooldown,
    scan_market_opportunities,
)


@pytest.mark.offline
class TestConvictionScoring:
    """Validate 4-pillar conviction scoring and tier classification."""

    def test_high_conviction_setup(self):
        """Top-tier setup with deep MoS, sound technicals, catalyst and strong flow."""
        score_res = calculate_conviction_score(
            mos_pct=26.0,
            val_confidence="HIGH",
            curr_price=50.0,
            ma20=48.0,
            rsi=54.0,
            vol_ratio=1.4,
            cat_info={"tag": "KQKD", "title": "Lợi nhuận tăng trưởng kỷ lục 45%"},
            foreign_flow={"status": "BUYING", "badge": "TÂY MUA RÒNG"},
            is_trap=False
        )
        assert score_res["score"] >= HIGH_CONVICTION_THRESHOLD
        assert score_res["tier"] == "HIGH"
        assert score_res["breakdown"]["valuation"] == 40.0
        assert score_res["breakdown"]["technical"] == 25.0
        assert score_res["breakdown"]["catalyst"] == 20.0
        assert score_res["breakdown"]["liquidity"] == 15.0
        assert score_res["score"] == 100.0

    def test_medium_conviction_watch_setup(self):
        """Adequate valuation (MoS 10%) but modest catalyst and average flow."""
        score_res = calculate_conviction_score(
            mos_pct=10.0,
            val_confidence="MEDIUM",
            curr_price=22.0,
            ma20=21.8,
            rsi=52.0,
            vol_ratio=1.05,
            cat_info=None,
            foreign_flow={"status": "NEUTRAL"},
            is_trap=False
        )
        assert MEDIUM_CONVICTION_THRESHOLD <= score_res["score"] < HIGH_CONVICTION_THRESHOLD
        assert score_res["tier"] == "MEDIUM"

    def test_trap_penalization(self):
        """Stock with catalyst and apparent MoS but flagged as distribution trap."""
        score_res = calculate_conviction_score(
            mos_pct=18.0,
            val_confidence="HIGH",
            curr_price=30.0,
            ma20=32.0,  # Below MA20
            rsi=40.0,
            vol_ratio=0.8,
            cat_info={"tag": "TIN TỨC", "title": "Tin đồn kế hoạch thoái vốn"},
            foreign_flow={"status": "SELLING"},
            is_trap=True
        )
        # Heavy technical penalty should push score down
        assert score_res["score"] < HIGH_CONVICTION_THRESHOLD
        assert score_res["tier"] in ["LOW", "MEDIUM"]
        assert score_res["breakdown"]["technical"] <= 0.0

    def test_low_conviction_overvalued(self):
        """Overvalued stock with no catalyst and weak technicals."""
        score_res = calculate_conviction_score(
            mos_pct=-15.0,
            val_confidence="LOW",
            curr_price=90.0,
            ma20=95.0,
            rsi=38.0,
            vol_ratio=0.7,
            cat_info=None,
            foreign_flow={"status": "SELLING"},
            is_trap=False
        )
        assert score_res["score"] < MEDIUM_CONVICTION_THRESHOLD
        assert score_res["tier"] == "LOW"


@pytest.mark.offline
class TestCooldownEngine:
    """Validate cross-day cooldown persistence and detection."""

    def test_cooldown_record_and_check(self, tmp_path):
        """Record symbol and ensure it enters cooldown window."""
        fake_cooldown_file = str(tmp_path / ".test_cooldown.json")
        with patch("data_engine.SIGNAL_COOLDOWN_FILE", fake_cooldown_file):
            assert not is_symbol_in_cooldown("TCB")

            record_signal_cooldown("TCB", action="RECOMMEND_BUY", conviction_score=85.0)
            assert is_symbol_in_cooldown("TCB")

            # Active symbols count
            active = get_active_cooldown_symbols()
            assert "TCB" in active

    def test_cooldown_expiry(self, tmp_path):
        """Verify cooldown expires after 5 days."""
        fake_cooldown_file = str(tmp_path / ".test_cooldown.json")
        past_date = (datetime.now() - timedelta(days=6)).strftime("%Y-%m-%d")
        with open(fake_cooldown_file, "w", encoding="utf-8") as f:
            json.dump({"HPG": {"last_signal_date": past_date, "action": "RECOMMEND_BUY"}}, f)

        with patch("data_engine.SIGNAL_COOLDOWN_FILE", fake_cooldown_file):
            assert not is_symbol_in_cooldown("HPG", cooldown_days=5)


@pytest.mark.offline
class TestSignalBudgetAndGuards:
    """Validate daily signal budget cap (max 2 BUYs) and portfolio guard (max 8 positions)."""

    def test_signal_budget_caps_at_two_buys(self, tmp_path):
        """When 4 stocks qualify for HIGH conviction BUY, only top 2 remain BUY."""
        fake_cooldown_file = str(tmp_path / ".test_cooldown.json")

        def mock_tech(sym):
            p = 30.0
            return {
                "current_price": p,
                "ma20": 29.0,
                "ma50": 28.0,
                "rsi14": 55.0,
                "vol_ratio": 1.5,
                "change_pct": 1.2,
                "trap_info": {"is_trap": False},
                "foreign_flow": {"status": "BUYING", "badge": "TÂY MUA"}
            }

        def mock_val(symbol, current_price, sector):
            return {
                "fair_value": current_price * 1.3,
                "mos_pct": 25.0,
                "valuation_method": "DCF",
                "confidence": "HIGH",
                "price_target": current_price * 1.35
            }

        with patch("data_engine.SIGNAL_COOLDOWN_FILE", fake_cooldown_file), \
             patch("db_manager.check_symbol_recent_signal", return_value=False), \
             patch("db_manager.fetch_open_signals", return_value=[]), \
             patch("data_engine.fetch_stock_technical", side_effect=mock_tech), \
             patch("quant_valuation.calculate_fair_value_and_mos", side_effect=mock_val), \
             patch("data_engine.fetch_macro_news", return_value=[]), \
             patch("data_engine.load_watchlist", return_value=[]):

            results = scan_market_opportunities(extra_symbols=["HPG", "FPT", "SSI", "TCB"])

            buy_results = [r for r in results if r["status"] == "RECOMMEND_BUY"]
            watch_results = [r for r in results if r["status"] == "WATCH_CONFIRMATION"]

            # Daily budget limit: exactly 2 BUY signals max
            assert len(buy_results) <= MAX_DAILY_BUY_SIGNALS

            # Overflow picks were gracefully downgraded to WATCH_CONFIRMATION
            assert len(watch_results) >= 1
            assert any("VƯỢT HẠN MỨC" in w["setup_type"] for w in watch_results)

    def test_cooldown_downgrades_to_watch(self, tmp_path):
        """Stock qualifying for BUY that is in active cooldown gets downgraded to WATCH."""
        fake_cooldown_file = str(tmp_path / ".test_cooldown.json")
        today_str = datetime.now().strftime("%Y-%m-%d")
        with open(fake_cooldown_file, "w", encoding="utf-8") as f:
            json.dump({"HPG": {"last_signal_date": today_str, "action": "RECOMMEND_BUY"}}, f)

        def mock_tech(sym):
            return {
                "current_price": 28.0,
                "ma20": 27.0,
                "ma50": 26.0,
                "rsi14": 56.0,
                "vol_ratio": 1.4,
                "change_pct": 0.8,
                "trap_info": {"is_trap": False},
                "foreign_flow": {"status": "BUYING"}
            }

        def mock_val(symbol, current_price, sector):
            return {
                "fair_value": 35.0,
                "mos_pct": 25.0,
                "valuation_method": "P/B",
                "confidence": "HIGH"
            }

        with patch("data_engine.SIGNAL_COOLDOWN_FILE", fake_cooldown_file), \
             patch("db_manager.check_symbol_recent_signal", return_value=False), \
             patch("db_manager.fetch_open_signals", return_value=[]), \
             patch("data_engine.fetch_stock_technical", side_effect=mock_tech), \
             patch("quant_valuation.calculate_fair_value_and_mos", side_effect=mock_val), \
             patch("data_engine.fetch_macro_news", return_value=[]), \
             patch("data_engine.load_watchlist", return_value=[]):

            results = scan_market_opportunities(extra_symbols=["HPG"])
            hpg_pick = next((r for r in results if r["symbol"] == "HPG"), None)

            assert hpg_pick is not None
            assert hpg_pick["status"] == "WATCH_CONFIRMATION"
            assert "COOLDOWN" in hpg_pick["setup_type"].upper()

    def test_portfolio_guard_blocks_when_max_positions_reached(self, tmp_path):
        """When 8 positions are active in cooldown, all new buys are blocked and put on WATCH."""
        fake_cooldown_file = str(tmp_path / ".test_cooldown.json")
        today_str = datetime.now().strftime("%Y-%m-%d")
        # Populate 8 active positions
        mock_data = {f"SYM{i}": {"last_signal_date": today_str, "action": "RECOMMEND_BUY"} for i in range(8)}
        with open(fake_cooldown_file, "w", encoding="utf-8") as f:
            json.dump(mock_data, f)

        def mock_tech(sym):
            return {
                "current_price": 50.0,
                "ma20": 48.0,
                "ma50": 47.0,
                "rsi14": 55.0,
                "vol_ratio": 1.5,
                "change_pct": 1.0,
                "trap_info": {"is_trap": False},
                "foreign_flow": {"status": "BUYING"}
            }

        def mock_val(symbol, current_price, sector):
            return {
                "fair_value": 70.0,
                "mos_pct": 30.0,
                "valuation_method": "DCF",
                "confidence": "HIGH"
            }

        with patch("data_engine.SIGNAL_COOLDOWN_FILE", fake_cooldown_file), \
             patch("db_manager.check_symbol_recent_signal", return_value=False), \
             patch("db_manager.fetch_open_signals", return_value=[]), \
             patch("data_engine.fetch_stock_technical", side_effect=mock_tech), \
             patch("quant_valuation.calculate_fair_value_and_mos", side_effect=mock_val), \
             patch("data_engine.fetch_macro_news", return_value=[]), \
             patch("data_engine.load_watchlist", return_value=[]):

            results = scan_market_opportunities(extra_symbols=["NEW_STOCK"])
            buy_results = [r for r in results if r["status"] == "RECOMMEND_BUY"]
            watch_results = [r for r in results if r["status"] == "WATCH_CONFIRMATION"]

            assert len(buy_results) == 0, "No BUY signals allowed when portfolio cap is full"
            assert len(watch_results) >= 1
            assert any("THU HỒI VỐN" in w["setup_type"] or "VỊ THẾ" in w["setup_type"] for w in watch_results)


@pytest.mark.offline
class TestSignalDeduplication:
    """Validate cross-category deduplication and guarantee 0% duplicate ticker rate."""

    def test_bsr_in_news_and_watchlist_dedup(self, tmp_path):
        """BSR present in RSS news, user watchlist, and extra_symbols must appear at most once."""
        fake_cooldown_file = str(tmp_path / ".test_cooldown.json")

        def mock_tech(sym):
            return {
                "current_price": 19.5,
                "ma20": 19.0,
                "ma50": 18.5,
                "rsi14": 56.0,
                "vol_ratio": 1.4,
                "change_pct": 2.1,
                "trap_info": {"is_trap": False},
                "foreign_flow": {"status": "BUYING", "badge": "TÂY MUA RÒNG"}
            }

        def mock_val(symbol, current_price, sector):
            return {
                "fair_value": 26.0,
                "mos_pct": 33.3,
                "valuation_method": "P/B Chu kỳ",
                "confidence": "HIGH"
            }

        mock_news = [
            {"tag": "KQKD", "title": "BSR báo lãi lớn quý 1", "matched_symbols": ["BSR"]},
            {"tag": "VĨ MÔ", "title": "Giá dầu thế giới tăng mạnh", "matched_symbols": ["BSR"]}
        ]
        mock_wl = [{"symbol": "BSR", "note": "Mã trọng tâm lọc dầu"}]

        with patch("data_engine.SIGNAL_COOLDOWN_FILE", fake_cooldown_file), \
             patch("db_manager.check_symbol_recent_signal", return_value=False), \
             patch("db_manager.fetch_open_signals", return_value=[]), \
             patch("data_engine.fetch_stock_technical", side_effect=mock_tech), \
             patch("quant_valuation.calculate_fair_value_and_mos", side_effect=mock_val), \
             patch("data_engine.fetch_macro_news", return_value=mock_news), \
             patch("data_engine.load_watchlist", return_value=mock_wl):

            results = scan_market_opportunities(extra_symbols=["BSR"])
            bsr_matches = [r for r in results if r.get("symbol") == "BSR"]

            assert len(bsr_matches) == 1, f"Expected BSR to appear exactly once, but got {len(bsr_matches)}"

    def test_output_strictly_unique_symbols(self, tmp_path):
        """Under any candidate combination, the final output must contain 0 duplicate symbols."""
        fake_cooldown_file = str(tmp_path / ".test_cooldown.json")

        def mock_tech(sym):
            return {
                "current_price": 30.0,
                "ma20": 29.0,
                "ma50": 28.0,
                "rsi14": 55.0,
                "vol_ratio": 1.3,
                "change_pct": 1.5,
                "trap_info": {"is_trap": False},
                "foreign_flow": {"status": "BUYING"}
            }

        def mock_val(symbol, current_price, sector):
            return {
                "fair_value": 45.0,
                "mos_pct": 50.0,
                "valuation_method": "DCF",
                "confidence": "HIGH"
            }

        with patch("data_engine.SIGNAL_COOLDOWN_FILE", fake_cooldown_file), \
             patch("db_manager.check_symbol_recent_signal", return_value=False), \
             patch("db_manager.fetch_open_signals", return_value=[]), \
             patch("data_engine.fetch_stock_technical", side_effect=mock_tech), \
             patch("quant_valuation.calculate_fair_value_and_mos", side_effect=mock_val), \
             patch("data_engine.fetch_macro_news", return_value=[]), \
             patch("data_engine.load_watchlist", return_value=[{"symbol": "HPG"}]):

            # Pass duplicate symbols in extra_symbols
            results = scan_market_opportunities(extra_symbols=["HPG", "HPG", "FPT", "FPT", "BSR", "BSR"])
            symbols = [r["symbol"] for r in results]

            assert len(symbols) == len(set(symbols)), f"Duplicate symbols detected: {symbols}"

    def test_ai_morning_report_defensive_dedup(self):
        """generate_morning_strategy_report must defensively deduplicate any passed opportunities."""
        import pandas as pd

        from ai_analyst import generate_morning_strategy_report

        duplicated_opps = [
            {"symbol": "BSR", "status": "RECOMMEND_BUY", "current_price": 19.5, "sector": "Dầu khí", "story_tag": "KQKD", "story": "Lãi lớn"},
            {"symbol": "BSR", "status": "WATCH_CONFIRMATION", "current_price": 19.5, "sector": "Dầu khí", "setup_type": "Theo dõi", "rationale": "Chờ nền"},
            {"symbol": "HPG", "status": "RECOMMEND_BUY", "current_price": 28.0, "sector": "Thép", "story_tag": "ĐẦU TƯ CÔNG", "story": "Dung Quất 2"},
        ]

        captured_prompt = []

        def mock_call_gemini(client, prompt):
            captured_prompt.append(prompt)
            return "BÁO CÁO CHIẾN LƯỢC ĐẦU NGÀY..."

        with patch("ai_analyst.call_gemini", side_effect=mock_call_gemini), \
             patch("quant_valuation.calculate_fair_value_and_mos", return_value={"fair_value": 25.0, "mos_pct": 20.0, "valuation_method": "P/B", "confidence": "HIGH"}), \
             patch("data_engine.fetch_stock_technical", return_value={"current_price": 1280.0, "change_pct": 0.5, "ma20": 1270.0, "ma50": 1260.0, "rsi14": 55.0, "status_ma20": "TRÊN MA20"}):

            res = generate_morning_strategy_report(
                portfolio_df=pd.DataFrame(),
                watchlist_df=pd.DataFrame(),
                opportunities=duplicated_opps,
                news_items=[]
            )

            assert len(captured_prompt) == 1
            prompt_text = captured_prompt[0]

            # BSR was passed twice in opportunities, but defensive dedup ensures it is processed once
            # It was first RECOMMEND_BUY, so it appears in section 3, not in section 4
            assert "• Mã: **BSR**" in prompt_text
            # Check count of "• Mã: **BSR**"
            assert prompt_text.count("• Mã: **BSR**") == 1, "BSR must only appear once in AI prompt opportunities"

