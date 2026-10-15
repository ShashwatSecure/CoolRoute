"""Tools the agent can call to read the operational database.

The docstring of each ``@tool`` function is sent to the model as its description,
so it doubles as the prompt for tool selection (Module 2.2).
"""

from __future__ import annotations

import json
from decimal import Decimal
from typing import Any

import psycopg
from langchain_core.tools import tool
from sqlalchemy.exc import SQLAlchemyError

from agent.tools.sql_guard import ROW_CAP, UnsafeSQLError, cap_rows, guard_select
from db import queries
from db.connection import get_engine

# lat_min, lat_max, lon_min, lon_max. Approximate bounding box for Texas.
REGION_BOUNDS: dict[str, tuple[float, float, float, float]] = {
    "texas": (25.8, 36.5, -106.7, -93.5),
}
RESULT_ROW_LIMIT = 50  # rows returned to the model; the SQL cap is ROW_CAP
STATEMENT_TIMEOUT_MS = 3000


def _json_default(value: Any) -> Any:
    """Serialize the database types the model should see: numbers as numbers, the rest as text."""
    if isinstance(value, Decimal):
        return float(value)
    return str(value)


def _to_json(payload: Any) -> str:
    return json.dumps(payload, default=_json_default)


def _num(value: Any) -> float | None:
    """Convert Decimal or None from the database to a plain float for JSON output."""
    return None if value is None else round(float(value), 2)


@tool
def get_vehicle_status(vehicle_id: int) -> str:
    """Return one reefer truck's details, its newest sensor reading, and its in-transit shipments.

    Use this when the user asks about a specific truck by number, for example
    "Where is truck 284?" or "Is truck 7 healthy?".
    """
    vehicle = queries.get_vehicle(vehicle_id)
    if vehicle is None:
        return _to_json({"error": f"no vehicle with id {vehicle_id}"})
    shipments = queries.get_active_shipments_for_vehicle(vehicle_id)
    return _to_json({"vehicle": vehicle, "active_shipments": shipments})


@tool
def get_vehicles_in_region(region: str) -> str:
    """List active trucks whose latest GPS position is inside a named region.

    Supported region: "texas". Each row is one in-transit shipment with the truck's
    position, the cargo temperature, and whether that temperature is inside the cargo range.
    Use this for questions such as "Which refrigerated vehicles are in Texas?".
    """
    key = region.strip().lower()
    if key not in REGION_BOUNDS:
        return _to_json({"error": f"unsupported region '{region}'", "supported": sorted(REGION_BOUNDS)})
    lat_min, lat_max, lon_min, lon_max = REGION_BOUNDS[key]

    rows = []
    for reading in queries.get_latest_active_telemetry():
        lat, lon = float(reading["lat"]), float(reading["lon"])
        if not (lat_min <= lat <= lat_max and lon_min <= lon <= lon_max):
            continue
        temp = float(reading["cargo_temp_c"])
        low, high = float(reading["min_temp_c"]), float(reading["max_temp_c"])
        rows.append(
            {
                "vehicle_id": reading["vehicle_id"],
                "lat": round(lat, 3),
                "lon": round(lon, 3),
                "shipment_id": reading["shipment_id"],
                "cargo_type": reading["cargo_type"],
                "cargo_temp_c": _num(temp),
                "cargo_range_c": [_num(low), _num(high)],
                "temp_in_range": low <= temp <= high,
                "door_open": bool(reading["door_open"]),
            }
        )
    return _to_json({"region": key, "count": len(rows), "trucks": rows})


@tool
def get_shipments_by_status(status: str) -> str:
    """List shipments with a given status: "in_transit" or "planned".

    Use this for questions about all shipments in a state, for example
    "How many shipments are planned?". Returns at most 50 shipments.
    """
    rows = queries.get_shipments_by_status(status.strip().lower())
    return _to_json(
        {
            "status": status,
            "count": len(rows),
            "shipments": rows[:RESULT_ROW_LIMIT],
        }
    )


