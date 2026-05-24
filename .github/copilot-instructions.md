# GitHub Copilot Instructions

This is **odsbox-pilot** — a wxPython desktop application for querying and exploring
[ASAM ODS](https://www.asam.net/standards/detail/ods/) measurement-data servers.

---

## Tech stack

- **Language**: Python 3.14+
- **Package manager**: [uv](https://docs.astral.sh/uv/) — use `uv add`, `uv sync`, `uv run`
- **GUI framework**: [wxPython](https://wxpython.org/) (`wx.*`)
- **ODS client**: [odsbox](https://pypi.org/project/odsbox/) — provides `OdsClient`, JAQueL queries, and model access
- **Data**: [pandas](https://pandas.pydata.org/) for result tables
- **Charts**: [matplotlib](https://matplotlib.org/)
- **Credentials**: [keyring](https://pypi.org/project/keyring/) — never store secrets in plain text
- **Linter/formatter**: [ruff](https://docs.astral.sh/ruff/)
- **Type checker**: [mypy](https://mypy.readthedocs.io/) — all new code must type-check cleanly
- **Tests**: [pytest](https://pytest.org/) + [pytest-mock](https://pytest-mock.readthedocs.io/)

---

## Project layout

```
src/odsbox_pilot/
  __main__.py          # CLI entry point
  app.py               # wx.App, main window
  models.py            # shared dataclasses / enums
  connection/          # server config, keyring, dialogs
  query/               # Query tab: editor, result grid, history, examples
  browse/              # Browse tab: lazy tree, filter conditions
  model/               # Model tab: entity-relation schema browser
  static/              # Bundled CodeMirror editor (editor.html + bundle.js)
tests/
  unit/                # No wx, no server — fast, runs in CI
  integration/         # Require a live ODS server
  data/                # JSON fixtures (e.g. mdm_nvh_model.json)
```

---

## Coding conventions

- Follow the existing module structure — keep GUI logic in the appropriate tab package.
- All public functions and classes need type annotations.
- Use dataclasses (from `models.py`) for data transfer objects; avoid raw dicts where a typed structure is clearer.
- GUI panels inherit from `wx.Panel`. Dialogs inherit from `wx.Dialog`.
- Bind wx events with `self.Bind(wx.EVT_*, handler)` inside `__init__` or a dedicated `_bind_events` method.
- Do not call `wx.*` in unit tests — mock the ODS client instead.
- Keep business logic out of panel classes so it can be unit-tested without wx.
- Passwords/secrets: always read from `keyring`, never from config files or env vars.

---

## Running things

```bash
uv run odsbox-pilot              # launch the app
uv run pytest tests/unit/ -v     # unit tests
uv run ruff check src/ tests/    # lint
uv run ruff format src/ tests/   # format
uv run mypy src/                 # type check
```

---

## ODS / JAQueL specifics

- Queries are JSON objects following the [JAQueL](https://github.com/totonga/jaquel) schema.
- The simplest query is `{ "EntityName": {} }` — fetches all rows of that entity.
- Access the ODS model (entities, attributes, relations, enumerations) via
  `OdsClient.model` after connecting.
- Use `OdsClient.query(jaquel_dict)` to execute queries; the result is a pandas `DataFrame`.
- Entity base names follow ASAM ODS conventions: `AoTest`, `AoMeasurement`, `AoSubMatrix`, etc.

---

## Test conventions

- Place pure logic tests in `tests/unit/` — no wx imports, no live server.
- Use `pytest-mock` (`mocker.patch`, `mocker.MagicMock`) to mock `OdsClient` and keyring.
- Use the fixture in `tests/data/mdm_nvh_model.json` for model-related tests.
- Integration tests in `tests/integration/` may be skipped in CI; guard with
  `pytest.mark.skipif` or environment variable checks defined in `conftest.py`.

---

## What NOT to do

- Do not introduce new runtime dependencies without updating `pyproject.toml` via `uv add`.
- Do not store passwords in `~/.ods-pilot/servers.json` — only metadata goes there.
- Do not import `wx` in `models.py` or any module under `tests/unit/`.
- Do not use `subprocess` to call external tools from the GUI.
- Do not add `print()` debugging statements — use Python `logging` instead.
