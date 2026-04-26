"""EditorPanel: CodeMirror 6 JSON editor embedded in a wx.html2.WebView."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

import wx  # type: ignore[import-untyped]
import wx.html2  # type: ignore[import-untyped]

from ods_pilot.query.examples import EXAMPLES, by_category, categories
from ods_pilot.query.history import QueryHistory

_STATIC_DIR = Path(__file__).parent.parent / "static"
_EDITOR_HTML = _STATIC_DIR / "editor.html"


class EditorPanel(wx.Panel):
    """Panel hosting the CodeMirror JSON editor and its toolbar."""

    def __init__(
        self,
        parent: wx.Window,
        history: QueryHistory,
        on_execute: Callable[[str], None],
    ) -> None:
        super().__init__(parent)
        self._history = history
        self._on_execute = on_execute
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

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        vbox = wx.BoxSizer(wx.VERTICAL)

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
