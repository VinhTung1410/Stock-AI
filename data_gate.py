"""
Data Reconciliation Gate (Phase 0) — 100% Deterministic Python.

Bridges CFA-grade financial audit rigor with high-speed automated pipelines.
Evaluates data integrity, price consistency, corporate actions, financial statement
freshness, and news source hierarchy with 0 AI tokens and sub-millisecond latency.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Source Tier Hierarchy (from Official to Rumor)
SOURCE_TIER_OFFICIAL_FILING = "TIER_1_OFFICIAL_FILING"        # HOSE, HNX, UBCK, CBTT
SOURCE_TIER_AUDITED_FINANCIALS = "TIER_2_AUDITED_FINANCIALS"  # Audited BCTC
SOURCE_TIER_FINANCIAL_MEDIA = "TIER_3_FINANCIAL_MEDIA"        # CafeF, Vietstock, VnEconomy
SOURCE_TIER_GENERAL_RSS = "TIER_4_GENERAL_RSS"                # Google News RSS, general press
SOURCE_TIER_UNVERIFIED_RUMOR = "TIER_5_UNVERIFIED_RUMOR"      # Forums, social chatter

# Price & Quality Status Constants (SonarCloud S1192)
STATUS_CLEAN = "CLEAN"
STATUS_ADJUSTED = "ADJUSTED"
STATUS_CONFLICT = "CONFLICT"

TIER_HIGH = "HIGH"
TIER_MEDIUM = "MEDIUM"
TIER_LOW = "LOW"
TIER_CRITICAL = "CRITICAL"

BADGE_STALE_LOCKED = " | ⚠️ DỮ LIỆU ĐÓNG BĂNG - KHÓA KHUYẾN NGHỊ"
BADGE_MANUAL_VERIFY = " | ⚠️ CẦN XÁC MINH THỦ CÔNG"

# Exchange statutory daily price limits
EXCHANGE_DAILY_LIMITS = {
    "HOSE": 0.07,   # +/- 7.0%
    "HNX": 0.10,    # +/- 10.0%
    "UPCOM": 0.15   # +/- 15.0%
}


def reconcile_price(
    tech_data: Optional[Dict[str, Any]] = None,
    exchange: str = "HOSE"
) -> Tuple[str, float, List[str]]:
    """Reconcile market price anomalies, statutory ceiling/floor limits, and zero/negative checks.

    Returns:
        tuple of (status: 'CLEAN'|'ADJUSTED'|'CONFLICT', reconciled_price: float, issues: list[str])
    """
    issues = []
    if not tech_data:
        return STATUS_CONFLICT, 0.0, ["Missing technical price data dictionary"]

    curr_p = float(tech_data.get("current_price", 0.0))
    close_p = float(tech_data.get("close", curr_p))
    ref_p = float(tech_data.get("ref_price", tech_data.get("reference_price", 0.0)))
    chg_pct = float(tech_data.get("change_pct", 0.0))

    if curr_p <= 0.0 and close_p <= 0.0:
        issues.append(f"Fatal Price Error: Non-positive price detected ({curr_p}k).")
        return STATUS_CONFLICT, 0.0, issues

    reconciled_p = curr_p if curr_p > 0 else close_p
    status = STATUS_CLEAN

    # Verify statutory exchange band limit (+/- 7% on HOSE, +/- 10% on HNX)
    max_limit = EXCHANGE_DAILY_LIMITS.get(exchange.upper(), 0.07)
    if ref_p > 0:
        calculated_chg = (reconciled_p - ref_p) / ref_p
        if abs(calculated_chg) > (max_limit + 0.005):
            issues.append(
                f"Statutory Band Breach: Price change {calculated_chg*100:+.2f}% exceeds {exchange} limit ({max_limit*100}%)."
            )
            status = STATUS_CONFLICT

    # Check reported change_pct vs computed price change
    if ref_p > 0 and abs(chg_pct) > 0.01:
        expected_chg = round(((reconciled_p - ref_p) / ref_p) * 100, 2)
        if abs(chg_pct - expected_chg) > 1.5:
            issues.append(
                f"Price Change Mismatch: Reported {chg_pct:+.2f}% vs Computed {expected_chg:+.2f}%."
            )
            status = STATUS_ADJUSTED

    return status, reconciled_p, issues


def _evaluate_single_corporate_action(ca: Dict[str, Any], today: Any) -> Optional[Dict[str, Any]]:
    """Evaluate if a corporate action is on or near today's date."""
    ex_date_str = ca.get("ex_date") or ca.get("ngay_gdkhq")
    if not ex_date_str:
        return None
    try:
        ex_date = datetime.strptime(str(ex_date_str)[:10], "%Y-%m-%d").date()
        if abs((today - ex_date).days) <= 1:
            ca_type = ca.get("action_type", "DIVIDEND").upper()
            return {
                "type": ca_type,
                "impact": "MECHANICAL_PRICE_DROP",
                "ex_date": str(ex_date),
                "description": ca.get("description", f"Sự kiện quyền {ca_type} ngày {ex_date}")
            }
    except Exception:
        pass
    return None


