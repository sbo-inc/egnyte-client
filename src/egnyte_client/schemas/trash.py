from datetime import datetime
from typing import Literal

from pydantic import Field

from egnyte_client.schemas.generic import GenericBaseModel

type TrashSortBy = Literal[
    "date_deleted",
    "name",
    "deleted_by",
    "purge_date",
    "orig_location",
    "owner",
    "type",
]
type TrashSortDirection = Literal["asc", "desc"]

# =============================================================================
# CLASS: TrashItemOwner
# =============================================================================


class TrashItemOwner(GenericBaseModel):
    """
    The owner of a file in the trash.
    """

    id: int | None = Field(
        default=None,
        description="User ID.",
    )
    username: str | None = Field(
        default=None,
        description="Username.",
    )
    first_name: str | None = Field(
        default=None,
        alias="firstName",
        description="First name.",
    )
    last_name: str | None = Field(
        default=None,
        alias="lastName",
        description="Last name.",
    )
    email: str | None = Field(
        default=None,
        description="Email address.",
    )
    type_name: str | None = Field(
        default=None,
        alias="typeName",
        description="User type, such as admin.",
    )


# =============================================================================
# CLASS: DataRetentionInfo
# =============================================================================


class DataRetentionInfo(GenericBaseModel):
    """
    Why a trashed item is retained, when data retention is enabled.
    """

    retention: str | None = Field(
        default=None,
        description="RETENTION_POLICY, GRACE_PERIOD, or DEFAULT_RETENTION_PERIOD.",
    )
    earliest_expiry: datetime | None = Field(
        default=None,
        description="When the retention expires.",
    )
    is_retained: bool | None = Field(
        default=None,
        description="Whether the item is retained.",
    )


# =============================================================================
# CLASS: TrashItem
# =============================================================================


class TrashItem(GenericBaseModel):
    """
    A file, folder, or file version in the trash.
    """

    id: str = Field(
        description="Trash item ID, as restore and purge take it.",
    )
    type: str | None = Field(
        default=None,
        description="folder, file, or version.",
    )
    name: str | None = Field(
        default=None,
        description="Item name.",
    )
    path: str | None = Field(
        default=None,
        description="Path the item was deleted from.",
    )
    size: int | None = Field(
        default=None,
        description="Size in bytes, for files.",
    )
    owner: TrashItemOwner | None = Field(
        default=None,
        description="The file's owner, for files.",
    )
    deleted_by: str | None = Field(
        default=None,
        description="Full name of the user who deleted the item.",
    )
    delete_date: datetime | None = Field(
        default=None,
        description="When the item was deleted.",
    )
    purge_date: datetime | None = Field(
        default=None,
        description="When the item will be purged permanently.",
    )
    last_modified: datetime | None = Field(
        default=None,
        description="When the item last changed before it was deleted.",
    )
    data_retention_info: DataRetentionInfo | None = Field(
        default=None,
        description="Retention details, when data retention is enabled.",
    )


# =============================================================================
# CLASS: TrashPage
# =============================================================================


class TrashPage(GenericBaseModel):
    """
    One page of the trash listing.
    """

    count: int | None = Field(
        default=None,
        description="Number of items in this page.",
    )
    offset: int | None = Field(
        default=None,
        description="Index of the first item in this page.",
    )
    has_more: bool = Field(
        default=False,
        description="Whether more items follow this page.",
    )
    items: list[TrashItem] = Field(
        default_factory=list,
        description="The items in this page.",
    )


# =============================================================================
# CLASS: TrashCount
# =============================================================================


class TrashCount(GenericBaseModel):
    """
    The number of items in the trash.
    """

    total_count: int = Field(
        alias="totalCount",
        description="Total number of items in the trash.",
    )


# =============================================================================
# CLASS: TrashItemStatus
# =============================================================================


class TrashItemStatus(GenericBaseModel):
    """
    The outcome of a restore or purge for one trash item.
    """

    id: str = Field(
        description="Trash item ID.",
    )
    code: int = Field(
        description="HTTP status for this item; 200 when it succeeded.",
    )
    description: str | None = Field(
        default=None,
        alias="descriptions",
        description="Why the item failed, when it did.",
    )

    @property
    def succeeded(self) -> bool:
        """
        Whether the restore or purge of this item succeeded.

        Returns:
            bool: True when `code` is 200.
        """
        return self.code == 200


# =============================================================================
# CLASS: TrashMultiStatus
# =============================================================================


class TrashMultiStatus(GenericBaseModel):
    """
    The 207 body of a restore or purge that only partly succeeded.
    """

    resources: list[TrashItemStatus] = Field(
        default_factory=list,
        description="One status per requested item.",
    )


# =============================================================================
# CLASS: TrashActionRequest
# =============================================================================


class TrashActionRequest(GenericBaseModel):
    """
    Request body for a restore or purge.
    """

    action: Literal["RESTORE", "PURGE"]
    ids: list[str]
