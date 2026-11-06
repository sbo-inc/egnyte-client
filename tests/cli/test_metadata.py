"""
Coverage of the `metadata` commands against a mock-transport client.

Each command is asserted on the request it sends and the output it renders;
malformed JSON and invalid definitions must stop before any request.
"""

import json
from collections.abc import Callable
from typing import Any, get_args

import httpx
import pytest
from click.testing import Result
from conftest import body, respond

from egnyte_client.cli.commands import metadata
from egnyte_client.schemas.metadata import (
    DocumentType,
    MetadataKeyType,
    MetadataScope,
    MetadataScopeType,
)

Runner = Callable[..., tuple[Result, list[httpx.Request]]]

NAMESPACES = "/pubapi/v1/properties/namespace"

NAMESPACE: dict[str, Any] = {
    "name": "finance",
    "displayName": "Finance",
    "keys": {
        "status": {
            "type": "enum",
            "data": ["open", "closed"],
            "helpText": "Where the document stands",
        }
    },
    "scope": "PUBLIC",
    "metadataScopeType": "FOLDER_SCOPE",
    "folderAssociations": [{"folderId": "f-1", "path": "/Shared/Finance"}],
}

VALUES: dict[str, Any] = {
    "results": [{"finance": {"tags": ["alpha", "beta"], "due": 1793836800000}}]
}

KEYS = {
    "status": {
        "type": "enum",
        "helpText": "Where the document stands",
        "data": ["open", "closed"],
    }
}


@pytest.fixture
def run(cli_runner: Callable[..., Runner]) -> Callable[..., Runner]:
    """
    Return a factory for a runner invoking the CLI `metadata` group against a handler.

    Returns:
        Callable[..., Runner]: Takes a handler, gives back the runner.
    """
    return lambda handler: cli_runner(handler, prefix=("metadata",))


def _json(result: Result) -> Any:
    assert result.exit_code == 0, result.output
    return json.loads(result.stdout)


def _refused(result: Result, sent: list[httpx.Request], *messages: str) -> None:
    assert result.exit_code == 2, result.output
    for message in messages:
        assert message in result.stderr
    assert not sent


def test_choices_match_the_client_literals() -> None:
    assert metadata.KEY_TYPES.choices == get_args(MetadataKeyType.__value__)
    assert metadata.SCOPES.choices == get_args(MetadataScope.__value__)
    assert metadata.SCOPE_TYPES.choices == get_args(MetadataScopeType.__value__)
    assert metadata.DOCUMENT_TYPES.choices == get_args(DocumentType.__value__)


# =============================================================================
# TEST: namespaces
# =============================================================================


def test_namespaces_list(run: Callable[..., Runner]) -> None:
    result, sent = run(lambda r: respond([NAMESPACE]))(
        "namespaces", "list", "--folder-associations"
    )

    output = _json(result)
    assert output[0]["name"] == "finance"
    assert output[0]["folder_associations"] == [
        {"folder_id": "f-1", "path": "/Shared/Finance"}
    ]
    assert sent[0].method == "GET"
    assert sent[0].url.path == NAMESPACES
    assert sent[0].url.params["includeFolderAssociations"] == "true"


def test_namespaces_list_without_associations(run: Callable[..., Runner]) -> None:
    result, sent = run(lambda r: respond([]))("namespaces", "list")

    assert _json(result) == []
    assert "includeFolderAssociations" not in sent[0].url.params


def test_namespaces_get(run: Callable[..., Runner]) -> None:
    result, sent = run(lambda r: respond(NAMESPACE))("namespaces", "get", "fin ance")

    output = _json(result)
    assert output["display_name"] == "Finance"
    assert output["keys"]["status"]["help_text"] == "Where the document stands"
    assert sent[0].method == "GET"
    assert sent[0].url.raw_path == b"/pubapi/v1/properties/namespace/fin%20ance"


