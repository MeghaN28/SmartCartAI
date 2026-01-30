-- Database schema derived from CSVs in `Dataset/`
-- Use these CREATE statements as a starting point. Adjust types and constraints
-- to match your production DB and migrations workflow.

-- Inventory master (matches `Dataset/inventory_master_50_unique.csv`)
CREATE TABLE inventory (
  inventory_id VARCHAR(32) PRIMARY KEY,
  item_name TEXT NOT NULL,
  category TEXT,
  form TEXT,
  "use" TEXT,
  item_type TEXT,
  vendor_id VARCHAR(32),
  min_stock INT,
  max_capacity INT,
  opening_stock INT
);

-- Sales transactions (matches `Dataset/sales_50.csv`)
CREATE TABLE sales (
  invoice_id VARCHAR(64) PRIMARY KEY,
  vendor_id VARCHAR(32),
  inventory_id VARCHAR(32) REFERENCES inventory(inventory_id),
  purchase_date DATE,
  quantity INT,
  unit_cost NUMERIC(12,2),
  total_cost NUMERIC(12,2),
  payment_status TEXT,
  account_code TEXT,
  delivery_date DATE
);

CREATE INDEX idx_sales_inventory ON sales(inventory_id);

-- Consumption / transaction logs (matches `Dataset/consumption_50.csv`)
CREATE TABLE consumption (
  transaction_id VARCHAR(64) PRIMARY KEY,
  date DATE,
  inventory_id VARCHAR(32) REFERENCES inventory(inventory_id),
  quantity_consumed INT,
  department TEXT,
  staff_id VARCHAR(32),
  shift TEXT,
  consumption_reason TEXT,
  remaining_stock INT,
  batch_lot TEXT
);

CREATE INDEX idx_consumption_inventory ON consumption(inventory_id);

-- Demand predictions table (kept for agent outputs; extend as needed)
CREATE TABLE demand (
  demand_id SERIAL PRIMARY KEY,
  inventory_id VARCHAR(32) REFERENCES inventory(inventory_id),
  predicted_demand INT,
  model_version TEXT,
  prediction_date DATE DEFAULT CURRENT_DATE
);

-- Example: quick CSV imports for development (psql `COPY` requires file accessible to DB server)
-- Adjust the file path to your environment or use `[3mpsql[0m`'s \copy from client side.
--
-- COPY inventory(inventory_id, item_name, category, form, "use", item_type, vendor_id, min_stock, max_capacity, opening_stock)
-- FROM '/absolute/path/to/SmartCartAI/Dataset/inventory_master_50_unique.csv' WITH (FORMAT csv, HEADER true);
--
-- COPY sales(invoice_id, vendor_id, inventory_id, purchase_date, quantity, unit_cost, total_cost, payment_status, account_code, delivery_date)
-- FROM '/absolute/path/to/SmartCartAI/Dataset/sales_50.csv' WITH (FORMAT csv, HEADER true);
--
-- COPY consumption(transaction_id, date, inventory_id, quantity_consumed, department, staff_id, shift, consumption_reason, remaining_stock, batch_lot)
-- FROM '/absolute/path/to/SmartCartAI/Dataset/consumption_50.csv' WITH (FORMAT csv, HEADER true);

-- Note: for local development you can run (client-side) \copy relative to your current directory:
-- \copy inventory FROM 'Dataset/inventory_master_50_unique.csv' CSV HEADER;
