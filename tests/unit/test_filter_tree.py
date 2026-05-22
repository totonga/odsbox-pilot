"""Unit tests for odsbox_pilot.browse.filter_tree (no live server required)."""

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pandas as pd
import pytest
from odsbox.model_cache import ModelCache

from odsbox_pilot.browse.filter_tree import FilterNode, FilterTree


def _load_model_cache() -> ModelCache:
    from google.protobuf.json_format import ParseDict
    from odsbox.proto import ods

    file_path = Path(__file__).parent.parent / "data" / "mdm_nvh_model.json"
    with open(file_path, encoding="utf-8") as f:
        model = ods.Model()
        ParseDict(json.load(f), model)
        return ModelCache(model)


# ---------------------------------------------------------------------------
# Shared fixture
# ---------------------------------------------------------------------------


@pytest.fixture()
def mc() -> ModelCache:
    """Load the local NVH model for offline testing (shared by all unit-test classes)."""
    return _load_model_cache()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestFindPath:
    """Tests for the Dijkstra path-finding logic using a local model.

    Note: some tests call the private ``_find_path()`` directly and some use
    the public ``find_path()`` — intentionally, because they exercise different
    error paths.  ``_find_path('X', 'nonexistent')`` raises ``ValueError: No
    path from...`` (entity not in graph), whereas ``find_path('X',
    'nonexistent')`` raises ``ValueError: No entity named...`` (raised by
    ``_resolve_entity`` before graph traversal begins).
    """

    def test_project_to_mea_result(self, mc: ModelCache) -> None:
        ft = FilterTree(mc)
        path = ft._find_path("Project", "MeaResult")
        assert path == ["StructureLevel", "Tests", "TestSteps", "MeaResults"]

    def test_project_to_vehicle(self, mc: ModelCache) -> None:
        ft = FilterTree(mc)
        path = ft._find_path("Project", "vehicle")
        assert path[-1] == "vehicle"
        assert path[:6] == [
            "StructureLevel",
            "Tests",
            "TestSteps",
            "MeaResults",
            "UnitUnderTest",
            "vehicle",
        ]

    def test_same_entity(self, mc: ModelCache) -> None:
        ft = FilterTree(mc)
        assert ft._find_path("Project", "Project") == []

    def test_unreachable_raises(self, mc: ModelCache) -> None:
        ft = FilterTree(mc)
        with pytest.raises(ValueError, match="No path"):
            ft._find_path("Project", "nonexistent_entity_xyz")

    def test_find_path_with_entity_names(self, mc: ModelCache) -> None:
        ft = FilterTree(mc)
        path = ft.find_path("Project", "MeaResult")
        assert path == ["StructureLevel", "Tests", "TestSteps", "MeaResults"]

    def test_find_path_with_entity_objects(self, mc: ModelCache) -> None:
        ft = FilterTree(mc)
        source = mc.entity("Project")
        target = mc.entity("MeaResult")
        path = ft.find_path(source, target)
        assert path == ["StructureLevel", "Tests", "TestSteps", "MeaResults"]

    def test_find_path_mixed_entity_types(self, mc: ModelCache) -> None:
        ft = FilterTree(mc)
        target_obj = mc.entity("MeaResult")
        path = ft.find_path("Project", target_obj)
        assert path == ["StructureLevel", "Tests", "TestSteps", "MeaResults"]

        source_obj = mc.entity("Project")
        path = ft.find_path(source_obj, "MeaResult")
        assert path == ["StructureLevel", "Tests", "TestSteps", "MeaResults"]

    def test_find_path_same_entity(self, mc: ModelCache) -> None:
        ft = FilterTree(mc)
        path = ft.find_path("Project", "Project")
        assert path == []

    def test_find_path_unreachable_raises(self, mc: ModelCache) -> None:
        ft = FilterTree(mc)
        with pytest.raises(ValueError, match="No entity named"):
            ft.find_path("Project", "nonexistent_entity_xyz")


