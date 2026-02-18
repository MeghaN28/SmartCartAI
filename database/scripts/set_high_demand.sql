-- Set high predicted demand for a specific item by name
-- Default: Banana -> predicted_demand = 50
-- Usage (psql): psql -h <host> -U <user> -d <db> -f database/scripts/set_high_demand.sql

BEGIN;

-- Adjust these values as needed
\set ITEM_NAME 'Banana'
\set DEMAND_VAL 50

-- Delete previous manual entries for this item
DELETE FROM demand
WHERE inventory_id IN (
  SELECT inventory_id FROM inventory WHERE lower(item_name) = lower(:'ITEM_NAME')
);

-- Insert new predicted demand rows for matching inventory items
INSERT INTO demand (inventory_id, predicted_demand, model_version, prediction_date)
SELECT inventory_id, :'DEMAND_VAL'::int, 'manual-boost', CURRENT_DATE
FROM inventory
WHERE lower(item_name) = lower(:'ITEM_NAME');

COMMIT;

-- Verify results:
-- SELECT d.* FROM demand d JOIN inventory i ON d.inventory_id = i.inventory_id WHERE lower(i.item_name) = lower('Banana');
