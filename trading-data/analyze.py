#!/usr/bin/env python3
"""
Prosperity 4 — Market Data Analyzer
Usage: python analyze.py <data_directory>

Reads prices_round_*_day_*.csv and trades_round_*_day_*.csv files,
generates a multi-panel chart (PNG) and prints summary statistics.
"""

import sys
import os
import glob
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.gridspec import GridSpec
from collections import defaultdict


def load_data(directory):
    """Load all price and trade CSVs from a directory."""
    price_files = sorted(glob.glob(os.path.join(directory, "prices_round_*.csv")))
    trade_files = sorted(glob.glob(os.path.join(directory, "trades_round_*.csv")))

    if not price_files:
        print(f"No price files found in {directory}")
        sys.exit(1)

    prices = pd.concat(
        [pd.read_csv(f, sep=';') for f in price_files],
        ignore_index=True
    )
    trades = pd.concat(
        [pd.read_csv(f, sep=';') for f in trade_files],
        ignore_index=True
    ) if trade_files else pd.DataFrame()

    return prices, trades


def compute_stats(prices, trades):
    """Compute per-product statistics."""
    stats = {}
    for product in sorted(prices['product'].unique()):
        p = prices[prices['product'] == product].copy()
        p = p[p['mid_price'] > 0]  # filter empty book rows

        s = {}
        s['rows'] = len(p)
        s['days'] = sorted(p['day'].unique())
        s['mid_mean'] = p['mid_price'].mean()
        s['mid_std'] = p['mid_price'].std()
        s['mid_min'] = p['mid_price'].min()
        s['mid_max'] = p['mid_price'].max()

        # Spread
        has_both = p['bid_price_1'].notna() & p['ask_price_1'].notna()
        spreads = p.loc[has_both, 'ask_price_1'] - p.loc[has_both, 'bid_price_1']
        s['spread_mean'] = spreads.mean() if len(spreads) > 0 else None
        s['spread_median'] = spreads.median() if len(spreads) > 0 else None

        # Return autocorrelation
        mid = p.sort_values(['day', 'timestamp'])['mid_price']
        returns = mid.diff().dropna()
        if len(returns) > 10:
            s['ac_returns_1'] = returns.autocorr(lag=1)
            s['ac_level_1'] = mid.autocorr(lag=1)
        else:
            s['ac_returns_1'] = None
            s['ac_level_1'] = None

        # L1 vs L2 volume comparison
        has_l2 = p['bid_volume_2'].notna()
        if has_l2.sum() > 0:
            l1_bigger = (p.loc[has_l2, 'bid_volume_1'] > p.loc[has_l2, 'bid_volume_2']).sum()
            l2_bigger = (p.loc[has_l2, 'bid_volume_2'] >= p.loc[has_l2, 'bid_volume_1']).sum()
            s['l2_bigger_pct'] = l2_bigger / (l1_bigger + l2_bigger) * 100
        else:
            s['l2_bigger_pct'] = None

        s['l1_vol_mean'] = p['bid_volume_1'].mean()
        s['l2_pct_present'] = has_l2.mean() * 100

        # Drift detection (linear regression on mid vs timestamp)
        per_day_drift = []
        for day in s['days']:
            dp = p[p['day'] == day].sort_values('timestamp')
            if len(dp) > 100:
                ts = dp['timestamp'].values.astype(float)
                mp = dp['mid_price'].values.astype(float)
                if ts[-1] > ts[0]:
                    slope = np.polyfit(ts, mp, 1)[0]
                    per_day_drift.append(slope)
        s['drift_per_ts'] = np.mean(per_day_drift) if per_day_drift else 0
        s['drift_per_day'] = s['drift_per_ts'] * 1_000_000 if s['drift_per_ts'] else 0

        # Trade stats
        if len(trades) > 0:
            t = trades[trades['symbol'] == product]
            s['trade_count'] = len(t)
            s['trade_vol_total'] = t['quantity'].sum() if len(t) > 0 else 0
            s['trade_size_mean'] = t['quantity'].mean() if len(t) > 0 else 0
        else:
            s['trade_count'] = 0
            s['trade_vol_total'] = 0
            s['trade_size_mean'] = 0

        stats[product] = s
    return stats


