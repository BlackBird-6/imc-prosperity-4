import dash
from dash import dcc, html, Input, Output, State, dash_table, callback_context, no_update
import dash.exceptions

from data_loader import DataStore, CATEGORIES, PRODUCT_TO_CAT, ALL_PRODUCTS, CAT_COLORS, PRODUCT_COLORS
import figures as F
import stats as S

# ── Bootstrap data once ───────────────────────────────────────────────────────
DS = DataStore()

ALL_DAYS = [2, 3, 4]

# ── Helpers ───────────────────────────────────────────────────────────────────

def _day_options():
    return [
        {"label": "All Days", "value": "all"},
        {"label": "Day 2",    "value": 2},
        {"label": "Day 3",    "value": 3},
        {"label": "Day 4",    "value": 4},
    ]


def _resolve_days(day_val):
    if day_val == "all" or day_val is None:
        return ALL_DAYS
    if isinstance(day_val, list):
        return [int(d) for d in day_val if d != "all"]
    return [int(day_val)]


def _sidebar():
    items = []
    for cat, prods in CATEGORIES.items():
        cat_id = cat.replace(" ", "-").lower()
        items.append(html.Details([
            html.Summary(
                cat,
                style={"cursor": "pointer", "fontWeight": "600",
                       "color": CAT_COLORS.get(cat, "#58a6ff"), "fontSize": "13px",
                       "padding": "4px 0"},
            ),
            html.Div([
                dcc.Checklist(
                    id=f"chk-{cat_id}",
                    options=[{"label": p.split("_", 1)[-1], "value": p} for p in prods],
                    value=[],
                    labelStyle={"display": "block", "fontSize": "12px",
                                "color": "#c9d1d9", "padding": "1px 0 1px 8px"},
                    inputStyle={"marginRight": "5px"},
                )
            ]),
        ], open=False, style={"marginBottom": "4px"}))
    return html.Div(items, style={"overflowY": "auto", "flex": "1", "paddingRight": "4px"})


def _all_checklist_ids():
    return [f"chk-{cat.replace(' ', '-').lower()}" for cat in CATEGORIES]


# ── Layout ────────────────────────────────────────────────────────────────────

HEADER_STYLE = {
    "display": "flex", "alignItems": "center", "gap": "24px",
    "background": "#161b22", "padding": "8px 16px",
    "borderBottom": "1px solid #30363d", "flexWrap": "wrap",
}
LABEL_STYLE = {"fontSize": "11px", "color": "#8b949e", "marginBottom": "2px"}
SIDEBAR_STYLE = {
    "width": "200px", "minWidth": "200px", "background": "#0d1117",
    "borderRight": "1px solid #21262d", "padding": "8px",
    "display": "flex", "flexDirection": "column",
}
CONTENT_STYLE = {"flex": "1", "minWidth": "0", "padding": "8px", "overflowY": "auto"}
PAGE_STYLE = {
    "display": "flex", "flexDirection": "column",
    "height": "100vh", "background": "#0d1117", "fontFamily": "monospace",
}

app = dash.Dash(__name__, suppress_callback_exceptions=True)
app.title = "IMC R5 Visualizer"

