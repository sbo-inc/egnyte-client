from urllib.parse import urlencode

from egnyte_client.operations.generic import Operation, empty, model
from egnyte_client.schemas.auth import TokenInfo, UserInfo

# -----------------------------------------------------------------------------
# OPERATION: get_user_info
# -----------------------------------------------------------------------------


def get_user_info() -> Operation[UserInfo]:
    """
    Build the user-info operation.

    Returns:
        Operation[UserInfo]: The user-info operation.
    """
    return Operation(method="GET", path="/v1/userinfo", parse=model(UserInfo))


# -----------------------------------------------------------------------------
# OPERATION: get_token_info
# -----------------------------------------------------------------------------


def get_token_info() -> Operation[TokenInfo]:
    """
    Build the token inspection (`whoami`).

    Returns:
        Operation[TokenInfo]: The token info operation.
    """
    return Operation(method="GET", path="/v1/whoami", parse=model(TokenInfo))


# -----------------------------------------------------------------------------
# OPERATION: revoke_token
# -----------------------------------------------------------------------------


def revoke_token(token: str, client_secret: str) -> Operation[None]:
    """
    Build the token revocation, sent form-encoded.

    Returns:
        Operation[None]: The revoke operation.
    """
    return Operation(
        method="POST",
        path="/v1/tokens/revoke",
        content=urlencode({"token": token, "client_secret": client_secret}).encode(),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        parse=empty,
    )
