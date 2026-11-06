import hashlib
import io
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import httpx
import pytest
from conftest import FOLDER, body, respond

from egnyte_client.async_client import AsyncEgnyteClient
from egnyte_client.client import EgnyteClient
from egnyte_client.operations.filesystem import MAX_CHUNK_SIZE, MIN_CHUNK_SIZE

Recorder = tuple[EgnyteClient, list[httpx.Request]]

# Shaped after live responses.
STATS: dict[str, Any] = {
    "allVersionsSize": 20971720,
    "allFilesSize": 10485860,
    "filesCount": 2,
    "fileVersionsCount": 3,
    "foldersCount": 1,
    "allVersionsSizeInKB": 20480,
    "allFilesSizeInKB": 10240,
}
LOCK: dict[str, Any] = {"lock_token": "lt-1", "timeout": 3599}
OPTIONS_FOLDER: dict[str, Any] = {
    "name": "Docs",
    "lastModified": 1793906961000,
    "uploaded": 1793906961689,
    "path": "/Shared/Docs",
    "folder_id": "f-1",
    "parent_id": "f-0",
    "folder_description": "Quarterly reports",
    "is_folder": True,
    "allow_links": True,
    "allow_upload_links": False,
    "allowed_file_link_types": ["anyone", "password", "domain", "recipients"],
    "allowed_folder_link_types": ["domain", "recipients"],
    "public_links": "files_folders",
    "restrict_move_delete": True,
    "move_delete_folder_restriction": "admins_or_owners",
}


@pytest.fixture
def record(
    make_client: Callable[..., EgnyteClient],
) -> Callable[[httpx.Response], Recorder]:
    """
    Return a factory for a client that answers every call with one response.

    Returns:
        Callable[[httpx.Response], Recorder]: The client and its sent requests.
    """

    def factory(response: httpx.Response) -> Recorder:
        sent: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            sent.append(request)
            return response

        return make_client(handler), sent

    return factory


# =============================================================================
# TEST: copy, move, and delete by ID
# =============================================================================


@pytest.mark.parametrize("action", ["copy", "move"])
def test_transfer_file_by_id(
    record: Callable[[httpx.Response], Recorder], action: str
) -> None:
    client, sent = record(respond({"path": "/Shared/Docs/b.txt", "group_id": "g-2"}))
    method = client.copy_file_by_id if action == "copy" else client.move_file_by_id

    result = method("g-1", "f-1", name="b.txt", permissions="inherit_from_parent")

    assert sent[0].method == "POST"
    assert sent[0].url.path == "/pubapi/v1/fs/ids/file/g-1"
    assert body(sent[0]) == {
        "action": action,
        "destination_id": "f-1",
        "name": "b.txt",
        "permissions": "inherit_from_parent",
    }
    assert result.group_id == "g-2"
    assert result.path == "/Shared/Docs/b.txt"


@pytest.mark.parametrize("action", ["copy", "move"])
def test_transfer_folder_by_id(
    record: Callable[[httpx.Response], Recorder], action: str
) -> None:
    client, sent = record(respond({"path": "/Shared/Docs/Sub", "folder_id": "f-3"}))
    method = client.copy_folder_by_id if action == "copy" else client.move_folder_by_id

    result = method("f-2", "f-1", folder_options_mode="apply_destination")

    assert sent[0].url.path == "/pubapi/v1/fs/ids/folder/f-2"
    assert body(sent[0]) == {
        "action": action,
        "destination_id": "f-1",
        "folder_options_mode": "apply_destination",
    }
    assert result.folder_id == "f-3"


def test_delete_file_by_id(record: Callable[[httpx.Response], Recorder]) -> None:
    client, sent = record(respond({"parent_folder_path": "/Shared/Docs"}))

    deleted = client.delete_file_by_id("g-1", entry_id="e-1")

    assert sent[0].method == "DELETE"
    assert sent[0].url.path == "/pubapi/v1/fs/ids/file/g-1"
    assert dict(sent[0].url.params) == {"entry_id": "e-1"}
    assert deleted.parent_folder_path == "/Shared/Docs"


