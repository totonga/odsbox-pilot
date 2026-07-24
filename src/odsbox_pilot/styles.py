"""Central font-scaling helpers for the ODS Pilot GUI.

This module holds the global font-scale factor (controlled by the
``--scaling`` command-line option) plus small helpers used throughout the
wxPython UI so that font handling is defined in one place instead of being
duplicated ad-hoc across panels and dialogs.

The pure helpers (:class:`ScaleLevel`, :func:`get_scale_factor`,
:func:`scaled_point_size`) have no wx dependency and are unit-testable
without a running ``wx.App``.
"""

from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import wx


class ScaleLevel(StrEnum):
    """Named global font-scale levels selectable via ``--scaling``."""

    SMALL = "SMALL"
    MEDIUM = "MEDIUM"
    LARGE = "LARGE"
    XLARGE = "XLARGE"


_SCALE_FACTORS: dict[ScaleLevel, float] = {
    ScaleLevel.SMALL: 0.9,
    ScaleLevel.MEDIUM: 1.0,
    ScaleLevel.LARGE: 1.25,
    ScaleLevel.XLARGE: 1.5,
}

# Module-global scale factor; defaults to MEDIUM (no visual change).
_scale_factor: float = 1.0


def set_scale_level(level: ScaleLevel) -> None:
    """Set the global font-scale factor from a :class:`ScaleLevel`."""
    global _scale_factor
    _scale_factor = _SCALE_FACTORS[level]


def get_scale_factor() -> float:
    """Return the current global font-scale factor (1.0 == unscaled)."""
    return _scale_factor


def scaled_point_size(base_pt: int) -> int:
    """Scale an absolute font point size by the global scale factor.

    Use this for the few places that render at a fixed, hardcoded point
    size (e.g. splash-screen title, window-icon glyph, monospace preview).
    """
    return max(1, round(base_pt * _scale_factor))


def apply_scaled_app_font(window: wx.Window) -> None:
    """Apply the scaled default GUI font to *window* and its future children.

    Rebuilds the font from ``wx.SYS_DEFAULT_GUI_FONT`` every call, so it is
    idempotent and independent of any parent-font-inheritance chain. Call
    this in the ``__init__`` of every top-level frame/dialog, right after
    ``super().__init__()`` and before child widgets are created, so they
    inherit the scaled font at construction time.
    """
    window.SetFont(scaled_gui_font())


def scaled_gui_font() -> wx.Font:
    """Return the system default GUI font scaled by the global factor.

    Useful for widgets (such as ``wx.grid.Grid`` cells and labels) that do
    not inherit their parent window's font automatically.
    """
    import wx  # noqa: PLC0415

    font = wx.SystemSettings.GetFont(wx.SYS_DEFAULT_GUI_FONT)
    font.SetPointSize(scaled_point_size(font.GetPointSize()))
    return font


def bold_font(widget: wx.Window) -> wx.Font:
    """Return *widget*'s current font in bold."""
    return widget.GetFont().Bold()


def italic_font(widget: wx.Window) -> wx.Font:
    """Return *widget*'s current font in italic."""
    return widget.GetFont().Italic()
