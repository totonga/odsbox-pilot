"""Application-wide preferences dialog (Settings -> Preferences...).

Currently holds the persistent startup font-scaling level as its first
entry. Designed so future application-level settings can be added as
additional sections below without restructuring the dialog.
"""

from __future__ import annotations

from copy import copy

import wx  # type: ignore[import-untyped]

from odsbox_pilot import styles
from odsbox_pilot.models import AppSettings


class AppSettingsDialog(wx.Dialog):
    """Preferences dialog for application-wide (non-AI) settings."""

    def __init__(self, parent: wx.Window, settings: AppSettings) -> None:
        super().__init__(
            parent,
            title="Preferences",
            size=(420, 260),
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
        )
        styles.apply_scaled_app_font(self)
        self.SetSize(self.FromDIP(wx.Size(420, 260)))
        # Work on a copy so Cancel discards changes
        self._settings = copy(settings)
        self._build_ui()
        self.Centre()

    # ------------------------------------------------------------------
    # Build UI
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        outer = wx.BoxSizer(wx.VERTICAL)

        # --- General section (startup scaling is the first entry) ---
        general_box = wx.StaticBox(self, label="General")
        general_sizer = wx.StaticBoxSizer(general_box, wx.VERTICAL)

        scaling_row = wx.BoxSizer(wx.HORIZONTAL)
        scaling_row.Add(
            wx.StaticText(self, label="Startup UI scaling:"),
            flag=wx.ALIGN_CENTER_VERTICAL | wx.RIGHT,
            border=8,
        )
        levels = [level.value for level in styles.ScaleLevel]
        self._choice_scaling = wx.Choice(self, choices=levels)
        selected = (
            self._settings.startup_scaling
            if self._settings.startup_scaling in levels
            else styles.ScaleLevel.MEDIUM.value
        )
        self._choice_scaling.SetStringSelection(selected)
        scaling_row.Add(self._choice_scaling, flag=wx.ALIGN_CENTER_VERTICAL)
        general_sizer.Add(scaling_row, flag=wx.ALL, border=6)

        hint = wx.StaticText(self, label="Takes effect the next time ODS Pilot is started.")
        hint.SetForegroundColour(wx.Colour(100, 100, 100))
        general_sizer.Add(hint, flag=wx.LEFT | wx.RIGHT | wx.BOTTOM, border=6)

        outer.Add(general_sizer, flag=wx.EXPAND | wx.ALL, border=10)

        # Future application-level settings sections go here, below General.

        # --- Standard buttons ---
        btn_sizer = wx.StdDialogButtonSizer()
        btn_ok = wx.Button(self, wx.ID_OK, "OK")
        btn_ok.SetDefault()
        btn_sizer.AddButton(btn_ok)
        btn_cancel = wx.Button(self, wx.ID_CANCEL, "Cancel")
        btn_sizer.AddButton(btn_cancel)
        btn_sizer.Realize()
        outer.Add(btn_sizer, flag=wx.EXPAND | wx.ALL, border=10)

        self.SetSizer(outer)
        btn_ok.Bind(wx.EVT_BUTTON, self._on_ok)

    # ------------------------------------------------------------------
    # OK handler
    # ------------------------------------------------------------------

    def _on_ok(self, _event: wx.Event) -> None:
        self._settings.startup_scaling = self._choice_scaling.GetStringSelection()
        self.EndModal(wx.ID_OK)

    def get_settings(self) -> AppSettings:
        """Return the (potentially modified) settings."""
        return self._settings
