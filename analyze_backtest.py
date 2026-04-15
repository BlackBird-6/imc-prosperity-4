#!/usr/bin/env python3
"""
Prosperity 4 — Backtest Results Analyzer
Usage: python analyze_backtest.py <result_dir> [result_dir2 ...]

Reads the JSON from backtest result directories (e.g., 117419/),
generates PnL charts and prints performance statistics.
Supports comparing multiple runs side-by-side.
"""

import sys
import os
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.gridspec import GridSpec


def load_result(directory):
    """Load backtest result from a directory."""
    json_files = [f for f in os.listdir(directory) if f.endswith('.json')]
    if not json_files:
        print(f"No JSON file found in {directory}")
        return None

    path = os.path.join(directory, json_files[0])
    with open(path) as f:
        data = json.load(f)

    result = {
        'name': os.path.basename(directory.rstrip('/')),
        'round': data.get('round', '?'),
        'status': data.get('status', '?'),
        'profit': data.get('profit', 0),
        'positions': data.get('positions', []),
    }

    # Parse activities log → per-product time series
    log = data.get('activitiesLog', '')
    lines = log.strip().split('\n') if log else []
    products = {}
    if len(lines) > 1:
        for line in lines[1:]:
            f = line.split(';')
            if len(f) < 17:
                continue
            product = f[2]
            if product not in products:
                products[product] = {'ts': [], 'mid': [], 'pnl': [],
                                     'bid1': [], 'ask1': []}
            products[product]['ts'].append(int(f[1]))
            products[product]['mid'].append(float(f[-2]))
            products[product]['pnl'].append(float(f[-1]))
            products[product]['bid1'].append(float(f[3]) if f[3] else None)
            products[product]['ask1'].append(float(f[9]) if f[9] else None)
    result['products'] = products

    # Parse graph log → total PnL curve
    graph = data.get('graphLog', '')
    glines = graph.strip().split('\n') if graph else []
    total_ts, total_pnl = [], []
    for line in glines:
        if ';' in line and not line.startswith('timestamp'):
            parts = line.split(';')
            total_ts.append(int(parts[0]))
            total_pnl.append(float(parts[1]))
    result['total_ts'] = total_ts
    result['total_pnl'] = total_pnl

    return result


def compute_metrics(result):
    """Compute performance metrics for a single run."""
    m = {'name': result['name'], 'profit': result['profit'],
         'round': result['round'], 'status': result['status']}

    # Per-product metrics
    m['per_product'] = {}
    for product, d in result['products'].items():
        pnl = np.array(d['pnl'])
        mid = np.array(d['mid'])
        pm = {}
        pm['final_pnl'] = pnl[-1] if len(pnl) > 0 else 0
        pm['max_pnl'] = pnl.max() if len(pnl) > 0 else 0
        pm['min_pnl'] = pnl.min() if len(pnl) > 0 else 0
        pm['max_drawdown'] = pm['min_pnl']  # from zero baseline

        # Peak-to-trough drawdown
        running_max = np.maximum.accumulate(pnl)
        drawdowns = pnl - running_max
        pm['peak_drawdown'] = drawdowns.min()

        # Trade events (PnL changes not explained by mid-price movement)
        pnl_changes = 0
        big_changes = 0
        for i in range(1, len(pnl)):
            delta = abs(pnl[i] - pnl[i - 1])
            if delta > 0.01:
                pnl_changes += 1
            if delta > 5:
                big_changes += 1
        pm['pnl_change_events'] = pnl_changes
        pm['big_events'] = big_changes

        # Sharpe-like: mean PnL change / std PnL change
        if len(pnl) > 1:
            returns = np.diff(pnl)
            if returns.std() > 0:
                pm['pnl_sharpe'] = returns.mean() / returns.std() * np.sqrt(len(returns))
            else:
                pm['pnl_sharpe'] = 0
        else:
            pm['pnl_sharpe'] = 0

        # Price range
        valid_mid = mid[mid > 0]
        pm['mid_start'] = valid_mid[0] if len(valid_mid) > 0 else 0
        pm['mid_end'] = valid_mid[-1] if len(valid_mid) > 0 else 0

        m['per_product'][product] = pm

    # Final positions
    m['final_positions'] = {p['symbol']: p['quantity'] for p in result.get('positions', [])}

    # Total PnL metrics
    total = np.array(result['total_pnl']) if result['total_pnl'] else np.array([0])
    m['total_max'] = total.max()
    running_max = np.maximum.accumulate(total)
    m['total_peak_dd'] = (total - running_max).min()

    return m


