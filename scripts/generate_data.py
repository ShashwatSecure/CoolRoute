"""Generate deterministic synthetic CoolRoute operational data."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd
from faker import Faker

SEED = 284452101
TELEMETRY_HOURS = 168
CITIES = {
    "Phoenix": (33.4484, -112.0740), "Dallas": (32.7767, -96.7970),
    "Houston": (29.7604, -95.3698), "Denver": (39.7392, -104.9903),
    "Los Angeles": (34.0522, -118.2437), "Atlanta": (33.7490, -84.3880),
    "Miami": (25.7617, -80.1918), "Seattle": (47.6062, -122.3321),
    "Chicago": (41.8781, -87.6298), "New York": (40.7128, -74.0060),
    "San Antonio": (29.4241, -98.4936), "Las Vegas": (36.1699, -115.1398),
    "Nashville": (36.1627, -86.7816), "Charlotte": (35.2271, -80.8431),
    "Boston": (42.3601, -71.0589),
}
CARGO_PROFILES = {
    "Vaccines": (2.0, 8.0, 20, 72), "Seafood": (0.0, 2.0, 30, 48),
    "Frozen": (-25.0, -18.0, 45, 72), "Dairy": (1.0, 4.0, 60, 48),
    "Produce": (4.0, 10.0, 90, 36), "Chemicals": (15.0, 25.0, 120, 96),
}


def _vehicle_ids() -> list[int]:
    return [7, 101, 284, 452] + list(range(1000, 1021))


def generate_data(now: datetime | None = None) -> dict[str, pd.DataFrame]:
    """Return all seed tables as data frames using stable random values."""
    faker = Faker()
    faker.seed_instance(SEED)
    rng = np.random.default_rng(SEED)
    now = now or datetime.now(timezone.utc).replace(second=0, microsecond=0)
    vehicle_ids = _vehicle_ids()
    vehicles = []
    for vehicle_id in vehicle_ids:
        vehicles.append({
            "vehicle_id": vehicle_id, "plate": f"CR-{vehicle_id:04d}",
            "type": "Reefer truck", "reefer_unit_model": f"ThermoKing-{rng.choice(['A500', 'B700', 'C900'])}",
            "capacity_kg": int(rng.integers(8000, 24001)), "status": "active",
            "home_depot": faker.random_element(list(CITIES)),
        })

    cargo_types = list(CARGO_PROFILES)
    shipments, routes, vehicle_cargo = [], [], {}
    for shipment_id in range(1, 41):
        vehicle_id = vehicle_ids[(shipment_id - 1) % len(vehicle_ids)]
        cargo_type = cargo_types[(shipment_id - 1) % len(cargo_types)]
        origin, destination = rng.choice(list(CITIES), size=2, replace=False)
        planted = {
            1: (284, "Vaccines", "Phoenix"), 2: (452, "Seafood", "Seattle"),
            3: (101, "Dairy", "Dallas"), 4: (7, "Produce", "Denver"),
            5: (1000, "Frozen", "Chicago"),
        }
        if shipment_id in planted:
            vehicle_id, cargo_type, origin = planted[shipment_id]
        vehicle_cargo[vehicle_id] = cargo_type
        minimum, maximum, _, max_transit = CARGO_PROFILES[cargo_type]
        depart_time = now - timedelta(hours=int(rng.integers(8, 48)))
        eta = depart_time + timedelta(hours=int(rng.integers(24, max_transit + 1)))
        waypoint_names = [origin, destination, str(rng.choice(list(CITIES)))]
        planned_route = [{"name": name, "lat": CITIES[name][0], "lon": CITIES[name][1]} for name in waypoint_names]
        shipments.append({
            "shipment_id": shipment_id, "vehicle_id": vehicle_id, "cargo_type": cargo_type,
            "cargo_value_usd": round(float(rng.uniform(25000, 500000)), 2), "origin": origin,
            "destination": destination, "planned_route_json": planned_route, "depart_time": depart_time,
            "eta": eta, "status": "in_transit" if shipment_id <= 30 else "planned",
            "min_temp_c": minimum, "max_temp_c": maximum, "max_transit_hours": max_transit,
        })
        for sequence, name in enumerate(waypoint_names):
            routes.append({
                "route_id": shipment_id * 10 + sequence, "shipment_id": shipment_id, "seq": sequence,
                "waypoint_name": name, "lat": CITIES[name][0], "lon": CITIES[name][1],
                "planned_arrival": depart_time + timedelta(hours=sequence * 12),
            })

    profile_rows = [
        {"cargo_type": name, "min_temp_c": values[0], "max_temp_c": values[1],
         "max_excursion_minutes": values[2], "max_transit_hours": values[3]}
        for name, values in CARGO_PROFILES.items()
    ]
    timestamps = [now - timedelta(minutes=5 * index) for index in range(TELEMETRY_HOURS * 12)]
    telemetry, reading_id = [], 1
    for vehicle_id in vehicle_ids:
        cargo_type = vehicle_cargo.get(vehicle_id, cargo_types[vehicle_id % len(cargo_types)])
        minimum, maximum = CARGO_PROFILES[cargo_type][:2]
        setpoint = (minimum + maximum) / 2
        base_lat, base_lon = CITIES[vehicles[vehicle_ids.index(vehicle_id)]["home_depot"]]
        for index, timestamp in enumerate(reversed(timestamps)):
            hours_old = (now - timestamp).total_seconds() / 3600
            ambient = 20 + 10 * np.sin((timestamp.hour - 6) * np.pi / 12) + rng.normal(0, 1.2)
            compressor = np.clip(35 + max(ambient - 20, 0) * 3 + rng.normal(0, 4), 5, 98)
            cargo_temp = setpoint + rng.normal(0, 0.25) + max(0, compressor - 75) * 0.025
            door_open = False
            if vehicle_id == 284:
                compressor = min(98, 45 + (TELEMETRY_HOURS - hours_old) * 0.3 + rng.normal(0, 2))
                cargo_temp = setpoint + max(0, compressor - 70) * 0.04 + rng.normal(0, 0.15)
            elif vehicle_id == 452:
                ambient += 8
                compressor = min(98, compressor + 15)
            elif vehicle_id == 101 and 15 <= hours_old <= 15.33:
                door_open, cargo_temp = True, maximum + 2.5
            elif vehicle_id == 7:
                compressor, cargo_temp = 42 + rng.normal(0, 2), setpoint + rng.normal(0, 0.12)
            elif vehicle_id == 1000:
                cargo_temp = -20 + min(4, max(0, 168 - hours_old) * 0.024) + rng.normal(0, 0.12)
            telemetry.append({
                "reading_id": reading_id, "vehicle_id": vehicle_id, "ts": timestamp,
                "lat": base_lat + np.sin(index / 30) * 0.3, "lon": base_lon + np.cos(index / 30) * 0.3,
                "cargo_temp_c": round(float(cargo_temp), 2), "ambient_temp_c": round(float(ambient), 2),
                "setpoint_c": round(float(setpoint), 2), "compressor_load_pct": round(float(compressor), 2),
                "door_open": door_open, "fuel_pct": round(float(max(8, 98 - index * 0.002)), 2),
                "speed_kph": round(float(max(0, rng.normal(62, 8))), 2),
            })
            reading_id += 1
    return {
        "vehicles": pd.DataFrame(vehicles), "shipments": pd.DataFrame(shipments),
        "routes": pd.DataFrame(routes), "cargo_profiles": pd.DataFrame(profile_rows),
        "telemetry_readings": pd.DataFrame(telemetry),
    }