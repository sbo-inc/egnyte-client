import hashlib
from collections.abc import Callable, Iterator
from datetime import datetime
from email.utils import format_datetime
from typing import BinaryIO, Literal

import httpx
from pydantic import BaseModel, TypeAdapter

from egnyte_client.operations.generic import (
    Operation,
    as_utc,
    content,
    empty,
    encode_id,
    encode_path,
    model,
    normalize_path,
    query,
)
from egnyte_client.schemas.filesystem import (
    CreatedFolder,
    DeletedItem,
    EmailPreferences,
    File,
    FileLock,
    Folder,
    FolderOptionsMode,
    FolderOptionsRequest,
    FolderStats,
    InheritanceRule,
    ItemReference,
    LockRequest,
    MoveDeleteRestriction,
    PublicLinks,
    TransferByIdRequest,
    TransferRequest,
    UnlockRequest,
    UploadedChunk,
    UploadedFile,
)

type SortBy = Literal["name", "last_modified", "uploaded_by"]
type SortDirection = Literal["ascending", "descending"]
type Permissions = Literal["keep_original", "inherit_from_parent"]
type ItemKind = Literal["file", "folder"]

# Chunked upload bounds, in bytes: every chunk but the last is exactly the
# chunk size, which Egnyte requires to lie between 10 MiB and 1 GiB.
MIN_CHUNK_SIZE = 10 * 1024 * 1024
MAX_CHUNK_SIZE = 1024 * 1024 * 1024
DEFAULT_CHUNK_SIZE = 100 * 1024 * 1024

# Version prefix of the composite whole-file checksum a chunked upload ends with.
CHUNKED_CHECKSUM_VERSION = 2

# Longest lock Egnyte grants, in seconds (seven days).
MAX_LOCK_TIMEOUT = 604800

# Longest folder description Egnyte accepts, in characters.
MAX_FOLDER_DESCRIPTION = 200

# =============================================================================
# CLASS: AddFolderRequest
# =============================================================================


class AddFolderRequest(BaseModel):
    action: Literal["add_folder"] = "add_folder"


# =============================================================================
# FUNCTION: item
# =============================================================================


_ITEM: TypeAdapter[File | Folder] = TypeAdapter(File | Folder)


def item(response: httpx.Response) -> File | Folder:
    """
    Parse file system metadata into a `File` or a `Folder`.

    The two are told apart by `is_folder`, which each model pins to a literal.

    Returns:
        File | Folder: The parsed item.
    """
    return _ITEM.validate_json(response.content)


def _expect[T: File | Folder](cls: type[T]) -> Callable[[httpx.Response], T]:
    """
    Parse metadata as the expected kind, raising if the path is the other one.

    Returns:
        Callable[[httpx.Response], T]: The parser for this kind.
    """

    def parse(response: httpx.Response) -> T:
        parsed = item(response)
        if not isinstance(parsed, cls):
            kind = "folder" if isinstance(parsed, Folder) else "file"
            raise ValueError(f"{parsed.path} is a {kind}, not a {cls.__name__.lower()}")
        return parsed

    return parse


# -----------------------------------------------------------------------------
# OPERATION: get_item
# -----------------------------------------------------------------------------


def get_item(path: str) -> Operation[File | Folder]:
    """
    Build the metadata read for a path of either kind.

    Returns:
        Operation[File | Folder]: The get item operation.
    """
    return Operation(method="GET", path=f"/v1/fs{encode_path(path)}", parse=item)


# -----------------------------------------------------------------------------
# OPERATION: get_folder
# -----------------------------------------------------------------------------


def _folder_query(
    count: int | None,
    offset: int | None,
    sort_by: SortBy | None,
    sort_direction: SortDirection | None,
) -> dict[str, str | int | bool | None]:
    return query(
        list_content=True,
        count=count,
        offset=offset,
        sort_by=sort_by,
        sort_direction=sort_direction,
    )


def get_folder(
    path: str,
    *,
    count: int | None = None,
    offset: int | None = None,
    sort_by: SortBy | None = None,
    sort_direction: SortDirection | None = None,
) -> Operation[Folder]:
    """
    Build the folder listing by path.

    Returns:
        Operation[Folder]: The get folder operation.
    """
    return Operation(
        method="GET",
        path=f"/v1/fs{encode_path(path)}",
        params=_folder_query(count, offset, sort_by, sort_direction),
        parse=_expect(Folder),
    )


