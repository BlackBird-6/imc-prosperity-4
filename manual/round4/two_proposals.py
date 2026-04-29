import numpy as np

S0=50.0; sigma=2.51; dt=1.0/(252*4); steps_2w=40; steps_3w=60; CS=3000
np.random.seed(42); N=500000
paths=S0*np.exp(np.cumsum(-0.5*sigma**2*dt+sigma*np.sqrt(dt)*np.random.randn(N,steps_3w),axis=1))
S2=paths[:,steps_2w-1]; S3=paths[:,steps_3w-1]; minS=np.min(paths,axis=1)

cho = lambda s2,s3: np.where(s2>50,np.maximum(s3-50,0),np.maximum(50-s3,0))
ko1 = np.where(minS<35,0.0,np.maximum(45-S3,0))

PAYOFFS = {
    'AC':S3, 'AC_50_P':np.maximum(50-S3,0), 'AC_50_C':np.maximum(S3-50,0),
    'AC_35_P':np.maximum(35-S3,0), 'AC_40_P':np.maximum(40-S3,0),
    'AC_45_P':np.maximum(45-S3,0), 'AC_60_C':np.maximum(S3-60,0),
    'AC_50_P2':np.maximum(50-S2,0), 'AC_50_C2':np.maximum(S2-50,0),
    'AC_50_CO':cho(S2,S3), 'AC_40_BP':np.where(S3<40,10.0,0.0),
}
BID={'AC':49.975,'AC_50_P':12.000,'AC_50_C':12.000,'AC_35_P':4.330,'AC_40_P':6.500,
     'AC_45_P':9.050,'AC_60_C':8.800,'AC_50_P2':9.700,'AC_50_C2':9.700,
     'AC_50_CO':22.200,'AC_40_BP':5.000}
ASK={'AC':50.025,'AC_50_P':12.050,'AC_50_C':12.050,'AC_35_P':4.350,'AC_40_P':6.550,
     'AC_45_P':9.100,'AC_60_C':8.850,'AC_50_P2':9.750,'AC_50_C2':9.750,
     'AC_50_CO':22.300,'AC_40_BP':5.100}

def run(portfolio):
    # portfolio: {name: vol}, special key 'AC_45_KO' with vol
    total = np.zeros(N)
    for name, vol in portfolio.items():
        if vol == 0: continue
        if name == 'AC_45_KO':
            cost = ASK['AC_45_P'] if vol>0 else BID['AC_45_P']  # placeholder, use actual
            cost = 0.175 if vol>0 else 0.150
            pay = ko1 * vol
            total += (pay - cost*abs(vol))*CS if vol>0 else (cost*abs(vol) - pay)*CS
            # simpler:
            total -= total  # reset this, redo below
            break
    total = np.zeros(N)
    for name, vol in portfolio.items():
        if vol == 0: continue
        if name == 'AC_45_KO':
            c = 0.175 if vol>0 else 0.150
            pnl = (ko1 - c) * vol * CS if vol>0 else (c - ko1) * abs(vol) * CS
        else:
            c = ASK[name] if vol>0 else BID[name]
            pnl = (PAYOFFS[name]-c)*vol*CS if vol>0 else (c-PAYOFFS[name])*abs(vol)*CS
        total += pnl
    return total

def show(label, t, base=None):
    e=np.mean(t); p10=np.percentile(t,10); p25=np.percentile(t,25)
    p50=np.percentile(t,50); p75=np.percentile(t,75); p90=np.percentile(t,90)
    p99=np.percentile(t,99); mn=np.min(t); mx=np.max(t)
    print(f"\n{'='*80}")
    print(f"  {label}")
    print(f"  E={e:>10,.0f}  P10={p10:>10,.0f}  P25={p25:>9,.0f}  P50={p50:>9,.0f}")
    print(f"  P75={p75:>9,.0f}  P90={p90:>9,.0f}  P99={p99:>9,.0f}")
    print(f"  Min={mn:>10,.0f}  Max={mx:>10,.0f}  Std={np.std(t):>10,.0f}")
    if base is not None:
        b=base
        print(f"  -- vs BASE --")
        print(f"  dE={np.mean(t)-np.mean(b):>+10,.0f}  dP10={np.percentile(t,10)-np.percentile(b,10):>+10,.0f}  "
              f"dP50={np.percentile(t,50)-np.percentile(b,50):>+9,.0f}  dP90={np.percentile(t,90)-np.percentile(b,90):>+9,.0f}")
        print(f"  dStd={np.std(t)-np.std(b):>+10,.0f}  dMin={np.min(t)-np.min(b):>+10,.0f}  dMax={np.max(t)-np.max(b):>+10,.0f}")

