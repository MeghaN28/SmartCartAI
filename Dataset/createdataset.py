import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# ------------------------------
# PARAMETERS
# ------------------------------
start_date = datetime(2025, 1, 1)
end_date = datetime(2025, 12, 31)
dates = pd.date_range(start_date, end_date, freq='D')
np.random.seed(42)

# ------------------------------
# REALISTIC PRODUCT CATALOG
# ------------------------------
products = [
    {'name': 'Milk 1L', 'category': 'Dairy', 'shelf_life': 7, 'base_price': 3.5},
    {'name': 'Cheddar Cheese', 'category': 'Dairy', 'shelf_life': 20, 'base_price': 5.0},
    {'name': 'Yogurt', 'category': 'Dairy', 'shelf_life': 10, 'base_price': 2.5},
    {'name': 'Banana', 'category': 'Produce', 'shelf_life': 5, 'base_price': 0.5},
    {'name': 'Apple', 'category': 'Produce', 'shelf_life': 10, 'base_price': 0.8},
    {'name': 'Bread Loaf', 'category': 'Bakery', 'shelf_life': 5, 'base_price': 2.0},
    {'name': 'Bagel', 'category': 'Bakery', 'shelf_life': 4, 'base_price': 1.5},
    {'name': 'Orange Juice', 'category': 'Beverage', 'shelf_life': 15, 'base_price': 4.0},
    {'name': 'Soda Can', 'category': 'Beverage', 'shelf_life': 365, 'base_price': 1.2},
    {'name': 'Chocolate Bar', 'category': 'Snack', 'shelf_life': 180, 'base_price': 1.0}
]

# Assign initial stock for each product
for p in products:
    p['initial_stock'] = np.random.randint(100, 500)

# ------------------------------
# SIMULATION: INVENTORY, SALES, DEMAND
# ------------------------------
inventory_records = []
sales_records = []
demand_records = []

for prod in products:
    stock = prod['initial_stock']
    shelf_life = prod['shelf_life']
    base_price = prod['base_price']
    
    for day_idx, current_date in enumerate(dates):
        # True demand (Poisson around stock/10 + noise)
        demand = max(0, int(np.random.poisson(lam=max(1, stock/10)) + np.random.randint(-2,3)))
        sold_qty = min(demand, stock)
        stock -= sold_qty
        
        # Remaining shelf life
        days_left = max(shelf_life - day_idx, 0)
        
        # Waste risk
        if days_left <= 2 and stock > 0:
            waste_risk = 'High'
        elif days_left <= 5 and stock > 0:
            waste_risk = 'Medium'
        else:
            waste_risk = 'Low'
        
        # Price fluctuation
        price = round(base_price * np.random.uniform(0.9, 1.1), 2)
        
        # Inventory record
        inventory_records.append({
            'date': current_date.date(),
            'product_name': prod['name'],
            'category': prod['category'],
            'stock': stock,
            'days_left': days_left,
            'waste_risk': waste_risk
        })
        
        # Sales record
        sales_records.append({
            'date': current_date.date(),
            'product_name': prod['name'],
            'sold_qty': sold_qty,
            'price': price
        })
        
        # Demand record
        demand_records.append({
            'date': current_date.date(),
            'product_name': prod['name'],
            'demand_qty': demand
        })

# ------------------------------
# CREATE DATAFRAMES
# ------------------------------
inventory_df = pd.DataFrame(inventory_records)
sales_df = pd.DataFrame(sales_records)
demand_df = pd.DataFrame(demand_records)

# ------------------------------
# SAVE CSV FILES
# ------------------------------
inventory_df.to_csv('inventory_real_names_2025.csv', index=False)
sales_df.to_csv('sales_real_names_2025.csv', index=False)
demand_df.to_csv('demand_real_names_2025.csv', index=False)

print("Datasets with real-like product names generated!")
print("Inventory:", inventory_df.shape)
print("Sales:", sales_df.shape)
print("Demand:", demand_df.shape)
