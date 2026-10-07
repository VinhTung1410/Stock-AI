"""replay_contrarian.py

Replay LỊCH SỬ phần KỸ THUẬT của Contrarian Engine (Panic Score + Price Confirmation).
KHÔNG chạy gate cơ bản (FQ-Score, MoS) vì get_financial_ratios chỉ có BCTC mới nhất
và target đồng thuận bị hardcode, sẽ gây look-ahead bias. Gate cơ bản chỉ đánh giá bằng forward test.

Cách chạy (từ thư mục gốc project, cần mạng để tải dữ liệu lần đầu):
    python replay_contrarian.py --start 2018-01-01 --end 2024-12-31
    python replay_contrarian.py --symbols FPT HPG SSI --start 2020-01-01

Kết quả: data/replay_contrarian_events.csv + bảng tóm tắt in ra màn hình.

Mức sự kiện:
    ENTRY             panic >= 70 và price confirmation >= 60 (tương đương PANIC_BUY phần kỹ thuật)
    ELIGIBLE_NO_CONF  panic >= 70 nhưng chưa xác nhận đảo chiều
    WATCH             40 <= panic < 70

Entry = giá mở cửa phiên kế tiếp. Stop -8% (CONTRARIAN_STOP_LOSS_PCT), chỉ hiệu lực từ T+2 (quy tắc T+2.5).
"""

from __future__ import annotations

import argparse
import logging
import os
import time

import numpy as np
import pandas as pd

from contrarian_engine import CONTRARIAN_STOP_LOSS_PCT, ContrarianResult, _calculate_panic_score, _check_price_confirmation
from contrarian_features import compute_contrarian_features

HORIZONS = (5, 20, 60)
MAX_HOLD = 60
LEVEL_ENTRY, LEVEL_NOCONF, LEVEL_WATCH = "ENTRY", "ELIGIBLE_NO_CONF", "WATCH"


def load_history(symbol: str, start: str, end: str, cache_dir: str) -> pd.DataFrame:
    os.makedirs(cache_dir, exist_ok=True)
    path = os.path.join(cache_dir, f"{symbol}_{start}_{end}.csv")
    if os.path.exists(path):
        df = pd.read_csv(path, parse_dates=["time"])
    else:
        from data_engine import _fetch_history_with_fallback

        df = _fetch_history_with_fallback(symbol, start, end)
        if df is None or df.empty:
            return pd.DataFrame()
        df["time"] = pd.to_datetime(df["time"])
        df.to_csv(path, index=False)
        time.sleep(1.2)  # tránh rate limit vnstock
    return df.sort_values("time").reset_index(drop=True)


def _rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    return 100 - (100 / (1 + gain / loss.replace(0, np.nan)))


def _forward_outcome(df: pd.DataFrame, i: int, bench: pd.Series) -> dict | None:
    j0 = i + 1  # vào lệnh tại open phiên kế tiếp
    if j0 >= len(df):
        return None
    entry = float(df["open"].iloc[j0])
    if entry <= 0:
        return None
    end = min(j0 + MAX_HOLD, len(df) - 1)
    lows = df["low"].to_numpy(float)
    highs = df["high"].to_numpy(float)
    opens = df["open"].to_numpy(float)
    closes = df["close"].to_numpy(float)
    stop = entry * (1.0 - CONTRARIAN_STOP_LOSS_PCT)

    exit_idx, exit_px, stop_hit = end, closes[end], False
    for j in range(j0 + 2, end + 1):  # T+2.5: stop chỉ hiệu lực từ T+2
        if lows[j] <= stop:
            exit_idx, exit_px, stop_hit = j, min(stop, opens[j]), True
            break

    out = {
        "entry_price": round(entry, 2),
        "mae_pct": round((lows[j0 : end + 1].min() / entry - 1) * 100, 2),
        "mfe_pct": round((highs[j0 : end + 1].max() / entry - 1) * 100, 2),
        "stop_hit": stop_hit,
        "strat_ret": round((exit_px / entry - 1) * 100, 2),
    }
    dates = df["time"]
    b0 = bench.asof(dates.iloc[j0])
    for h in HORIZONS:
        k = j0 + h
        if k < len(df):
            ret = (closes[k] / entry - 1) * 100
            b1 = bench.asof(dates.iloc[k])
            out[f"ret_t{h}"] = round(ret, 2)
            out[f"alpha_t{h}"] = round(ret - (b1 / b0 - 1) * 100, 2) if b0 and b1 else np.nan
        else:
            out[f"ret_t{h}"] = np.nan
            out[f"alpha_t{h}"] = np.nan
    b_exit = bench.asof(dates.iloc[exit_idx])
    out["strat_alpha"] = round(out["strat_ret"] - (b_exit / b0 - 1) * 100, 2) if b0 and b_exit else np.nan
    return out


