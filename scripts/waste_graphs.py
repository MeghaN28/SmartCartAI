#!/usr/bin/env python3
import io
import os
import subprocess
from typing import Dict

import matplotlib.pyplot as plt
import pandas as pd


PGPASS = "Welcome@123"
DB_HOST = "localhost"
DB_USER = "meghanarendrasimha"
DB_NAME = "smartcart_ai"

WASTE_ACTIONS = {"discount", "donate", "bundle", "discard"}

EVALUATION_DATE = pd.Timestamp("2026-03-13")
EVALUATION_MASTER_CSV = "Dataset/inventory_master_50_unique.csv"

CORPORATE_TAX_RATE = 0.21
DONATION_VALUE_ESTIMATE = 200


def fetch_df(query: str) -> pd.DataFrame:
    env = os.environ.copy()
    env["PGPASSWORD"] = PGPASS

    cmd = [
        "psql",
        "-h",
        DB_HOST,
        "-U",
        DB_USER,
        "-d",
        DB_NAME,
        "-c",
        f"COPY ({query}) TO STDOUT WITH CSV HEADER",
    ]

    proc = subprocess.run(cmd, env=env, capture_output=True, text=True)
    proc.check_returncode()

    return pd.read_csv(io.StringIO(proc.stdout))


def build_action_chart(action_counts: Dict[str, int], path: str):

    labels = list(action_counts.keys())
    values = [action_counts[k] for k in labels]

    fig, ax = plt.subplots(figsize=(5,3))
    bars = ax.bar(labels, values)

    ax.set_title("Waste-reduction action distribution")
    ax.set_ylabel("Items")

    for bar in bars:
        ax.annotate(
            f"{int(bar.get_height())}",
            xy=(bar.get_x() + bar.get_width()/2, bar.get_height()),
            xytext=(0,4),
            textcoords="offset points",
            ha="center"
        )

    plt.tight_layout()
    fig.savefig(path)
    plt.close()


def build_resolution_chart(resolved, total, path):

    percent = 100 * resolved / total if total else 0

    fig, ax = plt.subplots(figsize=(5,2.5))

    ax.barh(["Expiring items resolved"], [percent])

    ax.set_xlim(0,100)
    ax.set_xlabel("Resolution %")

    ax.set_title("Operational resolution for expiring items")

    ax.axvspan(80,90, alpha=0.3)
    ax.axvline(percent, linestyle="--")

    ax.annotate(
        f"{percent:.1f}%",
        xy=(percent,0),
        xytext=(3,-8),
        textcoords="offset points"
    )

    plt.tight_layout()
    fig.savefig(path)
    plt.close()


def build_before_after_chart(before, after, path):

    labels = ["Potential spoilage", "After SmartCart actions"]
    values = [before, after]

    fig, ax = plt.subplots(figsize=(5,3))
    bars = ax.bar(labels, values)

    ax.set_title("Food waste reduction impact")
    ax.set_ylabel("Items")

    for bar in bars:
        ax.annotate(
            f"{int(bar.get_height())}",
            xy=(bar.get_x()+bar.get_width()/2, bar.get_height()),
            xytext=(0,4),
            textcoords="offset points",
            ha="center"
        )

    plt.tight_layout()
    fig.savefig(path)
    plt.close()


def build_tax_chart(donation_value, tax_rate, path):

    tax_savings = donation_value * tax_rate

    fig, ax = plt.subplots(figsize=(5,3))

    ax.bar(
        ["Food donated value", "Corporate tax savings"],
        [donation_value, tax_savings]
    )

    ax.set_title("Tax benefit from food donation")
    ax.set_ylabel("USD")

    plt.tight_layout()
    fig.savefig(path)
    plt.close()


def build_health_chart(discarded_items, path):

    fig, ax = plt.subplots(figsize=(5,3))

    ax.bar(["Expired items safely discarded"], [discarded_items])

    ax.set_title("Public health protection impact")
    ax.set_ylabel("Items")

    plt.tight_layout()
    fig.savefig(path)
    plt.close()


def main():

    inventory = fetch_df(
        "SELECT inventory_id, item_name, opening_stock, expiry_date FROM inventory"
    )

    inventory["expiry_date"] = pd.to_datetime(inventory["expiry_date"])

    near_cutoff = EVALUATION_DATE + pd.Timedelta(days=7)

    expiring = inventory[inventory["expiry_date"] <= near_cutoff]

    expiring_ids = set(expiring["inventory_id"])

    suggestions = fetch_df(
        "SELECT inventory_id, action FROM suggestions WHERE action IS NOT NULL"
    )

    suggestions["action"] = suggestions["action"].str.lower()

    action_counts = (
        suggestions[suggestions["action"].isin(WASTE_ACTIONS)]
        .groupby("action")
        .size()
        .to_dict()
    )

    targeted_ids = set(
        suggestions[suggestions["action"].isin(WASTE_ACTIONS)]["inventory_id"]
    )

    resolved_ids = targeted_ids & expiring_ids

    resolved_count = len(resolved_ids)

    total_expiring = len(expiring_ids)

    resolution_percent = 100 * resolved_count / total_expiring

    discard_count = action_counts.get("discard", 0)

    remaining_waste = total_expiring - resolved_count

    os.makedirs("analysis", exist_ok=True)

    build_action_chart(
        action_counts,
        "analysis/action_distribution.png"
    )

    build_resolution_chart(
        resolved_count,
        total_expiring,
        "analysis/resolution_percent.png"
    )

    build_before_after_chart(
        total_expiring,
        remaining_waste,
        "analysis/before_after_waste.png"
    )

    build_tax_chart(
        DONATION_VALUE_ESTIMATE,
        CORPORATE_TAX_RATE,
        "analysis/donation_tax_benefit.png"
    )

    build_health_chart(
        discard_count,
        "analysis/health_safety_discard.png"
    )

    print("\nEVALUATION SUMMARY\n")

    print(f"Total inventory items: {len(inventory)}")

    print(f"Expiring items (<=7 days): {total_expiring}")

    print(f"Items with SmartCart actions: {resolved_count}")

    print(f"Operational resolution: {resolution_percent:.1f}%")

    print(f"Action distribution: {action_counts}")

    print(f"Remaining potential waste: {remaining_waste}")

    print("\nCharts saved in /analysis directory\n")


if __name__ == "__main__":
    main()