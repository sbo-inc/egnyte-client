import hashlib
from collections.abc import Callable
from datetime import UTC, datetime, timedelta, timezone

import httpx
import pytest
from conftest import FILE, FOLDER, body, respond

from egnyte_client.client import EgnyteClient
from egnyte_client.operations.generic import encode_path, normalize_path
from egnyte_client.schemas.filesystem import File, Folder

Recorder = tuple[EgnyteClient, list[httpx.Request]]


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
# TEST: path encoding
# =============================================================================


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("/Shared/Docs", "/Shared/Docs"),
        ("Shared/Docs/", "/Shared/Docs"),
        ("/Shared//a b/c?.txt", "/Shared/a%20b/c%3F.txt"),
        ("/Shared/$file#1%.txt", "/Shared/%24file%231%25.txt"),
        ("/Shared/café", "/Shared/caf%C3%A9"),
        ("/", "/"),
    ],
)
def test_encode_path(path: str, expected: str) -> None:
    assert encode_path(path) == expected


def test_relative_segments_are_refused() -> None:
    with pytest.raises(ValueError, match="Relative segments"):
        encode_path("/Shared/../Private")


def test_normalize_path_keeps_characters() -> None:
    assert normalize_path("Shared//a b/") == "/Shared/a b"


# =============================================================================
# TEST: metadata reads
# =============================================================================


def test_get_folder_lists_content(record: Callable[[httpx.Response], Recorder]) -> None:
    client, sent = record(respond(FOLDER))

    folder = client.get_folder(
        "/Shared/Docs", count=10, offset=5, sort_by="name", sort_direction="descending"
    )

    assert sent[0].method == "GET"
    assert sent[0].url.path == "/pubapi/v1/fs/Shared/Docs"
    assert dict(sent[0].url.params) == {
        "list_content": "true",
        "count": "10",
        "offset": "5",
        "sort_by": "name",
        "sort_direction": "descending",
    }
    assert folder.folder_id == "f-1"
    assert folder.total_count == 2
    assert [f.name for f in folder.folders] == ["Sub"]
    assert folder.files[0].group_id == "g-1"
    assert folder.files[0].last_modified == datetime(2026, 11, 6, 0, 22, 45, tzinfo=UTC)
    assert folder.last_modified == datetime(2026, 11, 5, 19, 29, 21, tzinfo=UTC)


def test_get_folder_by_id(record: Callable[[httpx.Response], Recorder]) -> None:
    client, sent = record(respond(FOLDER))

    client.get_folder_by_id("f-1")

    assert sent[0].url.path == "/pubapi/v1/fs/ids/folder/f-1"


def test_get_item_returns_the_right_kind(
    record: Callable[[httpx.Response], Recorder],
) -> None:
    folder_client, _ = record(respond(FOLDER))
    file_client, sent = record(respond(FILE))

    assert isinstance(folder_client.get_item("/Shared/Docs"), Folder)
    assert isinstance(file_client.get_item("/Shared/Docs/hello world.txt"), File)
    assert sent[0].url.raw_path == b"/pubapi/v1/fs/Shared/Docs/hello%20world.txt"


def test_get_file_with_versions(record: Callable[[httpx.Response], Recorder]) -> None:
    versioned = {
        **FILE,
        "versions": [{"entry_id": "e-0", "size": 4, "is_current": False}],
    }
    client, sent = record(respond(versioned))

    file = client.get_file("/Shared/Docs/hello world.txt", include_versions=True)

    assert dict(sent[0].url.params) == {"list_content": "true"}
    assert [v.entry_id for v in file.versions] == ["e-0"]


def test_get_file_without_versions_sends_no_query(
    record: Callable[[httpx.Response], Recorder],
) -> None:
    client, sent = record(respond(FILE))

    client.get_file_by_id("g-1")

    assert sent[0].url.path == "/pubapi/v1/fs/ids/file/g-1"
    assert not sent[0].url.params


def test_get_file_on_a_folder_raises(
    record: Callable[[httpx.Response], Recorder],
) -> None:
    client, _ = record(respond(FOLDER))

    with pytest.raises(ValueError, match="is a folder, not a file"):
        client.get_file("/Shared/Docs")


