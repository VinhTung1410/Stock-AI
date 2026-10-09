"""Unit tests for audit trail logging quality and MoS normalization (TASK Logging Quality).

Tests:
- BVPS unit normalization in quant_valuation.py
- Session detection in data_engine.py (_get_scanner_session)
- Decision and gate mapping after budget and cooldown filters (_determine_scanner_decision_and_gate)
- Test isolation and canonicalization in db_manager.py (save_decision_record)
"""

from datetime import datetime
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

from data_engine import (
    _determine_scanner_decision_and_gate,
    _get_scanner_session,
)
from db_manager import save_decision_record
from quant_valuation import evaluate_real_estate_valuation


class TestBVPSUnitNormalization:
    """Kiểm tra chuẩn hóa đơn vị BVPS từ VND sang k VND."""

    def test_bvps_raw_vnd_scaled_down(self):
        """Khi BVPS trả về từ BCTC ở đơn vị VND (e.g. 57,197 VND), hệ thống phải chia cho 1000."""
        # VHM: current_price 67.9k, bvps 57197 VND -> bvps_val 57.197k
        res = evaluate_real_estate_valuation(
            symbol="VHM",
            current_price=67.9,
            fin_dict={"bvps": 57197.0, "pb": 1.18, "roe": 12.0, "debt_equity": 0.5},
            sector="Bất động sản",
        )
        # fv_base phải nằm quanh vùng ~60k-75k, KHÔNG được chạm trần 30,000k+
        assert 40.0 <= res["fv_base"] <= 90.0
        assert res["fv_base"] < 1000.0

    def test_bvps_already_in_thousand_vnd_unchanged(self):
        """Khi BVPS đã ở đơn vị nghìn VND (e.g. 25.0k), giữ nguyên giá trị."""
        res = evaluate_real_estate_valuation(
            symbol="DXG",
            current_price=10.0,
            fin_dict={"bvps": 25.0, "pb": 1.0, "roe": 10.0, "debt_equity": 0.6},
            sector="Bất động sản",
        )
        assert res["fv_base"] < 100.0


class TestScannerSessionDetection:
    """Kiểm tra xác định phiên thị trường theo giờ Việt Nam."""

    def test_weekend_session(self):
        # Thứ Bảy 2026-10-10
        sat = datetime(2026, 10, 10, 10, 0, tzinfo=ZoneInfo("Asia/Ho_Chi_Minh"))
        with patch("data_engine.datetime") as mock_dt:
            mock_dt.now.return_value = sat
            assert _get_scanner_session() == "WEEKEND"

    def test_ato_session(self):
        # Thứ Hai 09:05
        ato = datetime(2026, 10, 12, 9, 5, tzinfo=ZoneInfo("Asia/Ho_Chi_Minh"))
        with patch("data_engine.datetime") as mock_dt:
            mock_dt.now.return_value = ato
            assert _get_scanner_session() == "ATO"

    def test_morning_session(self):
        # Thứ Hai 10:15
        morn = datetime(2026, 10, 12, 10, 15, tzinfo=ZoneInfo("Asia/Ho_Chi_Minh"))
        with patch("data_engine.datetime") as mock_dt:
            mock_dt.now.return_value = morn
            assert _get_scanner_session() == "MORNING"

    def test_noon_session(self):
        # Thứ Hai 12:00
        noon = datetime(2026, 10, 12, 12, 0, tzinfo=ZoneInfo("Asia/Ho_Chi_Minh"))
        with patch("data_engine.datetime") as mock_dt:
            mock_dt.now.return_value = noon
            assert _get_scanner_session() == "NOON"

    def test_afternoon_session(self):
        # Thứ Hai 13:45
        aft = datetime(2026, 10, 12, 13, 45, tzinfo=ZoneInfo("Asia/Ho_Chi_Minh"))
        with patch("data_engine.datetime") as mock_dt:
            mock_dt.now.return_value = aft
            assert _get_scanner_session() == "AFTERNOON"

    def test_close_session(self):
        # Thứ Hai 15:30
        close = datetime(2026, 10, 12, 15, 30, tzinfo=ZoneInfo("Asia/Ho_Chi_Minh"))
        with patch("data_engine.datetime") as mock_dt:
            mock_dt.now.return_value = close
            assert _get_scanner_session() == "CLOSE"


