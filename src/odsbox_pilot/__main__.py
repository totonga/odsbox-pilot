"""Entry point: python -m odsbox_pilot"""

import sys


def main() -> None:
    import wx  # type: ignore[import-untyped]

    from odsbox_pilot.app import OdsPilotApp

    app = OdsPilotApp()
    app.MainLoop()
    sys.exit(0)


if __name__ == "__main__":
    main()
