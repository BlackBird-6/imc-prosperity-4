# Round 4 Signal Analysis

Exhaustive search across all trader pairs, order book features, and intraday patterns.
Scripts: `signal_01_all_pairs.py`, `signal_02_orderflow.py`, `signal_03_intraday.py`, `signal_04_deep_dive.py`
All signals verified by-day to confirm they hold on all 3 days independently.

---

## Summary table

| Signal | Strength | Verified across days | Actionable |
|--------|----------|---------------------|------------|
| Book imbalance → price | corr=+0.28 | Yes — Day1 +0.41 / Day2 +0.42 / Day3 +0.39 | Yes — quote skew |
| Mark 67 buy → VEV bounce | win=95–98% h=100, all 3 days | Yes | Delay VEV hedge, not a taker trade |
| Mark 49 sell → VEV continues up | win=87–100% h=100, all 3 days | Yes | Quote skew, same direction as M67 |
| HP mean reversion speed | Half-life ~26k ticks | Structural | Validates holding HP positions |
| Net trade flow | corr≈0 | — | No |
| Mark 22 write volume | corr≈−0.02 | — | No |
| Mark 38 HP flow | corr≈0 | — | No |
| Time-of-day drift | Alternating sign | — | No |
| VEV → option lead-lag | corr≈−0.01 | — | No |

---

## 1. Book Imbalance → Future Price

**Strongest and cleanest signal. Confirmed on all 3 days independently.**

When `bvol > avol` in the order book, price goes up over the next 100 ticks. When `avol > bvol`, price goes down. Holds across VEV, HP, and all option strikes.

### VEV — by day

| Day | Bid-heavy avg (h=100) | Ask-heavy avg (h=100) |
|-----|-----------------------|-----------------------|
| Day 1 | +0.409 | −0.386 |
| Day 2 | +0.417 | −0.375 |
| Day 3 | +0.385 | −0.398 |

Day 3 VEV fell 63.5 points overall, yet the book imbalance signal is identical in magnitude. This is a short-term microstructure signal, not a day-level drift artifact.

### All products (aggregate across 3 days)

| Product | h=100 corr | Bid-heavy avg | Ask-heavy avg |
|---------|-----------|---------------|---------------|
| VEV | +0.281 | +0.403 | −0.387 |
| HP | +0.299 | +4.172 | −3.786 |
| VEV_5200 | +0.256 | +0.301 | −0.285 |
| VEV_5300 | +0.302 | +0.314 | −0.293 |
| VEV_5400 | +0.269 | +0.249 | −0.237 |
| VEV_5500 | +0.272 | +0.261 | −0.262 |

Signal weakens at longer horizons (corr drops from 0.28 at h=100 to 0.10 at h=1000) but remains positive. Most of the predictive content is in the first 100 ticks.

### Microprice deviation (same signal, different formulation)

`microprice = (bid × avol + ask × bvol) / (bvol + avol)`. When microprice > mid, price goes up. Essentially the same information — pick one.

| Product | h=100 corr | Micro-positive avg | Micro-negative avg |
|---------|-----------|--------------------|--------------------|
| VEV | +0.226 | +0.414 | −0.392 |
| HP | +0.298 | +4.234 | −3.842 |

### Why it is not a standalone taker strategy

VEV signal +0.40 ticks expected. VEV half-spread ≈ 2.5 ticks. Net = −2.1 per round-trip. Cannot capture as an aggressor.

### How to use it — quote skew

Apply as a free adjustment to the reservation price in the market maker. No extra transaction cost:

```python
bvol = order_depths[sym].buy_orders.get(best_bid, 0)
avol = abs(order_depths[sym].sell_orders.get(best_ask, 0))
tot  = bvol + avol
imb  = (bvol / tot - 0.5) if tot > 0 else 0.0   # range: −0.5 to +0.5

reservation += imb * IMB_SKEW   # start with IMB_SKEW = 1.0
```

When bid-heavy: reservation shifts up → ask tightens, bid widens. Price is likely rising so lean toward selling. When ask-heavy: opposite.

Applies directly to VEV delta-hedge sizing and option passive quotes. For HP, the signal is large (+4 ticks) but so is the spread (15 ticks) — use mainly to skew which side to prioritise when managing inventory.

---

## 2. Mark 67 — Dip Buyer (V-Bounce Signal)

**VEV falls sharply before every Mark 67 trade, then bounces. The signal is a mean-reversion V-shape, not directional prediction.**

### Pre-trade and post-trade price path

