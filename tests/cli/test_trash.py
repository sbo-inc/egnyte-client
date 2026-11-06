"""
Coverage of the `trash` command group against a mock-transport client.

Each command is asserted on the request it sends and the output it renders;
the client behind it is the real one, so argument wiring is what is tested.
"""

import json
from collections.abc import Callable
from typing import Any

import httpx
import pytest
from click.testing import Result
from conftest import body, respond

Handler = Callable[[httpx.Request], httpx.Response]
Runner = Callable[..., tuple[Result, list[httpx.Request]]]

TRASHED_FILE: dict[str, Any] = {
    "id": "Zy0xfDE3OTM5Mjc2NzUwMDR8ZmlsZQ==",
    "type": "file",
    "path": "/Private/jdoe/Old/notes.txt",
    "deleted_by": "Jane Doe",
    "size": 10240,
    "delete_date": "2026-11-06T01:14:35Z",
    "purge_date": "2026-12-07T00:00:00Z",
    "name": "notes.txt",
}
PAGE: dict[str, Any] = {
    "count": 1,
    "offset": 0,
    "has_more": True,
    "items": [TRASHED_FILE],
}
PARTIAL: dict[str, Any] = {
    "resources": [
        {"id": "t-1", "code": 200},
        {"id": "t-2", "code": 404, "descriptions": "Item not found in trash"},
    ]
}


@pytest.fixture
def run(cli_runner: Callable[..., Runner]) -> Callable[..., Runner]:
    """
    Return a factory for a runner invoking the CLI `trash` group against a handler.

    Returns:
        Callable[..., Runner]: Takes a handler, gives back the runner.
    """
    return lambda handler: cli_runner(handler, prefix=("trash",))


def _json(result: Result) -> Any:
    assert result.exit_code == 0, result.output
    return json.loads(result.stdout)


# =============================================================================
# TEST: list and count
# =============================================================================


def test_list(run: Callable[[Handler], Runner]) -> None:
    result, sent = run(lambda r: respond(PAGE))("list")

    output = _json(result)
    assert output["has_more"] is True
    assert output["items"][0]["name"] == "notes.txt"
    assert sent[0].method == "GET"
    assert sent[0].url.path == "/pubapi/v2/fs/trash"
    assert not sent[0].url.params


def test_list_with_every_filter(run: Callable[[Handler], Runner]) -> None:
    result, sent = run(lambda r: respond(PAGE))(
        "list",
        "--sort-by",
        "purge_date",
        "--sort-direction",
        "asc",
        "--deleted-by",
        "Doe",
        "--start-date",
        "2026-11-01",
        "--end-date",
        "2026-11-06T12:30:00",
        "--offset",
        "50",
        "--count",
        "25",
    )

    assert _json(result)["items"][0]["id"] == TRASHED_FILE["id"]
    assert dict(sent[0].url.params) == {
        "sort_by": "purge_date",
        "sort_direction": "asc",
        "offset": "50",
        "count": "25",
        "deletedBy": "Doe",
        "startDate": "2026-11-01T00:00:00Z",
        "endDate": "2026-11-06T12:30:00Z",
    }


@pytest.mark.parametrize(
    "args",
    [
        ["--deleted-by", "Doe"],
        ["--start-date", "2026-11-01"],
        ["--deleted-by", "Doe", "--end-date", "2026-11-06"],
    ],
)
def test_list_filters_need_both_dates(
    run: Callable[[Handler], Runner], args: list[str]
) -> None:
    result, sent = run(lambda r: respond(PAGE))("list", *args)

    assert result.exit_code == 2
    assert "Give both --start-date and --end-date" in result.output
    assert not sent


def test_list_rejects_an_unknown_sort(run: Callable[[Handler], Runner]) -> None:
    result, sent = run(lambda r: respond(PAGE))("list", "--sort-by", "size")

    assert result.exit_code == 2
    assert not sent


def test_count(run: Callable[[Handler], Runner]) -> None:
    result, sent = run(lambda r: respond({"totalCount": 13}))("count")

    assert result.exit_code == 0, result.output
    assert result.stdout == "13\n"
    assert sent[0].method == "GET"
    assert sent[0].url.path == "/pubapi/v2/fs/trash/totalcount"


# =============================================================================
# TEST: restore
# =============================================================================


def test_restore(run: Callable[[Handler], Runner]) -> None:
    result, sent = run(lambda r: respond())("restore", "t-1", "t-2")

    assert _json(result) == [
        {"id": "t-1", "code": 200, "description": None},
        {"id": "t-2", "code": 200, "description": None},
    ]
    assert sent[0].method == "POST"
    assert sent[0].url.path == "/pubapi/v1/fs/trash"
    assert body(sent[0]) == {"action": "RESTORE", "ids": ["t-1", "t-2"]}


def test_restore_partial_failure_exits_non_zero(
    run: Callable[[Handler], Runner],
) -> None:
    result, sent = run(lambda r: respond(PARTIAL, 207))("restore", "t-1", "t-2")

    assert result.exit_code == 1
    statuses = json.loads(result.stdout)
    assert statuses[1] == {
        "id": "t-2",
        "code": 404,
        "description": "Item not found in trash",
    }
    assert "1 of 2 items were not restored: t-2" in result.stderr
    assert len(sent) == 1


def test_restore_needs_an_id(run: Callable[[Handler], Runner]) -> None:
    result, sent = run(lambda r: respond())("restore")

    assert result.exit_code == 2
    assert not sent


def test_restore_refuses_more_than_ten(run: Callable[[Handler], Runner]) -> None:
    ids = [f"t-{n}" for n in range(11)]

    result, sent = run(lambda r: respond())("restore", *ids)

    assert result.exit_code == 2
    assert "at most 10 trash item IDs" in result.output
    assert not sent


# =============================================================================
# TEST: purge
# =============================================================================


def test_purge_asks_first(run: Callable[[Handler], Runner]) -> None:
    invoke = run(lambda r: respond())

    declined, sent = invoke("purge", "t-1", "t-2", input="n\n")
    assert declined.exit_code == 1
    assert "Permanently delete trash item(s) t-1, t-2?" in declined.output
    assert "cannot be undone" in declined.output
    assert not sent

    confirmed, sent = invoke("purge", "t-1", "t-2", "--yes")
    assert [status["code"] for status in _json(confirmed)] == [200, 200]
    assert sent[0].method == "POST"
    assert sent[0].url.path == "/pubapi/v1/fs/trash"
    assert body(sent[0]) == {"action": "PURGE", "ids": ["t-1", "t-2"]}


def test_purge_partial_failure_exits_non_zero(
    run: Callable[[Handler], Runner],
) -> None:
    result, _ = run(lambda r: respond(PARTIAL, 207))("purge", "t-1", "t-2", "-y")

    assert result.exit_code == 1
    assert "1 of 2 items were not purged: t-2" in result.stderr


def test_purge_refuses_more_than_ten_before_asking(
    run: Callable[[Handler], Runner],
) -> None:
    ids = [f"t-{n}" for n in range(11)]

    result, sent = run(lambda r: respond())("purge", *ids)

    assert result.exit_code == 2
    assert "Permanently delete" not in result.output
    assert not sent
