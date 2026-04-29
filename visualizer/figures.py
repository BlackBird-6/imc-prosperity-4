import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from scipy import stats as sp

from data_loader import PRODUCT_COLORS, DAY_OFFSET

DARK = dict(
    plot_bgcolor="#0d1117",
    paper_bgcolor="#0d1117",
    font=dict(color="#c9d1d9", size=12),
)
GRID = dict(gridcolor="#21262d", zeroline=False)
GRID_ZERO = dict(gridcolor="#21262d", zeroline=True, zerolinecolor="#444")
MARGIN = dict(l=55, r=15, t=35, b=35)
MARGIN_COMPACT = dict(l=55, r=15, t=8, b=8)

DAY_LINES = [
    dict(x=DAY_OFFSET, label="D2→D3"),
    dict(x=2 * DAY_OFFSET, label="D3→D4"),
]

SWEEP_TIER_COLOR = {
    "single-category": "#2ecc71",
    "multi-category":  "#f39c12",
    "market-wide":     "#e74c3c",
}


def _day_vlines(fig, rows=None):
    for dl in DAY_LINES:
        kw = dict(x=dl["x"], line_dash="dash", line_color="rgba(200,200,200,0.2)",
                  line_width=1, annotation_text=dl["label"],
                  annotation_font=dict(size=9, color="#888"))
        if rows:
            for r in rows:
                fig.add_vline(row=r, col=1, **kw)
        else:
            fig.add_vline(**kw)


def _color(prod):
    return PRODUCT_COLORS.get(prod, "#888888")