| Window | Avg price move | Win rate |
|--------|---------------|----------|
| t−2000 to t=0 | **−1.867** | 0.297 (VEV falls before trade) |
| t−1000 to t=0 | **−1.958** | 0.236 |
| t−500 to t=0 | **−1.712** | 0.200 |
| t−200 to t=0 | **−1.815** | 0.024 |
| t−100 to t=0 | **−1.776** | 0.024 |
| t=0 to t+100 | **+1.970** | **0.958** |
| t=0 to t+200 | +1.945 | 0.903 |
| t=0 to t+500 | +1.945 | 0.830 |
| t=0 to t+1000 | +2.242 | 0.758 |
| t=0 to t+2000 | +1.845 | 0.648 |
| t=0 to t+5000 | +1.918 | 0.588 |

VEV falls ~1.8 ticks with 97–98% consistency in the 100–200 ticks before each trade. Then bounces +1.97 ticks with 95.8% consistency after. Mark 67 is systematically identifying and buying local dip bottoms.

The baseline (random VEV buy at any timestamp) is h=100 avg=−0.066, win=0.370. Mark 67's +1.970 at 0.958 win rate is real.

### Confirmed on all 3 days — including Day 3 (VEV fell −63.5 overall)

| Day | h=100 avg | h=100 win | h=500 avg | h=500 win |
|-----|-----------|-----------|-----------|-----------|
| Day 1 | +1.991 | 0.983 | +2.198 | 0.897 |
| Day 2 | +1.861 | 0.934 | +1.754 | 0.852 |
| Day 3 | +2.087 | **0.957** | +1.880 | 0.717 |

Day 3 is the critical test: VEV fell 63.5 points on that day, yet Mark 67's dip buys still recovered within 100 ticks 95.7% of the time. The intraday V-bounces are independent of the day-level trend.

### What this tells us about market structure

Mark 67 enters when VEV is ~1.76 ticks below its EMA. The pre-trade fall (~1.8 ticks) and post-trade rise (~1.97 ticks) roughly cancel out — VEV returns to where it was before the dip. Mark 67 is not predicting net new price discovery; it is identifying temporary dislocations that resolve quickly. The bounces exist because Mark 55 (VEV market maker) provides bids that catch the fall, and the book re-establishes after liquidity is consumed.

### Practical use

**As a taker**: expected gain +1.97 ticks, cost ≈ 2.5 ticks. Net = −0.53 per unit. Not worth chasing.

**As a quote adjustment**: when `Mark 67` appears in `state.market_trades` as VEV buyer (qty ≥ 7):
- VEV is at a local bottom and will recover within ~100 ticks
- Delay any VEV buy hedge by ~100–200 ticks (price rising, hedge will fill cheaper)
- If you need to reduce long VEV delta, act now before the bounce completes
- Skew option bids slightly more aggressive (calls about to rise as VEV recovers)

Detection: `buyer == "Mark 67"`, `symbol == "VELVETFRUIT_EXTRACT"`, `quantity >= 7`.

---

## 3. Mark 49 — Momentum Seller (Consistent Anti-Signal)

**Price rises in the 100 ticks after every Mark 49 sell. Holds on all 3 days, including Day 3.**

### Forward price after Mark 49 sell — by day

| Day | h=100 avg | h=100 price rose | h=1000 avg | h=1000 price rose |
|-----|-----------|-----------------|------------|-------------------|
| Day 1 | +1.882 | **100%** | +2.515 | 76.5% |
| Day 2 | +1.757 | 86.5% | +1.784 | 73.0% |
| Day 3 | +2.074 | **97.1%** | +2.162 | 70.6% |

Day 3 is again the key test. Despite VEV falling 63.5 points overall, price rose 97.1% of the time in the 100 ticks after each Mark 49 sell. Mark 49 systematically sells into the middle of local upward momentum that continues for ~100 ticks before eventually reversing.

The h=1000 signal (70–76% price-rose rate) is weaker but still above chance. Mark 49's sells are wrong at all horizons tested.

### Entry timing confirms the pattern

Mark 49 enters when VEV is +1.62 ticks above its EMA (average_dev = +1.617). It sells into local strength. Price then continues higher for another ~100 ticks before the local move exhausts. Mark 49 is consistently early in selling off local peaks.

### What this tells us about market structure

