from datetime import datetime

from pydantic import Field

from egnyte_client.schemas.generic import GenericBaseModel

# =============================================================================
# CLASS: RecentFile
# =============================================================================


class RecentFile(GenericBaseModel):
    """
    A file the caller recently accessed.
    """

    name: str = Field(
        description="File name.",
    )
    path: str = Field(
        description="Absolute path, including the file name.",
    )
    group_id: str | None = Field(
        default=None,
        description="Stable ID of the file across all of its versions.",
    )
    entry_id: str | None = Field(
        default=None,
        description="ID of the current version.",
    )
    size: int | None = Field(
        default=None,
        description="Size in bytes.",
    )
    uploaded_by: str | None = Field(
        default=None,
        description="Name of the uploader; absent when the owner is unavailable.",
    )
    num_versions: int | None = Field(
        default=None,
        description="Number of stored versions.",
    )
    last_modified: datetime | None = Field(
        default=None,
        description="When the file last changed.",
    )
    last_accessed: datetime | None = Field(
        default=None,
        description="When the caller last accessed the file.",
    )
    recommendation_type: str | None = Field(
        default=None,
        description="Why the file is listed; always recent here.",
    )


# =============================================================================
# CLASS: RecentFiles
# =============================================================================


class RecentFiles(GenericBaseModel):
    """
    The recent files listing.
    """

    recent_files: list[RecentFile] = Field(
        default_factory=list,
        alias="recentFiles",
        description="Recently accessed files, most recent first.",
    )