def test_delete_folder_by_id(record: Callable[[httpx.Response], Recorder]) -> None:
    client, sent = record(respond({"parent_folder_path": "/Shared"}))

    deleted = client.delete_folder_by_id("f-1")

    assert sent[0].method == "DELETE"
    assert sent[0].url.path == "/pubapi/v1/fs/ids/folder/f-1"
    assert not sent[0].url.params
    assert deleted.parent_folder_path == "/Shared"


def test_ids_are_encoded(record: Callable[[httpx.Response], Recorder]) -> None:
    client, sent = record(respond({"parent_folder_path": "/Shared"}))

    client.delete_folder_by_id("a/b c")

    assert sent[0].url.raw_path == b"/pubapi/v1/fs/ids/folder/a%2Fb%20c"


# =============================================================================
# TEST: folder stats
# =============================================================================


def test_get_folder_stats(record: Callable[[httpx.Response], Recorder]) -> None:
    client, sent = record(respond(STATS))

    stats = client.get_folder_stats("f-1")

    assert sent[0].method == "GET"
    assert sent[0].url.path == "/pubapi/v1/fs/ids/folder/f-1/stats"
    assert stats.files_count == 2
    assert stats.file_versions_count == 3
    assert stats.folders_count == 1
    assert stats.all_files_size == 10485860
    assert stats.all_versions_size_in_kb == 20480


# =============================================================================
# TEST: locks
# =============================================================================


def test_lock_file_lets_egnyte_pick_the_token(
    record: Callable[[httpx.Response], Recorder],
) -> None:
    client, sent = record(respond(LOCK))

    lock = client.lock_file("/Shared/Docs/a b.txt")

    assert sent[0].method == "POST"
    assert sent[0].url.raw_path == b"/pubapi/v1/fs/Shared/Docs/a%20b.txt"
    assert body(sent[0]) == {"action": "lock"}
    assert lock.lock_token == "lt-1"
    assert lock.timeout == 3599


def test_lock_file_by_id_with_every_option(
    record: Callable[[httpx.Response], Recorder],
) -> None:
    client, sent = record(respond({"lock_token": "mine", "timeout": 600}))

    lock = client.lock_file_by_id(
        "g-1", lock_token="mine", lock_timeout=600, collaboration="Y29sbGFi"
    )

    assert sent[0].url.path == "/pubapi/v1/fs/ids/file/g-1"
    assert body(sent[0]) == {
        "action": "lock",
        "lock_token": "mine",
        "lock_timeout": 600,
        "collaboration": "Y29sbGFi",
    }
    assert lock.lock_token == "mine"


@pytest.mark.parametrize("timeout", [0, 604801])
def test_lock_timeout_out_of_range_is_refused(
    record: Callable[[httpx.Response], Recorder], timeout: int
) -> None:
    client, sent = record(respond(LOCK))

    with pytest.raises(ValueError, match="lock_timeout"):
        client.lock_file("/Shared/a.txt", lock_timeout=timeout)
    assert not sent


def test_unlock_file(record: Callable[[httpx.Response], Recorder]) -> None:
    # Egnyte answers an unlock with 200 and an empty body.
    client, sent = record(respond())

    assert client.unlock_file("/Shared/a.txt", "lt-1") is None
    assert sent[0].url.path == "/pubapi/v1/fs/Shared/a.txt"
    assert body(sent[0]) == {"action": "unlock", "lock_token": "lt-1"}


def test_unlock_file_by_id(record: Callable[[httpx.Response], Recorder]) -> None:
    client, sent = record(respond())

    client.unlock_file_by_id("g-1", "lt-1")

    assert sent[0].url.path == "/pubapi/v1/fs/ids/file/g-1"
    assert body(sent[0]) == {"action": "unlock", "lock_token": "lt-1"}


# =============================================================================
# TEST: folder options
# =============================================================================


