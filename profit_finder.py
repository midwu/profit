"""
profit_finder.py

Finds profitable two-party flips between shops: buy low from one shop,
sell high to another.

Stock allocation: a naive merge lets one seller's stock get "used" by
every buyer it matches, and vice versa, which inflates the summed
Total_Profit far past what's actually achievable. This version allocates
each shop's stock greedily (highest profit-per-item first) so no unit of
stock is counted toward more than one trade. It's a heuristic, not a
provably-optimal assignment, but it removes the double-counting.

Same-owner buy/sell mismatches (a player's own buy order paying more
than their own sell order) are intentionally excluded here — those
aren't limited by stock at all, since you can farm/grind the item
yourself. See self_flip_finder.py for those.

Also outputs:
  - best_trade_per_item.csv   the single most profitable trade for each item
  - top_trades_readable.txt   a short list (--top-n) of the very best trades

And supports (see --help for all flags):
  --min-total-profit   drop trades below a total-profit floor, not just per-item
  --max-age-hours      optionally drop listings older than N hours (off by default)
  --limit              cap how many rows go into the main CSV/TXT outputs
"""

import argparse
from pathlib import Path

import pandas as pd

from data_loader import load_shop_data

# ========== CONFIG DEFAULTS (all overridable via CLI flags, see --help) ==========
DEFAULT_INPUT_FILE = "shop_data.csv"
DEFAULT_MIN_PROFIT_PER_ITEM = 0.01
IGNORE_ITEMS_FILE = "ignore_items.txt"
IGNORE_OWNERS_FILE = "ignore_owners.txt"
IGNORE_WARPS_FILE = "ignore_warps.txt"
OUTPUT_CSV = "profitable_trades.csv"
OUTPUT_TXT = "profitable_trades_readable.txt"
OUTPUT_CANNOT_FLIP = "items_cannot_flip.txt"
OUTPUT_CAN_FLIP = "items_can_flip.txt"
OUTPUT_BEST_PER_ITEM = "best_trade_per_item.csv"
OUTPUT_TOP_TRADES = "top_trades_readable.txt"
# ===================================================================================


def parse_args():
    p = argparse.ArgumentParser(description="Find profitable shop-to-shop flips.")
    p.add_argument("--input", default=DEFAULT_INPUT_FILE,
                    help="Path to shop_data.csv. Relative or absolute, both work (default: %(default)s)")
    p.add_argument("--min-profit", type=float, default=DEFAULT_MIN_PROFIT_PER_ITEM,
                    help="Minimum profit PER ITEM to report (default: %(default)s)")
    p.add_argument("--min-total-profit", type=float, default=0.0,
                    help="Minimum TOTAL profit (per-item profit x quantity) to report (default: %(default)s)")
    p.add_argument("--max-age-hours", type=float, default=None,
                    help="Drop listings older than this many hours, measured from the newest "
                         "timestamp in the file. Off by default — nothing is excluded on age unless set.")
    p.add_argument("--top-n", type=int, default=30,
                    help="How many trades go in the short top_trades_readable.txt (default: %(default)s)")
    p.add_argument("--limit", type=int, default=None,
                    help="Cap how many rows are written to the main CSV/TXT outputs (default: no cap)")
    p.add_argument("--include-inactive", action="store_true",
                    help="Include shops not marked Active (default: active-only)")
    p.add_argument("--ignore-items", default=IGNORE_ITEMS_FILE, help="Path to ignore-items list")
    p.add_argument("--ignore-owners", default=IGNORE_OWNERS_FILE, help="Path to ignore-owners list")
    p.add_argument("--ignore-warps", default=IGNORE_WARPS_FILE, help="Path to ignore-warps list")
    return p.parse_args()


def load_ignore_list(filepath: str) -> set:
    if Path(filepath).exists():
        with open(filepath, "r", encoding="utf-8") as f:
            items = {line.strip() for line in f if line.strip()}
        print(f"Loaded {len(items)} entries from {filepath}")
        return items
    print(f"No {filepath} found → nothing ignored from this list")
    return set()


def allocate_stock(candidates: pd.DataFrame) -> pd.DataFrame:
    """
    Greedily allocate seller/buyer stock across candidate trades, highest
    profit-per-item first, so no unit of stock is double-counted.
    """
    if candidates.empty:
        return candidates.assign(Quantity=pd.Series(dtype=int))

    candidates = candidates.sort_values("Profit_Per_Item", ascending=False)

    remaining_seller = dict(zip(candidates["Seller_ID"], candidates["Seller_Stock"]))
    remaining_buyer = dict(zip(candidates["Buyer_ID"], candidates["Buyer_Stock"]))

    rows = []
    for row in candidates.itertuples(index=False):
        s_left = remaining_seller[row.Seller_ID]
        b_left = remaining_buyer[row.Buyer_ID]
        qty = min(s_left, b_left)
        if qty <= 0:
            continue
        remaining_seller[row.Seller_ID] -= qty
        remaining_buyer[row.Buyer_ID] -= qty
        d = row._asdict()
        d["Quantity"] = int(qty)
        rows.append(d)

    if not rows:
        return candidates.iloc[0:0].assign(Quantity=pd.Series(dtype=int))

    return pd.DataFrame(rows)


