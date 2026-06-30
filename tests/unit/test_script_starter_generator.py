"""Unit tests for script_starter_generator."""

from __future__ import annotations

from pathlib import Path

import pytest

from odsbox_pilot.models import AuthType, ServerConfig
from odsbox_pilot.query.script_starter_generator import (
    _sanitize_project_name,
    generate_starter,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _basic_config() -> ServerConfig:
    return ServerConfig(
        id="id-basic",
        name="My Server",
        url="https://example.com/api",
        auth_type=AuthType.BASIC,
        username="alice",
        verify_certificate=True,
    )


def _m2m_config() -> ServerConfig:
    return ServerConfig(
        id="id-m2m",
        name="M2M Server",
        url="https://example.com/api",
        auth_type=AuthType.M2M,
        token_endpoint="https://auth.example.com/token",
        client_id="my-client",
        scope=["read", "write"],
        verify_certificate=False,
    )


def _oidc_config() -> ServerConfig:
    return ServerConfig(
        id="id-oidc",
        name="OIDC Server",
        url="https://example.com/api",
        auth_type=AuthType.OIDC,
        client_id="oidc-client",
        redirect_uri="http://127.0.0.1:12345",
        webfinger_path_prefix="/wf",
        redirect_url_allow_insecure=True,
        verify_certificate=True,
    )


def _atfx_config() -> ServerConfig:
    return ServerConfig(
        id="id-atfx",
        name="Local File",
        url=r"C:\data\sample.atfx",
        auth_type=AuthType.ATFX,
        verify_certificate=False,
    )


_QUERY_JSON = '{"AoTest": {}}'


# ---------------------------------------------------------------------------
# _sanitize_project_name
# ---------------------------------------------------------------------------


class TestSanitizeProjectName:
    def test_simple_name(self) -> None:
        assert _sanitize_project_name("MyServer") == "myserver"

    def test_spaces_become_dashes(self) -> None:
        assert _sanitize_project_name("My Server") == "my-server"

    def test_special_chars_replaced(self) -> None:
        assert _sanitize_project_name("Server@2024!") == "server-2024"

    def test_empty_falls_back(self) -> None:
        assert _sanitize_project_name("!!!") == "ods-starter"

    def test_leading_trailing_dashes_stripped(self) -> None:
        result = _sanitize_project_name("--server--")
        assert not result.startswith("-")
        assert not result.endswith("-")


# ---------------------------------------------------------------------------
# generate_starter: folder and file creation
# ---------------------------------------------------------------------------


class TestGenerateStarterFiles:
    def test_creates_three_files(self, tmp_path: Path) -> None:
        folder = tmp_path / "my-starter"
        result = generate_starter(_basic_config(), _QUERY_JSON, folder)
        assert result == folder
        assert (folder / "pyproject.toml").exists()
        assert (folder / "script.py").exists()
        assert (folder / "README.md").exists()

    def test_raises_if_folder_exists(self, tmp_path: Path) -> None:
        folder = tmp_path / "existing"
        folder.mkdir()
        with pytest.raises(FileExistsError):
            generate_starter(_basic_config(), _QUERY_JSON, folder)

    def test_invalid_query_json_still_writes_script(self, tmp_path: Path) -> None:
        folder = tmp_path / "bad-query"
        # Should not raise even with malformed JSON
        generate_starter(_basic_config(), "not-valid-json", folder)
        script = (folder / "script.py").read_text(encoding="utf-8")
        assert "not-valid-json" in script


# ---------------------------------------------------------------------------
# pyproject.toml content
# ---------------------------------------------------------------------------


class TestPyprojectToml:
    def test_basic_has_keyring_dep(self, tmp_path: Path) -> None:
        generate_starter(_basic_config(), _QUERY_JSON, tmp_path / "s")
        content = (tmp_path / "s" / "pyproject.toml").read_text(encoding="utf-8")
        assert "odsbox[oidc]" in content
        assert "keyring" in content
        assert "wodson" not in content

    def test_atfx_has_wodson_no_keyring(self, tmp_path: Path) -> None:
        generate_starter(_atfx_config(), _QUERY_JSON, tmp_path / "s")
        content = (tmp_path / "s" / "pyproject.toml").read_text(encoding="utf-8")
        assert "wodson" in content
        assert "keyring" not in content

    def test_name_is_sanitized(self, tmp_path: Path) -> None:
        generate_starter(_basic_config(), _QUERY_JSON, tmp_path / "s")
        content = (tmp_path / "s" / "pyproject.toml").read_text(encoding="utf-8")
        assert 'name = "my-server"' in content

    def test_description_contains_server_name(self, tmp_path: Path) -> None:
        generate_starter(_basic_config(), _QUERY_JSON, tmp_path / "s")
        content = (tmp_path / "s" / "pyproject.toml").read_text(encoding="utf-8")
        assert "My Server" in content


# ---------------------------------------------------------------------------
# script.py: BASIC auth
# ---------------------------------------------------------------------------


class TestScriptBasic:
    def _script(self, tmp_path: Path) -> str:
        generate_starter(_basic_config(), _QUERY_JSON, tmp_path / "s")
        return (tmp_path / "s" / "script.py").read_text(encoding="utf-8")

    def test_uses_conifactory_basic(self, tmp_path: Path) -> None:
        assert "ConIFactory.basic(" in self._script(tmp_path)

    def test_reads_secret_from_keyring(self, tmp_path: Path) -> None:
        script = self._script(tmp_path)
        assert "keyring.get_password" in script

    def test_keyring_set_comment_present(self, tmp_path: Path) -> None:
        script = self._script(tmp_path)
        assert "keyring set ods-pilot" in script
        assert "https://example.com/api::alice" in script

    def test_contains_url_and_username(self, tmp_path: Path) -> None:
        script = self._script(tmp_path)
        assert "https://example.com/api" in script
        assert "alice" in script

    def test_contains_query(self, tmp_path: Path) -> None:
        assert "AoTest" in self._script(tmp_path)

    def test_with_context_manager(self, tmp_path: Path) -> None:
        assert "with con_i as c:" in self._script(tmp_path)

    def test_context_variables_included(self, tmp_path: Path) -> None:
        cfg = _basic_config()
        cfg.context_variables = {"env": "production"}
        folder = tmp_path / "s"
        generate_starter(cfg, _QUERY_JSON, folder)
        script = (folder / "script.py").read_text(encoding="utf-8")
        assert "context_variables" in script


# ---------------------------------------------------------------------------
# script.py: M2M auth
# ---------------------------------------------------------------------------


class TestScriptM2m:
    def _script(self, tmp_path: Path) -> str:
        generate_starter(_m2m_config(), _QUERY_JSON, tmp_path / "s")
        return (tmp_path / "s" / "script.py").read_text(encoding="utf-8")

    def test_uses_conifactory_m2m(self, tmp_path: Path) -> None:
        assert "ConIFactory.m2m(" in self._script(tmp_path)

    def test_reads_secret_from_keyring(self, tmp_path: Path) -> None:
        assert "keyring.get_password" in self._script(tmp_path)

    def test_keyring_set_comment_with_client_id(self, tmp_path: Path) -> None:
        script = self._script(tmp_path)
        assert "keyring set ods-pilot" in script
        assert "my-client" in script

    def test_token_endpoint_included(self, tmp_path: Path) -> None:
        assert "auth.example.com" in self._script(tmp_path)

    def test_scope_included(self, tmp_path: Path) -> None:
        assert "read" in self._script(tmp_path)


# ---------------------------------------------------------------------------
# script.py: OIDC auth
# ---------------------------------------------------------------------------


class TestScriptOidc:
    def _script(self, tmp_path: Path) -> str:
        generate_starter(_oidc_config(), _QUERY_JSON, tmp_path / "s")
        return (tmp_path / "s" / "script.py").read_text(encoding="utf-8")

    def test_uses_conifactory_oidc(self, tmp_path: Path) -> None:
        assert "ConIFactory.oidc(" in self._script(tmp_path)

    def test_no_keyring_import(self, tmp_path: Path) -> None:
        assert "import keyring" not in self._script(tmp_path)

    def test_contains_client_id(self, tmp_path: Path) -> None:
        assert "oidc-client" in self._script(tmp_path)

    def test_contains_redirect_uri(self, tmp_path: Path) -> None:
        assert "127.0.0.1:12345" in self._script(tmp_path)


# ---------------------------------------------------------------------------
# script.py: ATFX auth
# ---------------------------------------------------------------------------


class TestScriptAtfx:
    def _script(self, tmp_path: Path) -> str:
        generate_starter(_atfx_config(), _QUERY_JSON, tmp_path / "s")
        return (tmp_path / "s" / "script.py").read_text(encoding="utf-8")

    def test_uses_atfx_session(self, tmp_path: Path) -> None:
        assert "AtfxSession" in self._script(tmp_path)

    def test_uses_con_i_directly(self, tmp_path: Path) -> None:
        assert "from odsbox.con_i import ConI" in self._script(tmp_path)

    def test_no_keyring(self, tmp_path: Path) -> None:
        assert "keyring" not in self._script(tmp_path)

    def test_no_conifactory(self, tmp_path: Path) -> None:
        assert "ConIFactory" not in self._script(tmp_path)

    def test_file_path_included(self, tmp_path: Path) -> None:
        assert "sample.atfx" in self._script(tmp_path)

    def test_nested_with_blocks(self, tmp_path: Path) -> None:
        script = self._script(tmp_path)
        assert "with AtfxSession(" in script
        assert "with ConI(" in script


# ---------------------------------------------------------------------------
# README.md
# ---------------------------------------------------------------------------


class TestReadme:
    def test_basic_readme_has_keyring_setup(self, tmp_path: Path) -> None:
        generate_starter(_basic_config(), _QUERY_JSON, tmp_path / "s")
        readme = (tmp_path / "s" / "README.md").read_text(encoding="utf-8")
        assert "keyring set" in readme
        assert "uv sync" in readme
        assert "uv run python script.py" in readme

    def test_oidc_readme_mentions_browser(self, tmp_path: Path) -> None:
        generate_starter(_oidc_config(), _QUERY_JSON, tmp_path / "s")
        readme = (tmp_path / "s" / "README.md").read_text(encoding="utf-8")
        assert "browser" in readme.lower()
        assert "keyring set" not in readme

    def test_atfx_readme_no_credentials_section(self, tmp_path: Path) -> None:
        generate_starter(_atfx_config(), _QUERY_JSON, tmp_path / "s")
        readme = (tmp_path / "s" / "README.md").read_text(encoding="utf-8")
        assert "keyring set" not in readme
        assert "uv run python script.py" in readme

    def test_readme_contains_server_name(self, tmp_path: Path) -> None:
        generate_starter(_basic_config(), _QUERY_JSON, tmp_path / "s")
        readme = (tmp_path / "s" / "README.md").read_text(encoding="utf-8")
        assert "My Server" in readme
