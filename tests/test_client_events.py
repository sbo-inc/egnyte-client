from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import httpx
from conftest import respond

from egnyte_client.async_client import AsyncEgnyteClient
from egnyte_client.client import EgnyteClient

CURSOR = {
    "latest_event_id": 52,
    "oldest_event_id": 1,
    "timestamp": "2026-11-06T01:10:16.000Z",
}

# The event shapes below follow live v2 events, anonymized.
COPY_EVENT: dict[str, Any] = {
    "id": 23,
    "timestamp": "2026-11-06T00:22:50.000Z",
    "action_source": "PublicAPI",
    "actor": 8,
    "type": "file_system",
    "action": "copy",
    "object_detail": "https://acme.egnyte.com/pubapi/v1/fs/Shared/Docs/copy.txt",
    "data": {
        "target_path": "/Shared/Docs/copy.txt",
        "target_id": "e-2",
        "target_group_id": "g-2",
        "source_path": "/Shared/Docs/hello world.txt",
        "source_id": "e-1",
        "source_group_id": "g-1",
        "is_folder": False,
    },
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

# Shaped after the docs; no note event was observed live.
NOTE_EVENT: dict[str, Any] = {
    "id": 27,
    "timestamp": "2026-11-06T00:24:00.000Z",
    "action_source": "WebUI",
    "actor": 8,
    "type": "note",
    "action": "create",
    "object_detail": "https://acme.egnyte.com/pubapi/v1/notes/n-1",
    "data": {"note_id": "n-1"},
}

# Live: `eventTypeSpecificAttributes` is a sibling of `data`, not inside it.
PERMISSION_EVENT: dict[str, Any] = {
    "id": 28,
    "timestamp": "2026-11-05T21:52:38.000Z",
    "action_source": "System",
    "actor": 9,
    "type": "permission_change",
    "action": "permission_change",
    "data": {"target_path": "/Shared/Templates", "is_folder": False},
    "eventTypeSpecificAttributes": {
        "changeGroupEvents": [],
        "changePermissionEvent": {
            "changedPermissions": [
                {"action": "ADD", "entry": {"subject": "/group/grp-1", "priv": "READ"}},
                {
                    "action": "DELETE",
                    "entry": {"subject": "/group/grp-1", "priv": "NONE"},
                },
            ]
        },
        "changeContext": None,
        "targetFolderId": "f-9",
        "groupChange": False,
        "futureField": 1,
    },
}

PAGE: dict[str, Any] = {
    "latest_id": 28,
    "oldest_id": 23,
    "count": 4,
    "events": [COPY_EVENT, DELETE_EVENT, NOTE_EVENT, PERMISSION_EVENT],
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
# TEST: get_event_cursor
# =============================================================================


def test_get_event_cursor(make_client: Callable[..., EgnyteClient]) -> None:
    client, sent = _client(make_client, respond(CURSOR))

    cursor = client.get_event_cursor()

    assert sent[0].method == "GET"
    assert sent[0].url.path == "/pubapi/v1/events/cursor"
    assert cursor.latest_event_id == 52
    assert cursor.oldest_event_id == 1
    assert cursor.timestamp == datetime(2026, 11, 6, 1, 10, 16, tzinfo=UTC)


# =============================================================================
# TEST: list_events
# =============================================================================


def test_list_events_sends_only_the_cursor_by_default(
    make_client: Callable[..., EgnyteClient],
) -> None:
    client, sent = _client(make_client, respond(PAGE))

    client.list_events(22)

    assert sent[0].method == "GET"
    assert sent[0].url.path == "/pubapi/v2/events"
    assert dict(sent[0].url.params) == {"id": "22"}


def test_list_events_sends_every_filter(
    make_client: Callable[..., EgnyteClient],
) -> None:
    client, sent = _client(make_client, respond(PAGE))

    client.list_events(
        22,
        count=100,
        filter_by_folder="Shared/Docs/",
        filter_by_types=["file_system", "permission_change"],
        suppress="app",
        reverse=True,
    )

    assert dict(sent[0].url.params) == {
        "id": "22",
        "folder": "/Shared/Docs",
        "suppress": "app",
        "type": "file_system|permission_change",
        "count": "100",
        "reverse": "1",
    }


def test_list_events_parses_each_event_type(
    make_client: Callable[..., EgnyteClient],
) -> None:
    client, _ = _client(make_client, respond(PAGE))

    page = client.list_events(22)

    assert (page.latest_id, page.oldest_id, page.count) == (28, 23, 4)
    copy, delete, note, permission = page.events

    assert copy.type == "file_system"
    assert copy.data.source_path == "/Shared/Docs/hello world.txt"
    assert copy.data.target_group_id == "g-2"
    assert copy.timestamp == datetime(2026, 11, 6, 0, 22, 50, tzinfo=UTC)
    assert copy.event_type_specific_attributes is None

    assert delete.object_detail is None
    assert delete.data.target_id is None

    assert note.data.note_id == "n-1"

    attributes = permission.event_type_specific_attributes
    assert attributes is not None
    assert attributes.target_folder_id == "f-9"
    assert attributes.change_context is None
    assert attributes.change_permission_event is not None
    changes = attributes.change_permission_event.changed_permissions
    assert [(change.action, change.entry.priv) for change in changes] == [
        ("ADD", "READ"),
        ("DELETE", "NONE"),
    ]


def test_list_events_with_nothing_new_keeps_the_cursor(
    make_client: Callable[..., EgnyteClient],
) -> None:
    client, _ = _client(make_client, respond(status=204))

    page = client.list_events(52)

    assert page.latest_id == 52
    assert page.events == []
    assert page.count == 0


# =============================================================================
# TEST: async
# =============================================================================


async def test_async_events(
    make_async_client: Callable[..., AsyncEgnyteClient],
) -> None:
    sent: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(request)
        if request.url.path == "/pubapi/v1/events/cursor":
            return respond(CURSOR)
        return respond(status=204)

    client = make_async_client(handler)

    cursor = await client.get_event_cursor()
    page = await client.list_events(cursor.latest_event_id, filter_by_types=["note"])

    assert page.latest_id == 52
    assert dict(sent[1].url.params) == {"id": "52", "type": "note"}
