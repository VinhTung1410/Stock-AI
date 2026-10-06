"""replay_contrarian_v2.py

Replay LỊCH SỬ phần KỸ THUẬT của Contrarian Engine. KHÔNG chạy gate cơ bản (FQ-Score, MoS)
vì sẽ dính look-ahead bias (BCTC mới nhất, target đồng thuận hardcode).

Khác v1:
  1. Logic có nhớ trạng thái: ENTRY_V2 = từng có panic >= 70 trong N phiên gần nhất
     VÀ hôm nay price-confirmation >= ngưỡng (v1 đòi cả hai cùng phiên nên ENTRY luôn = 0).
  2. Alpha điều chỉnh beta (beta rolling 120 phiên, point-in-time, co về 1 kiểu Blume).
  3. Hai nhóm đối chứng: CONTROL_RSI (RSI thấp nhưng panic < 40) và CONTROL_RANDOM (ngày ngẫu nhiên).
     Báo cáo hiệu số (mức tín hiệu - đối chứng) với CI bootstrap theo cụm.
  4. So sánh stop cố định -8% với stop cấu trúc (swing low 10 phiên - 0.5*ATR, giới hạn -5%..-12%).
  5. Bootstrap theo cụm QUÝ (mặc định) để giảm vấn đề cửa sổ T+60 chồng lấn.
  6. Tách TRAIN / TEST theo --split-date. Chỉ tune trên TRAIN, kết luận trên TEST.

Chạy:
    python replay_contrarian_v2.py --start 2018-01-01 --split-date 2022-01-01
    python replay_contrarian_v2.py --symbols FPT HPG SSI --start 2020-01-01

Mức sự kiện:
    ENTRY_V2        panic_max_{N}d >= 70 và conf_score >= --conf-threshold (mặc định 60)
    ENTRY_V2_LOOSE  panic_max_{N}d >= 70 và --loose-threshold <= conf_score < --conf-threshold
    PANIC70_ANY     panic hôm nay >= 70 (không xét xác nhận)
    WATCH           40 <= panic hôm nay < 70
    CONTROL_RSI     RSI <= 35 nhưng panic < 40
    CONTROL_RANDOM  ngày ngẫu nhiên cùng mã

Lưu ý: số kiểm định rất nhiều (mức x chỉ số x giai đoạn). Cận dưới CI sát 0 dễ là ngẫu nhiên.
"""

from __future__ import annotations

import argparse
import logging
import os
import time

import numpy as np
import pandas as pd

from contrarian_engine import (
    CONTRARIAN_STOP_LOSS_PCT,
    ContrarianResult,
    _calculate_panic_score,
    _check_price_confirmation,
)
from contrarian_features import compute_contrarian_features

HORIZONS = (5, 20, 60)
MAX_HOLD = 60
STRUCT_STOP_MIN_PCT = 0.05  # stop cấu trúc xa entry tối thiểu 5%
STRUCT_STOP_MAX_PCT = 0.12  # và tối đa 12% (cùng giới hạn calculate_structural_stop_loss)

L_V2, L_LOOSE, L_P70, L_WATCH = "ENTRY_V2", "ENTRY_V2_LOOSE", "PANIC70_ANY", "WATCH"
C_RSI, C_RAND = "CONTROL_RSI", "CONTROL_RANDOM"
EVENT_LEVELS = (L_V2, L_LOOSE, L_P70, L_WATCH)
CONTROL_LEVELS = (C_RSI, C_RAND)

METRICS = (
    ("alpha_adj_t20", "Alpha(β) T+20"),
    ("alpha_adj_t60", "Alpha(β) T+60"),
    ("alpha_adj_fixed8", "Alpha(β) stop -8%"),
    ("alpha_adj_struct", "Alpha(β) stop cấu trúc"),
)
COMPARE_METRICS = ("alpha_adj_t20", "alpha_adj_t60", "alpha_adj_struct")


# ----------------------------------------------------------------------------- data
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
    return df.sort_values("time").drop_duplicates("time").reset_index(drop=True)


def _rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    return 100 - (100 / (1 + gain / loss.replace(0, np.nan)))


