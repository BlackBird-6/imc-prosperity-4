# Round 4 Counterparty Analysis

3 days of data. `sp` = fill position within bid-ask spread (0.00 = at bid, 0.50 = mid, 1.00 = at ask).

---

## Quick reference

| Trader | Products | Net bias | Role summary |
|--------|----------|----------|--------------|
| Mark 01 | VEV options (OTM), VEV | Long vol / neutral VEV | Passive option buyer, VEV two-sided |
| Mark 22 | VEV options (all strikes), VEV, HP | Short vol / net VEV seller | Option writer, primary liquidity source |
| Mark 14 | HP, VEV, VEV_4000 | Balanced | HP and VEV market maker |
| Mark 38 | HP, VEV_4000 | Balanced | HP and VEV_4000 taker against Mark 14 |
| Mark 55 | VEV | Balanced | VEV two-sided taker (very active) |
| Mark 49 | VEV | Net seller (6:1 vol ratio) | Block VEV seller |
| Mark 67 | VEV | Pure buyer (never sells) | Directional VEV accumulator |

---

## Mark 01 — Option Vol Buyer

**Counterparties:** all options exclusively against Mark 22. VEV two-sided (buys from/sells to Mark 55, Mark 14, Mark 22).

### Options (buy only — never sells)

| Strike | Trades | Total vol | Avg qty | Avg price | Dev from mid | Fill position | Avg interval |
|--------|--------|-----------|---------|-----------|--------------|---------------|--------------|
| VEV_5200 | 11 | 34 | 3.1 | 65.4 | −1.0 | bid (0.00) | 76,000 ticks |
| VEV_5300 | 132 | 439 | 3.3 | 35.9 | −0.9 | bid (0.00) | 22,600 ticks |
| VEV_5400 | 263 | 911 | 3.5 | 11.1 | −0.6 | bid (0.00) | 11,400 ticks |
| VEV_5500 | 299 | 1,042 | 3.5 | 3.85 | −0.5 | bid (0.00) | 10,000 ticks |
| VEV_6000 | 317 | 1,105 | 3.5 | 0.00 | — | — | 9,500 ticks |
| VEV_6500 | 317 | 1,105 | 3.5 | 0.00 | — | — | 9,500 ticks |

**Always buys at sp=0.00 (bid).** Mark 01 posts passive bids at the market bid; Mark 22 hits them.

**Frequency increases with how far OTM**: buys VEV_6000/6500 nearly every ~9500 ticks (every ~95 seconds) at price zero. Buys VEV_5200 only ~11 times total. This is a vol/lottery-ticket accumulation strategy.

**VEV (two-sided):** 260 buys / 244 sells, avg qty 5.5–5.6, buy at bid (sp=0.00), sell at ask (sp=1.00). Uniformly distributed across the day (34/33/34% early/mid/late). Acts as a balanced VEV dealer alongside VEV option activity — likely hedging delta.

---

## Mark 22 — Option Writer (Primary Liquidity Source)

**Counterparties:** sells options to Mark 01 (1,339), Mark 14 (83), Mark 38 (17). Also sells VEV. Tiny HP presence.

### Options (mostly sells)

| Strike | Buy trades | Buy vol | Sell trades | Sell vol | Avg sell price | Dev from mid | Fill sp |
|--------|-----------|---------|------------|---------|----------------|--------------|---------|
| VEV_5200 | 1 | 3 | 46 | 159 | 75.6 | −0.93 | 0.04 |
| VEV_5300 | 1 | 3 | 163 | 545 | 36.6 | −0.87 | 0.01 |
| VEV_5400 | 0 | 0 | 276 | 959 | 11.2 | −0.59 | 0.00 |
| VEV_5500 | 0 | 0 | 306 | 1,069 | 3.89 | −0.53 | 0.00 |
| VEV_6000 | 0 | 0 | 317 | 1,105 | 0.00 | — | — |
| VEV_6500 | 0 | 0 | 317 | 1,105 | 0.00 | — | — |

Sells all strikes at sp≈0.00 (bid price). **Mark 22 is posting asks at the bid level** — it is a passive ask-poster that undercuts the spread. This is how it matches with Mark 01's passive bids: both are quoting at the same tight price.

Deep ITM strikes (VEV_4000/4500/5000/5100): tiny 3-lot one-off trades, very rarely (avg interval ~966k ticks = once per day). These appear to be calibration/initialization trades.

**VEV:** Net seller (25 buys / 101 sells). Sells at sp=0.87 (near ask), avg size 6.9. Likely delta-hedging short option book. Counterparties: Mark 55 (32), Mark 67 (75), Mark 49 (19).

---

## Mark 14 — HP and VEV Market Maker

