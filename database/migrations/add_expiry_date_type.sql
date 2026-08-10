-- Distinguish label semantics on expiry_date: "sell by" (retailer stocking cutoff),
-- "use by" (food-safety cutoff), and "best by" (quality-only, not safety). Reviewer
-- feedback noted these labels are shown to influence consumer waste behavior
-- differently and were not represented in the schema (only one generic date).
-- Run: psql -h localhost -U your_user -d smartcart_ai -f database/migrations/add_expiry_date_type.sql

ALTER TABLE inventory
  ADD COLUMN IF NOT EXISTS expiry_date_type VARCHAR(10)
    CHECK (expiry_date_type IN ('sell_by', 'use_by', 'best_by'));

COMMENT ON COLUMN inventory.expiry_date_type IS
  'Label semantics for expiry_date: sell_by (retailer stocking cutoff), use_by (food-safety cutoff), best_by (quality only, not safety).';
