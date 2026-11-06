"""
Coverage of the shared transport behaviour on both clients.

Error mapping, the rate-limit retry, and the refresh-on-401 flow.
"""

from collections.abc import Callable
from urllib.parse import parse_qs

import httpx
import pytest
from conftest import BASE, respond

from egnyte_client.async_client import AsyncEgnyteClient
from egnyte_client.client import EgnyteClient
from egnyte_client.errors import (
    EgnyteAPIError,
    EgnyteAuthError,
    EgnyteConfigurationError,
    EgnyteConflictError,
    EgnyteError,
    EgnyteForbiddenError,
    EgnyteNotFoundError,
    EgnyteQuotaExceededError,
    EgnyteRateLimitError,
    EgnyteServerError,
    EgnyteValidationError,
)
from egnyte_client.schemas.auth import OAuthToken

USER_INFO = {"id": 8, "username": "jdoe"}

# =============================================================================
# TEST: error bodies
# =============================================================================


@pytest.mark.parametrize(
    ("status", "payload", "error_type", "message", "code"),
    [
        (404, {"errorMessage": "Not found"}, EgnyteNotFoundError, "Not found", None),
        (
            404,
            {"message": "Link does not exist"},
            EgnyteNotFoundError,
            "Link does not exist",
            None,
        ),
        (
            400,
            {
                "formErrors": [
                    {
                        "msg": "Group already exists.",
                        "code": "ERROR_DUPLICATE_GROUP_NAME",
                    }
                ]
            },
            EgnyteValidationError,
            "Group already exists.",
            "ERROR_DUPLICATE_GROUP_NAME",
        ),
        (
            400,
            {
                "formErrors": [],
                "inputErrors": {
                    "members": [
                        {
                            "code": "MEMBERS_FIELD_IS_REQUIRED",
                            "msg": "Members field is required.",
                        }
                    ]
                },
            },
            EgnyteValidationError,
            "members: Members field is required.",
            "MEMBERS_FIELD_IS_REQUIRED",
        ),
        (
            401,
            {
                "fault": {
                    "faultstring": "Invalid Access Token",
                    "detail": {
                        "errorcode": "keymanagement.service.invalid_access_token"
                    },
                }
            },
            EgnyteAuthError,
            "Invalid Access Token",
            "keymanagement.service.invalid_access_token",
        ),
        (
            409,
            {"Errors": [{"description": "User exists", "code": "409"}]},
            EgnyteConflictError,
            "User exists",
            "409",
        ),
    ],
)
def test_error_bodies_map_to_a_message_and_code(
    make_client: Callable[..., EgnyteClient],
    status: int,
    payload: dict[str, object],
    error_type: type[EgnyteAPIError],
    message: str,
    code: str | None,
) -> None:
    client = make_client(lambda request: respond(payload, status))

    with pytest.raises(error_type) as caught:
        client.get_user_info()

    assert type(caught.value) is error_type
    assert caught.value.status_code == status
    assert caught.value.message == message
    assert caught.value.code == code


def test_non_json_error_body_falls_back_to_text(
    make_client: Callable[..., EgnyteClient],
) -> None:
    client = make_client(lambda request: httpx.Response(502, text="Bad gateway"))

    with pytest.raises(EgnyteError, match="502: Bad gateway"):
        client.get_user_info()


@pytest.mark.parametrize(
    ("status", "error_type"),
    [
        (403, EgnyteForbiddenError),
        (500, EgnyteServerError),
        (503, EgnyteServerError),
        (418, EgnyteAPIError),
    ],
)
def test_other_statuses_map_to_their_class(
    make_client: Callable[..., EgnyteClient],
    status: int,
    error_type: type[EgnyteAPIError],
) -> None:
    client = make_client(lambda request: respond({"message": "nope"}, status))

    with pytest.raises(error_type) as caught:
        client.get_user_info()

    assert type(caught.value) is error_type
    assert isinstance(caught.value, EgnyteError)
    assert caught.value.response is not None
    assert caught.value.response.status_code == status


def test_rate_limit_error_reports_retry_after(
    make_client: Callable[..., EgnyteClient],
) -> None:
    client = make_client(
        lambda request: respond({}, 429, **{"Retry-After": "7"}),
        rate_limit_retries=0,
    )

    with pytest.raises(EgnyteRateLimitError) as caught:
        client.get_user_info()

    assert caught.value.retry_after == 7.0


def test_rate_limit_error_without_a_usable_retry_after(
    make_client: Callable[..., EgnyteClient],
) -> None:
    client = make_client(
        lambda request: respond(
            {}, 429, **{"Retry-After": "Wed, 21 Oct 2026 07:28:00 GMT"}
        ),
        rate_limit_retries=0,
    )

    with pytest.raises(EgnyteRateLimitError) as caught:
        client.get_user_info()

    assert caught.value.retry_after is None