# -----------------------------------------------------------------------------
# OPERATION: get_folder_by_id
# -----------------------------------------------------------------------------


def get_folder_by_id(
    folder_id: str,
    *,
    count: int | None = None,
    offset: int | None = None,
    sort_by: SortBy | None = None,
    sort_direction: SortDirection | None = None,
) -> Operation[Folder]:
    """
    Build the folder listing by folder ID.

    Returns:
        Operation[Folder]: The get folder by ID operation.
    """
    return Operation(
        method="GET",
        path=f"/v1/fs/ids/folder/{encode_id(folder_id)}",
        params=_folder_query(count, offset, sort_by, sort_direction),
        parse=_expect(Folder),
    )


# -----------------------------------------------------------------------------
# OPERATION: get_file
# -----------------------------------------------------------------------------


def get_file(path: str, *, include_versions: bool = False) -> Operation[File]:
    """
    Build the file metadata read by path.

    Returns:
        Operation[File]: The get file operation.
    """
    return Operation(
        method="GET",
        path=f"/v1/fs{encode_path(path)}",
        params=query(list_content=include_versions or None),
        parse=_expect(File),
    )


# -----------------------------------------------------------------------------
# OPERATION: get_file_by_id
# -----------------------------------------------------------------------------


def get_file_by_id(group_id: str, *, include_versions: bool = False) -> Operation[File]:
    """
    Build the file metadata read by group ID.

    Returns:
        Operation[File]: The get file by ID operation.
    """
    return Operation(
        method="GET",
        path=f"/v1/fs/ids/file/{encode_id(group_id)}",
        params=query(list_content=include_versions or None),
        parse=_expect(File),
    )


# -----------------------------------------------------------------------------
# OPERATION: create_folder
# -----------------------------------------------------------------------------


def create_folder(path: str) -> Operation[CreatedFolder]:
    """
    Build the folder create.

    Returns:
        Operation[CreatedFolder]: The create folder operation.
    """
    return Operation(
        method="POST",
        path=f"/v1/fs{encode_path(path)}",
        body=AddFolderRequest(),
        parse=model(CreatedFolder),
    )


# -----------------------------------------------------------------------------
# OPERATION: upload_file
# -----------------------------------------------------------------------------


def _http_date(value: datetime) -> str:
    """
    Format a datetime as the RFC 1123 `Last-Modified` header; naive means UTC.

    Returns:
        str: A stamp such as `Fri, 02 Jan 2026 03:04:05 GMT`.
    """
    return format_datetime(as_utc(value), usegmt=True)


def upload_file(
    path: str,
    data: bytes,
    *,
    last_modified: datetime | None = None,
) -> Operation[UploadedFile]:
    """
    Build the single-request upload, which creates a file or adds a version.

    The SHA-512 of `data` rides along in `X-Sha512-Checksum`, so Egnyte rejects
    the upload rather than store content that was damaged in transit.

    Returns:
        Operation[UploadedFile]: The upload file operation.
    """
    headers = {
        "Content-Type": "application/octet-stream",
        "X-Sha512-Checksum": hashlib.sha512(data).hexdigest(),
    }
    if last_modified is not None:
        headers["Last-Modified"] = _http_date(last_modified)

    return Operation(
        method="POST",
        path=f"/v1/fs-content{encode_path(path)}",
        content=data,
        headers=headers,
        parse=model(UploadedFile),
    )


# -----------------------------------------------------------------------------
# OPERATION: download_file
# -----------------------------------------------------------------------------


def download_file(path: str, *, entry_id: str | None = None) -> Operation[bytes]:
    """
    Build the download by path; `entry_id` picks a version other than the current.

    Returns:
        Operation[bytes]: The download file operation.
    """
    return Operation(
        method="GET",
        path=f"/v1/fs-content{encode_path(path)}",
        params=query(entry_id=entry_id),
        parse=content,
    )


# -----------------------------------------------------------------------------
# OPERATION: download_file_by_id
# -----------------------------------------------------------------------------


def download_file_by_id(
    group_id: str, *, entry_id: str | None = None
) -> Operation[bytes]:
    """
    Build the download by group ID; `entry_id` picks a version other than the current.

    Returns:
        Operation[bytes]: The download file by ID operation.
    """
    return Operation(
        method="GET",
        path=f"/v1/fs-content/ids/file/{encode_id(group_id)}",
        params=query(entry_id=entry_id),
        parse=content,
    )


# -----------------------------------------------------------------------------
# OPERATION: transfer_item
# -----------------------------------------------------------------------------


