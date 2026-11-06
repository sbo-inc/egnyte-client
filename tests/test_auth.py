"""
Coverage of the OAuth helpers.

The authorization URL, the code and password grants, token inspection, and
revocation.
"""

from collections.abc import Callable
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
from conftest import respond

from egnyte_client import build_authorization_url
from egnyte_client.async_client import AsyncEgnyteClient
from egnyte_client.client import EgnyteClient
from egnyte_client.schemas.auth import OAuthToken

CREDENTIALS = {"client_id": "id", "client_secret": "secret"}
PAIR = {
    "access_token": "new-access",
    "refresh_token": "new-refresh",
    "token_type": "Bearer",
    "expires_in": 2592000,
}
WHOAMI = {
    "clientId": "id",
    "username": "jdoe",
    "domain": "acme",
    "scopes": ["Egnyte.filesystem", "Egnyte.link"],
}


def _recording(
    response: Callable[[], httpx.Response],
) -> tuple[list[httpx.Request], Callable[[httpx.Request], httpx.Response]]:
    sent: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(request)
        return response()

    return sent, handler


def _form(request: httpx.Request) -> dict[str, list[str]]:
    return parse_qs(request.content.decode())


# =============================================================================
# TEST: build_authorization_url
# =============================================================================


def test_authorization_url_for_the_code_flow() -> None:
    url = build_authorization_url(
        "acme",
        "id",
        "https://app.test/callback",
        scope=["Egnyte.filesystem", "Egnyte.link"],
        state="xyz",
    )

    parts = urlsplit(url)
    assert f"{parts.scheme}://{parts.netloc}{parts.path}" == (
        "https://acme.egnyte.com/puboauth/token"
    )
    assert parse_qs(parts.query) == {
        "client_id": ["id"],
        "redirect_uri": ["https://app.test/callback"],
        "response_type": ["code"],
        "scope": ["Egnyte.filesystem Egnyte.link"],
        "state": ["xyz"],
    }
    # Spaces are percent-encoded, not turned into `+`.
    assert "scope=Egnyte.filesystem%20Egnyte.link" in url


def test_authorization_url_for_the_implicit_flow() -> None:
    url = build_authorization_url(
        "https://acme.egnyte.com/", "id", "https://app.test/cb", implicit=True
    )

    assert parse_qs(urlsplit(url).query) == {
        "client_id": ["id"],
        "redirect_uri": ["https://app.test/cb"],
        "response_type": ["token"],
    }


# =============================================================================
# TEST: grants
# =============================================================================


def test_exchange_authorization_code_adopts_the_pair(
    make_client: Callable[..., EgnyteClient],
) -> None:
    sent, handler = _recording(lambda: respond(PAIR))
    persisted: list[OAuthToken] = []
    client = make_client(
        handler, access_token=None, on_token_refresh=persisted.append, **CREDENTIALS
    )

    token = client.exchange_authorization_code("abc", "https://app.test/cb")

    assert str(sent[0].url) == "https://acme.egnyte.com/puboauth/token"
    assert _form(sent[0]) == {
        "client_id": ["id"],
        "client_secret": ["secret"],
        "grant_type": ["authorization_code"],
        "code": ["abc"],
        "redirect_uri": ["https://app.test/cb"],
    }
    assert token.access_token == "new-access"
    assert client.access_token == "new-access"
    assert client.refresh_token == "new-refresh"
    assert persisted == [token]


def test_login_with_password(make_client: Callable[..., EgnyteClient]) -> None:
    sent, handler = _recording(lambda: respond(PAIR))
    client = make_client(handler, access_token=None, **CREDENTIALS)

    client.login_with_password("jdoe", "pw", scope=["Egnyte.filesystem"])

    assert _form(sent[0]) == {
        "client_id": ["id"],
        "client_secret": ["secret"],
        "grant_type": ["password"],
        "username": ["jdoe"],
        "password": ["pw"],
        "scope": ["Egnyte.filesystem"],
    }
    assert client.access_token == "new-access"


async def test_async_login_with_password(
    make_async_client: Callable[..., AsyncEgnyteClient],
) -> None:
    sent, handler = _recording(lambda: respond(PAIR))
    client = make_async_client(handler, access_token=None, **CREDENTIALS)

    await client.login_with_password("jdoe", "pw")

    assert "scope" not in _form(sent[0])
    assert client.refresh_token == "new-refresh"


def test_grants_need_the_client_credentials(
    make_client: Callable[..., EgnyteClient],
) -> None:
    sent, handler = _recording(lambda: respond(PAIR))
    client = make_client(handler)

    with pytest.raises(ValueError, match="client ID and secret"):
        client.exchange_authorization_code("abc", "https://app.test/cb")
    with pytest.raises(ValueError, match="client ID and secret"):
        client.login_with_password("jdoe", "pw")
    assert not sent


def test_bad_password_raises(make_client: Callable[..., EgnyteClient]) -> None:
    _, handler = _recording(
        lambda: respond({"message": "INVALID_USERNAME_OR_PASSWORD"}, 403)
    )
    client = make_client(handler, **CREDENTIALS)

    with pytest.raises(Exception, match="INVALID_USERNAME_OR_PASSWORD"):
        client.login_with_password("jdoe", "wrong")
    assert client.access_token == "token"


# =============================================================================
# TEST: token inspection and revocation
# =============================================================================


def test_get_token_info(make_client: Callable[..., EgnyteClient]) -> None:
    sent, handler = _recording(lambda: respond(WHOAMI))
    client = make_client(handler)

    info = client.get_token_info()

    assert sent[0].url.path == "/pubapi/v1/whoami"
    assert info.client_id == "id"
    assert info.scopes == ["Egnyte.filesystem", "Egnyte.link"]


def test_revoke_own_token_forgets_the_pair(
    make_client: Callable[..., EgnyteClient],
) -> None:
    sent, handler = _recording(lambda: respond())
    client = make_client(handler, refresh_token="refresh", **CREDENTIALS)

    client.revoke_token()

    assert sent[0].method == "POST"
    assert sent[0].url.path == "/pubapi/v1/tokens/revoke"
    assert sent[0].headers["Content-Type"] == "application/x-www-form-urlencoded"
    assert _form(sent[0]) == {"token": ["token"], "client_secret": ["secret"]}
    assert client.access_token is None
    assert client.refresh_token is None


async def test_revoke_another_token_keeps_ours(
    make_async_client: Callable[..., AsyncEgnyteClient],
) -> None:
    sent, handler = _recording(lambda: respond())
    client = make_async_client(handler, **CREDENTIALS)

    await client.revoke_token("someone-elses")

    assert _form(sent[0])["token"] == ["someone-elses"]
    assert client.access_token == "token"


def test_revoke_needs_the_client_secret(
    make_client: Callable[..., EgnyteClient],
) -> None:
    sent, handler = _recording(lambda: respond())

    with pytest.raises(ValueError, match="client secret"):
        make_client(handler).revoke_token()
    with pytest.raises(ValueError, match="No token to revoke"):
        make_client(handler, access_token=None, **CREDENTIALS).revoke_token()
    assert not sent
