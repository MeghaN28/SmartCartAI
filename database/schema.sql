-- Database schema placeholders for SmartCartAI

CREATE TABLE inventory (
  inventory_id VARCHAR(64) PRIMARY KEY,
  name TEXT,
  quantity INT,
  flagged BOOLEAN DEFAULT FALSE,
  metadata JSONB
);

CREATE TABLE sales (
  sale_id SERIAL PRIMARY KEY,
  inventory_id VARCHAR(64) REFERENCES inventory(inventory_id),
  quantity INT,
  sale_date TIMESTAMP
);

CREATE TABLE demand (
  demand_id SERIAL PRIMARY KEY,
  inventory_id VARCHAR(64) REFERENCES inventory(inventory_id),
  predicted_demand INT,
  model_version TEXT
);
