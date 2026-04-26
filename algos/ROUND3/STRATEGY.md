# Round 3 Strategy: Options Market-Making + HP Mean-Reversion

## Overview

Round 3 introduces 12 products:
- **HYDROGEL_PACK (HP)** — a commodity that bounces around a fixed price like a rubber ball. It barely drifts and tends to snap back whenever it moves away. Same behaviour as Round 1's ASH_COATED_OSMIUM.
- **VELVETFRUIT_EXTRACT (VEV)** — an "underlying" asset. It slowly drifts upward over time. On its own it isn't interesting to trade directly, but its price is what drives the value of the options below.
- **VEV_4000 through VEV_6500** — 10 European call options on VEV, with strike prices 4000, 4500, 5000, 5100, 5200, 5300, 5400, 5500, 6000, 6500.

A **European call option** with strike K gives the buyer the right (but not the obligation) to buy the underlying at price K when the option expires. If VEV is trading at 5300 at expiry and you hold the VEV_5000 option, you can buy at 5000 and immediately sell at 5300 — capturing 300 profit per unit. The option is only worth exercising if VEV > K at expiry.

The strategy has two independent components:
1. **HYDROGEL_PACK** — passive market-making around a hard fair value of 10,000
2. **VEV_5000 to VEV_5400** — Black-Scholes-based options market-making

Backtested total PnL across 3 days: **~187,000**

---

## 1. Data Analysis

### Historical Data (3 days, 10,000 timestamps each)

#### HYDROGEL_PACK

HP barely moves. Looking at all 3 days:
- Mean price: ~9,990 (within 10 ticks of 10,000)
- Full range: 9,891–10,079
- Bots quote approximately ±8 ticks from mid (so the bot bid-ask spread is about 15–17 ticks wide)
- Lag-1 return autocorrelation: −0.14

The autocorrelation of −0.14 means: if the price just went up, it's slightly more likely to come back down on the next tick than to keep going up. That's the definition of mean-reversion. It's weak (−1.0 would be perfect mean-reversion, 0 would be random), but it's enough to tell us this product has a natural anchor.

**Conclusion:** Treat 10,000 as the "true" fair value. This is identical to how we traded ASH_COATED_OSMIUM in Round 1.

---

#### VELVETFRUIT_EXTRACT (underlying)

VEV drifts slowly upward — from around 5,250 to 5,296 across the 3 historical days. The bots' bid-ask spread is about 5 ticks wide.

There's no identifiable fair value we can pin down for VEV itself, so we don't directly market-make on it. We only use VEV's current price as an input to pricing the options.

---

#### VEV Vouchers — Implied Volatility Analysis

This is the most important part of the options analysis. Here's the concept from scratch:

**What is volatility?**
In finance, "volatility" (σ, pronounced "sigma") is how much an asset's price tends to move around per unit of time. A highly volatile stock might swing ±5% per day; a stable bond might move ±0.05% per day. Volatility is usually expressed as an annualised percentage — e.g. σ = 30% means the asset moves roughly 30% per year in standard deviation terms.

**What is implied volatility?**
Options prices are set by the market. The Black-Scholes formula (explained in Section 3) lets you compute a theoretical option price if you supply: the underlying price (S), strike (K), time to expiry (T), and volatility (σ). If you flip this around — take the market price of the option as given and solve backwards for σ — the σ you get is called the **implied volatility (IV)**. It's the market's consensus estimate of how volatile the underlying will be over the option's life.

**Why does this matter?**
If we know the typical IV that the market is pricing in, we can set σ in our Black-Scholes model to match it, which means our theoretical prices will agree with the market's prices on average. We're not trying to predict whether IV will go up or down — we're trying to calibrate our model so we're quoting around the right centre. If we use the wrong σ, we'll systematically over- or under-price options and fill heavily on one side, accumulating a big position that could turn against us.

**How we computed IV from the data:**

For each option at each timestamp, we knew:
- S = VEV mid price at that moment
- K = strike (e.g. 5000, 5100, ...)
- T = time remaining until expiry (in years)
- C_market = the mid price of the option in the order book

We binary-searched for the σ that makes BS_call(S, K, T, σ) = C_market. That σ is the implied volatility.

