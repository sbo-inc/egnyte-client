"""
The exceptions this client raises.

Every error the package raises is an `EgnyteError`. A failed API call raises
an `EgnyteAPIError` carrying the status, Egnyte's message and code, and the
response. Subclasses exist for the statuses Egnyte uses, so a caller can catch
the one case it knows how to handle - a missing path, an expired token, the
rate limit - without matching on a number.
"""

import json
from typing import cast

import httpx

# =============================================================================
# CLASS: EgnyteError
# =============================================================================


class EgnyteError(Exception):
    """
    Base class for every error raised by this package.
    """


# =============================================================================
# CLASS: EgnyteConfigurationError
# =============================================================================


class EgnyteConfigurationError(EgnyteError, ValueError):
    """
    Raised when the client lacks the domain, token, or credentials a call needs.

    Configuration is checked on use rather than on construction, so building a
    client never fails. It is also a `ValueError`, as a missing setting is a
    bad value.
    """


# =============================================================================
# CLASS: EgnyteAPIError
# =============================================================================


class EgnyteAPIError(EgnyteError):
    """
    Raised when Egnyte answers a call with an error status.

    Egnyte reports failures in several body shapes depending on the API and on
    which layer refused the call (the gateway, the file system, the SCIM user
    and group services). `from_response` reads each of them into the same
    `message` and `code`, and keeps the raw `body` and the `response`.
    """

    def __init__(
        self,
        status_code: int,
        message: str,
        code: str | None = None,
        body: str = "",
        response: httpx.Response | None = None,
    ) -> None:
        """
        Build the error from Egnyte's response.

        Args:
            status_code: The HTTP status the call was answered with.
            message: Egnyte's description of the failure.
            code: Egnyte's machine-readable error code, when it sends one.
            body: The raw response body.
            response: The response itself, for headers such as `Retry-After`.
        """
        self.status_code = status_code
        self.message = message
        self.code = code
        self.body = body
        self.response = response
        detail = f" [{code}]" if code else ""
        super().__init__(f"Egnyte API error {status_code}{detail}: {message}")

    @classmethod
    def from_response(cls, response: httpx.Response) -> "EgnyteAPIError":
        """
        Build the error matching a failed response's status.

        Returns:
            EgnyteAPIError: The most specific subclass for the status code.
        """
        message, code = _describe(response)
        error_cls = error_for_status(response.status_code)
        return error_cls(response.status_code, message, code, response.text, response)


class EgnyteValidationError(EgnyteAPIError):
    """
    400: Egnyte refused the request's content, such as a too-short search query.
    """


class EgnyteAuthError(EgnyteAPIError):
    """
    401: the access token is missing, invalid, expired, or revoked.
    """


class EgnyteForbiddenError(EgnyteAPIError):
    """
    403: the token is valid but not permitted this call.

    Egnyte also answers 403 for some conflicts, such as creating a folder that
    already exists, and for a token without the scope a call needs.
    """


class EgnyteNotFoundError(EgnyteAPIError):
    """
    404: the path, ID, link, user, or group does not exist.
    """


class EgnyteConflictError(EgnyteAPIError):
    """
    409: the call conflicts with existing state, such as a duplicate username.
    """


class EgnyteRateLimitError(EgnyteAPIError):
    """
    429: the per-second rate limit still refused the call after every retry.
    """

    @property
    def retry_after(self) -> float | None:
        """
        The wait Egnyte asked for before a retry, in seconds.

        Returns:
            float | None: The delay, or None when no usable header was sent.
        """
        header = self.response.headers.get("Retry-After") if self.response else None
        try:
            return float(header) if header else None
        except ValueError:
            return None


class EgnyteServerError(EgnyteAPIError):
    """
    5xx: the call failed inside Egnyte.
    """


STATUS_ERRORS: dict[int, type[EgnyteAPIError]] = {
    400: EgnyteValidationError,
    401: EgnyteAuthError,
    403: EgnyteForbiddenError,
    404: EgnyteNotFoundError,
    409: EgnyteConflictError,
    429: EgnyteRateLimitError,
}


def error_for_status(status: int) -> type[EgnyteAPIError]:
    """
    Select the exception class for a status code.

    Returns:
        type[EgnyteAPIError]: The class to raise.
    """
    if status in STATUS_ERRORS:
        return STATUS_ERRORS[status]
    if status >= 500:
        return EgnyteServerError
    return EgnyteAPIError


# =============================================================================
# FUNCTION: _describe
# =============================================================================


def _describe(response: httpx.Response) -> tuple[str, str | None]:
    """
    Pull a message and an error code out of any of Egnyte's error bodies.

    Shapes seen live:

    - `{"errorMessage": "Not found"}` (file system)
    - `{"message": "Link does not exist"}` (links)
    - `{"formErrors": [{"msg", "code"}], "inputErrors": {field: [{"msg", "code"}]}}` (users, groups)
    - `{"fault": {"faultstring", "detail": {"errorcode"}}}` (gateway: auth, rate limit)
    - `{"Errors": [{"description", "code"}]}` (documented for users)

    Returns:
        tuple[str, str | None]: The message and the error code, if any.
    """
    fallback = response.reason_phrase or "Request failed"
    try:
        payload = cast(object, json.loads(response.text))
    except ValueError:
        return (response.text.strip() or fallback), None
    if not isinstance(payload, dict):
        return fallback, None
    data = cast(dict[str, object], payload)

    for key in ("errorMessage", "message"):
        value = data.get(key)
        if isinstance(value, str) and value:
            return value, None

    fault = data.get("fault")
    if isinstance(fault, dict):
        fault_data = cast(dict[str, object], fault)
        detail = fault_data.get("detail")
        code = (
            _str(cast(dict[str, object], detail).get("errorcode"))
            if isinstance(detail, dict)
            else None
        )
        return _str(fault_data.get("faultstring")) or fallback, code

    entries: list[dict[str, object]] = []
    for key in ("formErrors", "Errors", "errors"):
        found = data.get(key)
        if isinstance(found, list):
            entries.extend(e for e in found if isinstance(e, dict))
    input_errors = data.get("inputErrors")
    if isinstance(input_errors, dict):
        for field, found in cast(dict[str, object], input_errors).items():
            if isinstance(found, list):
                for e in found:
                    if isinstance(e, dict):
                        entry = dict(cast(dict[str, object], e))
                        entry.setdefault("field", field)
                        entries.append(entry)

    if entries:
        messages: list[str] = []
        for entry in entries:
            text = _str(entry.get("msg")) or _str(entry.get("description")) or ""
            field_name = _str(entry.get("field"))
            messages.append(f"{field_name}: {text}" if field_name else text)
        return "; ".join(m for m in messages if m) or fallback, _str(
            entries[0].get("code")
        )

    return fallback, None


def _str(value: object) -> str | None:
    if value is None:
        return None
    return str(value)