def plot_charts(prices, trades, stats, output_path):
    """Generate multi-panel analysis chart."""
    products = sorted(prices['product'].unique())
    n_products = len(products)

    # Color palette
    colors = plt.cm.Set2(np.linspace(0, 1, max(n_products, 3)))

    fig = plt.figure(figsize=(18, 5 * n_products + 3))
    gs = GridSpec(n_products + 1, 4, figure=fig, hspace=0.45, wspace=0.35)

    # ── Row per product: mid price, spread dist, trade prices, volume ──
    for i, product in enumerate(products):
        p = prices[prices['product'] == product].copy()
        p = p[p['mid_price'] > 0]
        color = colors[i]
        short_name = product.replace('_', ' ')

        # Panel 1: Mid-price over time (by day)
        ax1 = fig.add_subplot(gs[i, 0:2])
        for day in sorted(p['day'].unique()):
            dp = p[p['day'] == day].sort_values('timestamp')
            ax1.plot(dp['timestamp'], dp['mid_price'], alpha=0.7, linewidth=0.8,
                     label=f"Day {day}")
        ax1.set_title(f"{short_name} — Mid Price", fontsize=11, fontweight='bold')
        ax1.set_xlabel("Timestamp")
        ax1.set_ylabel("Mid Price")
        ax1.legend(fontsize=8)
        ax1.grid(True, alpha=0.3)

        # Annotate drift if significant
        drift = stats[product]['drift_per_ts']
        if abs(drift) > 0.0001:
            ax1.text(0.02, 0.95, f"Drift: {drift:.6f}/ts ({stats[product]['drift_per_day']:.0f}/day)",
                     transform=ax1.transAxes, fontsize=8, verticalalignment='top',
                     bbox=dict(boxstyle='round', facecolor='yellow', alpha=0.5))

        # Panel 2: Spread distribution
        ax2 = fig.add_subplot(gs[i, 2])
        has_both = p['bid_price_1'].notna() & p['ask_price_1'].notna()
        spreads = (p.loc[has_both, 'ask_price_1'] - p.loc[has_both, 'bid_price_1']).dropna()
        if len(spreads) > 0:
            spread_counts = spreads.value_counts().sort_index()
            top_spreads = spread_counts.head(15)
            ax2.bar(top_spreads.index.astype(str), top_spreads.values, color=color, alpha=0.8)
            ax2.set_title(f"Spread Distribution", fontsize=10)
            ax2.set_xlabel("Spread")
            ax2.set_ylabel("Count")
            ax2.tick_params(axis='x', rotation=45, labelsize=7)
            med = spreads.median()
            ax2.axvline(x=list(top_spreads.index.astype(str)).index(str(int(med)))
                        if str(int(med)) in list(top_spreads.index.astype(str)) else 0,
                        color='red', linestyle='--', alpha=0.5, label=f'Median={med:.0f}')
            ax2.legend(fontsize=7)

        # Panel 3: Trade analysis
        ax3 = fig.add_subplot(gs[i, 3])
        if len(trades) > 0:
            t = trades[trades['symbol'] == product].copy()
            if len(t) > 0:
                ax3.hist(t['quantity'], bins=range(int(t['quantity'].min()),
                         int(t['quantity'].max()) + 2), color=color, alpha=0.8,
                         edgecolor='black', linewidth=0.5)
                ax3.set_title(f"Trade Size Distribution", fontsize=10)
                ax3.set_xlabel("Quantity")
                ax3.set_ylabel("Count")
                ax3.text(0.95, 0.95,
                         f"n={len(t)}\nmean={t['quantity'].mean():.1f}\nvol={t['quantity'].sum()}",
                         transform=ax3.transAxes, fontsize=8, verticalalignment='top',
                         horizontalalignment='right',
                         bbox=dict(boxstyle='round', facecolor='lightyellow', alpha=0.8))

    # ── Bottom row: Summary statistics table ──
    ax_table = fig.add_subplot(gs[n_products, :])
    ax_table.axis('off')

    col_labels = ['Product', 'Days', 'Mid Mean', 'Mid Std', 'Range',
                  'Spread (med)', 'AC(ret)', 'AC(lvl)', 'Drift/ts',
                  'L2>L1%', 'Trades', 'Avg Size']
    table_data = []
    for product in products:
        s = stats[product]
        table_data.append([
            product[:20],
            str(s['days']),
            f"{s['mid_mean']:.1f}",
            f"{s['mid_std']:.2f}",
            f"{s['mid_min']:.0f}–{s['mid_max']:.0f}",
            f"{s['spread_median']:.0f}" if s['spread_median'] else "N/A",
            f"{s['ac_returns_1']:.3f}" if s['ac_returns_1'] is not None else "N/A",
            f"{s['ac_level_1']:.3f}" if s['ac_level_1'] is not None else "N/A",
            f"{s['drift_per_ts']:.6f}" if abs(s['drift_per_ts']) > 1e-6 else "~0",
            f"{s['l2_bigger_pct']:.0f}%" if s['l2_bigger_pct'] is not None else "N/A",
            str(s['trade_count']),
            f"{s['trade_size_mean']:.1f}" if s['trade_size_mean'] else "N/A",
        ])

    table = ax_table.table(cellText=table_data, colLabels=col_labels,
                           cellLoc='center', loc='center')
    table.auto_set_font_size(False)
    table.set_fontsize(8)
    table.scale(1, 1.4)

    # Style header row
    for j, label in enumerate(col_labels):
        table[0, j].set_facecolor('#4472C4')
        table[0, j].set_text_props(color='white', fontweight='bold')

    # Alternate row colors
    for i in range(len(table_data)):
        for j in range(len(col_labels)):
            if i % 2 == 0:
                table[i + 1, j].set_facecolor('#D9E2F3')

    round_name = os.path.basename(os.path.normpath(directory))
    fig.suptitle(f"Prosperity 4 — {round_name} Market Data Analysis",
                 fontsize=14, fontweight='bold', y=0.98)

    plt.savefig(output_path, dpi=150, bbox_inches='tight', facecolor='white')
    print(f"Chart saved to: {output_path}")
    plt.close()


