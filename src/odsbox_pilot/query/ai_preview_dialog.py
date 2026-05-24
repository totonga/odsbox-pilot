"""Preview dialog for AI-generated query conditions."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

import wx  # type: ignore[import-untyped]

_COL_INVALID = wx.Colour(255, 220, 220)  # light red background for invalid rows

_JAQUEL_OPERATORS = [
    "$eq",
    "$ne",
    "$lt",
    "$lte",
    "$gt",
    "$gte",
    "$like",
    "$notlike",
    "$between",
    "$in",
]

# Column widths: entity, attribute, operator, value
_COL_W = (140, 125, 90, 195)


class AiPreviewDialog(wx.Dialog):
    """Dialog to review and edit AI-parsed conditions before applying.

    Valid and invalid conditions are shown together with editable dropdowns
    for entity, attribute, and operator.  Invalid rows are highlighted in red.
    The JAQueL preview updates live as conditions are edited or removed.
    """

    def __init__(
        self,
        parent: wx.Window,
        conditions: list[dict[str, Any]],
        jaquel: dict[str, Any],
        invalid_conditions: list[dict[str, Any]] | None = None,
        rebuild_query: Callable[[list[dict[str, Any]]], dict[str, Any]] | None = None,
    ) -> None:
        """Initialize the preview dialog.

        Args:
            parent: Parent window.
            conditions: Valid condition dicts (entity, attr, op, val).
            jaquel: Initially generated JAQueL query dict.
            invalid_conditions: Conditions the LLM produced that could not be
                resolved.  Each dict may carry a ``"reason"`` key.
            rebuild_query: Optional callable that, given a flat list of
                condition dicts, returns a fresh JAQueL dict.  When provided,
                the query preview updates live on every edit or removal.
        """
        super().__init__(
            parent,
            title="AI Query Preview",
            size=(920, 680),
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
        )
        # Merge all conditions; invalid ones carry "_invalid": True
        self._all_conditions: list[dict[str, Any]] = [
            *[dict(c) for c in conditions],
            *[{**c, "_invalid": True} for c in (invalid_conditions or [])],
        ]
        self._jaquel = dict(jaquel)
        self._rebuild_query = rebuild_query
        self._build_ui()
        self.Centre()

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    def get_jaquel(self) -> dict[str, Any]:
        """Return the (possibly updated) JAQueL query."""
        return self._jaquel

    def get_conditions(self) -> list[dict[str, Any]]:
        """Return all remaining conditions (internal flags stripped)."""
        return [{k: v for k, v in c.items() if not k.startswith("_")} for c in self._all_conditions]

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        vbox = wx.BoxSizer(wx.VERTICAL)

        # Title
        title = wx.StaticText(self, label="Review AI-Generated Query")
        title_font = title.GetFont()
        title_font.SetPointSize(title_font.GetPointSize() + 2)
        title_font.SetWeight(wx.FONTWEIGHT_BOLD)
        title.SetFont(title_font)
        vbox.Add(title, flag=wx.ALL, border=10)

        desc = wx.StaticText(
            self,
            label="Edit or remove conditions below. The JAQueL query updates automatically.",
        )
        vbox.Add(desc, flag=wx.LEFT | wx.RIGHT | wx.BOTTOM, border=10)

        # Conditions header label
        cond_label = wx.StaticText(self, label="Extracted Conditions:")
        cond_label_font = cond_label.GetFont()
        cond_label_font.SetWeight(wx.FONTWEIGHT_BOLD)
        cond_label.SetFont(cond_label_font)
        vbox.Add(cond_label, flag=wx.LEFT | wx.RIGHT | wx.TOP, border=10)

        # Scrollable conditions area
        self._scroll = wx.ScrolledWindow(self, style=wx.VSCROLL | wx.BORDER_SUNKEN)
        self._scroll.SetScrollRate(0, 20)
        self._rows_sizer = wx.BoxSizer(wx.VERTICAL)

        # Column header row
        self._rows_sizer.Add(
            self._make_header_row(self._scroll),
            flag=wx.EXPAND | wx.BOTTOM,
            border=2,
        )

        # Data rows (valid first, then invalid)
        any_invalid = any(c.get("_invalid") for c in self._all_conditions)
        for cond in self._all_conditions:
            self._rows_sizer.Add(
                self._make_condition_row(self._scroll, cond),
                flag=wx.EXPAND,
            )

        if any_invalid:
            note = wx.StaticText(
                self._scroll,
                label="\u26a0 Red rows could not be resolved \u2014 edit to fix or remove.",
            )
            note_font = note.GetFont()
            note_font.SetStyle(wx.FONTSTYLE_ITALIC)
            note.SetFont(note_font)
            note.SetForegroundColour(wx.Colour(140, 0, 0))
            self._rows_sizer.Add(note, flag=wx.LEFT | wx.TOP | wx.BOTTOM, border=6)

        self._scroll.SetSizer(self._rows_sizer)
        vbox.Add(
            self._scroll, proportion=1, flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, border=10
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
        mono_font = wx.Font(9, wx.FONTFAMILY_TELETYPE, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL)
        self._jaquel_text.SetFont(mono_font)
        vbox.Add(
            self._jaquel_text,
            proportion=1,
            flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM,
            border=10,
        )

        # Dialog buttons
        btn_sizer = wx.StdDialogButtonSizer()
        btn_apply = wx.Button(self, wx.ID_OK, "Apply to Editor")
        btn_apply.SetDefault()
        btn_cancel = wx.Button(self, wx.ID_CANCEL, "Cancel")
        btn_sizer.AddButton(btn_apply)
        btn_sizer.AddButton(btn_cancel)
        btn_sizer.Realize()
        vbox.Add(btn_sizer, flag=wx.ALL | wx.ALIGN_CENTER, border=10)

        self.SetSizer(vbox)

    # ------------------------------------------------------------------
    # Row factories
    # ------------------------------------------------------------------

    def _make_header_row(self, parent: wx.Window) -> wx.Panel:
        row = wx.Panel(parent)
        sizer = wx.BoxSizer(wx.HORIZONTAL)
        for label, width in zip(("Entity", "Attribute", "Operator", "Value"), _COL_W, strict=False):
            txt = wx.StaticText(row, label=label, size=(width, -1))
            f = txt.GetFont()
            f.SetWeight(wx.FONTWEIGHT_BOLD)
            txt.SetFont(f)
            sizer.Add(txt, flag=wx.LEFT | wx.ALIGN_CENTER_VERTICAL, border=4)
        sizer.Add((90, 0))  # spacer for remove button column
        row.SetSizer(sizer)
        return row

    def _make_condition_row(self, parent: wx.Window, cond: dict[str, Any]) -> wx.Panel:
        invalid = bool(cond.get("_invalid"))
        row = wx.Panel(parent)
        if invalid:
            row.SetBackgroundColour(_COL_INVALID)

        sizer = wx.BoxSizer(wx.HORIZONTAL)

        # Unique entity names across all conditions for the dropdown
        entity_choices = sorted(
            {c.get("entity", "") for c in self._all_conditions if c.get("entity", "")}
        )

        # ── Entity (ComboBox: dropdown + freetext) ───────────────────────
        entity_cb = wx.ComboBox(
            row,
            value=cond.get("entity", ""),
            choices=entity_choices,
            size=(_COL_W[0], -1),
            style=wx.CB_DROPDOWN,
        )
        if invalid:
            entity_cb.SetBackgroundColour(_COL_INVALID)
            entity_cb.SetForegroundColour(wx.Colour(140, 0, 0))

        # ── Attribute (TextCtrl) ─────────────────────────────────────────
        attr_tc = wx.TextCtrl(row, value=cond.get("attr", ""), size=(_COL_W[1], -1))
        if invalid:
            attr_tc.SetBackgroundColour(_COL_INVALID)
            attr_tc.SetForegroundColour(wx.Colour(140, 0, 0))

        # ── Operator (Choice) ────────────────────────────────────────────
        current_op = cond.get("op", "$eq")
        op_choices = list(_JAQUEL_OPERATORS)
        if current_op not in op_choices:
            op_choices.insert(0, current_op)
        op_choice = wx.Choice(row, choices=op_choices, size=(_COL_W[2], -1))
        op_choice.SetSelection(op_choices.index(current_op))
        if invalid:
            op_choice.SetBackgroundColour(_COL_INVALID)

        # ── Value (TextCtrl) ─────────────────────────────────────────────
        val_raw = cond.get("val", "")
        val_str = json.dumps(val_raw) if isinstance(val_raw, (list, dict)) else str(val_raw)
        val_tc = wx.TextCtrl(row, value=val_str, size=(_COL_W[3], -1))
        if invalid:
            val_tc.SetBackgroundColour(_COL_INVALID)
            val_tc.SetForegroundColour(wx.Colour(140, 0, 0))

        for widget in (entity_cb, attr_tc, op_choice, val_tc):
            sizer.Add(widget, flag=wx.LEFT | wx.ALIGN_CENTER_VERTICAL, border=4)

        # ── Remove button ────────────────────────────────────────────────
        btn_remove = wx.Button(row, label="\u2715 Remove", size=(85, -1))
        reason = cond.get("reason", "")
        btn_remove.SetToolTip(reason if reason else "Remove this condition")
        if invalid:
            btn_remove.SetBackgroundColour(wx.Colour(200, 60, 60))
            btn_remove.SetForegroundColour(wx.WHITE)
        sizer.Add(btn_remove, flag=wx.LEFT | wx.ALIGN_CENTER_VERTICAL, border=6)

        row.SetSizer(sizer)

        # ── Bindings ─────────────────────────────────────────────────────
        def _on_change(_evt: wx.Event) -> None:
            cond["entity"] = entity_cb.GetValue()
            cond["attr"] = attr_tc.GetValue()
            sel = op_choice.GetSelection()
            if sel != wx.NOT_FOUND:
                cond["op"] = op_choices[sel]
            raw_val = val_tc.GetValue()
            try:
                cond["val"] = json.loads(raw_val)
            except json.JSONDecodeError, ValueError:
                cond["val"] = raw_val
            self._refresh_jaquel()

        entity_cb.Bind(wx.EVT_TEXT, _on_change)
        entity_cb.Bind(wx.EVT_COMBOBOX, _on_change)
        attr_tc.Bind(wx.EVT_TEXT, _on_change)
        op_choice.Bind(wx.EVT_CHOICE, _on_change)
        val_tc.Bind(wx.EVT_TEXT, _on_change)
        btn_remove.Bind(wx.EVT_BUTTON, lambda _evt, r=row, c=cond: self._on_remove(r, c))

        return row

    # ------------------------------------------------------------------
    # Live refresh / remove
    # ------------------------------------------------------------------

    def _refresh_jaquel(self) -> None:
        """Rebuild JAQueL from the current condition list and update the text box."""
        if self._rebuild_query is None:
            return
        try:
            clean = [
                {k: v for k, v in c.items() if not k.startswith("_")} for c in self._all_conditions
            ]
            self._jaquel = self._rebuild_query(clean)
            self._jaquel_text.SetValue(json.dumps(self._jaquel, indent=2))
        except Exception as exc:
            self._jaquel_text.SetValue(f"// Error rebuilding query:\n// {exc}")

    def _on_remove(self, row: wx.Panel, cond: dict[str, Any]) -> None:
        """Remove a condition row and refresh the query."""
        if cond in self._all_conditions:
            self._all_conditions.remove(cond)
        row.Hide()
        self._rows_sizer.Detach(row)
        row.Destroy()
        self._scroll.Layout()
        self._scroll.FitInside()
        self._refresh_jaquel()
