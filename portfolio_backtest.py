"""portfolio_backtest.py

Chạy Backtest Cấp Độ Danh Mục (Portfolio Level) để kiểm định Tầng 0 (Regime Gate).
So sánh danh mục khi:
  - NO_GATE: Mua theo tín hiệu kỹ thuật cơ bản (Quant Core), không quan tâm vĩ mô.
  - REGIME_GATE: Kích hoạt Macro Circuit Breaker (Cash Mode) khi VN-Index vào Downtrend.

Cách chạy:
    python portfolio_backtest.py --start 2018-01-01 --end 2024-12-31
"""

import argparse
import logging
import os
import pandas as pd
import numpy as np


from data_engine import BROAD_MARKET_POOL
from replay_contrarian_v2 import load_history
from regime_classifier import classify_market_regime, METHOD_MA200_HYSTERESIS
from backtest_engine import RegimeBacktestEngine, _generate_quant_core_signals, _calculate_cagr, _calculate_drawdown

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="2018-01-01")
    ap.add_argument("--end", default=pd.Timestamp.today().strftime("%Y-%m-%d"))
    ap.add_argument("--cache-dir", default="data/replay_cache")
    args = ap.parse_args()

    logging.basicConfig(level=logging.WARNING)

    print("=" * 80)
    print("PORTFOLIO LEVEL BACKTEST (TẦNG 0 - REGIME GATE)")
    print(f"Giai đoạn: {args.start} -> {args.end}")
    print("=" * 80)

    # 1. Tải dữ liệu VNINDEX và phân loại Regime
    print("Đang tải dữ liệu VN-Index và tính toán Regime...")
    bench_df = load_history("VNINDEX", args.start, args.end, args.cache_dir)
    if bench_df.empty:
        raise SystemExit("Không tải được VNINDEX.")
    
    bench_df = bench_df.set_index("time")
    regimes = classify_market_regime(bench_df, method=METHOD_MA200_HYSTERESIS)

    # Khởi tạo Dictionary để lưu Equity Curve của từng mã
    equity_no_gate = {}
    equity_with_gate = {}
    
    total_trades_no_gate = 0
    total_trades_with_gate = 0

    print(f"Bắt đầu chạy Backtest trên {len(BROAD_MARKET_POOL)} mã cổ phiếu...")
    
    # Engine backtest với vốn khởi điểm 100M VND cho mỗi mã
    INITIAL_CAP_PER_STOCK = 100_000_000.0
    engine = RegimeBacktestEngine(initial_capital=INITIAL_CAP_PER_STOCK)

    for sym in BROAD_MARKET_POOL:
        df = load_history(sym, args.start, args.end, args.cache_dir)
        if df.empty or len(df) < 100:
            continue
            
        df = df.set_index("time")
        
        # 2A. Backtest KHÔNG CÓ Gate
        sig_no_gate = _generate_quant_core_signals(
            df, f_score=7, mos_pct=20.0, z_score=2.5, 
            regimes=regimes, enforce_regime_gate=False
        )
        res_no_gate = engine.run_backtest(
            df_price=df, signals=sig_no_gate, regimes=regimes, 
            enforce_regime_gate=False
        )
        if not res_no_gate.equity_curve.empty:
            equity_no_gate[sym] = res_no_gate.equity_curve
            total_trades_no_gate += len([t for t in res_no_gate.trades if t.is_filled and t.exit_price is not None])

        # 2B. Backtest CÓ Gate
        sig_with_gate = _generate_quant_core_signals(
            df, f_score=7, mos_pct=20.0, z_score=2.5, 
            regimes=regimes, enforce_regime_gate=True
        )
        res_with_gate = engine.run_backtest(
            df_price=df, signals=sig_with_gate, regimes=regimes, 
            enforce_regime_gate=True
        )
        if not res_with_gate.equity_curve.empty:
            equity_with_gate[sym] = res_with_gate.equity_curve
            total_trades_with_gate += len([t for t in res_with_gate.trades if t.is_filled and t.exit_price is not None])

    # 3. Tổng hợp danh mục (Cộng gộp Equity Curve)
    if not equity_no_gate or not equity_with_gate:
        print("Không có dữ liệu hợp lệ để tổng hợp.")
        return

    # Gộp tất cả equity curves lại
    df_eq_no_gate = pd.DataFrame(equity_no_gate).fillna(method='ffill').fillna(INITIAL_CAP_PER_STOCK)
    df_eq_with_gate = pd.DataFrame(equity_with_gate).fillna(method='ffill').fillna(INITIAL_CAP_PER_STOCK)

    portfolio_eq_no_gate = df_eq_no_gate.sum(axis=1)
    portfolio_eq_with_gate = df_eq_with_gate.sum(axis=1)

    # 4. Tính toán Metrics
    cagr_no_gate = _calculate_cagr(portfolio_eq_no_gate) * 100
    dd_no_gate, rec_no_gate = _calculate_drawdown(portfolio_eq_no_gate)
    dd_no_gate *= 100

    cagr_with_gate = _calculate_cagr(portfolio_eq_with_gate) * 100
    dd_with_gate, rec_with_gate = _calculate_drawdown(portfolio_eq_with_gate)
    dd_with_gate *= 100

    print("\n" + "=" * 80)
    print("KẾT QUẢ TỔNG HỢP DANH MỤC (PORTFOLIO METRICS)")
    print("=" * 80)
    print(f"{'Metric':<25} | {'NO GATE (Buy & Hold Core)':<25} | {'WITH REGIME GATE (Cash Mode)'}")
    print("-" * 80)
    print(f"{'Tổng vốn ban đầu':<25} | {portfolio_eq_no_gate.iloc[0]:>20,.0f} đ | {portfolio_eq_with_gate.iloc[0]:>20,.0f} đ")
    print(f"{'Vốn cuối kỳ':<25} | {portfolio_eq_no_gate.iloc[-1]:>20,.0f} đ | {portfolio_eq_with_gate.iloc[-1]:>20,.0f} đ")
    print(f"{'CAGR (Lợi nhuận năm)':<25} | {cagr_no_gate:>24.2f}% | {cagr_with_gate:>24.2f}%")
    print(f"{'Max Drawdown (Sụt giảm)':<25} | {dd_no_gate:>24.2f}% | {dd_with_gate:>24.2f}%")
    print(f"{'Recovery Days (Hồi phục)':<25} | {rec_no_gate:>25} | {rec_with_gate:>25}")
    print(f"{'Tổng số lệnh (Trades)':<25} | {total_trades_no_gate:>25} | {total_trades_with_gate:>25}")
    print("=" * 80)
    
    print("\n* Kết luận: Nếu Max Drawdown của 'WITH REGIME GATE' giảm đáng kể so với 'NO GATE'")
    print("  trong khi CAGR không bị sụt giảm quá mạnh, thì Tầng 0 hoạt động cực kỳ hiệu quả như một lớp bảo hiểm.")

if __name__ == "__main__":
    main()
