"""Stats table for all 5 products in a category.

Usage:
  python scripts/category.py "UV-Visors"
  python scripts/category.py "robots" --days 3 4
  python scripts/category.py "Pebbles" --json
"""
import sys, os, argparse, json
sys.path.insert(0, os.path.dirname(__file__))
from _load import prices, trades, resolve_days, CATEGORIES, match_category, table
import numpy as np
from scipy import stats as sp

parser = argparse.ArgumentParser()
parser.add_argument("category")
parser.add_argument("--days", nargs="+")
parser.add_argument("--json", action="store_true")
args = parser.parse_args()

cat   = match_category(args.category)
prods = CATEGORIES[cat]
days  = resolve_days(args.days)

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
        "product":      prod.split("_")[-1],
        "start":        round(float(mid[0]), 1),
        "end":          round(float(mid[-1]), 1),
        "drift/day":    round(float((mid[-1]-mid[0])/len(days)), 1),
        "ols/day":      round(float(slope*1_000_000), 1),
        "r2":           round(float(r**2), 3),
        "vol%":         round(float(mid.std()/mid.mean()*100), 2),
        "max_dd":       round(float((mid-run_max).min()), 1),
        "ac_lag1":      round(ac, 4) if ac else None,
        "mean_spread":  round(float(pf["spread"].mean()), 2),
        "n_trades":     len(tf),
    })

if args.json:
    print(json.dumps({"category": cat, "days": days, "products": rows}, indent=2))
else:
    print(f"\n{cat} | Days: {days}\n")
    table(rows, ["product","start","end","drift/day","ols/day","r2","vol%","max_dd","ac_lag1","mean_spread","n_trades"])
