"""OdsPilotApp: application bootstrap."""

from __future__ import annotations

import wx  # type: ignore[import-untyped]

from ods_pilot.connection.manager import ServerConfigManager
from ods_pilot.connection.server_list_dialog import ServerListDialog


class OdsPilotApp(wx.App):
    def OnInit(self) -> bool:  # noqa: N802
        manager = ServerConfigManager()
        dlg = ServerListDialog(None, manager)

        while True:
            result = dlg.ShowModal()
            if result != wx.ID_OK:
                dlg.Destroy()
                return False  # user closed the dialog — exit

            config = dlg.selected_config
            if config is None:
                dlg.Destroy()
                return False

            # Try to connect (opens ConnectDialog flow via Save & Connect path,
            # but here the user clicked "Connect" from the list which means the
            # config already exists — we just need to open ConnectDialog in
            # connect-only mode to resolve the secret and build a ConI).
            con_i = self._connect(dlg, manager, config)
            if con_i is None:
                # Connection cancelled or failed — go back to server list
                continue

            dlg.Destroy()
            self._open_main_frame(con_i, config.name)
            return True

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _connect(self, parent, manager: ServerConfigManager, config):  # type: ignore[return]
        """Open a connect dialog pre-populated with config to authenticate."""
        from ods_pilot.connection.connect_dialog import ConnectDialog

        connect_dlg = ConnectDialog(parent, manager, config=config)
        result = connect_dlg.ShowModal()
        con_i = connect_dlg.con_i if result == wx.ID_OK else None
        connect_dlg.Destroy()
        return con_i

    def _open_main_frame(self, con_i, server_name: str) -> None:
        from ods_pilot.query.main_frame import MainFrame

        frame = MainFrame(con_i, server_name)
        frame.Show()
        self.SetTopWindow(frame)
