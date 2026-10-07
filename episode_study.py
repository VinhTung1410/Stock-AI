"""episode_study.py

Nghiên cứu contrarian theo PANIC EPISODE (1 episode = 1 cơ hội vào lệnh), thay vì từng ngày tín hiệu.

Gồm 3 phần:
  A. Dựng episode theo cổ phiếu, gắn nhãn cụm ở CẤP THỊ TRƯỜNG (MKT-yyyy-mm) hoặc IDIO-yyyyQq
     (cổ phiếu tự hoảng loạn khi thị trường bình thường). Bootstrap theo cụm này.
  B. ĐỐI CHỨNG TRONG EPISODE: với cùng cổ phiếu, cùng đợt panic, so sánh
        CONFIRM (ngày xác nhận đảo chiều đầu tiên)  vs  WINDOW (trung bình mọi ngày vào lệnh trong cửa sổ)
        FIRST   (ngày panic đầu tiên)                vs  WINDOW
        CONFIRM vs FIRST
     => đo giá trị của việc "chờ xác nhận" mà không bị nhiễu bởi regime hay survivorship.
  C. WALK-FORWARD MỞ RỘNG có EMBARGO: train [đầu dữ liệu, năm Y) -> test năm Y, cho Y trong --test-years.
     Mỗi fold chọn cấu hình (conf_threshold, post_window) trên TRAIN theo quy tắc cố định,
     áp lên TEST, rồi GỘP kết quả OOS để kiểm định (từng fold quá ít mẫu để kết luận).
     Đồng thời báo cáo cấu hình ĐÓNG BĂNG (60, 10) không qua chọn lựa.

Chạy (từ thư mục gốc project, cùng thư mục với replay_contrarian_v2.py và contrarian_features.py):
    python episode_study.py --start 2018-01-01 --test-years 2022 2023 2024 2025 2026
    python episode_study.py --symbols FPT HPG SSI --rolling-years 3

Quy ước tránh overfit:
  - Lưới tham số nhỏ, cố định trước: conf in {40,50,60} x post_window in {5,10,15} (9 cấu hình).
  - Số lần thử = 9 x số fold, được in ra. Đừng thêm cấu hình sau khi đã xem kết quả.
  - Chỉ số chọn cấu hình: trung bình (CONFIRM - WINDOW) của alpha(β) có stop cấu trúc trên TRAIN.
"""

from __future__ import annotations

import argparse
import itertools
import logging
import os

import numpy as np
import pandas as pd

from contrarian_engine import ContrarianResult, _calculate_panic_score, _check_price_confirmation
from contrarian_features import compute_contrarian_features
from replay_contrarian_v2 import Ctx, MAX_HOLD, _rsi, build_event, cluster_ci, load_history

OUT_COLS = ("alpha_adj_t20", "alpha_adj_t60", "alpha_adj_struct", "alpha_adj_fixed8", "mae_pct")
SHOW_COLS = ("alpha_adj_t20", "alpha_adj_t60", "alpha_adj_struct")
SELECT_COL = "alpha_adj_struct"
GRID_CONF = (40.0, 50.0, 60.0)
GRID_PW = (5, 10, 15)
MAX_PW = max(GRID_PW)
DEFAULT_CFG = (60.0, 10)


# ----------------------------------------------------------------------------- market episodes
def market_episodes(bench_close: pd.Series, dd_thr: float, lookback: int = 60, merge_gap: int = 20):
    """Các đợt VN-Index giảm >= |dd_thr|% so với đỉnh `lookback` phiên; gộp nếu cách nhau <= merge_gap phiên."""
    close = bench_close.dropna()
    dd = (close / close.rolling(lookback, min_periods=20).max() - 1.0) * 100.0
    flag = (dd <= dd_thr).to_numpy()
    spans, start, last = [], None, None
    for k, f in enumerate(flag):
        if not f:
            continue
        if start is None:
            start = k
        elif k - last > merge_gap:
            spans.append((start, last))
            start = k
        last = k
    if start is not None:
        spans.append((start, last))
    return [(close.index[a], close.index[b]) for a, b in spans]


def assign_cluster(date: pd.Timestamp, mkt_eps, pad_days: int) -> tuple[str, bool]:
    pad = pd.Timedelta(days=pad_days)
    for s, e in mkt_eps:
        if s - pad <= date <= e + pad:
            return f"MKT-{s:%Y-%m}", True
    return f"IDIO-{date.year}Q{(date.month - 1) // 3 + 1}", False


