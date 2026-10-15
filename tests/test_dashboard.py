from decimal import Decimal

import pandas as pd

from app.formatters import map_coordinates


def test_map_coordinates_converts_database_decimals_to_floats() -> None:
    telemetry = pd.DataFrame(
        [{"lat": Decimal("33.448400"), "lon": Decimal("-112.074000")}]
    )

    result = map_coordinates(telemetry)

    assert list(result.columns) == ["latitude", "longitude"]
    assert result.iloc[0].to_dict() == {"latitude": 33.4484, "longitude": -112.074}
    assert all(dtype.kind == "f" for dtype in result.dtypes)
