#!/usr/bin/env python3
"""
Prosperity 4 — Interactive Market Analyzer (Plotly Dash)

Usage:
    pip install -r requirements.txt
    python app.py

Opens at http://localhost:8050
"""

import os
import glob
import json

import dash
from dash import dcc, html, Input, Output, State, callback, ctx
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np

# ── Configuration ─────────────────────────────────────────────────────

TRADING_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "trading-data")

COLORS = {
    "bg": "#111827",
    "card": "#1f2937",
    "border": "#374151",
    "text": "#f9fafb",
    "text2": "#9ca3af",
    "blue": "#3b82f6",
    "amber": "#f59e0b",
    "green": "#22c55e",
    "red": "#ef4444",
    "purple": "#a78bfa",
    "teal": "#14b8a6",
}

# ── Data Loading ──────────────────────────────────────────────────────


def discover_rounds():
    """Find all ROUND* directories in trading-data/."""
    rounds = []
    if not os.path.isdir(TRADING_DATA_DIR):
        return rounds
    for entry in sorted(os.listdir(TRADING_DATA_DIR)):
        path = os.path.join(TRADING_DATA_DIR, entry)
        if os.path.isdir(path) and entry.upper().startswith("ROUND"):
            rounds.append(entry)
    return rounds


def load_round_data(round_name):
    """Load all price and trade CSVs for a round."""
    round_dir = os.path.join(TRADING_DATA_DIR, round_name)

    price_files = sorted(glob.glob(os.path.join(round_dir, "prices_*.csv")))
    trade_files = sorted(glob.glob(os.path.join(round_dir, "trades_*.csv")))

    # Load prices
    price_dfs = []
    for f in price_files:
        df = pd.read_csv(f, sep=";")
        price_dfs.append(df)
    prices = pd.concat(price_dfs, ignore_index=True) if price_dfs else pd.DataFrame()

    # Load trades — extract day from filename since trades CSVs don't have a day column
    trade_dfs = []
    for f in trade_files:
        df = pd.read_csv(f, sep=";")
        # Extract day from filename: e.g. trades_round_1_day_-2.csv -> -2
        import re
        day_match = re.search(r"day_(-?\d+)", os.path.basename(f))
        if day_match:
            df["day"] = int(day_match.group(1))
        else:
            df["day"] = 0
        trade_dfs.append(df)
    trades = pd.concat(trade_dfs, ignore_index=True) if trade_dfs else pd.DataFrame()

    if len(prices) > 0:
        # Filter out empty book rows
        prices = prices[prices["mid_price"] > 0].copy()

        # Create global timestamp for multi-day stitching
        days_sorted = sorted(prices["day"].unique())
        day_to_idx = {d: i for i, d in enumerate(days_sorted)}
        prices["day_index"] = prices["day"].map(day_to_idx)
        prices["global_ts"] = prices["day_index"] * 1_000_000 + prices["timestamp"]
        prices["spread"] = prices["ask_price_1"] - prices["bid_price_1"]
        prices = prices.sort_values("global_ts").reset_index(drop=True)

    if len(trades) > 0 and len(prices) > 0:
        days_sorted = sorted(prices["day"].unique())
        day_to_idx = {d: i for i, d in enumerate(days_sorted)}
        trades["day_index"] = trades["day"].map(day_to_idx).fillna(0).astype(int)
        trades["global_ts"] = trades["day_index"] * 1_000_000 + trades["timestamp"]
        trades = trades.sort_values("global_ts").reset_index(drop=True)

    return prices, trades


def get_products(prices):
    if len(prices) == 0:
        return []
    return sorted(prices["product"].unique().tolist())


