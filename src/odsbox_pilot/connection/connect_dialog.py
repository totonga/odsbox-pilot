"""ConnectDialog: create or edit an ODS server config.

Three tabs: Basic (username/password), M2M (client credentials), OIDC.
On OK the config is saved and, if the user clicked "Save & Connect",
the returned ConI is available via the `con_i` property.
"""

from __future__ import annotations

import contextlib
import logging
import uuid

import wx  # type: ignore[import-untyped]

from odsbox_pilot.connection.manager import ServerConfigManager
from odsbox_pilot.models import AuthType, ServerConfig

_log = logging.getLogger(__name__)


def do_connect(config: ServerConfig, secret: str):  # type: ignore[return]
    """Create a live ConI from *config* + *secret* without any UI."""
    if config.auth_type == AuthType.ATFX:
        from odsbox_pilot.connection.atfx_factory import open_atfx

        return open_atfx(config.url)

    from odsbox.con_i_factory import ConIFactory  # type: ignore[import-untyped]

    ctx = config.context_variables if config.context_variables else None
    if config.auth_type == AuthType.BASIC:
        return ConIFactory.basic(
            url=config.url,
            username=config.username,
            password=secret,
            verify_certificate=config.verify_certificate,
            context_variables=ctx,
        )
    elif config.auth_type == AuthType.M2M:
        return ConIFactory.m2m(
            url=config.url,
            token_endpoint=config.token_endpoint,
            client_id=config.client_id,
            client_secret=secret,
            scope=config.scope or None,
            verify_certificate=config.verify_certificate,
            context_variables=ctx,
        )
    else:  # OIDC
        return ConIFactory.oidc(
            url=config.url,
            client_id=config.client_id,
            redirect_uri=config.redirect_uri,
            redirect_url_allow_insecure=config.redirect_url_allow_insecure,
            webfinger_path_prefix=config.webfinger_path_prefix,
            verify_certificate=config.verify_certificate,
            context_variables=ctx,
        )