def transfer_item(
    action: Literal["copy", "move"],
    path: str,
    destination: str,
    *,
    permissions: Permissions | None = None,
) -> Operation[ItemReference]:
    """
    Build a copy or move of a file or folder to an absolute destination path.

    Returns:
        Operation[ItemReference]: The copy or move operation.
    """
    return Operation(
        method="POST",
        path=f"/v1/fs{encode_path(path)}",
        body=TransferRequest(
            action=action,
            destination=normalize_path(destination),
            permissions=permissions,
        ),
        parse=model(ItemReference),
    )


# -----------------------------------------------------------------------------
# OPERATION: delete_item
# -----------------------------------------------------------------------------


def delete_item(path: str, *, entry_id: str | None = None) -> Operation[DeletedItem]:
    """
    Build the delete of a file or folder; `entry_id` deletes one file version.

    Returns:
        Operation[DeletedItem]: The delete operation.
    """
    return Operation(
        method="DELETE",
        path=f"/v1/fs{encode_path(path)}",
        params=query(entry_id=entry_id),
        parse=_deleted,
    )


def _deleted(response: httpx.Response) -> DeletedItem:
    if not response.content.strip():
        return DeletedItem()
    return DeletedItem.model_validate_json(response.content)


# -----------------------------------------------------------------------------
# OPERATION: transfer_item_by_id
# -----------------------------------------------------------------------------


def transfer_item_by_id(
    action: Literal["copy", "move"],
    kind: ItemKind,
    item_id: str,
    destination_folder_id: str,
    *,
    name: str | None = None,
    permissions: Permissions | None = None,
    folder_options_mode: FolderOptionsMode | None = None,
) -> Operation[ItemReference]:
    """
    Build a copy or move of a file (by group ID) or folder (by folder ID).

    The item lands in the destination folder, under `name` when given.

    Returns:
        Operation[ItemReference]: The copy or move by ID operation.
    """
    return Operation(
        method="POST",
        path=f"/v1/fs/ids/{kind}/{encode_id(item_id)}",
        body=TransferByIdRequest(
            action=action,
            destination_id=destination_folder_id,
            name=name,
            permissions=permissions,
            folder_options_mode=folder_options_mode,
        ),
        parse=model(ItemReference),
    )


# -----------------------------------------------------------------------------
# OPERATION: delete_item_by_id
# -----------------------------------------------------------------------------


def delete_item_by_id(
    kind: ItemKind, item_id: str, *, entry_id: str | None = None
) -> Operation[DeletedItem]:
    """
    Build the delete of a file (by group ID) or folder (by folder ID).

    `entry_id` deletes one file version.

    Returns:
        Operation[DeletedItem]: The delete by ID operation.
    """
    return Operation(
        method="DELETE",
        path=f"/v1/fs/ids/{kind}/{encode_id(item_id)}",
        params=query(entry_id=entry_id),
        parse=_deleted,
    )


# -----------------------------------------------------------------------------
# OPERATION: get_folder_stats
# -----------------------------------------------------------------------------


def get_folder_stats(folder_id: str) -> Operation[FolderStats]:
    """
    Build the folder statistics read.

    Returns:
        Operation[FolderStats]: The get folder stats operation.
    """
    return Operation(
        method="GET",
        path=f"/v1/fs/ids/folder/{encode_id(folder_id)}/stats",
        parse=model(FolderStats),
    )


# -----------------------------------------------------------------------------
# OPERATION: lock_file
# -----------------------------------------------------------------------------


def _file_target(path: str | None, group_id: str | None) -> str:
    """
    Address a file under `/v1/fs` by group ID when given, otherwise by path.

    Returns:
        str: The operation path.
    """
    if group_id is not None:
        return f"/v1/fs/ids/file/{encode_id(group_id)}"
    return f"/v1/fs{encode_path(path or '')}"


def lock_file(
    *,
    path: str | None = None,
    group_id: str | None = None,
    lock_token: str | None = None,
    lock_timeout: int | None = None,
    collaboration: str | None = None,
) -> Operation[FileLock]:
    """
    Build a file lock, addressed by path or by group ID.

    Returns:
        Operation[FileLock]: The lock file operation.
    """
    if lock_timeout is not None and not 0 < lock_timeout <= MAX_LOCK_TIMEOUT:
        raise ValueError(
            f"lock_timeout must be between 1 and {MAX_LOCK_TIMEOUT} seconds"
        )

    return Operation(
        method="POST",
        path=_file_target(path, group_id),
        body=LockRequest(
            lock_token=lock_token,
            lock_timeout=lock_timeout,
            collaboration=collaboration,
        ),
        parse=model(FileLock),
    )


