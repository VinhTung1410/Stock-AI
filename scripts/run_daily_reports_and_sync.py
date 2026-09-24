import logging
import os
import sys

# Configure UTF-8 encoding for Windows terminal
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

from data_engine import (
    evaluate_portfolio,
    evaluate_watchlist,
    group_watchlist_by_sector,
    load_portfolio,
    load_watchlist,
    prune_unsuitable_watchlist,
    sync_auto_watchlist,
)
from quant_valuation import get_stock_archetype_details
from trading_bot import (
    _audit_portfolio_risk,
    _scan_watchlist_opportunities,
    get_vn_time,
    sent_alerts,
    trigger_post_market_audit,
    trigger_scheduled_report,
)

COL_MA_CP = "Mã CP"


def _check_portfolio_status() -> None:
    """Print current portfolio holding status and risk parameters."""
    print("\n" + "-" * 60)
    print("💼 1. KIỂM TRA TRẠNG THÁI DANH MỤC NẮM GIỮ (PORTFOLIO)")
    print("-" * 60)
    portfolio = load_portfolio()
    df_eval = evaluate_portfolio(portfolio)
    if df_eval is not None and not df_eval.empty:
        for _, row in df_eval.iterrows():
            sym = row.get(COL_MA_CP) or row.get("symbol")
            cp = float(row.get("Giá vốn (k)") or row.get("cost_price", 0.0))
            curr = float(row.get("Thị giá (k)") or row.get("current_price", 0.0))
            pnl_pct = float(row.get("Lãi/Lỗ (%)") or row.get("pnl_pct", 0.0))
            ma20_status = str(row.get("Vị thế MA20", "N/A"))
            arch_info = get_stock_archetype_details(sym)
            arch_name = arch_info.get("archetype")
            shield = "🛡️ BẬT (Holding Shield)" if arch_info.get("holding_shield") else "Thường"
            print(
                f"  • {sym}: Giá vốn {cp:.2f} | Thị giá {curr:.2f} | PnL: {pnl_pct:+.2f}% | "
                f"MA20: {ma20_status} | Archetype: {arch_name} | Khiên bảo vệ: {shield}"
            )
    else:
        print("  ⚠️ Không có dữ liệu đánh giá danh mục.")


def _print_pruned_watchlist_report(pruned_tickers: list[dict]) -> None:
    """Print results of watchlist pruning."""
    if pruned_tickers:
        print(f"  ❌ ĐÃ LOẠI BỎ {len(pruned_tickers)} CỔ PHIẾU KHỎI WATCHLIST:")
        for pt in pruned_tickers:
            print(f"    - Mã {pt['symbol']}: {pt.get('reason')} (Giá: {pt.get('current_price')}k, RSI: {pt.get('rsi14')})")
    else:
        print("  ✅ Không có mã nào vi phạm tiêu chí quá nóng (RSI > 75) hay bẫy giá cần loại bỏ.")


def _print_added_watchlist_report(added_tickers: set[str], wl_after: list[dict]) -> None:
    """Print results of newly discovered and added watchlist tickers."""
    if added_tickers:
        print(f"  ➕ ĐÃ BỔ SUNG {len(added_tickers)} CỔ PHIẾU MỚI VÀO WATCHLIST:")
        for sym in sorted(added_tickers):
            arch_info = get_stock_archetype_details(sym)
            item = next((x for x in wl_after if x.get("symbol") == sym), {})
            print(
                f"    + Mã {sym} ({item.get('sector', 'N/A')}): Archetype={arch_info.get('archetype')} | "
                f"Lý do: {item.get('reason', 'N/A')}"
            )
    else:
        print("  ℹ️ Watchlist đã đồng bộ đầy đủ các mã tiềm năng hiện tại.")


def _print_watchlist_sectors_report(wl_after: list[dict]) -> None:
    """Evaluate and print sector breakdown of watchlist."""
    if not wl_after:
        return
    df_wl = evaluate_watchlist(wl_after)
    if df_wl is None or df_wl.empty:
        return
    sectors_dict = group_watchlist_by_sector(df_wl)
    print("\n🏢 PHÂN BỔ WATCHLIST THEO NGÀNH:")
    for sec, group_df in sectors_dict.items():
        syms = group_df[COL_MA_CP].tolist() if COL_MA_CP in group_df.columns else []
        print(f"  • {sec}: {', '.join(syms)}")


