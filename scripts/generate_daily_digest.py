"""Daily Quant Research Digest Generator.

Automates the end-to-end post-market quant reporting pipeline:
1. Syncs today's decision records & lifecycle events from DB (via export_today_csv.py).
2. Calculates forward returns and updates institutional benchmarks (via update_forward_returns.py).
3. Aggregates decisions, gate statistics, watchlist state transitions, and multi-cohort forward returns.
4. Outputs a single, ultra-dense Markdown briefing (reports/daily_digest_YYYYMMDD.md) optimized for Claude / AI Analyst research.
"""

from __future__ import annotations

import argparse
import glob
import json
import logging
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from typing import Any

import pandas as pd

# Windows UTF-8 Terminal Fix
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
LOGGER = logging.getLogger("daily_digest")

# SonarCloud S1192 Constants
SESSION_EOD = "EOD_CANONICAL"
DEC_BUY = "BUY"
DEC_WATCH = "WATCH"
DEC_REJECT = "REJECT"
COL_DECISION = "decision"
COL_SYMBOL = "symbol"
GATE_TECH = "TECH_CONFIRMATION"
GATE_RISK = "RISK_TRAP"
EVENT_WL_ADDED = "WATCHLIST_ADDED"


def get_default_vn_date() -> str:
    """Return current date in Vietnam timezone (UTC+7) formatted as YYYY-MM-DD."""
    vn_tz = timezone(timedelta(hours=7))
    return datetime.now(vn_tz).strftime("%Y-%m-%d")


def _run_sub_step(cmd: list[str], step_name: str) -> bool:
    """Execute a python sub-step safely via subprocess."""
    LOGGER.info("[*] Bước: %s -> %s", step_name, " ".join(cmd))
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", check=False)
        if res.returncode == 0:
            LOGGER.info("[✓] %s hoàn tất thành công.", step_name)
            return True
        LOGGER.warning("[!] %s cảnh báo (mã lỗi %d): %s", step_name, res.returncode, res.stderr[-300:] if res.stderr else "N/A")
        return False
    except Exception:
        LOGGER.exception("Lỗi bất thường khi thực thi %s", step_name)
        return False


def run_pipeline_sync(target_date: str, skip_export: bool, skip_returns: bool, sync_db: bool = True) -> None:
    """Run underlying synchronization scripts if not explicitly skipped."""
    py_exec = sys.executable

    if not skip_export:
        _run_sub_step([py_exec, os.path.join("scripts", "export_today_csv.py"), target_date], "Xuất CSV quyết định hôm nay")

    if not skip_returns:
        returns_cmd = [py_exec, os.path.join("scripts", "update_forward_returns.py"), "--up-to", target_date]
        if not sync_db:
            returns_cmd.append("--skip-db")
        step_name = "Cập nhật lợi nhuận đa kỳ & đồng bộ Supabase" if sync_db else "Cập nhật lợi nhuận đa kỳ"
        _run_sub_step(returns_cmd, step_name)


def _load_decision_records(target_date: str) -> pd.DataFrame:
    """Load decision_records CSV for the given target date."""
    date_code = target_date.replace("-", "")
    filename = f"decision_records_{date_code}.csv"
    if not os.path.exists(filename):
        LOGGER.warning("Không tìm thấy tệp %s", filename)
        return pd.DataFrame()
    return pd.read_csv(filename)


def _load_lifecycle_events(target_date: str) -> pd.DataFrame:
    """Load lifecycle_events CSV for the given target date."""
    date_code = target_date.replace("-", "")
    filename = f"lifecycle_events_{date_code}.csv"
    if not os.path.exists(filename):
        LOGGER.warning("Không tìm thấy tệp %s", filename)
        return pd.DataFrame()
    return pd.read_csv(filename)


