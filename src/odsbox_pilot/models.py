"""Domain models: ServerConfig and AuthType."""

from __future__ import annotations

import copy
import json
import uuid
from collections.abc import Mapping
from dataclasses import asdict, dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any

from odsbox_pilot.styles import ScaleLevel


class AuthType(StrEnum):
    BASIC = "basic"
    M2M = "m2m"
    OIDC = "oidc"
    ATFX = "atfx"


_DEFAULT_REDIRECT_URI = "http://127.0.0.1:12345"
_DEFAULT_REDIRECT_URL_ALLOW_INSECURE = True
_DEFAULT_VERIFY_CERTIFICATE = True


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
    redirect_uri: str = _DEFAULT_REDIRECT_URI
    webfinger_path_prefix: str = ""
    redirect_url_allow_insecure: bool = _DEFAULT_REDIRECT_URL_ALLOW_INSECURE

    # --- Shared TLS option ---
    verify_certificate: bool = _DEFAULT_VERIFY_CERTIFICATE

    # --- Context variables passed to ConI on connect ---
    context_variables: dict[str, str] = field(default_factory=dict)

    # Keyring account key is derived as:  f"{url}::{username or client_id}"

    @property
    def keyring_account(self) -> str:
        credential = self.username or self.client_id
        return f"{self.url}::{credential}"

    @property
    def requires_secret(self) -> bool:
        return self.auth_type in {AuthType.BASIC, AuthType.M2M}

    @property
    def secret_label(self) -> str | None:
        if self.auth_type == AuthType.BASIC:
            return "password"
        if self.auth_type == AuthType.M2M:
            return "client secret"
        return None

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

    def to_portable_dict(self) -> dict[str, Any]:
        """Serialize to a minimal portable config payload without secrets."""
        name = self.name.strip()
        url = self.url.strip()
        if not name:
            raise ValueError("Portable export requires a non-empty server name.")
        if not url:
            raise ValueError("Portable export requires a non-empty server URL or file path.")

        data: dict[str, Any] = {
            "name": name,
            "url": url,
            "auth_type": self.auth_type.value,
        }

        if self.auth_type == AuthType.BASIC:
            username = self.username.strip()
            if not username:
                raise ValueError("Portable export for Basic auth requires a username.")
            data["username"] = username
        elif self.auth_type == AuthType.M2M:
            token_endpoint = self.token_endpoint.strip()
            client_id = self.client_id.strip()
            if not token_endpoint or not client_id:
                raise ValueError(
                    "Portable export for M2M auth requires token endpoint and client ID."
                )
            data["token_endpoint"] = token_endpoint
            data["client_id"] = client_id
            if self.scope:
                data["scope"] = copy.deepcopy(self.scope)
        elif self.auth_type == AuthType.OIDC:
            client_id = self.client_id.strip()
            if not client_id:
                raise ValueError("Portable export for OIDC auth requires a client ID.")
            data["client_id"] = client_id
            if self.redirect_uri != _DEFAULT_REDIRECT_URI:
                data["redirect_uri"] = self.redirect_uri
            if self.webfinger_path_prefix:
                data["webfinger_path_prefix"] = self.webfinger_path_prefix
            if self.redirect_url_allow_insecure != _DEFAULT_REDIRECT_URL_ALLOW_INSECURE:
                data["redirect_url_allow_insecure"] = self.redirect_url_allow_insecure

        if (
            self.auth_type != AuthType.ATFX
            and self.verify_certificate != _DEFAULT_VERIFY_CERTIFICATE
        ):
            data["verify_certificate"] = self.verify_certificate
        if self.context_variables:
            data["context_variables"] = copy.deepcopy(self.context_variables)

        return data

    @classmethod
    def from_portable_dict(
        cls, data: Mapping[str, Any], *, config_id: str | None = None
    ) -> ServerConfig:
        """Create a new config from a minimal portable config payload."""
        name = cls._required_portable_str(data, "name")
        url = cls._required_portable_str(data, "url")
        auth_type_str = cls._required_portable_str(data, "auth_type")
        try:
            auth_type = AuthType(auth_type_str)
        except ValueError as exc:
            raise ValueError(f"Unsupported auth_type {auth_type_str!r}.") from exc

        base_kwargs: dict[str, Any] = {
            "id": config_id or str(uuid.uuid4()),
            "name": name,
            "url": url,
            "auth_type": auth_type,
            "verify_certificate": cls._optional_portable_bool(
                data, "verify_certificate", default=_DEFAULT_VERIFY_CERTIFICATE
            ),
            "context_variables": cls._optional_portable_context_variables(data),
        }

        if auth_type == AuthType.BASIC:
            base_kwargs["username"] = cls._required_portable_str(data, "username")
        elif auth_type == AuthType.M2M:
            base_kwargs["token_endpoint"] = cls._required_portable_str(data, "token_endpoint")
            base_kwargs["client_id"] = cls._required_portable_str(data, "client_id")
            base_kwargs["scope"] = cls._optional_portable_scope(data)
        elif auth_type == AuthType.OIDC:
            base_kwargs["client_id"] = cls._required_portable_str(data, "client_id")
            base_kwargs["redirect_uri"] = cls._optional_portable_str(
                data, "redirect_uri", default=_DEFAULT_REDIRECT_URI
            )
            base_kwargs["webfinger_path_prefix"] = cls._optional_portable_str(
                data, "webfinger_path_prefix", default=""
            )
            base_kwargs["redirect_url_allow_insecure"] = cls._optional_portable_bool(
                data,
                "redirect_url_allow_insecure",
                default=_DEFAULT_REDIRECT_URL_ALLOW_INSECURE,
            )
        elif auth_type == AuthType.ATFX:
            base_kwargs["verify_certificate"] = False

        return cls(**base_kwargs)

    @staticmethod
    def _required_portable_str(data: Mapping[str, Any], key: str) -> str:
        value = data.get(key)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"Portable config field {key!r} must be a non-empty string.")
        return value.strip()

    @staticmethod
    def _optional_portable_str(data: Mapping[str, Any], key: str, *, default: str) -> str:
        value = data.get(key)
        if value is None:
            return default
        if not isinstance(value, str):
            raise ValueError(f"Portable config field {key!r} must be a string.")
        return value.strip()

    @staticmethod
    def _optional_portable_bool(data: Mapping[str, Any], key: str, *, default: bool) -> bool:
        value = data.get(key)
        if value is None:
            return default
        if not isinstance(value, bool):
            raise ValueError(f"Portable config field {key!r} must be a boolean.")
        return value

    @staticmethod
    def _optional_portable_scope(data: Mapping[str, Any]) -> list[str]:
        value = data.get("scope")
        if value is None:
            return []
        if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
            raise ValueError("Portable config field 'scope' must be a list of strings.")
        return [item for item in value if item]

    @staticmethod
    def _optional_portable_context_variables(data: Mapping[str, Any]) -> dict[str, str]:
        value = data.get("context_variables")
        if value is None:
            return {}
        if not isinstance(value, dict):
            raise ValueError("Portable config field 'context_variables' must be an object.")

        result: dict[str, str] = {}
        for key, item in value.items():
            if not isinstance(key, str) or not key.strip() or not isinstance(item, str):
                raise ValueError(
                    "Portable config context_variables entries must map non-empty strings to strings."
                )
            result[key.strip()] = item
        return result


CONFIG_DIR: Path = Path.home() / ".ods-pilot"
SERVERS_FILE: Path = CONFIG_DIR / "servers.json"
HISTORY_FILE: Path = CONFIG_DIR / "history.json"
SETTINGS_FILE: Path = CONFIG_DIR / "settings.json"
AI_SETTINGS_FILE: Path = CONFIG_DIR / "ai_settings.json"

_VALID_NAMING_MODES = frozenset({"query", "model"})
_VALID_SCALING_LEVELS = frozenset(level.value for level in ScaleLevel)


@dataclass
class AppSettings:
    """Application-level preferences persisted across sessions."""

    result_naming_mode: str = "query"  # "query" or "model"
    startup_scaling: str = ScaleLevel.MEDIUM.value  # SMALL/MEDIUM/LARGE/XLARGE

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
            if obj.startup_scaling not in _VALID_SCALING_LEVELS:
                obj.startup_scaling = ScaleLevel.MEDIUM.value
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
