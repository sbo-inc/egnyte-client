"""
Coverage of the CLI commands against a mock-transport client.

Each command is asserted on the request it sends and the output it renders;
the client behind it is the real one, so argument wiring is what is tested.
"""

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx
import pytest
from click.testing import Result
from conftest import FILE, FOLDER, GROUP, USER, body, respond

Runner = Callable[..., tuple[Result, list[httpx.Request]]]


@pytest.fixture
def run(cli_runner: Callable[..., Runner]) -> Callable[..., Runner]:
    """
    Return a factory for a runner invoking the CLI against a handler.

    Returns:
        Callable[..., Runner]: Takes a handler, gives back the runner.
    """
    return lambda handler: cli_runner(handler)


def _json(result: Result) -> Any:
    assert result.exit_code == 0, result.output
    return json.loads(result.stdout)


def test_auth_whoami(run: Callable[..., Runner]) -> None:
    result, sent = run(lambda r: respond({"id": 8, "username": "jdoe"}))(
        "auth", "whoami"
    )

    assert _json(result)["username"] == "jdoe"
    assert sent[0].url.path == "/pubapi/v1/userinfo"


def test_fs_ls_renders_field_names(run: Callable[..., Runner]) -> None:
    result, sent = run(lambda r: respond(FOLDER))(
        "fs", "ls", "/Shared/Docs", "--count", "5"
    )

    output = _json(result)
    assert output["last_modified"] == "2026-11-05T19:29:21Z"
    assert output["files"][0]["name"] == "hello world.txt"
    assert sent[0].url.params["count"] == "5"


def test_fs_stat_with_versions(run: Callable[..., Runner]) -> None:
    result, sent = run(lambda r: respond(FILE))(
        "fs", "stat", "/Shared/a.txt", "--versions"
    )

    assert _json(result)["group_id"] == "g-1"
    assert sent[0].url.params["list_content"] == "true"


def test_fs_upload_into_a_folder(run: Callable[..., Runner], tmp_path: Path) -> None:
    local = tmp_path / "notes.txt"
    local.write_bytes(b"notes")
    invoke = run(
        lambda r: respond(
            {"group_id": "g", "entry_id": "e", "path": "/Shared/notes.txt"}
        )
    )

    result, sent = invoke("fs", "upload", str(local), "/Shared/")

    assert _json(result)["entry_id"] == "e"
    assert sent[0].url.path == "/pubapi/v1/fs-content/Shared/notes.txt"
    assert sent[0].content == b"notes"


def test_fs_download_to_a_file(
    run: Callable[..., Runner], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)

    result, _ = run(lambda r: httpx.Response(200, content=b"data"))(
        "fs", "download", "/Shared/x.bin"
    )

    assert result.exit_code == 0, result.output
    assert (tmp_path / "x.bin").read_bytes() == b"data"


def test_fs_download_to_stdout(run: Callable[..., Runner]) -> None:
    result, _ = run(lambda r: httpx.Response(200, content=b"data"))(
        "fs", "download", "/Shared/x.bin", "-o", "-"
    )

    assert result.stdout_bytes == b"data"


def test_fs_mv(run: Callable[..., Runner]) -> None:
    result, sent = run(lambda r: respond({"path": "/Shared/b.txt", "group_id": "g"}))(
        "fs", "mv", "/Shared/a.txt", "/Shared/b.txt"
    )

    assert _json(result)["path"] == "/Shared/b.txt"
    assert body(sent[0]) == {"action": "move", "destination": "/Shared/b.txt"}


def test_fs_rm_asks_first(run: Callable[..., Runner]) -> None:
    invoke = run(lambda r: respond({"parent_folder_path": "/Shared"}))

    declined, sent = invoke("fs", "rm", "/Shared/a.txt", input="n\n")
    assert declined.exit_code == 1
    assert not sent

    confirmed, sent = invoke("fs", "rm", "/Shared/a.txt", "-y")
    assert _json(confirmed)["parent_folder_path"] == "/Shared"
    assert sent[0].method == "DELETE"


def test_links_create(run: Callable[..., Runner]) -> None:
    created = {
        "links": [{"id": "L1", "url": "https://acme.egnyte.com/dl/L1"}],
        "path": "/Shared/a.txt",
        "type": "file",
    }
    result, sent = run(lambda r: respond(created))(
        "links",
        "create",
        "/Shared/a.txt",
        "--type",
        "file",
        "--accessibility",
        "anyone",
        "--expiry-date",
        "2026-12-01",
    )

    assert _json(result)["id"] == "L1"
    assert body(sent[0]) == {
        "path": "/Shared/a.txt",
        "type": "file",
        "accessibility": "anyone",
        "expiry_date": "2026-12-01",
    }


