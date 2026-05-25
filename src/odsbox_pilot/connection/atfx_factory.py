"""Factory for in-process ATFX file connections via wodson.atfx.AtfxSession.

Usage::

    from odsbox_pilot.connection.atfx_factory import open_atfx

    with open_atfx("path/to/file.atfx") as con:
        model = con.mc.model()

The returned :class:`AtfxConI` wraps both an :class:`~wodson.atfx.AtfxSession`
and an :class:`~odsbox.con_i.ConI`, delegating all attribute access to the
inner ``ConI`` so it is a drop-in replacement for the network-based ``ConI``
objects returned by ``ConIFactory``.
"""

from __future__ import annotations

import logging
from pathlib import Path
from types import TracebackType
from typing import Any

_log = logging.getLogger(__name__)


class AtfxConI:
    """Wraps :class:`~wodson.atfx.AtfxSession` and an inner ConI together.

    Attribute access for names not defined on this class is delegated to the
    inner ConI via ``__getattr__``, making this a transparent proxy.
    """

    def __init__(self, file_path: str | Path) -> None:
        from odsbox.con_i import ConI
        from wodson.atfx import AtfxSession

        resolved = str(Path(file_path).resolve())
        _log.debug("Opening ATFX file: %s", resolved)

        self._session: Any = AtfxSession(default_file=resolved)
        self._session.__enter__()
        try:
            self._con: Any = ConI(
                url=self._session.url,
                auth=None,
                custom_session=self._session,
            )
        except Exception:
            self._session.close()
            raise

    # ------------------------------------------------------------------
    # Context manager
    # ------------------------------------------------------------------

    def __enter__(self) -> AtfxConI:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        self.close()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def close(self) -> None:
        """Close the inner ConI then the AtfxSession."""
        try:
            self._con.close()
        finally:
            self._session.close()

    # ------------------------------------------------------------------
    # Transparent delegation to the inner ConI
    # ------------------------------------------------------------------

    def __getattr__(self, name: str) -> Any:
        # Only reached for attributes not found on AtfxConI itself.
        return getattr(self._con, name)


def open_atfx(file_path: str | Path) -> AtfxConI:
    """Create an in-process :class:`AtfxConI` connected to *file_path*.

    :param file_path: Path to a local ``.atfx`` file.
    :returns: An :class:`AtfxConI` with the ODS model already loaded.
    :raises requests.HTTPError: If *file_path* does not exist or cannot be
        parsed as a valid ATFX file.
    """
    return AtfxConI(file_path)
