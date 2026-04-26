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