def compute_stats(prices, trades, product):
    """Compute summary statistics for a product."""
    p = prices[prices["product"] == product]
    t = trades[trades["symbol"] == product] if len(trades) > 0 else pd.DataFrame()
    mids = p["mid_price"].values

    stats = {}
    stats["mid_mean"] = np.mean(mids) if len(mids) > 0 else 0
    stats["mid_std"] = np.std(mids, ddof=1) if len(mids) > 1 else 0
    stats["mid_min"] = np.min(mids) if len(mids) > 0 else 0
    stats["mid_max"] = np.max(mids) if len(mids) > 0 else 0

    spreads = p["spread"].dropna().values
    stats["spread_median"] = np.median(spreads) if len(spreads) > 0 else None
    stats["spread_mean"] = np.mean(spreads) if len(spreads) > 0 else None

    # Returns autocorrelation
    returns = np.diff(mids)
    if len(returns) > 10:
        stats["ac_returns_1"] = pd.Series(returns).autocorr(lag=1)
    else:
        stats["ac_returns_1"] = None

    if len(mids) > 10:
        stats["ac_level_1"] = pd.Series(mids).autocorr(lag=1)
    else:
        stats["ac_level_1"] = None

    # Drift
    if len(p) > 100:
        ts = p["global_ts"].values.astype(float)
        mp = mids.astype(float)
        slope = np.polyfit(ts, mp, 1)[0]
        stats["drift_per_ts"] = slope
        stats["drift_per_day"] = slope * 1_000_000
    else:
        stats["drift_per_ts"] = 0
        stats["drift_per_day"] = 0

    stats["trade_count"] = len(t)
    stats["trade_vol_total"] = int(t["quantity"].sum()) if len(t) > 0 else 0
    stats["trade_size_mean"] = t["quantity"].mean() if len(t) > 0 else 0
    stats["total_rows"] = len(p)

    return stats


# ── Load initial data ─────────────────────────────────────────────────

ROUNDS = discover_rounds()
if not ROUNDS:
    print(f"No ROUND directories found in {TRADING_DATA_DIR}")
    print("Make sure trading-data/ROUND1/ exists with CSV files.")

# Cache
_data_cache = {}


def get_data(round_name):
    if round_name not in _data_cache:
        _data_cache[round_name] = load_round_data(round_name)
    return _data_cache[round_name]


# ── Dash App ──────────────────────────────────────────────────────────

app = dash.Dash(
    __name__,
    title="Prosperity 4 — Market Analyzer",
    update_title=None,
)

# ── Layout ────────────────────────────────────────────────────────────

CARD_STYLE = {
    "backgroundColor": COLORS["card"],
    "border": f"1px solid {COLORS['border']}",
    "borderRadius": "8px",
    "padding": "16px",
    "marginBottom": "16px",
}

LABEL_STYLE = {
    "color": COLORS["text2"],
    "fontSize": "13px",
    "fontWeight": "500",
    "marginRight": "6px",
}

INPUT_STYLE = {
    "backgroundColor": "#374151",
    "border": f"1px solid {COLORS['border']}",
    "color": COLORS["text"],
    "padding": "6px 10px",
    "borderRadius": "6px",
    "fontFamily": "Inter, monospace",
    "fontSize": "13px",
    "width": "130px",
    "outline": "none",
}

DROPDOWN_STYLE = {
    "backgroundColor": "#374151",
    "color": COLORS["text"],
    "width": "220px",
}

