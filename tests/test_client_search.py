from collections.abc import Callable
from datetime import UTC, datetime, timedelta, timezone
from typing import Any

import httpx
import pytest
from conftest import body, respond
from pydantic import ValidationError

from egnyte_client.async_client import AsyncEgnyteClient
from egnyte_client.client import EgnyteClient
from egnyte_client.schemas.search import MetadataFilter, MetadataRange

FILE_HIT: dict[str, Any] = {
    "name": "Q3 report.pdf",
    "path": "/Shared/Reports/Q3 report.pdf",
    "type": "application/pdf",
    "size": 238428,
    "snippet": "quarterly revenue grew",
    "snippet_html": "quarterly <b>revenue</b> grew",
    "entry_id": "e-1",
    "group_id": "g-1",
    "last_modified": "2026-10-01T12:30:00.000+0000",
    "uploaded_by": "Jane Doe",
    "uploaded_by_username": "jdoe",
    "num_versions": 3,
    "is_folder": False,
    "custom_properties": [
        {
            "namespace": "finance",
            "key": "quarter",
            "value": "Q3",
            "scope": "public",
            "valueToStampOnFile": "Q3",
        }
    ],
    "score": 12.5,
}

# Shaped after a live folder hit, which carries folder_id and no file fields.
FOLDER_HIT: dict[str, Any] = {
    "name": "Reports",
    "path": "/Shared/Reports",
    "is_folder": True,
    "folder_id": "f-1",
    "custom_properties": [],
    "score": 1159.9921,
}

PAGE: dict[str, Any] = {
    "count": 2,
    "offset": 0,
    "total_count": 3,
    "results": [FILE_HIT, FOLDER_HIT],
    "hasMore": True,
}


def _client(
    make_client: Callable[..., EgnyteClient], response: httpx.Response
) -> tuple[EgnyteClient, list[httpx.Request]]:
    sent: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(request)
        return response

    return make_client(handler), sent


# =============================================================================
# TEST: request
# =============================================================================


def test_query_only_sends_a_minimal_body(
    make_client: Callable[..., EgnyteClient],
) -> None:
    client, sent = _client(make_client, respond(PAGE))

    client.search("revenue")

    assert sent[0].method == "POST"
    assert sent[0].url.path == "/pubapi/v2/search"
    assert sent[0].headers["Content-Type"] == "application/json"
    assert body(sent[0]) == {"query": "revenue"}


def test_every_option_reaches_the_body(
    make_client: Callable[..., EgnyteClient],
) -> None:
    client, sent = _client(make_client, respond(PAGE))

    client.search(
        "revenue report",
        folder="Shared//Reports/",
        type="FILE",
        modified_after=datetime(2026, 1, 1, tzinfo=UTC),
        modified_before=datetime(2026, 1, 1, 1, tzinfo=timezone(timedelta(hours=1))),
        uploaded_after=datetime(2026, 1, 1),
        file_query_fields=["FILENAME", "CONTENT"],
        folder_query_fields=["FOLDERNAME"],
        query_operator="ALL",
        namespaces=["finance"],
        include_snippets=False,
        sort_by="last_modified",
        sort_direction="descending",
        offset=20,
        count=20,
    )

    assert body(sent[0]) == {
        "query": "revenue report",
        "offset": 20,
        "count": 20,
        "folder": "/Shared/Reports",
        "type": "FILE",
        # Dates go over the wire as epoch milliseconds; naive means UTC.
        "modified_after": 1767225600000,
        "modified_before": 1767225600000,
        "uploaded_after": 1767225600000,
        "snippet_requested": False,
        "sort_by": "last_modified",
        "sort_direction": "descending",
        "query_operator": "ALL",
        "file_query_fields": ["FILENAME", "CONTENT"],
        "folder_query_fields": ["FOLDERNAME"],
        "namespaces": ["finance"],
    }


