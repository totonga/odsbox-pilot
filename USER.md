# ODS Pilot — User Guide

ODS Pilot is a desktop application for querying and exploring
[ASAM ODS](https://www.asam.net/standards/detail/ods/) servers.
This guide walks through everything you need to get started.

---

## Table of Contents

1. [Installation](#1-installation)
2. [First launch & connecting](#2-first-launch--connecting)
3. [Managing server connections](#3-managing-server-connections)
4. [Query tab](#4-query-tab)
5. [Browse tab](#5-browse-tab)
6. [Model tab](#6-model-tab)
7. [Keyboard shortcuts](#7-keyboard-shortcuts)
8. [Tips & troubleshooting](#8-tips--troubleshooting)

---

## 1. Installation

### Quickest way (no install needed)

```
uvx odsbox-pilot[gui]@latest
```

Requires [uv](https://docs.astral.sh/uv/getting-started/installation/).

### Install permanently

```
uv tool install odsbox-pilot[gui]
odsbox-pilot
```

### With pip

```
pip install odsbox-pilot[gui]
python -m odsbox_pilot
```

---

## 2. First launch & connecting

When ODS Pilot starts, the **Server List** dialog opens.

### Adding a new server

1. Click **Add…**.
2. Fill in the fields:
   | Field | Description |
   |---|---|
   | Name | A friendly label shown in the server list (e.g. `Production`) |
   | URL | Base URL of the ODS server REST API (e.g. `https://ods.example.com/api`) |
   | Username | Your login name |
   | Password | Stored securely via the OS keyring — never saved in plain text |
   | Auth mode | `basic` for username/password; `oidc` or `m2m` for token-based auth |
3. Click **OK** to save.

### Connecting

- Double-click a server in the list, **or** select it and click **Connect**.
- ODS Pilot opens the main window when the connection succeeds.

### Command-line shortcut

To skip the server list and connect directly:

```
odsbox-pilot --server "Production"
```

Use the name exactly as saved. To list all saved server names:

```
odsbox-pilot --list-servers
```

---

## 3. Managing server connections

From the **Server List** dialog you can:

| Action | How |
|---|---|
| Edit a server | Select it, click **Edit…** |
| Delete a server | Select it, click **Delete** |
| Re-order the list | Select and use the **↑ / ↓** buttons |
| Test the connection | Click **Connect** — a connection error shows a message |

To disconnect from the current server, use **File → Disconnect** (Ctrl+W) in the main window.
The Server List dialog re-appears, letting you connect to a different server.

---

## 4. Query tab

The **Query** tab (first tab) sends raw [JAQueL](https://github.com/totonga/jaquel) queries to the server and displays the results as a table.

### Editor toolbar

| Button | Action |
|---|---|
| **Examples ▾** | Drop-down of ready-made queries grouped by category |
| **History ▾** | Drop-down of previously executed queries |
| **Settings ▾** | Switch column naming between *Query* mode (JAQueL names) and *Model* mode (schema names like `Unit.Name`) |
| **Pretty Print** | Re-formats the JSON in the editor with indentation |
| **▶ Execute** | Sends the query to the server |

### Writing a query

Queries are JSON objects. The simplest form is:

```json
{ "Unit": {} }
```

This fetches all rows from the `Unit` entity. Refer to the **Examples** drop-down for
common patterns including filters, joins, ordering, and aggregations.

### Result table

- Results appear in the table below the editor.
- Click any column header to sort.
- **File → Export CSV…** (Ctrl+S) saves the current result to a CSV file.

### Query log

The panel at the bottom of the window shows a timestamped log of every query, its row count,
and whether it succeeded (✓) or failed (✗). Click a log entry to copy the query back to the editor.

---

## 5. Browse tab

The **Browse** tab (second tab) provides a point-and-click way to navigate the ODS data
hierarchy without writing queries manually.

### Toolbar

| Control | Description |
|---|---|
| **Root entity** combo box | Choose which entity type to use as the top level of the tree |
| **Query** button | Run the query and populate the tree |
| **Add condition / Edit / Remove / Clear** | Manage filter conditions |

### Filter conditions

Conditions narrow down which instances appear in the tree.  Each condition targets one entity
and one attribute.

1. Click **Add condition** (the `+` button).
2. Choose the **Entity** and **Attribute** from the drop-downs.
3. Pick an **Operator** (`=`, `$like`, `$between`, `$in`, …) and type a value.
   - Click **…** next to the value field to fetch distinct values or the min/max range
     directly from the server.
4. Click **OK**.

Conditions survive across sessions — they are saved in `~/.ods-pilot/browse_conditions.json`.

### Navigating the instance tree

- After clicking **Query**, the root level shows instances of the chosen entity.
- Expand any instance node to see the relations defined on that entity.
- Expand a relation node to fetch and display the connected instances.
- Click any instance node to see its attributes in the **Properties** panel on the right.

### Preview panel

The panel below the tree shows the JAQueL query that was (or will be) sent for the current
selection. The **Values** sub-tab shows a flat list of all visible attribute values for the
currently selected instance. The **Chart** sub-tab renders a simple bar chart when numeric
columns are present.

---

## 6. Model tab

The **Model** tab (third tab) is a read-only browser for the ODS entity-relation schema.
It uses the model that was already loaded on connect — no extra server calls.

### Entity tree

Entities are shown colour-coded by their ODS base type and sorted by base name then
application name.  Entities with base type `AoAny` appear last.

Expand an entity to reveal two sub-groups:

| Sub-group | Contents |
|---|---|
| **Attributes** | All attributes of the entity. Each shows a data-type symbol (e.g. `S` = string, `I32` = integer). |
| **Relations** | All relations. Cardinality (e.g. `1:n`) is shown inline. Expanding a relation node reveals the target entity, which can be expanded further. Cycles are detected and shown as `↩ EntityName (see above)`. |

### Enumeration tree

All enumerations defined in the model appear here, sorted alphabetically.  Expand an
enumeration to see its items and their numeric index values (sorted by index).

### Properties panel

Selecting any node in the tree populates the right-hand panel:

| Node type | Properties shown |
|---|---|
| Entity | Name, base name, attribute count, relation count |
| Attribute | Name, base name, data type, length, obligatory, unique, autogenerated, enumeration, unit ID, internal ID |
| Relation | All 15 proto fields: name, base name, target entity, target base name, inverse names, range, relation type, relationship, virtual/acl reference flags, entity aid |
| Enumeration | Name and all items with index values |
| Enumeration item | Enumeration name, item name, index value |

---

## 7. Keyboard shortcuts

| Shortcut | Action |
|---|---|
| **Alt+Enter** or **Ctrl+Enter** | Execute the current query (Query tab) |
| **Ctrl+S** | Export results to CSV |
| **Ctrl+W** | Disconnect from the current server |
| **Alt+F4** | Exit ODS Pilot |

---

## 8. Tips & troubleshooting

### The app starts but shows no data after connecting

Make sure the ODS server is reachable and your credentials are correct.  Check the **Query Log**
at the bottom of the window for error messages.

### "Browse" tab query runs automatically

When you switch to the Browse tab for the first time, the query runs automatically using
the selected root entity.  You can change the root entity and click **Query** at any time.

### Column names look wrong

Use **Settings ▾ → Result Naming: Model** to show schema-qualified names (e.g. `AoUnit.Name`)
instead of the raw JAQueL column names.

### Closing the app

- Click the **×** button, or use **File → Exit** (Alt+F4).
- Pressing **Ctrl+C** in the terminal also closes the app cleanly within ~200 ms.

### Passwords / credentials

Passwords are stored in the operating system keyring (Windows Credential Manager on Windows,
Keychain on macOS, SecretService on Linux) and are never written to disk in plain text.

### Server URL format

The URL must point to the REST API root, for example:

```
https://ods.example.com/api
https://localhost:8080/ods/rest
```

Trailing slashes are optional.