def test_namespaces_create(run: Callable[..., Runner]) -> None:
    result, sent = run(lambda r: respond(status=201))(
        "namespaces",
        "create",
        "finance",
        "--keys",
        json.dumps(KEYS),
        "--scope",
        "protected",
        "--display-name",
        "Finance",
        "--no-inheritable",
        "--scope-type",
        "FOLDER_SCOPE",
        "--folder-id",
        "f-1",
        "--folder-id",
        "f-2",
    )

    assert result.exit_code == 0, result.output
    assert result.stdout == ""
    assert "Created namespace finance" in result.stderr
    assert sent[0].method == "POST"
    assert sent[0].url.path == NAMESPACES
    assert body(sent[0]) == {
        "name": "finance",
        "scope": "protected",
        "keys": {
            "status": {
                "type": "enum",
                "helpText": "Where the document stands",
                "data": ["open", "closed"],
            }
        },
        "displayName": "Finance",
        "inheritable": False,
        "metadataScopeType": "FOLDER_SCOPE",
        "associatedFolderIds": ["f-1", "f-2"],
    }


def test_namespaces_create_document_type(run: Callable[..., Runner]) -> None:
    keys = {"due": {"type": "date", "help_text": "The date the document is due"}}
    result, sent = run(lambda r: respond(status=201))(
        "namespaces",
        "create",
        "contracts",
        "--keys",
        json.dumps(keys),
        "--scope-type",
        "DOCUMENT_TYPE",
        "--document-type",
        "PDF",
    )

    assert result.exit_code == 0, result.output
    assert body(sent[0]) == {
        "name": "contracts",
        "scope": "public",
        "keys": {"due": {"type": "date", "helpText": "The date the document is due"}},
        "metadataScopeType": "DOCUMENT_TYPE",
        "documentTypes": ["PDF"],
    }


@pytest.mark.parametrize(
    ("keys", "message"),
    [
        ("{not json", "expected a JSON document"),
        ("[]", "Input should be a valid dictionary"),
        ("{}", "a namespace needs at least one key"),
        (
            json.dumps({"status": {"type": "enum", "helpText": "x" * 20}}),
            "needs its allowed values in data",
        ),
        (
            json.dumps({"status": {"type": "string", "helpText": "short"}}),
            "status.helpText: String should have at least 20 characters",
        ),
        (
            json.dumps({"status": {"type": "text", "helpText": "x" * 20}}),
            "status.type: Input should be",
        ),
    ],
)
def test_namespaces_create_refuses_bad_keys(
    run: Callable[..., Runner], keys: str, message: str
) -> None:
    result, sent = run(lambda r: respond())(
        "namespaces", "create", "finance", "--keys", keys
    )

    _refused(result, sent, "--keys", message)


def test_namespaces_create_document_type_needs_types(
    run: Callable[..., Runner],
) -> None:
    result, sent = run(lambda r: respond())(
        "namespaces",
        "create",
        "contracts",
        "--keys",
        json.dumps(KEYS),
        "--scope-type",
        "DOCUMENT_TYPE",
    )

    _refused(result, sent, "--scope-type DOCUMENT_TYPE needs --document-type.")


def test_namespaces_update(run: Callable[..., Runner]) -> None:
    result, sent = run(lambda r: respond(NAMESPACE))(
        "namespaces",
        "update",
        "finance",
        "--display-name",
        "Finance",
        "--priority",
        "status=3",
        "--priority",
        "due=1",
        "--associate-folder",
        "f-1",
        "--dissociate-folder",
        "f-9",
    )

    assert _json(result)["name"] == "finance"
    assert sent[0].method == "PATCH"
    assert sent[0].url.path == f"{NAMESPACES}/finance"
    assert body(sent[0]) == {
        "displayName": "Finance",
        "priorities": {"status": 3, "due": 1},
        "folderAssociation": {
            "associateFolderIds": ["f-1"],
            "dissociateFolderIds": ["f-9"],
        },
    }


