# Food Bank Subagent

Finds **nearest food banks** for donation suggestions when the system recommends **discard** or **sell/donate soon** (near-expiry).

## Behavior

- Reads `facility` (default store location) and `food_banks` from PostgreSQL.
- **Haversine** distance in miles; returns list sorted by distance.
- Used by the Decision Orchestrator when action is `discard` or when the user asks about waste/donate, so recommendations can include "Consider donating to: [nearest food banks]".

## Endpoints

- `POST /nearest` – body optional: `{ "lat", "lon", "limit" }`. If `lat`/`lon` omitted, uses facility location.
- `GET /nearest?lat=&lon=&limit=5` – same via query params.
- `GET /health`

## Database

Run migration first:

```bash
psql -U meghanarendrasimha -d smartcart_ai -f database/migrations/add_facility_food_banks_donation.sql
```

Then insert at least one facility and some food banks:

```sql
INSERT INTO facility (name, address, city, state, zip, lat, lon)
VALUES ('Main Store', '123 Main St', 'Boston', 'MA', '02101', 42.3601, -71.0589);

INSERT INTO food_banks (name, address, city, state, zip, lat, lon, phone, url)
VALUES
  ('Boston Food Bank', '70 South Bay Ave', 'Boston', 'MA', '02118', 42.3362, -71.0689, '555-0100', 'https://example.org'),
  ('Greater Boston Food Bank', '160 Royall St', 'Canton', 'MA', '02021', 42.1584, -71.1418, '555-0101', NULL);
```

## Env

Same as other subagents: `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`. Optional: `PORT` (default 9007).
