from typing import Literal, Self

from pydantic import Field, model_validator

from egnyte_client.schemas.generic import GenericBaseModel, HttpDate

type SearchType = Literal["FILE", "FOLDER", "ALL"]
type SearchSortBy = Literal["score", "last_modified", "size", "name"]
type FileQueryField = Literal["ALL", "FILENAME", "COMMENTS", "CONTENT"]
type FolderQueryField = Literal["ALL", "FOLDERNAME", "DESCRIPTION"]
type QueryOperator = Literal["ANY", "ALL"]
type MetadataOperator = Literal[
    "EQUALS",
    "GREATER_THAN",
    "LESS_THAN",
    "BETWEEN",
    "IN",
    "CONTAINS",
    "HAS_KEY",
    "HAS_NOT_KEY",
    "SUB_SET",
]
type MetadataValue = str | int | float | bool

# =============================================================================
# CLASS: MetadataRange
# =============================================================================


class MetadataRange(GenericBaseModel):
    """
    Bounds for a `BETWEEN` filter: `start` is inclusive, `end` exclusive.

    Dates are Unix epoch milliseconds.
    """

    start: MetadataValue
    end: MetadataValue


# =============================================================================
# CLASS: MetadataFilter
# =============================================================================


_SCALAR_OPERATORS = {"EQUALS", "GREATER_THAN", "LESS_THAN", "CONTAINS"}
_LIST_OPERATORS = {"IN", "SUB_SET"}


class MetadataFilter(GenericBaseModel):
    """
    A custom-metadata condition for `search`.

    `EQUALS`, `GREATER_THAN`, `LESS_THAN`, and `CONTAINS` take `value`; `IN`
    and `SUB_SET` take `values`; `BETWEEN` takes `range`; `HAS_KEY` and
    `HAS_NOT_KEY` take nothing. Dates are Unix epoch milliseconds.
    """

    namespace: str
    key: str
    operator: MetadataOperator = "EQUALS"
    value: MetadataValue | None = None
    values: list[MetadataValue] | None = None
    range: MetadataRange | None = None

    @model_validator(mode="after")
    def _check_operand(self) -> Self:
        given = {
            name
            for name in ("value", "values", "range")
            if getattr(self, name) is not None
        }
        if self.operator in _SCALAR_OPERATORS:
            needed = {"value"}
        elif self.operator in _LIST_OPERATORS:
            needed = {"values"}
        elif self.operator == "BETWEEN":
            needed = {"range"}
        else:
            needed = set()
        if given != needed:
            expected = ", ".join(sorted(needed)) or "no operand"
            raise ValueError(f"{self.operator} takes {expected}")
        return self


# =============================================================================
# CLASS: CustomProperty
# =============================================================================


class CustomProperty(GenericBaseModel):
    """
    A custom metadata value on a search result.
    """

    namespace: str | None = Field(
        default=None,
        description="Metadata namespace.",
    )
    key: str | None = Field(
        default=None,
        description="Metadata key.",
    )
    value: MetadataValue | list[MetadataValue] | None = Field(
        default=None,
        description="The stored value.",
    )
    scope: str | None = Field(
        default=None,
        description="Where the namespace applies.",
    )
    value_to_stamp_on_file: MetadataValue | list[MetadataValue] | None = Field(
        default=None,
        alias="valueToStampOnFile",
        description="The value as stamped on the file.",
    )


# =============================================================================
# CLASS: SearchResult
# =============================================================================


class SearchResult(GenericBaseModel):
    """
    One file or folder matched by a search.

    File hits carry `group_id`, `entry_id`, and the file fields; folder hits
    carry `folder_id`.
    """

    name: str = Field(
        description="File or folder name.",
    )
    path: str = Field(
        description="Absolute path.",
    )
    is_folder: bool = Field(
        default=False,
        description="Whether the hit is a folder.",
    )
    folder_id: str | None = Field(
        default=None,
        description="Folder ID, for a folder hit.",
    )
    group_id: str | None = Field(
        default=None,
        description="File ID across versions, for a file hit.",
    )
    entry_id: str | None = Field(
        default=None,
        description="ID of the matched file version.",
    )
    mime_type: str | None = Field(
        default=None,
        alias="type",
        description="MIME type of a file hit.",
    )
    size: int | None = Field(
        default=None,
        description="Size in bytes.",
    )
    snippet: str | None = Field(
        default=None,
        description="Matched text, plain.",
    )
    snippet_html: str | None = Field(
        default=None,
        description="Matched text, with the matches highlighted in HTML.",
    )
    last_modified: HttpDate | None = Field(
        default=None,
        description="When the item last changed.",
    )
    uploaded_by: str | None = Field(
        default=None,
        description="Display name of the uploader.",
    )
    uploaded_by_username: str | None = Field(
        default=None,
        description="Username of the uploader.",
    )
    num_versions: int | None = Field(
        default=None,
        description="Number of stored versions.",
    )
    score: float | None = Field(
        default=None,
        description="Relevance score; higher is better.",
    )
    custom_properties: list[CustomProperty] = Field(
        default_factory=list,
        description="Custom metadata values on the item.",
    )


# =============================================================================
# CLASS: SearchResults
# =============================================================================


class SearchResults(GenericBaseModel):
    """
    One page of search results.

    Page with `offset` and `count` on the request, and stop when `has_more`
    is false. `total_count` is not a full total: Egnyte reports at most one
    more than the page holds.
    """

    results: list[SearchResult] = Field(
        default_factory=list,
        description="The hits in this page.",
    )
    count: int = Field(
        default=0,
        description="Number of hits in this page.",
    )
    total_count: int = Field(
        default=0,
        description="Hits found, capped at one more than the page holds.",
    )
    has_more: bool = Field(
        default=False,
        alias="hasMore",
        description="Whether another page follows.",
    )


# =============================================================================
# CLASS: SearchRequest
# =============================================================================


class SearchRequest(GenericBaseModel):
    """
    Request body for the v2 search.
    """

    query: str | None = None
    offset: int | None = None
    count: int | None = None
    folder: str | None = None
    type: SearchType | None = None
    modified_before: int | None = None
    modified_after: int | None = None
    uploaded_before: int | None = None
    uploaded_after: int | None = None
    snippet_requested: bool | None = None
    sort_by: SearchSortBy | None = None
    sort_direction: Literal["ascending", "descending"] | None = None
    query_operator: QueryOperator | None = None
    file_query_fields: list[FileQueryField] | None = None
    folder_query_fields: list[FolderQueryField] | None = None
    custom_metadata: list[MetadataFilter] | None = None
    namespaces: list[str] | None = None
    mlt: list[str] | None = None
    mltt: list[str] | None = None
