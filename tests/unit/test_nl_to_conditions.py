"""Unit tests for NL to conditions parser."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from odsbox_pilot.ai.nl_to_conditions import NlToConditions


class TestNlToConditions:
    """Test natural language to conditions parsing."""

    @pytest.fixture
    def mock_index(self) -> MagicMock:
        """Create mock ModelSearchIndex."""
        index = MagicMock()
        # Mock search to return some sample schema matches
        index.search.return_value = [
            MagicMock(
                kind="attribute",
                entity_name="AoMeasurement",
                item_name="name",
                data_type=7,  # DT_STRING
            ),
            MagicMock(
                kind="attribute",
                entity_name="AoMeasurement",
                item_name="measurement_begin",
                data_type=10,  # DT_DATE
            ),
        ]
        # entity_schema must return a string so it can be joined
        index.entity_schema.return_value = (
            "Entity AoMeasurement:\n  attr name\n  attr id\n  attr measurement_begin"
        )
        # resolve_attribute: return the attr unchanged (all attrs valid)
        index.resolve_attribute.side_effect = lambda entity, attr: attr
        # resolve_entity: return the entity unchanged (all entity names valid)
        index.resolve_entity.side_effect = lambda entity: entity
        # find_date_attribute: return the standard date attr
        index.find_date_attribute.return_value = "measurement_begin"
        return index

    @pytest.fixture
    def mock_pipeline(self) -> MagicMock:
        """Create mock OvLlmPipeline."""
        pipeline = MagicMock()
        return pipeline

    def test_parse_simple_condition(self, mock_index: MagicMock, mock_pipeline: MagicMock) -> None:
        """Test parsing a simple name filter."""
        mock_pipeline.generate.return_value = json.dumps(
            {
                "root_entity": "AoMeasurement",
                "conditions": [
                    {"entity": "AoMeasurement", "attr": "name", "op": "$like", "val": "Profile_*"}
                ],
            }
        )

        parser = NlToConditions(mock_index, mock_pipeline)
        result = parser.parse("Show measurements starting with Profile_")

        assert result.root_entity == "AoMeasurement"
        assert len(result.conditions) == 1
        assert result.conditions[0]["entity"] == "AoMeasurement"
        assert result.conditions[0]["attr"] == "name"
        assert result.conditions[0]["op"] == "$like"
        assert result.conditions[0]["val"] == "Profile_*"

    def test_parse_markdown_code_block(
        self, mock_index: MagicMock, mock_pipeline: MagicMock
    ) -> None:
        """Test parsing when LLM returns JSON in markdown code blocks."""
        mock_pipeline.generate.return_value = """
Sure, here's the parsed query:

```json
{
  "root_entity": "AoTest",
  "conditions": [
    {"entity": "AoTest", "attr": "id", "op": "$gt", "val": 100}
  ]
}
```
"""

        parser = NlToConditions(mock_index, mock_pipeline)
        result = parser.parse("Tests with ID greater than 100")

        assert result.root_entity == "AoTest"
        assert len(result.conditions) == 1
        assert result.conditions[0]["attr"] == "id"
        assert result.conditions[0]["op"] == "$gt"
        assert result.conditions[0]["val"] == 100

    def test_parse_regex_fallback(self, mock_index: MagicMock, mock_pipeline: MagicMock) -> None:
        """Test regex fallback when JSON is embedded in text."""
        mock_pipeline.generate.return_value = """
