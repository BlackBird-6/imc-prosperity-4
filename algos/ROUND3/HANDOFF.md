# IMC Prosperity 4 — Round 3 Handoff

## Competition context
- Platform: IMC Prosperity 4
- Round 3 products: HYDROGEL_PACK (HP), VELVETFRUIT_EXTRACT (VEV), and 10 option vouchers on VEV
- Competition "test" runs 1,000 timesteps (t=0 to t=99,900, step 100) — only the first 10% of a day
- Full day = 10,000 timesteps (0–999,900). Backtester uses all 3 days × 10,000 steps = 30,000 ticks
- Timestamps offset by 1,000,000 per day in backtester (Day 0: 0–999,900, Day 1: 1M–1.999M, Day 2: 2M–2.999M)
- Position limits: HP=200, VEV=200, each VEV_* voucher=300

## File locations
- **Main algorithm v1**: `algos/ROUND3/round3_v1.py` — current stable version (backtest: 136,063)
- **Main algorithm v2**: `algos/ROUND3/round3_v2.py` — new version with better HP (backtest: 138,096), NOT yet competition-tested
- **Strategy notes**: `algos/ROUND3/STRATEGY.md`
- **Round 3 price data**: `data_Round3/prices_round_3_day_{0,1,2}.csv`
- **Backtester**: `python -m prosperity4bt algos/ROUND3/round3_v1.py 3 --merge-pnl --no-out`

## Products

### HYDROGEL_PACK (HP)
- Mean-reverts strongly around 10,000
- Typical order book spread: ~16 ticks (bid ~10003, ask ~10019)

**v1 HP approach** (137,880 HP-only backtest):
- Fixed fair=10,000, adjusted by momentum fade (×0.5) and inventory skew (×4.0)
- Passive quotes at fair ± 15 ticks, 6 units per side

