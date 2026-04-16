# Prosperity 4 — Market Analyzer

Interactive market data dashboard for IMC Prosperity 4, built with Plotly Dash.

## Quick Start

```bash
# From the project root
pip install -r requirements.txt
python imc4-visualizer/app.py
```

Open **http://localhost:8050** in your browser.

## Data

Place trading data in `../trading-data/ROUND*/` relative to this directory. The app auto-discovers all `ROUND*` folders on startup.

Expected CSV structure (semicolon-delimited):
- `prices_round_<N>_day_<D>.csv` — order book snapshots (bid/ask levels 1–3, mid price)
- `trades_round_<N>_day_<D>.csv` — executed trades (symbol, price, quantity)

Days are stitched into a continuous timeline using `global_ts = day_index * 1,000,000 + timestamp`.

## Features

- **Product & round selectors** — switch between products and trading rounds
- **Timestamp range controls** — integer min/max inputs to zoom into any time window
- **Price chart** — mid-price line with bid-ask band, trade markers (sized by quantity), and day boundary lines
- **Order book viewer** — click any chart point to see the L1–L3 bid/ask depth at that timestamp
- **Spread distribution** — histogram with median annotation
- **Trade size distribution** — histogram with count, mean, and total volume
- **Volume profile** — horizontal bars showing volume at each price level
- **Returns distribution** — tick-to-tick return histogram (green/red)
- **Rolling volatility** — 50-tick rolling std dev with min/max/mean
- **Summary statistics** — table with mean, std, range, spread, autocorrelation, drift, and trade metrics

## Dependencies

Managed via `requirements.txt` in the project root.