# ----------------------------------------------------------------------------- build episodes
def build_symbol_episodes(sym: str, df: pd.DataFrame, bench_open: pd.Series, bench_close: pd.Series, args) -> list[dict]:
    ctx = Ctx(df, bench_open, bench_close)
    close = df["close"].astype(float)
    ma20 = close.rolling(20).mean().to_numpy()
    rsi = _rsi(close).to_numpy()
    roll_max20 = close.rolling(20).max().to_numpy()
    n = ctx.n
    bench_dd20 = (bench_close / bench_close.rolling(20, min_periods=5).max() - 1.0) * 100.0

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

    panic_by_idx: dict[int, float] = {}
    trig: list[int] = []
    for i in range(args.warmup, n - 2):
        if np.isfinite(rsi[i]) and np.isfinite(ma20[i]) and rsi[i] <= args.rsi_prefilter:
            p = _calculate_panic_score(float(ctx.c[i]), tech_at(i))
            panic_by_idx[i] = p
            if p >= args.trigger_score:
                trig.append(i)

    groups: list[list[int]] = []
    for i in trig:
        if groups and i - groups[-1][-1] <= args.gap:
            groups[-1].append(i)
        else:
            groups.append([i])

    episodes: list[dict] = []
    for gi, g in enumerate(groups):
        start, last = g[0], g[-1]
        next_start = groups[gi + 1][0] if gi + 1 < len(groups) else n
        hi = min(last + MAX_PW, next_start - 1, n - 3)
        days: dict[int, dict] = {}
        for i in range(start, hi + 1):
            ev = build_event(sym, ctx, i, "EP", panic_by_idx.get(i, np.nan), panic_by_idx.get(i, np.nan), conf_at(i), rsi[i])
            if ev is not None:
                days[i] = ev
        if start not in days:
            continue
        start_date = ctx.dates.iloc[start]
        stock_dd = (close.iloc[start] / roll_max20[start] - 1.0) * 100.0
        mkt_dd = bench_dd20.asof(start_date)
        beta = float(ctx.beta[start])
        episodes.append(
            {
                "symbol": sym,
                "start": start,
                "last": last,
                "start_date": start_date,
                "panic_max": max(panic_by_idx[i] for i in g),
                "n_trigger": len(g),
                "stock_dd20": round(float(stock_dd), 2),
                "market_dd20": round(float(mkt_dd), 2) if pd.notna(mkt_dd) else np.nan,
                "idio_dd20": round(float(stock_dd - beta * mkt_dd), 2) if pd.notna(mkt_dd) else np.nan,
                "beta": round(beta, 2),
                "days": days,
            }
        )
    return episodes


def _nanmean(vals) -> float:
    a = np.asarray(vals, dtype=float)
    a = a[np.isfinite(a)]
    return float(a.mean()) if len(a) else np.nan


def derive_rows(episodes: list[dict], conf_thr: float, pw: int, mkt_eps, pad_days: int) -> pd.DataFrame:
    """Với cấu hình (conf_thr, post_window), dựng bảng 1 dòng / episode kèm các hiệu số theo cặp."""
    rows = []
    for ep in episodes:
        end = ep["last"] + pw
        idxs = [i for i in sorted(ep["days"]) if i <= end]
        first = ep["days"].get(ep["start"])
        if not idxs or first is None:
            continue
        conf_idx = next((i for i in idxs if ep["days"][i]["conf_score"] >= conf_thr), None)
        conf_ev = ep["days"][conf_idx] if conf_idx is not None else None
        cluster, is_mkt = assign_cluster(ep["start_date"], mkt_eps, pad_days)
        row = {
            "symbol": ep["symbol"],
            "start_date": ep["start_date"],
            "cluster": cluster,
            "is_market": is_mkt,
            "panic_max": ep["panic_max"],
            "n_trigger": ep["n_trigger"],
            "window_days": len(idxs),
            "has_confirm": conf_ev is not None,
            "confirm_offset": (conf_idx - ep["start"]) if conf_idx is not None else np.nan,
            "stock_dd20": ep["stock_dd20"],
            "market_dd20": ep["market_dd20"],
            "idio_dd20": ep["idio_dd20"],
            "conf_thr": conf_thr,
            "post_window": pw,
        }
        for c in OUT_COLS:
            win = _nanmean([ep["days"][i][c] for i in idxs])
            f = first[c]
            cv = conf_ev[c] if conf_ev is not None else np.nan
            row[f"win_{c}"], row[f"first_{c}"], row[f"conf_{c}"] = win, f, cv
            row[f"d_conf_win_{c}"] = cv - win if np.isfinite(cv) and np.isfinite(win) else np.nan
            row[f"d_first_win_{c}"] = f - win if np.isfinite(f) and np.isfinite(win) else np.nan
            row[f"d_conf_first_{c}"] = cv - f if np.isfinite(cv) and np.isfinite(f) else np.nan
        rows.append(row)
    return pd.DataFrame(rows)


