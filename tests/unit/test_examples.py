"""Unit tests for built-in query examples."""

from __future__ import annotations

import json

import pytest

from ods_pilot.query.examples import EXAMPLES, by_category, categories


class TestExamplesContent:
    def test_not_empty(self) -> None:
        assert len(EXAMPLES) > 0

    @pytest.mark.parametrize("cat,label,query_str", EXAMPLES)
    def test_each_example_is_valid_json(self, cat: str, label: str, query_str: str) -> None:
        try:
            parsed = json.loads(query_str)
        except json.JSONDecodeError as exc:
            pytest.fail(f"Example '{label}' ({cat}) is not valid JSON: {exc}")
        assert isinstance(parsed, dict), f"Example '{label}' root must be a JSON object"

    @pytest.mark.parametrize("cat,label,query_str", EXAMPLES)
    def test_each_example_has_non_empty_label(self, cat: str, label: str, query_str: str) -> None:
        assert label.strip(), f"Example in category '{cat}' has an empty label"

    @pytest.mark.parametrize("cat,label,query_str", EXAMPLES)
    def test_each_example_has_category(self, cat: str, label: str, query_str: str) -> None:
        assert cat.strip(), f"Example '{label}' has an empty category"


class TestCategoryHelpers:
    def test_categories_returns_list(self) -> None:
        cats = categories()
        assert isinstance(cats, list)
        assert len(cats) > 0

    def test_categories_no_duplicates(self) -> None:
        cats = categories()
        assert len(cats) == len(set(cats))

    def test_by_category_returns_correct_items(self) -> None:
        cats = categories()
        for cat in cats:
            items = by_category(cat)
            assert len(items) > 0
            for label, q in items:
                assert label
                json.loads(q)  # must be valid JSON

    def test_by_category_unknown_returns_empty(self) -> None:
        assert by_category("__nonexistent__") == []
