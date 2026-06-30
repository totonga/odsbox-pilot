"""Business logic for script starter generation (wx-free)."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path
from typing import NamedTuple

from odsbox_pilot.models import ServerConfig
from odsbox_pilot.query.history import QueryHistory


class ValidationResult(NamedTuple):
    """Result of script starter validation."""

    is_valid: bool
    error_message: str | None


class GenerationPlan(NamedTuple):
    """Information needed to generate a script starter."""

    server_config: ServerConfig
    last_query: str
    target_path: Path


def validate_script_starter_prerequisites(
    server_config: ServerConfig | None,
    history: QueryHistory,
) -> ValidationResult:
    """Validate that script starter generation is possible.

    Returns ValidationResult with is_valid=True if OK, or error_message if not.
    """
    if server_config is None:
        return ValidationResult(
            is_valid=False,
            error_message="No server configuration available for this connection.",
        )

    last_query = next(
        (e.query for e in history.entries if e.error is None),
        None,
    )
    if last_query is None:
        return ValidationResult(
            is_valid=False,
            error_message="No successful query to export.\nPlease run a query first.",
        )

    return ValidationResult(is_valid=True, error_message=None)


def compute_target_path(
    parent_path: Path,
    server_config: ServerConfig,
) -> Path | str:
    """Compute target path for script starter, handling collisions.

    Returns Path if successful, or error message (str) if collision detection fails.
    """
    timestamp = datetime.now(tz=UTC).strftime("%Y%m%d-%H%M%S")
    safe_name = re.sub(r"[^a-zA-Z0-9_-]", "-", server_config.name).strip("-") or "ods"
    base_name = f"{safe_name}-starter-{timestamp}"
    base_path = parent_path / base_name

    # Collision-safe folder resolution
    target_path = base_path
    if target_path.exists():
        for i in range(1, 11):
            candidate = parent_path / f"{base_name}-{i}"
            if not candidate.exists():
                target_path = candidate
                break
        else:
            return f"Could not find a free folder name under {parent_path}"

    return target_path