app.layout = html.Div(
    style={
        "backgroundColor": COLORS["bg"],
        "minHeight": "100vh",
        "fontFamily": "Inter, -apple-system, BlinkMacSystemFont, sans-serif",
        "color": COLORS["text"],
    },
    children=[
        # ── Header ──
        html.Div(
            style={
                "backgroundColor": COLORS["card"],
                "borderBottom": f"1px solid {COLORS['border']}",
                "padding": "16px 24px",
                "display": "flex",
                "alignItems": "center",
                "justifyContent": "space-between",
                "flexWrap": "wrap",
                "gap": "12px",
            },
            children=[
                html.H1(
                    "Prosperity 4 — Market Analyzer",
                    style={"fontSize": "18px", "fontWeight": "700", "margin": 0},
                ),
                html.Div(
                    style={"display": "flex", "alignItems": "center", "gap": "16px"},
                    children=[
                        html.Div(
                            [
                                html.Label("Round", style=LABEL_STYLE),
                                dcc.Dropdown(
                                    id="round-select",
                                    options=[{"label": r, "value": r} for r in ROUNDS],
                                    value=ROUNDS[0] if ROUNDS else None,
                                    clearable=False,
                                    style={"width": "150px"},
                                    className="dark-dropdown",
                                ),
                            ],
                            style={"display": "flex", "alignItems": "center", "gap": "6px"},
                        ),
                        html.Div(
                            [
                                html.Label("Product", style=LABEL_STYLE),
                                dcc.Dropdown(
                                    id="product-select",
                                    options=[],
                                    value=None,
                                    clearable=False,
                                    style={"width": "260px"},
                                    className="dark-dropdown",
                                ),
                            ],
                            style={"display": "flex", "alignItems": "center", "gap": "6px"},
                        ),
                    ],
                ),
            ],
        ),
        # ── Timestamp Range ──
        html.Div(
            style={
                **CARD_STYLE,
                "margin": "16px 24px 0 24px",
                "display": "flex",
                "alignItems": "center",
                "gap": "16px",
                "flexWrap": "wrap",
                "marginBottom": "0",
            },
            children=[
                html.Label("Min Timestamp", style=LABEL_STYLE),
                dcc.Input(id="min-ts", type="number", value=0, style=INPUT_STYLE),
                html.Label("Max Timestamp", style=LABEL_STYLE),
                dcc.Input(id="max-ts", type="number", value=0, style=INPUT_STYLE),
                html.Button(
                    "Apply",
                    id="apply-btn",
                    n_clicks=0,
                    style={
                        "backgroundColor": COLORS["blue"],
                        "color": "white",
                        "border": "none",
                        "padding": "7px 16px",
                        "borderRadius": "6px",
                        "cursor": "pointer",
                        "fontWeight": "500",
                        "fontSize": "13px",
                    },
                ),
                html.Button(
                    "Reset",
                    id="reset-btn",
                    n_clicks=0,
                    style={
                        "backgroundColor": "#374151",
                        "color": COLORS["text"],
                        "border": f"1px solid {COLORS['border']}",
                        "padding": "6px 14px",
                        "borderRadius": "6px",
                        "cursor": "pointer",
                        "fontSize": "13px",
                    },
                ),
                html.Span(id="range-info", style={"fontSize": "12px", "color": COLORS["text2"]}),
            ],
        ),
        # ── Main Content ──
        html.Div(
            style={"padding": "16px 24px 40px"},
            children=[
                # Price chart
                html.Div(style=CARD_STYLE, children=[dcc.Graph(id="price-chart", config={"displayModeBar": True, "scrollZoom": True})]),
                # Order book
                html.Div(id="order-book-container", style={"display": "none"}, children=[
                    html.Div(style=CARD_STYLE, children=[
                        html.Div(
                            style={"display": "flex", "justifyContent": "space-between", "alignItems": "center", "marginBottom": "8px"},
                            children=[
                                html.H3(id="ob-title", style={"fontSize": "14px", "fontWeight": "600", "margin": 0}),
                            ],
                        ),
                        dcc.Graph(id="order-book-chart", config={"displayModeBar": False}),
                        html.Div(id="ob-table"),
                    ]),
                ]),
                # Metrics grid
                html.Div(
                    style={
                        "display": "grid",
                        "gridTemplateColumns": "repeat(3, 1fr)",
                        "gap": "16px",
                    },
                    children=[
                        html.Div(style=CARD_STYLE, children=[
                            html.H3("Spread Distribution", style={"fontSize": "14px", "fontWeight": "600", "marginBottom": "8px", "marginTop": 0}),
                            dcc.Graph(id="spread-chart", config={"displayModeBar": False}),
                        ]),
                        html.Div(style=CARD_STYLE, children=[
                            html.H3("Trade Size Distribution", style={"fontSize": "14px", "fontWeight": "600", "marginBottom": "8px", "marginTop": 0}),
                            dcc.Graph(id="trade-size-chart", config={"displayModeBar": False}),
                        ]),
                        html.Div(style=CARD_STYLE, children=[
                            html.H3("Volume Profile", style={"fontSize": "14px", "fontWeight": "600", "marginBottom": "8px", "marginTop": 0}),
                            dcc.Graph(id="volume-chart", config={"displayModeBar": False}),
                        ]),
                        html.Div(style=CARD_STYLE, children=[
                            html.H3("Returns Distribution", style={"fontSize": "14px", "fontWeight": "600", "marginBottom": "8px", "marginTop": 0}),
                            dcc.Graph(id="returns-chart", config={"displayModeBar": False}),
                        ]),
                        html.Div(style=CARD_STYLE, children=[
                            html.H3("Rolling Volatility (50-tick)", style={"fontSize": "14px", "fontWeight": "600", "marginBottom": "8px", "marginTop": 0}),
                            dcc.Graph(id="volatility-chart", config={"displayModeBar": False}),
                        ]),
                        html.Div(style=CARD_STYLE, children=[
                            html.H3("Summary Statistics", style={"fontSize": "14px", "fontWeight": "600", "marginBottom": "8px", "marginTop": 0}),
                            html.Div(id="stats-table"),
                        ]),
                    ],
                ),
            ],
        ),
        # Hidden stores
        dcc.Store(id="data-range-store", data={"min": 0, "max": 0}),
        dcc.Store(id="selected-ts-store", data=None),
    ],
)

