# ER Diagram & Normalization

Entity–relationship view of the SmartCartAI schema and how it satisfies normal forms.

---

## ER Diagram (Mermaid)

```mermaid
erDiagram
    inventory ||--o{ sales : "sold in"
    inventory ||--o{ consumption : "consumed in"
    inventory ||--o{ demand : "predicted for"
    inventory ||--o{ suggestions : "recommended for"
    vendor ||--o{ inventory : "supplies"
    vendor ||--o{ sales : "invoiced by"
    suggestions ||--o{ suggestion_food_bank : "matched to"
    food_banks ||--o{ suggestion_food_bank : "matched from"

    inventory {
        varchar inventory_id PK
        text item_name
        text category
        text form
        text use
        text item_type
        varchar vendor_id FK
        int min_stock
        int max_capacity
        int opening_stock
        date expiry_date
        varchar expiry_date_type
        numeric selling_price
    }

    vendor {
        varchar vendor_id PK
        text name
        text contact_email
        varchar phone
        timestamp created_at
    }

    sales {
        varchar invoice_id PK
        varchar vendor_id FK
        varchar inventory_id FK
        date purchase_date
        int quantity
        numeric unit_cost
        numeric total_cost
        text payment_status
        text account_code
        date delivery_date
    }

    consumption {
        varchar transaction_id PK
        date date
        varchar inventory_id FK
        int quantity_consumed
        text department
        varchar staff_id
        text shift
        text consumption_reason
        int remaining_stock
        text batch_lot
    }

    demand {
        serial demand_id PK
        varchar inventory_id FK
        int predicted_demand
        text model_version
        date prediction_date
    }

    suggestions {
        serial suggestion_id PK
        varchar inventory_id FK
        text item_name
        text user_query
        varchar action
        varchar priority
        text reasoning
        text expected_outcome
        varchar risk_level
        int risk_score
        boolean is_feasible
        numeric estimated_cost
        boolean within_budget
        text explanation
        int current_stock
        int min_stock
        numeric forecasted_demand
        timestamp created_at
        varchar status
        text donation_info "deprecated: legacy JSON snapshot, pre-migration rows only"
    }

    suggestion_food_bank {
        serial id PK
        int suggestion_id FK
        int food_bank_id FK
        int rank
        numeric distance_mi
    }

    facility {
        serial facility_id PK
        text name
        text address
        text city
        text state
        varchar zip
        numeric lat
        numeric lon
        timestamp created_at
    }

    food_banks {
        serial food_bank_id PK
        text name
        text address
        text city
        text state
        varchar zip
        numeric lat
        numeric lon
        varchar phone
        text url
        timestamp created_at
    }
```

---

## Normalization

### 1NF (First Normal Form)

- **Rule**: Atomic values; no repeating groups; each row uniquely identified.
- **Applied**:
  - All attributes hold single values (no lists or nested structures).
  - No repeating groups (e.g. multiple “quantity” columns).
  - Each table has a primary key: `inventory_id`, `invoice_id`, `transaction_id`, `demand_id`.

### 2NF (Second Normal Form)

- **Rule**: 1NF + every non-key attribute depends on the **whole** primary key (no partial dependency).
- **Applied**:
  - **inventory**: PK is `inventory_id` (single column); all attributes describe the inventory item.
  - **sales**: PK is `invoice_id`; attributes describe the invoice line (vendor, inventory, dates, costs, etc.).
  - **consumption**: PK is `transaction_id`; attributes describe the consumption event.
  - **demand**: PK is `demand_id`; attributes describe the prediction.
- **suggestions**: PK is `suggestion_id`; attributes describe the AI recommendation; `inventory_id` is FK.
- **facility**: PK is `facility_id`; attributes describe the store location.
- **food_banks**: PK is `food_bank_id`; attributes describe the food bank. No composite PKs, so no partial dependencies.
- **vendor**: PK is `vendor_id`; attributes describe the vendor.
- **suggestion_food_bank**: PK is `id`; `rank`/`distance_mi` describe the (suggestion, food bank) match itself, not either FK column alone -- this is why it's a separate table rather than columns bolted onto `suggestions`.

### 3NF (Third Normal Form)

- **Rule**: 2NF + no non-key attribute depends on another non-key attribute (no transitive dependency).
- **Applied**:
  - **inventory**: Non-key attributes (item_name, category, form, use, item_type, vendor_id, min_stock, max_capacity, opening_stock, expiry_date, expiry_date_type, selling_price) depend only on `inventory_id`. `vendor_id` is now a proper FK into `vendor` (see below) rather than a repeated code.
  - **sales**: Attributes depend on the invoice line; `inventory_id` and `vendor_id` are FKs, not stored descriptive attributes that depend on each other.
  - **consumption**: Attributes depend on the transaction; `inventory_id` is FK only.
  - **demand**: Attributes depend on the prediction record; `inventory_id` is FK only.
  - **suggestions**: Attributes depend on the recommendation; `inventory_id` is FK only. `donation_info` (legacy JSON snapshot) is deprecated -- it stored `food_banks.name`/`address` as a duplicated blob (a transitive dependency, not just JSON-in-TEXT), which `suggestion_food_bank` below removes.
  - **vendor**: Attributes (name, contact_email, phone) depend only on `vendor_id`.
  - **suggestion_food_bank**: `food_bank_id` references `food_banks` by key only; name/address are looked up via the FK at read time instead of being copied in, so there's no transitive dependency on `food_banks`' non-key columns.
  - **facility** and **food_banks**: Standalone reference data; no transitive dependencies.

### Summary

| Table                 | 1NF | 2NF | 3NF |
|-----------------------|-----|-----|-----|
| inventory              | ✓   | ✓   | ✓   |
| sales                  | ✓   | ✓   | ✓   |
| consumption            | ✓   | ✓   | ✓   |
| demand                 | ✓   | ✓   | ✓   |
| suggestions            | ✓   | ✓   | ✓   |
| vendor                 | ✓   | ✓   | ✓   |
| suggestion_food_bank   | ✓   | ✓   | ✓   |
| facility               | ✓   | ✓   | ✓   |
| food_banks             | ✓   | ✓   | ✓   |

The schema is in **third normal form (3NF)**.

**Notes:**
- **suggestions**: AI-generated recommendations; `inventory_id` FK links to the item. `donation_info` (TEXT) is a deprecated JSON snapshot of nearest food banks, kept only so suggestions written before `suggestion_food_bank` existed still render; new rows are written to `suggestion_food_bank` instead (see below).
- **suggestion_food_bank**: Normalized nearest-food-bank match per suggestion (`suggestion_id` FK, `food_bank_id` FK, `rank`, `distance_mi`). One row per match instead of a JSON array in a TEXT column, so matches can be queried/joined/indexed and don't duplicate `food_banks.name`/`address`.
- **vendor**: Referenced from `inventory.vendor_id` and `sales.vendor_id` (both FK, `database/migrations/add_vendor_table.sql`). Previously `vendor_id` was a bare code with no lookup entity or referential integrity.
- **facility**: Store/warehouse location (lat/lon) used by the Food Bank agent as the origin for "nearest" distance.
- **food_banks**: Reference list of food banks (name, address, lat/lon); Food Bank agent computes nearest by distance; referenced by `suggestion_food_bank.food_bank_id`.