@tool
def get_temp_history(vehicle_id: int, hours: int = 6) -> str:
    """Summarize one truck's cargo temperature over the last N hours of its data.

    Returns min, max, average, the latest value, and how many readings fall outside
    each in-transit shipment's cargo range. Use this for "Show truck 284's temperature
    for the last 6 hours" or "Did truck 101 have any excursions?".
    """
    if hours < 1 or hours > 168:
        return _to_json({"error": "hours must be between 1 and 168"})
    rows = queries.get_temperature_window(vehicle_id, hours)
    if not rows:
        return _to_json({"error": f"no readings for vehicle {vehicle_id} in that window"})

    temps = [float(r["cargo_temp_c"]) for r in rows]
    shipments = queries.get_active_shipments_for_vehicle(vehicle_id)
    against = []
    for shipment in shipments:
        low, high = float(shipment["min_temp_c"]), float(shipment["max_temp_c"])
        against.append(
            {
                "shipment_id": shipment["shipment_id"],
                "cargo_type": shipment["cargo_type"],
                "cargo_range_c": [_num(low), _num(high)],
                "readings_out_of_range": sum(1 for t in temps if not low <= t <= high),
            }
        )
    return _to_json(
        {
            "vehicle_id": vehicle_id,
            "window_hours": hours,
            "readings": len(temps),
            "first_ts": rows[0]["ts"],
            "last_ts": rows[-1]["ts"],
            "min_c": _num(min(temps)),
            "max_c": _num(max(temps)),
            "avg_c": _num(sum(temps) / len(temps)),
            "latest_c": _num(temps[-1]),
            "door_open_readings": sum(1 for r in rows if r["door_open"]),
            "against_shipments": against,
        }
    )


@tool
def run_sql(query: str) -> str:
    """Run one read-only PostgreSQL SELECT for questions the other tools cannot answer.

    Allowed tables: vehicles, shipments, telemetry_readings, routes, maintenance_log,
    cargo_profiles. Use the column names from the system prompt. Results are capped
    at 200 rows, and 50 are shown. Prefer aggregates such as COUNT, AVG, or GROUP BY.
    Returns JSON with columns and rows, or an error that you can fix and retry.
    """
    try:
        checked = guard_select(query)
    except UnsafeSQLError as exc:
        return _to_json({"error": f"query rejected: {exc}"})

    try:
        with get_engine().connect() as connection:
            # Go through the raw psycopg cursor with no parameters. SQLAlchemy would
            # treat % in LIKE patterns as placeholders.
            with connection.connection.driver_connection.cursor() as cursor:
                # Read-only transaction, role without write rights, and a timeout.
                # The timeout is our constant, not model input.
                cursor.execute("SET TRANSACTION READ ONLY")
                cursor.execute(f"SET LOCAL statement_timeout = '{STATEMENT_TIMEOUT_MS}ms'")
                cursor.execute("SET LOCAL ROLE agent_ro")
                cursor.execute(cap_rows(checked, ROW_CAP))
                columns = [column.name for column in cursor.description or []]
                rows = [list(row) for row in cursor.fetchall()]
    except (SQLAlchemyError, psycopg.Error) as exc:
        first_line = str(getattr(exc, "orig", exc) or exc).splitlines()[0]
        return _to_json({"error": f"database error: {first_line}"})

    payload: dict[str, Any] = {
        "columns": columns,
        "row_count": len(rows),
        "rows": rows[:RESULT_ROW_LIMIT],
    }
    if len(rows) > RESULT_ROW_LIMIT:
        payload["note"] = f"showing {RESULT_ROW_LIMIT} of {len(rows)} rows; use an aggregate or narrower filter"
    return _to_json(payload)


SQL_TOOLS = [get_vehicle_status, get_vehicles_in_region, get_shipments_by_status, get_temp_history, run_sql]

