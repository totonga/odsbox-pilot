# Portable connection format

Portable connection files export an ODS Pilot server definition without secrets. They are used by the import/export workflow in the server dialog and by the CLI import command.

The same format can be stored as either JSON or TOML. Use the `.ods-pilot.con.json` extension for JSON files and `.ods-pilot.con.toml` for TOML files. TOML files can include comments, which makes them convenient for longer manual edits.

## Required fields

- `name`: non-empty display name for the server.
- `url`: target ODS server URL or local ATFX file path.
- `auth_type`: one of `basic`, `m2m`, `oidc`, or `atfx`.

## Auth-specific fields

- Basic auth requires `username`.
- M2M auth requires `token_endpoint` and `client_id`.
- OIDC auth requires `client_id` and `redirect_uri`.
- ATFX uses the file path in `url` and does not require additional auth fields.

## Optional fields

- `scope`: list of scopes for M2M auth.
- `redirect_uri`, `webfinger_path_prefix`, `redirect_url_allow_insecure`: OIDC options.
- `verify_certificate`: toggle TLS certificate verification.
- `context_variables`: optional key/value map passed to the connection context.

## Examples

### JSON example: basic auth

```json
{
  "name": "Basic demo",
  "url": "https://demo.example.com/api",
  "auth_type": "basic",
  "username": "alice"
}
```

### TOML example: basic auth

```toml
# Portable connection example for a basic-auth ODS server
name = "Basic demo"
url = "https://demo.example.com/api"
auth_type = "basic"
username = "alice"
```

### TOML example: M2M auth

```toml
name = "M2M demo"
url = "https://m2m.example.com/api"
auth_type = "m2m"
token_endpoint = "https://auth.example.com/oauth/token"
client_id = "ods-pilot-client"
scope = ["ods.read", "ods.write"]
verify_certificate = false
```

You can find additional examples in [basic.ods-pilot.con.json](https://raw.githubusercontent.com/totonga/odsbox-pilot/refs/heads/main/docs/examples/connections/basic.ods-pilot.con.json), [basic.ods-pilot.con.toml](https://raw.githubusercontent.com/totonga/odsbox-pilot/refs/heads/main/docs/examples/connections/basic.ods-pilot.con.toml), [m2m.ods-pilot.con.json](https://raw.githubusercontent.com/totonga/odsbox-pilot/refs/heads/main/docs/examples/connections/basic.ods-pilot.con.json), [m2m.ods-pilot.con.toml](https://raw.githubusercontent.com/totonga/odsbox-pilot/refs/heads/main/docs/examples/connections/m2m.ods-pilot.con.toml), [oidc.ods-pilot.con.json](https://raw.githubusercontent.com/totonga/odsbox-pilot/refs/heads/main/docs/examples/connections/oidc.ods-pilot.con.json), and [oidc.ods-pilot.con.toml](https://raw.githubusercontent.com/totonga/odsbox-pilot/refs/heads/main/docs/examples/connections/oidc.ods-pilot.con.toml).

The schema for this format is stored in [ods-pilot.con.schema.json](https://raw.githubusercontent.com/totonga/odsbox-pilot/refs/heads/main/src/odsbox_pilot/connection/ods-pilot.con.schema.json).
