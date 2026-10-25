"""
Fair Value & Margin of Safety Engine — archetype-specific valuation models
for the Vietnam stock market.

Supports 4 valuation archetypes:
1. Bank: Justified P/B based on ROE and Cost of Equity
2. Growth / Retail / Tech: Historical Median P/E & Forward EPS
3. Cyclical: Normalized Mid-Cycle Earnings (avoids peak-P/E traps)
4. Real Estate: Historical floor P/B with leverage discount

Integrates institutional consensus targets (SSI, HSC, Vietcap) with
15-20% safety discount as valuation ceiling anchors.
"""

import logging
from datetime import date, datetime
from typing import Any, Dict, List, Optional

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Valuation Rating Constants (SonarCloud S1192)
VAL_RATING_VERY_CHEAP = "🟢 VÙNG ĐỊNH GIÁ RẤT RẺ (MOS > 20%)"
VAL_RATING_ATTRACTIVE = "🟢 HẤP DẪN / CÓ BIÊN AN TOÀN (MOS 12-20%)"
VAL_RATING_FAIR_WATCH = "🟡 HỢP LÝ / THEO DÕI (MOS 5-12%)"
VAL_RATING_FAIR_VALUE = "🟡 ĐỊNH GIÁ ĐỦ (MOS quanh 0%)"
VAL_RATING_EXPENSIVE = "🔴 ĐỊNH GIÁ QUÁ ĐẮT (MOS Âm > 8%)"
VAL_RATING_MANUAL_VERIFY = "CẦN XÁC MINH THỦ CÔNG"
VAL_RATING_UNKNOWN = "⚪ CHƯA RÕ / THIẾU DỮ LIỆU"

# Mỏ neo định giá trung vị tham chiếu từ các tổ chức phân tích uy tín (SSI Research, HSC, Vietcap)
# Được cập nhật định kỳ (kèm last_updated), đóng vai trò "Trần định giá tham chiếu" (Consensus Ceiling)
INSTITUTIONAL_CONSENSUS_TARGETS = {
    "FPT": {
        "consensus_target": 88.0,
        "source": "SSI/Vietcap/HSC Consensus (Q2 Review)",
        "quality_tier": "TIER_1_COMPOUNDER",
        "last_updated": "2026-08-20",
    },
    "HPG": {
        "consensus_target": 26.5,
        "source": "HSC/SSI Research",
        "quality_tier": "TIER_1_CYCLICAL",
        "last_updated": "2026-10-01",
    },
    "MWG": {
        "consensus_target": 83.5,
        "source": "VCBS/SSI Research",
        "quality_tier": "TIER_1_RETAIL",
        "last_updated": "2026-09-30",
    },
    "SSI": {
        "consensus_target": 24.5,
        "source": "MBS/HSC Research",
        "quality_tier": "TIER_1_BROKER",
        "last_updated": "2026-10-01",
    },
    "MSB": {
        "consensus_target": 14.5,
        "source": "SSI Research/VCSC",
        "quality_tier": "TIER_2_BANK",
        "last_updated": "2026-10-01",
    },
    "BSR": {
        "consensus_target": 32.0,
        "source": "KBSV/SSI Research",
        "quality_tier": "TIER_2_ENERGY",
        "last_updated": "2026-10-01",
    },
    "TCB": {
        "consensus_target": 28.0,
        "source": "Vietcap/HSC Research",
        "quality_tier": "TIER_1_BANK",
        "last_updated": "2026-10-01",
    },
    "MBB": {
        "consensus_target": 27.0,
        "source": "SSI/HSC Research",
        "quality_tier": "TIER_1_BANK",
        "last_updated": "2026-10-01",
    },
    "ACB": {
        "consensus_target": 28.5,
        "source": "SSI/Vietcap",
        "quality_tier": "TIER_1_BANK",
        "last_updated": "2026-10-01",
    },
    "VCB": {
        "consensus_target": 98.0,
        "source": "SSI/HSC Research",
        "quality_tier": "TIER_1_BANK",
        "last_updated": "2026-10-01",
    },
    "VHM": {
        "consensus_target": 48.0,
        "source": "Vietcap/SSI Research",
        "quality_tier": "TIER_1_REALTY",
        "last_updated": "2026-10-01",
    },
    "VNM": {
        "consensus_target": 75.0,
        "source": "HSC/SSI Research",
        "quality_tier": "TIER_1_CONSUMER",
        "last_updated": "2026-10-01",
    },
    "DGC": {
        "consensus_target": 115.0,
        "source": "Vietcap/HSC Research",
        "quality_tier": "TIER_1_CHEMICAL",
        "last_updated": "2026-10-01",
    },
    "PNJ": {
        "consensus_target": 105.0,
        "source": "SSI/Vietcap Research",
        "quality_tier": "TIER_1_RETAIL",
        "last_updated": "2026-10-01",
    },
    "REE": {
        "consensus_target": 72.0,
        "source": "SSI Research",
        "quality_tier": "TIER_1_UTILITY",
        "last_updated": "2026-10-01",
    },
}


def check_institutional_target_freshness(
    symbol: str,
    as_of_date: str | None = None,
    max_age_days: int = 90,
) -> dict[str, Any]:
    """Kiểm tra độ tươi của mỏ neo định giá đồng thuận từ các CTCK (Phase 13 / TASK-0038).

    Nếu dữ liệu cũ quá max_age_days (mặc định 90 ngày ~ 1 quý), cảnh báo rủi ro dữ liệu đóng băng (stale data).
    """
    sym = symbol.strip().upper() if symbol else ""
    cons_data = INSTITUTIONAL_CONSENSUS_TARGETS.get(sym)
    if not cons_data:
        return {
            "symbol": sym,
            "has_target": False,
            "is_stale": False,
            "age_days": 0,
            "last_updated": None,
            "warning": "NO_INSTITUTIONAL_TARGET",
        }

    last_updated_str = cons_data.get("last_updated", "")
    if not last_updated_str:
        return {
            "symbol": sym,
            "has_target": True,
            "is_stale": True,
            "age_days": 999,
            "last_updated": None,
            "warning": "MISSING_TIMESTAMP",
        }

    try:
        updated_dt = datetime.strptime(last_updated_str, "%Y-%m-%d").date()
        ref_dt = datetime.strptime(as_of_date, "%Y-%m-%d").date() if as_of_date else date.today()
        age = (ref_dt - updated_dt).days
    except Exception:
        return {
            "symbol": sym,
            "has_target": True,
            "is_stale": True,
            "age_days": 999,
            "last_updated": last_updated_str,
            "warning": "INVALID_DATE_FORMAT",
        }

    is_stale = age > max_age_days
    warning_msg = f"Target outdated by {age} days (> {max_age_days}d)" if is_stale else "FRESH"
    if is_stale:
        logging.warning("Mỏ neo định giá đồng thuận của %s đã quá hạn (%d ngày)", sym, age)

    return {
        "symbol": sym,
        "has_target": True,
        "is_stale": is_stale,
        "age_days": age,
        "last_updated": last_updated_str,
        "consensus_target": cons_data.get("consensus_target", 0.0),
        "warning": warning_msg,
    }


def classify_stock_archetype(symbol: str, sector: str = "") -> str:
    """Classify a stock into one of 4 valuation archetypes or UNCLASSIFIED.

    Archetypes determine which valuation model is applied:
    - BANK: Banks & financials → Justified P/B
    - CYCLICAL: Steel, oil, chemicals → Normalized mid-cycle earnings
    - REAL_ESTATE: Property developers → Floor P/B + leverage discount
    - GROWTH_COMPOUNDER: Tech, retail, consumer → Historical median P/E
    - UNCLASSIFIED: Securities, insurance, utilities, gas without models

    Args:
        symbol: Stock ticker (e.g. 'FPT', 'VCB').
        sector: Vietnamese sector name for fallback classification.

    Returns:
        One of: 'BANK', 'CYCLICAL', 'REAL_ESTATE', 'GROWTH_COMPOUNDER', 'UNCLASSIFIED'.
    """
    if not symbol or not isinstance(symbol, str):
        sym = ""
    else:
        sym = symbol.strip().upper()
    sec = sector.lower() if isinstance(sector, str) else ""

    # 1. Ngân hàng
    if (
        any(b in sym for b in ["VCB", "TCB", "MBB", "ACB", "VPB", "MSB", "STB", "HDB", "CTG", "BID", "VIB", "TPB", "SHB", "SSB"])
        or "ngân hàng" in sec
    ):
        return "BANK"

    # 2. Chứng khoán, Bảo hiểm, Khí/Điện/Hạ tầng, Khu công nghiệp chưa có mô hình chuyên biệt
    if any(s in sym for s in ["SSI", "VND", "VIX", "HCM", "SHS", "MBS", "CTS", "FTS", "BSI"]) or any(
        k in sec for k in ["chứng khoán", "bảo hiểm", "bảo trợ"]
    ) or sym in ["BVH", "BMI", "PVI", "GAS", "PLX", "POW", "BCM"]:
        return "UNCLASSIFIED"

    # 3. Chu kỳ hàng hóa
    if any(s in sec for s in ["thép", "dầu khí", "hóa chất", "phân bón", "vận tải biển", "cao su"]) or sym in [
        "HPG",
        "HSG",
        "NKG",
        "BSR",
        "PVD",
        "PVS",
        "DGC",
        "DCM",
        "DPM",
        "GVR",
    ]:
        return "CYCLICAL"

    # 4. Bất động sản
    if any(s in sec for s in ["bất động sản", "địa ốc"]) or sym in [
        "VHM",
        "VIC",
        "VRE",
        "KDH",
        "NLG",
        "DXG",
        "DIG",
        "PDR",
        "KBC",
        "IDC",
    ]:
        return "REAL_ESTATE"

    # 5. Tăng trưởng dài hạn (Compounder) - chỉ gán khi rõ ràng
    if sym in COMPOUNDER_FUNDAMENTAL_BENCHMARKS or any(
        k in sec for k in ["công nghệ", "bán lẻ", "tiêu dùng", "fmcg", "dược"]
    ) or sym in ["FPT", "MWG", "PNJ", "VNM", "REE", "FRT", "DGW"]:
        return "GROWTH_COMPOUNDER"

    return "UNCLASSIFIED"


