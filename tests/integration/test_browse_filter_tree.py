"""Integration tests for odsbox_pilot.browse.filter_tree (requires live ASAM ODS server)."""

from typing import Any

import pytest
from odsbox import ConI

from odsbox_pilot.browse.filter_tree import FilterNode, FilterTree

_DEMO_URL = "https://docker.peak-solution.de:10032/api"
_DEMO_USER = "Demo"
_DEMO_PASS = "mdm"


@pytest.fixture(scope="module")
def con_i() -> Any:
    """Provide a live server connection; skip if unreachable."""
    try:
        with ConI(url=_DEMO_URL, auth=(_DEMO_USER, _DEMO_PASS)) as connection:
            yield connection
    except Exception as exc:
        pytest.skip(f"Server not reachable: {exc}")


@pytest.mark.integration
class TestIntegration:
    """Integration tests that query the live ASAM ODS server."""

    def test_query_project(self, con_i: Any) -> None:
        mc = con_i.mc
        ft = FilterTree(
            mc,
            [
                FilterNode(mc.entity("Project"), {"name": {"$like": "Elec*"}}),
                FilterNode(mc.entity("MeaResult"), {"name": {"$like": "Profile_*"}}),
            ],
        )

        df = ft.query(con_i, "Project")

        assert not df.empty
        assert "ElectricMotorTemperature" in df["name"].values

    def test_follow_structure_level(self, con_i: Any) -> None:
        mc = con_i.mc
        ft = FilterTree(
            mc,
            [
                FilterNode(mc.entity("Project"), {"name": {"$like": "Elec*"}}),
                FilterNode(mc.entity("MeaResult"), {"name": {"$like": "Profile_*"}}),
            ],
        )

        project_df = ft.query(con_i, "Project")
        assert not project_df.empty

        project_ids = project_df["id"].tolist()
        sl_df = ft.follow(con_i, "Project", project_ids, "StructureLevel")

        assert not sl_df.empty
        assert "id" in sl_df.columns
        assert "name" in sl_df.columns

    def test_query_with_test_step(self, con_i: Any) -> None:
        mc = con_i.mc
        ft = FilterTree(
            mc,
            [
                FilterNode(mc.entity("Project"), {"name": {"$like": "Elec*"}}),
                FilterNode(mc.entity("TestStep"), {"name": {"$like": "*"}}),
            ],
        )

        df = ft.query(con_i, "Project")
        assert not df.empty

    def test_query_with_distinct_attribute(self, con_i: Any) -> None:
        mc = con_i.mc
        ft = FilterTree(
            mc,
            [
                FilterNode(mc.entity("Test"), {"name": {"$like": "Campaign*"}}),
            ],
        )

        df = ft.query(con_i, "Test", attributes={"name": {"$distinct": 1}})
        assert not df.empty
        assert "name.$distinct" in df.columns
        assert len(df["name.$distinct"]) >= 7

        df = ft.query(con_i, "TestStep", attributes={"name": {"$distinct": 1}})
        assert not df.empty
        assert "name.$distinct" in df.columns
        assert len(df["name.$distinct"]) > 50

        df = ft.query(con_i, "MeaResult", attributes={"name": {"$distinct": 1}})
        assert not df.empty
        assert "name.$distinct" in df.columns
        assert len(df["name.$distinct"]) > 50

    def test_query_with_distinct_attribute2(self, con_i: Any) -> None:
        mc = con_i.mc
        ft = FilterTree(
            mc,
            [
                FilterNode(mc.entity("Test"), {"name": {"$like": "Campaign_01"}}),
            ],
        )

        df = ft.query(con_i, "Test", attributes={"name": {"$distinct": 1}})
        assert not df.empty
        assert "name.$distinct" in df.columns
        assert len(df["name.$distinct"]) >= 1

        df = ft.query(con_i, "TestStep", attributes={"name": {"$distinct": 1}})
        assert not df.empty
        assert "name.$distinct" in df.columns
        assert len(df["name.$distinct"]) >= 10

        df = ft.query(con_i, "MeaResult", attributes={"name": {"$distinct": 1}})
        assert not df.empty
        assert "name.$distinct" in df.columns
        assert len(df["name.$distinct"]) >= 10

    def test_query_with_distinct_attribute3(self, con_i: Any) -> None:
        mc = con_i.mc
        ft = FilterTree(
            mc,
            [
                FilterNode(mc.entity("Test"), {"name": {"$like": "Campaign_01"}}),
                FilterNode(mc.entity("MeaResult"), {"name": {"$like": "Profile_*"}}),
            ],
        )

        df = ft.query(con_i, "Test", attributes={"name": {"$distinct": 1}})
        assert not df.empty
        assert "name.$distinct" in df.columns
        assert len(df["name.$distinct"]) >= 1

        df = ft.query(con_i, "TestStep", attributes={"name": {"$distinct": 1}})
        assert not df.empty
        assert "name.$distinct" in df.columns
        assert len(df["name.$distinct"]) >= 10

        df = ft.query(con_i, "MeaResult", attributes={"name": {"$distinct": 1}})
        assert not df.empty
        assert "name.$distinct" in df.columns
        assert len(df["name.$distinct"]) >= 10

    def test_query_with_distinct_attribute4(self, con_i: Any) -> None:
        mc = con_i.mc
        ft = FilterTree(
            mc,
            [
                FilterNode(mc.entity("Test"), {"name": {"$like": "Campaign_01"}}),
                FilterNode(mc.entity("MeaResult"), {"name": {"$like": "Profile_2*"}}),
            ],
        )

        df = ft.query(con_i, "Test", attributes={"name": {"$distinct": 1}})
        assert not df.empty
        assert "name.$distinct" in df.columns
        assert len(df["name.$distinct"]) >= 1

        df = ft.query(con_i, "TestStep", attributes={"name": {"$distinct": 1}})
        assert not df.empty
        assert "name.$distinct" in df.columns
        assert len(df["name.$distinct"]) >= 3

        df = ft.query(con_i, "MeaResult", attributes={"name": {"$distinct": 1}})
        assert not df.empty
        assert "name.$distinct" in df.columns
        assert len(df["name.$distinct"]) >= 3

        df = ft.query(
            con_i,
            "MeaResult",
            attributes={"measurement_begin": {"$min": 1, "$max": 1}},
        )
        assert not df.empty
        assert "measurement_begin.$min" in df.columns
        assert "measurement_begin.$max" in df.columns
        assert len(df["measurement_begin.$min"]) == 1
        assert len(df["measurement_begin.$max"]) == 1
