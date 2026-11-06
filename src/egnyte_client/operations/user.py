from egnyte_client.operations.generic import (
    Operation,
    empty,
    encode_id,
    model,
    query,
    resources,
    scim_filter,
)
from egnyte_client.schemas.user import (
    AuthType,
    CreateUserRequest,
    UpdateUserRequest,
    User,
    UserNameRequest,
    UserType,
)

# -----------------------------------------------------------------------------
# OPERATION: list_users
# -----------------------------------------------------------------------------


def list_users(
    *,
    filter_by_user_name: str | None = None,
    filter_by_email: str | None = None,
    filter_by_external_id: str | None = None,
    start_index: int | None = None,
    count: int | None = None,
) -> Operation[list[User]]:
    """
    Build one page of the user listing.

    Returns:
        Operation[list[User]]: The list users operation.
    """
    return Operation(
        method="GET",
        path="/v2/users",
        params=query(
            filter=scim_filter(
                userName=("eq", filter_by_user_name),
                email=("eq", filter_by_email),
                externalId=("eq", filter_by_external_id),
            ),
            startIndex=start_index,
            count=count,
        ),
        parse=resources(User),
    )


# -----------------------------------------------------------------------------
# OPERATION: get_user
# -----------------------------------------------------------------------------


def get_user(user_id: int) -> Operation[User]:
    """
    Build the user read.

    Returns:
        Operation[User]: The get user operation.
    """
    return Operation(
        method="GET", path=f"/v2/users/{encode_id(user_id)}", parse=model(User)
    )


# -----------------------------------------------------------------------------
# OPERATION: create_user
# -----------------------------------------------------------------------------


def create_user(
    user_name: str,
    email: str,
    given_name: str,
    family_name: str,
    *,
    auth_type: AuthType,
    user_type: UserType,
    active: bool = True,
    send_invite: bool | None = None,
    external_id: str | None = None,
    is_service_account: bool | None = None,
    language: str | None = None,
    role: str | None = None,
    idp_user_id: str | None = None,
    user_principal_name: str | None = None,
) -> Operation[User]:
    """
    Build the user create.

    Returns:
        Operation[User]: The create user operation.
    """
    return Operation(
        method="POST",
        path="/v2/users",
        body=CreateUserRequest(
            user_name=user_name,
            email=email,
            name=UserNameRequest(given_name=given_name, family_name=family_name),
            active=active,
            auth_type=auth_type,
            user_type=user_type,
            send_invite=send_invite,
            external_id=external_id,
            is_service_account=is_service_account,
            language=language,
            role=role,
            idp_user_id=idp_user_id,
            user_principal_name=user_principal_name,
        ),
        parse=model(User),
    )


# -----------------------------------------------------------------------------
# OPERATION: update_user
# -----------------------------------------------------------------------------


def update_user(
    user_id: int,
    *,
    email: str | None = None,
    given_name: str | None = None,
    family_name: str | None = None,
    active: bool | None = None,
    auth_type: AuthType | None = None,
    user_type: UserType | None = None,
    send_invite: bool | None = None,
    language: str | None = None,
    role: str | None = None,
    idp_user_id: str | None = None,
    user_principal_name: str | None = None,
) -> Operation[User]:
    """
    Build the partial user update; only the given fields change.

    Returns:
        Operation[User]: The update user operation.
    """
    name = (
        UserNameRequest(given_name=given_name, family_name=family_name)
        if given_name is not None or family_name is not None
        else None
    )
    request = UpdateUserRequest(
        email=email,
        name=name,
        active=active,
        auth_type=auth_type,
        user_type=user_type,
        send_invite=send_invite,
        language=language,
        role=role,
        idp_user_id=idp_user_id,
        user_principal_name=user_principal_name,
    )
    changed = request.model_dump(exclude_none=True)
    if not changed:
        raise ValueError("update_user needs at least one field to change")
    if set(changed) == {"send_invite"}:
        raise ValueError("send_invite cannot be the only field in an update")

    return Operation(
        method="PATCH",
        path=f"/v2/users/{encode_id(user_id)}",
        body=request,
        parse=model(User),
    )


# -----------------------------------------------------------------------------
# OPERATION: delete_user
# -----------------------------------------------------------------------------


def delete_user(user_id: int) -> Operation[None]:
    """
    Build the user delete.

    Returns:
        Operation[None]: The delete user operation.
    """
    return Operation(
        method="DELETE", path=f"/v2/users/{encode_id(user_id)}", parse=empty
    )
