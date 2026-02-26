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
SELECT 'Main Store', '7900 Edgewater Drive', 'Oakland', 'CA', '94621', 37.741538, -122.201300
WHERE NOT EXISTS (SELECT 1 FROM facility LIMIT 1);

INSERT INTO food_banks (name, address, city, state, zip, lat, lon, phone, url)
SELECT * FROM (VALUES
  ('Alameda County Community Food Bank', '7900 Edgewater Drive', 'Oakland', 'CA', '94621', 37.741538, -122.201300, '510-635-3663', 'https://www.accfb.org/'),
  ('Alameda Food Bank', '650 W Ranger Avenue', 'Alameda', 'CA', '94501', 37.784108, -122.299112, '510-523-5850', 'http://www.alamedafoodbank.org/'),
  ('Agnes Memorial Church Of God In Christ', '2372 International Boulevard', 'Oakland', 'CA', '94601', 37.783047, -122.234238, '510-533-1101', 'http://agnesmemorialchurch.com')
) AS v(name, address, city, state, zip, lat, lon, phone, url)
WHERE (SELECT COUNT(*) FROM food_banks) = 0;