# ----------------------------------------------------------------------------- reporting
def _line(label: str, s: pd.Series, cl: pd.Series) -> str:
    m, lo, hi = cluster_ci(s, cl)
    n = int(s.notna().sum())
    return f"{label:<34} n={n:<4} mean={m:+6.2f}  CI95=[{lo:+6.2f}, {hi:+6.2f}]"


def print_group(df: pd.DataFrame, title: str) -> None:
    n, k = len(df), df["cluster"].nunique()
    flag = "  ⚠️ <30 cụm: chỉ mô tả" if k < 30 else ""
    print(f"\n  [{title}] episode={n} | cụm={k} | có xác nhận={df['has_confirm'].mean() * 100:.0f}%{flag}")
    if n == 0:
        return
    for c in SHOW_COLS:
        print(f"    -- {c}")
        print("      " + _line("FIRST (ngày panic đầu)", df[f"first_{c}"], df["cluster"]))
        print("      " + _line("CONFIRM (ngày xác nhận)", df[f"conf_{c}"], df["cluster"]))
        print("      " + _line("WINDOW (TB mọi ngày trong cửa sổ)", df[f"win_{c}"], df["cluster"]))
        print("      " + _line("Δ CONFIRM - WINDOW", df[f"d_conf_win_{c}"], df["cluster"]))
        print("      " + _line("Δ FIRST   - WINDOW", df[f"d_first_win_{c}"], df["cluster"]))
        print("      " + _line("Δ CONFIRM - FIRST", df[f"d_conf_first_{c}"], df["cluster"]))


def section_a(episodes, mkt_eps, args) -> pd.DataFrame:
    conf, pw = DEFAULT_CFG
    rows = derive_rows(episodes, conf, pw, mkt_eps, args.pad_days)
    print("\n" + "=" * 88)
    print(f"A+B. EPISODE & ĐỐI CHỨNG TRONG EPISODE (cấu hình đóng băng: conf>={conf:.0f}, post_window={pw})")
    print("=" * 88)
    print(f"Số đợt stress của thị trường phát hiện được (VN-Index <= {args.mkt_dd}%): {len(mkt_eps)}")
    for s, e in mkt_eps:
        print(f"   MKT-{s:%Y-%m}: {s:%Y-%m-%d} -> {e:%Y-%m-%d}")
    print_group(rows, "TẤT CẢ")
    print_group(rows[rows["is_market"]], "EPISODE THEO THỊ TRƯỜNG")
    print_group(rows[~rows["is_market"]], "EPISODE ĐỘC LẬP CỔ PHIẾU (IDIO)")
    if rows["idio_dd20"].notna().sum() > 10:
        med = rows["idio_dd20"].median()
        print(f"\n  Tách theo mức giảm riêng của mã (idio_dd20 trung vị = {med:.1f}%):")
        print_group(rows[rows["idio_dd20"] <= med], "idio_dd20 SÂU (riêng mã giảm mạnh)")
        print_group(rows[rows["idio_dd20"] > med], "idio_dd20 NÔNG (chủ yếu do thị trường)")
    return rows


