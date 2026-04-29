import numpy as np

S0=50.0; sigma=2.51; dt=1.0/(252*4); steps_2w=40; steps_3w=60; CS=3000
np.random.seed(42); N=500000
paths=S0*np.exp(np.cumsum(-0.5*sigma**2*dt+sigma*np.sqrt(dt)*np.random.randn(N,steps_3w),axis=1))
S2=paths[:,steps_2w-1]; S3=paths[:,steps_3w-1]; minS=np.min(paths,axis=1)

cho = np.where(S2>50,np.maximum(S3-50,0),np.maximum(50-S3,0))
ko1 = np.where(minS<35,0.0,np.maximum(45-S3,0))
bp  = np.where(S3<40,10.0,0.0)

# All payoff arrays
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
    n = len(pnl)
    nb = n // batch_size
    if nb == 0: return {}
    batched = np.mean(pnl[:nb*batch_size].reshape(nb, batch_size), axis=1)
    sorted_b = np.sort(batched)
    pct_positive = np.mean(batched > 0) * 100
    return {
        'E': np.mean(batched), 'Std': np.std(batched),
        'Min': np.min(batched), 'P5': np.percentile(batched,5),
        'P10': np.percentile(batched,10), 'P25': np.percentile(batched,25),
        'P50': np.percentile(batched,50), 'P75': np.percentile(batched,75),
        'P90': np.percentile(batched,90), 'P95': np.percentile(batched,95),
        'Max': np.max(batched), 'PctPos': pct_positive,
        'raw': batched,
    }

def show(label, port):
    pnl = run(port)
    bs = batch_stats(pnl)
    print(f"\n{'='*90}")
    print(f"  {label}")
    print(f"  Batch-100 stats:  E={bs['E']:>10,.0f}  Std={bs['Std']:>10,.0f}  %Pos={bs['PctPos']:.1f}%")
    print(f"  Min={bs['Min']:>10,.0f}  P5={bs['P5']:>10,.0f}  P10={bs['P10']:>10,.0f}  P25={bs['P25']:>10,.0f}")
    print(f"  P50={bs['P50']:>10,.0f}  P75={bs['P75']:>10,.0f}  P90={bs['P90']:>10,.0f}  P95={bs['P95']:>10,.0f}  Max={bs['Max']:>10,.0f}")
    # Sigmoid shape indicator: ratio of P90-P10 range to P75-P25 range 
    iqr = bs['P75'] - bs['P25']
    wide = bs['P90'] - bs['P10']
    if iqr > 0:
        print(f"  Tail-stretch ratio (P90-P10)/(P75-P25) = {wide/iqr:.2f}  (higher = fatter tails)")
    return bs

# CURRENT: core mispricing trades only
core = {'AC_50_P2':50,'AC_50_C2':50,'AC_50_CO':-50,'AC_40_BP':-50}
show("CORE (straddle + short chooser + short BP)", core)

# CURRENT in.csv
current = {'AC_50_P2':50,'AC_50_C2':50,'AC_50_CO':-50,'AC_40_BP':-50,'AC_45_KO':500}
show("CURRENT (core + 500 KO)", current)

# APPROACH: sigmoid shape where batch-100 median ~ 0, extreme tails
# The KO puts add lottery-ticket variance. Short puts add premium but downside risk.
# Key: selling OTM puts gives us premium to offset the straddle cost (pushing median up)
# while adding fat negative tails when S3 crashes.
# The chooser short already gives big negative tails on upside.
# KO puts add big positive tails.
# Result: bimodal-ish, S-curve CDF

# Test various KO amounts + short put combos
configs = [
    ("KO=200",                    {**core, 'AC_45_KO':200}),
    ("KO=300",                    {**core, 'AC_45_KO':300}),
    ("KO=500",                    {**core, 'AC_45_KO':500}),
    ("KO=500 + sell 45P/40P",     {**core, 'AC_45_KO':500, 'AC_45_P':-50, 'AC_40_P':-50}),
    ("KO=500 + sell 45P/40P/35P", {**core, 'AC_45_KO':500, 'AC_45_P':-50, 'AC_40_P':-50, 'AC_35_P':-50}),
    ("KO=500 + sell 50C",         {**core, 'AC_45_KO':500, 'AC_50_C':-50}),
    ("KO=500 + sell 50P+50C",     {**core, 'AC_45_KO':500, 'AC_50_P':-50, 'AC_50_C':-50}),
    # Aim for ~50% positive batches: need to shift median toward 0
    # Short 50P+50C collects 24k premium but adds variance
    # Add long AC for upside delta hedge
    ("KO=500 + sell 50P+50C + buy 200AC", {**core, 'AC_45_KO':500, 'AC_50_P':-50, 'AC_50_C':-50, 'AC':200}),
    ("KO=500 + sell all puts",    {**core, 'AC_45_KO':500, 'AC_50_P':-50, 'AC_45_P':-50, 'AC_40_P':-50, 'AC_35_P':-50}),
    # Extreme variance: sell everything vanilla, buy all the edge  
    ("KO=500+sell 50C+60C+45P+40P", {**core,'AC_45_KO':500,'AC_50_C':-50,'AC_60_C':-50,'AC_45_P':-50,'AC_40_P':-50}),
    ("KO=500+sell 50C+60C+all puts", {**core,'AC_45_KO':500,'AC_50_C':-50,'AC_60_C':-50,'AC_45_P':-50,'AC_40_P':-50,'AC_35_P':-50,'AC_50_P':-50}),
]

for label, port in configs:
    show(label, port)

# Now find the one closest to 50% positive with extreme tails
print("\n\n" + "="*90)
print("SUMMARY: Sorted by distance from 50% positive")
print(f"{'Config':<45} {'%Pos':>6} {'E':>10} {'P10':>10} {'P50':>10} {'P90':>10} {'Std':>10}")
results = []
for label, port in configs:
    pnl = run(port)
    bs = batch_stats(pnl)
    dist = abs(bs['PctPos'] - 50)
    results.append((dist, label, bs))
results.sort()
for dist, label, bs in results:
    print(f"  {label:<43} {bs['PctPos']:>5.1f}% {bs['E']:>10,.0f} {bs['P10']:>10,.0f} {bs['P50']:>10,.0f} {bs['P90']:>10,.0f} {bs['Std']:>10,.0f}")