# ── Custom CSS for dark dropdowns ─────────────────────────────────────

app.index_string = """<!DOCTYPE html>
<html>
<head>
    {%metas%}
    <title>{%title%}</title>
    {%favicon%}
    {%css%}
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
        body { margin: 0; }
        .dark-dropdown .Select-control,
        .dark-dropdown .Select-menu-outer {
            background-color: #374151 !important;
            border-color: #374151 !important;
            color: #f9fafb !important;
        }
        .dark-dropdown .Select-value-label,
        .dark-dropdown .Select-placeholder {
            color: #f9fafb !important;
        }
        .dark-dropdown .Select-option {
            background-color: #1f2937 !important;
            color: #f9fafb !important;
        }
        .dark-dropdown .Select-option.is-focused {
            background-color: #374151 !important;
        }
        /* Dash dropdown overrides */
        .Select-control { background-color: #374151 !important; border-color: #4b5563 !important; }
        .Select-menu-outer { background-color: #1f2937 !important; border-color: #374151 !important; }
        .Select-value-label { color: #f9fafb !important; }
        .Select-placeholder { color: #9ca3af !important; }
        .Select-option { background-color: #1f2937 !important; color: #f9fafb !important; }
        .Select-option.is-focused { background-color: #374151 !important; }
        .Select-arrow-zone .Select-arrow { border-color: #9ca3af transparent transparent !important; }
        .is-open > .Select-control .Select-arrow { border-color: transparent transparent #9ca3af !important; }
        .Select-input > input { color: #f9fafb !important; }
        .Select-clear-zone { color: #9ca3af !important; }
    </style>
</head>
<body>
    {%app_entry%}
    <footer>
        {%config%}
        {%scripts%}
        {%renderer%}
    </footer>
</body>
</html>"""

# ── Callbacks ─────────────────────────────────────────────────────────


@callback(
    Output("product-select", "options"),
    Output("product-select", "value"),
    Input("round-select", "value"),
)
def update_products(round_name):
    if not round_name:
        return [], None
    prices, _ = get_data(round_name)
    products = get_products(prices)
    options = [{"label": p, "value": p} for p in products]
    value = products[0] if products else None
    return options, value


@callback(
    Output("data-range-store", "data"),
    Output("min-ts", "value"),
    Output("max-ts", "value"),
    Output("range-info", "children"),
    Input("product-select", "value"),
    Input("reset-btn", "n_clicks"),
    State("round-select", "value"),
)
def update_range(product, n_reset, round_name):
    if not round_name or not product:
        return {"min": 0, "max": 0}, 0, 0, ""
    prices, _ = get_data(round_name)
    p = prices[prices["product"] == product]
    if len(p) == 0:
        return {"min": 0, "max": 0}, 0, 0, ""
    mn = int(p["global_ts"].min())
    mx = int(p["global_ts"].max())
    return {"min": mn, "max": mx}, mn, mx, f"Data range: {mn:,} – {mx:,}"


