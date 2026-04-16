from datamodel import OrderDepth, UserId, TradingState, Order
from typing import List
import json

class Logger:
    def __init__(self) -> None:
        self.logs = ""
        self.max_log_length = 3750

    def print(self, *objects, sep=" ", end="\n") -> None:
        self.logs += sep.join(map(str, objects)) + end

    def flush(self, state: TradingState, orders, conversions, trader_data) -> None:
        base_length = len(
            self.to_json([
                self.compress_state(state, ""),
                self.compress_orders(orders),
                conversions,
                "",
                "",
            ])
        )
        max_item_length = (self.max_log_length - base_length) // 3
        print(
            self.to_json([
                self.compress_state(state, self.truncate(state.traderData, max_item_length)),
                self.compress_orders(orders),
                conversions,
                self.truncate(trader_data, max_item_length),
                self.truncate(self.logs, max_item_length),
            ])
        )
        self.logs = ""

    def compress_state(self, state: TradingState, trader_data: str):
        return [
            state.timestamp,
            trader_data,
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


class Trader:

    # ── ASH_COATED_OSMIUM ──────────────────────────────────────────
    ACO          = "ASH_COATED_OSMIUM"
    ACO_FAIR     = 10000.0
    ACO_LIMIT    = 80
    ACO_HALF_SPREAD = 5
    ACO_BASE_VOL = 11

    # ── INTARIAN_PEPPER_ROOT ───────────────────────────────────────
    IPR          = "INTARIAN_PEPPER_ROOT"
    IPR_LIMIT    = 80
    IPR_DRIFT    = 0.001
    IPR_TARGET   = 0.85
    IPR_SANITY   = 10

    def run(self, state: TradingState):
        result = {}
        conversions = 0
        
        # Parse persistent traderData
        data = {}
        if state.traderData:
            try:
                data = json.loads(state.traderData)
            except (json.JSONDecodeError, TypeError):
                data = {}

        # Trade products independently
        if self.ACO in state.order_depths:
            result[self.ACO] = self.trade_aco(state, data)

        if self.IPR in state.order_depths:
            result[self.IPR] = self.trade_ipr(state, data)

        trader_data = json.dumps(data)
        logger.flush(state, result, conversions, trader_data)
        return result, conversions, trader_data

    def trade_aco(self, state: TradingState, data: dict) -> List[Order]:
        """
        Mean-Reversion Market Maker for ASH_COATED_OSMIUM.
        Maintains momentum skew and inventory balancing internally.
        """
        product = self.ACO
        orders: List[Order] = []
        od = state.order_depths[product]
        pos = state.position.get(product, 0)

        prev_mid = data.get("aco_prev_mid", 10000.0)
        
        best_bid = max(od.buy_orders.keys()) if od.buy_orders else None
        best_ask = min(od.sell_orders.keys()) if od.sell_orders else None
        
        current_mid = prev_mid
        if best_bid is not None and best_ask is not None:
            current_mid = (best_bid + best_ask) / 2.0
        
        # Extract prev_mid for momentum calculation
        price_change = current_mid - prev_mid
        momentum_skew = -price_change * 0.5 
        
        # Inventory risk skew
        inventory_skew = -(pos / self.ACO_LIMIT) * 4.0
        
        adjusted_fair = self.ACO_FAIR + momentum_skew + inventory_skew
        
        our_bid = int(round(adjusted_fair - self.ACO_HALF_SPREAD))
        our_ask = int(round(adjusted_fair + self.ACO_HALF_SPREAD))
        
        # Quoting base blocks
        acc_buy_vol = min(self.ACO_BASE_VOL, self.ACO_LIMIT - pos)
        acc_sell_vol = min(self.ACO_BASE_VOL, self.ACO_LIMIT + pos)
        
        if acc_buy_vol > 0:
            orders.append(Order(product, our_bid, acc_buy_vol))
        if acc_sell_vol > 0:
            orders.append(Order(product, our_ask, -acc_sell_vol))
            
        data["aco_prev_mid"] = current_mid
        
        return orders

    def trade_ipr(self, state: TradingState, data: dict) -> List[Order]:
        """
        Drift-Capture Strategy for INTARIAN_PEPPER_ROOT.
        Legs into long positions securely, while market-making the spikes.
        """
        product = self.IPR
        orders: List[Order] = []
        od = state.order_depths[product]
        pos = state.position.get(product, 0)

        if not od.buy_orders or not od.sell_orders:
            return orders

        limit  = self.IPR_LIMIT
        target = int(limit * self.IPR_TARGET)  # ~72 target inventory

        mid = self._wall_mid(od)

        # Baseline alignment for drift calculation
        if "ipr_base" not in data:
            data["ipr_base"] = mid
            data["ipr_ts0"]  = state.timestamp

        # Linear drift projection
        formula = data["ipr_base"] + self.IPR_DRIFT * (state.timestamp - data["ipr_ts0"])

        # Sanity checking to avoid extreme divergence
        if abs(formula - mid) > self.IPR_SANITY:
            data["ipr_base"] = mid
            data["ipr_ts0"]  = state.timestamp
            fair = round(mid)
        else:
            fair = round(formula)

        buy_cap  = limit - pos
        sell_cap = limit + pos
        accumulating = pos < target

        # ── Buy only — never sell IPR ───────────────────────────────
        buy_threshold = fair + 8 if accumulating else fair + 1

        for price in sorted(od.sell_orders):
            if price <= buy_threshold and buy_cap > 0:
                vol = min(abs(od.sell_orders[price]), buy_cap)
                orders.append(Order(product, price, vol))
                buy_cap -= vol
                pos += vol

        # Phase 2: Passive bid to catch any remaining fills.
        # No ask posted — we never want to sell.
        if buy_cap > 0:
            orders.append(Order(product, int(fair + 1), buy_cap))

        return orders

    @staticmethod
    def _wall_mid(od: OrderDepth) -> float:
        """Average of the largest-volume price level on each side."""
        wall_bid = max(od.buy_orders,  key=lambda p: od.buy_orders[p])
        wall_ask = max(od.sell_orders, key=lambda p: abs(od.sell_orders[p]))
        return (wall_bid + wall_ask) / 2