def main():
    args = parse_args()

    ignore_items = load_ignore_list(args.ignore_items)
    ignore_owners = load_ignore_list(args.ignore_owners)
    ignore_warps = load_ignore_list(args.ignore_warps)

    df = load_shop_data(args.input)

    if not args.include_inactive:
        df = df[df["Status"] == "Active"].copy()

    if ignore_items:
        df = df[~df["Item"].isin(ignore_items)]
    if ignore_owners:
        df = df[~df["Shop Owner"].isin(ignore_owners)]
    if ignore_warps:
        df = df[~df["Warp"].isin(ignore_warps)]

    print(f"Rows remaining after filters: {len(df):,}")

    sellers = df[df["Action"] == "SELLING"].copy().reset_index(drop=True)
    buyers = df[df["Action"] == "BUYING"].copy().reset_index(drop=True)
    sellers["Seller_ID"] = sellers.index
    buyers["Buyer_ID"] = buyers.index

    sellers = sellers.rename(columns={
        "Shop Owner": "Seller", "Price": "Sell_Price", "Stock/Space": "Seller_Stock",
        "Warp": "Seller_Warp", "Shop Location": "Seller_Location", "Timestamp": "Seller_Timestamp",
    })[["Item", "Seller", "Sell_Price", "Seller_Stock", "Seller_Warp",
        "Seller_Location", "Seller_Timestamp", "Seller_ID"]]

    buyers = buyers.rename(columns={
        "Shop Owner": "Buyer", "Price": "Buy_Price", "Stock/Space": "Buyer_Stock",
        "Warp": "Buyer_Warp", "Shop Location": "Buyer_Location", "Timestamp": "Buyer_Timestamp",
    })[["Item", "Buyer", "Buy_Price", "Buyer_Stock", "Buyer_Warp",
        "Buyer_Location", "Buyer_Timestamp", "Buyer_ID"]]

    # --- Optional data-age filter (off unless --max-age-hours is set) ---
    if args.max_age_hours is not None:
        sellers["_seller_ts"] = pd.to_datetime(sellers["Seller_Timestamp"], errors="coerce")
        buyers["_buyer_ts"] = pd.to_datetime(buyers["Buyer_Timestamp"], errors="coerce")
        newest = max(sellers["_seller_ts"].max(), buyers["_buyer_ts"].max())
        cutoff = newest - pd.Timedelta(hours=args.max_age_hours)
        before_s, before_b = len(sellers), len(buyers)
        sellers = sellers[sellers["_seller_ts"] >= cutoff].drop(columns="_seller_ts")
        buyers = buyers[buyers["_buyer_ts"] >= cutoff].drop(columns="_buyer_ts")
        print(f"Age filter (<= {args.max_age_hours}h old, relative to newest timestamp {newest}): "
              f"kept {len(sellers)}/{before_s} sell listings, {len(buyers)}/{before_b} buy listings")

    candidates = sellers.merge(buyers, on="Item", how="inner")
    candidates = candidates[candidates["Seller"] != candidates["Buyer"]]  # self-flips: see self_flip_finder.py
    candidates = candidates[candidates["Buy_Price"] > candidates["Sell_Price"]].copy()
    candidates["Profit_Per_Item"] = candidates["Buy_Price"] - candidates["Sell_Price"]
    candidates = candidates[candidates["Profit_Per_Item"] >= args.min_profit]

    merged = allocate_stock(candidates)
    if len(merged):
        merged["Total_Profit"] = merged["Profit_Per_Item"] * merged["Quantity"]
        merged["Buy_Total"] = merged["Sell_Price"] * merged["Quantity"]   # = capital required for this trade
        merged["Sell_Total"] = merged["Buy_Price"] * merged["Quantity"]
        merged = merged[merged["Total_Profit"] >= args.min_total_profit]
        merged = merged.sort_values("Total_Profit", ascending=False).reset_index(drop=True)

    # ---------- Items that can / cannot be flipped for profit ----------
    all_items = set(df["Item"].unique())
    profitable_items = set(merged["Item"].unique()) if len(merged) else set()
    can_flip_items = sorted(profitable_items)
    cannot_flip_items = sorted(all_items - profitable_items)

    with open(OUTPUT_CAN_FLIP, "w", encoding="utf-8") as f:
        f.write("\n".join(can_flip_items))
    with open(OUTPUT_CANNOT_FLIP, "w", encoding="utf-8") as f:
        f.write("\n".join(cannot_flip_items))

    print(f"Items that can be flipped for profit: {len(can_flip_items)} → {OUTPUT_CAN_FLIP}")
    print(f"Items that cannot be flipped for profit: {len(cannot_flip_items)} → {OUTPUT_CANNOT_FLIP}")

    # ---------- Best trade per item (uses the FULL list, before --limit) ----------
    csv_cols = [
        "Item", "Quantity", "Sell_Price", "Buy_Price", "Profit_Per_Item", "Total_Profit",
        "Seller", "Seller_Warp", "Seller_Stock",
        "Buyer", "Buyer_Warp", "Buyer_Stock",
        "Seller_Location", "Buyer_Location",
        "Seller_Timestamp", "Buyer_Timestamp",
    ]
    if len(merged):
        best_per_item = merged.drop_duplicates(subset="Item", keep="first")  # already sorted by Total_Profit desc
    else:
        best_per_item = pd.DataFrame(columns=csv_cols)
    best_per_item[csv_cols].to_csv(OUTPUT_BEST_PER_ITEM, index=False)
    print(f"Best single trade per item: {len(best_per_item)} → {OUTPUT_BEST_PER_ITEM}")

    # ---------- Top trades shortlist (also from the FULL list) ----------
    top_trades = merged.head(args.top_n)
    top_lines = [
        f"Top {len(top_trades)} Trades (of {len(merged)} total opportunities)",
        "=" * 80, "",
    ]
    for i, row in top_trades.iterrows():
        top_lines.append(
            f"{i+1}. '{row['Item']}' x{row['Quantity']}: buy @ ${row['Sell_Price']:.2f} from "
            f"'{row['Seller']}' ({row['Seller_Warp']}) → sell @ ${row['Buy_Price']:.2f} to "
            f"'{row['Buyer']}' ({row['Buyer_Warp']})\n"
            f"    Capital required: ${row['Buy_Total']:.2f}  |  Total profit: ${row['Total_Profit']:.2f}"
        )
    with open(OUTPUT_TOP_TRADES, "w", encoding="utf-8") as f:
        f.write("\n".join(top_lines))
    print(f"Top {len(top_trades)} trades → {OUTPUT_TOP_TRADES}")

    # ---------- Save main files (respects --limit, if set) ----------
    merged_limited = merged.head(args.limit) if args.limit else merged
    merged_out = merged_limited[csv_cols] if len(merged_limited) else pd.DataFrame(columns=csv_cols)
    merged_out.to_csv(OUTPUT_CSV, index=False)

    lines = [
        "Profitable Trade Opportunities",
        f"Generated from: {args.input}",
        f"Total opportunities found: {len(merged)}"
        + (f" (showing top {args.limit})" if args.limit else ""),
        "=" * 80, "",
    ]
    for i, row in merged_limited.iterrows():
        text = (
            f"{i+1}. Purchase {row['Quantity']} '{row['Item']}' at ${row['Sell_Price']:.2f} each "
            f"(total: ${row['Buy_Total']:.2f}) from '{row['Seller']}' ({row['Seller_Warp']}),\n"
            f"   then sell {row['Quantity']} '{row['Item']}' at ${row['Buy_Price']:.2f} each "
            f"(total: ${row['Sell_Total']:.2f}) at '{row['Buyer']}' ({row['Buyer_Warp']})\n"
            f"   → Profit: ${row['Profit_Per_Item']:.2f} per item | Total profit: ${row['Total_Profit']:.2f}\n"
        )
        lines.append(text)
        lines.append("-" * 80)
    with open(OUTPUT_TXT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    # ========== SUMMARY STATISTICS ==========
    total_opportunities = len(merged)
    total_money = merged["Total_Profit"].sum() if total_opportunities else 0
    avg_profit = merged["Total_Profit"].mean() if total_opportunities else 0
    max_profit = merged["Total_Profit"].max() if total_opportunities else 0

    total_capital = merged["Buy_Total"].sum() if total_opportunities else 0

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Total profitable opportunities : {total_opportunities:,}")
    print(f"Total money that can be made    : ${total_money:,.2f}  (stock-allocated, not double-counted)")
    print(f"Total capital required (all)    : ${total_capital:,.2f}")
    print(f"Average profit per opportunity  : ${avg_profit:,.2f}")
    print(f"Highest single opportunity      : ${max_profit:,.2f}")
    print()
    for n in [10, 100, 1000, 10000]:
        if total_opportunities == 0:
            break
        top_n_sum = merged["Total_Profit"].head(n).sum()
        top_n_capital = merged["Buy_Total"].head(n).sum()
        print(f"Top {n:>5,} opportunities: profit ${top_n_sum:,.2f}  |  capital needed ${top_n_capital:,.2f}")
    print("=" * 60)
    print("\nFiles saved:")
    print(f"  {OUTPUT_CSV}")
    print(f"  {OUTPUT_TXT}")
    print(f"  {OUTPUT_BEST_PER_ITEM}")
    print(f"  {OUTPUT_TOP_TRADES}")
    print(f"  {OUTPUT_CAN_FLIP}")
    print(f"  {OUTPUT_CANNOT_FLIP}")


if __name__ == "__main__":
    main()