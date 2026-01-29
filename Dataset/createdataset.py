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
uses = ['Food', 'Non-Food']
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

categories_list = np.random.choice(categories, num_products)
forms_list = np.random.choice(forms, num_products)
uses_list = np.random.choice(uses, num_products)
item_types_list = np.random.choice(item_types, num_products)
vendor_ids = np.random.choice(vendors, num_products)
min_stocks = np.random.randint(20, 50, num_products)
max_caps = np.random.randint(200, 500, num_products)
opening_stocks = np.random.randint(50, 300, num_products)

inventory_master_df = pd.DataFrame({
    'inventory_id': inventory_ids,
    'item_name': product_names,
    'category': categories_list,
    'form': forms_list,
    'use': uses_list,
    'item_type': item_types_list,
    'vendor_id': vendor_ids,
    'min_stock': min_stocks,
    'max_capacity': max_caps,
    'opening_stock': opening_stocks
})

# ------------------------------
# SIMULATE CONSUMPTION & SALES
# ------------------------------
inventory_records = []
consumption_records = []
sales_records = []

for idx, prod in inventory_master_df.iterrows():
    stock = prod['opening_stock']
    inventory_id = prod['inventory_id']
    item_name = prod['item_name']
    min_stock = prod['min_stock']
    max_capacity = prod['max_capacity']
    form = prod['form']
    use = prod['use']
    item_type = prod['item_type']
    category = prod['category']
    vendor_id = prod['vendor_id']
    lead_time_days = np.random.randint(1, 7)
    department_count = np.random.randint(1, 6)

    for day_idx, current_date in enumerate(dates):
        # ---------- Consumption ----------
        num_consumptions = np.random.randint(1, 4)
        total_consumed = 0
        for c in range(num_consumptions):
            quantity_consumed = min(stock, np.random.randint(1, 20))
            department = np.random.choice(departments)
            staff_id = np.random.choice(staff_ids)
            shift = np.random.choice(shifts)
            reason = np.random.choice(consumption_reasons)
            batch_lot = f'BATCH{np.random.randint(1000,9999)}'
            remaining_stock = stock - quantity_consumed
            stock -= quantity_consumed
            total_consumed += quantity_consumed

            consumption_records.append({
                'transaction_id': f'TX{idx:03d}{day_idx:03d}{c:02d}',
                'date': current_date.date(),
                'inventory_id': inventory_id,
                'quantity_consumed': quantity_consumed,
                'department': department,
                'staff_id': staff_id,
                'shift': shift,
                'consumption_reason': reason,
                'remaining_stock': remaining_stock,
                'batch_lot': batch_lot
            })

        # ---------- Restock ----------
        quantity_restocked = np.random.randint(0, 50)
        stock += quantity_restocked

        out_of_stock = stock == 0
        low_stock = stock < min_stock

        inventory_records.append({
            'date': current_date.date(),
            'inventory_id': inventory_id,
            'opening_stock': stock - quantity_restocked + total_consumed,
            'quantity_consumed': total_consumed,
            'quantity_restocked': quantity_restocked,
            'closing_stock': stock,
            'vendor_id': vendor_id,
            'lead_time_days': lead_time_days,
            'department_count': department_count,
            'min_stock': min_stock,
            'max_capacity': max_capacity,
            'item_name': item_name,
            'category': category,
            'form': form,
            'use': use,
            'item_type': item_type,
            'out_of_stock': out_of_stock,
            'low_stock': low_stock
        })

        # ---------- Sales ----------
        num_sales = np.random.randint(1, 4)
        for s in range(num_sales):
            quantity_sold = min(stock, np.random.randint(1, 15))
            stock -= quantity_sold
            unit_cost = round(np.random.uniform(1.0, 20.0), 2)
            total_cost = round(unit_cost * quantity_sold, 2)
            account_code = f'AC{np.random.randint(1000,9999)}'
            delivery_date = current_date + timedelta(days=np.random.randint(0,5))
            payment_status = np.random.choice(['Paid','Pending'])

            sales_records.append({
                'invoice_id': f'INVX{idx:03d}{day_idx:03d}{s:02d}',
                'vendor_id': vendor_id,
                'inventory_id': inventory_id,
                'purchase_date': current_date.date(),
                'quantity': quantity_sold,
                'unit_cost': unit_cost,
                'total_cost': total_cost,
                'payment_status': payment_status,
                'account_code': account_code,
                'delivery_date': delivery_date.date()
            })

# ------------------------------
# CREATE DATAFRAMES
# ------------------------------
inventory_master_df.to_csv('inventory_master_50_unique.csv', index=False)

inventory_history_df = pd.DataFrame(inventory_records)

# --------- UNIQUE INVENTORY HISTORY (AGGREGATED) ----------
inventory_history_unique_df = (
    inventory_history_df
    .sort_values('date')
    .groupby('inventory_id', as_index=False)
    .agg({
        'date': 'max',
        'opening_stock': 'first',
        'closing_stock': 'last',
        'quantity_consumed': 'sum',
        'quantity_restocked': 'sum',
        'vendor_id': 'first',
        'lead_time_days': 'mean',
        'department_count': 'max',
        'min_stock': 'first',
        'max_capacity': 'first',
        'item_name': 'first',
        'category': 'first',
        'form': 'first',
        'use': 'first',
        'item_type': 'first',
        'out_of_stock': 'max',
        'low_stock': 'max'
    })
)

consumption_df = pd.DataFrame(consumption_records)
sales_df = pd.DataFrame(sales_records)

inventory_history_unique_df.to_csv('inventory_history_50_unique.csv', index=False)
consumption_df.to_csv('consumption_50.csv', index=False)
sales_df.to_csv('sales_50.csv', index=False)

print("Generated Inventory Master, UNIQUE Inventory History, Consumption, and Sales datasets for 50 unique items!")
