from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import httpx
from conftest import respond

from egnyte_client.async_client import AsyncEgnyteClient
from egnyte_client.client import EgnyteClient

# Shaped after the documented example; times are epoch milliseconds.
RECENT: dict[str, Any] = {
    "recentFiles": [
        {
            "name": "Q3 report.pdf",
            "path": "/Shared/Reports/Q3 report.pdf",
            "size": 238428,
            "entry_id": "e-1",
            "group_id": "g-1",
            "uploaded_by": "Jane Doe",
            "num_versions": 3,
            "last_modified": 1793906961000,
            "last_accessed": 1793924565000,
            "recommendation_type": "recent",
        },
        {
            # The uploader is omitted when the owner is unavailable.
            "name": "notes.txt",
            "path": "/Shared/Reports/notes.txt",
            "size": 12,
            "entry_id": "e-2",
            "group_id": "g-2",
            "num_versions": 1,
            "last_modified": 1793906961000,
            "last_accessed": 1793906962000,
            "recommendation_type": "recent",
        },
    ]
}


def test_list_recent_files(make_client: Callable[..., EgnyteClient]) -> None:
    sent: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(request)
        return respond(RECENT)

    client = make_client(handler)

    files = client.list_recent_files()

    assert sent[0].method == "GET"
    assert sent[0].url.path == "/pubapi/v1/insights/files"
    assert not sent[0].url.params
    assert [f.name for f in files] == ["Q3 report.pdf", "notes.txt"]
    assert files[0].group_id == "g-1"
    assert files[0].last_accessed == datetime(2026, 11, 6, 0, 22, 45, tzinfo=UTC)
    assert files[1].uploaded_by is None


def test_list_recent_files_in_a_folder(
    make_client: Callable[..., EgnyteClient],
) -> None:
    sent: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(request)
        return respond({"recentFiles": []})

    client = make_client(handler)

    assert client.list_recent_files(folder_path="Shared//Reports/") == []
    assert dict(sent[0].url.params) == {"folder_path": "/Shared/Reports"}


async def test_async_list_recent_files(
    make_async_client: Callable[..., AsyncEgnyteClient],
) -> None:
    client = make_async_client(lambda request: respond(RECENT))

    files = await client.list_recent_files(folder_path="/Shared")

    assert files[0].recommendation_type == "recent"
