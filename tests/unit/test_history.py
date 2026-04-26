"""Unit tests for QueryHistory."""

from __future__ import annotations

import json

from odsbox_pilot.query.history import _MAX_ENTRIES, HistoryEntry, QueryHistory


def _make_history(tmp_path) -> QueryHistory:
    return QueryHistory(path=tmp_path / "history.json")


class TestHistoryEntry:
    def test_success_entry(self) -> None:
        e = HistoryEntry.success('{"AoUnit": {}}', 42)
        assert e.row_count == 42
        assert e.error is None
        assert "T" in e.timestamp  # ISO-8601

    def test_failure_entry(self) -> None:
        e = HistoryEntry.failure("bad json", "SyntaxError: ...")
        assert e.row_count is None
        assert e.error is not None

    def test_short_label_success(self) -> None:
        e = HistoryEntry.success('{"AoUnit": {}}', 7)
        label = e.short_label()
        assert "[7 rows]" in label

    def test_short_label_error(self) -> None:
        e = HistoryEntry.failure("bad", "boom")
        assert "[ERR]" in e.short_label()

    def test_short_label_truncates_long_query(self) -> None:
        long_q = "x" * 200
        e = HistoryEntry.success(long_q, 0)
        assert len(e.short_label()) < 200


class TestQueryHistoryAppend:
    def test_append_single(self, tmp_path) -> None:
        h = _make_history(tmp_path)
        h.append(HistoryEntry.success('{"q": 1}', 5))
        assert len(h.entries) == 1

    def test_entries_most_recent_first(self, tmp_path) -> None:
        h = _make_history(tmp_path)
        h.append(HistoryEntry.success("first", 1))
        h.append(HistoryEntry.success("second", 2))
        assert h.entries[0].query == "second"
        assert h.entries[1].query == "first"

    def test_trim_to_max(self, tmp_path) -> None:
        h = _make_history(tmp_path)
        for i in range(_MAX_ENTRIES + 20):
            h.append(HistoryEntry.success(f"q{i}", i))
        assert len(h.entries) == _MAX_ENTRIES


class TestQueryHistoryPersistence:
    def test_persist_and_reload(self, tmp_path) -> None:
        h1 = _make_history(tmp_path)
        h1.append(HistoryEntry.success('{"AoUnit": {}}', 10))

        h2 = _make_history(tmp_path)
        assert len(h2.entries) == 1
        assert h2.entries[0].row_count == 10

    def test_history_file_is_valid_json(self, tmp_path) -> None:
        h = _make_history(tmp_path)
        h.append(HistoryEntry.success("q", 3))
        raw = (tmp_path / "history.json").read_text(encoding="utf-8")
        data = json.loads(raw)
        assert isinstance(data, list)

    def test_corrupt_file_yields_empty(self, tmp_path) -> None:
        p = tmp_path / "history.json"
        p.write_text("BROKEN", encoding="utf-8")
        h = QueryHistory(path=p)
        assert h.entries == []

    def test_missing_file_yields_empty(self, tmp_path) -> None:
        h = QueryHistory(path=tmp_path / "nonexistent.json")
        assert h.entries == []
