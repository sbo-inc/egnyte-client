import logging
import os
from collections.abc import Callable, Mapping

import httpx

from egnyte_client.errors import (
    EgnyteAPIError,
    EgnyteConfigurationError,
    rate_limit_kind,
    retry_after,
)
from egnyte_client.operations.generic import Operation, QueryValue
from egnyte_client.schemas.auth import OAuthToken

# The package logger. A library only attaches a NullHandler: whether, where,
# and at what level its records appear is the application's choice. Each
# request is logged at DEBUG; retries and token refreshes at INFO.
logger = logging.getLogger("egnyte_client")
logger.addHandler(logging.NullHandler())

# Default (connect, read) timeout in seconds applied to every request. Without
# one, a stalled connection or an unresponsive server would block the caller
# far longer than any Egnyte call legitimately takes.
DEFAULT_TIMEOUT: tuple[float, float] = (5.0, 30.0)

# How many times a call refused by the per-second rate limit (HTTP 429) is
# retried after waiting out its `Retry-After`. The gateway refuses a call
# before it reaches Egnyte, so a retried write is never applied twice.
DEFAULT_RATE_LIMIT_RETRIES = 5

# Wait used when a per-second refusal carries no usable `Retry-After`.
DEFAULT_RETRY_AFTER = 1.0

# The longest `Retry-After` the client waits out. A 429 asking for longer is
# not the per-second limit, and blocking the caller for it would not help.
MAX_RETRY_AFTER = 5.0

type TokenCallback = Callable[[OAuthToken], None]

# =============================================================================
# FUNCTION: normalize_domain
# =============================================================================


def normalize_domain(domain: str) -> str:
    """
    Turn a domain given in any common form into the base URL.

    `acme`, `acme.egnyte.com`, and `https://acme.egnyte.com/` all become
    `https://acme.egnyte.com`. A host with a dot is used as given, which keeps
    custom and regional hosts working.

    Returns:
        str: The base URL, with scheme and without a trailing slash.
    """
    value = domain.strip().rstrip("/")
    if not value:
        raise EgnyteConfigurationError("No Egnyte domain provided")
    if "://" not in value:
        host = value if "." in value else f"{value}.egnyte.com"
        value = f"https://{host}"
    return value


# =============================================================================
# CLASS: BaseEgnyteClient
# =============================================================================


