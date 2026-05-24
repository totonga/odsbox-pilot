"""Unit tests for date expression parser."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from odsbox_pilot.ai.date_parser import parse_date_expressions


class TestDateParser:
    """Test date expression parsing."""

    def test_last_year_german(self) -> None:
        """Test 'letzten Jahr' pattern."""
        now = datetime(2026, 5, 24, 12, 0, 0, tzinfo=UTC)
        results = parse_date_expressions("Zeig mir Messungen vom letzten Jahr", now)

        assert len(results) == 1
        assert results[0].keyword in ("letzten Jahr", "letzten Jahr")
        assert results[0].start_ods == "20250101000000000000"
        assert results[0].end_ods == "20260101000000000000"

    def test_last_year_english(self) -> None:
        """Test 'last year' pattern."""
        now = datetime(2026, 5, 24, 12, 0, 0, tzinfo=UTC)
        results = parse_date_expressions("Show measurements from last year", now)

        assert len(results) == 1
        assert results[0].keyword == "last year"
        assert results[0].start_ods == "20250101000000000000"
        assert results[0].end_ods == "20260101000000000000"

    def test_last_month_german(self) -> None:
        """Test 'letzten Monat' pattern."""
        now = datetime(2026, 5, 24, 12, 0, 0, tzinfo=UTC)
        results = parse_date_expressions("Daten vom letzten Monat", now)

        assert len(results) == 1
        assert results[0].keyword in ("letzten Monat", "letzten Monat")
        assert results[0].start_ods == "20260401000000000000"  # April 1st
        assert results[0].end_ods == "20260501000000000000"  # May 1st

    def test_last_month_english(self) -> None:
        """Test 'last month' pattern."""
        now = datetime(2026, 5, 24, 12, 0, 0, tzinfo=UTC)
        results = parse_date_expressions("Data from last month", now)

        assert len(results) == 1
        assert results[0].keyword == "last month"
        assert results[0].start_ods == "20260401000000000000"
        assert results[0].end_ods == "20260501000000000000"

    def test_last_month_january(self) -> None:
        """Test 'last month' when current month is January (should go to previous year)."""
        now = datetime(2026, 1, 15, 12, 0, 0, tzinfo=UTC)
        results = parse_date_expressions("last month", now)

        assert len(results) == 1
        assert results[0].start_ods == "20251201000000000000"  # December 1st 2025
        assert results[0].end_ods == "20260101000000000000"  # January 1st 2026

    def test_last_week_german(self) -> None:
        """Test 'letzte Woche' pattern."""
        now = datetime(2026, 5, 24, 0, 0, 0, tzinfo=UTC)
        results = parse_date_expressions("Tests von letzte Woche", now)

        assert len(results) == 1
        assert results[0].keyword == "letzte Woche"
        # 7 days ago from May 24 is May 17
        assert results[0].start_ods == "20260517000000000000"
        assert results[0].end_ods == "20260524000000000000"

    def test_last_week_english(self) -> None:
        """Test 'last week' pattern."""
        now = datetime(2026, 5, 24, 0, 0, 0, tzinfo=UTC)
        results = parse_date_expressions("Tests from last week", now)

        assert len(results) == 1
        assert results[0].keyword == "last week"
        assert results[0].start_ods == "20260517000000000000"
        assert results[0].end_ods == "20260524000000000000"

    def test_year_literal(self) -> None:
        """Test 4-digit year literal (e.g., '2024')."""
        results = parse_date_expressions("Show data from 2024")

        assert len(results) == 1
        assert results[0].keyword == "2024"
        assert results[0].start_ods == "20240101000000000000"
        assert results[0].end_ods == "20250101000000000000"

    def test_multiple_expressions(self) -> None:
        """Test multiple date expressions in one string."""
        now = datetime(2026, 5, 24, 12, 0, 0, tzinfo=UTC)
        results = parse_date_expressions(
            "Show measurements from last year or last month or 2024", now
        )

        assert len(results) == 3
        keywords = {r.keyword for r in results}
        assert "last year" in keywords
        assert "last month" in keywords
        assert "2024" in keywords

    def test_no_expressions(self) -> None:
        """Test text with no date expressions."""
        results = parse_date_expressions("Show all measurements with name Profile_*")

        assert len(results) == 0

    def test_case_insensitive(self) -> None:
        """Test case-insensitive matching."""
        now = datetime(2026, 5, 24, 12, 0, 0, tzinfo=UTC)
        results = parse_date_expressions("LAST YEAR", now)

        assert len(results) == 1
        assert results[0].start_ods == "20250101000000000000"

    @pytest.mark.parametrize(
        ("text", "expected_count"),
        [
            ("letzten Jahr", 1),
            ("last year", 1),
            ("letzten Monat", 1),
            ("last month", 1),
            ("letzte Woche", 1),
            ("last week", 1),
            ("2024", 1),
            ("2025", 1),
            ("", 0),
            ("no dates here", 0),
        ],
    )
    def test_parametrized(self, text: str, expected_count: int) -> None:
        """Parametrized test for various inputs."""
        now = datetime(2026, 5, 24, 12, 0, 0, tzinfo=UTC)
        results = parse_date_expressions(text, now)
        assert len(results) == expected_count
