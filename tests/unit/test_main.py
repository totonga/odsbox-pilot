"""Unit tests for CLI entry points."""

from __future__ import annotations

import importlib
import json
from types import ModuleType, SimpleNamespace

import pytest
from pytest_mock import MockerFixture

from odsbox_pilot.connection.manager import ServerConfigManager
from odsbox_pilot.models import AuthType


def _load_main_module() -> ModuleType:
    import odsbox_pilot.__main__ as main_module

    return importlib.reload(main_module)


def test_import_server_prompts_for_secret_and_saves_it(
    tmp_path, mocker: MockerFixture, capsys
) -> None:
    set_mock = mocker.patch("odsbox_pilot.connection.manager.keyring.set_password")
    mocker.patch("odsbox_pilot.connection.manager.keyring.get_password", return_value=None)
    mocker.patch("odsbox_pilot.connection.manager.keyring.delete_password", side_effect=None)

    export_path = tmp_path / "server.odsbox-pilot.con.json"
    export_path.write_text(
        json.dumps(
            {
                "name": "Imported Basic",
                "url": "https://example.com/api",
                "auth_type": "basic",
                "username": "alice",
            }
        ),
        encoding="utf-8",
    )
    manager = ServerConfigManager(path=tmp_path / "servers.json")
    main_module = _load_main_module()
    mocker.patch("odsbox_pilot.connection.manager.ServerConfigManager", return_value=manager)
    mocker.patch.object(main_module.sys, "stdin", SimpleNamespace(isatty=lambda: True))
    prompt_mock = mocker.patch("odsbox_pilot.__main__.getpass.getpass", return_value="secret")

    with pytest.raises(SystemExit) as exc_info:
        main_module.main(["--import-server", str(export_path)])

    assert exc_info.value.code == 0
    assert len(manager.configs) == 1
    imported = manager.configs[0]
    assert imported.auth_type == AuthType.BASIC
    prompt_mock.assert_called_once()
    set_mock.assert_called_once_with("ods-pilot", imported.keyring_account, "secret")
    captured = capsys.readouterr()
    assert "Imported server 'Imported Basic'" in captured.out


def test_import_server_skips_secret_prompt_for_oidc(tmp_path, mocker: MockerFixture) -> None:
    mocker.patch("odsbox_pilot.connection.manager.keyring.set_password")
    mocker.patch("odsbox_pilot.connection.manager.keyring.get_password", return_value=None)
    mocker.patch("odsbox_pilot.connection.manager.keyring.delete_password", side_effect=None)

    export_path = tmp_path / "server.odsbox-pilot.con.json"
    export_path.write_text(
        json.dumps(
            {
                "name": "Imported OIDC",
                "url": "https://example.com/api",
                "auth_type": "oidc",
                "client_id": "oidc-client",
            }
        ),
        encoding="utf-8",
    )
    manager = ServerConfigManager(path=tmp_path / "servers.json")
    main_module = _load_main_module()
    mocker.patch("odsbox_pilot.connection.manager.ServerConfigManager", return_value=manager)
    prompt_mock = mocker.patch("odsbox_pilot.__main__.getpass.getpass")

    with pytest.raises(SystemExit) as exc_info:
        main_module.main(["--import-server", str(export_path)])

    assert exc_info.value.code == 0
    assert len(manager.configs) == 1
    prompt_mock.assert_not_called()