| Strike | Day 0 IV | Day 1 IV | Day 2 IV |
|--------|----------|----------|----------|
| 5000   | 30.3%    | 32.1%    | 35.4%    |
| 5100   | 30.4%    | 32.2%    | 33.9%    |
| 5200   | 30.3%    | 32.4%    | 35.4%    |
| 5300   | 30.6%    | 32.1%    | 35.5%    |
| 5400   | 30.3%    | 30.4%    | 32.5%    |
| 5500   | 30.3%    | 33.3%    | 35.6%    |

**Key observations:**

1. **Flat volatility surface.** In real markets, options at different strikes often have different IVs — this is called the "volatility smile" or "volatility skew." Here, all strikes show essentially the same IV on any given day (~30–31% on day 0). This simplifies our model enormously: we only need one σ value to price all the options, rather than a complex curve.

2. **IV rises as expiry approaches.** Day 0 IV ≈ 30%, Day 2 IV ≈ 35–36%. This seems counterintuitive (normally IV can go either way), but in this simulation it drifts upward consistently. We chose to ignore this drift and anchor on day-0 IV because competition day 0 is what we'll actually trade. Using a fixed σ = 0.31 is deliberately conservative — we're not trying to predict IV movements.

3. **VEV_5400 has slightly lower IV (~30%)** compared to its neighbours (~31%). This is a minor anomaly in the data; not significant enough to adjust our model for.

---

#### Deep ITM Options: VEV_4000 and VEV_4500

An option is **in the money (ITM)** when the underlying is already above the strike (so exercising now would give a profit). **Deep ITM** means the underlying is far above the strike.

For VEV_4000 (strike = 4000), with VEV at ~5,270, the option is 1,270 ticks in the money. The market was pricing these options at exactly their **intrinsic value** (S − K), with zero time value on top.

