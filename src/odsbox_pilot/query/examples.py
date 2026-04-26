"""Built-in JAQuel query examples, grouped by category.

Each entry is a tuple of (category, label, json_string).
All json_string values are valid JSON.
"""

from __future__ import annotations

# Format: (category, label, json_str)
EXAMPLES: list[tuple[str, str, str]] = [
    # ── Basic Access ────────────────────────────────────────────────────────
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
