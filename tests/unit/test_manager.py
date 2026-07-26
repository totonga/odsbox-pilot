"""Unit tests for ServerConfigManager."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pytest_mock import MockerFixture

from odsbox_pilot.connection.manager import ServerConfigManager
from odsbox_pilot.models import AuthType, ServerConfig


def _cfg(suffix: str = "1") -> ServerConfig:
    return ServerConfig(
        id=f"id-{suffix}",
        name=f"Server {suffix}",
        url=f"https://server{suffix}.example.com/api",
        auth_type=AuthType.BASIC,
        username=f"user{suffix}",
    )


@pytest.fixture
def manager(tmp_path: Path, mocker: MockerFixture) -> ServerConfigManager:
    """A ServerConfigManager backed by a tmp directory with mocked keyring."""
    servers_file = tmp_path / "servers.json"
    mocker.patch("odsbox_pilot.connection.manager.keyring.set_password")
    mocker.patch("odsbox_pilot.connection.manager.keyring.get_password", return_value=None)
    mocker.patch(
        "odsbox_pilot.connection.manager.keyring.delete_password",
        side_effect=None,
    )
    return ServerConfigManager(path=servers_file)


class TestManagerCRUD:
    def test_initially_empty(self, manager: ServerConfigManager) -> None:
        assert manager.configs == []

    def test_add_and_get(self, manager: ServerConfigManager) -> None:
        cfg = _cfg("a")
        manager.add(cfg)
        assert manager.get("id-a") == cfg

    def test_add_duplicate_raises(self, manager: ServerConfigManager) -> None:
        manager.add(_cfg("x"))
        with pytest.raises(ValueError, match="already exists"):
            manager.add(_cfg("x"))

    def test_add_duplicate_name_makes_unique(self, manager: ServerConfigManager) -> None:
        first = _cfg("x")
        first.name = "Shared Name"
        manager.add(first)

        second = _cfg("y")
        second.name = "Shared Name"
        manager.add(second)

        assert manager.get(second.id).name == "Shared Name (2)"

    def test_update(self, manager: ServerConfigManager) -> None:
        manager.add(_cfg("b"))
        updated = _cfg("b")
        updated.name = "Updated Name"
        manager.update(updated)
        assert manager.get("id-b").name == "Updated Name"

    def test_update_missing_raises(self, manager: ServerConfigManager) -> None:
        with pytest.raises(KeyError):
            manager.update(_cfg("missing"))

    def test_remove(self, manager: ServerConfigManager) -> None:
        manager.add(_cfg("c"))
        manager.remove("id-c")
        assert len(manager.configs) == 0

    def test_remove_missing_raises(self, manager: ServerConfigManager) -> None:
        with pytest.raises(KeyError):
            manager.remove("no-such-id")

    def test_get_missing_raises(self, manager: ServerConfigManager) -> None:
        with pytest.raises(KeyError):
            manager.get("ghost")

    def test_multiple_configs_order_preserved(self, manager: ServerConfigManager) -> None:
        for i in range(5):
            manager.add(_cfg(str(i)))
        ids = [c.id for c in manager.configs]
        assert ids == [f"id-{i}" for i in range(5)]


class TestManagerPersistence:
    def test_reload_from_file(self, tmp_path: Path, mocker: MockerFixture) -> None:
        mocker.patch("odsbox_pilot.connection.manager.keyring.set_password")
        mocker.patch("odsbox_pilot.connection.manager.keyring.get_password", return_value=None)
        mocker.patch("odsbox_pilot.connection.manager.keyring.delete_password", side_effect=None)

        path = tmp_path / "servers.json"
        m1 = ServerConfigManager(path=path)
        m1.add(_cfg("persist"))

        m2 = ServerConfigManager(path=path)
        assert len(m2.configs) == 1
        assert m2.get("id-persist").name == "Server persist"

    def test_context_variables_survive_save_load(
        self, tmp_path: Path, mocker: MockerFixture
    ) -> None:
        mocker.patch("odsbox_pilot.connection.manager.keyring.set_password")
        mocker.patch("odsbox_pilot.connection.manager.keyring.get_password", return_value=None)
        mocker.patch("odsbox_pilot.connection.manager.keyring.delete_password", side_effect=None)

        path = tmp_path / "servers.json"
        m1 = ServerConfigManager(path=path)
        cfg = _cfg("cv")
        cfg.context_variables = {"WRITE_MODE": "FILE", "X": "1"}
        m1.add(cfg)

        m2 = ServerConfigManager(path=path)
        loaded = m2.get("id-cv")
        assert loaded.context_variables == {"WRITE_MODE": "FILE", "X": "1"}

    def test_corrupt_file_yields_empty(self, tmp_path: Path, mocker: MockerFixture) -> None:
        mocker.patch("odsbox_pilot.connection.manager.keyring.set_password")
        mocker.patch("odsbox_pilot.connection.manager.keyring.get_password", return_value=None)
        path = tmp_path / "servers.json"
        path.write_text("NOT JSON", encoding="utf-8")
        m = ServerConfigManager(path=path)
        assert m.configs == []

    def test_export_to_file_omits_secret_and_defaults(
        self, manager: ServerConfigManager, tmp_path: Path
    ) -> None:
        cfg = _cfg("export")
        manager.add(cfg)
        manager.save_secret(cfg, "s3cr3t")

        export_path = tmp_path / "server.ods-pilot.con.json"
        manager.export_to_file(cfg, export_path)

        data = json.loads(export_path.read_text(encoding="utf-8"))
        assert data == {
            "name": "Server export",
            "url": "https://serverexport.example.com/api",
            "auth_type": "basic",
            "username": "userexport",
        }

    def test_export_to_file_writes_schema_sidecar(
        self, manager: ServerConfigManager, tmp_path: Path
    ) -> None:
        cfg = _cfg("sidecar")
        manager.add(cfg)

        export_path = tmp_path / "server.ods-pilot.con.json"
        manager.export_to_file(cfg, export_path)

        schema_path = export_path.with_name("ods-pilot.con.schema.json")
        assert schema_path.exists()
        schema_data = json.loads(schema_path.read_text(encoding="utf-8"))
        assert schema_data["title"] == "ODS Pilot portable connection"

    def test_read_portable_config_creates_new_unsaved_draft(
        self, manager: ServerConfigManager, tmp_path: Path
    ) -> None:
        export_path = tmp_path / "server.ods-pilot.con.json"
        export_path.write_text(
            json.dumps(
                {
                    "name": "Imported Server",
                    "url": "https://import.example.com/api",
                    "auth_type": "m2m",
                    "token_endpoint": "https://auth.example.com/token",
                    "client_id": "client-123",
                }
            ),
            encoding="utf-8",
        )

        imported = manager.read_portable_config(export_path)

        assert imported.id
        assert imported.id != "id-1"
        assert imported.name == "Imported Server"
        assert imported.auth_type == AuthType.M2M
        assert imported.client_id == "client-123"
        assert manager.configs == []

    def test_read_portable_config_rejects_invalid_schema(
        self, manager: ServerConfigManager, tmp_path: Path
    ) -> None:
        export_path = tmp_path / "server.ods-pilot.con.json"
        export_path.write_text(
            json.dumps(
                {
                    "name": "Imported Server",
                    "url": "https://import.example.com/api",
                    "auth_type": "basic",
                    "username": "alice",
                    "unexpected": True,
                }
            ),
            encoding="utf-8",
        )

        with pytest.raises(ValueError, match="schema"):
            manager.read_portable_config(export_path)


class TestKeyringIntegration:
    def test_save_and_load_secret(self, tmp_path: Path, mocker: MockerFixture) -> None:
        set_mock = mocker.patch("odsbox_pilot.connection.manager.keyring.set_password")
        get_mock = mocker.patch(
            "odsbox_pilot.connection.manager.keyring.get_password", return_value="s3cr3t"
        )
        mocker.patch("odsbox_pilot.connection.manager.keyring.delete_password", side_effect=None)

        path = tmp_path / "servers.json"
        m = ServerConfigManager(path=path)
        cfg = _cfg("k")
        m.add(cfg)
        m.save_secret(cfg, "s3cr3t")
        secret = m.load_secret(cfg)

        set_mock.assert_called_once_with("ods-pilot", cfg.keyring_account, "s3cr3t")
        get_mock.assert_called_once_with("ods-pilot", cfg.keyring_account)
        assert secret == "s3cr3t"

    def test_import_from_file_saves_secret(self, tmp_path: Path, mocker: MockerFixture) -> None:
        set_mock = mocker.patch("odsbox_pilot.connection.manager.keyring.set_password")
        mocker.patch("odsbox_pilot.connection.manager.keyring.get_password", return_value=None)
        mocker.patch("odsbox_pilot.connection.manager.keyring.delete_password", side_effect=None)

        path = tmp_path / "servers.json"
        export_path = tmp_path / "server.ods-pilot.con.json"
        export_path.write_text(
            json.dumps(
                {
                    "name": "Imported Server",
                    "url": "https://import.example.com/api",
                    "auth_type": "basic",
                    "username": "alice",
                }
            ),
            encoding="utf-8",
        )

        manager = ServerConfigManager(path=path)
        imported = manager.import_from_file(export_path, secret="imported-secret")

        assert manager.get(imported.id) == imported
        set_mock.assert_called_once_with(
            "ods-pilot",
            imported.keyring_account,
            "imported-secret",
        )