**Why is time value interesting?** Normally, the option has extra value on top of intrinsic because there's a chance VEV moves even higher before expiry. But deep enough ITM, this extra time value becomes negligible — the option basically just moves 1:1 with VEV. When the market prices these at exactly intrinsic with no premium, there's no edge for us as market-makers (we're not getting paid any spread for the risk we take). So we skip these.

---

#### Far OTM Options: VEV_6000 and VEV_6500

An option is **out of the money (OTM)** when the underlying is below the strike (exercising now would give a loss). **Far OTM** means the underlying would need to move a huge amount to be worth anything.

With VEV at ~5,270, VEV_6000 (strike = 6000) would need VEV to jump ~730 ticks before expiry. The market was pricing these at 0.5 consistently — basically the minimum tick. There's no real market here: no sensible market-maker would quote on an instrument nobody wants to trade. Skipped.

---

## 2. Time to Expiry (TTE)

The VEV options are 7-day European calls starting from Round 1. By Round 3, 2 days have already passed:

| Round | TTE at start of that round |
|-------|---------------------------|
| 1     | 7 days                    |
| 2     | 6 days                    |
| 3     | 5 days                    |

Within a single competition day (timestamps 0 → 999,900), the option ticks closer to expiry continuously:

```
TTE(ts) = (TTE_START - ts / 999_900) / 365   [in years]
```

The divide by 365 converts days to years, which is what Black-Scholes expects.

The backtester sets an env var `PROSPERITY4BT_DAY` (0, 1, or 2) so we can offset `TTE_START` correctly when backtesting:

```python
_BT_DAY = int(os.environ.get("PROSPERITY4BT_DAY", "0"))
_TTE_START_DAYS = 5.0 - _BT_DAY
```

In the actual competition this env var doesn't exist, so the default of day 0 (TTE_START = 5) is used — correct for the competition.

**Why does TTE matter?** The more time left before expiry, the more the underlying can move, and the more the option is worth (all else equal). As the clock ticks down, option values decay — this is called **theta decay**. Our Black-Scholes price will naturally reflect this by computing a smaller value as T shrinks, so we don't need any special logic for it.

---

## 3. Black-Scholes Model

### What is Black-Scholes?

Black-Scholes (BS) is a mathematical formula for pricing European options. It was derived in 1973 and is still the industry standard for a first-approximation price. It takes in S, K, T, and σ, and outputs the theoretical fair value of the option assuming the underlying moves randomly with constant volatility.

The formula for a European call with no dividends and zero risk-free rate (r = 0 — fine since this is a competition, not a real bond market):

```
C(S, K, T, σ) = S · N(d₁) − K · N(d₂)
d₁ = [ln(S/K) + ½σ²T] / (σ√T)
d₂ = d₁ − σ√T
```

Where N(·) is the standard normal CDF (the S-shaped curve that tells you the probability of a normal random variable being below a certain value). You don't need to understand every symbol — the key takeaway is:

- If S is much larger than K (deep ITM), d₁ and d₂ are large, N(d₁) ≈ N(d₂) ≈ 1, and C ≈ S − K (intrinsic value only, matching what we observed for VEV_4000).
- If S is much smaller than K (deep OTM), d₁ and d₂ are very negative, N(d₁) ≈ N(d₂) ≈ 0, and C ≈ 0 (matching VEV_6000/6500).
- The interesting cases are near-the-money (ATM), where the formula gives a value between 0 and intrinsic, incorporating the possibility that VEV ends up either side of K by expiry.

### Call delta (Δ)

Delta is the slope of the option's price with respect to a move in the underlying:

```
Δ = N(d₁)
```

In plain English: if VEV moves up by 1 tick and your option's delta is 0.6, your option gains about 0.6 ticks in value. Delta is between 0 and 1 for calls.

For the strikes we trade, roughly:
- VEV_5000 (deep ITM): Δ ≈ 0.91 — moves almost 1:1 with VEV
- VEV_5100: Δ ≈ 0.80
- VEV_5200 (near ATM): Δ ≈ 0.62
- VEV_5300: Δ ≈ 0.38
- VEV_5400: Δ ≈ 0.20 — barely reacts to VEV moves

### Why σ = 0.31?

From the IV analysis: all strikes on day 0 show IV between 30.3% and 30.6%. We round up slightly to 0.31 to give a small upward cushion — our model fair price will be very slightly above the market's consensus, which means we'll be marginally more willing to sell than to buy. This slight lean is a deliberate choice to avoid accumulating an uncapped long position in a product where VEV is slowly drifting up.

A grid search across σ ∈ {0.28, 0.30, 0.31, 0.32, 0.34} confirmed σ = 0.31 with take_edge = 5 gives the most consistent performance across days (σ = 0.32 take = 3 squeezed out slightly more total PnL at 192k, but that combination benefits from VEV's upward drift in the historical data — it's not robust for a future day where VEV doesn't happen to drift up).

---

## 4. Options Market-Making Strategy

"Market-making" means we continuously quote both a bid (where we'll buy) and an ask (where we'll sell). The idea is that other participants trade against our quotes, and we capture the spread between our bid and ask as profit. The risk is that if we buy and then the price falls (or sell and the price rises), we lose on the position.

For each option from VEV_5000 to VEV_5400, every tick we:

### Phase 1: Aggressive Take on Mispricings

If someone is offering to sell an option to us below fair value (by more than 5 ticks), we immediately buy it — we're getting a discount:

```
if best_ask < BS_fair − 5:
    buy up to position limit at best_ask
```

If someone is bidding above fair (by more than 5 ticks), we immediately sell — we're getting a premium:

```
if best_bid > BS_fair + 5:
    sell up to position limit at best_bid
```

This is sometimes called "taking" the market (vs. "making" the market by posting resting orders). In practice this fires infrequently — bots are well-calibrated and don't often quote 5 ticks away from fair. But when it does fire, the edge is large.

The 5-tick threshold (`OPT_TAKE_EDGE`) was chosen by grid search. Too small and we're constantly hitting the book and paying crossing costs; too large and we miss real mispricings.

### Phase 2: Passive Market-Making

We post resting limit orders on both sides:

```
our_bid = round(BS_fair − 1 + inv_skew)
our_ask = round(BS_fair + 1 + inv_skew)
```

**Half-spread = 1 tick:** We're quoting ±1 tick around our fair value. The bots' bid-ask spreads on these options range from about 1.4 ticks (VEV_5500) to 6 ticks (VEV_5000). By quoting ±1, our orders sit inside the bot spread — competitive, meaning other market participants will preferentially trade with us. This is why we use half-spread = 1 rather than something wider: we want to actually attract trades.

**Inventory skew:** Without any adjustment, if VEV is trending up, our fair value rises every tick, and our buy orders fill more often than our sell orders — we slowly accumulate a long position. This is risky because it means our PnL is now correlated with VEV's direction (if VEV suddenly drops, we lose).

The inventory skew nudges both quotes based on our current position:

```
inv_skew = −(position / limit) × 3
```

At maximum long (+300 units), the skew is −3, pushing our bid down by 3 ticks (less attractive to sellers) and our ask down by 3 ticks (more attractive to buyers). This naturally rebalances the inventory over time without ever completely stopping us from trading.

**Guard:** We never let our passive bid cross the best ask or our ask cross the best bid — that would be an unintended immediate fill at a crossed price.

---

### Why Not Delta Hedge with VEV?

The natural instinct when running an options book is to hedge your delta exposure: if you've bought a bunch of options with Δ ≈ 0.6, you have the equivalent of 0.6 units of VEV exposure per option. To neutralise that, you'd short VEV.

We tested this and it made things worse:

| Strategy          | 3-day PnL |
|-------------------|-----------|
| With VEV hedge    | 135,605   |
| No VEV hedge      | 187,428   |

**Why hedging loses money here:** The VEV bid-ask spread is ~5 ticks. Every time you hedge by buying VEV at the ask and then selling at the bid (or vice versa), you pay 5 ticks. Hedging frequently means paying that cost over and over.

In our case, this cost outweighs the benefit. Our options market-making is approximately delta-neutral in aggregate — when we buy some options and sell others across many fills, the delta exposures partially cancel. The residual delta risk doesn't cause enough harm to justify the repeated 5-tick crossing cost.

This is a specific property of this simulation environment. In a real market with tiny spreads you'd always hedge; here, spreads are wide enough that hedging is expensive.

---

## 5. HYDROGEL_PACK Market-Making

### Why Hard Fair Value = 10,000?

HP across all 3 days:
- Mean price: 9,990 (within 10 ticks of 10,000)
- Range: 9,891–10,079
- Lag-1 return autocorrelation: −0.14

This instrument has no drift and mean-reverts reliably. There's no estimation needed — 10,000 is the obvious anchor. Any time HP moves away from 10,000, it's almost certain to come back.

### Quote Construction

```
adjusted_fair = 10,000 + momentum_skew + inventory_skew
bid = round(adjusted_fair − 15)
ask = round(adjusted_fair + 15)
```

**Momentum skew** — contrarian, fades the last mid-price move:
```
momentum_skew = −(current_mid − prev_mid) × 0.5
```

If the price just moved up 2 ticks, our fair drops by 1 tick. This is a small bet on mean-reversion: after a move up, we expect a move back down, so we lean our quotes lower. It also reduces adverse selection (being filled by someone who knows the price is about to keep moving against us).

**Inventory skew** — shifts quotes toward zero inventory:
```
inventory_skew = −(position / limit) × 4
```

At +200 (full long), our fair drops by 4 ticks: our ask becomes 4 ticks cheaper (more likely to fill, reducing the long) and our bid becomes 4 ticks cheaper (less likely to add more longs). This keeps us from drifting to a permanently one-sided position.

### Why HP_HALF_SPREAD = 15? The Backtester Fill Mechanic

This deserves its own explanation because the logic is counterintuitive at first.

The bots quote approximately ±8 ticks from mid. That means the bot spread is about 16 ticks wide.

If our half-spread is **smaller than 8** (e.g. ±5), our quotes sit **inside** the bot spread. When a "market trade" happens at the bot prices, the backtester fills us first (we're inside the book). But it fills us at **our price** (e.g. 9,995 for a buy when fair is 10,000). We make 5 ticks per fill.

If our half-spread is **larger than 8** (e.g. ±15), our quotes sit **outside** the bot spread. Bot quotes absorb everything at normal prices, and our orders only fill if someone trades all the way out to 9,985 (for a buy). That's unlikely from normal activity — but when it does happen, the backtester fills us at **our price**, and we make 15 ticks.

The grid search across HP_HALF_SPREAD ∈ {3…25}:

| HS  | Vol | 3-day PnL |
|-----|-----|-----------|
| 5   | 15  | 160,012   |
| 10  | 5   | 173,938   |
| 15  | 6   | **187,428** |
| 20  | 5   | 161,968   |
| 25  | 5   | 143,202   |

HS=15 wins because: the higher spread gives us 15 ticks of edge per fill instead of 5, and there are still enough market trades reaching our price to keep inventory turning over. At HS=20+, fills become too rare and inventory accumulates (paying the inventory skew cost without earning enough to compensate).

`HP_BASE_VOL = 6` means we quote 6 units per side. Smaller volume → less inventory per fill → inventory skew stays effective and we don't hit position limits from a single large fill.

---

## 6. Products Excluded and Why

| Product        | Reason                                                                   |
|----------------|--------------------------------------------------------------------------|
| VEV_4000       | Trades at intrinsic value exactly — no time value, no edge for MM        |
| VEV_4500       | Same                                                                     |
| VEV_5500       | Bot spread ≈ 1 tick — no room to quote inside; risk of crossing both sides |
| VEV_6000       | Far OTM, stuck at 0.5 — no real market                                  |
| VEV_6500       | Same                                                                     |
| VEV (direct)   | No fair value to anchor on; trading it eats into the budget we'd need for delta hedging |

---

## 7. Parameter Summary

| Parameter        | Value | How determined                             |
|------------------|-------|--------------------------------------------|
| `HP_FAIR`        | 10,000 | Historical mean, confirmed mean-reverting  |
| `HP_HALF_SPREAD` | 15    | Grid search: HS ∈ {3…25} × vol ∈ {2…15}   |
| `HP_BASE_VOL`    | 6     | Grid search (same sweep)                   |
| `OPT_SIGMA`      | 0.31  | Fitted to day-0 historical IV              |
| `OPT_HALF_SPREAD`| 1     | Grid search: HS ∈ {1,2,3}                  |
| `OPT_BASE_VOL`   | 20    | Saturated by bot depth; no effect above ~15 |
| `OPT_TAKE_EDGE`  | 5     | Grid search: edge ∈ {3,5,8}               |
| `OPT_INV_SKEW`   | 3     | Heuristic; keeps options position bounded  |
| `VEV_EMA_ALPHA`  | 0.05  | Slow EMA for smoothing the VEV reference price |

---

## 8. Backtested Results

```
Round 3 day 0 (TTE: 5→4): +81,192
Round 3 day 1 (TTE: 4→3): +42,822
Round 3 day 2 (TTE: 3→2): +63,414
Total:                    +187,428
```

Per-product (summed across 3 days):
- HYDROGEL_PACK: +137,880
- VEV_5000: +10,991
- VEV_5100: +19,391
- VEV_5200: +16,704
- VEV_5300: +2,070
- VEV_5400: +392

HP contributes ~74% of total PnL. The options account for the rest (~49k), with VEV_5100 and VEV_5200 being the biggest contributors (near-ATM options have the widest market and the most activity).

---

## 9. Risks and Limitations

1. **Options delta exposure:** Without delta hedging, accumulated positions create directional VEV risk. If VEV moves sharply and we're sitting on a large net long options position, we could lose on the unhedged delta. In practice the inventory skew limits how large any single position grows, and the aggregate delta across buys and sells is close to zero over time.

2. **IV drift:** Historical IV rose from ~30% (day 0) to ~36% (day 2). Our model is fixed at σ=0.31. If the competition day sees IV significantly different from 31%, our quotes will be systematically above or below the market — we'll only fill on one side, slowly building a one-sided position. The upside is that this position would then be profitable if prices move in our favour; the downside is the uncontrolled directional risk.

3. **Backtester limitations:** The fill mechanics in `prosperity4btx` may differ from the official platform. In particular, HP's HS=15 parameter is explicitly tuned to the backtester's fill behaviour (resting orders fill at their price from market trades). The same parameter might underperform on the real platform if it uses different matching logic.

4. **Day 1 variance:** Day 1 PnL (42,822) was much lower than days 0 and 2 (>60k each). HP contributed only 31k on day 1 vs 44–64k on others. This suggests HP's profitability is sensitive to the specific path of prices during the day — if there aren't enough large market trades reaching our ±15 quotes, HP underperforms significantly.
