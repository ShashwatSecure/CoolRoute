"""Module 2.3 tests: the SQL guard accepts one read-only SELECT and rejects everything else."""

import pytest

from agent.tools.sql_guard import ROW_CAP, UnsafeSQLError, cap_rows, guard_select

ALLOWED = [
    "SELECT 1",
    "SELECT vehicle_id, status FROM vehicles WHERE status = 'active'",
    "WITH x AS (SELECT vehicle_id FROM vehicles) SELECT count(*) FROM x;",
    "SELECT public.vehicles.vehicle_id FROM public.vehicles -- trailing comment",
]

REJECTED = [
    ("DROP TABLE vehicles", "not a query"),
    ("SELECT 1; DELETE FROM vehicles", "exactly one statement"),
    ("SELECT * INTO z FROM vehicles", "Into"),
    ("COPY vehicles TO stdout", "Copy"),
    ("SELECT pg_read_file('x')", "pg_"),
    ("SELECT * FROM audit_events", "not in the allow-list"),
    ("WITH d AS (DELETE FROM vehicles RETURNING *) SELECT * FROM d", "Delete"),
    ("SELECT dblink('x')", "dblink"),
    ("SELECT * FROM pg_tables", "pg_"),
    ("VACUUM", "not a query"),
    ("UPDATE vehicles SET status = 1", "not a query"),
    ("", "empty"),
]


@pytest.mark.parametrize("sql", ALLOWED)
def test_allows_read_only_select(sql):
    assert guard_select(sql)


@pytest.mark.parametrize(("sql", "_reason"), REJECTED)
def test_rejects_unsafe_sql(sql, _reason):
    with pytest.raises(UnsafeSQLError):
        guard_select(sql)


def test_strips_trailing_semicolon():
    assert not guard_select("SELECT 1;").endswith(";")


def test_cap_rows_wraps_query_with_limit():
    capped = cap_rows("SELECT vehicle_id FROM vehicles")
    assert capped.startswith("SELECT * FROM (")
    assert capped.rstrip().endswith(f"LIMIT {ROW_CAP}")
