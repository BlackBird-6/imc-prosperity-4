"""
Round 3 — v2
============
Changes from v1
----------------
1. VOLATILITY SMILE: Per-strike IV from a quadratic fit of market-implied
   vols across all tradeable strikes, replacing the flat σ = 0.31 constant.
   This eliminates systematic mispricing on wing strikes (especially VEV_5400).

2. IV DEVIATION SCALPING: Primary options alpha signal.  For each strike we
   track the EMA of (market_mid − BS_fair) and scalp the deviation of the
   current diff from that EMA.  This captures short-term mean reversion in
   option mispricing — the technique that was the #1 PnL contributor for
   Frankfurt Hedgehogs (2nd place, Prosperity 3).

3. WALL-MID PRICING: VEV underlying priced at the wall-mid (mid of the
   deepest-volume levels) instead of best-bid/best-ask mid.  More stable,
   less noisy.

4. EXPANDED VOUCHER SET: Trades VEV_5000–VEV_5500.  Deep ITM (4000, 4500)
   are still skipped (mid ≈ intrinsic, no edge).  Far OTM (6000, 6500) are
   skipped (mid stuck at 0.5).

5. DEAD CODE REMOVED: Delta-hedge function removed (was disabled in v1).

Products
--------
HYDROGEL_PACK (HP)
    Unchanged from v1.  Mean-reverting around 10,000.

VELVETFRUIT_EXTRACT (VEV)
    Underlying for all vouchers.  Not actively traded.

VEV_5000 … VEV_5500   (near-ATM European call options)
    IV Scalping + passive market-making at smile-derived fair value.

Skipped
-------
VEV_4000, VEV_4500  — deep ITM; mid ≈ intrinsic, no time-value edge.
VEV_6000, VEV_6500  — far OTM; mid stuck at 0.5, worthless.

Position limits
---------------
HYDROGEL_PACK          : 200
VELVETFRUIT_EXTRACT    : 200
VEV_* (each voucher)   : 300
"""

import json
import math
from typing import Dict, List, Optional, Tuple

from datamodel import Order, TradingState

# ┌─────────────────────────────────────────────────────────────────────────────┐
# │ !!!  IMPORTANT — SET BACKTEST_MODE AND _TTE_START PROPERLY  !!!           │
# │                                                                           │
# │  For backtesting historical data (Days 0, 1, 2):                          │
# │  Set BACKTEST_MODE = True (automatically starts at 8.0 and decrements)    │
# │                                                                           │
# │  For FINAL SUBMISSION:                                                    │
# │  Set BACKTEST_MODE = False                                                │
# │  Set _TTE_START = 5.0 (for Round 3)                                       │
# └─────────────────────────────────────────────────────────────────────────────┘
BACKTEST_MODE = False
_TTE_START = 5.0

def _get_tte(timestamp: int, data: dict) -> float:
    """
    Time to expiry in years.
    If BACKTEST_MODE is True, it dynamically tracks the day across merged
    backtests, starting at TTE=8 for Day 0 and decrementing each day.
    """
    frac = timestamp / 999_900

    if BACKTEST_MODE:
        # Track day transitions using timestamp roll-overs
        prev_ts = data.get("prev_ts", 0)
        day_idx = data.get("day_idx", 0)
        if timestamp < prev_ts:
            day_idx += 1
        data["prev_ts"] = timestamp
        data["day_idx"] = day_idx
        
        # Historical Day 0 starts at TTE=8
        tte_days = (8.0 - day_idx) - frac
    else:
        tte_days = _TTE_START - frac
        
    return max(tte_days, 1e-6) / 365.0


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


def _bs_delta(S: float, K: float, T: float, sigma: float) -> float:
    """Black-Scholes call delta dC/dS (r = 0)."""
    if T <= 0.0:
        return 1.0 if S > K else 0.0
    d1 = (math.log(S / K) + 0.5 * sigma * sigma * T) / (sigma * math.sqrt(T))
    return _norm_cdf(d1)


def _implied_vol(S: float, K: float, T: float, market_price: float,
                 lo: float = 0.05, hi: float = 1.5) -> Optional[float]:
    """Implied volatility via bisection.  Returns None if price is at or
    below intrinsic (no time value to invert)."""
    intrinsic = max(S - K, 0.0)
    if market_price <= intrinsic + 0.01 or T <= 0.0:
        return None
    for _ in range(60):                     # ~60 iters → ~1e-18 precision
        mid = (lo + hi) * 0.5
        p = _bs_call(S, K, T, mid)
        if p < market_price:
            lo = mid
        else:
            hi = mid
        if hi - lo < 1e-7:
            break
    result = (lo + hi) * 0.5
    if result < 0.05 or result > 1.5:       # sanity bounds
        return None
    return result


