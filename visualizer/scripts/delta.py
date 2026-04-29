"""Cumulative signed trade-flow (buy vs sell aggressor pressure) for a product.

Trade price > mid at that timestamp = buy aggressor (+qty)
Trade price < mid at that timestamp = sell aggressor (-qty)

Usage:
  python scripts/delta.py MICROCHIP_OVAL
  python scripts/delta.py OXYGEN_SHAKE_GARLIC --days 4
  python scripts/delta.py UV_VISOR_AMBER --json
"""
import sys, os, argparse, json
sys.path.insert(0, os.path.dirname(__file__))
from _load import prices, trades, resolve_days, ALL_PRODUCTS, fmt_ts
import numpy as np

parser = argparse.ArgumentParser()
parser.add_argument("product")
parser.add_argument("--days", nargs="+")
parser.add_argument("--json", action="store_true")
args = parser.parse_args()

product = args.product.upper()
if product not in ALL_PRODUCTS:
    sys.exit(f"Unknown product '{product}'. Run: python scripts/list.py")

days = resolve_days(args.days)
pf   = prices([product], days)
tf   = trades([product], days)

# Join trade price to mid at snapped timestamp
pf_snap = pf[["day","timestamp","mid_price"]].copy()
tf["snap_ts"] = (tf["timestamp"] // 100) * 100
tf = tf.merge(pf_snap.rename(columns={"timestamp":"snap_ts"}), on=["day","snap_ts"], how="left")
tf["signed_qty"] = np.where(tf["price"] > tf["mid_price"], tf["quantity"],
                   np.where(tf["price"] < tf["mid_price"], -tf["quantity"], 0))

total_buy  = int(tf[tf["signed_qty"] > 0]["signed_qty"].sum())
total_sell = int(tf[tf["signed_qty"] < 0]["signed_qty"].sum())

by_day = {}
for d in days:
    ddf = tf[tf["day"] == d]
    if ddf.empty:
        continue
    buy  = int(ddf[ddf["signed_qty"] > 0]["signed_qty"].sum())
    sell = int(ddf[ddf["signed_qty"] < 0]["signed_qty"].sum())
    by_day[f"day_{d}"] = {
        "buy_vol": buy, "sell_vol": sell,
        "net_delta": buy + sell, "n_trades": len(ddf),
    }

result = {
    "product":       product,
    "days":          days,
    "total_buy_vol": total_buy,
    "total_sell_vol":total_sell,
    "net_delta":     total_buy + total_sell,
    "flow_bias":     "buy-heavy" if total_buy > abs(total_sell) else "sell-heavy",
    "by_day":        by_day,
}

if args.json:
    print(json.dumps(result, indent=2))
else:
    for k, v in result.items():
        if isinstance(v, dict):
            print(f"{k}:")
            for dk, dv in v.items():
                if isinstance(dv, dict):
                    print(f"  {dk}: {dv}")
                else:
                    print(f"  {dk}: {dv}")
        else:
            print(f"{k}: {v}")
