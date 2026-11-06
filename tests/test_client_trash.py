from collections.abc import Callable
from datetime import UTC, datetime, timedelta, timezone
from typing import Any

import httpx
import pytest
from conftest import body, respond

from egnyte_client.async_client import AsyncEgnyteClient
from egnyte_client.client import EgnyteClient

# Shaped after a live v2 trash page; IDs are base64 strings.
TRASHED_FOLDER: dict[str, Any] = {
    "id": "Zi0xfDE3OTM5Mjc2NzY0Mjd8Zm9sZGVy",
    "type": "folder",
    "path": "/Private/jdoe/Old",
    "deleted_by": "Jane Doe",
    "delete_date": "2026-11-06T01:14:36Z",
    "purge_date": "2026-12-07T00:00:00Z",
    "name": "Old",
}
TRASHED_FILE: dict[str, Any] = {
    "id": "Zy0xfDE3OTM5Mjc2NzUwMDR8ZmlsZQ==",
    "type": "file",
    "path": "/Private/jdoe/Old/notes.txt",
    "deleted_by": "Jane Doe",
    "size": 10240,
    "owner": {
        "id": 8,
        "username": "jdoe",
        "firstName": "Jane",
        "lastName": "Doe",
        "email": "jdoe@acme.test",
        "status": "ACTIVE",
        "_self": {"url": "/rest/public/1.0/users/8", "linkedResources": {}},
        "typeName": "admin",
    },
    "delete_date": "2026-11-06T01:14:35Z",
    "purge_date": "2026-12-07T00:00:00Z",
    "last_modified": "2026-11-06T01:14:28Z",
    "name": "notes.txt",
    "data_retention_info": {
        "retention": "GRACE_PERIOD",
        "earliest_expiry": "1796515200",
        "is_retained": True,
    },
}
PAGE: dict[str, Any] = {
    "count": 2,
    "offset": 0,
    "has_more": True,
    "items": [TRASHED_FOLDER, TRASHED_FILE],
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
# TEST: listing
# =============================================================================


def test_list_trash_parses_the_page(make_client: Callable[..., EgnyteClient]) -> None:
    client, sent = _client(make_client, respond(PAGE))

    page = client.list_trash()

    assert sent[0].method == "GET"
    assert sent[0].url.path == "/pubapi/v2/fs/trash"
    assert not sent[0].url.params
    assert page.has_more is True
    folder, file = page.items
    assert folder.type == "folder"
    assert folder.owner is None
    assert folder.delete_date == datetime(2026, 11, 6, 1, 14, 36, tzinfo=UTC)
    assert file.id == "Zy0xfDE3OTM5Mjc2NzUwMDR8ZmlsZQ=="
    assert file.size == 10240
    assert file.owner is not None
    assert file.owner.username == "jdoe"
    assert file.owner.first_name == "Jane"
    assert file.owner.type_name == "admin"
    assert file.data_retention_info is not None
    assert file.data_retention_info.is_retained is True
    assert file.data_retention_info.earliest_expiry == datetime(2026, 12, 6, tzinfo=UTC)


def test_list_trash_sends_every_filter(
    make_client: Callable[..., EgnyteClient],
) -> None:
    client, sent = _client(make_client, respond(PAGE))

    client.list_trash(
        sort_by="purge_date",
        sort_direction="asc",
        offset=50,
        count=25,
        deleted_by="Jane Doe",
        start_date=datetime(
            2026, 4, 18, 18, 11, 38, tzinfo=timezone(timedelta(hours=2))
        ),
        end_date=datetime(2026, 5, 1),
    )

    assert dict(sent[0].url.params) == {
        "sort_by": "purge_date",
        "sort_direction": "asc",
        "offset": "50",
        "count": "25",
        "deletedBy": "Jane Doe",
        # Converted to UTC; naive means UTC.
        "startDate": "2026-04-18T16:11:38Z",
        "endDate": "2026-05-01T00:00:00Z",
    }


@pytest.mark.parametrize(
    "filters",
    [
        {"deleted_by": "Jane Doe"},
        {"start_date": datetime(2026, 1, 1)},
        {"deleted_by": "Jane Doe", "end_date": datetime(2026, 1, 1)},
    ],
)
def test_list_trash_filters_need_both_dates(
    make_client: Callable[..., EgnyteClient], filters: dict[str, Any]
) -> None:
    client, sent = _client(make_client, respond(PAGE))

    with pytest.raises(ValueError, match="start_date and end_date"):
        client.list_trash(**filters)
    assert not sent


def test_count_trash(make_client: Callable[..., EgnyteClient]) -> None:
    client, sent = _client(make_client, respond({"totalCount": 13}))

    assert client.count_trash() == 13
    assert sent[0].method == "GET"
    assert sent[0].url.path == "/pubapi/v2/fs/trash/totalcount"


# =============================================================================
# TEST: restore and purge
# =============================================================================


@pytest.mark.parametrize(
    ("method", "action"),
    [("restore_trash_items", "RESTORE"), ("purge_trash_items", "PURGE")],
)
def test_full_success_reports_every_item(
    make_client: Callable[..., EgnyteClient], method: str, action: str
) -> None:
    # Egnyte answers a full success with 200 and an empty body.
    client, sent = _client(make_client, respond())

    statuses = getattr(client, method)(["t-1", "t-2"])

    assert sent[0].method == "POST"
    assert sent[0].url.path == "/pubapi/v1/fs/trash"
    assert body(sent[0]) == {"action": action, "ids": ["t-1", "t-2"]}
    assert [(s.id, s.code, s.succeeded) for s in statuses] == [
        ("t-1", 200, True),
        ("t-2", 200, True),
    ]


def test_partial_failure_reports_each_status(
    make_client: Callable[..., EgnyteClient],
) -> None:
    multi_status = {
        "resources": [
            {"id": "t-1", "code": "200"},
            {"id": "t-2", "code": "404", "descriptions": "Item not found in trash"},
        ]
    }
    client, _ = _client(make_client, respond(multi_status, 207))

    statuses = client.purge_trash_items(["t-1", "t-2"])

    assert statuses[0].succeeded
    assert statuses[1].code == 404
    assert not statuses[1].succeeded
    assert statuses[1].description == "Item not found in trash"


@pytest.mark.parametrize("item_ids", [[], [f"t-{n}" for n in range(11)]])
def test_trash_actions_take_one_to_ten_ids(
    make_client: Callable[..., EgnyteClient], item_ids: list[str]
) -> None:
    client, sent = _client(make_client, respond())

    with pytest.raises(ValueError):
        client.restore_trash_items(item_ids)
    client.restore_trash_items([f"t-{n}" for n in range(10)])
    assert len(sent) == 1


# =============================================================================
# TEST: async
# =============================================================================


async def test_async_list_and_restore(
    make_async_client: Callable[..., AsyncEgnyteClient],
) -> None:
    sent: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(request)
        if request.method == "GET":
            return respond(PAGE)
        return respond()

    client = make_async_client(handler)

    page = await client.list_trash(count=2)
    statuses = await client.restore_trash_items([item.id for item in page.items])

    assert dict(sent[0].url.params) == {"count": "2"}
    assert body(sent[1])["ids"] == [TRASHED_FOLDER["id"], TRASHED_FILE["id"]]
    assert all(status.succeeded for status in statuses)
