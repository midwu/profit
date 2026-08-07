import pandas as pd
from pathlib import Path

# ========== CONFIG ==========
INPUT_FILE = "shop_data.csv"
OUTPUT_CSV = "profitable_trades.csv"
OUTPUT_TXT = "profitable_trades_readable.txt"
IGNORE_FILE = "ignore_items.txt"
MIN_PROFIT_PER_ITEM = 0.01
ONLY_ACTIVE = True
# ============================

# --- Load ignore list ---
ignore_items = set()
if Path(IGNORE_FILE).exists():
    with open(IGNORE_FILE, "r", encoding="utf-8") as f:
        ignore_items = {line.strip() for line in f if line.strip()}
    print(f"Ignoring {len(ignore_items)} items: {sorted(ignore_items)}")
else:
    print(f"No {IGNORE_FILE} found → no items ignored")

# --- Load data ---
df = pd.read_csv(INPUT_FILE)
df.columns = df.columns.str.strip()

if ONLY_ACTIVE:
    df = df[df["Status"] == "Active"].copy()

if ignore_items:
    df = df[~df["Item"].isin(ignore_items)]

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

# Join
merged = sellers.merge(buyers, on="Item", how="inner")
merged = merged[merged["Buy_Price"] > merged["Sell_Price"]].copy()

# Calculate
merged["Quantity"] = merged[["Seller_Stock", "Buyer_Stock"]].min(axis=1).astype(int)
merged["Profit_Per_Item"] = merged["Buy_Price"] - merged["Sell_Price"]
merged["Total_Profit"] = merged["Profit_Per_Item"] * merged["Quantity"]
merged["Buy_Total"] = merged["Sell_Price"] * merged["Quantity"]
merged["Sell_Total"] = merged["Buy_Price"] * merged["Quantity"]

merged = merged[merged["Profit_Per_Item"] >= MIN_PROFIT_PER_ITEM]
merged = merged.sort_values("Total_Profit", ascending=False).reset_index(drop=True)

# Save clean CSV
csv_cols = [
    "Item", "Quantity", "Sell_Price", "Buy_Price", "Profit_Per_Item", "Total_Profit",
    "Seller", "Seller_Warp", "Seller_Stock",
    "Buyer", "Buyer_Warp", "Buyer_Stock",
    "Seller_Location", "Buyer_Location",
    "Seller_Timestamp", "Buyer_Timestamp"
]
merged[csv_cols].to_csv(OUTPUT_CSV, index=False)

# --- Human readable report ---
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

print(f"Found {len(merged)} profitable opportunities")
print(f"CSV saved to:  {OUTPUT_CSV}")
print(f"Readable saved to: {OUTPUT_TXT}")
print("\nTop 5 opportunities (preview):")
print(merged.head(5)[["Item", "Quantity", "Sell_Price", "Buy_Price", "Total_Profit", "Seller_Warp", "Buyer_Warp"]].to_string())