[![CI](https://github.com/sbo-inc/egnyte-client/actions/workflows/ci.yaml/badge.svg?branch=main)](https://github.com/sbo-inc/egnyte-client/actions/workflows/ci.yaml)
[![PyPI](https://img.shields.io/pypi/v/egnyte-client.svg)](https://pypi.org/project/egnyte-client/)
[![Python versions](https://img.shields.io/pypi/pyversions/egnyte-client.svg)](https://pypi.org/project/egnyte-client/)
[![License](https://img.shields.io/pypi/l/egnyte-client.svg)](https://github.com/sbo-inc/egnyte-client/blob/main/LICENSE)

# Egnyte Python client

An unofficial typed Python client and command-line interface for the [Egnyte Public API](https://developers.egnyte.com/integration/cfs/api-docs/getting-started). No affiliation with Egnyte is implied or intended.

The package wraps Egnyte's REST APIs in a fully type-hinted client built on [Pydantic](https://docs.pydantic.dev/), plus an `egnyte-client` CLI for quick access from the terminal. Responses are validated into predictable Python objects, so you can work with files, folders, search, links, users, and groups without hand-rolling requests.

## Features

- **Typed models.** Every response is parsed into Pydantic models with descriptive fields, and Egnyte's timestamps become `datetime`s.
- **Python client and CLI.** Use it as a library or from the shell via `egnyte-client`.
- **Sync and async.** `EgnyteClient` and `AsyncEgnyteClient` expose the same methods over `httpx`.
- **Sensible defaults.** Paths are encoded for you, calls refused by the rate limit are retried after `Retry-After`, and an expired token is refreshed when refresh credentials are configured.
- **The core platform.** Files and folders (including chunked upload, locks, and trash), search, links, permissions, comments, bookmarks, metadata, events, webhooks, users, groups, and audit reporting.
- **Typed errors.** Egnyte's error bodies come in several shapes. Each is raised as an `EgnyteError` with a status, message, and code. `EgnyteNotFoundError`, `EgnyteAuthError`, and `EgnyteRateLimitError` are its subclasses.

## Installation

The package is published on PyPI as [`egnyte-client`](https://pypi.org/project/egnyte-client/) and imported as `egnyte_client`:

```bash
pip install egnyte-client
# or, with uv:
uv add egnyte-client
```

Requires Python 3.12+.

## Configuration

Settings are read from environment variables, or can be passed directly to `EgnyteClient`:

| Variable | Description |
| --- | --- |
| `EGNYTE_DOMAIN` | Your domain: `acme`, `acme.egnyte.com`, or `https://acme.egnyte.com`. |
| `EGNYTE_ACCESS_TOKEN` | OAuth 2.0 bearer token. |
| `EGNYTE_REFRESH_TOKEN` | Optional. Refreshes an expired access token, together with the next two. |
| `EGNYTE_CLIENT_ID` | Optional. Your API key. |
| `EGNYTE_CLIENT_SECRET` | Optional. Your API secret. |

```bash
export EGNYTE_DOMAIN="acme"
export EGNYTE_ACCESS_TOKEN="your-access-token"
```

### Getting a token

Register an application at [developers.egnyte.com](https://developers.egnyte.com/) to get an API key and secret. Then complete one of the OAuth 2.0 flows in [Egnyte's authentication docs](https://developers.egnyte.com/integration/cfs/api-docs/authentication) against `https://<domain>.egnyte.com/puboauth/token`. Use the authorization code flow for public apps, or the resource-owner password flow for internal apps. Access tokens last 30 days.

The client can run the flow for you:

```python
from egnyte_client import EgnyteClient, build_authorization_url

url = build_authorization_url(
    "acme",
    client_id,
    "https://app.example.com/callback",
    scope=["Egnyte.filesystem"],
    state=state,
)
# ... send the user to `url`, then take `code` from the redirect:
client = EgnyteClient("acme", client_id=client_id, client_secret=client_secret)
token = client.exchange_authorization_code(code, "https://app.example.com/callback")

# Internal API keys can use the password grant instead:
token = client.login_with_password(username, password)
```

`get_token_info()` reports a token's user, domain, and scopes, and `revoke_token()` revokes it.

When `refresh_token`, `client_id`, and `client_secret` are all set, a call that fails with 401 refreshes the token once and is retried. Egnyte rotates the refresh token on every refresh, so the old refresh token stops working: pass `on_token_refresh` to save each new pair where the next run will find it. For example, with the pair kept in a JSON file:

```python
from pathlib import Path

from egnyte_client import EgnyteClient, OAuthToken

TOKEN_FILE = Path("egnyte-token.json")  # keep it out of version control


def save_token(token: OAuthToken) -> None:
    TOKEN_FILE.write_text(token.model_dump_json())


# The first pair comes from exchange_authorization_code() or
# login_with_password() above; save it with save_token(token).
token = OAuthToken.model_validate_json(TOKEN_FILE.read_text())

client = EgnyteClient(
    "acme",
    access_token=token.access_token,
    refresh_token=token.refresh_token,
    client_id="...",
    client_secret="...",
    on_token_refresh=save_token,  # called with each new OAuthToken
)
```

### Rate limits, timeouts and retries

Egnyte allows 2 calls per second per token, and between 1,000 and 4,000 calls per day depending on the plan. A call refused by the per-second limit (HTTP 429, a spike-arrest violation) is retried after its `Retry-After` (1 second if absent), up to `rate_limit_retries` times (default 5). The gateway refuses such a call before it reaches Egnyte, so retrying a write is safe. The daily quota is never retried: it raises `EgnyteQuotaExceededError` at once, since waiting seconds will not help and the quota resets at 00:00 UTC. Any other 429 is retried only when it asks for a wait of 5 seconds or less, so a long `Retry-After` never blocks the caller.

Every request carries a timeout (default `(5, 30)` seconds for connect and read). Pass `timeout=` to override it (a single float, a `(connect, read)` tuple, or `None` to disable). Pass `retries=` to retry connection-establishment failures:

```python
client = EgnyteClient(timeout=60, retries=3, rate_limit_retries=10)
```

The CLI reads `EGNYTE_API_TIMEOUT` (seconds), `EGNYTE_API_RETRIES` (count), and `EGNYTE_API_HEADERS` (a JSON object of extra headers) for the same behaviour.

## Quick start

### Python

```python
from egnyte_client import EgnyteClient, EgnyteNotFoundError

with EgnyteClient() as client:
    me = client.get_user_info()

    # Folders and files
    client.create_folder("/Shared/Reports/2026")
    uploaded = client.upload_file("/Shared/Reports/2026/summary.pdf", pdf_bytes)
    folder = client.get_folder("/Shared/Reports/2026")
    for file in folder.files:
        print(file.name, file.size, file.last_modified)
    data = client.download_file("/Shared/Reports/2026/summary.pdf")
    client.move_item(
        "/Shared/Reports/2026/summary.pdf", "/Shared/Reports/2026/final.pdf"
    )

    # Search names, content, comments, and metadata
    page = client.search("quarterly revenue", folder="/Shared/Reports", type="FILE")
    for hit in page.results:
        print(hit.path, hit.score, hit.snippet)

    # Links
    link = client.create_link(
        "/Shared/Reports/2026/final.pdf", "file", accessibility="domain"
    )
    print(link.url)
    client.delete_link(link.id)

    # Groups
    group = client.create_group("Reporting", [me.id])
    client.update_group(group.id, add_member_ids=[42])
    client.delete_group(group.id)

    try:
        client.get_file("/Shared/missing.txt")
    except EgnyteNotFoundError:
        ...
```

### Python (async)

`AsyncEgnyteClient` mirrors `EgnyteClient` method for method, with the same arguments and return types, awaited. Share one instance across tasks so they reuse its connection pool and tokens. Keep fan-out modest, because Egnyte allows two calls per second:

```python
import asyncio

from egnyte_client import AsyncEgnyteClient


async def main() -> None:
    async with AsyncEgnyteClient() as client:
        folder = await client.get_folder("/Shared/Reports")
        contents = await asyncio.gather(
            *(client.download_file(file.path) for file in folder.files[:4])
        )


asyncio.run(main())
```

### CLI

```console
$ egnyte-client auth whoami
$ egnyte-client fs ls /Shared/Reports --count 20
$ egnyte-client fs upload ./summary.pdf /Shared/Reports/
$ egnyte-client fs download /Shared/Reports/summary.pdf -o -
$ egnyte-client search "quarterly revenue" --folder /Shared/Reports --type file --in content
$ egnyte-client links create /Shared/Reports/summary.pdf --type file --accessibility domain
$ egnyte-client groups create Reporting --member 8
$ egnyte-client trash list --count 20
$ egnyte-client perms set /Shared/Reports --group Finance=Viewer
$ egnyte-client metadata set project --folder-id FOLDER_ID --value status=active
$ egnyte-client audit create files 2026-11-01 2026-11-05 --folder /Shared
$ egnyte-client --log users list --email jdoe@acme.com
```

Every client method has a command except the token grants (the CLI reads its token from the environment); the API reference below lists each one. `egnyte-client <group> --help` lists every option.

- **Output.** Results print as indented JSON, so they pipe into `jq`; downloads write raw bytes (`-o -` for stdout); a bare value, such as a lock token or a permission level, prints alone so a script can capture it.
- **Confirmation.** Commands that delete, purge, replace, or change permissions ask first, naming what will change; `-y`/`--yes` skips the prompt. Prompts go to stderr.
- **Structured input.** Options that take a structure, such as a namespace's keys or metadata values, take JSON (`--keys '[...]'`), checked before anything is sent.
- **Secrets.** The webhook `--auth-header` can come from `EGNYTE_WEBHOOK_AUTH_HEADER` instead, keeping it out of shell history, and is never printed back.
- **Disabling commands.** Set `EGNYTE_CLI_DISABLE` to a comma-separated list of dotted command paths (for example `users.delete,groups,metadata.namespaces.delete`) to hide and refuse those commands.

## Usage

### Pagination

List methods return one page, and the page size is capped by Egnyte. Each API family pages in its own style:

| API | Arguments | Cap |
| --- | --- | --- |
| Links, comments, bookmarks, audit report rows | `offset`, `count` | varies |
| Users, groups | `start_index` (1-based), `count` | 100 |
| Folder listing | `offset`, `count`; the folder's `total_count` says how many children there are | |
| Search | `offset`, `count`; continue while `has_more` | 20 |
| Trash | `offset`, `count`; continue while `has_more` | |
| Events | start from `get_event_cursor().latest_event_id`; each page's `latest_id` is the next start | |
| Audit stream | `start_date`, then each page's `next_cursor` while `more_events` | |

Every page is an API call, and Egnyte's daily quota is between 1,000 and 4,000 calls, so page deliberately.

### Errors

Every error this package raises is an `EgnyteError`:

| Exception | When |
| --- | --- |
| `EgnyteConfigurationError` | The domain, token, or OAuth credentials a call needs are missing. Also a `ValueError`. |
| `EgnyteAPIError` | Egnyte answered with an error status. Carries `status_code`, `message`, `code`, `body`, and `response`. |
| `EgnyteValidationError` | 400: the request's content was refused. |
| `EgnyteAuthError` | 401: the token is missing, invalid, expired, or revoked. |
| `EgnyteForbiddenError` | 403: not permitted, a missing scope, or (for folders) already exists. |
| `EgnyteNotFoundError` | 404: no such path, ID, link, user, or group. |
| `EgnyteConflictError` | 409: conflicts with existing state, such as a duplicate username. |
| `EgnyteRateLimitError` | 429: the per-second limit after every retry, or a refusal not worth retrying; `retry_after` is Egnyte's requested wait. |
| `EgnyteQuotaExceededError` | 429: the token's daily quota is used up (raised at once; resets at 00:00 UTC). A subclass of `EgnyteRateLimitError`. |
| `EgnyteServerError` | 5xx. |

Egnyte words its errors in several body shapes depending on the API; each is read into the same `message` and `code`:

```python
from egnyte_client import EgnyteForbiddenError, EgnyteNotFoundError

try:
    client.create_folder("/Shared/Reports")
except EgnyteForbiddenError:
    pass  # already exists
try:
    client.get_file("/Shared/missing.txt")
except EgnyteNotFoundError as error:
    print(error.message)
```

Arguments the client can check before sending (for example, two mutually exclusive filters) raise a plain `ValueError` without a request.

### Logging

The package logs to the `egnyte_client` logger and configures nothing itself: it attaches only a `NullHandler`, so records appear only where your application's logging sends them. Each request is logged at DEBUG (`GET /pubapi/v1/userinfo -> 200`); rate-limit retries and token refreshes at INFO.

```python
import logging

logging.basicConfig(level=logging.INFO)
logging.getLogger("egnyte_client").setLevel(logging.DEBUG)  # include each request
```

The CLI's `--log` flag prints the same records to stderr.

### Uploads and downloads

`upload_file()` sends content in one request and suits files up to about 100 MB. For larger files, `upload_file_chunked()` takes bytes or an open binary file and streams it in chunks; the CLI's `fs upload` switches to it on its own. `download_file()` returns the content as bytes.

### Background jobs

Audit reports are generated asynchronously:

```python
job = client.create_file_audit_report(start, end, folders=["/Shared"])
status = client.get_audit_job(job.id)  # poll at most every 2 minutes
if status.is_complete:
    report = client.get_audit_report(status.report_type, status.report_id)
    client.delete_audit_report(status.report_type, status.report_id)
```

## Design

### Operations, transport, and two clients

Each API call is described once, in `egnyte_client.operations`, as an `Operation`: method, path, query, body, and the parser that turns the response into a model. Nothing there performs I/O. `EgnyteClient` and `AsyncEgnyteClient` only put operations on the wire, through a shared transport that holds configuration, token refresh, the rate-limit retry, and error mapping. The two clients therefore have the same methods, arguments, docstrings, and return types, which a test checks.

### Live behaviour over the documentation

Where Egnyte's live API differs from its documentation, the models and methods follow the live API. For example, date values come back as epoch milliseconds, the by-ID chunked upload endpoint is unusable, and some status codes differ. Response models ignore fields they do not declare, so a new field from Egnyte never breaks parsing. Audit report rows and events also keep undeclared fields in `model_extra`, since their columns vary by report type.

## Reference Documentation

This client follows (to the extent possible) the API documentation Egnyte provides at [developers.egnyte.com](https://developers.egnyte.com/integration/cfs/api-docs/getting-started).

## API reference

Each section maps client methods to the Egnyte endpoints they call, and to the CLI command where there is one. `AsyncEgnyteClient` exposes every method as a coroutine of the same name.

### Auth

Docs: [Authentication](https://developers.egnyte.com/integration/cfs/api-docs/authentication)

| Client | Endpoint | CLI |
| --- | --- | --- |
| `build_authorization_url()` (function) | `GET /puboauth/token` | library only |
| `exchange_authorization_code()` | `POST /puboauth/token` | library only |
| `login_with_password()` | `POST /puboauth/token` | library only |
| `refresh_access_token()` | `POST /puboauth/token` | library only |
| `get_user_info()` | `GET /pubapi/v1/userinfo` | `egnyte-client auth whoami` |
| `get_token_info()` | `GET /pubapi/v1/whoami` | `egnyte-client auth token-info` |
| `revoke_token()` | `POST /pubapi/v1/tokens/revoke` | library only |

`build_authorization_url()` is a module function, as it makes no request. The token grants are library-only: the CLI reads its token from `EGNYTE_ACCESS_TOKEN`. Each grant adopts the new token pair and passes it to `on_token_refresh`.

### File system

Docs: [File System Management](https://developers.egnyte.com/integration/cfs/api-docs/file-system-management) · [Folder Options](https://developers.egnyte.com/integration/cfs/api-docs/folder-options-api)

| Client | Endpoint | CLI |
| --- | --- | --- |
| `get_folder()` | `GET /pubapi/v1/fs/{path}` | `egnyte-client fs ls` |
| `get_folder_by_id()` | `GET /pubapi/v1/fs/ids/folder/{id}` | `egnyte-client fs ls --folder-id ID` |
| `get_item()` | `GET /pubapi/v1/fs/{path}` | `egnyte-client fs stat` |
| `get_file()` | `GET /pubapi/v1/fs/{path}` | `egnyte-client fs stat --versions` |
| `get_file_by_id()` | `GET /pubapi/v1/fs/ids/file/{id}` | `egnyte-client fs stat --file-id ID` |
| `get_folder_stats()` | `GET /pubapi/v1/fs/ids/folder/{id}/stats` | `egnyte-client fs stats PATH` |
| `create_folder()` | `POST /pubapi/v1/fs/{path}` | `egnyte-client fs mkdir` |
| `update_folder_options()` | `PATCH /pubapi/v1/fs/{path}` | `egnyte-client fs options PATH` |
| `upload_file()` | `POST /pubapi/v1/fs-content/{path}` | `egnyte-client fs upload` |
| `upload_file_chunked()` | `POST /pubapi/v1/fs-content-chunked/{path}` | `egnyte-client fs upload LOCAL DEST (large files)` |
| `upload_file_chunked_by_id()` | `GET /pubapi/v1/fs/ids/file/{id}`, then `POST /pubapi/v1/fs-content-chunked/{path}` | `egnyte-client fs upload LOCAL --file-id ID (large files)` |
| `download_file()` | `GET /pubapi/v1/fs-content/{path}` | `egnyte-client fs download` |
| `download_file_by_id()` | `GET /pubapi/v1/fs-content/ids/file/{id}` | `egnyte-client fs download --file-id ID` |
| `copy_item()` | `POST /pubapi/v1/fs/{path}` | `egnyte-client fs cp` |
| `move_item()` | `POST /pubapi/v1/fs/{path}` | `egnyte-client fs mv` |
| `copy_file_by_id()` | `POST /pubapi/v1/fs/ids/file/{id}` | `egnyte-client fs cp --file-id ID DEST_FOLDER_ID` |
| `move_file_by_id()` | `POST /pubapi/v1/fs/ids/file/{id}` | `egnyte-client fs mv --file-id ID DEST_FOLDER_ID` |
| `copy_folder_by_id()` | `POST /pubapi/v1/fs/ids/folder/{id}` | `egnyte-client fs cp --folder-id ID DEST_FOLDER_ID` |
| `move_folder_by_id()` | `POST /pubapi/v1/fs/ids/folder/{id}` | `egnyte-client fs mv --folder-id ID DEST_FOLDER_ID` |
| `lock_file()` | `POST /pubapi/v1/fs/{path}` | `egnyte-client fs lock PATH` |
| `unlock_file()` | `POST /pubapi/v1/fs/{path}` | `egnyte-client fs unlock PATH --lock-token T` |
| `lock_file_by_id()` | `POST /pubapi/v1/fs/ids/file/{id}` | `egnyte-client fs lock --file-id ID` |
| `unlock_file_by_id()` | `POST /pubapi/v1/fs/ids/file/{id}` | `egnyte-client fs unlock --file-id ID --lock-token T` |
| `delete_item()` | `DELETE /pubapi/v1/fs/{path}` | `egnyte-client fs rm` |
| `delete_file_by_id()` | `DELETE /pubapi/v1/fs/ids/file/{id}` | `egnyte-client fs rm --file-id ID` |
| `delete_folder_by_id()` | `DELETE /pubapi/v1/fs/ids/folder/{id}` | `egnyte-client fs rm --folder-id ID` |

`upload_file()` sends one request and suits files up to about 100 MB. `upload_file_chunked()` streams bytes or a binary file object in chunks of 10 MiB to 1 GiB (default 100 MiB), with the composite checksum Egnyte verifies. Egnyte refuses content under 10 MiB on the chunked endpoint, so use `upload_file()` for small files. Egnyte's documented by-ID chunked endpoint rejects every upload, so `upload_file_chunked_by_id()` looks up the file's path (one extra call) and uploads to it. For chunked uploads, Egnyte stores the composite checksum, not a plain SHA-512. Downloads are read into memory.

### Search

Docs: [Search](https://developers.egnyte.com/integration/cfs/api-docs/search-api)

| Client | Endpoint | CLI |
| --- | --- | --- |
| `search()` | `POST /pubapi/v2/search` | `egnyte-client search` |

`search` matches file and folder names, file content, comments, and folder descriptions. It also takes:

- Filters: `folder`, `type`, and modified and uploaded date ranges.
- `metadata_filters`, a list of `MetadataFilter`s, for custom metadata.
- `similar_to_entry_ids` and `similar_to_text`, for similarity search.

The query must be 3 to 250 characters. Results arrive 20 at a time at most, best match first. Page with `offset` while `has_more` is true:

```python
from egnyte_client import MetadataFilter

offset = 0
while True:
    page = client.search(
        "invoice",
        metadata_filters=[
            MetadataFilter(namespace="finance", key="status", value="paid")
        ],
        offset=offset,
        count=20,
    )
    handle(page.results)
    if not page.has_more:
        break
    offset += page.count
```

Each page is one API call, so mind the daily quota when paging deep.

### Trash and insights

Docs: [Trash](https://developers.egnyte.com/integration/cfs/api-docs/trash-api) · [User Insights](https://developers.egnyte.com/integration/cfs/api-docs/user-insights-api)

| Client | Endpoint | CLI |
| --- | --- | --- |
| `list_trash()` | `GET /pubapi/v2/fs/trash` | `egnyte-client trash list` |
| `count_trash()` | `GET /pubapi/v2/fs/trash/totalcount` | `egnyte-client trash count` |
| `restore_trash_items()` | `POST /pubapi/v1/fs/trash` | `egnyte-client trash restore ITEM_ID...` |
| `purge_trash_items()` | `POST /pubapi/v1/fs/trash` | `egnyte-client trash purge ITEM_ID...` |
| `list_recent_files()` | `GET /pubapi/v1/insights/files` | `egnyte-client fs recent` |

Restore and purge take up to 10 item IDs and return one result per item, so a partial failure does not raise. Purging cannot be undone.

### Permissions

Docs: [Permissions](https://developers.egnyte.com/integration/cfs/api-docs/permissions-api)

| Client | Endpoint | CLI |
| --- | --- | --- |
| `get_effective_permission()` | `GET /pubapi/v1/perms/user/{username}` | `egnyte-client perms effective PATH` |
| `get_folder_permissions()` | `GET /pubapi/v2/perms/{path}` | `egnyte-client perms get PATH` |
| `set_folder_permissions()` | `POST /pubapi/v2/perms/{path}` | `egnyte-client perms set PATH` |

In `set_folder_permissions()`, mapping a user or group to `None` removes its permission. Egnyte rejects top-level paths such as `/Shared` (the path needs at least two segments).

### Comments and bookmarks

Docs: [Comments](https://developers.egnyte.com/integration/cfs/api-docs/comments-api) · [Bookmarks](https://developers.egnyte.com/integration/cfs/api-docs/bookmarks-api)

| Client | Endpoint | CLI |
| --- | --- | --- |
| `create_comment()` | `POST /pubapi/v1/notes` | `egnyte-client comments create PATH MESSAGE` |
| `list_comments()` | `GET /pubapi/v1/notes` | `egnyte-client comments list` |
| `get_comment()` | `GET /pubapi/v1/notes/{id}` | `egnyte-client comments get ID` |
| `delete_comment()` | `DELETE /pubapi/v1/notes/{id}` | `egnyte-client comments delete ID` |
| `create_bookmark()` | `POST /pubapi/v1/bookmarks` | `egnyte-client bookmarks create PATH` |
| `list_bookmarks()` | `GET /pubapi/v1/bookmarks` | `egnyte-client bookmarks list` |
| `get_bookmark()` | `GET /pubapi/v1/bookmarks/{id}` | `egnyte-client bookmarks get ID` |
| `delete_bookmark()` | `DELETE /pubapi/v1/bookmarks/{id}` | `egnyte-client bookmarks delete ID` |

### Metadata

Docs: [Metadata](https://developers.egnyte.com/integration/cfs/api-docs/metadata-api)

| Client | Endpoint | CLI |
| --- | --- | --- |
| `list_metadata_namespaces()` | `GET /pubapi/v1/properties/namespace` | `egnyte-client metadata namespaces list` |
| `create_metadata_namespace()` | `POST /pubapi/v1/properties/namespace` | `egnyte-client metadata namespaces create NAME --keys JSON` |
| `get_metadata_namespace()` | `GET /pubapi/v1/properties/namespace/{ns}` | `egnyte-client metadata namespaces get NAMESPACE` |
| `update_metadata_namespace()` | `PATCH /pubapi/v1/properties/namespace/{ns}` | `egnyte-client metadata namespaces update NAMESPACE` |
| `delete_metadata_namespace()` | `DELETE /pubapi/v1/properties/namespace/{ns}` | `egnyte-client metadata namespaces delete NAMESPACE` |
| `add_metadata_key()` | `POST /pubapi/v1/properties/namespace/{ns}/keys` | `egnyte-client metadata keys add NAMESPACE KEY` |
| `update_metadata_key()` | `PATCH /pubapi/v1/properties/namespace/{ns}/keys/{key}` | `egnyte-client metadata keys update NAMESPACE KEY` |
| `delete_metadata_key()` | `DELETE /pubapi/v1/properties/namespace/{ns}/keys/{key}` | `egnyte-client metadata keys delete NAMESPACE KEY` |
| `delete_metadata_key_values()` | `PATCH /pubapi/v1/properties/namespace/{ns}/keys/{key}/data` | `egnyte-client metadata keys delete-values NAMESPACE KEY VALUE...` |
| `delete_metadata_values()` | `PATCH /pubapi/v1/properties/namespace/{ns}/keys/data` | `egnyte-client metadata namespaces delete-values NAMESPACE` |
| `get_file_metadata()` | `GET /pubapi/v1/fs/ids/file/{id}/properties/{ns}` | `egnyte-client metadata get NAMESPACE --file-id ID` |
| `set_file_metadata()` | `PUT /pubapi/v1/fs/ids/file/{id}/properties/{ns}` | `egnyte-client metadata set NAMESPACE --file-id ID` |
| `get_folder_metadata()` | `GET /pubapi/v1/fs/ids/folder/{id}/properties/{ns}` | `egnyte-client metadata get NAMESPACE --folder-id ID` |
| `set_folder_metadata()` | `PUT /pubapi/v1/fs/ids/folder/{id}/properties/{ns}` | `egnyte-client metadata set NAMESPACE --folder-id ID` |

Date values go over the wire as epoch milliseconds; pass a `date` or `datetime`. Setting a value to `None` removes it. Pass `force=True` to the deletes to remove definitions that are in use. To search by metadata, use `search(metadata_filters=...)`.

### Events and webhooks

Docs: [Events](https://developers.egnyte.com/integration/cfs/api-docs/events-api) · [Webhooks](https://developers.egnyte.com/integration/cfs/api-docs/webhooks-api)

| Client | Endpoint | CLI |
| --- | --- | --- |
| `get_event_cursor()` | `GET /pubapi/v1/events/cursor` | `egnyte-client events cursor` |
| `list_events()` | `GET /pubapi/v2/events` | `egnyte-client events list START_ID` |
| `create_webhook()` | `POST /pubapi/v1/webhooks` | `egnyte-client webhooks create URL` |
| `list_webhooks()` | `GET /pubapi/v1/webhooks` | `egnyte-client webhooks list` |
| `get_webhook()` | `GET /pubapi/v1/webhooks/{id}/details` | `egnyte-client webhooks get ID` |
| `get_webhook_status()` | `GET /pubapi/v1/webhooks/{id}/status` | `egnyte-client webhooks status ID` |
| `set_webhook_status()` | `POST /pubapi/v1/webhooks/{id}/status` | `egnyte-client webhooks enable ID / disable ID` |
| `update_webhook()` | `PUT /pubapi/v1/webhooks/{id}` | `egnyte-client webhooks update ID URL` |
| `delete_webhook()` | `DELETE /pubapi/v1/webhooks/{id}` | `egnyte-client webhooks delete ID` |

`list_events()` returns a page whose `latest_id` is the cursor for the next call. Egnyte sends back the `auth_header` registered with a webhook as each delivery's `Authorization` header; check it with `verify_webhook_authorization()` from `egnyte_client.operations.webhook`, and parse delivery bodies with the `WebhookDelivery` model. Webhook calls need the `Egnyte.webhooks` scope.

### Audit reporting

Docs: [Audit Reporting v1](https://developers.egnyte.com/integration/cfs/api-docs/audit-reporting-api/v1) · [Audit Reporting v2](https://developers.egnyte.com/integration/cfs/api-docs/audit-reporting-api/v2)

| Client | Endpoint | CLI |
| --- | --- | --- |
| `create_login_audit_report()` | `POST /pubapi/v1/audit/logins` | `egnyte-client audit create logins START END` |
| `create_file_audit_report()` | `POST /pubapi/v1/audit/files` | `egnyte-client audit create files START END` |
| `create_permissions_audit_report()` | `POST /pubapi/v1/audit/permissions` | `egnyte-client audit create permissions START END` |
| `create_user_audit_report()` | `POST /pubapi/v1/audit/users` | `egnyte-client audit create users START END` |
| `create_group_audit_report()` | `POST /pubapi/v1/audit/groups` | `egnyte-client audit create groups START END` |
| `create_workgroup_settings_audit_report()` | `POST /pubapi/v1/audit/workgroup-settings` | `egnyte-client audit create workgroup-settings START END` |
| `create_workflow_audit_report()` | `POST /pubapi/v1/audit/workflows` | `egnyte-client audit create workflows START END` |
| `create_workflow_template_audit_report()` | `POST /pubapi/v1/audit/workflow-templates` | `egnyte-client audit create workflow-templates START END` |
| `create_quality_docs_audit_report()` | `POST /pubapi/v1/audit/quality-docs` | `egnyte-client audit create quality-docs START END` |
| `create_quality_docs_categories_audit_report()` | `POST /pubapi/v1/audit/quality-docs-categories` | `egnyte-client audit create quality-docs-categories START END` |
| `create_quality_docs_courses_audit_report()` | `POST /pubapi/v1/audit/quality-docs-courses` | `egnyte-client audit create quality-docs-courses START END` |
| `create_etmf_audit_report()` | `POST /pubapi/v1/audit/etmf` | `egnyte-client audit create etmf START END` |
| `create_snapshot_restore_audit_report()` | `POST /pubapi/v1/audit/snapshot-restore` | `egnyte-client audit create snapshot-restore START END` |
| `create_upload_requests_audit_report()` | `POST /pubapi/v1/audit/upload-requests` | `egnyte-client audit create upload-requests START END` |
| `get_audit_job()` | `GET /pubapi/v1/audit/jobs/{id}` | `egnyte-client audit job JOB_ID` |
| `get_audit_report()` | `GET /pubapi/v1/audit/{type}/{id}` | `egnyte-client audit get TYPE REPORT_ID` |
| `download_audit_report()` | `GET /pubapi/v1/audit/{type}/{id}` | `egnyte-client audit download TYPE REPORT_ID` |
| `delete_audit_report()` | `DELETE /pubapi/v1/audit/{type}/{id}` | `egnyte-client audit delete TYPE REPORT_ID` |
| `stream_audit_events()` | `POST /pubapi/v2/audit/stream` | `egnyte-client audit stream --start-date DATE` |

Reports are generated asynchronously: create one, poll `get_audit_job()` (Egnyte asks for no more than once every 2 minutes) until `is_complete`, then read it with `get_audit_report()` (JSON) or `download_audit_report()` (CSV bytes). `stream_audit_events()` pages through the last 7 days of events with a cursor.

### Links

Docs: [Links](https://developers.egnyte.com/integration/cfs/api-docs/links-api)

| Client | Endpoint | CLI |
| --- | --- | --- |
| `list_links()` | `GET /pubapi/v2/links` | `egnyte-client links list` |
| `get_link()` | `GET /pubapi/v1/links/{id}` | `egnyte-client links get` |
| `create_link()` | `POST /pubapi/v1/links` | `egnyte-client links create` |
| `delete_link()` | `DELETE /pubapi/v1/links/{id}` | `egnyte-client links delete` |

### Users

Docs: [User Management](https://developers.egnyte.com/integration/cfs/api-docs/user-management-api)

| Client | Endpoint | CLI |
| --- | --- | --- |
| `list_users()` | `GET /pubapi/v2/users` | `egnyte-client users list` |
| `get_user()` | `GET /pubapi/v2/users/{id}` | `egnyte-client users get` |
| `create_user()` | `POST /pubapi/v2/users` | `egnyte-client users create` |
| `update_user()` | `PATCH /pubapi/v2/users/{id}` | `egnyte-client users update` |
| `delete_user()` | `DELETE /pubapi/v2/users/{id}` | `egnyte-client users delete` |

Creating a user emails an invitation unless `send_invite=False`. For `egnyte` authentication, Egnyte always sends one.

### Groups

Docs: [Group Management](https://developers.egnyte.com/integration/cfs/api-docs/group-management)

| Client | Endpoint | CLI |
| --- | --- | --- |
| `list_groups()` | `GET /pubapi/v2/groups` | `egnyte-client groups list` |
| `get_group()` | `GET /pubapi/v2/groups/{id}` | `egnyte-client groups get` |
| `create_group()` | `POST /pubapi/v2/groups` | `egnyte-client groups create` |
| `update_group()` | `PATCH /pubapi/v2/groups/{id}` | `egnyte-client groups update` |
| `replace_group()` | `PUT /pubapi/v2/groups/{id}` | `egnyte-client groups replace ID NAME --member ID...` |
| `delete_group()` | `DELETE /pubapi/v2/groups/{id}` | `egnyte-client groups delete` |

Egnyte requires at least one member to create a group, although its documentation marks `members` optional.

## License

[MIT](LICENSE)
