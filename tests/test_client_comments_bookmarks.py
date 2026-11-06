from collections.abc import Callable
from datetime import UTC, datetime, timedelta, timezone

import httpx
import pytest
from conftest import body, respond

from egnyte_client.async_client import AsyncEgnyteClient
from egnyte_client.client import EgnyteClient

# Shaped after a live create, which answers 201.
COMMENT = {
    "can_delete": True,
    "creation_time": "2026-11-06T01:10:16.009+0000",
    "id": "6f1c2e0a-0000-4000-8000-000000000001",
    "message": "Looks good",
    "username": "jdoe",
    "formatted_name": "Jane Doe",
    "file_path": "/Shared/Docs/hello world.txt",
    "group_id": "g-1",
}

# Shaped after a live create, which answers 201.
BOOKMARK = {
    "id": 5468,
    "folder_id": "f-1",
    "creation_date": "2026-11-05T17:09:56.000+0000",
    "path": "/Shared/Docs",
}


def _client(
    make_client: Callable[..., EgnyteClient], response: httpx.Response
) -> tuple[EgnyteClient, list[httpx.Request]]:
    sent: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(request)
        return response

    return make_client(handler), sent


# =============================================================================
# TEST: comments
# =============================================================================


def test_create_comment(make_client: Callable[..., EgnyteClient]) -> None:
    client, sent = _client(make_client, respond(COMMENT, status=201))

    comment = client.create_comment("Shared/Docs/hello world.txt", "Looks good")

    assert sent[0].method == "POST"
    assert sent[0].url.path == "/pubapi/v1/notes"
    assert body(sent[0]) == {
        "path": "/Shared/Docs/hello world.txt",
        "body": "Looks good",
    }
    assert comment.id == COMMENT["id"]
    assert comment.message == "Looks good"
    assert comment.can_delete is True
    assert comment.creation_time == datetime(2026, 11, 6, 1, 10, 16, 9000, tzinfo=UTC)


def test_list_comments_sends_every_filter(
    make_client: Callable[..., EgnyteClient],
) -> None:
    page = {"count": 1, "offset": 5, "notes": [COMMENT], "total_results": 6}
    client, sent = _client(make_client, respond(page))

    comments = client.list_comments(
        filter_by_path="/Shared/Docs/hello world.txt",
        filter_by_start_time=datetime(2026, 1, 1),
        filter_by_end_time=datetime(2026, 2, 1, 1, tzinfo=timezone(timedelta(hours=1))),
        offset=5,
        count=50,
    )

    assert sent[0].method == "GET"
    assert sent[0].url.path == "/pubapi/v1/notes"
    assert dict(sent[0].url.params) == {
        "file": "/Shared/Docs/hello world.txt",
        # ISO 8601 in UTC, as the docs' example; naive is read as UTC.
        "start_time": "2026-01-01T00:00:00Z",
        "end_time": "2026-02-01T00:00:00Z",
        "offset": "5",
        "count": "50",
    }
    assert [comment.username for comment in comments] == ["jdoe"]


def test_list_comments_without_filters(
    make_client: Callable[..., EgnyteClient],
) -> None:
    client, sent = _client(make_client, respond({"count": 0, "offset": 0}))

    assert client.list_comments() == []
    assert dict(sent[0].url.params) == {}


def test_list_comments_refuses_an_inverted_window(
    make_client: Callable[..., EgnyteClient],
) -> None:
    client, sent = _client(make_client, respond({}))

    with pytest.raises(ValueError, match="before"):
        client.list_comments(
            filter_by_start_time=datetime(2026, 2, 1, tzinfo=UTC),
            filter_by_end_time=datetime(2026, 1, 1, tzinfo=UTC),
        )
    assert sent == []


def test_get_comment(make_client: Callable[..., EgnyteClient]) -> None:
    client, sent = _client(make_client, respond(COMMENT))

    comment = client.get_comment(COMMENT["id"])

    assert sent[0].url.path == f"/pubapi/v1/notes/{COMMENT['id']}"
    assert comment.file_path == "/Shared/Docs/hello world.txt"


def test_delete_comment(make_client: Callable[..., EgnyteClient]) -> None:
    client, sent = _client(make_client, respond())

    assert client.delete_comment(COMMENT["id"]) is None
    assert sent[0].method == "DELETE"
    assert sent[0].url.path == f"/pubapi/v1/notes/{COMMENT['id']}"


