import hmac

from pydantic import TypeAdapter

from egnyte_client.operations.generic import (
    Operation,
    empty,
    encode_id,
    model,
    normalize_path,
)
from egnyte_client.schemas.webhook import (
    MAX_WEBHOOK_PATHS,
    Webhook,
    WebhookDetails,
    WebhookEventType,
    WebhookRequest,
    WebhookStatusRequest,
)

WEBHOOKS = "/v1/webhooks"

_WEBHOOK_LIST = TypeAdapter(list[Webhook])


def _webhook(webhook_id: str) -> str:
    return f"{WEBHOOKS}/{encode_id(webhook_id)}"


def _join_paths(paths: list[str] | None) -> str | None:
    """
    Join folder paths into the comma-separated filter Egnyte takes.

    Returns:
        str | None: The filter, or None to watch the whole domain.
    """
    if not paths:
        return None
    if len(paths) > MAX_WEBHOOK_PATHS:
        raise ValueError(f"A webhook watches at most {MAX_WEBHOOK_PATHS} paths")
    normalized = [normalize_path(path) for path in paths]
    if any("," in path for path in normalized):
        raise ValueError("Webhook paths cannot contain a comma")
    return ",".join(normalized)


def _event_types(
    event_types: list[WebhookEventType] | None,
) -> list[WebhookEventType] | None:
    if event_types is not None and not event_types:
        raise ValueError("event_types needs at least one event type when given")
    return event_types


# -----------------------------------------------------------------------------
# OPERATION: create_webhook
# -----------------------------------------------------------------------------


def create_webhook(
    url: str,
    *,
    event_types: list[WebhookEventType] | None = None,
    paths: list[str] | None = None,
    auth_header: str | None = None,
) -> Operation[Webhook]:
    """
    Build the webhook registration.

    Returns:
        Operation[Webhook]: The create webhook operation.
    """
    return Operation(
        method="POST",
        path=WEBHOOKS,
        body=WebhookRequest(
            url=url,
            event_type=_event_types(event_types),
            path=_join_paths(paths),
            auth_header=auth_header,
        ),
        parse=model(Webhook),
    )


# -----------------------------------------------------------------------------
# OPERATION: list_webhooks
# -----------------------------------------------------------------------------


def list_webhooks() -> Operation[list[Webhook]]:
    """
    Build the webhook listing.

    Returns:
        Operation[list[Webhook]]: The list webhooks operation.
    """
    return Operation(
        method="GET",
        path=WEBHOOKS,
        parse=lambda response: _WEBHOOK_LIST.validate_json(response.content),
    )


# -----------------------------------------------------------------------------
# OPERATION: get_webhook
# -----------------------------------------------------------------------------


def get_webhook(webhook_id: str) -> Operation[WebhookDetails]:
    """
    Build the webhook read, with its configuration.

    Returns:
        Operation[WebhookDetails]: The get webhook operation.
    """
    return Operation(
        method="GET",
        path=f"{_webhook(webhook_id)}/details",
        parse=model(WebhookDetails),
    )


# -----------------------------------------------------------------------------
# OPERATION: get_webhook_status
# -----------------------------------------------------------------------------


def get_webhook_status(webhook_id: str) -> Operation[Webhook]:
    """
    Build the webhook status read.

    Returns:
        Operation[Webhook]: The get webhook status operation.
    """
    return Operation(
        method="GET", path=f"{_webhook(webhook_id)}/status", parse=model(Webhook)
    )


# -----------------------------------------------------------------------------
# OPERATION: set_webhook_status
# -----------------------------------------------------------------------------


def set_webhook_status(webhook_id: str, enabled: bool) -> Operation[Webhook]:
    """
    Build the webhook enable or disable.

    Returns:
        Operation[Webhook]: The set webhook status operation.
    """
    return Operation(
        method="POST",
        path=f"{_webhook(webhook_id)}/status",
        body=WebhookStatusRequest(status="enabled" if enabled else "disabled"),
        parse=model(Webhook),
    )


# -----------------------------------------------------------------------------
# OPERATION: update_webhook
# -----------------------------------------------------------------------------


def update_webhook(
    webhook_id: str,
    url: str,
    *,
    event_types: list[WebhookEventType] | None = None,
    paths: list[str] | None = None,
    auth_header: str | None = None,
    enabled: bool | None = None,
) -> Operation[None]:
    """
    Build the webhook reconfiguration.

    Returns:
        Operation[None]: The update webhook operation.
    """
    status = None if enabled is None else ("enabled" if enabled else "disabled")
    return Operation(
        method="PUT",
        path=_webhook(webhook_id),
        body=WebhookRequest(
            url=url,
            event_type=_event_types(event_types),
            path=_join_paths(paths),
            auth_header=auth_header,
            status=status,
        ),
        parse=empty,
    )


# -----------------------------------------------------------------------------
# OPERATION: delete_webhook
# -----------------------------------------------------------------------------


def delete_webhook(webhook_id: str) -> Operation[None]:
    """
    Build the webhook delete.

    Returns:
        Operation[None]: The delete webhook operation.
    """
    return Operation(method="DELETE", path=_webhook(webhook_id), parse=empty)


# =============================================================================
# FUNCTION: verify_webhook_authorization
# =============================================================================


def verify_webhook_authorization(authorization: str | None, auth_header: str) -> bool:
    """
    Check that a delivery carries the `auth_header` its webhook was given.

    Egnyte does not sign deliveries; it sends the `auth_header` set at
    registration as the `Authorization` header of every POST. Pass that
    header's value (None when absent) and the expected value. The comparison
    takes constant time, so it does not leak the secret through timing.

    Returns:
        bool: Whether the delivery is authentic.
    """
    if authorization is None or not auth_header:
        return False
    return hmac.compare_digest(authorization.encode(), auth_header.encode())
