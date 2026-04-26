"""Domain models: ServerConfig and AuthType."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any


class AuthType(StrEnum):
    BASIC = "basic"
    M2M = "m2m"
    OIDC = "oidc"


@dataclass
class ServerConfig:
    """Holds all non-secret fields for an ODS server connection.

    Secrets (password, client_secret) are stored in the OS keyring.
    """

    id: str  # unique stable identifier (UUID)
    name: str  # human-readable label
    url: str  # ODS server base URL, e.g. https://host/api
    auth_type: AuthType

    # --- Basic auth fields ---
    username: str = ""

    # --- M2M (client credentials) fields ---
    token_endpoint: str = ""
    client_id: str = ""
    scope: list[str] = field(default_factory=list)

    # --- OIDC fields ---
    redirect_uri: str = "http://127.0.0.1:12345"
    webfinger_path_prefix: str = ""
    redirect_url_allow_insecure: bool = True

    # --- Shared TLS option ---
    verify_certificate: bool = True

    # Keyring account key is derived as:  f"{url}::{username or client_id}"

    @property
    def keyring_account(self) -> str:
        credential = self.username or self.client_id
        return f"{self.url}::{credential}"

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["auth_type"] = self.auth_type.value
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ServerConfig:
        d = dict(d)
        d["auth_type"] = AuthType(d["auth_type"])
        return cls(**d)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)

    @classmethod
    def from_json(cls, s: str) -> ServerConfig:
        return cls.from_dict(json.loads(s))


CONFIG_DIR: Path = Path.home() / ".ods-pilot"
SERVERS_FILE: Path = CONFIG_DIR / "servers.json"
HISTORY_FILE: Path = CONFIG_DIR / "history.json"
