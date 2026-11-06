"""
Coverage of the `fs` command group against a mock-transport client.

Each command is asserted on the requests it sends and the output it renders;
the client behind it is the real one, so argument wiring is what is tested.
"""

import hashlib
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx
import pytest
from click.testing import Result
from conftest import FILE, FOLDER, body, respond

from egnyte_client.cli.commands import fs as fs_cli
from egnyte_client.operations import filesystem as fs_ops

Handler = Callable[[httpx.Request], httpx.Response]
Runner = Callable[..., tuple[Result, list[httpx.Request]]]

STATS: dict[str, Any] = {
    "allVersionsSize": 20971720,
    "allFilesSize": 10485860,
    "filesCount": 2,
    "fileVersionsCount": 3,
    "foldersCount": 1,
    "allVersionsSizeInKB": 20480,
    "allFilesSizeInKB": 10240,
}
LOCK: dict[str, Any] = {"lock_token": "lt-1", "timeout": 3599}
MOVED: dict[str, Any] = {"path": "/Shared/Archive/b.txt", "group_id": "g-1"}
MOVED_FOLDER: dict[str, Any] = {"path": "/Shared/Archive/Old", "folder_id": "f-9"}
UPLOADED: dict[str, Any] = {"group_id": "g-1", "entry_id": "e-2", "path": FILE["path"]}


@pytest.fixture
def run(cli_runner: Callable[..., Runner]) -> Callable[..., Runner]:
    """
    Return a factory for a runner invoking the CLI `fs` group against a handler.

    Returns:
        Callable[..., Runner]: Takes a handler, gives back the runner.
    """
    return lambda handler: cli_runner(handler, prefix=("fs",))


def _json(result: Result) -> Any:
    assert result.exit_code == 0, result.output
    return json.loads(result.stdout)


def _usage_error(result: Result, sent: list[httpx.Request], message: str) -> None:
    assert result.exit_code == 2, result.output
    assert message in result.output
    assert not sent


# =============================================================================
# TEST: Target exclusivity
# =============================================================================


@pytest.mark.parametrize(
    ("args", "message"),
    [
        (["ls"], "Give exactly one of PATH or --folder-id."),
        (["ls", "/Shared", "--folder-id", "f-1"], "PATH or --folder-id"),
        (["stat"], "Give exactly one of PATH, --file-id, or --folder-id."),
        (["stat", "/Shared/a.txt", "--file-id", "g-1"], "PATH, --file-id, or"),
        (["stat", "--file-id", "g-1", "--folder-id", "f-1"], "PATH, --file-id, or"),
        (["stats", "/Shared", "--folder-id", "f-1"], "PATH or --folder-id"),
        (["download", "/Shared/a.txt", "--file-id", "g-1"], "SOURCE or --file-id"),
        (["download"], "SOURCE or --file-id"),
        (["rm", "/Shared/a.txt", "--folder-id", "f-1", "-y"], "PATH, --file-id, or"),
        (["lock", "/Shared/a.txt", "--file-id", "g-1"], "PATH or --file-id"),
        (
            ["unlock", "--lock-token", "lt-1"],
            "Give exactly one of PATH or --file-id.",
        ),
        (["cp", "/Shared/a.txt"], "Give SOURCE and DESTINATION paths"),
        (
            ["cp", "--file-id", "g-1", "--folder-id", "f-1", "f-2"],
            "--file-id or --folder-id",
        ),
        (["cp", "--file-id", "g-1", "/Shared/a.txt", "f-2"], "give only a DEST"),
        (["mv", "--folder-id", "f-1"], "give only a DEST_FOLDER_ID"),
        (["cp", "/Shared/a.txt", "/Shared/b.txt", "--name", "b"], "--name and"),
        (
            ["mv", "--file-id", "g-1", "f-2", "--folder-options-mode", "keep_source"],
            "--folder-options-mode applies only to folders.",
        ),
        (["stat", "--folder-id", "f-1", "--versions"], "--versions applies only"),
        (["rm", "--folder-id", "f-1", "--entry-id", "e-1", "-y"], "--entry-id"),
        (["options", "/Shared/Docs"], "Give at least one option to change."),
    ],
)
def test_usage_errors_send_nothing(
    run: Callable[[Handler], Runner], args: list[str], message: str
) -> None:
    result, sent = run(lambda r: respond(FOLDER))(*args)

    _usage_error(result, sent, message)


