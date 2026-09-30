"""Built-in JAQuel query examples, grouped by category.

Each entry is a tuple of (category, label, json_string).
All json_string values are valid JSON.
"""

from __future__ import annotations

import importlib.util
import json
import logging
from collections.abc import Iterable
from pathlib import Path

# Format: (category, label, json_str)
EXAMPLES: list[tuple[str, str, str]] = [
    # ── Basic Access ────────────────────────────────────────────────────────
    (
        "Basic Access",
        "Some Measurements",
        """{
  "AoMeasurement": {},
  "$attributes": {
    "name": 1,
    "id": 1
  },
  "$options": {
    "$rowlimit": 25
  }
}""",
    ),
    (
        "Basic Access",
        "All Units",
        """{
  "Unit": {}
}""",
    ),
    (
        "Basic Access",
        "Units (selected attributes)",
        """{
  "Unit": {},
  "$attributes": {
    "name": 1,
    "factor": 1,
    "offset": 1
  }
}""",
    ),
    (
        "Basic Access",
        "Units with physical dimension",
        """{
  "Unit": {},
  "$attributes": {
    "name": 1,
    "factor": 1,
    "offset": 1,
    "phys_dimension.name": 1,
    "phys_dimension.length_exp": 1,
    "phys_dimension.mass_exp": 1
  }
}""",
    ),
    (
        "Basic Access",
        "Units ordered by name",
        """{
  "AoUnit": {},
  "$attributes": {
    "id": 1,
    "name": 1
  },
  "$orderby": {
    "name": 1
  }
}""",
    ),
    (
        "Basic Access",
        "Units — limit 5",
        """{
  "AoUnit": {},
  "$options": {
    "$rowlimit": 5
  }
}""",
    ),
    # ── Filters ────────────────────────────────────────────────────────────
    (
        "Filters",
        "Unit by id = 3",
        """{
  "AoUnit": {
    "id": 3
  }
}""",
    ),
    (
        "Filters",
        "Unit by name = 's'",
        """{
  "AoUnit": {
    "name": "s"
  }
}""",
    ),
    (
        "Filters",
        "Units name LIKE 'k*'",
        """{
  "AoUnit": {
    "name": {
      "$like": "k*"
    }
  }
}""",
    ),
    (
        "Filters",
        "Units with ids in [1,2,3]",
        """{
  "AoUnit": {
    "id": {
      "$in": [1, 2, 3]
    }
  }
}""",
    ),
    (
        "Filters",
        "Speed-based Units ($and)",
        """{
  "AoUnit": {
    "phys_dimension": {
      "length_exp": 1,
      "mass_exp": 0,
      "time_exp": -1,
      "current_exp": 0,
      "temperature_exp": 0,
      "molar_amount_exp": 0,
      "luminous_intensity_exp": 0
    }
  },
  "$attributes": {
    "name": 1,
    "factor": 1,
    "offset": 1,
    "phys_dimension.name": 1
  }
}""",
    ),
    (
        "Filters",
        "Speed or time Units ($or)",
        """{
  "AoUnit": {
    "phys_dimension": {
      "$or": [
        {
          "length_exp": 1, "mass_exp": 0, "time_exp": -1,
          "current_exp": 0, "temperature_exp": 0,
          "molar_amount_exp": 0, "luminous_intensity_exp": 0
        },
        {
          "length_exp": 0, "mass_exp": 0, "time_exp": 1,
          "current_exp": 0, "temperature_exp": 0,
          "molar_amount_exp": 0, "luminous_intensity_exp": 0
        }
      ]
    }
  },
  "$attributes": {
    "name": 1,
    "factor": 1,
    "offset": 1,
    "phys_dimension.name": 1
  }
}""",
    ),
    (
        "Filters",
        "Measurements in time range",
        """{
  "AoMeasurement": {
    "measurement_begin": {
      "$between": [
        "2000-04-22T00:00:00.001Z",
        "2024-04-23T00:00:00.002Z"
      ]
    }
  },
  "$options": {
    "$rowlimit": 5
  }
}""",
    ),
    # ── Aggregates ─────────────────────────────────────────────────────────
    (
        "Aggregates",
        "Distinct count of Unit description",
        """{
  "AoUnit": {},
  "$attributes": {
    "description": {
      "$dcount": 1
    }
  }
}""",
    ),
    (
        "Aggregates",
        "Min / Max of Unit factor",
        """{
  "AoUnit": {},
  "$attributes": {
    "factor": {
      "$max": 1,
      "$min": 1
    }
  }
}""",
    ),
    (
        "Aggregates",
        "Group Measurements by name",
        """{
  "AoMeasurement": {},
  "$attributes": {
    "name": 1,
    "description": 1
  },
  "$orderby": {
    "name": 1
  },
  "$groupby": {
    "name": 1,
    "description": 1
  }
}""",
    ),
    # ── Joins ──────────────────────────────────────────────────────────────
    (
        "Joins",
        "MeasurementQuantity inner join",
        """{
  "AoMeasurementQuantity": {},
  "$attributes": {
    "name": 1,
    "unit.name": 1,
    "quantity.name": 1
  },
  "$options": {
    "$rowlimit": 5
  }
}""",
    ),
    (
        "Joins",
        "MeasurementQuantity outer join",
        """{
  "AoMeasurementQuantity": {},
  "$attributes": {
    "name": 1,
    "unit:OUTER.name": 1,
    "quantity:OUTER.name": 1
  },
  "$options": {
    "$rowlimit": 5
  }
}""",
    ),
    # ── OpenMDM Hierarchy ──────────────────────────────────────────────────
    (
        "OpenMDM",
        "AoTest instances (limit 5)",
        """{
  "AoTest": {},
  "$options": {
    "$rowlimit": 5
  }
}""",
    ),
    (
        "OpenMDM",
        "Project instances (limit 5)",
        """{
  "Project": {},
  "$options": {
    "$rowlimit": 5
  }
}""",
    ),
    (
        "OpenMDM",
        "Test instances (limit 5)",
        """{
  "Test": {},
  "$options": {
    "$rowlimit": 5
  }
}""",
    ),
    (
        "OpenMDM",
        "TestStep instances (limit 5)",
        """{
  "TestStep": {},
  "$options": {
    "$rowlimit": 5
  }
}""",
    ),
    (
        "OpenMDM",
        "MeaResult instances (limit 5)",
        """{
  "MeaResult": {},
  "$options": {
    "$rowlimit": 5
  }
}""",
    ),
    (
        "OpenMDM",
        "MeaResult children of TestStep id=4",
        """{
  "TestStep": 4,
  "$attributes": {
    "children": {
      "name": 1,
      "id": 1
    }
  },
  "$options": {
    "$rowlimit": 5
  }
}""",
    ),
    # ── Bulk / Measurement Data ─────────────────────────────────────────────
    (
        "Bulk",
        "MeasurementQuantity for Measurement id=153",
        """{
  "AoMeasurementQuantity": {
    "measurement": 153
  },
  "$attributes": {
    "name": 1,
    "id": 1
  },
  "$options": {
    "$rowlimit": 5
  }
}""",
    ),
    (
        "Bulk",
        "SubMatrix for Measurement id=153",
        """{
  "AoSubmatrix": {
    "measurement": 153
  },
  "$attributes": {
    "name": 1,
    "id": 1,
    "number_of_rows": 1
  },
  "$options": {
    "$rowlimit": 5
  }
}""",
    ),
]

