"""Unit tests for ServerConfig model."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import Mock

import pytest

import odsbox_pilot.query.main_frame as main_frame_module
from odsbox_pilot.models import AppSettings, AuthType, ServerConfig


def _make_basic() -> ServerConfig:
    return ServerConfig(
        id="test-id-1",
        name="Demo Basic",
        url="https://demo.example.com/api",
        auth_type=AuthType.BASIC,
        username="alice",
    )


def _make_m2m() -> ServerConfig:
    return ServerConfig(
        id="test-id-2",
        name="Demo M2M",
        url="https://demo.example.com/api",
        auth_type=AuthType.M2M,
        token_endpoint="https://auth.example.com/token",
        client_id="client-abc",
        scope=["api", "admin"],
    )


def _make_oidc() -> ServerConfig:
    return ServerConfig(
        id="test-id-3",
        name="Demo OIDC",
        url="https://demo.example.com/api",
        auth_type=AuthType.OIDC,
        client_id="oidc-client",
        redirect_uri="http://127.0.0.1:12345",
        webfinger_path_prefix="/ods",
    )


class TestAuthTypeEnum:
    def test_values(self) -> None:
        assert AuthType.BASIC.value == "basic"
        assert AuthType.M2M.value == "m2m"
        assert AuthType.OIDC.value == "oidc"

    def test_from_value(self) -> None:
        assert AuthType("basic") == AuthType.BASIC


class TestServerConfigSerialization:
    @pytest.mark.parametrize("cfg", [_make_basic(), _make_m2m(), _make_oidc()])
    def test_round_trip_dict(self, cfg: ServerConfig) -> None:
        restored = ServerConfig.from_dict(cfg.to_dict())
        assert restored == cfg

    @pytest.mark.parametrize("cfg", [_make_basic(), _make_m2m(), _make_oidc()])
    def test_round_trip_json(self, cfg: ServerConfig) -> None:
        restored = ServerConfig.from_json(cfg.to_json())
        assert restored == cfg

    def test_to_dict_auth_type_is_string(self) -> None:
        d = _make_basic().to_dict()
        assert isinstance(d["auth_type"], str)
        assert d["auth_type"] == "basic"

    def test_to_json_is_valid_json(self) -> None:
        data = json.loads(_make_m2m().to_json())
        assert data["auth_type"] == "m2m"

    def test_context_variables_round_trip_dict(self) -> None:
        cfg = _make_basic()
        cfg.context_variables = {"WRITE_MODE": "FILE", "LANGUAGE": "en"}
        restored = ServerConfig.from_dict(cfg.to_dict())
        assert restored.context_variables == {"WRITE_MODE": "FILE", "LANGUAGE": "en"}

    def test_context_variables_round_trip_json(self) -> None:
        cfg = _make_m2m()
        cfg.context_variables = {"ENV": "test"}
        restored = ServerConfig.from_json(cfg.to_json())
        assert restored.context_variables == {"ENV": "test"}

    def test_context_variables_empty_by_default(self) -> None:
        cfg = _make_oidc()
        assert cfg.context_variables == {}
        d = cfg.to_dict()
        assert d["context_variables"] == {}

    def test_portable_dict_omits_defaults(self) -> None:
        cfg = _make_oidc()
        data = cfg.to_portable_dict()

        assert data == {
            "name": "Demo OIDC",
            "url": "https://demo.example.com/api",
            "auth_type": "oidc",
            "client_id": "oidc-client",
            "webfinger_path_prefix": "/ods",
            "redirect_uri": "http://127.0.0.1:12345",
        }

    def test_portable_dict_keeps_non_default_values(self) -> None:
        cfg = _make_m2m()
        cfg.verify_certificate = False
        cfg.context_variables = {"WRITE_MODE": "FILE"}

        data = cfg.to_portable_dict()

        assert data == {
            "name": "Demo M2M",
            "url": "https://demo.example.com/api",
            "auth_type": "m2m",
            "token_endpoint": "https://auth.example.com/token",
            "client_id": "client-abc",
            "scope": ["api", "admin"],
            "verify_certificate": False,
            "context_variables": {"WRITE_MODE": "FILE"},
        }

    def test_from_portable_dict_uses_defaults_and_new_id(self) -> None:
        cfg = ServerConfig.from_portable_dict(
            {
                "name": "Imported OIDC",
                "url": "https://example.com/api",
                "auth_type": "oidc",
                "client_id": "client-1",
                "redirect_uri": "http://127.0.0.1:12345",
            }
        )

        assert cfg.id
        assert cfg.name == "Imported OIDC"
        assert cfg.redirect_uri == "http://127.0.0.1:12345"
        assert cfg.redirect_url_allow_insecure is False
        assert cfg.verify_certificate is True
        assert cfg.context_variables == {}

    def test_from_portable_dict_rejects_invalid_scope(self) -> None:
        with pytest.raises(ValueError, match="scope"):
            ServerConfig.from_portable_dict(
                {
                    "name": "Imported M2M",
                    "url": "https://example.com/api",
                    "auth_type": "m2m",
                    "token_endpoint": "https://auth.example.com/token",
                    "client_id": "client-1",
                    "scope": "api admin",
                }
            )

    def test_from_portable_dict_rejects_unknown_fields(self) -> None:
        with pytest.raises(ValueError, match="schema"):
            ServerConfig.from_portable_dict(
                {
                    "name": "Imported Basic",
                    "url": "https://example.com/api",
                    "auth_type": "basic",
                    "username": "alice",
                    "unexpected": True,
                }
            )

    def test_from_portable_dict_rejects_auth_specific_field_for_wrong_auth(self) -> None:
        with pytest.raises(ValueError, match="schema"):
            ServerConfig.from_portable_dict(
                {
                    "name": "Imported Basic",
                    "url": "https://example.com/api",
                    "auth_type": "basic",
                    "username": "alice",
                    "redirect_uri": "http://127.0.0.1:12345",
                }
            )


class TestKeyringAccount:
    def test_basic_keyring_account(self) -> None:
        cfg = _make_basic()
        assert cfg.keyring_account == "https://demo.example.com/api::alice"

    def test_m2m_keyring_account(self) -> None:
        cfg = _make_m2m()
        assert cfg.keyring_account == "https://demo.example.com/api::client-abc"

    def test_oidc_keyring_account(self) -> None:
        cfg = _make_oidc()
        assert cfg.keyring_account == "https://demo.example.com/api::oidc-client"

    def test_requires_secret_for_secret_backed_auth(self) -> None:
        assert _make_basic().requires_secret is True
        assert _make_m2m().requires_secret is True
        assert _make_oidc().requires_secret is False


class TestAppSettings:
    def test_execute_uses_current_result_settings(self, mocker: pytest.MockFixture) -> None:
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

    def test_defaults(self) -> None:
        s = AppSettings()
        assert s.result_naming_mode == "query"
        assert s.startup_scaling == "MEDIUM"
        assert s.date_as_timestamp is True
        assert s.enum_as_string is True
        assert s.is_null_to_nan is True

    def test_save_and_load(self, tmp_path: Path) -> None:
        import odsbox_pilot.models as models_module

        orig_settings_file = models_module.SETTINGS_FILE
        models_module.SETTINGS_FILE = tmp_path / "settings.json"
        try:
            s = AppSettings(result_naming_mode="model", startup_scaling="LARGE")
            s.save()
            loaded = AppSettings.load()
            assert loaded.result_naming_mode == "model"
            assert loaded.startup_scaling == "LARGE"
        finally:
            models_module.SETTINGS_FILE = orig_settings_file

    def test_save_and_load_boolean_settings(self, tmp_path: Path) -> None:
        import odsbox_pilot.models as models_module

        orig_settings_file = models_module.SETTINGS_FILE
        models_module.SETTINGS_FILE = tmp_path / "settings.json"
        try:
            s = AppSettings(
                result_naming_mode="model",
                startup_scaling="LARGE",
                date_as_timestamp=False,
                enum_as_string=False,
                is_null_to_nan=False,
            )
            s.save()
            loaded = AppSettings.load()
            assert loaded.result_naming_mode == "model"
            assert loaded.date_as_timestamp is False
            assert loaded.enum_as_string is False
            assert loaded.is_null_to_nan is False
        finally:
            models_module.SETTINGS_FILE = orig_settings_file

    def test_load_missing_file_returns_defaults(self, tmp_path: Path) -> None:
        import odsbox_pilot.models as models_module

        orig_settings_file = models_module.SETTINGS_FILE
        models_module.SETTINGS_FILE = tmp_path / "nonexistent.json"
        try:
            s = AppSettings.load()
            assert s.result_naming_mode == "query"
            assert s.date_as_timestamp is True
            assert s.enum_as_string is True
            assert s.is_null_to_nan is True
        finally:
            models_module.SETTINGS_FILE = orig_settings_file

    def test_load_invalid_naming_mode_fallback(self, tmp_path: Path) -> None:
        import odsbox_pilot.models as models_module

        orig_settings_file = models_module.SETTINGS_FILE
        f = tmp_path / "settings.json"
        f.write_text(json.dumps({"result_naming_mode": "INVALID"}))
        models_module.SETTINGS_FILE = f
        try:
            s = AppSettings.load()
            assert s.result_naming_mode == "query"
        finally:
            models_module.SETTINGS_FILE = orig_settings_file

    def test_load_invalid_boolean_settings_fallback(self, tmp_path: Path) -> None:
        import odsbox_pilot.models as models_module

        orig_settings_file = models_module.SETTINGS_FILE
        f = tmp_path / "settings.json"
        f.write_text(
            json.dumps(
                {
                    "date_as_timestamp": "invalid",
                    "enum_as_string": "nope",
                    "is_null_to_nan": "maybe",
                }
            )
        )
        models_module.SETTINGS_FILE = f
        try:
            s = AppSettings.load()
            assert s.date_as_timestamp is True
            assert s.enum_as_string is True
            assert s.is_null_to_nan is True
        finally:
            models_module.SETTINGS_FILE = orig_settings_file

    def test_load_ignores_unknown_keys(self, tmp_path: Path) -> None:
        import odsbox_pilot.models as models_module

        orig_settings_file = models_module.SETTINGS_FILE
        f = tmp_path / "settings.json"
        f.write_text(json.dumps({"result_naming_mode": "model", "future_key": 42}))
        models_module.SETTINGS_FILE = f
        try:
            s = AppSettings.load()
            assert s.result_naming_mode == "model"
        finally:
            models_module.SETTINGS_FILE = orig_settings_file

    def test_load_invalid_scaling_fallback(self, tmp_path: Path) -> None:
        import odsbox_pilot.models as models_module

        orig_settings_file = models_module.SETTINGS_FILE
        f = tmp_path / "settings.json"
        f.write_text(json.dumps({"startup_scaling": "HUGE"}))
        models_module.SETTINGS_FILE = f
        try:
            s = AppSettings.load()
            assert s.startup_scaling == "MEDIUM"
        finally:
            models_module.SETTINGS_FILE = orig_settings_file
