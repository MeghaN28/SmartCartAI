#!/usr/bin/env python3
"""Generate a simple bar chart of inventory items and their on-hand stock."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Iterable, List, Tuple

import matplotlib.pyplot as plt
import pandas as pd
import psycopg2
from psycopg2.extras import RealDictCursor


def load_dotenv(dotenv_path: Path) -> None:
    """Load environment variables if python-dotenv is available."""
    try:
        from dotenv import load_dotenv as _load_dotenv

        _load_dotenv(dotenv_path)
    except ImportError:  # pragma: no cover
        # If python-dotenv is not installed, assume env already loaded.
        pass


def get_db_connection() -> psycopg2.extensions.connection:
    """Return a new connection using env vars with repository defaults."""
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
    return psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", "5432"),
        database=os.getenv("DB_NAME", "smartcart_ai"),
        user=os.getenv("DB_USER", "meghanarendrasimha"),
        password=os.getenv("DB_PASSWORD", "Welcome@123"),
        cursor_factory=RealDictCursor,
    )


def fetch_inventory_items(limit: int | None = None) -> List[Tuple[str, float]]:
    """Return (item_name, remaining_stock) tuples ordered by stock descending."""
    query = """
        SELECT item_name,
               COALESCE(opening_stock, 0) AS remaining_stock
        FROM inventory
        ORDER BY remaining_stock DESC, item_name ASC
    """
    if limit:
        query += "\nLIMIT %s"
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (limit,) if limit else None)
            rows = cur.fetchall()
    return [(row["item_name"], float(row["remaining_stock"] or 0)) for row in rows]


def plot_stock(
    items: Iterable[Tuple[str, float]],
    title: str,
    out_path: Path | None = None,
    show: bool = True,
) -> None:
    """Render the horizontal bar chart and either show it or save to disk."""
    df = pd.DataFrame(items, columns=["item_name", "remaining_stock"])
    if df.empty:
        print("No inventory data returned.", file=sys.stderr)
        return

    df = df.sort_values("remaining_stock", ascending=True)
    fig, ax = plt.subplots(figsize=(10, max(4, len(df) * 0.35)))
    bars = ax.barh(df["item_name"], df["remaining_stock"], color="#4c78a8")
    ax.set_xlabel("Remaining stock (units)")
    ax.set_title(title)
    ax.grid(axis="x", linestyle=":", alpha=0.6)
    ax.tick_params(axis="y", labelsize=9)
    for bar in bars:
        width = bar.get_width()
        ax.text(
            width + max(df["remaining_stock"]) * 0.01,
            bar.get_y() + bar.get_height() / 2,
            f"{width:.0f}",
            va="center",
            fontsize=8,
        )

    plt.tight_layout()

    if out_path:
        fig.savefig(out_path, dpi=150)
        print(f"Saved inventory stock chart to {out_path}")
    if show and not out_path:
        plt.show()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Plot inventory items sorted by current stock."
    )
    parser.add_argument(
        "--limit",
        "-n",
        type=int,
        help="Limit to the top-N most stocked items (default all).",
    )
    parser.add_argument(
        "--title",
        default="Inventory stock levels",
        help="Chart title.",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        help="Path to save the chart as an image (PNG). If omitted, the chart is displayed.",
    )
    parser.add_argument(
        "--no-show",
        action="store_true",
        help="Do not open the interactive window (useful when saving).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    try:
        items = fetch_inventory_items(limit=args.limit)
    except Exception as exc:
        print(f"Failed to load inventory data: {exc}", file=sys.stderr)
        sys.exit(1)

    plot_stock(
        items,
        title=args.title,
        out_path=args.output,
        show=not args.no_show,
    )


if __name__ == "__main__":
    main()
