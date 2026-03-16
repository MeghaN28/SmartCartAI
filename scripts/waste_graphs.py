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
ACTION_SHARE_KEYS = ["bundle", "discount", "discard", "donate", "reorder"]

EVALUATION_DATE = pd.Timestamp("2026-03-13")

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

    fig, ax = plt.subplots(figsize=(6,4))
    bars = ax.bar(labels, values)

    ax.set_title("Waste Reduction Action Distribution")
    ax.set_ylabel("Inventory Units")

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


def build_resolution_chart(resolved_stock, total_expiring_stock, path):

    percent = 100 * resolved_stock / total_expiring_stock if total_expiring_stock else 0

    fig, ax = plt.subplots(figsize=(6,3))

    ax.barh(["Resolved expiring stock"], [percent])

    ax.set_xlim(0,100)
    ax.set_xlabel("Resolution %")
    ax.set_title("Operational Resolution for Expiring Inventory")

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

    fig, ax = plt.subplots(figsize=(6,4))
    bars = ax.bar(labels, values)

    ax.set_title("Food Waste Reduction Impact")
    ax.set_ylabel("Inventory Units")

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

    fig, ax = plt.subplots(figsize=(6,4))

    bars = ax.bar(
        ["Food donated value", "Corporate tax savings"],
        [donation_value, tax_savings]
    )

    ax.set_title("Tax Benefit from Food Donation")
    ax.set_ylabel("USD")

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


def build_health_chart(discarded_stock, path):

    fig, ax = plt.subplots(figsize=(6,4))

    bars = ax.bar(["Expired items safely discarded"], [discarded_stock])

    ax.set_title("Public Health Protection Impact")
    ax.set_ylabel("Inventory Units")

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


def build_stock_breakdown_chart(total_stock, expiring_stock, resolved_stock, remaining_waste_stock, path):

    labels = ["Total inventory", "Expiring stock", "Resolved by SmartCart", "Remaining waste"]
    values = [total_stock, expiring_stock, resolved_stock, remaining_waste_stock]
    percent = 100 * resolved_stock / expiring_stock if expiring_stock else 0

    fig, ax = plt.subplots(figsize=(7,4))
    bars = ax.bar(labels, values, color=["#5b9bd5", "#ed7d31", "#70ad47", "#a5a5a5"])

    ax.set_ylabel("Inventory units")
    ax.set_title("Inventory vs. Waste Resolution")

    for bar in bars:
        ax.annotate(
            f"{int(bar.get_height())}",
            xy=(bar.get_x() + bar.get_width()/2, bar.get_height()),
            xytext=(0,4),
            textcoords="offset points",
            ha="center"
        )

    ax.text(2.2, max(values) * 0.85 if max(values) else 0, f"{percent:.1f}% of expiring resolved", fontsize=10, color="#444444")

    plt.tight_layout()
    fig.savefig(path)
    plt.close()


def build_action_percentage_chart(action_percentages, path):

    total = sum(action_percentages.values())
    fig, ax = plt.subplots(figsize=(6,6))

    if total <= 0:
        ax.text(0.5, 0.5, "No action data available", ha="center", va="center", fontsize=12)
        ax.set_axis_off()
    else:
        labels = list(action_percentages.keys())
        sizes = [action_percentages[label] for label in labels]
        ax.pie(
            sizes,
            labels=labels,
            autopct="%1.1f%%",
            startangle=140,
            wedgeprops={"linewidth": 0.5, "edgecolor": "white"}
        )
        ax.set_title("Action share across key tactics")
        ax.axis("equal")

    plt.tight_layout()
    fig.savefig(path)
    plt.close()


def build_donation_savings_chart(donation_value, tax_savings, total_benefit, path):

    fig, ax = plt.subplots(figsize=(6,4))

    bars = ax.bar(
        ["Donation value", "Tax savings", "Total benefit"],
        [donation_value, tax_savings, total_benefit],
        color=["#5b9bd5", "#70ad47", "#ffc000"]
    )

    ax.set_title("Corporate benefit from donations")
    ax.set_ylabel("USD")

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


