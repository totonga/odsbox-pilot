"""Unit tests for AtfxConI / open_atfx factory.

These tests use a real in-process AtfxSession (no network, no wx).
The Example_Simple.atfx fixture is the canonical ASAM ODS example file
from the wodson project.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import requests

from odsbox_pilot.connection.atfx_factory import AtfxConI, open_atfx

SIMPLE_ATFX = (
    Path(__file__).resolve().parent.parent / "data" / "openatfx" / "asam600" / "Example_Simple.atfx"
)


class TestOpenAtfx:
    """Tests for the open_atfx factory function."""

    def test_fixture_exists(self) -> None:
        assert SIMPLE_ATFX.is_file(), f"Test fixture not found: {SIMPLE_ATFX}"

    def test_returns_atfx_con_i(self) -> None:
        con = open_atfx(SIMPLE_ATFX)
        try:
            assert isinstance(con, AtfxConI)
        finally:
            con.close()

    def test_model_has_environment_entity(self) -> None:
        con = open_atfx(SIMPLE_ATFX)
        try:
            model = con.mc.model()
            assert "Environment" in model.entities
        finally:
            con.close()

    def test_model_has_measurement_entity(self) -> None:
        con = open_atfx(SIMPLE_ATFX)
        try:
            model = con.mc.model()
            assert "Measurement" in model.entities
        finally:
            con.close()

    def test_model_entity_count(self) -> None:
        con = open_atfx(SIMPLE_ATFX)
        try:
            model = con.mc.model()
            assert len(model.entities) > 0
        finally:
            con.close()

    def test_context_manager_enters_and_exits(self) -> None:
        with open_atfx(SIMPLE_ATFX) as con:
            model = con.mc.model()
            assert "Test" in model.entities

    def test_context_manager_returns_atfx_con_i(self) -> None:
        with open_atfx(SIMPLE_ATFX) as con:
            assert isinstance(con, AtfxConI)

    def test_path_object_accepted(self) -> None:
        with open_atfx(Path(SIMPLE_ATFX)) as con:
            model = con.mc.model()
            assert len(model.entities) > 0

    def test_string_path_accepted(self) -> None:
        with open_atfx(str(SIMPLE_ATFX)) as con:
            model = con.mc.model()
            assert len(model.entities) > 0

    def test_bad_path_raises(self) -> None:
        with pytest.raises(Exception):  # requests.HTTPError from ConI  # noqa: B017
            open_atfx("/nonexistent/path/file.atfx")


class TestAtfxConIDelegation:
    """Tests that AtfxConI correctly delegates to the inner ConI."""

    def test_mc_attribute_accessible(self) -> None:
        with open_atfx(SIMPLE_ATFX) as con:
            mc = con.mc
            assert mc is not None

    def test_unknown_attribute_raises_attribute_error(self) -> None:
        with open_atfx(SIMPLE_ATFX) as con, pytest.raises(AttributeError):
            _ = con._this_attribute_does_not_exist_xyz

    def test_close_is_callable(self) -> None:
        con = open_atfx(SIMPLE_ATFX)
        con.close()  # must not raise

    def test_double_close_does_not_raise(self) -> None:
        con = open_atfx(SIMPLE_ATFX)
        con.close()
        con.close()  # second close should not raise


class TestAtfxConINoWx:
    """Verify that atfx_factory has no wx dependency at import time."""

    def test_no_wx_import_needed(self) -> None:
        # Re-import to confirm module loads cleanly without wx
        import importlib

        import odsbox_pilot.connection.atfx_factory as mod

        importlib.reload(mod)
        assert hasattr(mod, "open_atfx")
        assert hasattr(mod, "AtfxConI")


class TestAtfxHttpError:
    """Tests around error handling for bad ATFX paths."""

    def test_bad_path_raises_http_error(self) -> None:
        with pytest.raises(requests.HTTPError):
            open_atfx("/nonexistent/path/file.atfx")