def _process_watchlist_sync() -> None:
    """Prune unsuitable tickers, sync auto watchlist opportunities, and display groupings."""
    print("\n" + "-" * 60)
    print("📋 2. KIỂM TOÁN & CẬP NHẬT WATCHLIST (LỌC BỎ & THÊM MỚI)")
    print("-" * 60)
    wl_before = load_watchlist()
    symbols_before = {item["symbol"] for item in wl_before}
    print(f"📌 Watchlist ban đầu ({len(symbols_before)} mã): {sorted(symbols_before)}")

    print("\n🧹 Đang quét thanh lọc (prune_unsuitable_watchlist)...")
    _, pruned_tickers = prune_unsuitable_watchlist()
    _print_pruned_watchlist_report(pruned_tickers)

    print("\n🔄 Đang quét bổ sung cổ phiếu tiềm năng (sync_auto_watchlist)...")
    sync_auto_watchlist()
    wl_after = load_watchlist()
    symbols_after = {item["symbol"] for item in wl_after}
    added_tickers = symbols_after - symbols_before
    _print_added_watchlist_report(added_tickers, wl_after)

    print(f"\n📌 Watchlist sau khi tối ưu ({len(symbols_after)} mã): {sorted(symbols_after)}")
    _print_watchlist_sectors_report(wl_after)


def _scan_signals(today_str: str) -> None:
    """Scan and dispatch portfolio risk warnings and watchlist buy opportunities."""
    print("\n" + "-" * 60)
    print("⚡ 3. QUÉT TÍN HIỆU THỰC TẾ (PORTFOLIO RISK & WATCHLIST BUY)")
    print("-" * 60)
    sent_alerts_before = len(sent_alerts)
    _audit_portfolio_risk(today_str)
    _scan_watchlist_opportunities(today_str)
    new_alerts_count = len(sent_alerts) - sent_alerts_before
    print(f"  ➜ Số tín hiệu mới được kích hoạt: {new_alerts_count}")


def _trigger_all_reports() -> None:
    """Trigger daily scheduled Discord DM and post-market reports."""
    print("\n" + "-" * 60)
    print("📤 4. PHÁT VÀ BẮN BÁO CÁO NGUYÊN NGÀY VỀ DISCORD DM & WEBHOOK")
    print("-" * 60)

    print("\n[BÁO CÁO 1] 🍱 Tạo và gửi BÁO CÁO PHIÊN TRƯA (11:30) - 5 CÂU HỎI CHIẾN LƯỢC...")
    trigger_scheduled_report("11:30", "BÁO CÁO CHIẾN LƯỢC PHIÊN TRƯA (CHIẾN LƯỢC V3 - 5 CÂU HỎI)")

    print("\n[BÁO CÁO 2] 📊 Tạo và gửi BÁO CÁO TỔNG KẾT PHIÊN ATC (14:45)...")
    trigger_scheduled_report("14:45", "BÁO CÁO TỔNG KẾT PHIÊN ATC (CHIẾN LƯỢC V3)")

    print("\n[BÁO CÁO 3] 🎯 Tạo và gửi BÁO CÁO KIỂM TOÁN TÍN HIỆU ALPHA (15:15)...")
    trigger_post_market_audit()


def run_full_daily_workflow():
    """Execute end-to-end daily portfolio audit, watchlist prune/sync, and alert dispatch."""
    print("=" * 80)
    print("🚀 BẮT ĐẦU QUY TRÌNH KIỂM TOÁN & CHẠY BÁO CÁO NGUYÊN NGÀY (DISCORD DM)")
    print("=" * 80)

    now_vn = get_vn_time()
    today_str = now_vn.strftime("%Y-%m-%d")
    print(f"🕒 Thời gian thực thi: {now_vn.strftime('%d/%m/%Y %H:%M:%S')} (Giờ VN)")

    _check_portfolio_status()
    _process_watchlist_sync()
    _scan_signals(today_str)
    _trigger_all_reports()

    print("\n" + "=" * 80)
    print("🏁 HOÀN TẤT TOÀN BỘ QUY TRÌNH KIỂM TOÁN & GỬI BÁO CÁO!")
    print("=" * 80)


if __name__ == "__main__":
    run_full_daily_workflow()