def test_missing_configuration_is_an_egnyte_error_and_a_value_error() -> None:
    client = EgnyteClient(access_token="t")

    with pytest.raises(EgnyteConfigurationError) as caught:
        client.get_user_info()

    assert isinstance(caught.value, EgnyteError)
    assert isinstance(caught.value, ValueError)


# =============================================================================
# TEST: rate-limit retry
# =============================================================================


# The per-second refusal as Egnyte's gateway sent it live.
SPIKE_ARREST = {
    "fault": {
        "faultstring": "Spike arrest violation. Allowed rate : 2",
        "detail": {"errorcode": "policies.ratelimit.SpikeArrestViolation"},
    }
}
# Apigee's standard daily-quota refusal, which Egnyte's gateway uses.
QUOTA = {
    "fault": {
        "faultstring": "Rate limit quota violation. Quota limit  exceeded.",
        "detail": {"errorcode": "policies.ratelimit.QuotaViolation"},
    }
}


def _sequence(
    *responses: httpx.Response,
) -> tuple[Callable[[httpx.Request], httpx.Response], list[httpx.Request]]:
    sent: list[httpx.Request] = []
    pending = iter(responses)

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(request)
        return next(pending)

    return handler, sent


def _throttle_then_succeed(failures: int) -> Callable[[httpx.Request], httpx.Response]:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] <= failures:
            return respond(SPIKE_ARREST, 429, **{"Retry-After": "1"})
        return respond(USER_INFO)

    return handler


def test_429_is_retried_after_retry_after(
    make_client: Callable[..., EgnyteClient], no_sleep: list[float]
) -> None:
    client = make_client(_throttle_then_succeed(2))

    assert client.get_user_info().username == "jdoe"
    assert no_sleep == [1.0, 1.0]


async def test_async_429_is_retried_after_retry_after(
    make_async_client: Callable[..., AsyncEgnyteClient], no_sleep: list[float]
) -> None:
    client = make_async_client(_throttle_then_succeed(1))

    assert (await client.get_user_info()).username == "jdoe"
    assert no_sleep == [1.0]


def test_429_raises_once_retries_are_spent(
    make_client: Callable[..., EgnyteClient], no_sleep: list[float]
) -> None:
    client = make_client(_throttle_then_succeed(10), rate_limit_retries=2)

    with pytest.raises(EgnyteRateLimitError):
        client.get_user_info()
    assert len(no_sleep) == 2


def test_spike_arrest_without_retry_after_waits_one_second(
    make_client: Callable[..., EgnyteClient], no_sleep: list[float]
) -> None:
    handler, sent = _sequence(respond(SPIKE_ARREST, 429), respond(USER_INFO))

    make_client(handler).get_user_info()

    assert no_sleep == [1.0]
    assert len(sent) == 2


def test_daily_quota_raises_at_once(
    make_client: Callable[..., EgnyteClient], no_sleep: list[float]
) -> None:
    handler, sent = _sequence(respond(QUOTA, 429, **{"Retry-After": "1"}))

    with pytest.raises(EgnyteQuotaExceededError) as caught:
        make_client(handler).get_user_info()

    assert len(sent) == 1
    assert no_sleep == []
    assert isinstance(caught.value, EgnyteRateLimitError)
    assert caught.value.code == "policies.ratelimit.QuotaViolation"
    assert "daily API quota is used up" in str(caught.value)
    assert "00:00 UTC" in str(caught.value)


def test_daily_quota_is_recognized_by_its_message_alone(
    make_client: Callable[..., EgnyteClient], no_sleep: list[float]
) -> None:
    body = {
        "fault": {"faultstring": "Rate limit quota violation. Quota limit exceeded."}
    }
    handler, sent = _sequence(respond(body, 429))

    with pytest.raises(EgnyteQuotaExceededError):
        make_client(handler).get_user_info()

    assert len(sent) == 1


@pytest.mark.parametrize(
    "headers",
    [{"Retry-After": "3600"}, {}, {"Retry-After": "Wed, 21 Oct 2026 07:28:00 GMT"}],
    ids=["long-wait", "no-retry-after", "http-date"],
)
def test_unidentified_429_without_a_short_wait_raises_at_once(
    make_client: Callable[..., EgnyteClient],
    no_sleep: list[float],
    headers: dict[str, str],
) -> None:
    handler, sent = _sequence(respond({"message": "Too many requests"}, 429, **headers))

    with pytest.raises(EgnyteRateLimitError) as caught:
        make_client(handler).get_user_info()

    assert type(caught.value) is EgnyteRateLimitError
    assert len(sent) == 1
    assert no_sleep == []


