-- Refresh facility + food_banks to California data using
-- /Users/meghanarendrasimha/Downloads/Food_Resources_in_California_20260217.csv
--
-- Run:
-- psql -h localhost -U <user> -d smartcart_ai -f database/scripts/load_california_food_banks.sql

BEGIN;

-- Replace Boston (or older) location with one California facility row.
TRUNCATE TABLE facility RESTART IDENTITY;
INSERT INTO facility (name, address, city, state, zip, lat, lon)
VALUES (
  'California Main Store',
  '7900 Edgewater Drive',
  'Oakland',
  'CA',
  '94621',
  37.741538,
  -122.201300
);

-- Replace food bank list with California resource dataset.
TRUNCATE TABLE food_banks RESTART IDENTITY;

CREATE TEMP TABLE food_banks_ca_staging (
  name TEXT,
  street_address TEXT,
  city TEXT,
  state TEXT,
  zip_code TEXT,
  county TEXT,
  phone TEXT,
  description TEXT,
  resource_type TEXT,
  web_link TEXT,
  notes TEXT,
  latitude TEXT,
  longitude TEXT
);

\copy food_banks_ca_staging(name,street_address,city,state,zip_code,county,phone,description,resource_type,web_link,notes,latitude,longitude) FROM '/Users/meghanarendrasimha/Downloads/Food_Resources_in_California_20260217.csv' WITH (FORMAT csv, HEADER true)

INSERT INTO food_banks (name, address, city, state, zip, lat, lon, phone, url)
SELECT DISTINCT
  btrim(name) AS name,
  NULLIF(btrim(street_address), '') AS address,
  NULLIF(btrim(city), '') AS city,
  'CA' AS state,
  NULLIF(LEFT(regexp_replace(COALESCE(zip_code, ''), '[^0-9]', '', 'g'), 5), '') AS zip,
  CAST(latitude AS NUMERIC(10, 7)) AS lat,
  CAST(longitude AS NUMERIC(10, 7)) AS lon,
  NULLIF(LEFT(btrim(phone), 50), '') AS phone,
  NULLIF(btrim(web_link), '') AS url
FROM food_banks_ca_staging
WHERE UPPER(COALESCE(state, '')) = 'CA'
  AND NULLIF(btrim(name), '') IS NOT NULL
  AND NULLIF(btrim(latitude), '') IS NOT NULL
  AND NULLIF(btrim(longitude), '') IS NOT NULL
  AND LOWER(COALESCE(resource_type, '')) IN ('food bank', 'food pantry');

COMMIT;
