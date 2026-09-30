"""tests/test_task_0018_context_engine.py

Comprehensive test suite for Phase 8 / TASK-0018:
- AC-18.1: Reference structure & manifest tracking
- AC-18.2: TCBS Daily Report Parser with Zero-Fabrication enforcement
- AC-18.3: Context Engine loading & graceful non-blocking fail-safes
- AC-18.4: Quantitative vs Institutional Regime Conflict Arbitration
- AC-18.5: SignalEvent audit trail & integration
- AC-18.6: 100% Quality & Safety compliance
"""

import json
from pathlib import Path
from unittest import mock

import pytest

from context_engine import (
    MarketContext,
    build_context_prompt_snippet,
    check_regime_conflict,
    load_market_context,
)
from dispatcher import SignalEvent
from scripts.parse_daily_reports import (
    extract_buy_sell_signals,
    extract_focus_sectors,
    extract_market_regime_and_sentiment,
    extract_risk_keywords,
    extract_support_resistance_zones,
    extract_vnindex_summary,
    parse_date_from_filename_or_text,
    parse_tcbs_daily_report,
    update_manifests_after_processing,
)


class TestManifestManagement:
    """Test AC-18.1: Directory structure and manifest tracking."""

    def test_manifest_files_exist_and_valid_json(self):
        root_manifest = Path("docs/Reference/manifest.json")
        ptkt_manifest = Path("docs/Reference/PTKT_Daily/manifest.json")

        assert root_manifest.exists()
        assert ptkt_manifest.exists()

        with open(root_manifest, "r", encoding="utf-8") as f:
            data_root = json.load(f)
            assert "files" in data_root
            assert len(data_root["files"]) >= 5

        with open(ptkt_manifest, "r", encoding="utf-8") as f:
            data_ptkt = json.load(f)
            assert "files" in data_ptkt
            assert any(item["filename"] == "20260930_BC_PTKT.pdf" for item in data_ptkt["files"])

    def test_update_manifests_after_processing(self, tmp_path):
        dummy_manifest = tmp_path / "manifest.json"
        dummy_manifest.write_text(
            json.dumps({
                "last_updated": "2026-09-30T00:00:00Z",
                "files": [{"filename": "sample.pdf", "processed": False, "context_output": None}]
            }),
            encoding="utf-8"
        )

        with mock.patch("scripts.parse_daily_reports.DEFAULT_MANIFEST_FILE", dummy_manifest), \
             mock.patch("scripts.parse_daily_reports.DEFAULT_PTKT_MANIFEST", dummy_manifest):
            update_manifests_after_processing("sample.pdf", Path("data/market_context.json"))

        updated_data = json.loads(dummy_manifest.read_text(encoding="utf-8"))
        assert updated_data["files"][0]["processed"] is True
        assert "data/market_context.json" in updated_data["files"][0]["context_output"]


class TestDailyReportParser:
    """Test AC-18.2: Parser extracts authentic data from real PDF without fabrication."""

    def test_parse_real_tcbs_report(self):
        real_pdf = Path("docs/Reference/PTKT_Daily/20260930_BC_PTKT.pdf")
        if not real_pdf.exists():
            pytest.skip("File 20260930_BC_PTKT.pdf not found in local workspace")

        res = parse_tcbs_daily_report(real_pdf)
        assert res["date"] == "2026-09-30"
        assert res["source"] == "TCBS"
        assert res["source_file"] == "20260930_BC_PTKT.pdf"
        assert res["vnindex_close"] == 1768.6
        assert res["vnindex_change_pts"] == -9.1
        assert res["vnindex_change_pct"] == -0.5
        assert res["market_regime_analyst"] == "DOWNTREND"
        assert res["sentiment"] == "BEARISH"

        # Zero fabrication checks
        assert res["vnindex_support_zones"] == []
        assert res["vnindex_resistance_zones"] == []
        assert res["buy_signals"] == []
        assert "CMG" in res["sell_signals"]
        assert "168" not in res["sell_signals"]  # Digits cleanly filtered out
        assert len(res["focus_sectors"]) > 0
        assert "áp lực điều chỉnh" in res["risk_keywords"]
        assert len(res["raw_summary"]) > 50

    def test_extract_vnindex_summary_positive(self):
        sample_text = (
            "VN-Index đóng cửa tại 1,280.50 điểm, tăng 12.30 điểm (tương đương 0.97%). "
            "Phiên giao dịch ngày 15/10 tăng mạnh mẽ... HNX-Index"
        )
        res = extract_vnindex_summary(sample_text)
        assert res["vnindex_close"] == 1280.5
        assert res["vnindex_change_pts"] == 12.3
        assert res["vnindex_change_pct"] == 0.97
        assert "Phiên giao dịch ngày 15/10" in res["raw_summary"]

    def test_extract_support_resistance_zones_when_present(self):
        sample_text = "Vùng hỗ trợ mạnh tại 1250 - 1260, vùng kháng cự tại 1300."
        sup, res = extract_support_resistance_zones(sample_text)
        assert 1250.0 in sup
        assert 1260.0 in sup
        assert 1300.0 in res

    def test_extract_support_resistance_zones_absent(self):
        sample_text = "Thị trường giằng co quanh mốc tham chiếu không rõ biên độ."
        sup, res = extract_support_resistance_zones(sample_text)
        assert sup == []
        assert res == []

    def test_extract_focus_sectors(self):
        sample_text = "Nhóm Bất động sản và Ngân hàng dẫn dắt thị trường, Bán lẻ sụt giảm."
        sectors = extract_focus_sectors(sample_text)
        assert "Bất động sản" in sectors
        assert "Ngân hàng" in sectors
        assert "Bán lẻ" in sectors
        assert "Thép" not in sectors

    def test_extract_risk_keywords(self):
        sample_text = "Áp lực chốt lời gia tăng mạnh, thị trường có rủi ro điều chỉnh và suy yếu."
        kws = extract_risk_keywords(sample_text)
        assert "áp lực chốt lời" in kws
        assert "rủi ro điều chỉnh" in kws
        assert "suy yếu" in kws

    def test_extract_buy_sell_signals(self):
        pages = [
            "Danh mục cổ phiếu có tín hiệu MUA\nMã CK: HPG, SSI\nDanh mục cổ phiếu có tín hiệu BÁN\nMã CK: VHM\nDiễn giải"
        ]
        buys, sells = extract_buy_sell_signals(pages)
        assert "HPG" in buys
        assert "SSI" in buys
        assert "VHM" in sells

    def test_parse_date_fallback(self):
        date1 = parse_date_from_filename_or_text("20261015_BC_PTKT.pdf", "")
        assert date1 == "2026-10-15"

        date2 = parse_date_from_filename_or_text("sample.pdf", "Techcom Securities\nNgày: 05/11/2026\n...")
        assert date2 == "2026-11-05"

    def test_extract_regime_and_sentiment_bullish(self):
        regime, sent = extract_market_regime_and_sentiment("Thị trường tích cực bứt phá sắc xanh tăng điểm", 1.2)
        assert regime == "UPTREND"
        assert sent == "BULLISH"


