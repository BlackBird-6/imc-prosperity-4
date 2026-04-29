import numpy as np
import pandas as pd
from scipy import stats as sp

DAY_OFFSET = 1_000_000


def product_stats(price_df: pd.DataFrame, trade_df: pd.DataFrame) -> dict:
    if price_df.empty:
        return {}

    mid = price_df["mid_price"].values
    spreads = price_df["spread"].values

    start, end = mid[0], mid[-1]
    total_drift = end - start
    drift_pct = total_drift / start * 100 if start else 0
    n_days = price_df["day"].nunique()
    drift_per_day = total_drift / n_days if n_days else 0

    x = price_df["global_ts"].values.astype(float)
    slope, intercept, r, *_ = sp.linregress(x, mid)
    ols_per_day = slope * DAY_OFFSET
    r2 = r ** 2

    mean_p = np.mean(mid)
    std_p = np.std(mid)
    vol_pct = std_p / mean_p * 100 if mean_p else 0

    min_i, max_i = np.argmin(mid), np.argmax(mid)

    # Max drawdown
    run_max = np.maximum.accumulate(mid)
    dd = mid - run_max
    max_dd = np.min(dd)
    dd_ref = run_max[np.argmin(dd)]
    max_dd_pct = max_dd / dd_ref * 100 if dd_ref else 0

    # Max runup
    run_min = np.minimum.accumulate(mid)
    ru = mid - run_min
    max_ru = np.max(ru)
    ru_ref = run_min[np.argmax(ru)]
    max_ru_pct = max_ru / ru_ref * 100 if ru_ref else 0

    returns = np.diff(mid)
    ac = pd.Series(returns).autocorr(lag=1) if len(returns) > 1 else np.nan
    half_life = -np.log(2) / np.log(ac) if (not np.isnan(ac) and 0 < ac < 1) else None
    skew = float(sp.skew(returns)) if len(returns) > 2 else None
    kurt = float(sp.kurtosis(returns)) if len(returns) > 2 else None

    n_trades = len(trade_df)
    avg_qty = trade_df["quantity"].mean() if n_trades else None
    trade_freq = n_trades / len(price_df) * 1000 if len(price_df) else 0

    def _fmt_ts(gts):
        day = int(gts) // DAY_OFFSET + 2
        ts = int(gts) % DAY_OFFSET
        return f"D{day}@{ts}"

    return {
        "start_price":    round(float(start), 1),
        "end_price":      round(float(end), 1),
        "total_drift":    round(float(total_drift), 1),
        "drift_pct":      round(float(drift_pct), 2),
        "drift_per_day":  round(float(drift_per_day), 1),
        "ols_slope":      round(float(ols_per_day), 1),
        "r2":             round(float(r2), 3),
        "mean":           round(float(mean_p), 1),
        "std_dev":        round(float(std_p), 1),
        "vol_pct":        round(float(vol_pct), 2),
        "min_price":      round(float(mid[min_i]), 1),
        "max_price":      round(float(mid[max_i]), 1),
        "min_at":         _fmt_ts(price_df["global_ts"].iloc[min_i]),
        "max_at":         _fmt_ts(price_df["global_ts"].iloc[max_i]),
        "max_drawdown":   round(float(max_dd), 1),
        "max_dd_pct":     round(float(max_dd_pct), 2),
        "max_runup":      round(float(max_ru), 1),
        "max_ru_pct":     round(float(max_ru_pct), 2),
        "autocorr_l1":    round(float(ac), 4) if not np.isnan(ac) else None,
        "half_life":      round(float(half_life), 1) if half_life else None,
        "skewness":       round(skew, 3) if skew is not None else None,
        "kurtosis":       round(kurt, 3) if kurt is not None else None,
        "mean_spread":    round(float(np.nanmean(spreads)), 2),
        "spread_pct":     round(float(np.nanmean(spreads) / mean_p * 100), 3) if mean_p else None,
        "n_trades":       n_trades,
        "avg_trade_qty":  round(float(avg_qty), 2) if avg_qty is not None else None,
        "trade_freq":     round(float(trade_freq), 3),
    }


def category_stats_table(price_df: pd.DataFrame, trade_df: pd.DataFrame, products: list) -> list[dict]:
    rows = []
    for p in products:
        s = product_stats(
            price_df[price_df["product"] == p],
            trade_df[trade_df["product"] == p],
        )
        if s:
            s["product"] = p.split("_", 1)[-1] if "_" in p else p
            s["full_name"] = p
            rows.append(s)
    return rows


STATS_COLUMNS = [
    {"name": "Product",      "id": "product"},
    {"name": "Start",        "id": "start_price",   "type": "numeric", "format": {"specifier": ".1f"}},
    {"name": "End",          "id": "end_price",      "type": "numeric", "format": {"specifier": ".1f"}},
    {"name": "Drift",        "id": "total_drift",    "type": "numeric", "format": {"specifier": "+.1f"}},
    {"name": "Drift %",      "id": "drift_pct",      "type": "numeric", "format": {"specifier": "+.2f"}},
    {"name": "Drift/Day",    "id": "drift_per_day",  "type": "numeric", "format": {"specifier": "+.1f"}},
    {"name": "OLS/Day",      "id": "ols_slope",      "type": "numeric", "format": {"specifier": "+.1f"}},
    {"name": "R²",           "id": "r2",             "type": "numeric", "format": {"specifier": ".3f"}},
    {"name": "Mean",         "id": "mean",           "type": "numeric", "format": {"specifier": ".1f"}},
    {"name": "Std Dev",      "id": "std_dev",        "type": "numeric", "format": {"specifier": ".1f"}},
    {"name": "Vol %",        "id": "vol_pct",        "type": "numeric", "format": {"specifier": ".2f"}},
    {"name": "Min",          "id": "min_price",      "type": "numeric", "format": {"specifier": ".1f"}},
    {"name": "Max",          "id": "max_price",      "type": "numeric", "format": {"specifier": ".1f"}},
    {"name": "Max DD",       "id": "max_drawdown",   "type": "numeric", "format": {"specifier": ".1f"}},
    {"name": "Max DD %",     "id": "max_dd_pct",     "type": "numeric", "format": {"specifier": ".2f"}},
    {"name": "Max Runup",    "id": "max_runup",      "type": "numeric", "format": {"specifier": ".1f"}},
    {"name": "AC Lag-1",     "id": "autocorr_l1",    "type": "numeric", "format": {"specifier": ".4f"}},
    {"name": "Half-Life",    "id": "half_life",      "type": "numeric", "format": {"specifier": ".1f"}},
    {"name": "Skew",         "id": "skewness",       "type": "numeric", "format": {"specifier": ".3f"}},
    {"name": "Kurt",         "id": "kurtosis",       "type": "numeric", "format": {"specifier": ".3f"}},
    {"name": "Avg Spread",   "id": "mean_spread",    "type": "numeric", "format": {"specifier": ".2f"}},
    {"name": "Spread %",     "id": "spread_pct",     "type": "numeric", "format": {"specifier": ".3f"}},
    {"name": "Trades",       "id": "n_trades",       "type": "numeric"},
    {"name": "Avg Qty",      "id": "avg_trade_qty",  "type": "numeric", "format": {"specifier": ".2f"}},
    {"name": "Trade/1k ts",  "id": "trade_freq",     "type": "numeric", "format": {"specifier": ".3f"}},
]
