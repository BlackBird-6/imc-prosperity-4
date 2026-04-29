"""Per-day OHLC breakdown for a product.

Usage:
  python scripts/day.py ROBOT_IRONING
  python scripts/day.py PANEL_2X4 --json
"""
import sys, os, argparse, json
sys.path.insert(0, os.path.dirname(__file__))
from _load import prices, ALL_PRODUCTS, table
import numpy as np

parser = argparse.ArgumentParser()
parser.add_argument("product")
parser.add_argument("--json", action="store_true")
args = parser.parse_args()

product = args.product.upper()
if product not in ALL_PRODUCTS:
    sys.exit(f"Unknown product '{product}'. Run: python scripts/list.py")

pf = prices([product])
rows = []
for day in [2, 3, 4]:
    dpf = pf[pf["day"] == day].sort_values("timestamp")
    if dpf.empty:
        continue
    mid = dpf["mid_price"].values
    ts  = dpf["timestamp"].values
    run_max = np.maximum.accumulate(mid)
    early = dpf[dpf["timestamp"] <= 100_000]["mid_price"]
    late  = dpf[dpf["timestamp"] >= 900_000]["mid_price"]
    rows.append({
        "day":             day,
        "open":            round(float(mid[0]), 1),
        "close":           round(float(mid[-1]), 1),
        "high":            round(float(mid.max()), 1),
        "low":             round(float(mid.min()), 1),
        "drift":           round(float(mid[-1]-mid[0]), 1),
        "drift_pct":       round(float((mid[-1]-mid[0])/mid[0]*100), 2),
        "max_drawdown":    round(float((mid-run_max).min()), 1),
        "peak_ts":         int(ts[np.argmax(mid)]),
        "trough_ts":       int(ts[np.argmin(mid)]),
        "first_100k_drift":round(float(early.iloc[-1]-mid[0]), 1) if len(early) else None,
        "last_100k_drift": round(float(mid[-1]-late.iloc[0]), 1) if len(late) else None,
    })

if args.json:
    print(json.dumps({"product": product, "days": rows}, indent=2))
else:
    print(f"\nPer-day breakdown -- {product}\n")
    table(rows, ["day","open","close","high","low","drift","drift_pct","max_drawdown","peak_ts","trough_ts","first_100k_drift","last_100k_drift"])