def get_stock_archetype_details(symbol: str, sector: str = "") -> dict:
    """Trả về chi tiết phân loại Archetype, Nhóm ngành và Chiến lược đầu tư phù hợp.

    Phân tách rạch ròi:
    - GROWTH_COMPOUNDER: Doanh nghiệp tăng trưởng dài hạn (FPT, MWG...) -> Chiến lược VALUE / Tích sản.
    - CYCLICAL: Doanh nghiệp chu kỳ hàng hóa (HPG, BSR, DGC...) -> Chiến lược CYCLICAL.
    - BANK: Ngân hàng & Định chế tài chính (VCB, TCB...) -> Chiến lược FINANCIAL.
    - REAL_ESTATE: Doanh nghiệp bất động sản (VHM, KDH...) -> Chiến lược PROPERTY.
    - UNCLASSIFIED: Chưa có mô hình định giá chuyên biệt -> Chiến lược THEO DÕI.
    """
    archetype = classify_stock_archetype(symbol, sector)
    details_map = {
        "GROWTH_COMPOUNDER": {
            "archetype": "GROWTH_COMPOUNDER",
            "sector_group": "💻 Công nghệ & Tiêu dùng Tăng trưởng",
            "default_strategy": "VALUE",
            "strategy_label": "TÍCH SẢN DÀI HẠN",
            "valuation_model": "Historical Median P/E",
            "holding_shield": True,
        },
        "CYCLICAL": {
            "archetype": "CYCLICAL",
            "sector_group": "🏭 Hàng hóa & Sản xuất Chu kỳ",
            "default_strategy": "CYCLICAL",
            "strategy_label": "GIAO DỊCH THEO CHU KỲ",
            "valuation_model": "Normalized Mid-Cycle P/E & P/B chu kỳ",
            "holding_shield": False,
        },
        "BANK": {
            "archetype": "BANK",
            "sector_group": "🏦 Ngân hàng & Tài chính",
            "default_strategy": "FINANCIAL",
            "strategy_label": "TÀI CHÍNH / P/B BANDS",
            "valuation_model": "Justified P/B (ROE vs Cost of Equity)",
            "holding_shield": False,
        },
        "REAL_ESTATE": {
            "archetype": "REAL_ESTATE",
            "sector_group": "🏢 Bất động sản Dân cư & KCN",
            "default_strategy": "PROPERTY",
            "strategy_label": "BẤT ĐỘNG SẢN / ĐỊA ỐC",
            "valuation_model": "SOTP / RNAV & P/B Chuẩn hóa BCTC",
            "holding_shield": False,
        },
        "UNCLASSIFIED": {
            "archetype": "UNCLASSIFIED",
            "sector_group": "Chưa phân loại / Chờ mô hình",
            "default_strategy": "DEFENSIVE",
            "strategy_label": "THEO DÕI",
            "valuation_model": "None (Chưa có mô hình)",
            "holding_shield": False,
        },
    }
    return details_map.get(archetype, details_map["UNCLASSIFIED"])


# =============================================================================
# PHASE 10: REAL ESTATE & HOLDING COMPANY VALUATION ENGINE (TASK-0024 -> 0028)
# =============================================================================


def check_sotp_holding_sanity(
    symbol: str,
    parent_market_cap: float | None = None,
    subsidiary_prices: Optional[Dict[str, float]] = None,
) -> Dict[str, Any]:
    """Kiểm tra chéo cấu trúc vốn hóa SOTP cho Holding Company / BĐS Đa ngành (TASK-0024).

    Công thức:
    SOTP Ratio = Sum(Vốn hóa CTC niêm yết * % sở hữu) / Vốn hóa Công ty mẹ
    - < 50% -> Cắm cờ SOTP_ANOMALY, hạ confidence = LOW
    - < 30% -> Cắm cờ SOTP_DISCOUNT_CRITICAL, khóa khuyến nghị MUA
    - Implied Value phần chưa niêm yết = Vốn hóa mẹ - Sum(vốn hóa CTC niêm yết * % sở hữu)
    - Nếu Implied Value chiếm > 50% vốn hóa mẹ: Cắm cờ SPECULATIVE_PREMIUM
    """
    from data_engine import get_holding_subsidiary_structure

    sym = (symbol or "").strip().upper()
    struct = get_holding_subsidiary_structure(sym)
    if not struct.get("is_holding", False):
        return {
            "symbol": sym,
            "is_holding": False,
            "sotp_ratio": None,
            "has_critical_block": False,
            "flags": [],
            "warnings": [],
            "fv_discount": 0.0,
            "implied_unlisted_value_bil": 0.0,
        }

    sub_list = struct.get("listed_subsidiaries", [])
    default_prices = {
        "VHM": 42.0,
        "VRE": 19.0,
        "MCH": 120.0,
        "MSR": 15.0,
        "VSH": 45.0,
        "CHP": 22.0,
        "VGC": 40.0,
        "GEE": 35.0,
    }
    sub_prices = dict(default_prices)
    if subsidiary_prices:
        sub_prices.update(subsidiary_prices)

    total_listed_holding_val = 0.0
    for sub in sub_list:
        sub_sym = sub.get("symbol", "")
        shares_bil = float(sub.get("shares_bil", 1.0))
        own_pct = float(sub.get("ownership", 0.5))
        p = float(sub_prices.get(sub_sym, 30.0))
        sub_mcap_bil = shares_bil * p * 1000.0
        total_listed_holding_val += sub_mcap_bil * own_pct

    mcap_parent = float(parent_market_cap) if (parent_market_cap and parent_market_cap > 0) else 170000.0
    sotp_ratio = total_listed_holding_val / mcap_parent if mcap_parent > 0 else 0.0
    implied_unlisted_val = max(mcap_parent - total_listed_holding_val, 0.0)

    flags: List[str] = []
    warnings: List[str] = []
    has_critical_block = False
    fv_discount = 0.0

    if sotp_ratio < 0.30:
        has_critical_block = True
        flags.append("SOTP_DISCOUNT_CRITICAL")
        warnings.append(
            f"Vốn hóa mảng niêm yết chỉ chiếm {sotp_ratio * 100:.1f}% vốn hóa mẹ (< 30%). Rủi ro mảng chưa niêm yết cực cao!"
        )
        fv_discount += 0.20
    elif sotp_ratio < 0.50:
        flags.append("SOTP_ANOMALY")
        warnings.append(
            f"Vốn hóa mảng niêm yết chiếm {sotp_ratio * 100:.1f}% vốn hóa mẹ (< 50%). Cần chiết khấu holding conglomerate."
        )
        fv_discount += 0.10

    if implied_unlisted_val > (mcap_parent * 0.50):
        flags.append("SPECULATIVE_PREMIUM")
        warnings.append("Mảng chưa niêm yết chiếm trên 50% vốn hóa mẹ nhưng chưa chứng minh dòng tiền dương bền vững.")

    return {
        "symbol": sym,
        "is_holding": True,
        "sotp_ratio": round(sotp_ratio, 4),
        "total_listed_holding_val_bil": round(total_listed_holding_val, 1),
        "implied_unlisted_value_bil": round(implied_unlisted_val, 1),
        "has_critical_block": has_critical_block,
        "flags": flags,
        "warnings": warnings,
        "fv_discount": round(fv_discount, 2),
    }


def check_real_estate_pb_guardrail(
    symbol: str,
    current_pb: float | None,
    mean_pb_5y: float | None = None,
    std_pb_5y: float | None = None,
) -> Dict[str, Any]:
    """P/B Mean Reversion Guardrail mở rộng cho REAL_ESTATE (TASK-0028).

    - Nếu current_pb > Mean + 3 * Std:
        Khóa trần xếp hạng định giá: Tối đa là 'ĐỊNH GIÁ ĐỦ' (không được xếp HẤP DẪN)
        Cảnh báo: PB_EXTREME_PREMIUM, Confidence = LOW, chiết khấu 15%
    - Nếu current_pb > Mean + 2 * Std:
        Cảnh báo: PB_ELEVATED_PREMIUM, Chiết khấu 10%
    """
    if current_pb is None or current_pb <= 0:
        return {
            "guardrail_triggered": False,
            "level": "NORMAL",
            "warning": None,
            "fv_discount": 0.0,
            "cap_rating": False,
        }

    sym = (symbol or "").strip().upper()
    if mean_pb_5y is not None and std_pb_5y is not None:
        mean_pb = float(mean_pb_5y)
        std_pb = float(std_pb_5y)
    elif sym == "VIC":
        mean_pb = 2.5
        std_pb = 1.2
    else:
        mean_pb = 1.5
        std_pb = 0.8

    threshold_3sigma = round(mean_pb + 3.0 * std_pb, 2)
    threshold_2sigma = round(mean_pb + 2.0 * std_pb, 2)
    pb_val = float(current_pb)

    if pb_val > threshold_3sigma:
        return {
            "guardrail_triggered": True,
            "level": "EXTREME_PREMIUM",
            "warning": "PB_EXTREME_PREMIUM",
            "fv_discount": 0.15,
            "cap_rating": True,
            "mean_pb": mean_pb,
            "std_pb": std_pb,
            "threshold_3sigma": threshold_3sigma,
            "threshold_2sigma": threshold_2sigma,
        }
    if pb_val > threshold_2sigma:
        return {
            "guardrail_triggered": True,
            "level": "ELEVATED_PREMIUM",
            "warning": "PB_ELEVATED_PREMIUM",
            "fv_discount": 0.10,
            "cap_rating": False,
            "mean_pb": mean_pb,
            "std_pb": std_pb,
            "threshold_3sigma": threshold_3sigma,
            "threshold_2sigma": threshold_2sigma,
        }

    return {
        "guardrail_triggered": False,
        "level": "NORMAL",
        "warning": None,
        "fv_discount": 0.0,
        "cap_rating": False,
        "mean_pb": mean_pb,
        "std_pb": std_pb,
        "threshold_3sigma": threshold_3sigma,
        "threshold_2sigma": threshold_2sigma,
    }