def _downsample(df: pd.DataFrame, max_pts: int = 3000) -> pd.DataFrame:
    """Thin a DataFrame to at most max_pts rows, preserving first and last."""
    n = len(df)
    if n <= max_pts:
        return df
    idx = list(range(0, n, n // max_pts))
    if idx[-1] != n - 1:
        idx.append(n - 1)
    return df.iloc[idx]


def _rgba(hex_color: str, alpha: float = 0.15) -> str:
    """Convert a #RRGGBB hex string to rgba(r,g,b,alpha). Safe for Plotly."""
    h = hex_color.lstrip("#")
    if len(h) == 6:
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        return f"rgba({r},{g},{b},{alpha})"
    return hex_color  # already rgba or named — return as-is


# ── Price chart ───────────────────────────────────────────────────────────────

def price_chart(
    price_df: pd.DataFrame,
    products: list,
    price_mode: str = "mid",
    show_trades: bool = False,
    trade_df: pd.DataFrame = None,
    normalize: bool = False,
    show_ols: bool = True,
) -> go.Figure:
    fig = go.Figure()

    for prod in products:
        pf = price_df[price_df["product"] == prod].sort_values("global_ts")
        if pf.empty:
            continue
        c = _color(prod)
        x = pf["global_ts"]
        scale = (10000 / pf["mid_price"].iloc[0]) if normalize and pf["mid_price"].iloc[0] else 1
        mid = pf["mid_price"] * scale
        bid = pf["bid_price_1"] * scale
        ask = pf["ask_price_1"] * scale

        custom = np.column_stack([bid, ask, pf["spread"]])

        if price_mode == "spread":
            # Shaded bid-ask band
            xs = pd.concat([x, x.iloc[::-1]])
            ys = pd.concat([ask, bid.iloc[::-1]])
            fig.add_trace(go.Scatter(
                x=xs, y=ys, fill="toself",
                fillcolor=_rgba(c, 0.15),
                line=dict(width=0), showlegend=False, hoverinfo="skip", name=prod + "_band",
            ))

        fig.add_trace(go.Scatter(
            x=x, y=mid, name=prod, line=dict(color=c, width=1.5),
            customdata=custom,
            hovertemplate=(
                f"<b>{prod}</b><br>"
                "ts: %{x}<br>mid: %{y:.1f}<br>"
                "bid: %{customdata[0]:.1f}  ask: %{customdata[1]:.1f}<br>"
                "spread: %{customdata[2]:.1f}<extra></extra>"
            ),
        ))

        # OLS only when single product is charted
        if show_ols and len(products) == 1:
            xv = x.values.astype(float)
            yv = mid.values
            slope, intercept, *_ = sp.linregress(xv, yv)
            label = f"OLS {slope * DAY_OFFSET:+.0f}/day"
            fig.add_trace(go.Scatter(
                x=x, y=slope * xv + intercept, name=label,
                line=dict(color=c, width=1, dash="dash"), hoverinfo="skip",
            ))

    if show_trades and trade_df is not None and not trade_df.empty:
        tf = trade_df[trade_df["product"].isin(products)]
        if not tf.empty:
            marker_color = tf["signed_qty"].map(
                lambda q: "#2ecc71" if q > 0 else ("#e74c3c" if q < 0 else "#888")
            )
            fig.add_trace(go.Scatter(
                x=tf["global_ts"], y=tf["price"],
                mode="markers",
                marker=dict(size=4, color=marker_color, line=dict(width=0)),
                name="Trades", hovertemplate="ts: %{x}<br>price: %{y:.1f}<extra></extra>",
            ))

    _day_vlines(fig)
    fig.update_layout(
        **DARK, margin=MARGIN, hovermode="x unified",
        xaxis=dict(title="Timestamp", **GRID),
        yaxis=dict(title="Price (norm.)" if normalize else "Price", **GRID),
        legend=dict(orientation="h", y=1.04, x=1, xanchor="right"),
    )
    return fig


# ── Sweep indicator ───────────────────────────────────────────────────────────

def sweep_chart(sweep_df: pd.DataFrame) -> go.Figure:
    df = sweep_df.copy()
    colors = df["tier"].map(SWEEP_TIER_COLOR).fillna("#888")
    # Hover: list products at that ts is expensive — just show count + tier
    fig = go.Figure(go.Bar(
        x=df["global_ts"], y=df["sweep_size"],
        marker_color=colors,
        hovertemplate="ts: %{x}<br>swept: %{y} products<extra></extra>",
        name="Sweep",
    ))
    _day_vlines(fig)
    fig.update_layout(
        **DARK, height=90, margin=MARGIN_COMPACT,
        xaxis=dict(showticklabels=False, **GRID),
        yaxis=dict(title="Sweep", **GRID),
        showlegend=False,
    )
    return fig


# ── Spread width ──────────────────────────────────────────────────────────────

def spread_chart(price_df: pd.DataFrame, products: list) -> go.Figure:
    fig = go.Figure()
    for prod in products:
        pf = price_df[price_df["product"] == prod].sort_values("global_ts")
        if pf.empty:
            continue
        fig.add_trace(go.Scatter(
            x=pf["global_ts"], y=pf["spread"],
            name=prod, line=dict(color=_color(prod), width=1),
            hovertemplate=f"{prod}<br>ts: %{{x}}<br>spread: %{{y:.1f}}<extra></extra>",
        ))
    _day_vlines(fig)
    fig.update_layout(
        **DARK, height=130, margin=MARGIN_COMPACT,
        xaxis=dict(title="Timestamp", **GRID),
        yaxis=dict(title="Spread (L1)", **GRID),
        showlegend=False,
    )
    return fig


# ── Cumulative signed delta ───────────────────────────────────────────────────

def delta_chart(delta_df: pd.DataFrame, products: list) -> go.Figure:
    fig = go.Figure()
    for prod in products:
        df = delta_df[delta_df["product"] == prod].sort_values("global_ts")
        if df.empty:
            continue
        fig.add_trace(go.Scatter(
            x=df["global_ts"], y=df["cum_delta"],
            name=prod, line=dict(color=_color(prod), width=1.5, shape="hv"),
            hovertemplate=f"{prod}<br>ts: %{{x}}<br>Δ: %{{y}}<extra></extra>",
        ))
    _day_vlines(fig)
    fig.update_layout(
        **DARK, height=150, margin=MARGIN_COMPACT,
        xaxis=dict(title="Timestamp", **GRID),
        yaxis=dict(title="Cum. Delta", **GRID_ZERO),
        showlegend=False,
    )
    return fig


# ── Day comparison ────────────────────────────────────────────────────────────

def day_comparison_chart(price_df: pd.DataFrame, products: list, normalize: bool = False) -> go.Figure:
    fig = go.Figure()
    DASHES = {2: "solid", 3: "dash", 4: "dot"}

    for prod in products:
        c = _color(prod)
        for day in [2, 3, 4]:
            pf = price_df[(price_df["product"] == prod) & (price_df["day"] == day)].sort_values("timestamp")
            if pf.empty:
                continue
            y = pf["mid_price"]
            if normalize and y.iloc[0]:
                y = y / y.iloc[0] * 10000
            short = prod.split("_")[-1]
            fig.add_trace(go.Scatter(
                x=pf["timestamp"], y=y,
                name=f"{short} D{day}",
                line=dict(color=c, width=1.5, dash=DASHES[day]),
                hovertemplate=f"<b>{prod} Day {day}</b><br>ts: %{{x}}<br>price: %{{y:.1f}}<extra></extra>",
            ))

    fig.update_layout(
        **DARK, margin=MARGIN, hovermode="x unified",
        xaxis=dict(title="Within-Day Timestamp", **GRID),
        yaxis=dict(title="Price (norm.)" if normalize else "Price", **GRID),
        legend=dict(orientation="h", y=1.04, x=1, xanchor="right"),
    )
    return fig


# ── Single-asset sub-charts ───────────────────────────────────────────────────

def depth_chart(price_df: pd.DataFrame, product: str) -> go.Figure:
    pf = _downsample(
        price_df[price_df["product"] == product].sort_values("global_ts"),
        max_pts=2000,
    )
    if pf.empty:
        return go.Figure()

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=pf["global_ts"], y=pf["bid_volume_1"],
        name="Bid L1", fill="tozeroy", fillcolor="rgba(46,204,113,0.25)",
        line=dict(color="#2ecc71", width=0.5)))
    fig.add_trace(go.Scatter(x=pf["global_ts"], y=pf["bid_volume_2"],
        name="Bid L2", fill="tozeroy", fillcolor="rgba(46,204,113,0.1)",
        line=dict(color="#2ecc71", width=0.5, dash="dot")))
    fig.add_trace(go.Scatter(x=pf["global_ts"], y=-pf["ask_volume_1"],
        name="Ask L1", fill="tozeroy", fillcolor="rgba(231,76,60,0.25)",
        line=dict(color="#e74c3c", width=0.5)))
    fig.add_trace(go.Scatter(x=pf["global_ts"], y=-pf["ask_volume_2"],
        name="Ask L2", fill="tozeroy", fillcolor="rgba(231,76,60,0.1)",
        line=dict(color="#e74c3c", width=0.5, dash="dot")))

    # Level 3 appearances as triangle markers
    l3 = pf[(pf["bid_volume_3"] > 0) | (pf["ask_volume_3"] > 0)]
    if not l3.empty:
        fig.add_trace(go.Scatter(
            x=l3["global_ts"], y=[0] * len(l3),
            mode="markers", marker=dict(symbol="triangle-up", size=8, color="#f1c40f"),
            name="L3 event",
        ))

    fig.add_hline(y=0, line_color="#30363d", line_width=1)
    _day_vlines(fig)
    fig.update_layout(
        **DARK, height=140, margin=MARGIN_COMPACT,
        xaxis=dict(**GRID),
        yaxis=dict(title="Vol (bid+/ask-)", **GRID_ZERO),
        showlegend=False,
    )
    return fig