def test_get_folder_on_a_file_raises(
    record: Callable[[httpx.Response], Recorder],
) -> None:
    client, _ = record(respond(FILE))

    with pytest.raises(ValueError, match="is a file, not a folder"):
        client.get_folder("/Shared/Docs/hello world.txt")


# =============================================================================
# TEST: writes
# =============================================================================


def test_create_folder(record: Callable[[httpx.Response], Recorder]) -> None:
    client, sent = record(respond({"folder_id": "f-9", "path": "/Shared/New"}, 201))

    created = client.create_folder("/Shared/New")

    assert sent[0].method == "POST"
    assert sent[0].url.path == "/pubapi/v1/fs/Shared/New"
    assert sent[0].headers["Content-Type"] == "application/json"
    assert body(sent[0]) == {"action": "add_folder"}
    assert created.folder_id == "f-9"


def test_upload_sends_raw_bytes_and_checksum(
    record: Callable[[httpx.Response], Recorder],
) -> None:
    client, sent = record(
        respond(
            {
                "checksum": "c",
                "group_id": "g-1",
                "entry_id": "e-2",
                "path": "/Shared/a.txt",
            }
        )
    )
    data = b"hello egnyte\n"

    uploaded = client.upload_file(
        "/Shared/a.txt",
        data,
        last_modified=datetime(
            2026, 1, 2, 4, 4, 5, tzinfo=timezone(timedelta(hours=1))
        ),
    )

    request = sent[0]
    assert request.url.path == "/pubapi/v1/fs-content/Shared/a.txt"
    assert request.content == data
    assert request.headers["Content-Type"] == "application/octet-stream"
    assert request.headers["X-Sha512-Checksum"] == hashlib.sha512(data).hexdigest()
    assert request.headers["Last-Modified"] == "Fri, 02 Jan 2026 03:04:05 GMT"
    assert uploaded.entry_id == "e-2"


def test_upload_treats_naive_last_modified_as_utc(
    record: Callable[[httpx.Response], Recorder],
) -> None:
    client, sent = record(
        respond({"group_id": "g", "entry_id": "e", "path": "/Shared/a.txt"})
    )

    client.upload_file(
        "/Shared/a.txt", b"x", last_modified=datetime(2026, 1, 2, 3, 4, 5)
    )

    assert sent[0].headers["Last-Modified"] == "Fri, 02 Jan 2026 03:04:05 GMT"
    assert "Last-Modified" in sent[0].headers


def test_download_returns_bytes(record: Callable[[httpx.Response], Recorder]) -> None:
    client, sent = record(httpx.Response(200, content=b"\x00binary"))

    assert client.download_file("/Shared/a.bin", entry_id="e-1") == b"\x00binary"
    assert sent[0].url.path == "/pubapi/v1/fs-content/Shared/a.bin"
    assert dict(sent[0].url.params) == {"entry_id": "e-1"}


def test_download_by_id(record: Callable[[httpx.Response], Recorder]) -> None:
    client, sent = record(httpx.Response(200, content=b"x"))

    client.download_file_by_id("g-1")

    assert sent[0].url.path == "/pubapi/v1/fs-content/ids/file/g-1"


@pytest.mark.parametrize("action", ["copy", "move"])
def test_copy_and_move(
    record: Callable[[httpx.Response], Recorder], action: str
) -> None:
    client, sent = record(respond({"path": "/Shared/b c.txt", "group_id": "g-1"}))
    method = client.copy_item if action == "copy" else client.move_item

    result = method("/Shared/a.txt", "Shared//b c.txt", permissions="keep_original")

    assert sent[0].url.path == "/pubapi/v1/fs/Shared/a.txt"
    assert body(sent[0]) == {
        "action": action,
        "destination": "/Shared/b c.txt",
        "permissions": "keep_original",
    }
    assert result.group_id == "g-1"


def test_delete_item(record: Callable[[httpx.Response], Recorder]) -> None:
    client, sent = record(respond({"parent_folder_path": "/Shared"}))

    deleted = client.delete_item("/Shared/a.txt", entry_id="e-1")

    assert sent[0].method == "DELETE"
    assert dict(sent[0].url.params) == {"entry_id": "e-1"}
    assert deleted.parent_folder_path == "/Shared"


def test_delete_tolerates_an_empty_body(
    record: Callable[[httpx.Response], Recorder],
) -> None:
    client, _ = record(respond())

    assert client.delete_item("/Shared/a.txt").parent_folder_path is None
