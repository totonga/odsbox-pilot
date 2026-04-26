"""QueryHistory: persisted, trimmed history of executed queries."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from ods_pilot.models import HISTORY_FILE

_MAX_ENTRIES = 100


@dataclass
class HistoryEntry:
    query: str
    timestamp: str  # ISO-8601
    row_count: int | None  # None on error
    error: str | None  # error message or None

    @classmethod
    def success(cls, query: str, row_count: int) -> HistoryEntry:
        return cls(
            query=query,
            timestamp=datetime.now(tz=timezone.utc).isoformat(),
            row_count=row_count,
            error=None,
        )

    @classmethod
    def failure(cls, query: str, error: str) -> HistoryEntry:
        return cls(
            query=query,
            timestamp=datetime.now(tz=timezone.utc).isoformat(),
            row_count=None,
            error=error,
        )

    def short_label(self) -> str:
        """One-line label for display in history dropdown."""
        ts = self.timestamp[:19].replace("T", " ")
        q = self.query.replace("\n", " ").strip()
        if len(q) > 60:
            q = q[:57] + "…"
        if self.error:
            return f"[ERR] {ts}  {q}"
        return f"[{self.row_count} rows] {ts}  {q}"


class QueryHistory:
    """Append-only query history, persisted to ``~/.ods-pilot/history.json``."""

    def __init__(self, path: Path = HISTORY_FILE) -> None:
        self._path = path
        self._entries: list[HistoryEntry] = []
        self._load()

    @property
    def entries(self) -> list[HistoryEntry]:
        """Most-recent-first view of all entries."""
        return list(reversed(self._entries))

    def append(self, entry: HistoryEntry) -> None:
        self._entries.append(entry)
        # Trim oldest beyond max
        if len(self._entries) > _MAX_ENTRIES:
            self._entries = self._entries[-_MAX_ENTRIES:]
        self._save()

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
            self._entries = [HistoryEntry(**e) for e in raw]
        except Exception:
            self._entries = []

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            json.dumps([asdict(e) for e in self._entries], indent=2),
            encoding="utf-8",
        )
