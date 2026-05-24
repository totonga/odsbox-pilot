"""Unit tests for odsbox_pilot.model.model_panel pure helpers (no wx required)."""

from __future__ import annotations

from odsbox.proto import ods

from odsbox_pilot.model.model_panel import _range_str, _rel_range, _rel_type_label


class TestRangeStr:
    def test_unbounded_returns_n(self) -> None:
        assert _range_str(-1) == "n"

    def test_zero(self) -> None:
        assert _range_str(0) == "0"

    def test_one(self) -> None:
        assert _range_str(1) == "1"

    def test_large_value(self) -> None:
        assert _range_str(999) == "999"


class TestRelRange:
    def _make_rel(self, range_max: int, inverse_range_max: int) -> ods.Model.Relation:
        rel = ods.Model.Relation()
        rel.range_max = range_max
        rel.inverse_range_max = inverse_range_max
        return rel

    def test_one_to_one(self) -> None:
        assert _rel_range(self._make_rel(1, 1)) == "1:1"

    def test_one_to_many(self) -> None:
        assert _rel_range(self._make_rel(-1, 1)) == "1:n"

    def test_many_to_many(self) -> None:
        assert _rel_range(self._make_rel(-1, -1)) == "n:n"

    def test_zero_range(self) -> None:
        assert _rel_range(self._make_rel(0, 1)) == "1:0"


class TestRelTypeLabel:
    def _make_rel(self, relationship: int) -> ods.Model.Relation:
        rel = ods.Model.Relation()
        rel.relationship = relationship
        return rel

    def test_rs_father(self) -> None:
        # 0 = RS_FATHER per ods.Model.RelationshipEnum
        rel = self._make_rel(0)
        assert _rel_type_label(rel) == "RS_FATHER"

    def test_rs_child(self) -> None:
        # 1 = RS_CHILD
        rel = self._make_rel(1)
        assert _rel_type_label(rel) == "RS_CHILD"

    def test_rs_info_to(self) -> None:
        # 2 = RS_INFO_TO
        rel = self._make_rel(2)
        assert _rel_type_label(rel) == "RS_INFO_TO"
