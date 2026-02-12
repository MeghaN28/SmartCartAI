"""
Update embeddings on inventory table.
Combines item_name, item_type, form, usage, category into a single text and stores its embedding.
Requires: pip install psycopg2-binary sentence-transformers python-dotenv
"""

import os
import sys
from pathlib import Path

# Optional: load .env from project root or Agents/inventory-agent
for d in [Path(__file__).resolve().parent.parent, Path(__file__).resolve().parent]:
    env_file = d / ".env"
    if env_file.exists():
        try:
            from dotenv import load_dotenv
            load_dotenv(env_file)
            break
        except ImportError:
            pass

import psycopg2
from psycopg2.extras import RealDictCursor

# DB config (same as inventory-agent)
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "smartcart_ai")
DB_USER = os.getenv("DB_USER", "meghanarendrasimha")
DB_PASSWORD = os.getenv("DB_PASSWORD", "Welcome@123")


def get_connection():
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        cursor_factory=RealDictCursor,
    )


def ensure_embedding_column(conn):
    """Add embedding column if it doesn't exist (real array for float vector)."""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'inventory' AND column_name = 'embedding';
        """)
        if cur.fetchone():
            return
        cur.execute("""
            ALTER TABLE inventory
            ADD COLUMN IF NOT EXISTS embedding real[];
        """)
        conn.commit()


def combined_text(row):
    """Combine item_name, item_type, form, usage, category for embedding."""
    parts = [
        str(row.get("item_name") or "").strip(),
        str(row.get("item_type") or "").strip(),
        str(row.get("form") or "").strip(),
        str(row.get("usage") or "").strip(),
        str(row.get("category") or "").strip(),
    ]
    return " ".join(p for p in parts if p).strip() or "unknown"


def get_embedding_model():
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer("all-MiniLM-L6-v2")  # 384-dim, fast


def update_embeddings(conn, model, batch_size=32):
    with conn.cursor() as cur:
        cur.execute("""
            SELECT inventory_id, item_name, item_type, form, usage, category
            FROM inventory;
        """)
        rows = cur.fetchall()

    if not rows:
        print("No inventory rows found.")
        return 0

    updated = 0
    for i in range(0, len(rows), batch_size):
        batch = rows[i : i + batch_size]
        texts = [combined_text(r) for r in batch]
        embeddings = model.encode(texts, show_progress_bar=False)
        if embeddings.ndim == 1:
            embeddings = embeddings.reshape(1, -1)

        with conn.cursor() as cur:
            for r, vec in zip(batch, embeddings):
                cur.execute(
                    "UPDATE inventory SET embedding = %s WHERE inventory_id = %s;",
                    (vec.tolist(), r["inventory_id"]),
                )
                updated += 1
        conn.commit()
        print(f"Updated {min(i + batch_size, len(rows))}/{len(rows)} rows.")

    return updated


def main():
    print("Loading embedding model...")
    model = get_embedding_model()
    print("Connecting to database...")
    conn = get_connection()
    try:
        ensure_embedding_column(conn)
        print("Updating inventory embeddings (item_name + item_type + form + usage + category)...")
        n = update_embeddings(conn, model)
        print(f"Done. Updated {n} rows.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
