from datetime import datetime
from typing import Literal

from pydantic import Field

from egnyte_client.schemas.generic import GenericBaseModel, HttpDate

type PublicLinks = Literal["files_folders", "folders", "files", "disabled"]
type MoveDeleteRestriction = Literal[
    "admins_owners_or_full_access_users", "admins_or_owners", "admins_only"
]
type InheritanceRule = Literal[
    "legacy",
    "this_folder_only",
    "this_folder_and_subfolders_until_overridden",
    "this_folder_and_subfolders",
]
type FolderOptionsMode = Literal["keep_source", "apply_destination"]

# =============================================================================
# CLASS: FileVersion
# =============================================================================


class FileVersion(GenericBaseModel):
    """
    One stored version of a file, listed when a file is read with its versions.
    """

    entry_id: str = Field(
        description="ID of this version.",
    )
    checksum: str | None = Field(
        default=None,
        description="SHA-512 of this version's content.",
    )
    size: int | None = Field(
        default=None,
        description="Size in bytes.",
    )
    last_modified: HttpDate | None = Field(
        default=None,
        description="Modification time recorded for this version.",
    )
    uploaded: datetime | None = Field(
        default=None,
        description="When this version was uploaded.",
    )
    uploaded_by: str | None = Field(
        default=None,
        description="Username that uploaded this version.",
    )
    is_current: bool | None = Field(
        default=None,
        description="Whether this is the current version.",
    )


# =============================================================================
# CLASS: File
# =============================================================================


class File(GenericBaseModel):
    """
    File metadata from the file system API.
    """

    name: str = Field(
        description="File name.",
    )
    path: str = Field(
        description="Absolute path, including the file name.",
    )
    group_id: str = Field(
        description="Stable ID of the file across all of its versions.",
    )
    entry_id: str | None = Field(
        default=None,
        description="ID of the current version.",
    )
    parent_id: str | None = Field(
        default=None,
        description="Folder ID of the containing folder.",
    )
    size: int | None = Field(
        default=None,
        description="Size in bytes.",
    )
    checksum: str | None = Field(
        default=None,
        description="SHA-512 of the current version's content.",
    )
    last_modified: HttpDate | None = Field(
        default=None,
        description="Modification time of the current version.",
    )
    uploaded: datetime | None = Field(
        default=None,
        description="When the current version was uploaded.",
    )
    uploaded_by: str | None = Field(
        default=None,
        description="Username that uploaded the current version.",
    )
    num_versions: int | None = Field(
        default=None,
        description="Number of stored versions.",
    )
    locked: bool | None = Field(
        default=None,
        description="Whether the file is locked.",
    )
    permission: str | None = Field(
        default=None,
        description="The caller's permission on the file.",
    )
    is_folder: Literal[False] = Field(
        default=False,
        description="Always false for a file.",
    )
    versions: list[FileVersion] = Field(
        default_factory=list,
        description="Prior versions, when requested.",
    )


# =============================================================================
# CLASS: Folder
# =============================================================================


class Folder(GenericBaseModel):
    """
    Folder metadata from the file system API, with its listed contents.

    `folders` and `files` hold one page of the folder's children; `offset`,
    `count`, and `total_count` describe the page. Sub-folders carry only their
    own identity, never their children.
    """

    name: str = Field(
        description="Folder name.",
    )
    path: str = Field(
        description="Absolute path.",
    )
    folder_id: str = Field(
        description="Stable folder ID.",
    )
    parent_id: str | None = Field(
        default=None,
        description="Folder ID of the parent; empty at the root.",
    )
    uploaded: datetime | None = Field(
        default=None,
        description="When the folder was created.",
    )
    last_modified: datetime | None = Field(
        default=None,
        alias="lastModified",
        description="When the folder last changed.",
    )
    count: int | None = Field(
        default=None,
        description="Number of children requested for this page.",
    )
    offset: int | None = Field(
        default=None,
        description="Index of the first child in this page.",
    )
    total_count: int | None = Field(
        default=None,
        description="Total number of children in the folder.",
    )
    permission: str | None = Field(
        default=None,
        description="The caller's permission on the folder.",
    )
    folder_description: str | None = Field(
        default=None,
        description="Folder description.",
    )
    allow_links: bool | None = Field(
        default=None,
        description="Whether links may be created to the folder.",
    )
    allow_upload_links: bool | None = Field(
        default=None,
        description="Whether upload links may be created to the folder.",
    )
    public_links: str | None = Field(
        default=None,
        description="Which items may be shared by public link.",
    )
    restrict_move_delete: bool | None = Field(
        default=None,
        description="Whether moving and deleting are restricted.",
    )
    move_delete_folder_restriction: str | None = Field(
        default=None,
        description="Who may move or delete the folder, such as admins_or_owners.",
    )
    allowed_file_link_types: list[str] | None = Field(
        default=None,
        description="Link types that may be created to files in the folder.",
    )
    allowed_folder_link_types: list[str] | None = Field(
        default=None,
        description="Link types that may be created to the folder.",
    )
    is_folder: Literal[True] = Field(
        default=True,
        description="Always true for a folder.",
    )
    folders: list["Folder"] = Field(
        default_factory=list,
        description="Sub-folders in this page.",
    )
    files: list[File] = Field(
        default_factory=list,
        description="Files in this page.",
    )


# =============================================================================
# CLASS: CreatedFolder
# =============================================================================


