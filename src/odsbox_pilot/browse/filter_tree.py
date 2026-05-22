"""FilterTree — Dijkstra-based relation-path query engine for ASAM ODS models.

Given a set of entity-level filter conditions (FilterNodes), FilterTree finds the
shortest relation path between entities using a weighted graph built from the ODS
application model. It generates Jaquel queries automatically and supports
hierarchical tree browsing via ``query()`` and ``follow()``.

Weight logic (lower = preferred):
    1 — RS_CHILD relations (follow hierarchy downward)
    3 — Non-RS_CHILD relations with a base_name (standardised base model)
    7 — Non-RS_CHILD relations without a base_name (application-specific)
"""

from __future__ import annotations

import heapq
from dataclasses import dataclass
from typing import Any

import pandas as pd
from odsbox.model_cache import ModelCache
from odsbox.proto import ods


@dataclass
class FilterNode:
    """A single entity-level filter condition for use in a FilterTree.

    Attributes:
        entity: The ODS model entity this condition applies to.
        condition: Jaquel condition dict, e.g. ``{"name": {"$like": "Elec*"}}``.
    """

    entity: ods.Model.Entity
    condition: dict[str, Any]


# Edge in the relation graph: (relation_name, target_entity_name, weight)
_Edge = tuple[str, str, int]

# Default Jaquel $attributes selection returned by query() and follow().
DEFAULT_ATTRS: dict[str, int] = {"id": 1, "name": 1}