def test_groups_create_and_delete(run: Callable[..., Runner]) -> None:
    invoke = run(lambda r: respond(GROUP) if r.method == "POST" else respond())

    created, sent = invoke(
        "groups", "create", "Finance", "--member", "8", "--member", "9"
    )
    assert _json(created)["display_name"] == "Finance"
    assert body(sent[0])["members"] == [{"value": 8}, {"value": 9}]

    deleted, sent = invoke("groups", "delete", "grp-1", "--yes")
    assert deleted.exit_code == 0, deleted.output
    assert sent[-1].method == "DELETE"


def test_users_update(run: Callable[..., Runner]) -> None:
    result, sent = run(lambda r: respond(USER))("users", "update", "8", "--inactive")

    assert _json(result)["user_name"] == "jdoe"
    assert body(sent[0]) == {"active": False}


def test_disabled_commands_are_rejected(
    run: Callable[..., Runner], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("EGNYTE_CLI_DISABLE", "users.delete")

    result, sent = run(lambda r: respond())("users", "delete", "8", "-y")

    assert result.exit_code != 0
    assert not sent


SEARCH_PAGE = {
    "count": 1,
    "results": [
        {"name": "Docs", "path": "/Shared/Docs", "is_folder": True, "folder_id": "f-1"}
    ],
    "hasMore": False,
}


def test_search(run: Callable[..., Runner]) -> None:
    result, sent = run(lambda r: respond(SEARCH_PAGE))(
        "search",
        "quarterly revenue",
        "--folder",
        "/Shared",
        "--type",
        "file",
        "--in",
        "content",
        "--in",
        "filename",
        "--match-all",
        "--metadata",
        "finance",
        "quarter",
        "Q3",
        "--modified-after",
        "2026-01-01",
        "--count",
        "5",
    )

    output = _json(result)
    assert output["results"][0]["folder_id"] == "f-1"
    assert output["has_more"] is False
    assert sent[0].url.path == "/pubapi/v2/search"
    assert body(sent[0]) == {
        "query": "quarterly revenue",
        "count": 5,
        "folder": "/Shared",
        "type": "FILE",
        "modified_after": 1767225600000,
        "query_operator": "ALL",
        "file_query_fields": ["CONTENT", "FILENAME"],
        "custom_metadata": [
            {
                "namespace": "finance",
                "key": "quarter",
                "operator": "EQUALS",
                "value": "Q3",
            }
        ],
    }


def test_search_needs_a_query_or_metadata(run: Callable[..., Runner]) -> None:
    result, sent = run(lambda r: respond(SEARCH_PAGE))("search")

    assert result.exit_code == 2
    assert "Give a QUERY, --metadata, or both." in result.output
    assert not sent


def test_links_delete_asks_first(run: Callable[..., Runner]) -> None:
    invoke = run(lambda r: respond())

    declined, sent = invoke("links", "delete", "L1", input="n\n")
    assert declined.exit_code == 1
    assert "Delete link L1?" in declined.output
    assert not sent

    confirmed, sent = invoke("links", "delete", "L1", "--yes")
    assert confirmed.exit_code == 0, confirmed.output
    assert sent[0].method == "DELETE"
    assert sent[0].url.path == "/pubapi/v1/links/L1"


def test_groups_replace_asks_first_and_sends_the_full_membership(
    run: Callable[..., Runner],
) -> None:
    invoke = run(lambda r: respond(GROUP))

    declined, sent = invoke(
        "groups", "replace", "grp-1", "Finance", "--member", "8", input="n\n"
    )
    assert declined.exit_code == 1
    assert not sent

    result, sent = invoke(
        "groups",
        "replace",
        "grp-1",
        "Finance",
        "--member",
        "8",
        "--member",
        "9",
        "--yes",
    )
    assert _json(result)["display_name"] == "Finance"
    assert sent[0].method == "PUT"
    assert sent[0].url.path == "/pubapi/v2/groups/grp-1"
    assert body(sent[0]) == {
        "displayName": "Finance",
        "members": [{"value": 8}, {"value": 9}],
    }