class BaseEgnyteClient:
    """
    Transport-agnostic half of the Egnyte clients.

    Holds everything that does not depend on whether the underlying HTTP call
    is awaited: configuration and its environment fallbacks, the bearer and
    refresh tokens, request construction, the rate-limit retry policy, and the
    error check. `EgnyteClient` and `AsyncEgnyteClient` add only the transport.
    """

    domain: str | None
    access_token: str | None
    refresh_token: str | None
    client_id: str | None
    client_secret: str | None
    timeout: float | tuple[float, float] | None
    rate_limit_retries: int

    def __init__(
        self,
        domain: str | None = None,
        access_token: str | None = None,
        *,
        refresh_token: str | None = None,
        client_id: str | None = None,
        client_secret: str | None = None,
        on_token_refresh: TokenCallback | None = None,
        timeout: float | tuple[float, float] | None = DEFAULT_TIMEOUT,
        rate_limit_retries: int = DEFAULT_RATE_LIMIT_RETRIES,
    ) -> None:
        """
        Resolve configuration, falling back to the `EGNYTE_*` environment.

        Args:
            domain: The Egnyte domain, as `acme`, `acme.egnyte.com`, or a URL (Environment: `EGNYTE_DOMAIN`)
            access_token: OAuth bearer token (Environment: `EGNYTE_ACCESS_TOKEN`)
            refresh_token: OAuth refresh token (Environment: `EGNYTE_REFRESH_TOKEN`)
            client_id: The API key, needed to refresh (Environment: `EGNYTE_CLIENT_ID`)
            client_secret: The API secret, needed to refresh (Environment: `EGNYTE_CLIENT_SECRET`)
            on_token_refresh: Called with the new token pair after a refresh
            timeout: Per-request timeout in seconds applied to every call.
            rate_limit_retries: Retries for calls refused with HTTP 429.
        """
        self.domain = domain or os.environ.get("EGNYTE_DOMAIN")
        self.access_token = access_token or os.environ.get("EGNYTE_ACCESS_TOKEN")
        self.refresh_token = refresh_token or os.environ.get("EGNYTE_REFRESH_TOKEN")
        self.client_id = client_id or os.environ.get("EGNYTE_CLIENT_ID")
        self.client_secret = client_secret or os.environ.get("EGNYTE_CLIENT_SECRET")
        self.on_token_refresh = on_token_refresh
        self.timeout = timeout
        self.rate_limit_retries = rate_limit_retries

    # -------------------------------------------------------------------------
    # PROPERTY: base_url
    # -------------------------------------------------------------------------

    @property
    def base_url(self) -> str:
        """
        The domain's base URL, such as `https://acme.egnyte.com`.

        Returns:
            str: The base URL.
        """
        if not self.domain:
            raise EgnyteConfigurationError("No Egnyte domain provided")
        return normalize_domain(self.domain)

    # -------------------------------------------------------------------------
    # METHOD: _request_timeout
    # -------------------------------------------------------------------------

    def _request_timeout(self) -> httpx.Timeout | None:
        """
        Translate the configured timeout into the httpx representation.

        A `(connect, read)` pair carries over from the `requests` convention;
        the write and pool stages inherit the read and connect budgets
        respectively, since neither has a meaningful budget of its own here.

        Returns:
            httpx.Timeout | None: The per-request timeout, or None to disable.
        """
        timeout = self.timeout
        if timeout is None:
            return None
        if isinstance(timeout, tuple):
            connect, read = timeout
            return httpx.Timeout(connect=connect, read=read, write=read, pool=connect)
        return httpx.Timeout(timeout)

    # -------------------------------------------------------------------------
    # METHOD: _build_request
    # -------------------------------------------------------------------------

    def _build_request(
        self, http: httpx.Client | httpx.AsyncClient, operation: Operation[object]
    ) -> httpx.Request:
        """
        Build the HTTP request for an operation, with the current bearer token.

        The token is read at build time, so a request retried after a refresh
        carries the new one.

        Returns:
            httpx.Request: The request, ready to send.
        """
        url = f"{self.base_url}/pubapi{operation.path}"
        if not self.access_token:
            raise EgnyteConfigurationError("No Egnyte access token provided")

        headers = {"Authorization": f"Bearer {self.access_token}"}
        content = operation.content
        if operation.body is not None:
            headers["Content-Type"] = "application/json"
            content = operation.body.model_dump_json(
                exclude_none=True, by_alias=True
            ).encode()
        headers.update(operation.headers)

        params: dict[str, QueryValue] = {
            key: value for key, value in operation.params.items() if value is not None
        }
        return http.build_request(
            operation.method,
            url,
            params=params,
            content=content,
            headers=headers,
            timeout=self._request_timeout(),
        )

    # -------------------------------------------------------------------------
    # METHOD: _build_token_request
    # -------------------------------------------------------------------------

    def _build_token_request(
        self, http: httpx.Client | httpx.AsyncClient, grant: Mapping[str, str]
    ) -> httpx.Request:
        """
        Build a POST to `/puboauth/token` for one grant, with the client credentials.

        Returns:
            httpx.Request: The token request.
        """
        if not self.client_id or not self.client_secret:
            raise EgnyteConfigurationError(
                "Token requests need the client ID and secret"
            )

        return http.build_request(
            "POST",
            f"{self.base_url}/puboauth/token",
            data={
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                **grant,
            },
            timeout=self._request_timeout(),
        )

    # -------------------------------------------------------------------------
    # METHOD: _refresh_grant
    # -------------------------------------------------------------------------

    def _refresh_grant(self) -> dict[str, str]:
        """
        The refresh-token grant, raising if there is no refresh token.

        Returns:
            dict[str, str]: The grant fields.
        """
        if not self.refresh_token:
            raise EgnyteConfigurationError("No Egnyte refresh token provided")
        return {"grant_type": "refresh_token", "refresh_token": self.refresh_token}

    # -------------------------------------------------------------------------
    # METHOD: _can_refresh
    # -------------------------------------------------------------------------

    def _can_refresh(self) -> bool:
        """
        Whether a 401 can be answered by refreshing the token.

        Returns:
            bool: True when the refresh token, client ID, and secret are all set.
        """
        return bool(self.refresh_token and self.client_id and self.client_secret)

    # -------------------------------------------------------------------------
    # METHOD: _apply_token
    # -------------------------------------------------------------------------

    def _apply_token(self, response: httpx.Response) -> OAuthToken:
        """
        Check a token response, adopt the new pair, and notify the callback.

        Egnyte rotates the refresh token on every refresh, so the callback is
        how a caller persists the pair the next process will need. Every grant
        (refresh, authorization code, password) ends here.

        Returns:
            OAuthToken: The new token pair.
        """
        self._raise_for_status(response)
        token = OAuthToken.model_validate_json(response.content)
        self.access_token = token.access_token
        if token.refresh_token:
            self.refresh_token = token.refresh_token
        logger.info("access token updated")
        if self.on_token_refresh is not None:
            self.on_token_refresh(token)
        return token

    # -------------------------------------------------------------------------
    # METHOD: _retry_delay
    # -------------------------------------------------------------------------

    def _retry_delay(self, response: httpx.Response, attempt: int) -> float | None:
        """
        How long to wait before retrying a response, or None not to retry.

        Only the per-second limit is retried: a 429 whose fault names spike
        arrest, or any 429 asking for a wait of at most `MAX_RETRY_AFTER`
        seconds, for up to `rate_limit_retries` attempts. The daily quota, a
        longer wait, or an unidentified 429 with no `Retry-After` raises at
        once, as waiting seconds would not get the call through.

        Returns:
            float | None: Seconds to wait, or None.
        """
        if response.status_code != 429 or attempt >= self.rate_limit_retries:
            return None
        kind = rate_limit_kind(response)
        wait = retry_after(response)
        if kind == "quota" or (wait is not None and wait > MAX_RETRY_AFTER):
            return None
        if wait is None:
            if kind != "spike_arrest":
                return None
            wait = DEFAULT_RETRY_AFTER
        delay = wait
        logger.info(
            "rate limited; retrying in %.1fs (attempt %d of %d)",
            delay,
            attempt + 1,
            self.rate_limit_retries,
        )
        return delay

    # -------------------------------------------------------------------------
    # METHOD: _raise_for_status
    # -------------------------------------------------------------------------

    def _raise_for_status(
        self, response: httpx.Response, accept: frozenset[int] = frozenset()
    ) -> None:
        """
        Raise the matching `EgnyteAPIError` when a response is not a success.

        Statuses in `accept` pass through to the operation's parser, as the
        303 a finished audit job answers with does.
        """
        logger.debug(
            "%s %s -> %d",
            response.request.method,
            response.request.url.path,
            response.status_code,
        )
        if not response.is_success and response.status_code not in accept:
            raise EgnyteAPIError.from_response(response)
