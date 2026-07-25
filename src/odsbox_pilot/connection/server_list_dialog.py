"""ServerListDialog: shows saved ODS servers; entry point to connect."""

from __future__ import annotations

import contextlib
import re
import uuid
from dataclasses import replace
from pathlib import Path

import wx  # type: ignore[import-untyped]

from odsbox_pilot import styles
from odsbox_pilot.connection.manager import (
    PORTABLE_CONFIG_SUFFIX,
    PORTABLE_CONFIG_WILDCARD,
    ServerConfigManager,
)
from odsbox_pilot.models import AuthType, ServerConfig

_INVALID_FILENAME_CHARS = re.compile(r'[<>:"/\\|?*]+')


class ServerListDialog(wx.Dialog):
    """Main entry dialog listing configured ODS servers."""

    def __init__(self, parent: wx.Window | None, manager: ServerConfigManager) -> None:
        super().__init__(
            parent,
            title="ODS Pilot — Servers",
            size=(600, 380),
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
        )
        styles.apply_scaled_app_font(self)
        self.SetSize(self.FromDIP(wx.Size(600, 380)))
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
        self._list.AppendColumn("Name", width=self.FromDIP(180))
        self._list.AppendColumn("URL", width=self.FromDIP(260))
        self._list.AppendColumn("Auth", width=self.FromDIP(80))
        self._list.Bind(wx.EVT_LIST_ITEM_ACTIVATED, self._on_connect)
        self._list.Bind(wx.EVT_LIST_ITEM_SELECTED, self._on_selection_changed)
        self._list.Bind(wx.EVT_LIST_ITEM_DESELECTED, self._on_selection_changed)
        self._list.Bind(wx.EVT_CONTEXT_MENU, self._on_list_context_menu)
        vbox.Add(self._list, proportion=1, flag=wx.EXPAND | wx.ALL, border=8)

        # --- Buttons ---
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)

        self._btn_new = wx.Button(panel, label="New…")
        self._btn_connect = wx.Button(panel, wx.ID_OK, label="Connect")
        btn_close = wx.Button(panel, wx.ID_CANCEL, label="Close")
        self._btn_open_atfx_file = wx.Button(panel, label="📄", size=wx.Size(24, -1))
        self._btn_open_atfx_file.SetToolTip("Open ATFX file")

        self._btn_connect.Disable()
        self._btn_connect.SetDefault()

        btn_sizer.Add(self._btn_new, flag=wx.RIGHT, border=4)
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
        self._btn_open_atfx_file.Bind(wx.EVT_BUTTON, self._on_open_atfx_file)
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
        self._btn_connect.Enable(has_selection)

    @staticmethod
    def _default_export_filename(server_name: str) -> str:
        base_name = _INVALID_FILENAME_CHARS.sub("_", server_name).strip().rstrip(".")
        return f"{base_name or 'server'}{PORTABLE_CONFIG_SUFFIX}"

    @staticmethod
    def _ensure_export_suffix(path: Path) -> Path:
        if str(path).endswith(PORTABLE_CONFIG_SUFFIX):
            return path
        return path.with_name(f"{path.name}{PORTABLE_CONFIG_SUFFIX}")

    def _selected_config_or_none(self) -> ServerConfig | None:
        config_id = self._selected_id()
        if config_id is None:
            return None
        return self._manager.get(config_id)

    def _show_connect_dialog(
        self,
        config: ServerConfig | None,
        *,
        allow_secret_prefill: bool = True,
    ) -> None:
        from odsbox_pilot.connection.connect_dialog import ConnectDialog

        dlg = ConnectDialog(
            self,
            self._manager,
            config=config,
            allow_secret_prefill=allow_secret_prefill,
        )
        if dlg.ShowModal() == wx.ID_OK:
            if dlg.con_i is not None:
                self._selected_config = dlg.result_config
                self._connected_con_i = dlg.con_i
                dlg.Destroy()
                self.EndModal(wx.ID_OK)
                return
            self._refresh_list()
        dlg.Destroy()

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

    def _on_list_context_menu(self, _event: wx.ContextMenuEvent) -> None:
        menu = wx.Menu()
        item_import = menu.Append(wx.ID_ANY, "Import...")
        menu.AppendSeparator()
        item_edit = menu.Append(wx.ID_ANY, "Edit...")
        item_copy = menu.Append(wx.ID_ANY, "Copy")
        item_export = menu.Append(wx.ID_ANY, "Export...")
        item_delete = menu.Append(wx.ID_ANY, "Delete")

        has_selection = self._selected_config_or_none() is not None
        item_edit.Enable(has_selection)
        item_copy.Enable(has_selection)
        item_export.Enable(has_selection)
        item_delete.Enable(has_selection)

        self.Bind(wx.EVT_MENU, self._on_import, item_import)
        self.Bind(wx.EVT_MENU, self._on_edit, item_edit)
        self.Bind(wx.EVT_MENU, self._on_copy, item_copy)
        self.Bind(wx.EVT_MENU, self._on_export, item_export)
        self.Bind(wx.EVT_MENU, self._on_delete, item_delete)
        self._list.PopupMenu(menu)
        menu.Destroy()

    def _on_new(self, _event: wx.Event) -> None:
        self._show_connect_dialog(config=None)

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
        config = self._selected_config_or_none()
        if config is None:
            return
        self._show_connect_dialog(config=config)

    def _on_copy(self, _event: wx.Event) -> None:
        original_config = self._selected_config_or_none()
        if original_config is None:
            return
        # Create a copy with new ID and modified name
        copied_config = replace(
            original_config,
            id=str(uuid.uuid4()),
            name=f"{original_config.name} - copy",
        )
        self._show_connect_dialog(config=copied_config)

    def _on_import(self, _event: wx.Event) -> None:
        with wx.FileDialog(
            self,
            "Import server configuration",
            wildcard=PORTABLE_CONFIG_WILDCARD,
            style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST,
        ) as dlg:
            if dlg.ShowModal() != wx.ID_OK:
                return
            import_path = Path(dlg.GetPath())

        try:
            imported_config = self._manager.read_portable_config(import_path)
        except Exception as exc:
            wx.MessageBox(
                f"Could not import server configuration:\n\n{exc}",
                "Import Error",
                wx.OK | wx.ICON_ERROR,
                self,
            )
            return

        self._show_connect_dialog(config=imported_config, allow_secret_prefill=False)

    def _on_export(self, _event: wx.Event) -> None:
        config = self._selected_config_or_none()
        if config is None:
            return

        with wx.FileDialog(
            self,
            "Export server configuration",
            defaultFile=self._default_export_filename(config.name),
            wildcard=PORTABLE_CONFIG_WILDCARD,
            style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT,
        ) as dlg:
            if dlg.ShowModal() != wx.ID_OK:
                return
            export_path = self._ensure_export_suffix(Path(dlg.GetPath()))

        try:
            self._manager.export_to_file(config, export_path)
        except Exception as exc:
            wx.MessageBox(
                f"Could not export server configuration:\n\n{exc}",
                "Export Error",
                wx.OK | wx.ICON_ERROR,
                self,
            )

    def _on_delete(self, _event: wx.Event) -> None:
        config = self._selected_config_or_none()
        if config is None:
            return
        answer = wx.MessageBox(
            f"Delete server '{config.name}'?",
            "Confirm Delete",
            wx.YES_NO | wx.ICON_WARNING,
            self,
        )
        if answer == wx.YES:
            self._manager.remove(config.id)
            self._refresh_list()

    def _on_connect(self, _event: wx.Event) -> None:
        config_id = self._selected_id()
        if config_id is None:
            return
        self._selected_config = self._manager.get(config_id)
        self.EndModal(wx.ID_OK)