def print_metrics(metrics_list):
    """Print performance comparison table."""
    print("\n" + "=" * 75)
    print("  BACKTEST PERFORMANCE SUMMARY")
    print("=" * 75)

    for m in metrics_list:
        print(f"\n  Run: {m['name']}  |  Round: {m['round']}  |  Status: {m['status']}")
        print(f"  {'─' * 60}")
        print(f"  {'Total Profit:':<30} {m['profit']:>12.2f}")
        print(f"  {'Peak PnL:':<30} {m['total_max']:>12.2f}")
        print(f"  {'Peak-to-trough drawdown:':<30} {m['total_peak_dd']:>12.2f}")

        print(f"\n  {'Product':<25} {'PnL':>8} {'Peak':>8} {'MaxDD':>8} {'PeakDD':>8} {'Events':>7} {'Sharpe':>7}")
        print(f"  {'─' * 71}")
        for product, pm in sorted(m['per_product'].items()):
            short = product[:24]
            print(f"  {short:<25} {pm['final_pnl']:>8.1f} {pm['max_pnl']:>8.1f} "
                  f"{pm['min_pnl']:>8.1f} {pm['peak_drawdown']:>8.1f} "
                  f"{pm['pnl_change_events']:>7} {pm['pnl_sharpe']:>7.2f}")

        if m['final_positions']:
            print(f"\n  Final positions:")
            for sym, qty in sorted(m['final_positions'].items()):
                if sym != 'XIRECS':
                    print(f"    {sym}: {qty}")
            xirecs = m['final_positions'].get('XIRECS', 0)
            print(f"    XIRECS (cash): {xirecs:,}")

    # Side-by-side comparison if multiple runs
    if len(metrics_list) > 1:
        print(f"\n{'=' * 75}")
        print(f"  COMPARISON")
        print(f"{'=' * 75}")
        header = f"  {'Metric':<30}"
        for m in metrics_list:
            header += f" {m['name']:>12}"
        print(header)
        print(f"  {'─' * (30 + 13 * len(metrics_list))}")

        print(f"  {'Total Profit':<30}", end="")
        for m in metrics_list:
            print(f" {m['profit']:>12.2f}", end="")
        print()

        all_products = set()
        for m in metrics_list:
            all_products.update(m['per_product'].keys())

        for product in sorted(all_products):
            short = product[:28]
            print(f"  {short:<30}", end="")
            for m in metrics_list:
                pm = m['per_product'].get(product, {})
                pnl = pm.get('final_pnl', 0)
                print(f" {pnl:>12.2f}", end="")
            print()

        print(f"  {'Peak-to-trough DD':<30}", end="")
        for m in metrics_list:
            print(f" {m['total_peak_dd']:>12.2f}", end="")
        print()