def returns_scatter(price_df: pd.DataFrame, product: str) -> go.Figure:
    pf = price_df[price_df["product"] == product].sort_values("global_ts")
    returns = pf["mid_price"].diff().dropna()
    # Use lines+markers downsampled — raw 30k marker scatter is very slow in browser
    ds = _downsample(
        pd.DataFrame({"global_ts": pf["global_ts"].iloc[1:].values, "ret": returns.values}),
        max_pts=3000,
    )
    fig = go.Figure(go.Scatter(
        x=ds["global_ts"], y=ds["ret"],
        mode="lines", line=dict(color=_color(product), width=0.8),
        name="Returns",
        hovertemplate="ts: %{x}<br>Δ: %{y:.2f}<extra></extra>",
    ))
    fig.add_hline(y=0, line_color="#444", line_width=1)
    _day_vlines(fig)
    fig.update_layout(
        **DARK, height=130, margin=MARGIN_COMPACT,
        xaxis=dict(**GRID), yaxis=dict(title="1-step Return", **GRID_ZERO),
        showlegend=False,
    )
    return fig


def rolling_mean_std(price_df: pd.DataFrame, product: str, window: int = 500) -> go.Figure:
    pf = price_df[price_df["product"] == product].sort_values("global_ts")
    mid = pf["mid_price"]
    roll_mean = mid.rolling(window).mean()
    roll_std = mid.rolling(window).std()
    c = _color(product)

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=pf["global_ts"], y=roll_mean + roll_std,
        line=dict(width=0), showlegend=False, hoverinfo="skip", name="upper",
    ))
    fig.add_trace(go.Scatter(
        x=pf["global_ts"], y=roll_mean - roll_std,
        fill="tonexty", fillcolor="rgba(88,166,255,0.12)",
        line=dict(width=0), showlegend=False, hoverinfo="skip", name="lower",
    ))
    fig.add_trace(go.Scatter(
        x=pf["global_ts"], y=roll_mean,
        name=f"Rolling mean ({window})", line=dict(color=c, width=1.5),
    ))
    fig.add_trace(go.Scatter(
        x=pf["global_ts"], y=mid,
        name="Mid", line=dict(color="#c9d1d9", width=0.8, dash="dot"),
    ))
    _day_vlines(fig)
    fig.update_layout(
        **DARK, height=160, margin=MARGIN_COMPACT,
        xaxis=dict(**GRID), yaxis=dict(title=f"Price ± 1σ ({window})", **GRID),
        showlegend=False,
    )
    return fig


