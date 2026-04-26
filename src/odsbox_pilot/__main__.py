"""Entry point: python -m odsbox_pilot"""

import argparse
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
    app.MainLoop()
    sys.exit(0)


if __name__ == "__main__":
    main()
