# odsbox-pilot

[![PyPI](https://img.shields.io/pypi/v/odsbox-pilot)](https://pypi.org/project/odsbox-pilot/)
[![Python](https://img.shields.io/pypi/pyversions/odsbox-pilot)](https://pypi.org/project/odsbox-pilot/)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)
[![CI](https://github.com/totonga/odsbox-pilot/actions/workflows/ci.yml/badge.svg)](https://github.com/totonga/odsbox-pilot/actions/workflows/ci.yml)

A desktop query tool for [ASAM ODS](https://www.asam.net/standards/detail/ods/) servers, built on top of [odsbox](https://pypi.org/project/odsbox/).

## Features

- Connect to ASAM ODS servers with multiple auth modes (Basic, OIDC, M2M)
- Manage multiple server configurations with secure credential storage via `keyring`
- Interactive query editor with syntax highlighting (CodeMirror)
- Query history and built-in examples
- Tabular result display powered by pandas
- **Browse tab**: FilterTree-based ODS server navigation with lazy tree expansion,
  filter condition management, and attribute value discovery

## Requirements

- Python 3.14+
- A running ASAM ODS server

## Installation

```bash
pip install odsbox-pilot[gui]
```

## Usage

Launch without installing (always uses the latest release):

```bash
uvx odsbox-pilot[gui]@latest
```

Install as a persistent tool:

```bash
uv tool install odsbox-pilot[gui]
odsbox-pilot
```

Or run as a module:

```bash
python -m odsbox_pilot
```

### Browse tab

The **Browse** tab (second tab in the main window) lets you navigate the ODS
server hierarchy interactively:

1. **Filter Conditions** — add conditions per entity (e.g., `Project.name $like Elec*`).
   Use the **…** button next to a value field to discover distinct values or the min/max
   range directly from the server.  Conditions are persisted in
   `~/.ods-pilot/browse_conditions.json` across sessions.
2. **Root entity** — select which entity type to query as the tree root, then click **Query**.
3. **Tree** — expand nodes to follow relations one level at a time.  Each instance node
   shows related relation names; expanding a relation node fetches the connected instances.
4. **Query Preview** — shows the Jaquel query that will be (or was) sent to the server.

## Development

This project uses [uv](https://github.com/astral-sh/uv) for dependency management.

```bash
# Clone and set up
git clone https://github.com/totonga/odsbox-pilot.git
cd odsbox-pilot
uv sync

# Run tests
uv run pytest tests/unit/

# Lint and type-check
uv run ruff check src/ tests/
uv run mypy src/
```

## License

Apache License 2.0 — see [LICENSE](LICENSE) for details.