app.layout = html.Div([
    # ── Header ──
    html.Div([
        html.Span("IMC R5", style={"fontWeight": "700", "color": "#58a6ff", "fontSize": "16px"}),

        html.Div([
            html.Div("View", style=LABEL_STYLE),
            dcc.RadioItems(
                id="view-mode",
                options=[
                    {"label": "Category", "value": "category"},
                    {"label": "Day Compare", "value": "day-compare"},
                    {"label": "Single Asset", "value": "single-asset"},
                ],
                value="category",
                inline=True,
                inputStyle={"marginRight": "3px"},
                labelStyle={"marginRight": "12px", "fontSize": "13px", "color": "#c9d1d9"},
            ),
        ]),

        html.Div([
            html.Div("Day", style=LABEL_STYLE),
            dcc.Dropdown(
                id="day-select",
                options=_day_options(),
                value="all",
                clearable=False,
                style={"width": "120px", "fontSize": "12px"},
            ),
        ]),

        html.Div([
            html.Div("Price Mode", style=LABEL_STYLE),
            dcc.RadioItems(
                id="price-mode",
                options=[{"label": "Mid", "value": "mid"}, {"label": "Bid/Ask Band", "value": "spread"}],
                value="mid", inline=True,
                inputStyle={"marginRight": "3px"},
                labelStyle={"marginRight": "10px", "fontSize": "13px", "color": "#c9d1d9"},
            ),
        ]),

        html.Div([
            dcc.Checklist(
                id="toggles",
                options=[
                    {"label": " Trades", "value": "trades"},
                    {"label": " Normalise", "value": "norm"},
                    {"label": " Spread chart", "value": "spread"},
                    {"label": " Delta chart", "value": "delta"},
                ],
                value=[],
                inline=True,
                inputStyle={"marginRight": "3px"},
                labelStyle={"marginRight": "10px", "fontSize": "13px", "color": "#c9d1d9"},
            ),
        ]),
    ], style=HEADER_STYLE),

    # ── Body (switches per view) ──
    html.Div(id="body", style={"display": "flex", "flex": "1", "minHeight": "0"}),

], style=PAGE_STYLE)


# ── Aggregate selected products from all category checklists ──────────────────

@app.callback(
    Output("body", "children"),
    Input("view-mode", "value"),
)
def render_view(mode):
    if mode == "category":
        return _category_layout()
    if mode == "day-compare":
        return _day_compare_layout()
    return _single_asset_layout()


def _category_layout():
    return [
        html.Div([
            html.Div("Products", style={**LABEL_STYLE, "marginBottom": "6px", "fontSize": "12px"}),
            html.Button("Clear All", id="btn-clear", n_clicks=0,
                        style={"fontSize": "10px", "background": "#21262d", "color": "#c9d1d9",
                               "border": "1px solid #30363d", "padding": "2px 8px",
                               "cursor": "pointer", "marginBottom": "6px"}),
            _sidebar(),
        ], style=SIDEBAR_STYLE),

        html.Div([
            # Sweep indicator
            html.Div([
                html.Div("XIRECS Sweep  ■ single-cat  ■ multi-cat  ■ market-wide",
                         style={"fontSize": "10px", "color": "#8b949e", "marginBottom": "2px"}),
                dcc.Graph(id="cat-sweep", config={"displayModeBar": False},
                          style={"height": "90px"}),
            ]),

            # Main price chart
            dcc.Graph(id="cat-price", config={"displayModeBar": True},
                      style={"height": "360px"}),

            # Optional spread chart
            html.Div(id="cat-spread-wrap"),

            # Optional delta chart
            html.Div(id="cat-delta-wrap"),

            # Stats tabs
            html.Div(id="cat-stats", style={"marginTop": "8px"}),

        ], style=CONTENT_STYLE),
    ]


def _day_compare_layout():
    return [
        html.Div([
            html.Div("Products", style={**LABEL_STYLE, "marginBottom": "6px", "fontSize": "12px"}),
            html.Button("Clear All", id="btn-clear", n_clicks=0,
                        style={"fontSize": "10px", "background": "#21262d", "color": "#c9d1d9",
                               "border": "1px solid #30363d", "padding": "2px 8px",
                               "cursor": "pointer", "marginBottom": "6px"}),
            _sidebar(),
        ], style=SIDEBAR_STYLE),

        html.Div([
            html.Div("Solid = Day 2  |  Dashed = Day 3  |  Dotted = Day 4",
                     style={"fontSize": "11px", "color": "#8b949e", "marginBottom": "4px"}),
            dcc.Graph(id="dc-chart", config={"displayModeBar": True}, style={"height": "500px"}),
            html.Div(id="dc-stats", style={"marginTop": "8px"}),
        ], style=CONTENT_STYLE),
    ]


