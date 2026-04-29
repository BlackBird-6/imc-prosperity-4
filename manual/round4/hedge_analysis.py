import numpy as np
import scipy.stats as stats

S0=50.0; sigma=2.51; TDAY=252; SPD=4
dt=1.0/(TDAY*SPD); steps_2w=40; steps_3w=60; CS=3000

np.random.seed(42); N=500000
paths=S0*np.exp(np.cumsum(-0.5*sigma**2*dt + sigma*np.sqrt(dt)*np.random.randn(N,steps_3w),axis=1))
S2=paths[:,steps_2w-1]; S3=paths[:,steps_3w-1]; minS=np.min(paths,axis=1)

def chooser(s2,s3): return np.where(s2>50,np.maximum(s3-50,0),np.maximum(50-s3,0))
def ko(s3,ms): return np.where(ms<35,0.0,np.maximum(45-s3,0))

# Legs
p2   = np.maximum(50-S2,0); c2=np.maximum(S2-50,0)
cho  = chooser(S2,S3)
ko500= ko(S3,minS)
p3_50= np.maximum(50-S3,0); c3_50=np.maximum(S3-50,0)
p3_45= np.maximum(45-S3,0); p3_40=np.maximum(40-S3,0); p3_35=np.maximum(35-S3,0)
c3_60= np.maximum(S3-60,0)
bp40 = np.where(S3<40,10.0,0.0)

def pnl(pay,v,cost):
    return (pay-cost)*v*CS if v>0 else (cost-pay)*abs(v)*CS

def run(port):
    tot=np.zeros(N)
    for name,(pay,v,cost) in port.items():
        tot += pnl(pay,v,cost)
    return tot

def stats_line(arr):
    return (f"E={np.mean(arr):>10,.0f}  "
            f"P10={np.percentile(arr,10):>10,.0f}  "
            f"P25={np.percentile(arr,25):>9,.0f}  "
            f"P50={np.percentile(arr,50):>9,.0f}  "
            f"P90={np.percentile(arr,90):>9,.0f}  "
            f"P99={np.percentile(arr,99):>9,.0f}  "
            f"Min={np.min(arr):>10,.0f}")

# === CURRENT strategy ===
cur = {
    'AC_50_P2': (p2,  +50,  9.750),
    'AC_50_C2': (c2,  +50,  9.750),
    'AC_50_CO': (cho, -50, 22.200),
    'AC_45_KO': (ko500,+500,0.175),
}

# === PROPOSED: add cap hedges ===
# Key insight: short chooser ≈ short 3w call@50 (net after 2w put cancels chooser's put component)
# Hedge A: buy AC_60_C → caps upside loss, turns short call@50 into short call-spread @50/60
# Hedge B: buy AC_40_P → downside buffer for barrier-hit paths where S3<40
# Edge cost: AC_60_C -0.11/unit, AC_40_P -0.05/unit

variants = {
    "BASE (current in.csv)":         cur,
    "+60C hedge (buy 50 AC_60C)":   {**cur,'AC_60_C': (c3_60, +50, 8.850)},
    "+40P hedge (buy 50 AC_40P)":   {**cur,'AC_40_P': (p3_40, +50, 6.550)},
    "+BOTH 60C+40P":                {**cur,'AC_60_C': (c3_60,+50,8.850),'AC_40_P':(p3_40,+50,6.550)},
    "+BOTH +SELL 50C (sell overpd)":{**cur,'AC_60_C':(c3_60,+50,8.850),'AC_40_P':(p3_40,+50,6.550),'AC_50_C':(c3_50,-50,12.000)},
}

print("="*120)
for name, port in variants.items():
    t=run(port)
    print(f"\n{name}")
    print("  "+stats_line(t))

# Edge summary table
print("\n\n=== FULL EDGE TABLE (Fair - Market Mid) ===")
T2=steps_2w*dt; T3=steps_3w*dt
def bsm_call(S,K,T,s): 
    d1=(np.log(S/K)+0.5*s**2*T)/(s*np.sqrt(T)); d2=d1-s*np.sqrt(T)
    return S*stats.norm.cdf(d1)-K*stats.norm.cdf(d2)
def bsm_put(S,K,T,s):
    d1=(np.log(S/K)+0.5*s**2*T)/(s*np.sqrt(T)); d2=d1-s*np.sqrt(T)
    return K*stats.norm.cdf(-d2)-S*stats.norm.cdf(-d1)

rows=[
 ("AC_50_P",  np.mean(p3_50), 12.000,12.050,"3w put@50"),
 ("AC_50_C",  np.mean(c3_50), 12.000,12.050,"3w call@50"),
 ("AC_35_P",  np.mean(p3_35),  4.330, 4.350,"3w put@35"),
 ("AC_40_P",  np.mean(p3_40),  6.500, 6.550,"3w put@40"),
 ("AC_45_P",  np.mean(p3_45),  9.050, 9.100,"3w put@45"),
 ("AC_60_C",  np.mean(c3_60),  8.800, 8.850,"3w call@60"),
 ("AC_50_P2", np.mean(p2),     9.700, 9.750,"2w put@50"),
 ("AC_50_C2", np.mean(c2),     9.700, 9.750,"2w call@50"),
 ("AC_50_CO", np.mean(cho),   22.200,22.300,"chooser"),
 ("AC_40_BP", np.mean(bp40),   5.000, 5.100,"binary put"),
 ("AC_45_KO", np.mean(ko500/500),0.150,0.175,"KO put"),
]
print(f"  {'Option':<12} {'Fair':>7} {'Bid':>7} {'Ask':>7} {'Edge(buy)':>10} {'Edge(sell)':>11} {'Verdict':<25} {'Desc'}")
for opt,fair,bid,ask,desc in rows:
    eb=fair-ask; es=bid-fair
    best='BUY' if eb>es else 'SELL'
    flag='** ' if abs(max(eb,es))>0.05 else '   '
    print(f"  {opt:<12} {fair:>7.3f} {bid:>7.3f} {ask:>7.3f} {eb:>+10.3f} {es:>+11.3f} {flag+best:<25} {desc}")

# Decompose chooser vs components
chooser_fair = np.mean(cho)
comp_fair = np.mean(c3_50) + np.mean(p2)  # call_3w + put_2w
print(f"\n=== CHOOSER DECOMPOSITION ===")
print(f"  Chooser fair (MC)            = {chooser_fair:.3f}")
print(f"  call_3w@50 + put_2w@50 (MC)  = {np.mean(c3_50):.3f} + {np.mean(p2):.3f} = {comp_fair:.3f}")
print(f"  Chooser overpriced vs comps  = {chooser_fair - comp_fair:+.3f}")
print(f"  Market mid chooser           = {22.250:.3f}")
print(f"  Market mids (call3w+put2w)   = {12.025:.3f} + {9.725:.3f} = {12.025+9.725:.3f}")
print(f"  Market mispricing (chooser)  = {22.250 - (12.025+9.725):+.3f}")