class TestGenerateQuery:
    """Tests for generate_query using a local model (no server)."""

    def test_project_and_mea_result(self, mc: ModelCache) -> None:
        node1 = FilterNode(
            entity=mc.entity("Project"), condition={"name": {"$like": "Elec*"}}
        )
        node2 = FilterNode(
            entity=mc.entity("MeaResult"), condition={"name": {"$like": "Profile_*"}}
        )
        ft = FilterTree(mc, [node1, node2])

        query = ft.generate_query("Project")

        assert "Project" in query
        project_conds = query["Project"]
        assert project_conds["name"] == {"$like": "Elec*"}
        assert "StructureLevel.Tests.TestSteps.MeaResults" in project_conds
        assert project_conds["StructureLevel.Tests.TestSteps.MeaResults"] == {
            "name": {"$like": "Profile_*"}
        }
        assert query["$attributes"] == {"id": 1, "name": 1}
        assert query["$groupby"] == {"id": 1, "name": 1}

    def test_with_vehicle(self, mc: ModelCache) -> None:
        node1 = FilterNode(
            entity=mc.entity("Project"), condition={"name": {"$like": "Elec*"}}
        )
        node2 = FilterNode(
            entity=mc.entity("MeaResult"), condition={"name": {"$like": "Profile_*"}}
        )
        node3 = FilterNode(
            entity=mc.entity("vehicle"), condition={"name": {"$like": "*"}}
        )
        ft = FilterTree(mc, [node1, node2, node3])

        query = ft.generate_query("Project")

        project_conds = query["Project"]
        assert project_conds["name"] == {"$like": "Elec*"}
        assert "StructureLevel.Tests.TestSteps.MeaResults" in project_conds
        vehicle_keys = [k for k in project_conds if k.endswith("vehicle")]
        assert len(vehicle_keys) == 1
        assert project_conds[vehicle_keys[0]] == {"name": {"$like": "*"}}

    def test_custom_attributes(self, mc: ModelCache) -> None:
        node = FilterNode(
            entity=mc.entity("Project"), condition={"name": {"$like": "*"}}
        )
        ft = FilterTree(mc, [node])

        attrs = {"id": 1, "name": 1, "Description": 1}
        query = ft.generate_query("Project", attributes=attrs)

        assert query["$attributes"] == attrs
        assert "$groupby" not in query

    def test_no_conditions(self, mc: ModelCache) -> None:
        ft = FilterTree(mc)
        query = ft.generate_query("Project")
        assert "Project" in query
        assert query["Project"] == {}
        assert "$groupby" not in query

    def test_add_node_fluent(self, mc: ModelCache) -> None:
        ft = FilterTree(mc)
        result = ft.add_node(
            FilterNode(entity=mc.entity("Project"), condition={"name": {"$like": "X*"}})
        )
        assert result is ft
        query = ft.generate_query("Project")
        assert query["Project"]["name"] == {"$like": "X*"}

    def test_nm_relation_generates_groupby(self, mc: ModelCache) -> None:
        node = FilterNode(mc.entity("Role"), {"name": {"$eq": "admin"}})
        ft = FilterTree(mc, [node])

        query = ft.generate_query("User")

        assert "User" in query
        assert "users2groups.id" in query["User"]
        assert query["User"]["users2groups.id"] == {"name": {"$eq": "admin"}}
        assert "$groupby" in query

    def test_id_bound_entity_suppresses_deeper_conditions(self, mc: ModelCache) -> None:
        ft = FilterTree(
            mc,
            [
                FilterNode(mc.entity("Test"), {"id": 24}),
                FilterNode(mc.entity("StructureLevel"), {"name": {"$like": "Level*"}}),
            ],
        )
        query = ft.generate_query("MeaResult")
        conds = query["MeaResult"]

        test_keys = [k for k in conds if "Test" in k]
        assert any(k.endswith("Test") or k == "TestStep.Test" for k in test_keys)
        sl_keys = [k for k in conds if "StructureLevel" in k]
        assert len(sl_keys) == 0
        assert "$groupby" not in query


class TestRelationWeight:
    """Verify the weight ordering: RS_CHILD < base_name < app-only."""

    def test_child_relation_is_cheapest(self, mc: ModelCache) -> None:
        rel = mc.relation("Project", "StructureLevel")
        assert FilterTree._relation_weight(rel) == 1

    def test_base_name_relation_is_medium(self, mc: ModelCache) -> None:
        rel = mc.relation("MeaResult", "UnitUnderTest")
        assert FilterTree._relation_weight(rel) == 3

    def test_app_only_relation_is_heaviest(self, mc: ModelCache) -> None:
        rel = mc.relation("UnitUnderTest", "TestSteps")
        assert FilterTree._relation_weight(rel) == 13


class TestFindDirectRelation:
    """Tests for _find_direct_relation() using the local model."""

    def test_returns_relation_for_connected_entities(self, mc: ModelCache) -> None:
        ft = FilterTree(mc)
        rel = ft._find_direct_relation("Project", "StructureLevel")
        assert rel is not None
        assert rel.entity_name == "StructureLevel"

    def test_returns_none_for_unconnected_entities(self, mc: ModelCache) -> None:
        ft = FilterTree(mc)
        rel = ft._find_direct_relation("Project", "MeaResult")
        assert rel is None

    def test_returned_relation_has_correct_name(self, mc: ModelCache) -> None:
        ft = FilterTree(mc)
        rel = ft._find_direct_relation("Project", "StructureLevel")
        assert rel is not None
        assert rel.name == "StructureLevel"


