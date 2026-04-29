"""
Counterparty analysis graphs for Round 4.
Generates a multi-page PDF: trading-data/ROUND4/counterparty_analysis.pdf
"""

import csv
import math
from collections import defaultdict
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from matplotlib.backends.backend_pdf import PdfPages
import numpy as np

DATA_DIR = "C:/Users/naeem/Documents/imc-prosperity-2025/imc-prosperity-4/trading-data/ROUND4"
OUT_PDF   = DATA_DIR + "/counterparty_analysis.pdf"

TRADERS = ["Mark 01", "Mark 14", "Mark 22", "Mark 38", "Mark 49", "Mark 55", "Mark 67"]
COLORS   = {
    "Mark 01": "#e74c3c",
    "Mark 14": "#3498db",
    "Mark 22": "#2ecc71",
    "Mark 38": "#f39c12",
    "Mark 49": "#9b59b6",
    "Mark 55": "#1abc9c",
    "Mark 67": "#e67e22",
}
MARKER_BUY  = "^"
MARKER_SELL = "v"

# ── Load prices ────────────────────────────────────────────────────────────────

def load_prices():
    """Return {product: {global_ts: (bid1, ask1, mid)}}"""
    prices = defaultdict(dict)
    for day in [1, 2, 3]:
        path = f"{DATA_DIR}/prices_round_4_day_{day}.csv"
        with open(path) as f:
            for row in csv.DictReader(f, delimiter=";"):
                product = row["product"]
                ts = int(row["timestamp"]) + (day - 1) * 1_000_000
                mid = float(row["mid_price"])
                bid = float(row["bid_price_1"]) if row["bid_price_1"] else mid
                ask = float(row["ask_price_1"]) if row["ask_price_1"] else mid
                prices[product][ts] = (bid, ask, mid)
    return prices

# ── Load trades ────────────────────────────────────────────────────────────────

def load_trades():
    """Return list of dicts: {ts, buyer, seller, symbol, price, qty}"""
    trades = []
    for day in [1, 2, 3]:
        path = f"{DATA_DIR}/trades_round_4_day_{day}.csv"
        with open(path) as f:
            for row in csv.DictReader(f, delimiter=";"):
                trades.append({
                    "ts":     int(row["timestamp"]) + (day - 1) * 1_000_000,
                    "buyer":  row["buyer"],
                    "seller": row["seller"],
                    "symbol": row["symbol"],
                    "price":  float(row["price"]),
                    "qty":    int(float(row["quantity"])),
                })
    return trades

# ── Helpers ────────────────────────────────────────────────────────────────────

def nearest_price(prices_for_product, ts):
    """Find the closest price snapshot to ts (within 5000 ticks)."""
    if ts in prices_for_product:
        return prices_for_product[ts]
    # search near
    for delta in range(100, 5001, 100):
        for sign in [-1, 1]:
            candidate = ts + sign * delta
            if candidate in prices_for_product:
                return prices_for_product[candidate]
    return None

def spread_position(price, bid, ask):
    """Fraction 0=at bid, 1=at ask, 0.5=at mid. Can exceed [0,1] for outside quotes."""
    if ask == bid:
        return 0.5
    return (price - bid) / (ask - bid)

def day_label(ts):
    return f"Day {ts // 1_000_000 + 1}"

def ts_to_day_frac(ts):
    """Return fractional day (e.g. Day1 ts=500000 → 1.5)."""
    day = ts // 1_000_000
    within = (ts % 1_000_000) / 999_900
    return day + within

# ── Build per-trader-per-product trade lists ───────────────────────────────────

