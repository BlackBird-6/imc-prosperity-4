"""
Round 3 strategy
================
HYDROGEL_PACK        — mean-reverts ~10,000; passive market-make ± HP_HALF_SPREAD
                       with momentum and inventory skew.
VELVETFRUIT_EXTRACT  — underlying for options; EMA used as spot fallback only.
VEV_5000…VEV_5400    — European calls; fair value via Black-Scholes.
                       Phase 1: aggressively take when bot quote > OPT_TAKE_EDGE off fair.
                       Phase 2: passively quote fair ± OPT_HALF_SPREAD with inventory skew.

On tick 0 we calibrate two things from observed option mids:
  tte_start — days remaining at day open (avoids TTE mis-estimation).
  sigmas    — per-strike implied vol (corrects the vol smile).
Both are stored in traderData and reused every subsequent tick.

Position limits: HYDROGEL_PACK 200 · VELVETFRUIT_EXTRACT 200 · VEV_* 300.
"""

import json
import math
from typing import List, Optional

from datamodel import Order, TradingState

# ── Platform constants ─────────────────────────────────────────────────────────
DAYS_PER_YEAR = 365
DAY_END_TS    = 999_900   # final timestamp within a single day

# ── Black-Scholes ──────────────────────────────────────────────────────────────

def _norm_cdf(x: float) -> float:
    # Abramowitz & Stegun §26.2.17 — max error 7.5e-8
    t = 1.0 / (1.0 + 0.2316419 * abs(x))
    p = 1.0 - math.exp(-0.5*x*x) / math.sqrt(2*math.pi) * t * (
        0.319381530 + t*(-0.356563782 + t*(1.781477937 + t*(-1.821255978 + t*1.330274429))))
    return p if x >= 0.0 else 1.0 - p

def _bs_call(S: float, K: float, T: float, sigma: float) -> float:
    """European call price (r=0)."""
    if T <= 0.0:
        return max(S - K, 0.0)
    sq = math.sqrt(T)
    d1 = (math.log(S / K) + 0.5*sigma*sigma*T) / (sigma*sq)
    return S*_norm_cdf(d1) - K*_norm_cdf(d1 - sigma*sq)

def _tte_years(timestamp: int, tte_start: float) -> float:
    """TTE in years; decreases linearly from tte_start to tte_start-1 across a day."""
    return max(tte_start - timestamp / DAY_END_TS, 1e-6) / DAYS_PER_YEAR

def _bisect(lo: float, hi: float, n: int, fn) -> float:
    """n-iteration binary search; fn(mid)==True → lo=mid, else hi=mid."""
    for _ in range(n):
        mid = (lo + hi) / 2.0
        if fn(mid): lo = mid
        else:       hi = mid
    return (lo + hi) / 2.0

SIGMA_DEFAULT = 0.31   # historical IV baseline

# ── Calibration ────────────────────────────────────────────────────────────────