def test_update_folder_options_sends_every_option(
    record: Callable[[httpx.Response], Recorder],
) -> None:
    client, sent = record(respond(OPTIONS_FOLDER))

    folder = client.update_folder_options(
        "Shared//Docs/",
        description="Quarterly reports",
        allow_links=True,
        allow_upload_links=False,
        public_links="files_folders",
        restrict_move_delete=True,
        move_delete_folder_restriction="admins_or_owners",
        inheritance_rule="this_folder_only",
        notify_content_updates=True,
        notify_content_accessed=False,
    )

    assert sent[0].method == "PATCH"
    assert sent[0].url.path == "/pubapi/v1/fs/Shared/Docs"
    assert sent[0].headers["Content-Type"] == "application/json"
    assert body(sent[0]) == {
        "folder_description": "Quarterly reports",
        "allow_links": True,
        "allow_upload_links": False,
        "public_links": "files_folders",
        "restrict_move_delete": True,
        "move_delete_folder_restriction": "admins_or_owners",
        "inheritance_rule": "this_folder_only",
        "email_preferences": {"content_updates": True, "content_accessed": False},
    }
    assert folder.folder_description == "Quarterly reports"
    assert folder.move_delete_folder_restriction == "admins_or_owners"
    assert folder.allowed_folder_link_types == ["domain", "recipients"]


def test_update_folder_options_sends_only_what_is_given(
    record: Callable[[httpx.Response], Recorder],
) -> None:
    client, sent = record(respond(OPTIONS_FOLDER))

    client.update_folder_options("/Shared/Docs", notify_content_accessed=True)

    assert body(sent[0]) == {"email_preferences": {"content_accessed": True}}


def test_update_folder_options_needs_an_option(
    record: Callable[[httpx.Response], Recorder],
) -> None:
    client, sent = record(respond(OPTIONS_FOLDER))

    with pytest.raises(ValueError, match="at least one option"):
        client.update_folder_options("/Shared/Docs")
    assert not sent


def test_update_folder_options_refuses_a_long_description(
    record: Callable[[httpx.Response], Recorder],
) -> None:
    client, sent = record(respond(OPTIONS_FOLDER))

    client.update_folder_options("/Shared/Docs", description="x" * 200)
    with pytest.raises(ValueError, match="200 characters"):
        client.update_folder_options("/Shared/Docs", description="x" * 201)
    assert len(sent) == 1


def test_update_folder_options_on_a_file_raises(
    record: Callable[[httpx.Response], Recorder],
) -> None:
    client, _ = record(respond(FOLDER["files"][0]))

    with pytest.raises(ValueError, match="is a file, not a folder"):
        client.update_folder_options("/Shared/Docs/hello world.txt", allow_links=True)


# =============================================================================
# TEST: chunked upload
# =============================================================================

UPLOAD_ID = "u-1"


def _chunked_handler(
    sent: list[httpx.Request], path: str = "/Shared/big.bin"
) -> Callable[[httpx.Request], httpx.Response]:
    """
    Stand in for the chunked upload endpoint, shaped after live responses.

    Returns:
        Callable[[httpx.Request], httpx.Response]: The handler.
    """

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(request)
        headers = {
            "X-Egnyte-Upload-Id": UPLOAD_ID,
            "X-Egnyte-Chunk-Num": request.headers["X-Egnyte-Chunk-Num"],
            "X-Egnyte-Chunk-Sha512-Checksum": hashlib.sha512(
                request.content
            ).hexdigest(),
        }
        if request.headers.get("X-Egnyte-Last-Chunk") != "true":
            return httpx.Response(200, headers=headers)
        return httpx.Response(
            200,
            headers=headers,
            json={
                "checksum": request.headers["X-Sha512-Checksum"],
                "group_id": "g-9",
                "entry_id": "e-9",
                "path": path,
            },
        )

    return handler


def _composite(chunks: list[bytes], chunk_size: int) -> str:
    combined = "".join(hashlib.sha512(chunk).hexdigest() for chunk in chunks)
    digest = hashlib.sha512(combined.encode()).hexdigest()
    return f"2-{len(chunks)}-{chunk_size}-{digest}"