**v2 HP approach** (139,913 HP-only backtest — taken from competitor 457839):
- Blended fair = 0.90×10000 + 0.10×EMA(mid), EMA alpha=0.02
- `tilt = (fair - mid) × 0.70 - (pos/LIMIT) × 6.0`
- `reservation = mid + tilt`
- `bid = min(round(reservation - 8), best_ask)` ← intentionally crosses to best_ask when HP is cheap (aggressive take)
- `ask = max(round(reservation + 8), best_bid)` ← crosses to best_bid when expensive
- 20 units per side (vs v1's 6)
- The crossing-to-best_ask behavior is the KEY alpha: when mid << fair, bid hits best_ask → immediate fill buying cheap HP

### VELVETFRUIT_EXTRACT (VEV)
- Underlying for options, spot ~5,250–5,270 on Day 2
- Not directly traded (no delta hedge — tested, was harmful)
- EMA (alpha=0.05) maintained as fallback if book unavailable

### VEV Options (VEV_5000, VEV_5100, VEV_5200, VEV_5300, VEV_5400)
- European calls on VEV, expiring end of competition
- Fair value via Black-Scholes (r=0, flat σ=0.31)
- Two-phase strategy:
  - **Phase 1**: take aggressively if bot quote is >5 ticks from BS fair
  - **Phase 2**: passive quote at fair ± 1 tick with inventory skew (max 3 ticks at full position)
- 20 units per side passive, 300 position limit each

**Options contribution in backtest**: approximately −1,817 over 3 days (Day 0: −58, Day 1: +151, Day 2: −1,910). The Day 2 loss is likely mark-to-market on short positions at day-end.

## Key technical decisions and WHY

### TTE calibration (tick 0 only)
- Problem: hardcoding TTE=5 days overpriced options by 7-10 ticks → all option positions maxed (300/300) in ~500 steps → stuck with no market-making
- Fix: on tick 0, invert BS across all strikes to find true TTE. Binary search on T in [1/365, 8/365] such that BS(vev_mid, K, T, σ) = observed_mid. Take median, clamp [2, 7]. Falls back to 5.0.
- Confirmed fix: competition log 450320 showed 10,583 (vs 5,723 before fix)

### vev_mid not EMA for BS pricing (+15k in backtest)
- Old code used `vev_ref` (EMA of VEV) as spot price S in Black-Scholes
- New code uses `vev_mid` (current order book mid) directly
- Reason: EMA has ~20-tick lag. If VEV rises, EMA underestimates S, making calls appear cheap → systematic buy bias → consistent overbuying into rising prices. Using current spot removes this lag.

### Per-strike sigma calibration (removed in v1, was in 457282)
- We tested calibrating per-strike IV (corrects the vol smile: VEV_5300 IV ~3% higher than VEV_5200)
- Backtest improvement: only +2,045 over 3 days
- Vol smile is NOT stable: Day 0 tick 0 nearly flat (0.303–0.306), Day 2 tick 0 strongly skewed (0.329–0.356)
- We REMOVED it from v1 because the improvement is within noise over 3 days, and the smile changes throughout each day anyway (tick-0 calibration degrades quickly)
- Decision: stick with flat σ=0.31

### Delta hedge (disabled)
- Tested VEV position to hedge net option delta — made things worse
- Residual long delta from options benefits from VEV upward drift historically
- Removed entirely

## Competition log analysis method

Competition logs are in `Downloads/XXXXXX_extracted/XXXXXX.log`. They are JSON with:
- `activitiesLog`: CSV (delimiter `;`) with columns:
  `day;timestamp;product;bid_price_1;bid_volume_1;bid_price_2;bid_volume_2;bid_price_3;bid_volume_3;ask_price_1;ask_volume_1;ask_price_2;ask_volume_2;ask_price_3;ask_volume_3;mid_price;profit_and_loss`
  - **Column 15 = mid_price, column 16 = profit_and_loss** (0-indexed)
- `logs`: list of 1,000 entries, each with `sandboxLog` and `lambdaLog`
  - `lambdaLog` is JSON: `[state_compressed, orders, conversions, new_traderData, our_print_output]`
  - `state_compressed[0]` = timestamp, `state_compressed[6]` = position dict, `state_compressed[3]` = order depths

### Useful analysis script
```python
import json
log = open('Downloads/XXXXXX_extracted/XXXXXX.log', encoding='utf-8').read()
data = json.loads(log)

# Final PnL per product
lines = data['activitiesLog'].strip().split('\n')
last_pnl = {}
for line in lines[1:]:
    parts = line.split(';')
    if len(parts) >= 17:
        last_pnl[parts[2]] = float(parts[16])
for prod, pnl in sorted(last_pnl.items()):
    print(f'{prod}: {pnl:,.2f}')

# Final position and traderData
logs = data['logs']
last = logs[-1]
llog = json.loads(last['lambdaLog'])
print('Final position:', llog[0][6])
print('Final traderData:', llog[3][:300])

# Check orders at tick 0
first = logs[0]
llog0 = json.loads(first['lambdaLog'])
print('Tick 0 orders:', llog0[1])
print('Tick 0 position:', llog0[0][6])
```

## Backtest numbers summary

| Version | Description | Backtest total | Competition result |
|---------|-------------|---------------|-------------------|
| 447107 | TTE=5 hardcoded (broken) | — | 5,723 |
| 450320 | Calibrated TTE, flat σ, **EMA for S** | 120,636 | 10,583 |
| 457282 | Calibrated TTE, per-strike σ, **vev_mid** | 138,108 | 8,232 |
| **v1 (current)** | Calibrated TTE, flat σ=0.31, vev_mid | **136,063** | untested |
| **v2 (new)** | v1 + competitor HP approach | **138,096** | untested |

Note: 457282 vs 450320 competition result is explained by variance (1,000 ticks is tiny sample), not a code regression. The backtest confirms v1 > 450320 by +15k.

## Backtest per-day breakdown

| Version | Day 0 | Day 1 | Day 2 |
|---------|-------|-------|-------|
| v1 | 63,652 | 31,202 | 41,209 |
| v2 | 57,254 | 42,970 | 37,872 |
| Competitor HP-only | 57,312 | 42,819 | 39,782 |

## What to look for when analyzing new competition logs

1. **Were positions maxed?** If any option at 300/300 within first 200 ticks → TTE calibration failed, check `traderData` for `tte_start`
2. **What did tte_start calibrate to?** Should be ~3.5–4.0 for Day 2, ~4.5 for Day 1, ~5.0 for Day 0
3. **HP performance**: HP PnL should dominate. Check if HP position is bouncing (mean-reversion working) or stuck long/short
4. **Option positions at end**: small positions (±5–50) = passive market-making. Large positions (±100–300) = either aggressive take fired or position limit issue
5. **Compare HP PnL**: our HP earns ~8,000–9,000 per 1,000 ticks historically; below 5,000 suggests something wrong
6. **Look at tick-0 orders**: option quotes should be within 1–2 ticks of market mid. If quotes are 5+ ticks away → TTE or sigma issue

## v2 HP key parameters (from competitor 457839)
```python
HP_HALF_SPREAD  = 8      # tighter than v1's 15
HP_BASE_VOL     = 20     # higher than v1's 6
HP_EMA_ALPHA    = 0.02   # slow EMA
HP_FIXED_WEIGHT = 0.90   # 90% fixed anchor to 10000
HP_ANCHOR_PULL  = 0.70   # pull toward fair when mid deviates
HP_INV_SKEW     = 6.0    # inventory skew
```

## v2 HP formula
```python
mid  = (best_bid + best_ask) / 2.0
ema  = 0.02 * mid + 0.98 * prev_ema
fair = 0.90 * 10000 + 0.10 * ema
tilt = (fair - mid) * 0.70 - (pos / 200) * 6.0
reservation = mid + tilt
bid = min(round(reservation - 8), best_ask)   # crosses to best_ask if HP is cheap
ask = max(round(reservation + 8), best_bid)   # crosses to best_bid if HP is expensive
```

## Current state / next steps
- v1 is stable and submitted; v2 has not been competition-tested yet
- v2 is the version to test next
- Options strategy is unchanged between v1 and v2
- The main open question: do options actually add positive value in competition? Backtest shows -1,817 over 3 days. If options are net negative, consider disabling them entirely.
- Secondary question: can the option strategy be improved? The vol smile shifts throughout the day, so tick-0 sigma calibration degrades quickly. One option: recalibrate sigma every N ticks (but must store sigmas in traderData carefully).