def _atr_array(df: pd.DataFrame, period: int = 14) -> np.ndarray:
    h, low, c = df["high"].astype(float), df["low"].astype(float), df["close"].astype(float)
    pc = c.shift(1)
    tr = pd.concat([h - low, (h - pc).abs(), (low - pc).abs()], axis=1).max(axis=1)
    return tr.rolling(period).mean().to_numpy()


def _rolling_beta(df: pd.DataFrame, bench_close: pd.Series, window: int = 120) -> np.ndarray:
    """Beta point-in-time (chỉ dùng dữ liệu đến hết phiên tín hiệu), co về 1 (Blume), kẹp [0.3, 2.5]."""
    b = bench_close.reindex(pd.DatetimeIndex(df["time"]), method="ffill")
    r_s = df["close"].astype(float).reset_index(drop=True).pct_change()
    r_b = pd.Series(b.to_numpy(float)).pct_change()
    beta = r_s.rolling(window, min_periods=60).cov(r_b) / r_b.rolling(window, min_periods=60).var()
    return (0.67 * beta + 0.33).clip(0.3, 2.5).fillna(1.0).to_numpy()


class Ctx:
    """Gói mảng giá của 1 mã để tính kết quả nhanh."""

    def __init__(self, df: pd.DataFrame, bench_open: pd.Series, bench_close: pd.Series):
        self.n = len(df)
        self.dates = df["time"].reset_index(drop=True)
        self.o = df["open"].to_numpy(float)
        self.h = df["high"].to_numpy(float)
        self.l = df["low"].to_numpy(float)
        self.c = df["close"].to_numpy(float)
        self.atr = _atr_array(df)
        self.beta = _rolling_beta(df, bench_close)
        self.bench_open = bench_open
        self.bench_close = bench_close

    def bench_ret(self, j_entry: int, j_exit: int) -> float:
        b0 = self.bench_open.asof(self.dates.iloc[j_entry])
        b1 = self.bench_close.asof(self.dates.iloc[j_exit])
        if pd.isna(b0) or pd.isna(b1) or b0 <= 0:
            return np.nan
        return (b1 / b0 - 1.0) * 100.0

    def simulate_exit(self, j0: int, end: int, stop: float) -> tuple[int, float, bool]:
        """Stop chỉ có hiệu lực từ T+2 (quy tắc T+2.5). Gap xuống dưới stop thì khớp tại giá mở cửa."""
        for j in range(j0 + 2, end + 1):
            if self.l[j] <= stop:
                return j, min(stop, self.o[j]), True
        return end, self.c[end], False


# ----------------------------------------------------------------------------- events
def build_event(sym: str, ctx: Ctx, i: int, level: str, panic: float, panic_max: float, conf: float, rsi_i: float):
    j0 = i + 1
    if j0 >= ctx.n:
        return None
    entry = float(ctx.o[j0])
    end = min(j0 + MAX_HOLD, ctx.n - 1)
    if entry <= 0 or end < j0 + 2:
        return None

    beta = float(ctx.beta[i])
    atr = ctx.atr[i] if np.isfinite(ctx.atr[i]) else entry * 0.03
    anchor = float(ctx.l[max(0, i - 9) : i + 1].min())
    cand = anchor - 0.5 * atr
    stop_struct = max(min(cand, entry * (1 - STRUCT_STOP_MIN_PCT)), entry * (1 - STRUCT_STOP_MAX_PCT))
    stops = {"fixed8": entry * (1.0 - CONTRARIAN_STOP_LOSS_PCT), "struct": stop_struct}

    ev: dict = {
        "symbol": sym,
        "signal_date": ctx.dates.iloc[i].date(),
        "level": level,
        "panic_score": panic,
        "panic_max_window": panic_max,
        "conf_score": conf,
        "rsi": round(float(rsi_i), 1),
        "beta": round(beta, 2),
        "entry_price": round(entry, 2),
        "mae_pct": round((ctx.l[j0 : end + 1].min() / entry - 1) * 100, 2),
        "mfe_pct": round((ctx.h[j0 : end + 1].max() / entry - 1) * 100, 2),
        "struct_stop_pct": round((stop_struct / entry - 1) * 100, 2),
    }
    for h in HORIZONS:
        k = j0 + h
        if k < ctx.n:
            ret = (ctx.c[k] / entry - 1) * 100
            b = ctx.bench_ret(j0, k)
            ev[f"ret_t{h}"] = round(ret, 2)
            ev[f"alpha_t{h}"] = round(ret - b, 2) if np.isfinite(b) else np.nan
            ev[f"alpha_adj_t{h}"] = round(ret - beta * b, 2) if np.isfinite(b) else np.nan
        else:
            ev[f"ret_t{h}"] = ev[f"alpha_t{h}"] = ev[f"alpha_adj_t{h}"] = np.nan
    for name, stop in stops.items():
        xi, xp, hit = ctx.simulate_exit(j0, end, stop)
        ret = (xp / entry - 1) * 100
        b = ctx.bench_ret(j0, xi)
        ev[f"ret_{name}"] = round(ret, 2)
        ev[f"alpha_adj_{name}"] = round(ret - beta * b, 2) if np.isfinite(b) else np.nan
        ev[f"hit_{name}"] = bool(hit)
    return ev