class ConnectDialog(wx.Dialog):
    """Dialog to create or edit an ODS server connection config."""

    def __init__(
        self,
        parent: wx.Window | None,
        manager: ServerConfigManager,
        config: ServerConfig | None,
    ) -> None:
        is_existing_config = bool(config and any(c.id == config.id for c in manager.configs))
        title = "Edit Server" if is_existing_config else "New Server"
        super().__init__(
            parent,
            title=title,
            size=wx.Size(480, 480),
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
        )
        self._manager = manager
        self._original_config = config if is_existing_config else None
        self._con_i = None  # set when "Save & Connect" succeeds
        self._result_config: ServerConfig | None = None

        self._build_ui(config)
        self._populate(config)
        self.Centre()

    # ------------------------------------------------------------------
    # Public result
    # ------------------------------------------------------------------

    @property
    def con_i(self):  # type: ignore[return]
        """The live ConI instance after a successful 'Save & Connect'."""
        return self._con_i

    @property
    def result_config(self) -> ServerConfig | None:
        """Config associated with a successful dialog result."""
        return self._result_config

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self, config: ServerConfig | None) -> None:
        panel = wx.Panel(self)
        self._main_panel = panel
        vbox = wx.BoxSizer(wx.VERTICAL)

        # --- Common fields (name + URL) ---
        grid = wx.FlexGridSizer(cols=2, hgap=8, vgap=6)
        grid.AddGrowableCol(1)

        grid.Add(wx.StaticText(panel, label="Name:"), flag=wx.ALIGN_CENTER_VERTICAL)
        self._txt_name = wx.TextCtrl(panel, size=wx.Size(300, -1))
        grid.Add(self._txt_name, flag=wx.EXPAND)

        grid.Add(wx.StaticText(panel, label="URL:"), flag=wx.ALIGN_CENTER_VERTICAL)
        self._txt_url = wx.TextCtrl(panel, size=wx.Size(300, -1))
        grid.Add(self._txt_url, flag=wx.EXPAND)

        self._chk_verify = wx.CheckBox(panel, label="Verify TLS certificate")
        self._chk_verify.SetValue(True)
        grid.Add(wx.Size(0, 0))
        grid.Add(self._chk_verify)

        vbox.Add(grid, flag=wx.EXPAND | wx.ALL, border=10)

        # --- Auth notebook ---
        self._notebook = wx.Notebook(panel)
        self._page_basic = self._build_basic_page()
        self._page_m2m = self._build_m2m_page()
        self._page_oidc = self._build_oidc_page()
        self._page_atfx = self._build_atfx_page()
        self._notebook.AddPage(self._page_basic, "Basic")
        self._notebook.AddPage(self._page_m2m, "M2M")
        self._notebook.AddPage(self._page_oidc, "OIDC")
        self._notebook.AddPage(self._page_atfx, "ATFX File")
        vbox.Add(self._notebook, proportion=1, flag=wx.EXPAND | wx.LEFT | wx.RIGHT, border=10)

        # --- Context variables (applies to all auth methods) ---
        self._cpane = wx.CollapsiblePane(panel, label="Context Variables")
        self._build_context_vars_content(self._cpane.GetPane())
        vbox.Add(self._cpane, flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, border=10)
        self._cpane.Bind(wx.EVT_COLLAPSIBLEPANE_CHANGED, self._on_cpane_changed)

        # --- Buttons ---
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self._btn_save_connect = wx.Button(panel, label="Save && Connect")
        self._btn_save_connect.SetDefault()
        btn_save = wx.Button(panel, label="Save only")
        btn_cancel = wx.Button(panel, wx.ID_CANCEL, label="Cancel")

        btn_sizer.AddStretchSpacer()
        btn_sizer.Add(btn_cancel, flag=wx.RIGHT, border=4)
        btn_sizer.Add(btn_save, flag=wx.RIGHT, border=4)
        btn_sizer.Add(self._btn_save_connect)

        vbox.Add(btn_sizer, flag=wx.EXPAND | wx.ALL, border=10)
        panel.SetSizer(vbox)

        self._btn_save_connect.Bind(wx.EVT_BUTTON, self._on_save_connect)
        btn_save.Bind(wx.EVT_BUTTON, self._on_save_only)
        btn_cancel.Bind(wx.EVT_BUTTON, self._on_cancel)

    def _build_basic_page(self) -> wx.Panel:
        page = wx.Panel(self._notebook)
        grid = wx.FlexGridSizer(cols=2, hgap=8, vgap=6)
        grid.AddGrowableCol(1)

        grid.Add(wx.StaticText(page, label="Username:"), flag=wx.ALIGN_CENTER_VERTICAL)
        self._txt_basic_user = wx.TextCtrl(page)
        grid.Add(self._txt_basic_user, flag=wx.EXPAND)

        grid.Add(wx.StaticText(page, label="Password:"), flag=wx.ALIGN_CENTER_VERTICAL)
        self._txt_basic_pass = wx.TextCtrl(page, style=wx.TE_PASSWORD)
        grid.Add(self._txt_basic_pass, flag=wx.EXPAND)

        page.SetSizer(self._wrap_page(page, grid))
        return page

    def _build_m2m_page(self) -> wx.Panel:
        page = wx.Panel(self._notebook)
        grid = wx.FlexGridSizer(cols=2, hgap=8, vgap=6)
        grid.AddGrowableCol(1)

        grid.Add(wx.StaticText(page, label="Token endpoint:"), flag=wx.ALIGN_CENTER_VERTICAL)
        self._txt_m2m_token_ep = wx.TextCtrl(page)
        grid.Add(self._txt_m2m_token_ep, flag=wx.EXPAND)

        grid.Add(wx.StaticText(page, label="Client ID:"), flag=wx.ALIGN_CENTER_VERTICAL)
        self._txt_m2m_client_id = wx.TextCtrl(page)
        grid.Add(self._txt_m2m_client_id, flag=wx.EXPAND)

        grid.Add(wx.StaticText(page, label="Client secret:"), flag=wx.ALIGN_CENTER_VERTICAL)
        self._txt_m2m_secret = wx.TextCtrl(page, style=wx.TE_PASSWORD)
        grid.Add(self._txt_m2m_secret, flag=wx.EXPAND)

        grid.Add(
            wx.StaticText(page, label="Scope (space-separated):"),
            flag=wx.ALIGN_CENTER_VERTICAL,
        )
        self._txt_m2m_scope = wx.TextCtrl(page)
        grid.Add(self._txt_m2m_scope, flag=wx.EXPAND)

        page.SetSizer(self._wrap_page(page, grid))
        return page

    def _build_oidc_page(self) -> wx.Panel:
        page = wx.Panel(self._notebook)
        grid = wx.FlexGridSizer(cols=2, hgap=8, vgap=6)
        grid.AddGrowableCol(1)

        grid.Add(wx.StaticText(page, label="Client ID:"), flag=wx.ALIGN_CENTER_VERTICAL)
        self._txt_oidc_client_id = wx.TextCtrl(page)
        grid.Add(self._txt_oidc_client_id, flag=wx.EXPAND)

        grid.Add(wx.StaticText(page, label="Redirect URI:"), flag=wx.ALIGN_CENTER_VERTICAL)
        self._txt_oidc_redirect = wx.TextCtrl(page)
        grid.Add(self._txt_oidc_redirect, flag=wx.EXPAND)

        grid.Add(wx.StaticText(page, label="WebFinger prefix:"), flag=wx.ALIGN_CENTER_VERTICAL)
        self._txt_oidc_webfinger = wx.TextCtrl(page)
        grid.Add(self._txt_oidc_webfinger, flag=wx.EXPAND)

        self._chk_oidc_insecure = wx.CheckBox(page, label="Allow insecure redirect (localhost)")
        self._chk_oidc_insecure.SetValue(True)
        grid.Add(wx.Size(0, 0))
        grid.Add(self._chk_oidc_insecure)

        note = wx.StaticText(
            page,
            label="OIDC re-authenticates via your browser on each app launch.",
            style=wx.ST_ELLIPSIZE_END,
        )
        note.SetForegroundColour(wx.Colour(100, 100, 100))
        grid.Add(wx.Size(0, 0))
        grid.Add(note, flag=wx.EXPAND)

        page.SetSizer(self._wrap_page(page, grid))
        return page

    def _build_atfx_page(self) -> wx.Panel:
        page = wx.Panel(self._notebook)
        vbox = wx.BoxSizer(wx.VERTICAL)

        btn_browse = wx.Button(page, label="Browse\u2026")
        vbox.Add(btn_browse, flag=wx.ALL, border=10)

        note = wx.StaticText(
            page,
            label="Select a local ATFX file. The path appears in the URL field above.",
            style=wx.ST_ELLIPSIZE_END,
        )
        note.SetForegroundColour(wx.Colour(100, 100, 100))
        vbox.Add(note, flag=wx.LEFT | wx.RIGHT | wx.BOTTOM, border=10)

        page.SetSizer(vbox)
        btn_browse.Bind(wx.EVT_BUTTON, self._on_atfx_browse)
        return page

    def _on_atfx_browse(self, _event: wx.Event) -> None:
        with wx.FileDialog(
            self,
            "Select ATFX file",
            wildcard="ATFX files (*.atfx)|*.atfx|All files (*.*)|*.*",
            style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST,
        ) as dlg:
            if dlg.ShowModal() == wx.ID_OK:
                self._txt_url.SetValue(dlg.GetPath())

    def _build_context_vars_content(self, parent: wx.Window) -> None:
        vbox = wx.BoxSizer(wx.VERTICAL)

        self._lc_ctx_vars = wx.ListCtrl(
            parent,
            style=wx.LC_REPORT | wx.LC_SINGLE_SEL | wx.BORDER_SUNKEN,
            size=wx.Size(-1, 120),
        )
        self._lc_ctx_vars.AppendColumn("Name", width=180)
        self._lc_ctx_vars.AppendColumn("Value", width=220)
        vbox.Add(self._lc_ctx_vars, flag=wx.EXPAND | wx.ALL, border=6)

        btn_row = wx.BoxSizer(wx.HORIZONTAL)
        btn_add = wx.Button(parent, label="Add")
        self._btn_cv_edit = wx.Button(parent, label="Edit")
        self._btn_cv_remove = wx.Button(parent, label="Remove")
        btn_row.Add(btn_add, flag=wx.RIGHT, border=4)
        btn_row.Add(self._btn_cv_edit, flag=wx.RIGHT, border=4)
        btn_row.Add(self._btn_cv_remove)
        vbox.Add(btn_row, flag=wx.LEFT | wx.RIGHT | wx.BOTTOM, border=6)

        parent.SetSizer(vbox)

        btn_add.Bind(wx.EVT_BUTTON, self._on_cv_add)
        self._btn_cv_edit.Bind(wx.EVT_BUTTON, self._on_cv_edit)
        self._btn_cv_remove.Bind(wx.EVT_BUTTON, self._on_cv_remove)

    def _on_cpane_changed(self, _event: wx.CollapsiblePaneEvent) -> None:
        self._main_panel.Layout()
        self.Fit()

    def _update_cpane_label(self) -> None:
        count = self._lc_ctx_vars.GetItemCount()
        label = "Context Variables" if count == 0 else f"Context Variables ({count})"
        self._cpane.SetLabel(label)

    def _on_cv_add(self, _event: wx.Event) -> None:
        dlg_name = wx.TextEntryDialog(self, "Variable name:", "Add Context Variable")
        if dlg_name.ShowModal() != wx.ID_OK:
            dlg_name.Destroy()
            return
        name = dlg_name.GetValue().strip()
        dlg_name.Destroy()
        if not name:
            return
        dlg_val = wx.TextEntryDialog(self, "Value:", f"Value for '{name}'")
        if dlg_val.ShowModal() != wx.ID_OK:
            dlg_val.Destroy()
            return
        value = dlg_val.GetValue()
        dlg_val.Destroy()
        idx = self._lc_ctx_vars.InsertItem(self._lc_ctx_vars.GetItemCount(), name)
        self._lc_ctx_vars.SetItem(idx, 1, value)
        self._update_cpane_label()

    def _on_cv_edit(self, _event: wx.Event) -> None:
        idx = self._lc_ctx_vars.GetFirstSelected()
        if idx == -1:
            return
        old_name = self._lc_ctx_vars.GetItemText(idx, 0)
        old_val = self._lc_ctx_vars.GetItemText(idx, 1)
        dlg_name = wx.TextEntryDialog(self, "Variable name:", "Edit Context Variable", old_name)
        if dlg_name.ShowModal() != wx.ID_OK:
            dlg_name.Destroy()
            return
        name = dlg_name.GetValue().strip()
        dlg_name.Destroy()
        if not name:
            return
        dlg_val = wx.TextEntryDialog(self, "Value:", f"Value for '{name}'", old_val)
        if dlg_val.ShowModal() != wx.ID_OK:
            dlg_val.Destroy()
            return
        value = dlg_val.GetValue()
        dlg_val.Destroy()
        self._lc_ctx_vars.SetItem(idx, 0, name)
        self._lc_ctx_vars.SetItem(idx, 1, value)
        self._update_cpane_label()

    def _on_cv_remove(self, _event: wx.Event) -> None:
        idx = self._lc_ctx_vars.GetFirstSelected()
        if idx != -1:
            self._lc_ctx_vars.DeleteItem(idx)
            self._update_cpane_label()

    def _read_context_vars(self) -> dict[str, str]:
        result: dict[str, str] = {}
        for i in range(self._lc_ctx_vars.GetItemCount()):
            key = self._lc_ctx_vars.GetItemText(i, 0).strip()
            val = self._lc_ctx_vars.GetItemText(i, 1)
            if key:
                result[key] = val
        return result

    @staticmethod
    def _wrap_page(page: wx.Panel, inner: wx.Sizer) -> wx.BoxSizer:
        outer = wx.BoxSizer(wx.VERTICAL)
        outer.Add(inner, proportion=1, flag=wx.EXPAND | wx.ALL, border=10)
        return outer

    # ------------------------------------------------------------------
    # Populate from existing config
    # ------------------------------------------------------------------

    def _populate(self, config: ServerConfig | None) -> None:
        if config is None:
            self._txt_oidc_redirect.SetValue("http://127.0.0.1:12345")
            return

        self._txt_name.SetValue(config.name)
        self._txt_url.SetValue(config.url)
        self._chk_verify.SetValue(config.verify_certificate)

        self._lc_ctx_vars.DeleteAllItems()
        for key, val in config.context_variables.items():
            idx = self._lc_ctx_vars.InsertItem(self._lc_ctx_vars.GetItemCount(), key)
            self._lc_ctx_vars.SetItem(idx, 1, val)
        self._update_cpane_label()

        if config.auth_type == AuthType.BASIC:
            self._notebook.SetSelection(0)
            self._txt_basic_user.SetValue(config.username)
            secret = self._manager.load_secret(config)
            if secret:
                self._txt_basic_pass.SetValue(secret)

        elif config.auth_type == AuthType.M2M:
            self._notebook.SetSelection(1)
            self._txt_m2m_token_ep.SetValue(config.token_endpoint)
            self._txt_m2m_client_id.SetValue(config.client_id)
            self._txt_m2m_scope.SetValue(" ".join(config.scope))
            secret = self._manager.load_secret(config)
            if secret:
                self._txt_m2m_secret.SetValue(secret)

        elif config.auth_type == AuthType.OIDC:
            self._notebook.SetSelection(2)
            self._txt_oidc_client_id.SetValue(config.client_id)
            self._txt_oidc_redirect.SetValue(config.redirect_uri)
            self._txt_oidc_webfinger.SetValue(config.webfinger_path_prefix)
            self._chk_oidc_insecure.SetValue(config.redirect_url_allow_insecure)

        elif config.auth_type == AuthType.ATFX:
            self._notebook.SetSelection(3)

    # ------------------------------------------------------------------
    # Build ServerConfig from current form values
    # ------------------------------------------------------------------

    def _build_config(self) -> tuple[ServerConfig, str] | None:
        """Return (config, secret) or None if validation fails."""
        name = self._txt_name.GetValue().strip()
        url = self._txt_url.GetValue().strip()
        tab = self._notebook.GetSelection()
        if not name:
            wx.MessageBox("Name is required.", "Validation", wx.OK | wx.ICON_WARNING, self)
            return None
        if not url and tab != 3:  # URL not required for ATFX
            wx.MessageBox("URL is required.", "Validation", wx.OK | wx.ICON_WARNING, self)
            return None
        config_id = self._original_config.id if self._original_config else str(uuid.uuid4())
        verify = self._chk_verify.GetValue()

        ctx_vars = self._read_context_vars()

        if tab == 0:  # Basic
            username = self._txt_basic_user.GetValue().strip()
            password = self._txt_basic_pass.GetValue()
            if not username:
                wx.MessageBox("Username is required.", "Validation", wx.OK | wx.ICON_WARNING, self)
                return None
            cfg = ServerConfig(
                id=config_id,
                name=name,
                url=url,
                auth_type=AuthType.BASIC,
                username=username,
                verify_certificate=verify,
                context_variables=ctx_vars,
            )
            return cfg, password

        elif tab == 1:  # M2M
            token_ep = self._txt_m2m_token_ep.GetValue().strip()
            client_id = self._txt_m2m_client_id.GetValue().strip()
            secret = self._txt_m2m_secret.GetValue()
            scope_str = self._txt_m2m_scope.GetValue().strip()
            scope = scope_str.split() if scope_str else []
            if not token_ep or not client_id:
                wx.MessageBox(
                    "Token endpoint and Client ID are required.",
                    "Validation",
                    wx.OK | wx.ICON_WARNING,
                    self,
                )
                return None
            cfg = ServerConfig(
                id=config_id,
                name=name,
                url=url,
                auth_type=AuthType.M2M,
                token_endpoint=token_ep,
                client_id=client_id,
                scope=scope,
                verify_certificate=verify,
                context_variables=ctx_vars,
            )
            return cfg, secret

        elif tab == 2:  # OIDC
            client_id = self._txt_oidc_client_id.GetValue().strip()
            redirect = self._txt_oidc_redirect.GetValue().strip()
            webfinger = self._txt_oidc_webfinger.GetValue().strip()
            insecure = self._chk_oidc_insecure.GetValue()
            if not client_id or not redirect:
                wx.MessageBox(
                    "Client ID and Redirect URI are required.",
                    "Validation",
                    wx.OK | wx.ICON_WARNING,
                    self,
                )
                return None
            cfg = ServerConfig(
                id=config_id,
                name=name,
                url=url,
                auth_type=AuthType.OIDC,
                client_id=client_id,
                redirect_uri=redirect,
                webfinger_path_prefix=webfinger,
                redirect_url_allow_insecure=insecure,
                verify_certificate=verify,
                context_variables=ctx_vars,
            )
            return cfg, ""  # no secret stored for OIDC

        else:  # ATFX (tab == 3)
            file_path = url
            if not file_path:
                wx.MessageBox(
                    "Please select an ATFX file.",
                    "Validation",
                    wx.OK | wx.ICON_WARNING,
                    self,
                )
                return None
            cfg = ServerConfig(
                id=config_id,
                name=name,
                url=file_path,  # file path stored in url for display
                auth_type=AuthType.ATFX,
                verify_certificate=False,
                context_variables=ctx_vars,
            )
            return cfg, ""  # no secret for ATFX

        return None  # unreachable

    # ------------------------------------------------------------------
    # Save helper
    # ------------------------------------------------------------------

    def _save_config(self, config: ServerConfig, secret: str) -> None:
        if self._original_config:
            self._manager.update(config)
        else:
            self._manager.add(config)
        if secret:
            self._manager.save_secret(config, secret)

    # ------------------------------------------------------------------
    # Connect helper
    # ------------------------------------------------------------------

    def _do_connect(self, config: ServerConfig, secret: str):  # type: ignore[return]
        return do_connect(config, secret)

    def _show_save_error(self, config_id: str, exc: Exception) -> None:
        if isinstance(exc, KeyError):
            detail = f"GUID '{config_id}' could not be found."
        else:
            detail = str(exc)
        wx.MessageBox(
            f"Could not save server configuration:\n\n{detail}",
            "Save Error",
            wx.OK | wx.ICON_ERROR,
            self,
        )

    # ------------------------------------------------------------------
    # Button handlers
    # ------------------------------------------------------------------

    def _on_cancel(self, _event: wx.Event) -> None:
        self.EndModal(wx.ID_CANCEL)

    def _on_save_only(self, _event: wx.Event) -> None:
        result = self._build_config()
        if result is None:
            return
        config, secret = result
        try:
            self._save_config(config, secret)
        except Exception as exc:
            self._show_save_error(config.id, exc)
            return
        self._result_config = config
        self.EndModal(wx.ID_OK)

    def _on_save_connect(self, _event: wx.Event) -> None:
        result = self._build_config()
        if result is None:
            return
        config, secret = result
        try:
            self._save_config(config, secret)
        except Exception as exc:
            self._show_save_error(config.id, exc)
            return

        try:
            wx.BeginBusyCursor()
            con_i = self._do_connect(config, secret)
        except Exception as exc:
            _log.exception("Connection failed")
            detail = str(exc)
            response = getattr(exc, "response", None)
            if response is not None and getattr(response, "text", ""):
                detail += f"\n\nServer response:\n{response.text}"
            wx.MessageBox(
                f"Connection failed:\n\n{detail}",
                "Connection Error",
                wx.OK | wx.ICON_ERROR,
                self,
            )
            return
        finally:
            with contextlib.suppress(Exception):
                wx.EndBusyCursor()

        self._result_config = config
        self._con_i = con_i
        self.EndModal(wx.ID_OK)
