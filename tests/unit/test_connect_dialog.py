"""Unit tests for ConnectDialog button handler behavior."""

from __future__ import annotations

import importlib
import sys
from types import ModuleType
from typing import Any, cast

from pytest_mock import MockerFixture

from odsbox_pilot.models import AuthType, ServerConfig


class _FakeWxDialog:
    pass


def _install_fake_wx(mocker: MockerFixture) -> ModuleType:
    fake_wx: Any = ModuleType("wx")
    fake_wx.Dialog = _FakeWxDialog
    fake_wx.Window = object
    fake_wx.Event = object
    fake_wx.OK = 1
    fake_wx.ICON_ERROR = 2
    fake_wx.ID_OK = 5100
    fake_wx.ID_CANCEL = 5101
    fake_wx.MessageBox = mocker.Mock()
    fake_wx.BeginBusyCursor = mocker.Mock()
    fake_wx.EndBusyCursor = mocker.Mock()
    mocker.patch.dict(sys.modules, {"wx": fake_wx})
    return cast(ModuleType, fake_wx)


def _load_connect_dialog_module(mocker: MockerFixture) -> ModuleType:
    _install_fake_wx(mocker)
    import odsbox_pilot.connection.connect_dialog as connect_dialog_module

    return importlib.reload(connect_dialog_module)


def _basic_config() -> ServerConfig:
    return ServerConfig(
        id="id-1",
        name="Server 1",
        url="https://example.com/api",
        auth_type=AuthType.BASIC,
        username="user",
    )


def test_on_cancel_closes_dialog(mocker: MockerFixture) -> None:
    module = _load_connect_dialog_module(mocker)
    dialog = module.ConnectDialog.__new__(module.ConnectDialog)
    dialog.EndModal = mocker.Mock()

    module.ConnectDialog._on_cancel(dialog, mocker.Mock())

    dialog.EndModal.assert_called_once_with(module.wx.ID_CANCEL)


def test_on_save_only_success_closes_dialog(mocker: MockerFixture) -> None:
    module = _load_connect_dialog_module(mocker)
    dialog = module.ConnectDialog.__new__(module.ConnectDialog)
    dialog._build_config = mocker.Mock(return_value=(_basic_config(), "secret"))
    dialog._save_config = mocker.Mock()
    dialog.EndModal = mocker.Mock()

    module.ConnectDialog._on_save_only(dialog, mocker.Mock())

    dialog._save_config.assert_called_once()
    dialog.EndModal.assert_called_once_with(module.wx.ID_OK)


def test_on_save_only_save_error_stays_open(mocker: MockerFixture) -> None:
    module = _load_connect_dialog_module(mocker)
    dialog = module.ConnectDialog.__new__(module.ConnectDialog)
    dialog._build_config = mocker.Mock(return_value=(_basic_config(), "secret"))
    dialog._save_config = mocker.Mock(side_effect=RuntimeError("disk error"))
    dialog.EndModal = mocker.Mock()

    module.ConnectDialog._on_save_only(dialog, mocker.Mock())

    dialog.EndModal.assert_not_called()
    module.wx.MessageBox.assert_called_once()


def test_on_save_connect_save_error_stays_open(mocker: MockerFixture) -> None:
    module = _load_connect_dialog_module(mocker)
    dialog = module.ConnectDialog.__new__(module.ConnectDialog)
    dialog._build_config = mocker.Mock(return_value=(_basic_config(), "secret"))
    dialog._save_config = mocker.Mock(side_effect=RuntimeError("permission denied"))
    dialog._do_connect = mocker.Mock()
    dialog.EndModal = mocker.Mock()

    module.ConnectDialog._on_save_connect(dialog, mocker.Mock())

    dialog._do_connect.assert_not_called()
    dialog.EndModal.assert_not_called()
    module.wx.MessageBox.assert_called_once()


def test_on_save_connect_connect_error_stays_open(mocker: MockerFixture) -> None:
    module = _load_connect_dialog_module(mocker)
    dialog = module.ConnectDialog.__new__(module.ConnectDialog)
    dialog._build_config = mocker.Mock(return_value=(_basic_config(), "secret"))
    dialog._save_config = mocker.Mock()
    dialog._do_connect = mocker.Mock(side_effect=RuntimeError("connect failed"))
    dialog.EndModal = mocker.Mock()

    module.ConnectDialog._on_save_connect(dialog, mocker.Mock())

    dialog.EndModal.assert_not_called()
    module.wx.MessageBox.assert_called_once()
    module.wx.BeginBusyCursor.assert_called_once()
    module.wx.EndBusyCursor.assert_called()


def test_on_save_only_missing_guid_error_message(mocker: MockerFixture) -> None:
    module = _load_connect_dialog_module(mocker)
    dialog = module.ConnectDialog.__new__(module.ConnectDialog)
    cfg = _basic_config()
    cfg.id = "missing-guid"
    dialog._build_config = mocker.Mock(return_value=(cfg, "secret"))
    dialog._save_config = mocker.Mock(side_effect=KeyError("Config missing"))
    dialog.EndModal = mocker.Mock()

    module.ConnectDialog._on_save_only(dialog, mocker.Mock())

    dialog.EndModal.assert_not_called()
    module.wx.MessageBox.assert_called_once()
    message = module.wx.MessageBox.call_args.args[0]
    assert "GUID 'missing-guid' could not be found." in message
