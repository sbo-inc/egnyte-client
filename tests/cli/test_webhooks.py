"""
Coverage of the `webhooks` commands against a mock-transport client.

Each command is asserted on the request it sends and the output it renders.
The `auth_header` secret must never reach the output, whichever command
handled it.
"""

import json
from collections.abc import Callable
from typing import Any, get_args

import httpx
import pytest
from click.testing import Result
from conftest import body, respond

from egnyte_client.cli.commands import webhooks
from egnyte_client.schemas.webhook import WebhookEventType

Runner = Callable[..., tuple[Result, list[httpx.Request]]]

WEBHOOK_ID = "c9ac0519-284a-4bee-9574-30ae7891e5dc"
SECRET = "Bearer secret-token-12345"
URL = "https://hooks.acme.test/egnyte"

WEBHOOK: dict[str, Any] = {
    "webhookId": WEBHOOK_ID,
    "expires": 2100000000,
    "status": "enabled",
}

DETAILS: dict[str, Any] = {
    **WEBHOOK,
    "eventType": ["fs:add_file", "fs:delete_file"],
    "path": "/Shared/Documents/Invoices,/Shared/Documents/Samples",
    "authHeader": SECRET,
    "url": URL,
}


@pytest.fixture(autouse=True)
def no_secret_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Keep a developer's exported auth header out of the commands under test.
    """
    monkeypatch.delenv(webhooks.AUTH_HEADER_ENV_VAR, raising=False)


@pytest.fixture
def run(cli_runner: Callable[..., Runner]) -> Callable[..., Runner]:
    """
    Return a factory for a runner invoking the CLI `webhooks` group against a handler.

    Returns:
        Callable[..., Runner]: Takes a handler, gives back the runner.
    """
    return lambda handler: cli_runner(handler, prefix=("webhooks",))


def _json(result: Result) -> Any:
    assert result.exit_code == 0, result.output
    assert SECRET not in result.output
    return json.loads(result.stdout)


def test_event_choices_match_the_client_literal() -> None:
    assert webhooks.EVENT_TYPES.choices == get_args(WebhookEventType.__value__)


def test_list(run: Callable[..., Runner]) -> None:
    result, sent = run(lambda r: respond([WEBHOOK]))("list")

    assert _json(result) == [
        {
            "webhook_id": WEBHOOK_ID,
            "status": "enabled",
            "expires": "2036-07-18T13:20:00Z",
        }
    ]
    assert sent[0].method == "GET"
    assert sent[0].url.path == "/pubapi/v1/webhooks"


def test_get_hides_the_auth_header(run: Callable[..., Runner]) -> None:
    result, sent = run(lambda r: respond(DETAILS))("get", WEBHOOK_ID)

    output = _json(result)
    assert "auth_header" not in output
    assert output["url"] == URL
    assert output["event_types"] == ["fs:add_file", "fs:delete_file"]
    assert output["paths"] == [
        "/Shared/Documents/Invoices",
        "/Shared/Documents/Samples",
    ]
    assert sent[0].method == "GET"
    assert sent[0].url.path == f"/pubapi/v1/webhooks/{WEBHOOK_ID}/details"


def test_create(run: Callable[..., Runner]) -> None:
    # Egnyte answers a create with the webhook only; an echoed header must
    # still not be printed.
    result, sent = run(lambda r: respond({**WEBHOOK, "authHeader": SECRET}))(
        "create",
        URL,
        "--event",
        "fs:add_file",
        "--event",
        "link:*",
        "--path",
        "/Shared/Invoices",
        "--path",
        "/Shared/Samples",
        "--auth-header",
        SECRET,
    )

    assert _json(result)["webhook_id"] == WEBHOOK_ID
    assert sent[0].method == "POST"
    assert sent[0].url.path == "/pubapi/v1/webhooks"
    assert body(sent[0]) == {
        "url": URL,
        "eventType": ["fs:add_file", "link:*"],
        "path": "/Shared/Invoices,/Shared/Samples",
        "authHeader": SECRET,
    }


def test_create_reads_the_auth_header_from_the_environment(
    run: Callable[..., Runner],
) -> None:
    result, sent = run(lambda r: respond(WEBHOOK))(
        "create", URL, env={webhooks.AUTH_HEADER_ENV_VAR: SECRET}
    )

    assert _json(result)["status"] == "enabled"
    assert body(sent[0]) == {"url": URL, "authHeader": SECRET}


def test_create_rejects_an_unknown_event(run: Callable[..., Runner]) -> None:
    result, sent = run(lambda r: respond(WEBHOOK))(
        "create", URL, "--event", "fs:everything"
    )

    assert result.exit_code == 2
    assert "Invalid value for '--event'" in result.stderr
    assert not sent


def test_update(run: Callable[..., Runner]) -> None:
    result, sent = run(lambda r: respond())(
        "update",
        WEBHOOK_ID,
        URL,
        "--event",
        "fs:*",
        "--path",
        "/Shared/Invoices",
        "--auth-header",
        SECRET,
        "--disable",
    )

    assert result.exit_code == 0, result.output
    assert result.stdout == ""
    assert SECRET not in result.output
    assert f"Updated webhook {WEBHOOK_ID}" in result.stderr
    assert sent[0].method == "PUT"
    assert sent[0].url.path == f"/pubapi/v1/webhooks/{WEBHOOK_ID}"
    assert body(sent[0]) == {
        "url": URL,
        "eventType": ["fs:*"],
        "path": "/Shared/Invoices",
        "authHeader": SECRET,
        "status": "disabled",
    }


def test_update_with_only_the_url(run: Callable[..., Runner]) -> None:
    result, sent = run(lambda r: respond())("update", WEBHOOK_ID, URL)

    assert result.exit_code == 0, result.output
    assert body(sent[0]) == {"url": URL}


def test_status(run: Callable[..., Runner]) -> None:
    result, sent = run(lambda r: respond(WEBHOOK))("status", WEBHOOK_ID)

    assert _json(result)["status"] == "enabled"
    assert sent[0].method == "GET"
    assert sent[0].url.path == f"/pubapi/v1/webhooks/{WEBHOOK_ID}/status"


@pytest.mark.parametrize(
    ("command", "status"), [("enable", "enabled"), ("disable", "disabled")]
)
def test_enable_and_disable(
    run: Callable[..., Runner], command: str, status: str
) -> None:
    result, sent = run(lambda r: respond({**WEBHOOK, "status": status}))(
        command, WEBHOOK_ID
    )

    assert _json(result)["status"] == status
    assert sent[0].method == "POST"
    assert sent[0].url.path == f"/pubapi/v1/webhooks/{WEBHOOK_ID}/status"
    assert body(sent[0]) == {"status": status}


def test_delete_asks_first(run: Callable[..., Runner]) -> None:
    invoke = run(lambda r: respond())

    declined, sent = invoke("delete", WEBHOOK_ID, input="n\n")
    assert declined.exit_code == 1
    assert f"Delete webhook {WEBHOOK_ID}?" in declined.output
    assert not sent

    confirmed, sent = invoke("delete", WEBHOOK_ID, "--yes")
    assert confirmed.exit_code == 0, confirmed.output
    assert f"Deleted webhook {WEBHOOK_ID}" in confirmed.stderr
    assert sent[0].method == "DELETE"
    assert sent[0].url.path == f"/pubapi/v1/webhooks/{WEBHOOK_ID}"