def build_trader_trades(trades):
    """
    Returns {trader: {symbol: [{'ts', 'price', 'qty', 'role', 'bid', 'ask', 'mid', 'spread_pos'}]}}
    role = 'buy' | 'sell'
    """
    prices = load_prices()
    out = defaultdict(lambda: defaultdict(list))

    for t in trades:
        sym = t["symbol"]
        sym_prices = prices.get(sym, {})
        snap = nearest_price(sym_prices, t["ts"])
        bid, ask, mid = snap if snap else (t["price"], t["price"], t["price"])
        sp = spread_position(t["price"], bid, ask)

        for trader, role in [(t["buyer"], "buy"), (t["seller"], "sell")]:
            if trader in TRADERS:
                out[trader][sym].append({
                    "ts":         t["ts"],
                    "price":      t["price"],
                    "qty":        t["qty"],
                    "role":       role,
                    "bid":        bid,
                    "ask":        ask,
                    "mid":        mid,
                    "spread_pos": sp,
                    "day_frac":   ts_to_day_frac(t["ts"]),
                })
    return out

# ── Section 1: Overview — all bots on each product ───────────────────────────

def page_product_overview(pdf, prices, trader_trades, product):
    """
    One page per product: mid-price line + buy/sell markers for every bot.
    """
    prod_prices = prices.get(product)
    if not prod_prices:
        return

    sorted_ts = sorted(prod_prices)
    xs = [ts_to_day_frac(t) for t in sorted_ts]
    mids = [prod_prices[t][2] for t in sorted_ts]
    bids = [prod_prices[t][0] for t in sorted_ts]
    asks = [prod_prices[t][1] for t in sorted_ts]

    fig, axes = plt.subplots(2, 1, figsize=(16, 10),
                             gridspec_kw={"height_ratios": [3, 1]})
    fig.suptitle(f"{product} — All counterparty trades", fontsize=14, fontweight="bold")

    ax = axes[0]
    ax.fill_between(xs, bids, asks, alpha=0.12, color="steelblue", label="Bid-Ask spread")
    ax.plot(xs, mids, color="steelblue", lw=0.8, label="Mid")

    for trader in TRADERS:
        tlist = trader_trades[trader].get(product, [])
        if not tlist:
            continue
        buy_x  = [t["day_frac"] for t in tlist if t["role"] == "buy"]
        buy_p  = [t["price"]    for t in tlist if t["role"] == "buy"]
        sell_x = [t["day_frac"] for t in tlist if t["role"] == "sell"]
        sell_p = [t["price"]    for t in tlist if t["role"] == "sell"]
        buy_sz  = [max(4, t["qty"]) for t in tlist if t["role"] == "buy"]
        sell_sz = [max(4, t["qty"]) for t in tlist if t["role"] == "sell"]
        c = COLORS[trader]
        if buy_x:
            ax.scatter(buy_x, buy_p, s=buy_sz, c=c, marker=MARKER_BUY,
                       alpha=0.7, label=f"{trader} buy", zorder=3)
        if sell_x:
            ax.scatter(sell_x, sell_p, s=sell_sz, c=c, marker=MARKER_SELL,
                       alpha=0.7, label=f"{trader} sell", zorder=3)

    ax.set_ylabel("Price")
    ax.set_xlabel("Day (fractional)")
    ax.legend(fontsize=7, ncol=3, loc="upper right")
    ax.set_xticks([0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0])
    ax.set_xticklabels(["Day1 open", "Day1 mid", "Day2 open", "Day2 mid",
                         "Day3 open", "Day3 mid", "Day3 close"])
    ax.grid(True, alpha=0.3)

    # Bottom panel: spread (ask - bid) over time
    ax2 = axes[1]
    spreads = [prod_prices[t][1] - prod_prices[t][0] for t in sorted_ts]
    ax2.plot(xs, spreads, color="darkorange", lw=0.7)
    ax2.fill_between(xs, spreads, alpha=0.3, color="darkorange")
    ax2.set_ylabel("Bid-Ask Spread")
    ax2.set_xticks([0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0])
    ax2.set_xticklabels(["Day1 open", "Day1 mid", "Day2 open", "Day2 mid",
                          "Day3 open", "Day3 mid", "Day3 close"])
    ax2.grid(True, alpha=0.3)

    plt.tight_layout()
    pdf.savefig(fig)
    plt.close(fig)

# ── Section 2: Per-trader deep dives ─────────────────────────────────────────

