from datetime import datetime

from pydantic import Field

from egnyte_client.schemas.generic import GenericBaseModel

# =============================================================================
# CLASS: Comment
# =============================================================================


class Comment(GenericBaseModel):
    """
    A comment (a "note" on the wire) on a file.
    """

    id: str = Field(
        description="Comment ID (a UUID).",
    )
    message: str = Field(
        description="The comment text.",
    )
    username: str | None = Field(
        default=None,
        description="Username of the author.",
    )
    formatted_name: str | None = Field(
        default=None,
        description="Display name of the author.",
    )
    can_delete: bool | None = Field(
        default=None,
        description="Whether the caller may delete the comment.",
    )
    creation_time: datetime | None = Field(
        default=None,
        description="When the comment was made.",
    )
    file_path: str | None = Field(
        default=None,
        description="Absolute path of the commented file.",
    )
    group_id: str | None = Field(
        default=None,
        description="File group ID of the commented file.",
    )


# =============================================================================
# CLASS: ListCommentsResponse
# =============================================================================


class ListCommentsResponse(GenericBaseModel):
    """
    Response body of the comment listing.
    """

    notes: list[Comment] = Field(default_factory=list)
    count: int = Field(default=0)
    offset: int = Field(default=0)
    total_results: int = Field(default=0)


# =============================================================================
# CLASS: CreateCommentRequest
# =============================================================================


class CreateCommentRequest(GenericBaseModel):
    """
    Request body for adding a comment.
    """

    path: str
    body: str
