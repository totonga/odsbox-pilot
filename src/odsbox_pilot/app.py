"""OdsPilotApp: application bootstrap."""

from __future__ import annotations

import wx  # type: ignore[import-untyped]

from odsbox_pilot.connection.manager import ServerConfigManager
from odsbox_pilot.connection.server_list_dialog import ServerListDialog
from odsbox_pilot.models import AppSettings, ServerConfig
from odsbox_pilot.styles import ScaleLevel, set_scale_level


class OdsPilotApp(wx.App):
    def __init__(self, initial_server: str | None = None, scaling: str | None = None) -> None:
        self._initial_server = initial_server
        # None => use the persisted startup scaling; a value => CLI override.
        self._scaling_override = ScaleLevel(scaling) if scaling is not None else None
        super().__init__()

    def OnInit(self) -> bool:  # noqa: N802
        if self._scaling_override is not None:
            scaling = self._scaling_override
        else:
            scaling = ScaleLevel(AppSettings.load().startup_scaling)
        set_scale_level(scaling)
        self.SetExitOnFrameDelete(False)
        if self._initial_server is not None:
            return self._connect_to_named_server(self._initial_server)
        return self._run_connection_loop()

    def _connect_to_named_server(self, name_or_id: str) -> bool:
        """Try to connect directly to a server matching *name_or_id* (name or id)."""
        manager = ServerConfigManager()
        config = next(
            (c for c in manager.configs if c.name == name_or_id or c.id == name_or_id),
            None,
        )
        if config is None:
            wx.MessageBox(
                f"No saved server found matching {name_or_id!r}.\nFalling back to server list.",
                "Server Not Found",
                wx.OK | wx.ICON_WARNING,
            )
            return self._run_connection_loop()
        con_i = self._connect(None, manager, config)
        if con_i is None:
            return self._run_connection_loop()
        self._open_main_frame(con_i, config.name, config)
        return True

    def _run_connection_loop(self) -> bool:
        """Show the server list and connect.  Returns True if a frame was opened."""
        manager = ServerConfigManager()
        dlg = ServerListDialog(None, manager)

        while True:
            result = dlg.ShowModal()
            if result != wx.ID_OK:
                dlg.Destroy()
                return False

            if dlg.connected_con_i is not None:
                config = dlg.selected_config
                server_name = config.name if config is not None else "ATFX"
                con_i = dlg.connected_con_i
                dlg.Destroy()
                self._open_main_frame(con_i, server_name, config)
                return True

            config = dlg.selected_config
            if config is None:
                dlg.Destroy()
                return False

            con_i = self._connect(dlg, manager, config)
            if con_i is None:
                # Connection cancelled or failed — go back to server list
                continue

            dlg.Destroy()
            self._open_main_frame(con_i, config.name, config)
            return True

    def _on_reconnect(self) -> None:
        """Called via wx.CallAfter after the user disconnects from a session."""
        if not self._run_connection_loop():
            self.ExitMainLoop()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _connect(self, parent, manager: ServerConfigManager, config):  # type: ignore[return]
        """Connect using saved credentials; open ConnectDialog only on failure."""
        from odsbox_pilot.connection.connect_dialog import ConnectDialog, do_connect
        from odsbox_pilot.splash import hide_splash, show_splash

        secret = manager.load_secret(config) or ""
        splash = None
        try:
            splash = show_splash(parent)
            con_i = do_connect(config, secret)
            return con_i
        except Exception as exc:
            hide_splash(splash)
            splash = None
            wx.MessageBox(
                f"Connection failed:\n\n{exc}\n\nPlease check your settings.",
                "Connection Error",
                wx.OK | wx.ICON_ERROR,
                parent,
            )
            # Fall back to edit dialog so user can fix credentials
            connect_dlg = ConnectDialog(parent, manager, config=config)
            result = connect_dlg.ShowModal()
            con_i = connect_dlg.con_i if result == wx.ID_OK else None
            connect_dlg.Destroy()
            return con_i
        finally:
            if splash is not None:
                hide_splash(splash)

    def _open_main_frame(
        self, con_i, server_name: str, server_config: ServerConfig | None = None
    ) -> None:
        from odsbox_pilot.query.main_frame import MainFrame

        frame = MainFrame(
            con_i, server_name, server_config=server_config, on_disconnect=self._on_reconnect
        )
        frame.Show()
        self.SetTopWindow(frame)
