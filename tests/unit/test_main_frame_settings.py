"""Unit tests for MainFrame settings interactions.

These tests are wx-dependent and are skipped when wxPython is unavailable.
"""

from __future__ import annotations

from unittest.mock import Mock

import pytest

from odsbox_pilot.models import AppSettings

pytest.importorskip("wx", reason="wxPython is required for MainFrame tests")
import odsbox_pilot.query.main_frame as main_frame_module


def test_execute_uses_current_result_settings(mocker: pytest.MockFixture) -> None:
    frame = main_frame_module.MainFrame.__new__(main_frame_module.MainFrame)
    frame._settings = AppSettings(
        result_naming_mode="model",
        date_as_timestamp=False,
        enum_as_string=False,
        is_null_to_nan=False,
    )
    frame._con_i = Mock()
    frame._con_i.query_data.return_value = [{"value": 1}]
    frame._grid = Mock()
    frame._history = Mock()
    frame._log_entry = Mock()
    frame._show_error = Mock()
    frame._log = Mock()
    frame.GetStatusBar = Mock(return_value=Mock())
    mocker.patch.object(main_frame_module.wx, "BeginBusyCursor", lambda: None)
    mocker.patch.object(main_frame_module.wx, "EndBusyCursor", lambda: None)

    mocker.patch.object(
        main_frame_module,
        "jaquel_to_ods",
        return_value=({}, main_frame_module.ods.SelectStatement()),
    )

    frame._on_execute('{"AoTest": {}}')

    frame._con_i.query_data.assert_called_once()
    kwargs = frame._con_i.query_data.call_args.kwargs
    assert kwargs["date_as_timestamp"] is False
    assert kwargs["enum_as_string"] is False
    assert kwargs["is_null_to_nan"] is False
    assert kwargs["result_naming_mode"] == "model"


def test_convert_uses_current_use_base_names_setting(mocker: pytest.MockFixture) -> None:
    frame = main_frame_module.MainFrame.__new__(main_frame_module.MainFrame)
    frame._settings = AppSettings(use_base_names=True)
    frame._con_i = Mock()
    frame._con_i.mc = Mock()

    convert_mock = mocker.patch.object(
        main_frame_module.MainFrame,
        "convert_query_format",
        return_value="{}",
    )

    result = frame._on_convert("{}")

    assert result == "{}"
    convert_mock.assert_called_once_with("{}", frame._con_i.mc, True)
