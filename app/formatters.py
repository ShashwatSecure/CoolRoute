"""Presentation conversions for Streamlit components."""

from __future__ import annotations

import pandas as pd


def map_coordinates(telemetry: pd.DataFrame) -> pd.DataFrame:
    """Return latitude and longitude as native floats for Streamlit maps."""
    coordinates = telemetry.rename(columns={"lat": "latitude", "lon": "longitude"})[
        ["latitude", "longitude"]
    ].copy()
    coordinates["latitude"] = coordinates["latitude"].astype(float)
    coordinates["longitude"] = coordinates["longitude"].astype(float)
    return coordinates