log = logging.getLogger(__name__)


def _normalize_example_item(item: object) -> tuple[str, str, str] | None:
    if isinstance(item, (list, tuple)) and len(item) == 3:
        category, label, query_value = item
    elif isinstance(item, dict):
        category = item.get("category")
        label = item.get("label")
        query_value = item.get("query")
    else:
        return None

    if not isinstance(category, str) or not category.strip():
        return None
    if not isinstance(label, str) or not label.strip():
        return None

    if isinstance(query_value, str):
        try:
            query_obj = json.loads(query_value)
        except Exception:
            return None
    elif isinstance(query_value, dict):
        query_obj = query_value
    else:
        return None

    if not isinstance(query_obj, dict):
        return None
    return category.strip(), label.strip(), json.dumps(query_obj, indent=2)


def _load_custom_examples_from_python_file(path: Path) -> list[tuple[str, str, str]]:
    spec = importlib.util.spec_from_file_location("_odsbox_pilot_custom_examples", path)
    if spec is None or spec.loader is None:
        return []
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    loaded: object = None
    if hasattr(module, "get_examples"):
        maybe_fn = module.get_examples
        if callable(maybe_fn):
            loaded = maybe_fn()
    if loaded is None:
        loaded = getattr(module, "EXAMPLES", None)
    if not isinstance(loaded, Iterable):
        return []

    examples: list[tuple[str, str, str]] = []
    for item in loaded:
        normalized = _normalize_example_item(item)
        if normalized is not None:
            examples.append(normalized)
    return examples


