# odsbox-pilot

[![PyPI](https://img.shields.io/pypi/v/odsbox-pilot)](https://pypi.org/project/odsbox-pilot/)
[![Python](https://img.shields.io/pypi/pyversions/odsbox-pilot)](https://pypi.org/project/odsbox-pilot/)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)
[![CI](https://github.com/totonga/odsbox-pilot/actions/workflows/ci.yml/badge.svg)](https://github.com/totonga/odsbox-pilot/actions/workflows/ci.yml)

**ODS Pilot** is a desktop application for querying and exploring
[ASAM ODS](https://www.asam.net/standards/detail/ods/) measurement-data servers.
It provides an interactive GUI that lets you write and run queries, browse the
data hierarchy, and inspect the entity-relation model — all without writing any code.

---

## Features at a glance

| | Feature |
|---|---|
| 🔌 | **Multi-server management** — save and switch between multiple ODS server configurations |
| 🔐 | **Secure credentials** — passwords stored in the OS keyring (never in plain text) |
| 🔑 | **Flexible authentication** — Basic, OIDC, and M2M auth modes |
| ✏️ | **Interactive query editor** — JSON/JAQueL editor with syntax highlighting (CodeMirror) |
| 📋 | **Examples & history** — built-in query examples and per-session history |
| 📊 | **Tabular results** — sortable result grid powered by pandas; export to CSV |
| 🌳 | **Browse tab** — point-and-click navigation of the data hierarchy with filter conditions |
| 🗂️ | **Model tab** — read-only browser for the complete entity-relation schema and enumerations |

---

## Requirements

- Python 3.14 or later
- A running ASAM ODS server (REST API)

---

## Installation

**Quickest start — no install needed** (always runs the latest release):

```bash
uvx odsbox-pilot[gui]@latest
```

**Install as a persistent tool** with [uv](https://docs.astral.sh/uv/):

```bash
uv tool install odsbox-pilot[gui]
odsbox-pilot
```

**Install with pip:**

```bash
pip install odsbox-pilot[gui]
python -m odsbox_pilot
```

---

## Quick start

1. Launch ODS Pilot — the **Server List** dialog opens automatically.
2. Click **Add…** and enter your server URL, username, and password.
3. Double-click your server (or select it and click **Connect**).
4. Use the tabs to query, browse, and inspect your data.

**Command-line shortcut** — skip the server list and connect directly:

```bash
odsbox-pilot --server "My Server"   # connect by saved name
odsbox-pilot --list-servers         # print all saved names
```

---

## The three tabs

### Query tab

Write [JAQueL](https://github.com/totonga/jaquel) queries in a JSON editor and run them
against the server. Results appear in a sortable table.

```json
{ "Unit": {} }
```

Use **Examples ▾** for ready-made patterns (filters, joins, aggregations) and
**History ▾** to re-run previous queries. Export any result with **Ctrl+S**.

### Browse tab

Navigate the ODS data hierarchy without writing queries. Pick a root entity, add optional
filter conditions, and click **Query**. Expand tree nodes to follow relations level by
level. Click any instance to see its attributes on the right. The JAQueL query for the
current view is shown in the preview panel.

Filter conditions are saved in `~/.ods-pilot/browse_conditions.json` and persist across
sessions.

### Model tab

A read-only schema browser loaded from the ODS model on connect (no extra server calls).
Entities are colour-coded by base type. Expand any entity to see its attributes
(with data-type symbols) and relations (with cardinality). All enumerations and their
index values are listed at the bottom.

---

## Keyboard shortcuts

| Shortcut | Action |
|---|---|
| **Alt+Enter** / **Ctrl+Enter** | Execute query |
| **Ctrl+S** | Export results to CSV |
| **Ctrl+W** | Disconnect from current server |
| **Alt+F4** | Exit |

---

## Documentation

- 📖 [Full user guide](USER.md) — detailed instructions for every feature
- 🛠️ [Developer guide](DEVELOPER.md) — setup, project structure, tests, and CI
- 📝 [Changelog](CHANGELOG.md)

---

## License

Apache License 2.0 — see [LICENSE](LICENSE) for details.
