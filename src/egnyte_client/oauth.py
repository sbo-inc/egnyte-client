from urllib.parse import quote, urlencode

from egnyte_client.transport import normalize_domain

# =============================================================================
# FUNCTION: build_authorization_url
# =============================================================================


def build_authorization_url(
    domain: str,
    client_id: str,
    redirect_uri: str,
    *,
    scope: list[str] | None = None,
    state: str | None = None,
    implicit: bool = False,
) -> str:
    """
    Build the URL that starts Egnyte's OAuth 2.0 sign-in in a browser.

    Send the user to it; Egnyte redirects back to `redirect_uri` with a `code`
    (exchange it with `EgnyteClient.exchange_authorization_code`) and the
    `state` you passed. With `implicit=True` the redirect carries the access
    token itself in the URL fragment instead, and no refresh token.

    `redirect_uri` must be HTTPS and match the callback registered on the API
    key. `scope` lists scopes such as `Egnyte.filesystem`; Egnyte requires
    scoped tokens for apps approved for production. Use an unguessable `state`
    and check it on the redirect.

    Returns:
        str: The authorization URL.
    """
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "token" if implicit else "code",
    }
    if scope:
        params["scope"] = " ".join(scope)
    if state:
        params["state"] = state
    query = urlencode(params, quote_via=quote)
    return f"{normalize_domain(domain)}/puboauth/token?{query}"
