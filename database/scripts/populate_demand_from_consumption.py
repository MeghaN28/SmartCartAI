#!/usr/bin/env python3
"""Populate the demand table from real consumption history.

The demand table was empty, which meant the Decision Orchestrator's demand_signal
classification (get_demand_signal() in Agents/decision-orchestration-agent/agent.py)
always returned "unknown" -- every item fell through to the "hold" fallback regardless
of expiry proximity, so the waste-intervention policy (donate/discount/bundle) never
triggered.

predicted_demand is computed per item as mean daily demand over the last 7 days of
available consumption history: SUM(quantity_consumed) / 7, i.e. exactly the "Mean
Daily Demand" metric the paper's Table 5 already documents as the system's demand
baseline -- this ties demand_signal to real per-item consumption data instead of an
arbitrary manual value (cf. database/scripts/set_all_high_demand.sql, which sets every
item to the same flat number and was a dev/testing convenience, not a realistic input).

Run: python3 database/scripts/populate_demand_from_consumption.py
"""
import psycopg2
from psycopg2.extras import RealDictCursor

DB_HOST = "localhost"
DB_USER = "meghanarendrasimha"
DB_PASSWORD = "Welcome@123"
DB_NAME = "smartcart_ai"


def main():
    conn = psycopg2.connect(
        host=DB_HOST, dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD,
        cursor_factory=RealDictCursor,
    )
    cur = conn.cursor()

    cur.execute("DELETE FROM demand")

    cur.execute(
        """
        INSERT INTO demand (inventory_id, predicted_demand, model_version, prediction_date)
        SELECT
            c.inventory_id,
            ROUND(SUM(c.quantity_consumed) / 7.0)::int AS predicted_demand,
            'consumption-7d-avg',
            CURRENT_DATE
        FROM consumption c
        WHERE c.transaction_date > (SELECT MAX(transaction_date) FROM consumption) - INTERVAL '7 days'
        GROUP BY c.inventory_id
        """
    )
    inserted = cur.rowcount
    conn.commit()

    cur.execute("SELECT COUNT(*) AS n FROM inventory i WHERE NOT EXISTS (SELECT 1 FROM demand d WHERE d.inventory_id = i.inventory_id)")
    missing = cur.fetchone()["n"]

    cur.close()
    conn.close()

    print(f"Inserted {inserted} demand rows from the last 7 days of consumption history.")
    if missing:
        print(f"WARNING: {missing} inventory item(s) have no recent consumption history and got no demand row.")


if __name__ == "__main__":
    main()
