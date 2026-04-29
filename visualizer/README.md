# IMC Prosperity ROUND5 — Visualizer & Query Tools

Two complementary tools for analyzing the ROUND5 trading data:

- **`app.py`** — interactive browser-based visualizer (Plotly Dash)
- **`query.py`** — CLI query tool for scripted or LLM-driven analysis

Both run entirely locally. No external services required.

---

## Setup

From the `visualizer/` directory:

```bash
pip install -r requirements.txt
```

**Dependencies:** `dash`, `plotly`, `pandas`, `numpy`, `scipy`

**Data expected at:** `../trading-data/ROUND5/` (relative to `visualizer/`), containing:
```
prices_round_5_day_2.csv   trades_round_5_day_2.csv
prices_round_5_day_3.csv   trades_round_5_day_3.csv
prices_round_5_day_4.csv   trades_round_5_day_4.csv
```

---

## Visualizer (`app.py`)

```bash
cd visualizer
python app.py
```

Then open **http://localhost:8050** in your browser.

Data loads once at startup (~5 seconds for 1.5M price rows + 35k trade rows).

### Three views (toggle in the header)

**Category View** (default)
- Left sidebar: select any combination of products across all 10 categories
- XIRECS sweep indicator above the chart — colour-coded bar showing how many products traded at each timestamp (green = 1 category, orange = multi-category, red = near-total market sweep)
- Main price chart: mid-price lines (or bid/ask shaded bands) for all selected products
- Optional sub-charts: bid/ask spread width, cumulative signed trade delta
- Stats panel below: per-product stats table (sortable, CSV-exportable) + intra-category charts (normalised overlay, return distribution, rolling volatility, correlation heatmap, lead-lag heatmap, cumulative delta)
- Category-specific extras: Pebble basket sum chart, UV-Visor inter-product spread, Panel size ratios

**Day Comparison**
- Overlays Day 2, Day 3, Day 4 on the same within-day x-axis (0–999,900)
- Useful for detecting intraday periodicity — does a product always peak at the same time of day?
- Per-day OHLC stats table below

**Single Asset**
- Focused drill-down on one product (searchable dropdown of all 50)
- Stats sidebar: all 25 metrics computed for the selected product and day range
- Sub-charts available via tabs (each computed only when clicked):
  - Order Book Depth (L1 + L2 bid/ask volumes, L3 event markers)
  - Spread width over time
  - Cumulative signed trade delta
  - 1-step price returns
  - Rolling mean ± 1 std
  - Category peers (normalised overlay of the other 4 products in the same category)

### Global controls

| Control | Options | Default |
|---|---|---|
| Day | All Days / Day 2 / Day 3 / Day 4 | All Days |
| Price Mode | Mid / Bid-Ask Band | Mid |
| Trades | toggle market trade markers | Off |
| Normalise | rebase all products to 10,000 at start | Off |
| Spread chart | show L1 spread-width sub-chart | Off |
| Delta chart | show cumulative signed flow sub-chart | Off |

---

## Query Scripts (`scripts/`)

Individual, self-contained scripts — each reads only the data it needs. No persistent server required.

```bash
cd visualizer
python scripts/<script>.py [args] [--days 2 3 4] [--json]
```

All scripts support `--days` (restrict to specific days, default: all three) and `--json` for machine-readable output.

**Available scripts:**

| Script | Purpose |
|---|---|
| `list.py` | List all 50 products grouped by category |
| `stats.py` | All metrics for one product |
| `category.py` | Stats table for all 5 products in a category |
| `trends.py` | Rank all 50 products by drift/day |
| `compare.py` | Side-by-side comparison of any set of products |
| `correlations.py` | Pairwise return correlations within a category |
| `sweep.py` | XIRECS sweep events (market reprice signals) |
| `delta.py` | Signed trade-flow summary for one product |
| `basket.py` | Purification Pebbles basket-sum analysis |
| `day.py` | Per-day OHLC breakdown for one product |

---

### `list` — show all products and categories

```bash
python scripts/ list
```

```
Galaxy Sounds Recorders
  GALAXY_SOUNDS_DARK_MATTER
  GALAXY_SOUNDS_BLACK_HOLES
  ...
```

---

### `stats` — all metrics for one product

```bash
python scripts/ stats MICROCHIP_OVAL
python scripts/ stats OXYGEN_SHAKE_GARLIC --days 3 4
python scripts/ stats UV_VISOR_AMBER --json
```

