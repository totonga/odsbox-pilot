"""ConditionDialog — modal wx.Dialog for adding or editing a filter condition."""

from __future__ import annotations

from typing import Any

import wx  # type: ignore[import-untyped]
from odsbox.proto import ods

from odsbox_pilot import styles
from odsbox_pilot.browse.filter_tree import FilterTree

_OPERATORS: list[str] = ["$like", "$eq", "$gt", "$lt", "$gte", "$lte"]

_NUMERIC_TYPES: frozenset[int] = frozenset(
    {
        ods.DT_LONG,
        ods.DT_LONGLONG,
        ods.DT_FLOAT,
        ods.DT_DOUBLE,
        ods.DT_SHORT,
        ods.DT_DATE,
    }
)


class ConditionDialog(wx.Dialog):
    """Dialog for adding or editing a single filter condition.

    Pass *existing* (a dict with keys ``entity``, ``attr``, ``op``, ``val``) to
    pre-fill all fields for editing.  Returns ``None`` on Cancel, or the same
    four-key dict on OK.
    """

    def __init__(
        self,
        parent: wx.Window,
        mc: Any,
        con_i: Any,
        existing: dict[str, Any] | None = None,
    ) -> None:
        title = "Edit Condition" if existing else "Add Condition"
        super().__init__(parent, title=title, style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        styles.apply_scaled_app_font(self)
        self._mc = mc
        self._con_i = con_i
        self._result: dict[str, Any] | None = None
        self._build_ui()
        if existing:
            self._prefill(existing)
        self.Fit()
        self.SetMinSize(self.FromDIP(wx.Size(380, 200)))
        self.Centre(wx.BOTH)

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        grid = wx.FlexGridSizer(rows=4, cols=2, vgap=6, hgap=8)
        grid.AddGrowableCol(1)

        # Entity
        grid.Add(wx.StaticText(self, label="Entity:"), flag=wx.ALIGN_CENTER_VERTICAL)
        entities = sorted(self._mc.model().entities.keys())
        self._entity_cb = wx.ComboBox(
            self, choices=entities, style=wx.CB_READONLY, size=self.FromDIP(wx.Size(220, -1))
        )
        self._entity_cb.Bind(wx.EVT_COMBOBOX, self._on_entity_changed)
        grid.Add(self._entity_cb, flag=wx.EXPAND)

        # Attribute
        grid.Add(wx.StaticText(self, label="Attribute:"), flag=wx.ALIGN_CENTER_VERTICAL)
        self._attr_cb = wx.ComboBox(self, choices=[], size=self.FromDIP(wx.Size(220, -1)))
        grid.Add(self._attr_cb, flag=wx.EXPAND)

        # Operator
        grid.Add(wx.StaticText(self, label="Operator:"), flag=wx.ALIGN_CENTER_VERTICAL)
        self._op_cb = wx.ComboBox(
            self, choices=_OPERATORS, style=wx.CB_READONLY, size=self.FromDIP(wx.Size(100, -1))
        )
        self._op_cb.SetSelection(0)
        grid.Add(self._op_cb, flag=wx.ALIGN_LEFT)

        # Value + "…" button
        grid.Add(wx.StaticText(self, label="Value:"), flag=wx.ALIGN_CENTER_VERTICAL)
        val_row = wx.BoxSizer(wx.HORIZONTAL)
        self._val_tc = wx.TextCtrl(self, value="*")
        val_row.Add(self._val_tc, proportion=1, flag=wx.EXPAND)
        ellipsis_btn = wx.Button(self, label="\u2026", size=self.FromDIP(wx.Size(28, -1)))
        ellipsis_btn.Bind(wx.EVT_BUTTON, self._on_discover)
        val_row.Add(ellipsis_btn, flag=wx.LEFT, border=4)
        grid.Add(val_row, flag=wx.EXPAND)

        # Buttons
        btn_sizer = wx.StdDialogButtonSizer()
        ok_btn = wx.Button(self, wx.ID_OK)
        ok_btn.SetDefault()
        btn_sizer.AddButton(ok_btn)
        btn_sizer.AddButton(wx.Button(self, wx.ID_CANCEL))
        btn_sizer.Realize()
        ok_btn.Bind(wx.EVT_BUTTON, self._on_ok)

        outer = wx.BoxSizer(wx.VERTICAL)
        outer.Add(grid, flag=wx.EXPAND | wx.ALL, border=12)
        outer.Add(btn_sizer, flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, border=8)
        self.SetSizer(outer)

    def _prefill(self, existing: dict[str, Any]) -> None:
        entity = existing.get("entity", "")
        if entity:
            self._entity_cb.SetValue(entity)
            self._populate_attrs(entity)
        attr = existing.get("attr", "")
        if attr:
            self._attr_cb.SetValue(attr)
        op = existing.get("op", "$like")
        if op in _OPERATORS:
            self._op_cb.SetSelection(_OPERATORS.index(op))
        self._val_tc.SetValue(str(existing.get("val", "*")))

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def _on_entity_changed(self, _event: wx.CommandEvent) -> None:  # noqa: ARG002
        self._populate_attrs(self._entity_cb.GetValue())

    def _populate_attrs(self, entity_name: str) -> None:
        try:
            entity = self._mc.entity(entity_name)
        except ValueError:
            return
        attrs = sorted(entity.attributes.keys())
        self._attr_cb.Set(attrs)
        if "name" in attrs:
            self._attr_cb.SetValue("name")

    def _on_discover(self, _event: wx.CommandEvent) -> None:  # noqa: ARG002
        entity_name = self._entity_cb.GetValue().strip()
        attr = self._attr_cb.GetValue().strip()
        if not entity_name or not attr:
            wx.MessageBox(
                "Select an entity and attribute first.",
                "Discover values",
                wx.OK | wx.ICON_INFORMATION,
                self,
            )
            return
        dlg = DiscoverDialog(self, self._mc, self._con_i, entity_name, attr)
        if dlg.ShowModal() == wx.ID_OK and dlg.selected_value is not None:
            self._val_tc.SetValue(str(dlg.selected_value))
        dlg.Destroy()

    def _on_ok(self, _event: wx.CommandEvent) -> None:  # noqa: ARG002
        entity = self._entity_cb.GetValue().strip()
        attr = self._attr_cb.GetValue().strip()
        op = self._op_cb.GetValue().strip()
        val = self._val_tc.GetValue().strip()
        if not entity or not attr or not val:
            wx.MessageBox(
                "Fill in entity, attribute, and value.",
                "Incomplete",
                wx.OK | wx.ICON_WARNING,
                self,
            )
            return
        if op not in _OPERATORS:
            wx.MessageBox(
                "Select a valid operator.",
                "Invalid operator",
                wx.OK | wx.ICON_WARNING,
                self,
            )
            return
        self._result = {"entity": entity, "attr": attr, "op": op, "val": val}
        self.EndModal(wx.ID_OK)

    @property
    def result(self) -> dict[str, Any] | None:
        return self._result


class DiscoverDialog(wx.Dialog):
    """Queries distinct values or min/max for an attribute and lets the user pick one."""

    def __init__(
        self,
        parent: wx.Window,
        mc: Any,
        con_i: Any,
        entity_name: str,
        attr: str,
    ) -> None:
        super().__init__(
            parent,
            title=f"Values \u2014 {entity_name}.{attr}",
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
            size=(380, 400),
        )
        styles.apply_scaled_app_font(self)
        self.SetSize(self.FromDIP(wx.Size(380, 400)))
        self._mc = mc
        self._con_i = con_i
        self._entity_name = entity_name
        self._attr = attr
        self.selected_value: Any = None
        self._raw_values: list[Any] = []
        self._build_ui()
        self.Centre(wx.BOTH)

    def _build_ui(self) -> None:
        is_numeric = self._is_numeric()
        vbox = wx.BoxSizer(wx.VERTICAL)

        header = wx.StaticText(self, label=f"{self._entity_name}.{self._attr}")
        header.SetFont(styles.bold_font(header))
        vbox.Add(header, flag=wx.ALL, border=10)

        if is_numeric:
            self._build_numeric_ui(vbox)
        else:
            self._build_discrete_ui(vbox)

        close_btn = wx.Button(self, wx.ID_CANCEL, label="Close")
        vbox.Add(close_btn, flag=wx.ALIGN_CENTER | wx.BOTTOM, border=8)
        self.SetSizer(vbox)

    def _is_numeric(self) -> bool:
        try:
            attr_obj = self._mc.entity(self._entity_name).attributes.get(self._attr)
        except ValueError:
            return False
        return attr_obj is not None and attr_obj.data_type in _NUMERIC_TYPES

    def _build_numeric_ui(self, vbox: wx.BoxSizer) -> None:
        wx.BeginBusyCursor()
        try:
            ft = FilterTree(self._mc)
            min_val, max_val = ft.min_max(self._con_i, self._entity_name, self._attr)
        except Exception as exc:
            wx.EndBusyCursor()
            wx.MessageBox(str(exc), "Discovery error", wx.OK | wx.ICON_ERROR, self)
            return
        wx.EndBusyCursor()

        box = wx.StaticBox(self, label="Range")
        bsizer = wx.StaticBoxSizer(box, wx.VERTICAL)
        bsizer.Add(wx.StaticText(self, label=f"Min:  {min_val}"), flag=wx.ALL, border=4)
        bsizer.Add(wx.StaticText(self, label=f"Max:  {max_val}"), flag=wx.ALL, border=4)
        vbox.Add(bsizer, flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, border=10)

        btn_row = wx.BoxSizer(wx.HORIZONTAL)
        min_btn = wx.Button(self, label="Use Min")
        max_btn = wx.Button(self, label="Use Max")
        btn_row.Add(min_btn, flag=wx.RIGHT, border=4)
        btn_row.Add(max_btn)
        vbox.Add(btn_row, flag=wx.ALIGN_CENTER | wx.BOTTOM, border=6)

        def _use_min(_e: wx.Event) -> None:
            self.selected_value = min_val
            self.EndModal(wx.ID_OK)

        def _use_max(_e: wx.Event) -> None:
            self.selected_value = max_val
            self.EndModal(wx.ID_OK)

        min_btn.Bind(wx.EVT_BUTTON, _use_min)
        max_btn.Bind(wx.EVT_BUTTON, _use_max)

    def _build_discrete_ui(self, vbox: wx.BoxSizer) -> None:
        wx.BeginBusyCursor()
        try:
            ft = FilterTree(self._mc)
            values = ft.distinct(self._con_i, self._entity_name, self._attr)
        except Exception as exc:
            wx.EndBusyCursor()
            wx.MessageBox(str(exc), "Discovery error", wx.OK | wx.ICON_ERROR, self)
            return
        wx.EndBusyCursor()

        self._raw_values = values
        display = [str(v) for v in values[:200]]
        if len(values) > 200:
            display.append(f"\u2026 {len(values) - 200} more")

        box = wx.StaticBox(self, label=f"Distinct Values ({len(values)})")
        bsizer = wx.StaticBoxSizer(box, wx.VERTICAL)
        self._listbox = wx.ListBox(self, choices=display, style=wx.LB_SINGLE)
        bsizer.Add(self._listbox, proportion=1, flag=wx.EXPAND | wx.ALL, border=4)
        vbox.Add(bsizer, proportion=1, flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, border=10)

        use_btn = wx.Button(self, label="Use Selected")
        use_btn.Bind(wx.EVT_BUTTON, self._on_use_selected)
        vbox.Add(use_btn, flag=wx.ALIGN_CENTER | wx.BOTTOM, border=6)

    def _on_use_selected(self, _event: wx.CommandEvent) -> None:  # noqa: ARG002
        idx = self._listbox.GetSelection()
        if idx == wx.NOT_FOUND or idx >= len(self._raw_values):
            return
        self.selected_value = self._raw_values[idx]
        self.EndModal(wx.ID_OK)