def build_stockout_chart(before_gap, after_gap, path):

    labels = ["Stockout risk before", "Stockout risk after"]
    values = [before_gap, after_gap]

    fig, ax = plt.subplots(figsize=(6,4))
    bars = ax.bar(labels, values, color=["#ed7d31", "#70ad47"])

    ax.set_title("Projected stockout prevention")
    ax.set_ylabel("Inventory units at risk")

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


def print_waste_summary(total_inventory_stock, total_expiring_stock, recovered_discount, recovered_bundle,
                        recovered_donation, discard_stock):
    rows = [
        ("Total inventory", total_inventory_stock),
        ("Potential waste stock", total_expiring_stock),
        ("Recovered via discount", recovered_discount),
        ("Recovered via bundle", recovered_bundle),
        ("Recovered via donation", recovered_donation),
        ("Discarded (unsafe)", discard_stock),
    ]
    label_width = max(len(label) for label, _ in rows)
    print("\nWaste recovery summary")
    for label, value in rows:
        print(f"{label.ljust(label_width)} : {int(value)}")


def main():

    inventory = fetch_df(
        "SELECT inventory_id, item_name, opening_stock, expiry_date FROM inventory"
    )

    inventory["expiry_date"] = pd.to_datetime(inventory["expiry_date"])

    near_cutoff = EVALUATION_DATE + pd.Timedelta(days=7)

    expiring = inventory[inventory["expiry_date"] <= near_cutoff]

    expiring_ids = set(expiring["inventory_id"])

    suggestions = fetch_df(
        "SELECT inventory_id, action, current_stock, min_stock, forecasted_demand FROM suggestions WHERE action IS NOT NULL"
    )

    suggestions["action"] = suggestions["action"].str.lower()
    for column in ["current_stock", "min_stock", "forecasted_demand"]:
        suggestions[column] = pd.to_numeric(suggestions[column], errors="coerce").fillna(0)

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

    discarded_ids = set(
        suggestions[suggestions["action"]=="discard"]["inventory_id"]
    )

    donate_ids = set(
        suggestions[suggestions["action"]=="donate"]["inventory_id"]
    )

    suggestions_with_stock = suggestions.merge(
        inventory[["inventory_id", "opening_stock"]],
        on="inventory_id",
        how="left"
    ).rename(columns={"opening_stock": "inventory_opening_stock"})

    suggestions_with_stock["inventory_opening_stock"] = (
        suggestions_with_stock["inventory_opening_stock"].fillna(suggestions_with_stock["current_stock"])
    )

    reorder_suggestions = suggestions[suggestions["action"] == "reorder"].copy()
    reorder_total_qty = 0
    stockout_gap_before = 0
    stockout_gap_after = 0
    if not reorder_suggestions.empty:
        reorder_suggestions["target_stock"] = reorder_suggestions[["min_stock", "forecasted_demand"]].max(axis=1)
        reorder_suggestions["reorder_qty"] = (reorder_suggestions["target_stock"] - reorder_suggestions["current_stock"]).clip(lower=0)
        reorder_suggestions["stockout_gap_before"] = (
            reorder_suggestions["forecasted_demand"] - reorder_suggestions["current_stock"]
        ).clip(lower=0)
        reorder_suggestions["post_reorder_stock"] = (
            reorder_suggestions["current_stock"] + reorder_suggestions["reorder_qty"]
        )
        reorder_suggestions["stockout_gap_after"] = (
            reorder_suggestions["forecasted_demand"] - reorder_suggestions["post_reorder_stock"]
        ).clip(lower=0)
        reorder_total_qty = reorder_suggestions["reorder_qty"].sum()
        stockout_gap_before = reorder_suggestions["stockout_gap_before"].sum()
        stockout_gap_after = reorder_suggestions["stockout_gap_after"].sum()

    # STOCK BASED CALCULATIONS

    total_inventory_stock = inventory["opening_stock"].sum()

    total_expiring_stock = expiring["opening_stock"].sum()

    resolved_stock = inventory[
        inventory["inventory_id"].isin(resolved_ids)
    ]["opening_stock"].sum()

    remaining_waste_stock = total_expiring_stock - resolved_stock

    discard_stock = inventory[
        inventory["inventory_id"].isin(discarded_ids)
    ]["opening_stock"].sum()

    donate_stock = inventory[
        inventory["inventory_id"].isin(donate_ids)
    ]["opening_stock"].sum()

    donation_value = donate_stock * DONATION_VALUE_ESTIMATE

    resolution_percent = (
        100 * resolved_stock / total_expiring_stock
        if total_expiring_stock else 0
    )

    action_unit_totals = {}
    for action in ACTION_SHARE_KEYS:
        if action == "reorder":
            action_unit_totals["reorder"] = reorder_total_qty
        else:
            action_unit_totals[action] = (
                suggestions_with_stock[suggestions_with_stock["action"] == action]["inventory_opening_stock"].sum()
            )

    action_unit_total = sum(action_unit_totals.values())
    if action_unit_total <= 0:
        action_percentages = {action: 0 for action in ACTION_SHARE_KEYS}
    else:
        action_percentages = {
            action: 100 * value / action_unit_total
            for action, value in action_unit_totals.items()
        }

    recovered_discount = action_unit_totals.get("discount", 0)
    recovered_bundle = action_unit_totals.get("bundle", 0)
    recovered_donation = action_unit_totals.get("donate", 0)

    formatted_action_shares = {
        action: f"{percentage:.1f}%"
        for action, percentage in action_percentages.items()
    }

    tax_savings = donation_value * CORPORATE_TAX_RATE
    donation_total_benefit = donation_value + tax_savings

    stockout_prevented = stockout_gap_before - stockout_gap_after
    stockout_reduction_percent = (
        100 * stockout_prevented / stockout_gap_before
        if stockout_gap_before else 0
    )

    os.makedirs("analysis", exist_ok=True)

    build_action_chart(
        action_counts,
        "analysis/action_distribution.png"
    )

    build_action_percentage_chart(
        action_percentages,
        "analysis/action_percent_breakdown.png"
    )

    build_resolution_chart(
        resolved_stock,
        total_expiring_stock,
        "analysis/resolution_percent.png"
    )

    build_before_after_chart(
        total_expiring_stock,
        remaining_waste_stock,
        "analysis/before_after_waste.png"
    )

    build_stock_breakdown_chart(
        total_inventory_stock,
        total_expiring_stock,
        resolved_stock,
        remaining_waste_stock,
        "analysis/stock_vs_expiring_vs_resolved.png"
    )

    build_tax_chart(
        donation_value,
        CORPORATE_TAX_RATE,
        "analysis/donation_tax_benefit.png"
    )

    build_donation_savings_chart(
        donation_value,
        tax_savings,
        donation_total_benefit,
        "analysis/donation_revenue_savings.png"
    )

    build_health_chart(
        discard_stock,
        "analysis/health_safety_discard.png"
    )

    build_stockout_chart(
        stockout_gap_before,
        stockout_gap_after,
        "analysis/stockout_prevention.png"
    )

    print("\nEVALUATION SUMMARY\n")

    print(f"Total inventory stock units: {total_inventory_stock}")

    print(f"Expiring stock units (<=7 days): {total_expiring_stock}")

    print(f"Stock resolved by SmartCart: {resolved_stock}")

    print(f"Operational resolution: {resolution_percent:.1f}%")

    print(f"Action distribution (units): {action_counts}")

    print(f"Action share (% of key tactics): {formatted_action_shares}")
    print(f"Planned reorder quantity: {reorder_total_qty}")

    print(f"Remaining potential waste stock: {remaining_waste_stock}")

    print(f"Discarded unsafe stock: {discard_stock}")

    print(f"Donated stock: {donate_stock}")

    print(f"Estimated donation revenue saved: ${donation_value:,.2f}")

    print(f"Estimated tax savings from donations: ${tax_savings:,.2f}")

    print(f"Combined donation benefit: ${donation_total_benefit:,.2f}")

    print(f"Stockout risk before reorder: {stockout_gap_before}")

    print(f"Stockout risk after reorder: {stockout_gap_after}")

    print(f"Stockout units prevented: {stockout_prevented}")

    print(f"Reorder impact: {stockout_reduction_percent:.1f}% reduction in at-risk units")

    print_waste_summary(
        total_inventory_stock,
        total_expiring_stock,
        recovered_discount,
        recovered_bundle,
        recovered_donation,
        discard_stock,
    )

    print("\nCharts saved in /analysis directory\n")


if __name__ == "__main__":
    main()