def _extract_regime_and_version(dec_df: pd.DataFrame) -> dict[str, Any]:
    """Extract regime features, index status, and frozen logic versions."""
    res: dict[str, Any] = {
        "regime": "UNKNOWN",
        "vnindex_price": None,
        "vnindex_ma200": None,
        "vnindex_vs_ma200_pct": None,
        "logic_version": "v15.0_frozen_20261013",
        "model_version": "v15.0_post_fix",
        "git_sha": "unknown",
    }
    if dec_df.empty:
        return res

    sample = dec_df.iloc[0]
    res["logic_version"] = str(sample.get("logic_version") or res["logic_version"])
    res["model_version"] = str(sample.get("model_version") or res["model_version"])
    res["git_sha"] = str(sample.get("git_sha") or res["git_sha"])[:10]

    for _, row in dec_df.iterrows():
        raw_facts = row.get("facts")
        if not raw_facts or not isinstance(raw_facts, str):
            continue
        try:
            facts = json.loads(raw_facts)
            rf = facts.get("regime_features")
            if rf and isinstance(rf, dict):
                res["regime"] = rf.get("regime", res["regime"])
                res["vnindex_price"] = rf.get("vnindex_price")
                res["vnindex_ma200"] = rf.get("vnindex_ma200")
                res["vnindex_vs_ma200_pct"] = rf.get("vnindex_vs_ma200_pct")
                break
        except Exception:
            continue
    return res


def _compute_eod_decisions(dec_df: pd.DataFrame) -> dict[str, Any]:
    """Compute canonical EOD decision stats and gate distributions."""
    if dec_df.empty:
        return {"total": 0, "buy": 0, "watch": 0, "reject": 0, "gates": {}, "watch_symbols": []}

    if "session" in dec_df.columns:
        eod = dec_df[dec_df["session"] == SESSION_EOD]
    else:
        eod = pd.DataFrame()

    if eod.empty:
        eod = dec_df.drop_duplicates(subset=[COL_SYMBOL], keep="last")

    counts = eod[COL_DECISION].value_counts().to_dict() if COL_DECISION in eod.columns else {}
    gates = eod["primary_rejection_gate"].value_counts().head(5).to_dict() if "primary_rejection_gate" in eod.columns else {}

    watch_rows = eod[eod[COL_DECISION] == DEC_WATCH]
    watch_symbols = watch_rows[COL_SYMBOL].tolist() if not watch_rows.empty else []

    return {
        "total": len(eod),
        "buy": counts.get(DEC_BUY, 0),
        "watch": counts.get(DEC_WATCH, 0),
        "reject": counts.get(DEC_REJECT, 0),
        "gates": gates,
        "watch_symbols": watch_symbols,
    }


def _extract_watchlist_additions(lc_df: pd.DataFrame) -> list[str]:
    """Extract list of symbols added to watchlist from lifecycle events."""
    if lc_df.empty or "event_type" not in lc_df.columns:
        return []
    wl_events = lc_df[lc_df["event_type"] == EVENT_WL_ADDED]
    return sorted(list(wl_events[COL_SYMBOL].unique())) if not wl_events.empty else []


def _is_horizon_maturing_today(
    fwd_df: pd.DataFrame,
    horizon_num: int,
    target_date: str,
    vn_close_today: float | None,
    expected_exit_date: str | None,
) -> bool:
    """Check if a specific horizon (1, 3, 5) matured on target_date."""
    if not bool(fwd_df.get(f"matured_t{horizon_num}", pd.Series([False])).iloc[0]):
        return False

    # 1. Direct exit date column match
    ex_date = str(fwd_df.get(f"exit_date_t{horizon_num}", pd.Series([None])).iloc[0])
    if ex_date == target_date:
        return True

    # 1b. For T+1, entry_date_t1 is the executable entry / exit date
    if horizon_num == 1:
        t1_date = str(fwd_df.get("entry_date_t1", pd.Series([None])).iloc[0])
        if t1_date == target_date:
            return True

    # 2. Expected horizon date mapping match
    if expected_exit_date and expected_exit_date == target_date:
        return True

    # 3. Fallback: VN-Index close matching within tolerance
    if vn_close_today is not None and vn_close_today > 0:
        close_val = float(fwd_df.get(f"vn_close_t{horizon_num}", pd.Series([0.0])).iloc[0] or 0.0)
        if close_val > 0 and abs(close_val - vn_close_today) < 0.05:
            return True

    return False


