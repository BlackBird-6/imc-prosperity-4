"""XIRECS sweep events — timestamps where many products trade simultaneously.

Sweep tiers:
  1-20 products  = single-category sweep (localised reprice)
  21-60 products = multi-category sweep (broad market move)
  61+  products  = market-wide sweep (regime event)

Usage:
  python scripts/sweep.py
  python scripts/sweep.py --min-size 40
  python scripts/sweep.py --min-size 5 --days 3 --json
"""
import sys, os, argparse, json
sys.path.insert(0, os.path.dirname(__file__))
from _load import trades, resolve_days, fmt_ts, table
from collections import Counter
import pandas as pd

parser = argparse.ArgumentParser()
parser.add_argument("--days", nargs="+")
parser.add_argument("--min-size", type=int, default=1)
parser.add_argument("--json", action="store_true")
args = parser.parse_args()

days = resolve_days(args.days)
tf   = trades(days=days)

sweep = tf.groupby("global_ts")["product"].nunique().reset_index()
sweep.columns = ["global_ts", "sweep_size"]
sweep = sweep[sweep["sweep_size"] >= args.min_size].sort_values("global_ts")

def tier(n):
    if n <= 20:  return "single-category"
    if n <= 60:  return "multi-category"
    return "market-wide"

sweep["tier"] = sweep["sweep_size"].apply(tier)

rows = [{"timestamp": fmt_ts(r["global_ts"]), "sweep_size": int(r["sweep_size"]), "tier": r["tier"]}
        for _, r in sweep.iterrows()]

if args.json:
    tier_summary = dict(Counter(r["tier"] for r in rows))
    print(json.dumps({"days": days, "min_size": args.min_size,
                      "total_events": len(rows), "by_tier": tier_summary, "events": rows}, indent=2))
else:
    print(f"\nXIRECS Sweep Events | Days: {days} | Min size: {args.min_size}")
    print(f"Total events: {len(rows)}\n")
    for t, cnt in Counter(r["tier"] for r in rows).items():
        print(f"  {t}: {cnt}")
    big = [r for r in rows if r["sweep_size"] >= 40]
    if big:
        print(f"\nLarge sweeps (>=40 products): {len(big)}")
        table(big, ["timestamp","sweep_size","tier"])
