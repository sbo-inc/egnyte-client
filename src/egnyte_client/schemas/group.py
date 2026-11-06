from datetime import datetime
from typing import Literal

from pydantic import Field

from egnyte_client.schemas.generic import GenericBaseModel

# =============================================================================
# CLASS: GroupMember
# =============================================================================


class GroupMember(GenericBaseModel):
    user_id: int = Field(
        alias="value",
        description="Numeric user ID.",
    )
    username: str | None = Field(
        default=None,
        description="Username.",
    )
    display: str | None = Field(
        default=None,
        description="Display name.",
    )
    date_added: datetime | None = Field(
        default=None,
        description="When the user joined the group.",
    )


# =============================================================================
# CLASS: GroupSummary
# =============================================================================


class GroupSummary(GenericBaseModel):
    """
    A group as the listing returns it: identity only, no members.
    """

    id: str = Field(
        description="Group ID.",
    )
    display_name: str = Field(
        alias="displayName",
        description="Group name.",
    )


# =============================================================================
# CLASS: Group
# =============================================================================


class Group(GroupSummary):
    """
    A group with its members and owners.
    """

    members: list[GroupMember] = Field(
        default_factory=list,
        description="Group members.",
    )
    owners: list[str] = Field(
        default_factory=list,
        description="Usernames of the group owners.",
    )


# =============================================================================
# CLASS: MemberRef
# =============================================================================


class MemberRef(GenericBaseModel):
    """
    A member in a group request; `operation="delete"` removes it on PATCH.
    """

    value: int
    operation: Literal["delete"] | None = None


# =============================================================================
# CLASS: GroupRequest
# =============================================================================


class GroupRequest(GenericBaseModel):
    """
    Request body for creating, replacing, or patching a group.
    """

    display_name: str | None = Field(default=None, alias="displayName")
    members: list[MemberRef] | None = None
    owners: list[str] | None = None