class TestPathNeedsGroupby:
    """Tests for _path_needs_groupby() using the local model."""

    def test_rs_child_relation_needs_groupby(self, mc: ModelCache) -> None:
        ft = FilterTree(mc)
        assert ft._path_needs_groupby("Project", ["StructureLevel"]) is True

    def test_non_child_relation_no_groupby(self, mc: ModelCache) -> None:
        ft = FilterTree(mc)
        assert ft._path_needs_groupby("MeaResult", ["UnitUnderTest"]) is False

    def test_unknown_relation_name_assumes_worst_case(self, mc: ModelCache) -> None:
        ft = FilterTree(mc)
        assert ft._path_needs_groupby("Project", ["nonexistent_relation_xyz"]) is True

    def test_nm_relation_needs_groupby(self, mc: ModelCache) -> None:
        ft = FilterTree(mc)
        assert ft._path_needs_groupby("User", ["users2groups"]) is True

    def test_info_from_relation_needs_groupby(self, mc: ModelCache) -> None:
        ft = FilterTree(mc)
        assert ft._path_needs_groupby("User", ["Tests"]) is True


class TestFollow:
    """Offline unit tests for follow() using a mock ODS connection."""

    def _mock_con(self) -> MagicMock:
        mock = MagicMock()
        mock.query.return_value = pd.DataFrame({"id": [1], "name": ["test"]})
        return mock

    def test_single_id_uses_bare_value(self, mc: ModelCache) -> None:
        ft = FilterTree(mc)
        mock_con = self._mock_con()
        ft.follow(mock_con, "Project", [42], "StructureLevel")

        sent_query = mock_con.query.call_args[0][0]
        sl_conds = sent_query["StructureLevel"]
        assert 42 in sl_conds.values()

    def test_multiple_ids_uses_in_operator(self, mc: ModelCache) -> None:
        ft = FilterTree(mc)
        mock_con = self._mock_con()
        ft.follow(mock_con, "Project", [42, 43, 44], "StructureLevel")

        sent_query = mock_con.query.call_args[0][0]
        sl_conds = sent_query["StructureLevel"]
        assert {"$in": [42, 43, 44]} in sl_conds.values()

    def test_no_direct_relation_raises(self, mc: ModelCache) -> None:
        ft = FilterTree(mc)
        mock_con = self._mock_con()
        with pytest.raises(ValueError, match="No direct relation"):
            ft.follow(mock_con, "Project", [1], "MeaResult")

    def test_target_node_condition_is_included(self, mc: ModelCache) -> None:
        ft = FilterTree(
            mc,
            [FilterNode(mc.entity("StructureLevel"), {"name": {"$like": "Level*"}})],
        )
        mock_con = self._mock_con()
        ft.follow(mock_con, "Project", [42], "StructureLevel")

        sent_query = mock_con.query.call_args[0][0]
        sl_conds = sent_query["StructureLevel"]
        assert sl_conds["name"] == {"$like": "Level*"}

    def test_third_entity_node_is_included(self, mc: ModelCache) -> None:
        ft = FilterTree(
            mc,
            [FilterNode(mc.entity("MeaResult"), {"name": {"$like": "Profile_*"}})],
        )
        mock_con = self._mock_con()
        ft.follow(mock_con, "Project", [42], "StructureLevel")

        sent_query = mock_con.query.call_args[0][0]
        sl_conds = sent_query["StructureLevel"]
        mea_keys = [k for k in sl_conds if "MeaResults" in k]
        assert len(mea_keys) == 1
        assert sl_conds[mea_keys[0]] == {"name": {"$like": "Profile_*"}}

    def test_nm_follow_uses_dot_id_suffix(self, mc: ModelCache) -> None:
        ft = FilterTree(mc)
        mock_con = self._mock_con()
        ft.follow(mock_con, "User", [42], "Role")

        sent_query = mock_con.query.call_args[0][0]
        role_conds = sent_query["Role"]
        assert "groups2users.id" in role_conds
        assert role_conds["groups2users.id"] == 42

    def test_follow_skips_conditions_through_bound_parent(self, mc: ModelCache) -> None:
        ft = FilterTree(
            mc,
            [FilterNode(mc.entity("Project"), {"name": {"$like": "Elec*"}})],
        )
        mock_con = self._mock_con()
        ft.follow(mock_con, "Test", [42], "TestStep")

        sent_query = mock_con.query.call_args[0][0]
        ts_conds = sent_query["TestStep"]
        project_keys = [k for k in ts_conds if "Project" in k]
        assert len(project_keys) == 0


