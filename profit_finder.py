import pandas as pd
from pathlib import Path

# ========== CONFIG ==========
INPUT_FILE = "shop_data.csv"          # change if needed
OUTPUT_FILE = "profitable_trades.csv"
MIN_PROFIT_PER_ITEM = 0.01            # ignore tiny profits
ONLY_ACTIVE = True                    # set False if you also want out-of-stock/out-of-space
# ============================

df = pd.read_csv(INPUT_FILE)

# Clean column names just in case
df.columns = df.columns.str.strip()

# Optional: keep only Active
if ONLY_ACTIVE:
    df = df[df["Status"] == "Active"].copy()

# Split into sellers and buyers
sellers = df[df["Action"] == "SELLING"].copy()
buyers  = df[df["Action"] == "BUYING"].copy()

# Rename for clarity after merge
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

# Keep only needed columns
sellers = sellers[["Item", "Seller", "Sell_Price", "Seller_Stock", "Seller_Warp", "Seller_Location", "Seller_Timestamp"]]
buyers  = buyers[["Item", "Buyer", "Buy_Price", "Buyer_Stock", "Buyer_Warp", "Buyer_Location", "Buyer_Timestamp"]]

# Cartesian join on Item
merged = sellers.merge(buyers, on="Item", how="inner")

# Only profitable trades
merged = merged[merged["Buy_Price"] > merged["Sell_Price"]].copy()

# Calculate quantities and profits
merged["Quantity"] = merged[["Seller_Stock", "Buyer_Stock"]].min(axis=1)
merged["Profit_Per_Item"] = merged["Buy_Price"] - merged["Sell_Price"]
merged["Total_Profit"] = merged["Profit_Per_Item"] * merged["Quantity"]

# Filter very small profits
merged = merged[merged["Profit_Per_Item"] >= MIN_PROFIT_PER_ITEM]

# Sort by total profit (best opportunities first)
merged = merged.sort_values("Total_Profit", ascending=False)

# Nice column order
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

# Save
result.to_csv(OUTPUT_FILE, index=False)

print(f"Found {len(result)} profitable opportunities")
print(f"Results saved to: {OUTPUT_FILE}")
print("\nTop 10 opportunities:")
print(result.head(10).to_string())