def _single_asset_layout():
    product_options = []
    for cat, prods in CATEGORIES.items():
        for p in prods:
            product_options.append({"label": f"{p}  [{cat}]", "value": p})

    TAB_STYLE = {"background": "#0d1117", "color": "#8b949e",
                 "fontSize": "12px", "padding": "4px 10px"}
    TAB_SEL   = {"background": "#161b22", "color": "#58a6ff",
                 "fontSize": "12px", "padding": "4px 10px"}

    return [
        html.Div([
            html.Div("Asset", style={**LABEL_STYLE, "marginBottom": "4px"}),
            dcc.Dropdown(
                id="sa-product",
                options=product_options,
                value="OXYGEN_SHAKE_GARLIC",
                clearable=False,
                style={"fontSize": "12px"},
            ),
            html.Div(id="sa-stats-sidebar",
                     style={"marginTop": "12px", "fontSize": "12px",
                            "color": "#c9d1d9", "overflowY": "auto"}),
        ], style={**SIDEBAR_STYLE, "width": "240px", "minWidth": "240px"}),

        html.Div([
            # Price chart — always visible, loads first
            dcc.Loading(
                dcc.Graph(id="sa-price", config={"displayModeBar": True},
                          style={"height": "320px"}),
                color="#58a6ff",
            ),

            # Sub-charts behind tabs — only one rendered at a time
            dcc.Tabs(
                id="sa-subtab", value="depth",
                children=[
                    dcc.Tab(label="Order Book Depth", value="depth",
                            style=TAB_STYLE, selected_style=TAB_SEL),
                    dcc.Tab(label="Spread",           value="spread",
                            style=TAB_STYLE, selected_style=TAB_SEL),
                    dcc.Tab(label="Cum. Delta",       value="delta",
                            style=TAB_STYLE, selected_style=TAB_SEL),
                    dcc.Tab(label="Returns",          value="returns",
                            style=TAB_STYLE, selected_style=TAB_SEL),
                    dcc.Tab(label="Rolling ±σ",       value="rolling",
                            style=TAB_STYLE, selected_style=TAB_SEL),
                    dcc.Tab(label="Category peers",   value="siblings",
                            style=TAB_STYLE, selected_style=TAB_SEL),
                ],
                style={"marginTop": "6px"},
            ),
            dcc.Loading(
                html.Div(id="sa-subtab-content", style={"minHeight": "180px"}),
                color="#58a6ff",
            ),
        ], style=CONTENT_STYLE),
    ]


# ── Collect selected products (category view & day compare share same sidebar) ─

def _collect_products(*checklists):
    products = []
    for vals in checklists:
        if vals:
            products.extend(vals)
    return products


# ── Category view callbacks ───────────────────────────────────────────────────

_chk_ids = _all_checklist_ids()
_chk_inputs = [Input(cid, "value") for cid in _chk_ids]


@app.callback(
    Output("cat-sweep", "figure"),
    Output("cat-price", "figure"),
    Output("cat-spread-wrap", "children"),
    Output("cat-delta-wrap", "children"),
    Input("day-select", "value"),
    Input("price-mode", "value"),
    Input("toggles", "value"),
    *_chk_inputs,
)
def update_category_charts(day_val, price_mode, toggles, *checklists):
    products = _collect_products(*checklists)
    days = _resolve_days(day_val)
    normalize = "norm" in (toggles or [])
    show_trades = "trades" in (toggles or [])
    show_spread = "spread" in (toggles or [])
    show_delta = "delta" in (toggles or [])

    sweep_fig = F.sweep_chart(DS.sw(days))

    if not products:
        empty = F.price_chart(DS.px(), [], price_mode, normalize=normalize)
        return sweep_fig, empty, None, None

    pf = DS.px(products, days)
    tf = DS.tx(products, days) if show_trades else None
    price_fig = F.price_chart(pf, products, price_mode, show_trades, tf, normalize)

    spread_wrap = None
    if show_spread:
        spread_wrap = dcc.Graph(
            figure=F.spread_chart(pf, products),
            config={"displayModeBar": False},
            style={"height": "130px"},
        )

    delta_wrap = None
    if show_delta:
        df = DS.dx(products, days)
        delta_wrap = dcc.Graph(
            figure=F.delta_chart(df, products),
            config={"displayModeBar": False},
            style={"height": "150px"},
        )

    return sweep_fig, price_fig, spread_wrap, delta_wrap


