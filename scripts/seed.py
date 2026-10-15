"""Rebuild the synthetic CoolRoute data in PostgreSQL."""

from __future__ import annotations

import os

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.dialects.postgresql import JSONB

try:
    from scripts.generate_data import generate_data
except ModuleNotFoundError:
    from generate_data import generate_data


def main() -> None:
    load_dotenv()
    engine = create_engine(os.environ["DB_CONN"])
    frames = generate_data()
    with engine.begin() as connection:
        connection.execute(text("TRUNCATE telemetry_readings, routes, shipments, vehicles, cargo_profiles RESTART IDENTITY CASCADE"))
        frames["cargo_profiles"].to_sql("cargo_profiles", connection, if_exists="append", index=False, method="multi")
        frames["vehicles"].to_sql("vehicles", connection, if_exists="append", index=False, method="multi")
        frames["shipments"].to_sql("shipments", connection, if_exists="append", index=False, method="multi", dtype={"planned_route_json": JSONB})
        frames["routes"].to_sql("routes", connection, if_exists="append", index=False, method="multi")
        frames["telemetry_readings"].to_sql("telemetry_readings", connection, if_exists="append", index=False, method="multi", chunksize=5000)
    print(f"Seeded 25 vehicles, 40 shipments, 120 routes, and {len(frames['telemetry_readings']):,} telemetry readings.")


if __name__ == "__main__":
    main()