"""wx-free helpers for the Browse tab.

Extracted so that unit tests can import these without needing a ``wx``
installation (which is not available in headless CI environments).
"""

from __future__ import annotations

import contextlib
import json
from typing import Any

from odsbox_pilot.browse.filter_tree import FilterNode
from odsbox_pilot.models import CONFIG_DIR

_BROWSE_CONDITIONS_FILE = CONFIG_DIR / "browse_conditions.json"

# ------------------------------------------------------------------
# ODS type symbols / names
# ------------------------------------------------------------------

# Unicode symbol per ODS DataTypeEnum integer value.
_ODS_TYPE_SYMBOLS: dict[int, str] = {
    # ── Scalar (DT_) types ────────────────────────────────────────────────
    0:  "?",       # DT_UNKNOWN
    1:  "\uff21",  # DT_STRING             Ａ  fullwidth A
    2:  "\u2124",  # DT_SHORT              ℤ  integers
    3:  "\u211d",  # DT_FLOAT              ℝ  reals
    4:  "\u22a4",  # DT_BOOLEAN            ⊤  top / tautology
    5:  "\u229e",  # DT_BYTE               ⊞  squared plus
    6:  "\u2124",  # DT_LONG               ℤ
    7:  "\u211d",  # DT_DOUBLE             ℝ
    8:  "\u2124",  # DT_LONGLONG           ℤ
    10: "\u2299",  # DT_DATE               ⊙  circled dot
    11: "\u229e",  # DT_BYTESTR            ⊞
    12: "\u25a3",  # DT_BLOB               ▣  filled square
    13: "\u2102",  # DT_COMPLEX            ℂ
    14: "\u2102",  # DT_DCOMPLEX           ℂ
    28: "\u2934",  # DT_EXTERNALREFERENCE  ⤴  arrow curving up (single ref)
    30: "\u2208",  # DT_ENUM               ∈  element of
    # ── Array (DS_) types — n-ary / sequence visual motif ─────────────────
    # Each DS_ symbol is the "plural" counterpart of its DT_ scalar symbol.
    15: "\u2248",  # DS_STRING             ≈  double tilde   (many strings)
    16: "\u2261",  # DS_SHORT              ≡  triple bar     (column of ints)
    17: "\u2243",  # DS_FLOAT              ≃  asymptotic eq  (seq of reals)
    18: "\u22c0",  # DS_BOOLEAN            ⋀  n-ary AND      (boolean array)
    19: "\u229f",  # DS_BYTE               ⊟  squared minus  (array sibling of ⊞)
    20: "\u2261",  # DS_LONG               ≡
    21: "\u2243",  # DS_DOUBLE             ≃
    22: "\u2261",  # DS_LONGLONG           ≡
    23: "\u212d",  # DS_COMPLEX            ℭ  fraktur C      (complex sequence)
    24: "\u212d",  # DS_DCOMPLEX           ℭ
    25: "\u229b",  # DS_DATE               ⊛  circled ast.   (date series)
    26: "\u22a0",  # DS_BYTESTR            ⊠  squared times
    27: "\u25a4",  # DS_BLOB               ▤  lined square   (stacked blobs)
    29: "\u21d1",  # DS_EXTERNALREFERENCE  ⇑  double arrow   (many refs)
    31: "\u220b",  # DS_ENUM               ∋  contains-as-member (enum array)
}


# Unicode icon per ODS entity base_name.
_ENTITY_ICONS: dict[str, str] = {
    "AoEnvironment": "\u25c9",  # ◉
    "AoTest": "\u2697",  # ⚗
    "AoSubTest": "\u2299",  # ⊙
    "AoTestStep": "\u25b7",  # ▷
    "AoMeasurement": "\u223f",  # ∿
    "AoSubMatrix": "\u229e",  # ⊞
    "AoLocalColumn": "\u21a7",  # ↧
    "AoMeasurementQuantity": "\u0394",  # Δ
    "AoTestEquipment": "\u2699",  # ⚙
    "AoUnit": "\u03a9",  # Ω
    "AoPhysicalDimension": "\u2295",  # ⊕
    "AoParameterSet": "\u2261",  # ≡
    "AoParameter": "\u03bb",  # λ
    "AoFile": "\u25a4",  # ▤
    "AoLog": "\u2263",  # ≣
    "AoNameMap": "\u21cc",  # ⇌
    "AoAny": "\u25c7",  # ◇
    "AoUnitUnderTest": "\u25c8",  # ◈
    "AoUnitUnderTestPart": "\u25e6",  # ◦
    "AoTestSequence": "\u21d2",  # ⇒
    "AoTestSequencePart": "\u21aa",  # ↪
    "AoCatalogue": "\u229f",  # ⊟
    "AoCatalogueElement": "\u29c3",  # ⧃
    "AoUsers": "\u229b",  # ⊛
    "AoUserGroup": "\u229a",  # ⊚
}


def _ods_type_symbol(data_type: int) -> str:
    """Return a single unicode glyph for an ODS ``DataTypeEnum`` integer value."""
    return _ODS_TYPE_SYMBOLS.get(data_type, "?")


def _entity_icon(base_name: str) -> str:
    """Return a unicode glyph for the given ODS entity *base_name*."""
    return _ENTITY_ICONS.get(base_name, "\u25e6")  # default ◦


# ------------------------------------------------------------------
# Persistence helpers
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
        except ValueError, KeyError:
            failed.append(cond.get("entity", "?"))
            continue
        val: Any = cond.get("val", "")
        with contextlib.suppress(ValueError, TypeError):
            val = int(val)
        if not isinstance(val, int):
            with contextlib.suppress(ValueError, TypeError):
                val = float(val)
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
    except FileNotFoundError, json.JSONDecodeError, OSError:
        pass
    return []


def _save_conditions(conditions: list[dict[str, Any]]) -> None:
    """Persist conditions to ``~/.ods-pilot/browse_conditions.json``.

    Silently ignores write errors so UI operations are never blocked by disk
    issues.
    """
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        _BROWSE_CONDITIONS_FILE.write_text(json.dumps(conditions, indent=2), encoding="utf-8")
    except OSError:
        pass
