"""BrowsePanel — wxPython panel for interactive FilterTree browsing.

Designed to live as a tab page inside ``MainFrame``'s ``wx.Notebook``.
The two standalone helpers ``_load_conditions`` and ``_save_conditions`` at
the bottom of this module have no wx dependency and are unit-testable
without a running wx.App.
"""

from __future__ import annotations

import contextlib
import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import wx  # type: ignore[import-untyped]
from odsbox.proto import ods

from odsbox_pilot.browse._helpers import (
    _build_filter_nodes,
    _entity_colour,
    _entity_colour_light,
    _entity_icon,
    _load_conditions,
    _load_prefs,
    _ods_type_symbol,
    _save_conditions,
    _save_prefs,
)
from odsbox_pilot.browse.filter_tree import FilterNode, FilterTree


@dataclass
class _InstanceData:
    """Data stored on entity-instance tree nodes."""

    entity: str
    instance_id: int


@dataclass
class _RelMetaData:
    """Data stored on relation-meta tree nodes."""

    parent_entity: str
    parent_id: int
    rel_name: str
    target_entity: str


class BrowsePanel(wx.Panel):
    """wxPython panel for browsing an ASAM ODS server via FilterTree queries.

    Args:
        parent: The parent widget (typically a ``wx.Notebook``).
        con_i: Active ODS connection (``ConI`` instance).
        log_fn: Optional ``(message: str, ok: bool) -> None`` callback for
            writing to the shared query log in ``MainFrame``.
        status_fn: Optional ``(message: str) -> None`` callback for updating
            the ``MainFrame`` status bar.
    """

    def __init__(
        self,
        parent: wx.Window,
        con_i: Any,
        *,
        log_fn: Callable[[str, bool], None] | None = None,
        status_fn: Callable[[str], None] | None = None,
    ) -> None:
        super().__init__(parent)
        self._con_i = con_i
        self._mc: Any = con_i.mc
        self._log_fn = log_fn
        self._status_fn = status_fn
        self._ft: FilterTree = FilterTree(self._mc)
        self._saved_conditions: list[dict[str, Any]] = []
        self._nodes: list[FilterNode] = []
        self._closing = False
        self.Bind(wx.EVT_WINDOW_DESTROY, self._on_destroy)
        self._build_ui()
        self._load_and_rebuild()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def trigger_initial_query(self) -> None:
        """Run the initial query if the result tree is still empty."""
        if not self._closing and self._tree.GetChildrenCount(self._root) == 0:
            self._on_query(None)

    def clear_connection(self) -> None:
        """Disable controls and clear the tree before the connection is closed."""
        self._closing = True
        for btn in (
            self._query_btn,
            self._add_btn,
            self._edit_btn,
            self._remove_btn,
            self._clear_btn,
        ):
            btn.Disable()
        self._tree.DeleteChildren(self._root)
        self._props_list.DeleteAllItems()
        self._props_header.SetLabel("Properties")
        self._preview.SetValue("")
        self._clear_values_display("Disconnected")
        self._status("Disconnected")

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        # Style objects for tree node colouring
        self._instance_colour = wx.SystemSettings.GetColour(wx.SYS_COLOUR_WINDOWTEXT)
        self._relation_colour = wx.Colour(80, 100, 140)
        self._relation_font = self.GetFont()
        self._relation_font.SetStyle(wx.FONTSTYLE_ITALIC)

        vbox = wx.BoxSizer(wx.VERTICAL)
        vbox.Add(self._build_toolbar(), flag=wx.EXPAND | wx.ALL, border=4)
        self._cond_pane = self._build_conditions_section()
        vbox.Add(
            self._cond_pane,
            flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM,
            border=4,
        )
        self._splitter = wx.SplitterWindow(self, style=wx.SP_LIVE_UPDATE)
        self._build_tree(self._splitter)
        props_panel = self._build_props_panel(self._splitter)
        self._splitter.SetSashGravity(2.0 / 3.0)
        self._splitter.SplitVertically(self._tree, props_panel, sashPosition=600)
        wx.CallAfter(self._set_initial_sash)
        # Vertical splitter: top = tree/props, bottom = preview notebook
        self._v_splitter = wx.SplitterWindow(self, style=wx.SP_LIVE_UPDATE | wx.SP_3DSASH)
        self._splitter.Reparent(self._v_splitter)
        self._preview_nb = self._build_preview_notebook(self._v_splitter)
        self._v_splitter.SplitHorizontally(self._splitter, self._preview_nb, sashPosition=400)
        self._v_splitter.SetMinimumPaneSize(80)
        self._v_splitter.SetSashGravity(1.0)
        vbox.Add(self._v_splitter, proportion=1, flag=wx.EXPAND | wx.LEFT | wx.RIGHT, border=4)
        self.SetSizer(vbox)
        _saved_page = _load_prefs().get("preview_page", 0)
        if _saved_page < self._preview_nb.GetPageCount():
            wx.CallAfter(self._preview_nb.SetSelection, _saved_page)
        wx.CallAfter(self._set_initial_vsash)
        wx.CallAfter(self._initial_canvas_draw)
        if _load_prefs().get("cond_collapsed", False):
            wx.CallAfter(self._cond_body.Hide)
            wx.CallAfter(self._update_cond_toggle)
            wx.CallAfter(self.Layout)

    def _set_initial_sash(self) -> None:
        w = self._splitter.GetClientSize().width
        if w > 0:
            self._splitter.SetSashPosition(int(w * 2 / 3))

    def _set_initial_vsash(self) -> None:
        h = self._v_splitter.GetClientSize().height
        if h > 0:
            self._v_splitter.SetSashPosition(max(80, h - 220))

    def _initial_canvas_draw(self) -> None:
        """Force the matplotlib canvas to render at its actual laid-out size."""
        if getattr(self, "_values_canvas_type", None) == "matplotlib":
            w, h = self._values_display.GetClientSize()
            dpi = self._values_fig.get_dpi()
            if w > 0 and h > 0:
                self._values_fig.set_size_inches(w / dpi, h / dpi, forward=False)
            self._values_display.draw_idle()

    def _on_destroy(self, event: wx.WindowDestroyEvent) -> None:
        if event.GetEventObject() is self:
            self._closing = True
        event.Skip()

    def _build_toolbar(self) -> wx.Sizer:
        hbox = wx.BoxSizer(wx.HORIZONTAL)
        hbox.Add(
            wx.StaticText(self, label="Root entity:"),
            flag=wx.ALIGN_CENTER_VERTICAL | wx.RIGHT,
            border=4,
        )
        # Build entity choices with base name suffix, sorted case-insensitively
        entity_objs = list(self._mc.model().entities.values())
        entity_objs.sort(key=lambda e: e.name.lower())
        choices = [f"{e.name} - {e.base_name}" for e in entity_objs]
        
        self._root_combo = wx.ComboBox(self, choices=choices, style=wx.CB_READONLY, size=(220, -1))
        
        # Preselect AoTest-derived entity, fallback to Project, then first entity
        selected = None
        aotest_entities = [e for e in entity_objs if e.base_name == "AoTest"]
        aosubtest_entities = [e for e in entity_objs if e.base_name == "AoSubTest"]
        
        if aotest_entities:
            selected = f"{aotest_entities[0].name} - {aotest_entities[0].base_name}"
        elif aosubtest_entities:
            selected = f"{aosubtest_entities[0].name} - {aosubtest_entities[0].base_name}"
        elif any(e.name == "Project" for e in entity_objs):
            project_entity = next(e for e in entity_objs if e.name == "Project")
            selected = f"{project_entity.name} - {project_entity.base_name}"
        elif entity_objs:
            selected = choices[0]
        
        if selected:
            self._root_combo.SetValue(selected)
        
        self._root_combo.Bind(wx.EVT_COMBOBOX, self._on_root_changed)
        hbox.Add(self._root_combo, flag=wx.RIGHT, border=8)
        self._query_btn = wx.Button(self, label="Query")
        self._query_btn.Bind(wx.EVT_BUTTON, self._on_query)
        hbox.Add(self._query_btn)
        return hbox

    def _build_conditions_section(self) -> wx.Panel:
        outer = wx.Panel(self)
        vbox = wx.BoxSizer(wx.VERTICAL)

        # ── header row with toggle button ─────────────────────────────────
        hdr = wx.BoxSizer(wx.HORIZONTAL)
        self._cond_toggle = wx.Button(
            outer, label="▼  Filter Conditions", style=wx.BU_LEFT | wx.BORDER_NONE
        )
        self._cond_toggle.Bind(wx.EVT_BUTTON, self._on_cond_toggle)
        hdr.Add(self._cond_toggle, proportion=1, flag=wx.EXPAND)
        vbox.Add(hdr, flag=wx.EXPAND | wx.BOTTOM, border=2)

        # ── collapsible body ──────────────────────────────────────────────
        self._cond_body = wx.Panel(outer)
        body_hbox = wx.BoxSizer(wx.HORIZONTAL)

        self._cond_list = wx.ListCtrl(
            self._cond_body,
            style=wx.LC_REPORT | wx.LC_SINGLE_SEL | wx.BORDER_SUNKEN,
            size=(-1, 90),
        )
        self._cond_list.AppendColumn("Entity", width=140)
        self._cond_list.AppendColumn("Attribute", width=120)
        self._cond_list.AppendColumn("Operator", width=75)
        self._cond_list.AppendColumn("Value", width=140)
        self._cond_list.Bind(wx.EVT_LIST_ITEM_ACTIVATED, self._on_edit_condition)
        body_hbox.Add(self._cond_list, proportion=1, flag=wx.EXPAND | wx.RIGHT, border=4)

        btn_vbox = wx.BoxSizer(wx.VERTICAL)
        self._add_btn = wx.Button(self._cond_body, label="Add")
        self._edit_btn = wx.Button(self._cond_body, label="Edit")
        self._remove_btn = wx.Button(self._cond_body, label="Remove")
        self._clear_btn = wx.Button(self._cond_body, label="Clear")
        for btn in (self._add_btn, self._edit_btn, self._remove_btn, self._clear_btn):
            btn_vbox.Add(btn, flag=wx.EXPAND | wx.BOTTOM, border=3)
        self._add_btn.Bind(wx.EVT_BUTTON, self._on_add_condition)
        self._edit_btn.Bind(wx.EVT_BUTTON, self._on_edit_condition)
        self._remove_btn.Bind(wx.EVT_BUTTON, self._on_remove_condition)
        self._clear_btn.Bind(wx.EVT_BUTTON, self._on_clear_conditions)
        body_hbox.Add(btn_vbox, flag=wx.LEFT, border=0)

        self._cond_body.SetSizer(body_hbox)
        vbox.Add(self._cond_body, flag=wx.EXPAND)
        outer.SetSizer(vbox)
        return outer

    def _on_cond_toggle(self, _event: wx.CommandEvent) -> None:  # noqa: ARG002
        self._cond_body.Show(not self._cond_body.IsShown())
        self._update_cond_toggle()
        prefs = _load_prefs()
        prefs["cond_collapsed"] = not self._cond_body.IsShown()
        _save_prefs(prefs)
        self.Layout()

    def _update_cond_toggle(self) -> None:
        expanded = self._cond_body.IsShown()
        arrow = "\u25bc" if expanded else "\u25b6"
        if expanded or not self._saved_conditions:
            label = f"{arrow}  Filter Conditions"
        else:
            parts = [
                f"{c.get('entity', '?')}.{c.get('attr', '?')} {c.get('op', '?')} {c.get('val', '')}"
                for c in self._saved_conditions[:2]
            ]
            summary = ",  ".join(parts)
            if len(self._saved_conditions) > 2:
                summary += f"  (+{len(self._saved_conditions) - 2} more)"
            label = f"{arrow}  Filter Conditions  —  {summary}"
        self._cond_toggle.SetLabel(label)

    def _build_tree(self, parent: wx.Window) -> None:
        self._tree = wx.TreeCtrl(
            parent, style=wx.TR_DEFAULT_STYLE | wx.TR_HIDE_ROOT | wx.TR_HAS_BUTTONS
        )
        self._root = self._tree.AddRoot("")
        self._tree.Bind(wx.EVT_TREE_ITEM_EXPANDING, self._on_tree_expanding)
        self._tree.Bind(wx.EVT_TREE_SEL_CHANGED, self._on_tree_sel_changed)

    def _build_props_panel(self, parent: wx.Window) -> wx.Panel:
        panel = wx.Panel(parent)
        vbox = wx.BoxSizer(wx.VERTICAL)
        self._props_header = wx.StaticText(panel, label="Properties")
        font = self._props_header.GetFont()
        font.SetWeight(wx.FONTWEIGHT_BOLD)
        self._props_header.SetFont(font)
        vbox.Add(self._props_header, flag=wx.ALL, border=4)
        self._props_list = wx.ListCtrl(
            panel,
            style=wx.LC_REPORT | wx.LC_SINGLE_SEL | wx.BORDER_SUNKEN,
        )
        self._props_list.AppendColumn("Property", width=200)
        self._props_list.AppendColumn("Value", width=250)
        vbox.Add(
            self._props_list,
            proportion=1,
            flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM,
            border=4,
        )
        panel.SetSizer(vbox)
        return panel

    def _build_preview_notebook(self, parent: wx.Window) -> wx.Notebook:
        """Create the tabbed preview pane: *Jaquel* query and *Values* plot."""
        nb = wx.Notebook(parent)
        nb.SetMinSize((-1, 80))

        # ── Page 0: Jaquel query preview ─────────────────────────────────
        jaquel_panel = wx.Panel(nb)
        jsizer = wx.BoxSizer(wx.VERTICAL)
        self._preview = wx.TextCtrl(
            jaquel_panel,
            style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_DONTWRAP,
        )
        jsizer.Add(self._preview, proportion=1, flag=wx.EXPAND | wx.ALL, border=2)
        jaquel_panel.SetSizer(jsizer)
        nb.AddPage(jaquel_panel, "Jaquel")

        # ── Page 1: Values preview ────────────────────────────────────────
        values_panel = wx.Panel(nb)
        vsizer = wx.BoxSizer(wx.VERTICAL)
        ctrl_row = wx.BoxSizer(wx.HORIZONTAL)
        self._values_enable_cb = wx.CheckBox(values_panel, label="Enable values preview")
        self._values_enable_cb.SetValue(False)
        self._values_enable_cb.Bind(wx.EVT_CHECKBOX, self._on_values_enable_changed)
        ctrl_row.Add(self._values_enable_cb, flag=wx.ALIGN_CENTER_VERTICAL | wx.ALL, border=4)
        vsizer.Add(ctrl_row)
        self._values_display: Any = self._create_values_display(values_panel)
        vsizer.Add(self._values_display, proportion=1, flag=wx.EXPAND | wx.ALL, border=2)
        values_panel.SetSizer(vsizer)
        nb.AddPage(values_panel, "Values")

        nb.Bind(wx.EVT_NOTEBOOK_PAGE_CHANGED, self._on_preview_page_changed)
        return nb

    def _create_values_display(self, parent: wx.Window) -> Any:
        """Create a matplotlib canvas, or a plain TextCtrl fallback if matplotlib is absent."""
        try:
            import matplotlib  # noqa: PLC0415

            with contextlib.suppress(Exception):
                matplotlib.use("WxAgg")
            from matplotlib.backends.backend_wxagg import FigureCanvasWxAgg  # noqa: PLC0415
            from matplotlib.figure import Figure  # noqa: PLC0415

            fig = Figure(tight_layout=True)
            ax = fig.add_subplot(111)
            ax.axis("off")
            ax.text(
                0.5,
                0.5,
                "Select an AoLocalColumn to preview values",
                transform=ax.transAxes,
                ha="center",
                va="center",
                fontsize=9,
                color="gray",
            )
            canvas = FigureCanvasWxAgg(parent, -1, fig)
            self._values_fig = fig
            self._values_ax = ax
            self._values_canvas_type = "matplotlib"
            return canvas
        except Exception:  # noqa: BLE001
            self._values_canvas_type = "text"
            ctrl = wx.TextCtrl(parent, style=wx.TE_MULTILINE | wx.TE_READONLY)
            ctrl.SetValue("Select an AoLocalColumn to preview values")
            self._values_text_ctrl = ctrl
            return ctrl

    def _on_preview_page_changed(self, event: wx.BookCtrlEvent) -> None:
        page = event.GetSelection()
        prefs = _load_prefs()
        prefs["preview_page"] = page
        _save_prefs(prefs)
        if page == 1:
            wx.CallAfter(self._load_values_preview)
        event.Skip()

    def _on_values_enable_changed(self, _event: wx.CommandEvent) -> None:  # noqa: ARG002
        if self._values_enable_cb.GetValue():
            self._load_values_preview()
        else:
            self._clear_values_display("Values preview disabled")

    # ------------------------------------------------------------------
    # Query event handler
    # ------------------------------------------------------------------

    def _on_query(self, _event: wx.CommandEvent) -> None:  # noqa: ARG002
        root = self._get_selected_entity_name()
        if not root:
            return
        _prev_closing = self._closing
        self._closing = True
        self._tree.DeleteChildren(self._root)
        self._closing = _prev_closing
        wx.BeginBusyCursor()
        try:
            q = self._ft.generate_query(root)
            self._show_preview(q)
            df = self._con_i.query(q)
        except Exception as exc:
            wx.EndBusyCursor()
            self._log(f"Browse query error: {exc}", ok=False)
            wx.MessageBox(str(exc), "Query Error", wx.OK | wx.ICON_ERROR, self)
            return
        wx.EndBusyCursor()

        try:
            root_base = self._mc.entity(root).base_name
            root_icon = _entity_icon(root_base)
        except ValueError, AttributeError:
            root_base = ""
            root_icon = _entity_icon("")
        root_colour = _entity_colour(root_base)
        for _, row in df.iterrows():
            instance_id = int(row["id"])
            name = str(row.get("name", "")) or str(instance_id)
            text = f"{root_icon} {name}"
            child = self._tree.AppendItem(self._root, text)
            self._tree.SetItemData(child, _InstanceData(root, instance_id))
            self._tree.SetItemHasChildren(child, True)
            colour = wx.Colour(*root_colour) if root_colour else self._instance_colour
            self._tree.SetItemTextColour(child, colour)

        count = len(df)
        self._status(f"Browse: {count} {root} instance(s)")
        self._log(f"Browse query \u2014 {root}: {count} row(s)")

    # ------------------------------------------------------------------
    # Tree expansion
    # ------------------------------------------------------------------

    def _on_tree_expanding(self, event: wx.TreeEvent) -> None:
        item = event.GetItem()
        # GetFirstChild returns (child, cookie); if child is invalid the item
        # has been declared expandable via SetItemHasChildren but not yet populated.
        first_child, _ = self._tree.GetFirstChild(item)
        if first_child.IsOk():
            return  # already populated, let wx handle normal expansion

        data = self._tree.GetItemData(item)
        if isinstance(data, _InstanceData):
            self._expand_relation_meta(item, data)
        elif isinstance(data, _RelMetaData):
            self._expand_instance_node(item, data)

    def _expand_relation_meta(self, item: wx.TreeItemId, data: _InstanceData) -> None:
        """Insert relation meta-nodes as children of an entity instance node."""
        try:
            entity = self._mc.entity(data.entity)
        except ValueError:
            self._tree.SetItemHasChildren(item, False)
            return
        relations = [rel for _, rel in entity.relations.items() if rel.entity_name]
        relations.sort(key=FilterTree._relation_weight)
        if not relations:
            self._tree.SetItemHasChildren(item, False)
            return
        for rel in relations:
            weight = FilterTree._relation_weight(rel)
            text = f"\u2192 {rel.name}  \u2192  {rel.entity_name}  (w:{weight})"
            child = self._tree.AppendItem(item, text)
            self._tree.SetItemData(
                child,
                _RelMetaData(data.entity, data.instance_id, rel.name, rel.entity_name),
            )
            self._tree.SetItemHasChildren(child, True)
            try:
                rel_base = self._mc.entity(rel.entity_name).base_name
            except ValueError, AttributeError:
                rel_base = ""
            rel_rgb = _entity_colour_light(rel_base)
            rel_colour = wx.Colour(*rel_rgb) if rel_rgb else self._relation_colour
            self._tree.SetItemTextColour(child, rel_colour)
            self._tree.SetItemFont(child, self._relation_font)

    def _expand_instance_node(self, item: wx.TreeItemId, data: _RelMetaData) -> None:
        """Follow a relation and insert child entity instances."""
        wx.BeginBusyCursor()
        try:
            q = self._ft.generate_follow_query(
                data.parent_entity, [data.parent_id], data.target_entity
            )
            self._show_preview(q)
            df = self._con_i.query(q)
        except Exception as exc:
            wx.EndBusyCursor()
            self._log(f"Browse follow error: {exc}", ok=False)
            wx.MessageBox(str(exc), "Follow Error", wx.OK | wx.ICON_ERROR, self)
            return
        wx.EndBusyCursor()

        if df.empty:
            self._tree.SetItemHasChildren(item, False)
        try:
            target_base = self._mc.entity(data.target_entity).base_name
            target_icon = _entity_icon(target_base)
        except ValueError, AttributeError:
            target_base = ""
            target_icon = _entity_icon("")
        target_colour = _entity_colour(target_base)
        for _, row in df.iterrows():
            instance_id = int(row["id"])
            name = str(row.get("name", "")) or str(instance_id)
            text = f"{target_icon} {name}"
            child = self._tree.AppendItem(item, text)
            self._tree.SetItemData(child, _InstanceData(data.target_entity, instance_id))
            self._tree.SetItemHasChildren(child, True)
            colour = wx.Colour(*target_colour) if target_colour else self._instance_colour
            self._tree.SetItemTextColour(child, colour)

        count = len(df)
        self._status(f"Browse: {data.parent_entity} \u2192 {data.target_entity}: {count} row(s)")
        self._log(
            f"Browse follow \u2014 {data.parent_entity} \u2192 {data.target_entity}: {count} row(s)"
        )

    # ------------------------------------------------------------------
    # Selection / property panel
    # ------------------------------------------------------------------

    def _on_tree_sel_changed(self, event: wx.TreeEvent) -> None:
        if self._closing:
            return
        item = event.GetItem()
        if not item.IsOk():
            self._props_list.DeleteAllItems()
            self._props_header.SetLabel("Properties")
            self._maybe_load_values()
            return
        data = self._tree.GetItemData(item)
        if isinstance(data, _InstanceData):
            self._show_instance_properties(data.entity, data.instance_id)
        else:
            self._props_list.DeleteAllItems()
            self._props_header.SetLabel("Properties")
        self._maybe_load_values()

    def _show_instance_properties(self, entity: str, instance_id: int) -> None:
        try:
            entity_e: ods.Model.Entity = self._mc.entity(entity)
            q: dict[str, Any] = {entity: {"id": {"$eq": instance_id}}}
            if entity_e.base_name.lower() == "aolocalcolumn":
                attributes: dict[str, int] = {}
                for attr in entity_e.attributes.values():
                    if attr.name.lower() not in ["values", "flags"]:
                        attributes[attr.name] = 1
                for rel in entity_e.relations.values():
                    if rel.range_max == 1:
                        attributes[rel.name] = 1
                q["$attributes"] = attributes
            df = self._con_i.query(q)
        except Exception as exc:
            self._log(f"Properties query error: {exc}", ok=False)
            self._props_list.DeleteAllItems()
            self._props_header.SetLabel("Properties")
            return
        self._props_list.DeleteAllItems()
        self._props_header.SetLabel(f"{entity}  ·  {entity_e.base_name}  [{instance_id}]")
        if df.empty:
            return
        row = df.iloc[0]
        try:
            attr_map = self._mc.entity(entity).attributes
        except ValueError, AttributeError:
            attr_map = {}
        for col in df.columns:
            attr = attr_map.get(col)
            symbol = _ods_type_symbol(attr.data_type) if attr is not None else "\u2192"
            idx = self._props_list.GetItemCount()
            self._props_list.InsertItem(idx, f"{symbol} {col}")
            self._props_list.SetItem(idx, 1, str(row[col]))

    def _maybe_load_values(self) -> None:
        """Trigger a values load only when the Values tab is currently shown."""
        if self._preview_nb.GetSelection() == 1:
            self._load_values_preview()

    def _load_values_preview(self) -> None:
        """Fetch and display AoLocalColumn values in the Values tab."""
        if not self._values_enable_cb.GetValue():
            self._clear_values_display("Values preview disabled \u2014 enable checkbox above")
            return
        sel = self._tree.GetSelection()
        if not sel.IsOk():
            self._clear_values_display("No selection")
            return
        item_data = self._tree.GetItemData(sel)
        if not isinstance(item_data, _InstanceData):
            self._clear_values_display("Select an entity instance node")
            return
        entity, instance_id = item_data.entity, item_data.instance_id
        try:
            base = self._mc.entity(entity).base_name.lower()
        except ValueError, AttributeError:
            base = ""
        if base != "aolocalcolumn":
            self._clear_values_display(
                f"Values only available for AoLocalColumn\n(selected: {entity})"
            )
            return
        wx.BeginBusyCursor()
        try:
            q: dict[str, Any] = {
                entity: {"id": {"$eq": instance_id}},
                "$attributes": {"values": 1},
            }
            df = self._con_i.query(q)
        except Exception as exc:
            wx.EndBusyCursor()
            self._clear_values_display(f"Query error:\n{exc}")
            return
        wx.EndBusyCursor()
        if df.empty:
            self._clear_values_display("No values returned")
            return
        values_col = next((c for c in df.columns if "values" in c.lower()), None)
        if values_col is None:
            self._clear_values_display(
                f"No \u2018values\u2019 column in result: {list(df.columns)}"
            )
            return
        self._render_values(df[values_col].iloc[0], entity, instance_id)

    def _render_values(self, raw: Any, entity: str, instance_id: int) -> None:
        """Plot numeric data as y/index line; display non-numeric values as text."""
        import numpy as np  # noqa: PLC0415

        arr = np.asarray(raw)
        if self._values_canvas_type == "matplotlib":
            self._values_ax.clear()
            if arr.ndim > 0 and np.issubdtype(arr.dtype, np.number):
                self._values_ax.plot(np.arange(len(arr)), arr, linewidth=0.8)
                self._values_ax.tick_params(labelsize=7)
            else:
                self._values_ax.axis("off")
                sample = repr(list(arr[:30]))
                if len(arr) > 30:
                    sample += f"\n\u2026 {len(arr)} total"
                self._values_ax.text(
                    0.5,
                    0.5,
                    sample,
                    transform=self._values_ax.transAxes,
                    ha="center",
                    va="center",
                    fontsize=8,
                )
            self._values_fig.tight_layout(pad=0.3)
            self._values_display.draw()
        else:
            self._values_text_ctrl.SetValue(
                f"{entity} [{instance_id}] \u2014 {len(arr)} values\n{arr!r}"
            )

    def _clear_values_display(self, message: str = "") -> None:
        """Reset the values canvas and show an optional status message."""
        if self._values_canvas_type == "matplotlib":
            self._values_ax.clear()
            self._values_ax.axis("off")
            if message:
                self._values_ax.text(
                    0.5,
                    0.5,
                    message,
                    transform=self._values_ax.transAxes,
                    ha="center",
                    va="center",
                    fontsize=9,
                    color="gray",
                )
            self._values_display.draw()
        else:
            self._values_text_ctrl.SetValue(message)

    # ------------------------------------------------------------------
    # Condition event handlers
    # ------------------------------------------------------------------

    def _on_add_condition(self, _event: wx.Event) -> None:  # noqa: ARG002
        from odsbox_pilot.browse.condition_dialog import ConditionDialog

        dlg = ConditionDialog(self, self._mc, self._con_i)
        if dlg.ShowModal() == wx.ID_OK and dlg.result is not None:
            self._saved_conditions.append(dlg.result)
            self._rebuild_nodes()
            self._save_conditions()
            self._refresh_condition_list()
            self._update_preview()
        dlg.Destroy()

    def _on_edit_condition(self, _event: wx.Event) -> None:  # noqa: ARG002
        idx = self._cond_list.GetFirstSelected()
        if idx == wx.NOT_FOUND:
            return
        from odsbox_pilot.browse.condition_dialog import ConditionDialog

        existing = self._saved_conditions[idx]
        dlg = ConditionDialog(self, self._mc, self._con_i, existing=existing)
        if dlg.ShowModal() == wx.ID_OK and dlg.result is not None:
            self._saved_conditions[idx] = dlg.result
            self._rebuild_nodes()
            self._save_conditions()
            self._refresh_condition_list()
            self._update_preview()
        dlg.Destroy()

    def _on_remove_condition(self, _event: wx.Event) -> None:  # noqa: ARG002
        idx = self._cond_list.GetFirstSelected()
        if idx == wx.NOT_FOUND:
            return
        self._saved_conditions.pop(idx)
        self._rebuild_nodes()
        self._save_conditions()
        self._refresh_condition_list()
        self._update_preview()

    def _on_clear_conditions(self, _event: wx.Event) -> None:  # noqa: ARG002
        self._saved_conditions.clear()
        self._nodes.clear()
        self._ft = FilterTree(self._mc)
        self._save_conditions()
        self._refresh_condition_list()
        self._update_preview()

    def _on_root_changed(self, _event: wx.CommandEvent) -> None:  # noqa: ARG002
        self._update_preview()
    
    def _get_selected_entity_name(self) -> str:
        """Extract entity name from formatted combo selection.
        
        Returns:
            Entity name (without base name suffix)
        """
        value = self._root_combo.GetValue()
        if " - " in value:
            return value.split(" - ", 1)[0]
        return value

    # ------------------------------------------------------------------
    # Condition persistence
    # ------------------------------------------------------------------

    def _load_and_rebuild(self) -> None:
        self._saved_conditions = _load_conditions()
        failed = self._rebuild_nodes()
        self._refresh_condition_list()
        self._update_preview()
        if failed:
            wx.CallAfter(
                wx.MessageBox,
                f"Conditions not restored \u2014 entity not in model: {', '.join(failed)}",
                "Conditions restored with warnings",
                wx.OK | wx.ICON_WARNING,
            )

    def _rebuild_nodes(self) -> list[str]:
        """Re-build ``FilterNode`` list from ``_saved_conditions``.

        Returns:
            List of entity names that were not found in the current model.
        """
        nodes, failed = _build_filter_nodes(self._mc, self._saved_conditions)
        self._nodes = nodes
        self._ft = FilterTree(self._mc, self._nodes)
        return failed

    def _save_conditions(self) -> None:
        _save_conditions(self._saved_conditions)

    def _refresh_condition_list(self) -> None:
        self._cond_list.DeleteAllItems()
        for cond in self._saved_conditions:
            idx = self._cond_list.GetItemCount()
            self._cond_list.InsertItem(idx, cond.get("entity", ""))
            self._cond_list.SetItem(idx, 1, cond.get("attr", ""))
            self._cond_list.SetItem(idx, 2, cond.get("op", ""))
            self._cond_list.SetItem(idx, 3, str(cond.get("val", "")))
        self._update_cond_toggle()

    # ------------------------------------------------------------------
    # Preview helpers
    # ------------------------------------------------------------------

    def _show_preview(self, query: dict[str, Any]) -> None:
        self._preview.SetValue(json.dumps(query, indent=2))

    def _update_preview(self) -> None:
        root = self._get_selected_entity_name()
        if not root:
            self._preview.SetValue("")
            return
        try:
            self._show_preview(self._ft.generate_query(root))
        except Exception as exc:
            self._preview.SetValue(f"Error: {exc}")

    # ------------------------------------------------------------------
    # Logging / status
    # ------------------------------------------------------------------

    def _log(self, message: str, *, ok: bool = True) -> None:
        if self._log_fn is not None:
            self._log_fn(message, ok)

    def _status(self, message: str) -> None:
        if self._status_fn is not None:
            self._status_fn(message)
