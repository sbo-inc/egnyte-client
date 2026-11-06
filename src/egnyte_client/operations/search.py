from datetime import datetime
from typing import Literal

from egnyte_client.operations.generic import Operation, epoch_ms, model, normalize_path
from egnyte_client.schemas.search import (
    FileQueryField,
    FolderQueryField,
    MetadataFilter,
    QueryOperator,
    SearchRequest,
    SearchResults,
    SearchSortBy,
    SearchType,
)

# -----------------------------------------------------------------------------
# OPERATION: search
# -----------------------------------------------------------------------------


def search(
    query: str | None = None,
    *,
    folder: str | None = None,
    type: SearchType | None = None,
    modified_after: datetime | None = None,
    modified_before: datetime | None = None,
    uploaded_after: datetime | None = None,
    uploaded_before: datetime | None = None,
    file_query_fields: list[FileQueryField] | None = None,
    folder_query_fields: list[FolderQueryField] | None = None,
    query_operator: QueryOperator | None = None,
    metadata_filters: list[MetadataFilter] | None = None,
    namespaces: list[str] | None = None,
    similar_to_entry_ids: list[str] | None = None,
    similar_to_text: list[str] | None = None,
    include_snippets: bool | None = None,
    sort_by: SearchSortBy | None = None,
    sort_direction: Literal["ascending", "descending"] | None = None,
    offset: int | None = None,
    count: int | None = None,
) -> Operation[SearchResults]:
    """
    Build one page of the v2 search.

    Returns:
        Operation[SearchResults]: The search operation.
    """
    if not (query or metadata_filters or similar_to_entry_ids or similar_to_text):
        raise ValueError(
            "search needs a query, metadata_filters, or a similarity source"
        )

    return Operation(
        method="POST",
        path="/v2/search",
        body=SearchRequest(
            query=query,
            offset=offset,
            count=count,
            folder=normalize_path(folder) if folder else None,
            type=type,
            modified_before=epoch_ms(modified_before),
            modified_after=epoch_ms(modified_after),
            uploaded_before=epoch_ms(uploaded_before),
            uploaded_after=epoch_ms(uploaded_after),
            snippet_requested=include_snippets,
            sort_by=sort_by,
            sort_direction=sort_direction,
            query_operator=query_operator,
            file_query_fields=file_query_fields,
            folder_query_fields=folder_query_fields,
            custom_metadata=metadata_filters,
            namespaces=namespaces,
            mlt=similar_to_entry_ids,
            mltt=similar_to_text,
        ),
        parse=model(SearchResults),
    )
