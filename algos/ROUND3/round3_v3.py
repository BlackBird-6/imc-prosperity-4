"""
Round 3 v3
============
Products
--------
HYDROGEL_PACK (HP)
    Mean-reverting around 10,000. Market-make with a conservative half-spread
    and a small contrarian skew from the last mid-price move.

VELVETFRUIT_EXTRACT (VEV)
    Underlying for all vouchers. EMA is used as the option pricing reference.
    Direct VEV trading is disabled.

VEV_4000 ... VEV_5500   (ITM / ATM / near-OTM European call options)
    Fair value from Black-Scholes with sigma = 0.31.
    Strategy: passive market-making around BS fair plus aggressive taking when
    a bot quote is sufficiently mispriced. The take threshold tightens only
    when VEV is below its EMA, a state-based signal.

Skipped
-------
VEV_6000, VEV_6500 are far OTM in the data and add noise.

Time-to-expiry (TTE)
--------------------
TTE_START is calibrated from the live option surface on the first tick, using
real VEV spot rather than EMA to avoid corrupting the inversion.
Within a day TTE decreases linearly from TTE_START to TTE_START - 1.

Position limits (from problem statement)
-----------------------------------------
HYDROGEL_PACK          : 200
VELVETFRUIT_EXTRACT    : 200
VEV_* (each voucher)   : 300
"""

import json
import math
from typing import List, Optional

from datamodel import Order, TradingState


def _tte_years(timestamp: int, tte_start: float) -> float:
    """Time to expiry in years.  tte_start is days remaining at day open."""
    frac = timestamp / 999_900
    return max(tte_start - frac, 1e-6) / 365.0


