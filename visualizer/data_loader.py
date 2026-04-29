import pandas as pd
import numpy as np
from pathlib import Path
import plotly.express as px

DATA_DIR = Path(__file__).parent.parent / "trading-data" / "ROUND5"
DAYS = [2, 3, 4]
DAY_OFFSET = 1_000_000

CATEGORIES = {
    "Galaxy Sounds Recorders": [
        "GALAXY_SOUNDS_DARK_MATTER", "GALAXY_SOUNDS_BLACK_HOLES",
        "GALAXY_SOUNDS_PLANETARY_RINGS", "GALAXY_SOUNDS_SOLAR_WINDS",
        "GALAXY_SOUNDS_SOLAR_FLAMES",
    ],
    "Vertical Sleeping Pods": [
        "SLEEP_POD_SUEDE", "SLEEP_POD_LAMB_WOOL", "SLEEP_POD_POLYESTER",
        "SLEEP_POD_NYLON", "SLEEP_POD_COTTON",
    ],
    "Organic Microchips": [
        "MICROCHIP_CIRCLE", "MICROCHIP_OVAL", "MICROCHIP_SQUARE",
        "MICROCHIP_RECTANGLE", "MICROCHIP_TRIANGLE",
    ],
    "Purification Pebbles": [
        "PEBBLES_XS", "PEBBLES_S", "PEBBLES_M", "PEBBLES_L", "PEBBLES_XL",
    ],
    "Domestic Robots": [
        "ROBOT_VACUUMING", "ROBOT_MOPPING", "ROBOT_DISHES",
        "ROBOT_LAUNDRY", "ROBOT_IRONING",
    ],
    "UV-Visors": [
        "UV_VISOR_YELLOW", "UV_VISOR_AMBER", "UV_VISOR_ORANGE",
        "UV_VISOR_RED", "UV_VISOR_MAGENTA",
    ],
    "Instant Translators": [
        "TRANSLATOR_SPACE_GRAY", "TRANSLATOR_ASTRO_BLACK",
        "TRANSLATOR_ECLIPSE_CHARCOAL", "TRANSLATOR_GRAPHITE_MIST",
        "TRANSLATOR_VOID_BLUE",
    ],
    "Construction Panels": [
        "PANEL_1X2", "PANEL_2X2", "PANEL_1X4", "PANEL_2X4", "PANEL_4X4",
    ],
    "Liquid Breath Oxygen Shakes": [
        "OXYGEN_SHAKE_MORNING_BREATH", "OXYGEN_SHAKE_EVENING_BREATH",
        "OXYGEN_SHAKE_MINT", "OXYGEN_SHAKE_CHOCOLATE", "OXYGEN_SHAKE_GARLIC",
    ],
    "Protein Snack Packs": [
        "SNACKPACK_CHOCOLATE", "SNACKPACK_VANILLA", "SNACKPACK_PISTACHIO",
        "SNACKPACK_STRAWBERRY", "SNACKPACK_RASPBERRY",
    ],
}

PRODUCT_TO_CAT = {p: cat for cat, prods in CATEGORIES.items() for p in prods}
ALL_PRODUCTS = [p for prods in CATEGORIES.values() for p in prods]

_palette = (
    px.colors.qualitative.Dark24
    + px.colors.qualitative.Light24
    + px.colors.qualitative.Alphabet
)
PRODUCT_COLORS = {p: _palette[i % len(_palette)] for i, p in enumerate(ALL_PRODUCTS)}
CAT_COLORS = {
    cat: _palette[(i * 5) % len(_palette)]
    for i, cat in enumerate(CATEGORIES)
}


def _load_prices() -> pd.DataFrame:
    dfs = []
    for day in DAYS:
        f = DATA_DIR / f"prices_round_5_day_{day}.csv"
        df = pd.read_csv(f, sep=";")
        dfs.append(df)
    df = pd.concat(dfs, ignore_index=True)

    # Vectorised global timestamp
    df["global_ts"] = (df["day"] - 2) * DAY_OFFSET + df["timestamp"]

    # Coerce depth level columns (may be empty strings)
    depth_cols = [
        "bid_price_2", "bid_volume_2", "bid_price_3", "bid_volume_3",
        "ask_price_2", "ask_volume_2", "ask_price_3", "ask_volume_3",
    ]
    for col in depth_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    # Spread (L1)
    df["spread"] = df["ask_price_1"] - df["bid_price_1"]

    # Volume-weighted mid across L1 + L2
    bv1, bv2 = df["bid_volume_1"], df["bid_volume_2"]
    av1, av2 = df["ask_volume_1"], df["ask_volume_2"]
    bp1 = df["bid_price_1"]
    bp2 = df["bid_price_2"].replace(0, np.nan).fillna(df["bid_price_1"])
    ap1 = df["ask_price_1"]
    ap2 = df["ask_price_2"].replace(0, np.nan).fillna(df["ask_price_1"])

    vwap_bid = (bp1 * bv1 + bp2 * bv2) / (bv1 + bv2).replace(0, np.nan)
    vwap_ask = (ap1 * av1 + ap2 * av2) / (av1 + av2).replace(0, np.nan)
    df["vwap_mid"] = (vwap_bid + vwap_ask) / 2

    # Order book imbalance (L1 + L2)
    total_vol = bv1 + bv2 + av1 + av2
    df["ob_imbalance"] = (bv1 + bv2 - av1 - av2) / total_vol.replace(0, np.nan)

    df["category"] = df["product"].map(PRODUCT_TO_CAT)
    df = df.sort_values(["product", "global_ts"]).reset_index(drop=True)
    return df


