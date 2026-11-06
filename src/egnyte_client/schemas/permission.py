from typing import Literal

from pydantic import Field

from egnyte_client.schemas.generic import GenericBaseModel

type PermissionLevel = Literal["Viewer Only", "Viewer", "Editor", "Full", "Owner"]
type EffectivePermissionLevel = Literal[
    "None", "Nav", "Viewer Only", "Viewer", "Editor", "Full", "Owner"
]
type PermissionChange = Literal[
    "None", "Viewer Only", "Viewer", "Editor", "Full", "Owner"
]

# =============================================================================
# CLASS: EffectivePermission
# =============================================================================


class EffectivePermission(GenericBaseModel):
    """
    Response body of the effective permission read.
    """

    permission: EffectivePermissionLevel = Field(
        description=(
            "The user's effective level on the folder, after groups and "
            "inheritance: None, Nav, Viewer Only, Viewer, Editor, Full, or Owner."
        ),
    )


# =============================================================================
# CLASS: FolderPermissions
# =============================================================================


class FolderPermissions(GenericBaseModel):
    """
    The user and group permissions set on a folder.
    """

    user_permissions: dict[str, PermissionLevel] = Field(
        default_factory=dict,
        alias="userPerms",
        description="Username to permission level.",
    )
    group_permissions: dict[str, PermissionLevel] = Field(
        default_factory=dict,
        alias="groupPerms",
        description="Group name to permission level.",
    )
    inherits_permissions: bool | None = Field(
        default=None,
        alias="inheritsPermissions",
        description="Whether the folder inherits permissions from its parent.",
    )


# =============================================================================
# CLASS: SetFolderPermissionsRequest
# =============================================================================


class SetFolderPermissionsRequest(GenericBaseModel):
    """
    Request body for the v2 permission update; `"None"` removes an entry.
    """

    user_perms: dict[str, PermissionChange] | None = Field(
        default=None, alias="userPerms"
    )
    group_perms: dict[str, PermissionChange] | None = Field(
        default=None, alias="groupPerms"
    )
    inherits_permissions: bool | None = Field(default=None, alias="inheritsPermissions")
    keep_parent_permissions: bool | None = Field(
        default=None, alias="keepParentPermissions"
    )