def scan_symbol(sym: str, df: pd.DataFrame, bench_open: pd.Series, bench_close: pd.Series, args) -> list[dict]:
    ctx = Ctx(df, bench_open, bench_close)
    close = df["close"].astype(float)
    ma20 = close.rolling(20).mean().to_numpy()
    rsi = _rsi(close).to_numpy()
    n = ctx.n

    feat_cache: dict[int, dict] = {}

    def tech_at(i: int) -> dict:
        if i not in feat_cache:
            t = {"rsi14": float(rsi[i]), "ma20": float(ma20[i]), "is_backtest": True}
            t.update(compute_contrarian_features(df.iloc[: i + 1]))
            feat_cache[i] = t
        return feat_cache[i]

    def conf_at(i: int) -> float:
        res = ContrarianResult(symbol=sym, can_buy=False)
        _check_price_confirmation(float(ctx.c[i]), tech_at(i), res)
        return float(res.metrics.get("price_confirmation_score", 0))

    # 1) Panic score cho mọi ngày RSI thấp (prefilter để chạy nhanh)
    panic_by_idx: dict[int, float] = {}
    for i in range(args.warmup, n - 2):
        if np.isfinite(rsi[i]) and np.isfinite(ma20[i]) and rsi[i] <= args.rsi_prefilter:
            panic_by_idx[i] = _calculate_panic_score(float(ctx.c[i]), tech_at(i))

    events: list[dict] = []
    last_idx: dict[str, int] = {}

    def emit(level: str, i: int, panic: float, panic_max: float, conf: float) -> None:
        if i - last_idx.get(level, -999) < args.cooldown:
            return
        ev = build_event(sym, ctx, i, level, panic, panic_max, conf, rsi[i])
        if ev is not None:
            last_idx[level] = i
            events.append(ev)

    # 2) Mức theo panic hôm nay: WATCH và PANIC70_ANY
    for i in sorted(panic_by_idx):
        p = panic_by_idx[i]
        if p >= 70.0:
            emit(L_P70, i, p, p, conf_at(i))
        elif p >= args.watch_score:
            emit(L_WATCH, i, p, p, conf_at(i))

    # 3) ENTRY_V2: panic >= 70 trong N phiên gần nhất + xác nhận hôm nay
    w = args.post_window
    window_days = sorted({k for p0, p in panic_by_idx.items() if p >= 70.0 for k in range(p0, p0 + w + 1) if k < n - 2})
    for i in window_days:
        pmax = max((panic_by_idx[k] for k in range(i - w, i + 1) if k in panic_by_idx), default=0.0)
        if pmax < 70.0 or not np.isfinite(ma20[i]):
            continue
        cs = conf_at(i)
        today_panic = panic_by_idx.get(i, np.nan)
        if cs >= args.conf_threshold:
            emit(L_V2, i, today_panic, pmax, cs)
        elif cs >= args.loose_threshold:
            emit(L_LOOSE, i, today_panic, pmax, cs)

    # 4) Đối chứng
    for i in sorted(panic_by_idx):
        if rsi[i] <= 35.0 and panic_by_idx[i] < args.watch_score:
            emit(C_RSI, i, panic_by_idx[i], panic_by_idx[i], np.nan)

    rng = np.random.default_rng(args.seed + sum(ord(ch) for ch in sym))
    pool = np.arange(args.warmup, max(args.warmup + 1, n - MAX_HOLD - 2))
    take = min(args.control_n, len(pool))
    for i in sorted(rng.choice(pool, size=take, replace=False)):
        ev = build_event(sym, ctx, int(i), C_RAND, np.nan, np.nan, np.nan, rsi[i] if np.isfinite(rsi[i]) else np.nan)
        if ev is not None:
            events.append(ev)
    return events


