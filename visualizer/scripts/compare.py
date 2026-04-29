"""Side-by-side stat comparison for any set of products.

Usage:
  python scripts/compare.py MICROCHIP_OVAL MICROCHIP_CIRCLE MICROCHIP_SQUARE
  python scripts/compare.py OXYGEN_SHAKE_GARLIC GALAXY_SOUNDS_BLACK_HOLES --days 4
  python scripts/compare.py ROBOT_IRONING UV_VISOR_AMBER --json
"""
import sys, os, argparse, json
sys.path.insert(0, os.path.dirname(__file__))
from _load import prices, trades, resolve_days, ALL_PRODUCTS, PRODUCT_TO_CAT, table
import numpy as np
from scipy import stats as sp

parser = argparse.ArgumentParser()
parser.add_argument("products", nargs="+")
parser.add_argument("--days", nargs="+")
parser.add_argument("--json", action="store_true")
args = parser.parse_args()

prods = [p.upper() for p in args.products]
bad   = [p for p in prods if p not in ALL_PRODUCTS]
if bad:
    sys.exit(f"Unknown products: {bad}. Run: python scripts/list.py")

days   = resolve_days(args.days)
pf_all = prices(prods, days)
tf_all = trades(prods, days)

rows = []
for prod in prods:
    pf = pf_all[pf_all["product"] == prod].sort_values("global_ts")
    tf = tf_all[tf_all["product"] == prod]
    if pf.empty:
        continue
    mid   = pf["mid_price"].values
    slope, _, r, *_ = sp.linregress(pf["global_ts"].values.astype(float), mid)
    returns = np.diff(mid)
    run_max = np.maximum.accumulate(mid)
    ac = float(np.corrcoef(returns[:-1], returns[1:])[0,1]) if len(returns) > 2 else None
    rows.append({
        "product":     prod,
        "category":    PRODUCT_TO_CAT.get(prod,""),
        "start":       round(float(mid[0]),1),
        "end":         round(float(mid[-1]),1),
        "drift/day":   round(float((mid[-1]-mid[0])/len(days)),1),
        "ols/day":     round(float(slope*1_000_000),1),
        "r2":          round(float(r**2),3),
        "vol%":        round(float(mid.std()/mid.mean()*100),2),
        "max_dd":      round(float((mid-run_max).min()),1),
        "ac_lag1":     round(ac,4) if ac else None,
        "mean_spread": round(float(pf["spread"].mean()),2),
        "n_trades":    len(tf),
    })

if args.json:
    print(json.dumps({"days": days, "products": rows}, indent=2))
else:
    print(f"\nComparing {len(prods)} products | Days: {days}\n")
    table(rows, ["product","category","start","end","drift/day","ols/day","r2","vol%","max_dd","ac_lag1","mean_spread","n_trades"])
