"""ServerConfigManager: CRUD for saved ODS server configs.

Non-secret fields are persisted to ~/.ods-pilot/servers.json.
Secrets (passwords, client secrets) are stored in the OS keyring under
service "ods-pilot".
"""

from __future__ import annotations

import contextlib
import json
import tomllib
import uuid
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import keyring

from odsbox_pilot.models import SERVERS_FILE, ServerConfig, _read_portable_config_schema_text

_KEYRING_SERVICE = "ods-pilot"
PORTABLE_CONFIG_SUFFIX = ".ods-pilot.con.json"
PORTABLE_CONFIG_TOML_SUFFIX = ".ods-pilot.con.toml"
PORTABLE_CONFIG_WILDCARD = (
    "ODS Pilot Connection (*.ods-pilot.con.json; *.ods-pilot.con.toml)|"
    "*.ods-pilot.con.json;*.ods-pilot.con.toml|"
    "JSON files (*.json)|*.json|"
    "TOML files (*.toml)|*.toml|"
    "All files (*.*)|*.*"
)


def _toml_escape_string(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _serialize_toml_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return str(value)
    if isinstance(value, str):
        return _toml_escape_string(value)
    if isinstance(value, list):
        return "[" + ", ".join(_serialize_toml_value(item) for item in value) + "]"
    if isinstance(value, Mapping):
        inline_items = ", ".join(
            f"{key} = {_serialize_toml_value(item)}" for key, item in value.items()
        )
        return "{" + inline_items + "}"
    raise ValueError(f"Unsupported TOML value type: {type(value).__name__}")


def _serialize_portable_config_toml(data: Mapping[str, Any]) -> str:
    lines = [f"{key} = {_serialize_toml_value(value)}" for key, value in data.items()]
    return "\n".join(lines) + "\n"


def _load_portable_config_data(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".toml":
        try:
            data = tomllib.loads(text)
        except tomllib.TOMLDecodeError as exc:
            raise ValueError("Portable config file must contain valid TOML.") from exc
    else:
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            try:
                data = tomllib.loads(text)
            except tomllib.TOMLDecodeError as exc2:
                raise ValueError("Portable config file must contain valid JSON or TOML.") from exc2
    if not isinstance(data, dict):
        raise ValueError("Portable config file must contain a top-level object.")
    return data


class ServerConfigManager:
    """Load, save, and manage ODS server configurations."""

    def __init__(self, path: Path = SERVERS_FILE) -> None:
        self._path = path
        self._configs: list[ServerConfig] = []
        self._load()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def configs(self) -> list[ServerConfig]:
        return list(self._configs)

    def add(self, config: ServerConfig) -> None:
        """Add a new server config. Raises ValueError if id already exists."""
        if any(c.id == config.id for c in self._configs):
            raise ValueError(f"Config with id {config.id!r} already exists.")

        if any(c.name == config.name for c in self._configs):
            base_name = config.name.strip()
            suffix = 2
            candidate_name = f"{base_name} ({suffix})"
            while any(c.name == candidate_name for c in self._configs):
                suffix += 1
                candidate_name = f"{base_name} ({suffix})"
            config.name = candidate_name

        self._configs.append(config)
        self._save()

    def update(self, config: ServerConfig) -> None:
        """Replace an existing config by id. Raises KeyError if not found."""
        for i, c in enumerate(self._configs):
            if c.id == config.id:
                self._configs[i] = config
                self._save()
                return
        raise KeyError(f"Config {config.id!r} not found.")

    def remove(self, config_id: str) -> None:
        """Remove a config and its associated keyring secret if it is no longer shared."""
        config = self.get(config_id)
        self._configs = [c for c in self._configs if c.id != config_id]
        self._save()

        remaining_configs = [
            c for c in self._configs if c.keyring_account == config.keyring_account
        ]
        if remaining_configs:
            return

        # Best-effort cleanup of keyring secret
        with contextlib.suppress(keyring.errors.PasswordDeleteError):
            keyring.delete_password(_KEYRING_SERVICE, config.keyring_account)

    def get(self, config_id: str) -> ServerConfig:
        """Return a config by id. Raises KeyError if not found."""
        for c in self._configs:
            if c.id == config_id:
                return c
        raise KeyError(f"Config {config_id!r} not found.")

    # ------------------------------------------------------------------
    # Keyring helpers
    # ------------------------------------------------------------------

    def save_secret(self, config: ServerConfig, secret: str) -> None:
        """Store the password or client secret in the OS keyring."""
        keyring.set_password(_KEYRING_SERVICE, config.keyring_account, secret)

    def load_secret(self, config: ServerConfig) -> str | None:
        """Retrieve the password or client secret from the OS keyring."""
        return keyring.get_password(_KEYRING_SERVICE, config.keyring_account)

    def export_to_file(self, config: ServerConfig, path: Path) -> None:
        """Write a minimal, secret-free config export file and an adjacent schema sidecar."""
        path.parent.mkdir(parents=True, exist_ok=True)
        data = config.to_portable_dict()
        if path.suffix.lower() == ".toml":
            payload = _serialize_portable_config_toml(data)
        else:
            payload = json.dumps(data, indent=2)
        path.write_text(payload, encoding="utf-8")

        schema_path = path.with_name("ods-pilot.con.schema.json")
        if not schema_path.exists():
            schema_path.write_text(_read_portable_config_schema_text(), encoding="utf-8")

    def read_portable_config(self, path: Path) -> ServerConfig:
        """Read a portable config file into a new unsaved config draft."""
        try:
            data = _load_portable_config_data(path)
        except ValueError as exc:
            raise ValueError(str(exc)) from exc
        try:
            return ServerConfig.from_portable_dict(data, config_id=self.new_id())
        except ValueError as exc:
            raise ValueError(f"Portable config file failed schema validation: {exc}") from exc

    def import_from_file(self, path: Path, secret: str = "") -> ServerConfig:
        """Import a portable config file into the saved server list."""
        config = self.read_portable_config(path)
        self.add(config)
        if secret:
            self.save_secret(config, secret)
        return config

    # ------------------------------------------------------------------
    # Factory helpers
    # ------------------------------------------------------------------

    @staticmethod
    def new_id() -> str:
        return str(uuid.uuid4())

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _load(self) -> None:
        if not self._path.exists():
            self._configs = []
            return
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            self._configs = [ServerConfig.from_dict(d) for d in data]
        except Exception:
            self._configs = []

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        data = [c.to_dict() for c in self._configs]
        self._path.write_text(json.dumps(data, indent=2), encoding="utf-8")
