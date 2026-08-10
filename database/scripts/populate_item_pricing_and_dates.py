#!/usr/bin/env python3
"""Populate selling_price, expiry_date, and expiry_date_type for every inventory item.

Addresses ISCAP reviewer feedback: (1) the paper's donation-value figure ("$200 per
item") was a flat, unexplained constant with no unit or source -- this ties selling
price to each item's real per-unit price instead; (2) "sell by/use by/best by" date
semantics were missing from the schema entirely; (3) "completely remove non-perishable
items from your analysis" -- item_type is now the signal that actually drives shelf
life, so filtering on it is meaningful.

Selling price and the sell_by/use_by/best_by label are looked up by item_name (real
per-product pricing and labeling conventions). Shelf life (days from EVALUATION_DATE
to expiry_date) is driven by item_type instead of item_name: category/usage/item_type
in this dataset are randomly assigned by Dataset/createdataset.py and decoupled from
the real product (e.g. "Milk 1L" can land as Non-Perishable), so keying shelf life to
the specific product name would make item_type a meaningless signal for "is this at
risk of spoiling" -- exactly the kind of database-design gap a reviewer would flag.
Keying it to item_type instead makes that column the actual risk signal the paper's
waste analysis (and scripts/waste_graphs.py's item_type = 'Perishable' filter) relies
on: Perishable items get a 1-21 day window (a meaningful share land inside the 7-day
risk band used in Results), Non-Perishable items get 120-500 days (never at risk).

Expiry dates are generated relative to today's date (matching scripts/waste_graphs.py's
EVALUATION_DATE and the live chat pipeline's CURRENT_DATE-based near-expiry lookup, so a
live evaluation run and the offline chart script agree on what's "at risk"). A seeded RNG
is used per item so reruns are deterministic (same approach the paper describes for
Dataset/createdataset.py).

Run: python3 database/scripts/populate_item_pricing_and_dates.py
"""
import random
from datetime import date, timedelta

import psycopg2
from psycopg2.extras import RealDictCursor

DB_HOST = "localhost"
DB_USER = "meghanarendrasimha"
DB_PASSWORD = "Welcome@123"
DB_NAME = "smartcart_ai"

EVALUATION_DATE = date.today()

# item_name -> (selling_price USD, expiry_date_type)
PRICE_AND_DATE_TYPE = {
    "Milk 1L":         (4.29, "sell_by"),
    "Cheddar Cheese":  (5.49, "sell_by"),
    "Yogurt":          (3.99, "sell_by"),
    "Banana":          (0.59, "best_by"),
    "Apple":           (3.99, "best_by"),
    "Bread Loaf":      (3.49, "best_by"),
    "Bagel":           (4.29, "best_by"),
    "Orange Juice":    (4.99, "use_by"),
    "Soda Can":        (0.89, "best_by"),
    "Chocolate Bar":   (2.49, "best_by"),
    "Eggs Dozen":      (4.49, "sell_by"),
    "Butter 250g":     (4.99, "best_by"),
    "Cereal Box":      (4.49, "best_by"),
    "Tomato":          (2.99, "best_by"),
    "Potato":          (3.49, "best_by"),
    "Carrot":          (1.99, "best_by"),
    "Frozen Peas":     (2.99, "best_by"),
    "Chicken Breast":  (6.99, "use_by"),
    "Beef Steak":      (9.99, "use_by"),
    "Salmon Fillet":   (11.99, "use_by"),
    "Rice 1kg":        (3.49, "best_by"),
    "Pasta 500g":      (1.99, "best_by"),
    "Olive Oil 500ml": (8.99, "best_by"),
    "Coffee Beans":    (9.99, "best_by"),
    "Tea Pack":        (4.49, "best_by"),
    "Sugar 1kg":       (2.49, "best_by"),
    "Salt 500g":       (1.49, "best_by"),
    "Flour 1kg":       (2.99, "best_by"),
    "Lettuce":         (2.49, "best_by"),
    "Cucumber":        (0.99, "best_by"),
    "Onion":           (1.99, "best_by"),
    "Garlic":          (0.79, "best_by"),
    "Strawberry Pack": (3.99, "best_by"),
    "Blueberry Pack":  (4.49, "best_by"),
    "Mango":           (1.99, "best_by"),
    "Orange":          (3.49, "best_by"),
    "Water Bottle 1L": (1.29, "best_by"),
    "Energy Drink":    (2.99, "best_by"),
    "Chips Pack":      (3.49, "best_by"),
    "Cookies":         (3.99, "best_by"),
    "Peanut Butter":   (4.49, "best_by"),
    "Jam Jar":         (3.99, "best_by"),
    "Honey":           (6.99, "best_by"),
    "Yogurt Drink":    (2.49, "sell_by"),
    "Frozen Pizza":    (6.99, "best_by"),
    "Ice Cream":       (5.99, "best_by"),
    "Detergent":       (8.99, "best_by"),
    "Dish Soap":       (3.49, "best_by"),
    "Paper Towels":    (6.99, "best_by"),
    "Toilet Paper":    (9.99, "best_by"),
}

# item_type -> (min_shelf_days, max_shelf_days) from EVALUATION_DATE
SHELF_LIFE_BY_TYPE = {
    "Perishable": (1, 21),
    "Non-Perishable": (120, 500),
}
DEFAULT_SHELF_LIFE = (30, 180)


def main():
    conn = psycopg2.connect(
        host=DB_HOST, dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD,
        cursor_factory=RealDictCursor,
    )
    cur = conn.cursor()
    cur.execute("SELECT inventory_id, item_name, item_type FROM inventory ORDER BY inventory_id")
    rows = cur.fetchall()

    updated = 0
    missing = []
    for row in rows:
        profile = PRICE_AND_DATE_TYPE.get(row["item_name"])
        if not profile:
            missing.append(row["item_name"])
            continue
        price, date_type = profile
        min_days, max_days = SHELF_LIFE_BY_TYPE.get(row["item_type"], DEFAULT_SHELF_LIFE)
        rng = random.Random(row["inventory_id"])  # deterministic per item, reproducible reruns
        offset_days = rng.randint(min_days, max_days)
        expiry = EVALUATION_DATE + timedelta(days=offset_days)
        cur.execute(
            """
            UPDATE inventory
            SET selling_price = %s, expiry_date = %s, expiry_date_type = %s
            WHERE inventory_id = %s
            """,
            (price, expiry, date_type, row["inventory_id"]),
        )
        updated += 1

    conn.commit()
    cur.close()
    conn.close()

    print(f"Updated {updated} inventory rows with selling_price / expiry_date / expiry_date_type.")
    if missing:
        print(f"WARNING: no pricing profile for {len(missing)} item(s): {missing}")


if __name__ == "__main__":
    main()
