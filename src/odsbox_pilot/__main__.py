"""Entry point: python -m odsbox_pilot"""

import argparse
import signal
import sys


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="odsbox-pilot",
        description="ASAM ODS desktop query tool",
    )
    parser.add_argument(
        "--server",
        metavar="NAME_OR_ID",
        default=None,
        help="Name or ID of a saved server to connect to directly, skipping the server list.",
    )
    parser.add_argument(
        "--list-servers",
        action="store_true",
        help="Print all saved servers and exit.",
    )
    args = parser.parse_args()

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

    app = OdsPilotApp(initial_server=args.server)

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
