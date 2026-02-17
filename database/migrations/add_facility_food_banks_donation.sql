-- Facility (store/warehouse) for distance-to-food-bank calculations.
-- Single row or one per location; food-bank agent uses this for "nearest" lookup.
CREATE TABLE IF NOT EXISTS facility (
  facility_id SERIAL PRIMARY KEY,
  name TEXT NOT NULL,
  address TEXT,
  city TEXT,
  state TEXT,
  zip VARCHAR(20),
  lat NUMERIC(10, 7) NOT NULL,
  lon NUMERIC(10, 7) NOT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Food banks: name, address, lat/lon for distance calculation.
CREATE TABLE IF NOT EXISTS food_banks (
  food_bank_id SERIAL PRIMARY KEY,
  name TEXT NOT NULL,
  address TEXT,
  city TEXT,
  state TEXT,
  zip VARCHAR(20),
  lat NUMERIC(10, 7) NOT NULL,
  lon NUMERIC(10, 7) NOT NULL,
  phone VARCHAR(50),
  url TEXT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_food_banks_lat_lon ON food_banks(lat, lon);

-- Store nearest-food-bank suggestion when recommendation is donate/discard.
ALTER TABLE suggestions
  ADD COLUMN IF NOT EXISTS donation_info TEXT;

COMMENT ON COLUMN suggestions.donation_info IS 'JSON or text: nearest food bank(s) when action is discard/donate (e.g. for UI to show "Donate to: X, Y")';

-- Optional: seed one facility and sample food banks (safe to re-run: skips if rows exist).
INSERT INTO facility (name, address, city, state, zip, lat, lon)
SELECT 'Main Store', '123 Main St', 'Boston', 'MA', '02101', 42.3601, -71.0589
WHERE NOT EXISTS (SELECT 1 FROM facility LIMIT 1);

INSERT INTO food_banks (name, address, city, state, zip, lat, lon, phone, url)
SELECT * FROM (VALUES
  ('Greater Boston Food Bank', '70 South Bay Ave', 'Boston', 'MA', '02118', 42.3362, -71.0689, '617-427-5200', 'https://www.gbfb.org'),
  ('Merrimack Valley Food Bank', '73 East St', 'Lowell', 'MA', '01852', 42.6334, -71.3162, '978-454-7272', NULL),
  ('Worcester County Food Bank', '474 Boston Tpke', 'Shrewsbury', 'MA', '01545', 42.2841, -71.7198, '508-842-3663', NULL)
) AS v(name, address, city, state, zip, lat, lon, phone, url)
WHERE (SELECT COUNT(*) FROM food_banks) = 0;