class TestContextEngineCore:
    """Test AC-18.3: Safe loading, schema conformity and graceful fallback."""

    def test_load_market_context_valid(self):
        ctx = load_market_context(filepath="data/market_context.json", allow_stale=True)
        assert ctx.is_valid is True
        assert ctx.source == "TCBS"
        assert ctx.date == "2026-09-30"
        assert ctx.market_regime_analyst == "DOWNTREND"
        assert isinstance(ctx.to_dict(), dict)

    def test_load_market_context_missing_file(self, tmp_path):
        missing = tmp_path / "non_existent.json"
        ctx = load_market_context(filepath=missing)
        assert ctx.is_valid is False
        assert ctx.market_regime_analyst == "UNKNOWN"

    def test_load_market_context_corrupt_json(self, tmp_path):
        corrupt = tmp_path / "corrupt.json"
        corrupt.write_text("{invalid_json: true", encoding="utf-8")
        ctx = load_market_context(filepath=corrupt)
        assert ctx.is_valid is False

    def test_load_market_context_stale_date_detected(self, tmp_path):
        dummy = tmp_path / "market_context.json"
        dummy.write_text(json.dumps({"date": "2026-09-29", "source": "TCBS"}), encoding="utf-8")

        # Session date is 2026-09-30 but file date is 2026-09-29
        ctx_stale = load_market_context(filepath=dummy, current_date="2026-09-30", allow_stale=False)
        assert ctx_stale.is_valid is False
        assert ctx_stale.date == "2026-09-29"

        # When allow_stale=True, it succeeds
        ctx_allowed = load_market_context(filepath=dummy, current_date="2026-09-30", allow_stale=True)
        assert ctx_allowed.is_valid is True


class TestRegimeConflictArbitration:
    """Test AC-18.4: Mathematical MA200 code regime vs institutional report arbitration."""

    def test_uptrend_code_vs_downtrend_analyst_cuts_size_50(self):
        conflict, rationale = check_regime_conflict(code_regime="UPTREND", analyst_regime="DOWNTREND")
        assert conflict is True
        assert "50%" in rationale

    def test_downtrend_code_vs_bullish_analyst_code_wins_cash_mode(self):
        conflict, rationale = check_regime_conflict(code_regime="DOWNTREND", analyst_regime="BULLISH")
        assert conflict is True
        assert "Cash Mode" in rationale or "cấm mở mua" in rationale

    def test_sideways_code_vs_accumulation_compatible(self):
        conflict, rationale = check_regime_conflict(code_regime="SIDEWAYS", analyst_regime="ACCUMULATION")
        assert conflict is False
        assert "ĐỒNG THUẬN" in rationale

    def test_matching_uptrends_compatible(self):
        conflict, _ = check_regime_conflict(code_regime="UPTREND MẠNH", analyst_regime="UPTREND")
        assert conflict is False

    def test_unknown_analyst_no_conflict(self):
        conflict, rationale = check_regime_conflict(code_regime="UPTREND", analyst_regime="UNKNOWN")
        assert conflict is False
        assert "Không có" in rationale


