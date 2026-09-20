"""
Unit tests for Phase 3: Smart Compressed Prompt & Built-in Red Team.
Validates 5-expert sequential reasoning, Red Team contrarian challenge,
8 PM decision states, and zero-token Data Gate rejection.
"""
from unittest.mock import patch

import pandas as pd
import pytest

from ai_analyst import (
    analyze_stock_with_smart_committee,
    generate_morning_strategy_report,
    sanitize_ai_text,
)


@pytest.mark.offline
class TestSmartCompressedPrompt:
    """Test suite for Phase 3 Smart Compressed Prompt & Built-in Red Team."""

    def test_smart_prompt_construction_and_execution(self):
        """Verify 5-expert reasoning and 3 Red Team questions in prompt."""
        captured_prompts = []

        def mock_call_gemini(client, prompt):
            captured_prompts.append(prompt)
            return (
                "BÁO CÁO HỘI ĐỒNG ĐẦU TƯ CHO CỔ PHIẾU **HPG**\n"
                "FA VIEW: BULLISH\n"
                "TA VIEW: BULLISH\n"
                "MACRO VIEW: SUPPORTIVE\n"
                "RED TEAM: Điểm yếu nhất là giá quặng sắt biến động.\n"
                "PM DECISION: STRONG_OPPORTUNITY — Mua ngay vì định giá P/B dưới 1.5x."
            )

        mock_tech = {
            "current_price": 28.5,
            "ref_price": 28.0,
            "close": 28.5,
            "ma20": 27.8,
            "ma50": 26.5,
            "rsi14": 56.0,
            "volume": 25000000,
            "vol_ratio": 1.35,
            "adv20_billion": 500.0,
            "status_ma20": "TRÊN MA20"
        }
        mock_fin = {
            "period": "Q2/2026",
            "roe": 16.5,
            "pb": 1.45,
            "pe": 10.2,
            "f_score": 8,
            "z_score": 3.2
        }

        with patch("ai_analyst.call_gemini", side_effect=mock_call_gemini):
            res = analyze_stock_with_smart_committee(
                symbol="HPG",
                tech_data=mock_tech,
                fin_data=mock_fin,
                news_items=[{"title": "Hòa Phát xuất khẩu thép tăng mạnh", "tag": "KQKD"}]
            )

        assert res["status"] == "SUCCESS"
        assert res["symbol"] == "HPG"
        assert res["pm_decision"] == "STRONG_OPPORTUNITY"
        assert len(captured_prompts) == 1

        prompt = captured_prompts[0]
        # Check 5 expert sequential reasoning in prompt
        assert "BƯỚC 1: ĐÁNH GIÁ CƠ BẢN (FA VIEW)" in prompt
        assert "BƯỚC 2: ĐÁNH GIÁ KỸ THUẬT (TA VIEW)" in prompt
        assert "BƯỚC 3: ĐÁNH GIÁ VĨ MÔ & XÚC TÁC" in prompt
        assert "BƯỚC 4: RED TEAM — TỰ PHẢN BIỆN" in prompt
        assert "BƯỚC 5: QUYẾT ĐỊNH CUỐI CÙNG (PM DECISION)" in prompt

        # Check 3 core Red Team questions in prompt
        assert "Điểm YẾU NHẤT trong luận điểm đầu tư này là gì?" in prompt
        assert "Nếu loại bỏ chất xúc tác tốt nhất, luận điểm có còn đứng vững không?" in prompt
        assert "Kịch bản rủi ro sụt giảm (downside scenario)" in prompt

        # Check 8 PM states
        assert "STRONG_OPPORTUNITY | ATTRACTIVE | WATCHLIST | WAIT_BETTER_ENTRY" in prompt

    def test_smart_prompt_data_gate_rejection_zero_ai_tokens(self):
        """Corrupted data must be rejected immediately at Phase 0 gate with 0 AI calls."""
        corrupted_tech = {
            "current_price": -5.0,  # Fatal non-positive price
            "close": -5.0,
            "ref_price": 28.0
        }

        with patch("ai_analyst.call_gemini") as mock_gemini:
            res = analyze_stock_with_smart_committee(
                symbol="HPG",
                tech_data=corrupted_tech,
                fin_data={},
                news_items=[]
            )

            # Assert Gemini is NEVER called -> 0 AI tokens spent!
            mock_gemini.assert_not_called()

        assert res["status"] == "DATA_GATE_REJECTED"
        assert res["pm_decision"] == "INSUFFICIENT_DATA"
        assert "TỪ CHỐI KHUYẾN NGHỊ" in res["report_text"]
        assert res["data_quality"] in ["CRITICAL", "LOW"]

    def test_morning_report_injects_data_quality_and_5_expert_guidelines(self):
        """generate_morning_strategy_report must include Data Quality and 5-Expert guidelines."""
        captured_prompts = []

        def mock_call_gemini(client, prompt):
            captured_prompts.append(prompt)
            return "BÁO CÁO CHIẾN LƯỢC ĐẦU NGÀY..."

        opps = [
            {
                "symbol": "FPT",
                "status": "RECOMMEND_BUY",
                "current_price": 135.0,
                "sector": "Công nghệ",
                "story_tag": "AI",
                "story": "Hợp tác Nvidia",
                "data_quality": "HIGH",
                "data_badge": "📊 DATA QUALITY: HIGH (95/100)"
            }
        ]

        with patch("ai_analyst.call_gemini", side_effect=mock_call_gemini), \
             patch("quant_valuation.calculate_fair_value_and_mos", return_value={"fair_value": 150.0, "mos_pct": 11.1, "valuation_method": "P/E", "confidence": "HIGH"}), \
             patch("data_engine.fetch_stock_technical", return_value={"current_price": 1280.0, "change_pct": 0.5, "ma20": 1270.0, "ma50": 1260.0, "rsi14": 55.0, "status_ma20": "TRÊN MA20"}):

            generate_morning_strategy_report(
                portfolio_df=pd.DataFrame(),
                watchlist_df=pd.DataFrame(),
                opportunities=opps,
                news_items=[]
            )

        assert len(captured_prompts) == 1
        prompt = captured_prompts[0]

        # Verify Data Quality Badge in buy section
        assert "DATA QUALITY: HIGH" in prompt
        # Verify 5-Expert and Red Team guidelines in prompt
        assert "Hội đồng Đầu tư 5 vai trò & Tự phản biện Red Team" in prompt
        assert "Phản biện Red Team (3 câu cốt lõi)" in prompt
        assert "Phán quyết PM:" in prompt

    def test_zero_cjk_sanitization(self):
        """Output text must have zero CJK characters and bold tickers."""
        raw_text = "Phân tích 股票 cho Mã SSI tại 证券公司 SSI. Khuyến nghị 买入 với giá mục tiêu 40k."
        cleaned = sanitize_ai_text(raw_text)

        assert "股票" not in cleaned
        assert "买入" not in cleaned
        assert "证券公司" not in cleaned
        assert "**SSI**" in cleaned

    def test_pm_decision_strict_parsing_rejects_distractor_states(self):
        """Red Team mentioning STRONG_OPPORTUNITY as negative context must NOT override PM decision."""
        misleading_report = (
            "BÁO CÁO HỘI ĐỒNG ĐẦU TƯ CHO CỔ PHIẾU **VHM**\n"
            "BƯỚC 1: ĐÁNH GIÁ CƠ BẢN (FA VIEW): BEARISH\n"
            "BƯỚC 4: RED TEAM — TỰ PHẢN BIỆN:\n"
            "Điểm yếu nhất: Cổ phiếu này tuyệt đối KHÔNG phải là STRONG_OPPORTUNITY hay ATTRACTIVE.\n"
            "BƯỚC 5: QUYẾT ĐỊNH CUỐI CÙNG (PM DECISION):\n"
            "PM DECISION: AVOID — Nợ vay ngắn hạn quá lớn, nguy cơ pha loãng."
        )

        mock_tech = {"current_price": 40.0, "ref_price": 40.0, "close": 40.0, "ma20": 42.0}
        mock_fin = {"f_score": 3, "z_score": 1.1}

        with patch("ai_analyst.call_gemini", return_value=misleading_report):
            res = analyze_stock_with_smart_committee(
                symbol="VHM",
                tech_data=mock_tech,
                fin_data=mock_fin,
                news_items=[]
            )

        assert res["status"] == "SUCCESS"
        # Must be AVOID, NOT STRONG_OPPORTUNITY or ATTRACTIVE
        assert res["pm_decision"] == "AVOID"

    def test_missing_fin_data_does_not_hallucinate_healthy_scores(self):
        """Missing fin indicators must render as N/A in prompt instead of fake 7/9 or 2.50."""
        captured_prompts = []

        def mock_call_gemini(client, prompt):
            captured_prompts.append(prompt)
            return "PM DECISION: WATCHLIST — Thiếu BCTC."

        mock_tech = {"current_price": 20.0, "ref_price": 20.0, "close": 20.0}

        with patch("ai_analyst.call_gemini", side_effect=mock_call_gemini):
            res = analyze_stock_with_smart_committee(
                symbol="TEST",
                tech_data=mock_tech,
                fin_data={},  # Empty financial data
                news_items=[]
            )

        assert len(captured_prompts) == 1
        prompt = captured_prompts[0]
        # Should not default to fake healthy 7/9 or fake technical values
        assert "7/9" not in prompt
        assert "RSI(14): N/A" in prompt
        assert "MA20: N/A" in prompt
        assert "Vol/SMA20: N/A" in prompt
        assert "0/9 (YẾU / RỦI RO)" in prompt

    def test_call_gemini_retry_resilience(self):
        """call_gemini must retry on transient error and succeed when recovered."""
        from unittest.mock import MagicMock
        from ai_analyst import call_gemini

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.text = "BÁO CÁO HỢP LỆ"

        # Fail once, succeed on 2nd attempt
        mock_client.models.generate_content.side_effect = [
            TimeoutError("Connection timed out"),
            mock_response
        ]

        result = call_gemini(mock_client, "Test prompt", max_retries=2, retry_delay=0.01)
        assert result == "BÁO CÁO HỢP LỆ"
        assert mock_client.models.generate_content.call_count == 2

    def test_ai_generation_failed_handled_gracefully(self):
        """If Gemini completely fails all retries, analyze_stock_with_smart_committee handles gracefully."""
        mock_tech = {"current_price": 50.0, "ref_price": 50.0, "close": 50.0}

        with patch("ai_analyst.call_gemini", side_effect=RuntimeError("API Outage")):
            res = analyze_stock_with_smart_committee(
                symbol="FPT",
                tech_data=mock_tech,
                fin_data={"f_score": 8, "z_score": 3.0},
                news_items=[]
            )

        assert res["status"] == "AI_GENERATION_FAILED"
        assert res["pm_decision"] == "INSUFFICIENT_DATA"
        assert "Lỗi kết nối AI" in res["report_text"]