def page_trader_detail(pdf, prices, trader_trades, trader):
    """
    One page per trader with 4 panels:
      (A) Trade prices vs mid for each product they touch
      (B) Volume per trade over time (log scale)
      (C) Spread position histogram (where in bid-ask do they fill)
      (D) Buy/sell volume cumulative over time per product
    """
    all_trades = []
    for sym, tlist in trader_trades[trader].items():
        for t in tlist:
            all_trades.append({**t, "symbol": sym})

    if not all_trades:
        return

    products_touched = sorted(set(t["symbol"] for t in all_trades))

    fig = plt.figure(figsize=(18, 12))
    fig.suptitle(f"{trader} — Detailed Trading Analysis", fontsize=14, fontweight="bold",
                 color=COLORS[trader])
    gs = gridspec.GridSpec(2, 2, figure=fig, hspace=0.42, wspace=0.32)

    # ── Panel A: price relative to mid ──────────────────────────────────────
    ax_a = fig.add_subplot(gs[0, 0])
    for sym in products_touched:
        tlist = [t for t in all_trades if t["symbol"] == sym]
        xs = [t["day_frac"] for t in tlist]
        # delta from mid (normalised as % of mid for comparability across strikes)
        ys = [(t["price"] - t["mid"]) / max(t["mid"], 1) * 100 for t in tlist]
        roles = [t["role"] for t in tlist]
        buy_x  = [xs[i] for i in range(len(xs)) if roles[i] == "buy"]
        buy_y  = [ys[i] for i in range(len(ys)) if roles[i] == "buy"]
        sell_x = [xs[i] for i in range(len(xs)) if roles[i] == "sell"]
        sell_y = [ys[i] for i in range(len(ys)) if roles[i] == "sell"]
        short_sym = sym.replace("VELVETFRUIT_EXTRACT", "VEV").replace("HYDROGEL_PACK", "HP")
        if buy_x:
            ax_a.scatter(buy_x, buy_y, s=10, marker=MARKER_BUY,
                         label=f"{short_sym} buy", alpha=0.7)
        if sell_x:
            ax_a.scatter(sell_x, sell_y, s=10, marker=MARKER_SELL,
                         label=f"{short_sym} sell", alpha=0.7)

    ax_a.axhline(0, color="black", lw=0.8, ls="--", alpha=0.5, label="Mid")
    ax_a.set_title("Trade price – mid (% of mid)")
    ax_a.set_ylabel("% deviation from mid")
    ax_a.set_xlabel("Day (fractional)")
    ax_a.legend(fontsize=6, ncol=2, loc="upper right")
    ax_a.grid(True, alpha=0.3)
    ax_a.set_xticks([0, 1.0, 2.0, 3.0])
    ax_a.set_xticklabels(["D1", "D2", "D3", "D4"])

    # ── Panel B: volume per trade over time ──────────────────────────────────
    ax_b = fig.add_subplot(gs[0, 1])
    for sym in products_touched:
        tlist = sorted([t for t in all_trades if t["symbol"] == sym], key=lambda x: x["day_frac"])
        xs = [t["day_frac"] for t in tlist]
        qs = [t["qty"]      for t in tlist]
        short_sym = sym.replace("VELVETFRUIT_EXTRACT", "VEV").replace("HYDROGEL_PACK", "HP")
        ax_b.scatter(xs, qs, s=8, alpha=0.6, label=short_sym)

    ax_b.set_title("Volume per trade over time")
    ax_b.set_ylabel("Quantity per trade")
    ax_b.set_xlabel("Day (fractional)")
    ax_b.legend(fontsize=6, ncol=2, loc="upper right")
    ax_b.grid(True, alpha=0.3)
    ax_b.set_xticks([0, 1.0, 2.0, 3.0])
    ax_b.set_xticklabels(["D1", "D2", "D3", "D4"])

    # ── Panel C: spread position histogram ──────────────────────────────────
    ax_c = fig.add_subplot(gs[1, 0])
    buy_sp  = [t["spread_pos"] for t in all_trades if t["role"] == "buy"
               and -0.5 <= t["spread_pos"] <= 1.5]
    sell_sp = [t["spread_pos"] for t in all_trades if t["role"] == "sell"
               and -0.5 <= t["spread_pos"] <= 1.5]

    bins = np.linspace(-0.5, 1.5, 30)
    if buy_sp:
        ax_c.hist(buy_sp,  bins=bins, alpha=0.6, color="green",  label="Buys",  density=True)
    if sell_sp:
        ax_c.hist(sell_sp, bins=bins, alpha=0.6, color="red",    label="Sells", density=True)
    ax_c.axvline(0,   color="blue",   lw=1.2, ls="--", label="Bid")
    ax_c.axvline(0.5, color="black",  lw=1.0, ls=":",  label="Mid")
    ax_c.axvline(1,   color="orange", lw=1.2, ls="--", label="Ask")
    ax_c.set_title("Where in bid-ask spread do they fill?")
    ax_c.set_xlabel("Spread position  (0=bid, 0.5=mid, 1=ask)")
    ax_c.set_ylabel("Density")
    ax_c.legend(fontsize=7)
    ax_c.grid(True, alpha=0.3)

    # ── Panel D: cumulative buy/sell volume per product ──────────────────────
    ax_d = fig.add_subplot(gs[1, 1])
    for sym in products_touched:
        tlist = sorted([t for t in all_trades if t["symbol"] == sym], key=lambda x: x["day_frac"])
        buy_xs  = [t["day_frac"] for t in tlist if t["role"] == "buy"]
        buy_qs  = [t["qty"]      for t in tlist if t["role"] == "buy"]
        sell_xs = [t["day_frac"] for t in tlist if t["role"] == "sell"]
        sell_qs = [t["qty"]      for t in tlist if t["role"] == "sell"]
        short_sym = sym.replace("VELVETFRUIT_EXTRACT", "VEV").replace("HYDROGEL_PACK", "HP")
        if buy_xs:
            cum_buy = np.cumsum(buy_qs)
            ax_d.step(buy_xs, cum_buy, where="post", label=f"{short_sym} buy", lw=1.2)
        if sell_xs:
            cum_sell = np.cumsum(sell_qs)
            ax_d.step(sell_xs, cum_sell, where="post", label=f"{short_sym} sell",
                      lw=1.2, ls="--")

    ax_d.set_title("Cumulative volume (buy solid, sell dashed)")
    ax_d.set_ylabel("Cumulative quantity")
    ax_d.set_xlabel("Day (fractional)")
    ax_d.legend(fontsize=6, ncol=2, loc="upper left")
    ax_d.grid(True, alpha=0.3)
    ax_d.set_xticks([0, 1.0, 2.0, 3.0])
    ax_d.set_xticklabels(["D1", "D2", "D3", "D4"])

    plt.tight_layout(rect=[0, 0, 1, 0.96])
    pdf.savefig(fig)
    plt.close(fig)