def section_c(episodes, mkt_eps, args) -> None:
    grid = list(itertools.product(GRID_CONF, GRID_PW))
    derived = {cfg: derive_rows(episodes, cfg[0], cfg[1], mkt_eps, args.pad_days) for cfg in grid}
    embargo = pd.Timedelta(days=args.embargo_days)
    mode = f"rolling {args.rolling_years}Y" if args.rolling_years else "expanding (mở rộng)"
    print("\n" + "=" * 88)
    print(f"C. WALK-FORWARD {mode} | embargo={args.embargo_days} ngày | lưới={len(grid)} cấu hình")
    print("=" * 88)
    print(f"{'Test':<6}{'Train(eps/conf)':<17}{'Cấu hình chọn':<16}{'Δ train':>9}{'Test(eps/conf)':>16}{'Δ test chọn':>13}{'Δ test đóng băng':>18}")

    chosen_rows, frozen_rows = [], []
    for y in args.test_years:
        t0, t1 = pd.Timestamp(f"{y}-01-01"), pd.Timestamp(f"{y + 1}-01-01")
        lo = pd.Timestamp(f"{y - args.rolling_years}-01-01") if args.rolling_years else pd.Timestamp.min
        cut = t0 - embargo

        def split(df: pd.DataFrame):
            tr = df[(df["start_date"] >= lo) & (df["start_date"] < cut)]
            te = df[(df["start_date"] >= t0) & (df["start_date"] < t1)]
            return tr, te

        best_cfg, best_score, best_n = None, -np.inf, 0
        for cfg in grid:
            tr, _ = split(derived[cfg])
            s = tr[f"d_conf_win_{SELECT_COL}"].dropna()
            if len(s) >= args.min_train and s.mean() > best_score:
                best_cfg, best_score, best_n = cfg, float(s.mean()), len(s)
        fallback = best_cfg is None
        if fallback:
            best_cfg, best_score = DEFAULT_CFG, np.nan

        tr_all, _ = split(derived[best_cfg])
        _, te_ch = split(derived[best_cfg])
        _, te_fr = split(derived[DEFAULT_CFG])
        te_ch = te_ch.assign(fold=y)
        te_fr = te_fr.assign(fold=y)
        chosen_rows.append(te_ch)
        frozen_rows.append(te_fr)

        d_ch = te_ch[f"d_conf_win_{SELECT_COL}"].dropna()
        d_fr = te_fr[f"d_conf_win_{SELECT_COL}"].dropna()
        cfg_txt = f"{best_cfg[0]:.0f}/{best_cfg[1]}" + ("*" if fallback else "")
        train_txt = f"{len(tr_all)}/{int(tr_all['has_confirm'].sum())}"
        test_txt = f"{len(te_ch)}/{int(te_ch['has_confirm'].sum())}"
        sc = f"{best_score:+.2f}" if np.isfinite(best_score) else "n/a"
        print(
            f"{y:<6}{train_txt:<17}{cfg_txt:<16}{sc:>9}{test_txt:>16}"
            f"{(f'{d_ch.mean():+.2f}' if len(d_ch) else 'n/a'):>13}{(f'{d_fr.mean():+.2f}' if len(d_fr) else 'n/a'):>18}"
        )
    print("  (* = không đủ episode train, dùng cấu hình đóng băng)")
    print(f"  Số lần thử đã dùng: {len(grid)} cấu hình x {len(args.test_years)} fold = {len(grid) * len(args.test_years)}")

    for name, parts in (("CẤU HÌNH CHỌN THEO FOLD", chosen_rows), ("CẤU HÌNH ĐÓNG BĂNG (60/10)", frozen_rows)):
        pooled = pd.concat(parts, ignore_index=True)
        print(f"\n  OOS GỘP - {name}: episode={len(pooled)} | cụm={pooled['cluster'].nunique()} | có xác nhận={int(pooled['has_confirm'].sum())}")
        for c in SHOW_COLS:
            print("     " + _line(f"Δ CONFIRM - WINDOW [{c}]", pooled[f"d_conf_win_{c}"], pooled["cluster"]))
        print("     " + _line(f"Δ FIRST - WINDOW [{SELECT_COL}]", pooled[f"d_first_win_{SELECT_COL}"], pooled["cluster"]))
        signs = pooled.groupby("fold")[f"d_conf_win_{SELECT_COL}"].mean()
        print(f"     Dấu theo fold: {', '.join(f'{int(k)}:{v:+.1f}' for k, v in signs.items() if np.isfinite(v))}")
        pooled.to_csv(os.path.join(os.path.dirname(args.out_prefix) or ".", os.path.basename(args.out_prefix) + f"_oos_{'chosen' if 'CHỌN' in name else 'frozen'}.csv"), index=False)

    pooled = pd.concat(frozen_rows, ignore_index=True)
    m, lo, hi = cluster_ci(pooled[f"d_conf_win_{SELECT_COL}"], pooled["cluster"])
    print("\n  GỢI Ý ĐỌC (cấu hình đóng băng, OOS gộp):")
    if not np.isfinite(lo):
        print("   Chưa đủ dữ liệu.")
    elif lo > 0:
        print("   Cận dưới CI95 > 0: xác nhận có giá trị so với vào lệnh ngẫu nhiên trong episode. Cần xác nhận thêm bằng paper trading.")
    else:
        print("   Cận dưới CI95 <= 0: CHƯA có bằng chứng xác nhận vượt vào lệnh ngẫu nhiên trong cùng episode.")
        print("   Theo điều kiện dừng đã thống nhất: ngừng nâng cấp tín hiệu MUA kỹ thuật, hạ contrarian thành radar/WATCH.")
    print("   Lưu ý: giai đoạn test đã bị nhìn khi thiết kế v2, chỉ paper trading mới là kiểm định sạch.")