# ── Category intra-analysis charts ────────────────────────────────────────────

def normalised_overlay(price_df: pd.DataFrame, products: list) -> go.Figure:
    fig = go.Figure()
    for prod in products:
        pf = price_df[price_df["product"] == prod].sort_values("global_ts")
        if pf.empty or pf["mid_price"].iloc[0] == 0:
            continue
        norm = pf["mid_price"] / pf["mid_price"].iloc[0] * 10000
        short = prod.split("_")[-1]
        fig.add_trace(go.Scatter(
            x=pf["global_ts"], y=norm, name=short,
            line=dict(color=_color(prod), width=1.5),
        ))
    _day_vlines(fig)
    fig.update_layout(
        **DARK, height=230, margin={**MARGIN, "t": 30},
        title="Normalised Price (rebased to 10 000)",
        xaxis=dict(**GRID), yaxis=dict(title="Norm. Price", **GRID),
        legend=dict(orientation="h", y=1.04, x=1, xanchor="right"),
    )
    return fig


def return_distribution(price_df: pd.DataFrame, products: list) -> go.Figure:
    fig = go.Figure()
    for prod in products:
        pf = price_df[price_df["product"] == prod].sort_values("global_ts")
        returns = pf["mid_price"].diff().dropna()
        short = prod.split("_")[-1]
        fig.add_trace(go.Histogram(
            x=returns, name=short, opacity=0.55, nbinsx=60,
            marker_color=_color(prod),
        ))
    fig.update_layout(
        **DARK, barmode="overlay", height=200, margin={**MARGIN, "t": 30},
        title="Return Distribution (1-step price changes)",
        xaxis=dict(title="Price Change", **GRID),
        yaxis=dict(title="Count", **GRID),
        legend=dict(orientation="h", y=1.04, x=1, xanchor="right"),
    )
    return fig


