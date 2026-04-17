#!/usr/bin/env python3
"""
Build a simulated MAF (Market Access Fee) dataset for Round 2.

MAF mechanics (from the rules):
- Adds 25% more quotes to the order book
- New levels are inserted BETWEEN existing levels at prices fitting the distribution
- Volumes fit the existing distribution

Strategy:
- Need +0.82 levels/tick to reach 125% of current levels (~3.28 → 4.10)
- Insert extra levels between L1 and L2 on both bid and ask sides
- When L1-L2 gap is ≥ 2: insert at L1 ± 1 (one tick inside L1, one tick outside)
- Volume: sampled from L1 volume distribution (smaller than L2)
- Probability of insertion per tick: ~82% to hit the target of +0.82 levels/tick
"""

import os
import numpy as np
import pandas as pd
from collections import defaultdict

np.random.seed(42)

SRC_DIR = "data/round2"
DST_DIR = "data/round2_maf_v2"
ROUND   = 2
DAYS    = [-1, 0, 1]

# Insertion probability per tick per side (to get ~0.82 extra levels/tick total)
# 0.82 / 2 sides ≈ 0.41 per side
INSERT_PROB = 0.41

def sample_volume(l1_vol, l2_vol, rng):
    """Sample a plausible volume for the new inserted level."""
    # New level is between L1 and L2, so volume fits between them
    # Use the smaller of the two as a rough upper bound, with some noise
    base = min(l1_vol, l2_vol) if l2_vol else l1_vol
    # Slightly smaller than existing L1 since it's a less competitive quote
    vol = max(1, int(base * rng.uniform(0.5, 1.0)))
    return vol

def insert_level_bid(row, rng):
    """Insert an extra bid level between L1 and L2."""
    b1p = row.get('bid_price_1')
    b1v = row.get('bid_volume_1')
    b2p = row.get('bid_price_2')
    b2v = row.get('bid_volume_2')

    if pd.isna(b1p) or pd.isna(b1v):
        return row

    gap = int(b1p - b2p) if pd.notna(b2p) else 3

    # Only insert if there's room (gap >= 2)
    if gap < 2:
        return row

    # New level at L1 - 1 (one tick below L1, above L2)
    new_price = int(b1p) - 1
    new_vol   = sample_volume(b1v, b2v, rng)

    # Shift: existing L2 becomes L3, new level becomes L2
    row = dict(row)
    if pd.notna(b2p):
        row['bid_price_3']  = b2p
        row['bid_volume_3'] = b2v
    row['bid_price_2']  = new_price
    row['bid_volume_2'] = new_vol

    return row

def insert_level_ask(row, rng):
    """Insert an extra ask level between L1 and L2."""
    a1p = row.get('ask_price_1')
    a1v = row.get('ask_volume_1')
    a2p = row.get('ask_price_2')
    a2v = row.get('ask_volume_2')

    if pd.isna(a1p) or pd.isna(a1v):
        return row

    gap = int(a2p - a1p) if pd.notna(a2p) else 3

    if gap < 2:
        return row

    # New level at L1 + 1 (one tick above L1, below L2)
    new_price = int(a1p) + 1
    new_vol   = sample_volume(a1v, a2v, rng)

    row = dict(row)
    if pd.notna(a2p):
        row['ask_price_3']  = a2p
        row['ask_volume_3'] = a2v
    row['ask_price_2']  = new_price
    row['ask_volume_2'] = new_vol

    return row

def build_maf_prices(src_path, dst_path, rng):
    """Process a prices CSV and insert MAF extra levels."""
    df = pd.read_csv(src_path, sep=';')
    rows_out = []

    for _, row in df.iterrows():
        r = row.to_dict()

        # Independently decide whether to insert on each side
        if rng.random() < INSERT_PROB:
            r = insert_level_bid(r, rng)
        if rng.random() < INSERT_PROB:
            r = insert_level_ask(r, rng)

        rows_out.append(r)

    out = pd.DataFrame(rows_out, columns=df.columns)
    out.to_csv(dst_path, sep=';', index=False, float_format='%g')

def build_maf_trades(src_path, dst_path):
    """Trades: copy unchanged (trade data reflects fills, not book depth)."""
    import shutil
    shutil.copy2(src_path, dst_path)

def main():
    os.makedirs(f"{DST_DIR}/round{ROUND}", exist_ok=True)  # not needed
    os.makedirs(DST_DIR, exist_ok=True)
    rng = np.random.default_rng(42)

    total_orig, total_maf = 0, 0

    for day in DAYS:
        price_src = f"{SRC_DIR}/prices_round_{ROUND}_day_{day}.csv"
        trade_src = f"{SRC_DIR}/trades_round_{ROUND}_day_{day}.csv"
        price_dst = f"{DST_DIR}/prices_round_{ROUND}_day_{day}.csv"
        trade_dst = f"{DST_DIR}/trades_round_{ROUND}_day_{day}.csv"

        build_maf_prices(price_src, price_dst, rng)
        build_maf_trades(trade_src, trade_dst)

        # Count levels before/after
        orig = pd.read_csv(price_src, sep=';')
        maf  = pd.read_csv(price_dst, sep=';')
        level_cols = [c for c in orig.columns if 'price' in c and ('bid' in c or 'ask' in c)]

        o_levels = orig[level_cols].notna().sum().sum()
        m_levels = maf[level_cols].notna().sum().sum()
        total_orig += o_levels
        total_maf  += m_levels
        print(f"  Day {day:>2}: {o_levels:>7,} → {m_levels:>7,} levels (+{m_levels-o_levels:,}, "
              f"{(m_levels/o_levels-1)*100:.1f}%)")

    pct = (total_maf / total_orig - 1) * 100
    print(f"\n  Total: {total_orig:,} → {total_maf:,} levels (+{total_maf-total_orig:,}, {pct:.1f}%)")
    print(f"  Output: {DST_DIR}/")

    # Show a sample comparison
    print("\n  Sample tick (day 0, product ACO):")
    orig = pd.read_csv(f"{SRC_DIR}/prices_round_{ROUND}_day_0.csv", sep=';')
    maf  = pd.read_csv(f"{DST_DIR}/prices_round_{ROUND}_day_0.csv", sep=';')
    aco_orig = orig[orig['product']=='ASH_COATED_OSMIUM'].iloc[5]
    aco_maf  = maf[maf['product']=='ASH_COATED_OSMIUM'].iloc[5]
    for label, row in [("  Orig", aco_orig), ("  MAF ", aco_maf)]:
        bids = [(int(row[f'bid_price_{i}']), int(row[f'bid_volume_{i}']))
                for i in [1,2,3] if pd.notna(row.get(f'bid_price_{i}'))]
        asks = [(int(row[f'ask_price_{i}']), int(row[f'ask_volume_{i}']))
                for i in [1,2,3] if pd.notna(row.get(f'ask_price_{i}'))]
        print(f"    {label}  bids={bids}  asks={asks}")

if __name__ == '__main__':
    main()
