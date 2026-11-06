from collections.abc import Callable, Mapping
from datetime import UTC, date, datetime, time

import httpx
from pydantic import TypeAdapter

from egnyte_client.operations.generic import (
    Operation,
    empty,
    encode_id,
    epoch_ms,
    model,
    query,
)
from egnyte_client.schemas.metadata import (
    CreateMetadataKeyRequest,
    CreateNamespaceRequest,
    DeleteKeyDataRequest,
    DocumentType,
    DocumentTypeAssociationChange,
    FolderAssociationChange,
    KeyDataDeletion,
    KeyValuesRequest,
    MetadataKeyDefinition,
    MetadataKeyType,
    MetadataKeyValue,
    MetadataNamespace,
    MetadataScope,
    MetadataScopeType,
    MetadataValueInput,
    MetadataValuesRequest,
    MetadataValuesResponse,
    UpdateMetadataKeyRequest,
    UpdateNamespaceRequest,
)

NAMESPACES = "/v1/properties/namespace"
FORCE_DELETE = {"X-Egnyte-Force-Delete": "Yes"}

_NAMESPACE_LIST = TypeAdapter(list[MetadataNamespace])


def _namespace(namespace: str) -> str:
    return f"{NAMESPACES}/{encode_id(namespace)}"


def _key(namespace: str, key: str) -> str:
    return f"{_namespace(namespace)}/keys/{encode_id(key)}"


def _force(force: bool) -> dict[str, str]:
    return dict(FORCE_DELETE) if force else {}


# -----------------------------------------------------------------------------
# OPERATION: list_metadata_namespaces
# -----------------------------------------------------------------------------


def list_metadata_namespaces(
    *, include_folder_associations: bool | None = None
) -> Operation[list[MetadataNamespace]]:
    """
    Build the namespace listing.

    Returns:
        Operation[list[MetadataNamespace]]: The list namespaces operation.
    """
    return Operation(
        method="GET",
        path=NAMESPACES,
        params=query(includeFolderAssociations=include_folder_associations),
        parse=lambda response: _NAMESPACE_LIST.validate_json(response.content),
    )


# -----------------------------------------------------------------------------
# OPERATION: create_metadata_namespace
# -----------------------------------------------------------------------------


def create_metadata_namespace(
    name: str,
    *,
    keys: Mapping[str, MetadataKeyDefinition],
    scope: MetadataScope = "public",
    display_name: str | None = None,
    inheritable: bool | None = None,
    scope_type: MetadataScopeType | None = None,
    folder_ids: list[str] | None = None,
    document_types: list[DocumentType] | None = None,
) -> Operation[None]:
    """
    Build the namespace create.

    Returns:
        Operation[None]: The create namespace operation.
    """
    if not keys:
        raise ValueError("A namespace needs at least one key")
    if scope_type == "DOCUMENT_TYPE" and not document_types:
        raise ValueError("A DOCUMENT_TYPE namespace needs document_types")

    return Operation(
        method="POST",
        path=NAMESPACES,
        body=CreateNamespaceRequest(
            name=name,
            scope=scope,
            keys=dict(keys),
            display_name=display_name,
            inheritable=inheritable,
            metadata_scope_type=scope_type,
            associated_folder_ids=folder_ids,
            document_types=document_types,
        ),
        parse=empty,
    )


# -----------------------------------------------------------------------------
# OPERATION: get_metadata_namespace
# -----------------------------------------------------------------------------


def get_metadata_namespace(namespace: str) -> Operation[MetadataNamespace]:
    """
    Build the namespace read.

    Returns:
        Operation[MetadataNamespace]: The get namespace operation.
    """
    return Operation(
        method="GET", path=_namespace(namespace), parse=model(MetadataNamespace)
    )


# -----------------------------------------------------------------------------
# OPERATION: update_metadata_namespace
# -----------------------------------------------------------------------------