# -----------------------------------------------------------------------------
# OPERATION: unlock_file
# -----------------------------------------------------------------------------


def unlock_file(
    lock_token: str, *, path: str | None = None, group_id: str | None = None
) -> Operation[None]:
    """
    Build a file unlock, addressed by path or by group ID.

    Returns:
        Operation[None]: The unlock file operation.
    """
    return Operation(
        method="POST",
        path=_file_target(path, group_id),
        body=UnlockRequest(lock_token=lock_token),
        parse=empty,
    )


# -----------------------------------------------------------------------------
# OPERATION: update_folder_options
# -----------------------------------------------------------------------------


def update_folder_options(
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
) -> Operation[Folder]:
    """
    Build the folder options update.

    Returns:
        Operation[Folder]: The update folder options operation.
    """
    if description is not None and len(description) > MAX_FOLDER_DESCRIPTION:
        raise ValueError(
            f"A folder description is at most {MAX_FOLDER_DESCRIPTION} characters"
        )

    email_preferences = None
    if notify_content_updates is not None or notify_content_accessed is not None:
        email_preferences = EmailPreferences(
            content_updates=notify_content_updates,
            content_accessed=notify_content_accessed,
        )
    request = FolderOptionsRequest(
        folder_description=description,
        allow_links=allow_links,
        allow_upload_links=allow_upload_links,
        public_links=public_links,
        restrict_move_delete=restrict_move_delete,
        move_delete_folder_restriction=move_delete_folder_restriction,
        inheritance_rule=inheritance_rule,
        email_preferences=email_preferences,
    )
    if not request.model_dump(exclude_none=True):
        raise ValueError("update_folder_options needs at least one option")

    return Operation(
        method="PATCH",
        path=f"/v1/fs{encode_path(path)}",
        body=request,
        parse=_expect(Folder),
    )


# -----------------------------------------------------------------------------
# OPERATION: chunked upload
# -----------------------------------------------------------------------------


def _read_exactly(stream: BinaryIO, size: int) -> bytes:
    """
    Read `size` bytes from a stream, short only at its end.

    A raw stream may return less than asked before the end, so reads repeat
    until the chunk is full or the stream is exhausted.

    Returns:
        bytes: The bytes read.
    """
    parts: list[bytes] = []
    remaining = size
    while remaining > 0:
        part = stream.read(remaining)
        if not part:
            break
        parts.append(part)
        remaining -= len(part)
    return b"".join(parts)


def _chunks(data: bytes | BinaryIO, chunk_size: int) -> Iterator[bytes]:
    """
    Split content into chunks of `chunk_size` bytes, the last one shorter.

    A stream is read one chunk at a time, so it is never held whole.

    Returns:
        Iterator[bytes]: The chunks, in order.
    """
    if isinstance(data, bytes):
        for start in range(0, len(data), chunk_size):
            yield data[start : start + chunk_size]
        return
    while chunk := _read_exactly(data, chunk_size):
        yield chunk
        if len(chunk) < chunk_size:
            return


# =============================================================================
# CLASS: ChunkedUpload
# =============================================================================


