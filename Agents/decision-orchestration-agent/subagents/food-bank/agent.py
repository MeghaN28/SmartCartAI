"""Food Bank Subagent – Finds nearest food banks for donation suggestions (discard / near-expiry)."""
import os
import logging
import math
from typing import List, Dict, Optional
from pathlib import Path

import psycopg2
from psycopg2.extras import RealDictCursor
from flask import Flask, request, jsonify
from fastmcp import FastMCP

try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)
    parent_env = Path(__file__).parent.parent.parent / ".env"
    if parent_env.exists():
        load_dotenv(parent_env)
except ImportError:
    pass

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("food-bank")

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "smartcart_ai")
DB_USER = os.getenv("DB_USER", "meghanarendrasimha")
DB_PASSWORD = os.getenv("DB_PASSWORD", "Welcome@123")

DEFAULT_LIMIT = 5

mcp = FastMCP("Food Bank Subagent")
app = Flask(__name__)


def get_db_connection():
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        cursor_factory=RealDictCursor,
    )


def haversine_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distance in miles between two (lat, lon) points."""
    R = 3958.8  # Earth radius in miles
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def get_facility_location() -> Optional[tuple]:
    """Return (lat, lon) for the default facility, or None if not set."""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            "SELECT lat, lon FROM facility ORDER BY facility_id ASC LIMIT 1"
        )
        row = cur.fetchone()
        cur.close()
        conn.close()
        if row and row.get("lat") is not None and row.get("lon") is not None:
            return (float(row["lat"]), float(row["lon"]))
    except Exception as e:
        logger.warning(f"Could not load facility location: {e}")
    return None


def get_nearest_food_banks(
    lat: Optional[float] = None,
    lon: Optional[float] = None,
    limit: int = DEFAULT_LIMIT,
) -> List[Dict]:
    """
    Return nearest food banks to (lat, lon). If lat/lon omitted, use facility location.
    Each item: name, address, city, state, zip, lat, lon, phone, url, distance_mi.
    """
    if lat is None or lon is None:
        loc = get_facility_location()
        if not loc:
            logger.warning("No facility location; cannot compute nearest food banks")
            return []
        lat, lon = loc

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT food_bank_id, name, address, city, state, zip, lat, lon, phone, url
            FROM food_banks
            """
        )
        rows = cur.fetchall()
        cur.close()
        conn.close()
    except Exception as e:
        logger.error(f"Error fetching food banks: {e}")
        return []

    out = []
    for r in rows:
        try:
            la, lo = float(r["lat"]), float(r["lon"])
        except (TypeError, ValueError):
            continue
        dist = haversine_miles(lat, lon, la, lo)
        out.append({
            "food_bank_id": r["food_bank_id"],
            "name": r.get("name") or "",
            "address": r.get("address") or "",
            "city": r.get("city") or "",
            "state": r.get("state") or "",
            "zip": r.get("zip") or "",
            "lat": la,
            "lon": lo,
            "phone": r.get("phone") or "",
            "url": r.get("url") or "",
            "distance_mi": round(dist, 2),
        })
    out.sort(key=lambda x: x["distance_mi"])
    return out[: limit]


@app.route("/nearest", methods=["GET", "POST"])
def nearest_endpoint():
    """
    GET: ?lat=&lon=&limit=5
    POST: { "lat": 40.7, "lon": -74.0, "limit": 5 } (lat/lon optional; use facility if omitted)
    """
    if request.method == "GET":
        try:
            lat = request.args.get("lat", type=float)
            lon = request.args.get("lon", type=float)
        except (TypeError, ValueError):
            lat, lon = None, None
        limit = request.args.get("limit", default=DEFAULT_LIMIT, type=int) or DEFAULT_LIMIT
    else:
        payload = request.get_json(silent=True) or {}
        lat = payload.get("lat")
        lon = payload.get("lon")
        limit = payload.get("limit", DEFAULT_LIMIT) or DEFAULT_LIMIT

    limit = min(max(1, limit), 20)
    result = get_nearest_food_banks(lat=lat, lon=lon, limit=limit)
    return jsonify({"nearest_food_banks": result}), 200


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "agent": "food-bank"}), 200


@mcp.tool()
def get_nearest_food_banks_tool(lat: Optional[float] = None, lon: Optional[float] = None, limit: int = 5) -> dict:
    """Get nearest food banks to the facility (or to lat/lon if provided)."""
    return {"nearest_food_banks": get_nearest_food_banks(lat=lat, lon=lon, limit=limit)}


if __name__ == "__main__":
    # Mode switch:
    # - Default: Flask REST server (existing app integrations)
    # - MCP HTTP: expose MCP tools at http://host:port/mcp (for MCP-first usage)
    mode = os.getenv("SMARTCART_AGENT_MODE", "flask").strip().lower()
    if mode in ("mcp", "mcp_http", "mcp-http", "http_mcp"):
        mcp_port = int(os.getenv("MCP_PORT", "9107"))
        host = os.getenv("MCP_HOST", "0.0.0.0")
        logger.info("Starting Food Bank MCP server on %s:%s", host, mcp_port)
        mcp.run(transport="http", host=host, port=mcp_port)
    else:
        port = int(os.getenv("PORT", "9007"))
        app.run(host="0.0.0.0", port=port, debug=True)
