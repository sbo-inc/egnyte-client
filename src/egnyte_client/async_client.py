import asyncio
from collections.abc import Mapping
from datetime import date, datetime
from typing import BinaryIO, Literal, Self

import httpx

from egnyte_client.errors import EgnyteConfigurationError
from egnyte_client.operations import audit as audit_ops
from egnyte_client.operations import auth as auth_ops
from egnyte_client.operations import bookmark as bookmark_ops
from egnyte_client.operations import comment as comment_ops
from egnyte_client.operations import event as event_ops
from egnyte_client.operations import filesystem as fs_ops
from egnyte_client.operations import group as group_ops
from egnyte_client.operations import insights as insights_ops
from egnyte_client.operations import link as link_ops
from egnyte_client.operations import metadata as metadata_ops
from egnyte_client.operations import permission as permission_ops
from egnyte_client.operations import search as search_ops
from egnyte_client.operations import trash as trash_ops
from egnyte_client.operations import user as user_ops
from egnyte_client.operations import webhook as webhook_ops
from egnyte_client.operations.filesystem import Permissions, SortBy, SortDirection
from egnyte_client.operations.generic import Operation
from egnyte_client.schemas.audit import (
    AuditEventPage,
    AuditJob,
    AuditJobStatus,
    AuditReport,
    AuditReportFormat,
    AuditReportType,
    AuditStreamType,
    EtmfAuditAction,
    FileAuditTransaction,
    GroupAuditAction,
    LoginAccessPoint,
    LoginAuditEvent,
    QualityDocsAuditAction,
    QualityDocsCategoryAuditAction,
    QualityDocsCategoryFilter,
    QualityDocsCourseAuditAction,
    QualityDocsCourseParameter,
    QualityDocsStatus,
    UploadRequestAuditAction,
    UserAuditAction,
    WorkflowAuditAction,
    WorkflowAuditType,
    WorkflowTemplateAuditAction,
)
from egnyte_client.schemas.auth import OAuthToken, TokenInfo, UserInfo
from egnyte_client.schemas.bookmark import Bookmark
from egnyte_client.schemas.comment import Comment
from egnyte_client.schemas.event import EventCursor, EventPage, EventSuppress, EventType
from egnyte_client.schemas.filesystem import (
    CreatedFolder,
    DeletedItem,
    File,
    FileLock,
    Folder,
    FolderOptionsMode,
    FolderStats,
    InheritanceRule,
    ItemReference,
    MoveDeleteRestriction,
    PublicLinks,
    UploadedFile,
)
from egnyte_client.schemas.group import Group, GroupSummary
from egnyte_client.schemas.insights import RecentFile
from egnyte_client.schemas.link import Link, LinkAccessibility, LinkProtection, LinkType
from egnyte_client.schemas.metadata import (
    DocumentType,
    MetadataKeyDefinition,
    MetadataKeyType,
    MetadataKeyValue,
    MetadataNamespace,
    MetadataScope,
    MetadataScopeType,
    MetadataValueInput,
)
from egnyte_client.schemas.permission import (
    EffectivePermissionLevel,
    FolderPermissions,
    PermissionLevel,
)
from egnyte_client.schemas.search import (
    FileQueryField,
    FolderQueryField,
    MetadataFilter,
    QueryOperator,
    SearchResults,
    SearchSortBy,
    SearchType,
)
from egnyte_client.schemas.trash import (
    TrashItemStatus,
    TrashPage,
    TrashSortBy,
    TrashSortDirection,
)
from egnyte_client.schemas.user import AuthType, User, UserType
from egnyte_client.schemas.webhook import Webhook, WebhookDetails, WebhookEventType
from egnyte_client.transport import (
    DEFAULT_RATE_LIMIT_RETRIES,
    DEFAULT_TIMEOUT,
    BaseEgnyteClient,
    TokenCallback,
)

__all__ = ["AsyncEgnyteClient"]


# =============================================================================
# CLASS: AsyncEgnyteClient
# =============================================================================