def test_metadata_filters_alone(make_client: Callable[..., EgnyteClient]) -> None:
    client, sent = _client(make_client, respond(PAGE))

    client.search(
        metadata_filters=[
            MetadataFilter(namespace="finance", key="quarter", value="Q3"),
            MetadataFilter(
                namespace="finance",
                key="amount",
                operator="BETWEEN",
                range=MetadataRange(start=100, end=500),
            ),
            MetadataFilter(
                namespace="finance", key="region", operator="IN", values=["EU", "US"]
            ),
            MetadataFilter(namespace="finance", key="approved", operator="HAS_KEY"),
        ]
    )

    assert body(sent[0]) == {
        "custom_metadata": [
            {
                "namespace": "finance",
                "key": "quarter",
                "operator": "EQUALS",
                "value": "Q3",
            },
            {
                "namespace": "finance",
                "key": "amount",
                "operator": "BETWEEN",
                "range": {"start": 100, "end": 500},
            },
            {
                "namespace": "finance",
                "key": "region",
                "operator": "IN",
                "values": ["EU", "US"],
            },
            {"namespace": "finance", "key": "approved", "operator": "HAS_KEY"},
        ]
    }


def test_similarity_search(make_client: Callable[..., EgnyteClient]) -> None:
    client, sent = _client(make_client, respond(PAGE))

    client.search(similar_to_entry_ids=["e-1"], similar_to_text=["quarterly revenue"])

    assert body(sent[0]) == {"mlt": ["e-1"], "mltt": ["quarterly revenue"]}


def test_search_needs_something_to_match(
    make_client: Callable[..., EgnyteClient],
) -> None:
    client, sent = _client(make_client, respond(PAGE))

    with pytest.raises(ValueError, match="needs a query"):
        client.search()
    assert not sent


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"operator": "EQUALS"}, "EQUALS takes value"),
        ({"operator": "IN", "value": "x"}, "IN takes values"),
        ({"operator": "BETWEEN", "value": 1}, "BETWEEN takes range"),
        ({"operator": "HAS_KEY", "value": "x"}, "HAS_KEY takes no operand"),
    ],
)
def test_metadata_filter_checks_its_operand(
    kwargs: dict[str, Any], message: str
) -> None:
    with pytest.raises(ValidationError, match=message):
        MetadataFilter(namespace="n", key="k", **kwargs)


# =============================================================================
# TEST: response
# =============================================================================


def test_results_parse_file_and_folder_hits(
    make_client: Callable[..., EgnyteClient],
) -> None:
    client, _ = _client(make_client, respond(PAGE))

    page = client.search("revenue")

    assert page.has_more is True
    assert page.count == 2
    file_hit, folder_hit = page.results

    assert file_hit.is_folder is False
    assert file_hit.group_id == "g-1"
    assert file_hit.mime_type == "application/pdf"
    assert file_hit.snippet_html == "quarterly <b>revenue</b> grew"
    assert file_hit.last_modified == datetime(2026, 10, 1, 12, 30, tzinfo=UTC)
    assert file_hit.uploaded_by_username == "jdoe"
    assert file_hit.custom_properties[0].value_to_stamp_on_file == "Q3"

    assert folder_hit.is_folder is True
    assert folder_hit.folder_id == "f-1"
    assert folder_hit.group_id is None


def test_empty_results(make_client: Callable[..., EgnyteClient]) -> None:
    client, _ = _client(
        make_client,
        respond(
            {"count": 0, "offset": 0, "total_count": 0, "results": [], "hasMore": False}
        ),
    )

    page = client.search("nothing matches")

    assert page.results == []
    assert page.has_more is False


def test_short_query_error_is_readable(
    make_client: Callable[..., EgnyteClient],
) -> None:
    message = "Search query must be between at least 3 to max 250 characters."
    client, _ = _client(
        make_client,
        respond(
            {"formErrors": [{"code": message, "msg": message}], "inputErrors": {}}, 400
        ),
    )

    with pytest.raises(Exception, match="at least 3 to max 250"):
        client.search("ab")


async def test_async_search(
    make_async_client: Callable[..., AsyncEgnyteClient],
) -> None:
    sent: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(request)
        return respond(PAGE)

    client = make_async_client(handler)
    page = await client.search("revenue", type="ALL")

    assert body(sent[0]) == {"query": "revenue", "type": "ALL"}
    assert len(page.results) == 2
