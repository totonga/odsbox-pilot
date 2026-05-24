"""EditorPanel: CodeMirror 6 JSON editor embedded in a wx.html2.WebView."""

from __future__ import annotations

import json
import logging
import threading
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import wx  # type: ignore[import-untyped]
import wx.html2  # type: ignore[import-untyped]

from odsbox_pilot.models import AppSettings
from odsbox_pilot.query.examples import by_category, categories
from odsbox_pilot.query.history import QueryHistory

log = logging.getLogger(__name__)


@dataclass
class AiContext:
    """Context for AI query parsing (injected when AI is enabled)."""

    nl_parser: Any  # NlToConditions instance
    model_cache: Any  # ModelCache instance


_STATIC_DIR = Path(__file__).parent.parent / "static"
_EDITOR_HTML = _STATIC_DIR / "editor.html"


class EditorPanel(wx.Panel):
    """Panel hosting the CodeMirror JSON editor and its toolbar."""

    def __init__(
        self,
        parent: wx.Window,
        history: QueryHistory,
        on_execute: Callable[[str], None],
        settings: AppSettings | None = None,
        ai_context: AiContext | None = None,
    ) -> None:
        super().__init__(parent)
        self._history = history
        self._on_execute = on_execute
        self._settings = settings
        self._ai_context = ai_context
        self._webview_ready = False

        self._build_ui()
        self._load_editor()

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def get_query(self) -> str:
        """Return current editor content (raw string)."""
        if not self._webview_ready:
            return ""
        ok, result = self._webview.RunScript("getEditorContent()")
        return result if ok else ""

    def set_query(self, text: str) -> None:
        """Replace editor content with *text*."""
        if not self._webview_ready:
            return
        escaped = json.dumps(text)  # produces a valid JS string literal
        self._webview.RunScript(f"setEditorContent({escaped})")

    def has_errors(self) -> bool:
        if not self._webview_ready:
            return False
        ok, result = self._webview.RunScript("editorHasErrors()")
        return bool(ok and result.lower() == "true")

    def set_ai_context(self, ai_context: AiContext | None) -> None:
        """Update the AI context (e.g. after settings change)."""
        self._ai_context = ai_context
        self._refresh_ai_bar()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _refresh_ai_bar(self) -> None:
        """Sync the AI bar hint / enabled state with the current context."""
        if self._ai_context is not None:
            self._ai_input.SetHint(
                "e.g., Show me measurements named Pro* in the project Electric*, measured in the last year"
            )
            self._ai_input.Enable()
            self._btn_ai_parse.SetLabel("Parse")
        else:
            self._ai_input.SetHint("AI not configured — click 'Setup AI…' to download a model")
            self._ai_input.Disable()
            self._btn_ai_parse.SetLabel("Setup AI…")

    def _build_ui(self) -> None:
        vbox = wx.BoxSizer(wx.VERTICAL)

        # --- AI Query Bar (always visible; disabled when not configured) ---
        ai_panel = wx.Panel(self)
        ai_sizer = wx.BoxSizer(wx.HORIZONTAL)

        ai_label = wx.StaticText(ai_panel, label="✨ AI Query:")
        ai_label_font = ai_label.GetFont()
        ai_label_font.SetWeight(wx.FONTWEIGHT_BOLD)
        ai_label.SetFont(ai_label_font)
        ai_sizer.Add(ai_label, flag=wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, border=8)

        self._ai_input = wx.TextCtrl(
            ai_panel,
            style=wx.TE_PROCESS_ENTER,
            size=(500, -1),
        )
        self._ai_input.Bind(wx.EVT_TEXT_ENTER, self._on_ai_parse)
        ai_sizer.Add(
            self._ai_input,
            proportion=1,
            flag=wx.ALIGN_CENTER_VERTICAL | wx.RIGHT,
            border=8,
        )

        self._btn_ai_parse = wx.Button(ai_panel, label="Parse")
        self._btn_ai_parse.Bind(wx.EVT_BUTTON, self._on_ai_parse)
        ai_sizer.Add(self._btn_ai_parse, flag=wx.ALIGN_CENTER_VERTICAL)

        ai_panel.SetSizer(ai_sizer)
        vbox.Add(ai_panel, flag=wx.EXPAND | wx.ALL, border=6)
        self._refresh_ai_bar()

        # --- Toolbar ---
        toolbar = wx.Panel(self)
        tbar_sizer = wx.BoxSizer(wx.HORIZONTAL)

        # Examples menu button
        self._btn_examples = wx.Button(toolbar, label="Examples ▾")
        self._btn_examples.Bind(wx.EVT_BUTTON, self._on_examples_menu)
        tbar_sizer.Add(self._btn_examples, flag=wx.RIGHT, border=4)

        # History menu button
        self._btn_history = wx.Button(toolbar, label="History ▾")
        self._btn_history.Bind(wx.EVT_BUTTON, self._on_history_menu)
        tbar_sizer.Add(self._btn_history, flag=wx.RIGHT, border=4)

        # Settings dropdown button
        if self._settings is not None:
            self._btn_settings = wx.Button(toolbar, label="Settings ▾")
            self._btn_settings.Bind(wx.EVT_BUTTON, self._on_settings_menu)
            tbar_sizer.Add(self._btn_settings, flag=wx.RIGHT, border=4)

        tbar_sizer.AddStretchSpacer()

        # Pretty Print
        btn_pretty = wx.Button(toolbar, label="Pretty Print")
        btn_pretty.Bind(wx.EVT_BUTTON, self._on_pretty_print)
        tbar_sizer.Add(btn_pretty, flag=wx.RIGHT, border=4)

        # Execute
        self._btn_execute = wx.Button(toolbar, label="▶  Execute  (Alt+Enter)")
        self._btn_execute.SetBackgroundColour(wx.Colour(0, 120, 215))
        self._btn_execute.SetForegroundColour(wx.WHITE)
        font = self._btn_execute.GetFont()
        font.SetWeight(wx.FONTWEIGHT_BOLD)
        self._btn_execute.SetFont(font)
        self._btn_execute.Bind(wx.EVT_BUTTON, self._on_execute_btn)
        tbar_sizer.Add(self._btn_execute)

        toolbar.SetSizer(tbar_sizer)
        vbox.Add(toolbar, flag=wx.EXPAND | wx.ALL, border=6)

        # --- WebView ---
        self._webview = wx.html2.WebView.New(self)
        vbox.Add(self._webview, proportion=1, flag=wx.EXPAND)

        self.SetSizer(vbox)

        # Navigation event fires when the page hash changes (our change signal)
        self._webview.Bind(wx.html2.EVT_WEBVIEW_NAVIGATING, self._on_navigating)
        self._webview.Bind(wx.html2.EVT_WEBVIEW_LOADED, self._on_page_loaded)

        # Keyboard shortcut Ctrl+Enter → Execute
        self.Bind(wx.EVT_CHAR_HOOK, self._on_char_hook)

    def _load_editor(self) -> None:
        """Load the editor HTML from the local static directory."""
        url = _EDITOR_HTML.as_uri()
        self._webview.LoadURL(url)

    # ------------------------------------------------------------------
    # WebView events
    # ------------------------------------------------------------------

    def _on_page_loaded(self, event: wx.html2.WebViewEvent) -> None:
        self._webview_ready = True
        event.Skip()

    def _on_navigating(self, event: wx.html2.WebViewEvent) -> None:
        """Intercept hash-only navigation used as a change notification."""
        url = event.GetURL()
        if "#" in url and not url.endswith(".html"):
            fragment = url.split("#", 1)[1]
            if fragment.startswith("execute"):
                event.Veto()
                self._on_execute_btn(event)
            else:
                # Just a hash-change (e.g. "changed"); don't actually navigate
                event.Veto()
        else:
            event.Skip()

    # ------------------------------------------------------------------
    # Toolbar actions
    # ------------------------------------------------------------------

    def _on_examples_menu(self, _event: wx.Event) -> None:
        menu = wx.Menu()
        for cat in categories():
            submenu = wx.Menu()
            for label, query_str in by_category(cat):
                item = submenu.Append(wx.ID_ANY, label)
                self.Bind(
                    wx.EVT_MENU,
                    lambda evt, q=query_str: self.set_query(q),
                    item,
                )
            menu.AppendSubMenu(submenu, cat)
        self._btn_examples.PopupMenu(menu)
        menu.Destroy()

    def _on_history_menu(self, _event: wx.Event) -> None:
        entries = self._history.entries
        if not entries:
            wx.MessageBox("No history yet.", "History", wx.OK | wx.ICON_INFORMATION, self)
            return
        menu = wx.Menu()
        for entry in entries[:50]:  # cap at 50 items in menu
            item = menu.Append(wx.ID_ANY, entry.short_label())
            self.Bind(
                wx.EVT_MENU,
                lambda evt, q=entry.query: self.set_query(q),
                item,
            )
        self._btn_history.PopupMenu(menu)
        menu.Destroy()

    def _on_settings_menu(self, _event: wx.Event) -> None:
        menu = wx.Menu()
        item_query = menu.AppendRadioItem(
            wx.ID_ANY, "Result Naming: Query", "Column names from JAQueL query (default)"
        )
        item_model = menu.AppendRadioItem(
            wx.ID_ANY, "Result Naming: Model", "Column names from ODS model schema"
        )
        if self._settings.result_naming_mode == "model":  # type: ignore[union-attr]
            item_model.Check(True)
        else:
            item_query.Check(True)

        def _set_query(_e: wx.Event) -> None:
            self._settings.result_naming_mode = "query"  # type: ignore[union-attr]
            self._settings.save()  # type: ignore[union-attr]

        def _set_model(_e: wx.Event) -> None:
            self._settings.result_naming_mode = "model"  # type: ignore[union-attr]
            self._settings.save()  # type: ignore[union-attr]

        menu.Bind(wx.EVT_MENU, _set_query, item_query)
        menu.Bind(wx.EVT_MENU, _set_model, item_model)
        self._btn_settings.PopupMenu(menu)
        menu.Destroy()

    def _on_pretty_print(self, _event: wx.Event) -> None:
        raw = self.get_query().strip()
        if not raw:
            return
        try:
            parsed = json.loads(raw)
            pretty = json.dumps(parsed, indent=2)
            self.set_query(pretty)
        except json.JSONDecodeError as exc:
            wx.MessageBox(
                f"JSON syntax error:\n\n{exc}",
                "Pretty Print",
                wx.OK | wx.ICON_WARNING,
                self,
            )

    def _on_execute_btn(self, _event: wx.Event) -> None:
        raw = self.get_query().strip()
        if not raw:
            return
        # Validate JSON first
        try:
            json.loads(raw)
        except json.JSONDecodeError as exc:
            wx.MessageBox(
                f"Invalid JSON — cannot execute:\n\n{exc}",
                "Query Error",
                wx.OK | wx.ICON_WARNING,
                self,
            )
            return
        self._on_execute(raw)

    def _on_char_hook(self, event: wx.KeyEvent) -> None:
        if event.AltDown() and event.GetKeyCode() == wx.WXK_RETURN:
            self._on_execute_btn(event)
        else:
            event.Skip()

    # ------------------------------------------------------------------
    # Status bar helper
    # ------------------------------------------------------------------

    def _set_status(self, msg: str) -> None:
        """Write *msg* to field 0 of the top-level frame's status bar (if any)."""
        frame = wx.GetTopLevelParent(self)
        sb = frame.GetStatusBar()
        if sb is not None:
            sb.SetStatusText(msg, 0)

    # ------------------------------------------------------------------
    # AI parse (background thread + status bar progress)
    # ------------------------------------------------------------------

    def _on_ai_parse(self, _event: wx.Event) -> None:
        """Handle AI Parse / Setup AI… button click."""
        if self._ai_context is None:
            wx.MessageBox(
                "The AI Query Assistant is not configured.\n\n"
                "To get started:\n"
                "1. Install AI dependencies:  uv sync --extra ai\n"
                "2. Open Settings → AI Query Assistant… to download a model\n"
                "3. Enable the assistant in the same dialog",
                "AI Not Configured",
                wx.OK | wx.ICON_INFORMATION,
                self,
            )
            return

        nl_text = self._ai_input.GetValue().strip()
        if not nl_text:
            wx.MessageBox(
                "Please enter a natural language query.",
                "AI Query",
                wx.OK | wx.ICON_INFORMATION,
                self,
            )
            return

        wx.BeginBusyCursor()
        self._btn_ai_parse.Disable()
        self._set_status("AI: Starting…")
        log.info(f"Parsing NL query: {nl_text}")

        ai_context = self._ai_context

        def _run() -> None:
            try:
                from odsbox_pilot.browse._helpers import _build_filter_nodes
                from odsbox_pilot.browse.filter_tree import FilterTree

                def _progress(msg: str) -> None:
                    wx.CallAfter(self._set_status, f"AI: {msg}")

                parse_result = ai_context.nl_parser.parse(nl_text, on_progress=_progress)

                wx.CallAfter(self._set_status, "AI: Building query…")
                filter_nodes, _failed = _build_filter_nodes(
                    ai_context.model_cache, parse_result.conditions
                )
                filter_tree = FilterTree(ai_context.model_cache, filter_nodes)
                jaquel = filter_tree.generate_query(
                    parse_result.root_entity,
                    attributes={"id": 1, "name": 1},
                )

                root_entity = parse_result.root_entity

                def _rebuild(conditions: list[Any]) -> dict[str, Any]:
                    nodes, _ = _build_filter_nodes(ai_context.model_cache, conditions)
                    tree = FilterTree(ai_context.model_cache, nodes)
                    return tree.generate_query(root_entity, attributes={"id": 1, "name": 1})

                wx.CallAfter(
                    self._on_ai_result,
                    parse_result.conditions,
                    parse_result.invalid_conditions,
                    jaquel,
                    _rebuild,
                )
            except Exception as exc:
                log.exception("AI query parsing failed")
                wx.CallAfter(self._on_ai_error, exc)

        threading.Thread(target=_run, daemon=True).start()

    def _on_ai_result(
        self,
        conditions: list[Any],
        invalid_conditions: list[Any],
        jaquel: dict[str, Any],
        rebuild_query: Any,
    ) -> None:
        """Called on the main thread when AI parsing succeeded."""
        wx.EndBusyCursor()
        self._btn_ai_parse.Enable()

        from odsbox_pilot.query.ai_preview_dialog import AiPreviewDialog

        dlg = AiPreviewDialog(
            self,
            conditions,
            jaquel,
            invalid_conditions=invalid_conditions,
            rebuild_query=rebuild_query,
        )
        result = dlg.ShowModal()
        dlg.Destroy()

        if result == wx.ID_OK:
            pretty_json = json.dumps(dlg.get_jaquel(), indent=2)
            self.set_query(pretty_json)
            self._set_status("AI query applied")
            log.info("AI query applied to editor")
        else:
            self._set_status("Ready")

    def _on_ai_error(self, exc: Exception) -> None:
        """Called on the main thread when AI parsing failed."""
        wx.EndBusyCursor()
        self._btn_ai_parse.Enable()
        self._set_status("AI: Failed")
        wx.MessageBox(
            f"Failed to parse query:\n\n{exc}",
            "AI Query Error",
            wx.OK | wx.ICON_ERROR,
            self,
        )