def print_stats(stats):
    """Print formatted statistics to console."""
    print("\n" + "=" * 70)
    print("  SUMMARY STATISTICS")
    print("=" * 70)

    for product, s in stats.items():
        print(f"\n  {product}")
        print(f"  {'-' * 50}")
        print(f"  {'Days:':<25} {s['days']}")
        print(f"  {'Mid price:':<25} {s['mid_mean']:.1f} ± {s['mid_std']:.2f}  [{s['mid_min']:.0f} – {s['mid_max']:.0f}]")
        print(f"  {'Spread (median):':<25} {s['spread_median']:.0f}" if s['spread_median'] else f"  {'Spread:':<25} N/A")
        print(f"  {'AC(returns, lag1):':<25} {s['ac_returns_1']:.3f}" if s['ac_returns_1'] is not None else "")
        print(f"  {'AC(level, lag1):':<25} {s['ac_level_1']:.3f}" if s['ac_level_1'] is not None else "")

        if abs(s['drift_per_ts']) > 1e-6:
            print(f"  {'Drift rate:':<25} {s['drift_per_ts']:.6f}/ts  ({s['drift_per_day']:.0f}/day)")
            role = "DRIFTING"
        else:
            print(f"  {'Drift rate:':<25} ~0 (stationary)")
            role = "STABLE"

        print(f"  {'Role:':<25} {role}")

        if s['l2_bigger_pct'] is not None:
            print(f"  {'L2 > L1 volume:':<25} {s['l2_bigger_pct']:.0f}% of the time")
        print(f"  {'L1 avg volume:':<25} {s['l1_vol_mean']:.1f}")
        print(f"  {'L2 present:':<25} {s['l2_pct_present']:.0f}% of ticks")
        print(f"  {'Trades:':<25} {s['trade_count']} total, avg size {s['trade_size_mean']:.1f}")

        # Strategy hint
        print(f"\n  Strategy hint:")
        if role == "STABLE":
            print(f"    Fair value = {s['mid_mean']:.0f} (fixed)")
            print(f"    Market-make with edge inside the {s['spread_median']:.0f}-wide NPC spread")
        else:
            print(f"    Fair value = base + {s['drift_per_ts']:.6f} * (t - t0)")
            print(f"    Drift-capture: hold long, drift earns ~{s['drift_per_day']:.0f}/day per unit")