# ── Section 3: HP market-making spread analysis (Mark 14 vs Mark 38) ─────────

def page_hp_spread_analysis(pdf, prices, trader_trades):
    """
    Special page: Mark 14 and Mark 38 together in HP.
    Top: mid-price with buy/sell markers and bid-ask band.
    Middle: rolling average trade size over time (20-trade window).
    Bottom: inter-trade interval distribution.
    """
    prod = "HYDROGEL_PACK"
    prod_prices = prices.get(prod, {})
    sorted_ts = sorted(prod_prices)
    xs   = [ts_to_day_frac(t) for t in sorted_ts]
    mids = [prod_prices[t][2] for t in sorted_ts]
    bids = [prod_prices[t][0] for t in sorted_ts]
    asks = [prod_prices[t][1] for t in sorted_ts]

    fig, axes = plt.subplots(3, 1, figsize=(16, 12),
                             gridspec_kw={"height_ratios": [3, 1.5, 1.5]})
    fig.suptitle("HYDROGEL_PACK — Mark 14 vs Mark 38 spread dynamics", fontsize=13, fontweight="bold")

    ax = axes[0]
    ax.fill_between(xs, bids, asks, alpha=0.15, color="steelblue", label="Bid-ask band")
    ax.plot(xs, mids, color="steelblue", lw=0.7, label="Mid")

    for trader in ["Mark 14", "Mark 38"]:
        tlist = trader_trades[trader].get(prod, [])
        c = COLORS[trader]
        buy_x  = [t["day_frac"] for t in tlist if t["role"] == "buy"]
        buy_p  = [t["price"]    for t in tlist if t["role"] == "buy"]
        sell_x = [t["day_frac"] for t in tlist if t["role"] == "sell"]
        sell_p = [t["price"]    for t in tlist if t["role"] == "sell"]
        buy_sz  = [t["qty"] * 3 for t in tlist if t["role"] == "buy"]
        sell_sz = [t["qty"] * 3 for t in tlist if t["role"] == "sell"]
        if buy_x:
            ax.scatter(buy_x, buy_p, s=buy_sz, c=c, marker=MARKER_BUY,
                       alpha=0.6, label=f"{trader} buy")
        if sell_x:
            ax.scatter(sell_x, sell_p, s=sell_sz, c=c, marker=MARKER_SELL,
                       alpha=0.6, label=f"{trader} sell")

    ax.set_ylabel("Price")
    ax.legend(fontsize=8, ncol=3, loc="upper right")
    ax.grid(True, alpha=0.3)
    ax.set_xticks([0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0])
    ax.set_xticklabels(["D1 open","D1 mid","D2 open","D2 mid","D3 open","D3 mid","D3 close"])

    # Rolling avg size for each trader
    ax2 = axes[1]
    for trader in ["Mark 14", "Mark 38"]:
        tlist = sorted(trader_trades[trader].get(prod, []), key=lambda x: x["day_frac"])
        xs2 = [t["day_frac"] for t in tlist]
        qs  = [t["qty"]      for t in tlist]
        if len(qs) >= 5:
            window = 20
            rolled = np.convolve(qs, np.ones(window)/window, mode="valid")
            rolled_x = xs2[window-1:]
            ax2.plot(rolled_x, rolled, color=COLORS[trader], label=f"{trader} rolling avg size (w=20)")
    ax2.set_ylabel("Avg trade size")
    ax2.legend(fontsize=8)
    ax2.grid(True, alpha=0.3)
    ax2.set_xticks([0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0])
    ax2.set_xticklabels(["D1 open","D1 mid","D2 open","D2 mid","D3 open","D3 mid","D3 close"])

    # Inter-trade interval histogram
    ax3 = axes[2]
    for trader in ["Mark 14", "Mark 38"]:
        tlist = sorted(trader_trades[trader].get(prod, []), key=lambda x: x["ts"])
        if len(tlist) < 2:
            continue
        intervals = np.diff([t["ts"] for t in tlist])
        ax3.hist(intervals, bins=50, alpha=0.5, color=COLORS[trader],
                 label=f"{trader} inter-trade interval", density=True)
    ax3.set_xlabel("Ticks between trades")
    ax3.set_ylabel("Density")
    ax3.set_title("Inter-trade interval distribution (HP)")
    ax3.legend(fontsize=8)
    ax3.grid(True, alpha=0.3)

    plt.tight_layout()
    pdf.savefig(fig)
    plt.close(fig)

