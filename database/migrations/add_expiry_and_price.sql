-- Add expiry tracking and selling price for price optimization and waste management
-- Run this on existing database: psql -h localhost -U your_user -d smartcart_ai -f database/migrations/add_expiry_and_price.sql

ALTER TABLE inventory
  ADD COLUMN IF NOT EXISTS expiry_date DATE,
  ADD COLUMN IF NOT EXISTS selling_price NUMERIC(12,2);

COMMENT ON COLUMN inventory.expiry_date IS 'Date after which item is considered expired; used for waste alerts and discount suggestions';
COMMENT ON COLUMN inventory.selling_price IS 'Current or typical selling price; used for margin and price optimization';

CREATE INDEX IF NOT EXISTS idx_inventory_expiry ON inventory(expiry_date) WHERE expiry_date IS NOT NULL;