@app.callback(
    Output("cat-stats", "children"),
    Input("day-select", "value"),
    Input("toggles", "value"),
    *_chk_inputs,
)
def update_category_stats(day_val, toggles, *checklists):
    products = _collect_products(*checklists)
    days = _resolve_days(day_val)

    if not products:
        return html.Div("Select products to see stats.", style={"color": "#8b949e", "padding": "12px"})

    # Determine which categories are represented
    cats_selected = {}
    for p in products:
        cat = PRODUCT_TO_CAT.get(p)
        if cat:
            cats_selected.setdefault(cat, []).append(p)

    pf = DS.px(products, days)
    tf = DS.tx(products, days)

    tabs = []

    for cat, prods in cats_selected.items():
        rows = S.category_stats_table(pf, tf, prods)
        tab_children = [
            # Stats table
            dash_table.DataTable(
                data=rows,
                columns=S.STATS_COLUMNS,
                sort_action="native",
                page_size=10,
                style_table={"overflowX": "auto"},
                style_cell={"background": "#0d1117", "color": "#c9d1d9",
                            "border": "1px solid #21262d", "fontSize": "11px",
                            "padding": "4px 8px", "fontFamily": "monospace"},
                style_header={"background": "#161b22", "fontWeight": "600",
                              "color": "#58a6ff", "border": "1px solid #30363d"},
                style_data_conditional=[
                    {"if": {"filter_query": "{total_drift} > 0", "column_id": "total_drift"},
                     "color": "#2ecc71"},
                    {"if": {"filter_query": "{total_drift} < 0", "column_id": "total_drift"},
                     "color": "#e74c3c"},
                    {"if": {"filter_query": "{drift_per_day} > 0", "column_id": "drift_per_day"},
                     "color": "#2ecc71"},
                    {"if": {"filter_query": "{drift_per_day} < 0", "column_id": "drift_per_day"},
                     "color": "#e74c3c"},
                ],
                export_format="csv",
            ),

            # Intra-category charts
            html.Div([
                dcc.Graph(figure=F.normalised_overlay(pf, prods),   config={"displayModeBar": False}),
                dcc.Graph(figure=F.return_distribution(pf, prods),  config={"displayModeBar": False}),
                dcc.Graph(figure=F.rolling_volatility(pf, prods),   config={"displayModeBar": False}),
                dcc.Graph(figure=F.correlation_heatmap(pf, prods),  config={"displayModeBar": False}),
                dcc.Graph(figure=F.lead_lag_heatmap(pf, prods),     config={"displayModeBar": False}),
                dcc.Graph(figure=F.delta_chart(DS.dx(prods, days), prods), config={"displayModeBar": False}),
            ], style={"display": "grid", "gridTemplateColumns": "1fr 1fr", "gap": "4px"}),

            # Category-specific extras
            _category_extras(cat, pf, prods),
        ]
        tabs.append(dcc.Tab(label=cat, value=cat, children=tab_children,
                            style={"background": "#0d1117", "color": "#8b949e", "fontSize": "12px"},
                            selected_style={"background": "#161b22", "color": "#58a6ff", "fontSize": "12px"}))

    if len(cats_selected) > 1:
        cross_children = _cross_category_tab(cats_selected, pf, days)
        tabs.append(dcc.Tab(label="Cross-category", value="cross",
                            children=cross_children,
                            style={"background": "#0d1117", "color": "#8b949e", "fontSize": "12px"},
                            selected_style={"background": "#161b22", "color": "#58a6ff", "fontSize": "12px"}))

    return dcc.Tabs(children=tabs, value=list(cats_selected.keys())[0] if cats_selected else None,
                    style={"marginTop": "8px"})


def _category_extras(cat: str, pf, prods):
    if cat == "Purification Pebbles":
        return dcc.Graph(figure=F.pebble_basket(pf), config={"displayModeBar": False})
    if cat == "UV-Visors":
        return dcc.Graph(figure=F.uv_inter_spread(pf), config={"displayModeBar": False})
    if cat == "Construction Panels":
        return dcc.Graph(figure=F.panel_ratios(pf), config={"displayModeBar": False})
    return html.Div()


