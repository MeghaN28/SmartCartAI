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
EVALUATION_SIZE = 50


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


def build_coverage_chart(near_spoilage: float, covered: float, path: str) -> None:
    uncovered = max(near_spoilage - covered, 0)
    labels = ["Targeted for action", "Remaining near-expiry spoilage"]
    values = [covered, uncovered]
    colors = ["#4c78a8", "#e45756"]

    fig, ax = plt.subplots(figsize=(5, 4))
    bars = ax.bar(labels, values, color=colors)
    ax.set_title("Near-expiry spoilage coverage")
    ax.set_ylabel("Quantity (units)")
    ax.set_ylim(0, max(values) * 1.15 if max(values) > 0 else 1)
    for bar in bars:
        height = bar.get_height()
        ax.annotate(
            f"{int(height):,}",
            xy=(bar.get_x() + bar.get_width() / 2, height),
            xytext=(0, 6),
            textcoords="offset points",
            ha="center",
            va="bottom",
            fontsize=10,
        )

    plt.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def build_action_chart(action_counts: Dict[str, int], path: str) -> None:
    labels = list(action_counts.keys())
    values = [action_counts[label] for label in labels]
    colors = ["#4c78a8", "#f58518", "#54a24b", "#b279a2"][: len(labels)]

    fig, ax = plt.subplots(figsize=(5, 3))
    bars = ax.bar(labels, values, color=colors)
    ax.set_title("Action-type distribution (waste-reduction)")
    ax.set_ylabel("Suggestion count")
    for bar in bars:
        ax.annotate(
            f"{int(bar.get_height())}",
            xy=(bar.get_x() + bar.get_width() / 2, bar.get_height()),
            xytext=(0, 4),
            textcoords="offset points",
            ha="center",
            va="bottom",
            fontsize=9,
        )
    plt.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def build_resolution_chart(count: int, total: int, path: str) -> None:
    percent = 100 * count / total if total else 0
    fig, ax = plt.subplots(figsize=(5, 2.5))
    ax.barh(["Resolved"], [percent], color="#4c78a8")
    ax.set_xlim(0, 100)
    ax.set_xlabel("Resolution % of 50 items")
    ax.set_title("Evaluation coverage (50-item set)")
    ax.axvspan(80, 90, color="#54a24b", alpha=0.3, label="Target zone (80–90%)")
    ax.axvline(percent, color="#e45756", linestyle="--", label="Actual")
    ax.legend(loc="lower right", fontsize=8)
    ax.annotate(
        f"{percent:.1f}%",
        xy=(percent, 0),
        xytext=(3, -8),
        textcoords="offset points",
        ha="left",
        va="center",
        fontsize=10,
    )
    plt.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def build_expiring_chart(resolved: int, total: int, path: str) -> None:
    percent = 100 * resolved / total if total else 0
    fig, ax = plt.subplots(figsize=(5, 2.5))
    ax.barh(["Expiring subset"], [percent], color="#54a24b")
    ax.set_xlim(0, 100)
    ax.set_xlabel("Resolved % of expiring-soon items")
    ax.set_title("Expiring-soon items resolution")
    ax.axvspan(80, 90, color="#4c78a8", alpha=0.25, label="Target zone (80–90%)")
    ax.axvline(percent, color="#e45756", linestyle="--", label="Actual")
    ax.legend(loc="lower right", fontsize=8)
    ax.annotate(
        f"{percent:.1f}%",
        xy=(percent, 0),
        xytext=(3, -8),
        textcoords="offset points",
        ha="left",
        va="center",
        fontsize=10,
    )
    plt.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def main() -> None:
    inventory = fetch_df(
        "SELECT inventory_id, item_name, opening_stock, min_stock, expiry_date FROM inventory"
    )
    inventory["expiry_date"] = pd.to_datetime(inventory["expiry_date"])
    near_cutoff = EVALUATION_DATE + pd.Timedelta(days=7)
    near_expiry = inventory[inventory["expiry_date"] <= near_cutoff]

    suggestions = fetch_df(
        "SELECT inventory_id, action, created_at FROM suggestions WHERE action IS NOT NULL"
    )
    suggestions["action"] = suggestions["action"].str.lower()
    targeted_ids = set(suggestions[suggestions["action"].isin(WASTE_ACTIONS)]["inventory_id"])
    evaluation_master = pd.read_csv(EVALUATION_MASTER_CSV)
    evaluation_ids = set(evaluation_master["inventory_id"].astype(str))
    resolution_ids = targeted_ids & evaluation_ids
    resolution_count = len(resolution_ids)
    resolution_percent = 100 * resolution_count / EVALUATION_SIZE

    consumption = fetch_df(
        "SELECT inventory_id, quantity_consumed, consumption_reason FROM consumption"
    )
    consumption["consumption_reason"] = (
        consumption["consumption_reason"].fillna("").str.lower()
    )
    spoilage = consumption[consumption["consumption_reason"] == "spoilage"]
    near_spoilage = spoilage[
        spoilage["inventory_id"].isin(near_expiry["inventory_id"])
    ]
    near_spoil_total = near_spoilage["quantity_consumed"].sum()
    targeted_spoilage = near_spoilage[
        near_spoilage["inventory_id"].isin(targeted_ids)
    ]["quantity_consumed"].sum()
    coverage_pct = (
        100 * targeted_spoilage / near_spoil_total if near_spoil_total else 0
    )

    action_counts = (
        suggestions[suggestions["action"].isin(WASTE_ACTIONS)]
        .groupby("action")
        .size()
        .sort_values(ascending=False)
        .to_dict()
    )
    expiring_eval_ids = set(near_expiry["inventory_id"]) & evaluation_ids
    expiring_resolved = len(targeted_ids & expiring_eval_ids)
    expiring_percent = (
        100 * expiring_resolved / len(expiring_eval_ids)
        if expiring_eval_ids
        else 0
    )

    os.makedirs("analysis", exist_ok=True)
    build_coverage_chart(
        near_spoil_total, targeted_spoilage, "analysis/waste_spoilage_coverage.png"
    )
    build_action_chart(action_counts, "analysis/waste_action_counts.png")
    build_expiring_chart(
        expiring_resolved, len(expiring_eval_ids), "analysis/expiring_resolution.png"
    )

    print(f"Near-expiry spoilage (<= {near_cutoff.date()}): {near_spoil_total:,} units")
    print(f"Targeted spoilage from actionable items: {targeted_spoilage:,} units")
    print(f"Coverage of near-expiry spoilage: {coverage_pct:.1f}%")
    print(f"Action counts: {action_counts}")
    print(
        f"Resolution % (Resolved / {EVALUATION_SIZE}): {resolution_percent:.1f}% "
        f"({resolution_count} resolved items: {', '.join(sorted(resolution_ids))})"
    )
    print(
        f"Expiring-soon subset: {len(expiring_eval_ids)} items, {expiring_resolved} resolved → {expiring_percent:.1f}%"
    )
    build_resolution_chart(
        resolution_count, EVALUATION_SIZE, "analysis/waste_resolution_percent.png"
    )


if __name__ == "__main__":
    main()