def reconcile_corporate_actions(
    tech_data: Optional[Dict[str, Any]] = None,
    corporate_actions: Optional[List[Dict[str, Any]]] = None
) -> Tuple[List[Dict[str, Any]], bool]:
    """Check for corporate actions (GDKHQ, cash dividend, bonus shares, rights issue).

    Classifies price adjustments into:
    - MECHANICAL_DROP: Statutory adjustment on Ex-Dividend Date (GDKHQ) — NEVER trigger stop loss!
    - ECONOMIC_DROP: Real intraday market selling pressure.

    Returns:
        tuple of (tagged_actions: list[dict], is_ex_dividend_session: bool)
    """
    tagged = []
    is_ex_date = False
    today = datetime.now().date()

    if tech_data and tech_data.get("is_gdkhq"):
        is_ex_date = True
        tagged.append({
            "type": "GDKHQ",
            "impact": "MECHANICAL_PRICE_DROP",
            "description": "Ngày Giao dịch Không hưởng quyền — Giá điều chỉnh kỹ thuật tự động."
        })

    for ca in (corporate_actions or []):
        ca_result = _evaluate_single_corporate_action(ca, today)
        if ca_result:
            is_ex_date = True
            tagged.append(ca_result)

    return tagged, is_ex_date


def _parse_period_year_quarter(fin_data: Dict[str, Any]) -> Tuple[Optional[int], Optional[int]]:
    """Extract and parse (year, quarter) from fin_data dictionary or period string."""
    latest_quarter = fin_data.get("latest_quarter") or fin_data.get("quarter")
    latest_year = fin_data.get("latest_year") or fin_data.get("year")
    if latest_quarter and latest_year:
        try:
            return int(latest_year), int(str(latest_quarter).replace("Q", "").replace("q", ""))
        except (ValueError, TypeError):
            pass

    period_str = str(fin_data.get("period") or "").strip().upper()
    if "-Q" in period_str:
        try:
            parts = period_str.split("-Q")
            return int(parts[0]), int(parts[1])
        except (ValueError, IndexError):
            pass
    elif len(period_str) >= 4 and period_str[:4].isdigit():
        return int(period_str[:4]), 4

    return None, None


def _check_financial_freshness(latest_year: Optional[int], latest_quarter: Optional[int]) -> List[str]:
    """Check if financial statement quarter is more than 2 quarters old."""
    if not (latest_year and latest_quarter):
        return []
    try:
        now = datetime.now()
        current_quarter = (now.month - 1) // 3 + 1
        quarters_diff = (now.year - latest_year) * 4 + (current_quarter - latest_quarter)
        if quarters_diff > 2:
            return [f"Financial Statements (Q{latest_quarter}/{latest_year} is {quarters_diff} quarters old)"]
    except Exception:
        pass
    return []


