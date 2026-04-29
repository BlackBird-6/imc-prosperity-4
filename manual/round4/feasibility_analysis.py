import numpy as np
import scipy.stats as stats

S0=50.0; sigma=2.51; dt=1.0/(252*4); steps_2w=40; steps_3w=60; CS=3000
np.random.seed(42); N=500000
paths=S0*np.exp(np.cumsum(-0.5*sigma**2*dt + sigma*np.sqrt(dt)*np.random.randn(N,steps_3w),axis=1))
S2=paths[:,steps_2w-1]; S3=paths[:,steps_3w-1]; minS=np.min(paths,axis=1)

def cho(s2,s3): return np.where(s2>50,np.maximum(s3-50,0),np.maximum(50-s3,0))
def ko(s3,ms,n): return n*np.where(ms<35,0.0,np.maximum(45-s3,0))

payoffs = {
    'AC':       S3,
    'AC_50_P':  np.maximum(50-S3,0),
    'AC_50_C':  np.maximum(S3-50,0),
    'AC_35_P':  np.maximum(35-S3,0),
    'AC_40_P':  np.maximum(40-S3,0),
    'AC_45_P':  np.maximum(45-S3,0),
    'AC_60_C':  np.maximum(S3-60,0),
    'AC_50_P2': np.maximum(50-S2,0),
    'AC_50_C2': np.maximum(S2-50,0),
    'AC_50_CO': cho(S2,S3),
    'AC_40_BP': np.where(S3<40,10.0,0.0),
}

costs = {
    'AC':49.975,'AC_50_P':12.000,'AC_50_C':12.000,'AC_35_P':4.330,'AC_40_P':6.500,
    'AC_45_P':9.050,'AC_60_C':8.800,'AC_50_P2':9.750,'AC_50_C2':9.750,
    'AC_50_CO':22.300,'AC_40_BP':5.000,
}
asks = {
    'AC':50.025,'AC_50_P':12.050,'AC_50_C':12.050,'AC_35_P':4.350,'AC_40_P':6.550,
    'AC_45_P':9.100,'AC_60_C':8.850,'AC_50_P2':9.750,'AC_50_C2':9.750,
    'AC_50_CO':22.300,'AC_40_BP':5.100,
}

def pnl_leg(pay, vol):
    cost = asks[vol[0]] if vol[1]>0 else costs[vol[0]]
    v = vol[1]
    return (pay-cost)*v*CS if v>0 else (cost-pay)*abs(v)*CS

def run_portfolio(pos_dict, ko_n=500):
    total = np.zeros(N)
    for name, vol in pos_dict.items():
        if name == 'AC_45_KO':
            cost = 0.175 if vol>0 else 0.150
            pay = ko(S3,minS,1)
            total += ((pay-cost)*vol*CS if vol>0 else (cost-pay)*abs(vol)*CS)
        else:
            pay = payoffs[name]
            cost = asks[name] if vol>0 else costs[name]
            total += ((pay-cost)*vol*CS if vol>0 else (cost-pay)*abs(vol)*CS)
    return total

def summary(label, arr):
    print(f"\n{label}")
    print(f"  E={np.mean(arr):>10,.0f}  P10={np.percentile(arr,10):>10,.0f}  P25={np.percentile(arr,25):>9,.0f}  "
          f"P50={np.percentile(arr,50):>9,.0f}  P75={np.percentile(arr,75):>9,.0f}  "
          f"P90={np.percentile(arr,90):>9,.0f}  Min={np.min(arr):>10,.0f}  Max={np.max(arr):>10,.0f}")

# CURRENT portfolio (latest in.csv)
current = {
    'AC':-50,'AC_50_P':-50,'AC_50_C':-50,'AC_35_P':-50,'AC_40_P':-50,'AC_45_P':-50,
    'AC_60_C':-50,'AC_50_P2':50,'AC_50_C2':50,'AC_50_CO':50,'AC_40_BP':-50,'AC_45_KO':500,
}

def run2(pos_dict):
    total = np.zeros(N)
    for name, vol in pos_dict.items():
        if name == 'AC_45_KO':
            cost = 0.175 if vol>0 else 0.150
            pay = ko(S3, minS, 1)
            total += (pay-cost)*vol*CS if vol>0 else (cost-pay)*abs(vol)*CS
        else:
            pay = payoffs[name]
            cost = asks[name] if vol>0 else costs[name]
            total += (pay-cost)*vol*CS if vol>0 else (cost-pay)*abs(vol)*CS
    return total