def _content(size: int) -> bytes:
    return bytes(range(256)) * (size // 256) + bytes(size % 256)


def test_chunked_upload_sends_each_chunk_in_turn(
    make_client: Callable[..., EgnyteClient],
) -> None:
    sent: list[httpx.Request] = []
    client = make_client(_chunked_handler(sent))
    data = _content(2 * MIN_CHUNK_SIZE + 5)
    chunks = [
        data[:MIN_CHUNK_SIZE],
        data[MIN_CHUNK_SIZE : 2 * MIN_CHUNK_SIZE],
        data[2 * MIN_CHUNK_SIZE :],
    ]

    uploaded = client.upload_file_chunked(
        "/Shared/big.bin",
        data,
        chunk_size=MIN_CHUNK_SIZE,
        last_modified=datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC),
    )

    assert [request.content for request in sent] == chunks
    for number, (request, chunk) in enumerate(zip(sent, chunks, strict=True), 1):
        assert request.method == "POST"
        assert request.url.path == "/pubapi/v1/fs-content-chunked/Shared/big.bin"
        assert request.headers["Content-Type"] == "application/octet-stream"
        assert request.headers["X-Egnyte-Chunk-Num"] == str(number)
        assert (
            request.headers["X-Egnyte-Chunk-Sha512-Checksum"]
            == hashlib.sha512(chunk).hexdigest()
        )
    first, middle, last = sent
    assert "X-Egnyte-Upload-Id" not in first.headers
    assert middle.headers["X-Egnyte-Upload-Id"] == UPLOAD_ID
    assert "X-Egnyte-Last-Chunk" not in middle.headers
    assert last.headers["X-Egnyte-Upload-Id"] == UPLOAD_ID
    assert last.headers["X-Egnyte-Last-Chunk"] == "true"
    assert last.headers["X-Sha512-Checksum"] == _composite(chunks, MIN_CHUNK_SIZE)
    assert last.headers["Last-Modified"] == "Fri, 02 Jan 2026 03:04:05 GMT"
    assert "Last-Modified" not in first.headers
    assert uploaded.group_id == "g-9"
    assert uploaded.checksum == _composite(chunks, MIN_CHUNK_SIZE)


class TrickleStream(io.RawIOBase):
    """
    A raw stream that returns at most `step` bytes per read, as sockets may.
    """

    def __init__(self, data: bytes, step: int) -> None:
        self._data = memoryview(data)
        self._step = step
        self.reads = 0

    def readable(self) -> bool:
        return True

    def read(self, size: int = -1) -> bytes:
        self.reads += 1
        size = self._step if size < 0 else min(size, self._step)
        part, self._data = self._data[:size], self._data[size:]
        return bytes(part)


def test_chunked_upload_streams_a_file_object_by_id(
    make_client: Callable[..., EgnyteClient],
) -> None:
    sent: list[httpx.Request] = []
    lookups: list[httpx.Request] = []
    chunks = _chunked_handler(sent)

    def handler(request: httpx.Request) -> httpx.Response:
        # Egnyte's by-ID chunked endpoint rejects uploads, so the client
        # resolves the file's path first and uploads to it.
        if request.method == "GET":
            lookups.append(request)
            return respond(
                {
                    "name": "big file.bin",
                    "path": "/Shared/big file.bin",
                    "group_id": "g-1",
                }
            )
        return chunks(request)

    client = make_client(handler)
    # Exactly two full chunks: the second is the last, at full size.
    data = _content(2 * MIN_CHUNK_SIZE)
    stream = TrickleStream(data, step=4 * 1024 * 1024)

    uploaded = client.upload_file_chunked_by_id(
        "g-1", stream, chunk_size=MIN_CHUNK_SIZE
    )

    assert [r.url.path for r in lookups] == ["/pubapi/v1/fs/ids/file/g-1"]
    assert len(sent) == 2
    assert (
        sent[0].url.raw_path == b"/pubapi/v1/fs-content-chunked/Shared/big%20file.bin"
    )
    assert sent[1].url.raw_path == sent[0].url.raw_path
    assert sent[0].content == data[:MIN_CHUNK_SIZE]
    assert sent[1].content == data[MIN_CHUNK_SIZE:]
    assert sent[1].headers["X-Egnyte-Last-Chunk"] == "true"
    assert sent[1].headers["X-Sha512-Checksum"] == _composite(
        [data[:MIN_CHUNK_SIZE], data[MIN_CHUNK_SIZE:]], MIN_CHUNK_SIZE
    )
    assert stream.reads > 2
    assert uploaded.entry_id == "e-9"