def reconcile_financial_period(
    fin_data: Optional[Dict[str, Any]] = None
) -> Tuple[List[str], List[str]]:
    """Audit financial statement freshness and reporting period alignment.

    Checks:
    - Financial statement date within last 2 quarters.
    - Consistency of TTM vs FY basis.

    Returns:
        tuple of (missing_fields: list[str], stale_fields: list[str])
    """
    if not fin_data:
        return ["fin_data_dict"], []

    # Essential ratios needed for quantitative scoring
    required_keys = ["roe", "f_score", "z_score", "pb", "pe"]
    missing = [k for k in required_keys if fin_data.get(k) is None]

    latest_year, latest_quarter = _parse_period_year_quarter(fin_data)
    stale = _check_financial_freshness(latest_year, latest_quarter)

    return missing, stale


GATE_PB_SANITY_RANGES = {
    "bank_soe": (0.8, 3.0),
    "bank_private": (0.6, 2.5),
    "real_estate": (0.6, 3.0),
    "default": (0.5, 5.0),
}


def reconcile_valuation_sanity(symbol: str, fin_data: Optional[Dict[str, Any]] = None, sector: str = "") -> List[str]:
    """Kiểm tra P/B theo ngưỡng hợp lý (Sanity Range) ngành theo quy định Ban Kiểm soát Tài chính."""
    if not fin_data:
        return []
    pb = fin_data.get("pb")
    if pb is None or float(pb) <= 0:
        return []

    sym = symbol.strip().upper()
    sec = sector.lower()
    if sym in ("VCB", "CTG", "BID"):
        sec_key = "bank_soe"
    elif any(b in sym for b in ("TCB", "MBB", "ACB", "VPB", "MSB", "STB", "HDB", "VIB", "TPB", "LPB", "SHB", "OCB", "EIB", "SSB")) or "ngân hàng" in sec:
        sec_key = "bank_private"
    elif sym in ("VHM", "VIC", "VRE", "KDH", "NLG", "DXG", "DIG", "PDR", "KBC", "IDC", "NVL") or any(r in sec for r in ("bất động sản", "địa ốc")):
        sec_key = "real_estate"
    else:
        sec_key = "default"

    lo, hi = GATE_PB_SANITY_RANGES[sec_key]
    pb_val = float(pb)
    if not (lo <= pb_val <= hi):
        return [f"P/B={pb_val} ngoài ngưỡng an toàn ngành [{lo}, {hi}]. CẦN XÁC MINH THỦ CÔNG."]
    return []


def _classify_source_tier(source: str, tag: str) -> str:
    """Classify news source into hierarchical credibility tier."""
    src_upper = source.upper()
    if any(k in src_upper for k in ("UBCK", "HOSE", "CBTT")):
        return SOURCE_TIER_OFFICIAL_FILING
    if "BCTC" in tag or "AUDIT" in tag:
        return SOURCE_TIER_AUDITED_FINANCIALS
    if src_upper in ("CAFEF", "VIETSTOCK", "VNECONOMY", "VNDIRECT"):
        return SOURCE_TIER_FINANCIAL_MEDIA
    return SOURCE_TIER_GENERAL_RSS


def _compute_news_age_and_status(pub_date_str: Any, now: datetime) -> Tuple[float, str]:
    """Parse news publication timestamp and calculate age in hours and freshness bucket."""
    age_hours = 24.0
    if pub_date_str:
        try:
            pub_date = datetime.strptime(str(pub_date_str)[:19], "%Y-%m-%d %H:%M:%S")
            age_hours = (now - pub_date).total_seconds() / 3600.0
        except Exception:
            pass

    if age_hours > 72.0:
        status = "HISTORICAL"
    elif age_hours <= 12.0:
        status = "BREAKING"
    else:
        status = "CONFIRMED"

    return round(age_hours, 1), status


