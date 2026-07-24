"""Unit tests for the pure font-scaling helpers in ``styles``.

These exercise only the wx-free logic (enum, scale factor, point-size
scaling); the wx-dependent helpers are covered by manual/integration use.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from odsbox_pilot import styles
from odsbox_pilot.styles import ScaleLevel


@pytest.fixture(autouse=True)
def _reset_scale() -> Iterator[None]:
    """Ensure each test starts and ends at the default MEDIUM scale."""
    styles.set_scale_level(ScaleLevel.MEDIUM)
    yield
    styles.set_scale_level(ScaleLevel.MEDIUM)


def test_scale_levels_have_expected_values() -> None:
    assert [level.value for level in ScaleLevel] == ["SMALL", "MEDIUM", "LARGE", "XLARGE"]


def test_default_scale_factor_is_medium() -> None:
    assert styles.get_scale_factor() == 1.0


@pytest.mark.parametrize(
    ("level", "expected"),
    [
        (ScaleLevel.SMALL, 0.9),
        (ScaleLevel.MEDIUM, 1.0),
        (ScaleLevel.LARGE, 1.25),
        (ScaleLevel.XLARGE, 1.5),
    ],
)
def test_set_scale_level_updates_factor(level: ScaleLevel, expected: float) -> None:
    styles.set_scale_level(level)
    assert styles.get_scale_factor() == expected


def test_scaled_point_size_medium_is_identity() -> None:
    styles.set_scale_level(ScaleLevel.MEDIUM)
    assert styles.scaled_point_size(10) == 10


def test_scaled_point_size_large_rounds() -> None:
    styles.set_scale_level(ScaleLevel.LARGE)
    # 10 * 1.25 == 12.5 -> round-half-to-even -> 12
    assert styles.scaled_point_size(10) == 12
    # 12 * 1.25 == 15.0 -> 15
    assert styles.scaled_point_size(12) == 15
    # 8 * 1.25 == 10.0 -> 10
    assert styles.scaled_point_size(8) == 10


def test_scaled_point_size_never_below_one() -> None:
    styles.set_scale_level(ScaleLevel.SMALL)
    assert styles.scaled_point_size(1) == 1


def test_scale_level_accepts_string_value() -> None:
    assert ScaleLevel("LARGE") is ScaleLevel.LARGE
