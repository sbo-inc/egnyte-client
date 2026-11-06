from collections.abc import Callable

import httpx
import pytest
from conftest import body, respond

from egnyte_client.async_client import AsyncEgnyteClient
from egnyte_client.client import EgnyteClient

FOLDER_PERMISSIONS = {
    "userPerms": {"jdoe": "Full", "asmith": "Viewer"},
    "groupPerms": {"All Administrators": "Owner", "Marketing Team": "Editor"},
    "inheritsPermissions": True,
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
# TEST: get_effective_permission
# =============================================================================


def test_effective_permission_defaults_to_the_caller(
    make_client: Callable[..., EgnyteClient],
) -> None:
    client, sent = _client(make_client, respond({"permission": "Owner"}))

    level = client.get_effective_permission("Shared/Docs/")

    assert sent[0].method == "GET"
    # Live: omitting the username segment answers for the token's user.
    assert sent[0].url.path == "/pubapi/v1/perms/user"
    assert dict(sent[0].url.params) == {"folder": "/Shared/Docs"}
    assert level == "Owner"


def test_effective_permission_for_a_named_user(
    make_client: Callable[..., EgnyteClient],
) -> None:
    client, sent = _client(make_client, respond({"permission": "Nav"}))

    level = client.get_effective_permission("/Shared/Docs", username="jdoe@acme")

    assert sent[0].url.raw_path.startswith(b"/pubapi/v1/perms/user/jdoe%40acme?")
    assert level == "Nav"


# =============================================================================
# TEST: get_folder_permissions
# =============================================================================


def test_get_folder_permissions(make_client: Callable[..., EgnyteClient]) -> None:
    client, sent = _client(make_client, respond(FOLDER_PERMISSIONS))

    permissions = client.get_folder_permissions("/Shared/Q3 plan?")

    assert sent[0].method == "GET"
    # The docs' "no leading slash" is relative to /v2/perms/.
    assert sent[0].url.raw_path == b"/pubapi/v2/perms/Shared/Q3%20plan%3F"
    assert permissions.user_permissions == {"jdoe": "Full", "asmith": "Viewer"}
    assert permissions.group_permissions["All Administrators"] == "Owner"
    assert permissions.inherits_permissions is True


def test_get_folder_permissions_without_grants(
    make_client: Callable[..., EgnyteClient],
) -> None:
    client, _ = _client(make_client, respond({"inheritsPermissions": False}))

    permissions = client.get_folder_permissions("/Shared/Docs")

    assert permissions.user_permissions == {}
    assert permissions.group_permissions == {}


# =============================================================================
# TEST: set_folder_permissions
# =============================================================================


def test_set_folder_permissions_maps_none_to_removal(
    make_client: Callable[..., EgnyteClient],
) -> None:
    client, sent = _client(make_client, respond())

    result = client.set_folder_permissions(
        "Shared/Docs",
        user_permissions={"jdoe": "Viewer", "asmith": None},
        group_permissions={"Project Team": "Full", "Contractors": None},
    )

    assert result is None
    assert sent[0].method == "POST"
    assert sent[0].url.path == "/pubapi/v2/perms/Shared/Docs"
    assert body(sent[0]) == {
        "userPerms": {"jdoe": "Viewer", "asmith": "None"},
        "groupPerms": {"Project Team": "Full", "Contractors": "None"},
    }


def test_set_folder_permissions_breaks_inheritance(
    make_client: Callable[..., EgnyteClient],
) -> None:
    client, sent = _client(make_client, respond())

    client.set_folder_permissions(
        "/Shared/Docs", inherits_permissions=False, keep_parent_permissions=True
    )

    assert body(sent[0]) == {
        "inheritsPermissions": False,
        "keepParentPermissions": True,
    }


@pytest.mark.parametrize("inherits", [None, True])
def test_keep_parent_permissions_needs_inheritance_off(
    make_client: Callable[..., EgnyteClient], inherits: bool | None
) -> None:
    client, sent = _client(make_client, respond())

    with pytest.raises(ValueError, match="inherits_permissions=False"):
        client.set_folder_permissions(
            "/Shared/Docs",
            inherits_permissions=inherits,
            keep_parent_permissions=False,
        )
    assert sent == []


# =============================================================================
# TEST: async
# =============================================================================


async def test_async_permissions(
    make_async_client: Callable[..., AsyncEgnyteClient],
) -> None:
    sent: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(request)
        if request.method == "POST":
            return respond()
        if request.url.path.startswith("/pubapi/v1/"):
            return respond({"permission": "Editor"})
        return respond(FOLDER_PERMISSIONS)

    client = make_async_client(handler)

    assert await client.get_effective_permission("/Shared/Docs") == "Editor"
    permissions = await client.get_folder_permissions("/Shared/Docs")
    await client.set_folder_permissions("/Shared/Docs", user_permissions={"jdoe": None})

    assert permissions.inherits_permissions is True
    assert body(sent[2]) == {"userPerms": {"jdoe": "None"}}
