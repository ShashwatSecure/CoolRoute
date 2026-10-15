"""Create the operational telemetry schema.

Revision ID: 0002_create_operational_schema
Revises: 0001_enable_pgvector
Create Date: 2026-10-15
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0002_create_operational_schema"
down_revision: Union[str, Sequence[str], None] = "0001_enable_pgvector"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "vehicles",
        sa.Column("vehicle_id", sa.Integer(), primary_key=True),
        sa.Column("plate", sa.String(32), nullable=False, unique=True),
        sa.Column("type", sa.String(64), nullable=False),
        sa.Column("reefer_unit_model", sa.String(128)),
        sa.Column("capacity_kg", sa.Numeric(12, 2), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("home_depot", sa.String(128), nullable=False),
        sa.CheckConstraint("capacity_kg > 0", name="ck_vehicles_capacity_positive"),
    )

    op.create_table(
        "shipments",
        sa.Column("shipment_id", sa.Integer(), primary_key=True),
        sa.Column(
            "vehicle_id",
            sa.Integer(),
            sa.ForeignKey("vehicles.vehicle_id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("cargo_type", sa.String(64), nullable=False),
        sa.Column("cargo_value_usd", sa.Numeric(14, 2), nullable=False),
        sa.Column("origin", sa.String(128), nullable=False),
        sa.Column("destination", sa.String(128), nullable=False),
        sa.Column("planned_route_json", postgresql.JSONB, nullable=False),
        sa.Column("depart_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("eta", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("min_temp_c", sa.Numeric(5, 2), nullable=False),
        sa.Column("max_temp_c", sa.Numeric(5, 2), nullable=False),
        sa.Column("max_transit_hours", sa.Numeric(8, 2), nullable=False),
        sa.CheckConstraint("cargo_value_usd >= 0", name="ck_shipments_value_nonnegative"),
        sa.CheckConstraint("min_temp_c <= max_temp_c", name="ck_shipments_temperature_range"),
        sa.CheckConstraint("max_transit_hours > 0", name="ck_shipments_transit_positive"),
        sa.CheckConstraint("eta >= depart_time", name="ck_shipments_eta_after_departure"),
    )

    op.create_table(
        "telemetry_readings",
        sa.Column("reading_id", sa.BigInteger(), primary_key=True),
        sa.Column(
            "vehicle_id",
            sa.Integer(),
            sa.ForeignKey("vehicles.vehicle_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("lat", sa.Numeric(9, 6), nullable=False),
        sa.Column("lon", sa.Numeric(9, 6), nullable=False),
        sa.Column("cargo_temp_c", sa.Numeric(5, 2), nullable=False),
        sa.Column("ambient_temp_c", sa.Numeric(5, 2), nullable=False),
        sa.Column("setpoint_c", sa.Numeric(5, 2), nullable=False),
        sa.Column("compressor_load_pct", sa.Numeric(5, 2), nullable=False),
        sa.Column("door_open", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("fuel_pct", sa.Numeric(5, 2), nullable=False),
        sa.Column("speed_kph", sa.Numeric(6, 2), nullable=False),
        sa.CheckConstraint("lat >= -90 AND lat <= 90", name="ck_telemetry_latitude"),
        sa.CheckConstraint("lon >= -180 AND lon <= 180", name="ck_telemetry_longitude"),
        sa.CheckConstraint(
            "compressor_load_pct >= 0 AND compressor_load_pct <= 100",
            name="ck_telemetry_compressor_load",
        ),
        sa.CheckConstraint(
            "fuel_pct >= 0 AND fuel_pct <= 100",
            name="ck_telemetry_fuel",
        ),
        sa.CheckConstraint("speed_kph >= 0", name="ck_telemetry_speed_nonnegative"),
    )
    op.create_index(
        "ix_telemetry_readings_vehicle_id_ts",
        "telemetry_readings",
        ["vehicle_id", "ts"],
    )

    op.create_table(
        "routes",
        sa.Column("route_id", sa.Integer(), primary_key=True),
        sa.Column(
            "shipment_id",
            sa.Integer(),
            sa.ForeignKey("shipments.shipment_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("waypoint_name", sa.String(128), nullable=False),
        sa.Column("lat", sa.Numeric(9, 6), nullable=False),
        sa.Column("lon", sa.Numeric(9, 6), nullable=False),
        sa.Column("planned_arrival", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("seq >= 0", name="ck_routes_sequence_nonnegative"),
        sa.CheckConstraint("lat >= -90 AND lat <= 90", name="ck_routes_latitude"),
        sa.CheckConstraint("lon >= -180 AND lon <= 180", name="ck_routes_longitude"),
        sa.UniqueConstraint("shipment_id", "seq", name="uq_routes_shipment_sequence"),
    )

    op.create_table(
        "maintenance_log",
        sa.Column("maintenance_id", sa.BigInteger(), primary_key=True),
        sa.Column(
            "vehicle_id",
            sa.Integer(),
            sa.ForeignKey("vehicles.vehicle_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("maintenance_date", sa.Date(), nullable=False),
        sa.Column("issue", sa.Text(), nullable=False),
        sa.Column("compressor_hours", sa.Numeric(10, 2), nullable=False),
        sa.CheckConstraint("compressor_hours >= 0", name="ck_maintenance_compressor_hours"),
    )

    op.create_table(
        "cargo_profiles",
        sa.Column("cargo_type", sa.String(64), primary_key=True),
        sa.Column("min_temp_c", sa.Numeric(5, 2), nullable=False),
        sa.Column("max_temp_c", sa.Numeric(5, 2), nullable=False),
        sa.Column("max_excursion_minutes", sa.Integer(), nullable=False),
        sa.Column("max_transit_hours", sa.Numeric(8, 2), nullable=False),
        sa.CheckConstraint("min_temp_c <= max_temp_c", name="ck_cargo_profiles_temperature_range"),
        sa.CheckConstraint(
            "max_excursion_minutes >= 0",
            name="ck_cargo_profiles_excursion_nonnegative",
        ),
        sa.CheckConstraint("max_transit_hours > 0", name="ck_cargo_profiles_transit_positive"),
    )


def downgrade() -> None:
    op.drop_table("cargo_profiles")
    op.drop_table("maintenance_log")
    op.drop_table("routes")
    op.drop_index("ix_telemetry_readings_vehicle_id_ts", table_name="telemetry_readings")
    op.drop_table("telemetry_readings")
    op.drop_table("shipments")
    op.drop_table("vehicles")
