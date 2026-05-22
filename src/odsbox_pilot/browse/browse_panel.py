"""BrowsePanel — wxPython panel for interactive FilterTree browsing.

Designed to live as a tab page inside ``MainFrame``'s ``wx.Notebook``.
The two standalone helpers ``_load_conditions`` and ``_save_conditions`` at
the bottom of this module have no wx dependency and are unit-testable
without a running wx.App.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import wx  # type: ignore[import-untyped]

from odsbox_pilot.browse.filter_tree import FilterNode, FilterTree
from odsbox_pilot.models import CONFIG_DIR

_BROWSE_CONDITIONS_FILE = CONFIG_DIR / "browse_conditions.json"


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
        self._build_ui()
        self._load_and_rebuild()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def clear_connection(self) -> None:
        """Disable controls and clear the tree before the connection is closed."""
        for btn in (self._query_btn, self._add_btn, self._edit_btn,
                    self._remove_btn, self._clear_btn):
            btn.Disable()
        self._tree.DeleteChildren(self._root)
        self._preview.SetValue("")
        self._status("Disconnected")

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        vbox = wx.BoxSizer(wx.VERTICAL)
        vbox.Add(self._build_toolbar(), flag=wx.EXPAND | wx.ALL, border=4)
        vbox.Add(self._build_conditions_section(),
                 flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, border=4)
        vbox.Add(self._build_tree(), proportion=1, flag=wx.EXPAND | wx.LEFT | wx.RIGHT, border=4)
        vbox.Add(self._build_preview(),
                 flag=wx.EXPAND | wx.ALL, border=4)
        self.SetSizer(vbox)

    def _build_toolbar(self) -> wx.Sizer:
        hbox = wx.BoxSizer(wx.HORIZONTAL)
        hbox.Add(
            wx.StaticText(self, label="Root entity:"),
            flag=wx.ALIGN_CENTER_VERTICAL | wx.RIGHT,
            border=4,
        )
        entities = sorted(self._mc.model().entities.keys())
        self._root_combo = wx.ComboBox(
            self, choices=entities, style=wx.CB_READONLY, size=(180, -1)
        )
        if "Project" in entities:
            self._root_combo.SetValue("Project")
        elif entities:
            self._root_combo.SetSelection(0)
        self._root_combo.Bind(wx.EVT_COMBOBOX, self._on_root_changed)
        hbox.Add(self._root_combo, flag=wx.RIGHT, border=8)
        self._query_btn = wx.Button(self, label="Query")
        self._query_btn.Bind(wx.EVT_BUTTON, self._on_query)
        hbox.Add(self._query_btn)
        return hbox

    def _build_conditions_section(self) -> wx.Sizer:
        box = wx.StaticBox(self, label="Filter Conditions")
        sizer = wx.StaticBoxSizer(box, wx.HORIZONTAL)

        self._cond_list = wx.ListCtrl(
            self,
            style=wx.LC_REPORT | wx.LC_SINGLE_SEL | wx.BORDER_SUNKEN,
            size=(-1, 110),
        )
        self._cond_list.AppendColumn("Entity", width=140)
        self._cond_list.AppendColumn("Attribute", width=120)
        self._cond_list.AppendColumn("Operator", width=75)
        self._cond_list.AppendColumn("Value", width=140)
        self._cond_list.Bind(wx.EVT_LIST_ITEM_ACTIVATED, self._on_edit_condition)
        sizer.Add(self._cond_list, proportion=1, flag=wx.EXPAND | wx.ALL, border=4)

        btn_vbox = wx.BoxSizer(wx.VERTICAL)
        self._add_btn = wx.Button(self, label="Add")
        self._edit_btn = wx.Button(self, label="Edit")
        self._remove_btn = wx.Button(self, label="Remove")
        self._clear_btn = wx.Button(self, label="Clear")
        for btn in (self._add_btn, self._edit_btn, self._remove_btn, self._clear_btn):
            btn_vbox.Add(btn, flag=wx.EXPAND | wx.BOTTOM, border=3)
        self._add_btn.Bind(wx.EVT_BUTTON, self._on_add_condition)
        self._edit_btn.Bind(wx.EVT_BUTTON, self._on_edit_condition)
        self._remove_btn.Bind(wx.EVT_BUTTON, self._on_remove_condition)
        self._clear_btn.Bind(wx.EVT_BUTTON, self._on_clear_conditions)
        sizer.Add(btn_vbox, flag=wx.TOP | wx.BOTTOM | wx.RIGHT, border=4)
        return sizer

    def _build_tree(self) -> wx.TreeCtrl:
        self._tree = wx.TreeCtrl(
            self, style=wx.TR_DEFAULT_STYLE | wx.TR_HIDE_ROOT | wx.TR_HAS_BUTTONS
        )
        self._root = self._tree.AddRoot("")
        self._tree.Bind(wx.EVT_TREE_ITEM_EXPANDING, self._on_tree_expanding)
        return self._tree

    def _build_preview(self) -> wx.Sizer:
        box = wx.StaticBox(self, label="Query Preview (Jaquel)")
        sizer = wx.StaticBoxSizer(box, wx.VERTICAL)
        self._preview = wx.TextCtrl(
            self,
            style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_DONTWRAP,
            size=(-1, 90),
        )
        sizer.Add(self._preview, proportion=1, flag=wx.EXPAND | wx.ALL, border=2)
        return sizer

    # ------------------------------------------------------------------
    # Query event handler
    # ------------------------------------------------------------------

    def _on_query(self, _event: wx.CommandEvent) -> None:  # noqa: ARG002
        root = self._root_combo.GetValue()
        if not root:
            return
        self._tree.DeleteChildren(self._root)
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

        for _, row in df.iterrows():
            instance_id = int(row["id"])
            name = str(row.get("name", ""))
            text = f"{root}  [{instance_id}]  {name}"
            child = self._tree.AppendItem(self._root, text)
            self._tree.SetItemData(child, _InstanceData(root, instance_id))
            self._tree.SetItemHasChildren(child, True)

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
        for _, row in df.iterrows():
            instance_id = int(row["id"])
            name = str(row.get("name", ""))
            text = f"{data.target_entity}  [{instance_id}]  {name}"
            child = self._tree.AppendItem(item, text)
            self._tree.SetItemData(child, _InstanceData(data.target_entity, instance_id))
            self._tree.SetItemHasChildren(child, True)

        count = len(df)
        self._status(
            f"Browse: {data.parent_entity} \u2192 {data.target_entity}: {count} row(s)"
        )
        self._log(
            f"Browse follow \u2014 {data.parent_entity} \u2192 {data.target_entity}: {count} row(s)"
        )

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

    # ------------------------------------------------------------------
    # Preview helpers
    # ------------------------------------------------------------------

    def _show_preview(self, query: dict[str, Any]) -> None:
        self._preview.SetValue(json.dumps(query, indent=2))

    def _update_preview(self) -> None:
        root = self._root_combo.GetValue()
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


# ------------------------------------------------------------------
# Standalone persistence helpers — no wx dependency, fully unit-testable
# ------------------------------------------------------------------


def _build_filter_nodes(
    mc: Any, conditions: list[dict[str, Any]]
) -> tuple[list[FilterNode], list[str]]:
    """Convert a list of condition dicts into ``FilterNode`` objects.

    Args:
        mc: ``ModelCache`` from the active connection.
        conditions: List of condition dicts with keys
            ``entity``, ``attr``, ``op``, ``val``.

    Returns:
        A tuple ``(nodes, failed)`` where *nodes* is the list of valid
        ``FilterNode`` objects and *failed* contains entity names that were
        not found in the model (and were therefore skipped).
    """
    nodes: list[FilterNode] = []
    failed: list[str] = []
    for cond in conditions:
        try:
            entity = mc.entity(cond["entity"])
        except (ValueError, KeyError):
            failed.append(cond.get("entity", "?"))
            continue
        val: Any = cond.get("val", "")
        try:
            val = int(val)
        except (ValueError, TypeError):
            try:
                val = float(val)
            except (ValueError, TypeError):
                pass
        nodes.append(FilterNode(entity=entity, condition={cond["attr"]: {cond["op"]: val}}))
    return nodes, failed



def _load_conditions() -> list[dict[str, Any]]:
    """Load browse conditions from ``~/.ods-pilot/browse_conditions.json``.

    Returns an empty list on missing file, corrupt JSON, or any I/O error.
    """
    try:
        data = json.loads(_BROWSE_CONDITIONS_FILE.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return data
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        pass
    return []


def _save_conditions(conditions: list[dict[str, Any]]) -> None:
    """Persist conditions to ``~/.ods-pilot/browse_conditions.json``.

    Silently ignores write errors so UI operations are never blocked by disk
    issues.
    """
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        _BROWSE_CONDITIONS_FILE.write_text(
            json.dumps(conditions, indent=2), encoding="utf-8"
        )
    except OSError:
        pass
