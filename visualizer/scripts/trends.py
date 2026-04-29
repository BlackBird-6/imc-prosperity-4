"""Rank all 50 products by drift/day.

Usage:
  python scripts/trends.py
  python scripts/trends.py --direction long
  python scripts/trends.py --direction short --min-drift 500
  python scripts/trends.py --days 4 --json
"""
import sys, os, argparse, json
sys.path.insert(0, os.path.dirname(__file__))
from _load import prices, resolve_days, ALL_PRODUCTS, PRODUCT_TO_CAT, table
import numpy as np
from scipy import stats as sp

parser = argparse.ArgumentParser()
parser.add_argument("--days", nargs="+")
parser.add_argument("--direction", choices=["long","short"])
parser.add_argument("--min-drift", type=float, default=0)
parser.add_argument("--json", action="store_true")
args = parser.parse_args()

days = resolve_days(args.days)
# Load all prices in one pass
pf_all = prices(days=days)

rows = []
for prod in ALL_PRODUCTS:
    pf = pf_all[pf_all["product"] == prod].sort_values("global_ts")
    if pf.empty:
        continue
    mid = pf["mid_price"].values
    drift_per_day = (mid[-1] - mid[0]) / len(days)
    slope, _, r, *_ = sp.linregress(pf["global_ts"].values.astype(float), mid)
    rows.append({
        "direction":    "long" if drift_per_day > 0 else "short",
        "product":      prod,
        "category":     PRODUCT_TO_CAT.get(prod, ""),
        "drift_per_day":round(float(drift_per_day), 1),
        "total_drift":  round(float(mid[-1]-mid[0]), 1),
        "ols_per_day":  round(float(slope*1_000_000), 1),
        "r2":           round(float(r**2), 3),
        "vol_pct":      round(float(mid.std()/mid.mean()*100), 2),
    })

if args.direction:
    rows = [r for r in rows if r["direction"] == args.direction]
rows = [r for r in rows if abs(r["drift_per_day"]) >= args.min_drift]
rows.sort(key=lambda r: abs(r["drift_per_day"]), reverse=True)

if args.json:
    print(json.dumps({"days": days, "results": rows}, indent=2))
else:
    print(f"\nTrends | Days: {days} | Direction: {args.direction or 'all'} | Min |drift/day|: {args.min_drift}\n")
    table(rows, ["direction","product","category","drift_per_day","total_drift","ols_per_day","r2","vol_pct"])
