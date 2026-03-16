#!/usr/bin/env python3
"""Plot latest demand predictions per SKU from the ```demand``` table."""

from __future__ import annotations

import argparse
import os
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Iterable, List, Optional, Tuple

import matplotlib.pyplot as plt
import pandas as pd
import psycopg2
from psycopg2.extras import RealDictCursor


def load_dotenv(dotenv_path: Path) -> None:
    """Load repo .env if python-dotenv is installed."""
    try:
        from dotenv import load_dotenv as _load_dotenv

        _load_dotenv(dotenv_path)
    except ImportError:  # pragma: no cover
        pass


def get_db_connection() -> psycopg2.extensions.connection:
    """Return a new connection using repository defaults and environment overrides."""
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
    return psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", "5432"),
        database=os.getenv("DB_NAME", "smartcart_ai"),
        user=os.getenv("DB_USER", "meghanarendrasimha"),
        password=os.getenv("DB_PASSWORD", "Welcome@123"),
        cursor_factory=RealDictCursor,
    )


def fetch_demand_predictions(
    model_version: Optional[str] = None,
    since: Optional[date] = None,
    limit: Optional[int] = None,
) -> List[Tuple[str, float, date]]:
    """Return (item_name, predicted_demand, prediction_date) for the latest record per inventory item."""
    filters = []
    params: List[Optional[str]] = []
    if model_version:
        filters.append("d.model_version = %s")
        params.append(model_version)
    if since:
        filters.append("d.prediction_date >= %s")
        params.append(since)

    where_clause = f"AND {' AND '.join(filters)}" if filters else ""
    limit_clause = "LIMIT %s" if limit else ""
    if limit:
        params.append(limit)

    query = f"""
        SELECT DISTINCT ON (d.inventory_id)
               i.item_name,
               d.predicted_demand,
               d.prediction_date
        FROM demand d
        JOIN inventory i ON i.inventory_id = d.inventory_id
        WHERE d.predicted_demand IS NOT NULL
        {where_clause}
        ORDER BY d.inventory_id, d.prediction_date DESC
        {limit_clause}
    """

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, tuple(params) if params else None)
            rows = cur.fetchall()

    return [
        (row["item_name"], float(row["predicted_demand"]), row["prediction_date"]) for row in rows
    ]


def plot_demand(
    items: Iterable[Tuple[str, float, date]],
    title: str,
    out_path: Path | None = None,
    show: bool = True,
) -> None:
    """Render a horizontal bar chart of predicted demand."""
    df = pd.DataFrame(items, columns=["item_name", "predicted_demand", "prediction_date"])
    if df.empty:
        print("No demand predictions found.", file=sys.stderr)
        return

    df = df.sort_values("predicted_demand", ascending=True)
    fig, ax = plt.subplots(figsize=(10, max(4, len(df) * 0.35)))
    bars = ax.barh(df["item_name"], df["predicted_demand"], color="#c84e4e")
    ax.set_xlabel("Predicted demand (units)")
    ax.set_title(title)
    ax.grid(axis="x", linestyle=":", alpha=0.6)
    ax.tick_params(axis="y", labelsize=9)

    latest_date = df["prediction_date"].max()
    annotation = f"Latest prediction date: {latest_date}" if pd.notna(latest_date) else ""
    if annotation:
        ax.text(0.99, 0.01, annotation, ha="right", va="bottom", transform=ax.transAxes, fontsize=8)

    max_demand = df["predicted_demand"].max()
    for bar in bars:
        width = bar.get_width()
        ax.text(
            width + max_demand * 0.01,
            bar.get_y() + bar.get_height() / 2,
            f"{width:.1f}",
            va="center",
            fontsize=8,
        )

    plt.tight_layout()

    if out_path:
        fig.savefig(out_path, dpi=150)
        print(f"Saved demand chart to {out_path}")
    if show and not out_path:
        plt.show()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Plot demand predictions per inventory item."
    )
    parser.add_argument(
        "--model-version",
        "-m",
        help="Only include predictions from this model version.",
    )
    parser.add_argument(
        "--since",
        type=lambda value: datetime.strptime(value, "%Y-%m-%d").date(),
        help="Only include predictions made on or after this date (YYYY-MM-DD).",
    )
    parser.add_argument(
        "--limit",
        "-n",
        type=int,
        help="Limit to the top-N entries after selecting latest per item.",
    )
    parser.add_argument(
        "--title",
        default="Predicted demand by item",
        help="Chart title.",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        help="Path to save the chart image (PNG). If omitted, the chart is displayed.",
    )
    parser.add_argument(
        "--no-show",
        action="store_true",
        help="Do not open an interactive window (useful when saving).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    try:
        items = fetch_demand_predictions(model_version=args.model_version, since=args.since, limit=args.limit)
    except Exception as exc:
        print(f"Failed to load demand predictions: {exc}", file=sys.stderr)
        sys.exit(1)

    plot_demand(
        items,
        title=args.title,
        out_path=args.output,
        show=not args.no_show,
    )


if __name__ == "__main__":
    main()