class CreatedFolder(GenericBaseModel):
    """
    The folder a create call made.
    """

    folder_id: str = Field(
        description="Stable folder ID.",
    )
    path: str = Field(
        description="Absolute path.",
    )


# =============================================================================
# CLASS: UploadedFile
# =============================================================================


class UploadedFile(GenericBaseModel):
    """
    The file version an upload stored.
    """

    path: str = Field(
        description="Absolute path, including the file name.",
    )
    group_id: str = Field(
        description="Stable ID of the file across all of its versions.",
    )
    entry_id: str = Field(
        description="ID of the version just uploaded.",
    )
    checksum: str | None = Field(
        default=None,
        description="SHA-512 of the uploaded content, as Egnyte computed it.",
    )


# =============================================================================
# CLASS: ItemReference
# =============================================================================


class ItemReference(GenericBaseModel):
    """
    Where a copy or move left the item.

    A file carries `group_id`, a folder `folder_id`.
    """

    path: str = Field(
        description="Absolute path at the destination.",
    )
    group_id: str | None = Field(
        default=None,
        description="File ID, when the item is a file.",
    )
    folder_id: str | None = Field(
        default=None,
        description="Folder ID, when the item is a folder.",
    )


# =============================================================================
# CLASS: DeletedItem
# =============================================================================


class DeletedItem(GenericBaseModel):
    """
    The result of a delete. Deleted items move to the trash.
    """

    parent_folder_path: str | None = Field(
        default=None,
        description="Path of the folder the item was deleted from.",
    )


# =============================================================================
# CLASS: TransferRequest
# =============================================================================


class TransferRequest(GenericBaseModel):
    """
    Request body for a copy or move.
    """

    action: Literal["copy", "move"]
    destination: str
    permissions: Literal["keep_original", "inherit_from_parent"] | None = None


# =============================================================================
# CLASS: TransferByIdRequest
# =============================================================================


class TransferByIdRequest(GenericBaseModel):
    """
    Request body for a copy or move addressed by ID.
    """

    action: Literal["copy", "move"]
    destination_id: str
    name: str | None = None
    permissions: Literal["keep_original", "inherit_from_parent"] | None = None
    folder_options_mode: FolderOptionsMode | None = None


# =============================================================================
# CLASS: FolderStats
# =============================================================================


class FolderStats(GenericBaseModel):
    """
    Size and item counts of a folder, its files, and its sub-folders.
    """

    files_count: int | None = Field(
        default=None,
        alias="filesCount",
        description="Number of files.",
    )
    file_versions_count: int | None = Field(
        default=None,
        alias="fileVersionsCount",
        description="Number of file versions.",
    )
    folders_count: int | None = Field(
        default=None,
        alias="foldersCount",
        description="Number of sub-folders.",
    )
    all_files_size: int | None = Field(
        default=None,
        alias="allFilesSize",
        description="Size of the current file versions, in bytes.",
    )
    all_versions_size: int | None = Field(
        default=None,
        alias="allVersionsSize",
        description="Size of all file versions, in bytes.",
    )
    all_files_size_in_kb: int | None = Field(
        default=None,
        alias="allFilesSizeInKB",
        description="Size of the current file versions, in KB.",
    )
    all_versions_size_in_kb: int | None = Field(
        default=None,
        alias="allVersionsSizeInKB",
        description="Size of all file versions, in KB.",
    )


# =============================================================================
# CLASS: LockRequest
# =============================================================================


class LockRequest(GenericBaseModel):
    """
    Request body for a file lock.
    """

    action: Literal["lock"] = "lock"
    lock_token: str | None = None
    lock_timeout: int | None = None
    collaboration: str | None = None


# =============================================================================
# CLASS: UnlockRequest
# =============================================================================


class UnlockRequest(GenericBaseModel):
    """
    Request body for a file unlock.
    """

    action: Literal["unlock"] = "unlock"
    lock_token: str


# =============================================================================
# CLASS: FileLock
# =============================================================================


class FileLock(GenericBaseModel):
    """
    The lock a lock call placed on a file.
    """

    lock_token: str = Field(
        description="Token that unlocks or refreshes the lock.",
    )
    timeout: int | None = Field(
        default=None,
        description="Seconds until the lock expires.",
    )


# =============================================================================
# CLASS: UploadedChunk
# =============================================================================


class UploadedChunk(GenericBaseModel):
    """
    One chunk of a chunked upload, as Egnyte acknowledged it.
    """

    upload_id: str = Field(
        description="ID of the upload session the chunk joined.",
    )
    chunk_num: int = Field(
        description="1-based number of the chunk.",
    )
    checksum: str | None = Field(
        default=None,
        description="SHA-512 of the chunk, as Egnyte computed it.",
    )


# =============================================================================
# CLASS: EmailPreferences
# =============================================================================


class EmailPreferences(GenericBaseModel):
    """
    The caller's notification settings for a folder.
    """

    content_updates: bool | None = None
    content_accessed: bool | None = None


# =============================================================================
# CLASS: FolderOptionsRequest
# =============================================================================


class FolderOptionsRequest(GenericBaseModel):
    """
    Request body for a folder options update.
    """

    folder_description: str | None = None
    allow_links: bool | None = None
    allow_upload_links: bool | None = None
    public_links: PublicLinks | None = None
    restrict_move_delete: bool | None = None
    move_delete_folder_restriction: MoveDeleteRestriction | None = None
    inheritance_rule: InheritanceRule | None = None
    email_preferences: EmailPreferences | None = None