@callback(
    Output("price-chart", "figure"),
    Input("apply-btn", "n_clicks"),
    Input("product-select", "value"),
    State("round-select", "value"),
    State("min-ts", "value"),
    State("max-ts", "value"),
    State("data-range-store", "data"),
)
def update_price_chart(n_clicks, product, round_name, min_ts, max_ts, data_range):
    if not round_name or not product:
        return go.Figure()

    prices, trades = get_data(round_name)
    p = prices[prices["product"] == product].copy()

    # Apply range — if both are 0, use full data range
    mn = min_ts if min_ts is not None else data_range["min"]
    mx = max_ts if max_ts is not None else data_range["max"]
    if mn == 0 and mx == 0:
        mn = int(p["global_ts"].min())
        mx = int(p["global_ts"].max())
    p = p[(p["global_ts"] >= mn) & (p["global_ts"] <= mx)]

    if len(p) == 0:
        fig = go.Figure()
        fig.update_layout(
            template="plotly_dark",
            paper_bgcolor=COLORS["card"],
            plot_bgcolor=COLORS["bg"],
            title="No data in selected range",
        )
        return fig

    # Downsample if too many points
    if len(p) > 3000:
        step = len(p) // 3000
        p = p.iloc[::step]

    fig = go.Figure()

    # Bid-ask band
    has_both = p["bid_price_1"].notna() & p["ask_price_1"].notna()
    p_ba = p[has_both]
    if len(p_ba) > 0:
        fig.add_trace(go.Scatter(
            x=p_ba["global_ts"], y=p_ba["ask_price_1"],
            mode="lines", line=dict(width=0),
            showlegend=False, hoverinfo="skip",
        ))
        fig.add_trace(go.Scatter(
            x=p_ba["global_ts"], y=p_ba["bid_price_1"],
            mode="lines", line=dict(width=0),
            fill="tonexty", fillcolor="rgba(59,130,246,0.1)",
            name="Bid-Ask Band", hoverinfo="skip",
        ))

    # Mid-price line
    fig.add_trace(go.Scatter(
        x=p["global_ts"], y=p["mid_price"],
        mode="lines", name="Mid Price",
        line=dict(color=COLORS["blue"], width=1.5),
        hovertemplate="Timestamp: %{x}<br>Mid: %{y:.1f}<extra></extra>",
    ))

    # Trade markers
    if len(trades) > 0:
        t = trades[trades["symbol"] == product]
        t = t[(t["global_ts"] >= mn) & (t["global_ts"] <= mx)]
        if len(t) > 0:
            fig.add_trace(go.Scatter(
                x=t["global_ts"], y=t["price"],
                mode="markers", name=f"Trades (n={len(t)})",
                marker=dict(
                    color=COLORS["amber"], size=t["quantity"].clip(2, 12),
                    opacity=0.7, line=dict(width=0.5, color="#d97706"),
                ),
                hovertemplate="Trade @ %{x}<br>Price: %{y:.1f}<br>Qty: %{marker.size}<extra></extra>",
            ))

    # Day boundaries
    days_sorted = sorted(prices[prices["product"] == product]["day"].unique())
    day_to_idx = {d: i for i, d in enumerate(days_sorted)}
    for day_val, day_idx in day_to_idx.items():
        boundary_ts = day_idx * 1_000_000
        if mn <= boundary_ts <= mx:
            fig.add_vline(
                x=boundary_ts, line_dash="dash", line_color="#4b5563",
                annotation_text=f"Day {day_val}", annotation_position="top",
                annotation_font_color="#6b7280", annotation_font_size=11,
            )

    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor=COLORS["card"],
        plot_bgcolor=COLORS["bg"],
        margin=dict(l=50, r=20, t=30, b=40),
        height=400,
        xaxis=dict(title="Global Timestamp", gridcolor="#1e293b"),
        yaxis=dict(title="Price", gridcolor="#1e293b"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        hovermode="x unified",
    )

    return fig


