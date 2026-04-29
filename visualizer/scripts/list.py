"""List all products grouped by category.

Usage: python scripts/list.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from _load import CATEGORIES

for cat, prods in CATEGORIES.items():
    print(f"\n{cat}")
    for p in prods:
        print(f"  {p}")