def rolling_volatility(price_df: pd.DataFrame, products: list, window: int = 1000) -> go.Figure:
    fig = go.Figure()
    for prod in products:
        pf = price_df[price_df["product"] == prod].sort_values("global_ts")
        rv = pf["mid_price"].diff().rolling(window).std()
        short = prod.split("_")[-1]
        fig.add_trace(go.Scatter(
            x=pf["global_ts"], y=rv, name=short,
            line=dict(color=_color(prod), width=1.5),
        ))
    _day_vlines(fig)
    fig.update_layout(
        **DARK, height=200, margin={**MARGIN, "t": 30},
        title=f"Rolling Volatility ({window}-step σ of returns)",
        xaxis=dict(**GRID), yaxis=dict(title="Std Dev", **GRID),
        legend=dict(orientation="h", y=1.04, x=1, xanchor="right"),
    )
    return fig


def correlation_heatmap(price_df: pd.DataFrame, products: list) -> go.Figure:
    if len(products) < 2:
        return go.Figure(layout=dict(**DARK, title="Need ≥2 products"))

    mat_dict = {}
    for p in products:
        mid = price_df[price_df["product"] == p].sort_values("global_ts")["mid_price"]
        mat_dict[p] = mid.diff().dropna().values

    min_len = min(len(v) for v in mat_dict.values())
    arr = np.array([mat_dict[p][:min_len] for p in products])
    corr = np.corrcoef(arr)
    labels = [p.split("_")[-1] for p in products]

    fig = go.Figure(go.Heatmap(
        z=corr, x=labels, y=labels,
        colorscale="RdBu", zmid=0, zmin=-1, zmax=1,
        text=np.round(corr, 2), texttemplate="%{text}",
        hovertemplate="x: %{x}<br>y: %{y}<br>corr: %{z:.3f}<extra></extra>",
    ))
    fig.update_layout(
        **DARK, height=280, margin={**MARGIN, "t": 40},
        title="Return Correlation (pairwise Pearson)",
    )
    return fig


def lead_lag_heatmap(price_df: pd.DataFrame, products: list, max_lag: int = 10) -> go.Figure:
    if len(products) < 2:
        return go.Figure(layout=dict(**DARK, title="Need ≥2 products"))

    returns = {}
    for p in products:
        mid = price_df[price_df["product"] == p].sort_values("global_ts")["mid_price"]
        returns[p] = mid.diff().dropna().values

    min_len = min(len(v) for v in returns.values())
    lags = list(range(-max_lag, max_lag + 1))
    labels = [p.split("_")[-1] for p in products]

    z = np.zeros((len(products), len(lags)))
    base = products[0]
    for i, p in enumerate(products):
        for j, lag in enumerate(lags):
            a = returns[base][:min_len]
            b = returns[p][:min_len]
            if lag > 0:
                z[i, j] = np.corrcoef(a[lag:], b[:-lag])[0, 1]
            elif lag < 0:
                z[i, j] = np.corrcoef(a[:lag], b[-lag:])[0, 1]
            else:
                z[i, j] = np.corrcoef(a, b)[0, 1]

    fig = go.Figure(go.Heatmap(
        z=z, x=lags, y=labels,
        colorscale="RdBu", zmid=0, zmin=-1, zmax=1,
        hovertemplate="product: %{y}<br>lag: %{x}<br>corr: %{z:.3f}<extra></extra>",
    ))
    fig.update_layout(
        **DARK, height=280, margin={**MARGIN, "t": 40},
        title=f"Lead-Lag Correlation vs {labels[0]} (lags −{max_lag} to +{max_lag})",
        xaxis=dict(title="Lag (steps)"),
    )
    return fig


# ── Category-specific extras ──────────────────────────────────────────────────

