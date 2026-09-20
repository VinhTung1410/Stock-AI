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
