Run the SQL scripts in this folder to modify demand predictions used by agents.

**How demand is used:** Both the Inventory Agent and Chat Agent use `demand.predicted_demand` as a **daily demand floor**. Forecasted demand = max(ETS forecast from consumption history, predicted_demand). So inserting rows here makes demand "higher" and can trigger DISCOUNT (medium lot + demand more) instead of DONATE.

set_high_demand.sql
- Purpose: set predicted demand for a single item by name. Default: Banana -> 50 units/day.
- Usage (psql):

  psql -h <host> -U <user> -d <database> -f database/scripts/set_high_demand.sql

  Override item and value:

  psql -v ITEM_NAME='Milk 1L' -v DEMAND_VAL=100 -h <host> -U <user> -d <database> -f database/scripts/set_high_demand.sql

set_all_high_demand.sql
- Purpose: set the same predicted demand for ALL inventory items (default 25 units/day). Use to **increase demand** globally so DISCOUNT suggestions trigger more and DONATE less.
- Usage (run from project root or pass correct path):

  psql -h <host> -U <user> -d <database> -f database/scripts/set_all_high_demand.sql

  To increase demand further (e.g. 50 units/day):

  psql -v DEMAND_VAL=50 -h <host> -U <user> -d <database> -f database/scripts/set_all_high_demand.sql

Notes:
- Tables `inventory` and `demand` must exist (see database/schema.sql).
- If your DB user lacks permissions, run as superuser or admin.