def update_metadata_namespace(
    namespace: str,
    *,
    display_name: str | None = None,
    priorities: Mapping[str, int] | None = None,
    associate_folder_ids: list[str] | None = None,
    dissociate_folder_ids: list[str] | None = None,
    associate_document_types: list[DocumentType] | None = None,
    dissociate_document_types: list[DocumentType] | None = None,
) -> Operation[MetadataNamespace]:
    """
    Build the namespace update: rename, reorder keys, or change associations.

    Returns:
        Operation[MetadataNamespace]: The update namespace operation.
    """
    folders = None
    if associate_folder_ids or dissociate_folder_ids:
        folders = FolderAssociationChange(
            associate_folder_ids=associate_folder_ids,
            dissociate_folder_ids=dissociate_folder_ids,
        )
    document_types = None
    if associate_document_types or dissociate_document_types:
        document_types = DocumentTypeAssociationChange(
            associate_document_types=associate_document_types,
            dissociate_document_types=dissociate_document_types,
        )
    if folders is not None and document_types is not None:
        raise ValueError(
            "Folder and document type associations cannot change in one request"
        )
    request = UpdateNamespaceRequest(
        display_name=display_name,
        priorities=dict(priorities) if priorities else None,
        folder_association=folders,
        document_type_association=document_types,
    )
    if not request.model_dump(exclude_none=True):
        raise ValueError("update_metadata_namespace needs at least one change")

    return Operation(
        method="PATCH",
        path=_namespace(namespace),
        body=request,
        parse=model(MetadataNamespace),
    )


# -----------------------------------------------------------------------------
# OPERATION: delete_metadata_namespace
# -----------------------------------------------------------------------------


def delete_metadata_namespace(
    namespace: str, *, force: bool = False
) -> Operation[None]:
    """
    Build the namespace delete.

    Returns:
        Operation[None]: The delete namespace operation.
    """
    return Operation(
        method="DELETE",
        path=_namespace(namespace),
        headers=_force(force),
        parse=empty,
    )


# -----------------------------------------------------------------------------
# OPERATION: add_metadata_key
# -----------------------------------------------------------------------------


def add_metadata_key(
    namespace: str,
    key: str,
    type: MetadataKeyType,
    help_text: str,
    *,
    display_name: str | None = None,
    priority: int | None = None,
    data: list[str] | None = None,
    timezone_independent: bool | None = None,
) -> Operation[None]:
    """
    Build the key create.

    Returns:
        Operation[None]: The add key operation.
    """
    return Operation(
        method="POST",
        path=f"{_namespace(namespace)}/keys",
        body=CreateMetadataKeyRequest(
            key=key,
            type=type,
            help_text=help_text,
            display_name=display_name,
            priority=priority,
            data=data,
            timezone_independent=timezone_independent,
        ),
        parse=empty,
    )


# -----------------------------------------------------------------------------
# OPERATION: update_metadata_key
# -----------------------------------------------------------------------------


def update_metadata_key(
    namespace: str,
    key: str,
    *,
    display_name: str | None = None,
    help_text: str | None = None,
    type: MetadataKeyType | None = None,
    priority: int | None = None,
    data: list[str] | None = None,
    timezone_independent: bool | None = None,
) -> Operation[None]:
    """
    Build the key update.

    Returns:
        Operation[None]: The update key operation.
    """
    request = UpdateMetadataKeyRequest(
        display_name=display_name,
        help_text=help_text,
        type=type,
        priority=priority,
        data=data,
        timezone_independent=timezone_independent,
    )
    if not request.model_dump(exclude_none=True):
        raise ValueError("update_metadata_key needs at least one change")

    return Operation(
        method="PATCH", path=_key(namespace, key), body=request, parse=empty
    )


# -----------------------------------------------------------------------------
# OPERATION: delete_metadata_key
# -----------------------------------------------------------------------------


def delete_metadata_key(
    namespace: str, key: str, *, force: bool = False
) -> Operation[None]:
    """
    Build the key delete.

    Returns:
        Operation[None]: The delete key operation.
    """
    return Operation(
        method="DELETE",
        path=_key(namespace, key),
        headers=_force(force),
        parse=empty,
    )


# -----------------------------------------------------------------------------
# OPERATION: delete_metadata_key_values
# -----------------------------------------------------------------------------


