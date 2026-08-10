-- Replace the donation_info JSON-in-TEXT blob with a proper relational table.
-- suggestions.donation_info stored a JSON array of food bank objects as text,
-- which can't be queried/joined/indexed and duplicates food_banks columns
-- (name, address) instead of referencing them. This table normalizes that:
-- one row per (suggestion, food bank) with a real FK to food_banks.
-- donation_info is kept only for backward compatibility with rows written
-- before this migration; new suggestions are written here instead.
-- Run: psql -h localhost -U your_user -d smartcart_ai -f database/migrations/add_suggestion_food_bank.sql

CREATE TABLE IF NOT EXISTS suggestion_food_bank (
  id SERIAL PRIMARY KEY,
  suggestion_id INTEGER NOT NULL REFERENCES suggestions(suggestion_id) ON DELETE CASCADE,
  food_bank_id INTEGER NOT NULL REFERENCES food_banks(food_bank_id) ON DELETE CASCADE,
  rank INTEGER,
  distance_mi NUMERIC(8,2),
  UNIQUE (suggestion_id, food_bank_id)
);

CREATE INDEX IF NOT EXISTS idx_suggestion_food_bank_suggestion ON suggestion_food_bank(suggestion_id);
CREATE INDEX IF NOT EXISTS idx_suggestion_food_bank_food_bank ON suggestion_food_bank(food_bank_id);

COMMENT ON TABLE suggestion_food_bank IS 'Normalized nearest-food-bank matches per suggestion; supersedes suggestions.donation_info (kept for legacy rows only).';