# =============================================================================
# TEST: bookmarks
# =============================================================================


def test_create_bookmark_by_path(make_client: Callable[..., EgnyteClient]) -> None:
    client, sent = _client(make_client, respond(BOOKMARK, status=201))

    bookmark = client.create_bookmark(path="Shared/Docs/")

    assert sent[0].method == "POST"
    assert sent[0].url.path == "/pubapi/v1/bookmarks"
    assert body(sent[0]) == {"path": "/Shared/Docs"}
    assert bookmark.id == 5468
    assert bookmark.creation_date == datetime(2026, 11, 5, 17, 9, 56, tzinfo=UTC)


def test_create_bookmark_by_folder_id(
    make_client: Callable[..., EgnyteClient],
) -> None:
    client, sent = _client(make_client, respond(BOOKMARK, status=201))

    client.create_bookmark(folder_id="f-1")

    assert body(sent[0]) == {"folder_id": "f-1"}


@pytest.mark.parametrize("kwargs", [{}, {"path": "/Shared/Docs", "folder_id": "f-1"}])
def test_create_bookmark_needs_exactly_one_target(
    make_client: Callable[..., EgnyteClient], kwargs: dict[str, str]
) -> None:
    client, sent = _client(make_client, respond(BOOKMARK))

    with pytest.raises(ValueError, match="exactly one"):
        client.create_bookmark(**kwargs)
    assert sent == []


def test_list_bookmarks(make_client: Callable[..., EgnyteClient]) -> None:
    second = {**BOOKMARK, "id": 5469, "path": "/Shared/Other", "folder_id": "f-2"}
    page = {"offset": 2, "count": 2, "bookmarks": [BOOKMARK, second]}
    client, sent = _client(make_client, respond(page))

    bookmarks = client.list_bookmarks(offset=2, count=10)

    assert sent[0].url.path == "/pubapi/v1/bookmarks"
    assert dict(sent[0].url.params) == {"offset": "2", "count": "10"}
    assert [bookmark.id for bookmark in bookmarks] == [5468, 5469]


def test_get_bookmark(make_client: Callable[..., EgnyteClient]) -> None:
    client, sent = _client(make_client, respond(BOOKMARK))

    bookmark = client.get_bookmark(5468)

    assert sent[0].url.path == "/pubapi/v1/bookmarks/5468"
    assert bookmark.folder_id == "f-1"


def test_delete_bookmark(make_client: Callable[..., EgnyteClient]) -> None:
    client, sent = _client(make_client, respond(status=204))

    assert client.delete_bookmark(5468) is None
    assert sent[0].method == "DELETE"
    assert sent[0].url.path == "/pubapi/v1/bookmarks/5468"


# =============================================================================
# TEST: async
# =============================================================================


async def test_async_comments(
    make_async_client: Callable[..., AsyncEgnyteClient],
) -> None:
    sent: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(request)
        if request.method == "DELETE":
            return respond()
        if request.url.path == "/pubapi/v1/notes" and request.method == "GET":
            return respond({"count": 1, "offset": 0, "notes": [COMMENT]})
        return respond(COMMENT)

    client = make_async_client(handler)

    created = await client.create_comment("/Shared/Docs/hello world.txt", "Hi")
    listed = await client.list_comments(filter_by_path="/Shared/Docs/hello world.txt")
    fetched = await client.get_comment(created.id)
    await client.delete_comment(created.id)

    assert [comment.id for comment in listed] == [fetched.id]
    assert [request.method for request in sent] == ["POST", "GET", "GET", "DELETE"]


async def test_async_bookmarks(
    make_async_client: Callable[..., AsyncEgnyteClient],
) -> None:
    sent: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(request)
        if request.method == "DELETE":
            return respond(status=204)
        if request.url.path == "/pubapi/v1/bookmarks" and request.method == "GET":
            return respond({"offset": 0, "count": 1, "bookmarks": [BOOKMARK]})
        return respond(BOOKMARK)

    client = make_async_client(handler)

    created = await client.create_bookmark(folder_id="f-1")
    listed = await client.list_bookmarks()
    fetched = await client.get_bookmark(created.id)
    await client.delete_bookmark(created.id)

    assert [bookmark.id for bookmark in listed] == [fetched.id]
    assert sent[3].url.path == "/pubapi/v1/bookmarks/5468"
