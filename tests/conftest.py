"""
Shared helpers for the unit tests.

Both clients are driven through `httpx.MockTransport`, so one handler function
can stand in for the API on either surface and the sync and async paths are
asserted against the same fixture data. Fixture bodies are shaped after live
Egnyte responses.
"""

import asyncio
import json
import time
from collections.abc import Callable, Mapping, Sequence
from typing import Any

import httpx
import pytest
from click.testing import CliRunner, Result

from egnyte_client.async_client import AsyncEgnyteClient
from egnyte_client.cli import cli
from egnyte_client.cli.context import ClientContext
from egnyte_client.client import EgnyteClient

DOMAIN = "acme"
BASE = "https://acme.egnyte.com"
API = f"{BASE}/pubapi"

Handler = Callable[[httpx.Request], httpx.Response]

FOLDER: dict[str, Any] = {
    "name": "Docs",
    "lastModified": 1793906961000,
    "uploaded": 1793906961689,
    "count": 0,
    "offset": 0,
    "path": "/Shared/Docs",
    "folder_id": "f-1",
    "total_count": 2,
    "parent_id": "f-0",
    "allow_links": True,
    "is_folder": True,
    "folders": [
        {
            "name": "Sub",
            "lastModified": 1793921036000,
            "uploaded": 1793921028754,
            "path": "/Shared/Docs/Sub",
            "folder_id": "f-2",
            "parent_id": "f-1",
            "is_folder": True,
        }
    ],
    "files": [
        {
            "checksum": "abc",
            "size": 13,
            "path": "/Shared/Docs/hello world.txt",
            "name": "hello world.txt",
            "locked": False,
            "is_folder": False,
            "entry_id": "e-1",
            "group_id": "g-1",
            "uploaded": 1793924565939,
            "last_modified": "Fri, 06 Nov 2026 00:22:45 GMT",
            "uploaded_by": "jdoe",
            "num_versions": 1,
            "parent_id": "f-1",
        }
    ],
}

FILE: dict[str, Any] = FOLDER["files"][0]

USER: dict[str, Any] = {
    "id": 8,
    "userName": "jdoe",
    "externalId": "x-1",
    "email": "jdoe@acme.test",
    "name": {"formatted": "Jane Doe", "familyName": "Doe", "givenName": "Jane"},
    "active": True,
    "locked": False,
    "emailChangePending": False,
    "authType": "sso",
    "userType": "admin",
    "role": None,
    "createdDate": "2026-11-05T19:29:22.000+0000",
    "lastActiveDate": None,
    "groups": [{"displayName": "Finance", "value": "grp-1"}],
    "isServiceAccount": False,
}

GROUP: dict[str, Any] = {
    "id": "grp-1",
    "displayName": "Finance",
    "members": [
        {
            "username": "jdoe",
            "date_added": "2026-11-05T16:23:25.000+0000",
            "value": 8,
            "display": "Jane Doe",
        }
    ],
    "owners": [],
    "schemas": ["urn:scim:schemas:core:1.0"],
}


# =============================================================================
# FUNCTIONS: Request and response helpers
# =============================================================================


def body(request: httpx.Request) -> Any:
    """
    Decode the JSON body a client sent.

    Returns:
        Any: The decoded request body.
    """
    return json.loads(request.content)


def respond(payload: Any = None, status: int = 200, **headers: str) -> httpx.Response:
    """
    Build a JSON response, or an empty one when `payload` is None.

    Returns:
        httpx.Response: The mocked response.
    """
    if payload is None:
        return httpx.Response(status, headers=headers)
    return httpx.Response(status, json=payload, headers=headers)