# ── Section 4: VEV directional bots (Mark 55, 67, 49) ───────────────────────

def page_vev_directional(pdf, prices, trader_trades):
    """
    Mark 55/67/49 on VEV.
    Top: mid + trades.
    Middle: cumulative net VEV position for each.
    Bottom: rolling 50-trade avg price paid relative to mid.
    """
    prod = "VELVETFRUIT_EXTRACT"
    prod_prices = prices.get(prod, {})
    sorted_ts   = sorted(prod_prices)
    xs   = [ts_to_day_frac(t) for t in sorted_ts]
    mids = [prod_prices[t][2] for t in sorted_ts]
    bids = [prod_prices[t][0] for t in sorted_ts]
    asks = [prod_prices[t][1] for t in sorted_ts]

    fig, axes = plt.subplots(3, 1, figsize=(16, 12),
                             gridspec_kw={"height_ratios": [3, 2, 2]})
    fig.suptitle("VELVETFRUIT_EXTRACT — Directional bot analysis (Mark 49, 55, 67)",
                 fontsize=13, fontweight="bold")

    ax = axes[0]
    ax.fill_between(xs, bids, asks, alpha=0.12, color="steelblue", label="Bid-ask band")
    ax.plot(xs, mids, color="steelblue", lw=0.8, label="Mid")

    for trader in ["Mark 49", "Mark 55", "Mark 67"]:
        tlist = trader_trades[trader].get(prod, [])
        c = COLORS[trader]
        buy_x  = [t["day_frac"] for t in tlist if t["role"] == "buy"]
        buy_p  = [t["price"]    for t in tlist if t["role"] == "buy"]
        sell_x = [t["day_frac"] for t in tlist if t["role"] == "sell"]
        sell_p = [t["price"]    for t in tlist if t["role"] == "sell"]
        sz_b = [t["qty"] * 2 for t in tlist if t["role"] == "buy"]
        sz_s = [t["qty"] * 2 for t in tlist if t["role"] == "sell"]
        if buy_x:
            ax.scatter(buy_x, buy_p, s=sz_b, c=c, marker=MARKER_BUY, alpha=0.7, label=f"{trader} buy")
        if sell_x:
            ax.scatter(sell_x, sell_p, s=sz_s, c=c, marker=MARKER_SELL, alpha=0.7, label=f"{trader} sell")

    ax.set_ylabel("Price")
    ax.legend(fontsize=7, ncol=3)
    ax.grid(True, alpha=0.3)
    ax.set_xticks([0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0])
    ax.set_xticklabels(["D1 open","D1 mid","D2 open","D2 mid","D3 open","D3 mid","D3 close"])

    # Cumulative net position
    ax2 = axes[1]
    for trader in ["Mark 49", "Mark 55", "Mark 67"]:
        tlist = sorted(trader_trades[trader].get(prod, []), key=lambda x: x["day_frac"])
        xs2, net = [], []
        running = 0
        for t in tlist:
            xs2.append(t["day_frac"])
            delta = t["qty"] if t["role"] == "buy" else -t["qty"]
            running += delta
            net.append(running)
        if xs2:
            ax2.step(xs2, net, where="post", color=COLORS[trader], label=trader, lw=1.5)
    ax2.axhline(0, color="black", lw=0.7, ls="--", alpha=0.5)
    ax2.set_ylabel("Cumulative net position")
    ax2.legend(fontsize=8)
    ax2.grid(True, alpha=0.3)
    ax2.set_xticks([0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0])
    ax2.set_xticklabels(["D1 open","D1 mid","D2 open","D2 mid","D3 open","D3 mid","D3 close"])

    # Rolling avg price paid vs mid
    ax3 = axes[2]
    window = 20
    for trader in ["Mark 49", "Mark 55", "Mark 67"]:
        tlist = sorted(trader_trades[trader].get(prod, []), key=lambda x: x["day_frac"])
        deltas = [(t["price"] - t["mid"]) for t in tlist]
        xst    = [t["day_frac"] for t in tlist]
        if len(deltas) >= window:
            rolled = np.convolve(deltas, np.ones(window)/window, mode="valid")
            rolled_x = xst[window-1:]
            ax3.plot(rolled_x, rolled, color=COLORS[trader], label=f"{trader} (w={window})", lw=1.2)

    ax3.axhline(0, color="black", lw=0.8, ls="--", alpha=0.5, label="Mid")
    ax3.set_ylabel("Avg (trade price – mid)")
    ax3.set_title(f"Rolling {window}-trade avg price deviation from mid")
    ax3.legend(fontsize=8)
    ax3.grid(True, alpha=0.3)
    ax3.set_xticks([0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0])
    ax3.set_xticklabels(["D1 open","D1 mid","D2 open","D2 mid","D3 open","D3 mid","D3 close"])

    plt.tight_layout()
    pdf.savefig(fig)
    plt.close(fig)