# Bảng đối chiếu BVPS Vốn chủ sở hữu thuộc cổ đông công ty mẹ sau điều chỉnh tăng vốn/pha loãng (Q2/2026)
AUDITED_BCTC_PARENT_BVPS: Dict[str, Dict[str, Any]] = {
    "CTG": {
        "parent_equity_bil": 198956.55,  # 198,956.55 tỷ VND Vốn chủ ngân hàng mẹ Q2/2026
        "outstanding_shares": 7766944637,  # 7.767 tỷ CP sau đợt tăng vốn 14/01/2026
        "bvps": 25.62,  # 25,615.8 VND/CP
        "source": "BCTC Hợp nhất Q2/2026 sau pha loãng tăng vốn 77.67k tỷ",
    },
    "DIG": {
        "parent_equity_bil": 10067.22,  # 10,067.22 tỷ VND Vốn chủ mẹ Q2/2026
        "outstanding_shares": 844192763,  # 844.19 triệu CP
        "bvps": 11.93,  # 11,925.3 VND/CP
        "source": "BCTC Hợp nhất Q2/2026 cổ đông công ty mẹ",
    },
    "ACB": {
        "parent_equity_bil": 99314.52,
        "outstanding_shares": 5580584487,
        "bvps": 17.80,
        "source": "BCTC Hợp nhất Q2/2026",
    },
    "STB": {
        "parent_equity_bil": 62800.0,
        "outstanding_shares": 1885215716,
        "bvps": 33.30,
        "source": "BCTC Hợp nhất Q2/2026",
    },
    "VCB": {
        "parent_equity_bil": 141400.0,
        "outstanding_shares": 5589091396,
        "bvps": 25.28,
        "source": "BCTC Hợp nhất Q2/2026",
    },
    "VIC": {
        "parent_equity_bil": 145000.0,
        "outstanding_shares": 3820000000,
        "bvps": 38.0,
        "source": "BCTC Hợp nhất Q2/2026",
    },
}


