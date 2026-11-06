from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import httpx
import pytest
from conftest import body, respond

from egnyte_client.async_client import AsyncEgnyteClient
from egnyte_client.client import EgnyteClient
from egnyte_client.operations.webhook import verify_webhook_authorization
from egnyte_client.schemas.webhook import WebhookDelivery

# Shaped after the documented examples; `expires` is in epoch seconds.
WEBHOOK: dict[str, Any] = {
    "webhookId": "c9ac0519-284a-4bee-9574-30ae7891e5dc",
    "expires": 2100000000,
    "status": "enabled",
}

DETAILS: dict[str, Any] = {
    **WEBHOOK,
    "eventType": ["fs:add_file", "fs:delete_file"],
    "path": "/Shared/Documents/Invoices,/Shared/Documents/Samples",
    "authHeader": "Bearer secret-token-12345",
    "url": "https://hooks.acme.test/egnyte",
}

DELIVERY: dict[str, Any] = {
    "data": [
        {
            "eventId": "ev-1",
            "domain": "acme",
            "timestamp": 1793906961000,
            "user": {
                "id": 8,
                "displayName": "Jane Doe",
                "username": "jdoe",
                "email": "jdoe@acme.test",
                "clientIdHash": "0a1b2c",
            },
            "actionSource": "PublicAPI",
            "eventType": "fs:add_file",
            "webhookId": WEBHOOK["webhookId"],
            "data": {"targetPath": "/Shared/Docs/a.txt", "isFolder": False},
        }
    ]
}

EXPIRES = datetime(2036, 7, 18, 13, 20, tzinfo=UTC)
URL = "https://hooks.acme.test/egnyte"


def _client(
    make_client: Callable[..., EgnyteClient], response: httpx.Response
) -> tuple[EgnyteClient, list[httpx.Request]]:
    sent: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(request)
        return response

    return make_client(handler), sent


# =============================================================================
# TEST: webhooks
# =============================================================================


def test_create_webhook(make_client: Callable[..., EgnyteClient]) -> None:
    client, sent = _client(make_client, respond(WEBHOOK, 201))

    webhook = client.create_webhook(
        URL,
        event_types=["fs:add_file", "link:*"],
        paths=["/Shared/Documents/", "Shared/Samples"],
        auth_header="Bearer s3cret",
    )

    assert sent[0].method == "POST"
    assert sent[0].url.path == "/pubapi/v1/webhooks"
    assert body(sent[0]) == {
        "url": URL,
        "eventType": ["fs:add_file", "link:*"],
        "path": "/Shared/Documents,/Shared/Samples",
        "authHeader": "Bearer s3cret",
    }
    assert webhook.webhook_id == WEBHOOK["webhookId"]
    assert webhook.status == "enabled"
    assert webhook.expires == EXPIRES


def test_create_webhook_defaults_to_everything(
    make_client: Callable[..., EgnyteClient],
) -> None:
    client, sent = _client(make_client, respond(WEBHOOK, 201))

    client.create_webhook(URL)

    assert body(sent[0]) == {"url": URL}


@pytest.mark.parametrize(
    ("kwargs", "match"),
    [
        ({"paths": [f"/Shared/{n}" for n in range(101)]}, "at most 100"),
        ({"paths": ["/Shared/a,b"]}, "comma"),
        ({"event_types": []}, "at least one event type"),
    ],
)
def test_create_webhook_refusals(
    make_client: Callable[..., EgnyteClient], kwargs: dict[str, Any], match: str
) -> None:
    client, sent = _client(make_client, respond(WEBHOOK, 201))

    with pytest.raises(ValueError, match=match):
        client.create_webhook(URL, **kwargs)
    assert sent == []


def test_list_webhooks(make_client: Callable[..., EgnyteClient]) -> None:
    client, sent = _client(
        make_client,
        respond([WEBHOOK, {**WEBHOOK, "webhookId": "w-2", "status": "disabled"}]),
    )

    webhooks = client.list_webhooks()

    assert sent[0].method == "GET"
    assert sent[0].url.path == "/pubapi/v1/webhooks"
    assert [webhook.status for webhook in webhooks] == ["enabled", "disabled"]


