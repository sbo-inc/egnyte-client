from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from urllib.parse import quote

import httpx
from pydantic import BaseModel

from egnyte_client.schemas.generic import ScimListResponse

type QueryValue = str | int | bool | None

# =============================================================================
# CLASS: Operation
# =============================================================================


@dataclass(frozen=True)
class Operation[T]:
    """
    One API call, described without performing it.

    Everything an Egnyte call needs that is not transport: the method, the path
    under `/pubapi`, the query, the body (a model sent as JSON, or raw bytes),
    any extra headers, the non-2xx statuses the parser handles itself
    (`accept`), and the function that turns the response into the result. Both clients build the same `Operation` and differ only in how they
    put it on the wire, which keeps request construction and response
    reshaping written once.
    """

    method: str
    path: str
    parse: Callable[[httpx.Response], T]
    params: Mapping[str, QueryValue] = field(default_factory=dict)
    body: BaseModel | None = None
    content: bytes | None = None
    headers: Mapping[str, str] = field(default_factory=dict)
    accept: frozenset[int] = frozenset()


# =============================================================================
# FUNCTION: encode_path
# =============================================================================


def _segments(path: str) -> list[str]:
    segments = [segment for segment in path.strip().split("/") if segment]
    if any(segment in (".", "..") for segment in segments):
        raise ValueError(
            f"Relative segments are not allowed in an Egnyte path: {path!r}"
        )
    return segments


def normalize_path(path: str) -> str:
    """
    Make an Egnyte path absolute, collapsing repeated and trailing slashes.

    Returns:
        str: The absolute, unencoded path, as request bodies carry it.
    """
    return "/" + "/".join(_segments(path))


def encode_path(path: str) -> str:
    """
    Percent-encode an Egnyte path for use in a URL, one segment at a time.

    Egnyte requires each segment encoded separately with the `/` separators
    left alone, so `/Shared/a b/c?.txt` becomes `/Shared/a%20b/c%3F.txt`. The
    path is made absolute, and trailing slashes are dropped.

    Returns:
        str: The encoded absolute path, starting with `/`.
    """
    return "/" + "/".join(quote(segment, safe="") for segment in _segments(path))


# =============================================================================
# FUNCTION: encode_id
# =============================================================================


def encode_id(value: str | int) -> str:
    """
    Percent-encode an ID for use as one URL path segment.

    Returns:
        str: The encoded ID.
    """
    return quote(str(value), safe="")


# =============================================================================
# FUNCTION: query
# =============================================================================


def query(**params: QueryValue) -> dict[str, QueryValue]:
    """
    Build a query mapping, dropping parameters that were not given.

    Returns:
        dict[str, QueryValue]: The parameters whose value is not None.
    """
    return {key: value for key, value in params.items() if value is not None}


# =============================================================================
# FUNCTIONS: Datetimes on the wire
# =============================================================================
#
# Egnyte takes timestamps in several wire forms depending on the API. Each
# helper below reads a naive datetime as UTC, so a caller's timezone never
# leaks into a request.


def as_utc(value: datetime) -> datetime:
    """
    Make a datetime aware in UTC, reading a naive one as UTC.

    Returns:
        datetime: The same instant, in UTC.
    """
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def iso_utc(value: datetime | None) -> str | None:
    """
    Format a datetime as an ISO 8601 UTC stamp, such as `2026-04-18T16:11:38Z`.

    Returns:
        str | None: The stamp, or None.
    """
    return as_utc(value).strftime("%Y-%m-%dT%H:%M:%SZ") if value is not None else None


def epoch_ms(value: datetime | None) -> int | None:
    """
    Convert a datetime to Unix epoch milliseconds.

    Returns:
        int | None: Milliseconds since the epoch, or None.
    """
    return int(as_utc(value).timestamp() * 1000) if value is not None else None


# =============================================================================
# FUNCTION: scim_filter
# =============================================================================


def scim_filter(**clauses: tuple[str, str | None]) -> str | None:
    """
    Build the SCIM `filter` expression for the v2 user and group listings.

    Each keyword is an attribute mapped to `(operator, value)`; clauses whose
    value is None are skipped. Egnyte documents a single comparison per
    filter, so more than one given clause is refused.

    Returns:
        str | None: The expression, such as `userName eq "jdoe"`, or None.
    """
    given = [
        (attribute, operator, value)
        for attribute, (operator, value) in clauses.items()
        if value is not None
    ]
    if not given:
        return None
    if len(given) > 1:
        names = ", ".join(attribute for attribute, _, _ in given)
        raise ValueError(f"Egnyte accepts one filter at a time; got {names}")
    attribute, operator, value = given[0]
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'{attribute} {operator} "{escaped}"'


# =============================================================================
# FUNCTIONS: Response parsers
# =============================================================================


def model[T: BaseModel](cls: type[T]) -> Callable[[httpx.Response], T]:
    """
    Parse a JSON body straight into one model.

    Returns:
        Callable[[httpx.Response], T]: The parser for this model.
    """

    def parse(response: httpx.Response) -> T:
        return cls.model_validate_json(response.content)

    return parse


def resources[T: BaseModel](cls: type[T]) -> Callable[[httpx.Response], list[T]]:
    """
    Parse a SCIM page and return its `resources` as models.

    Returns:
        Callable[[httpx.Response], list[T]]: The parser for this page.
    """

    def parse(response: httpx.Response) -> list[T]:
        return ScimListResponse[cls].model_validate_json(response.content).resources  # type: ignore[valid-type]

    return parse


def empty(response: httpx.Response) -> None:
    """
    Discard a body that carries nothing, as deletes answer.
    """
    return None


def content(response: httpx.Response) -> bytes:
    """
    Return the raw body, as a download answers.

    Returns:
        bytes: The response body.
    """
    return response.content
