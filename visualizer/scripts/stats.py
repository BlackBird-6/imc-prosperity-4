"""All stats for a single product.

Usage:
  python scripts/stats.py MICROCHIP_OVAL
  python scripts/stats.py OXYGEN_SHAKE_GARLIC --days 3 4
  python scripts/stats.py UV_VISOR_AMBER --json
"""
import sys, os, argparse, json
sys.path.insert(0, os.path.dirname(__file__))
from _load import prices, trades, resolve_days, ALL_PRODUCTS, PRODUCT_TO_CAT, fmt_ts
import numpy as np
from scipy import stats as sp

parser = argparse.ArgumentParser()
parser.add_argument("product")
parser.add_argument("--days", nargs="+")
parser.add_argument("--json", action="store_true")
args = parser.parse_args()

product = args.product.upper()
if product not in ALL_PRODUCTS:
    sys.exit(f"Unknown product '{product}'. Run: python scripts/list.py")

days = resolve_days(args.days)
pf = prices([product], days).sort_values("global_ts")
tf = trades([product], days)

mid = pf["mid_price"].values
spreads = pf["spread"].values
start, end = mid[0], mid[-1]
n_days = len(days)

slope, _, r, *_ = sp.linregress(pf["global_ts"].values.astype(float), mid)
returns = np.diff(mid)
run_max = np.maximum.accumulate(mid)
dd = mid - run_max
run_min = np.minimum.accumulate(mid)
ru = mid - run_min

ac = float(np.corrcoef(returns[:-1], returns[1:])[0,1]) if len(returns) > 2 else None
half_life = round(-np.log(2)/np.log(ac), 1) if ac and 0 < ac < 1 else None

n_trades = len(tf)
mid_lookup = pf.set_index("timestamp")["mid_price"].to_dict()

result = {
    "product":        product,
    "category":       PRODUCT_TO_CAT.get(product),
    "days":           days,
    "start_price":    round(float(start), 1),
    "end_price":      round(float(end), 1),
    "total_drift":    round(float(end - start), 1),
    "drift_pct":      round(float((end-start)/start*100), 2),
    "drift_per_day":  round(float((end-start)/n_days), 1),
    "ols_per_day":    round(float(slope*1_000_000), 1),
    "r2":             round(float(r**2), 3),
    "mean":           round(float(mid.mean()), 1),
    "std_dev":        round(float(mid.std()), 1),
    "vol_pct":        round(float(mid.std()/mid.mean()*100), 2),
    "min_price":      round(float(mid.min()), 1),
    "max_price":      round(float(mid.max()), 1),
    "min_at":         fmt_ts(pf["global_ts"].iloc[int(np.argmin(mid))]),
    "max_at":         fmt_ts(pf["global_ts"].iloc[int(np.argmax(mid))]),
    "max_drawdown":   round(float(dd.min()), 1),
    "max_dd_pct":     round(float(dd.min()/run_max[np.argmin(dd)]*100), 2),
    "max_runup":      round(float(ru.max()), 1),
    "autocorr_lag1":  round(ac, 4) if ac is not None else None,
    "half_life_steps":half_life,
    "skewness":       round(float(sp.skew(returns)), 3),
    "kurtosis":       round(float(sp.kurtosis(returns)), 3),
    "mean_spread":    round(float(np.nanmean(spreads)), 2),
    "spread_pct":     round(float(np.nanmean(spreads)/mid.mean()*100), 3),
    "n_trades":       n_trades,
    "avg_trade_qty":  round(float(tf["quantity"].mean()), 2) if n_trades else None,
    "trade_per_1k_ts":round(float(n_trades/len(pf)*1000), 3),
}

if args.json:
    print(json.dumps(result, indent=2))
else:
    for k, v in result.items():
        print(f"  {k}: {v}")