def _inspect_cohort_maturity(fwd_df: pd.DataFrame, target_date: str, vn_close_today: float | None) -> list[dict[str, Any]]:
    """Inspect forward returns dataframe to detect which horizons matured on target_date."""
    results: list[dict[str, Any]] = []
    if fwd_df.empty or "entry_date_t0" not in fwd_df.columns:
        return results

    t0_date = str(fwd_df["entry_date_t0"].iloc[0])
    d_code = t0_date.replace("-", "")

    expected_h_dates: dict[int, str] = {}
    try:
        from scripts.enrich_forward_returns_valuation_events import TARGET_DATES_HORIZONS

        expected_h_dates = TARGET_DATES_HORIZONS.get(d_code, {})
    except Exception:
        pass

    for h in (1, 3, 5):
        exp_d = expected_h_dates.get(h)
        if _is_horizon_maturing_today(fwd_df, h, target_date, vn_close_today, exp_d):
            results.append(_calc_cohort_horizon_stats(fwd_df, t0_date, f"T+{h}", f"exec_t{h}_pct", f"excess_vs_universe_t{h}_pct"))

    return results


def _calc_cohort_horizon_stats(fwd_df: pd.DataFrame, t0_date: str, horizon: str, exec_col: str, excess_col: str) -> dict[str, Any]:
    """Calculate average executable return and universe excess return for a cohort horizon."""
    watch_sub = fwd_df[fwd_df[COL_DECISION] == DEC_WATCH]
    rej_sub = fwd_df[fwd_df[COL_DECISION] == DEC_REJECT]

    return {
        "cohort_t0": t0_date,
        "horizon": horizon,
        "watch_n": len(watch_sub),
        "watch_exec": float(watch_sub[exec_col].mean()) if not watch_sub.empty and exec_col in watch_sub else None,
        "watch_excess": float(watch_sub[excess_col].mean()) if not watch_sub.empty and excess_col in watch_sub else None,
        "rej_n": len(rej_sub),
        "rej_exec": float(rej_sub[exec_col].mean()) if not rej_sub.empty and exec_col in rej_sub else None,
        "rej_excess": float(rej_sub[excess_col].mean()) if not rej_sub.empty and excess_col in rej_sub else None,
    }


def _find_maturing_cohorts(target_date: str, vn_close_today: float | None) -> list[dict[str, Any]]:
    """Scan all canonical forward return files and find horizons maturing today."""
    fwd_files = sorted(glob.glob("canonical_forward_returns_*.csv"))
    cohort_stats: list[dict[str, Any]] = []

    for fpath in fwd_files:
        try:
            df = pd.read_csv(fpath)
            stats = _inspect_cohort_maturity(df, target_date, vn_close_today)
            cohort_stats.extend(stats)
        except Exception:
            LOGGER.exception("Lỗi khi đọc file forward returns: %s", fpath)

    # Sort so T+1 comes first, then T+3, then T+5
    cohort_stats.sort(key=lambda x: x.get("horizon", ""))
    return cohort_stats


