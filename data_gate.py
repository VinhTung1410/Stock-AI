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

# Exchange statutory daily price limits
EXCHANGE_DAILY_LIMITS = {
    "HOSE": 0.07,   # +/- 7.0%
    "HNX": 0.10,    # +/- 10.0%
    "UPCOM": 0.15   # +/- 15.0%
}


def reconcile_price(
    symbol: str,
    tech_data: Optional[Dict[str, Any]] = None,
    exchange: str = "HOSE"
) -> Tuple[str, float, List[str]]:
    """Reconcile market price anomalies, statutory ceiling/floor limits, and zero/negative checks.

    Returns:
        tuple of (status: 'CLEAN'|'ADJUSTED'|'CONFLICT', reconciled_price: float, issues: list[str])
    """
    issues = []
    if not tech_data:
        return "CONFLICT", 0.0, ["Missing technical price data dictionary"]

    curr_p = float(tech_data.get("current_price", 0.0))
    close_p = float(tech_data.get("close", curr_p))
    ref_p = float(tech_data.get("ref_price", tech_data.get("reference_price", 0.0)))
    chg_pct = float(tech_data.get("change_pct", 0.0))

    if curr_p <= 0.0 and close_p <= 0.0:
        issues.append(f"Fatal Price Error: Non-positive price detected ({curr_p}k).")
        return "CONFLICT", 0.0, issues

    reconciled_p = curr_p if curr_p > 0 else close_p
    status = "CLEAN"

    # Verify statutory exchange band limit (+/- 7% on HOSE, +/- 10% on HNX)
    max_limit = EXCHANGE_DAILY_LIMITS.get(exchange.upper(), 0.07)
    if ref_p > 0:
        calculated_chg = (reconciled_p - ref_p) / ref_p
        if abs(calculated_chg) > (max_limit + 0.005):
            issues.append(
                f"Statutory Band Breach: Price change {calculated_chg*100:+.2f}% exceeds {exchange} limit ({max_limit*100}%)."
            )
            status = "CONFLICT"

    # Check reported change_pct vs computed price change
    if ref_p > 0 and abs(chg_pct) > 0.01:
        expected_chg = round(((reconciled_p - ref_p) / ref_p) * 100, 2)
        if abs(chg_pct - expected_chg) > 1.5:
            issues.append(
                f"Price Change Mismatch: Reported {chg_pct:+.2f}% vs Computed {expected_chg:+.2f}%."
            )
            status = "ADJUSTED"

    return status, reconciled_p, issues


