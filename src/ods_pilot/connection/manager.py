"""ServerConfigManager: CRUD for saved ODS server configs.

Non-secret fields are persisted to ~/.ods-pilot/servers.json.
Secrets (passwords, client secrets) are stored in the OS keyring under
service "ods-pilot".
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path

import keyring

from ods_pilot.models import SERVERS_FILE, AuthType, ServerConfig

_KEYRING_SERVICE = "ods-pilot"


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
        """Remove a config and its associated keyring secret."""
        config = self.get(config_id)
        self._configs = [c for c in self._configs if c.id != config_id]
        self._save()
        # Best-effort cleanup of keyring secret
        try:
            keyring.delete_password(_KEYRING_SERVICE, config.keyring_account)
        except keyring.errors.PasswordDeleteError:
            pass

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
        self._path.write_text(
            json.dumps(data, indent=2), encoding="utf-8"
        )
