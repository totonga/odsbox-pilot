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
    args = parser.parse_args()

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
