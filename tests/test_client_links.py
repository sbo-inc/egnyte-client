from collections.abc import Callable
from datetime import UTC, date, datetime

import httpx
import pytest
from conftest import body, respond

from egnyte_client.client import EgnyteClient

CREATED = {
    "links": [
        {"id": "BK9q", "recipients": [], "url": "https://acme.egnyte.com/dl/BK9q"}
    ],
    "path": "/Shared/a.txt",
    "type": "file",
    "accessibility": "domain",
    "notify": False,
    "link_to_current": False,
    "creation_date": "2026-11-06",
    "send_mail": False,
    "copy_me": False,
}

DETAILS = {
    "path": "/Shared/a.txt",
    "type": "file",
    "accessibility": "domain",
    "recipients": [],
    "notify": False,
    "id": "BK9q",
    "protection": "NONE",
    "link_to_current": False,
    "creation_date": "2026-11-06T00:22:54+0000",
    "created_by": "jdoe",
    "url": "https://acme.egnyte.com/dl/BK9q",
    "resource_id": "g-1",
}


def _client(
    make_client: Callable[..., EgnyteClient], response: httpx.Response
) -> tuple[EgnyteClient, list[httpx.Request]]:
    sent: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(request)
        return response

    return make_client(handler), sent


def test_create_link_lifts_the_issued_url(
    make_client: Callable[..., EgnyteClient],
) -> None:
    client, sent = _client(make_client, respond(CREATED))

    link = client.create_link(
        "Shared/a.txt", "file", accessibility="domain", expiry_date=date(2026, 12, 1)
    )

    assert sent[0].method == "POST"
    assert sent[0].url.path == "/pubapi/v1/links"
    assert body(sent[0]) == {
        "path": "/Shared/a.txt",
        "type": "file",
        "accessibility": "domain",
        "expiry_date": "2026-12-01",
    }
    assert link.id == "BK9q"
    assert link.url == "https://acme.egnyte.com/dl/BK9q"
    assert link.creation_date == datetime(2026, 11, 6)


def test_create_link_uses_wire_names(make_client: Callable[..., EgnyteClient]) -> None:
    client, sent = _client(make_client, respond(CREATED))

    client.create_link("/Shared", "folder", use_default_settings=True)

    assert body(sent[0])["useDefaultSettings"] is True


def test_create_link_refuses_two_expiries(
    make_client: Callable[..., EgnyteClient],
) -> None:
    client, _ = _client(make_client, respond(CREATED))

    with pytest.raises(ValueError, match="cannot be combined"):
        client.create_link(
            "/Shared/a.txt", "file", expiry_date=date(2026, 1, 1), expiry_clicks=3
        )


def test_get_link(make_client: Callable[..., EgnyteClient]) -> None:
    client, sent = _client(make_client, respond(DETAILS))

    link = client.get_link("BK9q")

    assert sent[0].url.path == "/pubapi/v1/links/BK9q"
    assert link.created_by == "jdoe"
    assert link.protection == "NONE"


def test_list_links_uses_v2(make_client: Callable[..., EgnyteClient]) -> None:
    client, sent = _client(make_client, respond({"links": [DETAILS], "count": 1}))

    links = client.list_links(
        filter_by_path="/Shared/a.txt",
        filter_by_type="file",
        filter_by_created_after=datetime(2026, 1, 1, tzinfo=UTC),
        count=10,
    )

    assert sent[0].url.path == "/pubapi/v2/links"
    assert dict(sent[0].url.params) == {
        "path": "/Shared/a.txt",
        "type": "file",
        "created_after": "2026-01-01T00:00:00+00:00",
        "count": "10",
    }
    assert [link.resource_id for link in links] == ["g-1"]


def test_delete_link(make_client: Callable[..., EgnyteClient]) -> None:
    client, sent = _client(make_client, respond())

    assert client.delete_link("BK9q") is None
    assert sent[0].method == "DELETE"
    assert sent[0].url.path == "/pubapi/v1/links/BK9q"
