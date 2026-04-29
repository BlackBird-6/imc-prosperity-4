"""Purification Pebbles basket-sum analysis (constraint: ~50,000).

Usage:
  python scripts/basket.py
  python scripts/basket.py --days 2 3
  python scripts/basket.py --json
"""
import sys, os, argparse, json
sys.path.insert(0, os.path.dirname(__file__))
from _load import prices, resolve_days, fmt_ts
import numpy as np

parser = argparse.ArgumentParser()
parser.add_argument("--days", nargs="+")
parser.add_argument("--json", action="store_true")
args = parser.parse_args()

PEBBLES = ["PEBBLES_XS","PEBBLES_S","PEBBLES_M","PEBBLES_L","PEBBLES_XL"]
days = resolve_days(args.days)
pf   = prices(PEBBLES, days)

piv    = pf.pivot_table(index="global_ts", columns="product", values="mid_price").dropna()
basket = piv.sum(axis=1)
dev    = basket - 50_000
outliers = dev[dev.abs() > 5]

result = {
    "basket_target":     50_000,
    "mean_sum":          round(float(basket.mean()), 2),
    "std_dev":           round(float(basket.std()), 2),
    "min_sum":           round(float(basket.min()), 2),
    "max_sum":           round(float(basket.max()), 2),
    "pct_within_0.5":    round(float((dev.abs() <= 0.5).mean()*100), 1),
    "pct_within_1.0":    round(float((dev.abs() <= 1.0).mean()*100), 1),
    "n_outliers_gt5":    int((dev.abs() > 5).sum()),
    "max_positive_dev":  round(float(dev.max()), 2),
    "max_negative_dev":  round(float(dev.min()), 2),
    "outlier_timestamps":[fmt_ts(ts) for ts in outliers.index[:20]],
}

if args.json:
    print(json.dumps(result, indent=2))
else:
    print(f"\nPurification Pebbles -- Basket Sum | Days: {days}\n")
    for k, v in result.items():
        print(f"  {k}: {v}")
