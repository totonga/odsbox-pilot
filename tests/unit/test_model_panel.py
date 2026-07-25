"""Unit tests for odsbox_pilot.model.helpers pure functions (no wx required)."""

from __future__ import annotations

import sys
from types import ModuleType
from typing import Any, cast

from odsbox.proto import ods
from pytest_mock import MockerFixture

from odsbox_pilot.model.helpers import _range_str, _rel_range, _rel_type_label


class _FakeWxPanel:
    def __init__(self) -> None:
        self._destroyed = False

    def Destroy(self) -> None:
        self._destroyed = True


def _install_fake_wx(mocker: MockerFixture) -> ModuleType:
    fake_wx: Any = ModuleType("wx")
    fake_wx.Panel = _FakeWxPanel
    fake_wx.Window = object
    fake_wx.CommandEvent = object
    fake_wx.ListEvent = object
    fake_wx.TreeEvent = object
    fake_wx.TreeItemId = lambda: _FakeWxPanel()
    fake_wx.SplitterWindow = object
    fake_wx.CallAfter = lambda *args, **kwargs: None
    fake_wx.CallLater = lambda *args, **kwargs: None
    fake_wx.Colour = lambda *args, **kwargs: None
    fake_wx.TreeCtrl = object
    fake_wx.ListCtrl = object
    fake_wx.SearchCtrl = object
    fake_wx.StaticText = object
    fake_wx.BoxSizer = object
    fake_wx.Panel = _FakeWxPanel
    fake_wx.EVT_TREE_SEL_CHANGED = object()
    fake_wx.EVT_TREE_ITEM_EXPANDING = object()
    fake_wx.EVT_LIST_ITEM_ACTIVATED = object()
    fake_wx.EVT_TEXT = object()
    fake_wx.EVT_SEARCHCTRL_CANCEL_BTN = object()
    mocker.patch.dict(sys.modules, {"wx": fake_wx})
    return cast(ModuleType, fake_wx)


def test_model_panel_ignores_stale_search_callbacks_after_destroy(mocker: MockerFixture) -> None:
    _install_fake_wx(mocker)
    import importlib

    import odsbox_pilot.model.model_panel as model_panel_module

    importlib.reload(model_panel_module)
    panel = cast(Any, model_panel_module.ModelPanel.__new__(model_panel_module.ModelPanel))
    panel._destroyed = True
    panel._search_available = True
    panel._search_generation = 1
    panel._result_matches = []
    panel._search_ctrl = mocker.Mock()
    panel._search_ctrl.GetValue.return_value = "query"
    panel._results_list = mocker.Mock()
    panel._left_panel = mocker.Mock()
    panel._tree = mocker.Mock()

    panel._on_search_index_ready()
    panel._apply_search_unavailable("hint")
    panel._apply_search_results([], 1)

    panel._search_ctrl.SetHint.assert_not_called()
    panel._search_ctrl.Disable.assert_not_called()
    panel._results_list.DeleteAllItems.assert_not_called()


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
        assert _rel_range(self._make_rel(-1, -1)) == "n:m"

    def test_zero_range(self) -> None:
        assert _rel_range(self._make_rel(0, 1)) == "1:0"


class TestRelTypeLabel:
    def _make_rel(self, relationship: int) -> ods.Model.Relation:
        rel = ods.Model.Relation()
        rel.relationship = relationship  # type: ignore[assignment]
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
