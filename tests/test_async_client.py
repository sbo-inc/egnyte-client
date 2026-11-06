import inspect
from collections.abc import Callable

import httpx
import pytest
from conftest import FOLDER, GROUP, body, respond

from egnyte_client.async_client import AsyncEgnyteClient
from egnyte_client.client import EgnyteClient

# =============================================================================
# TEST: parity with the sync client
# =============================================================================
#
# The two clients are meant to be the same surface with a different transport,
# so the check is mechanical: every public method exists on both, the async one
# is a coroutine function, and the signatures and docstrings match exactly.


def _public_methods(cls: type) -> set[str]:
    return {
        name
        for name, value in vars(cls).items()
        if not name.startswith("_") and inspect.isfunction(value)
    }


SYNC_ONLY = {"close"}
ASYNC_ONLY = {"aclose"}


def test_every_sync_method_has_an_async_twin() -> None:
    assert _public_methods(EgnyteClient) - SYNC_ONLY == (
        _public_methods(AsyncEgnyteClient) - ASYNC_ONLY
    )


@pytest.mark.parametrize("name", sorted(_public_methods(EgnyteClient) - SYNC_ONLY))
def test_async_methods_match_their_sync_twin(name: str) -> None:
    sync = getattr(EgnyteClient, name)
    asynchronous = getattr(AsyncEgnyteClient, name)

    assert inspect.iscoroutinefunction(asynchronous)
    assert inspect.signature(sync) == inspect.signature(asynchronous)
    assert sync.__doc__ == asynchronous.__doc__


def test_constructors_match() -> None:
    assert inspect.signature(EgnyteClient.__init__) == inspect.signature(
        AsyncEgnyteClient.__init__
    )


# =============================================================================
# TEST: calls
# =============================================================================


async def test_get_folder(make_async_client: Callable[..., AsyncEgnyteClient]) -> None:
    sent: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(request)
        return respond(FOLDER)

    async with make_async_client(handler) as client:
        folder = await client.get_folder("/Shared/Docs")

    assert sent[0].headers["Authorization"] == "Bearer token"
    assert folder.files[0].name == "hello world.txt"
    assert client.http.is_closed


async def test_upload_and_download(
    make_async_client: Callable[..., AsyncEgnyteClient],
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            return respond({"group_id": "g", "entry_id": "e", "path": "/Shared/a.txt"})
        return httpx.Response(200, content=b"payload")

    client = make_async_client(handler)

    assert (await client.upload_file("/Shared/a.txt", b"payload")).entry_id == "e"
    assert await client.download_file("/Shared/a.txt") == b"payload"


async def test_update_group(
    make_async_client: Callable[..., AsyncEgnyteClient],
) -> None:
    sent: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(request)
        return respond(GROUP)

    client = make_async_client(handler)
    await client.update_group("grp-1", add_member_ids=[9])

    assert body(sent[0]) == {"members": [{"value": 9}]}


def test_async_retries_only_the_connection_stage() -> None:
    client = AsyncEgnyteClient(domain="acme", retries=3)

    transport = client.http._transport
    assert isinstance(transport, httpx.AsyncHTTPTransport)
    assert transport._pool._retries == 3