# ----------------------------------------------------------------------------- main
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", nargs="*", default=None, help="Mặc định: BROAD_MARKET_POOL")
    ap.add_argument("--start", default="2018-01-01")
    ap.add_argument("--end", default=pd.Timestamp.today().strftime("%Y-%m-%d"))
    ap.add_argument("--cache-dir", default="data/replay_cache")
    ap.add_argument("--trigger-score", type=float, default=70.0)
    ap.add_argument("--gap", type=int, default=10, help="Gộp các ngày panic cách nhau <= gap phiên vào 1 episode")
    ap.add_argument("--warmup", type=int, default=60)
    ap.add_argument("--rsi-prefilter", type=float, default=40.0)
    ap.add_argument("--mkt-dd", type=float, default=-8.0, help="Ngưỡng giảm VN-Index (%) tính là stress thị trường")
    ap.add_argument("--pad-days", type=int, default=21, help="Biên (ngày lịch) quanh đợt stress để gán episode vào cụm thị trường")
    ap.add_argument("--test-years", nargs="*", type=int, default=[2022, 2023, 2024, 2025, 2026])
    ap.add_argument("--rolling-years", type=int, default=0, help="0 = mở rộng; >0 = cửa sổ train trượt N năm")
    ap.add_argument("--embargo-days", type=int, default=100, help="Ngày lịch loại khỏi cuối train (nhãn T+60 chồng lấn)")
    ap.add_argument("--min-train", type=int, default=8, help="Số episode có xác nhận tối thiểu ở train để xét cấu hình")
    ap.add_argument("--out-prefix", default="data/episode_study")
    args = ap.parse_args()
    logging.basicConfig(level=logging.WARNING)

    symbols = [s.upper() for s in args.symbols] if args.symbols else None
    if symbols is None:
        from data_engine import BROAD_MARKET_POOL

        symbols = list(BROAD_MARKET_POOL)

    bench_df = load_history("VNINDEX", args.start, args.end, args.cache_dir)
    if bench_df.empty:
        raise SystemExit("Không tải được VNINDEX.")
    b = bench_df.set_index("time")
    bench_close = b["close"].astype(float)
    bench_open = (b["open"] if "open" in b.columns else b["close"]).astype(float)
    mkt_eps = market_episodes(bench_close, args.mkt_dd)

    episodes: list[dict] = []
    for sym in symbols:
        df = load_history(sym, args.start, args.end, args.cache_dir)
        if df.empty or len(df) < args.warmup + MAX_HOLD:
            print(f"Bỏ qua {sym}: thiếu dữ liệu")
            continue
        eps = build_symbol_episodes(sym, df, bench_open, bench_close, args)
        print(f"{sym}: {len(eps)} episode")
        episodes.extend(eps)
    if not episodes:
        print("Không có episode nào.")
        return

    os.makedirs(os.path.dirname(args.out_prefix) or ".", exist_ok=True)
    rows = section_a(episodes, mkt_eps, args)
    rows.to_csv(args.out_prefix + "_episodes.csv", index=False)
    section_c(episodes, mkt_eps, args)
    print(f"\nĐã lưu: {args.out_prefix}_episodes.csv và các file *_oos_*.csv")
e = pd.read_csv("data/episode_study_episodes.csv")
print(e["confirm_offset"].describe())          # xác nhận đến sau bao nhiêu phiên
print(e["d_conf_first_mae_pct"].mean())        # dương = vào lúc xác nhận ít bị lỗ sâu hơn
print(e["d_conf_win_mae_pct"].mean())

if __name__ == "__main__":
    main()