class ChunkedUpload:
    """
    One chunked upload, handing out an `Operation` for each chunk in turn.

    The content is read one chunk ahead, so the chunk that turns out to be the
    last can carry `X-Egnyte-Last-Chunk` and the composite checksum; at most
    two chunks are held in memory. The first chunk's response carries the
    upload ID, which every later chunk sends. Clients send `next_chunk()`
    until it returns None, then `last_chunk()`.
    """

    def __init__(
        self,
        target: str,
        data: bytes | BinaryIO,
        *,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        last_modified: datetime | None = None,
    ) -> None:
        """
        Prepare a chunked upload to an operation path under `/pubapi`.

        Args:
            target: The `/v1/fs-content-chunked/...` operation path.
            data: The content, as bytes or a binary stream.
            chunk_size: Size of every chunk but the last, in bytes.
            last_modified: Modification time recorded for the new version.
        """
        if not MIN_CHUNK_SIZE <= chunk_size <= MAX_CHUNK_SIZE:
            raise ValueError(
                f"chunk_size must be between {MIN_CHUNK_SIZE} and "
                f"{MAX_CHUNK_SIZE} bytes; got {chunk_size}"
            )
        self._target = target
        self._chunk_size = chunk_size
        self._last_modified = last_modified
        self._source = _chunks(data, chunk_size)
        self._pending: bytes = next(self._source, b"")
        self._checksums: list[str] = []
        self._upload_id: str | None = None

    @property
    def upload_id(self) -> str | None:
        """
        The upload ID Egnyte assigned on the first chunk.

        Returns:
            str | None: The upload ID, or None before the first chunk is sent.
        """
        return self._upload_id

    def _headers(self, chunk: bytes) -> dict[str, str]:
        checksum = hashlib.sha512(chunk).hexdigest()
        self._checksums.append(checksum)
        headers = {
            "Content-Type": "application/octet-stream",
            "X-Egnyte-Chunk-Num": str(len(self._checksums)),
            "X-Egnyte-Chunk-Sha512-Checksum": checksum,
        }
        if self._upload_id is not None:
            headers["X-Egnyte-Upload-Id"] = self._upload_id
        return headers

    def _record(self, response: httpx.Response) -> UploadedChunk:
        upload_id = response.headers.get("X-Egnyte-Upload-Id") or self._upload_id
        if not upload_id:
            raise ValueError("Egnyte answered the first chunk without an upload ID")
        self._upload_id = upload_id
        return UploadedChunk(
            upload_id=upload_id,
            chunk_num=int(
                response.headers.get("X-Egnyte-Chunk-Num", len(self._checksums))
            ),
            checksum=response.headers.get("X-Egnyte-Chunk-Sha512-Checksum"),
        )

    def next_chunk(self) -> Operation[UploadedChunk] | None:
        """
        Build the upload of the next chunk that is not the last.

        Returns:
            Operation[UploadedChunk] | None: The chunk upload, or None when
                only the last chunk remains.
        """
        following = next(self._source, None)
        if following is None:
            return None
        chunk, self._pending = self._pending, following
        return Operation(
            method="POST",
            path=self._target,
            content=chunk,
            headers=self._headers(chunk),
            parse=self._record,
        )

    def last_chunk(self) -> Operation[UploadedFile]:
        """
        Build the upload of the last chunk, which commits the file.

        It carries the composite checksum, `2-{chunks}-{chunk size}-{SHA-512 of
        the concatenated chunk checksums}`, so Egnyte rejects an upload whose
        chunks it did not receive intact.

        Egnyte refuses an upload whose only chunk is under 10 MiB, so that is
        refused here before anything is sent; `upload_file` suits such content.

        Returns:
            Operation[UploadedFile]: The last chunk upload.
        """
        chunk = self._pending
        if not self._checksums and len(chunk) < MIN_CHUNK_SIZE:
            raise ValueError(
                f"A chunked upload needs at least {MIN_CHUNK_SIZE} bytes; "
                f"got {len(chunk)}. Use upload_file for smaller content."
            )
        headers = self._headers(chunk)
        count = len(self._checksums)
        combined = hashlib.sha512("".join(self._checksums).encode()).hexdigest()
        chunk_size = self._chunk_size if count > 1 else len(chunk)
        headers["X-Egnyte-Last-Chunk"] = "true"
        headers["X-Sha512-Checksum"] = (
            f"{CHUNKED_CHECKSUM_VERSION}-{count}-{chunk_size}-{combined}"
        )
        if self._last_modified is not None:
            headers["Last-Modified"] = _http_date(self._last_modified)
        return Operation(
            method="POST",
            path=self._target,
            content=chunk,
            headers=headers,
            parse=model(UploadedFile),
        )


# -----------------------------------------------------------------------------
# OPERATION: upload_file_chunked
# -----------------------------------------------------------------------------


def upload_file_chunked(
    path: str,
    data: bytes | BinaryIO,
    *,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    last_modified: datetime | None = None,
) -> ChunkedUpload:
    """
    Start a chunked upload to a file path.

    Egnyte documents a by-ID form, `/fs-content-chunked/ids/file/{group_id}`,
    but answers it 409 "Can only add files in allowed roots": it reads the ID
    as a path. Uploads by ID therefore resolve the file's path first.

    Returns:
        ChunkedUpload: The upload, which builds each chunk's operation.
    """
    target = f"/v1/fs-content-chunked{encode_path(path)}"
    return ChunkedUpload(
        target, data, chunk_size=chunk_size, last_modified=last_modified
    )
