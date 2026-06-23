"""ServerListDialog: shows saved ODS servers; entry point to connect."""

from __future__ import annotations

import contextlib
import uuid
from dataclasses import replace
from pathlib import Path

import wx  # type: ignore[import-untyped]

from odsbox_pilot.connection.manager import ServerConfigManager
from odsbox_pilot.models import AuthType, ServerConfig


class ServerListDialog(wx.Dialog):
    """Main entry dialog listing configured ODS servers."""

    def __init__(self, parent: wx.Window | None, manager: ServerConfigManager) -> None:
        super().__init__(
            parent,
            title="ODS Pilot — Servers",
            size=(600, 380),
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
        )
        self._manager = manager
        self._selected_config: ServerConfig | None = None
        self._connected_con_i = None

        self._build_ui()
        self._refresh_list()
        self.Centre()

    # ------------------------------------------------------------------
    # Result
    # ------------------------------------------------------------------

    @property
    def selected_config(self) -> ServerConfig | None:
        return self._selected_config

    @property
    def connected_con_i(self):  # type: ignore[return]
        return self._connected_con_i

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        panel = wx.Panel(self)
        vbox = wx.BoxSizer(wx.VERTICAL)

        # --- List ---
        self._list = wx.ListCtrl(
            panel,
            style=wx.LC_REPORT | wx.LC_SINGLE_SEL | wx.BORDER_SUNKEN,
        )
        self._list.AppendColumn("Name", width=180)
        self._list.AppendColumn("URL", width=260)
        self._list.AppendColumn("Auth", width=80)
        self._list.Bind(wx.EVT_LIST_ITEM_ACTIVATED, self._on_connect)
        self._list.Bind(wx.EVT_LIST_ITEM_SELECTED, self._on_selection_changed)
        self._list.Bind(wx.EVT_LIST_ITEM_DESELECTED, self._on_selection_changed)
        vbox.Add(self._list, proportion=1, flag=wx.EXPAND | wx.ALL, border=8)

        # --- Buttons ---
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)

        self._btn_new = wx.Button(panel, label="New…")
        self._btn_edit = wx.Button(panel, label="Edit…")
        self._btn_copy = wx.Button(panel, label="Copy")
        self._btn_delete = wx.Button(panel, label="Delete")
        self._btn_connect = wx.Button(panel, wx.ID_OK, label="Connect")
        btn_close = wx.Button(panel, wx.ID_CANCEL, label="Close")
        self._btn_open_atfx_file = wx.Button(panel, label="📄", size=wx.Size(24, -1))
        self._btn_open_atfx_file.SetToolTip("Open ATFX file")

        self._btn_edit.Disable()
        self._btn_copy.Disable()
        self._btn_delete.Disable()
        self._btn_connect.Disable()
        self._btn_connect.SetDefault()

        btn_sizer.Add(self._btn_new, flag=wx.RIGHT, border=4)
        btn_sizer.Add(self._btn_edit, flag=wx.RIGHT, border=4)
        btn_sizer.Add(self._btn_copy, flag=wx.RIGHT, border=4)
        btn_sizer.Add(self._btn_delete)
        btn_sizer.AddStretchSpacer()
        btn_sizer.Add(btn_close, flag=wx.RIGHT, border=4)

        right_col = wx.BoxSizer(wx.HORIZONTAL)
        right_col.Add(self._btn_connect, flag=wx.RIGHT, border=4)
        right_col.Add(self._btn_open_atfx_file)
        btn_sizer.Add(right_col)

        vbox.Add(btn_sizer, flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, border=8)

        panel.SetSizer(vbox)

        # Bind events
        self._btn_new.Bind(wx.EVT_BUTTON, self._on_new)
        self._btn_edit.Bind(wx.EVT_BUTTON, self._on_edit)
        self._btn_open_atfx_file.Bind(wx.EVT_BUTTON, self._on_open_atfx_file)
        self._btn_copy.Bind(wx.EVT_BUTTON, self._on_copy)
        self._btn_delete.Bind(wx.EVT_BUTTON, self._on_delete)
        self._btn_connect.Bind(wx.EVT_BUTTON, self._on_connect)

        # Keyboard shortcut: Delete key on list
        self._list.Bind(wx.EVT_KEY_DOWN, self._on_list_key)

    # ------------------------------------------------------------------
    # List helpers
    # ------------------------------------------------------------------

    def _refresh_list(self) -> None:
        self._list.DeleteAllItems()
        sorted_configs = sorted(self._manager.configs, key=lambda c: c.name.lower())
        for cfg in sorted_configs:
            idx = self._list.InsertItem(self._list.GetItemCount(), cfg.name)
            self._list.SetItem(idx, 1, cfg.url)
            self._list.SetItem(idx, 2, cfg.auth_type.value.upper())
            self._list.SetItemData(idx, hash(cfg.id))  # tag for id retrieval
        self._update_buttons()

    def _selected_id(self) -> str | None:
        idx = self._list.GetFirstSelected()
        if idx == -1:
            return None
        sorted_configs = sorted(self._manager.configs, key=lambda c: c.name.lower())
        return sorted_configs[idx].id

    def _update_buttons(self) -> None:
        has_selection = self._list.GetFirstSelected() != -1
        self._btn_edit.Enable(has_selection)
        self._btn_copy.Enable(has_selection)
        self._btn_delete.Enable(has_selection)
        self._btn_connect.Enable(has_selection)

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def _on_selection_changed(self, _event: wx.Event) -> None:
        self._update_buttons()

    def _on_list_key(self, event: wx.KeyEvent) -> None:
        if event.GetKeyCode() == wx.WXK_DELETE:
            self._on_delete(event)
        else:
            event.Skip()

    def _on_new(self, _event: wx.Event) -> None:
        from odsbox_pilot.connection.connect_dialog import ConnectDialog

        dlg = ConnectDialog(self, self._manager, config=None)
        if dlg.ShowModal() == wx.ID_OK:
            if dlg.con_i is not None:
                self._selected_config = dlg.result_config
                self._connected_con_i = dlg.con_i
                dlg.Destroy()
                self.EndModal(wx.ID_OK)
                return
            self._refresh_list()
        dlg.Destroy()

    def _on_open_atfx_file(self, _event: wx.Event) -> None:
        with wx.FileDialog(
            self,
            "Open ATFX file",
            wildcard="ATFX files (*.atfx)|*.atfx|All files (*.*)|*.*",
            style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST,
        ) as dlg:
            if dlg.ShowModal() != wx.ID_OK:
                return
            file_path = dlg.GetPath()

        from odsbox_pilot.connection.atfx_factory import open_atfx

        try:
            wx.BeginBusyCursor()
            con_i = open_atfx(file_path)
        except Exception as exc:
            wx.MessageBox(
                f"Could not open ATFX file:\n\n{exc}",
                "ATFX Open Error",
                wx.OK | wx.ICON_ERROR,
                self,
            )
            return
        finally:
            with contextlib.suppress(Exception):
                wx.EndBusyCursor()

        self._selected_config = ServerConfig(
            id=str(uuid.uuid4()),
            name=Path(file_path).stem,
            url=file_path,
            auth_type=AuthType.ATFX,
            verify_certificate=False,
        )
        self._connected_con_i = con_i
        self.EndModal(wx.ID_OK)

    def _on_edit(self, _event: wx.Event) -> None:
        config_id = self._selected_id()
        if config_id is None:
            return
        from odsbox_pilot.connection.connect_dialog import ConnectDialog

        config = self._manager.get(config_id)
        dlg = ConnectDialog(self, self._manager, config=config)
        if dlg.ShowModal() == wx.ID_OK:
            if dlg.con_i is not None:
                self._selected_config = dlg.result_config
                self._connected_con_i = dlg.con_i
                dlg.Destroy()
                self.EndModal(wx.ID_OK)
                return
            self._refresh_list()
        dlg.Destroy()

    def _on_copy(self, _event: wx.Event) -> None:
        config_id = self._selected_id()
        if config_id is None:
            return
        from odsbox_pilot.connection.connect_dialog import ConnectDialog

        original_config = self._manager.get(config_id)
        # Create a copy with new ID and modified name
        copied_config = replace(
            original_config,
            id=str(uuid.uuid4()),
            name=f"{original_config.name} - copy",
        )
        dlg = ConnectDialog(self, self._manager, config=copied_config)
        if dlg.ShowModal() == wx.ID_OK:
            if dlg.con_i is not None:
                self._selected_config = dlg.result_config
                self._connected_con_i = dlg.con_i
                dlg.Destroy()
                self.EndModal(wx.ID_OK)
                return
            self._refresh_list()
        dlg.Destroy()

    def _on_delete(self, _event: wx.Event) -> None:
        config_id = self._selected_id()
        if config_id is None:
            return
        config = self._manager.get(config_id)
        answer = wx.MessageBox(
            f"Delete server '{config.name}'?",
            "Confirm Delete",
            wx.YES_NO | wx.ICON_WARNING,
            self,
        )
        if answer == wx.YES:
            self._manager.remove(config_id)
            self._refresh_list()

    def _on_connect(self, _event: wx.Event) -> None:
        config_id = self._selected_id()
        if config_id is None:
            return
        self._selected_config = self._manager.get(config_id)
        self.EndModal(wx.ID_OK)
