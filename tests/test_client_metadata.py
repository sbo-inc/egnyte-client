from collections.abc import Callable
from datetime import UTC, date, datetime
from typing import Any

import httpx
import pytest
from conftest import body, respond
from pydantic import ValidationError

from egnyte_client.async_client import AsyncEgnyteClient
from egnyte_client.client import EgnyteClient
from egnyte_client.schemas.metadata import MetadataKeyDefinition

# Shaped after a live namespace read; Egnyte answers the scope in upper case
# although requests send it in lower case.
NAMESPACE: dict[str, Any] = {
    "name": "finance",
    "displayName": "Finance",
    "priority": 0,
    "keys": {
        "tags": {
            "type": "multi_value_enum",
            "data": ["alpha", "beta", "gamma"],
            "displayName": "tags",
            "helpText": "Tags that describe the document",
            "priority": 0,
        },
        "due": {
            "type": "date",
            "displayName": "due",
            "helpText": "The date the document is due by",
            "priority": 2,
            "timezoneIndependent": False,
        },
    },
    "scope": "PUBLIC",
    "schemaSystemGenerated": False,
    "metadataScopeType": "GLOBAL",
    "inheritable": False,
}

FOLDER_SCOPED: dict[str, Any] = {
    **NAMESPACE,
    "metadataScopeType": "FOLDER_SCOPE",
    "folderAssociations": [{"folderId": "f-1", "path": "/Shared/Finance"}],
    "hasAccessToAllAssociations": True,
}

# Shaped after a live file read: dates come back as epoch milliseconds.
VALUES: dict[str, Any] = {
    "results": [{"finance": {"tags": ["alpha", "beta"], "due": 1793836800000}}]
}

HELP = "Tags that describe the document"


def _client(
    make_client: Callable[..., EgnyteClient], response: httpx.Response
) -> tuple[EgnyteClient, list[httpx.Request]]:
    sent: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(request)
        return response

    return make_client(handler), sent


# =============================================================================
# TEST: namespaces
# =============================================================================


def test_list_metadata_namespaces(make_client: Callable[..., EgnyteClient]) -> None:
    client, sent = _client(make_client, respond([NAMESPACE, FOLDER_SCOPED]))

    namespaces = client.list_metadata_namespaces(include_folder_associations=True)

    assert sent[0].method == "GET"
    assert sent[0].url.path == "/pubapi/v1/properties/namespace"
    assert dict(sent[0].url.params) == {"includeFolderAssociations": "true"}
    assert namespaces[0].name == "finance"
    assert namespaces[0].scope == "PUBLIC"
    assert namespaces[0].keys["tags"].data == ["alpha", "beta", "gamma"]
    assert namespaces[0].keys["due"].timezone_independent is False
    assert namespaces[0].folder_associations == []
    assert namespaces[1].folder_associations[0].folder_id == "f-1"
    assert namespaces[1].has_access_to_all_associations is True


def test_create_metadata_namespace(make_client: Callable[..., EgnyteClient]) -> None:
    client, sent = _client(make_client, respond(status=204))

    result = client.create_metadata_namespace(
        "finance",
        keys={
            "tags": MetadataKeyDefinition(
                type="multi_value_enum", help_text=HELP, data=["alpha", "beta"]
            ),
            "due": MetadataKeyDefinition(
                type="date",
                help_text="The date the document is due by",
                display_name="Due date",
                priority=2,
                timezone_independent=True,
            ),
        },
        display_name="Finance",
        scope_type="FOLDER_SCOPE",
        folder_ids=["f-1"],
    )

    assert result is None
    assert sent[0].method == "POST"
    assert sent[0].url.path == "/pubapi/v1/properties/namespace"
    assert body(sent[0]) == {
        "name": "finance",
        "scope": "public",
        "keys": {
            "tags": {
                "type": "multi_value_enum",
                "helpText": HELP,
                "data": ["alpha", "beta"],
            },
            "due": {
                "type": "date",
                "helpText": "The date the document is due by",
                "displayName": "Due date",
                "priority": 2,
                "timezoneIndependent": True,
            },
        },
        "displayName": "Finance",
        "metadataScopeType": "FOLDER_SCOPE",
        "associatedFolderIds": ["f-1"],
    }


def test_create_document_type_namespace_needs_document_types(
    make_client: Callable[..., EgnyteClient],
) -> None:
    client, sent = _client(make_client, respond(status=204))
    keys = {"note": MetadataKeyDefinition(type="string", help_text=HELP)}

    with pytest.raises(ValueError, match="document_types"):
        client.create_metadata_namespace(
            "finance", keys=keys, scope_type="DOCUMENT_TYPE"
        )
    with pytest.raises(ValueError, match="at least one key"):
        client.create_metadata_namespace("finance", keys={})
    assert sent == []