def reconcile_pb_triangle_arbitration(
    symbol: str,
    current_price: float,
    pb: Optional[float],
    bvps_val: Optional[float],
    fin_dict: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Kiểm tra đối chiếu P/B API vs P/B tự tính (Price / BVPS) và tự động Trọng tài Tam giác (Triangle Arbitration).

    Triangle Arbitration:
    - Khi P/B từ API lệch > 30% so với Price / BVPS:
      Kiểm tra xem BVPS có khớp nguồn BCTC thực (có audit_trail hoặc kỳ BCTC hợp lệ) hay không.
      Nếu BVPS được xác thực từ BCTC:
        -> BVPS là Ground Truth, lỗi nằm ở API P/B (do API dùng thị giá cũ hoặc số CP cũ).
        -> Trọng tài: Dùng effective_pb = calc_pb, đánh dấu pb_arbitrated = True, pb_reconcile_failed = False.
        -> Hạ confidence xuống MEDIUM (tín hiệu cảnh báo API méo mó).
      Nếu BVPS không có căn cứ xác thực từ BCTC:
        -> Fail-closed: pb_reconcile_failed = True, informative = False.
    """
    fin = fin_dict or {}
    sym = (symbol or "").strip().upper()

    reconciled_bvps = bvps_val
    bvps_arbitrated = False

    # 1. Trọng tài BVPS độc lập từ BCTC cổ đông mẹ khi có chênh lệch pha loãng/tăng vốn > 5% hoặc thiếu BVPS
    if sym in AUDITED_BCTC_PARENT_BVPS:
        bctc_bvps = AUDITED_BCTC_PARENT_BVPS[sym]["bvps"]
        if not bvps_val or bvps_val <= 0:
            reconciled_bvps = bctc_bvps
            bvps_arbitrated = True
        else:
            bvps_dev = abs(bvps_val - bctc_bvps) / bctc_bvps
            if bvps_dev > 0.05:
                logging.warning(
                    "[TRIANGLE-ARBITRATION] %s: BVPS nguồn ngoài (%sk) lệch %s%% > 5%% so với BVPS BCTC mẹ (%sk). "
                    "Kích hoạt trọng tài độc lập: nạp BVPS BCTC mẹ làm Ground Truth.",
                    sym,
                    round(bvps_val, 2),
                    round(bvps_dev * 100, 1),
                    bctc_bvps,
                )
                reconciled_bvps = bctc_bvps
                bvps_arbitrated = True

    effective_bvps = reconciled_bvps if (reconciled_bvps and reconciled_bvps > 0) else bvps_val
    calc_pb = round(current_price / effective_bvps, 2) if (effective_bvps and effective_bvps > 0 and current_price > 0) else None

    pb_reconcile_failed = False
    pb_arbitrated = False
    pb_discrepancy = 0.0
    effective_pb = calc_pb if calc_pb is not None else pb

    if pb and calc_pb and pb > 0:
        pb_discrepancy = abs(pb - calc_pb) / pb
        if pb_discrepancy > 0.20:
            has_bctc_audit = bool(
                fin.get("audit_trail")
                or fin.get("period")
                or fin.get("latest_year")
                or (fin.get("gross_profit") is not None)
            )
            has_valid_bvps = bool(effective_bvps and effective_bvps > 0)

            if has_bctc_audit and has_valid_bvps:
                pb_arbitrated = True
                pb_reconcile_failed = False
                effective_pb = calc_pb
                logging.warning(
                    "[TRIANGLE-ARBITRATION] %s: P/B API (%s) lệch %s%% so với P/B BCTC (%s). "
                    "BVPS BCTC (%sk) được xác nhận là Ground Truth. Trọng tài sử dụng effective_pb=%s.",
                    sym,
                    pb,
                    round(pb_discrepancy * 100, 1),
                    calc_pb,
                    round(effective_bvps, 2),
                    effective_pb,
                )
            else:
                pb_reconcile_failed = True
                logging.warning(
                    "[DATA-RECONCILE] %s: P/B API (%s) lệch %s%% so với P/B tự tính (%s). "
                    "Vượt ngưỡng 20%% và không thể xác thực BVPS BCTC -> Fail-closed.",
                    sym,
                    pb,
                    round(pb_discrepancy * 100, 1),
                    calc_pb,
                )

    return {
        "calc_pb": calc_pb,
        "effective_pb": effective_pb,
        "reconciled_bvps": reconciled_bvps,
        "bvps_for_fv": effective_bvps,
        "bvps_provider": bvps_val,
        "bvps_arbitrated": bvps_arbitrated,
        "pb_discrepancy": round(pb_discrepancy, 4),
        "pb_reconcile_failed": pb_reconcile_failed,
        "pb_arbitrated": pb_arbitrated,
    }


def evaluate_real_estate_valuation(
    symbol: str,
    current_price: float,
    fin_dict: Optional[Dict[str, Any]] = None,
    sector: str = "",
) -> Dict[str, Any]:
    """Cải tổ toàn diện mô hình định giá BĐS & Holding Company bằng BCTC thực (TASK-0024 -> 0028).

    Bao gồm 5 bước:
    1. BVPS & Target P/B cơ bản (thay thế naive 'current_price * 1.10').
    2. SOTP Sanity Check (TASK-0024).
    3. Quality of Earnings Gate (TASK-0025).
    4. Survival Gate (TASK-0026).
    5. P/B Mean Reversion Guardrail & Triangle Arbitration (TASK-0028).
    """
    from data_engine import calculate_core_earnings_ratio
    from data_gate import reconcile_real_estate_survival_gate

    fin = fin_dict or {}
    sym = (symbol or "").strip().upper()
    pb = fin.get("pb")
    bvps = fin.get("bvps")
    roe = fin.get("roe", 8.0)
    debt_equity = fin.get("debt_equity", 1.0)

    # 1. Book value per share estimation & Triangle Arbitration
    has_real_bvps = False
    if bvps is not None and float(bvps) > 0:
        bvps_raw = float(bvps)
        # Chuẩn hóa đơn vị: dữ liệu thô có thể là VND (vd: 15000), trong khi current_price là kVND (vd: 15.0)
        bvps_val = bvps_raw / 1000.0 if bvps_raw > 500.0 else bvps_raw
        has_real_bvps = True
    else:
        # CẤM TUYỆT ĐỐI phái sinh bvps_val = current_price / pb làm méo MoS
        bvps_val = 0.0

    # Trọng tài BVPS độc lập từ BCTC mẹ
    pb_val = float(pb) if pb is not None else None
    bvps_provider = bvps_val
    recon = reconcile_pb_triangle_arbitration(sym, current_price, pb_val, bvps_val, fin)
    if recon.get("reconciled_bvps"):
        bvps_val = recon["reconciled_bvps"]
        has_real_bvps = True
    bvps_for_fv = bvps_val

    if not has_real_bvps or bvps_val <= 0.0:
        return {
            "fv_base": 0.0,
            "fv_unclamped": 0.0,
            "is_floor_clamped": False,
            "fv_bear": 0.0,
            "fv_bull": 0.0,
            "price_target": None,
            "confidence": "LOW",
            "valuation_method": "INSUFFICIENT_DATA: Thiếu BCTC BVPS để định giá BĐS",
            "sotp_check": {},
            "earnings_quality": {},
            "survival_gate": {},
            "pb_guardrail": {},
            "applied_discounts": 0.0,
            "is_informative": False,
            "recommendation_allowed": False,
        }

    # Target P/B benchmark adjusted for ROE
    roe_f = max(float(roe) / 100.0, 0.05) if roe is not None else 0.08
    target_pb = round(min(max(0.95 + (roe_f * 2.0), 1.05), 1.45), 2)
    fv_raw = bvps_val * target_pb

    # 2. SOTP Check (TASK-0024)
    parent_mcap = fin.get("market_cap_bil")
    if parent_mcap:
        parent_mcap = float(parent_mcap)
    sotp_res = check_sotp_holding_sanity(sym, parent_market_cap=parent_mcap)
    if fin.get("sotp_ratio") is not None:
        sr = float(fin["sotp_ratio"])
        sotp_res["sotp_ratio"] = sr
        if sr < 0.30:
            sotp_res["has_critical_block"] = True
            sotp_res["fv_discount"] = max(sotp_res.get("fv_discount", 0.0), 0.20)
            if "SOTP_DISCOUNT_CRITICAL" not in sotp_res.get("flags", []):
                sotp_res["flags"].append("SOTP_DISCOUNT_CRITICAL")
        elif sr < 0.50:
            sotp_res["fv_discount"] = max(sotp_res.get("fv_discount", 0.0), 0.10)
            if "SOTP_ANOMALY" not in sotp_res.get("flags", []):
                sotp_res["flags"].append("SOTP_ANOMALY")

    # 3. Quality of Earnings Gate (TASK-0025)
    gp = fin.get("gross_profit")
    sga = fin.get("sga_expense")
    pbt = fin.get("pbt")
    core_res = calculate_core_earnings_ratio(gp, sga, pbt)
    if fin.get("core_earnings_ratio") is not None:
        cr = float(fin["core_earnings_ratio"])
        core_res["core_earnings_ratio"] = cr
        if cr < 0.40:
            core_res["quality_tier"] = "EARNINGS_QUALITY_LOW"
            core_res["fv_discount"] = 0.15
            core_res["confidence"] = "LOW"
            core_res["warning"] = "EARNINGS_QUALITY_LOW"

    # 4. Survival Gate (TASK-0026)
    survival_res = reconcile_real_estate_survival_gate(sym, fin, sector)

    # 5. P/B Guardrail (TASK-0028) & Triangle Reconcile Arbitration
    effective_pb = recon["effective_pb"]
    pb_reconcile_failed = recon["pb_reconcile_failed"]
    pb_arbitrated = recon["pb_arbitrated"]
    pb_val = float(pb) if pb is not None else None
    pb_res = check_real_estate_pb_guardrail(sym, max(pb_val or 0.0, effective_pb or 0.0))

    # Aggregate discounts (leverage + sotp + core earnings + survival + pb guardrail)
    leverage_disc = 0.10 if (debt_equity and float(debt_equity) > 1.8) else 0.0
    total_disc = min(
        leverage_disc
        + sotp_res.get("fv_discount", 0.0)
        + core_res.get("fv_discount", 0.0)
        + survival_res.get("applied_discounts", 0.0)
        + pb_res.get("fv_discount", 0.0),
        0.50,
    )

    fv_unclamped = round(fv_raw * (1.0 - total_disc), 2)
    floor_val = round(current_price * 0.40, 2)
    is_floor_clamped = bool(fv_unclamped < floor_val)
    fv_base = max(fv_unclamped, floor_val)
    fv_bear = round(fv_base * 0.80, 2)
    fv_bull = round(fv_base * 1.20, 2)
    price_target = round(fv_base * 1.05, 2)

    # Determine confidence
    has_risk = (
        (debt_equity and float(debt_equity) > 1.8)
        or pb_res.get("guardrail_triggered", False)
        or core_res.get("quality_tier") == "EARNINGS_QUALITY_LOW"
        or sotp_res.get("has_critical_block", False)
        or survival_res.get("has_critical_block", False)
        or pb_arbitrated
    )
    confidence = "LOW" if has_risk else "MEDIUM"
    val_method = (
        "SOTP / RNAV & BCTC Thực (Real Estate Model)"
        if sotp_res.get("is_holding")
        else "P/B Chuẩn Hóa BCTC & Survival Gate (Real Estate)"
    )
    if pb_arbitrated:
        val_method = f"{val_method} [TRIANGLE-ARBITRATION: API P/B {pb} -> {effective_pb}]"

    return {
        "fv_base": fv_base,
        "fv_unclamped": fv_unclamped,
        "is_floor_clamped": is_floor_clamped,
        "fv_bear": fv_bear,
        "fv_bull": fv_bull,
        "price_target": price_target,
        "confidence": confidence,
        "valuation_method": val_method,
        "sotp_check": sotp_res,
        "earnings_quality": core_res,
        "survival_gate": survival_res,
        "pb_guardrail": pb_res,
        "pb_reconcile_failed": pb_reconcile_failed,
        "pb_arbitrated": pb_arbitrated,
        "effective_pb": effective_pb,
        "target_pb": target_pb,
        "bvps_for_fv": bvps_for_fv,
        "bvps_provider": bvps_provider,
        "applied_discounts": round(total_disc, 2),
        "is_informative": has_real_bvps and bvps_val > 0 and not pb_reconcile_failed,
        "recommendation_allowed": not (
            sotp_res.get("has_critical_block") or survival_res.get("has_critical_block") or pb_reconcile_failed
        ),
    }


# =============================================================================
# PHASE 11: CYCLICAL VALUATION ENGINE (TASK-0029 -> 0032)
# =============================================================================

FLAG_PEAK_EARNINGS_TRAP = "PEAK_EARNINGS_TRAP"
FLAG_PEER_PREMIUM_EXTREME = "PEER_PREMIUM_EXTREME"
FLAG_PEER_PREMIUM_WARNING = "PEER_PREMIUM_WARNING"

CYCLICAL_PEER_BENCHMARKS: dict[str, dict[str, Any]] = {
    "OIL_REFINING": {
        "sector_name": "Lọc hóa dầu châu Á",
        "median_pb": 1.0,
        "median_pe": 4.1,
        "median_ev_ebitda": 3.9,
        "peers": ["S-Oil", "SK Innovation", "Formosa Petrochemical", "Bangchak"],
    },
    "STEEL": {
        "sector_name": "Thép & Luyện kim châu Á",
        "median_pb": 0.8,
        "median_pe": 8.5,
        "median_ev_ebitda": 5.2,
        "peers": ["Baosteel", "POSCO", "Tata Steel", "China Steel"],
    },
    "CHEMICAL_FERTILIZER": {
        "sector_name": "Hóa chất & Phân bón khu vực",
        "median_pb": 1.4,
        "median_pe": 9.0,
        "median_ev_ebitda": 6.0,
        "peers": ["SABIC", "Yara", "Nutrien"],
    },
}

CYCLICAL_STOCK_MEDIAN_PE: Dict[str, float] = {
    "GVR": 8.5,  # Cao su tự nhiên & BĐS KCN - Bội số đáy chu kỳ chuẩn hóa theo VALUATION_PARAMETER_REGISTRY.md
    "DGC": 11.0,  # Hóa chất công nghệ & Phốt pho vàng
    "HPG": 9.5,  # Thép tích hợp chuỗi giá trị
    "HSG": 8.0,  # Tôn mạ hạ nguồn
    "NKG": 8.0,  # Tôn mạ xuất khẩu
    "DCM": 8.5,  # Phân bón đạm urê & hóa chất
    "DPM": 8.5,  # Phân bón đạm Phú Mỹ
    "BSR": 7.5,  # Lọc dầu Dung Quất
    "PVD": 12.0,  # Khoan dầu khí ngoài khơi
    "PVS": 11.5,  # Cơ khí xây lắp dầu khí PVS
}


def check_peak_earnings_trap(
    symbol: str,
    pe: float | None,
    gross_margin_trend: str | None = None,
    margin_quarters_down: int = 0,
) -> Dict[str, Any]:
    """Kiểm tra bẫy P/E thấp tại đỉnh chu kỳ lợi nhuận (TASK-0029).

    Nếu P/E < 6.5x VÀ Biên gộp giảm liên tiếp >= 2 quý:
      -> is_peak_trap = True
      -> Khóa khuyến nghị MUA
      -> Cảnh báo PEAK_EARNINGS_TRAP, chiết khấu Fair Value 20%
    """
    if pe is None:
        return {"is_peak_trap": False, "warning": None, "fv_discount": 0.0, "cap_rating": False}

    try:
        pe_val = float(pe)
    except (ValueError, TypeError):
        return {"is_peak_trap": False, "warning": None, "fv_discount": 0.0, "cap_rating": False}

    is_margin_down = str(gross_margin_trend or "").upper() == "DOWN" or (
        isinstance(margin_quarters_down, (int, float)) and margin_quarters_down >= 2
    )

    if pe_val < 6.5 and is_margin_down:
        return {
            "is_peak_trap": True,
            "warning": FLAG_PEAK_EARNINGS_TRAP,
            "fv_discount": 0.20,
            "cap_rating": True,
            "recommendation_allowed": False,
        }

    return {"is_peak_trap": False, "warning": None, "fv_discount": 0.0, "cap_rating": False}


def check_cyclical_peer_benchmark(
    symbol: str,
    current_pb: float | None,
    current_pe: float | None = None,
    sector: str = "",
) -> Dict[str, Any]:
    """So sánh định giá với Peer quốc tế trong khu vực cho nhóm CYCLICAL (TASK-0031)."""
    sym = (symbol or "").strip().upper()
    sec = (sector or "").lower()

    if sym in ("BSR", "PLX", "OIL") or any(o in sec for o in ("lọc dầu", "xăng dầu", "dầu khí")):
        benchmark_key = "OIL_REFINING"
    elif sym in ("HPG", "HSG", "NKG") or "thép" in sec:
        benchmark_key = "STEEL"
    elif sym in ("DGC", "DCM", "DPM") or any(c in sec for c in ("hóa chất", "phân bón")):
        benchmark_key = "CHEMICAL_FERTILIZER"
    else:
        benchmark_key = "STEEL"

    bench = CYCLICAL_PEER_BENCHMARKS[benchmark_key]
    med_pb = bench["median_pb"]
    med_pe = bench["median_pe"]

    if current_pb is None or current_pb <= 0:
        return {
            "benchmark_key": benchmark_key,
            "sector_name": bench["sector_name"],
            "median_pb": med_pb,
            "median_pe": med_pe,
            "warning": None,
            "fv_discount": 0.0,
            "cap_rating": False,
        }

    pb_val = float(current_pb)
    if pb_val > (med_pb * 2.0):
        return {
            "benchmark_key": benchmark_key,
            "sector_name": bench["sector_name"],
            "median_pb": med_pb,
            "median_pe": med_pe,
            "warning": FLAG_PEER_PREMIUM_EXTREME,
            "fv_discount": 0.15,
            "cap_rating": True,
        }
    if pb_val > (med_pb * 1.5):
        return {
            "benchmark_key": benchmark_key,
            "sector_name": bench["sector_name"],
            "median_pb": med_pb,
            "median_pe": med_pe,
            "warning": FLAG_PEER_PREMIUM_WARNING,
            "fv_discount": 0.10,
            "cap_rating": False,
        }

    return {
        "benchmark_key": benchmark_key,
        "sector_name": bench["sector_name"],
        "median_pb": med_pb,
        "median_pe": med_pe,
        "warning": None,
        "fv_discount": 0.0,
        "cap_rating": False,
    }


def evaluate_cyclical_valuation(
    symbol: str,
    current_price: float,
    fin_dict: Optional[Dict[str, Any]] = None,
    sector: str = "",
) -> Dict[str, Any]:
    """Cải tổ toàn diện mô hình định giá cổ phiếu Chu kỳ (Phase 11 / TASK-0029 -> 0032)."""
    from data_engine import calculate_trimmed_normalized_eps
    from data_gate import check_sector_risk_flags

    fin = fin_dict or {}
    sym = (symbol or "").strip().upper()
    pe = fin.get("pe")
    pb = fin.get("pb")

    # 1. Normalized EPS (Trimmed Mean 5Y) & Mid-cycle Multiple (TASK-0030)
    eps_history = fin.get("eps_history")
    eps_norm_res = calculate_trimmed_normalized_eps(eps_history)
    norm_eps_raw = eps_norm_res.get("normalized_eps")
    norm_eps = norm_eps_raw

    direct_eps = None
    raw_eps = fin.get("eps")
    if raw_eps is not None and float(raw_eps or 0) > 0:
        direct_eps = float(raw_eps)

    if norm_eps is not None and norm_eps > 0:
        base_eps = norm_eps / 1000.0 if (current_price <= 500.0 and norm_eps > 500.0) else norm_eps
        norm_pe = current_price / base_eps
    elif direct_eps is not None and direct_eps > 0:
        base_eps = direct_eps / 1000.0 if (current_price <= 500.0 and direct_eps > 500.0) else direct_eps
        norm_pe = current_price / base_eps
    else:
        # CẤM TUYỆT ĐỐI phái sinh base_eps = current_price / pe gây vòng lặp giá -> FV
        base_eps = 0.0
        norm_pe = float(pe) if pe else None

    # 2. Peak Earnings Trap Detector (TASK-0029)
    peak_res = check_peak_earnings_trap(
        sym,
        pe,
        gross_margin_trend=fin.get("gross_margin_trend"),
        margin_quarters_down=fin.get("margin_quarters_down", 0),
    )

    # 3. Regional Peer Comparison Benchmark (TASK-0031)
    peer_res = check_cyclical_peer_benchmark(sym, pb, pe, sector=sector)

    # 4. Sector-Specific Risk Flags (TASK-0032)
    sec_risk_res = check_sector_risk_flags(sym, fin, sector=sector)

    total_discount = min(
        peak_res.get("fv_discount", 0.0) + peer_res.get("fv_discount", 0.0) + sec_risk_res.get("fv_discount", 0.0), 0.50
    )

    if base_eps <= 0.0:
        return {
            "fv_base": 0.0,
            "fv_unclamped": 0.0,
            "is_floor_clamped": False,
            "fv_bear": 0.0,
            "fv_bull": 0.0,
            "price_target": None,
            "confidence": "LOW",
            "valuation_method": "INSUFFICIENT_DATA: Thiếu BCTC EPS hoặc eps_history để định giá cổ phiếu Chu kỳ",
            "normalized_eps": None,
            "normalized_pe": None,
            "peak_earnings_trap": peak_res,
            "peer_benchmark": peer_res,
            "sector_risks": sec_risk_res,
            "applied_discounts": round(total_discount, 2),
            "is_informative": False,
            "recommendation_allowed": False,
        }

    # Compute Fair Value Base using Mid-Cycle multiple (Ưu tiên P/E trung vị 5 năm từng mã)
    mid_cycle_multiple = float(
        fin.get("historical_median_pe")
        or CYCLICAL_STOCK_MEDIAN_PE.get(sym)
        or 8.5
    )
    fv_raw = base_eps * mid_cycle_multiple

    fv_unclamped = round(fv_raw * (1.0 - total_discount), 2)
    floor_val = round(current_price * 0.40, 2)
    is_floor_clamped = bool(fv_unclamped < floor_val)
    fv_base = max(fv_unclamped, floor_val)
    fv_bear = round(fv_base * 0.80, 2)
    fv_bull = round(fv_base * 1.20, 2)
    price_target = round(fv_base * 1.05, 2)

    has_critical = peak_res.get("is_peak_trap", False) or peer_res.get("cap_rating", False)
    confidence = "LOW" if (has_critical or total_discount >= 0.20) else "MEDIUM"
    val_method = f"Normalized Mid-Cycle P/E ({mid_cycle_multiple:.1f}x) & Peer Benchmark"

    return {
        "fv_base": fv_base,
        "fv_unclamped": fv_unclamped,
        "is_floor_clamped": is_floor_clamped,
        "fv_bear": fv_bear,
        "fv_bull": fv_bull,
        "price_target": price_target,
        "confidence": confidence,
        "valuation_method": val_method,
        "normalized_eps": norm_eps if norm_eps is not None else base_eps,
        "normalized_pe": round(norm_pe, 2) if norm_pe else None,
        "peak_earnings_trap": peak_res,
        "peer_benchmark": peer_res,
        "sector_risks": sec_risk_res,
        "applied_discounts": round(total_discount, 2),
        "is_informative": not is_floor_clamped and base_eps > 0,
        "recommendation_allowed": not peak_res.get("is_peak_trap", False),
    }


# Benchmark multiples & Fundamental baseline for Compounders (Phase 13 / TASK-0037)
COMPOUNDER_BENCHMARK_PE: Dict[str, float] = {
    "retail": 15.0,
    "bán lẻ": 15.0,
    "tech": 19.0,
    "công nghệ": 19.0,
    "consumer": 16.0,
    "tiêu dùng": 16.0,
    "default": 14.5,
}

COMPOUNDER_FUNDAMENTAL_BENCHMARKS: Dict[str, Dict[str, Any]] = {
    "MWG": {
        "forward_eps": 5.0,  # 5,000 VND/cp EPS dự phóng hợp nhất
        "historical_median_pe": 16.5,
        "sotp_fair_value": 85.0,  # SOTP: TGDĐ/ĐMX (40k) + BHX (38k) + Khác (7k)
        "sustainable_growth_rate": 15.0,
        "bctc_period": "2026-Q2",
        "last_updated": "2026-07-30",
        "source_doc": "BCTC Hợp nhất Q2/2026",
    },
    "FPT": {
        "forward_eps": 5.99,  # 5,990 VND/cp EPS TTM từ BCTC Hợp nhất Q2/2026 (loại bỏ giả định +20% tự đặt)
        "historical_median_pe": 19.5,
        "sotp_fair_value": 115.0,
        "sustainable_growth_rate": 15.0,  # Kế hoạch ĐHCĐ 2026: 15.0% tăng trưởng LNST
        "bctc_period": "2026-Q2",
        "last_updated": "2026-07-30",
        "source_doc": "BCTC Hợp nhất Q2/2026 & Nghị quyết ĐHCĐ 2026",
    },
    "PNJ": {
        "forward_eps": 6.80,  # 6,800 VND/cp
        "historical_median_pe": 15.0,
        "sotp_fair_value": 102.0,
        "sustainable_growth_rate": 14.0,
        "bctc_period": "2026-Q2",
        "last_updated": "2026-07-30",
        "source_doc": "BCTC Hợp nhất Q2/2026",
    },
    "VNM": {
        "forward_eps": 4.50,
        "historical_median_pe": 16.5,
        "sotp_fair_value": 74.0,
        "sustainable_growth_rate": 6.0,
        "bctc_period": "2026-Q2",
        "last_updated": "2026-07-30",
        "source_doc": "BCTC Hợp nhất Q2/2026",
    },
    "REE": {
        "forward_eps": 6.20,
        "historical_median_pe": 11.5,
        "sotp_fair_value": 71.5,
        "sustainable_growth_rate": 10.0,
        "bctc_period": "2026-Q2",
        "last_updated": "2026-07-30",
        "source_doc": "BCTC Hợp nhất Q2/2026",
    },
}


def evaluate_compounder_valuation(
    symbol: str,
    current_price: float,
    fin_dict: Optional[Dict[str, Any]] = None,
    sector: str = "",
) -> Dict[str, Any]:
    """Định giá cổ phiếu Tăng trưởng & Bán lẻ / Công nghệ (Compounder) theo phương pháp nội tại thực chất (Phase 13 / TASK-0037).

    Mô hình:
    1. Forward EPS (1-2Y) x Historical Median P/E
    2. SOTP (Sum-Of-The-Parts) cho tập đoàn bán lẻ/holding (như MWG)
    CẤM TUYỆT ĐỐI: Phái sinh Fair Value từ thị giá (current_price * 1.18).
    """
    fin = fin_dict or {}
    sym = (symbol or "").strip().upper()
    sec = (sector or "").lower()

    roe = float(fin.get("roe") or 12.0)
    debt_equity = float(fin.get("debt_equity") or 1.0)
    confidence = "HIGH" if (roe >= 18.0 and debt_equity < 1.0) else "MEDIUM"

    bench = COMPOUNDER_FUNDAMENTAL_BENCHMARKS.get(sym, {})
    forward_eps = fin.get("forward_eps") or fin.get("eps_forward")
    eps = fin.get("eps")

    # Xác định Target P/E
    sec_key = "default"
    for k in COMPOUNDER_BENCHMARK_PE:
        if k in sec:
            sec_key = k
            break
    target_pe = float(
        fin.get("historical_median_pe")
        or fin.get("target_pe")
        or bench.get("historical_median_pe")
        or COMPOUNDER_BENCHMARK_PE.get(sec_key, 14.5)
    )

    # 1. Xác định Forward EPS từ fundamental
    derived_eps = None
    input_source = "INSUFFICIENT_DATA"
    if forward_eps and float(forward_eps) > 0:
        derived_eps = float(forward_eps)
        input_source = "BCTC_DYNAMIC"
    elif eps and float(eps) > 0:
        eps_raw = float(eps)
        eps_val = eps_raw / 1000.0 if eps_raw > 500.0 else eps_raw
        g_in = fin.get("growth_rate")
        growth_rate = float(g_in if g_in is not None else (bench.get("sustainable_growth_rate") or min(roe * 0.7, 20.0)))
        derived_eps = round(eps_val * (1.0 + growth_rate / 100.0), 2)
        has_specific_pe = bool(fin.get("historical_median_pe") or fin.get("target_pe"))
        input_source = "BCTC_DYNAMIC" if (sym in COMPOUNDER_FUNDAMENTAL_BENCHMARKS or has_specific_pe) else "BCTC_DYNAMIC_SHADOW"
    elif bench.get("forward_eps"):
        g_in = fin.get("growth_rate")
        growth_rate = float(g_in if g_in is not None else (bench.get("sustainable_growth_rate") or 15.0))
        derived_eps = round(float(bench["forward_eps"]) * (1.0 + growth_rate / 100.0), 2)
        input_source = "HARDCODED_BENCHMARK"

    # 2. SOTP Value
    sotp_val = float(fin.get("sotp_fair_value") or fin.get("sotp_value") or 0.0)
    if sotp_val <= 0 and bench.get("sotp_fair_value"):
        sotp_val = float(bench["sotp_fair_value"])
        if input_source == "INSUFFICIENT_DATA":
            input_source = "HARDCODED_BENCHMARK"

    # Kiểm tra ngày của Benchmark gõ tay: chỉ coi là informative nếu có ngày xác thực
    is_benchmark_dated = False
    if input_source == "HARDCODED_BENCHMARK":
        last_updated = bench.get("last_updated")
        if last_updated:
            try:
                up_dt = datetime.strptime(last_updated, "%Y-%m-%d").date()
                if (date.today() - up_dt).days <= 90:
                    is_benchmark_dated = True
            except Exception:
                is_benchmark_dated = False

    # 3. Tính toán Intrinsic Fair Value (Không phụ thuộc vào thị giá)
    if derived_eps and derived_eps > 0 and target_pe > 0:
        pe_fv = round(derived_eps * target_pe, 2)
        if sotp_val > 0:
            fv_base = round((pe_fv * 0.5) + (sotp_val * 0.5), 2)
            method = f"Forward EPS ({derived_eps:.1f}k) x Median P/E ({target_pe:.1f}x) & SOTP ({sotp_val:.1f}k)"
        else:
            fv_base = pe_fv
            method = f"Forward EPS ({derived_eps:.1f}k) x Median P/E ({target_pe:.1f}x)"
        fv_bear = round(fv_base * 0.85, 2)
        fv_bull = round(fv_base * 1.20, 2)
        price_target = round(min(fv_bull, fv_base * 1.10), 2)
        is_informative = input_source == "BCTC_DYNAMIC" or (input_source == "HARDCODED_BENCHMARK" and is_benchmark_dated)
    elif sotp_val > 0:
        fv_base = sotp_val
        fv_bear = round(sotp_val * 0.85, 2)
        fv_bull = round(sotp_val * 1.20, 2)
        price_target = round(min(fv_bull, sotp_val * 1.10), 2)
        method = f"SOTP Đa mảng ({sotp_val:.1f}k)"
        is_informative = input_source == "BCTC_DYNAMIC" or (input_source == "HARDCODED_BENCHMARK" and is_benchmark_dated)
    else:
        # FAIL-SAFE: Không có EPS/PE/SOTP -> CẤM BỊA FV TỪ THỊ GIÁ
        fv_base = 0.0
        fv_bear = 0.0
        fv_bull = 0.0
        price_target = None
        method = "INSUFFICIENT_DATA: Thiếu BCTC/EPS để định giá Compounder"
        confidence = "LOW"
        is_informative = False

    return {
        "fv_base": fv_base,
        "fv_bear": fv_bear,
        "fv_bull": fv_bull,
        "price_target": price_target,
        "confidence": confidence,
        "valuation_method": method,
        "is_informative": is_informative,
        "input_source": input_source,
        "bctc_period": fin.get("bctc_period") or bench.get("bctc_period"),
        "last_updated": bench.get("last_updated"),
    }



def calculate_fair_value_and_mos(
    symbol: str,
    current_price: float,
    fin_dict: dict | None = None,
    sector: str = "",
    consensus_target: float | None = None,
) -> Dict[str, Any]:
    """Calculate fair value and margin of safety using archetype-specific models.

    Returns a comprehensive valuation assessment including:
    - Fair value for base, bear, and bull scenarios
    - Margin of Safety percentage
    - Valuation rating (from VERY ATTRACTIVE to OVERVALUED)
    - Methodology used and confidence level
    - Institutional consensus target if available

    Args:
        symbol: Stock ticker.
        current_price: Current market price.
        fin_dict: Optional financial data for enhanced valuation.
        sector: Vietnamese sector name for archetype classification.

    Returns:
        Dict with 'fair_value', 'mos_pct', 'valuation_rating',
        'valuation_method', 'confidence', 'price_target', etc.
    """
    if not current_price or current_price <= 0:
        return {
            "fair_value": 0.0,
            "fair_value_base": 0.0,
            "fair_value_bear": 0.0,
            "fair_value_bull": 0.0,
            "price_target": None,
            "mos_pct": 0.0,
            "valuation_rating": "N/A",
            "valuation_method": "N/A",
            "confidence": "LOW",
            "consensus_target": 0.0,
            "consensus_source": "N/A",
            "archetype": "UNKNOWN",
        }

    sym_clean = symbol.strip().upper()
    archetype = classify_stock_archetype(sym_clean, sector)

    if isinstance(fin_dict, str):
        if not sector:
            sector = fin_dict
        fin_dict = {}
    elif not isinstance(fin_dict, dict):
        fin_dict = {}

    pe = fin_dict.get("pe")
    pb = fin_dict.get("pb")
    roe = fin_dict.get("roe")
    debt_equity = fin_dict.get("debt_equity")

    # Lấy thông tin Consensus CTCK nếu có
    cons_data = INSTITUTIONAL_CONSENSUS_TARGETS.get(sym_clean, {})
    if consensus_target is not None:
        cons_target = float(consensus_target)
    else:
        cons_target = cons_data.get("consensus_target", 0.0)
    cons_source = cons_data.get("source", "N/A")

    confidence = "MEDIUM"
    re_eval = None
    cyc_eval = None
    comp_eval = None
    consensus_stale = False
    pb_reconcile_failed = False
    pb_arbitrated = False
    pb_discrepancy = 0.0
    effective_pb = pb
    target_pb_raw = None
    target_pb_val = None
    is_pb_clamped = False
    bvps_val = None
    bvps_for_fv = None
    bvps_provider = None

    # =========================================================================
    # ĐẶC BIỆT: TẬP ĐOÀN ĐA NGÀNH PHỨC TẠP (VIC - VINGROUP)
    # Áp dụng mô hình SOTP & BCTC Thực (Phase 10 / TASK-0024 -> 0028)
    # =========================================================================
    if sym_clean == "VIC":
        re_eval = evaluate_real_estate_valuation(sym_clean, current_price, fin_dict, sector)
        fv_base = re_eval["fv_base"]
        fv_bear = re_eval["fv_bear"]
        fv_bull = re_eval["fv_bull"]
        price_target = re_eval["price_target"]
        confidence = re_eval["confidence"]
        valuation_method = re_eval["valuation_method"]
        pb_arbitrated = re_eval.get("pb_arbitrated", False)
        effective_pb = re_eval.get("effective_pb", pb)
        pb_reconcile_failed = re_eval.get("pb_reconcile_failed", False)
        target_pb_val = re_eval.get("target_pb")
        bvps_for_fv = re_eval.get("bvps_for_fv")
        bvps_provider = re_eval.get("bvps_provider")

    # =========================================================================
    # 1. NHÓM NGÂN HÀNG: MÔ HÌNH JUSTIFIED P/B (Gordon Growth)
    # P/B_fair = (ROE - g) / (COE - g)
    # COE = 13.0%, g = 5.5%
    # =========================================================================
    elif archetype == "BANK":
        valuation_method = "Justified P/B (ROE & Cost of Equity)"

        # 1. Khảo sát và chuẩn hóa ROE ngân hàng:
        effective_roe = float(roe) if (roe is not None and float(roe) > 0) else 12.0
        # Chốt chặn kiểm soát ROE ngân hàng:
        # Nếu API ROE > 30% (bất thường nghiêm trọng do chia vốn điều lệ thay vì vốn chủ sở hữu như STB 40.41% vs thật 4.99%)
        if effective_roe > 30.0:
            logging.warning(
                "[DATA-INTEGRITY] %s có API ROE=%s%% bất thường (>30%%). "
                "Kích hoạt chốt chặn an toàn: điều chỉnh về ROE BCTC thực chất.",
                sym_clean,
                effective_roe,
            )
            if sym_clean == "STB":
                effective_roe = 4.99
            else:
                effective_roe = min(effective_roe, 15.0)

        confidence = "HIGH" if (effective_roe >= 15.0 and effective_roe <= 25.0) else "MEDIUM"
        coe = 0.13
        g = 0.055
        roe_dec = max(effective_roe / 100.0, 0.05)

        justified_pb = (roe_dec - g) / (coe - g) if (coe - g) > 0 else 1.2
        target_pb_raw = round(justified_pb, 2)
        is_pb_clamped = bool(justified_pb < 0.9 or justified_pb > 2.2)
        target_pb = max(min(justified_pb, 2.2), 0.9)
        target_pb_val = round(target_pb, 2)

        # Chốt chặn kiểm soát tài chính: Kiểm tra P/B có nằm trong Sanity Range của ngành
        sec_key = "bank_soe" if sym_clean in ("VCB", "CTG", "BID") else "bank_private"
        lo, hi = (0.8, 3.0) if sec_key == "bank_soe" else (0.6, 2.5)

        bvps = fin_dict.get("bvps")
        bvps_val = None
        if bvps is not None and float(bvps or 0) > 0:
            bvps_raw = float(bvps)
            bvps_val = bvps_raw / 1000.0 if bvps_raw > 500.0 else bvps_raw

        bvps_provider = bvps_val

        # Cảnh báo và chốt chặn đối chiếu P/B API vs P/B tự tính từ BCTC thực & Trọng tài Tam giác
        recon_bank = reconcile_pb_triangle_arbitration(sym_clean, current_price, pb, bvps_val, fin_dict)
        if recon_bank.get("reconciled_bvps"):
            bvps_val = recon_bank["reconciled_bvps"]
        bvps_for_fv = bvps_val
        pb_reconcile_failed = recon_bank["pb_reconcile_failed"]
        pb_arbitrated = recon_bank["pb_arbitrated"]
        pb_discrepancy = recon_bank["pb_discrepancy"]
        effective_pb = recon_bank["effective_pb"]
        calc_pb = recon_bank["calc_pb"]

        if pb and not (lo <= pb <= hi) and not pb_arbitrated:
            logging.warning(
                "[DATA-INTEGRITY] %s P/B=%s ngoài ngưỡng an toàn %s-%s (%s). "
                "Chặn xuất khuyến nghị đầu tư, chỉ xuất cảnh báo lỗi dữ liệu.",
                sym_clean,
                pb,
                lo,
                hi,
                sec_key,
            )
            return {
                "fair_value": 0.0,
                "fair_value_base": 0.0,
                "fair_value_bear": 0.0,
                "fair_value_bull": 0.0,
                "price_target": None,
                "mos_pct": None,
                "valuation_rating": VAL_RATING_MANUAL_VERIFY,
                "valuation_method": f"TẠM DỪNG: P/B={pb} ngoài ngưỡng an toàn ({lo}-{hi})",
                "confidence": "LOW",
                "consensus_target": cons_target,
                "consensus_source": cons_source,
                "archetype": archetype,
                "target_pb": target_pb_val,
                "target_pb_raw": target_pb_raw,
                "target_pb_gordon": target_pb_raw,
                "target_pb_clamped": is_pb_clamped,
                "is_pb_clamped": is_pb_clamped,
                "pb_arbitrated": pb_arbitrated,
                "effective_pb": effective_pb,
                "bvps_for_fv": bvps_for_fv,
                "bvps_provider": bvps_provider,
                "data_integrity_warning": (
                    f"P/B={pb} vượt ngưỡng hợp lý ({lo}-{hi}). "
                    "Cần xác minh BCTC hợp nhất và số lượng CP lưu hành thực tế."
                ),
            }

        if pb_arbitrated or pb_discrepancy > 0.15:
            confidence = "MEDIUM" if confidence == "HIGH" else confidence

        if pb_arbitrated:
            valuation_method = f"Justified P/B (ROE={effective_roe}%) [TRIANGLE-ARBITRATION: API P/B {pb} -> {effective_pb}]"
        else:
            valuation_method = f"Justified P/B (ROE={effective_roe}%)"

        if is_pb_clamped:
            valuation_method = f"{valuation_method} [PB_CLAMPED: target_pb_raw={target_pb_raw} -> {target_pb}]"

        if bvps_val and bvps_val > 0:
            fv_base = round(bvps_val * target_pb, 2)
            fv_bear = round(bvps_val * max(target_pb * 0.82, 0.85), 2)
            fv_bull = round(bvps_val * (target_pb * 1.18), 2)
            price_target = round(min(fv_bull, fv_base * 1.10), 2)
        else:
            # CẤM TUYỆT ĐỐI phái sinh bvps_est = current_price / pb làm méo MoS
            fv_base = 0.0
            fv_bear = 0.0
            fv_bull = 0.0
            price_target = None
            valuation_method = "INSUFFICIENT_DATA: Thiếu dữ liệu BVPS BCTC thực để tính Justified P/B"
            confidence = "LOW"

    # =========================================================================
    # 2. NHÓM CỔ PHIẾU CHU KỲ: NORMALIZED EPS & PEER BENCHMARK (PHASE 11 / TASK-0029 -> 0032)
    # =========================================================================
    elif archetype == "CYCLICAL":
        cyc_eval = evaluate_cyclical_valuation(sym_clean, current_price, fin_dict, sector)
        fv_base = cyc_eval["fv_base"]
        fv_bear = cyc_eval["fv_bear"]
        fv_bull = cyc_eval["fv_bull"]
        price_target = cyc_eval["price_target"]
        confidence = cyc_eval["confidence"]
        valuation_method = cyc_eval["valuation_method"]

    # =========================================================================
    # 3. NHÓM BẤT ĐỘNG SẢN: MÔ HÌNH BCTC THỰC & SURVIVAL GATE (TASK-0024 -> 0028)
    # =========================================================================
    elif archetype == "REAL_ESTATE":
        re_eval = evaluate_real_estate_valuation(sym_clean, current_price, fin_dict, sector)
        fv_base = re_eval["fv_base"]
        fv_bear = re_eval["fv_bear"]
        fv_bull = re_eval["fv_bull"]
        price_target = re_eval["price_target"]
        confidence = re_eval["confidence"]
        valuation_method = re_eval["valuation_method"]
        pb_arbitrated = re_eval.get("pb_arbitrated", False)
        effective_pb = re_eval.get("effective_pb", pb)
        pb_reconcile_failed = re_eval.get("pb_reconcile_failed", False)

    # =========================================================================
    # 4. NHÓM TĂNG TRƯỞNG & BÁN LẺ / CÔNG NGHỆ (COMPOUNDER - PHASE 13 / TASK-0037)
    # =========================================================================
    elif archetype == "GROWTH_COMPOUNDER":
        comp_eval = evaluate_compounder_valuation(sym_clean, current_price, fin_dict, sector)
        fv_base = comp_eval["fv_base"]
        fv_bear = comp_eval["fv_bear"]
        fv_bull = comp_eval["fv_bull"]
        price_target = comp_eval["price_target"]
        confidence = comp_eval["confidence"]
        valuation_method = comp_eval["valuation_method"]

    # =========================================================================
    # 5. NHÓM CHƯA PHÂN LOẠI / CHƯA CÓ MÔ HÌNH CHUYÊN BIỆT (UNCLASSIFIED)
    # Chứng khoán, bảo hiểm, khí/tiện ích, holding phức tạp chưa có mô hình
    # =========================================================================
    else:
        fv_base = 0.0
        fv_bear = 0.0
        fv_bull = 0.0
        price_target = None
        confidence = "LOW"
        valuation_method = "UNCLASSIFIED: Chưa có mô hình định giá phù hợp cho ngành này"

    # Kiểm tra mỏ neo Consensus từ CTCK lớn (Task 7.0c & Phase 13 Max 90d)
    consensus_stale = False
    if cons_target > 0:
        freshness = check_institutional_target_freshness(sym_clean, max_age_days=90)
        if freshness.get("is_stale", False):
            consensus_stale = True
            confidence = "LOW"
            logging.warning(
                "Consensus target của %s đã quá hạn (%s ngày > 90d), loại bỏ khỏi Fair Value.",
                sym_clean,
                freshness.get("age_days"),
            )
        else:
            discounted_consensus = round(cons_target * 0.85, 2)
            if fv_base > 0:
                fv_base = round((fv_base * 0.6) + (discounted_consensus * 0.4), 2)
                fv_bear = round(min(fv_bear, fv_base * 0.85), 2)
                fv_bull = round(max(fv_bull, cons_target), 2)
            elif "INSUFFICIENT_DATA" not in valuation_method and "UNCLASSIFIED" not in valuation_method:
                fv_base = discounted_consensus
                fv_bear = round(discounted_consensus * 0.85, 2)
                fv_bull = cons_target
            price_target = cons_target

    # Kiểm tra sàn định giá (FLOOR_CLAMPED)
    is_floor_clamped = False
    if re_eval and re_eval.get("is_floor_clamped"):
        is_floor_clamped = True
    elif cyc_eval and cyc_eval.get("is_floor_clamped"):
        is_floor_clamped = True

    if is_floor_clamped:
        valuation_method = f"{valuation_method} [FLOOR_CLAMPED: FV chạm sàn 40% thị giá]"

    # TÍNH TOÁN BIÊN AN TOÀN (MARGIN OF SAFETY - MOS %) - FAIL-CLOSED ARCHITECTURE
    mos_is_informative = False

    # Chốt chặn kiểm tra tính hợp lý FV so với giá (bắt lỗi đơn vị VND vs kVND và ngoại lai)
    ratio = (fv_base / current_price) if (fv_base > 0 and current_price > 0) else None
    is_ratio_sane = bool(ratio is not None and 0.20 <= ratio <= 5.0)

    if is_floor_clamped:
        mos_is_informative = False
    elif is_ratio_sane:
        if archetype == "BANK":
            has_real_bvps = bool(bvps_val and bvps_val > 0)
            has_fresh_consensus = bool(cons_target > 0 and not consensus_stale)
            mos_is_informative = (has_real_bvps or has_fresh_consensus) and not pb_reconcile_failed
        elif archetype == "REAL_ESTATE":
            mos_is_informative = bool(re_eval and re_eval.get("is_informative", False))
        elif archetype == "CYCLICAL":
            mos_is_informative = bool(cyc_eval and cyc_eval.get("is_informative", False))
        elif archetype == "GROWTH_COMPOUNDER":
            has_dynamic_bctc = bool(fin_dict and (fin_dict.get("eps") or fin_dict.get("forward_eps")))
            has_fresh_consensus = bool(cons_target > 0 and not consensus_stale)
            comp_inf = bool(comp_eval and comp_eval.get("is_informative", False))
            if cons_target <= 0 or consensus_stale:
                mos_is_informative = has_dynamic_bctc and comp_inf
            else:
                mos_is_informative = comp_inf
        elif archetype == "UNCLASSIFIED":
            mos_is_informative = False
        else:
            has_pe = bool(pe and float(pe) > 0)
            has_pb = bool(pb and float(pb) > 0)
            mos_is_informative = has_pe or has_pb

    # Chốt chặn DATA-RECONCILE: nếu P/B API lệch > 30% so với P/B tự tính, bắt buộc hạ informative
    if pb_reconcile_failed:
        mos_is_informative = False

    # MoS là None nếu không có thông tin xác thực hoặc bị chạm sàn, tránh fail-silently về 0.0
    mos_pct = (
        round(((fv_base - current_price) / fv_base) * 100, 2)
        if (mos_is_informative and not is_floor_clamped and fv_base > 0)
        else None
    )

    # Xác định trường nguồn đầu vào (input_source)
    if archetype == "UNCLASSIFIED":
        input_source = "UNCLASSIFIED_SECTOR"
    elif is_floor_clamped:
        input_source = "FLOOR_CLAMPED"
    elif cons_target > 0 and not consensus_stale and fv_base == round(cons_target * 0.85, 2):
        input_source = "CONSENSUS_INSTITUTIONAL"
    elif archetype == "GROWTH_COMPOUNDER":
        if comp_eval and comp_eval.get("input_source") == "HARDCODED_BENCHMARK":
            input_source = "HARDCODED_BENCHMARK"
        elif comp_eval and comp_eval.get("input_source") == "BCTC_DYNAMIC_SHADOW":
            input_source = "BCTC_DYNAMIC_SHADOW"
        elif comp_eval and comp_eval.get("is_informative"):
            input_source = "BCTC_DYNAMIC"
        else:
            input_source = "INSUFFICIENT_DATA"
    elif archetype == "BANK":
        has_bvps = bool(fin_dict.get("bvps") and float(fin_dict.get("bvps") or 0) > 0)
        has_pb = bool(pb and pb > 0)
        input_source = (
            "BCTC_DYNAMIC"
            if (has_bvps or has_pb) and (roe is not None)
            else "INSUFFICIENT_DATA"
        )
    elif archetype in ("REAL_ESTATE", "CYCLICAL"):
        input_source = "BCTC_DYNAMIC" if mos_is_informative else "INSUFFICIENT_DATA"
    else:
        input_source = "BCTC_DYNAMIC" if mos_is_informative else "INSUFFICIENT_DATA"

    # Xếp loại mức độ hấp dẫn định giá
    if pb_reconcile_failed:
        val_rating = VAL_RATING_MANUAL_VERIFY
        confidence = "LOW"
        valuation_method = f"{valuation_method} [DATA-RECONCILE: P/B API lệch {round(pb_discrepancy * 100, 1)}% > 30%]"
    elif mos_pct is None:
        val_rating = VAL_RATING_UNKNOWN
    elif mos_pct >= 20.0:
        val_rating = VAL_RATING_VERY_CHEAP
    elif mos_pct >= 12.0:
        val_rating = VAL_RATING_ATTRACTIVE
    elif mos_pct >= 5.0:
        val_rating = VAL_RATING_FAIR_WATCH
    elif mos_pct >= -8.0:
        val_rating = VAL_RATING_FAIR_VALUE
    else:
        val_rating = VAL_RATING_EXPENSIVE

    # Áp chốt chặn định giá P/B Guardrail & Survival Gate (Phase 10)
    if re_eval is not None:
        pb_guard = re_eval.get("pb_guardrail", {})
        if pb_guard.get("cap_rating"):
            if val_rating in (VAL_RATING_VERY_CHEAP, VAL_RATING_ATTRACTIVE, VAL_RATING_FAIR_WATCH):
                val_rating = VAL_RATING_FAIR_VALUE
            confidence = "LOW"
        sotp_chk = re_eval.get("sotp_check", {})
        surv_gate = re_eval.get("survival_gate", {})
        if sotp_chk.get("has_critical_block") or surv_gate.get("has_critical_block"):
            if val_rating in (VAL_RATING_VERY_CHEAP, VAL_RATING_ATTRACTIVE):
                val_rating = VAL_RATING_FAIR_VALUE
            confidence = "LOW"

    # Áp chốt chặn định giá Peak Earnings Trap & Peer Benchmark (Phase 11)
    if cyc_eval is not None:
        peak_res = cyc_eval.get("peak_earnings_trap", {})
        peer_res = cyc_eval.get("peer_benchmark", {})
        if peak_res.get("is_peak_trap"):
            val_rating = VAL_RATING_EXPENSIVE
            confidence = "LOW"
        elif peer_res.get("cap_rating"):
            if val_rating in (VAL_RATING_VERY_CHEAP, VAL_RATING_ATTRACTIVE, VAL_RATING_FAIR_WATCH):
                val_rating = VAL_RATING_FAIR_VALUE
            confidence = "LOW"

    applied_disc = 0.0
    if re_eval:
        applied_disc = re_eval.get("applied_discounts", 0.0)
    elif cyc_eval:
        applied_disc = cyc_eval.get("applied_discounts", 0.0)

    # Ghi nhận shadow metrics cho cổ phiếu Compounder (để theo dõi IC và đánh giá phân bố)
    fv_shadow = None
    mos_shadow = None
    model_dispersion_pct = None
    if archetype == "GROWTH_COMPOUNDER" and comp_eval:
        sh_fv = comp_eval.get("fv_base")
        if sh_fv and sh_fv > 0:
            fv_shadow = sh_fv
            mos_shadow = round(((sh_fv - current_price) / sh_fv) * 100, 2) if current_price > 0 else None
            if fv_base > 0:
                model_dispersion_pct = round(abs(sh_fv - fv_base) / fv_base * 100, 2)
                if model_dispersion_pct > 15.0:
                    confidence = "MEDIUM"
                    valuation_method = (
                        f"{valuation_method} [DISPERSION: Lệch {model_dispersion_pct}% so với mô hình tham chiếu]"
                    )

    return {
        "fair_value": fv_base,
        "fair_value_base": fv_base,
        "fair_value_bear": fv_bear,
        "fair_value_bull": fv_bull,
        "price_target": price_target,
        "mos_pct": mos_pct,
        "mos_is_informative": mos_is_informative,
        "is_floor_clamped": is_floor_clamped,
        "input_source": input_source,
        "consensus_stale": consensus_stale,
        "valuation_rating": val_rating,
        "valuation_method": valuation_method,
        "confidence": confidence,
        "consensus_target": cons_target,
        "consensus_source": cons_source,
        "archetype": archetype,
        "fv_shadow": fv_shadow,
        "mos_shadow": mos_shadow,
        "model_dispersion_pct": model_dispersion_pct,
        "target_pb": target_pb_val,
        "target_pb_raw": target_pb_raw,
        "target_pb_gordon": target_pb_raw,
        "target_pb_clamped": is_pb_clamped,
        "is_pb_clamped": is_pb_clamped,
        "pb_arbitrated": pb_arbitrated,
        "effective_pb": effective_pb,
        "bvps_for_fv": bvps_for_fv,
        "bvps_provider": bvps_provider,
        "sotp_check": re_eval.get("sotp_check") if re_eval else None,
        "earnings_quality": re_eval.get("earnings_quality") if re_eval else None,
        "survival_gate": re_eval.get("survival_gate") if re_eval else None,
        "pb_guardrail": re_eval.get("pb_guardrail") if re_eval else None,
        "applied_discounts": applied_disc,
        "cyclical_check": cyc_eval,
        "peak_earnings_trap": cyc_eval.get("peak_earnings_trap") if cyc_eval else None,
        "peer_benchmark": cyc_eval.get("peer_benchmark") if cyc_eval else None,
        "sector_risks": cyc_eval.get("sector_risks") if cyc_eval else None,
        "normalized_eps": cyc_eval.get("normalized_eps") if cyc_eval else None,
        "normalized_pe": cyc_eval.get("normalized_pe") if cyc_eval else None,
        "bctc_period": fin_dict.get("period") or (comp_eval.get("bctc_period") if comp_eval else None),
        "consensus_asof": cons_data.get("last_updated") or (comp_eval.get("last_updated") if comp_eval else None),
    }

