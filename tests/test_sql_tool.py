"""Module 2.3 tests: the SQL tools against the seeded PostgreSQL database.

These tests need the Docker database running and seeded (see README / scripts/seed.py).
"""

import json

from agent.tools.sql_tool import (
    get_temp_history,
    get_vehicles_in_region,
    run_sql,
)


def test_run_sql_returns_rows_for_a_safe_select():
    result = json.loads(run_sql.invoke({"query": "SELECT count(*) AS n FROM vehicles"}))
    assert result["columns"] == ["n"]
    assert result["row_count"] == 1
    assert result["rows"][0][0] > 0


def test_run_sql_handles_like_patterns_with_percent_signs():
    result = json.loads(run_sql.invoke({"query": "SELECT count(*) FROM vehicles WHERE home_depot LIKE 'Phoen%'"}))
    assert "error" not in result


def test_run_sql_rejects_writes_with_error_json():
    result = json.loads(run_sql.invoke({"query": "DELETE FROM vehicles"}))
    assert result["error"].startswith("query rejected")


def test_run_sql_reports_database_errors_as_json():
    result = json.loads(run_sql.invoke({"query": "SELECT 1/0"}))
    assert result["error"] == "database error: division by zero"


def test_texas_vehicles_are_inside_the_bounding_box():
    result = json.loads(get_vehicles_in_region.invoke({"region": "texas"}))
    assert "error" not in result
    for row in result["trucks"]:
        assert 25.8 <= row["lat"] <= 36.5
        assert -106.7 <= row["lon"] <= -93.5


def test_unknown_region_lists_supported_regions():
    result = json.loads(get_vehicles_in_region.invoke({"region": "atlantis"}))
    assert "error" in result
    assert "texas" in result["supported"]


def test_temp_history_for_truck_284_has_readings():
    result = json.loads(get_temp_history.invoke({"vehicle_id": 284, "hours": 6}))
    assert "error" not in result
    assert result["readings"] > 0
    assert result["min_c"] <= result["avg_c"] <= result["max_c"]
