import numpy as np
from itertools import product as iprod

S0=50.0; sigma=2.51; dt=1.0/(252*4); steps_2w=40; steps_3w=60; CS=3000
np.random.seed(42); N=500000
paths=S0*np.exp(np.cumsum(-0.5*sigma**2*dt+sigma*np.sqrt(dt)*np.random.randn(N,steps_3w),axis=1))
S2=paths[:,steps_2w-1]; S3=paths[:,steps_3w-1]; minS=np.min(paths,axis=1)

cho = np.where(S2>50,np.maximum(S3-50,0),np.maximum(50-S3,0))
ko1 = np.where(minS<35,0.0,np.maximum(45-S3,0))
bp  = np.where(S3<40,10.0,0.0)

P = {
    'AC':S3, 'AC_50_P':np.maximum(50-S3,0), 'AC_50_C':np.maximum(S3-50,0),
    'AC_35_P':np.maximum(35-S3,0), 'AC_40_P':np.maximum(40-S3,0),
    'AC_45_P':np.maximum(45-S3,0), 'AC_60_C':np.maximum(S3-60,0),
    'AC_50_P2':np.maximum(50-S2,0), 'AC_50_C2':np.maximum(S2-50,0),
    'AC_50_CO':cho, 'AC_40_BP':bp, 'AC_45_KO':ko1,
}
BID={'AC':49.975,'AC_50_P':12.000,'AC_50_C':12.000,'AC_35_P':4.330,'AC_40_P':6.500,
     'AC_45_P':9.050,'AC_60_C':8.800,'AC_50_P2':9.700,'AC_50_C2':9.700,
     'AC_50_CO':22.200,'AC_40_BP':5.000,'AC_45_KO':0.150}
ASK={'AC':50.025,'AC_50_P':12.050,'AC_50_C':12.050,'AC_35_P':4.350,'AC_40_P':6.550,
     'AC_45_P':9.100,'AC_60_C':8.850,'AC_50_P2':9.750,'AC_50_C2':9.750,
     'AC_50_CO':22.300,'AC_40_BP':5.100,'AC_45_KO':0.175}
MAX_BUY={'AC':200,'AC_50_P':50,'AC_50_C':50,'AC_35_P':50,'AC_40_P':50,
         'AC_45_P':50,'AC_60_C':50,'AC_50_P2':50,'AC_50_C2':50,
         'AC_50_CO':50,'AC_40_BP':50,'AC_45_KO':500}
MAX_SELL={'AC':200,'AC_50_P':50,'AC_50_C':50,'AC_35_P':50,'AC_40_P':50,
          'AC_45_P':50,'AC_60_C':50,'AC_50_P2':50,'AC_50_C2':50,
          'AC_50_CO':50,'AC_40_BP':50,'AC_45_KO':500}

# Precompute per-unit PnL arrays for buy and sell
buy_pnl = {}  # per-unit pnl if buying 1 unit
sell_pnl = {}
for name in P:
    buy_pnl[name] = (P[name] - ASK[name]) * CS   # per unit if buy
    sell_pnl[name] = (BID[name] - P[name]) * CS   # per unit if sell

def run(port):
    total = np.zeros(N)
    for name, vol in port.items():
        if vol == 0: continue
        if vol > 0:
            total += buy_pnl[name] * vol
        else:
            total += sell_pnl[name] * abs(vol)
    return total

def batch_p25(pnl):
    nb = N // 100
    batched = np.mean(pnl[:nb*100].reshape(nb, 100), axis=1)
    return np.percentile(batched, 25), np.mean(batched), np.percentile(batched, 50), np.std(batched)

# Strategy: we need P25 > 0 on batch-100 means
# The core edge trades (buy cheap 2w options, sell overpriced chooser+BP) provide ~120k E[PnL]
# but have too much variance. We need to REDUCE variance.
# 
# Key insight: the main variance source is the short chooser (pays out huge on big moves).
# To reduce variance, we can:
# 1. Reduce chooser volume
# 2. Add hedges that offset chooser's tails
# 3. Focus only on the lowest-variance edge trades

print("="*100)
print("PHASE 1: Test reduced chooser volumes + core")
print(f"{'Config':<55} {'P25':>10} {'E':>10} {'P50':>10} {'Std':>10}")