def test_get_webhook(make_client: Callable[..., EgnyteClient]) -> None:
    client, sent = _client(make_client, respond(DETAILS))

    webhook = client.get_webhook("w 1")

    assert sent[0].url.raw_path == b"/pubapi/v1/webhooks/w%201/details"
    assert webhook.url == URL
    assert webhook.event_types == ["fs:add_file", "fs:delete_file"]
    assert webhook.paths == ["/Shared/Documents/Invoices", "/Shared/Documents/Samples"]
    assert webhook.auth_header == "Bearer secret-token-12345"
    assert webhook.expires == EXPIRES


def test_get_webhook_without_filters(
    make_client: Callable[..., EgnyteClient],
) -> None:
    client, _ = _client(make_client, respond({**WEBHOOK, "url": URL}))

    webhook = client.get_webhook("w-1")

    assert webhook.paths == []
    assert webhook.event_types == []


def test_webhook_status(make_client: Callable[..., EgnyteClient]) -> None:
    client, sent = _client(make_client, respond({**WEBHOOK, "status": "disabled"}))

    assert client.get_webhook_status("w-1").status == "disabled"
    assert client.set_webhook_status("w-1", False).status == "disabled"
    client.set_webhook_status("w-1", True)

    assert sent[0].method == "GET"
    assert sent[0].url.path == "/pubapi/v1/webhooks/w-1/status"
    assert sent[1].method == "POST"
    assert sent[1].url.path == "/pubapi/v1/webhooks/w-1/status"
    assert body(sent[1]) == {"status": "disabled"}
    assert body(sent[2]) == {"status": "enabled"}


def test_update_webhook(make_client: Callable[..., EgnyteClient]) -> None:
    client, sent = _client(make_client, respond())

    result = client.update_webhook(
        "w-1",
        URL,
        event_types=["fs:add_file"],
        paths=["/Shared/Documents/Invoices"],
        auth_header="Bearer s3cret",
        enabled=True,
    )

    assert result is None
    assert sent[0].method == "PUT"
    assert sent[0].url.path == "/pubapi/v1/webhooks/w-1"
    assert body(sent[0]) == {
        "url": URL,
        "eventType": ["fs:add_file"],
        "path": "/Shared/Documents/Invoices",
        "authHeader": "Bearer s3cret",
        "status": "enabled",
    }


def test_delete_webhook(make_client: Callable[..., EgnyteClient]) -> None:
    client, sent = _client(make_client, respond(status=204))

    client.delete_webhook("w-1")

    assert sent[0].method == "DELETE"
    assert sent[0].url.path == "/pubapi/v1/webhooks/w-1"


# =============================================================================
# TEST: deliveries
# =============================================================================


def test_verify_webhook_authorization() -> None:
    assert verify_webhook_authorization("Bearer s3cret", "Bearer s3cret")
    assert not verify_webhook_authorization("Bearer other", "Bearer s3cret")
    assert not verify_webhook_authorization(None, "Bearer s3cret")
    assert not verify_webhook_authorization("", "")


def test_parse_webhook_delivery() -> None:
    delivery = WebhookDelivery.model_validate(DELIVERY)

    event = delivery.data[0]
    assert event.event_id == "ev-1"
    assert event.event_type == "fs:add_file"
    assert event.timestamp == datetime(2026, 11, 5, 19, 29, 21, tzinfo=UTC)
    assert event.user is not None
    assert event.user.username == "jdoe"
    assert event.user.client_id_hash == "0a1b2c"
    assert event.data["targetPath"] == "/Shared/Docs/a.txt"
    assert event.custom_properties == {}


# =============================================================================
# TEST: async
# =============================================================================


async def test_async_webhooks(
    make_async_client: Callable[..., AsyncEgnyteClient],
) -> None:
    sent: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(request)
        if request.method == "POST":
            return respond(WEBHOOK, 201)
        if request.method == "DELETE":
            return respond(status=204)
        return respond(DETAILS)

    async with make_async_client(handler) as client:
        created = await client.create_webhook(URL, event_types=["fs:*"])
        details = await client.get_webhook(created.webhook_id)
        await client.delete_webhook(created.webhook_id)

    assert body(sent[0]) == {"url": URL, "eventType": ["fs:*"]}
    assert details.paths[1] == "/Shared/Documents/Samples"
    assert sent[2].method == "DELETE"
