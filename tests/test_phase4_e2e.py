"""
Unit and E2E regression tests for Phase 4:
- End-to-End quantitative and AI pipeline verification.
- Asynchronous batch execution with concurrency throttling.
- Zero-token Data Gate rejection for corrupted market inputs.
- Signal budget, cooldown, and deduplication integration.
"""

import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ai_analyst import (
    analyze_stock_with_smart_committee,
    async_analyze_stock_with_smart_committee,
    async_analyze_stocks_batch,
    async_call_gemini,
)


@pytest.mark.offline
class TestPhase4E2ERegression:
    """Test suite for Phase 4 E2E regression and asynchronous verification."""

    def test_e2e_clean_data_flow_to_pm_decision(self):
        """Clean market data flows through Gate -> Quant -> LLM -> Valid PM Decision."""
        tech = {
            "current_price": 28.5,
            "close": 28.5,
            "ref_price": 28.0,
            "change_pct": 1.79,
            "ma20": 27.5,
            "rsi14": 55.0,
            "vol_ratio": 1.2
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
        news = [{"title": "Lợi nhuận quý 1 tăng mạnh", "source": "CafeF", "tag": "KQKD"}]

        mock_client = MagicMock()
        mock_resp = MagicMock()
        mock_resp.text = """
BƯỚC 1: ĐÁNH GIÁ CƠ BẢN
- Phân tích cổ phiếu **HPG**: Cơ bản lành mạnh
- FA VIEW: BULLISH

BƯỚC 2: ĐÁNH GIÁ KỸ THUẬT
- TA VIEW: BULLISH

BƯỚC 3: ĐÁNH GIÁ VĨ MÔ
- MACRO VIEW: SUPPORTIVE

BƯỚC 4: RED TEAM
1. Điểm yếu nhất: Biến động giá thép thế giới.
2. Xúc tác biến mất: Định giá vẫn hấp dẫn theo P/B.
3. Kịch bản giảm: Xác suất 20%.

BƯỚC 5: QUYẾT ĐỊNH CUỐI CÙNG
PM DECISION: STRONG_OPPORTUNITY — Mua gom vùng hỗ trợ MA20 cho cổ phiếu HPG
- WHY NOW: Định giá rẻ và dòng tiền vào đều
"""
        mock_client.models.generate_content.return_value = mock_resp

        with patch("ai_analyst.get_ai_client", return_value=mock_client):
            res = analyze_stock_with_smart_committee(
                symbol="HPG",
                tech_data=tech,
                fin_data=fin,
                news_items=news
            )

        assert res["status"] == "SUCCESS"
        assert res["symbol"] == "HPG"
        assert res["pm_decision"] == "STRONG_OPPORTUNITY"
        assert res["data_quality"] == "HIGH"
        assert res["quality_score"] >= 85.0
        assert "**HPG**" in res["report_text"]

    def test_e2e_corrupt_data_rejected_zero_token(self):
        """Fatal price conflict or exchange band breach is rejected with ZERO token call."""
        corrupt_tech = {
            "current_price": -10.0,
            "close": -10.0,
            "ref_price": 28.0
        }

        mock_client = MagicMock()

        with patch("ai_analyst.get_ai_client", return_value=mock_client):
            res = analyze_stock_with_smart_committee(
                symbol="BAD",
                tech_data=corrupt_tech,
                fin_data={},
                news_items=[]
            )

        assert res["status"] == "DATA_GATE_REJECTED"
        assert res["pm_decision"] == "INSUFFICIENT_DATA"
        assert res["data_quality"] == "CRITICAL"
        assert "TỪ CHỐI KHUYẾN NGHỊ" in res["report_text"]
        # Ensure zero AI calls were made
        assert mock_client.models.generate_content.call_count == 0

    def test_async_call_gemini_retry_and_success(self):
        """async_call_gemini retries on transient failure and recovers."""
        mock_client = MagicMock()
        mock_client.aio = MagicMock()
        mock_resp = MagicMock()
        mock_resp.text = "BÁO CÁO ASYNC HỢP LỆ CHO MÃ **FPT**"

        mock_client.aio.models.generate_content = AsyncMock(
            side_effect=[
                TimeoutError("Connection timed out"),
                mock_resp
            ]
        )

        res = asyncio.run(async_call_gemini(mock_client, "Prompt test", max_retries=2, retry_delay=0.01))
        assert res == "BÁO CÁO ASYNC HỢP LỆ CHO MÃ **FPT**"
        assert mock_client.aio.models.generate_content.call_count == 2

    def test_async_analyze_stock_with_smart_committee(self):
        """async_analyze_stock_with_smart_committee returns structured analysis asynchronously."""
        tech = {"current_price": 100.0, "ref_price": 99.0, "close": 100.0}
        fin = {"roe": 25.0, "pe": 18.0, "pb": 3.0, "f_score": 8, "z_score": 4.0}

        mock_client = MagicMock()
        mock_client.aio = MagicMock()
        mock_resp = MagicMock()
        mock_resp.text = "PM DECISION: ATTRACTIVE — Định giá tốt cho **FPT**"
        mock_client.aio.models.generate_content = AsyncMock(return_value=mock_resp)

        res = asyncio.run(async_analyze_stock_with_smart_committee(
            symbol="FPT",
            tech_data=tech,
            fin_data=fin,
            client=mock_client
        ))

        assert res["status"] == "SUCCESS"
        assert res["symbol"] == "FPT"
        assert res["pm_decision"] == "ATTRACTIVE"

    def test_async_analyze_stocks_batch(self):
        """async_analyze_stocks_batch processes multiple candidates concurrently."""
        mock_client = MagicMock()
        mock_client.aio = MagicMock()
        mock_resp = MagicMock()
        mock_resp.text = "PM DECISION: WATCHLIST — Đang tích lũy"
        mock_client.aio.models.generate_content = AsyncMock(return_value=mock_resp)

        candidates = [
            {"symbol": "FPT", "tech_data": {"current_price": 100.0}, "fin_data": {}, "news_items": []},
            {"symbol": "HPG", "tech_data": {"current_price": 28.0}, "fin_data": {}, "news_items": []},
            {"symbol": "VHM", "tech_data": {"current_price": 42.0}, "fin_data": {}, "news_items": []}
        ]

        batch_results = asyncio.run(async_analyze_stocks_batch(
            symbols_or_candidates=candidates,
            max_concurrency=3,
            client=mock_client
        ))

        assert len(batch_results) == 3
        symbols = [r["symbol"] for r in batch_results]
        assert "FPT" in symbols
        assert "HPG" in symbols
        assert "VHM" in symbols
        assert all(r["status"] == "SUCCESS" for r in batch_results)

    def test_async_analyze_stocks_batch_empty_and_invalid(self):
        """Batch runner handles empty list and invalid inputs gracefully."""
        empty_res = asyncio.run(async_analyze_stocks_batch([]))
        assert empty_res == []

        invalid_res = asyncio.run(async_analyze_stocks_batch([12345], client=MagicMock()))
        assert len(invalid_res) == 1
        assert invalid_res[0]["status"] == "INVALID_INPUT"

    def test_async_call_gemini_retry_exhaustion_raises(self):
        """async_call_gemini raises RuntimeError when all retries fail."""
        mock_client = MagicMock()
        mock_client.aio = MagicMock()
        mock_client.aio.models.generate_content = AsyncMock(
            side_effect=TimeoutError("Server unreachable")
        )

        with pytest.raises(RuntimeError, match="failed after 2 attempts"):
            asyncio.run(async_call_gemini(mock_client, "Prompt test", max_retries=2, retry_delay=0.01))

    def test_async_analyze_stock_ai_failure_handled_gracefully(self):
        """Async analysis handles AI generation exceptions without crashing."""
        mock_client = MagicMock()
        mock_client.aio = MagicMock()
        mock_client.aio.models.generate_content = AsyncMock(
            side_effect=Exception("API Quota exceeded")
        )

        res = asyncio.run(async_analyze_stock_with_smart_committee(
            symbol="HPG",
            tech_data={"current_price": 28.0},
            fin_data={},
            news_items=[],
            client=mock_client
        ))

        assert res["status"] == "AI_GENERATION_FAILED"
        assert res["symbol"] == "HPG"
        assert res["pm_decision"] == "INSUFFICIENT_DATA"
        assert "Lỗi kết nối AI" in res["report_text"]

    def test_async_analyze_stocks_batch_with_symbol_strings(self):
        """async_analyze_stocks_batch accepts plain list of symbol strings."""
        mock_client = MagicMock()
        mock_client.aio = MagicMock()
        mock_resp = MagicMock()
        mock_resp.text = "PM DECISION: HOLD_MAINTAIN — Quan sát"
        mock_client.aio.models.generate_content = AsyncMock(return_value=mock_resp)

        # Mock resolve_input_data to avoid live API calls for string symbols
        with patch("ai_analyst._resolve_input_data", return_value=("HPG", {"current_price": 28.0}, {}, [])):
            res = asyncio.run(async_analyze_stocks_batch(["HPG"], client=mock_client))

        assert len(res) == 1
        assert res[0]["status"] == "SUCCESS"
        assert res[0]["pm_decision"] == "HOLD_MAINTAIN"

