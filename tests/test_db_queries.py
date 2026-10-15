import os

import pytest
from dotenv import load_dotenv

from db.connection import get_engine
from db.queries import get_active_shipments, get_latest_telemetry


load_dotenv()
pytestmark = pytest.mark.skipif(not os.getenv("DB_CONN"), reason="DB_CONN is not configured")


def test_get_active_shipments_returns_seeded_shipments() -> None:
    shipments = get_active_shipments()

    assert len(shipments) == 30
    assert {shipment["vehicle_id"] for shipment in shipments} >= {7, 101, 284, 452}
    assert all(shipment["status"] == "in_transit" for shipment in shipments)


def test_get_latest_telemetry_returns_newest_reading() -> None:
    reading = get_latest_telemetry(284)

    assert reading is not None
    assert reading["vehicle_id"] == 284
    assert reading["ts"] is not None
    assert reading["compressor_load_pct"] > 0


def test_get_latest_telemetry_returns_none_for_unknown_vehicle() -> None:
    assert get_latest_telemetry(999999) is None


def teardown_module() -> None:
    get_engine.cache_clear()
