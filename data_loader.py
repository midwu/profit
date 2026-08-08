"""
data_loader.py

Shared CSV loading and validation for the profit-finder scripts.
Handles: missing file, empty file, malformed CSV, missing required
columns, and prices/stock values that don't parse cleanly as numbers
(e.g. "$35", "1,250.50", stray whitespace).
"""

import re
import sys
from pathlib import Path

import pandas as pd

REQUIRED_COLUMNS = [
    "Item", "Shop Owner", "Action", "Price",
    "Stock/Space", "Warp", "Shop Location", "Timestamp", "Status",
]

_NUMERIC_STRIP = re.compile(r"[^0-9.\-]")


def parse_numeric(value):
    """
    Convert a value like '$35', '1,250.50', ' 12 ' or 15 into a float.
    Returns None if it can't be parsed.
    """
    if pd.isna(value):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    cleaned = _NUMERIC_STRIP.sub("", str(value))
    if cleaned in ("", "-", "."):
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def load_ignore_list(filepath: str) -> set:
    """Load a plain-text, one-entry-per-line ignore list. Returns an empty set if the file doesn't exist."""
    path = Path(filepath)
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            items = {line.strip() for line in f if line.strip()}
        print(f"Loaded {len(items)} entries from {filepath}")
        return items
    print(f"No {filepath} found → nothing ignored from this list")
    return set()


def load_shop_data(filepath: str) -> pd.DataFrame:
    """
    Load and validate shop_data.csv. Exits with a clear message (instead
    of a raw traceback) on missing file, empty file, malformed CSV,
    missing required columns, or an all-bad-data result. Rows with an
    unparseable Price or Stock/Space are dropped and reported, not
    silently kept as NaN/garbage.
    """
    path = Path(filepath)
    if not path.exists():
        sys.exit(f"ERROR: '{filepath}' not found. Check the path and try again.")

    try:
        df = pd.read_csv(path)
    except pd.errors.EmptyDataError:
        sys.exit(f"ERROR: '{filepath}' is empty.")
    except pd.errors.ParserError as e:
        sys.exit(f"ERROR: '{filepath}' could not be parsed as CSV — {e}")

    df.columns = df.columns.str.strip()

    missing_cols = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing_cols:
        sys.exit(
            f"ERROR: '{filepath}' is missing required column(s): {missing_cols}\n"
            f"Found columns: {list(df.columns)}"
        )

    if len(df) == 0:
        sys.exit(f"ERROR: '{filepath}' has headers but no data rows.")

    # --- Robust Price parsing ---
    price_parsed = df["Price"].apply(parse_numeric)
    bad_price = price_parsed.isna()
    if bad_price.any():
        print(f"WARNING: {int(bad_price.sum())} row(s) had an unparseable Price and were dropped:")
        print(df.loc[bad_price, ["Item", "Shop Owner", "Price"]].to_string(index=False))
    df = df.loc[~bad_price].copy()
    df["Price"] = price_parsed.loc[~bad_price].astype(float)

    # --- Robust Stock/Space parsing ---
    stock_parsed = df["Stock/Space"].apply(parse_numeric)
    bad_stock = stock_parsed.isna()
    if bad_stock.any():
        print(f"WARNING: {int(bad_stock.sum())} row(s) had an unparseable Stock/Space and were dropped:")
        print(df.loc[bad_stock, ["Item", "Shop Owner", "Stock/Space"]].to_string(index=False))
    df = df.loc[~bad_stock].copy()
    df["Stock/Space"] = stock_parsed.loc[~bad_stock].astype(int)

    if len(df) == 0:
        sys.exit(f"ERROR: every row in '{filepath}' had an unparseable Price or Stock/Space — nothing to work with.")

    # --- Duplicate listing detection ---
    # Shop Location pins a shop+item+action to a physical spot, so the same
    # combo appearing twice means the scrape captured it more than once
    # (usually an updated re-scrape). Keep the newest Timestamp, drop the rest.
    dup_key = ["Shop Location", "Item", "Action"]
    df["_ts_sort"] = pd.to_datetime(df["Timestamp"], errors="coerce")
    before = len(df)
    df = (df.sort_values("_ts_sort", ascending=False)
            .drop_duplicates(subset=dup_key, keep="first")
            .drop(columns="_ts_sort"))
    n_dupes = before - len(df)
    if n_dupes:
        print(f"NOTE: {n_dupes} duplicate listing(s) found (same Shop Location + Item + Action) — kept the newest Timestamp for each.")

    return df.reset_index(drop=True)