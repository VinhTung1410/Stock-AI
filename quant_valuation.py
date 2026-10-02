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

# Mỏ neo định giá trung vị tham chiếu từ các tổ chức phân tích uy tín (SSI Research, HSC, Vietcap)
# Được cập nhật định kỳ (kèm last_updated), đóng vai trò "Trần định giá tham chiếu" (Consensus Ceiling)
INSTITUTIONAL_CONSENSUS_TARGETS = {
    "FPT": {
        "consensus_target": 88.0,
        "source": "SSI/Vietcap/HSC Consensus",
        "quality_tier": "TIER_1_COMPOUNDER",
        "last_updated": "2024-10-01",
    },
    "HPG": {
        "consensus_target": 26.5,
        "source": "HSC/SSI Research",
        "quality_tier": "TIER_1_CYCLICAL",
        "last_updated": "2024-10-01",
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
        "last_updated": "2024-10-01",
    },
    "MSB": {
        "consensus_target": 14.5,
        "source": "SSI Research/VCSC",
        "quality_tier": "TIER_2_BANK",
        "last_updated": "2024-10-01",
    },
    "BSR": {
        "consensus_target": 32.0,
        "source": "KBSV/SSI Research",
        "quality_tier": "TIER_2_ENERGY",
        "last_updated": "2024-10-01",
    },
    "TCB": {
        "consensus_target": 28.0,
        "source": "Vietcap/HSC Research",
        "quality_tier": "TIER_1_BANK",
        "last_updated": "2024-10-01",
    },
    "MBB": {
        "consensus_target": 27.0,
        "source": "SSI/HSC Research",
        "quality_tier": "TIER_1_BANK",
        "last_updated": "2024-10-01",
    },
    "ACB": {
        "consensus_target": 28.5,
        "source": "SSI/Vietcap",
        "quality_tier": "TIER_1_BANK",
        "last_updated": "2024-10-01",
    },
    "VCB": {
        "consensus_target": 98.0,
        "source": "SSI/HSC Research",
        "quality_tier": "TIER_1_BANK",
        "last_updated": "2024-10-01",
    },
    "VHM": {
        "consensus_target": 48.0,
        "source": "Vietcap/SSI Research",
        "quality_tier": "TIER_1_REALTY",
        "last_updated": "2024-10-01",
    },
    "VNM": {
        "consensus_target": 75.0,
        "source": "HSC/SSI Research",
        "quality_tier": "TIER_1_CONSUMER",
        "last_updated": "2024-10-01",
    },
    "DGC": {
        "consensus_target": 115.0,
        "source": "Vietcap/HSC Research",
        "quality_tier": "TIER_1_CHEMICAL",
        "last_updated": "2024-10-01",
    },
    "PNJ": {
        "consensus_target": 105.0,
        "source": "SSI/Vietcap Research",
        "quality_tier": "TIER_1_RETAIL",
        "last_updated": "2024-10-01",
    },
    "REE": {
        "consensus_target": 72.0,
        "source": "SSI Research",
        "quality_tier": "TIER_1_UTILITY",
        "last_updated": "2024-10-01",
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
    """Classify a stock into one of 4 valuation archetypes.

    Archetypes determine which valuation model is applied:
    - BANK: Banks & financials → Justified P/B
    - CYCLICAL: Steel, oil, chemicals → Normalized mid-cycle earnings
    - REAL_ESTATE: Property developers → Floor P/B + leverage discount
    - GROWTH_COMPOUNDER: Tech, retail, consumer → Historical median P/E

    Args:
        symbol: Stock ticker (e.g. 'FPT', 'VCB').
        sector: Vietnamese sector name for fallback classification.

    Returns:
        One of: 'BANK', 'CYCLICAL', 'REAL_ESTATE', 'GROWTH_COMPOUNDER'.
    """
    if not symbol or not isinstance(symbol, str):
        sym = ""
    else:
        sym = symbol.strip().upper()
    sec = sector.lower() if isinstance(sector, str) else ""

    if (
        any(b in sym for b in ["VCB", "TCB", "MBB", "ACB", "VPB", "MSB", "STB", "HDB", "CTG", "BID", "VIB", "TPB"])
        or "ngân hàng" in sec
    ):
        return "BANK"
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
    return "GROWTH_COMPOUNDER"


def get_stock_archetype_details(symbol: str, sector: str = "") -> dict:
    """Trả về chi tiết phân loại Archetype, Nhóm ngành và Chiến lược đầu tư phù hợp.

    Phân tách rạch ròi:
    - GROWTH_COMPOUNDER: Doanh nghiệp tăng trưởng dài hạn (FPT, MWG...) -> Chiến lược VALUE / Tích sản.
    - CYCLICAL: Doanh nghiệp chu kỳ hàng hóa (HPG, BSR, DGC...) -> Chiến lược CYCLICAL.
    - BANK: Ngân hàng & Định chế tài chính (VCB, TCB...) -> Chiến lược FINANCIAL.
    - REAL_ESTATE: Doanh nghiệp bất động sản (VHM, KDH...) -> Chiến lược PROPERTY.
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
            "valuation_model": "Justified P/B & NPL/LLR Quality",
            "holding_shield": True,
        },
        "REAL_ESTATE": {
            "archetype": "REAL_ESTATE",
            "sector_group": "🏢 Bất động sản",
            "default_strategy": "PROPERTY",
            "strategy_label": "TÀI SẢN / RNAV",
            "valuation_model": "RNAV & Floor P/B",
            "holding_shield": False,
        },
    }
    return details_map.get(archetype, details_map["GROWTH_COMPOUNDER"])


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
    5. P/B Mean Reversion Guardrail (TASK-0028).
    """
    from data_engine import calculate_core_earnings_ratio
    from data_gate import reconcile_real_estate_survival_gate

    fin = fin_dict or {}
    sym = (symbol or "").strip().upper()
    pb = fin.get("pb")
    bvps = fin.get("bvps")
    roe = fin.get("roe", 8.0)
    debt_equity = fin.get("debt_equity", 1.0)

    # 1. Book value per share estimation
    if bvps is not None and float(bvps) > 0:
        bvps_val = float(bvps)
    elif pb is not None and float(pb) > 0:
        bvps_val = current_price / float(pb)
    else:
        bvps_val = current_price * 0.80

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

    # 5. P/B Guardrail (TASK-0028)
    pb_val = float(pb) if pb is not None else None
    pb_res = check_real_estate_pb_guardrail(sym, pb_val)

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

    fv_base = round(max(fv_raw * (1.0 - total_disc), current_price * 0.40), 2)
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
    )
    confidence = "LOW" if has_risk else "MEDIUM"
    val_method = (
        "SOTP / RNAV & BCTC Thực (Real Estate Model)"
        if sotp_res.get("is_holding")
        else "P/B Chuẩn Hóa BCTC & Survival Gate (Real Estate)"
    )

    return {
        "fv_base": fv_base,
        "fv_bear": fv_bear,
        "fv_bull": fv_bull,
        "price_target": price_target,
        "confidence": confidence,
        "valuation_method": val_method,
        "sotp_check": sotp_res,
        "earnings_quality": core_res,
        "survival_gate": survival_res,
        "pb_guardrail": pb_res,
        "applied_discounts": round(total_disc, 2),
        "recommendation_allowed": not (sotp_res.get("has_critical_block") or survival_res.get("has_critical_block")),
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
    norm_eps = eps_norm_res.get("normalized_eps")
    if norm_eps is not None and norm_eps > 0:
        base_eps = norm_eps
        norm_pe = current_price / norm_eps
    else:
        base_eps = (current_price / pe) if (pe and float(pe) > 0) else (current_price * 0.10)
        norm_pe = float(pe) if pe else 10.0

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

    # Compute Fair Value Base using Mid-Cycle multiple (8.5x)
    mid_cycle_multiple = 8.5
    fv_raw = base_eps * mid_cycle_multiple

    total_discount = min(
        peak_res.get("fv_discount", 0.0) + peer_res.get("fv_discount", 0.0) + sec_risk_res.get("fv_discount", 0.0), 0.50
    )

    fv_base = round(max(fv_raw * (1.0 - total_discount), current_price * 0.40), 2)
    fv_bear = round(fv_base * 0.80, 2)
    fv_bull = round(fv_base * 1.20, 2)
    price_target = round(fv_base * 1.05, 2)

    has_critical = peak_res.get("is_peak_trap", False) or peer_res.get("cap_rating", False)
    confidence = "LOW" if (has_critical or total_discount >= 0.20) else "MEDIUM"
    val_method = f"Normalized Mid-Cycle P/E ({mid_cycle_multiple}x) & Peer Benchmark"

    return {
        "fv_base": fv_base,
        "fv_bear": fv_bear,
        "fv_bull": fv_bull,
        "price_target": price_target,
        "confidence": confidence,
        "valuation_method": val_method,
        "normalized_eps": norm_eps,
        "normalized_pe": round(norm_pe, 2) if norm_pe else None,
        "peak_earnings_trap": peak_res,
        "peer_benchmark": peer_res,
        "sector_risks": sec_risk_res,
        "applied_discounts": round(total_discount, 2),
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
    },
    "FPT": {
        "forward_eps": 5.80,  # 5,800 VND/cp
        "historical_median_pe": 19.5,
        "sotp_fair_value": 115.0,
        "sustainable_growth_rate": 20.0,
    },
    "PNJ": {
        "forward_eps": 6.80,  # 6,800 VND/cp
        "historical_median_pe": 15.0,
        "sotp_fair_value": 102.0,
        "sustainable_growth_rate": 14.0,
    },
    "VNM": {
        "forward_eps": 4.50,
        "historical_median_pe": 16.5,
        "sotp_fair_value": 74.0,
        "sustainable_growth_rate": 6.0,
    },
    "REE": {
        "forward_eps": 6.20,
        "historical_median_pe": 11.5,
        "sotp_fair_value": 71.5,
        "sustainable_growth_rate": 10.0,
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
    if forward_eps and float(forward_eps) > 0:
        derived_eps = float(forward_eps)
    elif eps and float(eps) > 0:
        growth_rate = float(fin.get("growth_rate") or bench.get("sustainable_growth_rate") or min(roe * 0.7, 20.0))
        derived_eps = round(float(eps) * (1.0 + growth_rate / 100.0), 2)
    elif bench.get("forward_eps"):
        derived_eps = float(bench["forward_eps"])

    # 2. SOTP Value
    sotp_val = float(fin.get("sotp_fair_value") or fin.get("sotp_value") or bench.get("sotp_fair_value") or 0.0)

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
        is_informative = True
    elif sotp_val > 0:
        fv_base = sotp_val
        fv_bear = round(sotp_val * 0.85, 2)
        fv_bull = round(sotp_val * 1.20, 2)
        price_target = round(min(fv_bull, sotp_val * 1.10), 2)
        method = f"SOTP Đa mảng ({sotp_val:.1f}k)"
        is_informative = True
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

    fin_dict = fin_dict or {}
    pe = fin_dict.get("pe")
    pb = fin_dict.get("pb")
    roe = fin_dict.get("roe") or 12.0
    debt_equity = fin_dict.get("debt_equity") or 1.0

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

    # =========================================================================
    # 1. NHÓM NGÂN HÀNG: MÔ HÌNH JUSTIFIED P/B (Gordon Growth)
    # P/B_fair = (ROE - g) / (COE - g)
    # COE = 13.0%, g = 5.5%
    # =========================================================================
    elif archetype == "BANK":
        valuation_method = "Justified P/B (ROE & Cost of Equity)"
        confidence = "HIGH" if roe >= 15.0 else "MEDIUM"
        coe = 0.13
        g = 0.055
        roe_dec = max(roe / 100.0, 0.05)

        justified_pb = (roe_dec - g) / (coe - g) if (coe - g) > 0 else 1.2
        target_pb = max(min(justified_pb, 2.2), 0.9)

        # Chốt chặn kiểm soát tài chính: Kiểm tra P/B có nằm trong Sanity Range của ngành
        sec_key = "bank_soe" if sym_clean in ("VCB", "CTG", "BID") else "bank_private"
        lo, hi = (0.8, 3.0) if sec_key == "bank_soe" else (0.6, 2.5)
        if pb and not (lo <= pb <= hi):
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
                "mos_pct": 0.0,
                "valuation_rating": VAL_RATING_MANUAL_VERIFY,
                "valuation_method": f"TẠM DỪNG: P/B={pb} ngoài ngưỡng an toàn ({lo}-{hi})",
                "confidence": "LOW",
                "consensus_target": cons_target,
                "consensus_source": cons_source,
                "archetype": archetype,
                "data_integrity_warning": (
                    f"P/B={pb} vượt ngưỡng hợp lý ({lo}-{hi}). "
                    "Cần xác minh BCTC hợp nhất và số lượng CP lưu hành thực tế."
                ),
            }

        if pb and pb > 0:
            bvps_est = current_price / pb
            fv_base = round(bvps_est * target_pb, 2)
            fv_bear = round(bvps_est * max(target_pb * 0.82, 0.85), 2)
            fv_bull = round(bvps_est * (target_pb * 1.18), 2)
            price_target = round(min(fv_bull, fv_base * 1.10), 2)
        else:
            # Sửa triệt để v7.3: CẤM fallback current_price * 1.12
            fv_base = 0.0
            fv_bear = 0.0
            fv_bull = 0.0
            price_target = None
            valuation_method = "INSUFFICIENT_DATA: Thiếu dữ liệu P/B để tính Justified P/B"
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

    # =========================================================================
    # 4. NHÓM TĂNG TRƯỞNG & BÁN LẺ / CÔNG NGHỆ (COMPOUNDER - PHASE 13 / TASK-0037)
    # =========================================================================
    else:
        comp_eval = evaluate_compounder_valuation(sym_clean, current_price, fin_dict, sector)
        fv_base = comp_eval["fv_base"]
        fv_bear = comp_eval["fv_bear"]
        fv_bull = comp_eval["fv_bull"]
        price_target = comp_eval["price_target"]
        confidence = comp_eval["confidence"]
        valuation_method = comp_eval["valuation_method"]

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
            else:
                fv_base = discounted_consensus
                fv_bear = round(discounted_consensus * 0.85, 2)
                fv_bull = cons_target
            price_target = cons_target

    # TÍNH TOÁN BIÊN AN TOÀN (MARGIN OF SAFETY - MOS %)
    mos_pct = round(((fv_base - current_price) / fv_base) * 100, 2) if fv_base > 0 else 0.0

    # Phân định MoS thực chất vs MoS suy diễn (Phase 13 / TASK-0038)
    mos_is_informative = True
    if fv_base <= 0.0:
        mos_is_informative = False
        mos_pct = 0.0
    elif archetype == "GROWTH_COMPOUNDER":
        if comp_eval and not comp_eval.get("is_informative", True) and (cons_target <= 0 or consensus_stale):
            mos_is_informative = False
    elif archetype == "BANK" and (not pb or pb <= 0) and (cons_target <= 0 or consensus_stale):
        mos_is_informative = False

    # Xếp loại mức độ hấp dẫn định giá
    if mos_pct >= 20.0:
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

    return {
        "fair_value": fv_base,
        "fair_value_base": fv_base,
        "fair_value_bear": fv_bear,
        "fair_value_bull": fv_bull,
        "price_target": price_target,
        "mos_pct": mos_pct,
        "mos_is_informative": mos_is_informative,
        "consensus_stale": consensus_stale,
        "valuation_rating": val_rating,
        "valuation_method": valuation_method,
        "confidence": confidence,
        "consensus_target": cons_target,
        "consensus_source": cons_source,
        "archetype": archetype,
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
    }