def scan_symbol(sym: str, df: pd.DataFrame, bench: pd.Series, args) -> list[dict]:
    close = df["close"].astype(float)
    ma20 = close.rolling(20).mean()
    rsi = _rsi(close)
    cand = np.where((rsi <= args.rsi_prefilter) & ma20.notna())[0]  # prefilter để chạy nhanh

    last_idx = {LEVEL_ENTRY: -999, LEVEL_NOCONF: -999, LEVEL_WATCH: -999}
    events: list[dict] = []
    for i in cand:
        if i < args.warmup:
            continue
        tech = {"rsi14": float(rsi.iloc[i]), "ma20": float(ma20.iloc[i]), "is_backtest": True}
        tech.update(compute_contrarian_features(df.iloc[: i + 1]))
        price = float(close.iloc[i])
        panic = _calculate_panic_score(price, tech)
        if panic < args.watch_score:
            continue
        res = ContrarianResult(symbol=sym, can_buy=False)
        confirmed = _check_price_confirmation(price, tech, res)
        if panic >= 70.0:
            level = LEVEL_ENTRY if confirmed else LEVEL_NOCONF
        else:
            level = LEVEL_WATCH
        if i - last_idx[level] < args.cooldown:
            continue
        outcome = _forward_outcome(df, i, bench)
        if outcome is None:
            continue
        last_idx[level] = i
        events.append(
            {
                "symbol": sym,
                "signal_date": df["time"].iloc[i].date(),
                "month": df["time"].iloc[i].strftime("%Y-%m"),
                "level": level,
                "panic_score": panic,
                "conf_score": res.metrics.get("price_confirmation_score", 0),
                "rsi": round(float(rsi.iloc[i]), 1),
                **outcome,
            }
        )
    return events


def cluster_bootstrap_ci(values: pd.Series, clusters: pd.Series, n_boot: int = 5000, seed: int = 42):
    """Bootstrap theo CỤM THÁNG: các mã cùng rơi trong 1 đợt hoảng loạn không phải mẫu độc lập."""
    df = pd.DataFrame({"v": values, "c": clusters}).dropna()
    if df.empty:
        return np.nan, np.nan, np.nan
    g = df.groupby("c")["v"].agg(["sum", "count"])
    sums, counts = g["sum"].to_numpy(), g["count"].to_numpy()
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(g), size=(n_boot, len(g)))
    means = sums[idx].sum(axis=1) / counts[idx].sum(axis=1)
    return float(df["v"].mean()), float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))


def summarize(ev: pd.DataFrame) -> None:
    print("\n" + "=" * 78)
    print("TÓM TẮT REPLAY KỸ THUẬT CONTRARIAN (alpha so với VN-Index, cùng khoảng nắm giữ)")
    print("=" * 78)
    for level in (LEVEL_ENTRY, LEVEL_NOCONF, LEVEL_WATCH):
        sub = ev[ev["level"] == level]
        n, n_clusters = len(sub), sub["month"].nunique()
        print(f"\n[{level}] số tín hiệu={n} | số cụm tháng độc lập={n_clusters}")
        if n == 0:
            continue
        for col, label in (("alpha_t20", "Alpha T+20"), ("alpha_t60", "Alpha T+60"), ("strat_alpha", "Alpha có stop -8%")):
            m, lo, hi = cluster_bootstrap_ci(sub[col], sub["month"])
            wr = (sub[col].dropna() > 0).mean() * 100 if sub[col].notna().any() else np.nan
            print(f"  {label:<18} mean={m:+.2f}%  CI95=[{lo:+.2f}, {hi:+.2f}]  win_rate={wr:.0f}%")
        print(f"  Stop -8% bị chạm: {sub['stop_hit'].mean() * 100:.0f}% | MAE trung vị: {sub['mae_pct'].median():.1f}%")
        if n_clusters < 30:
            print("  ⚠️ < 30 cụm độc lập: chỉ mô tả, không kết luận (ngưỡng ESS >= 30 của hệ thống).")
        else:
            print("  Đủ cụm để đọc CI. Chỉ tin nếu cận dưới CI95 > 0.")
    print("\nLưu ý: đây chỉ là phần kỹ thuật. Gate cơ bản (FQ-Score, MoS) cần forward test.")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", nargs="*", default=None, help="Mặc định: BROAD_MARKET_POOL")
    ap.add_argument("--start", default="2018-01-01")
    ap.add_argument("--end", default=pd.Timestamp.today().strftime("%Y-%m-%d"))
    ap.add_argument("--cooldown", type=int, default=20, help="Số phiên tối thiểu giữa 2 sự kiện cùng mã, cùng mức")
    ap.add_argument("--warmup", type=int, default=60)
    ap.add_argument("--watch-score", type=float, default=40.0)
    ap.add_argument("--rsi-prefilter", type=float, default=40.0)
    ap.add_argument("--cache-dir", default="data/replay_cache")
    ap.add_argument("--out", default="data/replay_contrarian_events.csv")
    args = ap.parse_args()
    logging.basicConfig(level=logging.WARNING)

    from data_engine import BROAD_MARKET_POOL

    symbols = [s.upper() for s in (args.symbols or BROAD_MARKET_POOL)]
    bench_df = load_history("VNINDEX", args.start, args.end, args.cache_dir)
    if bench_df.empty:
        raise SystemExit("Không tải được VNINDEX để làm benchmark.")
    bench = bench_df.set_index("time")["close"].astype(float)

    all_events: list[dict] = []
    for sym in symbols:
        df = load_history(sym, args.start, args.end, args.cache_dir)
        if df.empty or len(df) < args.warmup + MAX_HOLD:
            print(f"Bỏ qua {sym}: thiếu dữ liệu")
            continue
        ev = scan_symbol(sym, df, bench, args)
        print(f"{sym}: {len(ev)} sự kiện")
        all_events.extend(ev)

    if not all_events:
        print("Không có sự kiện nào. Kiểm tra lại ngưỡng hoặc dữ liệu.")
        return
    events = pd.DataFrame(all_events)
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    events.to_csv(args.out, index=False)
    print(f"\nĐã lưu {len(events)} sự kiện vào {args.out}")
    summarize(events)


if __name__ == "__main__":
    main()