class FilterTree:
    """Weighted relation-graph query engine for ASAM ODS models.

    Builds a directed graph from the ODS application model where edges are
    entity relations weighted by type (children < base < application).  Uses
    Dijkstra's algorithm to find the shortest relation path between any two
    entities so that Jaquel queries can be assembled automatically.

    Args:
        mc: A :class:`ModelCache` instance providing the ODS model.
        nodes: Filter conditions to apply. Each :class:`FilterNode` ties a
            Jaquel condition dict to a specific entity.

    Example::

        ft = FilterTree(mc, [
            FilterNode(mc.entity("Project"), {"name": {"$like": "Elec*"}}),
            FilterNode(mc.entity("MeaResult"), {"name": {"$like": "Profile_*"}}),
        ])
        query = ft.generate_query("Project")
        df = ft.query(con_i, "Project")
    """

    def __init__(self, mc: ModelCache, nodes: list[FilterNode] | None = None) -> None:
        self._mc = mc
        self._nodes: list[FilterNode] = list(nodes) if nodes else []
        self._graph: dict[str, list[_Edge]] | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add_node(self, node: FilterNode) -> FilterTree:
        """Add a filter condition and return *self* for fluent chaining.

        Invalidates the cached relation graph so that the next path-finding
        call rebuilds it.

        Args:
            node: The :class:`FilterNode` to add.

        Returns:
            This FilterTree instance.
        """
        self._nodes.append(node)
        return self

    def generate_query(
        self,
        root_entity: str | ods.Model.Entity,
        attributes: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Build a Jaquel query dict without executing it.

        This is a pure function — it does **not** contact the server and can
        be used for offline testing or query inspection.

        Args:
            root_entity: Entity name (or object) to query from.
            attributes: Jaquel ``$attributes`` dict.  Defaults to
                ``{"id": 1, "name": 1}``.

        Returns:
            A Jaquel query dict ready for ``con_i.query()``.
        """
        entity = self._resolve_entity(root_entity)
        attrs = attributes or DEFAULT_ATTRS
        conditions = self._build_conditions(entity.name)
        query: dict[str, Any] = {entity.name: conditions, "$attributes": attrs}
        if self._needs_groupby(entity.name) and not self._contains_aggregation_operators(attrs):
            query["$groupby"] = attrs
        return query

    def query(
        self,
        con_i: Any,
        root_entity: str | ods.Model.Entity,
        attributes: dict[str, Any] | None = None,
    ) -> pd.DataFrame:
        """Execute a Jaquel query against the server.

        Builds the query via :meth:`generate_query` and passes it to
        ``con_i.query()``.

        Args:
            con_i: An active ODS connection (``ConI`` instance).
            root_entity: Entity name (or object) to query from.
            attributes: Jaquel ``$attributes`` dict.

        Returns:
            A :class:`~pandas.DataFrame` with the query results.
        """
        return con_i.query(self.generate_query(root_entity, attributes))

    def distinct(
        self,
        con_i: Any,
        root_entity: str | ods.Model.Entity,
        attribute: str,
    ) -> list[Any]:
        """Return a sorted list of distinct values for *attribute* in *root_entity*.

        Applies all current FilterNode conditions as joins so the result is
        already narrowed by the active filter set.

        Args:
            con_i: An active ODS connection.
            root_entity: Entity to query from.
            attribute: Attribute name to aggregate.

        Returns:
            List of distinct values (may be empty).  Raises ``ValueError`` if
            the server returns a result without the expected ``$distinct`` column.
        """
        df = self.query(con_i, root_entity, attributes={attribute: {"$distinct": 1}})
        if df.empty:
            return []
        col = f"{attribute}.$distinct"
        if col not in df.columns:
            raise ValueError(f"Expected column '{col}' not found in query result.")
        return list(df[col])

    def min_max(
        self,
        con_i: Any,
        root_entity: str | ods.Model.Entity,
        attribute: str,
    ) -> tuple[Any, Any]:
        """Return the ``(min, max)`` of *attribute* across all matching *root_entity* rows.

        Applies all current FilterNode conditions as joins so the range is
        already narrowed by the active filter set.

        Args:
            con_i: An active ODS connection.
            root_entity: Entity to query from.
            attribute: Attribute name to aggregate.

        Returns:
            ``(min_value, max_value)`` tuple.  Both values are ``None`` when
            the query returns no rows or the expected columns are absent.
        """
        df = self.query(con_i, root_entity, attributes={attribute: {"$min": 1, "$max": 1}})
        if df.empty:
            return None, None
        min_col = f"{attribute}.$min"
        max_col = f"{attribute}.$max"
        if min_col not in df.columns or max_col not in df.columns:
            return None, None
        return df[min_col].iloc[0], df[max_col].iloc[0]

    def generate_follow_query(
        self,
        parent_entity: str | ods.Model.Entity,
        parent_ids: list[int],
        target_entity: str | ods.Model.Entity,
        attributes: dict[str, int] | None = None,
    ) -> dict[str, Any]:
        """Build the Jaquel query dict for a follow() call without executing it.

        This is a pure function — it does **not** contact the server and can
        be used for offline testing or query inspection.

        Args:
            parent_entity: The entity whose instances have already been queried.
            parent_ids: Instance ids obtained from a previous ``query()`` or
                ``follow()`` call.
            target_entity: The directly-related entity to navigate to.
            attributes: Jaquel ``$attributes`` dict.

        Returns:
            A Jaquel query dict ready for ``con_i.query()``.

        Raises:
            ValueError: If there is no direct relation from *parent_entity*
                to *target_entity*.
        """
        parent_e = self._resolve_entity(parent_entity)
        target_e = self._resolve_entity(target_entity)
        attrs = attributes or DEFAULT_ATTRS

        relation = self._find_direct_relation(parent_e.name, target_e.name)
        if relation is None:
            raise ValueError(f"No direct relation from '{parent_e.name}' to '{target_e.name}'.")

        conditions: dict[str, Any] = {}

        # Narrow by parent id(s) via the inverse relation name.
        # n:m (RS_INFO_REL) relations require the ".id" suffix in Jaquel.
        inverse_key = (
            f"{relation.inverse_name}.id"
            if relation.relationship == ods.Model.RS_INFO_REL
            else relation.inverse_name
        )
        if len(parent_ids) == 1:
            conditions[inverse_key] = parent_ids[0]
        else:
            conditions[inverse_key] = {"$in": parent_ids}

        # Add target entity's own conditions (if any FilterNode matches)
        for node in self._nodes:
            if node.entity.name == target_e.name:
                conditions.update(node.condition)

        # Add remaining filter nodes (skip parent and target) via path.
        # Also skip any node whose path from target goes back through the
        # already-bound parent — the parent id already pins that branch.
        needs_gb = False
        for node in self._nodes:
            if node.entity.name in (parent_e.name, target_e.name):
                continue
            path = self._find_path(target_e.name, node.entity.name)
            if parent_e.name in self._entities_on_path(target_e.name, path)[:-1]:
                continue
            conditions[self._path_key(target_e.name, path)] = node.condition
            if self._path_needs_groupby(target_e.name, path):
                needs_gb = True

        follow_query: dict[str, Any] = {
            target_e.name: conditions,
            "$attributes": attrs,
        }
        if needs_gb and not self._contains_aggregation_operators(attrs):
            follow_query["$groupby"] = attrs
        return follow_query

    def follow(
        self,
        con_i: Any,
        parent_entity: str | ods.Model.Entity,
        parent_ids: list[int],
        target_entity: str | ods.Model.Entity,
        attributes: dict[str, int] | None = None,
    ) -> pd.DataFrame:
        """Follow a direct relation from *parent_entity* to *target_entity*.

        Replaces the parent entity's own FilterNode conditions with an id-based
        filter (since the parent instances are already narrowed down), then
        attaches all remaining FilterNode conditions via shortest paths
        relative to the target entity.

        Args:
            con_i: An active ODS connection.
            parent_entity: The entity whose instances have already been queried.
            parent_ids: Instance ids obtained from a previous ``query()`` or
                ``follow()`` call.
            target_entity: The directly-related entity to navigate to.
            attributes: Jaquel ``$attributes`` dict.

        Returns:
            A :class:`~pandas.DataFrame` with the target entity instances.

        Raises:
            ValueError: If there is no direct relation from *parent_entity*
                to *target_entity*.
        """
        return con_i.query(
            self.generate_follow_query(parent_entity, parent_ids, target_entity, attributes)
        )

    def find_path(
        self,
        source_entity: str | ods.Model.Entity,
        target_entity: str | ods.Model.Entity,
    ) -> list[str]:
        """Find the shortest weighted path between two entities.

        Uses Dijkstra's algorithm to compute the cheapest relation path,
        preferring children relations (weight 1) over base relations (weight 3)
        over application relations (weight 7).

        Args:
            source_entity: Starting entity (name or object).
            target_entity: Target entity (name or object).

        Returns:
            Ordered list of relation names forming the shortest path.

        Raises:
            ValueError: If *target_entity* is unreachable from *source_entity*.

        Example::

            path = ft.find_path("Project", "MeaResult")
            # Returns: ["StructureLevel", "Tests", "TestSteps", "MeaResults"]
        """
        source_e = self._resolve_entity(source_entity)
        target_e = self._resolve_entity(target_entity)
        return self._find_path(source_e.name, target_e.name)

    # ------------------------------------------------------------------
    # Graph building
    # ------------------------------------------------------------------

    @staticmethod
    def _relation_weight(relation: ods.Model.Relation) -> int:
        """Compute edge weight for a relation.

        Children relations (RS_CHILD) get the lowest weight so that Dijkstra
        prefers following the hierarchy downward.
        """
        if relation.relationship == ods.Model.RS_CHILD:
            return 1
        if relation.base_name:
            return 3
        if relation.range_max == -1 and relation.inverse_range_max == -1:
            return 33  # n:m relations are very expensive to join — avoid if possible
        return 13

    def _ensure_graph(self) -> dict[str, list[_Edge]]:
        """Lazily build and cache the directed relation graph."""
        if self._graph is None:
            self._graph = self._build_graph()
        return self._graph

    def _build_graph(self) -> dict[str, list[_Edge]]:
        """Build a directed weighted graph from all model entity relations."""
        graph: dict[str, list[_Edge]] = {}
        for entity_name, entity in self._mc.model().entities.items():
            edges: list[_Edge] = []
            for _, relation in entity.relations.items():
                if not relation.entity_name:
                    continue
                weight = self._relation_weight(relation)
                edges.append((relation.name, relation.entity_name, weight))
            graph[entity_name] = edges
        return graph

    # ------------------------------------------------------------------
    # Path finding (Dijkstra)
    # ------------------------------------------------------------------

    def _find_path(self, source: str, target: str) -> list[str]:
        """Find the shortest weighted path from *source* to *target*.

        Returns:
            Ordered list of relation names forming the path.

        Raises:
            ValueError: If *target* is unreachable from *source*.
        """
        if source == target:
            return []

        graph = self._ensure_graph()

        # dist[entity] = (total_weight, [relation_names...])
        dist: dict[str, tuple[int, list[str]]] = {source: (0, [])}
        # priority queue: (weight, entity_name)
        heap: list[tuple[int, str]] = [(0, source)]
        visited: set[str] = set()

        while heap:
            cost, current = heapq.heappop(heap)
            if current in visited:
                continue
            visited.add(current)

            if current == target:
                return dist[target][1]

            for rel_name, neighbor, weight in graph.get(current, []):
                new_cost = cost + weight
                if neighbor not in dist or new_cost < dist[neighbor][0]:
                    dist[neighbor] = (new_cost, dist[current][1] + [rel_name])
                    heapq.heappush(heap, (new_cost, neighbor))

        raise ValueError(f"No path from '{source}' to '{target}' in the model.")

    def _find_direct_relation(self, from_entity: str, to_entity: str) -> ods.Model.Relation | None:
        """Find the lowest-weight direct relation between two entities."""
        entity = self._mc.entity(from_entity)
        best: ods.Model.Relation | None = None
        best_weight = float("inf")
        for _, relation in entity.relations.items():
            if relation.entity_name == to_entity:
                w = self._relation_weight(relation)
                if w < best_weight:
                    best = relation
                    best_weight = w
        return best

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _resolve_entity(self, entity: str | ods.Model.Entity) -> ods.Model.Entity:
        """Resolve an entity name or object to an Entity."""
        if isinstance(entity, str):
            return self._mc.entity(entity)
        return entity

    @staticmethod
    def _contains_aggregation_operators(attrs: dict[str, Any]) -> bool:
        """Return True if any attribute value contains $distinct, $min, or $max.

        When aggregation operators are used, the database handles aggregation,
        so $groupby is not needed.
        """
        for value in attrs.values():
            if isinstance(value, dict) and any(
                key in value for key in ["$distinct", "$min", "$max"]
            ):
                return True
        return False

    def _path_needs_groupby(self, start_entity: str, relation_path: list[str]) -> bool:
        """Return True if any step in the path can return multiple rows per source.

        A join requires ``$groupby`` whenever ``range_max != 1``, which covers
        RS_CHILD (one-to-many hierarchy), RS_INFO_FROM (one-to-many back-refs)
        and RS_INFO_REL (n:m relations).
        """
        current = start_entity
        for rel_name in relation_path:
            entity = self._mc.entity(current)
            rel = next(
                (r for _, r in entity.relations.items() if r.name == rel_name),
                None,
            )
            if rel is None:
                return True  # Unknown — assume worst case
            if rel.range_max != 1:
                return True
            current = rel.entity_name
        return False

    def _needs_groupby(self, root_name: str) -> bool:
        """Return True if the query for *root_name* needs ``$groupby``.

        Only required when at least one joined path crosses an n-side
        (RS_CHILD) relation, which can produce duplicate root rows.
        Paths that are skipped in :meth:`_build_conditions` are also skipped here
        so ``$groupby`` is never emitted without a matching condition.
        """
        id_bound = self._id_bound_entities(root_name)
        for node in self._nodes:
            if node.entity.name == root_name:
                continue
            path = self._find_path(root_name, node.entity.name)
            if id_bound and any(
                e in id_bound for e in self._entities_on_path(root_name, path)[:-1]
            ):
                continue
            if self._path_needs_groupby(root_name, path):
                return True
        return False

    def _id_bound_entities(self, exclude_entity: str) -> set[str]:
        """Return entity names of FilterNodes (other than *exclude_entity*) that
        carry an id-based condition — i.e. ``"id"`` is a top-level key.

        Conditions routed *through* such entities are redundant because the
        instance is already pinned.
        """
        return {
            node.entity.name
            for node in self._nodes
            if "id" in node.condition and node.entity.name != exclude_entity
        }

    def _entities_on_path(self, start_entity: str, relation_path: list[str]) -> list[str]:
        """Return the sequence of entity names reached after each step in *relation_path*.

        The returned list has the same length as *relation_path*; the last element
        is the final destination entity.  If a relation name is not found the walk
        stops early.
        """
        result: list[str] = []
        current = start_entity
        for rel_name in relation_path:
            entity = self._mc.entity(current)
            rel = next(
                (r for _, r in entity.relations.items() if r.name == rel_name),
                None,
            )
            if rel is None:
                break
            current = rel.entity_name
            result.append(current)
        return result

    def _path_key(self, start_entity: str, relation_path: list[str]) -> str:
        """Build a dotted Jaquel path key, appending '.id' to n:m (RS_INFO_REL) steps."""
        parts: list[str] = []
        current = start_entity
        for rel_name in relation_path:
            entity = self._mc.entity(current)
            rel = next(
                (r for _, r in entity.relations.items() if r.name == rel_name),
                None,
            )
            if rel is not None and rel.relationship == ods.Model.RS_INFO_REL:
                parts.append(f"{rel_name}.id")
            else:
                parts.append(rel_name)
            if rel is not None:
                current = rel.entity_name
        return ".".join(parts)

    def _build_conditions(self, root_name: str) -> dict[str, Any]:
        """Merge all FilterNode conditions relative to *root_name*.

        Skips any FilterNode whose path from *root_name* passes through another
        FilterNode entity that is already id-bound (``"id"`` in its condition),
        because that instance is already pinned and adding a deeper condition
        through it would be redundant.
        """
        id_bound = self._id_bound_entities(root_name)
        conditions: dict[str, Any] = {}
        for node in self._nodes:
            if node.entity.name == root_name:
                conditions.update(node.condition)
            else:
                path = self._find_path(root_name, node.entity.name)
                if id_bound and any(
                    e in id_bound for e in self._entities_on_path(root_name, path)[:-1]
                ):
                    continue
                conditions[self._path_key(root_name, path)] = node.condition
        return conditions