def test_chunked_upload_of_one_full_chunk(
    make_client: Callable[..., EgnyteClient],
) -> None:
    sent: list[httpx.Request] = []
    client = make_client(_chunked_handler(sent))
    data = _content(MIN_CHUNK_SIZE)

    client.upload_file_chunked(
        "/Shared/big.bin", io.BytesIO(data), chunk_size=MIN_CHUNK_SIZE
    )

    assert len(sent) == 1
    assert "X-Egnyte-Upload-Id" not in sent[0].headers
    assert sent[0].headers["X-Egnyte-Last-Chunk"] == "true"
    assert sent[0].headers["X-Sha512-Checksum"] == _composite([data], MIN_CHUNK_SIZE)


@pytest.mark.parametrize("data", [b"small", io.BytesIO(b"small"), b""])
def test_chunked_upload_refuses_content_under_the_minimum(
    make_client: Callable[..., EgnyteClient], data: bytes | io.BytesIO
) -> None:
    sent: list[httpx.Request] = []
    client = make_client(_chunked_handler(sent))

    with pytest.raises(ValueError, match="Use upload_file"):
        client.upload_file_chunked("/Shared/a.txt", data)
    assert not sent


@pytest.mark.parametrize("chunk_size", [MIN_CHUNK_SIZE - 1, MAX_CHUNK_SIZE + 1])
def test_chunk_size_out_of_range_is_refused(
    make_client: Callable[..., EgnyteClient], chunk_size: int
) -> None:
    sent: list[httpx.Request] = []
    client = make_client(_chunked_handler(sent))

    with pytest.raises(ValueError, match="chunk_size"):
        client.upload_file_chunked("/Shared/a.bin", b"x", chunk_size=chunk_size)
    assert not sent


def test_chunked_upload_without_an_upload_id_raises(
    make_client: Callable[..., EgnyteClient],
) -> None:
    sent: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(request)
        return httpx.Response(200)

    client = make_client(handler)

    with pytest.raises(ValueError, match="without an upload ID"):
        client.upload_file_chunked(
            "/Shared/a.bin", _content(MIN_CHUNK_SIZE + 1), chunk_size=MIN_CHUNK_SIZE
        )
    assert len(sent) == 1


# =============================================================================
# TEST: async
# =============================================================================


async def test_async_chunked_upload(
    make_async_client: Callable[..., AsyncEgnyteClient],
) -> None:
    sent: list[httpx.Request] = []
    client = make_async_client(_chunked_handler(sent))
    data = _content(MIN_CHUNK_SIZE + 7)

    uploaded = await client.upload_file_chunked(
        "/Shared/big.bin", data, chunk_size=MIN_CHUNK_SIZE
    )

    assert [request.headers["X-Egnyte-Chunk-Num"] for request in sent] == ["1", "2"]
    assert sent[1].headers["X-Egnyte-Upload-Id"] == UPLOAD_ID
    assert sent[1].content == data[MIN_CHUNK_SIZE:]
    assert uploaded.path == "/Shared/big.bin"


async def test_async_lock_copy_and_stats(
    make_async_client: Callable[..., AsyncEgnyteClient],
) -> None:
    sent: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(request)
        if request.url.path.endswith("/stats"):
            return respond(STATS)
        if body(request)["action"] == "lock":
            return respond(LOCK)
        return respond({"path": "/Shared/b.txt", "group_id": "g-2"})

    client = make_async_client(handler)

    lock = await client.lock_file_by_id("g-1")
    copy = await client.copy_file_by_id("g-1", "f-1")
    stats = await client.get_folder_stats("f-1")

    assert lock.lock_token == "lt-1"
    assert body(sent[1]) == {"action": "copy", "destination_id": "f-1"}
    assert copy.group_id == "g-2"
    assert stats.folders_count == 1
