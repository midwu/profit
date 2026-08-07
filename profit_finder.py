import pandas as pd
from pathlib import Path

# ========== CONFIG ==========
INPUT_FILE = "shop_data.csv"
OUTPUT_CSV = "profitable_trades.csv"
OUTPUT_TXT = "profitable_trades_readable.txt"
OUTPUT_CANNOT_FLIP = "items_cannot_flip.txt"
OUTPUT_CAN_FLIP = "items_can_flip.txt"

IGNORE_ITEMS_FILE = "ignore_items.txt"
IGNORE_OWNERS_FILE = "ignore_owners.txt"
IGNORE_WARPS_FILE = "ignore_warps.txt"

MIN_PROFIT_PER_ITEM = 0.01
ONLY_ACTIVE = True
# ============================

def load_ignore_list(filepath: str) -> set:
    if Path(filepath).exists():
        with open(filepath, "r", encoding="utf-8") as f:
            items = {line.strip() for line in f if line.strip()}
        print(f"Loaded {len(items)} entries from {filepath}")
        return items
    else:
        print(f"No {filepath} found → nothing ignored from this list")
        return set()

# --- Load all ignore lists ---
ignore_items = load_ignore_list(IGNORE_ITEMS_FILE)
ignore_owners = load_ignore_list(IGNORE_OWNERS_FILE)
ignore_warps = load_ignore_list(IGNORE_WARPS_FILE)

# --- Load data ---
df = pd.read_csv(INPUT_FILE)
df.columns = df.columns.str.strip()

if ONLY_ACTIVE:
    df = df[df["Status"] == "Active"].copy()

# Apply all filters
if ignore_items:
    df = df[~df["Item"].isin(ignore_items)]
if ignore_owners:
    df = df[~df["Shop Owner"].isin(ignore_owners)]
if ignore_warps:
    df = df[~df["Warp"].isin(ignore_warps)]

print(f"Rows remaining after filters: {len(df):,}")

# Split
sellers = df[df["Action"] == "SELLING"].copy()
buyers  = df[df["Action"] == "BUYING"].copy()

sellers = sellers.rename(columns={
    "Shop Owner": "Seller",
    "Price": "Sell_Price",
    "Stock/Space": "Seller_Stock",
    "Warp": "Seller_Warp",
    "Shop Location": "Seller_Location",
    "Timestamp": "Seller_Timestamp"
})

buyers = buyers.rename(columns={
    "Shop Owner": "Buyer",
    "Price": "Buy_Price",
    "Stock/Space": "Buyer_Stock",
    "Warp": "Buyer_Warp",
    "Shop Location": "Buyer_Location",
    "Timestamp": "Buyer_Timestamp"
})

sellers = sellers[["Item", "Seller", "Sell_Price", "Seller_Stock", "Seller_Warp", "Seller_Location", "Seller_Timestamp"]]
buyers  = buyers[["Item", "Buyer", "Buy_Price", "Buyer_Stock", "Buyer_Warp", "Buyer_Location", "Buyer_Timestamp"]]

# Join + calculate
merged = sellers.merge(buyers, on="Item", how="inner")
merged = merged[merged["Buy_Price"] > merged["Sell_Price"]].copy()

merged["Quantity"] = merged[["Seller_Stock", "Buyer_Stock"]].min(axis=1).astype(int)
merged["Profit_Per_Item"] = merged["Buy_Price"] - merged["Sell_Price"]
merged["Total_Profit"] = merged["Profit_Per_Item"] * merged["Quantity"]
merged["Buy_Total"] = merged["Sell_Price"] * merged["Quantity"]
merged["Sell_Total"] = merged["Buy_Price"] * merged["Quantity"]

merged = merged[merged["Profit_Per_Item"] >= MIN_PROFIT_PER_ITEM]
merged = merged.sort_values("Total_Profit", ascending=False).reset_index(drop=True)

# ---------- Items that can / cannot be flipped for profit ----------
all_items = set(df["Item"].unique())
profitable_items = set(merged["Item"].unique())

can_flip_items = sorted(profitable_items)
cannot_flip_items = sorted(all_items - profitable_items)

with open(OUTPUT_CAN_FLIP, "w", encoding="utf-8") as f:
    f.write("\n".join(can_flip_items))

with open(OUTPUT_CANNOT_FLIP, "w", encoding="utf-8") as f:
    f.write("\n".join(cannot_flip_items))

print(f"Items that can be flipped for profit:   {len(can_flip_items)}  → {OUTPUT_CAN_FLIP}")
print(f"Items that cannot be flipped for profit: {len(cannot_flip_items)} → {OUTPUT_CANNOT_FLIP}")

# ---------- Save files ----------
csv_cols = [
    "Item", "Quantity", "Sell_Price", "Buy_Price", "Profit_Per_Item", "Total_Profit",
    "Seller", "Seller_Warp", "Seller_Stock",
    "Buyer", "Buyer_Warp", "Buyer_Stock",
    "Seller_Location", "Buyer_Location",
    "Seller_Timestamp", "Buyer_Timestamp"
]
merged[csv_cols].to_csv(OUTPUT_CSV, index=False)

lines = []
lines.append(f"Profitable Trade Opportunities")
lines.append(f"Generated from: {INPUT_FILE}")
lines.append(f"Total opportunities found: {len(merged)}")
lines.append("=" * 80)
lines.append("")

for i, row in merged.iterrows():
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
total_money = merged["Total_Profit"].sum()
avg_profit = merged["Total_Profit"].mean() if total_opportunities > 0 else 0
max_profit = merged["Total_Profit"].max() if total_opportunities > 0 else 0

print("\n" + "=" * 60)
print("SUMMARY")
print("=" * 60)
print(f"Total profitable opportunities : {total_opportunities:,}")
print(f"Total money that can be made   : ${total_money:,.2f}")
print(f"Average profit per opportunity : ${avg_profit:,.2f}")
print(f"Highest single opportunity     : ${max_profit:,.2f}")
print()

for n in [10, 100, 1000, 10000]:
    if total_opportunities == 0:
        break
    top_n_sum = merged["Total_Profit"].head(n).sum()
    print(f"Top {n:>5,} opportunities together : ${top_n_sum:,.2f}")

print("=" * 60)
print(f"\nFiles saved:")
print(f"  {OUTPUT_CSV}")
print(f"  {OUTPUT_TXT}")
print(f"  {OUTPUT_CAN_FLIP}")
print(f"  {OUTPUT_CANNOT_FLIP}")