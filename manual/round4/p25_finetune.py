import numpy as np

S0=50.0; sigma=2.51; dt=1.0/(252*4); steps_2w=40; steps_3w=60; CS=3000
np.random.seed(42); N=1000000  # More samples for stability
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

buy_pnl = {n: (P[n]-ASK[n])*CS for n in P}
sell_pnl = {n: (BID[n]-P[n])*CS for n in P}

def run(port):
    total = np.zeros(N)
    for name, vol in port.items():
        if vol == 0: continue
        if vol > 0: total += buy_pnl[name] * vol
        else: total += sell_pnl[name] * abs(vol)
    return total

def bstats(pnl):
    nb = N // 100
    return np.mean(pnl[:nb*100].reshape(nb, 100), axis=1)

# Fine-tune around best: {P2:30, C2:30, CO:-25, BP:-50, KO:200, 45P:25}
best_p25 = -1e18
best_port = None
count = 0

for p2 in range(20, 51, 5):
    for c2 in range(20, 51, 5):
        for co in range(15, 36):
            for bp in range(35, 51, 5):
                for ko in range(100, 301, 50):
                    for p45 in range(0, 51, 5):
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
for p_name, pct in [('Min',0),('P1',1),('P5',5),('P10',10),('P25',25),('P50',50),('P75',75),('P90',90),('P95',95),('P99',99),('Max',100)]:
    val = np.min(b) if pct==0 else (np.max(b) if pct==100 else np.percentile(b,pct))
    print(f"  {p_name:>4} = {val:>10,.0f}")
print(f"  %Positive: {np.mean(b>0)*100:.1f}%")

print(f"\nPer-leg E[PnL]:")
for name in sorted(best_port):
    vol = best_port[name]
    if vol == 0: continue
    if vol > 0: leg = buy_pnl[name]*vol
    else: leg = sell_pnl[name]*abs(vol)
    print(f"  {name:<12} vol={vol:>+4d}  E={np.mean(leg):>10,.0f}")
