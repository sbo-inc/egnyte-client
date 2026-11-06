"""
Coverage of the `perms` commands against a mock-transport client.
"""

import json
from collections.abc import Callable
from typing import Any, get_args

import httpx
import pytest
from click.testing import Result
from conftest import body, respond

from egnyte_client.cli.commands import perms
from egnyte_client.schemas.permission import PermissionLevel

Runner = Callable[..., tuple[Result, list[httpx.Request]]]

FOLDER_PERMISSIONS = {
    "userPerms": {"jdoe": "Full", "asmith": "Viewer"},
    "groupPerms": {"Finance": "Editor"},
    "inheritsPermissions": True,
}


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


def test_levels_match_the_client() -> None:
    assert perms.PERMISSION_LEVELS == get_args(PermissionLevel.__value__)


# =============================================================================
# TEST: perms get / effective
# =============================================================================


def test_get(run: Callable[..., Runner]) -> None:
    result, sent = run(lambda r: respond(FOLDER_PERMISSIONS))(
        "perms", "get", "/Shared/Docs"
    )

    assert _json(result) == {
        "user_permissions": {"jdoe": "Full", "asmith": "Viewer"},
        "group_permissions": {"Finance": "Editor"},
        "inherits_permissions": True,
    }
    assert sent[0].method == "GET"
    assert sent[0].url.path == "/pubapi/v2/perms/Shared/Docs"


def test_effective_for_the_caller(run: Callable[..., Runner]) -> None:
    result, sent = run(lambda r: respond({"permission": "Owner"}))(
        "perms", "effective", "/Shared/Docs"
    )

    assert result.exit_code == 0, result.output
    assert result.stdout == "Owner\n"
    assert sent[0].method == "GET"
    assert sent[0].url.path == "/pubapi/v1/perms/user"
    assert sent[0].url.params["folder"] == "/Shared/Docs"


def test_effective_for_a_user(run: Callable[..., Runner]) -> None:
    result, sent = run(lambda r: respond({"permission": "Viewer Only"}))(
        "perms", "effective", "/Shared/Docs", "--user", "jdoe"
    )

    assert result.stdout == "Viewer Only\n"
    assert sent[0].url.path == "/pubapi/v1/perms/user/jdoe"
    assert sent[0].url.params["folder"] == "/Shared/Docs"


# =============================================================================
# TEST: perms set
# =============================================================================


def test_set_grants_and_removes(run: Callable[..., Runner]) -> None:
    result, sent = run(lambda r: respond())(
        "perms",
        "set",
        "/Shared/Docs",
        "--user",
        "jdoe=Full",
        "--user",
        "asmith=viewer only",
        "--group",
        "Finance=Editor",
        "--remove-user",
        "bob",
        "--remove-group",
        "Interns",
        "--yes",
    )

    assert result.exit_code == 0, result.output
    assert result.stdout == ""
    assert "Updated permissions on /Shared/Docs" in result.stderr
    assert sent[0].method == "POST"
    assert sent[0].url.path == "/pubapi/v2/perms/Shared/Docs"
    assert body(sent[0]) == {
        "userPerms": {"jdoe": "Full", "asmith": "Viewer Only", "bob": "None"},
        "groupPerms": {"Finance": "Editor", "Interns": "None"},
    }


def test_set_stops_inheriting_and_keeps_parent(run: Callable[..., Runner]) -> None:
    result, sent = run(lambda r: respond())(
        "perms", "set", "/Shared/Docs", "--no-inherit", "--keep-parent", "-y"
    )

    assert result.exit_code == 0, result.output
    assert body(sent[0]) == {
        "inheritsPermissions": False,
        "keepParentPermissions": True,
    }


def test_set_resumes_inheriting(run: Callable[..., Runner]) -> None:
    result, sent = run(lambda r: respond())(
        "perms", "set", "/Shared/Docs", "--inherit", "-y"
    )

    assert result.exit_code == 0, result.output
    assert body(sent[0]) == {"inheritsPermissions": True}


def test_set_asks_first_naming_the_folder(run: Callable[..., Runner]) -> None:
    invoke = run(lambda r: respond())
    args = (
        "perms",
        "set",
        "/Shared/Docs",
        "--user",
        "jdoe=Full",
        "--remove-group",
        "Interns",
        "--no-inherit",
    )

    declined, sent = invoke(*args, input="n\n")
    assert declined.exit_code == 1
    assert (
        "Change permissions on /Shared/Docs: user jdoe -> Full, "
        "group Interns -> removed, stop inheriting?"
    ) in declined.output
    assert not sent

    confirmed, sent = invoke(*args, input="y\n")
    assert confirmed.exit_code == 0, confirmed.output
    assert body(sent[0]) == {
        "userPerms": {"jdoe": "Full"},
        "groupPerms": {"Interns": "None"},
        "inheritsPermissions": False,
    }


@pytest.mark.parametrize(
    ("grant", "message"),
    [
        ("jdoe", "expected NAME=LEVEL, got 'jdoe'."),
        ("=Full", "expected NAME=LEVEL, got '=Full'."),
        ("jdoe=", "expected NAME=LEVEL, got 'jdoe='."),
        ("jdoe=Admin", "'Admin' is not a level; use one of 'Viewer Only', 'Viewer',"),
        ("jdoe=None", "use --remove-user or --remove-group to remove a permission."),
    ],
)
def test_set_rejects_a_bad_grant(
    run: Callable[..., Runner], grant: str, message: str
) -> None:
    result, sent = run(lambda r: respond())(
        "perms", "set", "/Shared/Docs", "--user", grant, "-y"
    )

    assert result.exit_code == 2
    assert "Invalid value for '--user'" in result.output
    assert message in result.output
    assert not sent


def test_set_splits_a_grant_at_the_last_equals(run: Callable[..., Runner]) -> None:
    result, sent = run(lambda r: respond())(
        "perms", "set", "/Shared/Docs", "--group", "R=D=Viewer", "-y"
    )

    assert result.exit_code == 0, result.output
    assert body(sent[0]) == {"groupPerms": {"R=D": "Viewer"}}


@pytest.mark.parametrize(
    ("args", "message"),
    [
        ((), "Nothing to change"),
        (("--keep-parent",), "--keep-parent applies only with --no-inherit."),
        (
            ("--inherit", "--keep-parent"),
            "--keep-parent applies only with --no-inherit.",
        ),
        (
            ("--user", "jdoe=Full", "--remove-user", "jdoe"),
            "The user 'jdoe' is named more than once.",
        ),
        (
            ("--group", "Finance=Full", "--group", "Finance=Viewer"),
            "The group 'Finance' is named more than once.",
        ),
    ],
)
def test_set_rejects_bad_usage(
    run: Callable[..., Runner], args: tuple[str, ...], message: str
) -> None:
    result, sent = run(lambda r: respond())("perms", "set", "/Shared/Docs", *args, "-y")

    assert result.exit_code == 2
    assert message in result.output
    assert not sent