def _load_trades(prices_df: pd.DataFrame) -> pd.DataFrame:
    dfs = []
    for day in DAYS:
        f = DATA_DIR / f"trades_round_5_day_{day}.csv"
        tdf = pd.read_csv(f, sep=";")
        tdf = tdf.rename(columns={"symbol": "product"})
        tdf["day"] = day
        tdf = tdf[["day", "timestamp", "product", "price", "quantity"]].copy()
        dfs.append(tdf)
    tdf = pd.concat(dfs, ignore_index=True)
    tdf["global_ts"] = (tdf["day"] - 2) * DAY_OFFSET + tdf["timestamp"]

    # Snap trade timestamp to nearest price tick (step=100) for mid lookup
    tdf["snap_ts"] = (tdf["timestamp"] // 100) * 100

    # Build mid lookup via merge: join trades to prices on (product, day, snap_ts)
    mid_ref = prices_df[["product", "day", "timestamp", "mid_price"]].copy()
    mid_ref = mid_ref.rename(columns={"timestamp": "snap_ts"})
    tdf = tdf.merge(mid_ref, on=["product", "day", "snap_ts"], how="left")

    # Signed flow: +qty above mid (buy aggressor), -qty below mid (sell aggressor)
    tdf["signed_qty"] = np.where(
        tdf["price"] > tdf["mid_price"], tdf["quantity"],
        np.where(tdf["price"] < tdf["mid_price"], -tdf["quantity"], 0),
    )

    tdf = tdf.sort_values(["product", "global_ts"]).reset_index(drop=True)
    return tdf


def _compute_sweep(trades_df: pd.DataFrame) -> pd.DataFrame:
    sweep = (
        trades_df.groupby("global_ts")["product"]
        .nunique()
        .reset_index()
        .rename(columns={"product": "sweep_size"})
    )
    sweep["tier"] = pd.cut(
        sweep["sweep_size"],
        bins=[0, 20, 60, 200],
        labels=["single-category", "multi-category", "market-wide"],
    )
    return sweep


def _compute_delta(trades_df: pd.DataFrame) -> pd.DataFrame:
    groups = []
    for prod, g in trades_df.groupby("product"):
        g = g.sort_values("global_ts").copy()
        g["cum_delta"] = g["signed_qty"].cumsum()
        groups.append(g[["product", "global_ts", "day", "signed_qty", "cum_delta"]])
    return pd.concat(groups, ignore_index=True)


class DataStore:
    def __init__(self):
        print("Loading prices...")
        self.prices = _load_prices()
        print("Loading trades...")
        self.trades = _load_trades(self.prices)
        print("Computing sweep events...")
        self.sweep = _compute_sweep(self.trades)
        print("Computing cumulative delta...")
        self.delta = _compute_delta(self.trades)
        print(f"Ready — {len(self.prices):,} price rows, {len(self.trades):,} trade rows.")

    def px(self, products=None, days=None) -> pd.DataFrame:
        df = self.prices
        if products:
            df = df[df["product"].isin(products)]
        if days:
            df = df[df["day"].isin(days)]
        return df

    def tx(self, products=None, days=None) -> pd.DataFrame:
        df = self.trades
        if products:
            df = df[df["product"].isin(products)]
        if days:
            df = df[df["day"].isin(days)]
        return df

    def dx(self, products=None, days=None) -> pd.DataFrame:
        df = self.delta
        if products:
            df = df[df["product"].isin(products)]
        if days:
            df = df[df["day"].isin(days)]
        return df

    def sw(self, days=None) -> pd.DataFrame:
        df = self.sweep
        if days:
            valid_ts = set()
            for d in days:
                lo = (d - 2) * DAY_OFFSET
                hi = lo + 999_900
                valid_ts.update(df[(df["global_ts"] >= lo) & (df["global_ts"] <= hi)].index)
            df = df.loc[list(valid_ts)]
        return df
