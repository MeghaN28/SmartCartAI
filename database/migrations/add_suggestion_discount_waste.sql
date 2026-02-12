-- Optional: add price/waste fields to suggestions (run after add_expiry_and_price.sql)
ALTER TABLE suggestions
  ADD COLUMN IF NOT EXISTS suggested_discount_percent NUMERIC(5,2),
  ADD COLUMN IF NOT EXISTS waste_action TEXT;
