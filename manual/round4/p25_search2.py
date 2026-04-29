import numpy as np

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

buy_pnl = {}
sell_pnl = {}
for name in P:
    buy_pnl[name] = (P[name] - ASK[name]) * CS
    sell_pnl[name] = (BID[name] - P[name]) * CS

def run(port):
    total = np.zeros(N)
    for name, vol in port.items():
        if vol == 0: continue
        if vol > 0: total += buy_pnl[name] * vol
        else: total += sell_pnl[name] * abs(vol)
    return total

def bstats(pnl):
    nb = N // 100
    b = np.mean(pnl[:nb*100].reshape(nb, 100), axis=1)
    return b

# Wider grid: step by 5 for option volumes, 10 for AC/KO
best_p25 = -1e18
best_port = None
count = 0

# The three edge sources:
# 1. Buy 2w straddle: +30k edge, adds variance from 2w expiry
# 2. Sell chooser: +57k edge, adds massive 3w variance  
# 3. Sell binary put: +34k edge, moderate variance
#
# Strategy: scale down the high-variance legs, add variance reducers

for p2 in [30, 40, 50]:        # AC_50_P2 buy vol
    for c2 in [30, 40, 50]:    # AC_50_C2 buy vol
        for co in range(0, 51, 5):   # AC_50_CO sell vol
            for bp in range(0, 51, 10):  # AC_40_BP sell vol
                for ko in [0, 50, 100, 200]:  # AC_45_KO buy vol
                    for p45 in [0, 25, 50]:    # AC_45_P buy (variance reducer)
                        port = {
                            'AC_50_P2': p2, 'AC_50_C2': c2,
                            'AC_50_CO': -co, 'AC_40_BP': -bp,
                            'AC_45_KO': ko, 'AC_45_P': p45,
                        }
                        pnl = run(port)
                        b = bstats(pnl)
                        p25 = np.percentile(b, 25)
                        e = np.mean(b)
                        count += 1
                        if p25 > best_p25 and e > 0:
                            best_p25 = p25
                            best_port = dict(port)
                            best_e = e

print(f"Searched {count} combinations")
print(f"\nBest P25 = {best_p25:>10,.0f}  E = {best_e:>10,.0f}")
print(f"Portfolio: {best_port}")

pnl = run(best_port)
b = bstats(pnl)
print(f"\nFull batch-100 stats:")
print(f"  Min={np.min(b):>10,.0f}  P5={np.percentile(b,5):>10,.0f}  P10={np.percentile(b,10):>10,.0f}")
print(f"  P25={np.percentile(b,25):>10,.0f}  P50={np.percentile(b,50):>10,.0f}  P75={np.percentile(b,75):>10,.0f}")
print(f"  P90={np.percentile(b,90):>10,.0f}  P99={np.percentile(b,99):>10,.0f}  Max={np.max(b):>10,.0f}")
print(f"  %Positive: {np.mean(b>0)*100:.1f}%")

# Check: is P25 > 0 even theoretically possible?
# The minimum variance strategy is just the edge with no positions:
# Actually, let's check what the theoretical minimum-variance positive-edge portfolio is
print(f"\n--- Theoretical check ---")
# Pure chooser sell at small volume:
for co in range(1, 51):
    port = {'AC_50_CO': -co}
    b = bstats(run(port))
    p25 = np.percentile(b, 25)
    e = np.mean(b)
    if p25 > 0:
        print(f"  CO=-{co}: P25={p25:>8,.0f}  E={e:>8,.0f}")
        break
    elif co <= 5 or co % 10 == 0:
        print(f"  CO=-{co}: P25={p25:>8,.0f}  E={e:>8,.0f}")

# Pure BP sell:
for bp in range(1, 51):
    port = {'AC_40_BP': -bp}
    b = bstats(run(port))
    p25 = np.percentile(b, 25)
    e = np.mean(b)
    if p25 > 0:
        print(f"  BP=-{bp}: P25={p25:>8,.0f}  E={e:>8,.0f}")
        break
    elif bp <= 5 or bp % 10 == 0:
        print(f"  BP=-{bp}: P25={p25:>8,.0f}  E={e:>8,.0f}")

# Combo at small volume
for co in range(1, 20):
    for bp in range(1, 20):
        port = {'AC_50_CO': -co, 'AC_40_BP': -bp}
        b = bstats(run(port))
        p25 = np.percentile(b, 25)
        e = np.mean(b)
        if p25 > 0:
            print(f"  CO=-{co} BP=-{bp}: P25={p25:>8,.0f}  E={e:>8,.0f}  <<<")
            break
    if p25 > 0:
        # Now add straddle
        port2 = {'AC_50_CO': -co, 'AC_40_BP': -bp, 'AC_50_P2': 50, 'AC_50_C2': 50}
        b2 = bstats(run(port2))
        print(f"  +straddle: P25={np.percentile(b2,25):>8,.0f}  E={np.mean(b2):>8,.0f}")
        break
