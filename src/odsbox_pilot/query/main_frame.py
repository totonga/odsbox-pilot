"""MainFrame: the primary query window after connecting to an ODS server."""

from __future__ import annotations

import contextlib
import json
import logging
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

import wx  # type: ignore[import-untyped]
import wx.adv  # type: ignore[import-untyped]

from odsbox_pilot import styles
from odsbox_pilot.browse._helpers import _load_prefs, _save_prefs
from odsbox_pilot.models import AiSettings, AppSettings, ServerConfig
from odsbox_pilot.query.editor_panel import AiContext, EditorPanel
from odsbox_pilot.query.history import HistoryEntry, QueryHistory
from odsbox_pilot.query.result_grid import ResultGrid

log = logging.getLogger(__name__)

_LOG_ICON_OK = "✓"
_LOG_ICON_ERR = "✗"


class MainFrame(wx.Frame):
    """Main application window: query editor + result grid + status log."""

    def __init__(
        self,
        con_i,
        server_name: str,
        server_config: ServerConfig | None = None,
        on_disconnect: Callable[[], None] | None = None,
    ) -> None:
        try:
            server_url: str = con_i.con_i_url()
        except Exception:
            server_url = ""
        super().__init__(
            None,
            title=f"ODS Pilot — {server_name}  [{server_url}]"
            if server_url
            else f"ODS Pilot — {server_name}",
            size=(1100, 750),
            style=wx.DEFAULT_FRAME_STYLE,
        )
        styles.apply_scaled_app_font(self)
        self.SetSize(self.FromDIP(wx.Size(1100, 750)))
        self._con_i = con_i
        self._server_config = server_config
        self._history = QueryHistory()
        self._settings = AppSettings.load()
        self._ai_settings = AiSettings.load()
        self._ai_startup_hint: str | None = None
        self._on_disconnect_cb = on_disconnect
        self._is_disconnecting = False

        self._build_ui()
        if self._ai_startup_hint:
            self._log(self._ai_startup_hint, ok=False)
        self._set_icon()
        log_msg = f"Connected to {server_name}"
        if server_url:
            log_msg += f"  —  {server_url}"
        self._log(log_msg, ok=True)
        self.Centre()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _set_icon(self) -> None:
        """Create a window icon by rendering ⊞ (matrix/grid glyph) onto a bitmap."""
        size = 32
        bmp = wx.Bitmap(size, size)
        dc = wx.MemoryDC(bmp)
        dc.SetBackground(wx.Brush(wx.Colour(0, 120, 180)))
        dc.Clear()
        font = wx.Font(
            styles.scaled_point_size(22),
            wx.FONTFAMILY_DEFAULT,
            wx.FONTSTYLE_NORMAL,
            wx.FONTWEIGHT_BOLD,
            faceName="",
        )
        dc.SetFont(font)
        dc.SetTextForeground(wx.WHITE)
        glyph = "\u229e"  # ⊞ SQUARED PLUS
        tw, th = dc.GetTextExtent(glyph)
        dc.DrawText(glyph, (size - tw) // 2, (size - th) // 2)
        dc.SelectObject(wx.NullBitmap)
        icon = wx.Icon()
        icon.CopyFromBitmap(bmp)
        self.SetIcon(icon)

    def _build_ui(self) -> None:
        from odsbox_pilot.browse.browse_panel import BrowsePanel

        # Outer vertical splitter: top=notebook (tabs), bottom=log
        outer_splitter = wx.SplitterWindow(self, style=wx.SP_LIVE_UPDATE)

        # Notebook contains Tab 0 (Query) and Tab 1 (Browse)
        notebook = wx.Notebook(outer_splitter)

        # Tab 0 — Query: inner horizontal splitter with editor + grid
        inner_splitter = wx.SplitterWindow(notebook, style=wx.SP_LIVE_UPDATE)

        # Initialize AI context if enabled
        ai_context = self._init_ai_context()

        self._editor = EditorPanel(
            inner_splitter,
            self._history,
            self._on_execute,
            settings=self._settings,
            ai_context=ai_context,
        )
        self._grid = ResultGrid(inner_splitter)
        inner_splitter.SplitHorizontally(self._editor, self._grid, sashPosition=self.FromDIP(280))
        inner_splitter.SetMinimumPaneSize(self.FromDIP(80))
        notebook.AddPage(inner_splitter, "Query")

        # Tab 1 — Browse: FilterTree browser panel
        self._browse = BrowsePanel(
            notebook,
            self._con_i,
            log_fn=self._log,
            status_fn=lambda msg: self.GetStatusBar().SetStatusText(msg, 0),
        )
        notebook.AddPage(self._browse, "Browse")

        # Tab 2 — Model: entity-relation schema browser
        from odsbox_pilot.model.model_panel import ModelPanel

        self._model_panel = ModelPanel(notebook, self._con_i)
        notebook.AddPage(self._model_panel, "Model")

        self._notebook = notebook
        notebook.Bind(wx.EVT_NOTEBOOK_PAGE_CHANGED, self._on_main_tab_changed)
        wx.CallAfter(self._restore_main_tab)

        # Log panel
        log_panel = self._build_log_panel(outer_splitter)

        outer_splitter.SplitHorizontally(notebook, log_panel, sashPosition=self.FromDIP(550))
        outer_splitter.SetMinimumPaneSize(self.FromDIP(60))
        outer_splitter.SetSashGravity(1.0)

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
        self._log_label.SetFont(styles.bold_font(self._log_label))
        vbox.Add(self._log_label, flag=wx.LEFT | wx.TOP, border=4)

        self._log_list = wx.ListCtrl(
            panel,
            style=wx.LC_REPORT | wx.LC_NO_HEADER | wx.BORDER_NONE,
        )
        self._log_list.AppendColumn("", width=self.FromDIP(40))
        self._log_list.AppendColumn("Time", width=self.FromDIP(80))
        self._log_list.AppendColumn("Rows", width=self.FromDIP(60))
        self._log_list.AppendColumn("Query", width=self.FromDIP(600))

        vbox.Add(self._log_list, proportion=1, flag=wx.EXPAND | wx.ALL, border=2)
        panel.SetSizer(vbox)
        self._log_list.Bind(wx.EVT_SIZE, self._on_log_list_resize)
        return panel

    def _build_menu(self) -> None:
        menubar = wx.MenuBar()

        file_menu = wx.Menu()
        item_disconnect = file_menu.Append(wx.ID_ANY, "Disconnect\tCtrl+W")
        file_menu.AppendSeparator()
        item_export_csv = file_menu.Append(wx.ID_ANY, "Export CSV…\tCtrl+S")
        item_script_starter = file_menu.Append(wx.ID_ANY, "Generate Script Starter…")
        file_menu.AppendSeparator()
        item_exit = file_menu.Append(wx.ID_EXIT, "Exit\tAlt+F4")
        menubar.Append(file_menu, "&File")

        # Settings menu
        settings_menu = wx.Menu()
        item_preferences = settings_menu.Append(
            wx.ID_ANY, "Preferences…", "Configure application-wide settings"
        )
        item_ai_settings = settings_menu.Append(
            wx.ID_ANY, "AI Query Assistant…", "Configure AI model and download settings"
        )
        menubar.Append(settings_menu, "&Settings")

        # Help menu
        help_menu = wx.Menu()
        item_about = help_menu.Append(wx.ID_ABOUT, "&About ODS Pilot…")
        menubar.Append(help_menu, "&Help")

        self.Bind(wx.EVT_MENU, self._on_disconnect, item_disconnect)
        self.Bind(wx.EVT_MENU, self._on_export_csv, item_export_csv)
        self.Bind(wx.EVT_MENU, self._on_generate_script_starter, item_script_starter)
        self.Bind(wx.EVT_MENU, lambda _e: self.Close(), item_exit)
        self.Bind(wx.EVT_MENU, self._on_ai_settings, item_ai_settings)
        self.Bind(wx.EVT_MENU, self._on_preferences, item_preferences)
        self.Bind(wx.EVT_MENU, self._on_about, item_about)
        self.Bind(wx.EVT_CLOSE, self._on_close)

        self.SetMenuBar(menubar)

    def _init_ai_context(self) -> AiContext | None:
        """Initialize AI context if enabled and model is downloaded.

        Returns:
            AiContext if AI is enabled, None otherwise.
        """
        if not self._ai_settings.enabled:
            return None

        try:
            from odsbox_pilot.ai import ModelManager, NlToConditions, OvLlmPipeline
            from odsbox_pilot.model.search_index import ModelSearchIndex

            # Check if model is downloaded
            manager = ModelManager(self._ai_settings.model_cache_dir)
            model_path = manager.get_model_path(self._ai_settings.model_id)
            if model_path is None:
                self._ai_startup_hint = (
                    "AI model not downloaded yet. Open Settings → AI Query Assistant… "
                    "to download it, or keep AI disabled until you are ready."
                )
                log.warning("AI model not downloaded: %s", self._ai_settings.model_id)
                return None

            # Initialize LLM pipeline
            pipeline = OvLlmPipeline(model_path, device=self._ai_settings.device)

            # Initialize model search index
            model = self._con_i.mc.model()
            search_index = ModelSearchIndex(model)

            # Create NL parser
            nl_parser = NlToConditions(search_index, pipeline)

            log.info(f"AI context initialized with model {self._ai_settings.model_id}")
            return AiContext(nl_parser=nl_parser, model_cache=self._con_i.mc)

        except ImportError as e:
            log.warning(f"AI dependencies not installed: {e}")
            return None
        except Exception:
            log.exception("Failed to initialize AI context")
            return None

    # ------------------------------------------------------------------
    # AI settings
    # ------------------------------------------------------------------

    def _on_ai_settings(self, _event: wx.Event) -> None:
        from odsbox_pilot.query.ai_settings_dialog import AiSettingsDialog

        dlg = AiSettingsDialog(self, self._ai_settings)
        if dlg.ShowModal() == wx.ID_OK:
            self._ai_settings = dlg.get_settings()
            self._ai_settings.save()
            # Re-initialize and push the new context to the editor
            ai_context = self._init_ai_context()
            self._editor.set_ai_context(ai_context)
        dlg.Destroy()

    def _on_preferences(self, _event: wx.Event) -> None:
        from odsbox_pilot.query.settings_dialog import AppSettingsDialog

        dlg = AppSettingsDialog(self, self._settings)
        if dlg.ShowModal() == wx.ID_OK:
            self._settings = dlg.get_settings()
            self._settings.save()
        dlg.Destroy()

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

    def _on_log_list_resize(self, event: wx.SizeEvent) -> None:
        # Keep the Query column (index 3) filling whatever width is left
        fixed = sum(self._log_list.GetColumnWidth(i) for i in range(3))
        remaining = self._log_list.GetClientSize().width - fixed
        if remaining > 0:
            self._log_list.SetColumnWidth(3, remaining)
        event.Skip()

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

    def _on_generate_script_starter(self, _event: wx.Event) -> None:
        from odsbox_pilot.query.script_starter_generator import generate_starter
        from odsbox_pilot.query.script_starter_logic import (
            compute_target_path,
            validate_script_starter_prerequisites,
        )

        # Step 1: Validate prerequisites
        validation = validate_script_starter_prerequisites(self._server_config, self._history)
        if not validation.is_valid:
            wx.MessageBox(
                validation.error_message,
                "Generate Script Starter",
                wx.OK | wx.ICON_INFORMATION,
                self,
            )
            return

        # Step 2: Ask user for directory
        with wx.DirDialog(
            self,
            "Select destination folder for script starter",
            style=wx.DD_DEFAULT_STYLE | wx.DD_DIR_MUST_EXIST,
        ) as dlg:
            if dlg.ShowModal() != wx.ID_OK:
                return
            parent_path = Path(dlg.GetPath())

        # Step 3: Compute target path with collision handling
        target_result = compute_target_path(parent_path, self._server_config)
        if isinstance(target_result, str):  # Error message
            self._show_error(target_result)
            return
        target_path = target_result

        # Step 4: Generate the script starter
        last_query = next(
            (e.query for e in self._history.entries if e.error is None),
            None,
        )
        try:
            generate_starter(self._server_config, last_query, target_path)
        except Exception as exc:
            self._show_error(str(exc))
            return

        self.GetStatusBar().SetStatusText(f"Script starter created: {target_path}", 0)
        self._log(f"Script starter created: {target_path}", ok=True)

    def _on_about(self, _event: wx.Event) -> None:
        from odsbox_pilot import __version__

        info = wx.adv.AboutDialogInfo()
        info.SetName("ODS Pilot")
        info.SetVersion(__version__)
        info.SetDescription("ASAM ODS desktop query tool powered by odsbox.")
        info.SetCopyright("© Andreas K")
        info.SetWebSite("https://github.com/totonga/odsbox-pilot")
        wx.adv.AboutBox(info, self)

    def _on_disconnect(self, _event: wx.Event) -> None:
        self._is_disconnecting = True
        self.Close()

    _BROWSE_TAB = 1

    def _on_main_tab_changed(self, event: wx.BookCtrlEvent) -> None:
        prefs = _load_prefs()
        prefs["main_tab"] = event.GetSelection()
        _save_prefs(prefs)
        if event.GetSelection() == self._BROWSE_TAB:
            wx.CallAfter(self._browse.trigger_initial_query)
        event.Skip()

    def _restore_main_tab(self) -> None:
        page = _load_prefs().get("main_tab", 0)
        if 0 <= page < self._notebook.GetPageCount():
            self._notebook.SetSelection(page)

    def _on_close(self, event: wx.CloseEvent) -> None:
        self._close_connection()
        if self._is_disconnecting and self._on_disconnect_cb is not None:
            wx.CallAfter(self._on_disconnect_cb)
        else:
            wx.GetApp().ExitMainLoop()
        event.Skip()

    def _close_connection(self) -> None:
        with contextlib.suppress(Exception):
            self._browse.clear_connection()
        with contextlib.suppress(Exception):
            self._con_i.__exit__(None, None, None)
