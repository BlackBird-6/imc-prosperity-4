import numpy as np
import scipy.stats as stats

S0 = 50.0; sigma = 2.51
TRADING_DAYS_PER_YEAR = 252; STEPS_PER_DAY = 4
dt = 1.0 / (TRADING_DAYS_PER_YEAR * STEPS_PER_DAY)
steps_2w = 40; steps_3w = 60
contract_size = 3000

np.random.seed(42)
N = 500000
drift = -0.5 * sigma**2 * dt
vol_gbm = sigma * np.sqrt(dt)
paths = S0 * np.exp(np.cumsum(drift + vol_gbm * np.random.randn(N, steps_3w), axis=1))
S_2w = paths[:, steps_2w - 1]
S_3w = paths[:, steps_3w - 1]
min_S = np.min(paths, axis=1)

def payoff_chooser(s2, s3):
    return np.where(s2 > 50, np.maximum(s3 - 50, 0), np.maximum(50 - s3, 0))

def payoff_45ko(s3, min_s):
    return np.where(min_s < 35, 0.0, np.maximum(45 - s3, 0))

# ===== Current portfolio (user's in.csv) =====
portfolios = {
    "CURRENT (in.csv)": {
        'AC':       {'pay': S_3w,                                  'vol': -25,  'cost': 49.975},
        'AC_35_P':  {'pay': np.maximum(35 - S_3w, 0),             'vol': +50,  'cost': 4.350},
        'AC_50_C2': {'pay': np.maximum(S_2w - 50, 0),             'vol': -50,  'cost': 9.700},
        'AC_50_CO': {'pay': payoff_chooser(S_2w, S_3w),           'vol': +50,  'cost': 22.300},
    },
    "PROPOSED STRATEGY": {
        'AC_50_P2': {'pay': np.maximum(50 - S_2w, 0),             'vol': +50,  'cost': 9.750},
        'AC_50_C2': {'pay': np.maximum(S_2w - 50, 0),             'vol': +50,  'cost': 9.750},
        'AC_50_CO': {'pay': payoff_chooser(S_2w, S_3w),           'vol': -50,  'cost': 22.200},
        'AC_60_C':  {'pay': np.maximum(S_3w - 60, 0),             'vol': -50,  'cost': 8.800},
        'AC_45_KO': {'pay': payoff_45ko(S_3w, min_S),             'vol': +500, 'cost': 0.175},
    },
}

for pname, portfolio in portfolios.items():
    print(f"\n{'='*70}")
    print(f"  {pname}")
    print(f"{'='*70}")
    total = np.zeros(N)
    for name, pos in portfolio.items():
        v = pos['vol']; cost = pos['cost']; pay = pos['pay']
        if v > 0:
            pnl = (pay - cost) * v * contract_size
        else:
            pnl = (cost - pay) * abs(v) * contract_size
        total += pnl
        print(f"  {name:<12} vol={v:+4d}  E[PnL]={np.mean(pnl):>12,.0f}  P10={np.percentile(pnl,10):>10,.0f}  P90={np.percentile(pnl,90):>10,.0f}")
    print(f"  {'---'}")
    print(f"  TOTAL         E[PnL]={np.mean(total):>12,.0f}")
    print(f"    Min={np.min(total):>10,.0f}  P1 ={np.percentile(total, 1):>10,.0f}  P10={np.percentile(total,10):>10,.0f}")
    print(f"    P25={np.percentile(total,25):>10,.0f}  P50={np.percentile(total,50):>10,.0f}  P75={np.percentile(total,75):>10,.0f}")
    print(f"    P90={np.percentile(total,90):>10,.0f}  P99={np.percentile(total,99):>10,.0f}  Max={np.max(total):>10,.0f}")

# Also show price distribution
print("\n\n=== Terminal Price Distribution (3w, analytical) ===")
mu_X = -0.5 * sigma**2 * (steps_3w * dt)
sig_X = sigma * np.sqrt(steps_3w * dt)
for px in [30, 35, 40, 45, 50, 55, 60, 70, 80]:
    p_below = stats.norm.cdf((np.log(px / S0) - mu_X) / sig_X) * 100
    print(f"  P(S_3w < {px:2d}) = {p_below:5.1f}%    P(S_3w > {px:2d}) = {100 - p_below:5.1f}%")

print(f"\n  P(path touches 35 barrier) = {np.mean(min_S < 35)*100:.1f}%")
print(f"  P(path stays above 35)     = {np.mean(min_S >= 35)*100:.1f}%")
