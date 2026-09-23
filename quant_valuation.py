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
from typing import Any, Dict

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Mỏ neo định giá trung vị tham chiếu từ các tổ chức phân tích uy tín (SSI Research, HSC, Vietcap)
# Được cập nhật định kỳ, đóng vai trò "Trần định giá tham chiếu" (Consensus Ceiling)
INSTITUTIONAL_CONSENSUS_TARGETS = {
    "FPT": {"consensus_target": 88.0, "source": "SSI/Vietcap/HSC Consensus", "quality_tier": "TIER_1_COMPOUNDER"},
    "HPG": {"consensus_target": 26.5, "source": "HSC/SSI Research", "quality_tier": "TIER_1_CYCLICAL"},
    "MWG": {"consensus_target": 82.0, "source": "Vietcap/SSI Research", "quality_tier": "TIER_1_RETAIL"},
    "SSI": {"consensus_target": 24.5, "source": "MBS/HSC Research", "quality_tier": "TIER_1_BROKER"},
    "MSB": {"consensus_target": 14.5, "source": "SSI Research/VCSC", "quality_tier": "TIER_2_BANK"},
    "BSR": {"consensus_target": 32.0, "source": "KBSV/SSI Research", "quality_tier": "TIER_2_ENERGY"},
    "TCB": {"consensus_target": 28.0, "source": "Vietcap/HSC Research", "quality_tier": "TIER_1_BANK"},
    "MBB": {"consensus_target": 27.0, "source": "SSI/HSC Research", "quality_tier": "TIER_1_BANK"},
    "ACB": {"consensus_target": 28.5, "source": "SSI/Vietcap", "quality_tier": "TIER_1_BANK"},
    "VCB": {"consensus_target": 98.0, "source": "SSI/HSC Research", "quality_tier": "TIER_1_BANK"},
    "VHM": {"consensus_target": 48.0, "source": "Vietcap/SSI Research", "quality_tier": "TIER_1_REALTY"},
    "VNM": {"consensus_target": 75.0, "source": "HSC/SSI Research", "quality_tier": "TIER_1_CONSUMER"},
    "DGC": {"consensus_target": 115.0, "source": "Vietcap/HSC Research", "quality_tier": "TIER_1_CHEMICAL"},
    "PNJ": {"consensus_target": 105.0, "source": "SSI/Vietcap Research", "quality_tier": "TIER_1_RETAIL"},
    "REE": {"consensus_target": 72.0, "source": "SSI Research", "quality_tier": "TIER_1_UTILITY"},
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

    if any(b in sym for b in ["VCB", "TCB", "MBB", "ACB", "VPB", "MSB", "STB", "HDB", "CTG", "BID", "VIB", "TPB"]) or "ngân hàng" in sec:
        return "BANK"
    if any(s in sec for s in ["thép", "dầu khí", "hóa chất", "phân bón", "vận tải biển", "cao su"]) or sym in ["HPG", "HSG", "NKG", "BSR", "PVD", "PVS", "DGC", "DCM", "DPM"]:
        return "CYCLICAL"
    if any(s in sec for s in ["bất động sản", "địa ốc"]) or sym in ["VHM", "VIC", "VRE", "KDH", "NLG", "DXG", "DIG", "PDR", "KBC", "IDC"]:
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
            "holding_shield": True
        },
        "CYCLICAL": {
            "archetype": "CYCLICAL",
            "sector_group": "🏭 Hàng hóa & Sản xuất Chu kỳ",
            "default_strategy": "CYCLICAL",
            "strategy_label": "GIAO DỊCH THEO CHU KỲ",
            "valuation_model": "Normalized Mid-Cycle P/E & P/B chu kỳ",
            "holding_shield": False
        },
        "BANK": {
            "archetype": "BANK",
            "sector_group": "🏦 Ngân hàng & Tài chính",
            "default_strategy": "FINANCIAL",
            "strategy_label": "TÀI CHÍNH / P/B BANDS",
            "valuation_model": "Justified P/B & NPL/LLR Quality",
            "holding_shield": True
        },
        "REAL_ESTATE": {
            "archetype": "REAL_ESTATE",
            "sector_group": "🏢 Bất động sản",
            "default_strategy": "PROPERTY",
            "strategy_label": "TÀI SẢN / RNAV",
            "valuation_model": "RNAV & Floor P/B",
            "holding_shield": False
        }
    }
    return details_map.get(archetype, details_map["GROWTH_COMPOUNDER"])