def delete_metadata_key_values(
    namespace: str, key: str, values: list[str], *, force: bool = False
) -> Operation[None]:
    """
    Build the removal of allowed values from one key.

    Returns:
        Operation[None]: The delete key values operation.
    """
    if not values:
        raise ValueError("delete_metadata_key_values needs at least one value")

    return Operation(
        method="PATCH",
        path=f"{_key(namespace, key)}/data",
        body=KeyValuesRequest(values),
        headers=_force(force),
        parse=empty,
    )


# -----------------------------------------------------------------------------
# OPERATION: delete_metadata_values
# -----------------------------------------------------------------------------


def delete_metadata_values(
    namespace: str, values: Mapping[str, list[str]], *, force: bool = False
) -> Operation[None]:
    """
    Build the removal of allowed values from several keys of a namespace.

    Returns:
        Operation[None]: The delete values operation.
    """
    deletions = [
        KeyDataDeletion(key=key, data=data) for key, data in values.items() if data
    ]
    if not deletions:
        raise ValueError("delete_metadata_values needs at least one value")

    return Operation(
        method="PATCH",
        path=f"{_namespace(namespace)}/keys/data",
        body=DeleteKeyDataRequest(key_data_deletions=deletions),
        headers=_force(force),
        parse=empty,
    )


# -----------------------------------------------------------------------------
# OPERATIONS: file and folder values
# -----------------------------------------------------------------------------


def _wire_value(value: MetadataValueInput) -> MetadataKeyValue | None:
    """
    Convert a value to what Egnyte stores: dates become epoch milliseconds.

    A date is taken as UTC midnight, which timezone-independent date keys
    require; a naive datetime is read as UTC.

    Returns:
        MetadataKeyValue | None: The value as sent.
    """
    if isinstance(value, datetime):
        return epoch_ms(value)
    if isinstance(value, date):
        return int(datetime.combine(value, time(), tzinfo=UTC).timestamp() * 1000)
    return value


def _values(namespace: str) -> Callable[[httpx.Response], dict[str, MetadataKeyValue]]:
    def parse(response: httpx.Response) -> dict[str, MetadataKeyValue]:
        results = MetadataValuesResponse.model_validate_json(response.content).results
        return {
            key: value
            for result in results
            for key, value in result.get(namespace, {}).items()
            if value is not None
        }

    return parse


def _set_values(
    kind: str, item_id: str, namespace: str, values: Mapping[str, MetadataValueInput]
) -> Operation[None]:
    if not values:
        raise ValueError("Setting metadata needs at least one value")

    return Operation(
        method="PUT",
        path=f"/v1/fs/ids/{kind}/{encode_id(item_id)}/properties/{encode_id(namespace)}",
        body=MetadataValuesRequest(
            {key: _wire_value(value) for key, value in values.items()}
        ),
        parse=empty,
    )


def _get_values(
    kind: str, item_id: str, namespace: str
) -> Operation[dict[str, MetadataKeyValue]]:
    return Operation(
        method="GET",
        path=f"/v1/fs/ids/{kind}/{encode_id(item_id)}/properties/{encode_id(namespace)}",
        parse=_values(namespace),
    )


def set_file_metadata(
    file_id: str, namespace: str, values: Mapping[str, MetadataValueInput]
) -> Operation[None]:
    """
    Build the metadata write on a file (group ID) or one version (entry ID).

    Returns:
        Operation[None]: The set file metadata operation.
    """
    return _set_values("file", file_id, namespace, values)


def get_file_metadata(
    file_id: str, namespace: str
) -> Operation[dict[str, MetadataKeyValue]]:
    """
    Build the metadata read on a file (group ID) or one version (entry ID).

    Returns:
        Operation[dict[str, MetadataKeyValue]]: The get file metadata operation.
    """
    return _get_values("file", file_id, namespace)


def set_folder_metadata(
    folder_id: str, namespace: str, values: Mapping[str, MetadataValueInput]
) -> Operation[None]:
    """
    Build the metadata write on a folder.

    Returns:
        Operation[None]: The set folder metadata operation.
    """
    return _set_values("folder", folder_id, namespace, values)


def get_folder_metadata(
    folder_id: str, namespace: str
) -> Operation[dict[str, MetadataKeyValue]]:
    """
    Build the metadata read on a folder.

    Returns:
        Operation[dict[str, MetadataKeyValue]]: The get folder metadata operation.
    """
    return _get_values("folder", folder_id, namespace)
