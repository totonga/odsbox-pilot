# Portable connection format

Portable connection files are JSON documents that export an ODSPilot server definition without secrets. They are used by the import/export workflow in the server dialog and by the CLI import command.

## Required fields

- `name`: non-empty display name for the server.
- `url`: target ODS server URL or local ATFX file path.
- `auth_type`: one of `basic`, `m2m`, `oidc`, or `atfx`.

## Auth-specific fields

- Basic auth requires `username`.
- M2M auth requires `token_endpoint` and `client_id`.
- OIDC auth requires `client_id`.
- ATFX uses the file path in `url` and does not require additional auth fields.

## Optional fields

- `scope`: list of scopes for M2M auth.
- `redirect_uri`, `webfinger_path_prefix`, `redirect_url_allow_insecure`: OIDC options.
- `verify_certificate`: toggle TLS certificate verification.
- `context_variables`: optional key/value map passed to the connection context.

The schema for this format is stored in [ods-pilot.con.schema.json](https://github.com/totonga/odsbox-pilot/blob/main/src/odsbox_pilot/connection/ods-pilot.con.schema.json).