def test_upload_needs_a_destination_or_a_file_id(
    run: Callable[[Handler], Runner], tmp_path: Path
) -> None:
    local = tmp_path / "a.txt"
    local.write_bytes(b"data")
    invoke = run(lambda r: respond(UPLOADED))

    result, sent = invoke("upload", str(local))
    _usage_error(result, sent, "Give exactly one of DESTINATION or --file-id.")

    result, sent = invoke("upload", str(local), "/Shared/a.txt", "--file-id", "g-1")
    _usage_error(result, sent, "DESTINATION or --file-id")


# =============================================================================
# TEST: ls and stat
# =============================================================================


def test_ls_by_path(run: Callable[[Handler], Runner]) -> None:
    result, sent = run(lambda r: respond(FOLDER))(
        "ls", "/Shared/Docs", "--offset", "2", "--count", "5", "--sort-by", "name"
    )

    assert _json(result)["folder_id"] == "f-1"
    assert sent[0].method == "GET"
    assert sent[0].url.path == "/pubapi/v1/fs/Shared/Docs"
    assert dict(sent[0].url.params) == {
        "list_content": "true",
        "count": "5",
        "offset": "2",
        "sort_by": "name",
    }


def test_ls_by_folder_id(run: Callable[[Handler], Runner]) -> None:
    result, sent = run(lambda r: respond(FOLDER))(
        "ls", "--folder-id", "f-1", "--count", "5", "--sort-direction", "descending"
    )

    output = _json(result)
    assert output["path"] == "/Shared/Docs"
    assert output["files"][0]["name"] == "hello world.txt"
    assert sent[0].method == "GET"
    assert sent[0].url.path == "/pubapi/v1/fs/ids/folder/f-1"
    assert dict(sent[0].url.params) == {
        "list_content": "true",
        "count": "5",
        "sort_direction": "descending",
    }


def test_stat_by_file_id(run: Callable[[Handler], Runner]) -> None:
    result, sent = run(lambda r: respond(FILE))("stat", "--file-id", "g-1")

    assert _json(result)["group_id"] == "g-1"
    assert sent[0].method == "GET"
    assert sent[0].url.path == "/pubapi/v1/fs/ids/file/g-1"
    assert not sent[0].url.params


def test_stat_by_file_id_with_versions(run: Callable[[Handler], Runner]) -> None:
    result, sent = run(lambda r: respond(FILE))(
        "stat", "--file-id", "g-1", "--versions"
    )

    assert _json(result)["entry_id"] == "e-1"
    assert sent[0].url.path == "/pubapi/v1/fs/ids/file/g-1"
    assert dict(sent[0].url.params) == {"list_content": "true"}


def test_stat_by_folder_id(run: Callable[[Handler], Runner]) -> None:
    result, sent = run(lambda r: respond(FOLDER))("stat", "--folder-id", "f-1")

    assert _json(result)["is_folder"] is True
    assert sent[0].url.path == "/pubapi/v1/fs/ids/folder/f-1"


def test_stat_by_path(run: Callable[[Handler], Runner]) -> None:
    result, sent = run(lambda r: respond(FILE))("stat", "/Shared/Docs/a.txt")

    assert _json(result)["name"] == "hello world.txt"
    assert sent[0].url.path == "/pubapi/v1/fs/Shared/Docs/a.txt"
    assert not sent[0].url.params


# =============================================================================
# TEST: stats
# =============================================================================


