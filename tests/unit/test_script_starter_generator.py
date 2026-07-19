"""Unit tests for script_starter_generator."""

from __future__ import annotations

from pathlib import Path

import pytest

from odsbox_pilot.models import AuthType, ServerConfig
from odsbox_pilot.query.script_starter_generator import (
    _build_mcp_env_basic,
    _build_mcp_env_m2m,
    _build_mcp_env_oidc,
    _build_mcp_json,
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


# ---------------------------------------------------------------------------
# MCP JSON configuration
# ---------------------------------------------------------------------------


class TestMcpEnvBasic:
    def test_has_mode_basic(self) -> None:
        env = _build_mcp_env_basic(_basic_config())
        assert env["ODSBOX_MCP_MODE"] == "basic"

    def test_has_url(self) -> None:
        env = _build_mcp_env_basic(_basic_config())
        assert env["ODSBOX_MCP_URL"] == "https://example.com/api"

    def test_has_user(self) -> None:
        env = _build_mcp_env_basic(_basic_config())
        assert env["ODSBOX_MCP_USER"] == "alice"

    def test_password_is_placeholder(self) -> None:
        env = _build_mcp_env_basic(_basic_config())
        assert "ODSBOX_MCP_PASSWORD" not in env

    def test_verify_true_becomes_string_true(self) -> None:
        cfg = _basic_config()
        cfg.verify_certificate = True
        env = _build_mcp_env_basic(cfg)
        assert env["ODSBOX_MCP_VERIFY"] == "true"

    def test_verify_false_becomes_string_false(self) -> None:
        cfg = _basic_config()
        cfg.verify_certificate = False
        env = _build_mcp_env_basic(cfg)
        assert env["ODSBOX_MCP_VERIFY"] == "false"


class TestMcpEnvM2m:
    def test_has_mode_m2m(self) -> None:
        env = _build_mcp_env_m2m(_m2m_config())
        assert env["ODSBOX_MCP_MODE"] == "m2m"

    def test_has_url(self) -> None:
        env = _build_mcp_env_m2m(_m2m_config())
        assert env["ODSBOX_MCP_URL"] == "https://example.com/api"

    def test_has_token_endpoint(self) -> None:
        env = _build_mcp_env_m2m(_m2m_config())
        assert env["ODSBOX_MCP_M2M_TOKEN_ENDPOINT"] == "https://auth.example.com/token"

    def test_has_client_id(self) -> None:
        env = _build_mcp_env_m2m(_m2m_config())
        assert env["ODSBOX_MCP_M2M_CLIENT_ID"] == "my-client"

    def test_client_secret_is_placeholder(self) -> None:
        env = _build_mcp_env_m2m(_m2m_config())
        assert "ODSBOX_MCP_M2M_CLIENT_SECRET" not in env

    def test_verify_false(self) -> None:
        env = _build_mcp_env_m2m(_m2m_config())
        assert env["ODSBOX_MCP_VERIFY"] == "false"


class TestMcpEnvOidc:
    def test_has_mode_oidc(self) -> None:
        env = _build_mcp_env_oidc(_oidc_config())
        assert env["ODSBOX_MCP_MODE"] == "oidc"

    def test_has_url(self) -> None:
        env = _build_mcp_env_oidc(_oidc_config())
        assert env["ODSBOX_MCP_URL"] == "https://example.com/api"

    def test_has_client_id(self) -> None:
        env = _build_mcp_env_oidc(_oidc_config())
        assert env["ODSBOX_MCP_OIDC_CLIENT_ID"] == "oidc-client"

    def test_has_redirect_uri(self) -> None:
        env = _build_mcp_env_oidc(_oidc_config())
        assert env["ODSBOX_MCP_OIDC_REDIRECT_URI"] == "http://127.0.0.1:12345"

    def test_has_webfinger_path_prefix_when_set(self) -> None:
        env = _build_mcp_env_oidc(_oidc_config())
        assert env["ODSBOX_MCP_OIDC_WEBFINGER_PATH_PREFIX"] == "/wf"

    def test_no_webfinger_path_prefix_when_empty(self) -> None:
        cfg = _oidc_config()
        cfg.webfinger_path_prefix = ""
        env = _build_mcp_env_oidc(cfg)
        assert "ODSBOX_MCP_OIDC_WEBFINGER_PATH_PREFIX" not in env

    def test_verify_true(self) -> None:
        env = _build_mcp_env_oidc(_oidc_config())
        assert env["ODSBOX_MCP_VERIFY"] == "true"


class TestMcpJsonBuilder:
    def test_returns_none_for_atfx(self) -> None:
        result = _build_mcp_json(_atfx_config())
        assert result is None

    def test_returns_dict_for_basic(self) -> None:
        result = _build_mcp_json(_basic_config())
        assert isinstance(result, dict)

    def test_returns_dict_for_m2m(self) -> None:
        result = _build_mcp_json(_m2m_config())
        assert isinstance(result, dict)

    def test_returns_dict_for_oidc(self) -> None:
        result = _build_mcp_json(_oidc_config())
        assert isinstance(result, dict)

    def test_basic_has_correct_structure(self) -> None:
        result = _build_mcp_json(_basic_config())
        assert result is not None
        assert "servers" in result
        assert "ods-mcp" in result["servers"]
        assert "inputs" in result
        assert result["inputs"] == []

    def test_ods_mcp_server_config_basic(self) -> None:
        result = _build_mcp_json(_basic_config())
        assert result is not None
        server = result["servers"]["ods-mcp"]
        assert server["type"] == "stdio"
        assert server["command"] == "uvx"
        assert server["args"] == ["odsbox-jaquel-mcp@latest"]
        assert "env" in server

    def test_basic_env_in_server_config(self) -> None:
        result = _build_mcp_json(_basic_config())
        assert result is not None
        env = result["servers"]["ods-mcp"]["env"]
        assert env["ODSBOX_MCP_MODE"] == "basic"
        assert env["ODSBOX_MCP_USER"] == "alice"

    def test_m2m_env_in_server_config(self) -> None:
        result = _build_mcp_json(_m2m_config())
        assert result is not None
        env = result["servers"]["ods-mcp"]["env"]
        assert env["ODSBOX_MCP_MODE"] == "m2m"
        assert env["ODSBOX_MCP_M2M_CLIENT_ID"] == "my-client"

    def test_oidc_env_in_server_config(self) -> None:
        result = _build_mcp_json(_oidc_config())
        assert result is not None
        env = result["servers"]["ods-mcp"]["env"]
        assert env["ODSBOX_MCP_MODE"] == "oidc"
        assert env["ODSBOX_MCP_OIDC_CLIENT_ID"] == "oidc-client"


class TestMcpFileGeneration:
    def test_basic_generates_mcp_json(self, tmp_path: Path) -> None:
        folder = tmp_path / "starter"
        generate_starter(_basic_config(), _QUERY_JSON, folder)
        assert (folder / ".vscode" / "mcp.json").exists()

    def test_m2m_generates_mcp_json(self, tmp_path: Path) -> None:
        folder = tmp_path / "starter"
        generate_starter(_m2m_config(), _QUERY_JSON, folder)
        assert (folder / ".vscode" / "mcp.json").exists()

    def test_oidc_generates_mcp_json(self, tmp_path: Path) -> None:
        folder = tmp_path / "starter"
        generate_starter(_oidc_config(), _QUERY_JSON, folder)
        assert (folder / ".vscode" / "mcp.json").exists()

    def test_atfx_does_not_generate_mcp_json(self, tmp_path: Path) -> None:
        folder = tmp_path / "starter"
        generate_starter(_atfx_config(), _QUERY_JSON, folder)
        assert not (folder / ".vscode" / "mcp.json").exists()
        assert not (folder / ".vscode").exists()

    def test_mcp_json_is_valid_json(self, tmp_path: Path) -> None:
        import json as json_module

        folder = tmp_path / "starter"
        generate_starter(_basic_config(), _QUERY_JSON, folder)
        content = (folder / ".vscode" / "mcp.json").read_text(encoding="utf-8")
        data = json_module.loads(content)
        assert isinstance(data, dict)

    def test_mcp_json_content_basic(self, tmp_path: Path) -> None:
        import json as json_module

        folder = tmp_path / "starter"
        generate_starter(_basic_config(), _QUERY_JSON, folder)
        content = (folder / ".vscode" / "mcp.json").read_text(encoding="utf-8")
        data = json_module.loads(content)
        assert data["servers"]["ods-mcp"]["env"]["ODSBOX_MCP_USER"] == "alice"

    def test_vscode_dir_created_once(self, tmp_path: Path) -> None:
        folder = tmp_path / "starter"
        generate_starter(_basic_config(), _QUERY_JSON, folder)
        # Verify .vscode directory exists but is created only once (idempotent)
        assert (folder / ".vscode").is_dir()
        assert (folder / ".vscode" / "mcp.json").is_file()
