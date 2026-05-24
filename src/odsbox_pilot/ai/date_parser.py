"""Parse German and English date expressions into ODS DT_DATE format."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta


@dataclass
class DateCondition:
    """A parsed date expression with keyword and ODS DT_DATE range."""

    keyword: str  # Original expression (e.g., "letzten Jahr", "last year")
    start_ods: str  # ODS DT_DATE format "YYYYMMDDHHmmss000000"
    end_ods: str  # ODS DT_DATE format "YYYYMMDDHHmmss000000"


def _to_ods_date(dt: datetime) -> str:
    """Convert datetime to ODS DT_DATE format (20-char string)."""
    return dt.strftime("%Y%m%d%H%M%S") + "000000"


def parse_date_expressions(text: str, now: datetime | None = None) -> list[DateCondition]:
    """Parse German and English date expressions from text.

    Recognized patterns:
        - "letzten Jahr" / "last year" → previous calendar year
        - "letzten Monat" / "last month" → previous calendar month
        - "letzte Woche" / "last week" → previous 7 days
        - "YYYY" (4-digit year) → full year range

    Args:
        text: Input text potentially containing date expressions.
        now: Reference datetime (defaults to current UTC time).

    Returns:
        List of DateCondition objects, one per matched expression.
    """
    if now is None:
        now = datetime.now(UTC)

    conditions: list[DateCondition] = []

    # Pattern 1: Last year (German / English)
    last_year_pattern = re.compile(
        r"\b(letzten?\s+jahr|last\s+year)\b",
        re.IGNORECASE,
    )
    for match in last_year_pattern.finditer(text):
        year = now.year - 1
        start = datetime(year, 1, 1, 0, 0, 0, tzinfo=UTC)
        end = datetime(year + 1, 1, 1, 0, 0, 0, tzinfo=UTC)
        conditions.append(
            DateCondition(
                keyword=match.group(0),
                start_ods=_to_ods_date(start),
                end_ods=_to_ods_date(end),
            )
        )

    # Pattern 2: Last month (German / English)
    last_month_pattern = re.compile(
        r"\b(letzten?\s+monat|last\s+month)\b",
        re.IGNORECASE,
    )
    for match in last_month_pattern.finditer(text):
        # Go to first day of current month, then subtract 1 month
        first_of_this_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        if first_of_this_month.month == 1:
            start = first_of_this_month.replace(year=first_of_this_month.year - 1, month=12)
        else:
            start = first_of_this_month.replace(month=first_of_this_month.month - 1)
        end = first_of_this_month
        conditions.append(
            DateCondition(
                keyword=match.group(0),
                start_ods=_to_ods_date(start),
                end_ods=_to_ods_date(end),
            )
        )

    # Pattern 3: Last week (German / English)
    last_week_pattern = re.compile(
        r"\b(letzte\s+woche|last\s+week)\b",
        re.IGNORECASE,
    )
    for match in last_week_pattern.finditer(text):
        # Previous 7 days (inclusive today)
        end = now.replace(hour=0, minute=0, second=0, microsecond=0)
        start = end - timedelta(days=7)
        conditions.append(
            DateCondition(
                keyword=match.group(0),
                start_ods=_to_ods_date(start),
                end_ods=_to_ods_date(end),
            )
        )

    # Pattern 4: 4-digit year (e.g., "2024")
    year_pattern = re.compile(r"\b(20\d{2}|19\d{2})\b")
    for match in year_pattern.finditer(text):
        year = int(match.group(0))
        start = datetime(year, 1, 1, 0, 0, 0, tzinfo=UTC)
        end = datetime(year + 1, 1, 1, 0, 0, 0, tzinfo=UTC)
        conditions.append(
            DateCondition(
                keyword=match.group(0),
                start_ods=_to_ods_date(start),
                end_ods=_to_ods_date(end),
            )
        )

    return conditions