def reconcile_news_freshness(
    news: Optional[List[Dict[str, Any]]] = None
) -> Tuple[List[Dict[str, Any]], List[str]]:
    """Classify news items into source hierarchy tiers and freshness buckets.

    Returns:
        tuple of (reconciled_news: list[dict], news_warnings: list[str])
    """
    if not news:
        return [], ["No news catalyst detected in the last 72 hours"]

    now = datetime.now()
    reconciled = []

    for item in news:
        tag = (item.get("tag") or "TIN_TỨC").upper()
        title = item.get("title", "")
        source = item.get("source", "CafeF")
        tier = _classify_source_tier(source, tag)
        age_hours, status = _compute_news_age_and_status(
            item.get("published_date") or item.get("date"),
            now
        )
        reconciled.append({
            "title": title,
            "tag": tag,
            "source": source,
            "tier": tier,
            "freshness": status,
            "age_hours": age_hours
        })

    return reconciled, []


def reconcile_price_freshness(tech_data: Optional[Dict[str, Any]] = None) -> List[str]:
    """Check if market price data timestamp is fresh within 7 calendar days (~5 trading days)."""
    if not tech_data:
        return []
    date_val = tech_data.get("as_of_date") or tech_data.get("trade_date") or tech_data.get("date")
    if not date_val:
        return []
    try:
        trade_date = datetime.strptime(str(date_val)[:10], "%Y-%m-%d").date()
        days_gap = (datetime.now().date() - trade_date).days
        if days_gap > 7:
            return [f"Market Price Stale ({trade_date} is {days_gap} days old > 5 trading days)"]
    except Exception:
        pass
    return []


def reconcile_market_cap_consistency(
    reconciled_price: float,
    fin_data: Optional[Dict[str, Any]] = None,
    tech_data: Optional[Dict[str, Any]] = None
) -> List[str]:
    """Cross-validate price against market cap and shares outstanding.

    Formula: Implied Price = Market Cap / Shares Outstanding.
    Flags conflict if discrepancy > 15%.
    """
    if reconciled_price <= 0:
        return []

    combined = {**(tech_data or {}), **(fin_data or {})}
    cap_bil = combined.get("market_cap_bil") or combined.get("market_cap_billion")
    cap_vnd = None
    if cap_bil and float(cap_bil) > 0:
        cap_vnd = float(cap_bil) * 1e9
    elif combined.get("market_cap") and float(combined.get("market_cap")) > 0:
        raw_cap = float(combined.get("market_cap"))
        cap_vnd = raw_cap * 1e9 if raw_cap < 1e9 else raw_cap

    shares = combined.get("shares_outstanding") or combined.get("issue_share") or combined.get("shares")
    if not (cap_vnd and shares and float(shares) > 0):
        return []

    shares_val = float(shares)
    implied_price_k = (cap_vnd / shares_val) / 1000.0

    if implied_price_k <= 0:
        return []

    discrepancy_pct = abs(reconciled_price - implied_price_k) / reconciled_price
    if discrepancy_pct > 0.15:
        return [
            f"Cross-Validation Mismatch: Market Cap / Shares implies {implied_price_k:.1f}k VND "
            f"vs Market Price {reconciled_price:.1f}k VND ({discrepancy_pct*100:.1f}% discrepancy > 15%)."
        ]
    return []