This is the symmetric counterpart to Mark 67. Where Mark 67 buys dip bottoms too early (but catches the bounce), Mark 49 sells local peaks too early (and gets run over). Together they describe a market where VEV makes short, sharp moves (±1.8 ticks) that quickly revert. Mark 67 profits from the long-side reversion; Mark 49 loses on the short-side because the reversal takes more than 100 ticks to manifest.

### Practical use

**As a taker**: buy VEV when Mark 49 sells. Expected gain +1.88–2.07 ticks at h=100. Cost ≈ 2.5 ticks. Net = −0.4 to −0.6 per unit. Still marginal as a taker.

**As a quote adjustment**: when `Mark 49` appears in `state.market_trades` as VEV seller:
- Do not use as a sell signal — the trade moves against you 87–100% of the time at h=100
- Treat like Mark 67 — both point toward VEV continuing up for ~100 ticks
- Detection: `seller == "Mark 49"`, `symbol == "VELVETFRUIT_EXTRACT"`, typical qty ≥ 9

---

## 4. HP Mean Reversion Speed

Measured by tracking how long HP takes to return to within N/2 ticks of 10,000 after deviating by N.

| Deviation | n events | p25 | p50 (half-life) | p75 | p90 |
|-----------|----------|-----|-----------------|-----|-----|
| ≥5 ticks | 26,778 | 7,500 | 25,600 | 64,400 | 110,100 |
| ≥10 ticks | 23,519 | 8,000 | 26,200 | 68,200 | 114,200 |
| ≥20 ticks | 17,574 | 12,400 | 33,400 | 75,600 | 118,800 |
| ≥30 ticks | 12,871 | 17,200 | 41,300 | 82,900 | 128,600 |

**HP mean-reverts with a half-life of ~26,000 ticks** regardless of how large the initial deviation is. Large deviations take somewhat longer (half-life 41k at ≥30 ticks) but they do reliably revert. The wide p75–p90 range (64k–128k ticks) means some positions need to be held for most of a trading day.

The current HP strategy (anchor pull + inventory skew) is well-suited: fills accumulate during deviations and the position resolves within the half-life window in the median case.

---

## 5. Combined Mark 67 + Mark 49 + Book Imbalance

All three signals point in the same direction — VEV is about to rise short-term — under different conditions:

| Trigger | Condition | Expected VEV move h=100 |
|---------|-----------|------------------------|
| Book imbalance | bvol/total > 0.6 | +0.40 ticks |
| Mark 67 buys | seen in market_trades | +1.97 ticks |
| Mark 49 sells | seen in market_trades | +1.88 ticks |

These are independent signals. When multiple fire at once, the signal is stronger. All three can be applied as quote skew adjustments in the market maker at zero additional transaction cost.

---

## 6. What Is Not Signal

### Net trade flow (VEV, HP, options)
Correlation with future price ≈ 0 for all products and window/horizon combinations. Total buy volume minus sell volume in any rolling window is not predictive.

### Mark 22 option write volume → VEV
Mark 22 writes options and should delta-hedge by buying VEV. Tested net delta exposure in 5k-tick window vs VEV future price. corr = −0.007 at h=100, −0.023 at h=1000. Noise.

### Mark 38 HP flow
Correlation of Mark 38 net buy/sell with future HP ≈ 0 at all windows and horizons. Mark 38 is a pure liquidity taker against Mark 14 — no directional information.

### Time-of-day patterns
VEV and HP show isolated significant bins at long horizons but they alternate sign every bin and are inconsistent — noise rather than exploitable structure.

### VEV move → option price (lead-lag)
corr ≈ −0.01 at h=100. Options reprice when VEV moves, but the repricing is contemporaneous (happens at the same tick), not predictable from lagged VEV moves.

### Mark 01 / Mark 22 simultaneous multi-product trading
Both bots always trade 4–5 option strikes in a cluster within 200 ticks (312 cluster events each). This is mechanical strip quoting, not a signal.

---

## Implementation priority

1. **Book imbalance quote skew** — add `(bvol/total − 0.5) × IMB_SKEW` to reservation price. Verified signal on all 3 days. Zero extra cost. Start `IMB_SKEW = 1.0`. Apply to option quotes and VEV hedge sizing.

2. **Mark 67 / Mark 49 detection** — check `state.market_trades` each tick. Both bots signal short-term VEV upward move. When either fires, delay buy-side VEV hedges by ~100 ticks and lean into sell-side hedges. Cannot profitably chase as a taker but free to use as a timing adjustment.

3. **Nothing else** — net flow, write volume, time-of-day, and relative value signals are all noise or below transaction cost thresholds after verification.