def test_namespaces_update_document_types(run: Callable[..., Runner]) -> None:
    result, sent = run(lambda r: respond(NAMESPACE))(
        "namespaces",
        "update",
        "finance",
        "--associate-document-type",
        "PDF",
        "--dissociate-document-type",
        "IMAGE",
    )

    assert result.exit_code == 0, result.output
    assert body(sent[0]) == {
        "documentTypeAssociation": {
            "associateDocumentTypes": ["PDF"],
            "dissociateDocumentTypes": ["IMAGE"],
        }
    }


@pytest.mark.parametrize(
    ("args", "message"),
    [
        ((), "Give at least one change."),
        (
            ("--associate-folder", "f-1", "--associate-document-type", "PDF"),
            "cannot change in one call",
        ),
        (("--priority", "status"), "expected KEY=VALUE"),
        (("--priority", "status=high"), "integer priority"),
    ],
)
def test_namespaces_update_refusals(
    run: Callable[..., Runner], args: tuple[str, ...], message: str
) -> None:
    result, sent = run(lambda r: respond(NAMESPACE))(
        "namespaces", "update", "finance", *args
    )

    _refused(result, sent, message)


def test_namespaces_delete_asks_first(run: Callable[..., Runner]) -> None:
    invoke = run(lambda r: respond())

    declined, sent = invoke("namespaces", "delete", "finance", input="n\n")
    assert declined.exit_code == 1
    assert "Delete metadata namespace finance" in declined.output
    assert not sent

    confirmed, sent = invoke("namespaces", "delete", "finance", "--yes")
    assert confirmed.exit_code == 0, confirmed.output
    assert "Deleted namespace finance" in confirmed.stderr
    assert sent[0].method == "DELETE"
    assert sent[0].url.path == f"{NAMESPACES}/finance"
    assert "X-Egnyte-Force-Delete" not in sent[0].headers


def test_namespaces_delete_force(run: Callable[..., Runner]) -> None:
    result, sent = run(lambda r: respond())(
        "namespaces", "delete", "finance", "--force", "-y"
    )

    assert result.exit_code == 0, result.output
    assert sent[0].headers["X-Egnyte-Force-Delete"] == "Yes"


def test_namespaces_delete_values(run: Callable[..., Runner]) -> None:
    invoke = run(lambda r: respond())

    declined, sent = invoke(
        "namespaces", "delete-values", "finance", "--value", "status=closed"
    )
    assert declined.exit_code == 1
    assert not sent

    result, sent = invoke(
        "namespaces",
        "delete-values",
        "finance",
        "--values",
        json.dumps({"tags": ["alpha", "beta"]}),
        "--value",
        "status=closed",
        "--value",
        "tags=gamma",
        "--force",
        "--yes",
    )

    assert result.exit_code == 0, result.output
    assert sent[0].method == "PATCH"
    assert sent[0].url.path == f"{NAMESPACES}/finance/keys/data"
    assert sent[0].headers["X-Egnyte-Force-Delete"] == "Yes"
    assert body(sent[0]) == {
        "keyDataDeletions": [
            {"key": "tags", "data": ["alpha", "beta", "gamma"]},
            {"key": "status", "data": ["closed"]},
        ]
    }


@pytest.mark.parametrize(
    ("args", "message"),
    [
        ((), "Give --values or --value."),
        (("--values", "{oops"), "expected a JSON document"),
        (("--values", '{"tags": "alpha"}'), "tags: Input should be a valid list"),
        (("--value", "tags"), "expected KEY=VALUE"),
    ],
)
def test_namespaces_delete_values_refusals(
    run: Callable[..., Runner], args: tuple[str, ...], message: str
) -> None:
    result, sent = run(lambda r: respond())(
        "namespaces", "delete-values", "finance", "--yes", *args
    )

    _refused(result, sent, message)


# =============================================================================
# TEST: keys
# =============================================================================


