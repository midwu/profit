"""
self_flip_finder.py

Finds "shop owner mistakes": a single player whose buy order pays more
than their own sell order for the same item. These are NOT limited by
listed stock — you don't need their inventory, you supply the item
yourself (farming, grinding, crafting) and sell it straight into their
over-priced buy order, or buy their under-priced stock and sell it back
to them. Ranked purely by per-item margin, since how many you can
actually produce depends on your own grind rate, not on shop_data.csv.
"""

import argparse

from data_loader import load_shop_data

DEFAULT_INPUT_FILE = "shop_data.csv"
OUTPUT_CSV = "self_flip_opportunities.csv"
OUTPUT_TXT = "self_flip_opportunities.txt"


def parse_args():
    p = argparse.ArgumentParser(description="Find same-owner buy>sell price mistakes.")
    p.add_argument("--input", default=DEFAULT_INPUT_FILE, help="Path to shop_data.csv (default: %(default)s)")
    p.add_argument("--include-inactive", action="store_true",
                    help="Include shops not marked Active (default: active-only)")
    return p.parse_args()


def main():
    args = parse_args()
    df = load_shop_data(args.input)

    if not args.include_inactive:
        df = df[df["Status"] == "Active"].copy()

    sellers = df[df["Action"] == "SELLING"].copy().rename(columns={
        "Shop Owner": "Seller", "Price": "Sell_Price",
        "Warp": "Seller_Warp", "Shop Location": "Seller_Location", "Timestamp": "Seller_Timestamp",
    })[["Item", "Seller", "Sell_Price", "Seller_Warp", "Seller_Location", "Seller_Timestamp"]]

    buyers = df[df["Action"] == "BUYING"].copy().rename(columns={
        "Shop Owner": "Buyer", "Price": "Buy_Price",
        "Warp": "Buyer_Warp", "Shop Location": "Buyer_Location", "Timestamp": "Buyer_Timestamp",
    })[["Item", "Buyer", "Buy_Price", "Buyer_Warp", "Buyer_Location", "Buyer_Timestamp"]]

    merged = sellers.merge(buyers, on="Item", how="inner")
    merged = merged[merged["Seller"] == merged["Buyer"]].copy()
    merged = merged[merged["Buy_Price"] > merged["Sell_Price"]].copy()
    merged["Margin_Per_Item"] = merged["Buy_Price"] - merged["Sell_Price"]
    merged = merged.sort_values("Margin_Per_Item", ascending=False).reset_index(drop=True)

    print(f"Self-flip (owner mistake) opportunities found: {len(merged)}")

    cols = ["Item", "Seller", "Sell_Price", "Buy_Price", "Margin_Per_Item",
            "Seller_Warp", "Seller_Location", "Seller_Timestamp", "Buyer_Timestamp"]
    merged[cols].to_csv(OUTPUT_CSV, index=False)

    lines = [
        "Self-Flip / Shop Owner Mistake Opportunities",
        "Same player is both buyer and seller, with buy price > sell price.",
        "Exploitable indefinitely regardless of listed stock — grind/farm the item yourself.",
        "=" * 80, "",
    ]
    for i, row in merged.iterrows():
        lines.append(
            f"{i+1}. '{row['Item']}' — {row['Seller']} ({row['Seller_Warp']})\n"
            f"   Buys at ${row['Buy_Price']:.2f} each, sells at ${row['Sell_Price']:.2f} each\n"
            f"   → Margin: ${row['Margin_Per_Item']:.2f} per item\n"
        )
        lines.append("-" * 80)
    with open(OUTPUT_TXT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"Saved: {OUTPUT_CSV}, {OUTPUT_TXT}")


if __name__ == "__main__":
    main()