class TestDistinctAndMinMax:
    """Offline unit tests for the distinct() and min_max() convenience methods."""

    def _mock_distinct(self, values: list) -> MagicMock:
        mock = MagicMock()
        mock.query.return_value = pd.DataFrame({"name.$distinct": values})
        return mock

    def _mock_minmax(self, min_val: Any, max_val: Any) -> MagicMock:
        mock = MagicMock()
        mock.query.return_value = pd.DataFrame(
            {"measurement_begin.$min": [min_val], "measurement_begin.$max": [max_val]}
        )
        return mock

    def test_distinct_returns_list(self, mc: ModelCache) -> None:
        ft = FilterTree(mc)
        mock_con = self._mock_distinct(["Campaign_01", "Campaign_02"])
        result = ft.distinct(mock_con, "Test", "name")
        assert result == ["Campaign_01", "Campaign_02"]

    def test_distinct_uses_distinct_attribute(self, mc: ModelCache) -> None:
        ft = FilterTree(mc)
        mock_con = self._mock_distinct([])
        ft.distinct(mock_con, "Test", "name")
        sent_query = mock_con.query.call_args[0][0]
        assert sent_query["$attributes"] == {"name": {"$distinct": 1}}

    def test_distinct_empty_df_returns_empty_list(self, mc: ModelCache) -> None:
        ft = FilterTree(mc)
        mock = MagicMock()
        mock.query.return_value = pd.DataFrame()
        assert ft.distinct(mock, "Test", "name") == []

    def test_distinct_missing_column_raises(self, mc: ModelCache) -> None:
        ft = FilterTree(mc)
        mock = MagicMock()
        mock.query.return_value = pd.DataFrame({"other_col": [1]})
        with pytest.raises(ValueError, match=r"\$distinct"):
            ft.distinct(mock, "Test", "name")

    def test_distinct_no_groupby_with_child_join(self, mc: ModelCache) -> None:
        ft = FilterTree(
            mc,
            [FilterNode(mc.entity("MeaResult"), {"name": {"$like": "Profile_*"}})],
        )
        mock_con = self._mock_distinct([])
        ft.distinct(mock_con, "Test", "name")
        sent_query = mock_con.query.call_args[0][0]
        assert "$groupby" not in sent_query

    def test_min_max_returns_tuple(self, mc: ModelCache) -> None:
        ft = FilterTree(mc)
        mock_con = self._mock_minmax("2024-01-01", "2024-12-31")
        mn, mx = ft.min_max(mock_con, "MeaResult", "measurement_begin")
        assert mn == "2024-01-01"
        assert mx == "2024-12-31"

    def test_min_max_uses_min_max_attributes(self, mc: ModelCache) -> None:
        ft = FilterTree(mc)
        mock_con = self._mock_minmax(0, 100)
        ft.min_max(mock_con, "MeaResult", "measurement_begin")
        sent_query = mock_con.query.call_args[0][0]
        assert sent_query["$attributes"] == {"measurement_begin": {"$min": 1, "$max": 1}}

    def test_min_max_empty_df_returns_none_none(self, mc: ModelCache) -> None:
        ft = FilterTree(mc)
        mock = MagicMock()
        mock.query.return_value = pd.DataFrame()
        mn, mx = ft.min_max(mock, "MeaResult", "measurement_begin")
        assert mn is None
        assert mx is None

    def test_min_max_missing_columns_returns_none_none(self, mc: ModelCache) -> None:
        ft = FilterTree(mc)
        mock = MagicMock()
        mock.query.return_value = pd.DataFrame({"other": [1]})
        mn, mx = ft.min_max(mock, "MeaResult", "measurement_begin")
        assert mn is None
        assert mx is None

    def test_min_max_no_groupby_with_child_join(self, mc: ModelCache) -> None:
        ft = FilterTree(
            mc,
            [FilterNode(mc.entity("Test"), {"name": {"$like": "Campaign*"}})],
        )
        mock_con = self._mock_minmax(0, 100)
        ft.min_max(mock_con, "MeaResult", "measurement_begin")
        sent_query = mock_con.query.call_args[0][0]
        assert "$groupby" not in sent_query