Returns all 25 stats: start/end price, drift, drift/day, OLS slope, R², mean, std dev, volatility %, min/max with timestamps, max drawdown, max runup, autocorrelation lag-1, mean-reversion half-life, skewness, kurtosis, mean spread, trade count, avg trade qty, trade frequency.

---

### `category` — stats table for all 5 products in a category

```bash
python scripts/ category "UV-Visors"
python scripts/ category "Organic Microchips" --days 4
python scripts/ category "Purification Pebbles" --json
```

Category name matching is case-insensitive and substring-based (e.g. `"robots"` matches `"Domestic Robots"`).

---

### `trends` — rank all 50 products by drift/day

```bash
python scripts/ trends
python scripts/ trends --direction long
python scripts/ trends --direction short --min-drift 500
python scripts/ trends --min-drift 800 --days 3 4 --json
```

`--direction long|short` filters to products trending in that direction.
`--min-drift N` sets a minimum absolute drift/day threshold.
Output is sorted by |drift/day| descending. The `^` prefix means uptrend, `v` means downtrend.

---

### `compare` — side-by-side stats for any set of products

```bash
python scripts/ compare MICROCHIP_OVAL MICROCHIP_CIRCLE MICROCHIP_SQUARE
python scripts/ compare OXYGEN_SHAKE_GARLIC GALAXY_SOUNDS_BLACK_HOLES --days 4 --json
```

Shows a single aligned table with all key stats for each product. Useful for quickly comparing candidates within a category or across categories.

---

### `correlations` — pairwise return correlations within a category

```bash
python scripts/ correlations "UV-Visors"
python scripts/ correlations "Domestic Robots" --days 2 3
```

Computes Pearson correlation of 1-step price returns (not price levels) for all 5 products in the category. Near-zero correlations (as seen in UV-Visors, ~0.002–0.02) mean products within the category move independently despite shared macro exposure.

---

### `sweep` — XIRECS sweep events (market reprice signals)

```bash
python scripts/ sweep
python scripts/ sweep --min-size 40
python scripts/ sweep --min-size 5 --days 3 --json
```

XIRECS (the institutional bot) trades in batches. Sweep sizes observed:
- **5–15 products** — single-category sweep (localised reprice)
- **40–50 products** — multi-category sweep (broad market move)
- **80–85 products** — near-total market sweep (regime event)

`--min-size N` filters to sweeps of at least N products. Large sweeps (>=40) are shown as a detail table.

---

### `delta` — cumulative signed trade flow summary

```bash
python scripts/ delta MICROCHIP_OVAL
python scripts/ delta OXYGEN_SHAKE_GARLIC --days 4 --json
```

Infers buy/sell aggressor from trade price vs mid-price at that timestamp:
- `trade_price > mid` → buy aggressor (+qty)
- `trade_price < mid` → sell aggressor (-qty)

Returns total buy volume, sell volume, net delta, flow bias, and per-day breakdown. A product with a strongly negative delta despite a rising price may be approaching a reversal.

---

### `basket` — Purification Pebbles basket-sum analysis

```bash
python scripts/ basket
python scripts/ basket --days 2 3 --json
```

The five Pebble products (XS through XL) are structurally constrained to sum to ~50,000. This command reports:
- Mean/std of the basket sum
- % of timestamps within ±0.5 and ±1 of 50,000
- Timestamps where the constraint breaks (deviation > 5) — potential stat-arb signals

---

### `day` — per-day OHLC breakdown for one product

```bash
python scripts/ day ROBOT_IRONING
python scripts/ day PANEL_2X4 --json
```

Returns for each day: open, close, high, low, drift, drift %, max drawdown, peak timestamp, trough timestamp, first-100k-timestamps drift, last-100k-timestamps drift.

Useful for detecting intraday patterns — e.g. ROBOT_IRONING peaks very early each day (ts ~31000–41000) then falls.

---

## Data notes

- Timestamps: 0–999,900 per day (step size 100). Three days in the dataset: Day 2, 3, 4.
- All prices are mid-price (`(best_bid + best_ask) / 2`). Order book has up to 3 levels; level 3 appears only ~1.5% of timestamps.
- Market trades are all attributed to XIRECS (the exchange's institutional participant). Buyer/seller fields are always blank.
- The `profit_and_loss` column in the prices CSV is always 0 — ignore it.
- Position limits per product: ±10 for most products in ROUND5.
