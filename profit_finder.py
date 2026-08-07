import pandas as pd
from pathlib import Path

# ========== CONFIG ==========
INPUT_FILE = "shop_data.csv"
OUTPUT_FILE = "profitable_trades.csv"
IGNORE_FILE = "ignore_items.txt"      # ← new
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

# Remove ignored items
if ignore_items:
    df = df[~df["Item"].isin(ignore_items)]

# Split into sellers and buyers
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

# Join on Item
merged = sellers.merge(buyers, on="Item", how="inner")

# Only profitable
merged = merged[merged["Buy_Price"] > merged["Sell_Price"]].copy()

# Calculate
merged["Quantity"] = merged[["Seller_Stock", "Buyer_Stock"]].min(axis=1)
merged["Profit_Per_Item"] = merged["Buy_Price"] - merged["Sell_Price"]
merged["Total_Profit"] = merged["Profit_Per_Item"] * merged["Quantity"]

merged = merged[merged["Profit_Per_Item"] >= MIN_PROFIT_PER_ITEM]
merged = merged.sort_values("Total_Profit", ascending=False)

result = merged[[
    "Item",
    "Quantity",
    "Sell_Price",
    "Buy_Price",
    "Profit_Per_Item",
    "Total_Profit",
    "Seller",
    "Seller_Warp",
    "Seller_Stock",
    "Buyer",
    "Buyer_Warp",
    "Buyer_Stock",
    "Seller_Location",
    "Buyer_Location",
    "Seller_Timestamp",
    "Buyer_Timestamp"
]].reset_index(drop=True)

result.to_csv(OUTPUT_FILE, index=False)

print(f"\nFound {len(result)} profitable opportunities")
print(f"Results saved to: {OUTPUT_FILE}")
print("\nTop 10 opportunities:")
print(result.head(10).to_string())