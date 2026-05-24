"""Preview dialog for AI-generated query conditions."""

from __future__ import annotations

import json
from typing import Any

import wx  # type: ignore[import-untyped]


class AiPreviewDialog(wx.Dialog):
    """Dialog to review AI-parsed conditions and generated JAQueL query.

    Shows a read-only list of extracted conditions and the final JAQueL query
    before applying it to the editor.
    """

    def __init__(
        self,
        parent: wx.Window,
        conditions: list[dict[str, Any]],
        jaquel: dict[str, Any],
    ) -> None:
        """Initialize the preview dialog.

        Args:
            parent: Parent window.
            conditions: List of condition dicts (entity, attr, op, val).
            jaquel: Generated JAQueL query dict.
        """
        super().__init__(
            parent,
            title="AI Query Preview",
            size=(800, 600),
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
        )
        self._conditions = conditions
        self._jaquel = jaquel
        self._build_ui()
        self.Centre()

    def _build_ui(self) -> None:
        """Build the dialog UI."""
        vbox = wx.BoxSizer(wx.VERTICAL)

        # Title and description
        title = wx.StaticText(
            self,
            label="Review AI-Generated Query",
        )
        title_font = title.GetFont()
        title_font.SetPointSize(title_font.GetPointSize() + 2)
        title_font.SetWeight(wx.FONTWEIGHT_BOLD)
        title.SetFont(title_font)
        vbox.Add(title, flag=wx.ALL, border=10)

        desc = wx.StaticText(
            self,
            label="The AI parsed your natural language query into the following conditions and JAQueL query.",
        )
        vbox.Add(desc, flag=wx.LEFT | wx.RIGHT | wx.BOTTOM, border=10)

        # Conditions section
        cond_label = wx.StaticText(self, label="Extracted Conditions:")
        cond_label_font = cond_label.GetFont()
        cond_label_font.SetWeight(wx.FONTWEIGHT_BOLD)
        cond_label.SetFont(cond_label_font)
        vbox.Add(cond_label, flag=wx.LEFT | wx.RIGHT | wx.TOP, border=10)

        self._cond_list = wx.ListCtrl(
            self,
            style=wx.LC_REPORT | wx.LC_SINGLE_SEL | wx.BORDER_SUNKEN,
        )
        self._cond_list.AppendColumn("Entity", width=150)
        self._cond_list.AppendColumn("Attribute", width=150)
        self._cond_list.AppendColumn("Operator", width=80)
        self._cond_list.AppendColumn("Value", width=350)

        for i, cond in enumerate(self._conditions):
            idx = self._cond_list.InsertItem(i, cond.get("entity", ""))
            self._cond_list.SetItem(idx, 1, cond.get("attr", ""))
            self._cond_list.SetItem(idx, 2, cond.get("op", ""))
            val = cond.get("val", "")
            val_str = json.dumps(val) if isinstance(val, (list, dict)) else str(val)
            self._cond_list.SetItem(idx, 3, val_str)

        vbox.Add(
            self._cond_list,
            proportion=1,
            flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM,
            border=10,
        )

        # JAQueL section
        jaquel_label = wx.StaticText(self, label="Generated JAQueL Query:")
        jaquel_label_font = jaquel_label.GetFont()
        jaquel_label_font.SetWeight(wx.FONTWEIGHT_BOLD)
        jaquel_label.SetFont(jaquel_label_font)
        vbox.Add(jaquel_label, flag=wx.LEFT | wx.RIGHT | wx.TOP, border=10)

        self._jaquel_text = wx.TextCtrl(
            self,
            value=json.dumps(self._jaquel, indent=2),
            style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_DONTWRAP,
        )
        # Use monospace font for JSON
        font = wx.Font(
            9,
            wx.FONTFAMILY_TELETYPE,
            wx.FONTSTYLE_NORMAL,
            wx.FONTWEIGHT_NORMAL,
        )
        self._jaquel_text.SetFont(font)
        vbox.Add(
            self._jaquel_text,
            proportion=1,
            flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM,
            border=10,
        )

        # Buttons
        btn_sizer = wx.StdDialogButtonSizer()
        btn_apply = wx.Button(self, wx.ID_OK, "Apply to Editor")
        btn_apply.SetDefault()
        btn_cancel = wx.Button(self, wx.ID_CANCEL, "Cancel")
        btn_sizer.AddButton(btn_apply)
        btn_sizer.AddButton(btn_cancel)
        btn_sizer.Realize()
        vbox.Add(btn_sizer, flag=wx.ALL | wx.ALIGN_CENTER, border=10)

        self.SetSizer(vbox)
