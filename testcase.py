import pandas as pd
from replay_contrarian_v2 import diff_ci
e = pd.read_csv("data/episode_study_episodes.csv")
m = e[e.is_market]
med = m.idio_dd20.median()
deep, shallow = m[m.idio_dd20 <= med], m[m.idio_dd20 > med]
print(diff_ci(shallow, deep, "first_alpha_adj_t60"))

import glob, math
import pandas as pd

f = glob.glob("data/replay_cache/VNINDEX_*.csv")[0]
b = pd.read_csv(f, parse_dates=["time"]).sort_values("time").set_index("time")["close"].astype(float)
fwd = b.shift(-60) / b - 1
dd = b / b.rolling(60, min_periods=20).max() - 1

starts, last = [], -999
for k, v in enumerate(dd.to_numpy()):
    if v <= -0.08:
        if k - last > 20:
            starts.append(k)
        last = k

vals = fwd.iloc[starts].dropna()
p0 = (fwd.dropna() > 0).mean()
n, x = len(vals), int((vals > 0).sum())
p = sum(math.comb(n, i) * p0**i * (1 - p0)**(n - i) for i in range(x, n + 1))
print(f"đợt={n} dương={x} xác suất cơ sở={p0:.2f} p={p:.3f}")
print(f"TB lợi suất 60p sau trigger={vals.mean():+.1%} | vô điều kiện={fwd.mean():+.1%}")
print(vals.round(3).to_string())

import glob
import numpy as np
import pandas as pd
from regime_classifier import classify_regime_ma200_hysteresis

f = glob.glob("data/replay_cache/VNINDEX_*.csv")[0]
df = pd.read_csv(f, parse_dates=["time"]).sort_values("time").set_index("time")
reg = classify_regime_ma200_hysteresis(df)            # cấu hình mặc định, không chỉnh
ret = df["close"].pct_change().fillna(0.0)
in_mkt = (reg.shift(1) != "DOWNTREND")                # tín hiệu hôm nay, hành động phiên sau
cost = 0.002                                          # 0.2% mỗi lần đổi trạng thái
strat = ret.where(in_mkt, 0.0) - cost * in_mkt.astype(int).diff().abs().fillna(0.0)

start = df.index[220]                                 # bỏ 220 phiên đầu: MA200 chưa đủ
def stats(r):
    r = r.loc[start:]
    eq = (1 + r).cumprod()
    yrs = len(r) / 252
    cagr = eq.iloc[-1] ** (1 / yrs) - 1
    return cagr, (eq / eq.cummax() - 1).min(), cagr / (r.std() * np.sqrt(252))

for name, r in (("Buy & hold", ret), ("Cash Mode", strat)):
    c, d, s = stats(r)
    print(f"{name:<11} CAGR={c:+.1%}  MaxDD={d:.1%}  Sharpe={s:.2f}")
print("Thời gian trong thị trường:", f"{in_mkt.loc[start:].mean():.0%}",
      "| số lần đổi trạng thái:", int((reg.loc[start:] == 'DOWNTREND').astype(int).diff().abs().sum()))

import itertools
# 1) Trễ thực thi 1 phiên (vào/ra ở phiên sau tín hiệu) và chi phí 0.5%/lần đổi
for lag, cost in ((2, 0.002), (1, 0.005), (2, 0.005)):
    pos = (reg.shift(lag) != "DOWNTREND")
    r = ret.where(pos, 0.0) - cost * pos.astype(int).diff().abs().fillna(0.0)
    c, d, s = stats(r)
    print(f"lag={lag} cost={cost:.1%}: CAGR={c:+.1%} MaxDD={d:.1%} Sharpe={s:.2f}")

# 2) Placebo thời điểm: xoay vòng ngẫu nhiên chuỗi 'ngoài thị trường', giữ nguyên số ngày và độ dài mỗi đợt
r0 = ret.loc[start:].to_numpy()
out = (~in_mkt.loc[start:]).to_numpy()
def maxdd(rr):
    eq = np.cumprod(1 + rr)
    return (eq / np.maximum.accumulate(eq) - 1).min()
actual = maxdd(np.where(out, 0.0, r0))
rng = np.random.default_rng(42)
sim = np.array([maxdd(np.where(np.roll(out, int(rng.integers(len(out)))), 0.0, r0)) for _ in range(2000)])
print(f"MaxDD thực = {actual:.1%} | placebo: P5={np.percentile(sim,5):.1%} P50={np.percentile(sim,50):.1%} P95={np.percentile(sim,95):.1%}")
print(f"Tỷ lệ placebo có MaxDD nông hơn bản thực: {(sim >= actual).mean():.1%}")

pos = (reg.shift(2) != "DOWNTREND")
strat2 = ret.where(pos, 0.0) - 0.005 * pos.astype(int).diff().abs().fillna(0.0)
for a, b in (("2019-01-01", "2021-12-31"), ("2022-01-01", "2026-12-31")):
    for name, r in (("Buy&hold", ret), ("Cash Mode", strat2)):
        eq = (1 + r.loc[a:b]).cumprod()
        print(f"{a[:4]}-{b[:4]} {name:<10} MaxDD={(eq/eq.cummax()-1).min():.1%}  Ret={eq.iloc[-1]-1:+.1%}")