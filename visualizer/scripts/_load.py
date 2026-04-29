"""Minimal shared helpers for the query scripts."""
import os, sys
import pandas as pd

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "trading-data", "ROUND5")
DAYS = [2, 3, 4]

CATEGORIES = {
    "Galaxy Sounds Recorders":      ["GALAXY_SOUNDS_DARK_MATTER","GALAXY_SOUNDS_BLACK_HOLES","GALAXY_SOUNDS_PLANETARY_RINGS","GALAXY_SOUNDS_SOLAR_WINDS","GALAXY_SOUNDS_SOLAR_FLAMES"],
    "Vertical Sleeping Pods":       ["SLEEP_POD_SUEDE","SLEEP_POD_LAMB_WOOL","SLEEP_POD_POLYESTER","SLEEP_POD_NYLON","SLEEP_POD_COTTON"],
    "Organic Microchips":           ["MICROCHIP_CIRCLE","MICROCHIP_OVAL","MICROCHIP_SQUARE","MICROCHIP_RECTANGLE","MICROCHIP_TRIANGLE"],
    "Purification Pebbles":         ["PEBBLES_XS","PEBBLES_S","PEBBLES_M","PEBBLES_L","PEBBLES_XL"],
    "Domestic Robots":              ["ROBOT_VACUUMING","ROBOT_MOPPING","ROBOT_DISHES","ROBOT_LAUNDRY","ROBOT_IRONING"],
    "UV-Visors":                    ["UV_VISOR_YELLOW","UV_VISOR_AMBER","UV_VISOR_ORANGE","UV_VISOR_RED","UV_VISOR_MAGENTA"],
    "Instant Translators":          ["TRANSLATOR_SPACE_GRAY","TRANSLATOR_ASTRO_BLACK","TRANSLATOR_ECLIPSE_CHARCOAL","TRANSLATOR_GRAPHITE_MIST","TRANSLATOR_VOID_BLUE"],
    "Construction Panels":          ["PANEL_1X2","PANEL_2X2","PANEL_1X4","PANEL_2X4","PANEL_4X4"],
    "Liquid Breath Oxygen Shakes":  ["OXYGEN_SHAKE_MORNING_BREATH","OXYGEN_SHAKE_EVENING_BREATH","OXYGEN_SHAKE_MINT","OXYGEN_SHAKE_CHOCOLATE","OXYGEN_SHAKE_GARLIC"],
    "Protein Snack Packs":          ["SNACKPACK_CHOCOLATE","SNACKPACK_VANILLA","SNACKPACK_PISTACHIO","SNACKPACK_STRAWBERRY","SNACKPACK_RASPBERRY"],
}
ALL_PRODUCTS = [p for prods in CATEGORIES.values() for p in prods]
PRODUCT_TO_CAT = {p: c for c, ps in CATEGORIES.items() for p in ps}


def resolve_days(days_arg):
    return [int(d) for d in days_arg] if days_arg else DAYS


def match_category(name):
    for c in CATEGORIES:
        if name.lower() in c.lower():
            return c
    sys.exit(f"Unknown category '{name}'. Run: python scripts/list.py")


def prices(products=None, days=None, cols=None):
    """Read price CSVs, optionally filtered to specific products/days/columns."""
    default_cols = ["day","timestamp","product","bid_price_1","ask_price_1","mid_price"]
    use_cols = cols or default_cols
    days = days or DAYS
    dfs = []
    for d in days:
        path = os.path.join(DATA_DIR, f"prices_round_5_day_{d}.csv")
        df = pd.read_csv(path, sep=";", usecols=lambda c: c in use_cols)
        df["day"] = d
        if products:
            df = df[df["product"].isin(products)]
        dfs.append(df)
    df = pd.concat(dfs, ignore_index=True)
    df["global_ts"] = (df["day"] - 2) * 1_000_000 + df["timestamp"]
    if "bid_price_1" in df and "ask_price_1" in df:
        df["spread"] = df["ask_price_1"] - df["bid_price_1"]
    return df


def trades(products=None, days=None):
    """Read trade CSVs, optionally filtered."""
    days = days or DAYS
    dfs = []
    for d in days:
        path = os.path.join(DATA_DIR, f"trades_round_5_day_{d}.csv")
        df = pd.read_csv(path, sep=";", usecols=["timestamp","symbol","price","quantity"])
        df = df.rename(columns={"symbol": "product"})
        df["day"] = d
        if products:
            df = df[df["product"].isin(products)]
        dfs.append(df)
    df = pd.concat(dfs, ignore_index=True)
    df["global_ts"] = (df["day"] - 2) * 1_000_000 + df["timestamp"]
    return df


def fmt_ts(global_ts):
    d = int(global_ts) // 1_000_000 + 2
    t = int(global_ts) % 1_000_000
    return f"D{d}@{t}"


def table(rows, cols):
    if not rows:
        print("  (no data)")
        return
    widths = {c: max(len(c), max(len(str(r.get(c,""))) for r in rows)) for c in cols}
    print("  ".join(c.ljust(widths[c]) for c in cols))
    print("  ".join("-"*widths[c] for c in cols))
    for row in rows:
        print("  ".join(str(row.get(c,"")).ljust(widths[c]) for c in cols))
