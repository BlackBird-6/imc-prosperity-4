"""
Round 1 — v6
============
Based on patterns from top-finishing Prosperity 2/3 teams (chrispyroberts,
ericcccsliu/Linear Utility, pe049395, jmerle, etc.).

ASH_COATED_OSMIUM (ACO):
    Hard fair value = 10,000 (product is perfectly mean-reverting, drift ≈ 0).
    NPC quotes ±8 from mid (L1 spread = 16 ticks).

    Passive market making (grid-search calibrated):

    • Optimal spread = ±5 ticks from adjusted_fair.
      Grid-search over spread ∈ {2…8} × vol ∈ {8,11,15,20,30} on 3 days of
      real historical data confirmed spread=5 maximises E[edge × fill_rate]
      given NPC L1 depth ≈ 11 units and market-trade size distribution.
    • Volume = 15 units per side (marginal improvement over 11).
    • adjusted_fair = FAIR + momentum_skew + inventory_skew
        momentum_skew  = –Δmid × 0.5   (contrarian: fade the last move)
        inventory_skew = –(pos/LIMIT)×4 (shift quotes toward zero inventory)
    • Backtester fills depth orders at the depth-side price (price improvement),
      so a passive bid at `our_bid` already captures any depth ask ≤ our_bid;
      no separate aggressive-take phase is needed for depth matching.
    • For market-trade matching, fills happen at our order price — the ±5
      spread is the tuned level that maximises (price_edge × fill_probability).

INTARIAN_PEPPER_ROOT (IPR):
    Drift = exactly +1,000 per day (+1 tick per timestamp).
    Every unit held from start of a day earns ~1,000 regardless of entry price.

    Strategy: fill position limit (80) as fast as possible, never sell.
    Sweep the entire ask side each tick; leave an aggressive resting bid
    1 tick above best ask to catch any remaining depth immediately.
"""

from datamodel import OrderDepth, TradingState, Order
from typing import List
import json


# ── Visualizer-compatible logger ──────────────────────────────────────────────
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
        return [[t.symbol, t.price, t.quantity, t.buyer, t.seller, t.timestamp]
                for arr in trades.values() for t in arr]

    def compress_observations(self, observations):
        co = {}
        for product, obs in observations.conversionObservations.items():
            co[product] = [obs.bidPrice, obs.askPrice, obs.transportFees,
                           obs.exportTariff, obs.importTariff, obs.sugarPrice, obs.sunlightIndex]
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


# ── Trader ────────────────────────────────────────────────────────────────────
class Trader:

    # ── ASH_COATED_OSMIUM ──────────────────────────────────────────
    ACO             = "ASH_COATED_OSMIUM"
    ACO_FAIR        = 10_000
    ACO_LIMIT       = 80
    # Grid-search optimum on 3 days of historical data:
    #   spread=5, vol=15 → ACO PnL 34,140  (vs spread=2 → 23k, spread=8 → 31k)
    ACO_HALF_SPREAD = 5
    ACO_BASE_VOL    = 15

    # ── INTARIAN_PEPPER_ROOT ───────────────────────────────────────
    IPR       = "INTARIAN_PEPPER_ROOT"
    IPR_LIMIT = 80

    def run(self, state: TradingState):
        result = {}
        conversions = 0

        data: dict = {}
        if state.traderData:
            try:
                data = json.loads(state.traderData)
            except (json.JSONDecodeError, TypeError):
                data = {}

        if self.ACO in state.order_depths:
            result[self.ACO] = self._trade_aco(state, data)

        if self.IPR in state.order_depths:
            result[self.IPR] = self._trade_ipr(state)

        trader_data = json.dumps(data)
        logger.flush(state, result, conversions, trader_data)
        return result, conversions, trader_data

    # ── ACO: two-phase market maker ────────────────────────────────
    def _trade_aco(self, state: TradingState, data: dict) -> List[Order]:
        FAIR        = self.ACO_FAIR         # 10_000
        LIMIT       = self.ACO_LIMIT        # 80
        HALF_SPREAD = self.ACO_HALF_SPREAD  # 5
        BASE_VOL    = self.ACO_BASE_VOL     # 15

        product = self.ACO
        od      = state.order_depths[product]
        pos     = state.position.get(product, 0)
        orders: List[Order] = []

        buy_cap  = LIMIT - pos
        sell_cap = LIMIT + pos

        # ── Compute adjusted fair value ────────────────────────────
        # Use mid-price if both sides are present; else keep previous.
        prev_mid = data.get("aco_prev_mid", float(FAIR))

        best_bid = max(od.buy_orders)  if od.buy_orders  else None
        best_ask = min(od.sell_orders) if od.sell_orders else None

        # Only update mid when both sides are present (mirrors v5 behaviour).
        # One-sided ticks keep prev_mid so momentum_skew is not polluted.
        current_mid = prev_mid
        if best_bid is not None and best_ask is not None:
            current_mid = (best_bid + best_ask) / 2.0

        # Contrarian momentum skew: fade the last move
        momentum_skew  = -(current_mid - prev_mid) * 0.5
        # Inventory skew: shift both quotes toward zero inventory
        inventory_skew = -(pos / LIMIT) * 4.0

        adjusted_fair = FAIR + momentum_skew + inventory_skew
        data["aco_prev_mid"] = current_mid

        our_bid = int(round(adjusted_fair - HALF_SPREAD))
        our_ask = int(round(adjusted_fair + HALF_SPREAD))

        # ── Passive quoting ────────────────────────────────────────
        # The backtester fills depth orders at the depth-side price
        # (price improvement), so a passive bid at `our_bid` already
        # captures any depth ask ≤ our_bid at that ask's price.
        # No separate "aggressive take" phase needed — it's equivalent.
        bid_vol  = min(BASE_VOL, buy_cap)
        ask_vol  = min(BASE_VOL, sell_cap)

        if bid_vol > 0:
            orders.append(Order(product, our_bid, bid_vol))

        if ask_vol > 0:
            orders.append(Order(product, our_ask, -ask_vol))

        return orders

    # ── IPR: drift-capture (buy and hold) ─────────────────────────
    def _trade_ipr(self, state: TradingState) -> List[Order]:
        """
        Drift = +1,000/day.  Optimal strategy: maximise time at position limit.
        Sweep the full ask side every tick, plus an aggressive resting bid.
        Never sell.
        """
        LIMIT = self.IPR_LIMIT  # 80

        product = self.IPR
        od      = state.order_depths[product]
        pos     = state.position.get(product, 0)
        orders: List[Order] = []

        buy_cap = LIMIT - pos
        if buy_cap <= 0 or not od.sell_orders:
            return orders

        best_ask = min(od.sell_orders)

        # Sweep entire ask side
        for ask_price in sorted(od.sell_orders):
            if buy_cap <= 0:
                break
            qty = min(-od.sell_orders[ask_price], buy_cap)
            orders.append(Order(product, ask_price, qty))
            buy_cap -= qty

        # Aggressive resting bid: sits 1 above best ask so any
        # newly posted ask is filled immediately on the next tick.
        if buy_cap > 0:
            orders.append(Order(product, best_ask + 1, buy_cap))

        return orders