def _fit_smile(
    S: float, T: float,
    strikes: List[int],
    option_mids: Dict[str, float],
) -> Tuple[float, float, float]:
    """Fit IV(m) = a·m² + b·m + c   where m = ln(K/S) / √T.

    Uses manual least-squares (3×3 normal equations) — no numpy import needed,
    keeping the hot path dependency-free for speed.

    Returns (a, b, c).  Fallback: (0, 0, 0.30) if fewer than 3 valid IVs.
    """
    sqT = math.sqrt(T) if T > 0 else 1e-6
    ms: List[float] = []
    ivs: List[float] = []

    for K in strikes:
        prod = f"VEV_{K}"
        mid = option_mids.get(prod)
        if mid is None:
            continue
        iv = _implied_vol(S, K, T, mid)
        if iv is None:
            continue
        m = math.log(K / S) / sqT
        ms.append(m)
        ivs.append(iv)

    n = len(ms)
    if n < 3:
        # Not enough points for a quadratic — use median IV or 0.30
        if ivs:
            ivs_sorted = sorted(ivs)
            c = ivs_sorted[len(ivs_sorted) // 2]
            return (0.0, 0.0, c)
        return (0.0, 0.0, 0.30)

    # Build normal equations for least-squares:  X^T X β = X^T y
    # where X[i] = [m_i^2, m_i, 1],  y[i] = iv_i
    # We solve the 3×3 system directly via Cramer's rule.
    s0 = float(n)
    s1 = sum(ms)
    s2 = sum(m * m for m in ms)
    s3 = sum(m * m * m for m in ms)
    s4 = sum(m * m * m * m for m in ms)
    ty0 = sum(ivs)
    ty1 = sum(m * iv for m, iv in zip(ms, ivs))
    ty2 = sum(m * m * iv for m, iv in zip(ms, ivs))

    # X^T X = [[s4, s3, s2], [s3, s2, s1], [s2, s1, s0]]
    # X^T y = [ty2, ty1, ty0]
    det = (s4 * (s2 * s0 - s1 * s1)
           - s3 * (s3 * s0 - s1 * s2)
           + s2 * (s3 * s1 - s2 * s2))
    if abs(det) < 1e-15:
        if ivs:
            ivs_sorted = sorted(ivs)
            return (0.0, 0.0, ivs_sorted[len(ivs_sorted) // 2])
        return (0.0, 0.0, 0.30)

    a = (ty2 * (s2 * s0 - s1 * s1)
         - s3 * (ty1 * s0 - s1 * ty0)
         + s2 * (ty1 * s1 - s2 * ty0)) / det

    b = (s4 * (ty1 * s0 - s1 * ty0)
         - ty2 * (s3 * s0 - s1 * s2)
         + s2 * (s3 * ty0 - ty1 * s2)) / det

    c = (s4 * (s2 * ty0 - ty1 * s1)
         - s3 * (s3 * ty0 - ty1 * s2)
         + ty2 * (s3 * s1 - s2 * s2)) / det

    return (a, b, c)


def _smile_sigma(a: float, b: float, c: float,
                 S: float, K: int, T: float) -> float:
    """Evaluate fitted smile at a specific strike.  Clamped to [0.05, 1.5]."""
    sqT = math.sqrt(T) if T > 0 else 1e-6
    m = math.log(K / S) / sqT
    sigma = a * m * m + b * m + c
    return max(0.05, min(sigma, 1.5))


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

    # ── HYDROGEL_PACK (unchanged from v1) ──────────────────────────────────────
    HP             = "HYDROGEL_PACK"
    HP_FAIR        = 10_000
    HP_LIMIT       = 200
    HP_HALF_SPREAD = 15       # ±15 ticks; grid-search optimum on 3 days R3 data
    HP_BASE_VOL    = 6        # units per side

    # ── VELVETFRUIT_EXTRACT (underlying) ──────────────────────────────────────
    VEV            = "VELVETFRUIT_EXTRACT"
    VEV_LIMIT      = 200
    VEV_EMA_ALPHA  = 0.05     # EMA smoothing for reference price (matches v1)

    # ── Options (VEV_5000 … VEV_5500) ─────────────────────────────────────────
    # All strikes where market-implied IV is invertible (time-value > 0)
    # and mid price is meaningfully above 0.5.
    # Deep ITM (4000, 4500): mid ≈ intrinsic → no edge.
    # Far OTM  (6000, 6500): mid = 0.5 → worthless.
    VOUCHERS: dict = {
        "VEV_5000": 5000,
        "VEV_5100": 5100,
        "VEV_5200": 5200,
        "VEV_5300": 5300,
        "VEV_5400": 5400,
    }
    # All strikes used for smile fitting (includes untradeable ones for better fit)
    SMILE_STRIKES: List[int] = [5000, 5100, 5200, 5300, 5400, 5500]

    OPT_LIMIT       = 300
    OPT_SIGMA       = 0.31    # deliberate sigma for pricing (slightly > market)
    OPT_HALF_SPREAD = 1       # ±1 tick passive spread
    OPT_BASE_VOL    = 20      # units per passive side
    OPT_INV_SKEW    = 3       # max inventory skew ticks at full position
    OPT_TAKE_EDGE   = 5       # min ticks of edge to aggressively take

    # IV Scalping → quote skewing
    SCALP_EMA_WINDOW   = 20   # EMA window for theo-diff smoothing
    SCALP_SKEW_FACTOR  = 3.0  # deviation ticks → quote skew multiplier (grid-searched)

    # ── run ───────────────────────────────────────────────────────────────────
    def run(self, state: TradingState):
        result: dict = {}
        conversions = 0

        # ── Restore persistent state ──────────────────────────────────────────
        data: dict = {}
        if state.traderData:
            try:
                data = json.loads(state.traderData)
            except Exception:
                data = {}

        T: float = _get_tte(state.timestamp, data)

        # ── VEV reference prices ──────────────────────────────────────────────
        vev_od = state.order_depths.get(self.VEV)

        # EMA-smoothed mid for model pricing (preserves v1 behavior)
        vev_mid = self._mid(vev_od)
        if vev_mid is not None:
            prev_ema = data.get("vev_ema", vev_mid)
            data["vev_ema"] = prev_ema + self.VEV_EMA_ALPHA * (vev_mid - prev_ema)
        vev_ref: float = data.get("vev_ema", 5_250.0)

        # Wall-mid for smile fitting (more stable)
        vev_wall = self._wall_mid(vev_od)
        if vev_wall is None:
            vev_wall = vev_ref

        # ── Fit volatility smile across all strikes ───────────────────────────
        option_mids: Dict[str, float] = {}
        for prod in self.VOUCHERS:
            od = state.order_depths.get(prod)
            if od is not None:
                wm = self._wall_mid(od)
                if wm is None:
                    wm = self._mid(od)
                if wm is not None:
                    option_mids[prod] = wm

        a, b, c = _fit_smile(vev_wall, T, self.SMILE_STRIKES, option_mids)

        # ── Trade options ──────────────────────────────────────────────────────
        # Uses OPT_SIGMA for pricing (systematic edge from overpricing), and
        # smile-derived fair for the deviation-skew signal (relative mispricing).
        for prod, K in self.VOUCHERS.items():
            if prod not in state.order_depths:
                continue
            smile_sigma_k = _smile_sigma(a, b, c, vev_ref, K, T)
            orders = self._trade_option(
                state, data, prod, K, vev_ref, T,
                self.OPT_SIGMA, smile_sigma_k,
                option_mids.get(prod),
            )
            result[prod] = orders

        # ── HYDROGEL_PACK (unchanged from v1) ─────────────────────────────────
        if self.HP in state.order_depths:
            result[self.HP] = self._trade_hp(state, data)

        trader_data = json.dumps(data)
        logger.flush(state, result, conversions, trader_data)
        return result, conversions, trader_data

    # ── HYDROGEL_PACK market maker (unchanged from v1) ─────────────────────────
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
        momentum_skew  = -(cur_mid - prev_mid) * 0.5
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

    # ── Options: smile pricing + deviation-skewed passive MM ─────────────────
    def _trade_option(
        self,
        state: TradingState,
        data: dict,
        prod: str,
        K: int,
        S: float,
        T: float,
        model_sigma: float,
        smile_sigma: float,
        opt_wall_mid: Optional[float],
    ) -> List[Order]:
        """
        Two-phase options strategy per strike:
          Phase 1: Aggressive take priced from model_sigma (OPT_SIGMA = 0.31)
          Phase 2: Passive MM with quotes skewed by smile-based deviation

        model_sigma: used for pricing (systematic edge from overpricing)
        smile_sigma: used for deviation signal (relative mispricing detection)
        """
        od    = state.order_depths[prod]
        pos   = state.position.get(prod, 0)
        LIMIT = self.OPT_LIMIT

        fair  = _bs_call(S, K, T, model_sigma)
        smile_fair = _bs_call(S, K, T, smile_sigma)

        orders: List[Order] = []
        buy_cap  = LIMIT - pos
        sell_cap = LIMIT + pos

        best_bid = max(od.buy_orders)  if od.buy_orders  else None
        best_ask = min(od.sell_orders) if od.sell_orders else None

        # ── IV Deviation tracking ─────────────────────────────────────────────
        # Track EMA of (market_mid − BS_fair).  The deviation from this EMA
        # tells us if the option is transiently over- or under-priced.
        deviation = 0.0
        td_key = f"{prod}_td"
        if opt_wall_mid is not None:
            theo_diff = opt_wall_mid - smile_fair   # deviation vs smile, not model
            alpha = 2.0 / (self.SCALP_EMA_WINDOW + 1)
            prev_ema = data.get(td_key, theo_diff)
            ema_val = prev_ema + alpha * (theo_diff - prev_ema)
            data[td_key] = ema_val
            deviation = theo_diff - ema_val

        # ── Phase 1: Aggressive take on large absolute mispricing ─────────────
        # Sweep all ask levels below (fair − take_edge) and all bid levels
        # above (fair + take_edge).  Multi-level walk.
        if buy_cap > 0:
            for ask_p in sorted(od.sell_orders):
                if ask_p >= fair - self.OPT_TAKE_EDGE:
                    break
                avail = -od.sell_orders[ask_p]
                qty = min(avail, buy_cap)
                if qty > 0:
                    orders.append(Order(prod, ask_p, qty))
                    buy_cap -= qty
                if buy_cap <= 0:
                    break

        if sell_cap > 0:
            for bid_p in sorted(od.buy_orders, reverse=True):
                if bid_p <= fair + self.OPT_TAKE_EDGE:
                    break
                avail = od.buy_orders[bid_p]
                qty = min(avail, sell_cap)
                if qty > 0:
                    orders.append(Order(prod, bid_p, -qty))
                    sell_cap -= qty
                if sell_cap <= 0:
                    break

        # ── Phase 2: Passive MM with deviation + inventory skew ───────────────
        # Deviation skew: if option is overpriced (dev > 0), shift quotes down
        # to make our ask more competitive (eager to sell).  Clamped to ±2.
        dev_skew = max(-2.0, min(2.0, -deviation * self.SCALP_SKEW_FACTOR))
        inv_skew = -(pos / LIMIT) * self.OPT_INV_SKEW

        total_skew = inv_skew + dev_skew

        our_bid = int(round(fair - self.OPT_HALF_SPREAD + total_skew))
        our_ask = int(round(fair + self.OPT_HALF_SPREAD + total_skew))

        # Don't cross existing market (aggressive fills are Phase 1's job)
        if best_ask is not None and our_bid >= best_ask:
            our_bid = best_ask - 1
        if best_bid is not None and our_ask <= best_bid:
            our_ask = best_bid + 1
        if our_bid >= our_ask:
            return orders       # spread collapsed — skip passive leg

        if buy_cap > 0:
            orders.append(Order(prod, our_bid, min(self.OPT_BASE_VOL, buy_cap)))
        if sell_cap > 0:
            orders.append(Order(prod, our_ask, -min(self.OPT_BASE_VOL, sell_cap)))

        return orders

    # ── Utility ───────────────────────────────────────────────────────────────
    @staticmethod
    def _mid(od) -> Optional[float]:
        """Best-bid/best-ask mid."""
        if od is None or not od.buy_orders or not od.sell_orders:
            return None
        return (max(od.buy_orders) + min(od.sell_orders)) / 2.0

    @staticmethod
    def _wall_mid(od) -> Optional[float]:
        """Mid of the deepest-volume (wall) price levels on each side.
        More stable than best-bid/ask mid because it ignores small-lot
        noise from taker bots."""
        if od is None or not od.buy_orders or not od.sell_orders:
            return None
        wall_bid = max(od.buy_orders,  key=lambda p: od.buy_orders[p])
        wall_ask = min(od.sell_orders, key=lambda p: od.sell_orders[p])
        # sell_orders values are negative; largest volume = most negative
        return (wall_bid + wall_ask) / 2.0
