-- Set inventory and demand so "What's going to waste?" returns a mix of DONATE, DISCOUNT, and BUNDLE.
-- DISCOUNT: medium stock + good demand (surplus not very high), with selling_price for suggested price.
-- BUNDLE: stock in 20–320 and items in same category (similar items found at runtime).
-- Run: psql -h localhost -U meghanarendrasimha -d smartcart_ai -f database/scripts/set_discount_and_bundle_mix.sql

BEGIN;

-- 1) Ensure demand rows exist for all items (use as daily demand floor; agents use max(forecast, this))
DELETE FROM demand;
INSERT INTO demand (inventory_id, predicted_demand, model_version, prediction_date)
SELECT inventory_id, 25, 'manual-mix', CURRENT_DATE FROM inventory;

-- 2) DISCOUNT: medium stock (e.g. 60–120) + high demand so surplus is small (not DONATE, not HOLD)
--    Rule: surplus < 80 and stock < 380 → not DONATE; demand_before_expiry = predicted_demand * 14;
--    So e.g. stock 90, demand 12 → surplus = 90 - 168 = -78 (no HOLD which is surplus <= -80).
--    Set selling_price so suggested_discount_percent and suggested_selling_price appear.
UPDATE inventory
SET opening_stock = 90,
    selling_price = COALESCE(selling_price, 4.99)
WHERE item_name IN ('Milk 1L', 'Yogurt');
UPDATE inventory
SET expiry_date = CURRENT_DATE + 10
WHERE item_name IN ('Milk 1L', 'Yogurt');

-- 3) BUNDLE: stock in 20–320; similar items come from same category at runtime
--    Pick a category that has multiple items (e.g. Produce: Banana, Apple) and set moderate stock
UPDATE inventory
SET opening_stock = 85,
    selling_price = COALESCE(selling_price, 3.49)
WHERE item_name IN ('Banana');
UPDATE inventory
SET opening_stock = 70,
    selling_price = COALESCE(selling_price, 2.99)
WHERE item_name = 'Apple';
UPDATE inventory
SET expiry_date = CURRENT_DATE + 7
WHERE item_name = 'Apple';

-- 4) Lower predicted_demand for DISCOUNT items so surplus is in “medium” range (not very high)
--    e.g. daily 12 → demand_before_expiry = 168; stock 90 → surplus -78 → DISCOUNT
UPDATE demand d
SET predicted_demand = 12
FROM inventory i
WHERE d.inventory_id = i.inventory_id
  AND i.item_name IN ('Milk 1L', 'Yogurt', 'Apple', 'Banana');

-- 5) Keep some items as DONATE (very high surplus): high stock + moderate demand
UPDATE inventory SET opening_stock = 350 WHERE item_name = 'Cheddar Cheese';
UPDATE demand d SET predicted_demand = 5
FROM inventory i WHERE d.inventory_id = i.inventory_id AND i.item_name = 'Cheddar Cheese';

COMMIT;

-- Verify
-- SELECT item_name, opening_stock, selling_price, expiry_date FROM inventory WHERE item_name IN ('Milk 1L','Yogurt','Apple','Banana','Cheddar Cheese');
-- SELECT i.item_name, i.opening_stock, d.predicted_demand FROM inventory i JOIN demand d ON i.inventory_id = d.inventory_id WHERE i.item_name IN ('Milk 1L','Yogurt','Apple','Banana','Cheddar Cheese');
