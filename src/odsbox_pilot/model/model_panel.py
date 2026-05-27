"""ModelPanel — wxPython panel for browsing the ODS entity-relation model schema.

Designed to live as a tab page inside ``MainFrame``'s ``wx.Notebook``.
The tree shows all entities (sorted by base_name then name) and enumerations.
Entity/relation colouring is reused from the Browse tab.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from typing import Any

import wx  # type: ignore[import-untyped]
from odsbox.proto import ods

from odsbox_pilot.browse._helpers import (
    _entity_colour,
    _entity_colour_light,
    _entity_icon,
    _ods_type_symbol,
)
from odsbox_pilot.model.helpers import _range_str, _rel_range, _rel_type_label
from odsbox_pilot.model.search_index import ModelMatch, ModelSearchIndex

log = logging.getLogger(__name__)

# ------------------------------------------------------------------
# Node data classes — stored via SetItemData / retrieved via GetItemData
# ------------------------------------------------------------------


@dataclass
class _EntityNode:
    entity: ods.Model.Entity


@dataclass
class _AttrGroupNode:
    entity: ods.Model.Entity


@dataclass
class _RelGroupNode:
    entity: ods.Model.Entity


@dataclass
class _AttrNode:
    entity: ods.Model.Entity
    attr: ods.Model.Attribute


@dataclass
class _RelNode:
    entity: ods.Model.Entity
    rel: ods.Model.Relation


@dataclass
class _EnumGroupNode:
    pass


@dataclass
class _EnumNode:
    enum: ods.Model.Enumeration


@dataclass
class _EnumItemNode:
    enum: ods.Model.Enumeration
    item_name: str
    item_index: int


# ------------------------------------------------------------------
# Panel
# ------------------------------------------------------------------


class ModelPanel(wx.Panel):
    """wxPython panel for browsing the ODS entity-relation model schema.

    Args:
        parent: The parent widget (typically a ``wx.Notebook``).
        con_i: Active ODS connection (``ConI`` instance).
    """

    def __init__(self, parent: wx.Window, con_i: Any) -> None:
        super().__init__(parent)
        self._mc: Any = con_i.mc
        self._model: ods.Model | None = None
        self._search_index: ModelSearchIndex | None = None
        self._result_matches: list[ModelMatch] = []
        self._search_timer: wx.CallLater | None = None
        self._search_available: bool = True
        self._search_generation: int = 0
        self._search_generation: int = 0
        self._build_ui()
        self._populate_tree()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        # Font variants used for tree items
        base_font = self.GetFont()
        self._bold_font = base_font.Bold()
        self._italic_font = base_font.Italic()

        splitter = wx.SplitterWindow(self, style=wx.SP_LIVE_UPDATE)

        # Left panel — contains tree + search results
        self._left_panel = wx.Panel(splitter)
        left_sizer = wx.BoxSizer(wx.VERTICAL)

        self._tree = wx.TreeCtrl(
            self._left_panel,
            style=wx.TR_DEFAULT_STYLE | wx.TR_HAS_BUTTONS | wx.TR_HIDE_ROOT,
        )
        self._tree.Bind(wx.EVT_TREE_SEL_CHANGED, self._on_sel_changed)
        self._tree.Bind(wx.EVT_TREE_ITEM_EXPANDING, self._on_tree_expanding)
        left_sizer.Add(self._tree, proportion=1, flag=wx.EXPAND)

        # Search results list (hidden until a search is active)
        self._results_list = wx.ListCtrl(
            self._left_panel,
            style=wx.LC_REPORT | wx.LC_SINGLE_SEL | wx.BORDER_SUNKEN,
        )
        self._results_list.AppendColumn("Kind", width=70)
        self._results_list.AppendColumn("Entity", width=130)
        self._results_list.AppendColumn("Name", width=160)
        self._results_list.AppendColumn("Score", width=55)
        self._results_list.Bind(wx.EVT_LIST_ITEM_ACTIVATED, self._on_result_activated)
        self._results_list.Hide()
        left_sizer.Add(self._results_list, proportion=0, flag=wx.EXPAND)
        self._left_panel.SetSizer(left_sizer)

        # Right — properties
        props_panel = self._build_props_panel(splitter)

        splitter.SplitVertically(self._left_panel, props_panel, sashPosition=420)
        splitter.SetMinimumPaneSize(120)
        splitter.SetSashGravity(0.6)

        # Search control above the splitter
        self._search_ctrl = wx.SearchCtrl(self, style=wx.TE_PROCESS_ENTER)
        self._search_ctrl.SetHint("Search model…")
        self._search_ctrl.ShowSearchButton(True)
        self._search_ctrl.ShowCancelButton(True)
        self._search_ctrl.Bind(wx.EVT_TEXT, self._on_search_text)
        self._search_ctrl.Bind(wx.EVT_SEARCHCTRL_CANCEL_BTN, self._on_search_cancel)

        outer = wx.BoxSizer(wx.VERTICAL)
        outer.Add(self._search_ctrl, proportion=0, flag=wx.EXPAND | wx.ALL, border=4)
        outer.Add(
            splitter,
            proportion=1,
            flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM,
            border=4,
        )
        self.SetSizer(outer)

        # Set initial sash after layout is complete
        wx.CallAfter(self._set_initial_sash, splitter)

    def _set_initial_sash(self, splitter: wx.SplitterWindow) -> None:
        w = splitter.GetClientSize().width
        if w > 0:
            splitter.SetSashPosition(int(w * 0.55))

    def _build_props_panel(self, parent: wx.Window) -> wx.Panel:
        panel = wx.Panel(parent)
        vbox = wx.BoxSizer(wx.VERTICAL)

        self._props_header = wx.StaticText(panel, label="Model")
        font = self._props_header.GetFont()
        font.SetWeight(wx.FONTWEIGHT_BOLD)
        self._props_header.SetFont(font)
        vbox.Add(self._props_header, flag=wx.ALL, border=4)

        self._props_list = wx.ListCtrl(
            panel,
            style=wx.LC_REPORT | wx.LC_SINGLE_SEL | wx.BORDER_SUNKEN,
        )
        self._props_list.AppendColumn("Property", width=160)
        self._props_list.AppendColumn("Value", width=260)
        vbox.Add(
            self._props_list,
            proportion=1,
            flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM,
            border=4,
        )
        panel.SetSizer(vbox)
        return panel

    # ------------------------------------------------------------------
    # Tree population
    # ------------------------------------------------------------------

    def _populate_tree(self) -> None:
        self._tree.DeleteAllItems()
        try:
            model: ods.Model = self._mc.model()
        except Exception:  # noqa: BLE001
            root = self._tree.AddRoot("(model unavailable)")
            return

        root = self._tree.AddRoot("")

        # ── Entities group ──────────────────────────────────────────────
        entities_node = self._tree.AppendItem(root, "Entities")
        self._tree.SetItemFont(entities_node, self._bold_font)
        self._tree.SetItemData(entities_node, None)

        entities_sorted = sorted(
            model.entities.values(),
            key=lambda e: (
                1 if e.base_name == "AoAny" else 0,
                _entity_colour(e.base_name) or (999, 999, 999),
                e.base_name,
                e.name,
            ),
        )
        for entity in entities_sorted:
            self._add_entity_node(entities_node, entity, model)

        self._tree.Expand(entities_node)
        self._model = model

        # ── Enumerations group ──────────────────────────────────────────
        enums_node = self._tree.AppendItem(root, "Enumerations")
        self._tree.SetItemFont(enums_node, self._bold_font)
        self._tree.SetItemData(enums_node, _EnumGroupNode())

        for enum in sorted(model.enumerations.values(), key=lambda e: e.name):
            self._add_enum_node(enums_node, enum)

        self._tree.Expand(enums_node)
        wx.CallAfter(self._tree.ScrollTo, entities_node)

        # Build the semantic search index and warm it up in the background so the
        # first search completes instantly without loading weights on the UI thread.
        self._search_index = ModelSearchIndex(model)
        self._search_available = False
        self._search_ctrl.SetHint("Indexing model…")
        threading.Thread(
            target=self._warm_up_index,
            daemon=True,
            name="search-warmup",
        ).start()

    def _add_entity_node(
        self,
        parent: wx.TreeItemId,
        entity: ods.Model.Entity,
        model: ods.Model,
    ) -> None:
        icon = _entity_icon(entity.base_name)
        label = f"{icon} {entity.name} - {entity.aid}"
        item = self._tree.AppendItem(parent, label)
        self._tree.SetItemData(item, _EntityNode(entity))

        rgb = _entity_colour(entity.base_name)
        if rgb:
            self._tree.SetItemTextColour(item, wx.Colour(*rgb))

        # Attributes sub-group
        attrs_sorted = sorted(entity.attributes.values(), key=lambda a: a.name)
        if attrs_sorted:
            attrs_node = self._tree.AppendItem(item, "Attributes")
            self._tree.SetItemFont(attrs_node, self._italic_font)
            self._tree.SetItemData(attrs_node, _AttrGroupNode(entity))
            for attr in attrs_sorted:
                sym = _ods_type_symbol(attr.data_type)
                attr_label = f"{sym} {attr.name} - {attr.base_name}" if attr.base_name else f"{sym} {attr.name}"
                attr_item = self._tree.AppendItem(attrs_node, attr_label)
                self._tree.SetItemData(attr_item, _AttrNode(entity, attr))

        # Relations sub-group
        rels_sorted = sorted(entity.relations.values(), key=lambda r: r.name)
        if rels_sorted:
            rels_node = self._tree.AppendItem(item, "Relations")
            self._tree.SetItemFont(rels_node, self._italic_font)
            self._tree.SetItemData(rels_node, _RelGroupNode(entity))
            for rel in rels_sorted:
                range_label = _rel_range(rel)
                if rel.base_name:
                    rel_label = f"{rel.name} - {rel.base_name} → {rel.entity_name}  [{range_label}]"
                else:
                    rel_label = f"{rel.name} → {rel.entity_name}  [{range_label}]"
                rel_item = self._tree.AppendItem(rels_node, rel_label)
                self._tree.SetItemData(rel_item, _RelNode(entity, rel))
                # Colour by target entity's base_name (light), italic font
                target = model.entities.get(rel.entity_name)
                target_base = target.base_name if target else ""
                rel_rgb = _entity_colour_light(target_base)
                if rel_rgb:
                    self._tree.SetItemTextColour(rel_item, wx.Colour(*rel_rgb))
                self._tree.SetItemFont(rel_item, self._italic_font)
                self._tree.SetItemHasChildren(rel_item, True)

    def _add_enum_node(self, parent: wx.TreeItemId, enum: ods.Model.Enumeration) -> None:
        item = self._tree.AppendItem(parent, f"\u2208 {enum.name}")
        self._tree.SetItemData(item, _EnumNode(enum))
        for name, index_val in sorted(enum.items.items(), key=lambda kv: kv[1]):
            child = self._tree.AppendItem(item, f"  {name}")
            self._tree.SetItemData(child, _EnumItemNode(enum, name, index_val))

    # ------------------------------------------------------------------
    # Search warm-up (background thread)
    # ------------------------------------------------------------------

    def _warm_up_index(self) -> None:
        """Load embeddings and encoder in a background thread."""
        assert self._search_index is not None
        try:
            self._search_index.warm_up()
        except Exception:
            log.warning("Search index warm-up failed.", exc_info=True)
        wx.CallAfter(self._on_search_index_ready)

    def _on_search_index_ready(self) -> None:
        """Called on the UI thread once the index is warm."""
        self._search_available = True
        self._search_ctrl.SetHint("Search model\u2026")
        # Re-trigger search if the user already typed something.
        query = self._search_ctrl.GetValue().strip()
        if len(query) >= 2:
            self._do_search(query)

    # ------------------------------------------------------------------
    # Search handlers
    # ------------------------------------------------------------------

    def _on_search_text(self, event: wx.CommandEvent) -> None:
        # Cancel any pending debounce timer.
        if self._search_timer is not None and self._search_timer.IsRunning():
            self._search_timer.Stop()
        query = self._search_ctrl.GetValue()
        if not query.strip():
            self._hide_search_results()
            return
        self._search_timer = wx.CallLater(300, self._do_search, query)

    def _on_search_cancel(self, event: wx.CommandEvent) -> None:
        self._search_ctrl.SetValue("")
        self._hide_search_results()

    def _hide_search_results(self) -> None:
        self._results_list.DeleteAllItems()
        self._result_matches.clear()
        if self._results_list.IsShown():
            self._results_list.Hide()
            self._left_panel.Layout()

    def _do_search(self, query: str) -> None:
        if not self._search_available or self._search_index is None:
            return
        self._search_generation += 1
        gen = self._search_generation

        # Show an immediate placeholder so the user sees that work is in progress.
        self._result_matches.clear()
        self._results_list.DeleteAllItems()
        self._results_list.InsertItem(0, "")
        self._results_list.SetItem(0, 2, "Searching…")
        row_h = self._results_list.GetCharHeight() + 4
        self._results_list.SetMinSize((-1, row_h * 2))
        if not self._results_list.IsShown():
            self._results_list.Show()
        self._left_panel.Layout()

        index = self._search_index
        threading.Thread(
            target=self._run_search,
            args=(query, gen, index),
            daemon=True,
            name="search-query",
        ).start()

    def _run_search(self, query: str, gen: int, index: ModelSearchIndex) -> None:
        """Execute the search on a background thread and post results to the UI."""
        try:
            results = index.search(query, top_k=30)
        except ImportError:
            log.warning(
                "sentence-transformers is not installed; install it with: uv sync --extra gui"
            )
            wx.CallAfter(self._apply_search_unavailable)
            return
        except Exception:
            log.exception("Semantic search failed.")
            return
        wx.CallAfter(self._apply_search_results, results, gen)

    def _apply_search_unavailable(self) -> None:
        self._search_available = False
        self._search_ctrl.SetHint("Search unavailable — install sentence-transformers")
        self._hide_search_results()

    def _apply_search_results(self, results: list[ModelMatch], gen: int) -> None:
        """Called on the UI thread with search results from the background thread."""
        if gen != self._search_generation:
            return  # superseded by a newer query

        self._results_list.DeleteAllItems()
        self._result_matches = list(results)
        for i, match in enumerate(results):
            kind_label = {
                "attribute": "Attr",
                "relation": "Rel",
                "enumeration": "Enum",
            }.get(match.kind, match.kind[:4].title())
            self._results_list.InsertItem(i, kind_label)
            self._results_list.SetItem(i, 1, match.entity_name)
            self._results_list.SetItem(i, 2, match.item_name)
            self._results_list.SetItem(i, 3, f"{match.score:.2f}")
            self._results_list.SetItemData(i, i)

        if results:
            # Give the results list a reasonable height (up to 8 visible rows).
            row_h = self._results_list.GetCharHeight() + 4
            desired_h = min(len(results), 8) * row_h + self._results_list.GetCharHeight()
            self._results_list.SetMinSize((-1, desired_h))
            if not self._results_list.IsShown():
                self._results_list.Show()
            self._left_panel.Layout()
        else:
            self._hide_search_results()

    def _on_result_activated(self, event: wx.ListEvent) -> None:
        idx = event.GetIndex()
        if 0 <= idx < len(self._result_matches):
            self._navigate_to_match(self._result_matches[idx])

    # ------------------------------------------------------------------
    # Tree navigation (used by search result activation)
    # ------------------------------------------------------------------

    def _find_child(
        self,
        parent: wx.TreeItemId,
        predicate: Any,
    ) -> wx.TreeItemId:
        """Return the first child of *parent* for which ``predicate(item, data)`` is True."""
        child, cookie = self._tree.GetFirstChild(parent)
        while child.IsOk():
            if predicate(child, self._tree.GetItemData(child)):
                return child
            child, cookie = self._tree.GetNextChild(parent, cookie)
        return wx.TreeItemId()

    def _navigate_to_match(self, match: ModelMatch) -> None:
        root = self._tree.GetRootItem()
        if not root.IsOk():
            return

        if match.kind == "enumeration":
            enums_node = self._find_child(
                root,
                lambda item, _d: self._tree.GetItemText(item) == "Enumerations",
            )
            if not enums_node.IsOk():
                return
            self._tree.Expand(enums_node)
            target = self._find_child(
                enums_node,
                lambda _item, d: isinstance(d, _EnumNode) and d.enum.name == match.item_name,
            )
        else:
            entities_node = self._find_child(
                root,
                lambda item, _d: self._tree.GetItemText(item) == "Entities",
            )
            if not entities_node.IsOk():
                return
            entity_node = self._find_child(
                entities_node,
                lambda _item, d: isinstance(d, _EntityNode) and d.entity.name == match.entity_name,
            )
            if not entity_node.IsOk():
                return
            self._tree.Expand(entity_node)
            group_text = "Attributes" if match.kind == "attribute" else "Relations"
            group_node = self._find_child(
                entity_node,
                lambda item, _d: self._tree.GetItemText(item) == group_text,
            )
            if not group_node.IsOk():
                return
            self._tree.Expand(group_node)
            if match.kind == "attribute":
                target = self._find_child(
                    group_node,
                    lambda _item, d: isinstance(d, _AttrNode) and d.attr.name == match.item_name,
                )
            else:
                target = self._find_child(
                    group_node,
                    lambda _item, d: isinstance(d, _RelNode) and d.rel.name == match.item_name,
                )

        if target.IsOk():
            self._tree.SelectItem(target)
            self._tree.EnsureVisible(target)

    # ------------------------------------------------------------------
    # Lazy expansion
    # ------------------------------------------------------------------

    def _on_tree_expanding(self, event: wx.TreeEvent) -> None:
        item = event.GetItem()
        first_child, _ = self._tree.GetFirstChild(item)
        if first_child.IsOk():
            return  # already populated
        data = self._tree.GetItemData(item)
        if not isinstance(data, _RelNode) or self._model is None:
            return
        target = self._model.entities.get(data.rel.entity_name)
        if target is None:
            self._tree.SetItemHasChildren(item, False)
            return
        if self._entity_in_ancestors(item, target.name):
            placeholder = self._tree.AppendItem(item, f"\u21a9 {target.name}  (see above)")
            self._tree.SetItemData(placeholder, None)
            return
        self._add_entity_node(item, target, self._model)

    def _entity_in_ancestors(self, item: wx.TreeItemId, entity_name: str) -> bool:
        """Return True if *entity_name* appears as an _EntityNode on the ancestor path."""
        parent = self._tree.GetItemParent(item)
        while parent.IsOk():
            node_data = self._tree.GetItemData(parent)
            if isinstance(node_data, _EntityNode) and node_data.entity.name == entity_name:
                return True
            parent = self._tree.GetItemParent(parent)
        return False

    # ------------------------------------------------------------------
    # Selection → property panel
    # ------------------------------------------------------------------

    def _on_sel_changed(self, event: wx.TreeEvent) -> None:
        if not self._tree:
            return
        item = event.GetItem()
        if not item.IsOk():
            self._clear_props("Model")
            return
        data = self._tree.GetItemData(item)
        self._show_props(data)

    def _clear_props(self, header: str = "Model") -> None:
        self._props_list.DeleteAllItems()
        self._props_header.SetLabel(header)

    def _set_props(self, header: str, rows: list[tuple[str, str]]) -> None:
        self._props_list.DeleteAllItems()
        self._props_header.SetLabel(header)
        for prop, value in rows:
            idx = self._props_list.GetItemCount()
            self._props_list.InsertItem(idx, prop)
            self._props_list.SetItem(idx, 1, value)

    def _show_props(self, data: Any) -> None:  # noqa: PLR0912
        if data is None:
            self._clear_props("Model")

        elif isinstance(data, _EntityNode):
            entity = data.entity
            icon = _entity_icon(entity.base_name)
            n_attrs = len(entity.attributes)
            n_rels = len(entity.relations)
            self._set_props(
                f"{icon} {entity.name}",
                [
                    ("Name", entity.name),
                    ("Base name", entity.base_name),
                    ("Aid", str(entity.aid)),
                    ("Attributes", str(n_attrs)),
                    ("Relations", str(n_rels)),
                ],
            )

        elif isinstance(data, _AttrGroupNode):
            entity = data.entity
            self._set_props(
                f"Attributes \u2014 {entity.name}",
                [("Entity", entity.name), ("Count", str(len(entity.attributes)))],
            )

        elif isinstance(data, _RelGroupNode):
            entity = data.entity
            self._set_props(
                f"Relations \u2014 {entity.name}",
                [("Entity", entity.name), ("Count", str(len(entity.relations)))],
            )

        elif isinstance(data, _AttrNode):
            entity, attr = data.entity, data.attr
            sym = _ods_type_symbol(attr.data_type)
            rows: list[tuple[str, str]] = [
                ("Name", attr.name),
                ("Base name", attr.base_name or "\u2014"),
                ("Data type", f"{sym}  {ods.DataTypeEnum.Name(attr.data_type)}"),
                ("Length", str(attr.length) if attr.length else "\u2014"),
                ("Obligatory", str(attr.obligatory)),
                ("Unique", str(attr.unique)),
                ("Autogenerated", str(attr.autogenerated)),
                ("Enumeration", attr.enumeration or "\u2014"),
                ("Unit id", str(attr.unit_id) if attr.unit_id else "\u2014"),
                ("Id", str(attr.id)),
                ("Entity", entity.name),
            ]
            self._set_props(f"{sym} {attr.name}", rows)

        elif isinstance(data, _RelNode):
            entity, rel = data.entity, data.rel
            self._set_props(
                f"\u2192 {rel.name}",
                [
                    ("Name", rel.name),
                    ("Base name", rel.base_name or "\u2014"),
                    ("Target entity", rel.entity_name),
                    ("Target base name", rel.entity_base_name or "\u2014"),
                    ("Inverse name", rel.inverse_name),
                    ("Inverse base name", rel.inverse_base_name or "\u2014"),
                    ("Range", _rel_range(rel)),
                    ("Range min", str(rel.range_min)),
                    ("Range max", _range_str(rel.range_max)),
                    ("Inverse range min", str(rel.inverse_range_min)),
                    ("Inverse range max", _range_str(rel.inverse_range_max)),
                    ("Relation type", ods.Model.RelationTypeEnum.Name(rel.relation_type)),
                    ("Relationship", _rel_type_label(rel)),
                    ("Virtual reference", str(rel.virtual_reference)),
                    ("Acl reference", str(rel.acl_reference)),
                    ("Entity aid", str(rel.entity_aid) if rel.entity_aid else "\u2014"),
                    ("Source entity", entity.name),
                ],
            )

        elif isinstance(data, _EnumGroupNode):
            self._clear_props("Enumerations")

        elif isinstance(data, _EnumNode):
            enum = data.enum
            rows2: list[tuple[str, str]] = [("Name", enum.name)]
            for name, index_val in sorted(enum.items.items(), key=lambda kv: kv[1]):
                rows2.append((name, str(index_val)))
            self._set_props(f"\u2208 {enum.name}", rows2)

        elif isinstance(data, _EnumItemNode):
            self._set_props(
                f"{data.enum.name}.{data.item_name}",
                [
                    ("Enumeration", data.enum.name),
                    ("Name", data.item_name),
                    ("Index", str(data.item_index)),
                ],
            )

        else:
            self._clear_props("Model")
