"""Script starter generator: creates a portable uv project from an ODS connection."""

from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import sys
from pathlib import Path

from odsbox_pilot.models import AuthType, ServerConfig

_KEYRING_SERVICE = "ods-pilot"
_LOGGER = logging.getLogger(__name__)


def _sanitize_project_name(name: str) -> str:
    """Return a PEP-508-compatible project name from *name*."""
    sanitized = re.sub(r"[^a-zA-Z0-9_-]", "-", name).strip("-").lower()
    return sanitized or "ods-starter"


def _open_folder(folder: Path) -> None:
    """Try to open the folder in VS Code; fall back to file explorer on Windows.

    Skips opening if running under pytest.
    """
    # Skip opening in tests
    if "pytest" in sys.modules:
        _LOGGER.debug("Skipping folder open: running under pytest")
        return

    _LOGGER.debug(f"Attempting to open folder: {folder}")

    try:
        # Try to open in VS Code using folder as working directory
        _LOGGER.debug("Running 'code .' with cwd=%s on %s", folder, os.name)
        subprocess.run(
            "code.cmd ." if os.name == "nt" else "code .",
            cwd=str(folder),
            check=True,
            capture_output=True,
            timeout=5,
            shell=True,
        )
        _LOGGER.debug("Successfully opened folder in VS Code")
    except subprocess.TimeoutExpired as e:
        _LOGGER.warning("Timeout while opening VS Code: %s", e)
        _open_folder_fallback(folder)
    except FileNotFoundError as e:
        _LOGGER.warning("'code' command not found in PATH: %s", e)
        _open_folder_fallback(folder)
    except subprocess.CalledProcessError as e:
        _LOGGER.warning(
            "VS Code command failed with exit code %s: %s", e.returncode, e.stderr.decode().strip()
        )
        _open_folder_fallback(folder)
    except OSError as e:
        _LOGGER.warning("OS error while opening VS Code: %s", e)
        _open_folder_fallback(folder)


def _open_folder_fallback(folder: Path) -> None:
    """Fallback to file explorer on Windows."""
    if sys.platform == "win32":
        try:
            import os

            _LOGGER.debug(f"Falling back to file explorer for: {folder}")
            os.startfile(str(folder))
            _LOGGER.debug("Successfully opened folder in file explorer")
        except Exception as e:
            _LOGGER.warning(f"Failed to open folder in file explorer: {e}")
    else:
        _LOGGER.debug("Not on Windows, skipping file explorer fallback")


def generate_starter(
    server_config: ServerConfig,
    query_json: str,
    target_folder: Path,
) -> Path:
    """Create a starter project folder with pyproject.toml, script.py, README.md.

    Args:
        server_config: Active ODS connection configuration (secrets excluded).
        query_json:    Last successful query as a JSON string.
        target_folder: Exact path for the new folder (must not already exist).

    Returns:
        The created folder path.

    Raises:
        FileExistsError: If *target_folder* already exists.
    """
    target_folder.mkdir(parents=True, exist_ok=False)
    pretty_query = _format_query(query_json)
    sanitized = _sanitize_project_name(server_config.name)

    (target_folder / "pyproject.toml").write_text(
        _build_pyproject(server_config, sanitized), encoding="utf-8"
    )
    (target_folder / "script.py").write_text(
        _build_script(server_config, pretty_query), encoding="utf-8"
    )
    (target_folder / "README.md").write_text(_build_readme(server_config), encoding="utf-8")

    # Try to open the folder in VS Code or file explorer
    _open_folder(target_folder)

    return target_folder


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _format_query(query_json: str) -> str:
    """Reformat *query_json* as indented JSON; fall back to raw string on error."""
    try:
        return json.dumps(json.loads(query_json), indent=4)
    except Exception:
        return query_json


def _query_dict_lines(pretty_query: str) -> list[str]:
    """Lines for the query dict content, without outer braces."""
    lines = pretty_query.splitlines()
    if not lines:
        return []
    # Remove outer braces if present
    result = []
    for i, line in enumerate(lines):
        stripped = line.strip()
        # Skip opening brace on first line or closing brace on last line
        if i == 0 and stripped == "{":
            continue
        if i == len(lines) - 1 and stripped == "}":
            continue
        if i == 0 and stripped.startswith("{"):
            # First line might have both { and content
            if stripped == "{":
                continue
            # Content after opening brace
            result.append(line)
        elif i == len(lines) - 1 and stripped.endswith("}"):
            # Last line might have content and }
            if stripped == "}":
                continue
            # Strip closing brace
            result.append(line.rstrip().rstrip("}").rstrip())
        else:
            result.append(line)
    return result


