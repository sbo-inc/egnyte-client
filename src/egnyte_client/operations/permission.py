from collections.abc import Mapping

from egnyte_client.operations.generic import (
    Operation,
    empty,
    encode_id,
    encode_path,
    model,
    normalize_path,
    query,
)
from egnyte_client.schemas.permission import (
    EffectivePermission,
    EffectivePermissionLevel,
    FolderPermissions,
    PermissionChange,
    PermissionLevel,
    SetFolderPermissionsRequest,
)

# -----------------------------------------------------------------------------
# OPERATION: get_effective_permission
# -----------------------------------------------------------------------------


def get_effective_permission(
    folder: str, *, username: str | None = None
) -> Operation[EffectivePermissionLevel]:
    """
    Build the effective permission read, for the caller when no username.

    Returns:
        Operation[EffectivePermissionLevel]: The get effective permission operation.
    """
    path = "/v1/perms/user"
    if username is not None:
        path = f"{path}/{encode_id(username)}"

    return Operation(
        method="GET",
        path=path,
        params=query(folder=normalize_path(folder)),
        parse=lambda response: (
            EffectivePermission.model_validate_json(response.content).permission
        ),
    )


# -----------------------------------------------------------------------------
# OPERATION: get_folder_permissions
# -----------------------------------------------------------------------------


def get_folder_permissions(path: str) -> Operation[FolderPermissions]:
    """
    Build the v2 folder permission read.

    Returns:
        Operation[FolderPermissions]: The get folder permissions operation.
    """
    return Operation(
        method="GET",
        path=f"/v2/perms{encode_path(path)}",
        parse=model(FolderPermissions),
    )


# -----------------------------------------------------------------------------
# OPERATION: set_folder_permissions
# -----------------------------------------------------------------------------


def _changes(
    permissions: Mapping[str, PermissionLevel | None] | None,
) -> dict[str, PermissionChange] | None:
    """
    Map a Python None level to the `"None"` that removes an entry on the wire.

    Returns:
        dict[str, PermissionChange] | None: The wire map, or None.
    """
    if permissions is None:
        return None
    return {
        name: "None" if level is None else level for name, level in permissions.items()
    }


def set_folder_permissions(
    path: str,
    *,
    user_permissions: Mapping[str, PermissionLevel | None] | None = None,
    group_permissions: Mapping[str, PermissionLevel | None] | None = None,
    inherits_permissions: bool | None = None,
    keep_parent_permissions: bool | None = None,
) -> Operation[None]:
    """
    Build the v2 folder permission update, a delta over what is set.

    Returns:
        Operation[None]: The set folder permissions operation.
    """
    if keep_parent_permissions is not None and inherits_permissions is not False:
        raise ValueError(
            "keep_parent_permissions applies only with inherits_permissions=False"
        )

    return Operation(
        method="POST",
        path=f"/v2/perms{encode_path(path)}",
        body=SetFolderPermissionsRequest(
            user_perms=_changes(user_permissions),
            group_perms=_changes(group_permissions),
            inherits_permissions=inherits_permissions,
            keep_parent_permissions=keep_parent_permissions,
        ),
        parse=empty,
    )