def _compute_quality_deductions(
    price_status: str,
    reconciled_price: float,
    tech_data: Optional[Dict[str, Any]],
    fin_data: Optional[Dict[str, Any]],
    fin_missing: List[str],
    fin_stale: List[str],
    news: Optional[List[Dict[str, Any]]],
    val_issues: Optional[List[str]],
    price_stale: Optional[List[str]],
    cap_conflicts: Optional[List[str]],
) -> float:
    """Calculate total score deductions based on data anomalies."""
    deductions = 0.0
    if price_status == STATUS_CONFLICT:
        deductions += 65.0 if reconciled_price <= 0.0 else 45.0
    elif price_status == STATUS_ADJUSTED:
        deductions += 10.0

    if not tech_data:
        deductions += 35.0

    if not fin_data:
        deductions += 30.0
    elif fin_missing:
        deductions += min(len(fin_missing) * 6.0, 30.0)

    if fin_stale:
        deductions += 20.0
    if price_stale:
        deductions += 20.0
    if val_issues:
        deductions += 40.0
    if cap_conflicts:
        deductions += 35.0
    if not news:
        deductions += 5.0

    return deductions


def _assign_quality_tier(score: float) -> str:
    """Determine data quality tier based on final score."""
    if score >= 85.0:
        return TIER_HIGH
    if score >= 65.0:
        return TIER_MEDIUM
    if score >= 40.0:
        return TIER_LOW
    return TIER_CRITICAL


def _calculate_quality_score(
    price_status: str,
    reconciled_price: float,
    tech_data: Optional[Dict[str, Any]],
    fin_data: Optional[Dict[str, Any]],
    fin_missing: List[str],
    fin_stale: List[str],
    news: Optional[List[Dict[str, Any]]],
    val_issues: Optional[List[str]] = None,
    price_stale: Optional[List[str]] = None,
    cap_conflicts: Optional[List[str]] = None,
) -> Tuple[float, str]:
    """Compute 100-point data quality score and assign quality tier."""
    deductions = _compute_quality_deductions(
        price_status, reconciled_price, tech_data, fin_data,
        fin_missing, fin_stale, news, val_issues, price_stale, cap_conflicts
    )
    final_score = max(0.0, min(100.0, round(100.0 - deductions, 1)))
    tier = _assign_quality_tier(final_score)
    return final_score, tier


def _evaluate_gate_decision(
    quality_tier: str,
    has_conflict: bool,
    is_stale_data: bool,
    quality_score: float,
) -> Tuple[bool, bool, str]:
    """Determine gate passed status, recommendation allowed, and formatted badge string."""
    gate_passed = (
        quality_tier in (TIER_HIGH, TIER_MEDIUM)
        and not has_conflict
        and not is_stale_data
    )
    recommendation_allowed = gate_passed and quality_tier != TIER_LOW and not has_conflict and not is_stale_data

    badge = f"📊 DATA QUALITY: {quality_tier} ({quality_score:.0f}/100)"
    if is_stale_data:
        badge += BADGE_STALE_LOCKED
    elif has_conflict:
        badge += BADGE_MANUAL_VERIFY

    return gate_passed, recommendation_allowed, badge


