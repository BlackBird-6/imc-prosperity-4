from datamodel import OrderDepth, UserId, TradingState, Order
from typing import List
import json

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

        return result, conversions, json.dumps(data)

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