@callback(
    Output("order-book-container", "style"),
    Output("ob-title", "children"),
    Output("order-book-chart", "figure"),
    Output("ob-table", "children"),
    Input("price-chart", "clickData"),
    State("round-select", "value"),
    State("product-select", "value"),
)
def update_order_book(click_data, round_name, product):
    hidden = {"display": "none"}
    empty_fig = go.Figure()

    if not click_data or not round_name or not product:
        return hidden, "", empty_fig, ""

    # Get clicked timestamp
    point = click_data["points"][0]
    clicked_ts = point["x"]

    prices, _ = get_data(round_name)
    p = prices[prices["product"] == product]

    # Find nearest row
    idx = (p["global_ts"] - clicked_ts).abs().idxmin()
    row = p.loc[idx]

    title = f"Order Book — Timestamp {int(row['global_ts'])} (Day {int(row['day'])}, t={int(row['timestamp'])})"

    # Build order book data
    bids = []
    asks = []
    for lvl in [1, 2, 3]:
        bp = row.get(f"bid_price_{lvl}")
        bv = row.get(f"bid_volume_{lvl}")
        if pd.notna(bp) and pd.notna(bv):
            bids.append({"price": bp, "volume": int(bv), "level": lvl})
        ap = row.get(f"ask_price_{lvl}")
        av = row.get(f"ask_volume_{lvl}")
        if pd.notna(ap) and pd.notna(av):
            asks.append({"price": ap, "volume": int(av), "level": lvl})

    # Sort: bids descending, asks ascending
    bids.sort(key=lambda x: -x["price"])
    asks.sort(key=lambda x: x["price"])

    max_vol = max(
        [b["volume"] for b in bids] + [a["volume"] for a in asks] + [1]
    )

    fig = go.Figure()

    # Bids (negative x for left side)
    all_prices = []
    all_volumes = []
    all_colors = []
    all_text = []

    for b in bids:
        all_prices.append(str(int(b["price"])))
        all_volumes.append(-b["volume"])  # negative for left
        all_colors.append(COLORS["green"])
        all_text.append(str(b["volume"]))

    for a in asks:
        all_prices.append(str(int(a["price"])))
        all_volumes.append(a["volume"])
        all_colors.append(COLORS["red"])
        all_text.append(str(a["volume"]))

    fig.add_trace(go.Bar(
        y=all_prices, x=all_volumes,
        orientation="h",
        marker_color=all_colors,
        marker_opacity=0.7,
        text=all_text,
        textposition="auto",
        textfont=dict(color="white", size=12, family="Inter"),
        hoverinfo="skip",
    ))

    # Add mid-price annotation
    fig.add_annotation(
        x=0, y=-0.5,
        text=f"Mid: {row['mid_price']:.1f}",
        showarrow=False,
        font=dict(color=COLORS["blue"], size=13, family="Inter"),
        yref="paper",
    )

    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor=COLORS["card"],
        plot_bgcolor=COLORS["bg"],
        margin=dict(l=10, r=10, t=10, b=30),
        height=200,
        xaxis=dict(
            title="Volume", gridcolor="#1e293b",
            zeroline=True, zerolinecolor=COLORS["border"],
        ),
        yaxis=dict(gridcolor="#1e293b", autorange="reversed"),
        showlegend=False,
    )

    # Build table
    table_rows = []
    header = html.Tr([
        html.Th("Level", style={"color": COLORS["text2"], "padding": "4px 12px", "fontWeight": "500", "fontSize": "12px"}),
        html.Th("Bid Vol", style={"color": COLORS["green"], "padding": "4px 12px", "fontWeight": "500", "fontSize": "12px"}),
        html.Th("Bid Price", style={"color": COLORS["green"], "padding": "4px 12px", "fontWeight": "500", "fontSize": "12px"}),
        html.Th("Ask Price", style={"color": COLORS["red"], "padding": "4px 12px", "fontWeight": "500", "fontSize": "12px"}),
        html.Th("Ask Vol", style={"color": COLORS["red"], "padding": "4px 12px", "fontWeight": "500", "fontSize": "12px"}),
    ])

    for lvl in [1, 2, 3]:
        bp = row.get(f"bid_price_{lvl}")
        bv = row.get(f"bid_volume_{lvl}")
        ap = row.get(f"ask_price_{lvl}")
        av = row.get(f"ask_volume_{lvl}")
        td_style = {"padding": "4px 12px", "fontSize": "12px", "textAlign": "center"}
        table_rows.append(html.Tr([
            html.Td(f"L{lvl}", style={**td_style, "color": COLORS["text2"]}),
            html.Td(f"{int(bv)}" if pd.notna(bv) else "—", style={**td_style, "color": COLORS["green"]}),
            html.Td(f"{int(bp):,}" if pd.notna(bp) else "—", style={**td_style, "color": COLORS["green"]}),
            html.Td(f"{int(ap):,}" if pd.notna(ap) else "—", style={**td_style, "color": COLORS["red"]}),
            html.Td(f"{int(av)}" if pd.notna(av) else "—", style={**td_style, "color": COLORS["red"]}),
        ]))

    table = html.Table(
        [html.Thead(header), html.Tbody(table_rows)],
        style={"width": "100%", "borderCollapse": "collapse", "marginTop": "8px"},
    )

    return {"display": "block"}, title, fig, table


