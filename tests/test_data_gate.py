"""
Unit tests for data_gate.py — Phase 0 Data Reconciliation Gate.
Validates 100% deterministic Python auditing for price anomalies, corporate actions,
financial statement freshness, and data quality scoring.
"""

from datetime import datetime

import pytest

from data_gate import (
    SOURCE_TIER_FINANCIAL_MEDIA,
    SOURCE_TIER_OFFICIAL_FILING,
    format_data_quality_badge,
    reconcile_data,
    reconcile_news_freshness,
)


@pytest.mark.offline
class TestDataReconciliationGate:
    """Test suite for Phase 0 Data Reconciliation Gate."""

    def test_reconcile_clean_high_quality_data(self):
        """Standard high-quality data produces HIGH tier and passes gate."""
        tech = {
            "current_price": 28.5,
            "close": 28.5,
            "ref_price": 28.0,
            "change_pct": 1.79,
            "ma20": 27.5,
            "rsi14": 55.0
        }
        fin = {
            "roe": 22.5,
            "f_score": 8,
            "z_score": 3.2,
            "pe": 12.0,
            "pb": 1.8,
            "latest_quarter": 1,
            "latest_year": datetime.now().year
        }
        news = [
            {
                "title": "Doanh thu tăng trưởng 30% trong quý 1",
                "tag": "KQKD",
                "source": "CafeF",
                "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
        ]

        res = reconcile_data(symbol="HPG", tech_data=tech, fin_data=fin, news=news)

        assert res["symbol"] == "HPG"
        assert res["data_quality"] == "HIGH"
        assert res["quality_score"] >= 85.0
        assert res["gate_passed"] is True
        assert res["recommendation_allowed"] is True
        assert res["price_status"] == "CLEAN"
        assert len(res["conflicting_data"]) == 0
        assert len(res["missing_data"]) == 0

    def test_reconcile_price_conflict_statutory_limit_breach(self):
        """Price movement breaching HOSE +/-7% statutory limit triggers CONFLICT and blocks gate."""
        tech = {
            "current_price": 31.0,
            "close": 31.0,
            "ref_price": 28.0,  # (31 - 28) / 28 = +10.7% (> 7% HOSE limit)
            "change_pct": 10.7
        }

        res = reconcile_data(symbol="VHM", tech_data=tech, exchange="HOSE")

        assert res["price_status"] == "CONFLICT"
        assert res["gate_passed"] is False
        assert res["recommendation_allowed"] is False
        assert any("Statutory Band Breach" in issue for issue in res["conflicting_data"])

    def test_reconcile_corporate_action_gdkhq_mechanical_drop(self):
        """Ex-dividend date (GDKHQ) correctly classified as MECHANICAL_PRICE_DROP."""
        tech = {"current_price": 25.0, "is_gdkhq": True}
        today_str = datetime.now().strftime("%Y-%m-%d")
        corp_actions = [
            {
                "action_type": "CASH_DIVIDEND",
                "ex_date": today_str,
                "description": "Chi trả cổ tức bằng tiền 1,500đ/cp"
            }
        ]

        res = reconcile_data(symbol="SSI", tech_data=tech, corporate_actions=corp_actions)

        assert res["is_ex_dividend"] is True
        assert len(res["corporate_actions"]) >= 1
        assert any(ca["impact"] == "MECHANICAL_PRICE_DROP" for ca in res["corporate_actions"])

    def test_reconcile_stale_financial_statements(self):
        """Financial statements older than 2 quarters are flagged as stale."""
        fin = {
            "roe": 15.0,
            "f_score": 6,
            "z_score": 2.1,
            "pe": 10.0,
            "pb": 1.2,
            "latest_quarter": 1,
            "latest_year": datetime.now().year - 1  # 1 year ago (4+ quarters stale)
        }

        res = reconcile_data(symbol="MSB", tech_data={"current_price": 14.0}, fin_data=fin)

        assert len(res["stale_data"]) >= 1
        assert any("Financial Statements" in s for s in res["stale_data"])
        # Stale financials apply penalty
        assert res["quality_score"] <= 85.0

    def test_reconcile_missing_critical_data_critical_tier(self):
        """Missing technical data and non-positive price triggers CRITICAL tier."""
        tech = {"current_price": -5.0}

        res = reconcile_data(symbol="UNKNOWN", tech_data=tech)

        assert res["data_quality"] == "CRITICAL"
        assert res["gate_passed"] is False
        assert res["recommendation_allowed"] is False

    def test_news_hierarchy_and_freshness_classification(self):
        """News from official vs media sources are assigned proper source tiers."""
        news = [
            {"title": "Báo cáo thường niên", "source": "UBCK", "tag": "CBTT"},
            {"title": "Kế hoạch kinh doanh", "source": "CafeF", "tag": "TIN_TỨC"}
        ]

        reconciled, _ = reconcile_news_freshness(news)

        assert len(reconciled) == 2
        assert reconciled[0]["tier"] == SOURCE_TIER_OFFICIAL_FILING
        assert reconciled[1]["tier"] == SOURCE_TIER_FINANCIAL_MEDIA

    def test_format_data_quality_badge(self):
        """Badge formatter produces formatted markdown summary."""
        recon_mock = {
            "data_quality": "HIGH",
            "quality_score": 92.5,
            "conflicting_data": [],
            "missing_data": []
        }
        badge = format_data_quality_badge(recon_mock)
        assert "Data Quality:" in badge
        assert "HIGH" in badge
        assert "92" in badge

        # Test MEDIUM and LOW badges
        badge_med = format_data_quality_badge({"data_quality": "MEDIUM", "quality_score": 70.0})
        assert "🟡" in badge_med
        badge_crit = format_data_quality_badge({"data_quality": "CRITICAL", "quality_score": 20.0})
        assert "🔴" in badge_crit

    def test_reconcile_price_empty_and_mismatch(self):
        """Reconcile price handles empty tech data and reported vs computed mismatch."""
        from data_gate import reconcile_price

        status, p, issues = reconcile_price(tech_data=None)
        assert status == "CONFLICT"
        assert p == 0.0

        # Price mismatch: reported +5%, computed +2%
        tech = {
            "current_price": 102.0,
            "ref_price": 100.0,
            "change_pct": 5.0
        }
        status_adj, p_adj, issues_adj = reconcile_price(tech_data=tech)
        assert status_adj == "ADJUSTED"
        assert any("Price Change Mismatch" in iss for iss in issues_adj)

    def test_reconcile_corporate_actions_invalid_dates_and_empty(self):
        """Corporate action parsing handles invalid dates and empty items."""
        from data_gate import reconcile_corporate_actions

        actions = [
            {"action_type": "DIVIDEND"},  # Missing ex_date
            {"action_type": "BONUS", "ex_date": "invalid-date-format"}  # Malformed date
        ]
        tagged, is_ex = reconcile_corporate_actions(tech_data=None, corporate_actions=actions)
        assert len(tagged) == 0
        assert is_ex is False

    def test_reconcile_financial_period_missing_and_invalid(self):
        """Reconcile financial statements handles missing dict and invalid quarter formats."""
        from data_gate import reconcile_financial_period

        missing, stale = reconcile_financial_period(fin_data=None)
        assert "fin_data_dict" in missing

        fin_malformed = {
            "roe": 10.0,
            "f_score": 5,
            "z_score": 2.0,
            "pe": 10.0,
            "pb": 1.0,
            "latest_quarter": "INVALID_Q",
            "latest_year": "NOT_A_YEAR"
        }
        missing_m, stale_m = reconcile_financial_period(fin_data=fin_malformed)
        assert len(missing_m) == 0
        assert len(stale_m) == 0

    def test_reconcile_news_source_tiers_and_malformed_date(self):
        """Test news classification for BCTC tag, RSS general source, and invalid date."""
        from data_gate import (
            SOURCE_TIER_AUDITED_FINANCIALS,
            SOURCE_TIER_GENERAL_RSS,
        )

        news = [
            {"title": "Báo cáo kiểm toán 2024", "source": "Doanh nghiệp", "tag": "AUDIT", "date": "bad-date"},
            {"title": "Tin tổng hợp thị trường", "source": "Báo Lao Động", "tag": "TIN_TỨC", "date": None}
        ]
        reconciled, _ = reconcile_news_freshness(news)
        assert len(reconciled) == 2
        assert reconciled[0]["tier"] == SOURCE_TIER_AUDITED_FINANCIALS
        assert reconciled[1]["tier"] == SOURCE_TIER_GENERAL_RSS

    def test_reconcile_data_tier_low(self):
        """Test data quality producing LOW tier score."""
        # Partially missing financials + adjusted price -> score in 40-65 range
        tech = {
            "current_price": 102.0,
            "ref_price": 100.0,
            "change_pct": 5.0  # Mismatch triggers ADJUSTED (-10)
        }
        fin = {
            "roe": 10.0,
            "pe": 15.0,
            "pb": 1.5,
            # missing f_score and z_score (-12)
            "latest_quarter": 1,
            "latest_year": datetime.now().year - 2  # Stale (-15)
        }
        res = reconcile_data(symbol="TEST", tech_data=tech, fin_data=fin, news=[])
        assert res["data_quality"] in ["LOW", "MEDIUM"]
        assert res["quality_score"] < 70.0