def plot_results(results, metrics_list, output_path):
    """Generate performance charts."""
    n_runs = len(results)
    products_all = set()
    for r in results:
        products_all.update(r['products'].keys())
    products_all = sorted(products_all)
    n_products = len(products_all)

    fig = plt.figure(figsize=(16, 4 * (n_products + 1) + 1))
    gs = GridSpec(n_products + 1, 2, figure=fig, hspace=0.4, wspace=0.3)

    run_colors = plt.cm.Set1(np.linspace(0, 0.8, max(n_runs, 2)))

    # ── Row 0: Total PnL ──
    ax_total = fig.add_subplot(gs[0, :])
    for idx, (r, m) in enumerate(zip(results, metrics_list)):
        if r['total_ts']:
            ax_total.plot(r['total_ts'], r['total_pnl'],
                          color=run_colors[idx], linewidth=1.5,
                          label=f"{r['name']} (PnL={m['profit']:.0f})")
    ax_total.axhline(y=0, color='gray', linewidth=0.5, linestyle='-')
    ax_total.set_title("Total PnL Over Time", fontsize=12, fontweight='bold')
    ax_total.set_xlabel("Timestamp")
    ax_total.set_ylabel("PnL (SeaShells)")
    ax_total.legend(fontsize=9)
    ax_total.grid(True, alpha=0.3)

    # ── Per-product rows ──
    for i, product in enumerate(products_all):
        short = product.replace('_', ' ')[:30]

        # Left: PnL curve
        ax_pnl = fig.add_subplot(gs[i + 1, 0])
        for idx, (r, m) in enumerate(zip(results, metrics_list)):
            d = r['products'].get(product)
            if d:
                ax_pnl.plot(d['ts'], d['pnl'], color=run_colors[idx],
                            linewidth=1, alpha=0.9,
                            label=f"{r['name']} ({m['per_product'].get(product, {}).get('final_pnl', 0):.0f})")
                # Shade drawdown
                pnl = np.array(d['pnl'])
                running_max = np.maximum.accumulate(pnl)
                ax_pnl.fill_between(d['ts'], pnl, running_max,
                                    alpha=0.08, color=run_colors[idx])
        ax_pnl.axhline(y=0, color='gray', linewidth=0.5)
        ax_pnl.set_title(f"{short} — PnL", fontsize=10, fontweight='bold')
        ax_pnl.set_xlabel("Timestamp", fontsize=8)
        ax_pnl.set_ylabel("PnL", fontsize=8)
        ax_pnl.legend(fontsize=7)
        ax_pnl.grid(True, alpha=0.2)

        # Right: PnL change distribution (trade profitability)
        ax_hist = fig.add_subplot(gs[i + 1, 1])
        for idx, r in enumerate(results):
            d = r['products'].get(product)
            if d and len(d['pnl']) > 1:
                changes = np.diff(d['pnl'])
                # Filter to actual trade events (|change| > 0.5)
                trade_changes = changes[np.abs(changes) > 0.5]
                if len(trade_changes) > 0:
                    ax_hist.hist(trade_changes, bins=50, alpha=0.5,
                                 color=run_colors[idx], edgecolor='none',
                                 label=f"{r['name']} (n={len(trade_changes)})")
        ax_hist.axvline(x=0, color='red', linewidth=0.8, linestyle='--')
        ax_hist.set_title(f"{short} — PnL Changes per Tick", fontsize=10, fontweight='bold')
        ax_hist.set_xlabel("PnL Change", fontsize=8)
        ax_hist.set_ylabel("Count", fontsize=8)
        ax_hist.legend(fontsize=7)
        ax_hist.grid(True, alpha=0.2)

    fig.suptitle("Prosperity 4 — Backtest Analysis",
                 fontsize=14, fontweight='bold', y=0.99)
    plt.savefig(output_path, dpi=150, bbox_inches='tight', facecolor='white')
    print(f"Chart saved to: {output_path}")
    plt.close()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python analyze_backtest.py <result_dir> [result_dir2 ...]")
        print("Example: python analyze_backtest.py ~/Downloads/117419/")
        print("Compare: python analyze_backtest.py ~/Downloads/114096/ ~/Downloads/117419/")
        sys.exit(1)

    results = []
    for directory in sys.argv[1:]:
        if not os.path.isdir(directory):
            print(f"Warning: {directory} is not a directory, skipping")
            continue
        r = load_result(directory)
        if r:
            results.append(r)
            print(f"Loaded: {r['name']} (round {r['round']}, profit={r['profit']:.2f})")

    if not results:
        print("No valid results loaded.")
        sys.exit(1)

    metrics = [compute_metrics(r) for r in results]
    print_metrics(metrics)

    # Save chart next to the first result, or in cwd
    out_dir = sys.argv[1] if os.path.isdir(sys.argv[1]) else '.'
    output_path = os.path.join(out_dir, "backtest_analysis.png")
    plot_results(results, metrics, output_path)
