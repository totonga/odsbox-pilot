"""Entry point: python -m odsbox_pilot"""

import sys


def main() -> None:
    try:
        from odsbox_pilot.app import OdsPilotApp
    except ImportError as exc:
        print(
            "wxPython is required to run odsbox-pilot.\n"
            "Install it with:  pip install odsbox-pilot[gui]",
            file=sys.stderr,
        )
        raise SystemExit(1) from exc

    app = OdsPilotApp()
    app.MainLoop()
    sys.exit(0)


if __name__ == "__main__":
    main()
