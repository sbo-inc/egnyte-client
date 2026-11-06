# Changelog

## [0.1.0] - 2026-11-05

- `EgnyteClient` and `AsyncEgnyteClient`, method-for-method identical, over `httpx`.
- File system: `get_item`, `get_folder`, `get_folder_by_id`, `get_file`, `get_file_by_id`, `create_folder`, `upload_file`, `download_file`, `download_file_by_id`, `copy_item`, `move_item`, and `delete_item`.
- File system by ID: `copy_file_by_id`, `copy_folder_by_id`, `move_file_by_id`, `move_folder_by_id`, `delete_file_by_id`, `delete_folder_by_id`, and `get_folder_stats`.
- Locks: `lock_file`, `unlock_file`, `lock_file_by_id`, and `unlock_file_by_id`.
- Chunked upload: `upload_file_chunked` and `upload_file_chunked_by_id`, streaming bytes or a file object with Egnyte's composite checksum.
- Folder options, insights, and trash: `update_folder_options`, `list_recent_files`, `list_trash`, `count_trash`, `restore_trash_items`, and `purge_trash_items`.
- Permissions: `get_effective_permission`, `get_folder_permissions`, and `set_folder_permissions`.
- Comments and bookmarks: `create_comment`, `list_comments`, `get_comment`, `delete_comment`, `create_bookmark`, `list_bookmarks`, `get_bookmark`, and `delete_bookmark`.
- Metadata: namespaces (`list_`, `create_`, `get_`, `update_`, `delete_metadata_namespace`), keys (`add_`, `update_`, `delete_metadata_key`, `delete_metadata_key_values`, `delete_metadata_values`), and values on files and folders (`get_`/`set_file_metadata`, `get_`/`set_folder_metadata`).
- Events and webhooks: `get_event_cursor`, `list_events`, `create_webhook`, `list_webhooks`, `get_webhook`, `get_webhook_status`, `set_webhook_status`, `update_webhook`, `delete_webhook`, and `verify_webhook_authorization` for deliveries.
- Audit reporting: a `create_*_audit_report` method for each of the 14 report types, `get_audit_job`, `get_audit_report`, `download_audit_report`, `delete_audit_report`, and `stream_audit_events`.
- Links: `create_link`, `get_link`, `list_links`, and `delete_link`.
- Search: `search` over names, content, comments, and custom metadata, with folder, type, and date filters, similarity search, and `MetadataFilter`. The CLI command is `egnyte-client search`.
- Users: `list_users`, `get_user`, `create_user`, `update_user`, and `delete_user`.
- Groups: `list_groups`, `get_group`, `create_group`, `update_group`, `replace_group`, and `delete_group`.
- `get_user_info`, `get_token_info`, `revoke_token`, `refresh_access_token`, `exchange_authorization_code`, `login_with_password`, and `build_authorization_url`. A 401 refreshes the token once when refresh credentials are configured, and `on_token_refresh` receives the new pair.
- Calls refused by the per-second rate limit (HTTP 429, spike arrest) are retried after `Retry-After`. The daily quota raises `EgnyteQuotaExceededError` at once, and any other 429 is retried only when it asks for a wait of 5 seconds or less.
- Logging follows the library pattern: the `egnyte_client` logger has only a `NullHandler` and no level set. Requests log at DEBUG, retries and token refreshes at INFO; the CLI's `--log` prints them to stderr.
- Errors: every exception is an `EgnyteError`. `EgnyteAPIError` reads each of Egnyte's error body shapes into a message and code and keeps the response; `EgnyteValidationError` (400), `EgnyteAuthError` (401), `EgnyteForbiddenError` (403), `EgnyteNotFoundError` (404), `EgnyteConflictError` (409), `EgnyteRateLimitError` (429, with `retry_after`) and its `EgnyteQuotaExceededError` (the daily quota), and `EgnyteServerError` (5xx) subclass it, and `EgnyteConfigurationError` reports a missing domain, token, or credential.
- The `egnyte-client` CLI, with a command for every client method except the token grants: `auth`, `fs`, `search`, `trash`, `links`, `perms`, `comments`, `bookmarks`, `metadata`, `users`, `groups`, `events`, `webhooks`, and `audit`. Destructive commands confirm first (`--yes` skips), results print as JSON, and `EGNYTE_CLI_DISABLE` hides commands.