I understand! The query should be: {"root_entity": "AoMeasurement", "conditions": [{"entity": "AoMeasurement", "attr": "name", "op": "$eq", "val": "Test"}]} 
Hope this helps!
"""

        parser = NlToConditions(mock_index, mock_pipeline)
        result = parser.parse("Find measurement named Test")

        assert result.root_entity == "AoMeasurement"
        assert len(result.conditions) == 1

    def test_parse_between_operator(self, mock_index: MagicMock, mock_pipeline: MagicMock) -> None:
        """Test parsing $between operator with array values."""
        mock_pipeline.generate.return_value = json.dumps(
            {
                "root_entity": "AoTest",
                "conditions": [
                    {"entity": "AoTest", "attr": "id", "op": "$between", "val": [100, 200]}
                ],
            }
        )

        parser = NlToConditions(mock_index, mock_pipeline)
        result = parser.parse("Tests with ID between 100 and 200")

        assert len(result.conditions) == 1
        assert result.conditions[0]["op"] == "$between"
        assert result.conditions[0]["val"] == [100, 200]

    def test_parse_multiple_conditions(
        self, mock_index: MagicMock, mock_pipeline: MagicMock
    ) -> None:
        """Test parsing multiple conditions."""
        mock_pipeline.generate.return_value = json.dumps(
            {
                "root_entity": "AoMeasurement",
                "conditions": [
                    {"entity": "AoMeasurement", "attr": "name", "op": "$like", "val": "Profile_*"},
                    {"entity": "AoMeasurement", "attr": "id", "op": "$gt", "val": 1000},
                ],
            }
        )

        parser = NlToConditions(mock_index, mock_pipeline)
        result = parser.parse("Measurements starting with Profile_ and ID > 1000")

        assert len(result.conditions) == 2

    def test_parse_invalid_json_raises(
        self, mock_index: MagicMock, mock_pipeline: MagicMock
    ) -> None:
        """Test that invalid JSON raises ValueError."""
        mock_pipeline.generate.return_value = "This is not JSON at all!"

        parser = NlToConditions(mock_index, mock_pipeline)
        with pytest.raises(ValueError, match="Failed to parse LLM response"):
            parser.parse("Some query")

    def test_parse_missing_fields_raises(
        self, mock_index: MagicMock, mock_pipeline: MagicMock
    ) -> None:
        """Test that missing required fields raises ValueError."""
        mock_pipeline.generate.return_value = json.dumps(
            {"root_entity": "AoTest"}
        )  # missing conditions

        parser = NlToConditions(mock_index, mock_pipeline)
        with pytest.raises(ValueError, match="missing 'root_entity' or 'conditions'"):
            parser.parse("Some query")

    def test_parse_skips_malformed_conditions(
        self, mock_index: MagicMock, mock_pipeline: MagicMock
    ) -> None:
        """Test that malformed conditions are skipped with warning."""
        mock_pipeline.generate.return_value = json.dumps(
            {
                "root_entity": "AoTest",
                "conditions": [
                    {"entity": "AoTest", "attr": "name", "op": "$eq", "val": "Test"},
                    {"entity": "AoTest", "attr": "id"},  # Missing op and val
                ],
            }
        )

        parser = NlToConditions(mock_index, mock_pipeline)
        result = parser.parse("Some query")

        # Only the valid condition should be included
        assert len(result.conditions) == 1
        assert result.conditions[0]["attr"] == "name"

    def test_date_conditions_merged(self, mock_index: MagicMock, mock_pipeline: MagicMock) -> None:
        """Test that date conditions from parser are merged with LLM conditions."""
        mock_pipeline.generate.return_value = json.dumps(
            {
                "root_entity": "AoMeasurement",
                "conditions": [
                    {"entity": "AoMeasurement", "attr": "name", "op": "$like", "val": "Profile_*"}
                ],
            }
        )

        parser = NlToConditions(mock_index, mock_pipeline)
        # This query contains "letzten Jahr" which should be parsed by date_parser
        result = parser.parse("Zeig mir Messungen Profile_* die im letzten Jahr gemessen wurde")

        # Should have both the name condition and the date condition
        assert len(result.conditions) == 2
        # Find the date condition
        date_cond = next((c for c in result.conditions if c["op"] == "$between"), None)
        assert date_cond is not None
        # attr comes from find_date_attribute on the mock, which returns "measurement_begin"
        assert date_cond["attr"] == "measurement_begin"
        assert isinstance(date_cond["val"], list)
        assert len(date_cond["val"]) == 2

    def test_invalid_attr_corrected_by_resolve(
        self, mock_index: MagicMock, mock_pipeline: MagicMock
    ) -> None:
        """LLM emits wrong-case attr name; resolve_attribute corrects it."""
        mock_pipeline.generate.return_value = json.dumps(
            {
                "root_entity": "AoMeasurement",
                "conditions": [
                    # LLM used lowercase "name" — resolve should return "Name"
                    {"entity": "AoMeasurement", "attr": "name", "op": "$like", "val": "X*"}
                ],
            }
        )
        mock_index.resolve_attribute.side_effect = lambda entity, attr: (
            "Name" if attr == "name" else attr
        )

        parser = NlToConditions(mock_index, mock_pipeline)
        result = parser.parse("Measurements called X*")

        assert len(result.conditions) == 1
        assert result.conditions[0]["attr"] == "Name"

    def test_unknown_attr_skipped(
        self, mock_index: MagicMock, mock_pipeline: MagicMock
    ) -> None:
        """Conditions whose attr cannot be resolved at all are dropped."""
        mock_pipeline.generate.return_value = json.dumps(
            {
                "root_entity": "AoMeasurement",
                "conditions": [
                    # Good condition
                    {"entity": "AoMeasurement", "attr": "name", "op": "$like", "val": "X*"},
                    # Hallucinated attr that has no model match
                    {
                        "entity": "AoMeasurement",
                        "attr": "nonexistentField",
                        "op": "$eq",
                        "val": "42",
                    },
                ],
            }
        )
        # resolve returns attr unchanged for "name", None for unknown
        mock_index.resolve_attribute.side_effect = (
            lambda entity, attr: None if attr == "nonexistentField" else attr
        )

        parser = NlToConditions(mock_index, mock_pipeline)
        result = parser.parse("Some query")

        assert len(result.conditions) == 1
        assert result.conditions[0]["attr"] == "name"

    def test_date_attr_comes_from_find_date_attribute(
        self, mock_index: MagicMock, mock_pipeline: MagicMock
    ) -> None:
        """Date conditions use the attribute returned by find_date_attribute."""
        mock_index.find_date_attribute.return_value = "MeasurementBegin"
        mock_pipeline.generate.return_value = json.dumps(
            {"root_entity": "AoMeasurement", "conditions": []}
        )

        parser = NlToConditions(mock_index, mock_pipeline)
        result = parser.parse("Messungen im letzten Jahr")

        date_conds = [c for c in result.conditions if c["op"] == "$between"]
        assert len(date_conds) == 1
        assert date_conds[0]["attr"] == "MeasurementBegin"

    def test_date_skipped_when_no_date_attr(
        self, mock_index: MagicMock, mock_pipeline: MagicMock
    ) -> None:
        """If find_date_attribute returns None, the date condition is silently dropped."""
        mock_index.find_date_attribute.return_value = None
        mock_pipeline.generate.return_value = json.dumps(
            {"root_entity": "AoMeasurement", "conditions": []}
        )

        parser = NlToConditions(mock_index, mock_pipeline)
        result = parser.parse("Messungen im letzten Jahr")

        assert len(result.conditions) == 0

    def test_full_german_query_profile_electric_last_year(
        self, mock_index: MagicMock, mock_pipeline: MagicMock
    ) -> None:
        """End-to-end: 'Zeig mir Messungen Profile_* die im letzten Jahr im Projekt Electric* gemessen wurden'.

        Expected conditions:
        - MeaResult.Name $like "Profile_*"  (measurement name filter)
        - Test.Name $like "Electric*"        (project name filter via related entity)
        - MeaResult.MeasurementBegin $between [<last-year-start>, <last-year-end>]  (date)
        """
        mock_index.find_date_attribute.return_value = "MeasurementBegin"
        # resolve_attribute accepts the attrs used below
        mock_index.resolve_attribute.side_effect = lambda entity, attr: attr

        mock_pipeline.generate.return_value = json.dumps(
            {
                "root_entity": "MeaResult",
                "conditions": [
                    {
                        "entity": "MeaResult",
                        "attr": "Name",
                        "op": "$like",
                        "val": "Profile_*",
                    },
                    {
                        "entity": "Test",
                        "attr": "Name",
                        "op": "$like",
                        "val": "Electric*",
                    },
                ],
            }
        )

        parser = NlToConditions(mock_index, mock_pipeline)
        result = parser.parse(
            "Zeig mir Messungen Profile_* die im letzten Jahr im Projekt Electric* gemessen wurden"
        )

        assert result.root_entity == "MeaResult"

        # Measurement name filter
        mea_name = next(
            (c for c in result.conditions if c["entity"] == "MeaResult" and c["attr"] == "Name"),
            None,
        )
        assert mea_name is not None, "Expected MeaResult.Name condition"
        assert mea_name["op"] == "$like"
        assert mea_name["val"] == "Profile_*"

        # Project name filter (separate entity — FilterTree will join via relation graph)
        project_name = next(
            (c for c in result.conditions if c["entity"] == "Test" and c["attr"] == "Name"),
            None,
        )
        assert project_name is not None, "Expected Test.Name condition for Electric*"
        assert project_name["op"] == "$like"
        assert project_name["val"] == "Electric*"

        # Date range from "letzten Jahr" — attached to root entity's date attribute
        date_cond = next(
            (
                c
                for c in result.conditions
                if c["entity"] == "MeaResult" and c["op"] == "$between"
            ),
            None,
        )
        assert date_cond is not None, "Expected date condition for 'letzten Jahr'"
        assert date_cond["attr"] == "MeasurementBegin"
        assert isinstance(date_cond["val"], list)
        assert len(date_cond["val"]) == 2
        # ODS DT_DATE strings are 20 chars: "YYYYMMDDHHmmss000000"
        assert all(len(v) == 20 for v in date_cond["val"])
        # Range covers the whole previous calendar year:
        # start = "YYYY0101…" for last year, end = "YYYY0101…" for current year
        from datetime import datetime, timezone

        now = datetime.now(tz=timezone.utc)
        last_year = str(now.year - 1)
        this_year = str(now.year)
        assert date_cond["val"][0].startswith(last_year), "Range start should be in last year"
        assert date_cond["val"][1].startswith(this_year), "Range end should be start of this year"

        # Total: 3 conditions
        assert len(result.conditions) == 3

    def test_no_date_condition_when_none_in_query(
        self, mock_index: MagicMock, mock_pipeline: MagicMock
    ) -> None:
        """Queries without any date expression must produce no $between condition.

        'Measurement named Profile_* of project Electric*' contains no year /
        month / week reference, so parse_date_expressions returns [] and
        find_date_attribute must never be called.
        """
        mock_index.resolve_attribute.side_effect = lambda entity, attr: attr

        mock_pipeline.generate.return_value = json.dumps(
            {
                "root_entity": "MeaResult",
                "conditions": [
                    {"entity": "MeaResult", "attr": "Name", "op": "$like", "val": "Profile_*"},
                    {"entity": "Test", "attr": "Name", "op": "$like", "val": "Electric*"},
                ],
            }
        )

        parser = NlToConditions(mock_index, mock_pipeline)
        result = parser.parse("Measurement named Profile_* of project Electric*")

        assert result.root_entity == "MeaResult"
        assert not any(c["op"] == "$between" for c in result.conditions), (
            "No date condition expected for a query without a date expression"
        )
        # find_date_attribute must NOT be called — no date conditions to merge
        mock_index.find_date_attribute.assert_not_called()
        assert len(result.conditions) == 2

    def test_unknown_root_entity_raises(
        self, mock_index: MagicMock, mock_pipeline: MagicMock
    ) -> None:
        """If the LLM returns an unknown root_entity that cannot be resolved, raise ValueError."""
        mock_index.resolve_entity.side_effect = lambda entity: None  # everything unknown

        mock_pipeline.generate.return_value = json.dumps(
            {"root_entity": "MDL", "conditions": []}
        )

        parser = NlToConditions(mock_index, mock_pipeline)
        with pytest.raises(ValueError, match="unknown root_entity"):
            parser.parse("some query")

    def test_unknown_condition_entity_skipped(
        self, mock_index: MagicMock, mock_pipeline: MagicMock
    ) -> None:
        """Conditions whose entity cannot be resolved go to invalid_conditions, not conditions."""
        # "DateCreated" is an attribute name, not an entity — resolve_entity returns None for it
        mock_index.resolve_entity.side_effect = lambda entity: (
            None if entity == "DateCreated" else entity
        )

        mock_pipeline.generate.return_value = json.dumps(
            {
                "root_entity": "MeaResult",
                "conditions": [
                    {"entity": "MeaResult", "attr": "Name", "op": "$like", "val": "Pro*"},
                    {"entity": "DateCreated", "attr": "MeasurementEnd", "op": "$eq", "val": "x"},
                ],
            }
        )

        parser = NlToConditions(mock_index, mock_pipeline)
        result = parser.parse("measurements Pro*")

        assert result.root_entity == "MeaResult"
        assert len(result.conditions) == 1
        assert result.conditions[0]["entity"] == "MeaResult"
        # invalid entity must appear in invalid_conditions, not be silently dropped
        assert len(result.invalid_conditions) == 1
        assert result.invalid_conditions[0]["entity"] == "DateCreated"
        assert "reason" in result.invalid_conditions[0]

    def test_root_entity_corrected_by_resolve(
        self, mock_index: MagicMock, mock_pipeline: MagicMock
    ) -> None:
        """A close-but-wrong root_entity is corrected via resolve_entity."""
        # LLM returned "meaResult" (wrong case), resolve corrects to "MeaResult"
        mock_index.resolve_entity.side_effect = lambda entity: (
            "MeaResult" if entity.lower() == "mearesult" else entity
        )

        mock_pipeline.generate.return_value = json.dumps(
            {"root_entity": "meaResult", "conditions": []}
        )

        parser = NlToConditions(mock_index, mock_pipeline)
        result = parser.parse("show measurements")

        assert result.root_entity == "MeaResult"
