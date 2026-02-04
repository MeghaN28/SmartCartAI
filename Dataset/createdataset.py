import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import random

# ------------------------------
# PARAMETERS
# ------------------------------
num_products = 50
start_date = datetime(2025, 1, 1)
end_date = datetime(2025, 12, 31)
dates = pd.date_range(start_date, end_date, freq='D')

departments = ['Bakery', 'Dairy', 'Produce', 'Beverage', 'Snack', 'Frozen']
shifts = ['Morning', 'Evening', 'Night']
consumption_reasons = ['Routine', 'Spoilage', 'Sample']
forms = ['Solid', 'Liquid', 'Pack']
categories = ['Dairy', 'Produce', 'Bakery', 'Beverage', 'Snack']
usages = ['Food', 'Non-Food']   # renamed
item_types = ['Perishable', 'Non-Perishable']
vendors = [f'V{i:03d}' for i in range(1, 11)]
staff_ids = [f'S{i:03d}' for i in range(1, 21)]

np.random.seed(42)
random.seed(42)

# ------------------------------
# INVENTORY MASTER
# ------------------------------
inventory_ids = [f'INV{i:04d}' for i in range(1, num_products + 1)]

product_names = [
    "Milk 1L", "Cheddar Cheese", "Yogurt", "Banana", "Apple", "Bread Loaf", "Bagel",
    "Orange Juice", "Soda Can", "Chocolate Bar", "Eggs Dozen", "Butter 250g", "Cereal Box",
    "Tomato", "Potato", "Carrot", "Frozen Peas", "Chicken Breast", "Beef Steak", "Salmon Fillet",
    "Rice 1kg", "Pasta 500g", "Olive Oil 500ml", "Coffee Beans", "Tea Pack", "Sugar 1kg",
    "Salt 500g", "Flour 1kg", "Lettuce", "Cucumber", "Onion", "Garlic", "Strawberry Pack",
    "Blueberry Pack", "Mango", "Orange", "Water Bottle 1L", "Energy Drink", "Chips Pack",
    "Cookies", "Peanut Butter", "Jam Jar", "Honey", "Yogurt Drink", "Frozen Pizza", "Ice Cream",
    "Detergent", "Dish Soap", "Paper Towels", "Toilet Paper"
][:num_products]

inventory_master_df = pd.DataFrame({
    'inventory_id': inventory_ids,
    'item_name': product_names,
    'category': np.random.choice(categories, num_products),
    'form': np.random.choice(forms, num_products),
    'usage': np.random.choice(usages, num_products),     # renamed
    'item_type': np.random.choice(item_types, num_products),
    'vendor_id': np.random.choice(vendors, num_products),
    'min_stock': np.random.randint(20, 50, num_products),
    'max_capacity': np.random.randint(200, 500, num_products),
    'opening_stock': np.random.randint(50, 300, num_products)
})

# ------------------------------
# SIMULATE CONSUMPTION & SALES
# ------------------------------
consumption_records = []
sales_records = []

for idx, prod in inventory_master_df.iterrows():
    stock = prod['opening_stock']
    inventory_id = prod['inventory_id']
    vendor_id = prod['vendor_id']
    min_stock = prod['min_stock']

    for day_idx, current_date in enumerate(dates):

        # ---------- Consumption ----------
        num_consumptions = np.random.randint(1, 4)
        for c in range(num_consumptions):
            quantity_consumed = min(stock, np.random.randint(1, 20))
            stock -= quantity_consumed

            consumption_records.append({
                'transaction_id': f'TX{idx:03d}{day_idx:03d}{c:02d}',
                'transaction_date': current_date.date(),   # renamed
                'inventory_id': inventory_id,
                'quantity_consumed': quantity_consumed,
                'department': np.random.choice(departments),
                'staff_id': np.random.choice(staff_ids),
                'shift': np.random.choice(shifts),
                'consumption_reason': np.random.choice(consumption_reasons),
                'remaining_stock': stock,
                'batch_lot': f'BATCH{np.random.randint(1000,9999)}'
            })

        # ---------- Restock ----------
        stock += np.random.randint(0, 50)

        # ---------- Sales ----------
        num_sales = np.random.randint(1, 4)
        for s in range(num_sales):
            quantity_sold = min(stock, np.random.randint(1, 15))
            stock -= quantity_sold

            unit_cost = round(np.random.uniform(1.0, 20.0), 2)

            sales_records.append({
                'invoice_id': f'INVX{idx:03d}{day_idx:03d}{s:02d}',
                'vendor_id': vendor_id,
                'inventory_id': inventory_id,
                'purchase_date': current_date.date(),
                'quantity': quantity_sold,
                'unit_cost': unit_cost,
                'total_cost': round(unit_cost * quantity_sold, 2),
                'payment_status': np.random.choice(['Paid', 'Pending']),
                'account_code': f'AC{np.random.randint(1000,9999)}',
                'delivery_date': (current_date + timedelta(days=np.random.randint(0, 5))).date()
            })

# ------------------------------
# SAVE CSVs (MATCH DB SCHEMA)
# ------------------------------
inventory_master_df.to_csv('inventory_master_50_unique.csv', index=False)
pd.DataFrame(consumption_records).to_csv('consumption_50.csv', index=False)
pd.DataFrame(sales_records).to_csv('sales_50.csv', index=False)

print("Generated schema-aligned Inventory, Consumption, and Sales datasets (PostgreSQL ready)")
