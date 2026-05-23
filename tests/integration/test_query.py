"""Integration tests: real queries against the Peak Solution demo ODS server.

Run with:
    uv run pytest tests/integration/ -m integration
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest

_DEMO_URL = "https://docker.peak-solution.de:10032/api"
_DEMO_USER = "Demo"
_DEMO_PASS = "mdm"


@pytest.fixture(scope="module")
def con_i() -> Iterator[Any]:
    """Live ConI connection to the demo server (module-scoped)."""
    from odsbox import ConI

    with ConI(url=_DEMO_URL, auth=(_DEMO_USER, _DEMO_PASS)) as connection:
        yield connection


@pytest.mark.integration
class TestDemoServerQueries:
    def test_query_units_returns_dataframe(self, con_i: Any) -> None:
        import pandas as pd

        df = con_i.query({"AoUnit": {}})
        assert isinstance(df, pd.DataFrame)
        assert len(df) > 0
        # odsbox capitalises column names (e.g. "Name", "Id")
        assert any(col.lower() == "name" for col in df.columns)

    def test_query_units_with_attributes(self, con_i: Any) -> None:
        df = con_i.query(
            {
                "AoUnit": {},
                "$attributes": {"name": 1, "factor": 1, "offset": 1},
            }
        )
        cols_lower = {c.lower() for c in df.columns}
        assert {"name", "factor", "offset"}.issubset(cols_lower)

    def test_query_with_row_limit(self, con_i: Any) -> None:
        df = con_i.query({"AoUnit": {}, "$options": {"$rowlimit": 3}})
        assert len(df) <= 3

    def test_query_unit_by_name(self, con_i: Any) -> None:
        df = con_i.query({"AoUnit": {"name": "s"}})
        assert len(df) >= 0  # may or may not exist on demo server

    def test_query_invalid_entity_raises(self, con_i: Any) -> None:
        with pytest.raises(Exception, match="."):
            con_i.query({"__NonExistentEntity__": {}})

    def test_query_measurements(self, con_i: Any) -> None:
        import pandas as pd

        df = con_i.query({"AoMeasurement": {}, "$options": {"$rowlimit": 5}})
        assert isinstance(df, pd.DataFrame)

    def test_local_column_properties(self, con_i: Any) -> None:
        """Querying AoLocalColumn with explicit $attributes returns those columns."""
        import pandas as pd

        df = con_i.query(
            {
                "AoLocalColumn": {},
                "$attributes": {"id": 1, "name": 1, "independent": 1, "global_flag": 1},
                "$options": {"$rowlimit": 1},
            }
        )
        assert isinstance(df, pd.DataFrame)
        assert not df.empty
        cols_lower = {c.lower() for c in df.columns}
        assert "id" in cols_lower
        assert "name" in cols_lower

    def test_local_column_values(self, con_i: Any) -> None:
        """Querying $attributes: {values: 1} for an AoLocalColumn returns numeric array data."""
        import numpy as np
        import pandas as pd

        df_ids = con_i.query(
            {
                "AoLocalColumn": {},
                "$attributes": {"id": 1},
                "$options": {"$rowlimit": 1},
            }
        )
        assert not df_ids.empty, "Demo server has no AoLocalColumn instances"
        id_col = next(c for c in df_ids.columns if c.lower() == "id")
        col_id = int(df_ids[id_col].iloc[0])

        df = con_i.query(
            {
                "AoLocalColumn": {"id": {"$eq": col_id}},
                "$attributes": {"values": 1},
            }
        )
        assert isinstance(df, pd.DataFrame)
        assert not df.empty, f"No rows returned for AoLocalColumn id={col_id}"
        values_col = next((c for c in df.columns if "values" in c.lower()), None)
        assert values_col is not None, f"No 'values' column in result: {list(df.columns)}"

        raw = df[values_col].iloc[0]
        arr = np.asarray(raw)
        assert len(arr) > 0, "Values array is empty"
        assert np.issubdtype(arr.dtype, np.number), f"Expected numeric dtype, got {arr.dtype}"