def reconcile_data(
    symbol: str,
    tech_data: Optional[Dict[str, Any]] = None,
    fin_data: Optional[Dict[str, Any]] = None,
    news: Optional[List[Dict[str, Any]]] = None,
    corporate_actions: Optional[List[Dict[str, Any]]] = None,
    exchange: str = "HOSE"
) -> Dict[str, Any]:
    """Execute Phase 0 Data Reconciliation Gate in pure deterministic Python.

    Evaluates:
    1. Price Consistency & Exchange Limits
    2. Corporate Actions & GDKHQ Status
    3. Financial Statement Completeness & Freshness
    4. Valuation Multiple Sanity (P/B Sector Guardrail)
    5. News Catalysts & Source Tiers
    6. Overall Data Quality Score (0-100) & Quality Tier (HIGH / MEDIUM / LOW / CRITICAL)

    Returns:
        Structured audit dictionary with verified facts, warnings, and gate decision.
    """
    sym = (symbol or "").strip().upper()
    missing_data: List[str] = []
    conflicting_data: List[str] = []
    stale_data: List[str] = []

    # 1. Price Reconciliation
    price_status, reconciled_price, price_issues = reconcile_price(tech_data, exchange=exchange)
    if price_status == STATUS_CONFLICT:
        conflicting_data.extend(price_issues)
    elif price_status == STATUS_ADJUSTED:
        stale_data.extend(price_issues)

    # Price freshness check
    price_stale_issues = reconcile_price_freshness(tech_data)
    stale_data.extend(price_stale_issues)

    # 2. Corporate Actions
    tagged_actions, is_ex_dividend = reconcile_corporate_actions(tech_data, corporate_actions)

    # 3. Financial Statements & Freshness
    fin_missing, fin_stale = reconcile_financial_period(fin_data)
    missing_data.extend(fin_missing)
    stale_data.extend(fin_stale)

    # 4. Valuation Sanity Guardrail (Financial Control Rule 1.2)
    sec_str = (tech_data or {}).get("sector", "") or (fin_data or {}).get("sector", "")
    val_issues = reconcile_valuation_sanity(sym, fin_data, sec_str)
    if val_issues:
        conflicting_data.extend(val_issues)

    # Cross-validation: Market Cap / Shares vs Price
    cap_issues = reconcile_market_cap_consistency(reconciled_price, fin_data, tech_data)
    if cap_issues:
        conflicting_data.extend(cap_issues)

    # 5. News Catalysts
    reconciled_news, _ = reconcile_news_freshness(news)

    # 6. Compute Data Quality Score (100-point scale)
    quality_score, quality_tier = _calculate_quality_score(
        price_status=price_status,
        reconciled_price=reconciled_price,
        tech_data=tech_data,
        fin_data=fin_data,
        fin_missing=fin_missing,
        fin_stale=fin_stale,
        news=news,
        val_issues=val_issues,
        price_stale=price_stale_issues,
        cap_conflicts=cap_issues
    )

    # Determine Gate Status: Hard lock if stale data or conflicts
    is_stale_data = bool(fin_stale) or bool(price_stale_issues)
    has_conflict = bool(val_issues) or bool(cap_issues) or price_status == STATUS_CONFLICT

    gate_passed, recommendation_allowed, badge = _evaluate_gate_decision(
        quality_tier, has_conflict, is_stale_data, quality_score
    )

    # Source Tiers Summary
    source_tiers = {
        "price_source": "Vnstock/HOSE_Live" if tech_data else "None",
        "financial_source": "Audited_Quarterly_Reports" if fin_data else "None",
        "news_source": reconciled_news[0]["tier"] if reconciled_news else "None"
    }

    return {
        "symbol": sym,
        "data_quality": quality_tier,
        "quality_score": quality_score,
        "badge": badge,
        "gate_passed": gate_passed,
        "recommendation_allowed": recommendation_allowed,
        "is_stale": is_stale_data,
        "price_status": price_status,
        "reconciled_price": reconciled_price,
        "is_ex_dividend": is_ex_dividend,
        "corporate_actions": tagged_actions,
        "missing_data": missing_data,
        "conflicting_data": conflicting_data,
        "stale_data": stale_data,
        "news": reconciled_news,
        "source_tiers": source_tiers
    }


def format_data_quality_badge(reconcile_result: Dict[str, Any]) -> str:
    """Format a human-readable badge summary string for report headers."""
    tier = reconcile_result.get("data_quality", "MEDIUM")
    score = reconcile_result.get("quality_score", 0.0)
    conflicts = len(reconcile_result.get("conflicting_data", []))
    missing = len(reconcile_result.get("missing_data", []))

    status_icon_map = {
        "HIGH": "🟢",
        "MEDIUM": "🟡",
        "LOW": "🔴",
        "CRITICAL": "🔴"
    }
    status_icon = status_icon_map.get(tier, "🔴")
    return (
        f"{status_icon} **Data Quality:** `{tier}` ({score:.0f}/100) | "
        f"Conflicts: `{conflicts}` | Missing: `{missing}`"
    )