@pytest.mark.parametrize(
    ("fields", "match"),
    [
        ({"type": "enum", "help_text": HELP}, "allowed values"),
        ({"type": "string", "help_text": "too short"}, "at least 20"),
        (
            {"type": "string", "help_text": HELP, "timezone_independent": True},
            "date keys only",
        ),
    ],
)
def test_key_definition_rules(fields: dict[str, Any], match: str) -> None:
    with pytest.raises(ValidationError, match=match):
        MetadataKeyDefinition(**fields)


def test_get_metadata_namespace_encodes_the_name(
    make_client: Callable[..., EgnyteClient],
) -> None:
    client, sent = _client(make_client, respond(NAMESPACE))

    namespace = client.get_metadata_namespace("fin ance/x")

    assert sent[0].url.raw_path == b"/pubapi/v1/properties/namespace/fin%20ance%2Fx"
    assert namespace.metadata_scope_type == "GLOBAL"
    assert namespace.keys["due"].priority == 2


def test_update_metadata_namespace(make_client: Callable[..., EgnyteClient]) -> None:
    client, sent = _client(make_client, respond(FOLDER_SCOPED))

    namespace = client.update_metadata_namespace(
        "finance",
        display_name="Finance team",
        priorities={"due": 5, "tags": 1},
        associate_folder_ids=["f-2"],
    )

    assert sent[0].method == "PATCH"
    assert sent[0].url.path == "/pubapi/v1/properties/namespace/finance"
    assert body(sent[0]) == {
        "displayName": "Finance team",
        "priorities": {"due": 5, "tags": 1},
        "folderAssociation": {"associateFolderIds": ["f-2"]},
    }
    assert namespace.folder_associations[0].path == "/Shared/Finance"


def test_update_metadata_namespace_document_types(
    make_client: Callable[..., EgnyteClient],
) -> None:
    client, sent = _client(make_client, respond(NAMESPACE))

    client.update_metadata_namespace(
        "finance", associate_document_types=["PDF"], dissociate_document_types=["CAD"]
    )

    assert body(sent[0]) == {
        "documentTypeAssociation": {
            "associateDocumentTypes": ["PDF"],
            "dissociateDocumentTypes": ["CAD"],
        }
    }


def test_update_metadata_namespace_refusals(
    make_client: Callable[..., EgnyteClient],
) -> None:
    client, sent = _client(make_client, respond(NAMESPACE))

    with pytest.raises(ValueError, match="cannot change in one request"):
        client.update_metadata_namespace(
            "finance", associate_folder_ids=["f-1"], associate_document_types=["PDF"]
        )
    with pytest.raises(ValueError, match="at least one change"):
        client.update_metadata_namespace("finance")
    assert sent == []


def test_delete_metadata_namespace(make_client: Callable[..., EgnyteClient]) -> None:
    # Live, the delete answers 202 rather than the documented 204.
    client, sent = _client(make_client, respond(status=202))

    client.delete_metadata_namespace("finance")
    client.delete_metadata_namespace("finance", force=True)

    assert sent[0].method == "DELETE"
    assert sent[0].url.path == "/pubapi/v1/properties/namespace/finance"
    assert "X-Egnyte-Force-Delete" not in sent[0].headers
    assert sent[1].headers["X-Egnyte-Force-Delete"] == "Yes"


# =============================================================================
# TEST: keys
# =============================================================================


def test_add_metadata_key(make_client: Callable[..., EgnyteClient]) -> None:
    client, sent = _client(make_client, respond(status=204))

    client.add_metadata_key(
        "finance", "status", "enum", HELP, data=["open", "closed"], priority=3
    )

    assert sent[0].method == "POST"
    assert sent[0].url.path == "/pubapi/v1/properties/namespace/finance/keys"
    assert body(sent[0]) == {
        "key": "status",
        "type": "enum",
        "helpText": HELP,
        "priority": 3,
        "data": ["open", "closed"],
    }


def test_add_metadata_key_needs_enum_values(
    make_client: Callable[..., EgnyteClient],
) -> None:
    client, sent = _client(make_client, respond(status=204))

    with pytest.raises(ValueError, match="allowed values"):
        client.add_metadata_key("finance", "status", "multi_value_enum", HELP)
    assert sent == []


def test_update_metadata_key(make_client: Callable[..., EgnyteClient]) -> None:
    client, sent = _client(make_client, respond(status=204))

    client.update_metadata_key(
        "finance", "due date", type="string", display_name="Due", priority=1
    )

    assert sent[0].method == "PATCH"
    assert sent[0].url.raw_path == (
        b"/pubapi/v1/properties/namespace/finance/keys/due%20date"
    )
    assert body(sent[0]) == {"displayName": "Due", "type": "string", "priority": 1}

    with pytest.raises(ValueError, match="at least one change"):
        client.update_metadata_key("finance", "due")


def test_delete_metadata_key(make_client: Callable[..., EgnyteClient]) -> None:
    client, sent = _client(make_client, respond(status=204))

    client.delete_metadata_key("finance", "tags", force=True)

    assert sent[0].method == "DELETE"
    assert sent[0].url.path == "/pubapi/v1/properties/namespace/finance/keys/tags"
    assert sent[0].headers["X-Egnyte-Force-Delete"] == "Yes"


