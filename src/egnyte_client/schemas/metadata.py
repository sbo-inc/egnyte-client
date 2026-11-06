from datetime import date
from typing import Literal, Self

from pydantic import Field, RootModel, model_validator

from egnyte_client.schemas.generic import GenericBaseModel

type MetadataKeyType = Literal[
    "string",
    "integer",
    "decimal",
    "date",
    "enum",
    "labels",
    "multi_value_enum",
]
type MetadataScope = Literal["public", "protected", "private"]
type MetadataScopeType = Literal["GLOBAL", "FOLDER_SCOPE", "DOCUMENT_TYPE"]
type DocumentType = Literal[
    "PDF",
    "DOCUMENT",
    "SPREADSHEET",
    "PRESENTATION",
    "IMAGE",
    "AUDIO_VIDEO",
    "TEXT_SOURCE_CODE",
    "GOOGLE_FILE",
    "EMAIL",
    "CAD",
    "ARCHIVE",
]

# A stored metadata value: text and enum keys hold a string, integer and
# decimal keys a number, date keys Unix epoch milliseconds, and labels and
# multi-value enum keys a list of strings.
type MetadataKeyValue = str | int | float | list[str]

# What a metadata value may be set to; None removes the value. A date is sent
# as UTC midnight and a datetime as its instant, both in epoch milliseconds.
type MetadataValueInput = str | int | float | list[str] | date | None

_ENUM_TYPES = {"enum", "multi_value_enum"}

# =============================================================================
# CLASS: MetadataKey
# =============================================================================


class MetadataKey(GenericBaseModel):
    """
    A key defined in a metadata namespace.
    """

    type: str = Field(
        description=(
            "Data type: string, integer, decimal, date, enum, labels, or "
            "multi_value_enum."
        ),
    )
    display_name: str | None = Field(
        default=None,
        alias="displayName",
        description="Name shown in the UI.",
    )
    help_text: str | None = Field(
        default=None,
        alias="helpText",
        description="Guidance shown to users filling in the key.",
    )
    priority: int | None = Field(
        default=None,
        description="Display order; higher values are shown first.",
    )
    data: list[str] | None = Field(
        default=None,
        description="Allowed values of an enum, multi-value enum, or labels key.",
    )
    timezone_independent: bool | None = Field(
        default=None,
        alias="timezoneIndependent",
        description="Whether a date key stores UTC-midnight dates.",
    )


# =============================================================================
# CLASS: FolderAssociation
# =============================================================================


class FolderAssociation(GenericBaseModel):
    """
    A folder a folder-scoped namespace applies to.
    """

    folder_id: str = Field(
        alias="folderId",
        description="Folder ID.",
    )
    path: str | None = Field(
        default=None,
        description="Absolute folder path.",
    )


# =============================================================================
# CLASS: MetadataNamespace
# =============================================================================


class MetadataNamespace(GenericBaseModel):
    """
    A metadata namespace and the keys it defines.
    """

    name: str = Field(
        description="Namespace name, as used in URLs and search filters.",
    )
    display_name: str | None = Field(
        default=None,
        alias="displayName",
        description="Name shown in the UI.",
    )
    priority: int | None = Field(
        default=None,
        description="Display order of the namespace.",
    )
    keys: dict[str, MetadataKey] = Field(
        default_factory=dict,
        description="Key definitions, by key name.",
    )
    scope: str | None = Field(
        default=None,
        description="Who sees and edits it: PUBLIC, PROTECTED, or PRIVATE.",
    )
    schema_system_generated: bool | None = Field(
        default=None,
        alias="schemaSystemGenerated",
        description="Whether Egnyte created the namespace itself.",
    )
    inheritable: bool | None = Field(
        default=None,
        description="Whether values are inherited by child items.",
    )
    metadata_scope_type: str | None = Field(
        default=None,
        alias="metadataScopeType",
        description="Where it applies: GLOBAL, FOLDER_SCOPE, or DOCUMENT_TYPE.",
    )
    folder_associations: list[FolderAssociation] = Field(
        default_factory=list,
        alias="folderAssociations",
        description="Folders a folder-scoped namespace applies to.",
    )
    has_access_to_all_associations: bool | None = Field(
        default=None,
        alias="hasAccessToAllAssociations",
        description="Whether the caller can see every associated folder.",
    )
    document_types: list[str] = Field(
        default_factory=list,
        alias="documentTypes",
        description="Document types a document-type namespace applies to.",
    )
    document_extensions: list[str] = Field(
        default_factory=list,
        alias="documentExtensions",
        description="File extensions covered by those document types.",
    )


# =============================================================================
# CLASS: MetadataKeyDefinition
# =============================================================================


