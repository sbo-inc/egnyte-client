"""
Coverage of the `comments` and `bookmarks` commands against a mock client.
"""

import json
from collections.abc import Callable
from typing import Any

import httpx
import pytest
from click.testing import Result
from conftest import body, respond

Runner = Callable[..., tuple[Result, list[httpx.Request]]]

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

BOOKMARK = {
    "id": 5468,
    "folder_id": "f-1",
    "creation_date": "2026-11-05T17:09:56.000+0000",
    "path": "/Shared/Docs",
}


@pytest.fixture
def run(cli_runner: Callable[..., Runner]) -> Callable[..., Runner]:
    """
    Return a factory for a runner invoking the CLI against a handler.

    Returns:
        Callable[..., Runner]: Takes a handler, gives back the runner.
    """
    return lambda handler: cli_runner(handler)


def _json(result: Result) -> Any:
    assert result.exit_code == 0, result.output
    return json.loads(result.stdout)


# =============================================================================
# TEST: comments
# =============================================================================


def test_comments_create(run: Callable[..., Runner]) -> None:
    result, sent = run(lambda r: respond(COMMENT, status=201))(
        "comments", "create", "/Shared/Docs/hello world.txt", "Looks good"
    )

    output = _json(result)
    assert output["id"] == COMMENT["id"]
    assert output["creation_time"] == "2026-11-06T01:10:16.009000Z"
    assert sent[0].method == "POST"
    assert sent[0].url.path == "/pubapi/v1/notes"
    assert body(sent[0]) == {
        "path": "/Shared/Docs/hello world.txt",
        "body": "Looks good",
    }


def test_comments_list_sends_every_filter(run: Callable[..., Runner]) -> None:
    page = {"count": 1, "offset": 5, "notes": [COMMENT], "total_results": 6}
    result, sent = run(lambda r: respond(page))(
        "comments",
        "list",
        "--path",
        "/Shared/Docs/hello world.txt",
        "--start-time",
        "2026-01-01",
        "--end-time",
        "2026-02-01T12:30:00",
        "--offset",
        "5",
        "--count",
        "50",
    )

    output = _json(result)
    assert [comment["message"] for comment in output] == ["Looks good"]
    assert sent[0].method == "GET"
    assert sent[0].url.path == "/pubapi/v1/notes"
    assert dict(sent[0].url.params) == {
        "file": "/Shared/Docs/hello world.txt",
        "start_time": "2026-01-01T00:00:00Z",
        "end_time": "2026-02-01T12:30:00Z",
        "offset": "5",
        "count": "50",
    }


def test_comments_list_without_filters(run: Callable[..., Runner]) -> None:
    result, sent = run(lambda r: respond({"notes": []}))("comments", "list")

    assert _json(result) == []
    assert not sent[0].url.params


def test_comments_list_refuses_an_empty_window(run: Callable[..., Runner]) -> None:
    result, sent = run(lambda r: respond({"notes": []}))(
        "comments", "list", "--start-time", "2026-02-01", "--end-time", "2026-01-01"
    )

    assert result.exit_code == 2
    assert "--start-time must be before --end-time." in result.output
    assert not sent


def test_comments_get(run: Callable[..., Runner]) -> None:
    result, sent = run(lambda r: respond(COMMENT))(
        "comments", "get", "6f1c2e0a-0000-4000-8000-000000000001"
    )

    assert _json(result)["formatted_name"] == "Jane Doe"
    assert sent[0].method == "GET"
    assert sent[0].url.path == "/pubapi/v1/notes/6f1c2e0a-0000-4000-8000-000000000001"


def test_comments_delete_asks_first(run: Callable[..., Runner]) -> None:
    invoke = run(lambda r: respond())

    declined, sent = invoke("comments", "delete", "c-1", input="n\n")
    assert declined.exit_code == 1
    assert "Delete comment c-1?" in declined.output
    assert not sent

    confirmed, sent = invoke("comments", "delete", "c-1", input="y\n")
    assert confirmed.exit_code == 0, confirmed.output
    assert sent[0].method == "DELETE"
    assert sent[0].url.path == "/pubapi/v1/notes/c-1"

    skipped, sent = invoke("comments", "delete", "c-1", "--yes")
    assert skipped.exit_code == 0, skipped.output
    assert skipped.stdout == ""
    assert "Deleted comment c-1" in skipped.stderr
    assert len(sent) == 2


# =============================================================================
# TEST: bookmarks
# =============================================================================


def test_bookmarks_create_by_path(run: Callable[..., Runner]) -> None:
    result, sent = run(lambda r: respond(BOOKMARK, status=201))(
        "bookmarks", "create", "/Shared/Docs"
    )

    output = _json(result)
    assert output["id"] == 5468
    assert output["creation_date"] == "2026-11-05T17:09:56Z"
    assert sent[0].method == "POST"
    assert sent[0].url.path == "/pubapi/v1/bookmarks"
    assert body(sent[0]) == {"path": "/Shared/Docs"}


def test_bookmarks_create_by_folder_id(run: Callable[..., Runner]) -> None:
    result, sent = run(lambda r: respond(BOOKMARK, status=201))(
        "bookmarks", "create", "--folder-id", "f-1"
    )

    assert _json(result)["folder_id"] == "f-1"
    assert body(sent[0]) == {"folder_id": "f-1"}


@pytest.mark.parametrize(
    "args", [(), ("/Shared/Docs", "--folder-id", "f-1")], ids=["neither", "both"]
)
def test_bookmarks_create_needs_exactly_one_target(
    run: Callable[..., Runner], args: tuple[str, ...]
) -> None:
    result, sent = run(lambda r: respond(BOOKMARK))("bookmarks", "create", *args)

    assert result.exit_code == 2
    assert "Give exactly one of PATH or --folder-id." in result.output
    assert not sent


def test_bookmarks_list(run: Callable[..., Runner]) -> None:
    page = {"bookmarks": [BOOKMARK], "offset": 10, "count": 1}
    result, sent = run(lambda r: respond(page))(
        "bookmarks", "list", "--offset", "10", "--count", "5"
    )

    assert [bookmark["path"] for bookmark in _json(result)] == ["/Shared/Docs"]
    assert sent[0].method == "GET"
    assert sent[0].url.path == "/pubapi/v1/bookmarks"
    assert dict(sent[0].url.params) == {"offset": "10", "count": "5"}


def test_bookmarks_get(run: Callable[..., Runner]) -> None:
    result, sent = run(lambda r: respond(BOOKMARK))("bookmarks", "get", "5468")

    assert _json(result)["path"] == "/Shared/Docs"
    assert sent[0].method == "GET"
    assert sent[0].url.path == "/pubapi/v1/bookmarks/5468"


def test_bookmarks_get_needs_a_numeric_id(run: Callable[..., Runner]) -> None:
    result, sent = run(lambda r: respond(BOOKMARK))("bookmarks", "get", "abc")

    assert result.exit_code == 2
    assert not sent


def test_bookmarks_delete_asks_first(run: Callable[..., Runner]) -> None:
    invoke = run(lambda r: respond())

    declined, sent = invoke("bookmarks", "delete", "5468", input="n\n")
    assert declined.exit_code == 1
    assert "Delete bookmark 5468?" in declined.output
    assert not sent

    confirmed, sent = invoke("bookmarks", "delete", "5468", "-y")
    assert confirmed.exit_code == 0, confirmed.output
    assert "Deleted bookmark 5468" in confirmed.stderr
    assert sent[0].method == "DELETE"
    assert sent[0].url.path == "/pubapi/v1/bookmarks/5468"
