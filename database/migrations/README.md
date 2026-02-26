# Database migrations

Run these on your existing `smartcart_ai` database when needed.

## 1. Expiry and selling price (inventory)

Adds `expiry_date` and `selling_price` to `inventory` for waste management and price optimization.

```bash
psql -h localhost -U your_user -d smartcart_ai -f database/migrations/add_expiry_and_price.sql
```

## 2. Suggestion discount/waste fields (optional)

Adds `suggested_discount_percent` and `waste_action` to `suggestions`.

```bash
psql -h localhost -U your_user -d smartcart_ai -f database/migrations/add_suggestion_discount_waste.sql
```

## 3. RAGAS evaluation tables

Adds tables/views to store LLM evaluation runs and per-case RAGAS metric scores.

```bash
psql -h localhost -U your_user -d smartcart_ai -f database/migrations/add_ragas_evaluation_tables.sql
```

After running (1), you can set expiry and price per item, e.g.:

```sql
UPDATE inventory SET expiry_date = CURRENT_DATE + 7, selling_price = 4.99 WHERE item_name ILIKE '%apple%';
```