base = run2(current)
summary("CURRENT portfolio (in.csv)", base)

# PROPOSAL A: KO 500->450, add long 50 AC_45_P (buy at ask)
# Note: current already has -50 AC_45_P (short). Buying 50 closes that short.
# Net effect of A: AC_45_P goes from -50 to 0, KO goes from 500 to 450.
propA = dict(current)
propA['AC_45_P'] = 0
propA['AC_45_KO'] = 450
pA = run2(propA)
summary("PROPOSAL A (KO 500->450, close AC_45_P short)", pA)

# Net COST of proposal A vs current:
# Closing AC_45_P short: lose $9.050*50*3000 = $1,357,500 in collected premium
# Reducing KO by 50: save $0.175*50*3000 = $26,250
# NET ADDITIONAL COST = $1,357,500 - $26,250 = $1,331,250
print(f"\n  COST ANALYSIS FOR PROPOSAL A:")
print(f"  Closing AC_45_P short (lose premium collected): ${9.050*50*3000:>12,.0f}")
print(f"  Reducing 50 KO puts (save):                   -${0.175*50*3000:>12,.0f}")
print(f"  NET additional cost of Proposal A:              ${(9.050*50*3000 - 0.175*50*3000):>12,.0f}")
print(f"  KO savings cover {0.175*50*3000 / (9.050*50*3000) * 100:.1f}% of vanilla put cost")

# PROPOSAL B: Buy 15 long AC (underlying) to delta-hedge short calls
# Current has AC:-50 (short). Adding +15 goes to -35.
propB = dict(current)
propB['AC'] = -35  # was -50, buy 15 to reduce short
pB = run2(propB)
summary("PROPOSAL B (reduce short AC by 15: -50 -> -35)", pB)

# AC_55_C check
print("\n  NOTE: AC_55_C does NOT exist in the options market. Available calls: AC_50_C, AC_60_C only.")

# What if we add long AC_60_C instead (buy the cap)?
propC = dict(current)
propC['AC_60_C'] = -50  # keep as-is (already selling it)
# actually add buying it to create a call spread:
propC2 = dict(current)
propC2['AC_60_C'] = 0  # close the short 60C (no longer selling it)
pC2 = run2(propC2)
summary("Closing short AC_60_C (removes cap, higher upside exposure)", pC2)

# Combined A+B (as proposed):
propAB = dict(current)
propAB['AC_45_P'] = 0
propAB['AC_45_KO'] = 450
propAB['AC'] = -35
pAB = run2(propAB)
summary("A+B COMBINED (close AC_45_P short, KO->450, AC -50->-35)", pAB)

# DELTA analysis of current portfolio
T3 = steps_3w*dt; T2 = steps_2w*dt
def delta_call(K,T): 
    d1=(np.log(S0/K)+0.5*sigma**2*T)/(sigma*np.sqrt(T)); return stats.norm.cdf(d1)
def delta_put(K,T): return delta_call(K,T)-1

print(f"\n=== APPROXIMATE DELTA OF CURRENT PORTFOLIO (at S0=50) ===")
deltas = [
    ("AC -50",       -50*1.0),
    ("AC_50_P -50",  -50*delta_put(50,T3)),
    ("AC_50_C -50",  -50*delta_call(50,T3)),
    ("AC_35_P -50",  -50*delta_put(35,T3)),
    ("AC_40_P -50",  -50*delta_put(40,T3)),
    ("AC_45_P -50",  -50*delta_put(45,T3)),
    ("AC_60_C -50",  -50*delta_call(60,T3)),
    ("AC_50_P2 +50", +50*delta_put(50,T2)),
    ("AC_50_C2 +50", +50*delta_call(50,T2)),
    ("AC_50_CO +50", +50*(delta_call(50,T3)+delta_put(50,T2))),  # chooser approx
    ("AC_40_BP -50", -50*(-stats.norm.pdf((np.log(S0/40)+0.5*sigma**2*T3)/(sigma*np.sqrt(T3)))/(S0*sigma*np.sqrt(T3))*10)),
]
total_delta = 0
for name, d in deltas:
    print(f"  {name:<20} delta = {d:>+8.2f}")
    total_delta += d
print(f"  {'TOTAL DELTA':<20}       = {total_delta:>+8.2f}")
print(f"  Buying 15 AC would change total delta to: {total_delta+15:>+.2f}")
print(f"  Buying 50 AC would change total delta to: {total_delta+50:>+.2f}")
