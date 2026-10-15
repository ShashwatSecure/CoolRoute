"""Create the read-only role used by the agent SQL tool.

Revision ID: 0003_create_agent_readonly_role
Revises: 0002_create_operational_schema
Create Date: 2026-10-15
"""
from typing import Sequence, Union

from alembic import op


revision: str = "0003_create_agent_readonly_role"
down_revision: Union[str, Sequence[str], None] = "0002_create_operational_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

AGENT_READABLE_TABLES = (
    "vehicles",
    "shipments",
    "telemetry_readings",
    "routes",
    "maintenance_log",
    "cargo_profiles",
)


def upgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'agent_ro') THEN
                CREATE ROLE agent_ro NOLOGIN;
            END IF;
        END
        $$;
        """
    )
    op.execute("GRANT USAGE ON SCHEMA public TO agent_ro")
    for table in AGENT_READABLE_TABLES:
        op.execute(f"GRANT SELECT ON {table} TO agent_ro")


def downgrade() -> None:
    for table in AGENT_READABLE_TABLES:
        op.execute(f"REVOKE SELECT ON {table} FROM agent_ro")
    op.execute("REVOKE USAGE ON SCHEMA public FROM agent_ro")
    op.execute("DROP ROLE IF EXISTS agent_ro")
