"""context_engine.py

Context Engine for Stock-AI (v6.3 / Phase 8).
Loads and packages daily market context extracted from institutional analyst reports (e.g. TCBS),
provides prompt injection formatting for LLM analysis, arbitrates regime conflicts against
the quantitative MA200 code regime, and enforces graceful non-blocking fail-safes.
"""

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

LOGGER = logging.getLogger(__name__)

DEFAULT_CONTEXT_PATH = Path("data/market_context.json")

# String constants to comply with SonarCloud S1192
UNKNOWN_VAL = "UNKNOWN"
TCBS_SOURCE = "TCBS"
REGIME_UPTREND = "UPTREND"
REGIME_DOWNTREND = "DOWNTREND"
REGIME_SIDEWAYS = "SIDEWAYS"
REGIME_ACCUMULATION = "ACCUMULATION"
STATUS_BEARISH = "BEARISH"
STATUS_BULLISH = "BULLISH"


@dataclass
class MarketContext:
    """Represents daily contextual market intelligence from institutional reports."""

    date: str = ""
    source: str = TCBS_SOURCE
    source_file: str = ""
    extracted_at: str = ""
    market_regime_analyst: str = UNKNOWN_VAL
    sentiment: str = UNKNOWN_VAL
    vnindex_close: Optional[float] = None
    vnindex_change_pts: Optional[float] = None
    vnindex_change_pct: Optional[float] = None
    vnindex_support_zones: List[float] = field(default_factory=list)
    vnindex_resistance_zones: List[float] = field(default_factory=list)
    focus_sectors: List[str] = field(default_factory=list)
    risk_keywords: List[str] = field(default_factory=list)
    buy_signals: List[str] = field(default_factory=list)
    sell_signals: List[str] = field(default_factory=list)
    raw_summary: str = ""
    is_valid: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert context to standard dictionary."""
        return asdict(self)


def load_market_context(
    filepath: Optional[Path | str] = None, current_date: Optional[str] = None, allow_stale: bool = False
) -> MarketContext:
    """
    Safely load MarketContext from disk.

    Fail-safe behavior:
    - Missing file -> returns MarketContext(is_valid=False)
    - Corrupt JSON -> returns MarketContext(is_valid=False)
    - Date mismatch (when current_date provided and not allow_stale) -> returns MarketContext(is_valid=False)
    """
    target_path = Path(filepath) if filepath else DEFAULT_CONTEXT_PATH

    if not target_path.exists():
        LOGGER.warning("[ContextEngine] Context file does not exist: %s. Using default empty context.", target_path)
        return MarketContext(is_valid=False)

    try:
        with open(target_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        LOGGER.exception("[ContextEngine] Failed to read/parse context JSON at %s", target_path)
        return MarketContext(is_valid=False)

    report_date = data.get("date", "")
    if not allow_stale:
        effective_date = current_date or str(date.today())
        if report_date != effective_date:
            LOGGER.warning(
                "[ContextEngine] Context date '%s' does not match session date '%s'. Falling back to invalid context.",
                report_date,
                effective_date,
            )
            return MarketContext(is_valid=False, date=report_date)

    return MarketContext(
        date=report_date,
        source=data.get("source", TCBS_SOURCE),
        source_file=data.get("source_file", ""),
        extracted_at=data.get("extracted_at", ""),
        market_regime_analyst=data.get("market_regime_analyst", UNKNOWN_VAL),
        sentiment=data.get("sentiment", UNKNOWN_VAL),
        vnindex_close=data.get("vnindex_close"),
        vnindex_change_pts=data.get("vnindex_change_pts"),
        vnindex_change_pct=data.get("vnindex_change_pct"),
        vnindex_support_zones=data.get("vnindex_support_zones", []),
        vnindex_resistance_zones=data.get("vnindex_resistance_zones", []),
        focus_sectors=data.get("focus_sectors", []),
        risk_keywords=data.get("risk_keywords", []),
        buy_signals=data.get("buy_signals", []),
        sell_signals=data.get("sell_signals", []),
        raw_summary=data.get("raw_summary", ""),
        is_valid=True,
    )


def _normalize_regime_str(regime_str: Any) -> str:
    """Helper to uppercase and strip regime string or extract value from Enum."""
    if hasattr(regime_str, "value"):
        return str(regime_str.value).strip().upper()
    return str(regime_str or "").strip().upper()


def _handle_uptrend_conflict() -> Tuple[bool, str]:
    from datetime import datetime

    today_str = datetime.now().strftime("%Y-%m-%d")
    should_penalize = track_regime_hysteresis(True, today_str)

    if should_penalize:
        return True, (
            "XUNG ĐỘT REGIME: Code MA200 báo UPTREND nhưng Chuyên gia TCBS cảnh báo Giảm/Điều chỉnh. "
            "Hệ thống tự động kích hoạt cờ giảm 50% quy mô vị thế đề xuất để phòng thủ (Xung đột kéo dài >= 2 phiên)."
        )
    return True, (
        "XUNG ĐỘT REGIME: Code MA200 báo UPTREND nhưng Chuyên gia TCBS cảnh báo Giảm/Điều chỉnh. "
        "Đây là phiên đầu tiên cảnh báo, chưa kích hoạt phạt 50% quy mô vị thế (chờ xác nhận phiên tiếp theo)."
    )


def check_regime_conflict(code_regime: str, analyst_regime: str) -> Tuple[bool, str]:
    """Arbitrates conflict between quantitative code regime (FACT) and analyst report (INFERENCE)."""
    c_norm = _normalize_regime_str(code_regime)
    a_norm = _normalize_regime_str(analyst_regime)

    if not a_norm or a_norm == UNKNOWN_VAL:
        return False, "Không có nhận định xu hướng chuyên gia để đối chiếu."

    is_code_up = REGIME_UPTREND in c_norm or "TĂNG" in c_norm
    is_code_down = REGIME_DOWNTREND in c_norm or "GIẢM" in c_norm
    is_analyst_up = REGIME_UPTREND in a_norm or STATUS_BULLISH in a_norm
    is_analyst_down = REGIME_DOWNTREND in a_norm or STATUS_BEARISH in a_norm or "ĐIỀU CHỈNH" in a_norm

    if is_code_up and is_analyst_down:
        return _handle_uptrend_conflict()

    if is_code_down and is_analyst_up:
        return True, (
            "XUNG ĐỘT REGIME: Code MA200 báo DOWNTREND nhưng Chuyên gia TCBS nhận định Tăng. "
            "Quy tắc Zero-Democracy: Code toán học thắng tuyệt đối, giữ nguyên 100% Cash Mode, cấm mở mua."
        )

    from datetime import datetime

    today_str = datetime.now().strftime("%Y-%m-%d")
    track_regime_hysteresis(False, today_str)

    if REGIME_SIDEWAYS in c_norm and (REGIME_ACCUMULATION in a_norm or REGIME_SIDEWAYS in a_norm):
        return False, "ĐỒNG THUẬN REGIME: Thị trường đi ngang / tích lũy theo nhận định cả hai nguồn."

    if (is_code_up and is_analyst_up) or (is_code_down and is_analyst_down):
        return False, "ĐỒNG THUẬN REGIME: Xu hướng định lượng và nhận định chuyên gia thống nhất."

    return False, "Trạng thái thị trường không phát hiện xung đột trực diện."


def track_regime_hysteresis(is_conflict: bool, today_str: str) -> bool:
    """
    Theo dõi cờ xung đột Regime (Hysteresis).
    Chỉ kích hoạt hình phạt (giảm 50% vị thế) nếu xung đột duy trì liên tiếp >= 2 phiên.
    """
    import json
    import os

    file_path = "data/regime_hysteresis.json"
    history = {"consecutive_days": 0, "last_date": "", "last_conflict_date": ""}

    if os.path.exists(file_path):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                history = json.load(f)
        except Exception:
            pass

    if history.get("last_date") == today_str:
        return history.get("consecutive_days", 0) >= 2

    if is_conflict:
        history["consecutive_days"] = history.get("consecutive_days", 0) + 1
        history["last_conflict_date"] = today_str
    else:
        history["consecutive_days"] = 0

    history["last_date"] = today_str

    try:
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=2)
    except Exception:
        pass

    return history.get("consecutive_days", 0) >= 2


def build_context_prompt_snippet(context: MarketContext, code_regime: Optional[str] = None) -> str:
    """
    Đóng gói thông tin bối cảnh thị trường thành đoạn markdown súc tích
    để nhúng vào System Prompt / Context Section cho LLM.
    """
    if not context or not context.is_valid:
        return ""

    sup_str = (
        ", ".join(str(s) for s in context.vnindex_support_zones) if context.vnindex_support_zones else "Chưa xác định"
    )
    res_str = (
        ", ".join(str(r) for r in context.vnindex_resistance_zones)
        if context.vnindex_resistance_zones
        else "Chưa xác định"
    )
    sectors_str = ", ".join(context.focus_sectors) if context.focus_sectors else "Đa ngành"
    risks_str = ", ".join(context.risk_keywords) if context.risk_keywords else "Không có từ khóa rủi ro đột biến"
    buy_str = ", ".join(context.buy_signals) if context.buy_signals else "Không có"
    sell_str = ", ".join(context.sell_signals) if context.sell_signals else "Không có"

    vnindex_info = ""
    if context.vnindex_close is not None:
        pts = context.vnindex_change_pts or 0.0
        pct = context.vnindex_change_pct or 0.0
        vnindex_info = f"- VN-Index phiên báo cáo: {context.vnindex_close:.1f} điểm ({pts:+.1f} pts, {pct:+.2f}%)\n"

    conflict_info = ""
    if code_regime:
        has_conflict, rationale = check_regime_conflict(code_regime, context.market_regime_analyst)
        if has_conflict:
            conflict_info = f"- ⚠️ CẢNH BÁO XUNG ĐỘT XU HƯỚNG: {rationale}\n"

    snippet = (
        "\n### 📰 NGỮ CẢNH THỊ TRƯỜNG TỪ BÁO CÁO CHUYÊN GIA CTCK (TCBS)\n"
        f"- Nguồn: {context.source} | Ngày: {context.date} | File: {context.source_file}\n"
        f"{vnindex_info}"
        f"- Xu hướng chuyên gia nhận định: {context.market_regime_analyst} (Tâm lý: {context.sentiment})\n"
        f"{conflict_info}"
        f"- Vùng hỗ trợ kỹ thuật: {sup_str} | Vùng kháng cự: {res_str}\n"
        f"- Nhóm ngành tâm điểm: {sectors_str}\n"
        f"- Cảnh báo rủi ro / Từ khóa: {risks_str}\n"
        f"- Tín hiệu cổ phiếu CTCK: Mua [{buy_str}] | Bán [{sell_str}]\n"
        f"- Tóm tắt diễn biến CTCK: {context.raw_summary}\n"
        "> *LƯU Ý QUẢN TRỊ:* Đây là thông tin INFERENCE tham khảo từ chuyên gia bên ngoài. "
        "Tuyệt đối không thay thế, làm mềm hoặc ghi đè các chốt chặn toán học của Quant Gate.\n"
    )
    return snippet
