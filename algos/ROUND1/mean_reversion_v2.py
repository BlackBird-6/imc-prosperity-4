import json
from typing import List, Dict
from datamodel import OrderDepth, UserId, TradingState, Order

class Trader:

    def run(self, state: TradingState):
        """
        Takes all buy and sell orders for all symbols as an input,
        and outputs a list of orders to be sent.
        """
        
        print(state.market_trades)

        result = {}
        conversions = 0
        traderData = ""
        
        # Instantly buy and hold up to 80 INTARIAN_PEPPER_ROOT
        pepper = "INTARIAN_PEPPER_ROOT"
        if pepper in state.order_depths:
            pepper_pos = state.position.get(pepper, 0)
            target_buy = 80 - pepper_pos
            if target_buy > 0:
                pepper_depth = state.order_depths[pepper]
                best_pepper_ask = min(pepper_depth.sell_orders.keys()) if len(pepper_depth.sell_orders) > 0 else None
                if best_pepper_ask is not None:
                    # Place buy order safely at the market ask + 50 ticks to bound risk while ensuring fill
                    result[pepper] = [Order(pepper, best_pepper_ask + 50, target_buy)]
                else:
                    result[pepper] = [Order(pepper, 12050, target_buy)]
        
        # We only trade ASH_COATED_OSMIUM in this strategy
        product = "ASH_COATED_OSMIUM"
        
        # Load previous mid-price from traderData (JSON string)
        # Default to 10000.0 if this is the very first iteration
        prev_mid = 10000.0
        if state.traderData:
            try:
                data = json.loads(state.traderData)
                prev_mid = data.get("prev_mid", 10000.0)
            except json.JSONDecodeError:
                pass
        
        if product in state.order_depths:
            order_depth: OrderDepth = state.order_depths[product]
            orders: List[Order] = []
            
            # Position limits and current inventory
            POSITION_LIMIT = 80
            current_position = state.position.get(product, 0)
            
            # 1. Calculate the current mid price
            best_bid = max(order_depth.buy_orders.keys()) if len(order_depth.buy_orders) > 0 else None
            best_ask = min(order_depth.sell_orders.keys()) if len(order_depth.sell_orders) > 0 else None
            
            current_mid = prev_mid
            if best_bid is not None and best_ask is not None:
                current_mid = (best_bid + best_ask) / 2.0
                
            # 2. Base fair value
            # Since the product exhibits NO drift and stays tightly around 10k, we anchor it to 10000.
            base_fair_value = 10000.0
            
            # 3. Short-term momentum skew (mean-reversion exploit)
            # The lag-1 autocorrelation is -0.50. 
            # If price moved up (positive change), it's highly likely to mean-revert down.
            # So if it goes up, we skew our quotes downward to catch the drop.
            price_change = current_mid - prev_mid
            momentum_skew = -price_change * 0.5 
            
            # 4. Inventory risk skew
            # If we are holding a long position (e.g. +40), shift quotes downward
            # This makes us LESS likely to buy more, and MORE likely to sell what we have.
            # We scale the skew based on how close we are to the POSITION_LIMIT.
            inventory_skew = - (current_position / POSITION_LIMIT) * 4.0  # Max skew of 4 ticks
            
            # Combine all signals to find our dynamically adjusted fair value
            adjusted_fair = base_fair_value + momentum_skew + inventory_skew
            
            # 5. Quote generation
            # We target a half-spread of 5 ticks (10 tick total spread). 
            # Bots typically quote a 16-tick spread, so we are aggressive enough to guarantee fills.
            half_spread = 5
            our_bid = int(round(adjusted_fair - half_spread))
            our_ask = int(round(adjusted_fair + half_spread))
            
            # Determine maximum volume we can quote WITHOUT breaching position limits.
            # We quote in blocks of 11 to extract maximum safe volume.
            base_vol = 11
            acceptable_buy_vol = min(base_vol, POSITION_LIMIT - current_position)
            acceptable_sell_vol = min(base_vol, POSITION_LIMIT + current_position)
            
            # Place buy order (positive volume)
            if acceptable_buy_vol > 0:
                orders.append(Order(product, our_bid, acceptable_buy_vol))
                
            # Place sell order (negative volume)
            if acceptable_sell_vol > 0:
                orders.append(Order(product, our_ask, -acceptable_sell_vol))
                
            result[product] = orders
            
            # 6. Save current mid to traderData for the next iteration
            next_state = {"prev_mid": current_mid}
            traderData = json.dumps(next_state)

        return result, conversions, traderData
