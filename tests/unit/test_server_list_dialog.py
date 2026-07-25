"""Unit tests for the server-list dialog toolbar behavior."""

from __future__ import annotations

import importlib
import sys
from types import ModuleType
from typing import Any, cast

from pytest_mock import MockerFixture


class _FakeWxDialog:
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self._size = None

    def SetSize(self, size: Any) -> None:
        self._size = size

    def FromDIP(self, size: Any) -> Any:
        return size

    def Centre(self) -> None:
        return None


class _FakeWxPanel:
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.sizer = None

    def SetSizer(self, sizer: Any) -> None:
        self.sizer = sizer


class _FakeWxListCtrl:
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.columns: list[tuple[str, int]] = []

    def AppendColumn(self, name: str, width: int = -1) -> None:
        self.columns.append((name, width))

    def Bind(self, *args: Any, **kwargs: Any) -> None:
        return None

    def DeleteAllItems(self) -> None:
        return None

    def GetItemCount(self) -> int:
        return 0

    def InsertItem(self, index: int, text: str) -> int:
        return index

    def SetItem(self, index: int, column: int, value: str) -> None:
        return None

    def SetItemData(self, index: int, data: Any) -> None:
        return None

    def GetFirstSelected(self) -> int:
        return -1


class _FakeWxButton:
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.label = kwargs.get("label", "")
        self.enabled = True

    def Disable(self) -> None:
        self.enabled = False

    def Enable(self, enabled: bool = True) -> None:
        self.enabled = enabled

    def Bind(self, *args: Any, **kwargs: Any) -> None:
        return None

    def SetDefault(self) -> None:
        return None

    def SetToolTip(self, text: str) -> None:
        return None


class _TrackingBoxSizer:
    def __init__(self, orientation: int) -> None:
        self.orientation = orientation
        self.added: list[tuple[Any, dict[str, Any]]] = []

    def Add(self, item: Any, **kwargs: Any) -> None:
        self.added.append((item, kwargs))

    def AddStretchSpacer(self, *args: Any, **kwargs: Any) -> None:
        return None


def _install_fake_wx(mocker: MockerFixture) -> ModuleType:
    fake_wx: Any = ModuleType("wx")
    fake_wx.Dialog = _FakeWxDialog
    fake_wx.Panel = _FakeWxPanel
    fake_wx.ListCtrl = _FakeWxListCtrl
    fake_wx.Button = _FakeWxButton
    fake_wx.BoxSizer = _TrackingBoxSizer
    fake_wx.Size = lambda width, height: (width, height)
    fake_wx.Window = object
    fake_wx.Event = object
    fake_wx.KeyEvent = object
    fake_wx.ContextMenuEvent = object
    fake_wx.CommandEvent = object
    fake_wx.OK = 1
    fake_wx.ICON_ERROR = 2
    fake_wx.ICON_WARNING = 4
    fake_wx.ID_OK = 5100
    fake_wx.ID_CANCEL = 5101
    fake_wx.ID_ANY = -1
    fake_wx.VERTICAL = 0
    fake_wx.HORIZONTAL = 1
    fake_wx.EXPAND = 1
    fake_wx.ALL = 2
    fake_wx.LEFT = 4
    fake_wx.RIGHT = 8
    fake_wx.TOP = 16
    fake_wx.BOTTOM = 32
    fake_wx.LC_REPORT = 1
    fake_wx.LC_SINGLE_SEL = 2
    fake_wx.BORDER_SUNKEN = 4
    fake_wx.DEFAULT_DIALOG_STYLE = 0
    fake_wx.RESIZE_BORDER = 0
    fake_wx.EVT_LIST_ITEM_ACTIVATED = object()
    fake_wx.EVT_LIST_ITEM_SELECTED = object()
    fake_wx.EVT_LIST_ITEM_DESELECTED = object()
    fake_wx.EVT_CONTEXT_MENU = object()
    fake_wx.EVT_BUTTON = object()
    fake_wx.EVT_KEY_DOWN = object()
    fake_wx.EVT_MENU = object()
    fake_wx.WXK_DELETE = 127
    fake_wx.FD_OPEN = 1
    fake_wx.FD_SAVE = 2
    fake_wx.FD_FILE_MUST_EXIST = 4
    fake_wx.FD_OVERWRITE_PROMPT = 8
    fake_wx.MessageBox = mocker.Mock()
    fake_wx.BeginBusyCursor = mocker.Mock()
    fake_wx.EndBusyCursor = mocker.Mock()
    fake_wx.FileDialog = mocker.MagicMock()
    fake_wx.Menu = mocker.MagicMock()
    mocker.patch.dict(sys.modules, {"wx": fake_wx})
    return cast(ModuleType, fake_wx)


def _load_server_list_dialog_module(mocker: MockerFixture) -> ModuleType:
    _install_fake_wx(mocker)
    mocker.patch("odsbox_pilot.connection.server_list_dialog.styles.apply_scaled_app_font")
    import odsbox_pilot.connection.server_list_dialog as server_list_dialog_module

    return importlib.reload(server_list_dialog_module)


def test_server_list_toolbar_omits_edit_copy_delete_buttons(mocker: MockerFixture) -> None:
    module = _load_server_list_dialog_module(mocker)

    manager = mocker.Mock()
    manager.configs = []

    dialog = module.ServerListDialog.__new__(module.ServerListDialog)
    dialog._manager = manager
    dialog._selected_config = None
    dialog._connected_con_i = None

    tracked_sizers: list[_TrackingBoxSizer] = []

    original_box_sizer = module.wx.BoxSizer

    class TrackingBoxSizer(original_box_sizer):
        def __init__(self, orientation: int) -> None:
            super().__init__(orientation)
            tracked_sizers.append(self)

    mocker.patch("odsbox_pilot.connection.server_list_dialog.wx.BoxSizer", TrackingBoxSizer)

    dialog._build_ui()

    button_labels = [
        widget.label
        for sizer in tracked_sizers
        if isinstance(sizer, TrackingBoxSizer)
        for widget, _ in sizer.added
        if isinstance(widget, module.wx.Button)
    ]

    assert button_labels.count("New…") == 1
    assert button_labels.count("Connect") == 1
    assert button_labels.count("📄") == 1
    assert "Edit…" not in button_labels
    assert "Copy" not in button_labels
    assert "Delete" not in button_labels
    assert not hasattr(dialog, "_btn_edit")
    assert not hasattr(dialog, "_btn_copy")
    assert not hasattr(dialog, "_btn_delete")