def test_keys_add(run: Callable[..., Runner]) -> None:
    result, sent = run(lambda r: respond(status=201))(
        "keys",
        "add",
        "finance",
        "status",
        "--type",
        "enum",
        "--help-text",
        "Where the document stands",
        "--display-name",
        "Status",
        "--priority",
        "2",
        "--data",
        "open",
        "--data",
        "closed",
    )

    assert result.exit_code == 0, result.output
    assert "Added key status to finance" in result.stderr
    assert sent[0].method == "POST"
    assert sent[0].url.path == f"{NAMESPACES}/finance/keys"
    assert body(sent[0]) == {
        "key": "status",
        "type": "enum",
        "helpText": "Where the document stands",
        "displayName": "Status",
        "priority": 2,
        "data": ["open", "closed"],
    }


def test_keys_add_date(run: Callable[..., Runner]) -> None:
    result, sent = run(lambda r: respond(status=201))(
        "keys",
        "add",
        "finance",
        "due",
        "--type",
        "date",
        "--help-text",
        "The date the document is due",
        "--timezone-independent",
    )

    assert result.exit_code == 0, result.output
    assert body(sent[0]) == {
        "key": "due",
        "type": "date",
        "helpText": "The date the document is due",
        "timezoneIndependent": True,
    }


@pytest.mark.parametrize(
    ("args", "message"),
    [
        (
            ("--type", "string", "--help-text", "too short"),
            "String should have at least 20 characters",
        ),
        (
            ("--type", "enum", "--help-text", "Where the document stands"),
            "needs its allowed values in data",
        ),
        (
            (
                "--type",
                "string",
                "--help-text",
                "Where the document stands",
                "--timezone-independent",
            ),
            "applies to date keys only",
        ),
    ],
)
def test_keys_add_refusals(
    run: Callable[..., Runner], args: tuple[str, ...], message: str
) -> None:
    result, sent = run(lambda r: respond())("keys", "add", "finance", "status", *args)

    _refused(result, sent, message)


def test_keys_update(run: Callable[..., Runner]) -> None:
    result, sent = run(lambda r: respond())(
        "keys",
        "update",
        "finance",
        "status",
        "--type",
        "string",
        "--help-text",
        "Where the document stands now",
        "--data",
        "archived",
    )

    assert result.exit_code == 0, result.output
    assert "Updated key status of finance" in result.stderr
    assert sent[0].method == "PATCH"
    assert sent[0].url.path == f"{NAMESPACES}/finance/keys/status"
    assert body(sent[0]) == {
        "helpText": "Where the document stands now",
        "type": "string",
        "data": ["archived"],
    }


@pytest.mark.parametrize(
    ("args", "message"),
    [
        ((), "Give at least one change."),
        (("--help-text", "short"), "String should have at least 20 characters"),
    ],
)
def test_keys_update_refusals(
    run: Callable[..., Runner], args: tuple[str, ...], message: str
) -> None:
    result, sent = run(lambda r: respond())(
        "keys", "update", "finance", "status", *args
    )

    _refused(result, sent, message)


def test_keys_delete_asks_first(run: Callable[..., Runner]) -> None:
    invoke = run(lambda r: respond())

    declined, sent = invoke("keys", "delete", "finance", "status", input="n\n")
    assert declined.exit_code == 1
    assert "Delete key status of namespace finance" in declined.output
    assert not sent

    confirmed, sent = invoke("keys", "delete", "finance", "status", "-y", "--force")
    assert confirmed.exit_code == 0, confirmed.output
    assert sent[0].method == "DELETE"
    assert sent[0].url.path == f"{NAMESPACES}/finance/keys/status"
    assert sent[0].headers["X-Egnyte-Force-Delete"] == "Yes"