# ----------------------------------------------------------------------------- statistics
def cluster_ci(values: pd.Series, clusters: pd.Series, n_boot: int = 5000, seed: int = 42):
    df = pd.DataFrame({"v": values, "c": clusters}).dropna()
    if df.empty:
        return np.nan, np.nan, np.nan
    g = df.groupby("c")["v"].agg(["sum", "count"])
    sums, counts = g["sum"].to_numpy(), g["count"].to_numpy()
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(g), size=(n_boot, len(g)))
    means = sums[idx].sum(axis=1) / counts[idx].sum(axis=1)
    return float(df["v"].mean()), float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))


def diff_ci(a: pd.DataFrame, b: pd.DataFrame, col: str, n_boot: int = 5000, seed: int = 42):
    """CI95 của (mean_a - mean_b), bootstrap theo cụm trên hợp các cụm của hai nhóm."""
    da, db = a[[col, "cluster"]].dropna(), b[[col, "cluster"]].dropna()
    if da.empty or db.empty:
        return np.nan, np.nan, np.nan
    keys = sorted(set(da["cluster"]) | set(db["cluster"]))
    ga = da.groupby("cluster")[col].agg(["sum", "count"]).reindex(keys, fill_value=0)
    gb = db.groupby("cluster")[col].agg(["sum", "count"]).reindex(keys, fill_value=0)
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(keys), size=(n_boot, len(keys)))
    ca, sa = ga["count"].to_numpy()[idx].sum(1), ga["sum"].to_numpy()[idx].sum(1)
    cb, sb = gb["count"].to_numpy()[idx].sum(1), gb["sum"].to_numpy()[idx].sum(1)
    ok = (ca > 0) & (cb > 0)
    if ok.sum() < 200:
        return np.nan, np.nan, np.nan
    diffs = sa[ok] / ca[ok] - sb[ok] / cb[ok]
    point = float(da[col].mean() - db[col].mean())
    return point, float(np.percentile(diffs, 2.5)), float(np.percentile(diffs, 97.5))


def _print_level(sub: pd.DataFrame, level: str) -> None:
    n, k = len(sub), sub["cluster"].nunique()
    flag = "  ⚠️ <30 cụm: chỉ mô tả" if k < 30 else ""
    print(f"  [{level}] n={n} | cụm={k}{flag}")
    if n == 0:
        return
    for col, label in METRICS:
        m, lo, hi = cluster_ci(sub[col], sub["cluster"])
        s = sub[col].dropna()
        wr = (s > 0).mean() * 100 if len(s) else np.nan
        print(f"      {label:<24} mean={m:+6.2f}%  CI95=[{lo:+6.2f}, {hi:+6.2f}]  win={wr:3.0f}%")
    print(
        f"      Stop -8% chạm: {sub['hit_fixed8'].mean() * 100:.0f}% | stop cấu trúc chạm: "
        f"{sub['hit_struct'].mean() * 100:.0f}% (khoảng cách TB {sub['struct_stop_pct'].mean():.1f}%) | "
        f"MAE trung vị: {sub['mae_pct'].median():.1f}%"
    )