def _load_custom_examples_from_folder(path: Path) -> list[tuple[str, str, str]]:
    examples: list[tuple[str, str, str]] = []
    for file_path in sorted(path.rglob("*.json")):
        try:
            payload = json.loads(file_path.read_text(encoding="utf-8"))
        except Exception:
            log.warning("Could not read custom example file: %s", file_path)
            continue

        if isinstance(payload, dict) and {"category", "label", "query"} <= set(payload):
            normalized = _normalize_example_item(payload)
            if normalized is not None:
                examples.append(normalized)
            continue

        if isinstance(payload, dict):
            category = file_path.parent.name if file_path.parent != path else "Custom"
            label = file_path.stem.replace("_", " ").replace("-", " ").strip() or file_path.stem
            examples.append((category, label, json.dumps(payload, indent=2)))
            continue

        if isinstance(payload, list):
            for entry in payload:
                normalized = _normalize_example_item(entry)
                if normalized is not None:
                    examples.append(normalized)
            continue

        log.warning("Ignoring unsupported custom example payload in %s", file_path)
    return examples


def resolve_examples(
    custom_python_file: str = "",
    custom_examples_folder: str = "",
) -> list[tuple[str, str, str]]:
    """Return built-in examples and optional custom examples."""
    resolved = list(EXAMPLES)

    if custom_python_file.strip():
        path = Path(custom_python_file).expanduser()
        try:
            if path.is_file():
                resolved.extend(_load_custom_examples_from_python_file(path))
            else:
                log.warning("Custom examples python file does not exist: %s", path)
        except Exception:
            log.exception("Failed loading custom examples from python file: %s", path)

    if custom_examples_folder.strip():
        folder = Path(custom_examples_folder).expanduser()
        try:
            if folder.is_dir():
                resolved.extend(_load_custom_examples_from_folder(folder))
            else:
                log.warning("Custom examples folder does not exist: %s", folder)
        except Exception:
            log.exception("Failed loading custom examples from folder: %s", folder)

    return resolved


def categories() -> list[str]:
    """Return unique category names in insertion order."""
    seen: list[str] = []
    for cat, _, _ in EXAMPLES:
        if cat not in seen:
            seen.append(cat)
    return seen


def by_category(category: str) -> list[tuple[str, str]]:
    """Return (label, json_str) pairs for a given category."""
    return [(lbl, q) for cat, lbl, q in EXAMPLES if cat == category]


def categories_for_examples(examples: Iterable[tuple[str, str, str]]) -> list[str]:
    """Return unique category names for an arbitrary example list."""
    seen: list[str] = []
    for cat, _, _ in examples:
        if cat not in seen:
            seen.append(cat)
    return seen


def by_category_for_examples(
    examples: Iterable[tuple[str, str, str]], category: str
) -> list[tuple[str, str]]:
    """Return (label, json_str) pairs for a given category and example list."""
    return [(lbl, q) for cat, lbl, q in examples if cat == category]
