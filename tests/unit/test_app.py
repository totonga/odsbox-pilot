"""Unit tests for the application bootstrap flow."""

from __future__ import annotations

import sys
from types import ModuleType, SimpleNamespace
from typing import Any, cast

from pytest_mock import MockerFixture

from odsbox_pilot.models import AuthType, ServerConfig


class _FakeWxApp:
    pass


class _FakeWxDialog:
    pass


def _install_fake_wx(mocker: MockerFixture) -> ModuleType:
    fake_wx: Any = ModuleType("wx")
    fake_wx.App = _FakeWxApp
    fake_wx.Dialog = _FakeWxDialog
    fake_wx.MessageBox = mocker.Mock()
    fake_wx.OK = 1
    fake_wx.ICON_ERROR = 2
    fake_wx.ICON_WARNING = 4
    fake_wx.ID_OK = 5100
    fake_wx.Window = object
    mocker.patch.dict(sys.modules, {"wx": fake_wx})
    return cast(ModuleType, fake_wx)


def _load_app_module(mocker: MockerFixture) -> ModuleType:
    _install_fake_wx(mocker)
    import importlib

    import odsbox_pilot.app as app_module

    return importlib.reload(app_module)


def test_connect_hides_splash_before_error_dialog(mocker: MockerFixture) -> None:
    app_module = _load_app_module(mocker)

    call_order: list[str] = []
    splash_token = SimpleNamespace(name="splash")

    def show_splash(parent: object | None = None) -> object:
        call_order.append("show_splash")
        return splash_token

    def hide_splash(splash: object | None) -> None:
        call_order.append("hide_splash")
        assert splash is splash_token

    def do_connect(_config: ServerConfig, _secret: str) -> object:
        call_order.append("do_connect")
        raise RuntimeError("boom")

    class FakeConnectDialog:
        def __init__(self, parent: object | None, manager: object, config: ServerConfig) -> None:
            call_order.append("connect_dialog_init")
            self.con_i = "edited-connection"

        def ShowModal(self) -> int:
            call_order.append("connect_dialog_show_modal")
            return 5100

        def Destroy(self) -> None:
            call_order.append("connect_dialog_destroy")

    mocker.patch("odsbox_pilot.splash.show_splash", side_effect=show_splash)
    hide_mock = mocker.patch("odsbox_pilot.splash.hide_splash", side_effect=hide_splash)
    mocker.patch("odsbox_pilot.connection.connect_dialog.do_connect", side_effect=do_connect)
    mocker.patch("odsbox_pilot.connection.connect_dialog.ConnectDialog", FakeConnectDialog)
    message_box = mocker.patch("odsbox_pilot.app.wx.MessageBox")

    manager = mocker.Mock()
    manager.load_secret.return_value = "secret"
    config = ServerConfig(
        id="server-1",
        name="Server 1",
        url="https://example.com/api",
        auth_type=AuthType.BASIC,
        username="user",
    )
    app = app_module.OdsPilotApp.__new__(app_module.OdsPilotApp)

    result = app._connect(None, manager, config)

    assert result == "edited-connection"
    assert call_order == [
        "show_splash",
        "do_connect",
        "hide_splash",
        "connect_dialog_init",
        "connect_dialog_show_modal",
        "connect_dialog_destroy",
    ]
    hide_mock.assert_called_once_with(splash_token)
    message_box.assert_called_once()
