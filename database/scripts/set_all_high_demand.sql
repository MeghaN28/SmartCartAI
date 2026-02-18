-- Set high predicted demand for ALL inventory items (daily demand floor used by agents).
-- Run this to make "demand higher" globally so DISCOUNT/medium-demand rules trigger more.
-- Usage: psql -h <host> -U <user> -d <db> -f database/scripts/set_all_high_demand.sql
-- Optional: psql -v DEMAND_VAL=30 -h ... -f database/scripts/set_all_high_demand.sql

BEGIN;

\set DEMAND_VAL 25

DELETE FROM demand;

INSERT INTO demand (inventory_id, predicted_demand, model_version, prediction_date)
SELECT inventory_id, :'DEMAND_VAL'::int, 'manual-boost-all', CURRENT_DATE
FROM inventory;

COMMIT;

-- Verify: SELECT COUNT(*) FROM demand; SELECT * FROM demand LIMIT 5;