def _keyring_lines(url: str, credential: str) -> list[str]:
    """Lines that read a secret from keyring, with a setup comment."""
    account = f"{url}::{credential}"
    return [
        "# Before running, store your secret in the OS keyring:",
        f'#   keyring set {_KEYRING_SERVICE} "{account}"',
        "",
        "import keyring",
        "",
        f"secret = keyring.get_password({_KEYRING_SERVICE!r}, {account!r})",
        "if secret is None:",
        "    raise RuntimeError(",
        f'        "No secret found in keyring for {account!r}.\\n"',
        f'        "Run:  keyring set {_KEYRING_SERVICE} {account}"',
        "    )",
        "",
    ]


def _ctx_kwarg_line(config: ServerConfig) -> list[str]:
    """Optional ``context_variables=...`` kwarg line if the config has any."""
    if not config.context_variables:
        return []
    return [f"    context_variables={config.context_variables!r},"]


# ---------------------------------------------------------------------------
# pyproject.toml
# ---------------------------------------------------------------------------


def _build_pyproject(config: ServerConfig, sanitized_name: str) -> str:
    is_atfx = config.auth_type == AuthType.ATFX
    dep_lines = ['    "odsbox[oidc]>=1.2.0",']
    if not is_atfx:
        dep_lines.append('    "keyring>=25.7.0",')
    if is_atfx:
        dep_lines.append('    "wodson>=1.1.1",')

    return "\n".join(
        [
            "[project]",
            f'name = "{sanitized_name}"',
            'version = "0.1.0"',
            f'description = "ODS query starter for {config.name}"',
            'requires-python = ">=3.14"',
            "dependencies = [",
            *dep_lines,
            "]",
            "",
            "[dependency-groups]",
            "dev = [",
            '    "pytest>=8.0",',
            '    "ruff>=0.4",',
            "]",
            "",
        ]
    )


# ---------------------------------------------------------------------------
# script.py
# ---------------------------------------------------------------------------


def _build_script(config: ServerConfig, pretty_query: str) -> str:
    if config.auth_type == AuthType.ATFX:
        return _build_script_atfx(config, pretty_query)
    if config.auth_type == AuthType.BASIC:
        return _build_script_basic(config, pretty_query)
    if config.auth_type == AuthType.M2M:
        return _build_script_m2m(config, pretty_query)
    return _build_script_oidc(config, pretty_query)  # OIDC


def _build_script_basic(config: ServerConfig, pretty_query: str) -> str:
    account = f"{config.url}::{config.username}"
    query_lines = _query_dict_lines(pretty_query)
    lines: list[str] = [
        f'"""Query script for {config.name}.',
        "",
        "Before running, store your password in the OS keyring:",
        f'    keyring set {_KEYRING_SERVICE} "{account}"',
        "",
        "Then run:",
        "    uv run python script.py",
        '"""',
        "",
        "from __future__ import annotations",
        "",
        *_keyring_lines(config.url, config.username),
        "from odsbox.con_i_factory import ConIFactory",
        "",
        "con_i = ConIFactory.basic(",
        f"    url={config.url!r},",
        f"    username={config.username!r},",
        "    password=secret,",
        f"    verify_certificate={config.verify_certificate!r},",
        *_ctx_kwarg_line(config),
        ")",
        "",
        "with con_i as c:",
        "    df = c.query({" if query_lines else "    df = c.query({})",
        *[f"      {line}" for line in query_lines],
        "    })" if query_lines else "",
        "    print(df.to_string())",
        "",
    ]
    # Filter out empty strings that might be added
    lines = [line for line in lines if line != ""]
    return "\n".join(lines)


def _build_script_m2m(config: ServerConfig, pretty_query: str) -> str:
    account = f"{config.url}::{config.client_id}"
    scope_val = repr(config.scope) if config.scope else "None"
    query_lines = _query_dict_lines(pretty_query)
    lines: list[str] = [
        f'"""Query script for {config.name}.',
        "",
        "Before running, store your client secret in the OS keyring:",
        f'    keyring set {_KEYRING_SERVICE} "{account}"',
        "",
        "Then run:",
        "    uv run python script.py",
        '"""',
        "",
        "from __future__ import annotations",
        "",
        *_keyring_lines(config.url, config.client_id),
        "from odsbox.con_i_factory import ConIFactory",
        "",
        "con_i = ConIFactory.m2m(",
        f"    url={config.url!r},",
        f"    token_endpoint={config.token_endpoint!r},",
        f"    client_id={config.client_id!r},",
        "    client_secret=secret,",
        f"    scope={scope_val},",
        f"    verify_certificate={config.verify_certificate!r},",
        *_ctx_kwarg_line(config),
        ")",
        "",
        "with con_i as c:",
        "    df = c.query({" if query_lines else "    df = c.query({})",
        *[f"      {line}" for line in query_lines],
        "    })" if query_lines else "",
        "    print(df.to_string())",
        "",
    ]
    lines = [line for line in lines if line != ""]
    return "\n".join(lines)


