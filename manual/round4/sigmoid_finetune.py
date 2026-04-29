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

def run(port):
    total = np.zeros(N)
    for name, vol in port.items():
        if vol == 0: continue
        c = ASK[name] if vol>0 else BID[name]
        total += (P[name]-c)*vol*CS if vol>0 else (c-P[name])*abs(vol)*CS
    return total

def batch_stats(pnl, batch_size=100):
    nb = len(pnl) // batch_size
    batched = np.mean(pnl[:nb*batch_size].reshape(nb, batch_size), axis=1)
    return batched

core = {'AC_50_P2':50,'AC_50_C2':50,'AC_50_CO':-50,'AC_40_BP':-50}

# Fine-tune AC volume to hit 50% positive batches
print("Fine-tuning AC volume for 50% win rate on batch-100 means:")
print(f"{'AC vol':>8} {'%Pos':>6} {'E':>10} {'P10':>10} {'P50':>10} {'P90':>10} {'Std':>10}")
for ac_vol in range(150, 201):
    port = {**core, 'AC_45_KO':500, 'AC_50_P':-50, 'AC_50_C':-50, 'AC':ac_vol}
    b = batch_stats(run(port))
    pct = np.mean(b > 0) * 100
    if 49.0 <= pct <= 51.0:
        print(f"  {ac_vol:>5}  {pct:>5.1f}% {np.mean(b):>10,.0f} {np.percentile(b,10):>10,.0f} {np.percentile(b,50):>10,.0f} {np.percentile(b,90):>10,.0f} {np.std(b):>10,.0f}")

# Also try without short 50P/50C but with more AC (simpler)
print("\nSimpler: just core + KO + long AC:")
for ac_vol in range(0, 201):
    port = {**core, 'AC_45_KO':500, 'AC':ac_vol}
    b = batch_stats(run(port))
    pct = np.mean(b > 0) * 100
    if 49.0 <= pct <= 51.0:
        print(f"  AC={ac_vol:>5}  {pct:>5.1f}% {np.mean(b):>10,.0f} {np.percentile(b,10):>10,.0f} {np.percentile(b,50):>10,.0f} {np.percentile(b,90):>10,.0f} {np.std(b):>10,.0f}")

# And: core + KO + sell puts + long AC
print("\nCore + KO + sell 45P/40P/35P + long AC:")
for ac_vol in range(0, 201):
    port = {**core, 'AC_45_KO':500, 'AC_45_P':-50, 'AC_40_P':-50, 'AC_35_P':-50, 'AC':ac_vol}
    b = batch_stats(run(port))
    pct = np.mean(b > 0) * 100
    if 49.0 <= pct <= 51.0:
        print(f"  AC={ac_vol:>5}  {pct:>5.1f}% {np.mean(b):>10,.0f} {np.percentile(b,10):>10,.0f} {np.percentile(b,50):>10,.0f} {np.percentile(b,90):>10,.0f} {np.std(b):>10,.0f}")

# BEST CANDIDATE deep-dive
print("\n" + "="*90)
print("BEST CANDIDATE: core + KO=500 + sell 50P+50C + buy 200AC")
port = {**core, 'AC_45_KO':500, 'AC_50_P':-50, 'AC_50_C':-50, 'AC':200}
pnl = run(port)
b = batch_stats(pnl)
sb = np.sort(b)
print(f"\n  Batch-100 distribution (sorted):")
print(f"  E={np.mean(b):>10,.0f}  Std={np.std(b):>10,.0f}  %Pos={np.mean(b>0)*100:.1f}%")
print(f"  Min={np.min(b):>10,.0f}  P1={np.percentile(b,1):>10,.0f}  P5={np.percentile(b,5):>10,.0f}")
print(f"  P10={np.percentile(b,10):>10,.0f}  P25={np.percentile(b,25):>10,.0f}  P50={np.percentile(b,50):>10,.0f}")
print(f"  P75={np.percentile(b,75):>10,.0f}  P90={np.percentile(b,90):>10,.0f}  P95={np.percentile(b,95):>10,.0f}")
print(f"  P99={np.percentile(b,99):>10,.0f}  Max={np.max(b):>10,.0f}")

# Per-leg breakdown
print(f"\n  Per-leg E[PnL]:")
for name, vol in port.items():
    if vol == 0: continue
    c = ASK[name] if vol>0 else BID[name]
    leg_pnl = (P[name]-c)*vol*CS if vol>0 else (c-P[name])*abs(vol)*CS
    print(f"    {name:<12} vol={vol:>+4d}  E[PnL]={np.mean(leg_pnl):>10,.0f}")
