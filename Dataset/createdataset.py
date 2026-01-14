import pandas as pd
import numpy as np

# 1. Load the original datasets
retail_df = pd.read_csv('retail_store_inventory.csv')
grocery_df = pd.read_csv('Grocery_Inventory new v1.csv')

# --- 2. Create Inventory with Warehouses Dataset ---
# Extracts location-based stock data from the grocery inventory
inventory_df = grocery_df[[
    'Product_ID', 'Product_Name', 'Catagory', 'Warehouse_Location', 
    'Stock_Quantity', 'Reorder_Level', 'Reorder_Quantity', 'Status'
]].copy()
inventory_df.rename(columns={'Catagory': 'Category'}, inplace=True)
inventory_df['Category'] = inventory_df['Category'].fillna('General')

# --- 3. Create Consumption Dataset ---
# Uses the time-series retail data to track units sold over time
consumption_df = retail_df[['Date', 'Product ID', 'Category', 'Region', 'Units Sold']].copy()
consumption_df.rename(columns={'Product ID': 'Product_ID', 'Units Sold': 'Consumption_Units'}, inplace=True)

# --- 4. Create Sales and Transaction Dataset ---
# Samples the retail data and generates unique transaction IDs and revenue calculations
sales_transaction_df = retail_df.sample(500, random_state=42).copy()
sales_transaction_df['Transaction_ID'] = ['T' + str(100000 + i) for i in range(len(sales_transaction_df))]
sales_transaction_df['Total_Sales_Amount'] = sales_transaction_df['Units Sold'] * sales_transaction_df['Price']

sales_transaction_df = sales_transaction_df[[
    'Transaction_ID', 'Date', 'Product ID', 'Store ID', 
    'Units Sold', 'Price', 'Discount', 'Total_Sales_Amount'
]]
sales_transaction_df.rename(columns={
    'Product ID': 'Product_ID', 
    'Store ID': 'Store_ID', 
    'Units Sold': 'Quantity'
}, inplace=True)

# --- 5. Create Vendor Related Dataset ---
# Extracts unique suppliers and simulates operational metrics like lead time and ratings
vendor_df = grocery_df[['Supplier_ID', 'Supplier_Name']].drop_duplicates().copy()
np.random.seed(42)
vendor_df['Lead_Time_Days'] = np.random.randint(3, 15, size=len(vendor_df))
vendor_df['Vendor_Rating'] = np.round(np.random.uniform(3.0, 5.0, size=len(vendor_df)), 1)
vendor_df['Contact_Email'] = vendor_df['Supplier_Name'].str.lower().str.replace(' ', '') + "@vendor.com"

# --- 6. Export to CSV ---
inventory_df.to_csv('inventory_warehouse_data.csv', index=False)
consumption_df.to_csv('consumption_data.csv', index=False)
sales_transaction_df.to_csv('sales_transaction_data.csv', index=False)
vendor_df.to_csv('vendor_data.csv', index=False)

print("Datasets successfully generated and saved.")