def test_keys_delete_values(run: Callable[..., Runner]) -> None:
    invoke = run(lambda r: respond())

    declined, sent = invoke(
        "keys", "delete-values", "finance", "tags", "alpha", "beta", input="n\n"
    )
    assert declined.exit_code == 1
    assert "Remove alpha, beta from key tags" in declined.output
    assert not sent

    confirmed, sent = invoke(
        "keys", "delete-values", "finance", "tags", "alpha", "beta", "--yes"
    )
    assert confirmed.exit_code == 0, confirmed.output
    assert sent[0].method == "PATCH"
    assert sent[0].url.path == f"{NAMESPACES}/finance/keys/tags/data"
    assert "X-Egnyte-Force-Delete" not in sent[0].headers
    assert body(sent[0]) == ["alpha", "beta"]


def test_keys_delete_values_needs_a_value(run: Callable[..., Runner]) -> None:
    result, sent = run(lambda r: respond())(
        "keys", "delete-values", "finance", "tags", "--yes"
    )

    _refused(result, sent, "Missing argument 'VALUES...'")


# =============================================================================
# TEST: values on files and folders
# =============================================================================


@pytest.mark.parametrize(
    ("flag", "kind"), [("--file-id", "file"), ("--folder-id", "folder")]
)
def test_get(run: Callable[..., Runner], flag: str, kind: str) -> None:
    result, sent = run(lambda r: respond(VALUES))("get", "finance", flag, "id-1")

    assert _json(result) == {"tags": ["alpha", "beta"], "due": 1793836800000}
    assert sent[0].method == "GET"
    assert sent[0].url.path == f"/pubapi/v1/fs/ids/{kind}/id-1/properties/finance"


@pytest.mark.parametrize(
    "args", [(), ("--file-id", "g-1", "--folder-id", "f-1")], ids=["none", "both"]
)
def test_get_needs_exactly_one_item(
    run: Callable[..., Runner], args: tuple[str, ...]
) -> None:
    result, sent = run(lambda r: respond(VALUES))("get", "finance", *args)

    _refused(result, sent, "Give exactly one of --file-id or --folder-id.")


@pytest.mark.parametrize(
    ("flag", "kind"), [("--file-id", "file"), ("--folder-id", "folder")]
)
def test_set(run: Callable[..., Runner], flag: str, kind: str) -> None:
    result, sent = run(lambda r: respond())(
        "set",
        "finance",
        flag,
        "id-1",
        "--values",
        json.dumps({"amount": 12.5, "tags": ["alpha"], "due": 1793836800000}),
        "--value",
        "status=open",
        "--value",
        "note=a=b",
        "--remove",
        "owner",
    )

    assert result.exit_code == 0, result.output
    assert result.stdout == ""
    assert f"Set 6 values of finance on {kind} id-1" in result.stderr
    assert sent[0].method == "PUT"
    assert sent[0].url.path == f"/pubapi/v1/fs/ids/{kind}/id-1/properties/finance"
    assert body(sent[0]) == {
        "amount": 12.5,
        "tags": ["alpha"],
        "due": 1793836800000,
        "status": "open",
        "note": "a=b",
        "owner": None,
    }


@pytest.mark.parametrize(
    ("args", "message"),
    [
        ((), "Give --values, --value, or --remove."),
        (("--values", "{oops"), "expected a JSON document"),
        (("--values", '["a"]'), "expected a JSON object"),
        (
            ("--values", '{"a": {"b": 1}, "c": "ok"}'),
            "a: expected text, a number, a list of text, or null",
        ),
        (("--value", "status"), "expected KEY=VALUE"),
        (("--value", "=open"), "expected KEY=VALUE"),
        (("--value", "status=a", "--value", "status=b"), "more than once: status"),
        (
            ("--values", '{"status": "a"}', "--remove", "status"),
            "more than once: status",
        ),
        (("--folder-id", "f-1", "--value", "status=a"), "Give exactly one"),
    ],
)
def test_set_refusals(
    run: Callable[..., Runner], args: tuple[str, ...], message: str
) -> None:
    result, sent = run(lambda r: respond())("set", "finance", "--file-id", "g-1", *args)

    _refused(result, sent, message)
