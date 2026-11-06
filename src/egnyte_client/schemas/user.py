from datetime import datetime
from typing import Literal

from pydantic import Field

from egnyte_client.schemas.generic import GenericBaseModel

type AuthType = Literal["egnyte", "sso", "ad"]
type UserType = Literal["admin", "power", "standard"]

# =============================================================================
# CLASS: UserName
# =============================================================================


class UserName(GenericBaseModel):
    given_name: str | None = Field(
        default=None,
        alias="givenName",
        description="Given name.",
    )
    family_name: str | None = Field(
        default=None,
        alias="familyName",
        description="Family name.",
    )
    formatted: str | None = Field(
        default=None,
        description="Full display name.",
    )


# =============================================================================
# CLASS: UserGroup
# =============================================================================


class UserGroup(GenericBaseModel):
    """
    A group the user belongs to.
    """

    id: str = Field(
        alias="value",
        description="Group ID.",
    )
    display_name: str = Field(
        alias="displayName",
        description="Group name.",
    )


# =============================================================================
# CLASS: User
# =============================================================================


class User(GenericBaseModel):
    """
    A user from the v2 User Management API.
    """

    id: int = Field(
        description="Numeric user ID.",
    )
    user_name: str = Field(
        alias="userName",
        description="Username.",
    )
    email: str = Field(
        description="Email address.",
    )
    name: UserName = Field(
        default_factory=UserName,
        description="Given, family, and formatted name.",
    )
    external_id: str | None = Field(
        default=None,
        alias="externalId",
        description="Immutable external identifier, such as an AD SID.",
    )
    active: bool | None = Field(
        default=None,
        description="Whether the user is active.",
    )
    locked: bool | None = Field(
        default=None,
        description="Whether the user is locked out.",
    )
    email_change_pending: bool | None = Field(
        default=None,
        alias="emailChangePending",
        description="Whether an email change awaits confirmation.",
    )
    auth_type: str | None = Field(
        default=None,
        alias="authType",
        description="egnyte, sso, or ad.",
    )
    user_type: str | None = Field(
        default=None,
        alias="userType",
        description="admin, power, or standard.",
    )
    role: str | None = Field(
        default=None,
        description="Role name, for power users.",
    )
    idp_user_id: str | None = Field(
        default=None,
        alias="idpUserId",
        description="Identity-provider user ID, for SSO users.",
    )
    user_principal_name: str | None = Field(
        default=None,
        alias="userPrincipalName",
        description="AD user principal name.",
    )
    is_service_account: bool | None = Field(
        default=None,
        alias="isServiceAccount",
        description="Whether the user is a service account.",
    )
    language: str | None = Field(
        default=None,
        description="Language preference, where the Language Pack is enabled.",
    )
    created_date: datetime | None = Field(
        default=None,
        alias="createdDate",
        description="When the user was created.",
    )
    last_modification_date: datetime | None = Field(
        default=None,
        alias="lastModificationDate",
        description="When the user was last changed.",
    )
    last_active_date: datetime | None = Field(
        default=None,
        alias="lastActiveDate",
        description="When the user was last active.",
    )
    expiry_date: datetime | None = Field(
        default=None,
        alias="expiryDate",
        description="When the user expires, if set.",
    )
    delete_on_expiry: bool | None = Field(
        default=None,
        alias="deleteOnExpiry",
        description="Whether the user is deleted on expiry.",
    )
    groups: list[UserGroup] = Field(
        default_factory=list,
        description="Groups the user belongs to (single-user reads only).",
    )


# =============================================================================
# CLASS: UserNameRequest
# =============================================================================


class UserNameRequest(GenericBaseModel):
    given_name: str | None = Field(default=None, alias="givenName")
    family_name: str | None = Field(default=None, alias="familyName")


# =============================================================================
# CLASS: CreateUserRequest
# =============================================================================


class CreateUserRequest(GenericBaseModel):
    """
    Request body for creating a user.
    """

    user_name: str = Field(alias="userName")
    email: str
    name: UserNameRequest
    active: bool
    auth_type: AuthType = Field(alias="authType")
    user_type: UserType = Field(alias="userType")
    external_id: str | None = Field(default=None, alias="externalId")
    send_invite: bool | None = Field(default=None, alias="sendInvite")
    is_service_account: bool | None = Field(default=None, alias="isServiceAccount")
    language: str | None = None
    role: str | None = None
    idp_user_id: str | None = Field(default=None, alias="idpUserId")
    user_principal_name: str | None = Field(default=None, alias="userPrincipalName")


# =============================================================================
# CLASS: UpdateUserRequest
# =============================================================================


class UpdateUserRequest(GenericBaseModel):
    """
    Request body for a partial user update; unset fields are left alone.
    """

    email: str | None = None
    name: UserNameRequest | None = None
    active: bool | None = None
    auth_type: AuthType | None = Field(default=None, alias="authType")
    user_type: UserType | None = Field(default=None, alias="userType")
    send_invite: bool | None = Field(default=None, alias="sendInvite")
    language: str | None = None
    role: str | None = None
    idp_user_id: str | None = Field(default=None, alias="idpUserId")
    user_principal_name: str | None = Field(default=None, alias="userPrincipalName")
