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
    ATFX = "atfx"


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

    # --- Context variables passed to ConI on connect ---
    context_variables: dict[str, str] = field(default_factory=dict)

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
SETTINGS_FILE: Path = CONFIG_DIR / "settings.json"
AI_SETTINGS_FILE: Path = CONFIG_DIR / "ai_settings.json"

_VALID_NAMING_MODES = frozenset({"query", "model"})


@dataclass
class AppSettings:
    """Application-level preferences persisted across sessions."""

    result_naming_mode: str = "query"  # "query" or "model"

    def save(self) -> None:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        SETTINGS_FILE.write_text(json.dumps(asdict(self), indent=2))

    @classmethod
    def load(cls) -> AppSettings:
        try:
            data = json.loads(SETTINGS_FILE.read_text())
            known = set(cls.__dataclass_fields__)
            obj = cls(**{k: v for k, v in data.items() if k in known})
            if obj.result_naming_mode not in _VALID_NAMING_MODES:
                obj.result_naming_mode = "query"
            return obj
        except Exception:
            return cls()


@dataclass
class AiSettings:
    """AI query generation settings."""

    enabled: bool = False  # AI features enabled (model downloaded)
    model_id: str = "OpenVINO/qwen2.5-1.5b-instruct-int4-ov"
    device: str = "NPU"  # "NPU", "GPU", or "CPU"
    model_cache_dir: Path = field(default_factory=lambda: CONFIG_DIR / "models")

    def save(self) -> None:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        data = asdict(self)
        # Convert Path to string for JSON serialization
        data["model_cache_dir"] = str(data["model_cache_dir"])
        AI_SETTINGS_FILE.write_text(json.dumps(data, indent=2))

    @classmethod
    def load(cls) -> AiSettings:
        try:
            data = json.loads(AI_SETTINGS_FILE.read_text())
            # Convert string back to Path
            if "model_cache_dir" in data:
                data["model_cache_dir"] = Path(data["model_cache_dir"])
            known = set(cls.__dataclass_fields__)
            return cls(**{k: v for k, v in data.items() if k in known})
        except Exception:
            return cls()