# Systematically test chooser volumes from 0 to 50
for co_vol in [0, 10, 20, 30, 40, 50]:
    for bp_vol in [0, -50]:
        port = {'AC_50_P2':50, 'AC_50_C2':50, 'AC_50_CO':-co_vol, 'AC_40_BP':bp_vol}
        pnl = run(port)
        p25, e, p50, std = batch_p25(pnl)
        flag = " <<<" if p25 > 0 else ""
        label = f"straddle + CO={-co_vol} + BP={bp_vol}"
        print(f"  {label:<53} {p25:>10,.0f} {e:>10,.0f} {p50:>10,.0f} {std:>10,.0f}{flag}")

print("\n" + "="*100)
print("PHASE 2: Add vanilla hedges to reduce chooser tail risk")
# Buy 60C to cap upside loss from short chooser
# Buy 50P to cap downside loss from short chooser  
for co_vol in [30, 40, 50]:
    for hedge in ['none', '60C', '50P', '50P+60C', '45P', '45P+60C']:
        port = {'AC_50_P2':50, 'AC_50_C2':50, 'AC_50_CO':-co_vol, 'AC_40_BP':-50}
        if '60C' in hedge: port['AC_60_C'] = 50
        if '50P' in hedge: port['AC_50_P'] = 50
        if '45P' in hedge: port['AC_45_P'] = 50
        pnl = run(port)
        p25, e, p50, std = batch_p25(pnl)
        flag = " <<<" if p25 > 0 else ""
        label = f"CO={-co_vol} BP=-50 hedge={hedge}"
        print(f"  {label:<53} {p25:>10,.0f} {e:>10,.0f} {p50:>10,.0f} {std:>10,.0f}{flag}")

print("\n" + "="*100)
print("PHASE 3: Full grid search (coarser) - maximize P25")
best_p25 = -1e18
best_port = None
best_stats = None

# Search space: key levers are CO vol, BP vol, hedges, and KO
co_range = [0, 10, 20, 30, 40, 50]
bp_range = [0, -25, -50]
ko_range = [0, 100, 200, 300]
ac_range = [0]  # underlying adds too much variance
hedge_combos = [
    {},
    {'AC_60_C': 50},
    {'AC_50_P': 50},
    {'AC_50_P': 50, 'AC_60_C': 50},
    {'AC_45_P': 50},
    {'AC_45_P': 50, 'AC_60_C': 50},
    {'AC_50_C': -50},
    {'AC_35_P': -50},
]

count = 0
for co in co_range:
    for bp in bp_range:
        for ko in ko_range:
            for hedges in hedge_combos:
                port = {'AC_50_P2':50, 'AC_50_C2':50, 'AC_50_CO':-co, 'AC_40_BP':bp, 'AC_45_KO':ko}
                port.update(hedges)
                pnl = run(port)
                p25, e, p50, std = batch_p25(pnl)
                count += 1
                if p25 > best_p25 and e > 0:
                    best_p25 = p25
                    best_port = dict(port)
                    best_stats = (p25, e, p50, std)

print(f"  Searched {count} combinations")
print(f"\n  BEST P25 = {best_stats[0]:>10,.0f}  E={best_stats[1]:>10,.0f}  P50={best_stats[2]:>10,.0f}  Std={best_stats[3]:>10,.0f}")
print(f"  Portfolio: {best_port}")

# Full stats on best
pnl = run(best_port)
nb = N // 100
b = np.mean(pnl[:nb*100].reshape(nb, 100), axis=1)
print(f"\n  Full batch-100 stats:")
print(f"  Min={np.min(b):>10,.0f}  P5={np.percentile(b,5):>10,.0f}  P10={np.percentile(b,10):>10,.0f}")
print(f"  P25={np.percentile(b,25):>10,.0f}  P50={np.percentile(b,50):>10,.0f}  P75={np.percentile(b,75):>10,.0f}")
print(f"  P90={np.percentile(b,90):>10,.0f}  P95={np.percentile(b,95):>10,.0f}  Max={np.max(b):>10,.0f}")
print(f"  %Positive: {np.mean(b>0)*100:.1f}%")

# Per-leg breakdown
print(f"\n  Per-leg E[PnL]:")
for name, vol in sorted(best_port.items()):
    if vol == 0: continue
    c = ASK[name] if vol > 0 else BID[name]
    leg = (P[name]-c)*vol*CS if vol>0 else (c-P[name])*abs(vol)*CS
    print(f"    {name:<12} vol={vol:>+4d}  E={np.mean(leg):>10,.0f}")