def plot_price_charts(prices, trades, stats, output_path):
    """Generate a detailed price chart per product: bid/ask band, mid line, trade markers."""
    products = sorted(prices['product'].unique())
    days = sorted(prices['day'].unique())
    n_products = len(products)
    n_days = len(days)

    colors_day = plt.cm.tab10(np.linspace(0, 0.5, max(n_days, 2)))

    fig, axes = plt.subplots(n_products, n_days, figsize=(7 * n_days, 5 * n_products),
                             squeeze=False, sharey='row')

    for i, product in enumerate(products):
        p = prices[prices['product'] == product].copy()
        short_name = product.replace('_', ' ')

        for j, day in enumerate(days):
            ax = axes[i][j]
            dp = p[(p['day'] == day) & (p['mid_price'] > 0)].sort_values('timestamp')

            if len(dp) == 0:
                ax.set_visible(False)
                continue

            ts = dp['timestamp'].values
            mid = dp['mid_price'].values

            # Bid/ask band
            has_both = dp['bid_price_1'].notna() & dp['ask_price_1'].notna()
            dp_ba = dp[has_both]
            if len(dp_ba) > 0:
                ax.fill_between(dp_ba['timestamp'], dp_ba['bid_price_1'], dp_ba['ask_price_1'],
                                alpha=0.15, color='steelblue', label='Bid-Ask spread')
                ax.plot(dp_ba['timestamp'], dp_ba['bid_price_1'],
                        color='steelblue', alpha=0.4, linewidth=0.5)
                ax.plot(dp_ba['timestamp'], dp_ba['ask_price_1'],
                        color='steelblue', alpha=0.4, linewidth=0.5)

            # Mid-price line
            ax.plot(ts, mid, color='#1a1a2e', linewidth=0.8, label='Mid price', zorder=3)

            # Drift trendline if applicable
            drift = stats[product]['drift_per_ts']
            if abs(drift) > 0.0001 and len(ts) > 10:
                fit = np.polyfit(ts.astype(float), mid.astype(float), 1)
                trend_y = np.polyval(fit, ts.astype(float))
                ax.plot(ts, trend_y, color='red', linewidth=1.2, linestyle='--',
                        alpha=0.7, label=f'Trend ({fit[0]:.6f}/ts)')

            # Trade markers
            if len(trades) > 0:
                t = trades[(trades['symbol'] == product)].copy()
                # Filter to this day by timestamp range
                ts_min, ts_max = ts.min(), ts.max()
                t_day = t[(t['timestamp'] >= ts_min) & (t['timestamp'] <= ts_max)]
                if len(t_day) > 0:
                    ax.scatter(t_day['timestamp'], t_day['price'],
                               s=t_day['quantity'] * 3, alpha=0.5, color='orange',
                               edgecolors='darkorange', linewidth=0.3,
                               label=f'Trades (n={len(t_day)})', zorder=4)

            ax.set_title(f"{short_name} — Day {day}", fontsize=11, fontweight='bold')
            ax.set_xlabel("Timestamp", fontsize=9)
            if j == 0:
                ax.set_ylabel("Price", fontsize=9)
            ax.legend(fontsize=7, loc='upper left')
            ax.grid(True, alpha=0.2)
            ax.tick_params(labelsize=8)

            # Stats annotation
            spread_med = stats[product]['spread_median']
            annotation = f"Mid: {mid.mean():.1f} ± {mid.std():.1f}\n"
            if spread_med:
                annotation += f"Spread: {spread_med:.0f}\n"
            annotation += f"Range: {mid.min():.0f}–{mid.max():.0f}"
            ax.text(0.98, 0.05, annotation, transform=ax.transAxes, fontsize=7,
                    verticalalignment='bottom', horizontalalignment='right',
                    bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))

    round_name = os.path.basename(os.path.normpath(os.path.dirname(output_path)))
    fig.suptitle(f"Prosperity 4 — {round_name} Price Charts",
                 fontsize=14, fontweight='bold')
    plt.tight_layout(rect=[0, 0, 1, 0.96])
    plt.savefig(output_path, dpi=150, bbox_inches='tight', facecolor='white')
    print(f"Price chart saved to: {output_path}")
    plt.close()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python analyze.py <data_directory>")
        print("Example: python analyze.py ROUND1/")
        sys.exit(1)

    directory = sys.argv[1]
    if not os.path.isdir(directory):
        print(f"Error: {directory} is not a directory")
        sys.exit(1)

    print(f"Loading data from {directory}...")
    prices, trades = load_data(directory)
    print(f"  Loaded {len(prices)} price rows, {len(trades)} trade rows")
    print(f"  Products: {sorted(prices['product'].unique())}")

    stats = compute_stats(prices, trades)
    print_stats(stats)

    output_path = os.path.join(directory, "analysis.png")
    plot_charts(prices, trades, stats, output_path)

    price_path = os.path.join(directory, "prices.png")
    plot_price_charts(prices, trades, stats, price_path)
