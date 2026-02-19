-- Set selling_price on inventory so DISCOUNT recommendations show suggested price.
-- Run after set_discount_and_bundle_mix.sql or alone: psql -h localhost -U meghanarendrasimha -d smartcart_ai -f database/scripts/set_selling_prices_for_discount.sql

UPDATE inventory SET selling_price = COALESCE(selling_price, 4.99) WHERE item_name = 'Milk 1L';
UPDATE inventory SET selling_price = COALESCE(selling_price, 3.99) WHERE item_name = 'Yogurt';
UPDATE inventory SET selling_price = COALESCE(selling_price, 3.99) WHERE item_name = 'Apple';
UPDATE inventory SET selling_price = COALESCE(selling_price, 3.49) WHERE item_name = 'Banana';
UPDATE inventory SET selling_price = COALESCE(selling_price, 5.49) WHERE item_name = 'Cheddar Cheese';

-- Set prices for any other items that have NULL selling_price (optional)
-- UPDATE inventory SET selling_price = 3.99 WHERE selling_price IS NULL;