class MetadataKeyDefinition(GenericBaseModel):
    """
    A key to define in a new namespace, or to add to an existing one.

    `help_text` is 20 to 200 characters. `data` lists the allowed values and
    is required for `enum` and `multi_value_enum` keys (optional for
    `labels`). `timezone_independent` applies to `date` keys only, and once
    true it cannot be turned off. A higher `priority` is displayed first.
    """

    type: MetadataKeyType
    help_text: str = Field(alias="helpText", min_length=20, max_length=200)
    display_name: str | None = Field(default=None, alias="displayName")
    priority: int | None = None
    data: list[str] | None = None
    timezone_independent: bool | None = Field(default=None, alias="timezoneIndependent")

    @model_validator(mode="after")
    def _check_type_options(self) -> Self:
        if self.type in _ENUM_TYPES and not self.data:
            raise ValueError(f"A {self.type} key needs its allowed values in data")
        if self.timezone_independent is not None and self.type != "date":
            raise ValueError("timezone_independent applies to date keys only")
        return self


# =============================================================================
# CLASS: CreateMetadataKeyRequest
# =============================================================================


class CreateMetadataKeyRequest(MetadataKeyDefinition):
    """
    Request body for adding a key to a namespace.
    """

    key: str


# =============================================================================
# CLASS: UpdateMetadataKeyRequest
# =============================================================================


class UpdateMetadataKeyRequest(GenericBaseModel):
    """
    Request body for changing a key's definition.
    """

    display_name: str | None = Field(default=None, alias="displayName")
    help_text: str | None = Field(
        default=None, alias="helpText", min_length=20, max_length=200
    )
    type: MetadataKeyType | None = None
    priority: int | None = None
    data: list[str] | None = None
    timezone_independent: bool | None = Field(default=None, alias="timezoneIndependent")


# =============================================================================
# CLASS: CreateNamespaceRequest
# =============================================================================


class CreateNamespaceRequest(GenericBaseModel):
    """
    Request body for creating a namespace.
    """

    name: str
    scope: MetadataScope
    keys: dict[str, MetadataKeyDefinition]
    display_name: str | None = Field(default=None, alias="displayName")
    inheritable: bool | None = None
    metadata_scope_type: MetadataScopeType | None = Field(
        default=None, alias="metadataScopeType"
    )
    associated_folder_ids: list[str] | None = Field(
        default=None, alias="associatedFolderIds"
    )
    document_types: list[DocumentType] | None = Field(
        default=None, alias="documentTypes"
    )


# =============================================================================
# CLASS: UpdateNamespaceRequest
# =============================================================================


class FolderAssociationChange(GenericBaseModel):
    """
    Folders to add to or remove from a folder-scoped namespace.
    """

    associate_folder_ids: list[str] | None = Field(
        default=None, alias="associateFolderIds"
    )
    dissociate_folder_ids: list[str] | None = Field(
        default=None, alias="dissociateFolderIds"
    )


class DocumentTypeAssociationChange(GenericBaseModel):
    """
    Document types to add to or remove from a document-type namespace.
    """

    associate_document_types: list[DocumentType] | None = Field(
        default=None, alias="associateDocumentTypes"
    )
    dissociate_document_types: list[DocumentType] | None = Field(
        default=None, alias="dissociateDocumentTypes"
    )


class UpdateNamespaceRequest(GenericBaseModel):
    """
    Request body for changing a namespace's attributes.
    """

    display_name: str | None = Field(default=None, alias="displayName")
    priorities: dict[str, int] | None = None
    folder_association: FolderAssociationChange | None = Field(
        default=None, alias="folderAssociation"
    )
    document_type_association: DocumentTypeAssociationChange | None = Field(
        default=None, alias="documentTypeAssociation"
    )


# =============================================================================
# CLASS: KeyDataDeletion
# =============================================================================


class KeyDataDeletion(GenericBaseModel):
    """
    Allowed values to remove from one key.
    """

    key: str
    data: list[str]


class DeleteKeyDataRequest(GenericBaseModel):
    """
    Request body for removing allowed values from several keys.
    """

    key_data_deletions: list[KeyDataDeletion] = Field(alias="keyDataDeletions")


# =============================================================================
# CLASS: Root bodies
# =============================================================================


class MetadataValuesRequest(RootModel[dict[str, MetadataKeyValue | None]]):
    """
    Request body setting metadata values: key name to value, None removes.
    """


class KeyValuesRequest(RootModel[list[str]]):
    """
    Request body listing the allowed values to remove from one key.
    """


# =============================================================================
# CLASS: MetadataValuesResponse
# =============================================================================


class MetadataValuesResponse(GenericBaseModel):
    """
    The values of one namespace on a file or folder.

    Egnyte answers with a `results` array of `{namespace: {key: value}}`
    objects.
    """

    results: list[dict[str, dict[str, MetadataKeyValue | None]]] = Field(
        default_factory=list,
        description="Values by namespace, then by key.",
    )
