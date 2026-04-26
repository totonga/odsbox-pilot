"""OdsPilotApp: application bootstrap."""

from __future__ import annotations

import contextlib

import wx  # type: ignore[import-untyped]

from odsbox_pilot.connection.manager import ServerConfigManager
from odsbox_pilot.connection.server_list_dialog import ServerListDialog


class OdsPilotApp(wx.App):
    def OnInit(self) -> bool:  # noqa: N802
        self.SetExitOnFrameDelete(False)
        return self._run_connection_loop()

    def _run_connection_loop(self) -> bool:
        """Show the server list and connect.  Returns True if a frame was opened."""
        manager = ServerConfigManager()
        dlg = ServerListDialog(None, manager)

        while True:
            result = dlg.ShowModal()
            if result != wx.ID_OK:
                dlg.Destroy()
                return False

            config = dlg.selected_config
            if config is None:
                dlg.Destroy()
                return False

            con_i = self._connect(dlg, manager, config)
            if con_i is None:
                # Connection cancelled or failed — go back to server list
                continue

            dlg.Destroy()
            self._open_main_frame(con_i, config.name)
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

        secret = manager.load_secret(config) or ""
        try:
            wx.BeginBusyCursor()
            con_i = do_connect(config, secret)
            return con_i
        except Exception as exc:
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
            with contextlib.suppress(Exception):
                wx.EndBusyCursor()

    def _open_main_frame(self, con_i, server_name: str) -> None:
        from odsbox_pilot.query.main_frame import MainFrame

        frame = MainFrame(con_i, server_name, on_disconnect=self._on_reconnect)
        frame.Show()
        self.SetTopWindow(frame)
