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
                data_type=8,  # DT_DATE
            ),
        ]
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
        assert date_cond["attr"] == "measurement_begin"
        assert isinstance(date_cond["val"], list)
        assert len(date_cond["val"]) == 2