def _cross_category_tab(cats_selected: dict, pf, days):
    # Category basket returns correlation
    cat_prods = list(cats_selected.items())
    all_selected = [p for prods in cats_selected.values() for p in prods]

    rows = []
    for cat, prods in cat_prods:
        cat_pf = pf[pf["product"].isin(prods)]
        mean_mid = cat_pf.groupby("global_ts")["mid_price"].mean().reset_index()
        mean_mid["category"] = cat
        rows.append(mean_mid)

    import pandas as pd
    combined = pd.concat(rows)
    piv = combined.pivot_table(index="global_ts", columns="category", values="mid_price").dropna()

    import plotly.graph_objects as go
    overlay = go.Figure()
    for cat in piv.columns:
        y = piv[cat] / piv[cat].iloc[0] * 10000
        overlay.add_trace(go.Scatter(x=piv.index, y=y, name=cat,
                                     line=dict(width=1.5)))
    F._day_vlines(overlay)
    overlay.update_layout(**F.DARK, height=250, margin=F.MARGIN,
                          title="Category Basket (normalised)",
                          xaxis=dict(**F.GRID), yaxis=dict(**F.GRID),
                          legend=dict(orientation="h", y=1.04, x=1, xanchor="right"))

    return [dcc.Graph(figure=overlay, config={"displayModeBar": False})]


# ── Day comparison callbacks ──────────────────────────────────────────────────

@app.callback(
    Output("dc-chart", "figure"),
    Output("dc-stats", "children"),
    Input("day-select", "value"),
    Input("toggles", "value"),
    *_chk_inputs,
)
def update_day_compare(day_val, toggles, *checklists):
    products = _collect_products(*checklists)
    normalize = "norm" in (toggles or [])

    if not products:
        return F.day_comparison_chart(DS.px(), [], normalize), html.Div()

    pf = DS.px(products)
    fig = F.day_comparison_chart(pf, products, normalize)

    # Per-day stats table
    stat_rows = []
    for prod in products:
        for day in ALL_DAYS:
            dpf = pf[(pf["product"] == prod) & (pf["day"] == day)]
            if dpf.empty:
                continue
            mid = dpf["mid_price"].values
            run_max = __import__("numpy").maximum.accumulate(mid)
            dd = float((mid - run_max).min())
            stat_rows.append({
                "product": prod.split("_", 1)[-1],
                "day": day,
                "open": round(float(mid[0]), 1),
                "close": round(float(mid[-1]), 1),
                "high": round(float(mid.max()), 1),
                "low": round(float(mid.min()), 1),
                "drift": round(float(mid[-1] - mid[0]), 1),
                "max_dd": round(dd, 1),
            })

    tbl = dash_table.DataTable(
        data=stat_rows,
        columns=[
            {"name": c, "id": c} for c in
            ["product", "day", "open", "close", "high", "low", "drift", "max_dd"]
        ],
        sort_action="native",
        style_table={"overflowX": "auto"},
        style_cell={"background": "#0d1117", "color": "#c9d1d9",
                    "border": "1px solid #21262d", "fontSize": "11px",
                    "padding": "4px 8px", "fontFamily": "monospace"},
        style_header={"background": "#161b22", "fontWeight": "600",
                      "color": "#58a6ff", "border": "1px solid #30363d"},
        style_data_conditional=[
            {"if": {"filter_query": "{drift} > 0", "column_id": "drift"}, "color": "#2ecc71"},
            {"if": {"filter_query": "{drift} < 0", "column_id": "drift"}, "color": "#e74c3c"},
        ],
    )
    return fig, tbl


# ── Single asset callbacks ────────────────────────────────────────────────────