def _format_markdown_report(
    target_date: str,
    regime: dict[str, Any],
    stats: dict[str, Any],
    watchlist_additions: list[str],
    cohorts: list[dict[str, Any]],
) -> str:
    """Assemble final clean Markdown briefing for Claude / AI Analyst."""
    lines: list[str] = [
        f"# DAILY QUANT RESEARCH BRIEFING — {target_date}",
        "",
        "### 1. BỐI CẢNH THỊ TRƯỜNG & HỆ THỐNG (REGIME CONTEXT)",
    ]

    p_val = f"{regime['vnindex_price']:.2f}" if regime["vnindex_price"] else "N/A"
    ma_val = f"{regime['vnindex_ma200']:.2f}" if regime["vnindex_ma200"] else "N/A"
    gap_val = f"{regime['vnindex_vs_ma200_pct']:+.2f}%" if regime["vnindex_vs_ma200_pct"] is not None else "N/A"

    lines.append(f"- **Market Regime:** `{regime['regime']}` (VN-Index: {p_val} | MA200: {ma_val} | vs MA200: {gap_val})")
    lines.append(f"- **System Freeze Version:** Logic `{regime['logic_version']}` | Model `{regime['model_version']}` | Commit `{regime['git_sha']}`")
    lines.append("")

    lines.append(f"### 2. QUYẾT ĐỊNH CUỐI PHIÊN HÔM NAY (EOD CANONICAL T0 - {stats['total']} MÃ)")
    tot = max(stats["total"], 1)
    b_pct = (stats["buy"] / tot) * 100
    w_pct = (stats["watch"] / tot) * 100
    r_pct = (stats["reject"] / tot) * 100

    lines.append(f"- **Phân bổ:** BUY: **{stats['buy']}** ({b_pct:.1f}%) | WATCH: **{stats['watch']}** ({w_pct:.1f}%) | REJECT: **{stats['reject']}** ({r_pct:.1f}%)")

    gates_str = ", ".join(f"`{k}`: {v}" for k, v in stats["gates"].items()) if stats["gates"] else "Không có"
    lines.append(f"- **Cổng loại trừ chính (Top Rejection Gates):** {gates_str}")

    wl_display = ", ".join(f"`{s}`" for s in watchlist_additions) if watchlist_additions else "Không có mã mới"
    lines.append(f"- **Mã chuyển trạng thái WATCHLIST hôm nay ({len(watchlist_additions)} mã):** {wl_display}")
    lines.append("")

    lines.append("### 3. ĐO LƯỜNG KẾT QUẢ ĐA KỲ (MULTI-COHORT FORWARD RETURNS ĐÁO HẠN HÔM NAY)")
    if cohorts:
        lines.append("| Kỳ hạn đáo hạn | Cohort gốc (T0) | Nhóm | Số lượng | Exec Return TB (%) | Excess vs Universe (55 mã đều, %) |")
        lines.append("| :--- | :---: | :---: | :---: | :---: | :---: |")
        for c in cohorts:
            w_exec = f"{c['watch_exec']:+.2f}%" if c["watch_exec"] is not None else "N/A"
            w_exc = f"{c['watch_excess']:+.2f}%" if c["watch_excess"] is not None else "N/A"
            r_exec = f"{c['rej_exec']:+.2f}%" if c["rej_exec"] is not None else "N/A"
            r_exc = f"{c['rej_excess']:+.2f}%" if c["rej_excess"] is not None else "N/A"

            lines.append(f"| **{c['horizon']}** đáo hạn hôm nay | {c['cohort_t0']} | **WATCH** | {c['watch_n']} | **{w_exec}** | **{w_exc}** |")
            lines.append(f"| | {c['cohort_t0']} | **REJECT** | {c['rej_n']} | **{r_exec}** | **{r_exc}** |")
        lines.append("")
        lines.append("*(Benchmark của cột Excess là trung bình đều toàn bộ 55 mã Universe: Excess = Return − Mean_Universe. Do đó hiệu số Excess giữa WATCH và REJECT bằng đúng hiệu số Exec thô.)*")
    else:
        lines.append("*Không có cohort nào chạm mốc đáo hạn T+1/T+3/T+5 trong phiên hôm nay.*")
    lines.append("")

    lines.append("### 4. BẤT THƯỜNG ĐỊNH LƯỢNG (ANOMALIES) & CÂU HỎI NGHIÊN CỨU CHO CLAUDE")
    # Heuristic checks
    reversed_excess = False
    if cohorts:
        for c in cohorts:
            if c["rej_excess"] is not None and c["watch_excess"] is not None and c["rej_excess"] > c["watch_excess"]:
                reversed_excess = True
                break

    q_idx = 1
    if reversed_excess:
        lines.append(f"{q_idx}. **Hiện tượng Reversed Excess Return:** Nhóm `REJECT` sinh excess return cao hơn nhóm `WATCH` tại các mốc đáo hạn hôm nay. Hãy phân tích xem đây là hiệu ứng bật nảy kỹ thuật (Beta/Oversold rally) của nhóm đầu cơ hay do nhóm cơ bản tốt bị đè giá trong Downtrend?")
        q_idx += 1

    if stats["buy"] == 0 and stats["watch"] > 0:
        lines.append(f"{q_idx}. **Hiệu quả phòng vệ của cổng Kỹ thuật (`{GATE_TECH}`):** Hệ thống chặn 100% lệnh MUA (BUY = 0) và đưa {stats['watch']} mã vào diện theo dõi (WATCH). Kiểm tra xem kỷ luật này đã giúp tránh được bao nhiêu % thua lỗ trước đà rơi của thị trường?")
        q_idx += 1

    lines.append(f"{q_idx}. **Hành động tiếp theo:** Với danh sách {len(watchlist_additions)} mã trong Watchlist, nhóm ngành nào (Bank, Bất động sản, Sản xuất) có xác suất xác nhận ngừng rơi sớm nhất?")
    lines.append("")
    return "\n".join(lines)


