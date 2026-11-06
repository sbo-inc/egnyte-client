from egnyte_client.operations.generic import (
    Operation,
    empty,
    encode_id,
    model,
    query,
    resources,
    scim_filter,
)
from egnyte_client.schemas.group import Group, GroupRequest, GroupSummary, MemberRef

# -----------------------------------------------------------------------------
# OPERATION: list_groups
# -----------------------------------------------------------------------------


def list_groups(
    *,
    filter_by_name: str | None = None,
    filter_by_name_contains: str | None = None,
    filter_by_name_starts_with: str | None = None,
    start_index: int | None = None,
    count: int | None = None,
) -> Operation[list[GroupSummary]]:
    """
    Build one page of the custom-group listing.

    Returns:
        Operation[list[GroupSummary]]: The list groups operation.
    """
    filters = [
        ("eq", filter_by_name),
        ("co", filter_by_name_contains),
        ("sw", filter_by_name_starts_with),
    ]
    given = [(op, value) for op, value in filters if value is not None]
    if len(given) > 1:
        raise ValueError("Only one group name filter can be applied at a time")

    return Operation(
        method="GET",
        path="/v2/groups",
        params=query(
            filter=scim_filter(displayName=given[0]) if given else None,
            startIndex=start_index,
            count=count,
        ),
        parse=resources(GroupSummary),
    )


# -----------------------------------------------------------------------------
# OPERATION: get_group
# -----------------------------------------------------------------------------


def get_group(group_id: str) -> Operation[Group]:
    """
    Build the group read.

    Returns:
        Operation[Group]: The get group operation.
    """
    return Operation(
        method="GET", path=f"/v2/groups/{encode_id(group_id)}", parse=model(Group)
    )


# -----------------------------------------------------------------------------
# OPERATION: create_group
# -----------------------------------------------------------------------------


def create_group(
    display_name: str,
    member_ids: list[int],
    *,
    owners: list[str] | None = None,
) -> Operation[Group]:
    """
    Build the group create.

    Returns:
        Operation[Group]: The create group operation.
    """
    if not member_ids:
        raise ValueError("Egnyte requires at least one member to create a group")

    return Operation(
        method="POST",
        path="/v2/groups",
        body=GroupRequest(
            display_name=display_name,
            members=[MemberRef(value=user_id) for user_id in member_ids],
            owners=owners,
        ),
        parse=model(Group),
    )


# -----------------------------------------------------------------------------
# OPERATION: replace_group
# -----------------------------------------------------------------------------


def replace_group(
    group_id: str,
    display_name: str,
    member_ids: list[int],
    *,
    owners: list[str] | None = None,
) -> Operation[Group]:
    """
    Build the full group update, which overwrites the name and membership.

    Returns:
        Operation[Group]: The replace group operation.
    """
    return Operation(
        method="PUT",
        path=f"/v2/groups/{encode_id(group_id)}",
        body=GroupRequest(
            display_name=display_name,
            members=[MemberRef(value=user_id) for user_id in member_ids],
            owners=owners,
        ),
        parse=model(Group),
    )


# -----------------------------------------------------------------------------
# OPERATION: update_group
# -----------------------------------------------------------------------------


def update_group(
    group_id: str,
    *,
    display_name: str | None = None,
    add_member_ids: list[int] | None = None,
    remove_member_ids: list[int] | None = None,
    add_owners: list[str] | None = None,
) -> Operation[Group]:
    """
    Build the partial group update: rename, and add or remove members.

    Returns:
        Operation[Group]: The update group operation.
    """
    members = [MemberRef(value=user_id) for user_id in add_member_ids or []] + [
        MemberRef(value=user_id, operation="delete")
        for user_id in remove_member_ids or []
    ]
    request = GroupRequest(
        display_name=display_name,
        members=members or None,
        owners=add_owners,
    )
    if not request.model_dump(exclude_none=True):
        raise ValueError("update_group needs at least one change")

    return Operation(
        method="PATCH",
        path=f"/v2/groups/{encode_id(group_id)}",
        body=request,
        parse=model(Group),
    )


# -----------------------------------------------------------------------------
# OPERATION: delete_group
# -----------------------------------------------------------------------------


def delete_group(group_id: str) -> Operation[None]:
    """
    Build the group delete.

    Returns:
        Operation[None]: The delete group operation.
    """
    return Operation(
        method="DELETE", path=f"/v2/groups/{encode_id(group_id)}", parse=empty
    )
