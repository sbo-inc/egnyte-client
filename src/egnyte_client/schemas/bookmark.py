from datetime import datetime

from pydantic import Field

from egnyte_client.schemas.generic import GenericBaseModel

# =============================================================================
# CLASS: Bookmark
# =============================================================================


class Bookmark(GenericBaseModel):
    """
    A folder bookmarked by the calling user.
    """

    id: int = Field(
        description="Bookmark ID.",
    )
    path: str | None = Field(
        default=None,
        description="Absolute path of the bookmarked folder.",
    )
    folder_id: str | None = Field(
        default=None,
        description="ID of the bookmarked folder.",
    )
    creation_date: datetime | None = Field(
        default=None,
        description="When the bookmark was created.",
    )


# =============================================================================
# CLASS: ListBookmarksResponse
# =============================================================================


class ListBookmarksResponse(GenericBaseModel):
    """
    Response body of the bookmark listing.
    """

    bookmarks: list[Bookmark] = Field(default_factory=list)
    offset: int = Field(default=0)
    count: int = Field(default=0)


# =============================================================================
# CLASS: CreateBookmarkRequest
# =============================================================================


class CreateBookmarkRequest(GenericBaseModel):
    """
    Request body for bookmarking a folder, by path or by folder ID.
    """

    path: str | None = None
    folder_id: str | None = None