@callback(
    Output("spread-chart", "figure"),
    Output("trade-size-chart", "figure"),
    Output("volume-chart", "figure"),
    Output("returns-chart", "figure"),
    Output("volatility-chart", "figure"),
    Output("stats-table", "children"),
    Input("product-select", "value"),
    State("round-select", "value"),
)
def update_metrics(product, round_name):
    empty = go.Figure()
    empty.update_layout(
        template="plotly_dark", paper_bgcolor=COLORS["card"],
        plot_bgcolor=COLORS["bg"], height=220, margin=dict(l=40, r=20, t=10, b=30),
    )

    if not round_name or not product:
        return empty, empty, empty, empty, empty, ""

    prices, trades = get_data(round_name)
    p = prices[prices["product"] == product]
    t = trades[trades["symbol"] == product] if len(trades) > 0 else pd.DataFrame()
    stats = compute_stats(prices, trades, product)

    chart_layout = dict(
        template="plotly_dark",
        paper_bgcolor=COLORS["card"],
        plot_bgcolor=COLORS["bg"],
        height=220,
        margin=dict(l=40, r=20, t=10, b=30),
        xaxis=dict(gridcolor="#1e293b"),
        yaxis=dict(gridcolor="#1e293b"),
        showlegend=False,
    )

    # 1. Spread distribution
    spreads = p["spread"].dropna()
    spread_counts = spreads.value_counts().sort_index()
    if len(spread_counts) > 20:
        spread_counts = spread_counts.head(20)
    fig_spread = go.Figure(go.Bar(
        x=spread_counts.index.astype(str),
        y=spread_counts.values,
        marker_color=COLORS["blue"],
        text=spread_counts.values,
        textposition="outside",
        textfont=dict(size=9, color=COLORS["text2"]),
    ))
    fig_spread.update_layout(**chart_layout)
    if stats["spread_median"] is not None:
        fig_spread.add_annotation(
            x=0.02, y=0.95, xref="paper", yref="paper",
            text=f"Median: {stats['spread_median']:.0f}",
            showarrow=False, font=dict(color=COLORS["amber"], size=11),
        )

    # 2. Trade size distribution
    if len(t) > 0:
        qty_counts = t["quantity"].value_counts().sort_index()
        fig_trade = go.Figure(go.Bar(
            x=qty_counts.index.astype(str),
            y=qty_counts.values,
            marker_color=COLORS["amber"],
            text=qty_counts.values,
            textposition="outside",
            textfont=dict(size=9, color=COLORS["text2"]),
        ))
        fig_trade.update_layout(**chart_layout)
        fig_trade.add_annotation(
            x=0.98, y=0.95, xref="paper", yref="paper",
            text=f"n={len(t)} | mean={t['quantity'].mean():.1f} | vol={int(t['quantity'].sum()):,}",
            showarrow=False, font=dict(color=COLORS["text2"], size=10),
            xanchor="right",
        )
    else:
        fig_trade = empty

    # 3. Volume profile
    vol_by_price = {}
    for _, row in p.iterrows():
        if pd.notna(row.get("bid_price_1")) and pd.notna(row.get("bid_volume_1")):
            pr = int(round(row["bid_price_1"]))
            vol_by_price[pr] = vol_by_price.get(pr, 0) + row["bid_volume_1"]
        if pd.notna(row.get("ask_price_1")) and pd.notna(row.get("ask_volume_1")):
            pr = int(round(row["ask_price_1"]))
            vol_by_price[pr] = vol_by_price.get(pr, 0) + row["ask_volume_1"]

    if vol_by_price:
        # Downsample if too many levels
        sorted_levels = sorted(vol_by_price.items())
        if len(sorted_levels) > 30:
            step = len(sorted_levels) // 30
            sorted_levels = sorted_levels[::step]
        vp_prices = [str(x[0]) for x in sorted_levels]
        vp_vols = [x[1] for x in sorted_levels]
        fig_vol = go.Figure(go.Bar(
            y=vp_prices, x=vp_vols,
            orientation="h",
            marker_color=COLORS["blue"],
            text=[f"{int(v):,}" for v in vp_vols],
            textposition="outside",
            textfont=dict(size=9, color=COLORS["text2"]),
        ))
        fig_vol.update_layout(**{**chart_layout, "yaxis": {**chart_layout.get("yaxis", {}), "autorange": "reversed"}})
    else:
        fig_vol = empty

    # 4. Returns distribution
    mids = p["mid_price"].values
    returns = np.diff(mids)
    if len(returns) > 0:
        ret_rounded = np.round(returns).astype(int)
        unique, counts = np.unique(ret_rounded, return_counts=True)
        colors = [COLORS["green"] if v >= 0 else COLORS["red"] for v in unique]
        fig_ret = go.Figure(go.Bar(
            x=unique.astype(str), y=counts,
            marker_color=colors,
            text=counts,
            textposition="outside",
            textfont=dict(size=9, color=COLORS["text2"]),
        ))
        fig_ret.update_layout(**chart_layout)
    else:
        fig_ret = empty

    # 5. Rolling volatility
    window = 50
    if len(returns) > window:
        vol_series = pd.Series(returns).rolling(window).std().dropna().values
        vol_ts = p["global_ts"].values[window:]
        if len(vol_ts) > len(vol_series):
            vol_ts = vol_ts[:len(vol_series)]
        elif len(vol_series) > len(vol_ts):
            vol_series = vol_series[:len(vol_ts)]

        # Downsample
        if len(vol_ts) > 500:
            step = len(vol_ts) // 500
            vol_ts = vol_ts[::step]
            vol_series = vol_series[::step]

        fig_volat = go.Figure(go.Scatter(
            x=vol_ts, y=vol_series,
            mode="lines", line=dict(color=COLORS["purple"], width=1.5),
            hovertemplate="Ts: %{x}<br>Vol: %{y:.3f}<extra></extra>",
        ))
        fig_volat.update_layout(**chart_layout)
        fig_volat.add_annotation(
            x=0.02, y=0.95, xref="paper", yref="paper",
            text=f"Min: {vol_series.min():.2f}  Max: {vol_series.max():.2f}  Mean: {vol_series.mean():.2f}",
            showarrow=False, font=dict(color=COLORS["text2"], size=10),
        )
    else:
        fig_volat = empty

    # 6. Stats table
    def fmt(val, f=".1f"):
        if val is None:
            return "N/A"
        return f"{val:{f}}"

    stat_rows_data = [
        ("Mid Price Mean", f"{stats['mid_mean']:.1f}"),
        ("Mid Price Std", f"{stats['mid_std']:.2f}"),
        ("Price Range", f"{stats['mid_min']:,.0f} – {stats['mid_max']:,.0f}"),
        ("Spread (median)", fmt(stats["spread_median"], ".0f")),
        ("Spread (mean)", fmt(stats["spread_mean"], ".1f")),
        ("AC(returns, lag1)", fmt(stats["ac_returns_1"], ".4f")),
        ("AC(level, lag1)", fmt(stats["ac_level_1"], ".4f")),
        ("Drift / timestamp", f"{stats['drift_per_ts']:.6f}"),
        ("Drift / day", f"{stats['drift_per_day']:.1f}"),
        ("Total Trades", f"{stats['trade_count']:,}"),
        ("Avg Trade Size", f"{stats['trade_size_mean']:.1f}"),
        ("Total Trade Volume", f"{stats['trade_vol_total']:,}"),
        ("Data Points", f"{stats['total_rows']:,}"),
    ]

    td_label = {"padding": "5px 0", "color": COLORS["text2"], "fontSize": "13px", "fontWeight": "500", "borderBottom": f"1px solid {COLORS['border']}"}
    td_val = {"padding": "5px 0", "textAlign": "right", "fontWeight": "600", "fontSize": "13px", "fontVariantNumeric": "tabular-nums", "borderBottom": f"1px solid {COLORS['border']}"}

    stat_rows = [
        html.Tr([html.Td(label, style=td_label), html.Td(val, style=td_val)])
        for label, val in stat_rows_data
    ]
    stats_table = html.Table(
        html.Tbody(stat_rows),
        style={"width": "100%", "borderCollapse": "collapse"},
    )

    return fig_spread, fig_trade, fig_vol, fig_ret, fig_volat, stats_table


# ── Run ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("Starting Prosperity 4 Market Analyzer...")
    print(f"Found rounds: {ROUNDS}")
    if ROUNDS:
        prices, trades = get_data(ROUNDS[0])
        products = get_products(prices)
        print(f"Products: {products}")
        print(f"Loaded {len(prices)} price rows, {len(trades)} trade rows")
    print("\nOpen http://localhost:8050 in your browser\n")
    app.run(debug=True, port=8050)