def scim(resources: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Wrap records in the SCIM page the v2 listings answer with.

    Returns:
        dict[str, Any]: The page.
    """
    return {
        "totalResults": len(resources),
        "itemsPerPage": len(resources),
        "startIndex": 1,
        "resources": resources,
    }


# =============================================================================
# FIXTURES: Environment isolation
# =============================================================================


EGNYTE_ENV_VARS = (
    "EGNYTE_DOMAIN",
    "EGNYTE_ACCESS_TOKEN",
    "EGNYTE_REFRESH_TOKEN",
    "EGNYTE_CLIENT_ID",
    "EGNYTE_CLIENT_SECRET",
    "EGNYTE_API_HEADERS",
    "EGNYTE_API_TIMEOUT",
    "EGNYTE_API_RETRIES",
    "EGNYTE_CLI_DISABLE",
)


@pytest.fixture(autouse=True)
def isolate_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Clear the `EGNYTE_*` variables so unit tests never read the real shell.

    Config falls back to the environment, so without this a developer with a
    token exported would see different behaviour from CI, and could reach a
    live domain.
    """
    for name in EGNYTE_ENV_VARS:
        monkeypatch.delenv(name, raising=False)


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    """
    Record rate-limit waits instead of sleeping through them.

    Returns:
        list[float]: Every delay the clients asked to wait, in order.
    """
    delays: list[float] = []

    async def fake_async_sleep(delay: float) -> None:
        delays.append(delay)

    monkeypatch.setattr(time, "sleep", delays.append)
    monkeypatch.setattr(asyncio, "sleep", fake_async_sleep)
    return delays


# =============================================================================
# FIXTURES: Mock-transport clients
# =============================================================================


@pytest.fixture
def make_client() -> Callable[..., EgnyteClient]:
    """
    Return a factory building an `EgnyteClient` backed by a handler.

    Returns:
        Callable[..., EgnyteClient]: The client factory.
    """

    def factory(handler: Handler, **kwargs: Any) -> EgnyteClient:
        kwargs.setdefault("domain", DOMAIN)
        kwargs.setdefault("access_token", "token")
        client = EgnyteClient(**kwargs)
        headers = client.http.headers
        client.close()
        client._http = httpx.Client(
            headers=headers, transport=httpx.MockTransport(handler)
        )
        return client

    return factory


@pytest.fixture
def make_async_client() -> Callable[..., AsyncEgnyteClient]:
    """
    Return a factory building an `AsyncEgnyteClient` backed by a handler.

    Returns:
        Callable[..., AsyncEgnyteClient]: The client factory.
    """

    def factory(handler: Handler, **kwargs: Any) -> AsyncEgnyteClient:
        kwargs.setdefault("domain", DOMAIN)
        kwargs.setdefault("access_token", "token")
        client = AsyncEgnyteClient(**kwargs)
        headers = client.http.headers
        client._http = httpx.AsyncClient(
            headers=headers, transport=httpx.MockTransport(handler)
        )
        return client

    return factory


# =============================================================================
# FIXTURES: CLI runner
# =============================================================================
#
# Commands run through the real `egnyte-client` root, so registration and the
# `EGNYTE_CLI_DISABLE` switch are exercised as in production, with the client's
# HTTP layer replaced by a mock transport that records every request.

Runner = Callable[..., tuple[Result, list[httpx.Request]]]


@pytest.fixture
def cli_runner() -> Callable[..., Runner]:
    """
    Return a factory building a runner that invokes the CLI against a handler.

    `prefix` is prepended to every invocation, so a module's tests can name
    only the subcommand (`prefix=("fs",)` turns `invoke("ls", "/Shared")` into
    `egnyte-client fs ls /Shared`).

    Returns:
        Callable[..., Runner]: Takes a handler and an optional prefix; the
            runner returns the Click result and every request sent.
    """

    def factory(handler: Handler, *, prefix: Sequence[str] = ()) -> Runner:
        sent: list[httpx.Request] = []

        def record(request: httpx.Request) -> httpx.Response:
            sent.append(request)
            return handler(request)

        def invoke(
            *args: str, input: str | None = None, env: Mapping[str, str] | None = None
        ) -> tuple[Result, list[httpx.Request]]:
            client = EgnyteClient(domain="acme", access_token="token")
            client.close()
            client._http = httpx.Client(transport=httpx.MockTransport(record))
            context = ClientContext()
            context._client = client

            result = CliRunner().invoke(
                cli, [*prefix, *args], input=input, env=env, obj=context
            )
            return result, sent

        return invoke

    return factory
