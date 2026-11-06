from pydantic import Field

from egnyte_client.schemas.generic import GenericBaseModel

# =============================================================================
# CLASS: OAuthToken
# =============================================================================


class OAuthToken(GenericBaseModel):
    """
    Token pair returned by `/puboauth/token`.
    """

    access_token: str = Field(
        description="Bearer token sent on every API request.",
    )
    refresh_token: str | None = Field(
        default=None,
        description="Token exchanged for a new pair once the access token expires.",
    )
    token_type: str = Field(
        default="bearer",
        description="Token type; always bearer.",
    )
    expires_in: int | None = Field(
        default=None,
        description="Seconds until the access token expires (30 days).",
    )


# =============================================================================
# CLASS: UserInfo
# =============================================================================


class UserInfo(GenericBaseModel):
    """
    The user the access token belongs to, from `/v1/userinfo`.
    """

    id: int = Field(
        description="Numeric user ID.",
    )
    username: str = Field(
        description="Egnyte username.",
    )
    first_name: str | None = Field(
        default=None,
        description="Given name.",
    )
    last_name: str | None = Field(
        default=None,
        description="Family name.",
    )
    email: str | None = Field(
        default=None,
        description="Email address.",
    )
    user_type: str | None = Field(
        default=None,
        description="admin, power, or standard.",
    )


# =============================================================================
# CLASS: TokenInfo
# =============================================================================


class TokenInfo(GenericBaseModel):
    """
    What an access token grants, from `/v1/whoami`.
    """

    client_id: str = Field(
        alias="clientId",
        description="API key the token was issued to.",
    )
    username: str = Field(
        description="User the token acts as.",
    )
    domain: str = Field(
        description="Egnyte domain the token is valid for.",
    )
    scopes: list[str] = Field(
        default_factory=list,
        description="Granted scopes; empty means unscoped (global) access.",
    )
