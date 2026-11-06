from collections.abc import Callable
from datetime import UTC, datetime

import httpx
import pytest
from conftest import GROUP, USER, body, respond, scim

from egnyte_client.client import EgnyteClient


def _client(
    make_client: Callable[..., EgnyteClient], response: httpx.Response
) -> tuple[EgnyteClient, list[httpx.Request]]:
    sent: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(request)
        return response

    return make_client(handler), sent


# =============================================================================
# TEST: users
# =============================================================================


def test_list_users_with_filter(make_client: Callable[..., EgnyteClient]) -> None:
    client, sent = _client(make_client, respond(scim([USER])))

    users = client.list_users(filter_by_user_name='j"doe', start_index=1, count=5)

    assert sent[0].url.path == "/pubapi/v2/users"
    assert dict(sent[0].url.params) == {
        "filter": 'userName eq "j\\"doe"',
        "startIndex": "1",
        "count": "5",
    }
    assert users[0].user_name == "jdoe"
    assert users[0].name.given_name == "Jane"
    assert users[0].created_date == datetime(2026, 11, 5, 19, 29, 22, tzinfo=UTC)
    assert users[0].groups[0].display_name == "Finance"


def test_list_users_refuses_two_filters(
    make_client: Callable[..., EgnyteClient],
) -> None:
    client, _ = _client(make_client, respond(scim([])))

    with pytest.raises(ValueError, match="one filter at a time"):
        client.list_users(filter_by_user_name="a", filter_by_email="b")


def test_get_user(make_client: Callable[..., EgnyteClient]) -> None:
    client, sent = _client(make_client, respond(USER))

    assert client.get_user(8).id == 8
    assert sent[0].url.path == "/pubapi/v2/users/8"


def test_create_user(make_client: Callable[..., EgnyteClient]) -> None:
    client, sent = _client(make_client, respond(USER, 201))

    client.create_user(
        "jdoe",
        "jdoe@acme.test",
        "Jane",
        "Doe",
        auth_type="sso",
        user_type="standard",
        send_invite=False,
    )

    assert sent[0].method == "POST"
    assert body(sent[0]) == {
        "userName": "jdoe",
        "email": "jdoe@acme.test",
        "name": {"givenName": "Jane", "familyName": "Doe"},
        "active": True,
        "authType": "sso",
        "userType": "standard",
        "sendInvite": False,
    }


def test_update_user_sends_only_changes(
    make_client: Callable[..., EgnyteClient],
) -> None:
    client, sent = _client(make_client, respond(USER))

    client.update_user(8, family_name="Smith", active=False)

    assert sent[0].method == "PATCH"
    assert sent[0].url.path == "/pubapi/v2/users/8"
    assert body(sent[0]) == {"name": {"familyName": "Smith"}, "active": False}


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [({}, "at least one field"), ({"send_invite": True}, "only field")],
)
def test_update_user_refuses_empty_updates(
    make_client: Callable[..., EgnyteClient], kwargs: dict[str, bool], message: str
) -> None:
    client, sent = _client(make_client, respond(USER))

    with pytest.raises(ValueError, match=message):
        client.update_user(8, **kwargs)
    assert not sent


def test_delete_user(make_client: Callable[..., EgnyteClient]) -> None:
    client, sent = _client(make_client, respond())

    assert client.delete_user(8) is None
    assert sent[0].method == "DELETE"


# =============================================================================
# TEST: groups
# =============================================================================


@pytest.mark.parametrize(
    ("kwargs", "expected"),
    [
        ({"filter_by_name": "Finance"}, 'displayName eq "Finance"'),
        ({"filter_by_name_contains": "fin"}, 'displayName co "fin"'),
        ({"filter_by_name_starts_with": "Fi"}, 'displayName sw "Fi"'),
    ],
)
def test_list_groups_filters(
    make_client: Callable[..., EgnyteClient], kwargs: dict[str, str], expected: str
) -> None:
    client, sent = _client(
        make_client, respond(scim([{"id": "grp-1", "displayName": "Finance"}]))
    )

    groups = client.list_groups(**kwargs)

    assert sent[0].url.params["filter"] == expected
    assert groups[0].display_name == "Finance"


def test_list_groups_refuses_two_filters(
    make_client: Callable[..., EgnyteClient],
) -> None:
    client, _ = _client(make_client, respond(scim([])))

    with pytest.raises(ValueError, match="Only one group name filter"):
        client.list_groups(filter_by_name="a", filter_by_name_contains="b")


def test_get_group(make_client: Callable[..., EgnyteClient]) -> None:
    client, sent = _client(make_client, respond(GROUP))

    group = client.get_group("grp-1")

    assert sent[0].url.path == "/pubapi/v2/groups/grp-1"
    assert group.members[0].user_id == 8
    assert group.members[0].username == "jdoe"


def test_create_group(make_client: Callable[..., EgnyteClient]) -> None:
    client, sent = _client(make_client, respond(GROUP, 201))

    client.create_group("Finance", [8, 9], owners=["jdoe"])

    assert body(sent[0]) == {
        "displayName": "Finance",
        "members": [{"value": 8}, {"value": 9}],
        "owners": ["jdoe"],
    }


def test_create_group_needs_a_member(make_client: Callable[..., EgnyteClient]) -> None:
    client, _ = _client(make_client, respond(GROUP))

    with pytest.raises(ValueError, match="at least one member"):
        client.create_group("Finance", [])


def test_replace_group(make_client: Callable[..., EgnyteClient]) -> None:
    client, sent = _client(make_client, respond(GROUP))

    client.replace_group("grp-1", "Finance", [8])

    assert sent[0].method == "PUT"
    assert body(sent[0]) == {"displayName": "Finance", "members": [{"value": 8}]}


def test_update_group_adds_and_removes(
    make_client: Callable[..., EgnyteClient],
) -> None:
    client, sent = _client(make_client, respond(GROUP))

    client.update_group(
        "grp-1", display_name="Ops", add_member_ids=[9], remove_member_ids=[8]
    )

    assert sent[0].method == "PATCH"
    assert body(sent[0]) == {
        "displayName": "Ops",
        "members": [{"value": 9}, {"value": 8, "operation": "delete"}],
    }


def test_update_group_refuses_no_changes(
    make_client: Callable[..., EgnyteClient],
) -> None:
    client, _ = _client(make_client, respond(GROUP))

    with pytest.raises(ValueError, match="at least one change"):
        client.update_group("grp-1")


def test_delete_group(make_client: Callable[..., EgnyteClient]) -> None:
    client, sent = _client(make_client, respond())

    assert client.delete_group("grp-1") is None
    assert sent[0].url.path == "/pubapi/v2/groups/grp-1"