def _infer_tte_start(vev_mid: float, order_depths: dict, vouchers: dict, sigma: float) -> float:
    """Estimate TTE_START (days) from observed option mids via BS inversion.

    Only uses options where time value >= 20% of mid — deep ITM options have
    negligible time value so their TTE estimate is unreliable.
    Returns the median estimate clamped to [2, 7], falling back to 5.0.
    Must be called with real VEV spot (not EMA) to avoid bias from the default.
    """
    estimates = []
    for prod, K in vouchers.items():
        od = order_depths.get(prod)
        if od is None or not od.buy_orders or not od.sell_orders:
            continue
        mid = (max(od.buy_orders) + min(od.sell_orders)) / 2.0
        if mid <= 0:
            continue
        intrinsic = max(vev_mid - K, 0.0)
        time_value = mid - intrinsic
        if time_value < 5.0 or time_value / mid < 0.20:
            continue
        lo, hi = 1.0 / 365.0, 8.0 / 365.0
        for _ in range(50):
            t = (lo + hi) / 2.0
            if _bs_call(vev_mid, K, t, sigma) < mid:
                lo = t
            else:
                hi = t
        estimates.append((lo + hi) / 2.0 * 365.0)
    if not estimates:
        return 5.0
    estimates.sort()
    return max(2.0, min(7.0, estimates[len(estimates) // 2]))


# ── Black-Scholes helpers ──────────────────────────────────────────────────────
def _norm_cdf(x: float) -> float:
    """Abramowitz & Stegun approximation; max error 7.5e-8."""
    t = 1.0 / (1.0 + 0.2316419 * abs(x))
    poly = t * (
        0.319381530
        + t * (-0.356563782
               + t * (1.781477937
                      + t * (-1.821255978
                             + t * 1.330274429)))
    )
    p = 1.0 - (1.0 / math.sqrt(2.0 * math.pi)) * math.exp(-0.5 * x * x) * poly
    return p if x >= 0.0 else 1.0 - p


def _bs_call(S: float, K: float, T: float, sigma: float) -> float:
    """European call price (r = 0)."""
    if T <= 0.0:
        return max(S - K, 0.0)
    sq = math.sqrt(T)
    d1 = (math.log(S / K) + 0.5 * sigma * sigma * T) / (sigma * sq)
    d2 = d1 - sigma * sq
    return S * _norm_cdf(d1) - K * _norm_cdf(d2)


# ── Visualizer-compatible logger ───────────────────────────────────────────────
class Logger:
    def __init__(self) -> None:
        self.logs = ""
        self.max_log_length = 3750

    def print(self, *objects, sep=" ", end="\n") -> None:
        self.logs += sep.join(map(str, objects)) + end

    def flush(self, state: TradingState, orders, conversions, trader_data) -> None:
        base_length = len(self.to_json([
            self.compress_state(state, ""),
            self.compress_orders(orders),
            conversions, "", "",
        ]))
        max_item_length = (self.max_log_length - base_length) // 3
        print(self.to_json([
            self.compress_state(state, self.truncate(state.traderData, max_item_length)),
            self.compress_orders(orders),
            conversions,
            self.truncate(trader_data, max_item_length),
            self.truncate(self.logs, max_item_length),
        ]))
        self.logs = ""

    def compress_state(self, state: TradingState, trader_data: str):
        return [
            state.timestamp, trader_data,
            self.compress_listings(state.listings),
            self.compress_order_depths(state.order_depths),
            self.compress_trades(state.own_trades),
            self.compress_trades(state.market_trades),
            state.position,
            self.compress_observations(state.observations),
        ]

    def compress_listings(self, listings):
        return [[l.symbol, l.product, l.denomination] for l in listings.values()]

    def compress_order_depths(self, order_depths):
        return {s: [od.buy_orders, od.sell_orders] for s, od in order_depths.items()}

    def compress_trades(self, trades):
        return [
            [t.symbol, t.price, t.quantity, t.buyer, t.seller, t.timestamp]
            for arr in trades.values() for t in arr
        ]

    def compress_observations(self, observations):
        co = {}
        for product, obs in observations.conversionObservations.items():
            co[product] = [
                obs.bidPrice, obs.askPrice, obs.transportFees,
                obs.exportTariff, obs.importTariff, obs.sugarPrice, obs.sunlightIndex,
            ]
        return [observations.plainValueObservations, co]

    def compress_orders(self, orders):
        return [[o.symbol, o.price, o.quantity] for arr in orders.values() for o in arr]

    def to_json(self, value) -> str:
        return json.dumps(value, cls=ProsperityEncoder, separators=(",", ":"))

    def truncate(self, value: str, max_length: int) -> str:
        if len(value) <= max_length:
            return value
        return value[:max_length - 3] + "..."


class ProsperityEncoder(json.JSONEncoder):
    def default(self, obj):
        if hasattr(obj, "__dict__"):
            return obj.__dict__
        return super().default(obj)


logger = Logger()


# ── Trader ─────────────────────────────────────────────────────────────────────
class Trader:

    # ── HYDROGEL_PACK ──────────────────────────────────────────────────────────
    HP             = "HYDROGEL_PACK"
    HP_FAIR        = 10_000
    HP_LIMIT       = 200
    HP_HALF_SPREAD = 15       # ±15 ticks; grid-search optimum on 3 days R3 data
    HP_BASE_VOL    = 6        # units per side

    # ── VELVETFRUIT_EXTRACT (underlying) ──────────────────────────────────────
    VEV               = "VELVETFRUIT_EXTRACT"
    VEV_EMA_ALPHA     = 0.05  # EMA smoothing coefficient

    # ── Options (VEV_4000 … VEV_5500) ─────────────────────────────────────────
    # Trade all strikes where the BS model IV ≈ market IV (~31%)
    VOUCHERS: dict = {
        "VEV_4000": 4000,
        "VEV_4500": 4500,
        "VEV_5000": 5000,
        "VEV_5100": 5100,
        "VEV_5200": 5200,
        "VEV_5300": 5300,
        "VEV_5400": 5400,
        "VEV_5500": 5500,
    }
    OPT_LIMIT       = 300
    OPT_SIGMA       = 0.31    # fitted to historical IV; TTE=5 overestimate creates long-option bias that captures VEV upward drift
    OPT_HALF_SPREAD = 1       # ±1 tick: tightest viable spread (grid-searched)
    OPT_BASE_VOL    = 20      # units per side for passive quoting
    OPT_TAKE_EDGE   = 7       # conservative edge outside the VEV-below-EMA regime
    OPT_FAST_EDGE   = 4       # used when VEV is below EMA and mean-reversion edge is favorable
    OPT_FAST_EMA_GAP = 2.0    # state-based gate, not a timestamp/day rule
    OPT_INV_SKEW    = 3       # max inventory skew ticks at full position

    # ── run ───────────────────────────────────────────────────────────────────
    def run(self, state: TradingState):
        result: dict = {}
        conversions = 0

        data: dict = {}
        if state.traderData:
            try:
                data = json.loads(state.traderData)
            except Exception:
                data = {}

        # ── VEV EMA reference price ────────────────────────────────────────────
        vev_od = state.order_depths.get(self.VEV)
        vev_mid = self._mid(vev_od)
        if vev_mid is not None:
            prev_ema = data.get("vev_ema", vev_mid)
            data["vev_ema"] = prev_ema + self.VEV_EMA_ALPHA * (vev_mid - prev_ema)
        vev_ref: float = data.get("vev_ema", 5_250.0)
        opt_take_edge = self.OPT_TAKE_EDGE
        if vev_mid is not None and vev_mid <= data["vev_ema"] - self.OPT_FAST_EMA_GAP:
            opt_take_edge = self.OPT_FAST_EDGE

        # Calibrate TTE_START once on the first tick using real spot (not EMA).
        # EMA defaults to 5250 before first update which corrupts BS inversion.
        if "tte_start" not in data and vev_mid is not None:
            data["tte_start"] = _infer_tte_start(
                vev_mid, state.order_depths, self.VOUCHERS, self.OPT_SIGMA
            )
        tte_start: float = data.get("tte_start", 5.0)

        T: float = _tte_years(state.timestamp, tte_start)

        # ── Options ───────────────────────────────────────────────────────────
        for prod, K in self.VOUCHERS.items():
            if prod in state.order_depths:
                orders = self._trade_option(state, prod, K, vev_ref, T, opt_take_edge)
                result[prod] = orders

        # ── VEV: delta hedge disabled ─────────────────────────────────────────
        # Delta hedging via VEV incurs ~5-tick bid-ask spread costs per round trip.
        # Options market-making is approximately delta-neutral in aggregate,
        # so the hedge cost exceeds the benefit.  VEV trading is omitted in v1.

        # ── HYDROGEL_PACK ──────────────────────────────────────────────────────
        if self.HP in state.order_depths:
            result[self.HP] = self._trade_hp(state, data)

        trader_data = json.dumps(data)
        logger.flush(state, result, conversions, trader_data)
        return result, conversions, trader_data

    # ── HYDROGEL_PACK market maker ─────────────────────────────────────────────
    def _trade_hp(self, state: TradingState, data: dict) -> List[Order]:
        od    = state.order_depths[self.HP]
        pos   = state.position.get(self.HP, 0)
        FAIR  = self.HP_FAIR
        LIMIT = self.HP_LIMIT

        best_bid = max(od.buy_orders)  if od.buy_orders  else None
        best_ask = min(od.sell_orders) if od.sell_orders else None

        prev_mid = data.get("hp_mid", float(FAIR))
        cur_mid  = (best_bid + best_ask) / 2.0 if (best_bid and best_ask) else prev_mid
        data["hp_mid"] = cur_mid

        # Contrarian momentum: fade the last mid-price move
        momentum_skew  = -(cur_mid - prev_mid) * 0.35
        # Inventory skew: push both quotes toward zero position
        inventory_skew = -(pos / LIMIT) * 4.0

        adj_fair = FAIR + momentum_skew + inventory_skew
        bid = int(round(adj_fair - self.HP_HALF_SPREAD))
        ask = int(round(adj_fair + self.HP_HALF_SPREAD))

        orders: List[Order] = []
        buy_cap  = LIMIT - pos
        sell_cap = LIMIT + pos

        if buy_cap > 0:
            orders.append(Order(self.HP, bid,  min(self.HP_BASE_VOL, buy_cap)))
        if sell_cap > 0:
            orders.append(Order(self.HP, ask, -min(self.HP_BASE_VOL, sell_cap)))
        return orders

    # ── Options market maker ───────────────────────────────────────────────────
    def _trade_option(
        self,
        state: TradingState,
        prod: str,
        K: int,
        S: float,
        T: float,
        take_edge: int,
    ) -> List[Order]:
        """
        Return option orders for one voucher.
        """
        od    = state.order_depths[prod]
        pos   = state.position.get(prod, 0)
        LIMIT = self.OPT_LIMIT

        fair  = _bs_call(S, K, T, self.OPT_SIGMA)

        orders: List[Order] = []
        buy_cap  = LIMIT - pos
        sell_cap = LIMIT + pos

        best_bid = max(od.buy_orders)  if od.buy_orders  else None
        best_ask = min(od.sell_orders) if od.sell_orders else None

        # ── Phase 1: aggressive take on large mispricing ───────────────────────
        if best_ask is not None and best_ask < fair - take_edge and buy_cap > 0:
            qty = min(buy_cap, -od.sell_orders[best_ask])
            if qty > 0:
                orders.append(Order(prod, best_ask, qty))
                buy_cap -= qty

        if best_bid is not None and best_bid > fair + take_edge and sell_cap > 0:
            qty = min(sell_cap, od.buy_orders[best_bid])
            if qty > 0:
                orders.append(Order(prod, best_bid, -qty))
                sell_cap -= qty

        # ── Phase 2: passive market-making around BS fair value ────────────────
        # Inventory skew: if long options, lower quotes to sell faster; vice versa
        inv_skew = -(pos / LIMIT) * self.OPT_INV_SKEW

        our_bid = int(round(fair - self.OPT_HALF_SPREAD + inv_skew))
        our_ask = int(round(fair + self.OPT_HALF_SPREAD + inv_skew))

        # Never cross the existing market (would be an immediate fill at a
        # price we didn't intend; aggressive takes are handled in phase 1)
        if best_ask is not None and our_bid >= best_ask:
            our_bid = best_ask - 1
        if best_bid is not None and our_ask <= best_bid:
            our_ask = best_bid + 1
        if our_bid >= our_ask:
            return orders   # spread collapsed; skip passive leg

        if buy_cap > 0:
            orders.append(Order(prod, our_bid,  min(self.OPT_BASE_VOL, buy_cap)))
        if sell_cap > 0:
            orders.append(Order(prod, our_ask, -min(self.OPT_BASE_VOL, sell_cap)))

        return orders

    # ── Utility ───────────────────────────────────────────────────────────────
    @staticmethod
    def _mid(od) -> Optional[float]:
        if od is None or not od.buy_orders or not od.sell_orders:
            return None
        return (max(od.buy_orders) + min(od.sell_orders)) / 2.0