def _build_script_oidc(config: ServerConfig, pretty_query: str) -> str:
    query_lines = _query_dict_lines(pretty_query)
    lines: list[str] = [
        f'"""Query script for {config.name}.',
        "",
        "OIDC authentication will open your browser for login on first run.",
        "",
        "Run with:",
        "    uv run python script.py",
        '"""',
        "",
        "from __future__ import annotations",
        "",
        "from odsbox.con_i_factory import ConIFactory",
        "",
        "con_i = ConIFactory.oidc(",
        f"    url={config.url!r},",
        f"    client_id={config.client_id!r},",
        f"    redirect_uri={config.redirect_uri!r},",
        f"    webfinger_path_prefix={config.webfinger_path_prefix!r},",
        f"    redirect_url_allow_insecure={config.redirect_url_allow_insecure!r},",
        f"    verify_certificate={config.verify_certificate!r},",
        *_ctx_kwarg_line(config),
        ")",
        "",
        "with con_i as c:",
        "    df = c.query({" if query_lines else "    df = c.query({})",
        *[f"      {line}" for line in query_lines],
        "    })" if query_lines else "",
        "    print(df.to_string())",
        "",
    ]
    lines = [line for line in lines if line != ""]
    return "\n".join(lines)


def _build_script_atfx(config: ServerConfig, pretty_query: str) -> str:
    query_lines = _query_dict_lines(pretty_query)
    lines: list[str] = [
        f'"""Query script for {config.name}.',
        "",
        "Run with:",
        "    uv run python script.py",
        '"""',
        "",
        "from __future__ import annotations",
        "",
        "from odsbox.con_i import ConI",
        "from wodson.atfx import AtfxSession",
        "",
        f"_FILE_PATH = {config.url!r}",
        "",
        "with AtfxSession(default_file=_FILE_PATH) as session:",
        "    with ConI(url=session.url, auth=None, custom_session=session) as c:",
        "        df = c.query({" if query_lines else "        df = c.query({})",
        *[f"          {line}" for line in query_lines],
        "        })" if query_lines else "",
        "        print(df.to_string())",
        "",
    ]
    lines = [line for line in lines if line != ""]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# README.md
# ---------------------------------------------------------------------------


def _build_readme(config: ServerConfig) -> str:
    is_atfx = config.auth_type == AuthType.ATFX
    is_oidc = config.auth_type == AuthType.OIDC
    needs_keyring = not is_atfx and not is_oidc
    credential = config.username or config.client_id

    lines: list[str] = [
        f"# {config.name} — ODS Script Starter",
        "",
        f"Query starter project for the **{config.name}** ODS server,",
        "generated by [ODS Pilot](https://github.com/totonga/odsbox-pilot).",
        "",
        "## Prerequisites",
        "",
        "- [uv](https://docs.astral.sh/uv/) installed",
        "- Python 3.14+",
        "",
        "## Setup",
        "",
        "```bash",
        "uv sync",
        "```",
        "",
    ]

    if needs_keyring:
        account = f"{config.url}::{credential}"
        lines += [
            "## Set credentials",
            "",
            "Store your password or client secret in the OS keyring before running:",
            "",
            "```bash",
            f'keyring set {_KEYRING_SERVICE} "{account}"',
            "```",
            "",
            "Enter your password / client secret when prompted.",
            "",
        ]
    elif is_oidc:
        lines += [
            "## Authentication",
            "",
            "OIDC authentication opens your browser for login on first run.",
            "No credential pre-setup is needed.",
            "",
        ]

    lines += [
        "## Run",
        "",
        "```bash",
        "uv run python script.py",
        "```",
        "",
        "## Further reading",
        "",
        "- [odsbox on GitHub](https://github.com/peak-solution/odsbox)",
        "- [JAQueL query syntax](https://peak-solution.github.io/odsbox/jaquel_examples_notebook.html)",
        "- [uv documentation](https://docs.astral.sh/uv/)",
        "- [ASAM ODS standard](https://www.asam.net/standards/detail/ods/)",
        "",
    ]

    return "\n".join(lines)
