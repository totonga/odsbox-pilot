"""Entry point: python -m odsbox_pilot"""

import argparse
import getpass
import signal
import sys
from pathlib import Path

from odsbox_pilot.styles import ScaleLevel


def _enable_windows_dpi_awareness() -> None:
    """Enable Per-Monitor-V2 DPI awareness on Windows before wx is imported.

    Must run before any wx import so the process is DPI-aware from the start.
    Silently ignores failures on older Windows or non-Windows platforms.
    """
    if sys.platform != "win32":
        return
    import contextlib  # noqa: PLC0415
    import ctypes  # noqa: PLC0415

    try:
        # PROCESS_PER_MONITOR_DPI_AWARE = 2
        ctypes.windll.shcore.SetProcessDpiAwareness(2)  # type: ignore[attr-defined]
    except Exception:  # noqa: BLE001
        with contextlib.suppress(Exception):
            ctypes.windll.user32.SetProcessDPIAware()  # type: ignore[attr-defined]


def _prompt_secret_for_import(config) -> str:
    secret_label = getattr(config, "secret_label", None)
    if not getattr(config, "requires_secret", False) or secret_label is None:
        return ""
    if not sys.stdin.isatty():
        print(
            f"Imported server '{config.name}' requires a {secret_label}, "
            "but no interactive terminal is available. Skipping secret prompt.",
            file=sys.stderr,
        )
        return ""
    return getpass.getpass(f"Enter {secret_label} for '{config.name}' (leave blank to skip): ")


def _import_server(import_path: str) -> int:
    from odsbox_pilot.connection.manager import ServerConfigManager

    manager = ServerConfigManager()
    config = manager.read_portable_config(Path(import_path))
    secret = _prompt_secret_for_import(config)
    manager.add(config)
    if secret:
        manager.save_secret(config, secret)

    print(f"Imported server '{config.name}' (id: {config.id}).")
    if config.requires_secret and not secret:
        print(
            f"No {config.secret_label} was stored for '{config.name}'. "
            "You can add it later by editing the server.",
        )
    return 0


def main(argv: list[str] | None = None) -> None:
    _enable_windows_dpi_awareness()

    parser = argparse.ArgumentParser(
        prog="odsbox-pilot",
        description="ASAM ODS desktop query tool",
    )
    action_group = parser.add_mutually_exclusive_group()
    action_group.add_argument(
        "--server",
        metavar="NAME_OR_ID",
        default=None,
        help="Name or ID of a saved server to connect to directly, skipping the server list.",
    )
    action_group.add_argument(
        "--list-servers",
        action="store_true",
        help="Print all saved servers and exit.",
    )
    action_group.add_argument(
        "--import-server",
        metavar="PATH",
        default=None,
        help="Import a portable server file (*.ods-pilot.con.json) and exit.",
    )
    parser.add_argument(
        "--scaling",
        choices=[level.value for level in ScaleLevel],
        default=None,
        help=(
            "Global UI font scaling level. Overrides the persistent startup "
            "scaling saved in Settings for this launch only."
        ),
    )
    args = parser.parse_args(argv)

    if args.import_server:
        try:
            sys.exit(_import_server(args.import_server))
        except Exception as exc:
            print(f"Could not import server: {exc}", file=sys.stderr)
            raise SystemExit(1) from exc

    if args.list_servers:
        from odsbox_pilot.connection.manager import ServerConfigManager

        manager = ServerConfigManager()
        configs = manager.configs
        if not configs:
            print("No saved servers.")
        else:
            for cfg in configs:
                print(f"{cfg.name}  (id: {cfg.id}  url: {cfg.url})")
        sys.exit(0)

    try:
        from odsbox_pilot.app import OdsPilotApp
    except ImportError as exc:
        print(
            "wxPython is required to run odsbox-pilot.\n"
            "Install it with:  pip install odsbox-pilot[gui]",
            file=sys.stderr,
        )
        raise SystemExit(1) from exc

    app = OdsPilotApp(initial_server=args.server, scaling=args.scaling)

    import wx  # type: ignore[import-untyped]  # already loaded by OdsPilotApp  # noqa: PLC0415

    _exit_flag = [False]

    def _sigint_handler(signum: int, frame: object) -> None:
        _exit_flag[0] = True

    def _check_sigint(_event: object) -> None:
        if _exit_flag[0]:
            _exit_flag[0] = False
            windows = wx.GetTopLevelWindows()
            if windows:
                windows[0].Close()
            else:
                app.ExitMainLoop()

    signal.signal(signal.SIGINT, _sigint_handler)
    _sigint_timer = wx.Timer(app)
    app.Bind(wx.EVT_TIMER, _check_sigint, _sigint_timer)
    _sigint_timer.Start(200)  # wake the event loop every 200 ms to check the flag

    app.MainLoop()
    sys.exit(0)


if __name__ == "__main__":
    main()