def _calibrate_tte(vev_mid: float, order_depths: dict, vouchers: dict) -> float:
    """Infer days-remaining at day open from observed option mids via BS inversion.

    Only uses options where time_value >= 5 AND >= 20% of mid — deep-ITM
    options have negligible time value so their estimate is noisy.
    Returns the median, clamped to [2, 7]; falls back to 5.0.
    """
    estimates = []
    for prod, K in vouchers.items():
        od = order_depths.get(prod)
        if od is None or not od.buy_orders or not od.sell_orders:
            continue
        mid = (max(od.buy_orders) + min(od.sell_orders)) / 2.0
        if mid <= 0:
            continue
        tv = mid - max(vev_mid - K, 0.0)
        if tv >= 5.0 and tv / mid >= 0.20:
            t = _bisect(1/DAYS_PER_YEAR, 8/DAYS_PER_YEAR, 50,
                        lambda t: _bs_call(vev_mid, K, t, SIGMA_DEFAULT) < mid)
            estimates.append(t * DAYS_PER_YEAR)

    if not estimates:
        return 5.0   # competition days run TTE 5→3; 5 is a safe fallback
    estimates.sort()
    return max(2.0, min(7.0, estimates[len(estimates) // 2]))

# ── Logger (visualizer protocol — do not modify) ───────────────────────────────

class Logger:
    def __init__(self): self.logs = ""; self.max_log_length = 3750
    def print(self, *o, sep=" ", end="\n"): self.logs += sep.join(map(str, o)) + end

    def flush(self, state, orders, conv, td):
        base = len(self.to_json([self.compress_state(state,""), self.compress_orders(orders), conv,"",""]))
        L = (self.max_log_length - base) // 3
        print(self.to_json([
            self.compress_state(state, self.truncate(state.traderData, L)),
            self.compress_orders(orders), conv,
            self.truncate(td, L), self.truncate(self.logs, L),
        ]))
        self.logs = ""

    def compress_state(self, state, td):
        return [state.timestamp, td,
                [[l.symbol, l.product, l.denomination] for l in state.listings.values()],
                {s: [od.buy_orders, od.sell_orders] for s, od in state.order_depths.items()},
                self.compress_trades(state.own_trades),
                self.compress_trades(state.market_trades),
                state.position, self.compress_obs(state.observations)]

    def compress_trades(self, trades):
        return [[t.symbol,t.price,t.quantity,t.buyer,t.seller,t.timestamp]
                for arr in trades.values() for t in arr]

    def compress_obs(self, obs):
        return [obs.plainValueObservations,
                {p: [o.bidPrice,o.askPrice,o.transportFees,o.exportTariff,
                     o.importTariff,o.sugarPrice,o.sunlightIndex]
                 for p, o in obs.conversionObservations.items()}]

    def compress_orders(self, orders):
        return [[o.symbol,o.price,o.quantity] for arr in orders.values() for o in arr]

    def to_json(self, v): return json.dumps(v, cls=ProsperityEncoder, separators=(",",":"))
    def truncate(self, v, n): return v if len(v) <= n else v[:n-3] + "..."

class ProsperityEncoder(json.JSONEncoder):
    def default(self, obj):
        return obj.__dict__ if hasattr(obj, "__dict__") else super().default(obj)

logger = Logger()

# ── Trader ─────────────────────────────────────────────────────────────────────

class Trader:

    HP               = "HYDROGEL_PACK"
    HP_FAIR          = 10_000
    HP_LIMIT         = 200
    HP_HALF_SPREAD   = 8     # ±8 ticks (tighter than v1; more fills at lower per-trade profit)
    HP_BASE_VOL      = 20    # units per side (3× v1; compensates for tighter spread)
    HP_EMA_ALPHA     = 0.02  # slow EMA of recent mid (mostly ignored — 90% weight on fixed fair)
    HP_FIXED_WEIGHT  = 0.90  # blend: 90% fixed anchor + 10% EMA
    HP_ANCHOR_PULL   = 0.70  # how hard to pull reservation toward fair when mid deviates
    HP_INV_SKEW      = 6.0   # max midpoint shift (ticks) at full position limit

    VEV              = "VELVETFRUIT_EXTRACT"
    VEV_LIMIT        = 200
    VEV_EMA_ALPHA    = 0.05
    VEV_FAIR_FALLBACK = 5_250   # approximate VEV spot; only used before tick-0 book arrives

    VOUCHERS: dict = {"VEV_5000":5000, "VEV_5100":5100, "VEV_5200":5200,
                      "VEV_5300":5300, "VEV_5400":5400}
    OPT_LIMIT        = 300
    OPT_HALF_SPREAD  = 1    # ±1 tick (grid-search optimum)
    OPT_BASE_VOL     = 20   # units per side
    OPT_TAKE_EDGE    = 5    # take aggressively when > 5 ticks mispriced
    OPT_INV_SKEW     = 3    # max inventory skew ticks at full position

    def run(self, state: TradingState):
        result: dict = {}
        conversions = 0

        try:    data = json.loads(state.traderData) if state.traderData else {}
        except: data = {}

        # VEV spot price; EMA kept as fallback when book is unavailable
        vev_od  = state.order_depths.get(self.VEV)
        vev_mid = self._mid(vev_od)
        if vev_mid is not None:
            prev = data.get("vev_ema", vev_mid)
            data["vev_ema"] = prev + self.VEV_EMA_ALPHA * (vev_mid - prev)
        S = vev_mid if vev_mid is not None else data.get("vev_ema", self.VEV_FAIR_FALLBACK)

        # Calibrate TTE once on tick 0
        if "tte_start" not in data and vev_mid is not None:
            data["tte_start"] = _calibrate_tte(
                vev_mid, state.order_depths, self.VOUCHERS
            )
        tte_start = data.get("tte_start", 5.0)
        T         = _tte_years(state.timestamp, tte_start)

        for prod, K in self.VOUCHERS.items():
            if prod in state.order_depths:
                result[prod] = self._trade_option(
                    state, prod, K, S, T, SIGMA_DEFAULT
                )

        if self.HP in state.order_depths:
            result[self.HP] = self._trade_hp(state, data)

        trader_data = json.dumps(data)
        logger.flush(state, result, conversions, trader_data)
        return result, conversions, trader_data

    def _trade_hp(self, state: TradingState, data: dict) -> List[Order]:
        od    = state.order_depths[self.HP]
        pos   = state.position.get(self.HP, 0)
        LIMIT = self.HP_LIMIT

        best_bid = max(od.buy_orders)  if od.buy_orders  else None
        best_ask = min(od.sell_orders) if od.sell_orders else None
        if best_bid is None or best_ask is None:
            return []
        mid = (best_bid + best_ask) / 2.0

        # Blended fair: mostly anchored to 10000, slightly tracking recent mid via EMA
        ema  = self.HP_EMA_ALPHA * mid + (1 - self.HP_EMA_ALPHA) * data.get("hp_ema", mid)
        data["hp_ema"] = ema
        fair = self.HP_FIXED_WEIGHT * self.HP_FAIR + (1 - self.HP_FIXED_WEIGHT) * ema

        # Reservation price: pull toward fair when mid deviates, skew for inventory
        tilt        = (fair - mid) * self.HP_ANCHOR_PULL - (pos / LIMIT) * self.HP_INV_SKEW
        reservation = mid + tilt

        # Quote symmetrically around reservation.
        # Clamping to best_ask / best_bid (not best_ask-1) is intentional:
        # when HP is cheap (fair >> mid) the bid rises to best_ask → aggressive buy;
        # when expensive the ask falls to best_bid → aggressive sell.
        bid = min(int(round(reservation - self.HP_HALF_SPREAD)), best_ask)
        ask = max(int(round(reservation + self.HP_HALF_SPREAD)), best_bid)

        orders: List[Order] = []
        if LIMIT - pos > 0: orders.append(Order(self.HP, bid,  min(self.HP_BASE_VOL, LIMIT - pos)))
        if LIMIT + pos > 0: orders.append(Order(self.HP, ask, -min(self.HP_BASE_VOL, LIMIT + pos)))
        return orders

    def _trade_option(
        self, state: TradingState, prod: str, K: int, S: float, T: float, sigma: float
    ) -> List[Order]:
        od    = state.order_depths[prod]
        pos   = state.position.get(prod, 0)
        LIMIT = self.OPT_LIMIT
        fair  = _bs_call(S, K, T, sigma)

        buy_cap  = LIMIT - pos
        sell_cap = LIMIT + pos
        best_bid = max(od.buy_orders)  if od.buy_orders  else None
        best_ask = min(od.sell_orders) if od.sell_orders else None

        orders: List[Order] = []

        # Phase 1: take when a bot quote is far from fair value
        if best_ask is not None and best_ask < fair - self.OPT_TAKE_EDGE and buy_cap > 0:
            qty = min(buy_cap, -od.sell_orders[best_ask])
            if qty > 0: orders.append(Order(prod, best_ask,  qty)); buy_cap  -= qty

        if best_bid is not None and best_bid > fair + self.OPT_TAKE_EDGE and sell_cap > 0:
            qty = min(sell_cap, od.buy_orders[best_bid])
            if qty > 0: orders.append(Order(prod, best_bid, -qty)); sell_cap -= qty

        # Phase 2: passive quote with inventory skew to stay bounded
        inv_skew = -(pos / LIMIT) * self.OPT_INV_SKEW
        our_bid  = int(round(fair - self.OPT_HALF_SPREAD + inv_skew))
        our_ask  = int(round(fair + self.OPT_HALF_SPREAD + inv_skew))

        if best_ask is not None and our_bid >= best_ask: our_bid = best_ask - 1
        if best_bid is not None and our_ask <= best_bid: our_ask = best_bid + 1
        if our_bid >= our_ask: return orders  # spread collapsed

        if buy_cap  > 0: orders.append(Order(prod, our_bid,  min(self.OPT_BASE_VOL, buy_cap)))
        if sell_cap > 0: orders.append(Order(prod, our_ask, -min(self.OPT_BASE_VOL, sell_cap)))
        return orders

    @staticmethod
    def _mid(od) -> Optional[float]:
        if od is None or not od.buy_orders or not od.sell_orders: return None
        return (max(od.buy_orders) + min(od.sell_orders)) / 2.0