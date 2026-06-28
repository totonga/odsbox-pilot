"""AI Query Assistant settings dialog."""

from __future__ import annotations

import logging
import threading
from copy import copy

import wx  # type: ignore[import-untyped]

from odsbox_pilot.models import AiSettings

log = logging.getLogger(__name__)

_DEVICES = ["NPU", "GPU", "CPU"]


class AiSettingsDialog(wx.Dialog):
    """Configuration dialog for the AI Query Assistant.

    Lets the user enable/disable AI, select the inference device, and download
    the required OpenVINO model from HuggingFace Hub.
    """

    def __init__(self, parent: wx.Window, settings: AiSettings) -> None:
        super().__init__(
            parent,
            title="AI Query Assistant Settings",
            size=(540, 440),
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
        )
        # Work on a copy so Cancel discards changes
        self._settings = copy(settings)
        self._downloading = False
        self._build_ui()
        self._refresh_status()
        self.Centre()

    # ------------------------------------------------------------------
    # Build UI
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        outer = wx.BoxSizer(wx.VERTICAL)

        # --- Status section ---
        status_box = wx.StaticBox(self, label="Model Status")
        status_sizer = wx.StaticBoxSizer(status_box, wx.VERTICAL)

        self._lbl_model_id = wx.StaticText(self, label=f"Model: {self._settings.model_id}")
        status_sizer.Add(self._lbl_model_id, flag=wx.ALL, border=4)

        self._lbl_status = wx.StaticText(self, label="Checking…")
        status_sizer.Add(self._lbl_status, flag=wx.ALL, border=4)

        self._lbl_model_path = wx.StaticText(self, label="")
        self._lbl_model_path.SetForegroundColour(wx.Colour(100, 100, 100))
        status_sizer.Add(self._lbl_model_path, flag=wx.ALL | wx.EXPAND, border=4)

        outer.Add(status_sizer, flag=wx.EXPAND | wx.ALL, border=10)

        # --- Configuration ---
        config_box = wx.StaticBox(self, label="Configuration")
        config_sizer = wx.StaticBoxSizer(config_box, wx.VERTICAL)

        self._chk_enabled = wx.CheckBox(self, label="Enable AI Query Assistant")
        self._chk_enabled.SetValue(self._settings.enabled)
        config_sizer.Add(self._chk_enabled, flag=wx.ALL, border=6)

        device_row = wx.BoxSizer(wx.HORIZONTAL)
        device_row.Add(
            wx.StaticText(self, label="Inference device:"),
            flag=wx.ALIGN_CENTER_VERTICAL | wx.RIGHT,
            border=8,
        )
        self._choice_device = wx.Choice(self, choices=_DEVICES)
        sel = self._settings.device if self._settings.device in _DEVICES else "CPU"
        self._choice_device.SetStringSelection(sel)
        device_row.Add(self._choice_device, flag=wx.ALIGN_CENTER_VERTICAL)
        config_sizer.Add(device_row, flag=wx.ALL, border=6)

        outer.Add(config_sizer, flag=wx.EXPAND | wx.ALL, border=10)

        # --- Download section ---
        dl_box = wx.StaticBox(self, label="Download Model (~1 GB)")
        dl_sizer = wx.StaticBoxSizer(dl_box, wx.VERTICAL)

        dl_row = wx.BoxSizer(wx.HORIZONTAL)
        self._btn_download = wx.Button(self, label="Download Model")
        self._btn_download.Bind(wx.EVT_BUTTON, self._on_download)
        dl_row.Add(self._btn_download, flag=wx.RIGHT, border=8)

        self._lbl_dl_status = wx.StaticText(self, label="")
        dl_row.Add(self._lbl_dl_status, flag=wx.ALIGN_CENTER_VERTICAL)
        dl_sizer.Add(dl_row, flag=wx.ALL, border=6)

        self._gauge = wx.Gauge(self, range=100, style=wx.GA_HORIZONTAL | wx.GA_SMOOTH)
        self._gauge.Hide()
        dl_sizer.Add(
            self._gauge,
            flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM,
            border=6,
        )
        outer.Add(dl_sizer, flag=wx.EXPAND | wx.ALL, border=10)

        # --- Standard buttons ---
        btn_sizer = wx.StdDialogButtonSizer()
        self._btn_ok = wx.Button(self, wx.ID_OK, "Apply")
        self._btn_ok.SetDefault()
        btn_sizer.AddButton(self._btn_ok)
        btn_cancel = wx.Button(self, wx.ID_CANCEL, "Cancel")
        btn_sizer.AddButton(btn_cancel)
        btn_sizer.Realize()
        outer.Add(btn_sizer, flag=wx.EXPAND | wx.ALL, border=10)

        self.SetSizer(outer)
        self._btn_ok.Bind(wx.EVT_BUTTON, self._on_ok)

    # ------------------------------------------------------------------
    # Status / state helpers
    # ------------------------------------------------------------------

    def _refresh_status(self) -> None:
        try:
            from odsbox_pilot.ai.model_manager import ModelManager
        except ImportError:
            self._lbl_status.SetForegroundColour(wx.Colour(180, 0, 0))
            self._lbl_status.SetLabel("✗ AI dependencies not installed — run: uv sync --extra ai")
            self._btn_download.Disable()
            self._chk_enabled.Disable()
            return

        manager = ModelManager(self._settings.model_cache_dir)
        model_dir = manager.get_model_dir(self._settings.model_id)

        if manager.is_downloaded(self._settings.model_id):
            self._lbl_status.SetForegroundColour(wx.Colour(0, 140, 0))
            self._lbl_status.SetLabel("✓ Model downloaded and ready")
            self._lbl_model_path.SetLabel(str(model_dir))
            self._btn_download.SetLabel("Re-download Model")
            self._chk_enabled.Enable()
        else:
            self._lbl_status.SetForegroundColour(wx.Colour(180, 0, 0))
            self._lbl_status.SetLabel("✗ Model not downloaded yet")
            self._lbl_model_path.SetLabel(
                f"Download later to: {model_dir}  •  AI can still be enabled now"
            )
            self._btn_download.SetLabel("Download Model (~1 GB)")
            self._chk_enabled.Enable()

        self.Layout()

    # ------------------------------------------------------------------
    # Download
    # ------------------------------------------------------------------

    def _on_download(self, _event: wx.Event) -> None:
        if self._downloading:
            return

        try:
            from odsbox_pilot.ai.model_manager import ModelManager  # noqa: F401
        except ImportError:
            wx.MessageBox(
                "AI dependencies are not installed.\n\n"
                "Run the following command in a terminal:\n\n"
                "  uv sync --extra ai",
                "Missing Dependencies",
                wx.OK | wx.ICON_WARNING,
                self,
            )
            return

        self._downloading = True
        self._btn_download.Disable()
        self._gauge.SetValue(0)
        self._gauge.Show()
        self._lbl_dl_status.SetLabel("Starting download…")
        self.Layout()

        def _run() -> None:
            from odsbox_pilot.ai.model_manager import ModelManager

            manager = ModelManager(self._settings.model_cache_dir)
            try:

                def _progress(fraction: float, status: str) -> None:
                    wx.CallAfter(self._gauge.SetValue, int(fraction * 100))
                    wx.CallAfter(self._lbl_dl_status.SetLabel, status)

                manager.download_model(self._settings.model_id, _progress)
                wx.CallAfter(self._on_download_done, True, "")
            except Exception as exc:
                wx.CallAfter(self._on_download_done, False, str(exc))

        threading.Thread(target=_run, daemon=True).start()

    def _on_download_done(self, success: bool, error: str) -> None:
        self._downloading = False
        self._btn_download.Enable()
        self._gauge.Hide()
        self.Layout()

        if success:
            self._lbl_dl_status.SetLabel("")
            self._refresh_status()
            wx.MessageBox(
                "Model downloaded successfully!\n\nAI Query Assistant is ready to use.",
                "Download Complete",
                wx.OK | wx.ICON_INFORMATION,
                self,
            )
        else:
            self._lbl_dl_status.SetLabel(f"Error: {error[:60]}")
            log.error("Model download failed: %s", error)
            wx.MessageBox(
                f"Download failed:\n\n{error}",
                "Download Error",
                wx.OK | wx.ICON_ERROR,
                self,
            )

    # ------------------------------------------------------------------
    # OK handler
    # ------------------------------------------------------------------

    def _on_ok(self, _event: wx.Event) -> None:
        self._settings.enabled = self._chk_enabled.GetValue()
        self._settings.device = self._choice_device.GetStringSelection()
        self.EndModal(wx.ID_OK)

    def get_settings(self) -> AiSettings:
        """Return the (potentially modified) settings."""
        return self._settings