def test_stats_by_folder_id(run: Callable[[Handler], Runner]) -> None:
    result, sent = run(lambda r: respond(STATS))("stats", "--folder-id", "f-1")

    output = _json(result)
    assert output["files_count"] == 2
    assert output["all_versions_size_in_kb"] == 20480
    assert len(sent) == 1
    assert sent[0].method == "GET"
    assert sent[0].url.path == "/pubapi/v1/fs/ids/folder/f-1/stats"


def test_stats_by_path_looks_up_the_folder_id(
    run: Callable[[Handler], Runner],
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/stats"):
            return respond(STATS)
        return respond(FOLDER)

    result, sent = run(handler)("stats", "/Shared/Docs")

    assert _json(result)["folders_count"] == 1
    assert [request.url.path for request in sent] == [
        "/pubapi/v1/fs/Shared/Docs",
        "/pubapi/v1/fs/ids/folder/f-1/stats",
    ]


# =============================================================================
# TEST: download
# =============================================================================


def test_download_by_file_id_to_stdout(run: Callable[[Handler], Runner]) -> None:
    result, sent = run(lambda r: httpx.Response(200, content=b"\x00data"))(
        "download", "--file-id", "g-1", "--entry-id", "e-1", "-o", "-"
    )

    assert result.exit_code == 0, result.output
    assert result.stdout_bytes == b"\x00data"
    assert len(sent) == 1
    assert sent[0].method == "GET"
    assert sent[0].url.path == "/pubapi/v1/fs-content/ids/file/g-1"
    assert dict(sent[0].url.params) == {"entry_id": "e-1"}


def test_download_by_file_id_names_the_file(
    run: Callable[[Handler], Runner],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.startswith("/pubapi/v1/fs-content/"):
            return httpx.Response(200, content=b"data")
        return respond(FILE)

    result, sent = run(handler)("download", "--file-id", "g-1")

    assert result.exit_code == 0, result.output
    assert (tmp_path / "hello world.txt").read_bytes() == b"data"
    assert [request.url.path for request in sent] == [
        "/pubapi/v1/fs/ids/file/g-1",
        "/pubapi/v1/fs-content/ids/file/g-1",
    ]


def test_download_by_path_to_stdout(run: Callable[[Handler], Runner]) -> None:
    result, sent = run(lambda r: httpx.Response(200, content=b"data"))(
        "download", "/Shared/x.bin", "-o", "-"
    )

    assert result.stdout_bytes == b"data"
    assert sent[0].url.path == "/pubapi/v1/fs-content/Shared/x.bin"


# =============================================================================
# TEST: cp and mv
# =============================================================================


def test_cp_by_path(run: Callable[[Handler], Runner]) -> None:
    result, sent = run(lambda r: respond(MOVED))(
        "cp",
        "/Shared/a.txt",
        "/Shared/Archive/b.txt",
        "--permissions",
        "inherit_from_parent",
    )

    assert _json(result)["path"] == "/Shared/Archive/b.txt"
    assert sent[0].method == "POST"
    assert sent[0].url.path == "/pubapi/v1/fs/Shared/a.txt"
    assert body(sent[0]) == {
        "action": "copy",
        "destination": "/Shared/Archive/b.txt",
        "permissions": "inherit_from_parent",
    }


def test_cp_by_file_id(run: Callable[[Handler], Runner]) -> None:
    result, sent = run(lambda r: respond(MOVED))(
        "cp", "--file-id", "g-1", "f-2", "--name", "b.txt"
    )

    assert _json(result)["group_id"] == "g-1"
    assert sent[0].method == "POST"
    assert sent[0].url.path == "/pubapi/v1/fs/ids/file/g-1"
    assert body(sent[0]) == {
        "action": "copy",
        "destination_id": "f-2",
        "name": "b.txt",
    }


def test_cp_by_folder_id(run: Callable[[Handler], Runner]) -> None:
    result, sent = run(lambda r: respond(MOVED_FOLDER))(
        "cp",
        "--folder-id",
        "f-1",
        "f-2",
        "--permissions",
        "keep_original",
        "--folder-options-mode",
        "apply_destination",
    )

    assert _json(result)["folder_id"] == "f-9"
    assert sent[0].url.path == "/pubapi/v1/fs/ids/folder/f-1"
    assert body(sent[0]) == {
        "action": "copy",
        "destination_id": "f-2",
        "permissions": "keep_original",
        "folder_options_mode": "apply_destination",
    }


def test_mv_by_file_id(run: Callable[[Handler], Runner]) -> None:
    result, sent = run(lambda r: respond(MOVED))(
        "mv", "--file-id", "g-1", "f-2", "--permissions", "keep_original"
    )

    assert _json(result)["path"] == "/Shared/Archive/b.txt"
    assert sent[0].method == "POST"
    assert sent[0].url.path == "/pubapi/v1/fs/ids/file/g-1"
    assert body(sent[0]) == {
        "action": "move",
        "destination_id": "f-2",
        "permissions": "keep_original",
    }


def test_mv_by_folder_id(run: Callable[[Handler], Runner]) -> None:
    result, sent = run(lambda r: respond(MOVED_FOLDER))(
        "mv",
        "--folder-id",
        "f-1",
        "f-2",
        "--name",
        "Old",
        "--folder-options-mode",
        "keep_source",
    )

    assert _json(result)["path"] == "/Shared/Archive/Old"
    assert sent[0].url.path == "/pubapi/v1/fs/ids/folder/f-1"
    assert body(sent[0]) == {
        "action": "move",
        "destination_id": "f-2",
        "name": "Old",
        "folder_options_mode": "keep_source",
    }


def test_mv_by_path(run: Callable[[Handler], Runner]) -> None:
    result, sent = run(lambda r: respond(MOVED))(
        "mv", "/Shared/a.txt", "/Shared/Archive/b.txt"
    )

    assert _json(result)["path"] == "/Shared/Archive/b.txt"
    assert body(sent[0]) == {"action": "move", "destination": "/Shared/Archive/b.txt"}


# =============================================================================
# TEST: rm
# =============================================================================


def test_rm_by_file_id_asks_first(run: Callable[[Handler], Runner]) -> None:
    invoke = run(lambda r: respond({"parent_folder_path": "/Shared"}))

    declined, sent = invoke("rm", "--file-id", "g-1", "--entry-id", "e-1", input="n\n")
    assert declined.exit_code == 1
    assert "Delete version e-1 of file g-1?" in declined.output
    assert not sent

    confirmed, sent = invoke("rm", "--file-id", "g-1", "--entry-id", "e-1", "--yes")
    assert _json(confirmed)["parent_folder_path"] == "/Shared"
    assert sent[0].method == "DELETE"
    assert sent[0].url.path == "/pubapi/v1/fs/ids/file/g-1"
    assert dict(sent[0].url.params) == {"entry_id": "e-1"}


def test_rm_by_folder_id_asks_first(run: Callable[[Handler], Runner]) -> None:
    invoke = run(lambda r: respond())

    declined, sent = invoke("rm", "--folder-id", "f-1", input="n\n")
    assert declined.exit_code == 1
    assert "Delete folder f-1?" in declined.output
    assert not sent

    confirmed, sent = invoke("rm", "--folder-id", "f-1", input="y\n")
    assert confirmed.exit_code == 0, confirmed.output
    # The prompt goes to stderr, so stdout is only the JSON.
    assert json.loads(confirmed.stdout) == {"parent_folder_path": None}
    assert "Delete" in confirmed.stderr
    assert sent[0].method == "DELETE"
    assert sent[0].url.path == "/pubapi/v1/fs/ids/folder/f-1"
    assert not sent[0].url.params


def test_rm_by_path(run: Callable[[Handler], Runner]) -> None:
    result, sent = run(lambda r: respond({"parent_folder_path": "/Shared"}))(
        "rm", "/Shared/a.txt", "-y"
    )

    assert _json(result)["parent_folder_path"] == "/Shared"
    assert sent[0].method == "DELETE"
    assert sent[0].url.path == "/pubapi/v1/fs/Shared/a.txt"


# =============================================================================
# TEST: lock and unlock
# =============================================================================


def test_lock_by_path_prints_the_token(run: Callable[[Handler], Runner]) -> None:
    result, sent = run(lambda r: respond(LOCK))(
        "lock", "/Shared/a.txt", "--timeout", "60"
    )

    assert result.exit_code == 0, result.output
    assert result.stdout == "lt-1\n"
    assert "Locked /Shared/a.txt for 3599 seconds" in result.stderr
    assert sent[0].method == "POST"
    assert sent[0].url.path == "/pubapi/v1/fs/Shared/a.txt"
    assert body(sent[0]) == {"action": "lock", "lock_timeout": 60}


def test_lock_by_file_id_refreshes(run: Callable[[Handler], Runner]) -> None:
    result, sent = run(lambda r: respond(LOCK))(
        "lock", "--file-id", "g-1", "--lock-token", "lt-1", "--collaboration", "Y29s"
    )

    assert result.stdout == "lt-1\n"
    assert sent[0].url.path == "/pubapi/v1/fs/ids/file/g-1"
    assert body(sent[0]) == {
        "action": "lock",
        "lock_token": "lt-1",
        "collaboration": "Y29s",
    }


def test_lock_rejects_a_timeout_out_of_range(
    run: Callable[[Handler], Runner],
) -> None:
    result, sent = run(lambda r: respond(LOCK))(
        "lock", "/Shared/a.txt", "--timeout", "604801"
    )

    assert result.exit_code == 2
    assert not sent


def test_unlock_by_path(run: Callable[[Handler], Runner]) -> None:
    result, sent = run(lambda r: respond())(
        "unlock", "/Shared/a.txt", "--lock-token", "lt-1"
    )

    assert result.exit_code == 0, result.output
    assert result.stdout == ""
    assert "Unlocked /Shared/a.txt" in result.stderr
    assert sent[0].method == "POST"
    assert sent[0].url.path == "/pubapi/v1/fs/Shared/a.txt"
    assert body(sent[0]) == {"action": "unlock", "lock_token": "lt-1"}


def test_unlock_by_file_id(run: Callable[[Handler], Runner]) -> None:
    result, sent = run(lambda r: respond())(
        "unlock", "--file-id", "g-1", "--lock-token", "lt-1"
    )

    assert result.exit_code == 0, result.output
    assert "Unlocked file g-1" in result.stderr
    assert sent[0].url.path == "/pubapi/v1/fs/ids/file/g-1"
    assert body(sent[0]) == {"action": "unlock", "lock_token": "lt-1"}


def test_unlock_needs_the_token(run: Callable[[Handler], Runner]) -> None:
    result, sent = run(lambda r: respond())("unlock", "/Shared/a.txt")

    assert result.exit_code == 2
    assert "--lock-token" in result.output
    assert not sent


# =============================================================================
# TEST: options and recent
# =============================================================================


def test_options_sends_only_what_was_given(run: Callable[[Handler], Runner]) -> None:
    updated = {**FOLDER, "folder_description": "Quarterly", "folders": [], "files": []}

    result, sent = run(lambda r: respond(updated))(
        "options",
        "/Shared/Docs",
        "--description",
        "Quarterly",
        "--no-allow-links",
        "--allow-upload-links",
        "--public-links",
        "folders",
        "--restrict-move-delete",
        "--move-delete-restriction",
        "admins_only",
        "--inheritance-rule",
        "this_folder_only",
        "--notify-content-updates",
        "--no-notify-content-accessed",
    )

    assert _json(result)["folder_description"] == "Quarterly"
    assert sent[0].method == "PATCH"
    assert sent[0].url.path == "/pubapi/v1/fs/Shared/Docs"
    assert body(sent[0]) == {
        "folder_description": "Quarterly",
        "allow_links": False,
        "allow_upload_links": True,
        "public_links": "folders",
        "restrict_move_delete": True,
        "move_delete_folder_restriction": "admins_only",
        "inheritance_rule": "this_folder_only",
        "email_preferences": {"content_updates": True, "content_accessed": False},
    }


def test_options_with_one_flag(run: Callable[[Handler], Runner]) -> None:
    result, sent = run(lambda r: respond(FOLDER))(
        "options", "/Shared/Docs", "--no-restrict-move-delete"
    )

    assert result.exit_code == 0, result.output
    assert body(sent[0]) == {"restrict_move_delete": False}


RECENT: dict[str, Any] = {
    "recentFiles": [
        {
            "name": "Q3 report.pdf",
            "path": "/Shared/Reports/Q3 report.pdf",
            "group_id": "g-1",
            "last_accessed": 1793924565000,
        }
    ]
}


def test_recent(run: Callable[[Handler], Runner]) -> None:
    result, sent = run(lambda r: respond(RECENT))("recent")

    assert _json(result)[0]["group_id"] == "g-1"
    assert sent[0].method == "GET"
    assert sent[0].url.path == "/pubapi/v1/insights/files"
    assert not sent[0].url.params


def test_recent_in_a_folder(run: Callable[[Handler], Runner]) -> None:
    result, sent = run(lambda r: respond(RECENT))(
        "recent", "--folder", "Shared/Reports/"
    )

    assert _json(result)[0]["path"] == "/Shared/Reports/Q3 report.pdf"
    assert dict(sent[0].url.params) == {"folder_path": "/Shared/Reports"}


# =============================================================================
# TEST: upload
# =============================================================================


def _uploads(request: httpx.Request) -> httpx.Response:
    """
    Stand in for the file lookup and both upload endpoints.

    Returns:
        httpx.Response: The lookup's file, a chunk's headers, or the upload.
    """
    if request.method == "GET":
        return respond(FILE)
    if "/fs-content-chunked/" not in request.url.path:
        return respond(UPLOADED)
    headers = {"X-Egnyte-Upload-Id": "u-1"}
    if request.headers.get("X-Egnyte-Last-Chunk") != "true":
        return httpx.Response(200, headers=headers)
    return httpx.Response(200, headers=headers, json=UPLOADED)


@pytest.fixture
def small_chunks(monkeypatch: pytest.MonkeyPatch) -> list[type]:
    """
    Shrink the chunk bounds to bytes, and record what each chunked upload read.

    The default chunk size, the single-request threshold, becomes 10 bytes,
    so a few dozen bytes on disk exercise the chunked path.

    Returns:
        list[type]: The type of `data` handed to each chunked upload.
    """
    monkeypatch.setattr(fs_ops, "MIN_CHUNK_SIZE", 10)
    monkeypatch.setattr(fs_ops, "DEFAULT_CHUNK_SIZE", 10)
    sources: list[type] = []
    start = fs_ops.upload_file_chunked

    def spy(path: str, data: Any, **kwargs: Any) -> fs_ops.ChunkedUpload:
        sources.append(type(data))
        return start(path, data, **kwargs)

    monkeypatch.setattr(fs_ops, "upload_file_chunked", spy)
    return sources


def _chunks_of(sent: list[httpx.Request]) -> list[bytes]:
    return [r.content for r in sent if "/fs-content-chunked/" in r.url.path]


def test_upload_at_the_threshold_is_one_request(
    run: Callable[[Handler], Runner], tmp_path: Path, small_chunks: list[type]
) -> None:
    local = tmp_path / "a.txt"
    local.write_bytes(b"0123456789")

    result, sent = run(_uploads)("upload", str(local), "/Shared/Docs/a.txt")

    assert _json(result)["entry_id"] == "e-2"
    assert len(sent) == 1
    assert sent[0].method == "POST"
    assert sent[0].url.path == "/pubapi/v1/fs-content/Shared/Docs/a.txt"
    assert sent[0].content == b"0123456789"
    assert not small_chunks


def test_upload_over_the_threshold_streams_chunks(
    run: Callable[[Handler], Runner], tmp_path: Path, small_chunks: list[type]
) -> None:
    content = b"abcdefghij" * 2 + b"xyz"
    local = tmp_path / "big.bin"
    local.write_bytes(content)

    result, sent = run(_uploads)("upload", str(local), "/Shared/Docs/")

    assert _json(result)["entry_id"] == "e-2"
    assert "in chunks of 10 bytes" in result.stderr
    assert _chunks_of(sent) == [b"abcdefghij", b"abcdefghij", b"xyz"]
    assert {r.url.path for r in sent} == {
        "/pubapi/v1/fs-content-chunked/Shared/Docs/big.bin"
    }
    last = sent[-1]
    assert last.headers["X-Egnyte-Last-Chunk"] == "true"
    assert last.headers["X-Egnyte-Upload-Id"] == "u-1"
    combined = hashlib.sha512(
        "".join(hashlib.sha512(c).hexdigest() for c in _chunks_of(sent)).encode()
    ).hexdigest()
    assert last.headers["X-Sha512-Checksum"] == f"2-3-10-{combined}"
    assert small_chunks and small_chunks[0] is not bytes


def test_upload_chunk_size_overrides_the_threshold(
    run: Callable[[Handler], Runner],
    tmp_path: Path,
    small_chunks: list[type],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(fs_ops, "DEFAULT_CHUNK_SIZE", 1000)
    monkeypatch.setattr(fs_cli, "MIB", 2)
    local = tmp_path / "big.bin"
    local.write_bytes(b"x" * 45)

    result, sent = run(_uploads)(
        "upload", str(local), "/Shared/big.bin", "--chunk-size", "10"
    )

    assert result.exit_code == 0, result.output
    assert [len(c) for c in _chunks_of(sent)] == [20, 20, 5]
    assert len(small_chunks) == 1


def test_upload_rejects_a_chunk_size_out_of_range(
    run: Callable[[Handler], Runner], tmp_path: Path
) -> None:
    local = tmp_path / "a.txt"
    local.write_bytes(b"data")

    result, sent = run(_uploads)(
        "upload", str(local), "/Shared/a.txt", "--chunk-size", "5"
    )

    assert result.exit_code == 2
    assert not sent


def test_upload_small_file_by_id_resolves_the_path(
    run: Callable[[Handler], Runner], tmp_path: Path, small_chunks: list[type]
) -> None:
    local = tmp_path / "a.txt"
    local.write_bytes(b"new")

    result, sent = run(_uploads)("upload", str(local), "--file-id", "g-1")

    assert _json(result)["group_id"] == "g-1"
    assert [(r.method, r.url.path) for r in sent] == [
        ("GET", "/pubapi/v1/fs/ids/file/g-1"),
        ("POST", "/pubapi/v1/fs-content/Shared/Docs/hello world.txt"),
    ]
    assert sent[1].content == b"new"
    assert not small_chunks


def test_upload_large_file_by_id_is_chunked(
    run: Callable[[Handler], Runner], tmp_path: Path, small_chunks: list[type]
) -> None:
    local = tmp_path / "big.bin"
    local.write_bytes(b"0123456789abcde")

    result, sent = run(_uploads)("upload", str(local), "--file-id", "g-1")

    assert _json(result)["entry_id"] == "e-2"
    assert [(r.method, r.url.path) for r in sent] == [
        ("GET", "/pubapi/v1/fs/ids/file/g-1"),
        ("POST", "/pubapi/v1/fs-content-chunked/Shared/Docs/hello world.txt"),
        ("POST", "/pubapi/v1/fs-content-chunked/Shared/Docs/hello world.txt"),
    ]
    assert _chunks_of(sent) == [b"0123456789", b"abcde"]
    assert small_chunks and small_chunks[0] is not bytes