# ── Section 5: Option strip — Mark 01 vs Mark 22 per strike ──────────────────

def page_option_strip(pdf, prices, trader_trades):
    """
    One page: option strips for Mark 01 and Mark 22.
    4 strikes shown side by side (VEV_5200 through VEV_5500).
    For each: mid + trades, spread position histogram.
    """
    strikes = ["VEV_5200", "VEV_5300", "VEV_5400", "VEV_5500"]
    traders = ["Mark 01", "Mark 22"]

    fig, axes = plt.subplots(len(strikes), 2, figsize=(16, 14))
    fig.suptitle("Option strip — Mark 01 (buyer) vs Mark 22 (writer)", fontsize=13, fontweight="bold")

    for row, sym in enumerate(strikes):
        sym_prices = prices.get(sym, {})
        sorted_ts  = sorted(sym_prices)
        xs_p  = [ts_to_day_frac(t) for t in sorted_ts]
        mids  = [sym_prices[t][2]  for t in sorted_ts]
        bids  = [sym_prices[t][0]  for t in sorted_ts]
        asks  = [sym_prices[t][1]  for t in sorted_ts]

        # Left: price chart
        ax_left = axes[row, 0]
        ax_left.fill_between(xs_p, bids, asks, alpha=0.15, color="steelblue")
        ax_left.plot(xs_p, mids, color="steelblue", lw=0.7, label="Mid")

        for trader in traders:
            tlist = trader_trades[trader].get(sym, [])
            c = COLORS[trader]
            buy_x  = [t["day_frac"] for t in tlist if t["role"] == "buy"]
            buy_p  = [t["price"]    for t in tlist if t["role"] == "buy"]
            sell_x = [t["day_frac"] for t in tlist if t["role"] == "sell"]
            sell_p = [t["price"]    for t in tlist if t["role"] == "sell"]
            sz_b = [t["qty"] * 4 for t in tlist if t["role"] == "buy"]
            sz_s = [t["qty"] * 4 for t in tlist if t["role"] == "sell"]
            if buy_x:
                ax_left.scatter(buy_x, buy_p, s=sz_b, c=c, marker=MARKER_BUY,
                                alpha=0.7, label=f"{trader} buy")
            if sell_x:
                ax_left.scatter(sell_x, sell_p, s=sz_s, c=c, marker=MARKER_SELL,
                                alpha=0.7, label=f"{trader} sell")

        ax_left.set_ylabel("Price")
        ax_left.set_title(f"{sym} trades")
        ax_left.legend(fontsize=6, ncol=2)
        ax_left.grid(True, alpha=0.3)
        ax_left.set_xticks([0, 1.0, 2.0, 3.0])
        ax_left.set_xticklabels(["D1", "D2", "D3", "D4"])

        # Right: spread position histogram
        ax_right = axes[row, 1]
        bins = np.linspace(-1.0, 2.0, 35)
        for trader in traders:
            tlist = trader_trades[trader].get(sym, [])
            sp_all = [t["spread_pos"] for t in tlist if -1.0 <= t["spread_pos"] <= 2.0]
            if sp_all:
                ax_right.hist(sp_all, bins=bins, alpha=0.55, color=COLORS[trader],
                              label=trader, density=True)

        ax_right.axvline(0,   color="blue",   lw=1.2, ls="--", label="Bid")
        ax_right.axvline(0.5, color="black",  lw=1.0, ls=":",  label="Mid")
        ax_right.axvline(1,   color="orange", lw=1.2, ls="--", label="Ask")
        ax_right.set_title(f"{sym} fill position in spread")
        ax_right.set_xlabel("Spread position")
        ax_right.legend(fontsize=6)
        ax_right.grid(True, alpha=0.3)

    plt.tight_layout(rect=[0, 0, 1, 0.96])
    pdf.savefig(fig)
    plt.close(fig)

