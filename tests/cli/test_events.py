"""
Coverage of the `events` commands against a mock-transport client.
"""

import json
from collections.abc import Callable
from typing import Any, get_args

import httpx
import pytest
from click.testing import Result
from conftest import respond

from egnyte_client.cli.commands import events
from egnyte_client.schemas.event import EventSuppress, EventType

Runner = Callable[..., tuple[Result, list[httpx.Request]]]

CURSOR = {
    "latest_event_id": 52,
    "oldest_event_id": 1,
    "timestamp": "2026-11-06T01:10:16.000Z",
}

DELETE_EVENT: dict[str, Any] = {
    "id": 26,
    "timestamp": "2026-11-06T00:23:01.000Z",
    "action_source": "PublicAPI",
    "actor": 8,
    "type": "file_system",
    "action": "delete",
    "data": {
        "target_path": "/Shared/Docs/copy.txt",
        "target_group_id": "g-2",
        "is_folder": False,
    },
}

PAGE: dict[str, Any] = {
    "latest_id": 26,
    "oldest_id": 26,
    "count": 1,
    "events": [DELETE_EVENT],
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


def test_choices_match_the_client() -> None:
    assert events.EVENT_TYPES.choices == get_args(EventType.__value__)
    assert events.SUPPRESS.choices == get_args(EventSuppress.__value__)


def test_cursor(run: Callable[..., Runner]) -> None:
    result, sent = run(lambda r: respond(CURSOR))("events", "cursor")

    assert _json(result) == {
        "latest_event_id": 52,
        "oldest_event_id": 1,
        "timestamp": "2026-11-06T01:10:16Z",
    }
    assert sent[0].method == "GET"
    assert sent[0].url.path == "/pubapi/v1/events/cursor"


def test_list_sends_every_filter(run: Callable[..., Runner]) -> None:
    result, sent = run(lambda r: respond(PAGE))(
        "events",
        "list",
        "20",
        "--count",
        "10",
        "--folder",
        "Shared/Docs/",
        "--type",
        "file_system",
        "--type",
        "permission_change",
        "--suppress",
        "app",
        "--reverse",
    )

    output = _json(result)
    assert output["latest_id"] == 26
    assert output["events"][0]["data"]["target_path"] == "/Shared/Docs/copy.txt"
    assert sent[0].method == "GET"
    assert sent[0].url.path == "/pubapi/v2/events"
    assert dict(sent[0].url.params) == {
        "id": "20",
        "count": "10",
        "folder": "/Shared/Docs",
        "type": "file_system|permission_change",
        "suppress": "app",
        "reverse": "1",
    }


def test_list_sends_only_the_cursor_by_default(run: Callable[..., Runner]) -> None:
    result, sent = run(lambda r: respond(PAGE))("events", "list", "20")

    assert _json(result)["count"] == 1
    assert dict(sent[0].url.params) == {"id": "20"}


def test_list_prints_an_empty_page_to_poll_from(run: Callable[..., Runner]) -> None:
    result, _ = run(lambda r: httpx.Response(204))("events", "list", "52")

    assert _json(result) == {
        "latest_id": 52,
        "oldest_id": None,
        "count": 0,
        "events": [],
    }


@pytest.mark.parametrize(
    "args",
    [("--count", "0"), ("--count", "101"), ("--type", "login"), ("--suppress", "x")],
)
def test_list_rejects_bad_options(
    run: Callable[..., Runner], args: tuple[str, ...]
) -> None:
    result, sent = run(lambda r: respond(PAGE))("events", "list", "20", *args)

    assert result.exit_code == 2
    assert not sent