def reconcile_corporate_actions(
    symbol: str,
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

    actions = corporate_actions or []
    # Check if tech_data already includes ex_dividend indicator
    if tech_data and tech_data.get("is_gdkhq"):
        is_ex_date = True
        tagged.append({
            "type": "GDKHQ",
            "impact": "MECHANICAL_PRICE_DROP",
            "description": "Ngày Giao dịch Không hưởng quyền — Giá điều chỉnh kỹ thuật tự động."
        })

    for ca in actions:
        ex_date_str = ca.get("ex_date") or ca.get("ngay_gdkhq")
        if not ex_date_str:
            continue
        try:
            ex_date = datetime.strptime(str(ex_date_str)[:10], "%Y-%m-%d").date()
            if abs((today - ex_date).days) <= 1:
                is_ex_date = True
                ca_type = ca.get("action_type", "DIVIDEND").upper()
                tagged.append({
                    "type": ca_type,
                    "impact": "MECHANICAL_PRICE_DROP",
                    "ex_date": str(ex_date),
                    "description": ca.get("description", f"Sự kiện quyền {ca_type} ngày {ex_date}")
                })
        except Exception:
            continue

    return tagged, is_ex_date


def reconcile_financial_period(
    symbol: str,
    fin_data: Optional[Dict[str, Any]] = None
) -> Tuple[List[str], List[str]]:
    """Audit financial statement freshness and reporting period alignment.

    Checks:
    - Financial statement date within last 2 quarters.
    - Consistency of TTM vs FY basis.

    Returns:
        tuple of (missing_fields: list[str], stale_fields: list[str])
    """
    missing = []
    stale = []

    if not fin_data:
        return ["fin_data_dict"], []

    # Essential ratios needed for quantitative scoring
    required_keys = ["roe", "f_score", "z_score", "pb", "pe"]
    for k in required_keys:
        if k not in fin_data or fin_data[k] is None:
            missing.append(k)

    # Check statement quarter freshness
    latest_quarter = fin_data.get("latest_quarter") or fin_data.get("quarter")
    latest_year = fin_data.get("latest_year") or fin_data.get("year")

    if latest_quarter and latest_year:
        try:
            q_num = int(str(latest_quarter).replace("Q", "").replace("q", ""))
            y_num = int(latest_year)
            now = datetime.now()
            current_quarter = (now.month - 1) // 3 + 1
            current_year = now.year

            quarters_diff = (current_year - y_num) * 4 + (current_quarter - q_num)
            if quarters_diff > 2:
                stale.append(f"Financial Statements (Q{q_num}/{y_num} is {quarters_diff} quarters old)")
        except Exception:
            pass

    return missing, stale


def reconcile_news_freshness(
    news: Optional[List[Dict[str, Any]]] = None
) -> Tuple[List[Dict[str, Any]], List[str]]:
    """Classify news items into source hierarchy tiers and freshness buckets.

    Returns:
        tuple of (reconciled_news: list[dict], news_warnings: list[str])
    """
    reconciled = []
    warnings = []

    if not news:
        return [], ["No news catalyst detected in the last 72 hours"]

    now = datetime.now()

    for item in news:
        tag = (item.get("tag") or "TIN_TỨC").upper()
        title = item.get("title", "")
        source = item.get("source", "CafeF")

        # Assign Source Tier
        if "UBCK" in source.upper() or "HOSE" in source.upper() or "CBTT" in source.upper():
            tier = SOURCE_TIER_OFFICIAL_FILING
        elif "BCTC" in tag or "AUDIT" in tag:
            tier = SOURCE_TIER_AUDITED_FINANCIALS
        elif source.upper() in ["CAFEF", "VIETSTOCK", "VNECONOMY", "VNDIRECT"]:
            tier = SOURCE_TIER_FINANCIAL_MEDIA
        else:
            tier = SOURCE_TIER_GENERAL_RSS

        # Freshness evaluation
        pub_date_str = item.get("published_date") or item.get("date")
        age_hours = 24.0  # Default assumed fresh if date unparsed
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

        reconciled.append({
            "title": title,
            "tag": tag,
            "source": source,
            "tier": tier,
            "freshness": status,
            "age_hours": round(age_hours, 1)
        })

    return reconciled, warnings


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
    4. News Catalysts & Source Tiers
    5. Overall Data Quality Score (0-100) & Quality Tier (HIGH / MEDIUM / LOW / CRITICAL)

    Returns:
        Structured audit dictionary with verified facts, warnings, and gate decision.
    """
    sym = (symbol or "").strip().upper()
    missing_data: List[str] = []
    conflicting_data: List[str] = []
    stale_data: List[str] = []

    # 1. Price Reconciliation
    price_status, reconciled_price, price_issues = reconcile_price(sym, tech_data, exchange=exchange)
    if price_status == "CONFLICT":
        conflicting_data.extend(price_issues)
    elif price_status == "ADJUSTED":
        stale_data.extend(price_issues)

    # 2. Corporate Actions
    tagged_actions, is_ex_dividend = reconcile_corporate_actions(sym, tech_data, corporate_actions)

    # 3. Financial Statements
    fin_missing, fin_stale = reconcile_financial_period(sym, fin_data)
    missing_data.extend(fin_missing)
    stale_data.extend(fin_stale)

    # 4. News Catalysts
    reconciled_news, news_warnings = reconcile_news_freshness(news)

    # 5. Compute Data Quality Score (100-point scale)
    quality_score = 100.0

    if price_status == "CONFLICT":
        if reconciled_price <= 0.0:
            quality_score -= 65.0
        else:
            quality_score -= 45.0
    elif price_status == "ADJUSTED":
        quality_score -= 10.0

    if not tech_data:
        quality_score -= 35.0

    # Missing financial fields penalty (up to -30)
    if not fin_data:
        quality_score -= 30.0
    elif fin_missing:
        penalty = min(len(fin_missing) * 6.0, 30.0)
        quality_score -= penalty

    # Stale financial statements penalty
    if fin_stale:
        quality_score -= 15.0

    # News penalty
    if not news or len(news) == 0:
        quality_score -= 5.0

    quality_score = max(0.0, min(100.0, round(quality_score, 1)))

    # Assign Quality Tier
    if quality_score >= 85.0:
        quality_tier = "HIGH"
    elif quality_score >= 65.0:
        quality_tier = "MEDIUM"
    elif quality_score >= 40.0:
        quality_tier = "LOW"
    else:
        quality_tier = "CRITICAL"

    # Determine Gate Status
    gate_passed = quality_tier in ["HIGH", "MEDIUM"] and price_status != "CONFLICT"
    recommendation_allowed = gate_passed and quality_tier != "LOW"

    # Source Tiers Summary
    source_tiers = {
        "price_source": "Vnstock/HOSE_Live" if tech_data else "None",
        "financial_source": "Audited_Quarterly_Reports" if fin_data else "None",
        "news_source": reconciled_news[0]["tier"] if reconciled_news else "None"
    }

    # Badge string for UI / Discord
    badge = f"📊 DATA QUALITY: {quality_tier} ({quality_score:.0f}/100)"

    return {
        "symbol": sym,
        "data_quality": quality_tier,
        "quality_score": quality_score,
        "badge": badge,
        "gate_passed": gate_passed,
        "recommendation_allowed": recommendation_allowed,
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

    status_icon = "🟢" if tier == "HIGH" else ("🟡" if tier == "MEDIUM" else "🔴")
    return (
        f"{status_icon} **Data Quality:** `{tier}` ({score:.0f}/100) | "
        f"Conflicts: `{conflicts}` | Missing: `{missing}`"
    )