# ── Section 6: Trade size distributions (all bots, all products) ─────────────

def page_size_distributions(pdf, trader_trades):
    """Box plots + violin plots of trade sizes per trader."""
    fig, axes = plt.subplots(1, 2, figsize=(16, 7))
    fig.suptitle("Trade size distributions per trader", fontsize=13, fontweight="bold")

    # All products combined
    ax = axes[0]
    data = []
    labels = []
    for trader in TRADERS:
        qtys = []
        for tlist in trader_trades[trader].values():
            qtys.extend(t["qty"] for t in tlist)
        if qtys:
            data.append(qtys)
            labels.append(trader.replace("Mark ", "M"))
    parts = ax.violinplot(data, showmedians=True, showextrema=True)
    for pc, trader in zip(parts["bodies"], [t for t in TRADERS if any(trader_trades[t].values())]):
        pc.set_facecolor(COLORS[trader])
        pc.set_alpha(0.6)
    ax.set_xticks(range(1, len(labels)+1))
    ax.set_xticklabels(labels, rotation=30)
    ax.set_ylabel("Trade quantity")
    ax.set_title("All products combined")
    ax.grid(True, alpha=0.3, axis="y")

    # HP only
    ax2 = axes[1]
    data2, labels2 = [], []
    for trader in ["Mark 14", "Mark 38", "Mark 22"]:
        qtys = [t["qty"] for t in trader_trades[trader].get("HYDROGEL_PACK", [])]
        if qtys:
            data2.append(qtys)
            labels2.append(trader)
    if data2:
        bp = ax2.boxplot(data2, labels=labels2, patch_artist=True)
        for patch, trader in zip(bp["boxes"], [t for t in ["Mark 14", "Mark 38", "Mark 22"] if trader_trades[t].get("HYDROGEL_PACK")]):
            patch.set_facecolor(COLORS[trader])
            patch.set_alpha(0.6)
    ax2.set_ylabel("Trade quantity")
    ax2.set_title("HYDROGEL_PACK only")
    ax2.grid(True, alpha=0.3, axis="y")

    plt.tight_layout()
    pdf.savefig(fig)
    plt.close(fig)

# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    print("Loading data...")
    prices = load_prices()
    trades = load_trades()
    trader_trades = build_trader_trades(trades)

    print(f"Generating PDF: {OUT_PDF}")
    with PdfPages(OUT_PDF) as pdf:

        # Cover page
        fig = plt.figure(figsize=(12, 6))
        fig.text(0.5, 0.65, "Round 4 — Counterparty Analysis", ha="center",
                 fontsize=22, fontweight="bold")
        fig.text(0.5, 0.50, "7 identified bots across 3 days", ha="center", fontsize=14)
        fig.text(0.5, 0.40, "Products: HYDROGEL_PACK · VELVETFRUIT_EXTRACT · VEV_4000–6500",
                 ha="center", fontsize=11, color="gray")
        # Legend patch
        handles = [plt.Line2D([0],[0], marker="s", color="w",
                               markerfacecolor=COLORS[t], markersize=12, label=t) for t in TRADERS]
        fig.legend(handles=handles, loc="lower center", ncol=4, fontsize=10)
        pdf.savefig(fig)
        plt.close(fig)

        # Product overview pages
        for prod in ["HYDROGEL_PACK", "VELVETFRUIT_EXTRACT",
                     "VEV_5000", "VEV_5200", "VEV_5300", "VEV_5400", "VEV_5500"]:
            print(f"  Overview: {prod}")
            page_product_overview(pdf, prices, trader_trades, prod)

        # HP spread analysis
        print("  HP spread analysis...")
        page_hp_spread_analysis(pdf, prices, trader_trades)

        # VEV directional bots
        print("  VEV directional analysis...")
        page_vev_directional(pdf, prices, trader_trades)

        # Option strip
        print("  Option strip...")
        page_option_strip(pdf, prices, trader_trades)

        # Per-trader deep dives
        for trader in TRADERS:
            print(f"  Trader detail: {trader}")
            page_trader_detail(pdf, prices, trader_trades, trader)

        # Size distributions
        print("  Size distributions...")
        page_size_distributions(pdf, trader_trades)

    print(f"\nDone. PDF saved to {OUT_PDF}")

if __name__ == "__main__":
    main()
