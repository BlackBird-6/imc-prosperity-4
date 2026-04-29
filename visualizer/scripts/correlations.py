"""Pairwise return correlations within a category.

Usage:
  python scripts/correlations.py "UV-Visors"
  python scripts/correlations.py "robots" --days 2 3
  python scripts/correlations.py "Microchips" --json
"""
import sys, os, argparse, json
sys.path.insert(0, os.path.dirname(__file__))
from _load import prices, resolve_days, CATEGORIES, match_category
import numpy as np

parser = argparse.ArgumentParser()
parser.add_argument("category")
parser.add_argument("--days", nargs="+")
parser.add_argument("--json", action="store_true")
args = parser.parse_args()

cat   = match_category(args.category)
prods = CATEGORIES[cat]
days  = resolve_days(args.days)
pf    = prices(prods, days)

returns = {}
for p in prods:
    mid = pf[pf["product"] == p].sort_values("global_ts")["mid_price"]
    returns[p] = mid.diff().dropna().values

min_len = min(len(v) for v in returns.values())
arr  = np.array([returns[p][:min_len] for p in prods])
corr = np.corrcoef(arr)
labels = [p.split("_")[-1] for p in prods]

if args.json:
    matrix = {prods[i]: {prods[j]: round(float(corr[i,j]),4) for j in range(len(prods))} for i in range(len(prods))}
    print(json.dumps({"category": cat, "days": days, "correlation_matrix": matrix}, indent=2))
else:
    print(f"\nReturn Correlations -- {cat} | Days: {days}\n")
    w = max(len(l) for l in labels)
    print(" "*w + "  " + "  ".join(l.rjust(8) for l in labels))
    print("-" * (w + 2 + 10*len(labels)))
    for i, label in enumerate(labels):
        vals = "  ".join(f"{corr[i,j]:+.4f}" for j in range(len(prods)))
        print(f"{label.ljust(w)}  {vals}")