class TestPromptSnippetFormatting:
    """Test context injection snippet formatting for AI Prompt."""

    def test_snippet_empty_when_invalid_context(self):
        invalid_ctx = MarketContext(is_valid=False)
        snippet = build_context_prompt_snippet(invalid_ctx)
        assert snippet == ""

    def test_snippet_contains_structured_sections_when_valid(self):
        ctx = MarketContext(
            date="2026-09-30",
            source="TCBS",
            source_file="20260930_BC_PTKT.pdf",
            market_regime_analyst="DOWNTREND",
            sentiment="BEARISH",
            vnindex_close=1768.6,
            vnindex_change_pts=-9.1,
            vnindex_change_pct=-0.5,
            vnindex_support_zones=[1750.0],
            vnindex_resistance_zones=[1780.0],
            focus_sectors=["Vật liệu", "Tiện ích"],
            risk_keywords=["áp lực điều chỉnh"],
            buy_signals=[],
            sell_signals=["CMG"],
            raw_summary="VN-Index chịu áp lực bán ròng mạnh.",
            is_valid=True
        )

        snippet = build_context_prompt_snippet(ctx, code_regime="UPTREND")
        assert "TCBS" in snippet
        assert "2026-09-30" in snippet
        assert "1768.6" in snippet
        assert "DOWNTREND" in snippet
        assert "1750.0" in snippet
        assert "Vật liệu" in snippet
        assert "CMG" in snippet
        assert "CẢNH BÁO XUNG ĐỘT XU HƯỚNG" in snippet
        assert "LƯU Ý QUẢN TRỊ" in snippet


class TestDispatcherAndAiAnalystIntegration:
    """Test AC-18.5: SignalEvent and AI Analyst response audit fields."""

    def test_signal_event_holds_context_fields(self):
        event = SignalEvent(
            symbol="HPG",
            action="MUA",
            current_price=26.5,
            analyst_context_used=True,
            regime_conflict=True,
            context_source_file="20260930_BC_PTKT.pdf",
            context_date="2026-09-30"
        )
        data = event.to_dict()
        assert data["analyst_context_used"] is True
        assert data["regime_conflict"] is True
        assert data["context_source_file"] == "20260930_BC_PTKT.pdf"
        assert data["context_date"] == "2026-09-30"

    def test_smart_committee_returns_context_metadata(self):
        try:
            from ai_analyst import analyze_stock_with_smart_committee
        except ImportError as err:
            if "pyarrow" in str(err) or "_compute" in str(err):
                pytest.skip("Bỏ qua trên môi trường local do Windows AppLocker chặn pyarrow DLL. CI/CD Linux sẽ thực thi 100%.")
            raise

        with mock.patch("ai_analyst.call_gemini") as mock_call_gemini, \
             mock.patch("context_engine.load_market_context") as mock_load_ctx:
            mock_load_ctx.return_value = MarketContext(
                date="2026-09-30",
                source="TCBS",
                source_file="20260930_BC_PTKT.pdf",
                market_regime_analyst="DOWNTREND",
                sentiment="BEARISH",
                is_valid=True
            )
            mock_call_gemini.return_value = (
                "=== BƯỚC 1: ĐÁNH GIÁ CƠ BẢN ===\nFA VIEW: BULLISH\n"
                "=== BƯỚC 2: ĐÁNH GIÁ KỸ THUẬT ===\nTA VIEW: BULLISH\n"
                "=== BƯỚC 3: ĐÁNH GIÁ VĨ MÔ ===\nMACRO VIEW: SUPPORTIVE\n"
                "=== BƯỚC 4: RED TEAM ===\nDownside: 5%\n"
                "=== BƯỚC 5: QUYẾT ĐỊNH CUỐI CÙNG ===\nPM DECISION: ATTRACTIVE — Mua thăm dò\n"
            )

            tech_data = {
                "current_price": 30.0,
                "ref_price": 29.5,
                "change_pct": 1.7,
                "close": 30.0,
                "ma20": 29.0,
                "ma50": 28.0,
                "rsi14": 55.0,
                "vol_ratio": 1.2,
                "status_ma20": "UPTREND",
                "adv20_billion": 50.0,
                "foreign_flow": {"net_vol": 100000},
                "trap_info": {"is_trap": False}
            }
            fin_data = {
                "symbol": "FPT",
                "period": "Q2/2026",
                "roe": 0.25,
                "net_margin": 0.18,
                "debt_to_equity": 0.4
            }

            res = analyze_stock_with_smart_committee(symbol="FPT", tech_data=tech_data, fin_data=fin_data, news_items=[])
            assert res["status"] == "SUCCESS"
            assert res["analyst_context_used"] is True
            assert res["regime_conflict"] is True  # Code UPTREND vs TCBS DOWNTREND
            assert res["context_source_file"] == "20260930_BC_PTKT.pdf"
            assert res["context_date"] == "2026-09-30"