class AsyncEgnyteClient(BaseEgnyteClient):
    """
    Asynchronous Egnyte Public API Client

    Mirrors `EgnyteClient` method for method, over `httpx.AsyncClient`. Both
    clients build the same operations and differ only in how they put them on
    the wire, so behaviour, arguments, and return types match exactly.

    One instance is meant to be shared across tasks: its connection pool and
    its tokens are both reused, and gathered calls that all see an expired
    token refresh it once rather than once each. Egnyte allows about two calls
    per second per token, so bound the fan-out; refused calls are retried.

    https://developers.egnyte.com/integration/cfs/api-docs/getting-started
    """

    def __init__(
        self,
        domain: str | None = None,
        access_token: str | None = None,
        *,
        refresh_token: str | None = None,
        client_id: str | None = None,
        client_secret: str | None = None,
        on_token_refresh: TokenCallback | None = None,
        headers: Mapping[str, str] | None = None,
        timeout: float | tuple[float, float] | None = DEFAULT_TIMEOUT,
        retries: int | None = None,
        rate_limit_retries: int = DEFAULT_RATE_LIMIT_RETRIES,
    ) -> None:
        """
        Create a new asynchronous client for the Egnyte Public API.

        Args:
            domain: The Egnyte domain, as `acme`, `acme.egnyte.com`, or a URL (Environment: `EGNYTE_DOMAIN`)
            access_token: OAuth bearer token (Environment: `EGNYTE_ACCESS_TOKEN`)
            refresh_token: OAuth refresh token; with the client ID and secret,
                an expired access token is refreshed and the call retried
                once (Environment: `EGNYTE_REFRESH_TOKEN`)
            client_id: The API key (Environment: `EGNYTE_CLIENT_ID`)
            client_secret: The API secret (Environment: `EGNYTE_CLIENT_SECRET`)
            on_token_refresh: Called with the new token pair after a refresh,
                so the caller can persist it; Egnyte rotates the refresh token.
            headers: Additional headers to include in requests
            timeout: Per-request timeout in seconds applied to every call.
                Accepts a single float, a `(connect, read)` tuple, or `None`
                to disable. Defaults to `DEFAULT_TIMEOUT`.
            retries: Number of times to retry connection-establishment
                failures, which is safe for non-idempotent calls: a retry only
                ever happens before any bytes reach the server. `None`
                (default) disables retries.
            rate_limit_retries: Number of times a call refused by the
                per-second rate limit (HTTP 429) is retried after its
                `Retry-After`. Defaults to `DEFAULT_RATE_LIMIT_RETRIES`.
        """
        super().__init__(
            domain=domain,
            access_token=access_token,
            refresh_token=refresh_token,
            client_id=client_id,
            client_secret=client_secret,
            on_token_refresh=on_token_refresh,
            timeout=timeout,
            rate_limit_retries=rate_limit_retries,
        )

        self._http = httpx.AsyncClient(
            headers=dict(headers or {}),
            transport=httpx.AsyncHTTPTransport(retries=retries) if retries else None,
        )

        # Guards the refresh so gathered callers that all see the expired
        # token refresh it once rather than once each.
        self._token_lock = asyncio.Lock()

    @property
    def http(self) -> httpx.AsyncClient:
        """
        The underlying HTTP client.

        Returns:
            httpx.AsyncClient: The underlying HTTP client.
        """
        return self._http

    # -------------------------------------------------------------------------
    # METHOD: aclose
    # -------------------------------------------------------------------------

    async def aclose(self) -> None:
        """
        Close the underlying HTTP client and its connection pool.
        """
        await self._http.aclose()

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self.aclose()

    # -------------------------------------------------------------------------
    # METHOD: _send
    # -------------------------------------------------------------------------

    async def _send(self, operation: Operation[object]) -> httpx.Response:
        """
        Send an operation, refreshing on a 401 and waiting out a 429.

        A 401 is answered by one refresh and one retry, when refresh
        credentials are configured. A 429 is retried after its `Retry-After`,
        up to `rate_limit_retries` times. Any other failure raises.

        Returns:
            httpx.Response: The successful response.
        """
        refreshed = False
        attempt = 0
        while True:
            token = self.access_token
            response = await self._http.send(self._build_request(self._http, operation))

            if response.status_code == 401 and not refreshed and self._can_refresh():
                refreshed = True
                async with self._token_lock:
                    # Another task may have refreshed while this one waited.
                    if self.access_token == token:
                        await self.refresh_access_token()
                continue

            delay = self._retry_delay(response, attempt)
            if delay is not None:
                attempt += 1
                await asyncio.sleep(delay)
                continue

            self._raise_for_status(response, operation.accept)
            return response

    # -------------------------------------------------------------------------
    # METHOD: _run
    # -------------------------------------------------------------------------

    async def _run[T](self, operation: Operation[T]) -> T:
        """
        Send one operation and parse its response.

        Returns:
            T: Whatever the operation's parser produces.
        """
        return operation.parse(await self._send(operation))

    # -------------------------------------------------------------------------
    # METHOD: refresh_access_token
    # -------------------------------------------------------------------------

    async def refresh_access_token(self) -> OAuthToken:
        """
        Exchange the refresh token for a new access and refresh token pair.

        The client adopts the new pair and passes it to `on_token_refresh`.
        Called automatically on a 401 when refresh credentials are configured.

        Returns:
            OAuthToken: The new token pair.
        """
        grant = self._refresh_grant()
        response = await self._http.send(self._build_token_request(self._http, grant))
        return self._apply_token(response)

    # -------------------------------------------------------------------------
    # METHOD: exchange_authorization_code
    # -------------------------------------------------------------------------

    async def exchange_authorization_code(
        self, code: str, redirect_uri: str
    ) -> OAuthToken:
        """
        Exchange the `code` from the authorization redirect for a token pair.

        Completes the flow started at `build_authorization_url`; `redirect_uri`
        must be the one that URL carried. Needs the client ID and secret. The
        client adopts the new pair and passes it to `on_token_refresh`.

        Returns:
            OAuthToken: The new token pair.
        """
        grant = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
        }
        response = await self._http.send(self._build_token_request(self._http, grant))
        return self._apply_token(response)

    # -------------------------------------------------------------------------
    # METHOD: login_with_password
    # -------------------------------------------------------------------------

    async def login_with_password(
        self, username: str, password: str, *, scope: list[str] | None = None
    ) -> OAuthToken:
        """
        Get a token pair with a user's Egnyte username and password.

        The resource-owner password grant, which Egnyte allows only for
        internal API keys. Needs the client ID and secret. The client adopts
        the new pair and passes it to `on_token_refresh`.

        Returns:
            OAuthToken: The new token pair.
        """
        grant = {"grant_type": "password", "username": username, "password": password}
        if scope:
            grant["scope"] = " ".join(scope)
        response = await self._http.send(self._build_token_request(self._http, grant))
        return self._apply_token(response)

    # -------------------------------------------------------------------------
    # METHOD: get_user_info
    # -------------------------------------------------------------------------

    async def get_user_info(self) -> UserInfo:
        """
        Get the user the access token belongs to.

        Returns:
            UserInfo: The calling user.
        """
        return await self._run(auth_ops.get_user_info())

    # -------------------------------------------------------------------------
    # METHOD: get_token_info
    # -------------------------------------------------------------------------

    async def get_token_info(self) -> TokenInfo:
        """
        Inspect the access token: its API key, user, domain, and scopes.

        Returns:
            TokenInfo: What the token grants.
        """
        return await self._run(auth_ops.get_token_info())

    # -------------------------------------------------------------------------
    # METHOD: revoke_token
    # -------------------------------------------------------------------------

    async def revoke_token(self, token: str | None = None) -> None:
        """
        Revoke a token, by default the client's own access token.

        Revoking an access token also revokes its refresh token. When the
        token is the client's own, the client forgets both, so later calls
        fail until a new token is set. Needs the client secret.
        """
        if not self.client_secret:
            raise EgnyteConfigurationError("Revoking a token needs the client secret")
        target = token or self.access_token
        if not target:
            raise ValueError("No token to revoke")

        await self._run(auth_ops.revoke_token(target, self.client_secret))

        if target in (self.access_token, self.refresh_token):
            self.access_token = None
            self.refresh_token = None

    # -------------------------------------------------------------------------
    # METHOD: get_item
    # -------------------------------------------------------------------------

    async def get_item(self, path: str) -> File | Folder:
        """
        Get the metadata of a file or folder by path.

        A folder is returned with its first page of children.

        Returns:
            File | Folder: The item, typed by what the path holds.
        """
        return await self._run(fs_ops.get_item(path))

    # -------------------------------------------------------------------------
    # METHOD: get_folder
    # -------------------------------------------------------------------------

    async def get_folder(
        self,
        path: str,
        *,
        count: int | None = None,
        offset: int | None = None,
        sort_by: SortBy | None = None,
        sort_direction: SortDirection | None = None,
    ) -> Folder:
        """
        Get a folder by path, with one page of its sub-folders and files.

        `count` and `offset` page through the children; `total_count` on the
        result says how many there are.

        Returns:
            Folder: The folder and the listed children.
        """
        return await self._run(
            fs_ops.get_folder(
                path,
                count=count,
                offset=offset,
                sort_by=sort_by,
                sort_direction=sort_direction,
            )
        )

    # -------------------------------------------------------------------------
    # METHOD: get_folder_by_id
    # -------------------------------------------------------------------------

    async def get_folder_by_id(
        self,
        folder_id: str,
        *,
        count: int | None = None,
        offset: int | None = None,
        sort_by: SortBy | None = None,
        sort_direction: SortDirection | None = None,
    ) -> Folder:
        """
        Get a folder by folder ID, with one page of its sub-folders and files.

        Returns:
            Folder: The folder and the listed children.
        """
        return await self._run(
            fs_ops.get_folder_by_id(
                folder_id,
                count=count,
                offset=offset,
                sort_by=sort_by,
                sort_direction=sort_direction,
            )
        )

    # -------------------------------------------------------------------------
    # METHOD: get_file
    # -------------------------------------------------------------------------

    async def get_file(self, path: str, *, include_versions: bool = False) -> File:
        """
        Get a file's metadata by path, optionally with its stored versions.

        Returns:
            File: The file metadata.
        """
        return await self._run(fs_ops.get_file(path, include_versions=include_versions))

    # -------------------------------------------------------------------------
    # METHOD: get_file_by_id
    # -------------------------------------------------------------------------

    async def get_file_by_id(
        self, group_id: str, *, include_versions: bool = False
    ) -> File:
        """
        Get a file's metadata by group ID, optionally with its stored versions.

        Returns:
            File: The file metadata.
        """
        return await self._run(
            fs_ops.get_file_by_id(group_id, include_versions=include_versions)
        )

    # -------------------------------------------------------------------------
    # METHOD: create_folder
    # -------------------------------------------------------------------------

    async def create_folder(self, path: str) -> CreatedFolder:
        """
        Create a folder at an absolute path.

        Raises `EgnyteForbiddenError` (403) when the folder already exists.

        Returns:
            CreatedFolder: The new folder's ID and path.
        """
        return await self._run(fs_ops.create_folder(path))

    # -------------------------------------------------------------------------
    # METHOD: upload_file
    # -------------------------------------------------------------------------

    async def upload_file(
        self,
        path: str,
        data: bytes,
        *,
        last_modified: datetime | None = None,
    ) -> UploadedFile:
        """
        Upload content to a file path, creating the file or adding a version.

        Sent in one request, which suits files up to about 100 MB. The SHA-512
        of `data` is sent along, so Egnyte rejects content damaged in transit.

        Returns:
            UploadedFile: The stored version's IDs and checksum.
        """
        return await self._run(
            fs_ops.upload_file(path, data, last_modified=last_modified)
        )

    # -------------------------------------------------------------------------
    # METHOD: download_file
    # -------------------------------------------------------------------------

    async def download_file(self, path: str, *, entry_id: str | None = None) -> bytes:
        """
        Download a file's content by path.

        `entry_id` selects a stored version; the current one by default.

        Returns:
            bytes: The file content.
        """
        return await self._run(fs_ops.download_file(path, entry_id=entry_id))

    # -------------------------------------------------------------------------
    # METHOD: download_file_by_id
    # -------------------------------------------------------------------------

    async def download_file_by_id(
        self, group_id: str, *, entry_id: str | None = None
    ) -> bytes:
        """
        Download a file's content by group ID.

        `entry_id` selects a stored version; the current one by default.

        Returns:
            bytes: The file content.
        """
        return await self._run(fs_ops.download_file_by_id(group_id, entry_id=entry_id))

    # -------------------------------------------------------------------------
    # METHOD: copy_item
    # -------------------------------------------------------------------------

    async def copy_item(
        self,
        path: str,
        destination: str,
        *,
        permissions: Permissions | None = None,
    ) -> ItemReference:
        """
        Copy a file or folder to an absolute destination path.

        The destination is the full new path, including the item's name.

        Returns:
            ItemReference: The copy's path and ID.
        """
        return await self._run(
            fs_ops.transfer_item("copy", path, destination, permissions=permissions)
        )

    # -------------------------------------------------------------------------
    # METHOD: move_item
    # -------------------------------------------------------------------------

    async def move_item(
        self,
        path: str,
        destination: str,
        *,
        permissions: Permissions | None = None,
    ) -> ItemReference:
        """
        Move or rename a file or folder to an absolute destination path.

        The destination is the full new path, including the item's name.

        Returns:
            ItemReference: The item's new path and ID.
        """
        return await self._run(
            fs_ops.transfer_item("move", path, destination, permissions=permissions)
        )

    # -------------------------------------------------------------------------
    # METHOD: delete_item
    # -------------------------------------------------------------------------

    async def delete_item(
        self, path: str, *, entry_id: str | None = None
    ) -> DeletedItem:
        """
        Delete a file or folder by path, moving it to the trash.

        `entry_id` deletes a single version of a file instead.

        Returns:
            DeletedItem: The folder the item was deleted from.
        """
        return await self._run(fs_ops.delete_item(path, entry_id=entry_id))

    # -------------------------------------------------------------------------
    # METHOD: copy_file_by_id
    # -------------------------------------------------------------------------

    async def copy_file_by_id(
        self,
        group_id: str,
        destination_folder_id: str,
        *,
        name: str | None = None,
        permissions: Permissions | None = None,
    ) -> ItemReference:
        """
        Copy a file, by group ID, into a folder, by folder ID.

        The copy keeps the file's name unless `name` gives a new one.

        Returns:
            ItemReference: The copy's path and group ID.
        """
        return await self._run(
            fs_ops.transfer_item_by_id(
                "copy",
                "file",
                group_id,
                destination_folder_id,
                name=name,
                permissions=permissions,
            )
        )

    # -------------------------------------------------------------------------
    # METHOD: copy_folder_by_id
    # -------------------------------------------------------------------------

    async def copy_folder_by_id(
        self,
        folder_id: str,
        destination_folder_id: str,
        *,
        name: str | None = None,
        permissions: Permissions | None = None,
        folder_options_mode: FolderOptionsMode | None = None,
    ) -> ItemReference:
        """
        Copy a folder, by folder ID, into another folder, by folder ID.

        The copy keeps the folder's name unless `name` gives a new one.
        `folder_options_mode` keeps the source's folder options or applies the
        destination's; the workgroup setting decides by default.

        Returns:
            ItemReference: The copy's path and folder ID.
        """
        return await self._run(
            fs_ops.transfer_item_by_id(
                "copy",
                "folder",
                folder_id,
                destination_folder_id,
                name=name,
                permissions=permissions,
                folder_options_mode=folder_options_mode,
            )
        )

    # -------------------------------------------------------------------------
    # METHOD: move_file_by_id
    # -------------------------------------------------------------------------

    async def move_file_by_id(
        self,
        group_id: str,
        destination_folder_id: str,
        *,
        name: str | None = None,
        permissions: Permissions | None = None,
    ) -> ItemReference:
        """
        Move a file, by group ID, into a folder, by folder ID.

        The file keeps its name unless `name` gives a new one.

        Returns:
            ItemReference: The file's new path and group ID.
        """
        return await self._run(
            fs_ops.transfer_item_by_id(
                "move",
                "file",
                group_id,
                destination_folder_id,
                name=name,
                permissions=permissions,
            )
        )

    # -------------------------------------------------------------------------
    # METHOD: move_folder_by_id
    # -------------------------------------------------------------------------

    async def move_folder_by_id(
        self,
        folder_id: str,
        destination_folder_id: str,
        *,
        name: str | None = None,
        permissions: Permissions | None = None,
        folder_options_mode: FolderOptionsMode | None = None,
    ) -> ItemReference:
        """
        Move a folder, by folder ID, into another folder, by folder ID.

        The folder keeps its name unless `name` gives a new one.
        `folder_options_mode` keeps the folder's options or applies the
        destination's; the workgroup setting decides by default.

        Returns:
            ItemReference: The folder's new path and folder ID.
        """
        return await self._run(
            fs_ops.transfer_item_by_id(
                "move",
                "folder",
                folder_id,
                destination_folder_id,
                name=name,
                permissions=permissions,
                folder_options_mode=folder_options_mode,
            )
        )

    # -------------------------------------------------------------------------
    # METHOD: delete_file_by_id
    # -------------------------------------------------------------------------

    async def delete_file_by_id(
        self, group_id: str, *, entry_id: str | None = None
    ) -> DeletedItem:
        """
        Delete a file by group ID, moving it to the trash.

        `entry_id` deletes a single version of the file instead.

        Returns:
            DeletedItem: The folder the file was deleted from.
        """
        return await self._run(
            fs_ops.delete_item_by_id("file", group_id, entry_id=entry_id)
        )

    # -------------------------------------------------------------------------
    # METHOD: delete_folder_by_id
    # -------------------------------------------------------------------------

    async def delete_folder_by_id(self, folder_id: str) -> DeletedItem:
        """
        Delete a folder by folder ID, moving it and its contents to the trash.

        Returns:
            DeletedItem: The folder the folder was deleted from.
        """
        return await self._run(fs_ops.delete_item_by_id("folder", folder_id))

    # -------------------------------------------------------------------------
    # METHOD: get_folder_stats
    # -------------------------------------------------------------------------

    async def get_folder_stats(self, folder_id: str) -> FolderStats:
        """
        Get the size and item counts of a folder, including its sub-folders.

        Returns:
            FolderStats: The folder's file, version, and sub-folder totals.
        """
        return await self._run(fs_ops.get_folder_stats(folder_id))

    # -------------------------------------------------------------------------
    # METHOD: lock_file
    # -------------------------------------------------------------------------

    async def lock_file(
        self,
        path: str,
        *,
        lock_token: str | None = None,
        lock_timeout: int | None = None,
        collaboration: str | None = None,
    ) -> FileLock:
        """
        Lock a file by path, or refresh a lock held with `lock_token`.

        Egnyte generates the token unless one is given. `lock_timeout` is in
        seconds, 3600 by default and at most 604800 (seven days);
        `collaboration` is the base64 token of a UI Integration Framework app.

        Returns:
            FileLock: The lock's token and timeout.
        """
        return await self._run(
            fs_ops.lock_file(
                path=path,
                lock_token=lock_token,
                lock_timeout=lock_timeout,
                collaboration=collaboration,
            )
        )

    # -------------------------------------------------------------------------
    # METHOD: unlock_file
    # -------------------------------------------------------------------------

    async def unlock_file(self, path: str, lock_token: str) -> None:
        """
        Unlock a file by path with the token it was locked with.
        """
        return await self._run(fs_ops.unlock_file(lock_token, path=path))

    # -------------------------------------------------------------------------
    # METHOD: lock_file_by_id
    # -------------------------------------------------------------------------

    async def lock_file_by_id(
        self,
        group_id: str,
        *,
        lock_token: str | None = None,
        lock_timeout: int | None = None,
        collaboration: str | None = None,
    ) -> FileLock:
        """
        Lock a file by group ID, or refresh a lock held with `lock_token`.

        Egnyte generates the token unless one is given. `lock_timeout` is in
        seconds, 3600 by default and at most 604800 (seven days);
        `collaboration` is the base64 token of a UI Integration Framework app.

        Returns:
            FileLock: The lock's token and timeout.
        """
        return await self._run(
            fs_ops.lock_file(
                group_id=group_id,
                lock_token=lock_token,
                lock_timeout=lock_timeout,
                collaboration=collaboration,
            )
        )

    # -------------------------------------------------------------------------
    # METHOD: unlock_file_by_id
    # -------------------------------------------------------------------------

    async def unlock_file_by_id(self, group_id: str, lock_token: str) -> None:
        """
        Unlock a file by group ID with the token it was locked with.
        """
        return await self._run(fs_ops.unlock_file(lock_token, group_id=group_id))

    # -------------------------------------------------------------------------
    # METHOD: upload_file_chunked
    # -------------------------------------------------------------------------

    async def upload_file_chunked(
        self,
        path: str,
        data: bytes | BinaryIO,
        *,
        chunk_size: int = fs_ops.DEFAULT_CHUNK_SIZE,
        last_modified: datetime | None = None,
    ) -> UploadedFile:
        """
        Upload content to a file path in chunks, for files too large for one request.

        `data` is bytes or a binary stream; a stream is read one chunk at a
        time, so the file is never held whole. Every chunk but the last is
        `chunk_size` bytes, between 10 MiB and 1 GiB (100 MiB by default).
        Egnyte refuses content under 10 MiB here, so that raises `ValueError`
        before anything is sent; `upload_file` suits it. Each chunk and the
        whole file are checksummed, so Egnyte rejects content damaged in
        transit. The chunks are sent one after another.

        Returns:
            UploadedFile: The stored version's IDs and its composite checksum,
                `2-{chunks}-{chunk size}-{SHA-512 of the chunk checksums}`.
        """
        upload = fs_ops.upload_file_chunked(
            path, data, chunk_size=chunk_size, last_modified=last_modified
        )
        while (chunk := upload.next_chunk()) is not None:
            await self._run(chunk)
        return await self._run(upload.last_chunk())

    # -------------------------------------------------------------------------
    # METHOD: upload_file_chunked_by_id
    # -------------------------------------------------------------------------

    async def upload_file_chunked_by_id(
        self,
        group_id: str,
        data: bytes | BinaryIO,
        *,
        chunk_size: int = fs_ops.DEFAULT_CHUNK_SIZE,
        last_modified: datetime | None = None,
    ) -> UploadedFile:
        """
        Upload a new version of a file, by group ID, in chunks.

        Chunking works as in `upload_file_chunked`. Egnyte's by-ID chunked
        endpoint rejects every upload, so the file's current path is looked
        up first (one extra call) and the chunks go to that path.

        Returns:
            UploadedFile: The stored version's IDs and its composite checksum.
        """
        path = (await self.get_file_by_id(group_id)).path
        return await self.upload_file_chunked(
            path, data, chunk_size=chunk_size, last_modified=last_modified
        )

    # -------------------------------------------------------------------------
    # METHOD: update_folder_options
    # -------------------------------------------------------------------------

    async def update_folder_options(
        self,
        path: str,
        *,
        description: str | None = None,
        allow_links: bool | None = None,
        allow_upload_links: bool | None = None,
        public_links: PublicLinks | None = None,
        restrict_move_delete: bool | None = None,
        move_delete_folder_restriction: MoveDeleteRestriction | None = None,
        inheritance_rule: InheritanceRule | None = None,
        notify_content_updates: bool | None = None,
        notify_content_accessed: bool | None = None,
    ) -> Folder:
        """
        Change a folder's description, link, move and delete, and notification options.

        Only the options given are changed; at least one is required.
        `description` is at most 200 characters. `allow_links=False` disables
        every link regardless of `public_links`. `move_delete_folder_restriction`
        overrides `restrict_move_delete` when both are given, and neither applies
        to top-level folders. `inheritance_rule` sets how far the options reach
        into sub-folders. The two `notify_*` flags set the caller's email
        notifications for uploads and for downloads; Egnyte does not report them
        back, and only power users and admins may set `notify_content_accessed`.

        Returns:
            Folder: The folder's updated metadata, without its children.
        """
        return await self._run(
            fs_ops.update_folder_options(
                path,
                description=description,
                allow_links=allow_links,
                allow_upload_links=allow_upload_links,
                public_links=public_links,
                restrict_move_delete=restrict_move_delete,
                move_delete_folder_restriction=move_delete_folder_restriction,
                inheritance_rule=inheritance_rule,
                notify_content_updates=notify_content_updates,
                notify_content_accessed=notify_content_accessed,
            )
        )

    # -------------------------------------------------------------------------
    # METHOD: list_recent_files
    # -------------------------------------------------------------------------

    async def list_recent_files(
        self, *, folder_path: str | None = None
    ) -> list[RecentFile]:
        """
        List the files the caller accessed most recently, optionally within a folder.

        Egnyte returns up to ten, most recently accessed first.

        Returns:
            list[RecentFile]: The recent files.
        """
        return await self._run(insights_ops.list_recent_files(folder_path=folder_path))

    # -------------------------------------------------------------------------
    # METHOD: list_trash
    # -------------------------------------------------------------------------

    async def list_trash(
        self,
        *,
        sort_by: TrashSortBy | None = None,
        sort_direction: TrashSortDirection | None = None,
        offset: int | None = None,
        count: int | None = None,
        deleted_by: str | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> TrashPage:
        """
        List one page of the trash, newest deletion first by default.

        Needs an admin, or a power user allowed to manage the trash. `count`
        defaults to 50; `has_more` on the result says whether another page
        follows. `deleted_by` matches the deleting user's first or last name.
        Filtering by `deleted_by` or by date needs both `start_date` and
        `end_date`; naive datetimes are read as UTC.

        Returns:
            TrashPage: The items in the page.
        """
        return await self._run(
            trash_ops.list_trash(
                sort_by=sort_by,
                sort_direction=sort_direction,
                offset=offset,
                count=count,
                deleted_by=deleted_by,
                start_date=start_date,
                end_date=end_date,
            )
        )

    # -------------------------------------------------------------------------
    # METHOD: count_trash
    # -------------------------------------------------------------------------

    async def count_trash(self) -> int:
        """
        Count the items in the trash.

        Returns:
            int: The total number of trash items.
        """
        return await self._run(trash_ops.count_trash())

    # -------------------------------------------------------------------------
    # METHOD: restore_trash_items
    # -------------------------------------------------------------------------

    async def restore_trash_items(self, item_ids: list[str]) -> list[TrashItemStatus]:
        """
        Restore up to ten trash items, by trash item ID, to where they were deleted from.

        A partial failure does not raise: each item's status says whether it
        was restored.

        Returns:
            list[TrashItemStatus]: One status per item.
        """
        return await self._run(trash_ops.trash_action("RESTORE", item_ids))

    # -------------------------------------------------------------------------
    # METHOD: purge_trash_items
    # -------------------------------------------------------------------------

    async def purge_trash_items(self, item_ids: list[str]) -> list[TrashItemStatus]:
        """
        Permanently delete up to ten trash items, by trash item ID.

        Purged items cannot be recovered. A partial failure does not raise:
        each item's status says whether it was purged.

        Returns:
            list[TrashItemStatus]: One status per item.
        """
        return await self._run(trash_ops.trash_action("PURGE", item_ids))

    # -------------------------------------------------------------------------
    # METHOD: search
    # -------------------------------------------------------------------------

    async def search(
        self,
        query: str | None = None,
        *,
        folder: str | None = None,
        type: SearchType | None = None,
        modified_after: datetime | None = None,
        modified_before: datetime | None = None,
        uploaded_after: datetime | None = None,
        uploaded_before: datetime | None = None,
        file_query_fields: list[FileQueryField] | None = None,
        folder_query_fields: list[FolderQueryField] | None = None,
        query_operator: QueryOperator | None = None,
        metadata_filters: list[MetadataFilter] | None = None,
        namespaces: list[str] | None = None,
        similar_to_entry_ids: list[str] | None = None,
        similar_to_text: list[str] | None = None,
        include_snippets: bool | None = None,
        sort_by: SearchSortBy | None = None,
        sort_direction: Literal["ascending", "descending"] | None = None,
        offset: int | None = None,
        count: int | None = None,
    ) -> SearchResults:
        """
        Search file and folder names, file content, comments, and metadata.

        Needs a `query` (3 to 250 characters), `metadata_filters`, or a
        similarity source. `query` matches any of its terms unless
        `query_operator="ALL"`; `file_query_fields` and `folder_query_fields`
        narrow where it matches. `folder` scopes the search to a folder and
        everything under it, and `type` to files or folders. `similar_to_entry_ids`
        and `similar_to_text` find items like the given file versions or text.

        Results come a page at a time: `count` is 1 to 20 (default 20), and
        the next page starts at `offset + count` while `has_more` is true.

        Returns:
            SearchResults: One page of hits, best first unless `sort_by` is set.
        """
        return await self._run(
            search_ops.search(
                query,
                folder=folder,
                type=type,
                modified_after=modified_after,
                modified_before=modified_before,
                uploaded_after=uploaded_after,
                uploaded_before=uploaded_before,
                file_query_fields=file_query_fields,
                folder_query_fields=folder_query_fields,
                query_operator=query_operator,
                metadata_filters=metadata_filters,
                namespaces=namespaces,
                similar_to_entry_ids=similar_to_entry_ids,
                similar_to_text=similar_to_text,
                include_snippets=include_snippets,
                sort_by=sort_by,
                sort_direction=sort_direction,
                offset=offset,
                count=count,
            )
        )

    # -------------------------------------------------------------------------
    # METHOD: get_effective_permission
    # -------------------------------------------------------------------------

    async def get_effective_permission(
        self, folder: str, *, username: str | None = None
    ) -> EffectivePermissionLevel:
        """
        Get a user's effective permission on a folder.

        The level accounts for the user's own grants, their groups, and
        inheritance. `username` defaults to the caller. `Nav` means the user
        can only see the folder on the way to something below it.

        Returns:
            EffectivePermissionLevel: None, Nav, Viewer Only, Viewer, Editor,
                Full, or Owner.
        """
        return await self._run(
            permission_ops.get_effective_permission(folder, username=username)
        )

    # -------------------------------------------------------------------------
    # METHOD: get_folder_permissions
    # -------------------------------------------------------------------------

    async def get_folder_permissions(self, path: str) -> FolderPermissions:
        """
        Get the user and group permissions set on a folder.

        Egnyte refuses top-level folders such as `/Shared`; the path needs at
        least two segments.

        Returns:
            FolderPermissions: The grants by username and group name, and
                whether the folder inherits from its parent.
        """
        return await self._run(permission_ops.get_folder_permissions(path))

    # -------------------------------------------------------------------------
    # METHOD: set_folder_permissions
    # -------------------------------------------------------------------------

    async def set_folder_permissions(
        self,
        path: str,
        *,
        user_permissions: Mapping[str, PermissionLevel | None] | None = None,
        group_permissions: Mapping[str, PermissionLevel | None] | None = None,
        inherits_permissions: bool | None = None,
        keep_parent_permissions: bool | None = None,
    ) -> None:
        """
        Grant, change, or remove user and group permissions on a folder.

        This is a delta: only the users and groups named change. Map a
        username or group name to a level to grant it, or to `None` to remove
        its permission (sent as Egnyte's `"None"` level). Set
        `inherits_permissions=False` to stop inheriting from the parent, with
        `keep_parent_permissions=True` to copy the inherited grants onto the
        folder first; `keep_parent_permissions` is only valid then. The
        caller needs Owner on the folder or admin rights.
        """
        return await self._run(
            permission_ops.set_folder_permissions(
                path,
                user_permissions=user_permissions,
                group_permissions=group_permissions,
                inherits_permissions=inherits_permissions,
                keep_parent_permissions=keep_parent_permissions,
            )
        )

    # -------------------------------------------------------------------------
    # METHOD: create_comment
    # -------------------------------------------------------------------------

    async def create_comment(self, path: str, body: str) -> Comment:
        """
        Add a comment to a file.

        Returns:
            Comment: The new comment.
        """
        return await self._run(comment_ops.create_comment(path, body))

    # -------------------------------------------------------------------------
    # METHOD: list_comments
    # -------------------------------------------------------------------------

    async def list_comments(
        self,
        *,
        filter_by_path: str | None = None,
        filter_by_start_time: datetime | None = None,
        filter_by_end_time: datetime | None = None,
        offset: int | None = None,
        count: int | None = None,
    ) -> list[Comment]:
        """
        List one page of comments, on one file or across the domain.

        Without `filter_by_path`, every comment in the domain is listed, which
        only admins may do. The time filters bound when comments were made;
        a naive datetime is read as UTC. `count` defaults to 25 and is capped
        at 100 by Egnyte.

        Returns:
            list[Comment]: The comments in the page.
        """
        return await self._run(
            comment_ops.list_comments(
                filter_by_path=filter_by_path,
                filter_by_start_time=filter_by_start_time,
                filter_by_end_time=filter_by_end_time,
                offset=offset,
                count=count,
            )
        )

    # -------------------------------------------------------------------------
    # METHOD: get_comment
    # -------------------------------------------------------------------------

    async def get_comment(self, comment_id: str) -> Comment:
        """
        Get a comment by ID.

        Returns:
            Comment: The comment.
        """
        return await self._run(comment_ops.get_comment(comment_id))

    # -------------------------------------------------------------------------
    # METHOD: delete_comment
    # -------------------------------------------------------------------------

    async def delete_comment(self, comment_id: str) -> None:
        """
        Delete a comment by ID.
        """
        return await self._run(comment_ops.delete_comment(comment_id))

    # -------------------------------------------------------------------------
    # METHOD: create_bookmark
    # -------------------------------------------------------------------------

    async def create_bookmark(
        self, *, path: str | None = None, folder_id: str | None = None
    ) -> Bookmark:
        """
        Bookmark a folder for the caller, by path or by folder ID.

        Exactly one of `path` and `folder_id` must be given.

        Returns:
            Bookmark: The new bookmark.
        """
        return await self._run(
            bookmark_ops.create_bookmark(path=path, folder_id=folder_id)
        )

    # -------------------------------------------------------------------------
    # METHOD: list_bookmarks
    # -------------------------------------------------------------------------

    async def list_bookmarks(
        self, *, offset: int | None = None, count: int | None = None
    ) -> list[Bookmark]:
        """
        List one page of the caller's bookmarks.

        Returns:
            list[Bookmark]: The bookmarks in the page.
        """
        return await self._run(bookmark_ops.list_bookmarks(offset=offset, count=count))

    # -------------------------------------------------------------------------
    # METHOD: get_bookmark
    # -------------------------------------------------------------------------

    async def get_bookmark(self, bookmark_id: int) -> Bookmark:
        """
        Get a bookmark by ID.

        Returns:
            Bookmark: The bookmark.
        """
        return await self._run(bookmark_ops.get_bookmark(bookmark_id))

    # -------------------------------------------------------------------------
    # METHOD: delete_bookmark
    # -------------------------------------------------------------------------

    async def delete_bookmark(self, bookmark_id: int) -> None:
        """
        Delete a bookmark by ID.
        """
        return await self._run(bookmark_ops.delete_bookmark(bookmark_id))

    # -------------------------------------------------------------------------
    # METHOD: get_event_cursor
    # -------------------------------------------------------------------------

    async def get_event_cursor(self) -> EventCursor:
        """
        Get the current position of the domain's event stream.

        Start polling `list_events` from `latest_event_id` to see what happens
        from now on. The stream keeps the latest 500,000 events, up to 30 days.

        Returns:
            EventCursor: The newest and oldest event IDs available.
        """
        return await self._run(event_ops.get_event_cursor())

    # -------------------------------------------------------------------------
    # METHOD: list_events
    # -------------------------------------------------------------------------

    async def list_events(
        self,
        start_id: int,
        *,
        count: int | None = None,
        filter_by_folder: str | None = None,
        filter_by_types: list[EventType] | None = None,
        suppress: EventSuppress | None = None,
        reverse: bool | None = None,
    ) -> EventPage:
        """
        List one page of events after a cursor, from the v2 event stream.

        `filter_by_types` defaults to file_system, note, and permission_change
        events. `filter_by_folder` scopes the stream to a folder and everything
        under it. `suppress="app"` or `"user"` leaves out what this application
        or the calling user did. `count` is 1 to 100 (default 50). `reverse`
        walks backwards, returning events `start_id - count + 1` to `start_id`.

        Poll by passing the page's `latest_id` as the next `start_id`; when
        nothing follows the cursor the page is empty and `latest_id` stays
        `start_id`. Egnyte asks for at least 5 minutes between polls.

        Returns:
            EventPage: The events and the cursor to continue from.
        """
        return await self._run(
            event_ops.list_events(
                start_id,
                count=count,
                filter_by_folder=filter_by_folder,
                filter_by_types=filter_by_types,
                suppress=suppress,
                reverse=reverse,
            )
        )

    # -------------------------------------------------------------------------
    # METHOD: create_link
    # -------------------------------------------------------------------------

    async def create_link(
        self,
        path: str,
        type: LinkType,
        *,
        accessibility: LinkAccessibility | None = None,
        use_default_settings: bool | None = None,
        send_email: bool | None = None,
        recipients: list[str] | None = None,
        message: str | None = None,
        copy_me: bool | None = None,
        notify: bool | None = None,
        link_to_current: bool | None = None,
        expiry_date: date | None = None,
        expiry_clicks: int | None = None,
        add_file_name: bool | None = None,
        password: str | None = None,
        protection: LinkProtection | None = None,
        folder_per_recipient: bool | None = None,
    ) -> Link:
        """
        Create a shared link to a file or folder, or an upload link to a folder.

        `accessibility` is required unless `use_default_settings` is true or
        the link is an upload link.

        Returns:
            Link: The new link; `id` and `url` are its first issued URL.
        """
        return await self._run(
            link_ops.create_link(
                path,
                type,
                accessibility=accessibility,
                use_default_settings=use_default_settings,
                send_email=send_email,
                recipients=recipients,
                message=message,
                copy_me=copy_me,
                notify=notify,
                link_to_current=link_to_current,
                expiry_date=expiry_date,
                expiry_clicks=expiry_clicks,
                add_file_name=add_file_name,
                password=password,
                protection=protection,
                folder_per_recipient=folder_per_recipient,
            )
        )

    # -------------------------------------------------------------------------
    # METHOD: get_link
    # -------------------------------------------------------------------------

    async def get_link(self, link_id: str) -> Link:
        """
        Get a link's details by ID.

        Returns:
            Link: The link.
        """
        return await self._run(link_ops.get_link(link_id))

    # -------------------------------------------------------------------------
    # METHOD: list_links
    # -------------------------------------------------------------------------

    async def list_links(
        self,
        *,
        filter_by_path: str | None = None,
        filter_by_username: str | None = None,
        filter_by_type: LinkType | None = None,
        filter_by_accessibility: LinkAccessibility | None = None,
        filter_by_created_after: datetime | None = None,
        filter_by_created_before: datetime | None = None,
        offset: int | None = None,
        count: int | None = None,
    ) -> list[Link]:
        """
        List one page of links, with their details.

        Admins see every link in the domain, other users their own. `count`
        defaults to and is capped at 500 by Egnyte.

        Returns:
            list[Link]: The links in the page.
        """
        return await self._run(
            link_ops.list_links(
                filter_by_path=filter_by_path,
                filter_by_username=filter_by_username,
                filter_by_type=filter_by_type,
                filter_by_accessibility=filter_by_accessibility,
                filter_by_created_after=filter_by_created_after,
                filter_by_created_before=filter_by_created_before,
                offset=offset,
                count=count,
            )
        )

    # -------------------------------------------------------------------------
    # METHOD: delete_link
    # -------------------------------------------------------------------------

    async def delete_link(self, link_id: str) -> None:
        """
        Delete a link by ID.
        """
        return await self._run(link_ops.delete_link(link_id))

    # -------------------------------------------------------------------------
    # METHOD: list_metadata_namespaces
    # -------------------------------------------------------------------------

    async def list_metadata_namespaces(
        self, *, include_folder_associations: bool | None = None
    ) -> list[MetadataNamespace]:
        """
        List the domain's metadata namespaces and their keys.

        `include_folder_associations` adds the folders each folder-scoped
        namespace applies to.

        Returns:
            list[MetadataNamespace]: Every namespace the caller can see.
        """
        return await self._run(
            metadata_ops.list_metadata_namespaces(
                include_folder_associations=include_folder_associations
            )
        )

    # -------------------------------------------------------------------------
    # METHOD: create_metadata_namespace
    # -------------------------------------------------------------------------

    async def create_metadata_namespace(
        self,
        name: str,
        *,
        keys: Mapping[str, MetadataKeyDefinition],
        scope: MetadataScope = "public",
        display_name: str | None = None,
        inheritable: bool | None = None,
        scope_type: MetadataScopeType | None = None,
        folder_ids: list[str] | None = None,
        document_types: list[DocumentType] | None = None,
    ) -> None:
        """
        Create a metadata namespace with its keys.

        `keys` maps each key name to its definition. `scope` decides who sees
        and edits the namespace: `public` (everyone), `protected` (everyone
        sees, only this app edits), or `private` (only this app). `scope_type`
        limits where it applies: `FOLDER_SCOPE` to `folder_ids`, and
        `DOCUMENT_TYPE` to `document_types`, which it then requires.
        `inheritable` lets child items inherit the values. Needs an admin.
        """
        return await self._run(
            metadata_ops.create_metadata_namespace(
                name,
                keys=keys,
                scope=scope,
                display_name=display_name,
                inheritable=inheritable,
                scope_type=scope_type,
                folder_ids=folder_ids,
                document_types=document_types,
            )
        )

    # -------------------------------------------------------------------------
    # METHOD: get_metadata_namespace
    # -------------------------------------------------------------------------

    async def get_metadata_namespace(self, namespace: str) -> MetadataNamespace:
        """
        Get a metadata namespace and its key definitions by name.

        Returns:
            MetadataNamespace: The namespace.
        """
        return await self._run(metadata_ops.get_metadata_namespace(namespace))

    # -------------------------------------------------------------------------
    # METHOD: update_metadata_namespace
    # -------------------------------------------------------------------------

    async def update_metadata_namespace(
        self,
        namespace: str,
        *,
        display_name: str | None = None,
        priorities: Mapping[str, int] | None = None,
        associate_folder_ids: list[str] | None = None,
        dissociate_folder_ids: list[str] | None = None,
        associate_document_types: list[DocumentType] | None = None,
        dissociate_document_types: list[DocumentType] | None = None,
    ) -> MetadataNamespace:
        """
        Rename a namespace, reorder its keys, or change where it applies.

        `priorities` maps key names to their display priority (higher first).
        Folder and document type associations cannot change in one call.

        Returns:
            MetadataNamespace: The updated namespace.
        """
        return await self._run(
            metadata_ops.update_metadata_namespace(
                namespace,
                display_name=display_name,
                priorities=priorities,
                associate_folder_ids=associate_folder_ids,
                dissociate_folder_ids=dissociate_folder_ids,
                associate_document_types=associate_document_types,
                dissociate_document_types=dissociate_document_types,
            )
        )

    # -------------------------------------------------------------------------
    # METHOD: delete_metadata_namespace
    # -------------------------------------------------------------------------

    async def delete_metadata_namespace(
        self, namespace: str, *, force: bool = False
    ) -> None:
        """
        Delete a namespace, its keys, and their values on every item.

        Egnyte refuses (403) a namespace in use unless `force` is true.
        """
        return await self._run(
            metadata_ops.delete_metadata_namespace(namespace, force=force)
        )

    # -------------------------------------------------------------------------
    # METHOD: add_metadata_key
    # -------------------------------------------------------------------------

    async def add_metadata_key(
        self,
        namespace: str,
        key: str,
        type: MetadataKeyType,
        help_text: str,
        *,
        display_name: str | None = None,
        priority: int | None = None,
        data: list[str] | None = None,
        timezone_independent: bool | None = None,
    ) -> None:
        """
        Add a key to a namespace.

        `help_text` is 20 to 200 characters. `data` lists the allowed values,
        required for `enum` and `multi_value_enum` keys. `timezone_independent`
        makes a `date` key store UTC-midnight dates, and cannot be undone.
        """
        return await self._run(
            metadata_ops.add_metadata_key(
                namespace,
                key,
                type,
                help_text,
                display_name=display_name,
                priority=priority,
                data=data,
                timezone_independent=timezone_independent,
            )
        )

    # -------------------------------------------------------------------------
    # METHOD: update_metadata_key
    # -------------------------------------------------------------------------

    async def update_metadata_key(
        self,
        namespace: str,
        key: str,
        *,
        display_name: str | None = None,
        help_text: str | None = None,
        type: MetadataKeyType | None = None,
        priority: int | None = None,
        data: list[str] | None = None,
        timezone_independent: bool | None = None,
    ) -> None:
        """
        Change a key's definition.

        `type` can only broaden: `date` to `string`, `integer`, or `decimal`;
        `integer` to `string` or `decimal`; `decimal` or `enum` to `string`.
        `data` replaces an `enum` key's values (clearing them on items) and
        appends to a `multi_value_enum` or `labels` key's. `help_text` (20 to
        200 characters) is required when the key has none yet.
        """
        return await self._run(
            metadata_ops.update_metadata_key(
                namespace,
                key,
                display_name=display_name,
                help_text=help_text,
                type=type,
                priority=priority,
                data=data,
                timezone_independent=timezone_independent,
            )
        )

    # -------------------------------------------------------------------------
    # METHOD: delete_metadata_key
    # -------------------------------------------------------------------------

    async def delete_metadata_key(
        self, namespace: str, key: str, *, force: bool = False
    ) -> None:
        """
        Delete a key and its values on every item.

        Egnyte refuses (403) a key in use unless `force` is true.
        """
        return await self._run(
            metadata_ops.delete_metadata_key(namespace, key, force=force)
        )

    # -------------------------------------------------------------------------
    # METHOD: delete_metadata_key_values
    # -------------------------------------------------------------------------

    async def delete_metadata_key_values(
        self, namespace: str, key: str, values: list[str], *, force: bool = False
    ) -> None:
        """
        Remove allowed values from an enum, multi-value enum, or labels key.

        Egnyte refuses (403) values in use on items unless `force` is true.
        """
        return await self._run(
            metadata_ops.delete_metadata_key_values(namespace, key, values, force=force)
        )

    # -------------------------------------------------------------------------
    # METHOD: delete_metadata_values
    # -------------------------------------------------------------------------

    async def delete_metadata_values(
        self, namespace: str, values: Mapping[str, list[str]], *, force: bool = False
    ) -> None:
        """
        Remove allowed values from several keys of a namespace at once.

        `values` maps each key name to the values to remove. Egnyte refuses
        (403) values in use on items unless `force` is true.
        """
        return await self._run(
            metadata_ops.delete_metadata_values(namespace, values, force=force)
        )

    # -------------------------------------------------------------------------
    # METHOD: set_file_metadata
    # -------------------------------------------------------------------------

    async def set_file_metadata(
        self, file_id: str, namespace: str, values: Mapping[str, MetadataValueInput]
    ) -> None:
        """
        Set a namespace's values on a file, by group ID or a version's entry ID.

        Keys not given are left alone, and None removes a value. Enum values
        replace, while `labels` and `multi_value_enum` values are added. A
        `date` is sent as UTC midnight and a `datetime` as its instant (naive
        read as UTC), both in epoch milliseconds.
        """
        return await self._run(
            metadata_ops.set_file_metadata(file_id, namespace, values)
        )

    # -------------------------------------------------------------------------
    # METHOD: get_file_metadata
    # -------------------------------------------------------------------------

    async def get_file_metadata(
        self, file_id: str, namespace: str
    ) -> dict[str, MetadataKeyValue]:
        """
        Get a namespace's values on a file, by group ID or a version's entry ID.

        Returns:
            dict[str, MetadataKeyValue]: The set values by key name; dates are
                epoch milliseconds.
        """
        return await self._run(metadata_ops.get_file_metadata(file_id, namespace))

    # -------------------------------------------------------------------------
    # METHOD: set_folder_metadata
    # -------------------------------------------------------------------------

    async def set_folder_metadata(
        self, folder_id: str, namespace: str, values: Mapping[str, MetadataValueInput]
    ) -> None:
        """
        Set a namespace's values on a folder.

        Keys not given are left alone, and None removes a value. Enum values
        replace, while `labels` and `multi_value_enum` values are added. A
        `date` is sent as UTC midnight and a `datetime` as its instant (naive
        read as UTC), both in epoch milliseconds.
        """
        return await self._run(
            metadata_ops.set_folder_metadata(folder_id, namespace, values)
        )

    # -------------------------------------------------------------------------
    # METHOD: get_folder_metadata
    # -------------------------------------------------------------------------

    async def get_folder_metadata(
        self, folder_id: str, namespace: str
    ) -> dict[str, MetadataKeyValue]:
        """
        Get a namespace's values on a folder.

        Returns:
            dict[str, MetadataKeyValue]: The set values by key name; dates are
                epoch milliseconds.
        """
        return await self._run(metadata_ops.get_folder_metadata(folder_id, namespace))

    # -------------------------------------------------------------------------
    # METHOD: create_webhook
    # -------------------------------------------------------------------------

    async def create_webhook(
        self,
        url: str,
        *,
        event_types: list[WebhookEventType] | None = None,
        paths: list[str] | None = None,
        auth_header: str | None = None,
    ) -> Webhook:
        """
        Register a webhook that posts events to an HTTPS URL.

        `url` needs a CA-signed certificate. `event_types` takes event names
        or wildcards such as `fs:*`; omitted, every event is sent. `paths`
        limits events to up to 100 folders; omitted, the whole domain is
        watched. `auth_header` is sent back as the `Authorization` header of
        each delivery, so the endpoint can check it with
        `verify_webhook_authorization`. Needs the `Egnyte.webhooks` scope.

        Returns:
            Webhook: The new webhook's ID, status, and expiry.
        """
        return await self._run(
            webhook_ops.create_webhook(
                url, event_types=event_types, paths=paths, auth_header=auth_header
            )
        )

    # -------------------------------------------------------------------------
    # METHOD: list_webhooks
    # -------------------------------------------------------------------------

    async def list_webhooks(self) -> list[Webhook]:
        """
        List the webhooks this API client registered in the domain.

        Returns:
            list[Webhook]: Each webhook's ID, status, and expiry.
        """
        return await self._run(webhook_ops.list_webhooks())

    # -------------------------------------------------------------------------
    # METHOD: get_webhook
    # -------------------------------------------------------------------------

    async def get_webhook(self, webhook_id: str) -> WebhookDetails:
        """
        Get a webhook's configuration by ID.

        Returns:
            WebhookDetails: The webhook, with its URL, events, and paths.
        """
        return await self._run(webhook_ops.get_webhook(webhook_id))

    # -------------------------------------------------------------------------
    # METHOD: get_webhook_status
    # -------------------------------------------------------------------------

    async def get_webhook_status(self, webhook_id: str) -> Webhook:
        """
        Get whether a webhook is enabled, and when it expires.

        Returns:
            Webhook: The webhook's ID, status, and expiry.
        """
        return await self._run(webhook_ops.get_webhook_status(webhook_id))

    # -------------------------------------------------------------------------
    # METHOD: set_webhook_status
    # -------------------------------------------------------------------------

    async def set_webhook_status(self, webhook_id: str, enabled: bool) -> Webhook:
        """
        Enable or disable a webhook.

        Egnyte disables a webhook itself once a delivery has failed every
        retry; enable it again here.

        Returns:
            Webhook: The webhook's ID, new status, and expiry.
        """
        return await self._run(webhook_ops.set_webhook_status(webhook_id, enabled))

    # -------------------------------------------------------------------------
    # METHOD: update_webhook
    # -------------------------------------------------------------------------

    async def update_webhook(
        self,
        webhook_id: str,
        url: str,
        *,
        event_types: list[WebhookEventType] | None = None,
        paths: list[str] | None = None,
        auth_header: str | None = None,
        enabled: bool | None = None,
    ) -> None:
        """
        Reconfigure a webhook: its URL, events, paths, header, and status.

        `url` is always required; the other settings are as for
        `create_webhook`, and `enabled` sets the status.
        """
        return await self._run(
            webhook_ops.update_webhook(
                webhook_id,
                url,
                event_types=event_types,
                paths=paths,
                auth_header=auth_header,
                enabled=enabled,
            )
        )

    # -------------------------------------------------------------------------
    # METHOD: delete_webhook
    # -------------------------------------------------------------------------

    async def delete_webhook(self, webhook_id: str) -> None:
        """
        Delete a webhook by ID.
        """
        return await self._run(webhook_ops.delete_webhook(webhook_id))

    # -------------------------------------------------------------------------
    # METHOD: list_users
    # -------------------------------------------------------------------------

    async def list_users(
        self,
        *,
        filter_by_user_name: str | None = None,
        filter_by_email: str | None = None,
        filter_by_external_id: str | None = None,
        start_index: int | None = None,
        count: int | None = None,
    ) -> list[User]:
        """
        List one page of users, optionally filtered by one exact attribute.

        `start_index` is 1-based; `count` is capped at 100 by Egnyte.

        Returns:
            list[User]: The users in the page.
        """
        return await self._run(
            user_ops.list_users(
                filter_by_user_name=filter_by_user_name,
                filter_by_email=filter_by_email,
                filter_by_external_id=filter_by_external_id,
                start_index=start_index,
                count=count,
            )
        )

    # -------------------------------------------------------------------------
    # METHOD: get_user
    # -------------------------------------------------------------------------

    async def get_user(self, user_id: int) -> User:
        """
        Get a user by numeric ID, with the groups they belong to.

        Returns:
            User: The user.
        """
        return await self._run(user_ops.get_user(user_id))

    # -------------------------------------------------------------------------
    # METHOD: create_user
    # -------------------------------------------------------------------------

    async def create_user(
        self,
        user_name: str,
        email: str,
        given_name: str,
        family_name: str,
        *,
        auth_type: AuthType,
        user_type: UserType,
        active: bool = True,
        send_invite: bool | None = None,
        external_id: str | None = None,
        is_service_account: bool | None = None,
        language: str | None = None,
        role: str | None = None,
        idp_user_id: str | None = None,
        user_principal_name: str | None = None,
    ) -> User:
        """
        Create a user.

        Egnyte emails an invitation unless `send_invite` is false, and always
        does for `egnyte` authentication.

        Returns:
            User: The new user.
        """
        return await self._run(
            user_ops.create_user(
                user_name,
                email,
                given_name,
                family_name,
                auth_type=auth_type,
                user_type=user_type,
                active=active,
                send_invite=send_invite,
                external_id=external_id,
                is_service_account=is_service_account,
                language=language,
                role=role,
                idp_user_id=idp_user_id,
                user_principal_name=user_principal_name,
            )
        )

    # -------------------------------------------------------------------------
    # METHOD: update_user
    # -------------------------------------------------------------------------

    async def update_user(
        self,
        user_id: int,
        *,
        email: str | None = None,
        given_name: str | None = None,
        family_name: str | None = None,
        active: bool | None = None,
        auth_type: AuthType | None = None,
        user_type: UserType | None = None,
        send_invite: bool | None = None,
        language: str | None = None,
        role: str | None = None,
        idp_user_id: str | None = None,
        user_principal_name: str | None = None,
    ) -> User:
        """
        Update a user; only the fields given change.

        Returns:
            User: The updated user.
        """
        return await self._run(
            user_ops.update_user(
                user_id,
                email=email,
                given_name=given_name,
                family_name=family_name,
                active=active,
                auth_type=auth_type,
                user_type=user_type,
                send_invite=send_invite,
                language=language,
                role=role,
                idp_user_id=idp_user_id,
                user_principal_name=user_principal_name,
            )
        )

    # -------------------------------------------------------------------------
    # METHOD: delete_user
    # -------------------------------------------------------------------------

    async def delete_user(self, user_id: int) -> None:
        """
        Delete a user by numeric ID.
        """
        return await self._run(user_ops.delete_user(user_id))

    # -------------------------------------------------------------------------
    # METHOD: list_groups
    # -------------------------------------------------------------------------

    async def list_groups(
        self,
        *,
        filter_by_name: str | None = None,
        filter_by_name_contains: str | None = None,
        filter_by_name_starts_with: str | None = None,
        start_index: int | None = None,
        count: int | None = None,
    ) -> list[GroupSummary]:
        """
        List one page of custom groups, optionally filtered by name.

        The built-in "All ..." groups are not listed. `start_index` is
        1-based; `count` is capped at 100 by Egnyte.

        Returns:
            list[GroupSummary]: The groups in the page, without members.
        """
        return await self._run(
            group_ops.list_groups(
                filter_by_name=filter_by_name,
                filter_by_name_contains=filter_by_name_contains,
                filter_by_name_starts_with=filter_by_name_starts_with,
                start_index=start_index,
                count=count,
            )
        )

    # -------------------------------------------------------------------------
    # METHOD: get_group
    # -------------------------------------------------------------------------

    async def get_group(self, group_id: str) -> Group:
        """
        Get a group by ID, with its members and owners.

        Returns:
            Group: The group.
        """
        return await self._run(group_ops.get_group(group_id))

    # -------------------------------------------------------------------------
    # METHOD: create_group
    # -------------------------------------------------------------------------

    async def create_group(
        self,
        display_name: str,
        member_ids: list[int],
        *,
        owners: list[str] | None = None,
    ) -> Group:
        """
        Create a group. Egnyte requires at least one member.

        `owners` are usernames; the caller owns the group when omitted.

        Returns:
            Group: The new group.
        """
        return await self._run(
            group_ops.create_group(display_name, member_ids, owners=owners)
        )

    # -------------------------------------------------------------------------
    # METHOD: replace_group
    # -------------------------------------------------------------------------

    async def replace_group(
        self,
        group_id: str,
        display_name: str,
        member_ids: list[int],
        *,
        owners: list[str] | None = None,
    ) -> Group:
        """
        Overwrite a group's name and full membership.

        Members not in `member_ids` are removed. `owners` adds owners.

        Returns:
            Group: The updated group.
        """
        return await self._run(
            group_ops.replace_group(group_id, display_name, member_ids, owners=owners)
        )

    # -------------------------------------------------------------------------
    # METHOD: update_group
    # -------------------------------------------------------------------------

    async def update_group(
        self,
        group_id: str,
        *,
        display_name: str | None = None,
        add_member_ids: list[int] | None = None,
        remove_member_ids: list[int] | None = None,
        add_owners: list[str] | None = None,
    ) -> Group:
        """
        Rename a group, or add and remove members and owners, leaving the rest.

        Returns:
            Group: The updated group.
        """
        return await self._run(
            group_ops.update_group(
                group_id,
                display_name=display_name,
                add_member_ids=add_member_ids,
                remove_member_ids=remove_member_ids,
                add_owners=add_owners,
            )
        )

    # -------------------------------------------------------------------------
    # METHOD: delete_group
    # -------------------------------------------------------------------------

    async def delete_group(self, group_id: str) -> None:
        """
        Delete a group by ID.
        """
        return await self._run(group_ops.delete_group(group_id))

    # -------------------------------------------------------------------------
    # METHOD: create_login_audit_report
    # -------------------------------------------------------------------------

    async def create_login_audit_report(
        self,
        start_date: date | datetime,
        end_date: date | datetime,
        *,
        events: list[LoginAuditEvent],
        format: AuditReportFormat = "json",
        access_points: list[LoginAccessPoint] | None = None,
        users: list[str] | None = None,
        suppress_emails: bool | None = None,
    ) -> AuditJob:
        """
        Start a report of logins, logouts, lockouts, password resets, and failed attempts.

        `events` picks which of those to include (at least one).
        `access_points` and `users` narrow the report; all are included when
        omitted. Dates are `date` or `datetime` (naive means UTC), and
        `end_date` must be after `start_date`. `suppress_emails` skips the
        completion email.

        Returns:
            AuditJob: The job to poll with `get_audit_job`.
        """
        return await self._run(
            audit_ops.create_login_audit_report(
                start_date,
                end_date,
                events=events,
                format=format,
                access_points=access_points,
                users=users,
                suppress_emails=suppress_emails,
            )
        )

    # -------------------------------------------------------------------------
    # METHOD: create_file_audit_report
    # -------------------------------------------------------------------------

    async def create_file_audit_report(
        self,
        start_date: date | datetime,
        end_date: date | datetime,
        *,
        folders: list[str] | None = None,
        file: str | None = None,
        format: AuditReportFormat = "json",
        users: list[str] | None = None,
        transaction_types: list[FileAuditTransaction] | None = None,
        suppress_emails: bool | None = None,
    ) -> AuditJob:
        """
        Start a report of file and folder actions: uploads, downloads, moves, links, and so on.

        Needs `folders` (absolute paths) or `file`, a name pattern that may
        use the `*` wildcard but not start with it. `users` and
        `transaction_types` narrow the report; all are included when omitted.
        The time of day in either date is ignored, and `end_date` must be
        after `start_date`.

        Returns:
            AuditJob: The job to poll with `get_audit_job`.
        """
        return await self._run(
            audit_ops.create_file_audit_report(
                start_date,
                end_date,
                folders=folders,
                file=file,
                format=format,
                users=users,
                transaction_types=transaction_types,
                suppress_emails=suppress_emails,
            )
        )

    # -------------------------------------------------------------------------
    # METHOD: create_permissions_audit_report
    # -------------------------------------------------------------------------

    async def create_permissions_audit_report(
        self,
        start_date: date | datetime,
        end_date: date | datetime,
        *,
        format: AuditReportFormat = "json",
        folders: list[str] | None = None,
        assigners: list[str] | None = None,
        assignee_users: list[str] | None = None,
        assignee_groups: list[str] | None = None,
        suppress_emails: bool | None = None,
    ) -> AuditJob:
        """
        Start a report of folder permission changes.

        `folders` and `assigners` narrow the report; all are included when
        omitted. Give `assignee_users`, `assignee_groups`, or both: without
        `assignee_users` only group grants are reported, and without
        `assignee_groups` only user grants. The time of day in either date is
        ignored, and `end_date` must be after `start_date`.

        Returns:
            AuditJob: The job to poll with `get_audit_job`.
        """
        return await self._run(
            audit_ops.create_permissions_audit_report(
                start_date,
                end_date,
                format=format,
                folders=folders,
                assigners=assigners,
                assignee_users=assignee_users,
                assignee_groups=assignee_groups,
                suppress_emails=suppress_emails,
            )
        )

    # -------------------------------------------------------------------------
    # METHOD: create_user_audit_report
    # -------------------------------------------------------------------------

    async def create_user_audit_report(
        self,
        start_date: date | datetime,
        end_date: date | datetime,
        *,
        format: AuditReportFormat = "json",
        action_types: list[UserAuditAction] | None = None,
        performed_by: list[str] | None = None,
        subjects: list[str] | None = None,
        include_system_actions: bool | None = None,
    ) -> AuditJob:
        """
        Start a report of user account changes: creates, updates, disables, deletes, and passwords.

        `action_types`, `performed_by` (who made the change), and `subjects`
        (who was changed) narrow the report; all are included when omitted.
        System-initiated actions are left out unless `include_system_actions`.
        The time of day in either date is ignored, and `end_date` must be
        after `start_date`.

        Returns:
            AuditJob: The job to poll with `get_audit_job`.
        """
        return await self._run(
            audit_ops.create_user_audit_report(
                start_date,
                end_date,
                format=format,
                action_types=action_types,
                performed_by=performed_by,
                subjects=subjects,
                include_system_actions=include_system_actions,
            )
        )

    # -------------------------------------------------------------------------
    # METHOD: create_group_audit_report
    # -------------------------------------------------------------------------

    async def create_group_audit_report(
        self,
        start_date: date | datetime,
        end_date: date | datetime,
        *,
        format: AuditReportFormat = "json",
        action_types: list[GroupAuditAction] | None = None,
        users: list[str] | None = None,
        groups: list[str] | None = None,
        include_system_actions: bool | None = None,
    ) -> AuditJob:
        """
        Start a report of group changes: creates, membership changes, renames, and deletes.

        `action_types`, `users` (who made the change), and `groups` (names,
        matched case-insensitively) narrow the report; all are included when
        omitted. System-initiated actions are left out unless
        `include_system_actions`. The time of day in either date is ignored,
        and `end_date` must be after `start_date`.

        Returns:
            AuditJob: The job to poll with `get_audit_job`.
        """
        return await self._run(
            audit_ops.create_group_audit_report(
                start_date,
                end_date,
                format=format,
                action_types=action_types,
                users=users,
                groups=groups,
                include_system_actions=include_system_actions,
            )
        )

    # -------------------------------------------------------------------------
    # METHOD: create_workgroup_settings_audit_report
    # -------------------------------------------------------------------------

    async def create_workgroup_settings_audit_report(
        self,
        start_date: date | datetime,
        end_date: date | datetime,
        *,
        format: AuditReportFormat = "json",
        users: list[str] | None = None,
    ) -> AuditJob:
        """
        Start a report of domain configuration setting changes.

        `users` narrows the report to changes those users made. The time of
        day in either date is ignored, and `end_date` must be after
        `start_date`.

        Returns:
            AuditJob: The job to poll with `get_audit_job`.
        """
        return await self._run(
            audit_ops.create_workgroup_settings_audit_report(
                start_date, end_date, format=format, users=users
            )
        )

    # -------------------------------------------------------------------------
    # METHOD: create_workflow_audit_report
    # -------------------------------------------------------------------------

    async def create_workflow_audit_report(
        self,
        start_date: date | datetime,
        end_date: date | datetime,
        *,
        format: AuditReportFormat = "json",
        users: list[str] | None = None,
        file: str | None = None,
        workflow_actions: list[WorkflowAuditAction] | None = None,
        workflow_types: list[WorkflowAuditType] | None = None,
        suppress_emails: bool | None = None,
    ) -> AuditJob:
        """
        Start a report of workflow activity: workflows, steps, tasks, and webhooks.

        `users`, `workflow_actions`, and `workflow_types` narrow the report;
        all are included when omitted. `file` matches workflow names and may
        use the `*` wildcard but not start with it. `end_date` must be after
        `start_date`.

        Returns:
            AuditJob: The job to poll with `get_audit_job`.
        """
        return await self._run(
            audit_ops.create_workflow_audit_report(
                start_date,
                end_date,
                format=format,
                users=users,
                file=file,
                workflow_actions=workflow_actions,
                workflow_types=workflow_types,
                suppress_emails=suppress_emails,
            )
        )

    # -------------------------------------------------------------------------
    # METHOD: create_workflow_template_audit_report
    # -------------------------------------------------------------------------

    async def create_workflow_template_audit_report(
        self,
        start_date: date | datetime,
        end_date: date | datetime,
        *,
        format: AuditReportFormat = "json",
        users: list[str] | None = None,
        workflow_template_actions: list[WorkflowTemplateAuditAction] | None = None,
        suppress_emails: bool | None = None,
    ) -> AuditJob:
        """
        Start a report of workflow template changes.

        `users` and `workflow_template_actions` narrow the report; all are
        included when omitted. `end_date` must be after `start_date`.

        Returns:
            AuditJob: The job to poll with `get_audit_job`.
        """
        return await self._run(
            audit_ops.create_workflow_template_audit_report(
                start_date,
                end_date,
                format=format,
                users=users,
                workflow_template_actions=workflow_template_actions,
                suppress_emails=suppress_emails,
            )
        )

    # -------------------------------------------------------------------------
    # METHOD: create_quality_docs_audit_report
    # -------------------------------------------------------------------------

    async def create_quality_docs_audit_report(
        self,
        start_date: date | datetime,
        end_date: date | datetime,
        *,
        format: AuditReportFormat = "json",
        users: list[str] | None = None,
        quality_document_id: str | None = None,
        quality_docs_categories: list[QualityDocsCategoryFilter] | None = None,
        quality_docs_actions: list[QualityDocsAuditAction] | None = None,
        quality_docs_statuses: list[QualityDocsStatus] | None = None,
        suppress_emails: bool | None = None,
    ) -> AuditJob:
        """
        Start a report of Quality Docs activity: documents, drafts, and training.

        `users`, `quality_document_id`, `quality_docs_categories`,
        `quality_docs_actions`, and `quality_docs_statuses` narrow the report;
        all are included when omitted. `end_date` must be after `start_date`.

        Returns:
            AuditJob: The job to poll with `get_audit_job`.
        """
        return await self._run(
            audit_ops.create_quality_docs_audit_report(
                start_date,
                end_date,
                format=format,
                users=users,
                quality_document_id=quality_document_id,
                quality_docs_categories=quality_docs_categories,
                quality_docs_actions=quality_docs_actions,
                quality_docs_statuses=quality_docs_statuses,
                suppress_emails=suppress_emails,
            )
        )

    # -------------------------------------------------------------------------
    # METHOD: create_quality_docs_categories_audit_report
    # -------------------------------------------------------------------------

    async def create_quality_docs_categories_audit_report(
        self,
        start_date: date | datetime,
        end_date: date | datetime,
        *,
        format: AuditReportFormat = "json",
        users: list[str] | None = None,
        quality_docs_categories: list[QualityDocsCategoryFilter] | None = None,
        quality_docs_categories_actions: list[QualityDocsCategoryAuditAction]
        | None = None,
        suppress_emails: bool | None = None,
    ) -> AuditJob:
        """
        Start a report of Quality Docs category and subcategory changes.

        `users`, `quality_docs_categories`, and
        `quality_docs_categories_actions` narrow the report; all are included
        when omitted. `end_date` must be after `start_date`.

        Returns:
            AuditJob: The job to poll with `get_audit_job`.
        """
        return await self._run(
            audit_ops.create_quality_docs_categories_audit_report(
                start_date,
                end_date,
                format=format,
                users=users,
                quality_docs_categories=quality_docs_categories,
                quality_docs_categories_actions=quality_docs_categories_actions,
                suppress_emails=suppress_emails,
            )
        )

    # -------------------------------------------------------------------------
    # METHOD: create_quality_docs_courses_audit_report
    # -------------------------------------------------------------------------

    async def create_quality_docs_courses_audit_report(
        self,
        start_date: date | datetime,
        end_date: date | datetime,
        *,
        format: AuditReportFormat = "json",
        users: list[str] | None = None,
        quality_docs_courses_ids: list[str] | None = None,
        quality_docs_courses_actions: list[QualityDocsCourseAuditAction] | None = None,
        quality_docs_courses_parameters: list[QualityDocsCourseParameter] | None = None,
        suppress_emails: bool | None = None,
    ) -> AuditJob:
        """
        Start a report of Quality Docs training course changes.

        `users`, `quality_docs_courses_ids`, `quality_docs_courses_actions`,
        and `quality_docs_courses_parameters` narrow the report; all are
        included when omitted. `end_date` must be after `start_date`.

        Returns:
            AuditJob: The job to poll with `get_audit_job`.
        """
        return await self._run(
            audit_ops.create_quality_docs_courses_audit_report(
                start_date,
                end_date,
                format=format,
                users=users,
                quality_docs_courses_ids=quality_docs_courses_ids,
                quality_docs_courses_actions=quality_docs_courses_actions,
                quality_docs_courses_parameters=quality_docs_courses_parameters,
                suppress_emails=suppress_emails,
            )
        )

    # -------------------------------------------------------------------------
    # METHOD: create_etmf_audit_report
    # -------------------------------------------------------------------------

    async def create_etmf_audit_report(
        self,
        start_date: date | datetime,
        end_date: date | datetime,
        *,
        format: AuditReportFormat = "json",
        users: list[str] | None = None,
        etmf_actions: list[EtmfAuditAction] | None = None,
        etmf_study_ids: list[str] | None = None,
        etmf_artifact_number: str | None = None,
        suppress_emails: bool | None = None,
    ) -> AuditJob:
        """
        Start a report of eTMF activity: studies, trials, countries, sites, documents, and artifacts.

        `users`, `etmf_actions`, `etmf_study_ids`, and `etmf_artifact_number`
        narrow the report; all are included when omitted. `end_date` must be
        after `start_date`.

        Returns:
            AuditJob: The job to poll with `get_audit_job`.
        """
        return await self._run(
            audit_ops.create_etmf_audit_report(
                start_date,
                end_date,
                format=format,
                users=users,
                etmf_actions=etmf_actions,
                etmf_study_ids=etmf_study_ids,
                etmf_artifact_number=etmf_artifact_number,
                suppress_emails=suppress_emails,
            )
        )

    # -------------------------------------------------------------------------
    # METHOD: create_snapshot_restore_audit_report
    # -------------------------------------------------------------------------

    async def create_snapshot_restore_audit_report(
        self,
        start_date: date | datetime,
        end_date: date | datetime,
        *,
        format: AuditReportFormat = "json",
        users: list[str] | None = None,
        include_system_actions: bool | None = None,
        suppress_emails: bool | None = None,
    ) -> AuditJob:
        """
        Start a report of snapshot mounts, unmounts, previews, and restores.

        `users` narrows the report. System-initiated actions are included
        unless `include_system_actions` is false. `end_date` must be after
        `start_date`.

        Returns:
            AuditJob: The job to poll with `get_audit_job`.
        """
        return await self._run(
            audit_ops.create_snapshot_restore_audit_report(
                start_date,
                end_date,
                format=format,
                users=users,
                include_system_actions=include_system_actions,
                suppress_emails=suppress_emails,
            )
        )

    # -------------------------------------------------------------------------
    # METHOD: create_upload_requests_audit_report
    # -------------------------------------------------------------------------

    async def create_upload_requests_audit_report(
        self,
        start_date: date | datetime,
        end_date: date | datetime,
        *,
        format: AuditReportFormat = "json",
        users: list[str] | None = None,
        upload_requests_actions: list[UploadRequestAuditAction] | None = None,
        suppress_emails: bool | None = None,
    ) -> AuditJob:
        """
        Start a report of upload request activity: requests, uploads, submissions, and reviews.

        `users` and `upload_requests_actions` narrow the report; all are
        included when omitted. `end_date` must be after `start_date`.

        Returns:
            AuditJob: The job to poll with `get_audit_job`.
        """
        return await self._run(
            audit_ops.create_upload_requests_audit_report(
                start_date,
                end_date,
                format=format,
                users=users,
                upload_requests_actions=upload_requests_actions,
                suppress_emails=suppress_emails,
            )
        )

    # -------------------------------------------------------------------------
    # METHOD: get_audit_job
    # -------------------------------------------------------------------------

    async def get_audit_job(self, job_id: str) -> AuditJobStatus:
        """
        Check whether a report job has finished, without fetching the report.

        Egnyte asks that a job be polled no more than once every 2 minutes.
        A finished job's report has the job's ID, so `report_id` is set once
        `is_complete`. `report_type` and `location` are read from the
        redirect Egnyte answers a finished job with; the redirect is not
        followed.

        Returns:
            AuditJobStatus: running, or completed with the report to fetch.
        """
        return await self._run(audit_ops.get_audit_job(job_id))

    # -------------------------------------------------------------------------
    # METHOD: get_audit_report
    # -------------------------------------------------------------------------

    async def get_audit_report(
        self,
        report_type: AuditReportType,
        report_id: str,
        *,
        offset: int | None = None,
        count: int | None = None,
    ) -> AuditReport:
        """
        Read a finished JSON report, whole or a page of rows at a time.

        `offset` (0-based) and `count` page through the rows; without them
        the whole report arrives. A CSV report is read with
        `download_audit_report` instead.

        Returns:
            AuditReport: The rows, with the report's total row count.
        """
        return await self._run(
            audit_ops.get_audit_report(
                report_type, report_id, offset=offset, count=count
            )
        )

    # -------------------------------------------------------------------------
    # METHOD: download_audit_report
    # -------------------------------------------------------------------------

    async def download_audit_report(
        self, report_type: AuditReportType, report_id: str
    ) -> bytes:
        """
        Download a finished report as Egnyte serves it.

        A CSV report arrives in the layout the Egnyte audit UI downloads, and
        a JSON report as its raw JSON.

        Returns:
            bytes: The report body.
        """
        return await self._run(audit_ops.download_audit_report(report_type, report_id))

    # -------------------------------------------------------------------------
    # METHOD: delete_audit_report
    # -------------------------------------------------------------------------

    async def delete_audit_report(
        self, report_type: AuditReportType, report_id: str
    ) -> None:
        """
        Delete a report by type and ID.
        """
        return await self._run(audit_ops.delete_audit_report(report_type, report_id))

    # -------------------------------------------------------------------------
    # METHOD: stream_audit_events
    # -------------------------------------------------------------------------

    async def stream_audit_events(
        self,
        *,
        start_date: date | datetime | None = None,
        next_cursor: str | None = None,
        audit_types: list[AuditStreamType] | None = None,
        end_date: date | datetime | None = None,
    ) -> AuditEventPage:
        """
        Read one page of the v2 audit event stream.

        Start with `start_date`, which must be within the last 7 days: older
        events are not available here and need a v1 report. Continue with the
        page's `next_cursor`, passing it instead of `start_date` (exactly one
        of the two is given). While `more_events` is true more events are
        ready; after that, polling with the latest cursor picks up new ones.
        Each page holds up to 5,000 events from at most 30 minutes, so pages
        over quiet periods are empty while `more_events` is still true: keep
        following the cursor. Cursors expire after 7 days. `audit_types` filters by event type (default
        `ANY`). Egnyte allows 10 calls a minute and 100 an hour.

        Returns:
            AuditEventPage: The events, the next cursor, and whether more are ready.
        """
        return await self._run(
            audit_ops.stream_audit_events(
                start_date=start_date,
                next_cursor=next_cursor,
                audit_types=audit_types,
                end_date=end_date,
            )
        )