# CURRENT PORTFOLIO (in.csv)
BASE = {'AC':23,'AC_60_C':50,'AC_50_P2':50,'AC_50_C2':50,'AC_50_CO':-50,'AC_40_BP':-50,'AC_45_KO':500}
base_pnl = run(BASE)
show("BASE (current in.csv)  E[PnL]=+$151k", base_pnl)

# === PROPOSAL 1: HIGH RISK / HIGH REWARD ===
# Sell the 3 untapped OTM vanilla puts at full size
# AC_35_P, AC_40_P, AC_45_P all -50
# These are slightly overpriced (sell edge +0.006, +0.001, -0.030)
# Collects huge premium but creates massive short-gamma downside exposure
HIGH = {**BASE, 'AC_35_P':-50, 'AC_40_P':-50, 'AC_45_P':-50}
high_pnl = run(HIGH)
extra_premium = (4.330+6.500+9.050)*50*CS
print(f"\n  [HIGH RISK] Extra premium collected: ${extra_premium:,.0f}")
print(f"  [HIGH RISK] Max additional loss (S3->0): ${(35+40+45)*50*CS:,.0f}")
show("PROPOSAL 1 [HIGH RISK]: +Sell AC_35P/40P/45P x50 each", high_pnl, base_pnl)

# === PROPOSAL 2: LOW RISK / LOW REWARD ===
# Two options: (a) reduce KO 500->0 (b) reduce KO + close 60C long
# Strategy: Eliminate the KO lottery entirely, close the overpriced AC_60_C buy
# KO: removing 500 lots eliminates $262.5k cost, loses ~$0.045*500*3000=$67.5k edge
# AC_60_C close: stop buying an overpriced option, save $0.114*50*3000=$17.1k negative edge

# (a) just reduce KO to 0
LOW_a = {**BASE, 'AC_45_KO':0}
low_a_pnl = run(LOW_a)
show("PROPOSAL 2a [LOW RISK]: KO 500->0 (remove lottery)", low_a_pnl, base_pnl)

# (b) reduce KO to 0 AND close AC_60_C long (stop paying overpriced call)
LOW_b = {**BASE, 'AC_45_KO':0, 'AC_60_C':0}
low_b_pnl = run(LOW_b)
saved_edge = 0.114*50*CS  # stop losing edge on overpriced 60C
show("PROPOSAL 2b [LOW RISK]: KO->0 + close AC_60C", low_b_pnl, base_pnl)

# KO cost breakdown
print(f"\n  [LOW RISK] KO removal: free up ${0.175*500*CS:,.0f} in capital")
print(f"  [LOW RISK] KO edge lost: ~${0.045*500*CS:,.0f} in expected value")
print(f"  [LOW RISK] AC_60C: stop losing ${0.114*50*CS:,.0f} in negative edge per run")

# Show what specific paths gain/lose
print(f"\n=== PATH ANALYSIS ===")
barrier_hit = minS < 35
no_barrier  = minS >= 35
print(f"  Paths where KO knocked out (barrier hit): {np.mean(barrier_hit)*100:.1f}%")
print(f"  Paths where KO survives (no barrier):     {np.mean(no_barrier)*100:.1f}%")
print(f"\n  HIGH RISK: avg extra PnL in barrier-hit paths: {np.mean((high_pnl-base_pnl)[barrier_hit]):>+10,.0f}")
print(f"  HIGH RISK: avg extra PnL in no-barrier paths:  {np.mean((high_pnl-base_pnl)[no_barrier]):>+10,.0f}")
print(f"\n  LOW RISK (2a): avg PnL change in barrier-hit:  {np.mean((low_a_pnl-base_pnl)[barrier_hit]):>+10,.0f}")
print(f"  LOW RISK (2a): avg PnL change in no-barrier:   {np.mean((low_a_pnl-base_pnl)[no_barrier]):>+10,.0f}")
