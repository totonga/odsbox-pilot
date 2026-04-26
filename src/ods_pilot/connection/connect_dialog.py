"""ConnectDialog: create or edit an ODS server config.

Three tabs: Basic (username/password), M2M (client credentials), OIDC.
On OK the config is saved and, if the user clicked "Save & Connect",
the returned ConI is available via the `con_i` property.
"""

from __future__ import annotations

import uuid

import wx  # type: ignore[import-untyped]
import wx.lib.scrolledpanel as scrolled  # type: ignore[import-untyped]

from ods_pilot.connection.manager import ServerConfigManager
from ods_pilot.models import AuthType, ServerConfig


def do_connect(config: ServerConfig, secret: str):  # type: ignore[return]
    """Create a live ConI from *config* + *secret* without any UI."""
    from odsbox.con_i_factory import ConIFactory  # type: ignore[import-untyped]

    if config.auth_type == AuthType.BASIC:
        return ConIFactory.basic(
            url=config.url,
            username=config.username,
            password=secret,
            verify_certificate=config.verify_certificate,
        )
    elif config.auth_type == AuthType.M2M:
        return ConIFactory.m2m(
            url=config.url,
            token_endpoint=config.token_endpoint,
            client_id=config.client_id,
            client_secret=secret,
            scope=config.scope or None,
            verify_certificate=config.verify_certificate,
        )
    else:  # OIDC
        return ConIFactory.oidc(
            url=config.url,
            client_id=config.client_id,
            redirect_uri=config.redirect_uri,
            redirect_url_allow_insecure=config.redirect_url_allow_insecure,
            webfinger_path_prefix=config.webfinger_path_prefix,
            verify_certificate=config.verify_certificate,
        )


class ConnectDialog(wx.Dialog):
    """Dialog to create or edit an ODS server connection config."""

    def __init__(
        self,
        parent: wx.Window | None,
        manager: ServerConfigManager,
        config: ServerConfig | None,
    ) -> None:
        title = "Edit Server" if config else "New Server"
        super().__init__(
            parent,
            title=title,
            size=(480, 480),
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
        )
        self._manager = manager
        self._original_config = config
        self._con_i = None  # set when "Save & Connect" succeeds

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

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self, config: ServerConfig | None) -> None:
        panel = wx.Panel(self)
        vbox = wx.BoxSizer(wx.VERTICAL)

        # --- Common fields (name + URL) ---
        grid = wx.FlexGridSizer(cols=2, hgap=8, vgap=6)
        grid.AddGrowableCol(1)

        grid.Add(wx.StaticText(panel, label="Name:"), flag=wx.ALIGN_CENTER_VERTICAL)
        self._txt_name = wx.TextCtrl(panel, size=(300, -1))
        grid.Add(self._txt_name, flag=wx.EXPAND)

        grid.Add(wx.StaticText(panel, label="URL:"), flag=wx.ALIGN_CENTER_VERTICAL)
        self._txt_url = wx.TextCtrl(panel, size=(300, -1))
        grid.Add(self._txt_url, flag=wx.EXPAND)

        self._chk_verify = wx.CheckBox(panel, label="Verify TLS certificate")
        self._chk_verify.SetValue(True)
        grid.Add((0, 0))
        grid.Add(self._chk_verify)

        vbox.Add(grid, flag=wx.EXPAND | wx.ALL, border=10)

        # --- Auth notebook ---
        self._notebook = wx.Notebook(panel)
        self._page_basic = self._build_basic_page()
        self._page_m2m = self._build_m2m_page()
        self._page_oidc = self._build_oidc_page()
        self._notebook.AddPage(self._page_basic, "Basic")
        self._notebook.AddPage(self._page_m2m, "M2M")
        self._notebook.AddPage(self._page_oidc, "OIDC")
        vbox.Add(self._notebook, proportion=1, flag=wx.EXPAND | wx.LEFT | wx.RIGHT, border=10)

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

        grid.Add(
            wx.StaticText(page, label="WebFinger prefix:"), flag=wx.ALIGN_CENTER_VERTICAL
        )
        self._txt_oidc_webfinger = wx.TextCtrl(page)
        grid.Add(self._txt_oidc_webfinger, flag=wx.EXPAND)

        self._chk_oidc_insecure = wx.CheckBox(page, label="Allow insecure redirect (localhost)")
        self._chk_oidc_insecure.SetValue(True)
        grid.Add((0, 0))
        grid.Add(self._chk_oidc_insecure)

        note = wx.StaticText(
            page,
            label="OIDC re-authenticates via your browser on each app launch.",
            style=wx.ST_ELLIPSIZE_END,
        )
        note.SetForegroundColour(wx.Colour(100, 100, 100))
        grid.Add((0, 0))
        grid.Add(note, flag=wx.EXPAND)

        page.SetSizer(self._wrap_page(page, grid))
        return page

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

    # ------------------------------------------------------------------
    # Build ServerConfig from current form values
    # ------------------------------------------------------------------

    def _build_config(self) -> tuple[ServerConfig, str] | None:
        """Return (config, secret) or None if validation fails."""
        name = self._txt_name.GetValue().strip()
        url = self._txt_url.GetValue().strip()
        if not name:
            wx.MessageBox("Name is required.", "Validation", wx.OK | wx.ICON_WARNING, self)
            return None
        if not url:
            wx.MessageBox("URL is required.", "Validation", wx.OK | wx.ICON_WARNING, self)
            return None

        tab = self._notebook.GetSelection()
        config_id = self._original_config.id if self._original_config else str(uuid.uuid4())
        verify = self._chk_verify.GetValue()

        if tab == 0:  # Basic
            username = self._txt_basic_user.GetValue().strip()
            password = self._txt_basic_pass.GetValue()
            if not username:
                wx.MessageBox(
                    "Username is required.", "Validation", wx.OK | wx.ICON_WARNING, self
                )
                return None
            cfg = ServerConfig(
                id=config_id,
                name=name,
                url=url,
                auth_type=AuthType.BASIC,
                username=username,
                verify_certificate=verify,
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
            )
            return cfg, secret

        else:  # OIDC
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
            )
            return cfg, ""  # no secret stored for OIDC

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

    # ------------------------------------------------------------------
    # Button handlers
    # ------------------------------------------------------------------

    def _on_save_only(self, _event: wx.Event) -> None:
        result = self._build_config()
        if result is None:
            return
        config, secret = result
        self._save_config(config, secret)
        self.EndModal(wx.ID_OK)

    def _on_save_connect(self, _event: wx.Event) -> None:
        result = self._build_config()
        if result is None:
            return
        config, secret = result
        self._save_config(config, secret)

        try:
            wx.BeginBusyCursor()
            con_i = self._do_connect(config, secret)
        except Exception as exc:
            wx.EndBusyCursor()
            wx.MessageBox(
                f"Connection failed:\n\n{exc}",
                "Connection Error",
                wx.OK | wx.ICON_ERROR,
                self,
            )
            return
        finally:
            try:
                wx.EndBusyCursor()
            except Exception:
                pass

        self._con_i = con_i
        self.EndModal(wx.ID_OK)