**Counterparties:** HP almost entirely against Mark 38 (1,003 trades). VEV against Mark 55 (647). Options (small) against Mark 22.

### HYDROGEL_PACK

| Side | Trades | Total vol | Avg qty | Avg price | Dev from mid | Fill sp |
|------|--------|-----------|---------|-----------|--------------|---------|
| Buy  | 496 | 1,989 | 4.0 | 9,987.8 | −8.0 | 0.00 (bid) |
| Sell | 507 | 2,033 | 4.0 | 10,000.5 | +7.9 | 1.00 (ask) |

**Buys at bid (9,988), sells at ask (10,000.5). Spread = ~12.7 ticks.** This defines the passive HP book. Mark 14 IS the HP order book — it posts bids at ~9,988 and asks at ~10,000. Avg interval 2,980 ticks; uniform timing (34/33/34%). Perfectly balanced per day (Day 1: 1,359B/1,251S; Day 2: 1,113B/1,268S; Day 3: 1,278B/1,277S).

### VELVETFRUIT_EXTRACT

| Side | Trades | Total vol | Avg qty | Avg price | Dev from mid | Fill sp |
|------|--------|-----------|---------|-----------|--------------|---------|
| Buy  | 316 | 1,761 | 5.6 | 5,244.6 | −2.4 | 0.00 (bid) |
| Sell | 331 | 1,763 | 5.3 | 5,249.7 | +2.5 | 1.00 (ask) |

Same pattern as HP — Mark 14 buys at bid, sells at ask, nearly balanced. Spread ~5 ticks. Acts as a VEV maker alongside Mark 55.

### VEV_4000 (options)

| Side | Trades | Total vol | Avg qty | Avg price | Dev from mid | Fill sp |
|------|--------|-----------|---------|-----------|--------------|---------|
| Buy  | 232 | 458 | 2.0 | 1,237.7 | −10.5 | 0.00 (bid) |
| Sell | 207 | 412 | 2.0 | 1,257.0 | +10.4 | 1.00 (ask) |

Mark 14 also makes a market in VEV_4000 — avg spread of 20.8 ticks. Balanced, two-sided. This is paired with Mark 38 (439 direct trades).

---

## Mark 38 — HP Taker / Mark 14 Counterparty

**Counterparties:** HP entirely against Mark 14 (1,003 trades). VEV_4000 almost entirely against Mark 14 (439 trades).

### HYDROGEL_PACK

| Side | Trades | Total vol | Avg qty | Avg price | Dev from mid | Fill sp |
|------|--------|-----------|---------|-----------|--------------|---------|
| Buy  | 515 | 2,065 | 4.0 | 10,000.5 | +7.9 | 1.00 (ask) |
| Sell | 507 | 2,031 | 4.0 | 9,988.1 | −7.9 | 0.00 (bid) |

**Exact mirror of Mark 14.** Mark 38 lifts Mark 14's ask at 10,000.5 and hits Mark 14's bid at 9,988. It is a taker — every trade crosses the spread. Combined fill rate: avg interval 2,926 ticks; uniform timing. Per-day volumes match Mark 14 closely (D1: 745/740, D2: 658/586, D3: 662/705).

### VEV_4000

Same mirror structure: Mark 38 buys at sp=1.00 (avg 1,256.8) and sells at sp=0.00 (avg 1,237.7), perfectly inverted from Mark 14.

**What this means:** Mark 38 does not add directional information. It absorbs Mark 14's quotes. Any order we post in HP that is better than Mark 14's level will be filled by Mark 38 crossing through to our price.

---

## Mark 49 — Block VEV Seller

**Counterparties:** primarily Mark 67 (89 trades), also Mark 55 (14) and Mark 22 (19).

### VELVETFRUIT_EXTRACT

| Side | Trades | Total vol | Avg qty | Avg price | Dev from mid | Fill sp |
|------|--------|-----------|---------|-----------|--------------|---------|
| Buy  | 17 | 115 | 6.8 | 5,247.7 | −1.5 | −0.07 |
| Sell | 105 | 1,071 | **10.2** | 5,249.7 | +0.7 | 0.99 (ask) |

**Sells at the ask (sp=0.99) in large blocks of ~10 per trade.** This is the biggest single-trade seller in VEV. Avg interval 24,600 ticks — trades ~40 times per day. Net sell vol per day: D1 342, D2 400, D3 329. Consistent across all 3 days.

Fills are clustered early and late in the day (36% early, 39% late, only 25% midday) — slightly active at open and close.

Spread at time of trade is only 1.5 ticks — trades in a tight book, suggesting it reacts to market conditions rather than forcing trades when the spread is wide.