@app.callback(
    Output("sa-price",         "figure"),
    Output("sa-stats-sidebar", "children"),
    Input("sa-product",  "value"),
    Input("day-select",  "value"),
    Input("price-mode",  "value"),
    Input("toggles",     "value"),
)
def update_sa_main(product, day_val, price_mode, toggles):
    """Fast callback: only price chart + stats sidebar."""
    if not product:
        return F.price_chart(DS.px(), [], price_mode), html.Div()

    days = _resolve_days(day_val)
    show_trades = "trades" in (toggles or [])
    normalize   = "norm"   in (toggles or [])

    pf = DS.px([product], days)
    tf = DS.tx([product], days)

    price_fig = F.price_chart(pf, [product], price_mode, show_trades,
                              tf if show_trades else None, normalize)

    s = S.product_stats(pf, tf)
    direction = "▲ LONG" if (s.get("drift_per_day") or 0) > 0 else "▼ SHORT"
    dir_color = "#2ecc71" if "LONG" in direction else "#e74c3c"

    stat_items = [
        html.Div(direction, style={"color": dir_color, "fontWeight": "700",
                                   "fontSize": "14px", "marginBottom": "8px"}),
    ]
    labels = {
        "start_price":   "Start",        "end_price":     "End",
        "total_drift":   "Drift",        "drift_pct":     "Drift %",
        "drift_per_day": "Drift/Day",    "ols_slope":     "OLS/Day",
        "r2":            "R²",           "mean":          "Mean",
        "std_dev":       "Std Dev",      "vol_pct":       "Vol %",
        "min_price":     "Min",          "max_price":     "Max",
        "min_at":        "Min At",       "max_at":        "Max At",
        "max_drawdown":  "Max DD",       "max_dd_pct":    "Max DD %",
        "max_runup":     "Max Runup",    "max_ru_pct":    "Runup %",
        "autocorr_l1":   "AC Lag-1",    "half_life":     "Half-Life",
        "skewness":      "Skew",         "kurtosis":      "Kurt",
        "mean_spread":   "Mean Spread",  "spread_pct":    "Spread %",
        "n_trades":      "Trades",       "avg_trade_qty": "Avg Qty",
        "trade_freq":    "Trade/1k ts",
    }
    for key, label in labels.items():
        val = s.get(key)
        if val is None:
            continue
        val_str = (f"{val:+.1f}" if isinstance(val, float)
                   and key in ("total_drift", "drift_per_day", "ols_slope")
                   else str(val))
        stat_items.append(html.Div([
            html.Span(label + ": ", style={"color": "#8b949e"}),
            html.Span(val_str, style={"color": "#c9d1d9"}),
        ], style={"marginBottom": "2px"}))

    return price_fig, html.Div(stat_items)


@app.callback(
    Output("sa-subtab-content", "children"),
    Input("sa-subtab",   "value"),
    Input("sa-product",  "value"),
    Input("day-select",  "value"),
)
def update_sa_subchart(tab, product, day_val):
    """Lazy callback: only computes the active sub-chart tab."""
    if not product:
        return html.Div()

    days = _resolve_days(day_val)
    pf   = DS.px([product], days)
    tf   = DS.tx([product], days)
    df   = DS.dx([product], days)

    GH = {"config": {"displayModeBar": False}}

    if tab == "depth":
        return dcc.Graph(figure=F.depth_chart(pf, product),     **GH, style={"height": "220px"})
    if tab == "spread":
        return dcc.Graph(figure=F.spread_chart(pf, [product]),  **GH, style={"height": "220px"})
    if tab == "delta":
        return dcc.Graph(figure=F.delta_chart(df, [product]),   **GH, style={"height": "220px"})
    if tab == "returns":
        return dcc.Graph(figure=F.returns_scatter(pf, product), **GH, style={"height": "220px"})
    if tab == "rolling":
        return dcc.Graph(figure=F.rolling_mean_std(pf, product),**GH, style={"height": "220px"})
    if tab == "siblings":
        cat      = PRODUCT_TO_CAT.get(product)
        siblings = [p for p in CATEGORIES.get(cat, []) if p != product]
        fig      = F.normalised_overlay(DS.px([product] + siblings, days),
                                        [product] + siblings)
        return html.Div([
            html.Div(f"{cat} — all products (normalised)",
                     style={"color": "#8b949e", "fontSize": "11px",
                            "margin": "4px 0 2px 0"}),
            dcc.Graph(figure=fig, **GH, style={"height": "220px"}),
        ])
    return html.Div()


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app.run(debug=True, port=8050)
