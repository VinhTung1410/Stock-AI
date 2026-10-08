"""Policy Constants and Thresholds (Phase 26 - TASK-0077 / TASK-0078).

Single Source of Truth for all quantitative trading rules, thresholds,
action vocabularies, and capital allocation policies.
"""

from typing import Final

# ==============================================================================
# 1. CANONICAL ACTION VOCABULARY (Chuỗi Hành Động Chuẩn Hóa)
# ==============================================================================
ACTION_BUY: Final[str] = "🟢 MUA"
ACTION_ACCUMULATE: Final[str] = "🟢 TÍCH LŨY"
ACTION_WATCH: Final[str] = "🟡 THEO DÕI"
ACTION_HOLD: Final[str] = "🟡 NẮM GIỮ"
ACTION_REDUCE: Final[str] = "🟠 HẠ TỶ TRỌNG"
ACTION_STOP_LOSS: Final[str] = "🔴 CẮT LỖ KỸ THUẬT"
ACTION_EXIT_THESIS: Final[str] = "🔴 THOÁT VỊ THẾ (THESIS BREAKER)"
ACTION_EXIT_OVERVALUED: Final[str] = "🔴 CHỐT LỜI / THOÁT VỊ THẾ (ĐỊNH GIÁ ĐẮT ĐỎ)"
ACTION_PARTIAL_PROFIT: Final[str] = "🟢 BẢO VỆ THÀNH QUẢ / CHỐT LỜI TỪNG PHẦN"

# Action sets & keywords for cooldown and signal routing
BUY_ACTIONS: Final[set[str]] = {
    "🟢 MUA",
    "🟢 TÍCH LŨY",
    "🟢 ACCUMULATE",
    "🟢 VALUE BUY",
    "RECOMMEND_BUY",
    "MUA",
    "BUY",
}
BUY_KEYWORDS: Final[tuple[str, ...]] = ("MUA", "TÍCH LŨY", "ACCUMULATE", "BUY")

# ==============================================================================
# 2. VALUATION & MARGIN OF SAFETY THRESHOLDS (Biên An Toàn & Định Giá)
# ==============================================================================
DEFAULT_MIN_MOS_PCT: Final[float] = 15.0
OVERVALUED_MOS_THRESHOLD: Final[float] = 0.0

ARCHETYPE_MOS_THRESHOLDS: Final[dict[str, float]] = {
    "BANK": 10.0,
    "GROWTH_COMPOUNDER": 15.0,
    "GROWTH": 15.0,
    "CYCLICAL": 15.0,
    "REAL_ESTATE": 15.0,
    "DEFAULT": 15.0,
}

# ==============================================================================
# 3. TECHNICAL & RISK THRESHOLDS (Ngưỡng Kỹ Thuật & Cắt Lỗ / Chốt Lời)
# ==============================================================================
STRUCTURAL_STOP_LOSS_PCT: Final[float] = 7.0  # 7% Stop loss cấu trúc mặc định
HARD_STOP_LOSS_PCT: Final[float] = 8.0  # 8% Cắt lỗ kỹ thuật dứt khoát
WARNING_LOSS_PCT: Final[float] = 5.0  # 5% Cảnh báo lỗ vừa / Quản trị rủi ro
PARTIAL_TAKE_PROFIT_PCT: Final[float] = 20.0  # 20% Chốt lời từng phần bảo vệ thành quả
PROFIT_TRAIL_THRESHOLD_PCT: Final[float] = 8.0  # 8% Bắt đầu kích hoạt trailing stop
BREAKEVEN_LOCK_TARGET_PCT: Final[float] = 12.0  # 12% Chốt 50% dời stop lên breakeven
ATR_STOP_MULTIPLIER: Final[float] = 2.0  # 2.0x ATR buffer cho trailing stop

RSI_MAX_ENTRY: Final[float] = 70.0
RSI_OVERSOLD: Final[float] = 30.0

# ==============================================================================
# 4. SIZING & CAPITAL ALLOCATION POLICY (Quản Trị Vốn & Định Cỡ Vị Thế)
# ==============================================================================
FIXED_RISK_NAV_PCT: Final[float] = 0.01  # Mức rủi ro cố định mặc định 1.0% NAV
MAX_FIXED_RISK_NAV_PCT: Final[float] = 0.015  # Trần rủi ro cố định tối đa 1.5% NAV
MAX_POSITION_SIZE_NAV_PCT: Final[float] = 0.15  # Trần tỷ trọng tối đa 1 mã (15% NAV)
MAX_SECTOR_EXPOSURE_PCT: Final[float] = 0.25  # Trần tỷ trọng ngành (25% NAV)
MAX_POSITIONS_PER_SECTOR: Final[int] = 3  # Tối đa 3 mã trong 1 ngành

# Kelly Calibration Gate
MIN_TRADES_FOR_KELLY_CALIBRATION: Final[int] = 100  # Cần > 100 lệnh để mở Fractional Kelly

# Drawdown & Liquidity Gates
DRAWDOWN_BREAKER_PCT: Final[float] = 10.0  # 10% Drawdown Breaker -> Cash Mode
DRAWDOWN_HALF_SIZE_PCT: Final[float] = 5.0  # 5% Drawdown -> Giảm 50% size
MIN_ADV20_BILLION: Final[float] = 2.0  # Tối thiểu 2.0 tỷ VND ADV20
MAX_ADV20_ABSORPTION_PCT: Final[float] = 0.10  # Tối đa 10% ADV20

# ==============================================================================
# 5. CONVICTION & QUALITY GATES (Ngưỡng Điểm Conviction & Sức Khỏe Tài Chính)
# ==============================================================================
BUY_CONVICTION_MIN: Final[float] = 70.0
WATCH_CONVICTION_MIN: Final[float] = 55.0
F_SCORE_MIN: Final[int] = 6
Z_SCORE_MIN: Final[float] = 1.80