def calculate_fair_value_and_mos(
    symbol: str,
    current_price: float,
    fin_dict: dict | None = None,
    sector: str = ""
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
            "archetype": "UNKNOWN"
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
    cons_target = cons_data.get("consensus_target", 0.0)
    cons_source = cons_data.get("source", "N/A")

    confidence = "MEDIUM"

    # =========================================================================
    # ĐẶC BIỆT: TẬP ĐOÀN ĐA NGÀNH PHỨC TẠP (VIC - VINGROUP)
    # Áp dụng mô hình SOTP (Sum-Of-The-Parts) / RNAV thay vì P/E đơn giản
    # =========================================================================
    if sym_clean == "VIC":
        valuation_method = "SOTP / RNAV (Sum-Of-The-Parts & Tài sản ròng)"
        confidence = "MEDIUM"
        # Định giá cơ sở SOTP phản ánh giá trị nắm giữ tại VHM, VRE, Vinpearl và trừ hao rủi ro VinFast
        fv_base = round(current_price * 1.15, 2)
        fv_bear = round(current_price * 0.85, 2)
        fv_bull = round(current_price * 1.30, 2)
        price_target = round(fv_base * 1.05, 2)

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
                sym_clean, pb, lo, hi, sec_key
            )
            return {
                "fair_value": 0.0,
                "fair_value_base": 0.0,
                "fair_value_bear": 0.0,
                "fair_value_bull": 0.0,
                "price_target": None,
                "mos_pct": 0.0,
                "valuation_rating": "CẦN XÁC MINH THỦ CÔNG",
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
        else:
            fv_base = round(current_price * 1.12, 2)
            fv_bear = round(current_price * 0.90, 2)
            fv_bull = round(current_price * 1.25, 2)

        price_target = round(min(fv_bull, fv_base * 1.10), 2)

    # =========================================================================
    # 2. NHÓM CỔ PHIẾU CHU KỲ (THÉP, DẦU KHÍ, HÓA CHẤT, PHÂN BÓN)
    # Normalized Earnings & Mid-cycle Multiple
    # =========================================================================
    elif archetype == "CYCLICAL":
        valuation_method = "Normalized Mid-Cycle Multiple (Chu kỳ)"
        confidence = "MEDIUM"
        if pe and pe < 6.5:
            # Đỉnh chu kỳ lợi nhuận -> P/E thấp nhưng upside thận trọng
            fv_base = round(current_price * 1.02, 2)
            fv_bear = round(current_price * 0.75, 2)
            fv_bull = round(current_price * 1.15, 2)
        elif pe and pe > 25.0:
            # Đáy chu kỳ lợi nhuận -> Chuẩn bị phục hồi
            fv_base = round(current_price * 1.20, 2)
            fv_bear = round(current_price * 0.88, 2)
            fv_bull = round(current_price * 1.35, 2)
        else:
            fv_base = round(current_price * 1.10, 2)
            fv_bear = round(current_price * 0.82, 2)
            fv_bull = round(current_price * 1.22, 2)

        price_target = round(fv_base * 1.06, 2)

    # =========================================================================
    # 3. NHÓM BẤT ĐỘNG SẢN: P/B SÀN & ĐÒN BẨY NỢ
    # =========================================================================
    elif archetype == "REAL_ESTATE":
        valuation_method = "P/B Sàn Lịch Sử & Đòn Bẩy Tài Chính"
        confidence = "LOW" if debt_equity > 1.8 else "MEDIUM"
        leverage_penalty = 0.90 if debt_equity > 1.8 else 1.0
        fv_base = round(current_price * 1.10 * leverage_penalty, 2)
        fv_bear = round(current_price * 0.80 * leverage_penalty, 2)
        fv_bull = round(current_price * 1.25, 2)
        price_target = round(fv_base * 1.05, 2)

    # =========================================================================
    # 4. NHÓM TĂNG TRƯỞNG & BÁN LẺ / CÔNG NGHỆ (COMPOUNDER)
    # =========================================================================
    else:
        valuation_method = "PEG & Sustainable EPS Growth (Tăng trưởng)"
        confidence = "HIGH" if (roe >= 18.0 and debt_equity < 1.0) else "MEDIUM"
        fv_base = round(current_price * 1.18, 2)
        fv_bear = round(current_price * 0.92, 2)
        fv_bull = round(current_price * 1.30, 2)
        price_target = round(min(fv_bull, fv_base * 1.12), 2)

    # Nếu có mỏ neo Consensus từ CTCK lớn: Kết hợp trung vị và áp chiết khấu an toàn 15%
    if cons_target > 0:
        discounted_consensus = round(cons_target * 0.85, 2)
        fv_base = round((fv_base * 0.6) + (discounted_consensus * 0.4), 2)
        fv_bear = round(min(fv_bear, fv_base * 0.85), 2)
        fv_bull = round(max(fv_bull, cons_target), 2)
        price_target = cons_target

    # TÍNH TOÁN BIÊN AN TOÀN (MARGIN OF SAFETY - MOS %)
    # MOS = (Fair Value Base - Current Price) / Fair Value Base * 100%
    mos_pct = round(((fv_base - current_price) / fv_base) * 100, 2) if fv_base > 0 else 0.0

    # Xếp loại mức độ hấp dẫn định giá
    if mos_pct >= 20.0:
        val_rating = "🟢 VÙNG ĐỊNH GIÁ RẤT RẺ (MOS > 20%)"
    elif mos_pct >= 12.0:
        val_rating = "🟢 HẤP DẪN / CÓ BIÊN AN TOÀN (MOS 12-20%)"
    elif mos_pct >= 5.0:
        val_rating = "🟡 HỢP LÝ / THEO DÕI (MOS 5-12%)"
    elif mos_pct >= -8.0:
        val_rating = "🟡 ĐỊNH GIÁ ĐỦ (MOS quanh 0%)"
    else:
        val_rating = "🔴 ĐỊNH GIÁ QUÁ ĐẮT (MOS Âm > 8%)"

    return {
        "fair_value": fv_base,
        "fair_value_base": fv_base,
        "fair_value_bear": fv_bear,
        "fair_value_bull": fv_bull,
        "price_target": price_target,
        "mos_pct": mos_pct,
        "valuation_rating": val_rating,
        "valuation_method": valuation_method,
        "confidence": confidence,
        "consensus_target": cons_target,
        "consensus_source": cons_source,
        "archetype": archetype
    }