def generate_digest(
    target_date: str,
    skip_sync: bool = False,
    skip_export: bool = False,
    skip_returns: bool = False,
    sync_db: bool = True,
    output_dir: str = "reports",
) -> str:
    """Generate daily research digest end-to-end and save to file."""
    LOGGER.info("=== BẮT ĐẦU TẠO BÁO CÁO DAILY RESEARCH DIGEST CHO NGÀY: %s ===", target_date)

    # 1. Pipeline Sync
    if not skip_sync:
        run_pipeline_sync(target_date, skip_export=skip_export, skip_returns=skip_returns, sync_db=sync_db)

    # 2. Data Load & Processing
    dec_df = _load_decision_records(target_date)
    lc_df = _load_lifecycle_events(target_date)

    regime = _extract_regime_and_version(dec_df)
    decision_stats = _compute_eod_decisions(dec_df)
    wl_additions = _extract_watchlist_additions(lc_df)

    # Try extracting today's VN-Index close from forward return files or regime
    vn_close_today: float | None = None
    fwd_today_path = f"canonical_forward_returns_{target_date.replace('-', '')}.csv"
    if os.path.exists(fwd_today_path):
        try:
            today_fwd = pd.read_csv(fwd_today_path)
            if "vn_close_t0" in today_fwd.columns and not today_fwd.empty:
                vn_close_today = float(today_fwd["vn_close_t0"].iloc[0])
        except Exception:
            pass

    if vn_close_today is None:
        # Fallback to checking previous cohort file T1 close
        for f in glob.glob("canonical_forward_returns_*.csv"):
            try:
                cf = pd.read_csv(f)
                if cf.get("entry_date_t1", pd.Series([None])).iloc[0] == target_date:
                    vn_close_today = float(cf["vn_close_t1"].iloc[0])
                    break
            except Exception:
                continue

    cohort_stats = _find_maturing_cohorts(target_date, vn_close_today)

    # 3. Assemble Markdown Report
    report_content = _format_markdown_report(target_date, regime, decision_stats, wl_additions, cohort_stats)

    # 4. Save Output
    os.makedirs(output_dir, exist_ok=True)
    date_code = target_date.replace("-", "")
    out_file = os.path.join(output_dir, f"daily_digest_{date_code}.md")
    with open(out_file, "w", encoding="utf-8") as f:
        f.write(report_content)

    LOGGER.info("[✓] ĐÃ TẠO BÁO CÁO THÀNH CÔNG: %s (%d dòng)", out_file, len(report_content.splitlines()))
    return out_file


def main() -> None:
    """CLI Entrypoint."""
    parser = argparse.ArgumentParser(description="Automated Daily Quant Research Digest Generator.")
    parser.add_argument("date", nargs="?", default=None, help="Target date in YYYY-MM-DD or YYYYMMDD format. Default is today.")
    parser.add_argument("--date", "-d", dest="flag_date", default=None, help="Explicit target date flag.")
    parser.add_argument("--skip-sync", action="store_true", help="Skip running export_today_csv and update_forward_returns.")
    parser.add_argument("--skip-export", action="store_true", help="Skip running export_today_csv.")
    parser.add_argument("--skip-returns", action="store_true", help="Skip running update_forward_returns.")
    parser.add_argument("--skip-db", "--no-db", dest="skip_db", action="store_true", help="Bỏ qua cập nhật bảng Supabase DB.")
    parser.add_argument("--sync-db", dest="sync_db", action="store_true", default=None, help="Đồng bộ kết quả forward returns lên Supabase (mặc định bật).")
    parser.add_argument("--output-dir", default="reports", help="Output directory for reports (default: reports).")
    args = parser.parse_args()

    raw_date = args.flag_date or args.date or get_default_vn_date()
    raw_date = raw_date.strip()
    if len(raw_date) == 8 and raw_date.isdigit():
        target_date = f"{raw_date[:4]}-{raw_date[4:6]}-{raw_date[6:]}"
    else:
        target_date = raw_date

    sync_db_flag = False if args.skip_db else True

    out_path = generate_digest(
        target_date=target_date,
        skip_sync=args.skip_sync,
        skip_export=args.skip_export,
        skip_returns=args.skip_returns,
        sync_db=sync_db_flag,
        output_dir=args.output_dir,
    )
    print("\n" + "=" * 70)
    print(f"📄 BÁO CÁO ĐÃ SẴN SÀNG CHO CLAUDE: {out_path}")
    print("=" * 70)


if __name__ == "__main__":
    main()
