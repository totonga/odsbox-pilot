"""MainFrame: the primary query window after connecting to an ODS server."""

from __future__ import annotations

import contextlib
import json
from collections.abc import Callable
from datetime import UTC, datetime

import wx  # type: ignore[import-untyped]

from odsbox_pilot.models import AppSettings
from odsbox_pilot.query.editor_panel import EditorPanel
from odsbox_pilot.query.history import HistoryEntry, QueryHistory
from odsbox_pilot.query.result_grid import ResultGrid

_LOG_ICON_OK = "✓"
_LOG_ICON_ERR = "✗"


class MainFrame(wx.Frame):
    """Main application window: query editor + result grid + status log."""

    def __init__(self, con_i, server_name: str, on_disconnect: Callable[[], None] | None = None) -> None:
        super().__init__(
            None,
            title=f"ODS Pilot — {server_name}",
            size=(1100, 750),
            style=wx.DEFAULT_FRAME_STYLE,
        )
        self._con_i = con_i
        self._history = QueryHistory()
        self._settings = AppSettings.load()
        self._on_disconnect_cb = on_disconnect
        self._is_disconnecting = False

        self._build_ui()
        self._log(f"Connected to {server_name}", ok=True)
        self.Centre()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        # Outer vertical splitter: top=editor+grid, bottom=log
        outer_splitter = wx.SplitterWindow(self, style=wx.SP_LIVE_UPDATE)

        # Inner horizontal splitter: left/top=editor, right/bottom=grid
        inner_splitter = wx.SplitterWindow(outer_splitter, style=wx.SP_LIVE_UPDATE)

        self._editor = EditorPanel(inner_splitter, self._history, self._on_execute)
        self._grid = ResultGrid(inner_splitter)

        inner_splitter.SplitHorizontally(self._editor, self._grid, sashPosition=280)
        inner_splitter.SetMinimumPaneSize(80)

        # Log panel
        log_panel = self._build_log_panel(outer_splitter)

        outer_splitter.SplitHorizontally(inner_splitter, log_panel, sashPosition=550)
        outer_splitter.SetMinimumPaneSize(60)

        # Status bar
        sb = self.CreateStatusBar(2)
        sb.SetStatusWidths([-3, -1])
        sb.SetStatusText("Ready", 0)

        # Menu bar
        self._build_menu()

    def _build_log_panel(self, parent: wx.Window) -> wx.Panel:
        panel = wx.Panel(parent)
        vbox = wx.BoxSizer(wx.VERTICAL)

        self._log_label = wx.StaticText(panel, label="Query Log")
        font = self._log_label.GetFont()
        font.SetWeight(wx.FONTWEIGHT_BOLD)
        self._log_label.SetFont(font)
        vbox.Add(self._log_label, flag=wx.LEFT | wx.TOP, border=4)

        self._log_list = wx.ListCtrl(
            panel,
            style=wx.LC_REPORT | wx.LC_NO_HEADER | wx.BORDER_NONE,
        )
        self._log_list.AppendColumn("", width=40)
        self._log_list.AppendColumn("Time", width=80)
        self._log_list.AppendColumn("Rows", width=60)
        self._log_list.AppendColumn("Query", width=600)

        vbox.Add(self._log_list, proportion=1, flag=wx.EXPAND | wx.ALL, border=2)
        panel.SetSizer(vbox)
        return panel

    def _build_menu(self) -> None:
        menubar = wx.MenuBar()

        file_menu = wx.Menu()
        item_disconnect = file_menu.Append(wx.ID_ANY, "Disconnect\tCtrl+W")
        file_menu.AppendSeparator()
        item_export_csv = file_menu.Append(wx.ID_ANY, "Export CSV…\tCtrl+S")
        file_menu.AppendSeparator()
        item_exit = file_menu.Append(wx.ID_EXIT, "Exit\tAlt+F4")
        menubar.Append(file_menu, "&File")

        # Settings menu
        settings_menu = wx.Menu()
        self._item_naming_query = settings_menu.AppendRadioItem(
            wx.ID_ANY, "Result Naming: Query", "Column names come from the JAQueL query (default)"
        )
        self._item_naming_model = settings_menu.AppendRadioItem(
            wx.ID_ANY,
            "Result Naming: Model",
            "Column names come from the ODS model schema (e.g. Unit.Name)",
        )
        menubar.Append(settings_menu, "&Settings")

        # Reflect current settings
        if self._settings.result_naming_mode == "model":
            self._item_naming_model.Check(True)
        else:
            self._item_naming_query.Check(True)

        self.Bind(wx.EVT_MENU, self._on_disconnect, item_disconnect)
        self.Bind(wx.EVT_MENU, self._on_export_csv, item_export_csv)
        self.Bind(wx.EVT_MENU, lambda _e: self.Close(), item_exit)
        self.Bind(wx.EVT_MENU, self._on_naming_query, self._item_naming_query)
        self.Bind(wx.EVT_MENU, self._on_naming_model, self._item_naming_model)
        self.Bind(wx.EVT_CLOSE, self._on_close)

        self.SetMenuBar(menubar)

    # ------------------------------------------------------------------
    # Execute query
    # ------------------------------------------------------------------

    def _on_execute(self, query_str: str) -> None:
        self.GetStatusBar().SetStatusText("Executing…", 0)
        wx.BeginBusyCursor()
        try:
            query_dict = json.loads(query_str)
            df = self._con_i.query(query_dict, result_naming_mode=self._settings.result_naming_mode)
            row_count = len(df)
            self._grid.load_dataframe(df)
            entry = HistoryEntry.success(query_str, row_count)
            self._history.append(entry)
            self._log_entry(entry)
            self.GetStatusBar().SetStatusText(f"OK — {row_count} rows", 0)
            self.GetStatusBar().SetStatusText(datetime.now(tz=UTC).strftime("%H:%M:%S UTC"), 1)
        except Exception as exc:
            error_msg = str(exc)
            entry = HistoryEntry.failure(query_str, error_msg)
            self._history.append(entry)
            self._log_entry(entry)
            self.GetStatusBar().SetStatusText(f"Error: {error_msg[:80]}", 0)
            self._show_error(error_msg)
        finally:
            with contextlib.suppress(Exception):
                wx.EndBusyCursor()

    # ------------------------------------------------------------------
    # Log helpers
    # ------------------------------------------------------------------

    def _log(self, message: str, ok: bool = True) -> None:
        ts = datetime.now(tz=UTC).strftime("%H:%M:%S")
        icon = _LOG_ICON_OK if ok else _LOG_ICON_ERR
        idx = self._log_list.InsertItem(0, icon)  # prepend
        self._log_list.SetItem(idx, 1, ts)
        self._log_list.SetItem(idx, 2, "")
        self._log_list.SetItem(idx, 3, message)
        if not ok:
            self._log_list.SetItemTextColour(idx, wx.Colour(180, 0, 0))

    def _log_entry(self, entry: HistoryEntry) -> None:
        ts = entry.timestamp[11:19]  # HH:MM:SS
        icon = _LOG_ICON_OK if entry.error is None else _LOG_ICON_ERR
        row_str = str(entry.row_count) if entry.row_count is not None else "—"
        query_preview = entry.query.replace("\n", " ").strip()
        if len(query_preview) > 120:
            query_preview = query_preview[:117] + "…"
        idx = self._log_list.InsertItem(0, icon)  # prepend (newest first)
        self._log_list.SetItem(idx, 1, ts)
        self._log_list.SetItem(idx, 2, row_str)
        self._log_list.SetItem(idx, 3, query_preview)
        if entry.error:
            self._log_list.SetItemTextColour(idx, wx.Colour(180, 0, 0))
        else:
            self._log_list.SetItemTextColour(idx, wx.Colour(0, 130, 0))

    def _show_error(self, message: str) -> None:
        dlg = wx.MessageDialog(
            self,
            message,
            caption="Query Error",
            style=wx.OK | wx.ICON_ERROR,
        )
        dlg.ShowModal()
        dlg.Destroy()

    # ------------------------------------------------------------------
    # Menu handlers
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # Settings handlers
    # ------------------------------------------------------------------

    def _on_naming_query(self, _event: wx.Event) -> None:
        self._settings.result_naming_mode = "query"
        self._settings.save()

    def _on_naming_model(self, _event: wx.Event) -> None:
        self._settings.result_naming_mode = "model"
        self._settings.save()

    # ------------------------------------------------------------------
    # Menu handlers
    # ------------------------------------------------------------------

    def _on_export_csv(self, _event: wx.Event) -> None:
        if self._grid._df is None:
            wx.MessageBox(
                "No results to export. Execute a query first.",
                "Export CSV",
                wx.OK | wx.ICON_INFORMATION,
                self,
            )
            return
        with wx.FileDialog(
            self,
            "Export CSV",
            wildcard="CSV files (*.csv)|*.csv",
            style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT,
        ) as dlg:
            if dlg.ShowModal() != wx.ID_OK:
                return
            path = dlg.GetPath()
        try:
            self._grid.export_csv(path)
            self.GetStatusBar().SetStatusText(f"Exported: {path}", 0)
        except Exception as exc:
            self._show_error(str(exc))

    def _on_disconnect(self, _event: wx.Event) -> None:
        self._is_disconnecting = True
        self.Close()

    def _on_close(self, event: wx.CloseEvent) -> None:
        self._close_connection()
        if self._is_disconnecting and self._on_disconnect_cb is not None:
            wx.CallAfter(self._on_disconnect_cb)
        else:
            wx.GetApp().ExitMainLoop()
        event.Skip()

    def _close_connection(self) -> None:
        with contextlib.suppress(Exception):
            self._con_i.__exit__(None, None, None)
