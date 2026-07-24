"""ContextVariablesDialog: read-only view of the current session's context variables.

Uses ``ConI.context`` (odsbox >=1.6.0), a cached ``dict[str, Any]`` of the
session's ODS context variables (keys normalized to uppercase). See:
https://peak-solution.github.io/odsbox/session_context.html#quick-access-as-dictionary
"""

from __future__ import annotations

from typing import Any

import wx  # type: ignore[import-untyped]

from odsbox_pilot import styles


class ContextVariablesDialog(wx.Dialog):
    """Read-only dialog listing the current session's context variables."""

    def __init__(self, parent: wx.Window, con_i: Any) -> None:
        super().__init__(
            parent,
            title="Session Context Variables",
            size=(420, 380),
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
        )
        styles.apply_scaled_app_font(self)
        self.SetSize(self.FromDIP(wx.Size(420, 380)))
        self._con_i = con_i

        self._build_ui()
        self._populate()
        self.Centre()

    # ------------------------------------------------------------------
    # Build UI
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        outer = wx.BoxSizer(wx.VERTICAL)

        self._list = wx.ListCtrl(
            self,
            style=wx.LC_REPORT | wx.LC_SINGLE_SEL | wx.BORDER_SUNKEN,
        )
        self._list.AppendColumn("Name", width=self.FromDIP(160))
        self._list.AppendColumn("Value", width=self.FromDIP(220))
        outer.Add(self._list, proportion=1, flag=wx.EXPAND | wx.ALL, border=10)

        btn_row = wx.BoxSizer(wx.HORIZONTAL)
        btn_row.AddStretchSpacer()
        btn_close = wx.Button(self, wx.ID_CLOSE, "Close")
        btn_close.Bind(wx.EVT_BUTTON, lambda _e: self.EndModal(wx.ID_CLOSE))
        btn_row.Add(btn_close)
        outer.Add(btn_row, flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, border=10)

        self.SetSizer(outer)
        self.SetEscapeId(wx.ID_CLOSE)
        self.SetAffirmativeId(wx.ID_CLOSE)

    # ------------------------------------------------------------------
    # Data
    # ------------------------------------------------------------------

    def _populate(self) -> None:
        self._list.DeleteAllItems()
        try:
            context = self._con_i.context
        except Exception as exc:  # noqa: BLE001
            wx.MessageBox(
                f"Failed to read session context variables:\n\n{exc}",
                "Context Variables",
                wx.OK | wx.ICON_ERROR,
                self,
            )
            return

        for row, (name, value) in enumerate(sorted(context.items())):
            self._list.InsertItem(row, name)
            self._list.SetItem(row, 1, "" if value is None else str(value))