def test_spike_arrest_asking_for_a_long_wait_raises_at_once(
    make_client: Callable[..., EgnyteClient], no_sleep: list[float]
) -> None:
    handler, sent = _sequence(respond(SPIKE_ARREST, 429, **{"Retry-After": "60"}))

    with pytest.raises(EgnyteRateLimitError):
        make_client(handler).get_user_info()

    assert len(sent) == 1
    assert no_sleep == []


def test_unidentified_429_with_a_short_wait_is_retried(
    make_client: Callable[..., EgnyteClient], no_sleep: list[float]
) -> None:
    handler, sent = _sequence(
        respond({"message": "Too many requests"}, 429, **{"Retry-After": "2"}),
        respond(USER_INFO),
    )

    make_client(handler).get_user_info()

    assert no_sleep == [2.0]
    assert len(sent) == 2


async def test_async_daily_quota_raises_at_once(
    make_async_client: Callable[..., AsyncEgnyteClient], no_sleep: list[float]
) -> None:
    handler, sent = _sequence(respond(QUOTA, 429))

    with pytest.raises(EgnyteQuotaExceededError):
        await make_async_client(handler).get_user_info()

    assert len(sent) == 1
    assert no_sleep == []


async def test_async_unidentified_429_without_retry_after_raises_at_once(
    make_async_client: Callable[..., AsyncEgnyteClient], no_sleep: list[float]
) -> None:
    handler, sent = _sequence(respond({}, 429))

    with pytest.raises(EgnyteRateLimitError):
        await make_async_client(handler).get_user_info()

    assert len(sent) == 1


# =============================================================================
# TEST: refresh on 401
# =============================================================================


def expired() -> httpx.Response:
    return respond({"fault": {"faultstring": "Invalid Access Token"}}, 401)


NEW_PAIR = {
    "access_token": "new-access",
    "refresh_token": "new-refresh",
    "token_type": "Bearer",
    "expires_in": 2592000,
}
REFRESHABLE = {
    "refresh_token": "old-refresh",
    "client_id": "id",
    "client_secret": "secret",
}


def _expiring_api(
    log: list[httpx.Request],
) -> Callable[[httpx.Request], httpx.Response]:
    def handler(request: httpx.Request) -> httpx.Response:
        log.append(request)
        if request.url.path == "/puboauth/token":
            return respond(NEW_PAIR)
        if request.headers["Authorization"] == "Bearer new-access":
            return respond(USER_INFO)
        return expired()

    return handler


def test_401_refreshes_once_and_retries(
    make_client: Callable[..., EgnyteClient],
) -> None:
    sent: list[httpx.Request] = []
    persisted: list[OAuthToken] = []
    client = make_client(
        _expiring_api(sent), on_token_refresh=persisted.append, **REFRESHABLE
    )

    assert client.get_user_info().username == "jdoe"

    assert [r.url.path for r in sent] == [
        "/pubapi/v1/userinfo",
        "/puboauth/token",
        "/pubapi/v1/userinfo",
    ]
    assert str(sent[1].url) == f"{BASE}/puboauth/token"
    assert parse_qs(sent[1].content.decode()) == {
        "client_id": ["id"],
        "client_secret": ["secret"],
        "grant_type": ["refresh_token"],
        "refresh_token": ["old-refresh"],
    }
    assert client.access_token == "new-access"
    assert client.refresh_token == "new-refresh"
    assert [token.access_token for token in persisted] == ["new-access"]


async def test_async_401_refreshes_once_and_retries(
    make_async_client: Callable[..., AsyncEgnyteClient],
) -> None:
    sent: list[httpx.Request] = []
    client = make_async_client(_expiring_api(sent), **REFRESHABLE)

    assert (await client.get_user_info()).username == "jdoe"
    assert client.refresh_token == "new-refresh"
    assert len(sent) == 3


def test_401_without_refresh_credentials_raises(
    make_client: Callable[..., EgnyteClient],
) -> None:
    client = make_client(lambda request: expired())

    with pytest.raises(EgnyteAuthError):
        client.get_user_info()


def test_a_second_401_after_refreshing_raises(
    make_client: Callable[..., EgnyteClient],
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/puboauth/token":
            return respond(NEW_PAIR)
        return expired()

    client = make_client(handler, **REFRESHABLE)

    with pytest.raises(EgnyteAuthError):
        client.get_user_info()


def test_refresh_without_credentials_is_refused() -> None:
    client = EgnyteClient(domain="acme", access_token="t")

    with pytest.raises(ValueError, match="No Egnyte refresh token"):
        client.refresh_access_token()

    client.refresh_token = "r"
    with pytest.raises(ValueError, match="client ID and secret"):
        client.refresh_access_token()


def test_failed_refresh_raises(make_client: Callable[..., EgnyteClient]) -> None:
    client = make_client(
        lambda request: respond({"message": "Invalid Refresh Token"}, 400),
        **REFRESHABLE,
    )

    with pytest.raises(EgnyteError, match="Invalid Refresh Token"):
        client.refresh_access_token()