class TestScannerDecisionMapping:
    """Kiểm tra ánh xạ decision và gate sau khi áp dụng bộ lọc ngân sách."""

    def test_approved_buy(self):
        candidate = {"symbol": "HPG", "status": "RECOMMEND_BUY"}
        approved = [candidate]
        dec, gate = _determine_scanner_decision_and_gate(candidate, approved)
        assert dec == "BUY"
        assert gate == "PASSED"

    def test_cooldown_downgrade(self):
        candidate = {
            "symbol": "FPT",
            "status": "WATCH_CONFIRMATION",
            "setup_type": "⏳ THEO DÕI NẮM GIỮ (Đang Cooldown 5 ngày)",
            "rationale": "Mã FPT đã phát tín hiệu gần đây.",
        }
        dec, gate = _determine_scanner_decision_and_gate(candidate, [])
        assert dec == "WATCH"
        assert gate == "COOLDOWN_GATE"

    def test_portfolio_cap_downgrade(self):
        candidate = {
            "symbol": "MWG",
            "status": "WATCH_CONFIRMATION",
            "setup_type": "🛡️ CHỜ THU HỒI VỐN (Đã mở 8/8 vị thế)",
            "rationale": "hạn mức tối đa 8 vị thế đang theo dõi.",
        }
        dec, gate = _determine_scanner_decision_and_gate(candidate, [])
        assert dec == "WATCH"
        assert gate == "PORTFOLIO_CAP_GATE"

    def test_budget_overflow_downgrade(self):
        candidate = {
            "symbol": "SSI",
            "status": "WATCH_CONFIRMATION",
            "setup_type": "🎯 TIỀM NĂNG (VƯỢT HẠN MỨC 2 MÃ MUA/NGÀY)",
            "rationale": "hạn mức tối đa 2 mã mua/ngày.",
        }
        dec, gate = _determine_scanner_decision_and_gate(candidate, [])
        assert dec == "WATCH"
        assert gate == "SIGNAL_BUDGET_OVERFLOW"


class TestSaveDecisionRecordQuality:
    """Kiểm tra tính toàn vẹn và cách ly của save_decision_record."""

    def test_test_environment_isolation(self, monkeypatch):
        """Môi trường testing phải chặn ghi vào Supabase."""
        monkeypatch.setenv("ENV", "testing")
        dec_id = save_decision_record({"symbol": "TEST", "decision": "BUY"})
        assert dec_id.startswith("DEC_TEST_")

    def test_facts_and_opinions_canonicalization(self, monkeypatch):
        """Các trường facts, opinions và counterfactual được chuẩn hóa canonical."""
        monkeypatch.delenv("ENV", raising=False)
        monkeypatch.delenv("DRY_RUN", raising=False)

        mock_client = MagicMock()
        mock_client.table.return_value.insert.return_value.execute.return_value = MagicMock(data=[{"id": "rec-1"}])

        with patch("db_manager.get_supabase_client", return_value=mock_client):
            rec = {
                "symbol": "HPG",
                "session": "MORNING",
                "decision": "BUY",
                "prompt_hash": "hash123",
                "input_hash": "hash456",
                "facts": {"price": 28.5},
                "thesis_breaker": "Thủng MA50",
            }
            dec_id = save_decision_record(rec)
            assert dec_id is not None

            # Kiểm tra payload được gửi vào table insert
            inserted_row = mock_client.table.return_value.insert.call_args[0][0]
            assert inserted_row["facts"]["market_price"] == 28.5
            assert inserted_row["facts"]["snapshot_price"] == 28.5
            assert inserted_row["facts"]["price"] == 28.5
            assert inserted_row["opinions"]["prompt_hash"] == "hash123"
            assert inserted_row["opinions"]["input_hash"] == "hash456"
            assert inserted_row["counterfactual"]["thesis_breaker"] == "Thủng MA50"
