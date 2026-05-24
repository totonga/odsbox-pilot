# Developer Guide

This guide covers everything needed to build, test, and contribute to **odsbox-pilot**.

---

## Table of Contents

1. [Tech stack](#1-tech-stack)
2. [Project structure](#2-project-structure)
3. [Setting up the dev environment](#3-setting-up-the-dev-environment)
4. [Running the app from source](#4-running-the-app-from-source)
5. [Tests](#5-tests)
6. [Lint and type-checking](#6-lint-and-type-checking)
7. [Dependency management](#7-dependency-management)
8. [CI/CD pipeline](#8-cicd-pipeline)
9. [Release process](#9-release-process)
10. [Architecture notes](#10-architecture-notes)

---

## 1. Tech stack

| Concern | Tool |
|---|---|
| Package / env management | [uv](https://docs.astral.sh/uv/) |
| GUI framework | [wxPython](https://wxpython.org/) |
| ODS client library | [odsbox](https://pypi.org/project/odsbox/) |
| Data handling | [pandas](https://pandas.pydata.org/) |
| Charts | [matplotlib](https://matplotlib.org/) |
| Query editor (web component) | [CodeMirror 6](https://codemirror.net/) bundled as `static/editor.html` |
| Credential storage | [keyring](https://pypi.org/project/keyring/) |
| Linter / formatter | [ruff](https://docs.astral.sh/ruff/) |
| Static type checker | [mypy](https://mypy.readthedocs.io/) |
| Test framework | [pytest](https://pytest.org/) + [pytest-mock](https://pytest-mock.readthedocs.io/) |
| Security audit | [pip-audit](https://pypi.org/project/pip-audit/) |
| Versioning | [python-semantic-release](https://python-semantic-release.readthedocs.io/) |

---

## 2. Project structure

```
src/odsbox_pilot/
├── __main__.py          # Entry point (CLI arg parsing, app bootstrap)
├── app.py               # wx.App subclass and main window
├── models.py            # Shared data models / dataclasses
├── connection/
│   ├── manager.py       # ServerConfig persistence, keyring integration
│   ├── connect_dialog.py
│   └── server_list_dialog.py
├── query/
│   ├── main_frame.py    # Query tab panel
│   ├── editor_panel.py  # CodeMirror webview wrapper
│   ├── result_grid.py   # pandas → wx.grid
│   ├── history.py       # Query history (in-memory + session persistence)
│   └── examples.py      # Built-in query examples
├── browse/
│   ├── browse_panel.py  # Browse tab panel
│   ├── filter_tree.py   # Lazy ODS instance tree
│   ├── condition_dialog.py
│   └── _helpers.py
├── model/
│   ├── model_panel.py   # Model tab panel
│   └── helpers.py       # Entity/attribute/relation tree helpers
└── static/
    └── editor.html      # Self-contained CodeMirror bundle

tests/
├── unit/                # Pure unit tests (no ODS server required)
├── integration/         # Tests that require a live ODS server
├── conftest.py
└── data/
    └── mdm_nvh_model.json   # Sample ODS model fixture
```

---

## 3. Setting up the dev environment

Prerequisites: Python 3.14+ and [uv](https://docs.astral.sh/uv/getting-started/installation/).

```bash
git clone https://github.com/totonga/odsbox-pilot.git
cd odsbox-pilot

# Install all dependencies including the gui extra and dev tools
uv sync --extra gui --all-groups
```

---

## 4. Running the app from source

```bash
# Via the installed script
uv run odsbox-pilot

# Via the module entry point
uv run python -m odsbox_pilot

# With a specific server (skip the server-list dialog)
uv run odsbox-pilot --server "My Server"
```

---

## 5. Tests

```bash
# Unit tests only (no server needed — fast, runs in CI)
uv run pytest tests/unit/ -v

# Integration tests (require a live ODS server — see tests/conftest.py for env vars)
uv run pytest tests/integration/ -v

# Full suite
uv run pytest -v
```

Test fixtures live in `tests/data/`. The file `mdm_nvh_model.json` is a real ODS model
snapshot used to exercise the model panel and browse logic without a server.

---

## 6. Lint and type-checking

```bash
# Lint
uv run ruff check src/ tests/

# Auto-fix lint issues
uv run ruff check --fix src/ tests/

# Format check
uv run ruff format --check src/ tests/

# Auto-format
uv run ruff format src/ tests/

# Type checking
uv run mypy src/

# Security audit
uv run pip-audit
```

Configuration is in `pyproject.toml` under `[tool.ruff]` and `[tool.mypy]`.

---

## 7. Dependency management

Direct dependencies are declared in `pyproject.toml`:

- **`[project.dependencies]`** — runtime dependencies (installed with the package).
- **`[project.optional-dependencies] gui`** — wxPython + matplotlib; required for the GUI.
- **`[dependency-groups] dev`** — dev-only tools (pytest, ruff, mypy, …); not shipped.

Adding a new runtime dependency:

```bash
uv add some-package
```

Adding a dev-only tool:

```bash
uv add --group dev some-tool
```

---

## 8. CI/CD pipeline

The GitHub Actions workflow at `.github/workflows/ci.yml` runs on every push and pull
request to `main`:

| Job | What it does |
|---|---|
| **lint** | `ruff check`, `ruff format --check`, `mypy` |
| **test** | `pytest tests/unit/` |
| **audit** | `pip-audit` — checks for known vulnerabilities in dependencies |

wxPython is **not** installed in CI (headless environment). All tests that touch wx widgets
must be in `tests/integration/` or properly guarded.

---

## 9. Release process

Releases are managed by [python-semantic-release](https://python-semantic-release.readthedocs.io/)
using [Conventional Commits](https://www.conventionalcommits.org/).

Commit message prefixes:
- `feat:` — bumps the minor version
- `fix:` — bumps the patch version
- `feat!:` / `BREAKING CHANGE:` — bumps the major version
- `chore:`, `docs:`, `test:`, `refactor:` — no version bump

The changelog in `CHANGELOG.md` is generated automatically.

---

## 10. Architecture notes

### CodeMirror editor

The query editor is a `wx.html2.WebView` that loads `src/odsbox_pilot/static/editor.html`.
The JavaScript bundle (`static/codemirror/bundle.js`) is built separately using
`build_static.js` (Node.js / esbuild). To rebuild the bundle after changing editor features:

```bash
node build_static.js
```

### Credential storage

`connection/manager.py` uses `keyring` to store passwords keyed by service name
`odsbox-pilot` and the server name. Server metadata (URL, username, auth mode) is
serialised to `~/.ods-pilot/servers.json`. Passwords are never written to that file.

### Browse filter conditions

Conditions are persisted as JSON in `~/.ods-pilot/browse_conditions.json`. The schema is
a list of `BrowseCondition` dataclass instances (see `models.py`).

### Lazy tree expansion

`browse/filter_tree.py` implements the ODS hierarchy as a `wx.TreeCtrl` with on-demand
loading. Each expandable node carries a `NodeData` payload that encodes the entity type
and instance ID needed to fetch children.
