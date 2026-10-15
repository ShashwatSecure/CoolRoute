"""Small read-only query helpers for the operational database."""

from __future__ import annotations

from typing import Any

from sqlalchemy import text

from db.connection import get_engine


def get_active_shipments() -> list[dict[str, Any]]:
    """Return shipments currently in transit, ordered by ETA."""
    statement = text(
        """
        SELECT shipment_id, vehicle_id, cargo_type, origin, destination,
               depart_time, eta, min_temp_c, max_temp_c, status
        FROM shipments
        WHERE status = 'in_transit'
        ORDER BY eta, shipment_id
        """
    )
    with get_engine().connect() as connection:
        return [dict(row) for row in connection.execute(statement).mappings()]


def get_latest_telemetry(vehicle_id: int) -> dict[str, Any] | None:
    """Return the newest telemetry reading for a vehicle, if one exists."""
    statement = text(
        """
        SELECT reading_id, vehicle_id, ts, lat, lon, cargo_temp_c,
               ambient_temp_c, setpoint_c, compressor_load_pct,
               door_open, fuel_pct, speed_kph
        FROM telemetry_readings
        WHERE vehicle_id = :vehicle_id
        ORDER BY ts DESC, reading_id DESC
        LIMIT 1
        """
    )
    with get_engine().connect() as connection:
        row = connection.execute(statement, {"vehicle_id": vehicle_id}).mappings().first()
        return dict(row) if row else None


def get_latest_active_telemetry() -> list[dict[str, Any]]:
    """Return the latest reading for each vehicle with an active shipment."""
    statement = text(
        """
        WITH ranked_readings AS (
            SELECT t.*, ROW_NUMBER() OVER (
                PARTITION BY t.vehicle_id ORDER BY t.ts DESC, t.reading_id DESC
            ) AS row_number
            FROM telemetry_readings AS t
        )
        SELECT r.reading_id, r.vehicle_id, r.ts, r.lat, r.lon,
               r.cargo_temp_c, r.ambient_temp_c, r.setpoint_c,
               r.compressor_load_pct, r.door_open, r.fuel_pct, r.speed_kph,
               s.shipment_id, s.cargo_type, s.min_temp_c, s.max_temp_c,
               s.origin, s.destination
        FROM ranked_readings AS r
        JOIN shipments AS s ON s.vehicle_id = r.vehicle_id
        WHERE r.row_number = 1 AND s.status = 'in_transit'
        ORDER BY r.vehicle_id
        """
    )
    with get_engine().connect() as connection:
        return [dict(row) for row in connection.execute(statement).mappings()]


def get_temperature_history(vehicle_id: int, hours: int = 24) -> list[dict[str, Any]]:
    """Return temperature readings and shipment bounds for a vehicle."""
    statement = text(
        """
        SELECT t.ts, t.cargo_temp_c, t.ambient_temp_c, t.setpoint_c,
               s.min_temp_c, s.max_temp_c
        FROM telemetry_readings AS t
        JOIN shipments AS s ON s.vehicle_id = t.vehicle_id
        WHERE t.vehicle_id = :vehicle_id
          AND t.ts >= NOW() - (:hours * INTERVAL '1 hour')
        ORDER BY t.ts
        """
    )
    with get_engine().connect() as connection:
        return [
            dict(row)
            for row in connection.execute(statement, {"vehicle_id": vehicle_id, "hours": hours}).mappings()
        ]
