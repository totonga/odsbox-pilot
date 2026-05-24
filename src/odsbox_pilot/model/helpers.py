"""Pure (wx-free) helper functions for the Model tab.

Kept in a separate module so they can be imported and tested
without a wxPython installation.
"""

from __future__ import annotations

from odsbox.proto import ods

_UNBOUNDED = -1


def _range_str(max_val: int) -> str:
    """Return ``"n"`` for an unbounded range (-1), otherwise the value as a string."""
    return "n" if max_val == _UNBOUNDED else str(max_val)


def _rel_range(rel: ods.Model.Relation) -> str:
    """Return a human-readable cardinality string like ``'1:1'``, ``'1:n'``, ``'n:n'``."""
    return f"{_range_str(rel.inverse_range_max)}:{_range_str(rel.range_max)}"


def _rel_type_label(rel: ods.Model.Relation) -> str:
    """Return the ``RelationshipEnum`` name for *rel.relationship*."""
    return ods.Model.RelationshipEnum.Name(rel.relationship)
