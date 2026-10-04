import sys
import time
from collections import Counter

from contrarian_engine import evaluate_contrarian_gates
from data_engine import SECTOR_MAP, fetch_stock_technical, get_financial_ratios
from db_manager import save_decision_record

# Ensure UTF-8 output on Windows terminal
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

symbols = [
    "FPT", "GAS", "HPG", "MBB", "MSN", "MWG", "PNJ", "SSI", "STB", 
    "TCB", "VCB", "VHM", "VIC", "VNM", "VPB", "DXG", "DIG", "NVL"
]

def run_scan():
    print(f"=== BẮT ĐẦU LIVE SCAN TRÊN THỊ TRƯỜNG ({len(symbols)} MÃ) ===")
    watch_candidates = []
    blocked_records = []
    
    for i, sym in enumerate(symbols, 1):
        try:
            print(f"[{i}/{len(symbols)}] Đang phân tích {sym}...", end=" ", flush=True)
            tech_data = fetch_stock_technical(sym)
            if not tech_data:
                print("❌ Không lấy được dữ liệu kỹ thuật")
                continue
                
            current_price = float(tech_data.get("current_price", 0))
            fin_dict = get_financial_ratios(sym)
            sector = SECTOR_MAP.get(sym, fin_dict.get("industry", "Unknown") if fin_dict else "Unknown")
            
            res = evaluate_contrarian_gates(
                symbol=sym,
                current_price=current_price,
                tech_data=tech_data,
                fin_dict=fin_dict,
                sector=sector,
                macro_regime="UPTREND",
            )
            
            fq_score = res.metrics.get("f_score", "N/A")
            panic_score = res.metrics.get("panic_score", "N/A")
            rsi = tech_data.get("rsi14", "N/A")
            
            is_shadow = res.metrics.get("shadow_mode", True)
            if res.status == "PANIC_BUY":
                decision = "SHADOW_BUY" if is_shadow else "BUY"
                gate = "SHADOW_MODE" if is_shadow else "PASSED"
            elif res.status in ("NEAR_PANIC_WATCH", "EXTREME_FEAR_WATCH", "VALUATION_WATCH"):
                decision = "WATCH"
                gate = "CONTRARIAN_WATCH"
            else:
                decision = "REJECT"
                gate = res.blocked_by or "UNKNOWN"

            # Lưu vết vào decision_records (TASK-0074 Shadow Mode Trial)
            save_decision_record({
                "symbol": sym,
                "session": "SHADOW_TRIAL",
                "decision": decision,
                "primary_rejection_gate": gate,
                "rejection_reasons": res.blocking_reasons if res.status == "BLOCKED" else [res.setup_type or res.action_state or ""],
                "facts": {
                    "price": current_price,
                    "snapshot_price": current_price,
                    "mos_pct": res.mos_pct,
                    "rsi": rsi,
                    "fq_score": fq_score,
                    "panic_score": panic_score,
                    "contrarian_state": res.status,
                    "shadow_mode": is_shadow,
                }
            })

            if res.status != "BLOCKED":
                print(f"✅ {res.status} | Giá: {current_price:,.0f} | RSI: {rsi} | FQ: {fq_score} | Panic: {panic_score} | MoS: {res.mos_pct:+.1f}%")
                watch_candidates.append({
                    "symbol": sym,
                    "status": res.status,
                    "decision": decision,
                    "action": res.action_state,
                    "price": current_price,
                    "sector": sector,
                    "fq_score": fq_score,
                    "panic_score": panic_score,
                    "rsi": rsi,
                    "mos_pct": res.mos_pct,
                })
            else:
                reason = res.blocking_reasons[0] if res.blocking_reasons else "N/A"
                print(f"⛔ BLOCKED ({gate}) | Lý do: {reason[:60]}...")
                blocked_records.append({
                    "symbol": sym,
                    "gate": gate,
                    "reason": reason,
                    "rsi": rsi,
                    "fq_score": fq_score,
                })
                
            time.sleep(1.2)  # Tuân thủ rate limit API
        except Exception as e:
            print(f"⚠️ Lỗi: {e}")
            time.sleep(1)

    _print_scan_summary(watch_candidates, blocked_records, len(symbols))


def _print_scan_summary(watch_candidates: list, blocked_records: list, total_count: int) -> None:
    """In bảng tổng kết kết quả quét và cảnh báo phân phối gate."""
    print("\n" + "=" * 70)
    print("📊 KẾT QUẢ TỔNG HỢP LIVE SCAN")
    print("=" * 70)

    if watch_candidates:
        print(f"\n🎯 CÁC MÃ ĐẠT TIÊU CHUẨN THEO DÕI / WATCHLIST ({len(watch_candidates)} mã):")
        for c in watch_candidates:
            print(f"  👉 [{c['symbol']}] Trạng thái: {c['status']}")
            print(f"     + Ngành: {c['sector']} | Giá hiện tại: {c['price']:,.0f}")
            print(f"     + Điểm FQ: {c['fq_score']}/9 | RSI(14): {c['rsi']} | Panic Score: {c['panic_score']}/100")
            print(f"     + Biên an toàn (MoS): {c['mos_pct']:+.1f}%")
            print(f"     + Hành động: {c['action']}\n")
    else:
        print("\n👀 Không có mã nào kích hoạt trạng thái WATCH/BUY tại thời điểm quét.")

    print(f"\n🚫 PHÂN PHỐI LÝ DO BLOCK ({len(blocked_records)} mã bị chặn):")
    gate_counts = Counter(b["gate"] for b in blocked_records)
    for gate, count in gate_counts.most_common():
        pct = (count / len(blocked_records)) * 100 if blocked_records else 0
        print(f"  - {gate}: {count}/{len(blocked_records)} mã ({pct:.1f}%)")

    # Alarm check (TASK-0073)
    if len(gate_counts) == 1 and len(blocked_records) == total_count:
        first_gate = next(iter(gate_counts))
        print(f"\n⚠️ BÁO ĐỘNG (alarm_100pct_same_gate): 100% mã bị chặn cùng gate '{first_gate}'! Kiểm tra lại cấu hình.")
    else:
        print("\n✅ Phân phối lý do block đa dạng, hệ thống phân loại bình thường.")
    print("=" * 70)


if __name__ == "__main__":
    run_scan()