def pebble_basket(price_df: pd.DataFrame) -> go.Figure:
    PEBBLES = ["PEBBLES_XS", "PEBBLES_S", "PEBBLES_M", "PEBBLES_L", "PEBBLES_XL"]
    piv = (
        price_df[price_df["product"].isin(PEBBLES)]
        .pivot_table(index="global_ts", columns="product", values="mid_price")
        .dropna()
    )
    basket = piv.sum(axis=1)
    dev = basket - 50000

    fig = make_subplots(rows=2, cols=1, shared_xaxes=True,
                        row_heights=[0.65, 0.35], vertical_spacing=0.04)
    fig.add_trace(go.Scatter(x=basket.index, y=basket, name="Basket", line=dict(color="#3498db", width=1.5)), row=1, col=1)
    fig.add_hline(y=50000, line_dash="dash", line_color="#f1c40f", annotation_text="50 000", row=1, col=1)
    fig.add_trace(go.Scatter(x=dev.index, y=dev, name="Deviation",
        fill="tozeroy",
        fillcolor="rgba(231,76,60,0.2)",
        line=dict(color="#e74c3c", width=1)), row=2, col=1)
    fig.add_hline(y=0, line_color="#444", row=2, col=1)

    _day_vlines(fig, rows=[1, 2])
    fig.update_layout(
        **DARK, height=320, margin={**MARGIN, "t": 40},
        title="Purification Pebbles — Basket Sum",
        showlegend=False,
    )
    fig.update_yaxes(title_text="Basket Sum", row=1, col=1, **GRID)
    fig.update_yaxes(title_text="Dev from 50k", row=2, col=1, **GRID_ZERO)
    return fig


def uv_inter_spread(price_df: pd.DataFrame) -> go.Figure:
    UV = ["UV_VISOR_YELLOW", "UV_VISOR_AMBER", "UV_VISOR_ORANGE", "UV_VISOR_RED", "UV_VISOR_MAGENTA"]
    piv = (
        price_df[price_df["product"].isin(UV)]
        .pivot_table(index="global_ts", columns="product", values="mid_price")
        .dropna()
    )
    spread = piv.max(axis=1) - piv.min(axis=1)
    fig = go.Figure(go.Scatter(
        x=spread.index, y=spread, fill="tozeroy",
        fillcolor="rgba(155,89,182,0.2)", line=dict(color="#9b59b6", width=1.5),
        hovertemplate="ts: %{x}<br>inter-spread: %{y:.1f}<extra></extra>",
    ))
    _day_vlines(fig)
    fig.update_layout(
        **DARK, height=200, margin={**MARGIN, "t": 40},
        title="UV-Visor Inter-product Spread (max − min)",
        xaxis=dict(**GRID), yaxis=dict(title="Max − Min", **GRID),
    )
    return fig


def panel_ratios(price_df: pd.DataFrame) -> go.Figure:
    PANELS = ["PANEL_1X2", "PANEL_2X2", "PANEL_1X4", "PANEL_2X4", "PANEL_4X4"]
    piv = (
        price_df[price_df["product"].isin(PANELS)]
        .pivot_table(index="global_ts", columns="product", values="mid_price")
        .dropna()
    )
    pairs = [
        ("PANEL_2X4", "PANEL_1X4", "#3498db"),
        ("PANEL_4X4", "PANEL_2X2", "#e74c3c"),
        ("PANEL_2X2", "PANEL_1X2", "#2ecc71"),
    ]
    fig = go.Figure()
    for a, b, col in pairs:
        if a in piv.columns and b in piv.columns:
            ratio = piv[a] / piv[b]
            fig.add_trace(go.Scatter(
                x=ratio.index, y=ratio,
                name=f"{a.split('_')[1]} / {b.split('_')[1]}",
                line=dict(color=col, width=1.5),
            ))
    _day_vlines(fig)
    fig.update_layout(
        **DARK, height=200, margin={**MARGIN, "t": 40},
        title="Construction Panel — Size Ratios",
        xaxis=dict(**GRID), yaxis=dict(title="Price Ratio", **GRID),
        legend=dict(orientation="h", y=1.04, x=1, xanchor="right"),
    )
    return fig
