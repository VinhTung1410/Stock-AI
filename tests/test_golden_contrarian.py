"""
Golden Tests using offline recorded fixtures (TASK-0072 / Phase 25).
Zero Live API Calls. Fully reproducible offline regression testing.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

import pytest

from contrarian_engine import (
    GATE_SURVIVAL,
    STATE_BLOCKED,
    STATE_PANIC_BUY,
    evaluate_contrarian_gates,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def fpt_real() -> Dict[str, Any]:
    with open(FIXTURES_DIR / "fpt_q4_2024.json", "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def vnm_real() -> Dict[str, Any]:
    with open(FIXTURES_DIR / "vnm_q4_2024.json", "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def hpg_cfo_negative() -> Dict[str, Any]:
    with open(FIXTURES_DIR / "hpg_cfo_neg.json", "r", encoding="utf-8") as f:
        return json.load(f)


def test_fpt_real_passes_survival_gate(fpt_real: Dict[str, Any]):
    """FPT với BCTC thật Q4/2024 phải pass Survival Gate (tier >= 2)."""
    res = evaluate_contrarian_gates(
        symbol=fpt_real["symbol"],
        current_price=fpt_real["price"],
        tech_data=fpt_real["tech"],
        fin_dict=fpt_real["fin"],
        sector=fpt_real["sector"],
    )
    # FPT phải vượt qua GATE_SURVIVAL và không bị chặn bởi rủi ro cơ bản
    assert res.blocked_by != GATE_SURVIVAL, f"FPT bị block tại {res.blocked_by}: {res.blocking_reasons}"
    assert res.metrics.get("f_score", 0) >= 7
    # Vì tech đủ điều kiện đảo chiều và is_backtest=True -> đạt STATE_PANIC_BUY
    assert res.status == STATE_PANIC_BUY
    assert res.can_buy is True


def test_vnm_real_passes_survival_gate(vnm_real: Dict[str, Any]):
    """VNM với BCTC thật Q4/2024 phải pass Survival Gate (tier >= 2)."""
    res = evaluate_contrarian_gates(
        symbol=vnm_real["symbol"],
        current_price=vnm_real["price"],
        tech_data=vnm_real["tech"],
        fin_dict=vnm_real["fin"],
        sector=vnm_real["sector"],
    )
    assert res.blocked_by != GATE_SURVIVAL, f"VNM bị block tại {res.blocked_by}: {res.blocking_reasons}"
    assert res.metrics.get("f_score", 0) >= 7
    assert res.status in ("NEAR_PANIC_WATCH", "EXTREME_FEAR_WATCH", "PANIC_BUY")


def test_cfo_negative_must_block_at_survival(hpg_cfo_negative: Dict[str, Any]):
    """Mã chu kỳ dính CFO âm (hoặc P/CF âm) bắt buộc phải bị block tại SURVIVAL_QUALITY."""
    res = evaluate_contrarian_gates(
        symbol=hpg_cfo_negative["symbol"],
        current_price=hpg_cfo_negative["price"],
        tech_data=hpg_cfo_negative["tech"],
        fin_dict=hpg_cfo_negative["fin"],
        sector=hpg_cfo_negative["sector"],
    )
    assert res.can_buy is False
    assert res.status == STATE_BLOCKED
    assert res.blocked_by == GATE_SURVIVAL
    assert any("Dòng tiền cạn kiệt" in r or "CFO âm" in r for r in res.blocking_reasons)


# =============================================================================
# TASK-0074: SHADOW MODE TESTS
# =============================================================================
def test_shadow_mode_prevents_live_recommendation(fpt_real: Dict[str, Any]):
    """Khi shadow_mode=True và không phải backtest, không được phát can_buy=True."""
    live_tech = dict(fpt_real["tech"])
    live_tech["is_backtest"] = False  # Giả lập môi trường live quét phiên thực tế
    live_tech["is_late_session"] = True  # Giả lập phiên chiều sau 14:15 để test an toàn không phụ thuộc giờ chạy test

    res = evaluate_contrarian_gates(
        symbol=fpt_real["symbol"],
        current_price=fpt_real["price"],
        tech_data=live_tech,
        fin_dict=fpt_real["fin"],
        sector=fpt_real["sector"],
        shadow_mode=True,
    )
    assert res.status == STATE_PANIC_BUY
    assert res.can_buy is False  # Bị chặn mua thật
    assert "SHADOW BUY" in res.action_state
    assert res.metrics.get("shadow_mode") is True


def test_evaluate_shadow_graduation_rejection():
    """Kiểm tra điều kiện không cho tốt nghiệp khi thiếu mẫu hoặc hit rate thấp."""
    from unittest.mock import patch

    from scripts.evaluate_shadow_graduation import evaluate_shadow_graduation

    # Case 1: Không có bản ghi nào
    with patch("scripts.evaluate_shadow_graduation.get_decision_records", return_value=[]):
        res = evaluate_shadow_graduation()
        assert res["can_graduate"] is False

    # Case 2: Đủ 60 phiên nhưng chỉ có 10 mẫu T+10
    mock_records = [
        {"session": f"S_{i}", "decision": "SHADOW_BUY", "t10_return_pct": 5.0 if i < 10 else None}
        for i in range(65)
    ]
    with patch("scripts.evaluate_shadow_graduation.get_decision_records", return_value=mock_records):
        res = evaluate_shadow_graduation()
        assert res["can_graduate"] is False
        assert res["t10_sample_count"] == 10

    # Case 3: Đủ 35 mẫu nhưng hit rate chỉ đạt 40% (< 55%)
    mock_records_fail = [
        {"session": f"S_{i}", "decision": "SHADOW_BUY", "t10_return_pct": 4.0 if i < 14 else -2.0}
        for i in range(65)
    ]
    with patch("scripts.evaluate_shadow_graduation.get_decision_records", return_value=mock_records_fail):
        res = evaluate_shadow_graduation()
        assert res["can_graduate"] is False
        assert res["hit_rate_t10"] < 0.55


def test_evaluate_shadow_graduation_success():
    """Kiểm tra điều kiện tốt nghiệp thành công khi đủ 60 phiên, 35 mẫu, hit rate > 55%."""
    from unittest.mock import patch

    from scripts.evaluate_shadow_graduation import evaluate_shadow_graduation

    # 35 mẫu T+10 trong 65 phiên, 25 thắng (71.4% > 55%)
    mock_records_pass = [
        {"session": f"S_{i}", "decision": "SHADOW_BUY", "t10_return_pct": 6.5 if i < 25 else (-2.0 if i < 35 else None)}
        for i in range(65)
    ]
    with patch("scripts.evaluate_shadow_graduation.get_decision_records", return_value=mock_records_pass):
        res = evaluate_shadow_graduation()
        assert res["can_graduate"] is True
        assert res["hit_rate_t10"] > 0.55
        assert res["t10_sample_count"] == 35

