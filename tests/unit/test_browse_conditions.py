"""Unit tests for BrowsePanel's persistence helpers (_load_conditions, _save_conditions).

These tests exercise the module-level functions that have no wx dependency,
so they run without a display.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

from odsbox_pilot.browse.browse_panel import (
    _build_filter_nodes,
    _load_conditions,
    _save_conditions,
)

# ---------------------------------------------------------------------------
# _load_conditions
# ---------------------------------------------------------------------------


class TestLoadConditions:
    def test_returns_empty_list_when_file_missing(self, tmp_path: Path) -> None:
        with patch(
            "odsbox_pilot.browse.browse_panel._BROWSE_CONDITIONS_FILE",
            tmp_path / "nonexistent.json",
        ):
            result = _load_conditions()
        assert result == []

    def test_returns_empty_list_on_corrupt_json(self, tmp_path: Path) -> None:
        bad_file = tmp_path / "bad.json"
        bad_file.write_text("not valid json", encoding="utf-8")
        with patch("odsbox_pilot.browse.browse_panel._BROWSE_CONDITIONS_FILE", bad_file):
            result = _load_conditions()
        assert result == []

    def test_returns_empty_list_when_top_level_not_a_list(self, tmp_path: Path) -> None:
        obj_file = tmp_path / "obj.json"
        obj_file.write_text(json.dumps({"entity": "Project"}), encoding="utf-8")
        with patch("odsbox_pilot.browse.browse_panel._BROWSE_CONDITIONS_FILE", obj_file):
            result = _load_conditions()
        assert result == []

    def test_returns_conditions_from_valid_file(self, tmp_path: Path) -> None:
        conditions: list[dict[str, Any]] = [
            {"entity": "Project", "attr": "name", "op": "$like", "val": "Elec*"},
            {"entity": "MeaResult", "attr": "name", "op": "$eq", "val": "Profile_1"},
        ]
        valid_file = tmp_path / "conditions.json"
        valid_file.write_text(json.dumps(conditions), encoding="utf-8")
        with patch("odsbox_pilot.browse.browse_panel._BROWSE_CONDITIONS_FILE", valid_file):
            result = _load_conditions()
        assert result == conditions


# ---------------------------------------------------------------------------
# _save_conditions
# ---------------------------------------------------------------------------


class TestSaveConditions:
    def test_creates_config_dir_if_missing(self, tmp_path: Path) -> None:
        nested = tmp_path / "config" / "subdir"
        target = nested / "browse_conditions.json"
        with (
            patch("odsbox_pilot.browse.browse_panel.CONFIG_DIR", nested),
            patch("odsbox_pilot.browse.browse_panel._BROWSE_CONDITIONS_FILE", target),
        ):
            _save_conditions([])
        assert target.exists()

    def test_save_and_load_roundtrip(self, tmp_path: Path) -> None:
        conditions: list[dict[str, Any]] = [
            {"entity": "Test", "attr": "name", "op": "$like", "val": "Campaign*"},
        ]
        target = tmp_path / "browse_conditions.json"
        with (
            patch("odsbox_pilot.browse.browse_panel.CONFIG_DIR", tmp_path),
            patch("odsbox_pilot.browse.browse_panel._BROWSE_CONDITIONS_FILE", target),
        ):
            _save_conditions(conditions)
            result = _load_conditions()
        assert result == conditions

    def test_overwrites_existing_file(self, tmp_path: Path) -> None:
        target = tmp_path / "browse_conditions.json"
        target.write_text(json.dumps([{"entity": "old"}]), encoding="utf-8")
        new_conditions: list[dict[str, Any]] = [
            {"entity": "new", "attr": "x", "op": "$eq", "val": "y"}
        ]
        with (
            patch("odsbox_pilot.browse.browse_panel.CONFIG_DIR", tmp_path),
            patch("odsbox_pilot.browse.browse_panel._BROWSE_CONDITIONS_FILE", target),
        ):
            _save_conditions(new_conditions)
            result = _load_conditions()
        assert result == new_conditions

    def test_silently_ignores_write_error(self, tmp_path: Path) -> None:
        # Point at a non-writable path.  The function must not raise.
        ro_dir = tmp_path / "readonly"
        ro_dir.mkdir()
        ro_dir.chmod(0o444)
        target = ro_dir / "browse_conditions.json"
        try:
            with (
                patch("odsbox_pilot.browse.browse_panel.CONFIG_DIR", ro_dir),
                patch("odsbox_pilot.browse.browse_panel._BROWSE_CONDITIONS_FILE", target),
            ):
                _save_conditions([{"entity": "X"}])  # must not raise
        finally:
            ro_dir.chmod(0o755)  # restore for cleanup


# ---------------------------------------------------------------------------
# _build_filter_nodes (logic only — no wx required)
# ---------------------------------------------------------------------------


class TestRebuildNodes:
    """Test _build_filter_nodes() using a minimal mock mc."""

    def _make_mc(self, entities: dict[str, list[str]]) -> Any:
        """Build a minimal mock ModelCache with the given entities and attribute names."""
        mc = MagicMock()

        def _entity(name: str) -> Any:
            if name not in entities:
                raise ValueError(f"No entity named {name!r}")
            ent = MagicMock()
            ent.name = name
            ent.attributes = {attr: MagicMock() for attr in entities[name]}
            ent.relations = {}
            return ent

        mc.entity.side_effect = _entity

        model = MagicMock()
        model.entities = {name: MagicMock() for name in entities}
        mc.model.return_value = model

        return mc

    def test_valid_conditions_build_nodes(self) -> None:
        from odsbox_pilot.browse.filter_tree import FilterNode

        mc = self._make_mc({"Project": ["name", "id"]})
        conditions: list[dict[str, Any]] = [
            {"entity": "Project", "attr": "name", "op": "$like", "val": "Elec*"}
        ]

        nodes, failed = _build_filter_nodes(mc, conditions)

        assert failed == []
        assert len(nodes) == 1
        assert isinstance(nodes[0], FilterNode)

    def test_unknown_entity_is_skipped(self) -> None:
        mc = self._make_mc({"Project": ["name"]})
        conditions: list[dict[str, Any]] = [
            {"entity": "NoSuchEntity", "attr": "name", "op": "$eq", "val": "x"}
        ]

        nodes, failed = _build_filter_nodes(mc, conditions)

        assert failed == ["NoSuchEntity"]
        assert nodes == []

    def test_numeric_value_is_coerced(self) -> None:
        from odsbox_pilot.browse.filter_tree import FilterNode

        mc = self._make_mc({"Test": ["id"]})
        conditions: list[dict[str, Any]] = [
            {"entity": "Test", "attr": "id", "op": "$eq", "val": "42"}
        ]

        nodes, failed = _build_filter_nodes(mc, conditions)

        assert failed == []
        assert isinstance(nodes[0], FilterNode)
        assert nodes[0].condition["id"]["$eq"] == 42  # coerced int