---

## Mark 55 — VEV Two-Sided Taker

**Counterparties:** buys from Mark 14, Mark 22, Mark 01, Mark 49. Sells to Mark 01, Mark 49, Mark 14, Mark 22, Mark 67.

### VELVETFRUIT_EXTRACT

| Side | Trades | Total vol | Avg qty | Avg price | Dev from mid | Fill sp |
|------|--------|-----------|---------|-----------|--------------|---------|
| Buy  | 598 | 3,254 | 5.4 | 5,250.2 | +2.5 | 1.00 (ask) |
| Sell | 600 | 3,297 | 5.5 | 5,245.0 | −2.5 | 0.00 (bid) |

**Most active VEV bot.** Avg interval 2,499 ticks (trades every ~25 seconds). Perfectly balanced across all 3 days (D1: 1,011B/1,098S; D2: 1,190B/1,099S; D3: 1,053B/1,100S).

Buys at the ask (sp=1.00) and sells at the bid (sp=0.00) — it is an aggressive taker, always crossing the spread. **Mark 55 pays the spread on every trade.** This is unusual for a balanced bot.

Avg spread at time of trade = 5.0 ticks. Each round-trip costs Mark 55 ~5 ticks = ~0.1% of VEV value. At 3,254+3,297=6,551 vol total, that's roughly 6,551 × 2.5 = ~16,400 ticks of spread paid. Mark 55 is not a profit-seeking market maker — it behaves like a liquidity buffer or vol-neutral arbitrage engine.

**Implication for hedging:** Mark 55 is reliably present and always willing to take the other side of VEV delta hedges. When we need to buy VEV to reduce short delta, Mark 55 is likely already posting bids we can cross.

---

## Mark 67 — Directional VEV Accumulator

**Counterparties:** Mark 49 (89 trades), Mark 22 (75 trades), Mark 55 (1 trade).

### VELVETFRUIT_EXTRACT

| Side | Trades | Total vol | Avg qty | Avg price | Dev from mid | Fill sp |
|------|--------|-----------|---------|-----------|--------------|---------|
| Buy  | 165 | 1,510 | **9.2** | 5,249.3 | +0.8 | 0.99 (ask) |
| Sell | 0 | 0 | — | — | — | — |

**Pure accumulator — never sells.** Buys 9.2 units per trade at the ask (sp=0.99). Avg interval 18,134 ticks. Per-day volumes: D1 519, D2 567, D3 424 — slightly declining over the 3 days.

Timing is slightly back-weighted (35% early, 28% mid, 38% late). Spread at trade = 1.6 ticks — trades in a very tight VEV book, suggesting it may be finding windows of thin liquidity to accumulate.

**Mark 67 is paired with Mark 49:** 89 of Mark 67's 165 trades are directly against Mark 49. Mark 22 provides the remaining liquidity (75 trades). These two bots appear designed to clear inventory against each other.

Forward price signal: avg VEV change 50k ticks after Mark 67 buys = **+1.7 ticks**. Weak positive signal but consistent across days.

---

## Cross-bot structure summary

### HP: entirely a two-bot market
Mark 14 quotes, Mark 38 takes. All 1,003 HP trades in the dataset are between these two. Our HP strategy competes directly with Mark 14's quotes (~9,988 bid / ~10,000.5 ask). To get passive fills we need to improve on those levels.

### Options: Mark 01 ↔ Mark 22 own the market
1,339 of ~1,878 total option trades flow between these two. Mark 22 writes, Mark 01 absorbs. Both operate at the bid price (sp≈0). Occasional spill to Mark 14 and Mark 38 for large ITM strikes.

### VEV: layered liquidity
- Mark 55: always there, thin spread, taker (5 ticks spread, avg interval 2,500 ticks) — reliable hedge counterparty
- Mark 14: maker at ±2.4 ticks from mid — tighter than Mark 55
- Mark 49: block seller (~10/trade), periodic, 24,600 tick intervals
- Mark 67: block buyer (~9/trade), one-directional, 18,100 tick intervals
- Mark 22: occasional VEV seller for delta hedging short options book

### Implied strategy edges
1. **HP**: post inside Mark 14's spread (bid > 9,988, ask < 10,000.5). Mark 38 will cross through to fill us.
2. **Options**: Mark 22 quotes at bid. We take when BS fair > ask + edge. Our passive bids will sit alongside Mark 01's and fill from Mark 22.
3. **VEV hedge**: Mark 55 almost always fillable within 2,500 ticks. No need to hedge immediately — can wait for a natural crossing.
4. **Deep OTM (VEV_6000/6500)**: Mark 01 buys at 0, Mark 22 sells at 0. No edge — skip.