def summarize(ev: pd.DataFrame, split_date: str) -> None:
    ev = ev.copy()
    ev["period"] = np.where(pd.to_datetime(ev["signal_date"]) < pd.Timestamp(split_date), "TRAIN", "TEST")
    for period in ("TRAIN", "TEST", "ALL"):
        sub_p = ev if period == "ALL" else ev[ev["period"] == period]
        print("\n" + "=" * 86)
        print(f"GIAI ĐOẠN: {period}  (alpha điều chỉnh beta so với VN-Index)  | tổng sự kiện: {len(sub_p)}")
        print("=" * 86)
        for lv in EVENT_LEVELS + CONTROL_LEVELS:
            _print_level(sub_p[sub_p["level"] == lv], lv)

        print(f"\n  --- HIỆU SỐ so với đối chứng ({period}): mean(mức) - mean(đối chứng), CI95 theo cụm ---")
        for lv in EVENT_LEVELS:
            a = sub_p[sub_p["level"] == lv]
            for ctrl in CONTROL_LEVELS:
                b = sub_p[sub_p["level"] == ctrl]
                parts = []
                for col in COMPARE_METRICS:
                    m, lo, hi = diff_ci(a, b, col)
                    parts.append(f"{col.replace('alpha_adj_', '')}: {m:+.1f} [{lo:+.1f},{hi:+.1f}]")
                print(f"  {lv:<15} vs {ctrl:<15} " + " | ".join(parts))
    print(
        "\nCách đọc: chỉ tin một mức nếu (1) >= 30 cụm, (2) CI hiệu số so với CONTROL_RSI có cận dưới > 0 "
        "trên TEST, (3) kết quả cùng chiều trên TRAIN. Đây chỉ là phần kỹ thuật; gate cơ bản cần forward test."
    )


# ----------------------------------------------------------------------------- main
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", nargs="*", default=None, help="Mặc định: BROAD_MARKET_POOL")
    ap.add_argument("--start", default="2018-01-01")
    ap.add_argument("--end", default=pd.Timestamp.today().strftime("%Y-%m-%d"))
    ap.add_argument("--split-date", default="2022-01-01", help="Trước ngày này là TRAIN, từ ngày này là TEST")
    ap.add_argument("--cluster", choices=["quarter", "month"], default="quarter")
    ap.add_argument("--post-window", type=int, default=10, help="Số phiên nhìn lại tìm panic >= 70 cho ENTRY_V2")
    ap.add_argument("--conf-threshold", type=float, default=60.0)
    ap.add_argument("--loose-threshold", type=float, default=40.0)
    ap.add_argument("--cooldown", type=int, default=20)
    ap.add_argument("--warmup", type=int, default=60)
    ap.add_argument("--watch-score", type=float, default=40.0)
    ap.add_argument("--rsi-prefilter", type=float, default=40.0)
    ap.add_argument("--control-n", type=int, default=40, help="Số ngày ngẫu nhiên mỗi mã cho CONTROL_RANDOM")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--cache-dir", default="data/replay_cache")
    ap.add_argument("--out", default="data/replay_contrarian_events_v2.csv")
    args = ap.parse_args()
    logging.basicConfig(level=logging.WARNING)

    if args.symbols:
        symbols = [s.upper() for s in args.symbols]
    else:
        from data_engine import BROAD_MARKET_POOL

        symbols = list(BROAD_MARKET_POOL)

    bench_df = load_history("VNINDEX", args.start, args.end, args.cache_dir)
    if bench_df.empty:
        raise SystemExit("Không tải được VNINDEX để làm benchmark.")
    b = bench_df.set_index("time")
    bench_close = b["close"].astype(float)
    bench_open = (b["open"] if "open" in b.columns else b["close"]).astype(float)

    all_events: list[dict] = []
    for sym in symbols:
        df = load_history(sym, args.start, args.end, args.cache_dir)
        if df.empty or len(df) < args.warmup + MAX_HOLD:
            print(f"Bỏ qua {sym}: thiếu dữ liệu")
            continue
        ev = scan_symbol(sym, df, bench_open, bench_close, args)
        print(f"{sym}: {sum(e['level'] in EVENT_LEVELS for e in ev)} sự kiện, {sum(e['level'] in CONTROL_LEVELS for e in ev)} đối chứng")
        all_events.extend(ev)

    if not all_events:
        print("Không có sự kiện nào. Kiểm tra lại ngưỡng hoặc dữ liệu.")
        return
    events = pd.DataFrame(all_events)
    dt = pd.to_datetime(events["signal_date"])
    events["cluster"] = dt.dt.strftime("%Y-%m") if args.cluster == "month" else dt.dt.year.astype(str) + "Q" + dt.dt.quarter.astype(str)
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    events.to_csv(args.out, index=False)
    print(f"\nĐã lưu {len(events)} dòng vào {args.out}")
    summarize(events, args.split_date)


if __name__ == "__main__":
    main()