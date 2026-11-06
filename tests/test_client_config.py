from collections.abc import Callable
from typing import Any

import httpx
import pytest
from conftest import API, respond

from egnyte_client.client import DEFAULT_TIMEOUT, EgnyteClient
from egnyte_client.transport import normalize_domain

# =============================================================================
# TEST: domain resolution
# =============================================================================


@pytest.mark.parametrize(
    ("domain", "expected"),
    [
        ("acme", "https://acme.egnyte.com"),
        ("acme.egnyte.com", "https://acme.egnyte.com"),
        ("https://acme.egnyte.com/", "https://acme.egnyte.com"),
        (" acme ", "https://acme.egnyte.com"),
        ("files.acme.test", "https://files.acme.test"),
        ("http://localhost:8080", "http://localhost:8080"),
    ],
)
def test_normalize_domain(domain: str, expected: str) -> None:
    assert normalize_domain(domain) == expected


def test_blank_domain_is_refused() -> None:
    with pytest.raises(ValueError, match="No Egnyte domain"):
        normalize_domain("  ")


def test_reads_configuration_from_the_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("EGNYTE_DOMAIN", "env-domain")
    monkeypatch.setenv("EGNYTE_ACCESS_TOKEN", "env-token")
    monkeypatch.setenv("EGNYTE_REFRESH_TOKEN", "env-refresh")
    monkeypatch.setenv("EGNYTE_CLIENT_ID", "env-id")
    monkeypatch.setenv("EGNYTE_CLIENT_SECRET", "env-secret")

    client = EgnyteClient()

    assert client.base_url == "https://env-domain.egnyte.com"
    assert client.access_token == "env-token"
    assert client.refresh_token == "env-refresh"
    assert client.client_id == "env-id"
    assert client.client_secret == "env-secret"


def test_arguments_override_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EGNYTE_DOMAIN", "env-domain")

    assert EgnyteClient(domain="arg").base_url == "https://arg.egnyte.com"


def test_missing_domain_raises_on_first_call() -> None:
    client = EgnyteClient(access_token="t")

    with pytest.raises(ValueError, match="No Egnyte domain"):
        client.get_user_info()


def test_missing_token_raises_before_sending(
    make_client: Callable[..., EgnyteClient],
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("no request should be sent")

    client = make_client(handler, access_token=None)

    with pytest.raises(ValueError, match="No Egnyte access token"):
        client.get_user_info()


# =============================================================================
# TEST: request construction
# =============================================================================


def test_bearer_token_and_extra_headers_ride_along(
    make_client: Callable[..., EgnyteClient],
) -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return respond({"id": 1, "username": "jdoe"})

    client = make_client(handler, headers={"X-Trace": "abc"})
    client.get_user_info()

    assert str(seen[0].url) == f"{API}/v1/userinfo"
    assert seen[0].headers["Authorization"] == "Bearer token"
    assert seen[0].headers["X-Trace"] == "abc"


# =============================================================================
# TEST: timeout and retries
# =============================================================================


def test_default_timeout() -> None:
    assert EgnyteClient(domain="acme").timeout == DEFAULT_TIMEOUT


def test_timeout_tuple_maps_onto_the_httpx_stages() -> None:
    client = EgnyteClient(domain="acme", timeout=(1.0, 2.0))

    assert client._request_timeout() == httpx.Timeout(
        connect=1.0, read=2.0, write=2.0, pool=1.0
    )


def test_timeout_none_disables() -> None:
    assert EgnyteClient(domain="acme", timeout=None)._request_timeout() is None


def test_request_forwards_a_scalar_timeout(
    make_client: Callable[..., EgnyteClient],
) -> None:
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(request.extensions["timeout"])
        return respond({"id": 1, "username": "jdoe"})

    make_client(handler, timeout=12.5).get_user_info()

    assert captured == {"connect": 12.5, "read": 12.5, "write": 12.5, "pool": 12.5}


def test_no_connection_retries_by_default() -> None:
    client = EgnyteClient(domain="acme")

    assert client.http._transport._pool._retries == 0


def test_int_retries_only_the_connection_stage() -> None:
    client = EgnyteClient(domain="acme", retries=3)

    transport = client.http._transport
    assert isinstance(transport, httpx.HTTPTransport)
    assert transport._pool._retries == 3


def test_context_manager_closes_the_pool() -> None:
    with EgnyteClient(domain="acme") as client:
        pass

    assert client.http.is_closed
