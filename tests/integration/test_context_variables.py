"""Integration tests: context_variables passed through ConIFactory to ConI.

Run with:
    uv run pytest tests/integration/test_context_variables.py -m integration
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from odsbox import ConI

_DEMO_URL = "https://docker.peak-solution.de:10032/api"
_DEMO_USER = "Demo"
_DEMO_PASS = "mdm"


@pytest.fixture(scope="module")
def con_i_with_write_mode() -> Iterator[ConI]:
    """ConI connection to the demo server with WRITE_MODE=FILE context variable."""
    from odsbox.con_i_factory import ConIFactory

    with ConIFactory.basic(
        url=_DEMO_URL,
        username=_DEMO_USER,
        password=_DEMO_PASS,
        context_variables={"WRITE_MODE": "FILE"},
    ) as connection:
        yield connection


@pytest.mark.integration
class TestContextVariablesConnect:
    def test_connection_succeeds_with_context_variables(self, con_i_with_write_mode: ConI) -> None:
        """A connection opened with context_variables is fully operational."""
        import pandas as pd

        df = con_i_with_write_mode.query({"AoUnit": {}})
        assert isinstance(df, pd.DataFrame)
        assert len(df) > 0

    def test_query_works_with_context_variables(self, con_i_with_write_mode: ConI) -> None:
        """Queries return expected structure when WRITE_MODE=FILE is set."""
        df = con_i_with_write_mode.query(
            {
                "AoUnit": {},
                "$attributes": {"name": 1, "id": 1},
                "$options": {"$rowlimit": 5},
            }
        )
        assert len(df) <= 5
        cols_lower = {c.lower() for c in df.columns}
        assert {"name", "id"}.issubset(cols_lower)
