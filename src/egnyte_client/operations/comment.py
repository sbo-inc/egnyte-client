from datetime import datetime

from egnyte_client.operations.generic import (
    Operation,
    as_utc,
    empty,
    encode_id,
    iso_utc,
    model,
    normalize_path,
    query,
)
from egnyte_client.schemas.comment import (
    Comment,
    CreateCommentRequest,
    ListCommentsResponse,
)

# -----------------------------------------------------------------------------
# OPERATION: create_comment
# -----------------------------------------------------------------------------


def create_comment(path: str, body: str) -> Operation[Comment]:
    """
    Build the comment create.

    Returns:
        Operation[Comment]: The create comment operation.
    """
    return Operation(
        method="POST",
        path="/v1/notes",
        body=CreateCommentRequest(path=normalize_path(path), body=body),
        parse=model(Comment),
    )


# -----------------------------------------------------------------------------
# OPERATION: list_comments
# -----------------------------------------------------------------------------


def list_comments(
    *,
    filter_by_path: str | None = None,
    filter_by_start_time: datetime | None = None,
    filter_by_end_time: datetime | None = None,
    offset: int | None = None,
    count: int | None = None,
) -> Operation[list[Comment]]:
    """
    Build one page of the comment listing.

    Returns:
        Operation[list[Comment]]: The list comments operation.
    """
    start = as_utc(filter_by_start_time) if filter_by_start_time else None
    end = as_utc(filter_by_end_time) if filter_by_end_time else None
    if start is not None and end is not None and start >= end:
        raise ValueError("filter_by_start_time must be before filter_by_end_time")

    return Operation(
        method="GET",
        path="/v1/notes",
        params=query(
            file=normalize_path(filter_by_path) if filter_by_path else None,
            start_time=iso_utc(start),
            end_time=iso_utc(end),
            offset=offset,
            count=count,
        ),
        parse=lambda response: (
            ListCommentsResponse.model_validate_json(response.content).notes
        ),
    )


# -----------------------------------------------------------------------------
# OPERATION: get_comment
# -----------------------------------------------------------------------------


def get_comment(comment_id: str) -> Operation[Comment]:
    """
    Build the comment read.

    Returns:
        Operation[Comment]: The get comment operation.
    """
    return Operation(
        method="GET", path=f"/v1/notes/{encode_id(comment_id)}", parse=model(Comment)
    )


# -----------------------------------------------------------------------------
# OPERATION: delete_comment
# -----------------------------------------------------------------------------


def delete_comment(comment_id: str) -> Operation[None]:
    """
    Build the comment delete.

    Returns:
        Operation[None]: The delete comment operation.
    """
    return Operation(
        method="DELETE", path=f"/v1/notes/{encode_id(comment_id)}", parse=empty
    )
