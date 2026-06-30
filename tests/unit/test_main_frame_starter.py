"""Unit tests for script starter generation logic."""

from __future__ import annotations

from pathlib import Path

from pytest_mock import MockerFixture

from odsbox_pilot.models import AuthType, ServerConfig
from odsbox_pilot.query.history import HistoryEntry, QueryHistory
from odsbox_pilot.query.script_starter_logic import (
    compute_target_path,
    validate_script_starter_prerequisites,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _basic_config() -> ServerConfig:
    return ServerConfig(
        id="id-1",
        name="Test Server",
        url="https://example.com/api",
        auth_type=AuthType.BASIC,
        username="user",
    )


def _make_history(successful_queries: list[str]) -> QueryHistory:
    """Create a QueryHistory with specified successful queries."""
    history = QueryHistory()
    # Add entries in reverse order so they appear most-recent-first in the entries property
    for q in reversed(successful_queries):
        history.append(HistoryEntry.success(q, row_count=1))
    return history


# ---------------------------------------------------------------------------
# Tests for validation logic (no wx needed)
# ---------------------------------------------------------------------------


class TestValidateScriptStarterPrerequisites:
    def test_no_server_config_fails(self) -> None:
        history = _make_history([])
        result = validate_script_starter_prerequisites(None, history)

        assert not result.is_valid
        assert result.error_message is not None
        assert "No server configuration" in result.error_message

    def test_no_successful_query_fails(self, tmp_path: Path) -> None:
        config = _basic_config()
        # Create a history with only failed entries, using a temporary file
        history_file = tmp_path / "history.json"
        history = QueryHistory(history_file)
        history.append(HistoryEntry.failure('{"AoTest": {}}', error="syntax error"))
        result = validate_script_starter_prerequisites(config, history)

        assert not result.is_valid
        assert result.error_message is not None
        assert "run a query first" in result.error_message.lower()

    def test_with_config_and_query_passes(self) -> None:
        config = _basic_config()
        history = _make_history(['{"AoTest": {}}'])
        result = validate_script_starter_prerequisites(config, history)

        assert result.is_valid
        assert result.error_message is None


# ---------------------------------------------------------------------------
# Tests for path computation logic (no wx needed)
# ---------------------------------------------------------------------------


class TestComputeTargetPath:
    def test_creates_new_folder_when_no_collision(self, tmp_path: Path) -> None:
        config = _basic_config()
        result = compute_target_path(tmp_path, config)

        assert isinstance(result, Path)
        assert result.parent == tmp_path
        assert "Test-Server-starter" in result.name

    def test_uses_name_for_folder_prefix(self, tmp_path: Path) -> None:
        config = ServerConfig(
            id="id-1",
            name="My-Server_Name",
            url="https://example.com/api",
            auth_type=AuthType.BASIC,
            username="user",
        )
        result = compute_target_path(tmp_path, config)

        assert isinstance(result, Path)
        assert result.parent == tmp_path
        # The name should be preserved (alphanumerics, hyphens, underscores are kept)
        assert "My-Server_Name-starter" in result.name

    def test_sanitizes_unsafe_characters(self, tmp_path: Path) -> None:
        config = ServerConfig(
            id="id-1",
            name="Server <unsafe> Name!",
            url="https://example.com/api",
            auth_type=AuthType.BASIC,
            username="user",
        )
        result = compute_target_path(tmp_path, config)

        assert isinstance(result, Path)
        # Should not have < > or !
        assert "<" not in result.name
        assert ">" not in result.name
        assert "!" not in result.name

    def test_handles_collision_by_suffixing(self, tmp_path: Path) -> None:
        config = _basic_config()
        # Create the initial folder so collision happens
        (tmp_path / "Test-Server-starter-20260101-000000").mkdir()

        result = compute_target_path(tmp_path, config)

        assert isinstance(result, Path)
        # Should have a suffix like -1 or -2
        assert result != tmp_path / "Test-Server-starter-20260101-000000"

    def test_fails_after_10_collisions(self, mocker: MockerFixture, tmp_path: Path) -> None:
        """Test that collision handling stops after 10 attempts."""
        config = _basic_config()

        # Mock datetime to return a fixed timestamp
        fixed_timestamp = "20260101-000000"
        mock_datetime = mocker.Mock()
        mock_datetime.now.return_value.strftime.return_value = fixed_timestamp
        mocker.patch(
            "odsbox_pilot.query.script_starter_logic.datetime",
            mock_datetime,
        )

        # Create 11 folders to exceed the retry limit (1-10)
        base_name = "Test-Server-starter-20260101-000000"
        (tmp_path / base_name).mkdir()
        for i in range(1, 11):
            (tmp_path / f"{base_name}-{i}").mkdir()

        result = compute_target_path(tmp_path, config)

        assert isinstance(result, str)  # Error message
        assert "Could not find a free folder name" in result
