from egnyte_client.operations.generic import (
    Operation,
    empty,
    encode_id,
    model,
    normalize_path,
    query,
)
from egnyte_client.schemas.bookmark import (
    Bookmark,
    CreateBookmarkRequest,
    ListBookmarksResponse,
)

# -----------------------------------------------------------------------------
# OPERATION: create_bookmark
# -----------------------------------------------------------------------------


def create_bookmark(
    *, path: str | None = None, folder_id: str | None = None
) -> Operation[Bookmark]:
    """
    Build the bookmark create, by folder path or folder ID.

    Returns:
        Operation[Bookmark]: The create bookmark operation.
    """
    if (path is None) == (folder_id is None):
        raise ValueError("create_bookmark needs exactly one of path or folder_id")

    return Operation(
        method="POST",
        path="/v1/bookmarks",
        body=CreateBookmarkRequest(
            path=normalize_path(path) if path is not None else None,
            folder_id=folder_id,
        ),
        parse=model(Bookmark),
    )


# -----------------------------------------------------------------------------
# OPERATION: list_bookmarks
# -----------------------------------------------------------------------------


def list_bookmarks(
    *, offset: int | None = None, count: int | None = None
) -> Operation[list[Bookmark]]:
    """
    Build one page of the caller's bookmark listing.

    Returns:
        Operation[list[Bookmark]]: The list bookmarks operation.
    """
    return Operation(
        method="GET",
        path="/v1/bookmarks",
        params=query(offset=offset, count=count),
        parse=lambda response: (
            ListBookmarksResponse.model_validate_json(response.content).bookmarks
        ),
    )


# -----------------------------------------------------------------------------
# OPERATION: get_bookmark
# -----------------------------------------------------------------------------


def get_bookmark(bookmark_id: int) -> Operation[Bookmark]:
    """
    Build the bookmark read.

    Returns:
        Operation[Bookmark]: The get bookmark operation.
    """
    return Operation(
        method="GET",
        path=f"/v1/bookmarks/{encode_id(bookmark_id)}",
        parse=model(Bookmark),
    )


# -----------------------------------------------------------------------------
# OPERATION: delete_bookmark
# -----------------------------------------------------------------------------


def delete_bookmark(bookmark_id: int) -> Operation[None]:
    """
    Build the bookmark delete.

    Returns:
        Operation[None]: The delete bookmark operation.
    """
    return Operation(
        method="DELETE", path=f"/v1/bookmarks/{encode_id(bookmark_id)}", parse=empty
    )