def test_delete_metadata_key_values(make_client: Callable[..., EgnyteClient]) -> None:
    client, sent = _client(make_client, respond(status=204))

    client.delete_metadata_key_values("finance", "tags", ["gamma"])

    assert sent[0].method == "PATCH"
    assert sent[0].url.path == (
        "/pubapi/v1/properties/namespace/finance/keys/tags/data"
    )
    assert body(sent[0]) == ["gamma"]

    with pytest.raises(ValueError, match="at least one value"):
        client.delete_metadata_key_values("finance", "tags", [])


def test_delete_metadata_values(make_client: Callable[..., EgnyteClient]) -> None:
    client, sent = _client(make_client, respond(status=204))

    client.delete_metadata_values(
        "finance", {"tags": ["gamma"], "status": ["closed"], "empty": []}, force=True
    )

    assert sent[0].method == "PATCH"
    assert sent[0].url.path == "/pubapi/v1/properties/namespace/finance/keys/data"
    assert sent[0].headers["X-Egnyte-Force-Delete"] == "Yes"
    assert body(sent[0]) == {
        "keyDataDeletions": [
            {"key": "tags", "data": ["gamma"]},
            {"key": "status", "data": ["closed"]},
        ]
    }

    with pytest.raises(ValueError, match="at least one value"):
        client.delete_metadata_values("finance", {"tags": []})


# =============================================================================
# TEST: values
# =============================================================================


def test_set_file_metadata(make_client: Callable[..., EgnyteClient]) -> None:
    client, sent = _client(make_client, respond(status=204))

    client.set_file_metadata(
        "g-1",
        "finance",
        {
            "due": date(2026, 11, 5),
            "reviewed": datetime(2026, 11, 5, 12, 30),
            "tags": ["alpha"],
            "amount": 12.5,
            "count": 3,
            "note": "draft",
            "old": None,
        },
    )

    assert sent[0].method == "PUT"
    assert sent[0].url.path == "/pubapi/v1/fs/ids/file/g-1/properties/finance"
    assert body(sent[0]) == {
        "due": 1793836800000,
        "reviewed": int(datetime(2026, 11, 5, 12, 30, tzinfo=UTC).timestamp() * 1000),
        "tags": ["alpha"],
        "amount": 12.5,
        "count": 3,
        "note": "draft",
        "old": None,
    }


def test_set_metadata_needs_a_value(make_client: Callable[..., EgnyteClient]) -> None:
    client, sent = _client(make_client, respond(status=204))

    with pytest.raises(ValueError, match="at least one value"):
        client.set_folder_metadata("f-1", "finance", {})
    assert sent == []


def test_get_file_metadata(make_client: Callable[..., EgnyteClient]) -> None:
    client, sent = _client(make_client, respond(VALUES))

    values = client.get_file_metadata("g-1", "finance")

    assert sent[0].method == "GET"
    assert sent[0].url.path == "/pubapi/v1/fs/ids/file/g-1/properties/finance"
    assert values == {"tags": ["alpha", "beta"], "due": 1793836800000}


def test_set_and_get_folder_metadata(
    make_client: Callable[..., EgnyteClient],
) -> None:
    sent: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(request)
        if request.method == "PUT":
            return respond(status=204)
        return respond({"results": [{"finance": {"note": "draft", "count": None}}]})

    client = make_client(handler)
    client.set_folder_metadata("f-1", "finance", {"note": "draft"})
    values = client.get_folder_metadata("f-1", "finance")

    assert sent[0].url.path == "/pubapi/v1/fs/ids/folder/f-1/properties/finance"
    assert body(sent[0]) == {"note": "draft"}
    assert sent[1].url.path == "/pubapi/v1/fs/ids/folder/f-1/properties/finance"
    assert values == {"note": "draft"}


def test_get_metadata_of_an_unset_namespace(
    make_client: Callable[..., EgnyteClient],
) -> None:
    client, _ = _client(make_client, respond({"results": []}))

    assert client.get_folder_metadata("f-1", "finance") == {}


# =============================================================================
# TEST: async
# =============================================================================


async def test_async_metadata(
    make_async_client: Callable[..., AsyncEgnyteClient],
) -> None:
    sent: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(request)
        if request.url.path.endswith("/namespace"):
            return respond([NAMESPACE])
        if request.method == "PUT":
            return respond(status=204)
        return respond(VALUES)

    async with make_async_client(handler) as client:
        namespaces = await client.list_metadata_namespaces()
        await client.set_file_metadata("g-1", "finance", {"tags": ["beta"]})
        values = await client.get_file_metadata("g-1", "finance")

    assert namespaces[0].keys["tags"].type == "multi_value_enum"
    assert dict(sent[0].url.params) == {}
    assert body(sent[1]) == {"tags": ["beta"]}
    assert values["due"] == 1793836800000
