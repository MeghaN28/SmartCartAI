-- Suggestions table to store AI-generated recommendations
CREATE TABLE IF NOT EXISTS suggestions (
  suggestion_id SERIAL PRIMARY KEY,
  inventory_id VARCHAR(32) REFERENCES inventory(inventory_id),
  item_name TEXT,
  user_query TEXT,
  action VARCHAR(50), -- 'reorder', 'hold', 'transfer', 'none'
  priority VARCHAR(20), -- 'High', 'Medium', 'Low'
  reasoning TEXT,
  expected_outcome TEXT,
  risk_level VARCHAR(20),
  risk_score INT,
  is_feasible BOOLEAN,
  estimated_cost NUMERIC(12,2),
  within_budget BOOLEAN,
  explanation TEXT,
  current_stock INT,
  min_stock INT,
  forecasted_demand NUMERIC(10,2),
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  status VARCHAR(20) DEFAULT 'pending' -- 'pending', 'approved', 'rejected', 'implemented'
);

CREATE INDEX idx_suggestions_inventory ON suggestions(inventory_id);
CREATE INDEX idx_suggestions_created ON suggestions(created_at DESC);
CREATE INDEX idx_suggestions_status ON suggestions(status);
